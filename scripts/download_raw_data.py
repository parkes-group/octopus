"""
Script to download raw price data for all regions for a full year.
Saves data to data/raw/ directory for use in statistics calculations.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# Add the project root to the path (scripts are in scripts/ subdirectory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api_client import OctopusAPIClient
from app.config import Config
import json
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path('data/raw')

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
    
    logger.info(f"Starting download for region {region_code} ({Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')})")
    
    all_prices = []
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    current_date = start_date
    failed_days = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        try:
            logger.debug(f"Fetching {region_code} {date_str}")
            api_response = OctopusAPIClient.get_prices(product_code, region_code, date_str)
            prices_data = api_response.get('results', [])
            
            if prices_data:
                all_prices.extend(prices_data)
                logger.debug(f"Fetched {len(prices_data)} price slots for {date_str}")
            else:
                logger.warning(f"No prices returned for {region_code} on {date_str}")
                failed_days += 1
            
            # Progress logging every 30 days
            days_processed = (current_date - start_date).days + 1
            if days_processed % 30 == 0:
                logger.info(f"Region {region_code}: Processed {days_processed} days...")
            
        except Exception as e:
            logger.error(f"Error fetching prices for {region_code} on {date_str}: {e}")
            failed_days += 1
        
        current_date += timedelta(days=1)
    
    # Sort all prices chronologically by valid_from
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
        "days_processed": (end_date - start_date).days + 1 - failed_days,
        "days_failed": failed_days
    }
    
    logger.info(f"Region {region_code}: Downloaded {len(all_prices)} price slots ({failed_days} days failed)")
    
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
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        
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
                    'days_processed': raw_data.get('days_processed', 0),
                    'days_failed': raw_data.get('days_failed', 0)
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
            print(f"    - {item['days_processed']} days processed")
            if item['days_failed'] > 0:
                print(f"    - {item['days_failed']} days failed")
    
    if failed_regions:
        print(f"\nFailed regions: {', '.join(failed_regions)}")
    
    print(f"\n{'='*60}")

if __name__ == '__main__':
    main()

