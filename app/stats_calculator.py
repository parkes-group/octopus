"""
Historical Statistics Calculator for 2025 Agile Octopus pricing.
Calculates savings vs daily average, price cap comparison, and negative pricing analysis.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict
from app.api_client import OctopusAPIClient
from app.price_calculator import PriceCalculator
from app.config import Config
from app.timezone_utils import UK_TZ

logger = logging.getLogger(__name__)

class StatsCalculator:
    """Calculates historical statistics for Agile Octopus pricing."""
    
    STATS_DIR = Path('data/stats')
    RAW_DATA_DIR = Path('data/raw')
    BLOCK_DURATION_HOURS = 3.5
    
    @staticmethod
    def _ensure_stats_dir():
        """Ensure stats directory exists."""
        StatsCalculator.STATS_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def load_raw_data(region_code, year=2025):
        """
        Load raw price data from file.
        
        Args:
            region_code: Region code (A, B, C, etc.)
            year: Year (default 2025)
        
        Returns:
            list: List of price dictionaries, or None if file not found
        """
        filepath = StatsCalculator.RAW_DATA_DIR / f"{region_code}_{year}.json"
        
        if not filepath.exists():
            logger.warning(f"Raw data file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            prices = raw_data.get('prices', [])
            logger.debug(f"Loaded {len(prices)} price slots from {filepath}")
            return prices
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading raw data file {filepath}: {e}")
            return None
    
    @staticmethod
    def calculate_2025_stats(product_code, region_code='A', 
                            daily_kwh=None, 
                            battery_charge_power_kw=None,
                            price_cap_p_per_kwh=None):
        """
        Calculate comprehensive 2025 statistics for a region.
        
        Uses raw data files from data/raw/ directory if available, otherwise falls back to API calls.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Region code (default 'A' for national average)
            daily_kwh: Daily energy usage assumption (default from config)
            battery_charge_power_kw: Battery charge power in kW (default from config)
            price_cap_p_per_kwh: Ofgem price cap rate (default from config)
        
        Returns:
            dict: Statistics dictionary
        """
        # Use defaults from config if not provided
        daily_kwh = daily_kwh or Config.STATS_DAILY_KWH
        battery_charge_power_kw = battery_charge_power_kw or Config.STATS_BATTERY_CHARGE_POWER_KW
        price_cap_p_per_kwh = price_cap_p_per_kwh or Config.OFGEM_PRICE_CAP_P_PER_KWH
        
        logger.info(f"Starting 2025 statistics calculation for {product_code} region {region_code}")
        logger.info(f"Assumptions: {daily_kwh} kWh/day, {battery_charge_power_kw} kW charge rate, {price_cap_p_per_kwh} p/kWh price cap")
        
        # Try to load from raw data file first
        all_prices = StatsCalculator.load_raw_data(region_code, year=2025)
        use_raw_data = all_prices is not None
        
        if use_raw_data:
            logger.info(f"Using raw data file for region {region_code} ({len(all_prices)} price slots)")
        else:
            logger.info(f"Raw data file not found, will fetch from API (this will take longer)")
            all_prices = []
        
        # Initialize accumulators
        cheapest_block_prices = []
        daily_average_prices = []
        negative_slots = []
        total_days = 0
        failed_days = 0
        
        # Iterate through all days in 2025
        start_date = date(2025, 1, 1)
        end_date = date(2025, 12, 31)
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            try:
                if use_raw_data:
                    # Extract prices for this date from raw data
                    # valid_from format is ISO: "2025-01-01T00:00:00Z", so we can filter by date prefix
                    prices_data = [
                        p for p in all_prices
                        if p.get('valid_from', '').startswith(date_str)
                    ]
                else:
                    # Fetch prices from API
                    logger.debug(f"Fetching prices for {date_str}")
                    api_response = OctopusAPIClient.get_prices(product_code, region_code, date_str)
                    prices_data = api_response.get('results', [])
                
                if not prices_data:
                    logger.warning(f"No prices found for {date_str}")
                    failed_days += 1
                    current_date += timedelta(days=1)
                    continue
                
                # Sort prices chronologically
                prices_data = sorted(prices_data, key=lambda x: x.get('valid_from', ''))
                
                # Calculate cheapest block
                cheapest_block = PriceCalculator.find_cheapest_block(
                    prices_data, 
                    StatsCalculator.BLOCK_DURATION_HOURS
                )
                
                if cheapest_block:
                    cheapest_block_prices.append(cheapest_block['average_price'])
                
                # Calculate daily average
                daily_avg = PriceCalculator.calculate_daily_average_price(prices_data)
                if daily_avg:
                    daily_average_prices.append(daily_avg)
                
                # Find negative or zero price slots (including zero means you're paid to use electricity)
                for price in prices_data:
                    if price.get('value_inc_vat', 0) <= 0:
                        negative_slots.append({
                            'date': date_str,
                            'price_p_per_kwh': price['value_inc_vat'],
                            'valid_from': price['valid_from'],
                            'valid_to': price['valid_to']
                        })
                
                total_days += 1
                
                # Progress logging every 30 days
                if total_days % 30 == 0:
                    logger.info(f"Processed {total_days} days...")
                
            except Exception as e:
                logger.error(f"Error processing {date_str}: {e}", exc_info=True)
                failed_days += 1
            
            current_date += timedelta(days=1)
        
        logger.info(f"Completed processing: {total_days} successful days, {failed_days} failed days")
        
        # Calculate aggregates
        avg_cheapest_block = sum(cheapest_block_prices) / len(cheapest_block_prices) if cheapest_block_prices else 0
        avg_daily_average = sum(daily_average_prices) / len(daily_average_prices) if daily_average_prices else 0
        
        # Calculate savings vs daily average
        savings_p_per_kwh = avg_daily_average - avg_cheapest_block
        savings_percentage = (savings_p_per_kwh / avg_daily_average * 100) if avg_daily_average > 0 else 0
        
        # Calculate annual savings vs daily average
        # Only apply savings to the portion of usage in the cheapest block (35% by default)
        cheapest_block_usage_kwh = daily_kwh * (Config.STATS_CHEAPEST_BLOCK_USAGE_PERCENT / 100.0)
        annual_savings_vs_daily_avg = (savings_p_per_kwh * cheapest_block_usage_kwh * 365) / 100  # Convert pence to GBP
        
        # Calculate savings vs price cap
        savings_vs_cap_p_per_kwh = price_cap_p_per_kwh - avg_cheapest_block
        annual_savings_vs_cap = (savings_vs_cap_p_per_kwh * cheapest_block_usage_kwh * 365) / 100  # Convert pence to GBP
        
        # Calculate negative pricing statistics
        total_negative_slots = len(negative_slots)
        total_negative_hours = total_negative_slots * 0.5  # Each slot is 0.5 hours
        
        # Calculate average negative price per kWh
        avg_negative_price_p_per_kwh = 0.0
        if total_negative_slots > 0:
            total_negative_price_pence = sum(abs(slot['price_p_per_kwh']) for slot in negative_slots)
            avg_negative_price_p_per_kwh = total_negative_price_pence / total_negative_slots
        
        # Calculate total payment from Octopus (negative prices mean they pay you)
        total_paid_pence = 0
        for slot in negative_slots:
            kwh_per_slot = battery_charge_power_kw * 0.5  # 0.5 hours per slot
            payment_pence = abs(slot['price_p_per_kwh']) * kwh_per_slot
            total_paid_pence += payment_pence
        
        total_paid_gbp = total_paid_pence / 100
        avg_payment_per_day = total_paid_gbp / 365 if total_days > 0 else 0
        
        # Build results dictionary
        results = {
            "year": 2025,
            "region_code": region_code,
            "product_code": product_code,
            "calculation_date": datetime.now(UK_TZ).isoformat(),
            "days_processed": total_days,
            "days_failed": failed_days,
            "cheapest_block": {
                "block_hours": StatsCalculator.BLOCK_DURATION_HOURS,
                "avg_price_p_per_kwh": round(avg_cheapest_block, 2)
            },
            "daily_average": {
                "avg_price_p_per_kwh": round(avg_daily_average, 2)
            },
            "savings_vs_daily_average": {
                "savings_p_per_kwh": round(savings_p_per_kwh, 2),
                "savings_percentage": round(savings_percentage, 2),
                "annual_saving_gbp": round(annual_savings_vs_daily_avg, 2)
            },
            "price_cap_comparison": {
                "cap_price_p_per_kwh": price_cap_p_per_kwh,
                "savings_p_per_kwh": round(savings_vs_cap_p_per_kwh, 2),
                "annual_saving_gbp": round(annual_savings_vs_cap, 2)
            },
            "negative_pricing": {
                "total_negative_slots": total_negative_slots,
                "total_negative_hours": round(total_negative_hours, 1),
                "avg_negative_price_p_per_kwh": round(avg_negative_price_p_per_kwh, 2),
                "total_paid_gbp": round(total_paid_gbp, 2),
                "avg_payment_per_day_gbp": round(avg_payment_per_day, 3)
            },
            "assumptions": {
                "daily_kwh": daily_kwh,
                "battery_charge_power_kw": battery_charge_power_kw,
                "cheapest_block_usage_percent": Config.STATS_CHEAPEST_BLOCK_USAGE_PERCENT,
                "usage_shifted_to_cheapest_blocks": True,
                "usage_limited_to_negative_slots": True
            }
        }
        
        logger.info(f"Statistics calculated successfully: {total_days} days, {total_negative_slots} negative slots")
        
        return results
    
    @staticmethod
    def save_stats(stats_data, filename=None):
        """
        Save statistics to JSON file.
        
        Args:
            stats_data: Statistics dictionary
            filename: Optional filename. If None, generates from year and region.
        
        Returns:
            Path: Path to saved file
        """
        StatsCalculator._ensure_stats_dir()
        
        if filename is None:
            year = stats_data.get('year', 2025)
            region = stats_data.get('region_code', 'national')
            filename = f"{region}_{year}.json"
        
        filepath = StatsCalculator.STATS_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved statistics to {filepath}")
            return filepath
        except IOError as e:
            logger.error(f"Error saving statistics file {filepath}: {e}")
            raise
    
    @staticmethod
    def load_stats(filename=None, year=2025, region_code='national'):
        """
        Load statistics from JSON file.
        
        Args:
            filename: Optional filename. If None, generates from year and region.
            year: Year for filename generation (if filename not provided)
            region_code: Region code for filename generation (if filename not provided)
                        Use 'national' for national averages file, or region codes (A, B, C, etc.)
        
        Returns:
            dict: Statistics dictionary, or None if file not found
        """
        if filename is None:
            filename = f"{region_code}_{year}.json"
        
        filepath = StatsCalculator.STATS_DIR / filename
        
        if not filepath.exists():
            logger.warning(f"Statistics file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            
            logger.debug(f"Loaded statistics from {filepath}")
            return stats
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading statistics file {filepath}: {e}")
            return None
    
    @staticmethod
    def calculate_national_averages(product_code, year=2025):
        """
        Calculate national averages from all regional statistics.
        
        This method loads all regional stats files and calculates averages
        across all regions to create national statistics.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            year: Year (default 2025)
        
        Returns:
            dict: National statistics dictionary with averaged values
        """
        StatsCalculator._ensure_stats_dir()
        
        # Get all region codes from config
        region_codes = list(Config.OCTOPUS_REGION_NAMES.keys())
        
        # Load all regional stats
        regional_stats = []
        loaded_region_codes = []
        for region_code in region_codes:
            stats = StatsCalculator.load_stats(year=year, region_code=region_code)
            if stats and stats.get('product_code') == product_code:
                regional_stats.append(stats)
                loaded_region_codes.append(region_code)
        
        if not regional_stats:
            logger.warning("No regional statistics found to calculate national averages")
            return None
        
        logger.info(f"Calculating national averages from {len(regional_stats)} regional statistics")
        
        # Get assumptions from first region (should be the same for all)
        assumptions = regional_stats[0].get('assumptions', {})
        price_cap = regional_stats[0].get('price_cap_comparison', {}).get('cap_price_p_per_kwh', 0)
        
        # Calculate averages across all regions
        num_regions = len(regional_stats)
        
        # Average cheapest block prices
        avg_cheapest_block_prices = [
            s.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0)
            for s in regional_stats
        ]
        avg_cheapest_block = sum(avg_cheapest_block_prices) / num_regions if avg_cheapest_block_prices else 0
        
        # Average daily average prices
        avg_daily_average_prices = [
            s.get('daily_average', {}).get('avg_price_p_per_kwh', 0)
            for s in regional_stats
        ]
        avg_daily_average = sum(avg_daily_average_prices) / num_regions if avg_daily_average_prices else 0
        
        # Calculate savings vs daily average
        savings_p_per_kwh = avg_daily_average - avg_cheapest_block
        savings_percentage = (savings_p_per_kwh / avg_daily_average * 100) if avg_daily_average > 0 else 0
        daily_kwh = assumptions.get('daily_kwh', Config.STATS_DAILY_KWH)
        cheapest_block_usage_percent = assumptions.get('cheapest_block_usage_percent', Config.STATS_CHEAPEST_BLOCK_USAGE_PERCENT)
        cheapest_block_usage_kwh = daily_kwh * (cheapest_block_usage_percent / 100.0)
        annual_savings_vs_daily_avg = (savings_p_per_kwh * cheapest_block_usage_kwh * 365) / 100
        
        # Calculate savings vs price cap
        savings_vs_cap_p_per_kwh = price_cap - avg_cheapest_block
        annual_savings_vs_cap = (savings_vs_cap_p_per_kwh * cheapest_block_usage_kwh * 365) / 100
        
        # Average negative pricing statistics (not sum - these represent the same time period across regions)
        negative_slots_list = [
            s.get('negative_pricing', {}).get('total_negative_slots', 0)
            for s in regional_stats
        ]
        negative_hours_list = [
            s.get('negative_pricing', {}).get('total_negative_hours', 0)
            for s in regional_stats
        ]
        total_paid_list = [
            s.get('negative_pricing', {}).get('total_paid_gbp', 0)
            for s in regional_stats
        ]
        
        total_negative_slots = sum(negative_slots_list) / len(negative_slots_list) if negative_slots_list else 0
        total_negative_hours = sum(negative_hours_list) / len(negative_hours_list) if negative_hours_list else 0
        total_paid_gbp = sum(total_paid_list) / len(total_paid_list) if total_paid_list else 0
        avg_payment_per_day = total_paid_gbp / 365 if total_paid_gbp > 0 else 0
        
        # Calculate average negative price per kWh from regional averages
        avg_negative_prices = [
            s.get('negative_pricing', {}).get('avg_negative_price_p_per_kwh', 0)
            for s in regional_stats
            if s.get('negative_pricing', {}).get('avg_negative_price_p_per_kwh', 0) > 0
        ]
        avg_negative_price_p_per_kwh = sum(avg_negative_prices) / len(avg_negative_prices) if avg_negative_prices else 0.0
        
        # Calculate total days processed (average)
        total_days = sum(s.get('days_processed', 0) for s in regional_stats)
        avg_days = total_days / num_regions if num_regions > 0 else 0
        
        # Build national statistics
        national_stats = {
            "year": year,
            "region_code": "national",  # Use 'national' identifier for national averages
            "product_code": product_code,
            "calculation_date": datetime.now(UK_TZ).isoformat(),
            "days_processed": int(avg_days),
            "days_failed": 0,
            "is_national_average": True,  # Flag to indicate this is averaged from regions
            "source_regions": loaded_region_codes,  # List of regions actually used in calculation
            "cheapest_block": {
                "block_hours": StatsCalculator.BLOCK_DURATION_HOURS,
                "avg_price_p_per_kwh": round(avg_cheapest_block, 2)
            },
            "daily_average": {
                "avg_price_p_per_kwh": round(avg_daily_average, 2)
            },
            "savings_vs_daily_average": {
                "savings_p_per_kwh": round(savings_p_per_kwh, 2),
                "savings_percentage": round(savings_percentage, 2),
                "annual_saving_gbp": round(annual_savings_vs_daily_avg, 2)
            },
            "price_cap_comparison": {
                "cap_price_p_per_kwh": price_cap,
                "savings_p_per_kwh": round(savings_vs_cap_p_per_kwh, 2),
                "annual_saving_gbp": round(annual_savings_vs_cap, 2)
            },
            "negative_pricing": {
                "total_negative_slots": int(round(total_negative_slots)),  # Round to integer for slot count
                "total_negative_hours": round(total_negative_hours, 1),
                "avg_negative_price_p_per_kwh": round(avg_negative_price_p_per_kwh, 2),
                "total_paid_gbp": round(total_paid_gbp, 2),
                "avg_payment_per_day_gbp": round(avg_payment_per_day, 3)
            },
            "assumptions": {
                "daily_kwh": assumptions.get('daily_kwh', Config.STATS_DAILY_KWH),
                "battery_charge_power_kw": assumptions.get('battery_charge_power_kw', Config.STATS_BATTERY_CHARGE_POWER_KW),
                "cheapest_block_usage_percent": assumptions.get('cheapest_block_usage_percent', Config.STATS_CHEAPEST_BLOCK_USAGE_PERCENT),
                "usage_shifted_to_cheapest_blocks": True,
                "usage_limited_to_negative_slots": True
            }
        }
        
        logger.info(f"National averages calculated from {num_regions} regions")
        return national_stats
    
    @staticmethod
    def save_national_stats(national_stats, year=2025):
        """
        Save national statistics to file (uses 'national' as region code).
        
        Args:
            national_stats: National statistics dictionary
            year: Year (default 2025)
        
        Returns:
            Path: Path to saved file
        """
        # Override region_code to 'national' for filename
        stats_with_national = national_stats.copy()
        stats_with_national['region_code'] = 'national'
        return StatsCalculator.save_stats(stats_with_national, filename=f"national_{year}.json")

