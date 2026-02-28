"""
Script to download raw half-hourly Agile prices for a given year and store them under data/raw/{YEAR}/.

This script is the **raw data ingestion entry point** for historic stats.

Supports:
- Import: Agile Octopus (default)
- Export: Agile Outgoing (--export flag)

Key responsibilities:
- Build a full-year Octopus API query (explicit UTC range)
- Traverse Octopus pagination until exhausted
- Persist one JSON file per region (overwritten atomically)

Note:
- This script intentionally does not depend on the app's "today prices" API client method, because
  that method is designed for real-time pages and does not accept historic date ranges.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date, timezone

# Add the project root to the path (scripts are in scripts/ subdirectory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import Config
import json
import logging
import time
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

RAW_DATA_BASE_DIR = project_root / "data" / "raw"
RAW_EXPORT_SUBDIR = "export"

def _dt_to_utc_z(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt_utc.isoformat().replace("+00:00", "Z")

def _year_utc_range(year: int, *, year_to_date: bool) -> tuple[str, str]:
    """
    Build an explicit UTC time range for the requested year.

    - Full year: [YYYY-01-01T00:00:00Z, YYYY-12-31T23:59:59Z]
    - Year-to-date (for current year): [YYYY-01-01T00:00:00Z, now_utc]

    Required for correctness: do not rely on Octopus API defaults.

    Returns:
        (period_from, period_to) as ISO-8601 Z strings.
    """
    period_from = f"{year}-01-01T00:00:00Z"
    if year_to_date:
        period_to = _dt_to_utc_z(datetime.now(timezone.utc))
    else:
        period_to = f"{year}-12-31T23:59:59Z"
    return (period_from, period_to)

def _fetch_paginated(
    url: str,
    params: dict,
    region_code: str,
    *,
    page_size: int = 1000,
    sleep_seconds: float = 0.0,
    log_prefix: str = "INGEST",
) -> tuple[list[dict], dict]:
    """
    Generic paginated fetch for Octopus standard-unit-rates endpoint.
    Follows 'next' links until exhausted.
    """
    pages = 0
    results: list[dict] = []
    next_url = url
    next_params = params

    while next_url:
        pages += 1
        logger.info(f"[{log_prefix}] {region_code}: fetching page {pages} ({'with params' if next_params else 'next URL'})")
        response = requests.get(next_url, params=next_params, timeout=Config.OCTOPUS_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        page_results = data.get("results", [])
        results.extend(page_results)
        next_url = data.get("next")
        next_params = None
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return results, {"pages_fetched": pages, "total_price_slots": len(results)}


def fetch_prices_paginated(
    product_code: str,
    region_code: str,
    year: int,
    *,
    year_to_date: bool,
    page_size: int = 1000,
    sleep_seconds: float = 0.0,
) -> tuple[list[dict], dict]:
    """
    Fetch all unit rates for import (Agile Octopus) for the given region + product.
    """
    period_from, period_to = _year_utc_range(year, year_to_date=year_to_date)
    url = Config.get_prices_url(product_code, region_code)
    params = {"period_from": period_from, "period_to": period_to, "page_size": page_size}
    results, fetch_meta = _fetch_paginated(url, params, region_code, page_size=page_size, sleep_seconds=sleep_seconds)
    meta = {
        "product_code": product_code,
        "region_code": region_code,
        "year": year,
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
        **fetch_meta,
    }
    return results, meta


def _get_export_tariff_code(product_code: str, region_code: str) -> str | None:
    """Get tariff code for Agile Outgoing in a region from product tariffs."""
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


def fetch_export_prices_paginated(
    product_code: str,
    tariff_code: str,
    region_code: str,
    year: int,
    *,
    year_to_date: bool,
    page_size: int = 1000,
    sleep_seconds: float = 0.0,
) -> tuple[list[dict], dict]:
    """
    Fetch all unit rates for export (Agile Outgoing) for the given region.
    Uses get_unit_rates_url (same endpoint pattern as import, different path).
    """
    period_from, period_to = _year_utc_range(year, year_to_date=year_to_date)
    url = Config.get_unit_rates_url(product_code, tariff_code)
    params = {"period_from": period_from, "period_to": period_to, "page_size": page_size}
    results, fetch_meta = _fetch_paginated(
        url, params, region_code, page_size=page_size, sleep_seconds=sleep_seconds, log_prefix="EXPORT"
    )
    meta = {
        "product_code": product_code,
        "tariff_code": tariff_code,
        "region_code": region_code,
        "year": year,
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
        **fetch_meta,
    }
    return results, meta

def _sort_and_build_raw_data(all_prices: list, product_code: str, region_code: str, year: int, meta: dict, *, tariff_type: str = "import") -> dict:
    """Sort prices chronologically and build raw data dict. Shared by import and export."""
    try:
        all_prices = sorted(all_prices, key=lambda x: x.get("valid_from", ""))
    except Exception as e:
        logger.warning(f"Error sorting prices for {region_code}: {e}")
    raw_data = {
        "product_code": product_code,
        "region_code": region_code,
        "year": year,
        "tariff_type": tariff_type,
        "prices": all_prices,
        "fetched_at": datetime.now().isoformat(),
        "total_price_slots": len(all_prices),
        "ingestion": meta,
    }
    return raw_data


def download_region_data(product_code, region_code, year=2025, *, year_to_date: bool):
    """
    Download all price data for import (Agile Octopus) for a region for the entire year.
    """
    raw_year_dir = RAW_DATA_BASE_DIR / str(year)
    raw_year_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting full-year download for region {region_code} ({Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')})")

    all_prices, meta = fetch_prices_paginated(
        product_code=product_code,
        region_code=region_code,
        year=year,
        year_to_date=year_to_date,
        page_size=1000,
        sleep_seconds=0.0,
    )
    raw_data = _sort_and_build_raw_data(all_prices, product_code, region_code, year, meta, tariff_type="import")
    logger.info(
        f"Region {region_code}: Downloaded {len(all_prices)} price slots "
        f"(pages={meta.get('pages_fetched')}, range={meta.get('period_from')}..{meta.get('period_to')})"
    )
    return raw_data


def download_region_data_export(product_code: str, region_code: str, year: int = 2025, *, year_to_date: bool) -> dict | None:
    """
    Download all price data for export (Agile Outgoing) for a region for the entire year.
    """
    tariff_code = _get_export_tariff_code(product_code, region_code)
    if not tariff_code:
        logger.error(f"Could not resolve tariff code for export product {product_code} region {region_code}")
        return None

    raw_year_dir = RAW_DATA_BASE_DIR / RAW_EXPORT_SUBDIR / str(year)
    raw_year_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting export download for region {region_code} ({Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')})")

    all_prices, meta = fetch_export_prices_paginated(
        product_code=product_code,
        tariff_code=tariff_code,
        region_code=region_code,
        year=year,
        year_to_date=year_to_date,
        page_size=1000,
        sleep_seconds=0.0,
    )
    raw_data = _sort_and_build_raw_data(all_prices, product_code, region_code, year, meta, tariff_type="export")
    raw_data["tariff_code"] = tariff_code
    logger.info(
        f"Region {region_code}: Downloaded {len(all_prices)} export price slots "
        f"(pages={meta.get('pages_fetched')}, range={meta.get('period_from')}..{meta.get('period_to')})"
    )
    return raw_data


def save_raw_data(raw_data, region_code, year=2025, *, export: bool = False):
    """
    Save raw data to file.

    Args:
        raw_data: Raw data dictionary
        region_code: Region code
        year: Year
        export: If True, save to data/raw/export/{year}/

    Returns:
        Path: Path to saved file
    """
    if export:
        raw_year_dir = RAW_DATA_BASE_DIR / RAW_EXPORT_SUBDIR / str(year)
    else:
        raw_year_dir = RAW_DATA_BASE_DIR / str(year)
    raw_year_dir.mkdir(parents=True, exist_ok=True)
    filepath = raw_year_dir / f"{region_code}_{year}.json"
    
    # Atomic write (temp file then replace) to avoid partial files on interruption.
    temp_file = filepath.with_suffix('.json.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, filepath)
        logger.info(f"Saved raw data to {filepath}")
        return filepath
    except IOError as e:
        logger.error(f"Error saving raw data file {filepath}: {e}")
        raise

def main():
    """Main function to download raw data."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download raw price data for statistics')
    parser.add_argument('--region', '-r', type=str, help='Region code (A, B, C, etc.). If not provided, downloads all regions.')
    parser.add_argument('--product', '-p', type=str, default=None,
                       help='Product code (default: from config for import; discovered for export)')
    parser.add_argument('--year', '-y', type=int, default=2025, help='Year (default: 2025)')
    parser.add_argument('--full-year', action='store_true', help='Force full-year range instead of year-to-date for the current year')
    parser.add_argument('--export', action='store_true', help='Download export (Agile Outgoing) instead of import (Agile Octopus)')

    args = parser.parse_args()

    export_mode = args.export
    region_code = args.region
    year = args.year
    year_to_date = (year == datetime.now(timezone.utc).year) and (not args.full_year)

    if export_mode:
        from app.export_client import discover_export_products
        products = discover_export_products()
        agile_export = next((p for p in products if getattr(p, "tariff_type", None) == "agile_outgoing"), None)
        if not agile_export:
            print("Error: No Agile Outgoing product found")
            sys.exit(1)
        product_code = getattr(agile_export, "code", None) or agile_export.get("code", "")
    else:
        product_code = args.product or Config.OCTOPUS_PRODUCT_CODE

    # Get list of regions to process
    if region_code:
        regions_to_process = [region_code]
        if region_code not in Config.OCTOPUS_REGION_NAMES:
            print(f"Error: Invalid region code: {region_code}")
            print(f"Valid regions: {', '.join(Config.OCTOPUS_REGION_NAMES.keys())}")
            sys.exit(1)
    else:
        # Process all regions
        regions_to_process = list(Config.OCTOPUS_REGION_NAMES.keys())
        print(f"Downloading raw data for ALL {len(regions_to_process)} regions")
        print("This will take a very long time (1-2+ hours)...")
        print()
    
    print(f"Product: {product_code}")
    print(f"Year: {year}")
    print(f"Tariff: {'export (Agile Outgoing)' if export_mode else 'import (Agile Octopus)'}")
    print(f"Coverage: {'year_to_date' if year_to_date else 'full_year'}")
    print(f"Regions: {', '.join(regions_to_process)}")
    print()
    
    downloaded_files = []
    failed_regions = []
    
    for region in regions_to_process:
        try:
            print(f"\n{'='*60}")
            print(f"Processing region {region}: {Config.OCTOPUS_REGION_NAMES.get(region, 'Unknown')}")
            print(f"{'='*60}\n")
            
            if export_mode:
                raw_data = download_region_data_export(product_code, region, year, year_to_date=year_to_date)
            else:
                raw_data = download_region_data(product_code, region, year, year_to_date=year_to_date)

            if raw_data and raw_data.get("prices"):
                filepath = save_raw_data(raw_data, region, year, export=export_mode)
                downloaded_files.append({
                    'region': region,
                    'filepath': str(filepath),
                    'price_slots': raw_data.get('total_price_slots', 0),
                    'pages_fetched': raw_data.get('ingestion', {}).get('pages_fetched', 0),
                    'period_from': raw_data.get('ingestion', {}).get('period_from'),
                    'period_to': raw_data.get('ingestion', {}).get('period_to')
                })
                print(f"\n[OK] Successfully downloaded region {region}")
            else:
                logger.warning(f"No data downloaded for region {region}")
                failed_regions.append(region)
        
        except KeyboardInterrupt:
            print("\n\nDownload cancelled by user.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing region {region}: {e}", exc_info=True)
            failed_regions.append(region)
    
    # Summary
    print(f"\n\n{'='*60}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*60}")
    print(f"Successfully downloaded: {len(downloaded_files)} regions")
    print(f"Failed: {len(failed_regions)} regions")
    
    if downloaded_files:
        print("\nDownloaded files:")
        for item in downloaded_files:
            print(f"  {item['region']}: {item['filepath']}")
            print(f"    - {item['price_slots']} price slots")
            print(f"    - {item['pages_fetched']} pages fetched")
            if item.get('period_from') and item.get('period_to'):
                print(f"    - range: {item['period_from']} .. {item['period_to']}")
    
    if failed_regions:
        print(f"\nFailed regions: {', '.join(failed_regions)}")
    
    print(f"\n{'='*60}")

if __name__ == '__main__':
    main()

