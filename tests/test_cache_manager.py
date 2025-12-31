"""
Tests for cache manager.
"""
import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from app.cache_manager import CacheManager

class TestCacheManager:
    """Test cases for CacheManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a test cache directory
        self.test_cache_dir = Path('tests/test_cache')
        self.test_cache_dir.mkdir(parents=True, exist_ok=True)
        CacheManager.CACHE_DIR = self.test_cache_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test cache files
        if self.test_cache_dir.exists():
            for file in self.test_cache_dir.glob('*.json'):
                file.unlink()
            self.test_cache_dir.rmdir()
        # Reset to default
        CacheManager.CACHE_DIR = Path('app/cache')
    
    def test_cache_prices(self):
        """Test caching prices."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        CacheManager.cache_prices('A', '2024-01-15', prices)
        
        cache_file = CacheManager._get_cache_file('A', '2024-01-15')
        assert cache_file.exists()
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        assert 'prices' in data
        assert 'fetched_at' in data
        assert 'expires_at' in data
        assert len(data['prices']) == 1
    
    def test_get_cached_prices_valid(self):
        """Test retrieving valid cached prices."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        # Cache prices
        CacheManager.cache_prices('A', '2024-01-15', prices, expiry_minutes=60)
        
        # Retrieve cached prices
        result = CacheManager.get_cached_prices('A', '2024-01-15')
        
        assert result is not None
        assert len(result) == 1
        assert result[0]['value_inc_vat'] == 16.0
    
    def test_get_cached_prices_expired(self):
        """Test retrieving expired cached prices."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        # Cache with past expiry
        cache_file = CacheManager._get_cache_file('A', '2024-01-15')
        data = {
            'prices': prices,
            'fetched_at': (datetime.now() - timedelta(hours=2)).isoformat(),
            'expires_at': (datetime.now() - timedelta(hours=1)).isoformat()
        }
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        
        # Try to retrieve
        result = CacheManager.get_cached_prices('A', '2024-01-15')
        
        assert result is None
        assert not cache_file.exists()  # Should be deleted
    
    def test_get_cached_prices_missing(self):
        """Test retrieving non-existent cached prices."""
        result = CacheManager.get_cached_prices('Z', '2024-01-15')
        assert result is None

