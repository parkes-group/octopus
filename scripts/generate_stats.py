"""
Standalone script to generate historical statistics.
Can be run directly without Flask server.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to the path (scripts are in scripts/ subdirectory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.stats_calculator import StatsCalculator
from app.config import Config

def main():
    """Generate statistics for a region."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate historical statistics for a given year')
    parser.add_argument('--region', '-r', type=str, help='Region code (A, B, C, etc.)')
    parser.add_argument('--product', '-p', type=str, default=Config.OCTOPUS_PRODUCT_CODE,
                       help='Product code (default: from config)')
    parser.add_argument('--year', '-y', type=int, default=2025, help='Year (default: 2025)')
    
    args = parser.parse_args()
    
    product_code = args.product
    region_code = args.region
    year = args.year
    
    if not region_code:
        print("Error: Region code is required. Use --region or -r to specify a region (A, B, C, etc.)")
        print("Example: python generate_stats.py --region N")
        sys.exit(1)
    
    print(f"Starting statistics generation for {product_code} region {region_code} (year {year})")
    print(f"Region name: {Config.OCTOPUS_REGION_NAMES.get(region_code, 'Unknown')}")
    print("This may take several minutes...")
    print()
    
    try:
        # Calculate statistics
        if year == 2025:
            stats_data = StatsCalculator.calculate_2025_stats(
                product_code=product_code,
                region_code=region_code
            )
        else:
            current_year_utc = datetime.now(timezone.utc).year
            stats_data = StatsCalculator.calculate_year_stats(
                product_code=product_code,
                region_code=region_code,
                year=year,
                coverage="year_to_date" if year == current_year_utc else "full_year",
            )
        
        # Save to file
        filepath = StatsCalculator.save_stats(stats_data)
        
        print()
        print("=" * 60)
        print("Statistics generated successfully!")
        print(f"File saved to: {filepath}")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  Days processed: {stats_data.get('days_processed', 0)}")
        print(f"  Days failed: {stats_data.get('days_failed', 0)}")
        print(f"  Average cheapest block price: {stats_data.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
        print(f"  Average daily price: {stats_data.get('daily_average', {}).get('avg_price_p_per_kwh', 0)} p/kWh")
        print(f"  Annual savings vs daily avg: £{stats_data.get('savings_vs_daily_average', {}).get('annual_saving_gbp', 0):.2f}")
        print(f"  Negative pricing slots: {stats_data.get('negative_pricing', {}).get('total_negative_slots', 0)}")
        print(f"  Total paid by Octopus: £{stats_data.get('negative_pricing', {}).get('total_paid_gbp', 0):.2f}")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError generating statistics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

