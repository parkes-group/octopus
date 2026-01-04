"""
Tests for vote manager.
"""
import pytest
import json
from pathlib import Path
from app.vote_manager import VoteManager


class TestVoteManager:
    """Test cases for VoteManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use a test votes directory
        self.test_votes_dir = Path('tests/test_votes')
        self.test_votes_dir.mkdir(parents=True, exist_ok=True)
        self.original_votes_dir = VoteManager.VOTES_DIR
        VoteManager.VOTES_DIR = self.test_votes_dir
        VoteManager.VOTES_FILE = self.test_votes_dir / 'feature_votes.json'
        VoteManager.SUGGESTIONS_FILE = self.test_votes_dir / 'feature_suggestions.jsonl'
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove test files
        if VoteManager.VOTES_FILE.exists():
            VoteManager.VOTES_FILE.unlink()
        if VoteManager.SUGGESTIONS_FILE.exists():
            VoteManager.SUGGESTIONS_FILE.unlink()
        if self.test_votes_dir.exists():
            self.test_votes_dir.rmdir()
        
        # Reset to defaults
        VoteManager.VOTES_DIR = self.original_votes_dir
        VoteManager.VOTES_FILE = self.original_votes_dir / 'feature_votes.json'
        VoteManager.SUGGESTIONS_FILE = self.original_votes_dir / 'feature_suggestions.jsonl'
    
    def test_record_vote_new_feature(self):
        """Test recording a vote for a new feature."""
        result = VoteManager.record_vote('daily_cheapest_email')
        
        assert 'daily_cheapest_email' in result
        assert result['daily_cheapest_email'] == 1
    
    def test_record_vote_existing_feature(self):
        """Test recording multiple votes for the same feature."""
        # Record first vote
        VoteManager.record_vote('daily_cheapest_email')
        
        # Record second vote
        result = VoteManager.record_vote('daily_cheapest_email')
        
        assert result['daily_cheapest_email'] == 2
    
    def test_get_votes_empty(self):
        """Test getting votes when none exist."""
        result = VoteManager.get_votes()
        assert isinstance(result, dict)
        # Should be empty or have default structure
    
    def test_get_vote_percentages_single_vote(self):
        """Test getting vote percentages with single vote."""
        VoteManager.record_vote('daily_cheapest_email')
        
        result = VoteManager.get_vote_percentages()
        
        assert 'daily_cheapest_email' in result
        assert result['daily_cheapest_email']['count'] == 1
        assert result['daily_cheapest_email']['percentage'] == 100.0
    
    def test_get_vote_percentages_multiple_features(self):
        """Test getting vote percentages with multiple features."""
        VoteManager.record_vote('daily_cheapest_email')
        VoteManager.record_vote('daily_cheapest_email')
        VoteManager.record_vote('negative_price_alert')
        
        result = VoteManager.get_vote_percentages()
        
        assert 'daily_cheapest_email' in result
        assert 'negative_price_alert' in result
        assert result['daily_cheapest_email']['count'] == 2
        assert result['negative_price_alert']['count'] == 1
        # 2 out of 3 = 66.7%, 1 out of 3 = 33.3%
        assert result['daily_cheapest_email']['percentage'] == 66.7
        assert result['negative_price_alert']['percentage'] == 33.3
    
    def test_get_vote_percentages_no_votes(self):
        """Test getting vote percentages when no votes exist."""
        result = VoteManager.get_vote_percentages()
        assert result == {}
    
    def test_save_suggestion(self):
        """Test saving a feature suggestion."""
        suggestion_text = "Add email notifications for price drops"
        
        result = VoteManager.save_suggestion(suggestion_text)
        
        assert result is True
        assert VoteManager.SUGGESTIONS_FILE.exists()
        
        # Verify content
        with open(VoteManager.SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            line = f.readline()
            data = json.loads(line)
            assert data['suggestion'] == suggestion_text
            assert 'timestamp' in data
    
    def test_save_suggestion_truncates_long_text(self):
        """Test that long suggestions are truncated."""
        long_text = "A" * 300  # 300 characters
        
        VoteManager.save_suggestion(long_text)
        
        with open(VoteManager.SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            line = f.readline()
            data = json.loads(line)
            assert len(data['suggestion']) == 200  # MAX_SUGGESTION_LENGTH
    
    def test_save_suggestion_empty_raises_error(self):
        """Test that empty suggestions raise ValueError."""
        with pytest.raises(ValueError):
            VoteManager.save_suggestion("")
        
        with pytest.raises(ValueError):
            VoteManager.save_suggestion("   ")

