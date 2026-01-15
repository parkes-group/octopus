"""
Statistics loader utility for frontend display.
Loads pre-calculated statistics from JSON files.
"""
import logging
from pathlib import Path
from app.stats_calculator import StatsCalculator

logger = logging.getLogger(__name__)

class StatsLoader:
    """Loads and provides access to historical statistics."""
    
    @staticmethod
    def load_2025_stats(region_code='national'):
        """
        Load 2025 statistics for a region.
        
        Args:
            region_code: Region code (default 'national' for national averages)
                        Use 'national' for national stats, or specific region codes (A, B, C, etc.) for regional stats.
        
        Returns:
            dict: Statistics dictionary, or None if not found
        """
        return StatsCalculator.load_stats(year=2025, region_code=region_code)

    @staticmethod
    def load_stats(year: int = 2025, region_code: str = 'national'):
        """
        Load statistics for a given year and region.

        Args:
            year: Year (default 2025)
            region_code: Region code (default 'national' for national averages)

        Returns:
            dict: Statistics dictionary, or None if not found
        """
        return StatsCalculator.load_stats(year=year, region_code=region_code)
    
    @staticmethod
    def get_stats_for_display(region_code='national', year: int = 2025):
        """
        Get formatted statistics for frontend display.
        
        Args:
            region_code: Region code (default 'national' for national averages)
                        Use 'national' for national stats, or specific region codes (A, B, C, etc.) for regional stats.
            year: Year (default 2025)
        
        Returns:
            dict: Formatted statistics with display-friendly values, or None if not available
        """
        stats = StatsLoader.load_stats(year=year, region_code=region_code)
        
        if not stats:
            return None
        
        # Format for display
        formatted = {
            'year': stats.get('year', year),
            'coverage': stats.get('coverage'),
            'days_covered': stats.get('days_covered', stats.get('days_processed')),
            'cheapest_block_price': stats.get('cheapest_block', {}).get('avg_price_p_per_kwh', 0),
            'daily_average_price': stats.get('daily_average', {}).get('avg_price_p_per_kwh', 0),
            'savings_vs_daily_avg': stats.get('savings_vs_daily_average', {}).get('annual_saving_gbp', 0),
            'savings_vs_daily_avg_pct': stats.get('savings_vs_daily_average', {}).get('savings_percentage', 0),
            'savings_vs_cap': stats.get('price_cap_comparison', {}).get('annual_saving_gbp', 0),
            'price_cap': stats.get('price_cap_comparison', {}).get('cap_price_p_per_kwh', 0),
            'negative_pricing': {
                'total_slots': stats.get('negative_pricing', {}).get('total_negative_slots', 0),
                'total_hours': stats.get('negative_pricing', {}).get('total_negative_hours', 0),
                'avg_price_p_per_kwh': stats.get('negative_pricing', {}).get('avg_negative_price_p_per_kwh', 0),
                'total_paid': stats.get('negative_pricing', {}).get('total_paid_gbp', 0),
                'avg_per_day': stats.get('negative_pricing', {}).get('avg_payment_per_day_gbp', 0)
            },
            'assumptions': stats.get('assumptions', {})
        }
        
        return formatted

