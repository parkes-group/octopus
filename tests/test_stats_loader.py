"""
Tests for statistics loader.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch
from app.stats_loader import StatsLoader
from app.stats_calculator import StatsCalculator


class TestStatsLoader:
    """Test cases for StatsLoader."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a test stats directory
        self.test_stats_dir = Path('tests/test_stats_loader')
        self.test_stats_dir.mkdir(parents=True, exist_ok=True)
        self.original_stats_dir = StatsCalculator.STATS_DIR
        StatsCalculator.STATS_DIR = self.test_stats_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test directory
        if self.test_stats_dir.exists():
            for file in self.test_stats_dir.glob('*.json'):
                file.unlink()
            self.test_stats_dir.rmdir()
        
        # Reset to default
        StatsCalculator.STATS_DIR = self.original_stats_dir
    
    def test_load_2025_stats_national(self):
        """Test loading national 2025 statistics."""
        # Create test national stats file
        stats_data = {
            'year': 2025,
            'region_code': 'national',
            'product_code': 'AGILE-24-10-01',
            'cheapest_block': {'avg_price_p_per_kwh': 14.97},
            'daily_average': {'avg_price_p_per_kwh': 18.19},
            'savings_vs_daily_average': {'annual_saving_gbp': 45.3},
            'price_cap_comparison': {'annual_saving_gbp': 191.54},
            'negative_pricing': {
                'total_negative_slots': 52,
                'total_negative_hours': 26.0,
                'avg_negative_price_p_per_kwh': 1.1,
                'total_paid_gbp': 1.0
            },
            'assumptions': {
                'daily_kwh': 11.0,
                'battery_charge_power_kw': 3.5
            }
        }
        test_file = self.test_stats_dir / 'national_2025.json'
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f)
        
        result = StatsLoader.load_2025_stats(region_code='national')
        
        assert result is not None
        assert result['region_code'] == 'national'
        assert result['negative_pricing']['total_negative_slots'] == 52
    
    def test_load_2025_stats_regional(self):
        """Test loading regional 2025 statistics."""
        # Create test regional stats file
        stats_data = {
            'year': 2025,
            'region_code': 'A',
            'product_code': 'AGILE-24-10-01',
            'cheapest_block': {'avg_price_p_per_kwh': 14.72},
            'daily_average': {'avg_price_p_per_kwh': 17.94},
            'negative_pricing': {
                'total_negative_slots': 52,
                'total_negative_hours': 26.0,
                'avg_negative_price_p_per_kwh': 1.1,
                'total_paid_gbp': 1.0
            }
        }
        test_file = self.test_stats_dir / 'A_2025.json'
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f)
        
        result = StatsLoader.load_2025_stats(region_code='A')
        
        assert result is not None
        assert result['region_code'] == 'A'
    
    def test_get_stats_for_display_national(self):
        """Test formatting national stats for display."""
        # Create test national stats file
        stats_data = {
            'year': 2025,
            'region_code': 'national',
            'cheapest_block': {'avg_price_p_per_kwh': 14.97},
            'daily_average': {'avg_price_p_per_kwh': 18.19},
            'savings_vs_daily_average': {
                'annual_saving_gbp': 45.3,
                'savings_percentage': 17.72
            },
            'price_cap_comparison': {
                'annual_saving_gbp': 191.54,
                'cap_price_p_per_kwh': 28.6
            },
            'negative_pricing': {
                'total_negative_slots': 52,
                'total_negative_hours': 26.0,
                'avg_negative_price_p_per_kwh': 1.1,
                'total_paid_gbp': 1.0,
                'avg_payment_per_day_gbp': 0.003
            },
            'assumptions': {
                'daily_kwh': 11.0,
                'battery_charge_power_kw': 3.5
            }
        }
        test_file = self.test_stats_dir / 'national_2025.json'
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f)
        
        result = StatsLoader.get_stats_for_display(region_code='national')
        
        assert result is not None
        assert result['cheapest_block_price'] == 14.97
        assert result['daily_average_price'] == 18.19
        assert result['savings_vs_daily_avg'] == 45.3
        assert result['savings_vs_cap'] == 191.54
        assert result['negative_pricing']['total_slots'] == 52
        assert result['negative_pricing']['total_hours'] == 26.0
        assert result['negative_pricing']['avg_price_p_per_kwh'] == 1.1
        assert result['negative_pricing']['total_paid'] == 1.0
    
    def test_get_stats_for_display_not_found(self):
        """Test handling when stats file doesn't exist."""
        result = StatsLoader.get_stats_for_display(region_code='Z')
        assert result is None

