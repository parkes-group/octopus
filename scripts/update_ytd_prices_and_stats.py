"""
Scheduled job: update year-to-date raw prices + derived stats + app cache.

Intended for PythonAnywhere Scheduled Tasks at 19:05 Europe/London.

This job is safe to re-run:
- It fetches incrementally from the last known timestamp forward
- It de-duplicates by valid_from
- It writes files atomically
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, time, timezone
from pathlib import Path
from typing import Optional

import requests
from logging.handlers import TimedRotatingFileHandler

# Add the project root to sys.path so `import app.*` works when executed from scripts/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import Config
from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.export_client import (
    discover_export_products,
    fetch_agile_outgoing_tariff,
    fetch_fixed_export_tariff,
)
from app.stats_calculator import StatsCalculator
from app.timezone_utils import get_uk_now
from zoneinfo import ZoneInfo
from app.ytd_update_job import (
    FetchPlan,
    determine_fetch_plan,
    dedupe_sort_prices,
    expected_slot_count,
    validate_price_series,
)


def setup_job_logging() -> logging.Logger:
    """
    Configure logging for the scheduled job.

    - Always logs to console (PythonAnywhere task output)
    - Also logs to logs/YTD_Update.log (same directory as logs/app.log)
    """
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level_str = getattr(Config, "LOG_LEVEL", "INFO")
    log_level = getattr(logging, str(log_level_str).upper(), logging.INFO)

    job_logger = logging.getLogger("ytd_update_job")
    job_logger.setLevel(log_level)
    job_logger.propagate = False

    # Prevent duplicate handlers if script is imported in tests
    if job_logger.handlers:
        return job_logger

    formatter_console = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    formatter_file = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter_console)
    job_logger.addHandler(console_handler)

    file_handler = TimedRotatingFileHandler(
        str(log_dir / "YTD_Update.log"),
        when="midnight",
        interval=1,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter_file)
    job_logger.addHandler(file_handler)

    return job_logger


logger = setup_job_logging()


RAW_BASE_DIR = project_root / "data" / "raw"
STATS_BASE_DIR = project_root / "data" / "stats"


def _raw_file_path(year: int, region: str) -> Path:
    # Prefer year directory layout
    year_dir = RAW_BASE_DIR / str(year)
    return year_dir / f"{region}_{year}.json"


def _load_raw_prices(year: int, region: str) -> tuple[dict, list[dict]]:
    path = _raw_file_path(year, region)
    if not path.exists():
        return {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, data.get("prices", []) or []


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Atomic replace is ideal, but on Windows it can fail if the destination file is open
    # (e.g. in an editor) or briefly locked by antivirus/indexers.
    try:
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.05)
    except PermissionError:
        # Fallback: write directly to the destination file (non-atomic).
        # This is acceptable for local/dev runs and avoids failing the whole job.
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def fetch_prices_paginated_range(product_code: str, region: str, period_from: str, period_to: str, page_size: int = 1000) -> tuple[list[dict], dict]:
    """
    Fetch prices from Octopus for an explicit period range, following pagination until exhausted.
    """
    url = Config.get_prices_url(product_code, region)
    params = {"period_from": period_from, "period_to": period_to, "page_size": page_size}

    pages = 0
    results: list[dict] = []
    next_url: Optional[str] = url
    next_params = params

    while next_url:
        pages += 1
        resp = requests.get(next_url, params=next_params, timeout=Config.OCTOPUS_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
        next_params = None

    meta = {
        "product_code": product_code,
        "region_code": region,
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
        "pages_fetched": pages,
        "total_price_slots": len(results),
    }
    return results, meta


def is_slot_count_reasonable(actual: int, expected: int, *, boundary_slack: int = 2) -> bool:
    """
    Octopus period_from/period_to behaviour can exclude boundary slots even when aligned to 30 minutes.
    In practice we allow a small slack while relying on contiguity + ordering validation to catch real gaps.
    """
    if expected <= 0:
        return True
    return actual >= max(0, expected - boundary_slack)


UK_TZ = ZoneInfo("Europe/London")


def refresh_export_cache(regions: list[str]) -> None:
    """
    Refresh export tariff cache for all regions.
    Agile Outgoing: fetch unit rates for today+tomorrow, cache with edge-price expiry.
    Fixed: fetch product tariffs once, cache rate per region with 24h expiry.
    """
    try:
        products = discover_export_products()
    except Exception as e:
        logger.warning(f"[EXPORT_CACHE] skip discovery failed: {e}")
        return

    agile_product = next((p for p in products if getattr(p, "tariff_type", None) == "agile_outgoing"), None)
    fixed_product = next((p for p in products if getattr(p, "tariff_type", None) == "fixed"), None)

    now_uk = get_uk_now()
    today_uk = now_uk.date()
    tomorrow_uk = today_uk + timedelta(days=1)
    period_from = datetime.combine(today_uk, time(0, 0)).replace(tzinfo=UK_TZ).astimezone(timezone.utc)
    period_to = datetime.combine(tomorrow_uk + timedelta(days=1), time(0, 0)).replace(tzinfo=UK_TZ).astimezone(timezone.utc)

    for region in regions:
        try:
            if agile_product:
                product_code = getattr(agile_product, "code", None) or agile_product.get("code", "")
                if product_code:
                    tariff = fetch_agile_outgoing_tariff(product_code, region, period_from)
                    if tariff:
                        logger.info(f"[EXPORT_CACHE] agile region={region} ok")
                    else:
                        logger.warning(f"[EXPORT_CACHE] agile region={region} no data")
            if fixed_product:
                product_code = getattr(fixed_product, "code", None) or fixed_product.get("code", "")
                if product_code:
                    tariff = fetch_fixed_export_tariff(product_code, region)
                    if tariff:
                        logger.info(f"[EXPORT_CACHE] fixed region={region} ok")
                    else:
                        logger.warning(f"[EXPORT_CACHE] fixed region={region} no data")
        except Exception as e:
            logger.warning(f"[EXPORT_CACHE] region={region} error={e}")


def refresh_cache_for_region(product_code: str, region: str) -> bool:
    """
    Force-refresh the persistent cache file for a region using existing expiry rules.
    """
    api_response = OctopusAPIClient.get_prices(product_code, region)
    prices = api_response.get("results", []) or []
    if not prices:
        raise RuntimeError(f"No prices returned from Octopus for cache refresh: {product_code} {region}")

    first_entry = prices[0]
    last_entry = prices[-1]
    expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
    if expires_at is not None:
        logger.info(f"[CACHE] region={region} strategy=edge_prices expires_at={expires_at.isoformat()}")
        return CacheManager.cache_prices(product_code, region, prices, expires_at=expires_at)
    else:
        logger.info(f"[CACHE] region={region} strategy=fallback_ttl")
        return CacheManager.cache_prices(product_code, region, prices)


RAW_EXPORT_BASE_DIR = project_root / "data" / "raw" / "export"


def _raw_file_path_export(year: int, region: str) -> Path:
    year_dir = RAW_EXPORT_BASE_DIR / str(year)
    return year_dir / f"{region}_{year}.json"


def _load_raw_prices_export(year: int, region: str) -> tuple[dict, list[dict]]:
    path = _raw_file_path_export(year, region)
    if not path.exists():
        return {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, data.get("prices", []) or []


def _get_export_tariff_code(product_code: str, region_code: str) -> Optional[str]:
    """Resolve tariff code for Agile Outgoing in a region from product tariffs."""
    from app.export_client import get_product_tariffs
    detail = get_product_tariffs(product_code)
    if not detail:
        return None
    tariffs = detail.get("single_register_electricity_tariffs") or {}
    region_key = f"_{region_code}" if not region_code.startswith("_") else region_code
    region_tariffs = tariffs.get(region_key)
    if not region_tariffs:
        return None
    dd = region_tariffs.get("direct_debit_monthly")
    if not dd:
        keys = [k for k in region_tariffs if isinstance(region_tariffs[k], dict)]
        dd = region_tariffs.get(keys[0]) if keys else None
    if not dd:
        return None
    return dd.get("code")


def fetch_export_prices_paginated_range(
    product_code: str,
    tariff_code: str,
    region: str,
    period_from: str,
    period_to: str,
    page_size: int = 1000,
) -> tuple[list[dict], dict]:
    """Fetch export (Agile Outgoing) prices for an explicit period range."""
    url = Config.get_unit_rates_url(product_code, tariff_code)
    params = {"period_from": period_from, "period_to": period_to, "page_size": page_size}

    pages = 0
    results: list[dict] = []
    next_url: Optional[str] = url
    next_params = params

    while next_url:
        pages += 1
        resp = requests.get(next_url, params=next_params, timeout=Config.OCTOPUS_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
        next_params = None

    meta = {
        "product_code": product_code,
        "tariff_code": tariff_code,
        "region_code": region,
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
        "pages_fetched": pages,
        "total_price_slots": len(results),
    }
    return results, meta


def _run_import_ytd(
    year: int,
    product_code: str,
    regions: list[str],
    now_uk: datetime,
) -> tuple[list[str], dict[str, str]]:
    """Update import raw data for all regions. Returns (succeeded, failed)."""
    succeeded: list[str] = []
    failed: dict[str, str] = {}

    for region in regions:
        try:
            raw_data, existing_prices = _load_raw_prices(year, region)
            last_before = existing_prices[-1].get("valid_to") if existing_prices else None

            plan = determine_fetch_plan(region=region, existing_prices=existing_prices, now_uk=now_uk)
            if plan is None:
                logger.info(f"[IMPORT] region={region} action=skip reason=already_includes_tomorrow last_valid_to={last_before}")
                errs = validate_price_series(existing_prices)
                if errs:
                    raise RuntimeError(f"validation_failed_without_fetch: {errs[:5]}")
                succeeded.append(region)
                continue

            logger.info(
                f"[IMPORT] region={region} action=fetch reason={plan.reason} "
                f"period_from={plan.period_from_utc_z} period_to={plan.period_to_utc_z} last_valid_to_before={last_before}"
            )

            fetched, meta = fetch_prices_paginated_range(product_code, region, plan.period_from_utc_z, plan.period_to_utc_z)
            fetched = dedupe_sort_prices(fetched)
            expected = expected_slot_count(plan.period_from_utc_z, plan.period_to_utc_z)
            if expected and not is_slot_count_reasonable(len(fetched), expected, boundary_slack=2):
                raise RuntimeError(f"fetched_slot_count_too_low expected~{expected} got={len(fetched)}")
            if expected and len(fetched) < expected:
                logger.warning(
                    f"[IMPORT_WARN] region={region} fetched_less_than_expected expected~{expected} got={len(fetched)} "
                    f"(allowed boundary slack)"
                )

            merged_prices = dedupe_sort_prices([*existing_prices, *fetched])
            errs = validate_price_series(merged_prices)
            if errs:
                raise RuntimeError(f"validation_failed: {errs[:8]}")

            updated = raw_data or {"product_code": product_code, "region_code": region, "year": year}
            updated["product_code"] = product_code
            updated["region_code"] = region
            updated["year"] = year
            updated["prices"] = merged_prices
            updated["total_price_slots"] = len(merged_prices)
            updated["fetched_at"] = datetime.now(timezone.utc).isoformat()
            updated["ytd_update"] = {
                "ran_at_utc": datetime.now(timezone.utc).isoformat(),
                "plan": asdict(plan),
                "ingestion": meta,
                "last_valid_to_before": last_before,
                "last_valid_to_after": merged_prices[-1].get("valid_to") if merged_prices else None,
                "slots_fetched": len(fetched),
            }

            out_path = _raw_file_path(year, region)
            _atomic_write_json(out_path, updated)
            succeeded.append(region)
            logger.info(
                f"[IMPORT_OK] region={region} slots_fetched={len(fetched)} total_slots={len(merged_prices)} "
                f"last_valid_to_after={updated['ytd_update']['last_valid_to_after']}"
            )

        except Exception as e:
            msg = str(e)
            failed[region] = msg
            logger.error(f"[IMPORT_FAIL] region={region} error={msg}", exc_info=True)

    return succeeded, failed


def _run_export_ytd(
    year: int,
    product_code: str,
    regions: list[str],
    now_uk: datetime,
) -> tuple[list[str], dict[str, str]]:
    """Update export raw data for all regions. Returns (succeeded, failed)."""
    succeeded: list[str] = []
    failed: dict[str, str] = {}

    for region in regions:
        try:
            tariff_code = _get_export_tariff_code(product_code, region)
            if not tariff_code:
                raise RuntimeError(f"Could not resolve tariff_code for export product {product_code} region {region}")

            raw_data, existing_prices = _load_raw_prices_export(year, region)
            last_before = existing_prices[-1].get("valid_to") if existing_prices else None

            plan = determine_fetch_plan(region=region, existing_prices=existing_prices, now_uk=now_uk)
            if plan is None:
                logger.info(f"[EXPORT] region={region} action=skip reason=already_includes_tomorrow last_valid_to={last_before}")
                errs = validate_price_series(existing_prices)
                if errs:
                    raise RuntimeError(f"validation_failed_without_fetch: {errs[:5]}")
                succeeded.append(region)
                continue

            logger.info(
                f"[EXPORT] region={region} action=fetch reason={plan.reason} "
                f"period_from={plan.period_from_utc_z} period_to={plan.period_to_utc_z} last_valid_to_before={last_before}"
            )

            fetched, meta = fetch_export_prices_paginated_range(
                product_code, tariff_code, region, plan.period_from_utc_z, plan.period_to_utc_z
            )
            fetched = dedupe_sort_prices(fetched)
            expected = expected_slot_count(plan.period_from_utc_z, plan.period_to_utc_z)
            if expected and not is_slot_count_reasonable(len(fetched), expected, boundary_slack=2):
                raise RuntimeError(f"fetched_slot_count_too_low expected~{expected} got={len(fetched)}")
            if expected and len(fetched) < expected:
                logger.warning(
                    f"[EXPORT_WARN] region={region} fetched_less_than_expected expected~{expected} got={len(fetched)} "
                    f"(allowed boundary slack)"
                )

            merged_prices = dedupe_sort_prices([*existing_prices, *fetched])
            errs = validate_price_series(merged_prices)
            if errs:
                raise RuntimeError(f"validation_failed: {errs[:8]}")

            updated = raw_data or {
                "product_code": product_code,
                "tariff_code": tariff_code,
                "region_code": region,
                "year": year,
                "tariff_type": "export",
            }
            updated["product_code"] = product_code
            updated["tariff_code"] = tariff_code
            updated["region_code"] = region
            updated["year"] = year
            updated["tariff_type"] = "export"
            updated["prices"] = merged_prices
            updated["total_price_slots"] = len(merged_prices)
            updated["fetched_at"] = datetime.now(timezone.utc).isoformat()
            updated["ytd_update"] = {
                "ran_at_utc": datetime.now(timezone.utc).isoformat(),
                "plan": asdict(plan),
                "ingestion": meta,
                "last_valid_to_before": last_before,
                "last_valid_to_after": merged_prices[-1].get("valid_to") if merged_prices else None,
                "slots_fetched": len(fetched),
            }

            out_path = _raw_file_path_export(year, region)
            _atomic_write_json(out_path, updated)
            succeeded.append(region)
            logger.info(
                f"[EXPORT_OK] region={region} slots_fetched={len(fetched)} total_slots={len(merged_prices)} "
                f"last_valid_to_after={updated['ytd_update']['last_valid_to_after']}"
            )

        except Exception as e:
            msg = str(e)
            failed[region] = msg
            logger.error(f"[EXPORT_FAIL] region={region} error={msg}", exc_info=True)

    return succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Update YTD raw prices + stats + cache")
    parser.add_argument("--year", type=int, default=2026, help="Year to update (default: 2026)")
    parser.add_argument("--product", type=str, default=Config.OCTOPUS_PRODUCT_CODE, help="Octopus import product code")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--export", action="store_true", help="Process export (Agile Outgoing) only")
    group.add_argument("--both", action="store_true", help="Process import and export")
    args = parser.parse_args()

    year = args.year
    mode = "export" if args.export else ("both" if args.both else "import")
    now_uk = get_uk_now()

    # Resolve product code: import uses args.product; export discovers Agile Outgoing
    product_code = args.product
    export_product_code: Optional[str] = None
    if mode in ("export", "both"):
        try:
            products = discover_export_products()
            agile_export = next((p for p in products if getattr(p, "tariff_type", None) == "agile_outgoing"), None)
            if not agile_export:
                logger.error("[JOB_START] No Agile Outgoing product found for export mode")
                return 1
            export_product_code = agile_export.code
        except Exception as e:
            logger.error(f"[JOB_START] Export product discovery failed: {e}", exc_info=True)
            return 1

    logger.info(f"[JOB_START] year={year} mode={mode} now_uk={now_uk.isoformat()} product={product_code}")

    regions = list(Config.OCTOPUS_REGION_NAMES.keys())

    # --- Import raw update ---
    if mode in ("import", "both"):
        succeeded, failed = _run_import_ytd(year, product_code, regions, now_uk)
        if failed:
            logger.error("[ERROR_SUMMARY] Import: one or more regions failed; skipping stats + cache")
            for region, msg in failed.items():
                logger.error(f" - region={region}: {msg}")
            logger.info(f"[JOB_END] status=error mode=import regions_ok={len(succeeded)} regions_failed={len(failed)}")
            return 1

    # --- Export raw update ---
    if mode in ("export", "both"):
        export_succeeded, export_failed = _run_export_ytd(
            year, export_product_code or "", regions, now_uk
        )
        if export_failed:
            logger.error("[ERROR_SUMMARY] Export: one or more regions failed; skipping stats")
            for region, msg in export_failed.items():
                logger.error(f" - region={region}: {msg}")
            logger.info(f"[JOB_END] status=error mode=export regions_ok={len(export_succeeded)} regions_failed={len(export_failed)}")
            return 1

    # --- Import stats ---
    if mode in ("import", "both"):
        logger.info(f"[STATS] start import year={year}")
        try:
            for region in regions:
                stats = StatsCalculator.calculate_year_stats(
                    product_code, region_code=region, year=year, coverage="year_to_date"
                )
                StatsCalculator.save_stats(stats)
            national = StatsCalculator.calculate_national_averages(product_code, year=year)
            StatsCalculator.save_national_stats(national, year=year)
            logger.info(f"[STATS] import ok year={year} output_dir={STATS_BASE_DIR/str(year)}")
        except Exception as e:
            logger.error(f"[STATS] import failed year={year} error={e}", exc_info=True)
            logger.info("[JOB_END] status=error")
            return 1

    # --- Export stats ---
    if mode in ("export", "both"):
        logger.info(f"[STATS] start export year={year}")
        try:
            for region in regions:
                stats = StatsCalculator.calculate_export_year_stats(
                    export_product_code,
                    region_code=region,
                    year=year,
                    coverage="year_to_date",
                )
                if stats is None:
                    raise RuntimeError(f"Export stats failed for region {region} (raw data missing?)")
                StatsCalculator.save_stats(stats, export=True)
            national = StatsCalculator.calculate_national_averages_export(export_product_code, year=year)
            StatsCalculator.save_national_stats(national, year=year, export=True)
            logger.info(f"[STATS] export ok year={year} output_dir={STATS_BASE_DIR/'export'/str(year)}")
        except Exception as e:
            logger.error(f"[STATS] export failed year={year} error={e}", exc_info=True)
            logger.info("[JOB_END] status=error")
            return 1

    # --- Import cache ---
    if mode in ("import", "both"):
        logger.info("[CACHE] start refresh_all_regions (import)")
        try:
            for region in regions:
                refresh_cache_for_region(product_code, region)
            logger.info("[CACHE] ok")
        except Exception as e:
            logger.error(f"[CACHE] failed error={e}", exc_info=True)
            logger.info("[JOB_END] status=error")
            return 1

    # --- Export cache (Agile Outgoing + Fixed for live pages) ---
    if mode in ("export", "both"):
        logger.info("[EXPORT_CACHE] start refresh_all_regions")
        try:
            refresh_export_cache(regions)
            logger.info("[EXPORT_CACHE] ok")
        except Exception as e:
            logger.warning(f"[EXPORT_CACHE] failed (non-fatal): {e}", exc_info=True)

    logger.info(f"[JOB_END] status=ok mode={mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

