"""
Tests for Octopus API client.
"""
import pytest
from unittest.mock import patch, Mock
from app.api_client import OctopusAPIClient

class TestOctopusAPIClient:
    """Test cases for OctopusAPIClient."""
    
    @patch('app.api_client.requests.get')
    def test_get_regions_success(self, mock_get):
        """Test successful region fetching."""
        mock_response = Mock()
        # Mock the grid supply points API response structure
        mock_response.json.return_value = {
            'results': [
                {'group_id': '_A'},
                {'group_id': '_B'}
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = OctopusAPIClient.get_regions()
        
        assert 'results' in result
        assert len(result['results']) == 2
        assert result['results'][0]['region'] == 'A'
        assert result['results'][0]['name'] == 'Eastern England'
        mock_get.assert_called_once()
    
    @patch('app.api_client.requests.get')
    def test_get_regions_timeout(self, mock_get):
        """Test timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(requests.exceptions.Timeout):
            OctopusAPIClient.get_regions()
    
    @patch('app.api_client.requests.get')
    def test_get_prices_success(self, mock_get):
        """Test successful price fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'value_inc_vat': 16.0,
                    'valid_from': '2024-01-15T00:00:00Z',
                    'valid_to': '2024-01-15T00:30:00Z'
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = OctopusAPIClient.get_prices('AGILE-24-10-01', 'A')
        
        assert 'results' in result
        assert len(result['results']) == 1
        assert result['results'][0]['value_inc_vat'] == 16.0
        mock_get.assert_called_once()
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_single_page(self, mock_get):
        """Test successful Agile product discovery (single page)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'code': 'AGILE-24-10-01',
                    'full_name': 'Agile Octopus October 2024',
                    'direction': 'IMPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                },
                {
                    'code': 'SOME-OTHER-24-10-01',
                    'full_name': 'Some Other Tariff',
                    'direction': 'IMPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                }
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = OctopusAPIClient.get_agile_products()
        
        assert len(result) == 1
        assert result[0]['code'] == 'AGILE-24-10-01'
        assert result[0]['full_name'] == 'Agile Octopus October 2024'
        mock_get.assert_called_once()
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_pagination(self, mock_get):
        """Test Agile product discovery with pagination."""
        # First page response
        first_page_response = Mock()
        first_page_response.json.return_value = {
            'count': 100,
            'next': 'https://api.octopus.energy/v1/products/?page=2',
            'previous': None,
            'results': [
                {
                    'code': 'AGILE-24-10-01',
                    'full_name': 'Agile Octopus October 2024',
                    'direction': 'IMPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                }
            ]
        }
        first_page_response.status_code = 200
        first_page_response.raise_for_status.return_value = None
        
        # Second page response
        second_page_response = Mock()
        from datetime import datetime, timezone, timedelta
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        second_page_response.json.return_value = {
            'count': 100,
            'next': None,
            'previous': 'https://api.octopus.energy/v1/products/?page=1',
            'results': [
                {
                    'code': 'AGILE-23-09-01',
                    'full_name': 'Agile Octopus September 2023',
                    'direction': 'IMPORT',
                    'available_from': '2023-09-01T00:00:00Z',
                    'available_to': future_date  # Active (in future)
                }
            ]
        }
        second_page_response.status_code = 200
        second_page_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [first_page_response, second_page_response]
        
        result = OctopusAPIClient.get_agile_products()
        
        assert len(result) == 2
        assert result[0]['code'] == 'AGILE-24-10-01'
        assert result[1]['code'] == 'AGILE-23-09-01'
        assert mock_get.call_count == 2
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_direction_filter(self, mock_get):
        """Test Agile product discovery with direction filter."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'count': 3,
            'next': None,
            'previous': None,
            'results': [
                {
                    'code': 'AGILE-24-10-01',
                    'full_name': 'Agile Octopus October 2024',
                    'direction': 'IMPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                },
                {
                    'code': 'AGILE-EXPORT-24-10-01',
                    'full_name': 'Agile Octopus Export October 2024',
                    'direction': 'EXPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                },
                {
                    'code': 'AGILE-BOTH-24-10-01',
                    'full_name': 'Agile Octopus Both October 2024',
                    'direction': 'BOTH',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None
                }
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test IMPORT filter - only includes IMPORT direction products
        result_import = OctopusAPIClient.get_agile_products(direction_filter='IMPORT')
        assert len(result_import) == 1
        assert result_import[0]['code'] == 'AGILE-24-10-01'
        
        # Reset mock for next test
        mock_get.reset_mock()
        
        # Test EXPORT filter - only includes EXPORT direction products
        result_export = OctopusAPIClient.get_agile_products(direction_filter='EXPORT')
        assert len(result_export) == 1
        assert result_export[0]['code'] == 'AGILE-EXPORT-24-10-01'
        
        # Reset mock for next test
        mock_get.reset_mock()
        
        # Test BOTH filter - includes all products
        result_both = OctopusAPIClient.get_agile_products(direction_filter='BOTH')
        assert len(result_both) == 3
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_inactive_filtered(self, mock_get):
        """Test that inactive products are filtered out."""
        from datetime import datetime, timezone, timedelta
        
        mock_response = Mock()
        # available_to in the past - should be filtered out
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mock_response.json.return_value = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'code': 'AGILE-24-10-01',
                    'full_name': 'Agile Octopus October 2024',
                    'direction': 'IMPORT',
                    'available_from': '2024-10-01T00:00:00Z',
                    'available_to': None  # Active
                },
                {
                    'code': 'AGILE-23-09-01',
                    'full_name': 'Agile Octopus September 2023',
                    'direction': 'IMPORT',
                    'available_from': '2023-09-01T00:00:00Z',
                    'available_to': past_date  # Inactive (in past)
                }
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = OctopusAPIClient.get_agile_products()
        
        assert len(result) == 1
        assert result[0]['code'] == 'AGILE-24-10-01'
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_no_results(self, mock_get):
        """Test when no Agile products are found."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = OctopusAPIClient.get_agile_products()
        
        assert result == []
    
    @patch('app.api_client.requests.get')
    def test_get_agile_products_api_error(self, mock_get):
        """Test error handling when Products API fails."""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("API Error")
        
        with pytest.raises(requests.exceptions.RequestException):
            OctopusAPIClient.get_agile_products()

