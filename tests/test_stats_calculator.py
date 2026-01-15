"""
Tests for statistics calculator.
"""
import pytest
import json
from pathlib import Path
import shutil
from unittest.mock import patch, Mock
from app.stats_calculator import StatsCalculator
from app.config import Config


class TestStatsCalculator:
    """Test cases for StatsCalculator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a test stats directory
        self.test_stats_dir = Path('tests/test_stats')
        self.test_stats_dir.mkdir(parents=True, exist_ok=True)
        self.original_stats_dir = StatsCalculator.STATS_DIR
        StatsCalculator.STATS_DIR = self.test_stats_dir
        
        # Use a test raw data directory
        self.test_raw_dir = Path('tests/test_raw')
        self.test_raw_dir.mkdir(parents=True, exist_ok=True)
        self.original_raw_dir = StatsCalculator.RAW_DATA_DIR
        StatsCalculator.RAW_DATA_DIR = self.test_raw_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test directories (including year subdirectories)
        shutil.rmtree(self.test_stats_dir, ignore_errors=True)
        shutil.rmtree(self.test_raw_dir, ignore_errors=True)
        
        # Reset to defaults
        StatsCalculator.STATS_DIR = self.original_stats_dir
        StatsCalculator.RAW_DATA_DIR = self.original_raw_dir
    
    def test_load_raw_data_not_found(self):
        """Test loading raw data when file doesn't exist."""
        result = StatsCalculator.load_raw_data('Z', year=2025)
        assert result is None
    
    def test_load_raw_data_success(self):
        """Test loading raw data from file."""
        # Create test raw data file
        test_file = self.test_raw_dir / '2025' / 'A_2025.json'
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_data = {
            'prices': [
                {'value_inc_vat': 16.0, 'valid_from': '2025-01-01T00:00:00Z', 'valid_to': '2025-01-01T00:30:00Z'},
                {'value_inc_vat': 18.0, 'valid_from': '2025-01-01T00:30:00Z', 'valid_to': '2025-01-01T01:00:00Z'}
            ]
        }
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        result = StatsCalculator.load_raw_data('A', year=2025)
        
        assert result is not None
        assert len(result) == 2
        assert result[0]['value_inc_vat'] == 16.0
    
    @patch('app.stats_calculator.PriceCalculator.find_cheapest_block')
    @patch('app.stats_calculator.PriceCalculator.calculate_daily_average_price')
    def test_calculate_2025_stats_negative_pricing_includes_zero(self, mock_daily_avg, mock_block):
        """Test that negative pricing calculation includes zero-price slots."""
        # Create test raw data with negative and zero prices
        test_file = self.test_raw_dir / '2025' / 'A_2025.json'
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_data = {
            'prices': [
                {'value_inc_vat': -1.5, 'valid_from': '2025-01-01T00:00:00Z', 'valid_to': '2025-01-01T00:30:00Z'},
                {'value_inc_vat': 0.0, 'valid_from': '2025-01-01T00:30:00Z', 'valid_to': '2025-01-01T01:00:00Z'},
                {'value_inc_vat': 16.0, 'valid_from': '2025-01-01T01:00:00Z', 'valid_to': '2025-01-01T01:30:00Z'},
                {'value_inc_vat': 18.0, 'valid_from': '2025-01-01T01:30:00Z', 'valid_to': '2025-01-01T02:00:00Z'},
                {'value_inc_vat': 20.0, 'valid_from': '2025-01-01T02:00:00Z', 'valid_to': '2025-01-01T02:30:00Z'},
                {'value_inc_vat': 22.0, 'valid_from': '2025-01-01T02:30:00Z', 'valid_to': '2025-01-01T03:00:00Z'},
                {'value_inc_vat': 24.0, 'valid_from': '2025-01-01T03:00:00Z', 'valid_to': '2025-01-01T03:30:00Z'},
            ]
        }
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        # Mock calculator methods
        mock_block.return_value = {
            'average_price': 16.0,
            'start_time': '2025-01-01T01:00:00Z',
            'end_time': '2025-01-01T04:30:00Z',
            'slots': []
        }
        mock_daily_avg.return_value = 18.0
        
        # Calculate stats (only one day of data)
        result = StatsCalculator.calculate_2025_stats('AGILE-24-10-01', 'A')
        
        assert result is not None
        assert result['negative_pricing']['total_negative_slots'] == 2  # -1.5 and 0.0
        assert result['negative_pricing']['total_negative_hours'] == 1.0  # 2 slots * 0.5
    
    @patch('app.stats_calculator.PriceCalculator.find_cheapest_block')
    @patch('app.stats_calculator.PriceCalculator.calculate_daily_average_price')
    def test_calculate_2025_stats_negative_pricing_excludes_positive(self, mock_daily_avg, mock_block):
        """Test that positive prices are excluded from negative pricing."""
        # Create test raw data with only positive prices
        test_file = self.test_raw_dir / '2025' / 'A_2025.json'
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_data = {
            'prices': [
                {'value_inc_vat': 16.0, 'valid_from': '2025-01-01T00:00:00Z', 'valid_to': '2025-01-01T00:30:00Z'},
                {'value_inc_vat': 18.0, 'valid_from': '2025-01-01T00:30:00Z', 'valid_to': '2025-01-01T01:00:00Z'},
            ]
        }
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        mock_block.return_value = {
            'average_price': 16.0,
            'start_time': '2025-01-01T00:00:00Z',
            'end_time': '2025-01-01T01:00:00Z',
            'slots': []
        }
        mock_daily_avg.return_value = 17.0
        
        result = StatsCalculator.calculate_2025_stats('AGILE-24-10-01', 'A')
        
        assert result is not None
        assert result['negative_pricing']['total_negative_slots'] == 0
    
    def test_save_stats(self):
        """Test saving statistics to file."""
        stats_data = {
            'year': 2025,
            'region_code': 'A',
            'product_code': 'AGILE-24-10-01',
            'cheapest_block': {'avg_price_p_per_kwh': 14.0},
            'daily_average': {'avg_price_p_per_kwh': 18.0},
            'negative_pricing': {
                'total_negative_slots': 10,
                'total_negative_hours': 5.0,
                'total_paid_gbp': 0.5
            }
        }
        
        filepath = StatsCalculator.save_stats(stats_data, filename='test_A_2025.json')
        
        assert filepath.exists()
        with open(filepath, 'r') as f:
            loaded = json.load(f)
        
        assert loaded['year'] == 2025
        assert loaded['region_code'] == 'A'
        assert loaded['negative_pricing']['total_negative_slots'] == 10
    
    def test_load_stats(self):
        """Test loading statistics from file."""
        # Create test stats file
        stats_data = {
            'year': 2025,
            'region_code': 'A',
            'product_code': 'AGILE-24-10-01',
            'cheapest_block': {'avg_price_p_per_kwh': 14.0},
            'daily_average': {'avg_price_p_per_kwh': 18.0}
        }
        test_file = self.test_stats_dir / '2025' / 'A_2025.json'
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f)
        
        result = StatsCalculator.load_stats(year=2025, region_code='A')
        
        assert result is not None
        assert result['year'] == 2025
        assert result['region_code'] == 'A'
    
    def test_calculate_national_averages_averages_negative_slots(self):
        """Test that national averages correctly average (not sum) negative slots."""
        # Create test regional stats files
        for region_code in ['A', 'B', 'C']:
            stats_data = {
                'year': 2025,
                'region_code': region_code,
                'product_code': 'AGILE-24-10-01',
                'cheapest_block': {'avg_price_p_per_kwh': 14.0},
                'daily_average': {'avg_price_p_per_kwh': 18.0},
                'savings_vs_daily_average': {'annual_saving_gbp': 45.0},
                'price_cap_comparison': {'annual_saving_gbp': 190.0},
                'negative_pricing': {
                    'total_negative_slots': 38,  # Same for all regions
                    'total_negative_hours': 19.0,
                    'avg_negative_price_p_per_kwh': 1.5,
                    'total_paid_gbp': 1.0
                },
                'assumptions': {
                    'daily_kwh': 11.0,
                    'battery_charge_power_kw': 3.5
                }
            }
            test_file = self.test_stats_dir / '2025' / f'{region_code}_2025.json'
            test_file.parent.mkdir(parents=True, exist_ok=True)
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f)
        
        result = StatsCalculator.calculate_national_averages('AGILE-24-10-01', year=2025)
        
        assert result is not None
        assert result['region_code'] == 'national'
        assert result['is_national_average'] is True
        # Should be average (38), not sum (114)
        assert result['negative_pricing']['total_negative_slots'] == 38
        assert result['negative_pricing']['total_negative_hours'] == 19.0
        assert result['negative_pricing']['total_paid_gbp'] == 1.0
        assert len(result['source_regions']) == 3

