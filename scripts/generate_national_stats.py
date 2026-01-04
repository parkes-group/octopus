"""
Script to generate national averages from all regional statistics.
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
    """Generate national averages from all regional statistics."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate national averages from all regional statistics')
    parser.add_argument('--product', '-p', type=str, default=Config.OCTOPUS_PRODUCT_CODE,
                       help='Product code (default: from config)')
    parser.add_argument('--year', '-y', type=int, default=2025, help='Year (default: 2025)')
    
    args = parser.parse_args()
    
    product_code = args.product
    year = args.year
    
    if year != 2025:
        print(f"Error: Only 2025 statistics are supported (got {year})")
        sys.exit(1)
    
    print(f"Calculating national averages from all regional statistics")
    print(f"Product: {product_code}")
    print(f"Year: {year}")
    print()
    
    try:
        national_stats = StatsCalculator.calculate_national_averages(
            product_code=product_code,
            year=year
        )
        
        if national_stats:
            national_filepath = StatsCalculator.save_national_stats(national_stats, year=year)
            print(f"\n{'='*60}")
            print("National averages calculated successfully!")
            print(f"{'='*60}")
            print(f"File saved to: {national_filepath}")
            print()
            print("Summary:")
            print(f"  Average cheapest block price: {national_stats.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
            print(f"  Average daily price: {national_stats.get('daily_average', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
            print(f"  Annual savings vs daily avg: £{national_stats.get('savings_vs_daily_average', {}).get('annual_saving_gbp', 0):.2f}")
            print(f"  Annual savings vs price cap: £{national_stats.get('price_cap_comparison', {}).get('annual_saving_gbp', 0):.2f}")
            print(f"  Total negative pricing slots: {national_stats.get('negative_pricing', {}).get('total_negative_slots', 0)}")
            print(f"  Total paid by Octopus: £{national_stats.get('negative_pricing', {}).get('total_paid_gbp', 0):.2f}")
            print(f"  Source regions: {', '.join(national_stats.get('source_regions', []))}")
        else:
            print("Error: Failed to calculate national averages")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error generating national averages: {e}", exc_info=True)
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

