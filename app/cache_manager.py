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
    
    CACHE_DIR = Path('app/cache')
    
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
    def cache_prices(product_code, region_code, prices, expiry_minutes=None):
        """
        Cache prices with expiry. Updates the existing cache file in place.
        
        Uses atomic file write (temp file then rename) for PythonAnywhere-safe operations.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
            prices: List of price data to cache
            expiry_minutes: Cache expiry in minutes (defaults to config value)
        
        Returns:
            bool: True if cache was written successfully, False otherwise
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code)
        
        if expiry_minutes is None:
            expiry_minutes = CacheManager._get_cache_expiry_minutes()
        
        data = {
            'prices': prices,
            'fetched_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()
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

