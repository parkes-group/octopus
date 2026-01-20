"""
Tests for price calculator.
"""
import pytest
from app.price_calculator import PriceCalculator
from datetime import datetime, timedelta, timezone

class TestPriceCalculator:
    """Test cases for PriceCalculator."""
    
    def test_find_lowest_price(self):
        """Test finding lowest price."""
        prices = [
            {'value_inc_vat': 20.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'},
            {'value_inc_vat': 15.0, 'valid_from': '2024-01-15T01:00:00Z', 'valid_to': '2024-01-15T01:30:00Z'},
            {'value_inc_vat': 18.0, 'valid_from': '2024-01-15T02:00:00Z', 'valid_to': '2024-01-15T02:30:00Z'}
        ]
        
        result = PriceCalculator.find_lowest_price(prices)
        
        assert result is not None
        assert result['price'] == 15.0
        assert result['time_from'] == '2024-01-15T01:00:00Z'
    
    def test_find_lowest_price_empty(self):
        """Test with empty price list."""
        result = PriceCalculator.find_lowest_price([])
        assert result is None
    
    def test_find_cheapest_block(self):
        """Test finding cheapest block."""
        prices = [
            {'value_inc_vat': 20.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'},
            {'value_inc_vat': 15.0, 'valid_from': '2024-01-15T00:30:00Z', 'valid_to': '2024-01-15T01:00:00Z'},
            {'value_inc_vat': 18.0, 'valid_from': '2024-01-15T01:00:00Z', 'valid_to': '2024-01-15T01:30:00Z'},
            {'value_inc_vat': 22.0, 'valid_from': '2024-01-15T01:30:00Z', 'valid_to': '2024-01-15T02:00:00Z'}
        ]
        
        result = PriceCalculator.find_cheapest_block(prices, 1.0)  # 1 hour = 2 slots
        
        assert result is not None
        assert result['average_price'] == 16.5  # (15.0 + 18.0) / 2
        assert result['start_time'] == '2024-01-15T00:30:00Z'
    
    def test_find_cheapest_block_decimal_duration(self):
        """Test finding cheapest block with decimal duration (3.5 hours = 7 slots)."""
        # Build contiguous 30-minute slots (no gaps) so a 3.5h window (7 slots) is possible.
        start = datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)
        prices = []
        for i in range(10):
            vf = start + timedelta(minutes=30 * i)
            vt = vf + timedelta(minutes=30)
            prices.append(
                {
                    "value_inc_vat": 20.0,
                    "valid_from": vf.isoformat().replace("+00:00", "Z"),
                    "valid_to": vt.isoformat().replace("+00:00", "Z"),
                }
            )
        # Make middle block cheaper
        prices[2]['value_inc_vat'] = 10.0
        prices[3]['value_inc_vat'] = 10.0
        prices[4]['value_inc_vat'] = 10.0
        prices[5]['value_inc_vat'] = 10.0
        prices[6]['value_inc_vat'] = 10.0
        prices[7]['value_inc_vat'] = 10.0
        prices[8]['value_inc_vat'] = 10.0
        
        result = PriceCalculator.find_cheapest_block(prices, 3.5)  # 3.5 hours = 7 slots
        
        assert result is not None
        assert result['average_price'] == 10.0
    
    def test_find_cheapest_block_insufficient_slots(self):
        """Test with insufficient price slots."""
        prices = [
            {'value_inc_vat': 20.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        result = PriceCalculator.find_cheapest_block(prices, 2.0)  # 2 hours = 4 slots needed
        
        assert result is None
    
    def test_calculate_charging_cost(self):
        """Test cost calculation."""
        result = PriceCalculator.calculate_charging_cost(16.5, 10.0)  # 16.5 p/kWh, 10 kWh
        
        assert result == 1.65  # (16.5 * 10) / 100 = 1.65 pounds
    
    def test_calculate_charging_cost_invalid(self):
        """Test cost calculation with invalid inputs."""
        assert PriceCalculator.calculate_charging_cost(None, 10.0) is None
        assert PriceCalculator.calculate_charging_cost(16.5, None) is None
        assert PriceCalculator.calculate_charging_cost(-5, 10.0) is None
    
    def test_format_price_data(self):
        """Test price data formatting for charts."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'},
            {'value_inc_vat': 18.0, 'valid_from': '2024-01-15T00:30:00Z', 'valid_to': '2024-01-15T01:00:00Z'}
        ]
        
        result = PriceCalculator.format_price_data(prices)
        
        assert 'labels' in result
        assert 'prices' in result
        assert 'times' in result
        assert len(result['labels']) == 2
        assert result['prices'][0] == 16.0
        assert result['prices'][1] == 18.0
    
    def test_calculate_daily_averages_by_date_single_day(self):
        """Test calculating daily averages for single day."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'},
            {'value_inc_vat': 18.0, 'valid_from': '2024-01-15T00:30:00Z', 'valid_to': '2024-01-15T01:00:00Z'},
            {'value_inc_vat': 20.0, 'valid_from': '2024-01-15T01:00:00Z', 'valid_to': '2024-01-15T01:30:00Z'}
        ]
        
        result = PriceCalculator.calculate_daily_averages_by_date(prices)
        
        assert len(result) == 1
        assert result[0]['date'] == '2024-01-15'
        assert result[0]['date_display'] == '15/01/24'
        assert result[0]['average_price'] == 18.0  # (16 + 18 + 20) / 3
    
    def test_calculate_daily_averages_by_date_two_days(self):
        """Test calculating daily averages for two calendar days."""
        prices = [
            {'value_inc_vat': 10.0, 'valid_from': '2024-01-15T23:00:00Z', 'valid_to': '2024-01-15T23:30:00Z'},
            {'value_inc_vat': 12.0, 'valid_from': '2024-01-16T00:00:00Z', 'valid_to': '2024-01-16T00:30:00Z'},
            {'value_inc_vat': 14.0, 'valid_from': '2024-01-16T00:30:00Z', 'valid_to': '2024-01-16T01:00:00Z'},
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-16T01:00:00Z', 'valid_to': '2024-01-16T01:30:00Z'}
        ]
        
        result = PriceCalculator.calculate_daily_averages_by_date(prices)
        
        assert len(result) == 2
        assert result[0]['date'] == '2024-01-15'
        assert result[0]['date_display'] == '15/01/24'
        assert result[0]['average_price'] == 10.0  # Single price for day 1
        assert result[1]['date'] == '2024-01-16'
        assert result[1]['date_display'] == '16/01/24'
        assert result[1]['average_price'] == 14.0  # (12 + 14 + 16) / 3
    
    def test_calculate_daily_averages_by_date_empty(self):
        """Test with empty price list."""
        result = PriceCalculator.calculate_daily_averages_by_date([])
        assert result == []

    def test_filter_prices_from_uk_date_drops_past_days(self):
        # Start date = 2026-01-20 (UK); include one slot from 19th and one from 20th.
        start_date_uk = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc).date()
        prices = [
            {"value_inc_vat": 10.0, "valid_from": "2026-01-19T23:00:00Z", "valid_to": "2026-01-19T23:30:00Z"},
            {"value_inc_vat": 12.0, "valid_from": "2026-01-20T00:00:00Z", "valid_to": "2026-01-20T00:30:00Z"},
        ]
        filtered = PriceCalculator.filter_prices_from_uk_date(prices, start_date_uk)
        assert len(filtered) == 1
        assert filtered[0]["valid_from"] == "2026-01-20T00:00:00Z"
