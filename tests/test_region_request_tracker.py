"""
Tests for region request tracker.
"""
import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from app.region_request_tracker import RegionRequestTracker


class TestRegionRequestTracker:
    """Test cases for RegionRequestTracker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a test stats directory
        self.test_stats_dir = Path('tests/test_stats')
        self.test_stats_dir.mkdir(parents=True, exist_ok=True)
        self.original_stats_dir = RegionRequestTracker.STATS_DIR
        RegionRequestTracker.STATS_DIR = self.test_stats_dir
        RegionRequestTracker.COUNTS_FILE = self.test_stats_dir / 'region_request_counts.json'
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test files
        if RegionRequestTracker.COUNTS_FILE.exists():
            RegionRequestTracker.COUNTS_FILE.unlink()
        # Remove temp files if they exist
        temp_file = RegionRequestTracker.COUNTS_FILE.with_suffix('.json.tmp')
        if temp_file.exists():
            temp_file.unlink()
        if self.test_stats_dir.exists():
            try:
                self.test_stats_dir.rmdir()
            except OSError:
                pass  # Directory not empty, that's fine
        
        # Reset to defaults
        RegionRequestTracker.STATS_DIR = self.original_stats_dir
        RegionRequestTracker.COUNTS_FILE = self.original_stats_dir / 'region_request_counts.json'
    
    def test_record_region_request_new_region(self):
        """Test recording a request for a new region."""
        result = RegionRequestTracker.record_region_request('A')
        
        assert result is True
        
        counts = RegionRequestTracker.get_region_counts()
        assert 'A' in counts
        assert counts['A']['count'] == 1
        assert counts['A']['last_requested'] is not None
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(counts['A']['last_requested'].replace('Z', '+00:00'))
    
    def test_record_region_request_existing_region(self):
        """Test recording multiple requests for the same region."""
        # Record first request
        RegionRequestTracker.record_region_request('B')
        
        # Record second request
        result = RegionRequestTracker.record_region_request('B')
        
        assert result is True
        
        counts = RegionRequestTracker.get_region_counts()
        assert 'B' in counts
        assert counts['B']['count'] == 2
        assert counts['B']['last_requested'] is not None
    
    def test_record_region_request_multiple_regions(self):
        """Test recording requests for multiple different regions."""
        RegionRequestTracker.record_region_request('A')
        RegionRequestTracker.record_region_request('B')
        RegionRequestTracker.record_region_request('C')
        RegionRequestTracker.record_region_request('A')  # Second request for A
        
        counts = RegionRequestTracker.get_region_counts()
        
        assert counts['A']['count'] == 2
        assert counts['B']['count'] == 1
        assert counts['C']['count'] == 1
        assert counts['A']['last_requested'] is not None
        assert counts['B']['last_requested'] is not None
        assert counts['C']['last_requested'] is not None
    
    def test_record_region_request_invalid_code_empty(self):
        """Test that empty region code is rejected."""
        result = RegionRequestTracker.record_region_request('')
        assert result is False
        
        counts = RegionRequestTracker.get_region_counts()
        assert len(counts) == 0
    
    def test_record_region_request_invalid_code_none(self):
        """Test that None region code is rejected."""
        result = RegionRequestTracker.record_region_request(None)
        assert result is False
    
    def test_record_region_request_invalid_code_format(self):
        """Test that invalid region code formats are rejected."""
        invalid_codes = ['ab', '1', 'a', 'AB', 'region-a']
        
        for invalid_code in invalid_codes:
            result = RegionRequestTracker.record_region_request(invalid_code)
            assert result is False, f"Should reject invalid code: {invalid_code}"
    
    def test_get_region_counts_empty(self):
        """Test getting counts when no regions have been recorded."""
        counts = RegionRequestTracker.get_region_counts()
        assert isinstance(counts, dict)
        assert len(counts) == 0
    
    def test_get_region_counts_after_recording(self):
        """Test getting counts after recording some requests."""
        RegionRequestTracker.record_region_request('A')
        RegionRequestTracker.record_region_request('B')
        RegionRequestTracker.record_region_request('A')
        
        counts = RegionRequestTracker.get_region_counts()
        
        assert 'A' in counts
        assert 'B' in counts
        assert counts['A']['count'] == 2
        assert counts['B']['count'] == 1
    
    def test_atomic_write_preserves_data(self):
        """Test that atomic write doesn't lose data on concurrent-like access."""
        # Record multiple requests in sequence (simulating concurrent access)
        for _ in range(5):
            RegionRequestTracker.record_region_request('A')
        
        counts = RegionRequestTracker.get_region_counts()
        assert counts['A']['count'] == 5
    
    def test_corrupted_file_recovery(self):
        """Test that corrupted JSON file is handled gracefully."""
        # Create a corrupted JSON file
        with open(RegionRequestTracker.COUNTS_FILE, 'w') as f:
            f.write('{ invalid json }')
        
        # Should still work (returns empty dict and will create new file)
        counts = RegionRequestTracker.get_region_counts()
        assert isinstance(counts, dict)
        
        # Now recording should work
        result = RegionRequestTracker.record_region_request('A')
        assert result is True
        
        counts = RegionRequestTracker.get_region_counts()
        assert counts['A']['count'] == 1
    
    def test_file_structure(self):
        """Test that saved file has correct structure."""
        RegionRequestTracker.record_region_request('A')
        RegionRequestTracker.record_region_request('B')
        
        # Verify file exists and is readable
        assert RegionRequestTracker.COUNTS_FILE.exists()
        
        with open(RegionRequestTracker.COUNTS_FILE, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert 'A' in data
        assert 'B' in data
        assert 'count' in data['A']
        assert 'last_requested' in data['A']
        assert isinstance(data['A']['count'], int)
        assert isinstance(data['A']['last_requested'], str)
    
    def test_all_region_codes(self):
        """Test that all valid Octopus region codes work."""
        valid_regions = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P']
        
        for region in valid_regions:
            result = RegionRequestTracker.record_region_request(region)
            assert result is True, f"Should accept valid region code: {region}"
        
        counts = RegionRequestTracker.get_region_counts()
        assert len(counts) == len(valid_regions)
        for region in valid_regions:
            assert region in counts
            assert counts[region]['count'] == 1
