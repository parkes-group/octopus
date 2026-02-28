"""
Export tariff API client.

Discovers and fetches export product pricing (Fixed and Agile Outgoing).
Uses OctopusAPIClient for HTTP; builds domain objects from responses.

Cache: Mirrors import architecture. Uses CacheManager with same structure:
{ prices, fetched_at, expires_at }. File naming: {product_code}_{region_code}.json
e.g. AGILE-OUTGOING-19-05-13_A.json, OUTGOING-19-05-13_A.json
"""
import logging
import requests
from datetime import datetime, timezone

from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.export_tariff import (
    AgileOutgoingTariff,
    ExportProduct,
    FixedExportTariff,
    HalfHourlySlot,
)


# Display names for export product discovery (from Octopus API).
AGILE_OUTGOING_DISPLAY_NAME = "Agile Outgoing Octopus"
FIXED_EXPORT_DISPLAY_NAME = "Outgoing Octopus"

logger = logging.getLogger(__name__)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        s = (value or "").replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError, TypeError):
        return None


def discover_export_products() -> list[ExportProduct]:
    """
    Discover active export products from Octopus API.

    Matches display_name exactly:
    - "Agile Outgoing Octopus" -> agile_outgoing
    - "Outgoing Octopus" -> fixed

    Filters by availability:
    - available_from <= today
    - available_to is null OR available_to > today

    Returns:
        list[ExportProduct]: Discovered products (no ordering guarantee)
    """
    config = OctopusAPIClient._get_config()
    url = config["get_products_url"]()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    all_products: list[ExportProduct] = []
    next_url = url

    while next_url:
        resp = requests.get(next_url, timeout=config["timeout"])
        resp.raise_for_status()
        data = resp.json()
        products = data.get("results", [])
        next_url = data.get("next")

        for p in products:
            display = (p.get("display_name") or "").strip()
            if display != AGILE_OUTGOING_DISPLAY_NAME and display != FIXED_EXPORT_DISPLAY_NAME:
                continue

            # Availability: support both available_* and valid_* (API may vary)
            from_str = p.get("available_from") or p.get("valid_from")
            to_str = p.get("available_to") or p.get("valid_to")

            from_dt = _parse_iso_datetime(from_str)
            if from_dt is not None and from_dt > today:
                continue
            to_dt = _parse_iso_datetime(to_str)
            if to_dt is not None and to_dt <= today:
                continue

            tariff_type: str = "agile_outgoing" if display == AGILE_OUTGOING_DISPLAY_NAME else "fixed"
            all_products.append(
                ExportProduct(
                    code=p.get("code", ""),
                    display_name=display,
                    tariff_type=tariff_type,
                    full_name=p.get("full_name"),
                )
            )

    return all_products


def get_product_tariffs(product_code: str) -> dict | None:
    """
    Fetch product detail including tariffs per region.

    Returns the raw API response for single_register_electricity_tariffs,
    or None on error.
    """
    from app.config import Config

    config = OctopusAPIClient._get_config()
    base = getattr(Config, "OCTOPUS_API_BASE_URL", "https://api.octopus.energy/v1")
    url = f"{base}/products/{product_code}/"
    resp = requests.get(url, timeout=config["timeout"])
    resp.raise_for_status()
    return resp.json()


def get_unit_rates(
    product_code: str,
    tariff_code: str,
    period_from_utc: datetime,
    page_size: int = 1500,
) -> list[dict]:
    """
    Fetch half-hourly unit rates with pagination.

    Args:
        product_code: Product code
        tariff_code: Full tariff code from product tariffs
        period_from_utc: Start of period (UTC)
        page_size: Max results per page (API allows up to 1500)

    Returns:
        List of rate dicts with value_exc_vat, value_inc_vat, valid_from, valid_to
    """
    config = OctopusAPIClient._get_config()
    url = config["get_unit_rates_url"](product_code, tariff_code)
    period_str = period_from_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {"period_from": period_str, "page_size": page_size}
    all_results: list[dict] = []
    next_url: str | None = url

    while next_url:
        resp = requests.get(next_url, params=params if next_url == url else None, timeout=config["timeout"])
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        all_results.extend(results)
        next_url = data.get("next")
        params = None  # next URL is fully qualified

    return all_results


def _fixed_cache_to_tariff(product_code: str, region_code: str, cached: list) -> FixedExportTariff | None:
    """Build FixedExportTariff from cached fixed-format prices (single element with tariff_code)."""
    if not cached or len(cached) != 1:
        return None
    p = cached[0]
    if "tariff_code" not in p or "value_exc_vat" not in p or "value_inc_vat" not in p:
        return None
    return FixedExportTariff(
        product_code=p.get("product_code", product_code),
        region_code=p.get("region_code", region_code),
        tariff_code=str(p["tariff_code"]),
        rate_p_per_kwh_exc_vat=float(p["value_exc_vat"]),
        rate_p_per_kwh_inc_vat=float(p["value_inc_vat"]),
    )


def _tariff_to_fixed_cache(tariff: FixedExportTariff) -> list:
    """Serialize FixedExportTariff to cache prices format."""
    return [{
        "value_exc_vat": tariff.rate_p_per_kwh_exc_vat,
        "value_inc_vat": tariff.rate_p_per_kwh_inc_vat,
        "tariff_code": tariff.tariff_code,
        "product_code": tariff.product_code,
        "region_code": tariff.region_code,
    }]


def fetch_fixed_export_tariff(
    product_code: str,
    region_code: str,
) -> FixedExportTariff | None:
    """
    Build FixedExportTariff for a region from product tariffs.

    Uses standard_unit_rate from product tariff detail.
    Cache-first: if valid cache exists, return from cache. Otherwise fetch and cache.
    """
    cached = CacheManager.get_cached_prices(product_code, region_code)
    if cached is not None:
        tariff = _fixed_cache_to_tariff(product_code, region_code, cached)
        if tariff is not None:
            logger.debug(f"Export fixed cache hit for {product_code} {region_code}")
            return tariff
        # Cached data not in fixed format (e.g. wrong product) - fall through to fetch

    detail = get_product_tariffs(product_code)
    if not detail:
        return None

    tariffs = detail.get("single_register_electricity_tariffs") or {}
    region_key = f"_{region_code}" if not region_code.startswith("_") else region_code
    region_tariffs = tariffs.get(region_key)
    if not region_tariffs:
        return None

    # Use direct_debit_monthly as canonical (or first available)
    dd = region_tariffs.get("direct_debit_monthly")
    if not dd:
        keys = [k for k in region_tariffs if isinstance(region_tariffs[k], dict)]
        if not keys:
            return None
        dd = region_tariffs.get(keys[0])

    rate_exc = dd.get("standard_unit_rate_exc_vat")
    rate_inc = dd.get("standard_unit_rate_inc_vat")
    tariff_code = dd.get("code")
    if rate_exc is None or rate_inc is None or not tariff_code:
        return None

    tariff = FixedExportTariff(
        product_code=product_code,
        region_code=region_code,
        tariff_code=str(tariff_code),
        rate_p_per_kwh_exc_vat=float(rate_exc),
        rate_p_per_kwh_inc_vat=float(rate_inc),
    )
    from app.config import Config
    expiry_mins = Config.EXPORT_FIXED_CACHE_EXPIRY_MINUTES
    CacheManager.cache_prices(product_code, region_code, _tariff_to_fixed_cache(tariff), expiry_minutes=expiry_mins)
    return tariff


def fetch_agile_outgoing_tariff(
    product_code: str,
    region_code: str,
    period_from_utc: datetime,
) -> AgileOutgoingTariff | None:
    """
    Build AgileOutgoingTariff for a region by fetching half-hourly unit rates.

    Cache-first: if valid cache exists with time-series data, return from cache.
    Otherwise fetch and cache. Expiry uses same edge-price logic as import.
    """
    cached = CacheManager.get_cached_prices(product_code, region_code)
    if cached is not None and len(cached) > 0:
        # Verify cached data has time-series format (valid_from, valid_to)
        first = cached[0]
        if "valid_from" in first and "valid_to" in first:
            logger.debug(f"Export agile cache hit for {product_code} {region_code}")
            # Tariff code stored in first slot when cached (avoids API call on hit)
            tariff_code = first.get("_tariff_code", "")
            slots = [
                HalfHourlySlot(
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    value_exc_vat=float(r.get("value_exc_vat", 0)),
                    value_inc_vat=float(r.get("value_inc_vat", 0)),
                )
                for r in cached
            ]
            return AgileOutgoingTariff(
                product_code=product_code,
                region_code=region_code,
                tariff_code=str(tariff_code),
                slots=slots,
            )

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
        if not keys:
            return None
        dd = region_tariffs.get(keys[0])
    tariff_code = dd.get("code")
    if not tariff_code:
        return None

    raw = get_unit_rates(product_code, tariff_code, period_from_utc)
    slots = [
        HalfHourlySlot(
            valid_from=r["valid_from"],
            valid_to=r["valid_to"],
            value_exc_vat=float(r.get("value_exc_vat", 0)),
            value_inc_vat=float(r.get("value_inc_vat", 0)),
        )
        for r in raw
    ]

    tariff = AgileOutgoingTariff(
        product_code=product_code,
        region_code=region_code,
        tariff_code=str(tariff_code),
        slots=slots,
    )
    if raw:
        to_cache = [dict(r) for r in raw]
        if to_cache:
            to_cache[0]["_tariff_code"] = tariff_code  # store for cache-hit rebuild
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(raw[0], raw[-1])
        if expires_at is not None:
            CacheManager.cache_prices(product_code, region_code, to_cache, expires_at=expires_at)
        else:
            CacheManager.cache_prices(product_code, region_code, to_cache)
    return tariff
