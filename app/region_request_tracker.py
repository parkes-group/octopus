"""
Region Request Tracker for analytics.
Uses file-based JSON storage to track region usage (no database).
"""
import json
import os
from pathlib import Path
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RegionRequestTracker:
    """Manages file-based tracking of region request counts."""
    
    STATS_DIR = Path('data/stats')
    COUNTS_FILE = STATS_DIR / 'region_request_counts.json'
    
    @staticmethod
    def _ensure_stats_dir():
        """Ensure stats directory exists."""
        RegionRequestTracker.STATS_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _load_counts():
        """
        Load region request counts from JSON file.
        
        Returns:
            dict: Region counts dictionary with region codes as keys
        """
        RegionRequestTracker._ensure_stats_dir()
        
        if not RegionRequestTracker.COUNTS_FILE.exists():
            # Initialize with empty structure
            default_counts = {}
            RegionRequestTracker._save_counts(default_counts)
            return default_counts
        
        try:
            with open(RegionRequestTracker.COUNTS_FILE, 'r', encoding='utf-8') as f:
                counts = json.load(f)
            
            # Ensure counts is a dictionary
            if not isinstance(counts, dict):
                logger.warning(f"Region counts file corrupted, resetting to empty: {RegionRequestTracker.COUNTS_FILE}")
                counts = {}
                RegionRequestTracker._save_counts(counts)
            
            return counts
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error reading region counts file {RegionRequestTracker.COUNTS_FILE}: {e}")
            # Return empty dict on corruption, will be overwritten on next save
            return {}
        except Exception as e:
            logger.error(f"Error reading region counts file {RegionRequestTracker.COUNTS_FILE}: {e}")
            return {}
    
    @staticmethod
    def _save_counts(counts):
        """
        Save region request counts to JSON file using atomic write.
        
        Args:
            counts: Dictionary of region counts to save
        """
        RegionRequestTracker._ensure_stats_dir()
        
        # Use atomic write (temp file then rename) for PythonAnywhere safety
        temp_file = RegionRequestTracker.COUNTS_FILE.with_suffix('.json.tmp')
        
        try:
            # Write to temporary file first
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(counts, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_file, RegionRequestTracker.COUNTS_FILE)
            
        except Exception as e:
            logger.error(f"Error writing region counts file {RegionRequestTracker.COUNTS_FILE}: {e}")
            # Clean up temp file if it exists
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except:
                pass
            raise
    
    @staticmethod
    def record_region_request(region_code):
        """
        Record a region request by incrementing the count and updating last_requested timestamp.
        
        This method is safe to call concurrently and will never raise exceptions that
        would block the main request flow.
        
        Args:
            region_code: Octopus region code (e.g., 'A', 'B', etc.)
        
        Returns:
            bool: True if successfully recorded, False otherwise
        """
        if not region_code:
            logger.warning("Attempted to record region request with empty region_code")
            return False
        
        # Validate region code is a single uppercase letter (standard Octopus regions)
        if not isinstance(region_code, str) or len(region_code) != 1 or not region_code.isupper():
            logger.warning(f"Invalid region code format: {region_code}")
            return False
        
        try:
            # Load existing counts
            counts = RegionRequestTracker._load_counts()
            
            # Initialize region entry if it doesn't exist
            if region_code not in counts:
                counts[region_code] = {
                    'count': 0,
                    'last_requested': None
                }
            
            # Increment count and update timestamp
            counts[region_code]['count'] = counts[region_code].get('count', 0) + 1
            counts[region_code]['last_requested'] = datetime.now(timezone.utc).isoformat()
            
            # Save back to file
            RegionRequestTracker._save_counts(counts)
            
            logger.info(f"Recorded region request: {region_code} (total: {counts[region_code]['count']})")
            return True
            
        except Exception as e:
            # Log error but don't raise - stats recording must never break price rendering
            logger.error(f"Error recording region request for {region_code}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def get_region_counts():
        """
        Get current region request counts (for admin/analytics use).
        
        Returns:
            dict: Dictionary of region counts, or empty dict on error
        """
        try:
            return RegionRequestTracker._load_counts()
        except Exception as e:
            logger.error(f"Error loading region counts: {e}")
            return {}
