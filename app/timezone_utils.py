"""
Timezone utilities for UK timezone handling (GMT/BST).
All times from Octopus API are in UTC and need to be converted to UK local time.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# UK timezone (automatically handles GMT/BST)
UK_TZ = ZoneInfo('Europe/London')

def get_uk_now():
    """
    Get current datetime in UK timezone.
    
    Returns:
        datetime: Current datetime in UK timezone
    """
    return datetime.now(UK_TZ)

def utc_to_uk(utc_datetime_str):
    """
    Convert UTC datetime string (ISO format) to UK datetime.
    
    Args:
        utc_datetime_str: UTC datetime string (e.g., '2024-01-15T12:00:00Z')
    
    Returns:
        datetime: Datetime in UK timezone
    """
    try:
        # Parse UTC datetime string
        if utc_datetime_str.endswith('Z'):
            dt_str = utc_datetime_str.replace('Z', '+00:00')
        else:
            dt_str = utc_datetime_str
        
        # Parse as UTC
        dt_utc = datetime.fromisoformat(dt_str)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
        # Convert to UK timezone
        dt_uk = dt_utc.astimezone(UK_TZ)
        return dt_uk
    except (ValueError, AttributeError) as e:
        logger.error(f"Error converting UTC to UK timezone: {utc_datetime_str}, error: {e}")
        raise

def format_uk_datetime(dt_uk, include_date=True, include_time=True):
    """
    Format UK datetime for display.
    
    Args:
        dt_uk: Datetime in UK timezone
        include_date: Whether to include date
        include_time: Whether to include time
    
    Returns:
        str: Formatted datetime string
    """
    if not isinstance(dt_uk, datetime):
        return str(dt_uk)
    
    parts = []
    if include_date:
        parts.append(dt_uk.strftime('%Y-%m-%d'))
    if include_time:
        parts.append(dt_uk.strftime('%H:%M'))
    
    return ' '.join(parts)

def format_uk_datetime_short(dt_uk):
    """
    Format UK datetime for short display (DD/MM HH:MM or HH:MM).
    
    Args:
        dt_uk: Datetime in UK timezone
    
    Returns:
        str: Formatted datetime string (DD/MM HH:MM or HH:MM)
    """
    if not isinstance(dt_uk, datetime):
        return str(dt_uk)
    
    return dt_uk.strftime('%d/%m %H:%M')

def format_uk_time(dt_uk):
    """
    Format UK datetime for time-only display (HH:MM).
    
    Args:
        dt_uk: Datetime in UK timezone
    
    Returns:
        str: Formatted time string (HH:MM)
    """
    if not isinstance(dt_uk, datetime):
        return str(dt_uk)
    
    return dt_uk.strftime('%H:%M')

def format_uk_date(dt_uk):
    """
    Format UK datetime for date-only display (YYYY-MM-DD).
    
    Args:
        dt_uk: Datetime in UK timezone
    
    Returns:
        str: Formatted date string (YYYY-MM-DD)
    """
    if not isinstance(dt_uk, datetime):
        return str(dt_uk)
    
    return dt_uk.strftime('%Y-%m-%d')

def get_uk_date_string():
    """
    Get current UK date as string (YYYY-MM-DD).
    
    Returns:
        str: Current UK date string
    """
    return get_uk_now().strftime('%Y-%m-%d')

