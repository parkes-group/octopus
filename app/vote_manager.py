"""
Vote Manager for feature interest voting and suggestions.
Uses file-based JSON storage (no database).
"""
import json
import os
from pathlib import Path
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class VoteManager:
    """Manages file-based storage for feature votes and suggestions."""
    
    VOTES_DIR = Path('app/votes')
    VOTES_FILE = VOTES_DIR / 'feature_votes.json'
    SUGGESTIONS_FILE = VOTES_DIR / 'feature_suggestions.jsonl'
    
    # Maximum suggestion length
    MAX_SUGGESTION_LENGTH = 200
    
    @staticmethod
    def _ensure_votes_dir():
        """Ensure votes directory exists."""
        VoteManager.VOTES_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _load_votes():
        """
        Load votes from JSON file.
        
        Returns:
            dict: Votes dictionary with feature IDs as keys and counts as values
        """
        VoteManager._ensure_votes_dir()
        
        if not VoteManager.VOTES_FILE.exists():
            # Initialize with empty structure
            default_votes = {}
            VoteManager._save_votes(default_votes)
            return default_votes
        
        try:
            with open(VoteManager.VOTES_FILE, 'r', encoding='utf-8') as f:
                votes = json.load(f)
            
            # Ensure votes is a dictionary
            if not isinstance(votes, dict):
                logger.warning("Votes file corrupted, resetting to empty")
                votes = {}
                VoteManager._save_votes(votes)
            
            return votes
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading votes file {VoteManager.VOTES_FILE}: {e}")
            # Return empty structure on error
            return {}
    
    @staticmethod
    def _save_votes(votes):
        """
        Save votes to JSON file.
        
        Args:
            votes: Dictionary with feature IDs as keys and vote counts as values
        """
        VoteManager._ensure_votes_dir()
        
        try:
            # Write votes to file
            with open(VoteManager.VOTES_FILE, 'w', encoding='utf-8') as f:
                json.dump(votes, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved votes: {votes}")
        except IOError as e:
            logger.error(f"Error writing votes file {VoteManager.VOTES_FILE}: {e}")
            raise
    
    @staticmethod
    def record_vote(feature_id):
        """
        Record a vote for a feature.
        
        Args:
            feature_id: Feature identifier (e.g., 'daily_cheapest_email')
        
        Returns:
            dict: Updated votes dictionary
        """
        # Load current votes
        votes = VoteManager._load_votes()
        
        # Increment vote count (initialize to 0 if not exists)
        votes[feature_id] = votes.get(feature_id, 0) + 1
        
        # Save updated votes
        VoteManager._save_votes(votes)
        
        logger.info(f"Recorded vote for {feature_id}. New count: {votes[feature_id]}")
        
        return votes
    
    @staticmethod
    def get_votes():
        """
        Get current vote counts.
        
        Returns:
            dict: Votes dictionary with feature IDs as keys and counts as values
        """
        return VoteManager._load_votes()
    
    @staticmethod
    def get_vote_percentages():
        """
        Get vote counts and percentages for all features.
        
        Returns:
            dict: Dictionary with feature IDs as keys, containing 'count' and 'percentage'
        """
        votes = VoteManager.get_votes()
        total_votes = sum(votes.values())
        
        if total_votes == 0:
            return {}
        
        percentages = {}
        for feature_id, count in votes.items():
            percentage = (count / total_votes) * 100
            percentages[feature_id] = {
                'count': count,
                'percentage': round(percentage, 1)
            }
        
        return percentages
    
    @staticmethod
    def save_suggestion(suggestion_text):
        """
        Save a feature suggestion to the suggestions file.
        
        Args:
            suggestion_text: The suggestion text (max 200 characters)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not suggestion_text or not suggestion_text.strip():
            raise ValueError("Suggestion text cannot be empty")
        
        # Truncate if too long
        suggestion_text = suggestion_text.strip()[:VoteManager.MAX_SUGGESTION_LENGTH]
        
        VoteManager._ensure_votes_dir()
        
        try:
            # Append to JSONL file (one JSON object per line)
            suggestion_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "suggestion": suggestion_text
            }
            
            with open(VoteManager.SUGGESTIONS_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(suggestion_data, ensure_ascii=False) + '\n')
            
            logger.info(f"Saved suggestion: {suggestion_text[:50]}...")
            return True
        except IOError as e:
            logger.error(f"Error writing suggestion file {VoteManager.SUGGESTIONS_FILE}: {e}")
            return False

