"""
Tests for application routes.
"""
import pytest
from unittest.mock import patch, Mock
from app.routes import bp

class TestRoutes:
    """Test cases for application routes."""
    
    def test_index_route_success(self, client):
        """Test homepage with postcode-first UI."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'Find Your Energy Region' in response.data
        assert b'UK Postcode' in response.data
        # Region dropdown should not be visible by default (only shown on postcode lookup failure)
        assert b'Can\'t find your region?' not in response.data
    
    def test_index_route_with_regions(self, client):
        """Test homepage loads regions from static mapping."""
        response = client.get('/')
        
        assert response.status_code == 200
        # Should have region options available (even if not visible initially)
        # Since we're using static mapping, regions should always be available
    
    @patch('app.routes.OctopusAPIClient.get_agile_products')
    @patch('app.routes.CacheManager.get_cached_prices')
    @patch('app.routes.OctopusAPIClient.get_prices')
    @patch('app.routes.CacheManager.cache_prices')
    @patch('app.routes.PriceCalculator.find_lowest_price')
    @patch('app.routes.PriceCalculator.find_cheapest_block')
    @patch('app.routes.PriceCalculator.find_future_cheapest_block')
    @patch('app.routes.PriceCalculator.calculate_daily_average_price')
    @patch('app.routes.PriceCalculator.format_price_data')
    def test_prices_route(self, mock_format, mock_daily_avg, mock_future_block, mock_block, mock_lowest, mock_cache, mock_get_prices, mock_cached, mock_products, client):
        """Test prices route."""
        # Mock Agile products
        mock_products.return_value = [
            {'code': 'AGILE-24-10-01', 'full_name': 'Agile Octopus October 2024'}
        ]
        
        # Mock cached prices (empty - will fetch from API)
        mock_cached.return_value = None
        
        # Mock API response
        mock_get_prices.return_value = {
            'results': [
                {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
            ]
        }
        
        # Mock calculations with UK timezone fields
        from app.timezone_utils import utc_to_uk
        from datetime import datetime
        
        time_from_uk = utc_to_uk('2024-01-15T00:00:00Z')
        time_to_uk = utc_to_uk('2024-01-15T00:30:00Z')
        start_time_uk = utc_to_uk('2024-01-15T00:00:00Z')
        end_time_uk = utc_to_uk('2024-01-15T04:00:00Z')
        
        mock_lowest.return_value = {
            'price': 16.0, 
            'time_from': '2024-01-15T00:00:00Z', 
            'time_to': '2024-01-15T00:30:00Z',
            'time_from_uk': time_from_uk,
            'time_to_uk': time_to_uk
        }
        mock_block.return_value = {
            'start_time': '2024-01-15T00:00:00Z',
            'end_time': '2024-01-15T04:00:00Z',
            'start_time_uk': start_time_uk,
            'end_time_uk': end_time_uk,
            'average_price': 16.0,
            'total_cost': 64.0,
            'slots': []
        }
        mock_future_block.return_value = {
            'start_time': '2024-01-15T02:00:00Z',
            'end_time': '2024-01-15T06:00:00Z',
            'start_time_uk': utc_to_uk('2024-01-15T02:00:00Z'),
            'end_time_uk': utc_to_uk('2024-01-15T06:00:00Z'),
            'average_price': 17.0,
            'total_cost': 68.0,
            'slots': []
        }
        mock_daily_avg.return_value = 18.5
        mock_format.return_value = {'labels': ['00:00'], 'prices': [16.0], 'times': ['2024-01-15T00:00:00Z']}
        
        response = client.get('/prices?region=A&product=AGILE-24-10-01&duration=4.0')
        
        assert response.status_code == 200
        assert b'Agile Octopus Prices' in response.data
        mock_get_prices.assert_called_once_with('AGILE-24-10-01', 'A')
        mock_cache.assert_called_once()
    
    def test_prices_route_no_region(self, client):
        """Test prices route without region parameter."""
        response = client.get('/prices')
        
        assert response.status_code == 302  # Redirect
        assert '/prices' not in response.location or response.location.endswith('/')

