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
        
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices)
        
        cache_file = CacheManager._get_cache_file('AGILE-24-10-01', 'A')
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
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices, expiry_minutes=60)
        
        # Retrieve cached prices
        result = CacheManager.get_cached_prices('AGILE-24-10-01', 'A')
        
        assert result is not None
        assert len(result) == 1
        assert result[0]['value_inc_vat'] == 16.0
    
    def test_get_cached_prices_expired(self):
        """Test retrieving expired cached prices."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        # Cache with past expiry
        cache_file = CacheManager._get_cache_file('AGILE-24-10-01', 'A')
        data = {
            'prices': prices,
            'fetched_at': (datetime.now() - timedelta(hours=2)).isoformat(),
            'expires_at': (datetime.now() - timedelta(hours=1)).isoformat()
        }
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        
        # Try to retrieve - should return None but file should remain for overwrite
        result = CacheManager.get_cached_prices('AGILE-24-10-01', 'A')
        
        assert result is None
        assert cache_file.exists()  # File remains for in-place update
    
    def test_get_cached_prices_missing(self):
        """Test retrieving non-existent cached prices."""
        result = CacheManager.get_cached_prices('AGILE-24-10-01', 'Z')
        assert result is None
    
    def test_cache_file_overwrite(self):
        """Test that cache file is overwritten in place when refreshed."""
        prices1 = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        prices2 = [
            {'value_inc_vat': 18.0, 'valid_from': '2024-01-15T01:00:00Z', 'valid_to': '2024-01-15T01:30:00Z'}
        ]
        
        cache_file = CacheManager._get_cache_file('AGILE-24-10-01', 'A')
        
        # Cache first set of prices
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices1)
        assert cache_file.exists()
        
        # Cache second set - should overwrite same file
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices2)
        assert cache_file.exists()
        
        # Verify it's the new data
        result = CacheManager.get_cached_prices('AGILE-24-10-01', 'A')
        assert result is not None
        assert len(result) == 1
        assert result[0]['value_inc_vat'] == 18.0
    
    def test_clear_legacy_cache(self):
        """Test clearing legacy per-day cache files."""
        # Create a legacy cache file (with date in filename)
        legacy_file = self.test_cache_dir / 'AGILE-24-10-01_A_2024-01-15.json'
        with open(legacy_file, 'w') as f:
            json.dump({'prices': []}, f)
        
        # Create a new format cache file
        new_file = self.test_cache_dir / 'AGILE-24-10-01_A.json'
        with open(new_file, 'w') as f:
            json.dump({'prices': []}, f)
        
        # Clear legacy cache
        CacheManager.clear_legacy_cache()
        
        # Legacy file should be gone, new file should remain
        assert not legacy_file.exists()
        assert new_file.exists()

