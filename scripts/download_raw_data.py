"""
Script to download raw (historic) half-hourly Agile prices for 2025 and store them under data/raw/.

This script is the **raw data ingestion entry point** for historic stats.

Key responsibilities:
- Build a full-year Octopus API query (explicit UTC range)
- Traverse Octopus pagination until exhausted
- Persist one JSON file per region: data/raw/{REGION}_{YEAR}.json (overwritten atomically)

Note:
- This script intentionally does not depend on the app's "today prices" API client method, because
  that method is designed for real-time pages and does not accept historic date ranges.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date

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

RAW_DATA_DIR = Path('data/raw')

def _year_utc_range(year: int) -> tuple[str, str]:
    """
    Build an explicit UTC time range covering the full calendar year.

    Required for correctness: do not rely on Octopus API defaults.

    Returns:
        (period_from, period_to) as ISO-8601 Z strings.
    """
    return (f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z")

def fetch_prices_paginated(product_code: str, region_code: str, year: int, page_size: int = 1000, sleep_seconds: float = 0.0) -> tuple[list[dict], dict]:
    """
    Fetch all unit rates for the given region + product across the full year (UTC) using pagination.

    Returns:
        (results, meta) where meta includes page_count and total_results.
    """
    period_from, period_to = _year_utc_range(year)
    url = Config.get_prices_url(product_code, region_code)

    params = {
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
    }

    pages = 0
    results: list[dict] = []
    next_url = url
    next_params = params

    while next_url:
        pages += 1
        logger.info(f"[INGEST] {region_code}: fetching page {pages} ({'with params' if next_params else 'next URL already has params'})")
        response = requests.get(next_url, params=next_params, timeout=Config.OCTOPUS_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        page_results = data.get("results", [])
        results.extend(page_results)

        next_url = data.get("next")
        # When following a "next" URL, it already includes query params; don't re-send the original params.
        next_params = None

        if sleep_seconds:
            time.sleep(sleep_seconds)

    meta = {
        "product_code": product_code,
        "region_code": region_code,
        "year": year,
        "period_from": period_from,
        "period_to": period_to,
        "page_size": page_size,
        "pages_fetched": pages,
        "total_price_slots": len(results),
    }
    return results, meta

def download_region_data(product_code, region_code, year=2025):
    """
    Download all price data for a region for the entire year.
    
    Args:
        product_code: Octopus product code (e.g., 'AGILE-24-10-01')
        region_code: Region code (A, B, C, etc.)
        year: Year to download (default 2025)
    
    Returns:
        dict: Raw data dictionary with all prices, or None if failed
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting full-year download for region {region_code} ({Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')})")

    # Fetch the full year in one explicit ranged query, traversing pagination.
    # This avoids relying on any implicit defaults and makes completeness measurable.
    all_prices, meta = fetch_prices_paginated(
        product_code=product_code,
        region_code=region_code,
        year=year,
        page_size=1000,
        sleep_seconds=0.0,
    )
    
    # Sort all prices chronologically by valid_from (Octopus often returns reverse chronological)
    try:
        all_prices = sorted(all_prices, key=lambda x: x.get('valid_from', ''))
    except Exception as e:
        logger.warning(f"Error sorting prices for {region_code}: {e}")
    
    # Create raw data structure
    raw_data = {
        "product_code": product_code,
        "region_code": region_code,
        "year": year,
        "prices": all_prices,
        "fetched_at": datetime.now().isoformat(),
        "total_price_slots": len(all_prices),
        "ingestion": meta
    }
    
    logger.info(
        f"Region {region_code}: Downloaded {len(all_prices)} price slots "
        f"(pages={meta.get('pages_fetched')}, range={meta.get('period_from')}..{meta.get('period_to')})"
    )
    
    return raw_data

def save_raw_data(raw_data, region_code, year=2025):
    """
    Save raw data to file.
    
    Args:
        raw_data: Raw data dictionary
        region_code: Region code
        year: Year
    
    Returns:
        Path: Path to saved file
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RAW_DATA_DIR / f"{region_code}_{year}.json"
    
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
    parser.add_argument('--product', '-p', type=str, default=Config.OCTOPUS_PRODUCT_CODE,
                       help='Product code (default: from config)')
    parser.add_argument('--year', '-y', type=int, default=2025, help='Year (default: 2025)')
    
    args = parser.parse_args()
    
    product_code = args.product
    region_code = args.region
    year = args.year
    
    if year != 2025:
        print(f"Error: Only 2025 data download is supported (got {year})")
        sys.exit(1)
    
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
    print(f"Regions: {', '.join(regions_to_process)}")
    print()
    
    downloaded_files = []
    failed_regions = []
    
    for region in regions_to_process:
        try:
            print(f"\n{'='*60}")
            print(f"Processing region {region}: {Config.OCTOPUS_REGION_NAMES.get(region, 'Unknown')}")
            print(f"{'='*60}\n")
            
            raw_data = download_region_data(product_code, region, year)
            
            if raw_data and raw_data.get('prices'):
                filepath = save_raw_data(raw_data, region, year)
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

