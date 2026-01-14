"""
Validation script for 2025 historic statistics.
Performs spot checks and validation of calculations.
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, date
from app.price_calculator import PriceCalculator
from app.stats_calculator import StatsCalculator
from app.config import Config

def validate_raw_data():
    """Validate raw data structure and completeness."""
    print("=" * 80)
    print("1. RAW DATA VALIDATION")
    print("=" * 80)
    
    raw_dir = Path('data/raw')
    stats_dir = Path('data/stats')
    
    # Check all regions
    region_codes = list(Config.OCTOPUS_REGION_NAMES.keys())
    print(f"\nChecking {len(region_codes)} regions: {', '.join(region_codes)}")
    
    raw_data_summary = {}
    for region in region_codes:
        raw_file = raw_dir / f"{region}_2025.json"
        if not raw_file.exists():
            print(f"  [WARN]  Region {region}: Raw data file NOT FOUND")
            continue
        
        with open(raw_file, 'r') as f:
            data = json.load(f)
        
        prices = data.get('prices', [])
        dates = set()
        for p in prices:
            dates.add(p['valid_from'][:10])
        
        date_counts = Counter([p['valid_from'][:10] for p in prices])
        expected_slots = 48 * 365  # 48 slots/day * 365 days
        
        raw_data_summary[region] = {
            'total_slots': len(prices),
            'unique_dates': len(dates),
            'date_range': (min(dates), max(dates)) if dates else None,
            'slots_per_day': {d: c for d, c in date_counts.items() if c != 48}
        }
        
        print(f"  [OK] Region {region}: {len(prices)} slots, {len(dates)} unique dates")
        print(f"    Date range: {min(dates)} to {max(dates)}")
        
        # Check for days with non-48 slots
        non_48_days = {d: c for d, c in date_counts.items() if c != 48}
        if non_48_days:
            print(f"    [WARN] Days with non-48 slots: {len(non_48_days)}")
            for d, c in list(non_48_days.items())[:5]:
                print(f"      {d}: {c} slots")
    
    return raw_data_summary

def validate_sample_day_calculations():
    """Validate calculations for a sample day."""
    print("\n" + "=" * 80)
    print("2. SAMPLE DAY CALCULATION VALIDATION")
    print("=" * 80)
    
    # Load raw data for region A
    raw_file = Path('data/raw/A_2025.json')
    if not raw_file.exists():
        print("  [WARN] Raw data file not found, skipping sample validation")
        return
    
    with open(raw_file, 'r') as f:
        data = json.load(f)
    
    prices = data.get('prices', [])
    
    # Get prices for 2025-01-01
    sample_date = "2025-01-01"
    day_prices = [p for p in prices if p['valid_from'].startswith(sample_date)]
    
    print(f"\nValidating calculations for {sample_date} (Region A)")
    print(f"  Total slots for this day: {len(day_prices)}")
    
    if len(day_prices) != 48:
        print(f"  [WARN] WARNING: Expected 48 slots, got {len(day_prices)}")
    
    # Sort by time
    day_prices = sorted(day_prices, key=lambda x: x['valid_from'])
    
    # Manual daily average calculation
    total_price = sum(p['value_inc_vat'] for p in day_prices)
    manual_daily_avg = total_price / len(day_prices)
    print(f"\n  Daily Average (manual): {manual_daily_avg:.4f} p/kWh")
    
    # Using PriceCalculator
    calc_daily_avg = PriceCalculator.calculate_daily_average_price(day_prices)
    print(f"  Daily Average (calculator): {calc_daily_avg:.4f} p/kWh")
    
    if abs(manual_daily_avg - calc_daily_avg) > 0.01:
        print(f"  [ERROR] MISMATCH: Manual={manual_daily_avg:.4f}, Calculator={calc_daily_avg:.4f}")
    else:
        print(f"  [OK] Daily average calculation matches")
    
    # Cheapest block (3.5 hours = 7 slots)
    block_duration = 3.5
    cheapest_block = PriceCalculator.find_cheapest_block(day_prices, block_duration)
    
    if cheapest_block:
        print(f"\n  Cheapest Block ({block_duration}h):")
        print(f"    Start: {cheapest_block['start_time']}")
        print(f"    End: {cheapest_block['end_time']}")
        print(f"    Average price: {cheapest_block['average_price']:.4f} p/kWh")
        print(f"    Slots: {len(cheapest_block['slots'])}")
        
        # Manual verification
        block_slots = cheapest_block['slots']
        manual_block_avg = sum(s['value_inc_vat'] for s in block_slots) / len(block_slots)
        print(f"    Manual verification: {manual_block_avg:.4f} p/kWh")
        
        if abs(cheapest_block['average_price'] - manual_block_avg) > 0.01:
            print(f"    [ERROR] MISMATCH in block average")
        else:
            print(f"    [OK] Block average calculation matches")
    else:
        print(f"  [WARN] No cheapest block found")
    
    # Lowest 30-minute slot
    lowest_price = PriceCalculator.find_lowest_price(day_prices)
    if lowest_price:
        print(f"\n  Lowest 30-minute slot:")
        print(f"    Time: {lowest_price['time_from']}")
        print(f"    Price: {lowest_price['price']:.4f} p/kWh")
        
        # Manual verification
        manual_lowest = min(p['value_inc_vat'] for p in day_prices)
        if abs(lowest_price['price'] - manual_lowest) > 0.01:
            print(f"    [ERROR] MISMATCH: Calculator={lowest_price['price']:.4f}, Manual={manual_lowest:.4f}")
        else:
            print(f"    [OK] Lowest price calculation matches")
    
    # Negative pricing
    negative_slots = [p for p in day_prices if p['value_inc_vat'] <= 0]
    print(f"\n  Negative/zero price slots: {len(negative_slots)}")
    if negative_slots:
        for slot in negative_slots[:5]:
            print(f"    {slot['valid_from']}: {slot['value_inc_vat']:.4f} p/kWh")

def validate_regional_stats():
    """Validate regional statistics against raw data."""
    print("\n" + "=" * 80)
    print("3. REGIONAL STATISTICS VALIDATION")
    print("=" * 80)
    
    # Check region A stats
    stats_file = Path('data/stats/A_2025.json')
    if not stats_file.exists():
        print("  [WARN] Stats file not found")
        return
    
    with open(stats_file, 'r') as f:
        stats = json.load(f)
    
    print(f"\nRegion A Statistics:")
    print(f"  Days processed: {stats.get('days_processed')}")
    print(f"  Days failed: {stats.get('days_failed')}")
    print(f"  Cheapest block avg: {stats.get('cheapest_block', {}).get('avg_price_p_per_kwh')} p/kWh")
    print(f"  Daily average: {stats.get('daily_average', {}).get('avg_price_p_per_kwh')} p/kWh")
    print(f"  Negative slots: {stats.get('negative_pricing', {}).get('total_negative_slots')}")
    
    # Load raw data and recalculate for a few days
    raw_file = Path('data/raw/A_2025.json')
    if raw_file.exists():
        with open(raw_file, 'r') as f:
            raw_data = json.load(f)
        
        prices = raw_data.get('prices', [])
        
        # Group by date
        prices_by_date = defaultdict(list)
        for p in prices:
            date_key = p['valid_from'][:10]
            prices_by_date[date_key].append(p)
        
        # Calculate for first 10 days
        print(f"\n  Spot-checking first 10 days:")
        cheapest_blocks = []
        daily_averages = []
        negative_count = 0
        
        for date_str in sorted(prices_by_date.keys())[:10]:
            day_prices = sorted(prices_by_date[date_str], key=lambda x: x['valid_from'])
            
            # Daily average
            daily_avg = PriceCalculator.calculate_daily_average_price(day_prices)
            if daily_avg:
                daily_averages.append(daily_avg)
            
            # Cheapest block
            cheapest_block = PriceCalculator.find_cheapest_block(day_prices, 3.5)
            if cheapest_block:
                cheapest_blocks.append(cheapest_block['average_price'])
            
            # Negative slots
            negative_count += sum(1 for p in day_prices if p['value_inc_vat'] <= 0)
        
        if daily_averages:
            spot_avg_daily = sum(daily_averages) / len(daily_averages)
            print(f"    Spot-check daily avg (10 days): {spot_avg_daily:.2f} p/kWh")
            print(f"    Full-year daily avg: {stats.get('daily_average', {}).get('avg_price_p_per_kwh')} p/kWh")
        
        if cheapest_blocks:
            spot_avg_block = sum(cheapest_blocks) / len(cheapest_blocks)
            print(f"    Spot-check cheapest block (10 days): {spot_avg_block:.2f} p/kWh")
            print(f"    Full-year cheapest block: {stats.get('cheapest_block', {}).get('avg_price_p_per_kwh')} p/kWh")
        
        print(f"    Spot-check negative slots (10 days): {negative_count}")
        print(f"    Full-year negative slots: {stats.get('negative_pricing', {}).get('total_negative_slots')}")

def validate_national_averages():
    """Validate national average methodology."""
    print("\n" + "=" * 80)
    print("4. NATIONAL AVERAGE METHODOLOGY VALIDATION")
    print("=" * 80)
    
    national_file = Path('data/stats/national_2025.json')
    if not national_file.exists():
        print("  [WARN]  National stats file not found")
        return
    
    with open(national_file, 'r') as f:
        national_stats = json.load(f)
    
    print(f"\nNational Statistics:")
    print(f"  Source regions: {national_stats.get('source_regions', [])}")
    print(f"  Cheapest block avg: {national_stats.get('cheapest_block', {}).get('avg_price_p_per_kwh')} p/kWh")
    print(f"  Daily average: {national_stats.get('daily_average', {}).get('avg_price_p_per_kwh')} p/kWh")
    
    # Load all regional stats
    region_codes = national_stats.get('source_regions', [])
    regional_stats = []
    
    for region in region_codes:
        stats_file = Path(f'data/stats/{region}_2025.json')
        if stats_file.exists():
            with open(stats_file, 'r') as f:
                regional_stats.append(json.load(f))
    
    if not regional_stats:
        print("  [WARN] No regional stats found for validation")
        return
    
    print(f"\n  Validating national average calculation:")
    print(f"    Number of regions: {len(regional_stats)}")
    
    # Calculate manual average
    regional_cheapest_blocks = [
        s.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)
        for s in regional_stats
    ]
    regional_daily_averages = [
        s.get('daily_average', {}).get('avg_price_p_per_kwh', 0)
        for s in regional_stats
    ]
    
    manual_national_cheapest = sum(regional_cheapest_blocks) / len(regional_cheapest_blocks)
    manual_national_daily = sum(regional_daily_averages) / len(regional_daily_averages)
    
    national_cheapest = national_stats.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)
    national_daily = national_stats.get('daily_average', {}).get('avg_price_p_per_kwh', 0)
    
    print(f"\n    Cheapest Block Average:")
    print(f"      Manual calculation: {manual_national_cheapest:.2f} p/kWh")
    print(f"      National stats file: {national_cheapest:.2f} p/kWh")
    if abs(manual_national_cheapest - national_cheapest) < 0.01:
        print(f"      [OK] Matches")
    else:
        print(f"      [ERROR] MISMATCH: Difference = {abs(manual_national_cheapest - national_cheapest):.4f}")
    
    print(f"\n    Daily Average:")
    print(f"      Manual calculation: {manual_national_daily:.2f} p/kWh")
    print(f"      National stats file: {national_daily:.2f} p/kWh")
    if abs(manual_national_daily - national_daily) < 0.01:
        print(f"      [OK] Matches")
    else:
        print(f"      [ERROR] MISMATCH: Difference = {abs(manual_national_daily - national_daily):.4f}")
    
    # Check negative pricing averaging
    regional_negative_slots = [
        s.get('negative_pricing', {}).get('total_negative_slots', 0)
        for s in regional_stats
    ]
    manual_avg_negative = sum(regional_negative_slots) / len(regional_negative_slots)
    national_negative = national_stats.get('negative_pricing', {}).get('total_negative_slots', 0)
    
    print(f"\n    Negative Slots (averaged):")
    print(f"      Manual calculation: {manual_avg_negative:.1f} slots")
    print(f"      National stats file: {national_negative} slots")
    if abs(manual_avg_negative - national_negative) < 1:
        print(f"      [OK] Matches (within rounding)")
    else:
        print(f"      [ERROR] MISMATCH: Difference = {abs(manual_avg_negative - national_negative):.1f}")

def validate_negative_pricing():
    """Validate negative pricing calculations."""
    print("\n" + "=" * 80)
    print("5. NEGATIVE PRICING VALIDATION")
    print("=" * 80)
    
    # Check region A
    raw_file = Path('data/raw/A_2025.json')
    stats_file = Path('data/stats/A_2025.json')
    
    if not raw_file.exists() or not stats_file.exists():
        print("  [WARN] Required files not found")
        return
    
    with open(raw_file, 'r') as f:
        raw_data = json.load(f)
    
    with open(stats_file, 'r') as f:
        stats = json.load(f)
    
    prices = raw_data.get('prices', [])
    
    # Count negative/zero slots manually
    negative_slots = [p for p in prices if p.get('value_inc_vat', 0) <= 0]
    total_negative_slots = len(negative_slots)
    total_negative_hours = total_negative_slots * 0.5
    
    print(f"\nRegion A Negative Pricing:")
    print(f"  Manual count: {total_negative_slots} slots, {total_negative_hours} hours")
    print(f"  Stats file: {stats.get('negative_pricing', {}).get('total_negative_slots')} slots, {stats.get('negative_pricing', {}).get('total_negative_hours')} hours")
    
    if total_negative_slots == stats.get('negative_pricing', {}).get('total_negative_slots'):
        print(f"  [OK] Slot count matches")
    else:
        print(f"  [ERROR] MISMATCH in slot count")
    
    # Calculate average negative price
    if negative_slots:
        total_negative_price = sum(abs(slot['value_inc_vat']) for slot in negative_slots)
        avg_negative_price = total_negative_price / len(negative_slots)
        print(f"\n  Average negative price:")
        print(f"    Manual: {avg_negative_price:.4f} p/kWh")
        print(f"    Stats file: {stats.get('negative_pricing', {}).get('avg_negative_price_p_per_kwh')} p/kWh")
        
        stats_avg = stats.get('negative_pricing', {}).get('avg_negative_price_p_per_kwh', 0)
        if abs(avg_negative_price - stats_avg) < 0.01:
            print(f"    [OK] Matches")
        else:
            print(f"    [ERROR] MISMATCH")
        
        # Calculate total payment
        battery_power = Config.STATS_BATTERY_CHARGE_POWER_KW
        total_paid_pence = 0
        for slot in negative_slots:
            kwh_per_slot = battery_power * 0.5  # 0.5 hours per slot
            payment_pence = abs(slot['value_inc_vat']) * kwh_per_slot
            total_paid_pence += payment_pence
        
        total_paid_gbp = total_paid_pence / 100
        print(f"\n  Total payment (battery @ {battery_power} kW):")
        print(f"    Manual: £{total_paid_gbp:.2f}")
        print(f"    Stats file: £{stats.get('negative_pricing', {}).get('total_paid_gbp')}")
        
        stats_paid = stats.get('negative_pricing', {}).get('total_paid_gbp', 0)
        if abs(total_paid_gbp - stats_paid) < 0.01:
            print(f"    [OK] Matches")
        else:
            print(f"    [ERROR] MISMATCH")

def main():
    """Run all validation checks."""
    print("\n" + "=" * 80)
    print("HISTORIC 2025 STATISTICS VALIDATION AUDIT")
    print("=" * 80)
    
    try:
        raw_summary = validate_raw_data()
        validate_sample_day_calculations()
        validate_regional_stats()
        validate_national_averages()
        validate_negative_pricing()
        
        print("\n" + "=" * 80)
        print("VALIDATION COMPLETE")
        print("=" * 80)
        print("\nReview the output above for any mismatches or warnings.")
        
    except Exception as e:
        print(f"\n[ERROR] ERROR during validation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
