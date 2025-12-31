"""
Tests for price calculator.
"""
import pytest
from app.price_calculator import PriceCalculator

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
        prices = [
            {'value_inc_vat': 20.0, 'valid_from': f'2024-01-15T{i:02d}:00:00Z', 'valid_to': f'2024-01-15T{i:02d}:30:00Z'}
            for i in range(10)
        ]
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

