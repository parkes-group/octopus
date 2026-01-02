"""
Cache Manager for Octopus API responses.
Uses file-based JSON caching (NOT database).
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages file-based caching for API responses."""
    
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
    def _get_cache_file(product_code, region_code, date_str):
        """
        Get cache file path for product, region and date.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
            date_str: Date string in YYYY-MM-DD format
        
        Returns:
            Path: Path to cache file
        """
        CacheManager.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Sanitize product_code for filename (replace special chars)
        safe_product = product_code.replace('/', '_').replace('\\', '_')
        return CacheManager.CACHE_DIR / f"{safe_product}_{region_code}_{date_str}.json"
    
    @staticmethod
    def get_cached_prices(product_code, region_code, date_str):
        """
        Retrieve cached prices if valid.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
            date_str: Date string in YYYY-MM-DD format
        
        Returns:
            list: Cached prices if valid, None otherwise
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code, date_str)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now() < expires_at:
                logger.debug(f"Cache hit (valid, not expired) for {product_code} {region_code} on {date_str}")
                return data['prices']
            else:
                # Expired, delete file
                logger.debug(f"Cache expired for {product_code} {region_code} on {date_str}, will fetch from API")
                cache_file.unlink()
                return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
            # Delete corrupted cache file
            try:
                cache_file.unlink()
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading cache: {e}")
            return None
    
    @staticmethod
    def cache_prices(product_code, region_code, date_str, prices, expiry_minutes=None):
        """
        Cache prices with expiry.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code
            date_str: Date string in YYYY-MM-DD format
            prices: List of price data to cache
            expiry_minutes: Cache expiry in minutes (defaults to config value)
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code, date_str)
        
        if expiry_minutes is None:
            expiry_minutes = CacheManager._get_cache_expiry_minutes()
        
        data = {
            'prices': prices,
            'fetched_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(minutes=expiry_minutes)).isoformat()
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Cached prices for {product_code} {region_code} on {date_str}")
        except Exception as e:
            logger.error(f"Error writing cache file {cache_file}: {e}")
    
    @staticmethod
    def clear_old_cache(days=1):
        """
        Remove cache files older than specified days.
        
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

