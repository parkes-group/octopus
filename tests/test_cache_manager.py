"""
Tests for cache manager.
"""
import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.cache_manager import CacheManager
from app.timezone_utils import UK_TZ, get_uk_now

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
    
    def test_determine_cache_expiry_first_entry_tomorrow(self):
        """Test cache expiry when first entry (reverse order) is for tomorrow."""
        # Get today's date in UK timezone
        uk_now = get_uk_now()
        today_uk = uk_now.date()
        tomorrow_uk = today_uk + timedelta(days=1)
        
        # Simulate reverse chronological order: first entry is tomorrow
        first_entry = {
            'valid_to': f"{tomorrow_uk}T23:30:00Z"  # Tomorrow 23:30 UTC
        }
        last_entry = {
            'valid_to': f"{today_uk}T00:00:00Z"  # Today 00:00 UTC
        }
        
        # Determine expiry
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        
        # Should expire at tomorrow 16:00 UK time
        expected_expiry = datetime.combine(
            tomorrow_uk,
            datetime.min.time().replace(hour=16, minute=0, second=0, microsecond=0)
        ).replace(tzinfo=UK_TZ)
        
        # Allow small tolerance for execution time
        assert expires_at is not None
        assert abs((expires_at - expected_expiry).total_seconds()) < 1
    
    def test_determine_cache_expiry_last_entry_tomorrow(self):
        """Test cache expiry when last entry is for tomorrow (normal chronological order)."""
        # Get today's date in UK timezone
        uk_now = get_uk_now()
        today_uk = uk_now.date()
        tomorrow_uk = today_uk + timedelta(days=1)
        
        # Simulate normal chronological order: last entry is tomorrow
        first_entry = {
            'valid_to': f"{today_uk}T00:00:00Z"  # Today 00:00 UTC
        }
        last_entry = {
            'valid_to': f"{tomorrow_uk}T23:30:00Z"  # Tomorrow 23:30 UTC
        }
        
        # Determine expiry
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        
        # Should expire at tomorrow 16:00 UK time
        expected_expiry = datetime.combine(
            tomorrow_uk,
            datetime.min.time().replace(hour=16, minute=0, second=0, microsecond=0)
        ).replace(tzinfo=UK_TZ)
        
        # Allow small tolerance for execution time
        assert expires_at is not None
        assert abs((expires_at - expected_expiry).total_seconds()) < 1
    
    def test_determine_cache_expiry_both_today_fallback(self):
        """Test cache expiry fallback when both entries are for today."""
        # Get today's date in UK timezone
        uk_now = get_uk_now()
        today_uk = uk_now.date()
        
        # Both entries are for today
        first_entry = {
            'valid_to': f"{today_uk}T23:30:00Z"  # Today 23:30 UTC
        }
        last_entry = {
            'valid_to': f"{today_uk}T00:00:00Z"  # Today 00:00 UTC
        }
        
        # Determine expiry - should return None to use existing logic
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        
        assert expires_at is None
    
    def test_determine_cache_expiry_both_yesterday_fallback(self):
        """Test cache expiry fallback when both entries are in the past."""
        # Get today's date in UK timezone
        uk_now = get_uk_now()
        yesterday_uk = uk_now.date() - timedelta(days=1)
        
        # Both entries are for yesterday
        first_entry = {
            'valid_to': f"{yesterday_uk}T23:30:00Z"  # Yesterday 23:30 UTC
        }
        last_entry = {
            'valid_to': f"{yesterday_uk}T00:00:00Z"  # Yesterday 00:00 UTC
        }
        
        # Determine expiry - should return None to use existing logic
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        
        assert expires_at is None
    
    def test_determine_cache_expiry_missing_entries(self):
        """Test cache expiry fallback when entries are missing."""
        # Missing first entry
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(None, {'valid_to': '2026-01-13T00:00:00Z'})
        assert expires_at is None
        
        # Missing last entry
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices({'valid_to': '2026-01-13T00:00:00Z'}, None)
        assert expires_at is None
        
        # Both missing
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(None, None)
        assert expires_at is None
    
    def test_determine_cache_expiry_missing_valid_to(self):
        """Test cache expiry fallback when valid_to is missing."""
        first_entry = {
            'valid_from': '2026-01-13T00:00:00Z'  # Missing valid_to
        }
        last_entry = {
            'valid_to': '2026-01-13T23:30:00Z'
        }
        
        # Should handle gracefully and return None
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        assert expires_at is None
    
    def test_determine_cache_expiry_timezone_edge_case(self):
        """Test cache expiry with timezone edge case (BST/GMT transition)."""
        # Use a date that could be affected by timezone transitions
        # Test with dates around BST/GMT change
        uk_now = get_uk_now()
        tomorrow_uk = uk_now.date() + timedelta(days=1)
        
        # First entry tomorrow, last entry today
        first_entry = {
            'valid_to': f"{tomorrow_uk}T00:00:00Z"  # Tomorrow 00:00 UTC (could be 01:00 or 00:00 UK depending on BST)
        }
        last_entry = {
            'valid_to': f"{uk_now.date()}T23:30:00Z"  # Today 23:30 UTC
        }
        
        # Should detect tomorrow and return expiry
        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
        
        assert expires_at is not None
        # Should be tomorrow at 16:00 UK time
        expected_expiry = datetime.combine(
            tomorrow_uk,
            datetime.min.time().replace(hour=16, minute=0, second=0, microsecond=0)
        ).replace(tzinfo=UK_TZ)
        assert abs((expires_at - expected_expiry).total_seconds()) < 1
    
    def test_cache_prices_with_expires_at(self):
        """Test caching prices with explicit expires_at datetime."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        # Set explicit expiry (tomorrow 16:00 UK)
        tomorrow = get_uk_now().date() + timedelta(days=1)
        expires_at = datetime.combine(
            tomorrow,
            datetime.min.time().replace(hour=16, minute=0, second=0, microsecond=0)
        ).replace(tzinfo=UK_TZ)
        
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices, expires_at=expires_at)
        
        cache_file = CacheManager._get_cache_file('AGILE-24-10-01', 'A')
        assert cache_file.exists()
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        # Verify expires_at is stored as naive datetime (no timezone info) - matches old format
        cached_expires_at_str = data['expires_at']
        assert '+' not in cached_expires_at_str, "expires_at should not contain timezone info"
        assert cached_expires_at_str.endswith('00:00'), "Should be stored as UTC time"
        
        # Verify the stored datetime is naive and can be compared with datetime.now()
        cached_expires_at = datetime.fromisoformat(cached_expires_at_str)
        assert cached_expires_at.tzinfo is None, "Stored datetime should be naive"
        
        # Verify date and hour match (converted to UTC)
        from datetime import timezone
        expires_at_utc = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        assert cached_expires_at.date() == expires_at_utc.date()
        assert cached_expires_at.hour == expires_at_utc.hour
    
    def test_cache_prices_existing_logic_preserved(self):
        """Test that existing expiry logic is preserved when expires_at is None."""
        prices = [
            {'value_inc_vat': 16.0, 'valid_from': '2024-01-15T00:00:00Z', 'valid_to': '2024-01-15T00:30:00Z'}
        ]
        
        # Cache without expires_at - should use existing logic (expiry_minutes)
        CacheManager.cache_prices('AGILE-24-10-01', 'A', prices, expiry_minutes=30)
        
        cache_file = CacheManager._get_cache_file('AGILE-24-10-01', 'A')
        assert cache_file.exists()
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        # Verify expiry is approximately 30 minutes from now
        cached_expires_at = datetime.fromisoformat(data['expires_at'])
        now = datetime.now()
        if cached_expires_at.tzinfo is not None:
            # Convert to naive for comparison
            cached_expires_at = cached_expires_at.replace(tzinfo=None)
            now = datetime.now()
        
        time_diff = (cached_expires_at - now).total_seconds()
        # Should be approximately 30 minutes (allow 5 second tolerance)
        assert 1795 <= time_diff <= 1805

