"""
Script to generate statistics for all regions and calculate national averages.
Uses raw data files from data/raw/ directory.
"""
import os
import sys
from pathlib import Path

# Add the project root to the path (scripts are in scripts/ subdirectory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.stats_calculator import StatsCalculator
from app.config import Config
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Generate statistics for all regions and calculate national averages."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate statistics for all regions and national averages')
    parser.add_argument('--product', '-p', type=str, default=Config.OCTOPUS_PRODUCT_CODE,
                       help='Product code (default: from config)')
    parser.add_argument('--year', '-y', type=int, default=2025, help='Year (default: 2025)')
    
    args = parser.parse_args()
    
    product_code = args.product
    year = args.year
    
    if year != 2025:
        print(f"Error: Only 2025 statistics are supported (got {year})")
        sys.exit(1)
    
    # Get all region codes
    region_codes = list(Config.OCTOPUS_REGION_NAMES.keys())
    
    print(f"Generating statistics for all {len(region_codes)} regions")
    print(f"Product: {product_code}")
    print(f"Year: {year}")
    print()
    
    generated_files = []
    failed_regions = []
    
    # Generate stats for each region
    for region_code in region_codes:
        region_name = Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')
        print(f"\n{'='*60}")
        print(f"Processing region {region_code}: {region_name}")
        print(f"{'='*60}")
        
        try:
            stats_data = StatsCalculator.calculate_2025_stats(
                product_code=product_code,
                region_code=region_code
            )
            
            if stats_data:
                filepath = StatsCalculator.save_stats(stats_data)
                generated_files.append({
                    'region': region_code,
                    'filepath': str(filepath)
                })
                print(f"\n[OK] Successfully generated stats for region {region_code}")
                print(f"  - Average cheapest block: {stats_data.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
                print(f"  - Average daily price: {stats_data.get('daily_average', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
            else:
                print(f"\n[ERROR] Failed to generate stats for region {region_code}")
                failed_regions.append(region_code)
        
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error generating stats for region {region_code}: {e}", exc_info=True)
            print(f"\n[ERROR] Failed to generate stats for region {region_code}: {e}")
            failed_regions.append(region_code)
    
    # Calculate national averages
    print(f"\n\n{'='*60}")
    print("Calculating National Averages")
    print(f"{'='*60}\n")
    
    try:
        national_stats = StatsCalculator.calculate_national_averages(
            product_code=product_code,
            year=year
        )
        
        if national_stats:
            national_filepath = StatsCalculator.save_national_stats(national_stats, year=year)
            print(f"[OK] National averages calculated and saved to {national_filepath}")
            print(f"  - Average cheapest block: {national_stats.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
            print(f"  - Average daily price: {national_stats.get('daily_average', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
            print(f"  - Annual savings vs daily avg: £{national_stats.get('savings_vs_daily_average', {}).get('annual_saving_gbp', 0):.2f}")
            print(f"  - Annual savings vs price cap: £{national_stats.get('price_cap_comparison', {}).get('annual_saving_gbp', 0):.2f}")
        else:
            print("[ERROR] Failed to calculate national averages")
    except Exception as e:
        logger.error(f"Error calculating national averages: {e}", exc_info=True)
        print(f"[ERROR] Failed to calculate national averages: {e}")
    
    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Successfully generated: {len(generated_files)} regions")
    print(f"Failed: {len(failed_regions)} regions")
    
    if generated_files:
        print("\nGenerated files:")
        for item in generated_files:
            print(f"  {item['region']}: {item['filepath']}")
    
    if failed_regions:
        print(f"\nFailed regions: {', '.join(failed_regions)}")
    
    print(f"\n{'='*60}")

if __name__ == '__main__':
    main()

