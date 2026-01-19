"""
Cache Manager for Octopus API responses.
Uses file-based JSON caching (NOT database).

Cache files are stored as one persistent file per region: {product_code}_{region_code}.json
Files are updated in place when the cache expires, rather than creating new per-day files.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages file-based caching for API responses.
    
    Uses one persistent cache file per region, updated in place when expired.
    Files are named: {product_code}_{region_code}.json (no date in filename).
    """
    
    # IMPORTANT: This must be anchored to the project root, not the process CWD.
    # PythonAnywhere scheduled tasks may run with CWD=/home/<user>, which would otherwise write to
    # /home/<user>/app/cache instead of /home/<user>/<project>/app/cache.
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    CACHE_DIR = PROJECT_ROOT / 'app' / 'cache'
    
    @staticmethod
    def determine_cache_expiry_from_edge_prices(first_entry, last_entry):
        """
        Determine cache expiry datetime based on the first and last price entries.
        
        Octopus returns price data in reverse chronological order, so we check both
        the first and last entries to detect if next-day prices have been published.
        
        Args:
            first_entry: The first price entry from the API response (dict with 'valid_to' key)
            last_entry: The last price entry from the API response (dict with 'valid_to' key)
        
        Returns:
            datetime or None: 
                - If either entry is for tomorrow (UK date): returns tomorrow at 16:00 UK time
                - If both entries are not for tomorrow: returns None (use existing expiry logic)
        """
        from app.timezone_utils import utc_to_uk, get_uk_now, UK_TZ
        
        if not first_entry or not last_entry:
            logger.warning("Cannot determine cache expiry: first or last entry missing, using existing expiry logic")
            return None
        
        try:
            # Convert both timestamps to UK timezone
            first_price_uk = utc_to_uk(first_entry.get('valid_to', ''))
            last_price_uk = utc_to_uk(last_entry.get('valid_to', ''))
            
            first_price_date = first_price_uk.date()
            last_price_date = last_price_uk.date()
            
            # Get today's date in UK timezone
            uk_now = get_uk_now()
            today_uk = uk_now.date()
            
            # Check if either entry is for tomorrow
            if first_price_date > today_uk or last_price_date > today_uk:
                # At least one entry is for tomorrow - Octopus has published next-day prices
                # Use the later date (in case one is today and one is tomorrow)
                tomorrow_date = max(first_price_date, last_price_date)
                
                # Set expiry to tomorrow at 16:00 UK time
                tomorrow_16_00 = datetime.combine(
                    tomorrow_date,
                    datetime.min.time().replace(hour=16, minute=0, second=0, microsecond=0)
                ).replace(tzinfo=UK_TZ)
                
                logger.info(
                    f"Next-day publication detected (first entry: {first_price_date}, last entry: {last_price_date}) → "
                    f"expiry set to {tomorrow_16_00.strftime('%Y-%m-%d %H:%M')} UK"
                )
                return tomorrow_16_00
            else:
                # Both entries are for today or earlier - next-day prices not yet published
                logger.info(
                    f"Next-day prices not detected (first entry: {first_price_date}, last entry: {last_price_date}) → "
                    f"using existing expiry logic"
                )
                return None
                
        except (KeyError, ValueError, AttributeError) as e:
            # Error parsing or comparing dates - fallback to existing logic
            logger.error(f"Error determining cache expiry from edge prices: {e}, using existing expiry logic")
            return None
        except Exception as e:
            # Unexpected error - fallback to existing logic
            logger.error(f"Unexpected error determining cache expiry: {e}, using existing expiry logic")
            return None
    
    @staticmethod
    def _get_cache_expiry_minutes():
        """Get cache expiry minutes from config, with fallback."""
        try:
            # Try to get from Flask app context
            if current_app:
                return current_app.config.get('CACHE_EXPIRY_MINUTES', 5)
        except RuntimeError:
            # Not in Flask app context, use defaults
            pass
        
        # Fallback to defaults (for testing or non-Flask usage)
        from app.config import Config
        return Config.CACHE_EXPIRY_MINUTES
    
    @staticmethod
    def _get_cache_file(product_code, region_code):
        """
        Get cache file path for product and region.
        Uses persistent filename format: {product_code}_{region_code}.json
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code (e.g., 'A', 'B', etc.)
        
        Returns:
            Path: Path to cache file
        """
        CacheManager.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Sanitize product_code for filename (replace special chars)
        safe_product = product_code.replace('/', '_').replace('\\', '_')
        return CacheManager.CACHE_DIR / f"{safe_product}_{region_code}.json"
    
    @staticmethod
    def get_cached_prices(product_code, region_code):
        """
        Retrieve cached prices if valid.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
        
        Returns:
            list: Cached prices if valid, None otherwise
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code)
        
        if not cache_file.exists():
            logger.debug(f"Cache miss (file not found) for {product_code} {region_code}")
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now() < expires_at:
                logger.debug(f"Cache hit (valid, not expired) for {product_code} {region_code}")
                return data['prices']
            else:
                # Cache expired - caller will fetch and overwrite file
                logger.debug(f"Cache expired for {product_code} {region_code}, will refresh from API")
                return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
            # Corrupted cache file - remove it so it can be recreated
            try:
                cache_file.unlink()
                logger.debug(f"Removed corrupted cache file {cache_file}")
            except Exception as delete_error:
                logger.error(f"Error removing corrupted cache file {cache_file}: {delete_error}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading cache file {cache_file}: {e}")
            return None
    
    @staticmethod
    def cache_prices(product_code, region_code, prices, expiry_minutes=None, expires_at=None):
        """
        Cache prices with expiry. Updates the existing cache file in place.
        
        Uses atomic file write (temp file then rename) for PythonAnywhere-safe operations.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
            prices: List of price data to cache
            expiry_minutes: Cache expiry in minutes (defaults to config value, ignored if expires_at provided)
            expires_at: Optional datetime for cache expiry (takes precedence over expiry_minutes)
        
        Returns:
            bool: True if cache was written successfully, False otherwise
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code)
        
        # Determine expiry: expires_at takes precedence, then expiry_minutes, then config default
        if expires_at is not None:
            # expires_at is provided (datetime object, may be timezone-aware)
            expiry_datetime = expires_at
            # Convert timezone-aware datetime to naive UTC for storage (matches old format)
            if expiry_datetime.tzinfo is not None:
                # Convert to UTC and remove timezone info to match existing cache format
                from datetime import timezone
                expiry_datetime = expiry_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        elif expiry_minutes is not None:
            # expiry_minutes is provided
            expiry_datetime = datetime.now() + timedelta(minutes=expiry_minutes)
        else:
            # Use config default
            expiry_minutes = CacheManager._get_cache_expiry_minutes()
            expiry_datetime = datetime.now() + timedelta(minutes=expiry_minutes)
        
        # Convert to ISO format string for storage (always naive datetime)
        expires_at_iso = expiry_datetime.isoformat()
        
        data = {
            'prices': prices,
            'fetched_at': datetime.now().isoformat(),
            'expires_at': expires_at_iso
        }
        
        # Use atomic write (temp file then rename) for safety
        temp_file = cache_file.with_suffix('.json.tmp')
        
        try:
            # Write to temporary file first
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename (PythonAnywhere-safe)
            os.replace(temp_file, cache_file)
            
            logger.info(f"Cache refresh: Updated cache file for {product_code} {region_code}")
            return True
        except Exception as e:
            logger.error(f"Error writing cache file {cache_file}: {e}")
            # Clean up temp file if it exists
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except:
                pass
            return False
    
    @staticmethod
    def clear_legacy_cache():
        """
        Clean up legacy per-day cache files (old format with date in filename).
        
        Legacy files follow the pattern: {product_code}_{region_code}_{date}.json
        New files follow: {product_code}_{region_code}.json
        
        This method removes all legacy files to prevent disk space accumulation.
        """
        if not CacheManager.CACHE_DIR.exists():
            return
        
        deleted_count = 0
        
        # Pattern: files with date pattern (YYYY-MM-DD) before .json
        # This matches: AGILE-24-10-01_A_2026-01-10.json but not AGILE-24-10-01_A.json
        import re
        date_pattern = re.compile(r'_\d{4}-\d{2}-\d{2}\.json$')
        
        for cache_file in CacheManager.CACHE_DIR.glob('*.json'):
            try:
                # Check if this is a legacy file (contains date pattern)
                if date_pattern.search(str(cache_file)):
                    cache_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Removed legacy cache file: {cache_file.name}")
            except Exception as e:
                logger.error(f"Error deleting legacy cache file {cache_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} legacy per-day cache files")
    
    @staticmethod
    def clear_old_cache(days=1):
        """
        Remove cache files older than specified days (for any remaining legacy files).
        
        Note: With the new persistent cache system, this method is primarily
        for cleaning up any remaining legacy files. New cache files are updated
        in place and don't accumulate.
        
        Args:
            days: Number of days to keep cache files (default: 1)
        """
        if not CacheManager.CACHE_DIR.exists():
            return
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for cache_file in CacheManager.CACHE_DIR.glob('*.json'):
            try:
                if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff:
                    cache_file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting cache file {cache_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old cache files")

