"""
Price calculation logic.
Finds lowest prices and cheapest charging blocks.
"""
from datetime import datetime, timezone, timedelta
import logging
from app.timezone_utils import utc_to_uk, format_uk_datetime_short, format_uk_time, format_uk_date, get_uk_now, UK_TZ

logger = logging.getLogger(__name__)

class PriceCalculator:
    """Calculates optimal charging windows from price data."""
    
    @staticmethod
    def find_lowest_price(prices):
        """
        Find the lowest single 30-minute price.
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat', 'valid_from', 'valid_to'
        
        Returns:
            dict: Lowest price info with 'price', 'time_from', 'time_to', or None if empty
        """
        if not prices:
            return None
        
        try:
            lowest = min(prices, key=lambda x: x['value_inc_vat'])
            # Convert UTC times to UK times for display
            time_from_uk = utc_to_uk(lowest['valid_from'])
            time_to_uk = utc_to_uk(lowest['valid_to'])
            return {
                'price': lowest['value_inc_vat'],
                'time_from': lowest['valid_from'],  # Keep UTC for comparison
                'time_to': lowest['valid_to'],  # Keep UTC for comparison
                'time_from_uk': time_from_uk,  # UK timezone for display
                'time_to_uk': time_to_uk  # UK timezone for display
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Error finding lowest price: {e}")
            return None
    
    @staticmethod
    def find_cheapest_block(prices, duration_hours):
        """
        Find cheapest contiguous block of N hours (supports decimals, e.g., 3.5 hours).
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat', 'valid_from', 'valid_to'
            duration_hours: Duration in hours (supports decimals, e.g., 3.5)
        
        Returns:
            dict: Cheapest block info with 'start_time', 'end_time', 'average_price', 
                  'total_cost', 'slots', or None if invalid
        """
        if not prices or duration_hours < 0.5:
            return None
        
        # Convert hours to half-hour slots (e.g., 3.5 hours = 7 slots)
        slots_needed = int(duration_hours * 2)
        
        if len(prices) < slots_needed:
            logger.warning(f"Not enough price slots ({len(prices)}) for duration {duration_hours} hours ({slots_needed} slots needed)")
            return None
        
        cheapest_block = None
        cheapest_avg = float('inf')
        
        # Ensure prices are sorted by valid_from (required for contiguous blocks)
        sorted_prices = sorted(prices, key=lambda x: x.get('valid_from', ''))
        
        # Sliding window approach - find cheapest CONTIGUOUS block (time-wise, not just list-wise)
        for i in range(len(sorted_prices) - slots_needed + 1):
            block = sorted_prices[i:i + slots_needed]
            
            # Verify block has exactly the required number of slots
            if len(block) != slots_needed:
                continue
                
            try:
                # CRITICAL: Verify that slots are contiguous in TIME (not just in the list)
                # Each slot should start exactly 30 minutes after the previous slot ends
                is_contiguous = True
                gap_found = None
                for j in range(len(block) - 1):
                    current_valid_to = block[j]['valid_to']
                    next_valid_from = block[j + 1]['valid_from']
                    # These should be equal (current slot's end = next slot's start)
                    if current_valid_to != next_valid_from:
                        is_contiguous = False
                        gap_found = (j, current_valid_to, next_valid_from)
                        break
                
                if not is_contiguous:
                    # Skip this block - slots are not contiguous in time
                    logger.debug(f"Skipping non-contiguous block: gap between slot {gap_found[0]} ({gap_found[1]}) and slot {gap_found[0]+1} ({gap_found[2]})")
                    continue
                
                total_price = sum(slot['value_inc_vat'] for slot in block)
                avg_price = total_price / slots_needed
                
                if avg_price < cheapest_avg:
                    cheapest_avg = avg_price
                    # Convert UTC times to UK times for display
                    start_time_uk = utc_to_uk(block[0]['valid_from'])
                    end_time_uk = utc_to_uk(block[-1]['valid_to'])
                    
                    # Verify the block represents a contiguous time period (double-check)
                    expected_duration = timedelta(hours=duration_hours)
                    actual_duration = end_time_uk - start_time_uk
                    # Allow small tolerance (up to 1 minute) for rounding/timezone conversion
                    duration_diff_seconds = abs((actual_duration - expected_duration).total_seconds())
                    if duration_diff_seconds > 60:
                        logger.warning(f"Block duration mismatch (should not happen after contiguous check): expected {duration_hours}h, got {actual_duration.total_seconds()/3600:.2f}h. Start: {start_time_uk}, End: {end_time_uk}")
                        continue
                    
                    cheapest_block = {
                        'start_time': block[0]['valid_from'],  # Keep UTC for comparison
                        'end_time': block[-1]['valid_to'],  # Keep UTC for comparison
                        'start_time_uk': start_time_uk,  # UK timezone for display
                        'end_time_uk': end_time_uk,  # UK timezone for display
                        'average_price': round(avg_price, 2),
                        'total_cost': round(total_price, 2),
                        'slots': block  # Store actual block for validation
                    }
            except (KeyError, TypeError) as e:
                logger.error(f"Error processing price block at index {i}: {e}")
                continue
        
        return cheapest_block
    
    @staticmethod
    def find_worst_block(prices, duration_hours):
        """
        Find worst (most expensive) contiguous block of N hours (supports decimals, e.g., 3.5 hours).
        
        Uses the same logic as find_cheapest_block but finds the highest average price instead.
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat', 'valid_from', 'valid_to'
            duration_hours: Duration in hours (supports decimals, e.g., 3.5)
        
        Returns:
            dict: Worst block info with 'start_time', 'end_time', 'average_price', 
                  'total_cost', 'slots', or None if invalid
        """
        if not prices or duration_hours < 0.5:
            return None
        
        # Convert hours to half-hour slots (e.g., 3.5 hours = 7 slots)
        slots_needed = int(duration_hours * 2)
        
        if len(prices) < slots_needed:
            logger.warning(f"Not enough price slots ({len(prices)}) for duration {duration_hours} hours ({slots_needed} slots needed)")
            return None
        
        worst_block = None
        worst_avg = float('-inf')
        
        # Ensure prices are sorted by valid_from (required for contiguous blocks)
        sorted_prices = sorted(prices, key=lambda x: x.get('valid_from', ''))
        
        # Sliding window approach - find worst (most expensive) CONTIGUOUS block
        for i in range(len(sorted_prices) - slots_needed + 1):
            block = sorted_prices[i:i + slots_needed]
            
            # Verify block has exactly the required number of slots
            if len(block) != slots_needed:
                continue
                
            try:
                # CRITICAL: Verify that slots are contiguous in TIME (not just in the list)
                # Each slot should start exactly 30 minutes after the previous slot ends
                is_contiguous = True
                gap_found = None
                for j in range(len(block) - 1):
                    current_valid_to = block[j]['valid_to']
                    next_valid_from = block[j + 1]['valid_from']
                    # These should be equal (current slot's end = next slot's start)
                    if current_valid_to != next_valid_from:
                        is_contiguous = False
                        gap_found = (j, current_valid_to, next_valid_from)
                        break
                
                if not is_contiguous:
                    # Skip this block - slots are not contiguous in time
                    logger.debug(f"Skipping non-contiguous block: gap between slot {gap_found[0]} ({gap_found[1]}) and slot {gap_found[0]+1} ({gap_found[2]})")
                    continue
                
                total_price = sum(slot['value_inc_vat'] for slot in block)
                avg_price = total_price / slots_needed
                
                if avg_price > worst_avg:
                    worst_avg = avg_price
                    # Convert UTC times to UK times for display
                    start_time_uk = utc_to_uk(block[0]['valid_from'])
                    end_time_uk = utc_to_uk(block[-1]['valid_to'])
                    
                    # Verify the block represents a contiguous time period (double-check)
                    expected_duration = timedelta(hours=duration_hours)
                    actual_duration = end_time_uk - start_time_uk
                    # Allow small tolerance (up to 1 minute) for rounding/timezone conversion
                    duration_diff_seconds = abs((actual_duration - expected_duration).total_seconds())
                    if duration_diff_seconds > 60:
                        logger.warning(f"Block duration mismatch (should not happen after contiguous check): expected {duration_hours}h, got {actual_duration.total_seconds()/3600:.2f}h. Start: {start_time_uk}, End: {end_time_uk}")
                        continue
                    
                    worst_block = {
                        'start_time': block[0]['valid_from'],  # Keep UTC for comparison
                        'end_time': block[-1]['valid_to'],  # Keep UTC for comparison
                        'start_time_uk': start_time_uk,  # UK timezone for display
                        'end_time_uk': end_time_uk,  # UK timezone for display
                        'average_price': round(avg_price, 2),
                        'total_cost': round(total_price, 2),
                        'slots': block  # Store actual block for validation
                    }
            except (KeyError, TypeError) as e:
                logger.error(f"Error processing price block at index {i}: {e}")
                continue
        
        return worst_block
    
    @staticmethod
    def find_future_cheapest_block(prices, duration_hours, current_time_utc):
        """
        Find cheapest contiguous block of N hours considering only future time slots.
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat', 'valid_from', 'valid_to'
            duration_hours: Duration in hours (supports decimals, e.g., 3.5)
            current_time_utc: Current time as timezone-aware UTC datetime for comparison
        
        Returns:
            dict: Cheapest future block info with 'start_time', 'end_time', 'average_price', 
                  'total_cost', 'slots', or None if invalid/no future blocks
        """
        if not prices or duration_hours < 0.5:
            return None
        
        # Filter prices to only future slots (valid_from >= current_time_utc)
        # Convert valid_from strings to datetime for comparison
        future_prices = []
        for price in prices:
            try:
                # Parse UTC datetime string
                valid_from_str = price['valid_from']
                if valid_from_str.endswith('Z'):
                    dt_str = valid_from_str.replace('Z', '+00:00')
                else:
                    dt_str = valid_from_str
                
                price_time_utc = datetime.fromisoformat(dt_str)
                if price_time_utc.tzinfo is None:
                    price_time_utc = price_time_utc.replace(tzinfo=timezone.utc)
                
                # Only include if price slot is in the future (or current time)
                if price_time_utc >= current_time_utc:
                    future_prices.append(price)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error parsing price time for future filter: {e}")
                continue
        
        if not future_prices:
            logger.debug("No future prices found")
            return None
        
        # Use the same sliding window logic as find_cheapest_block
        slots_needed = int(duration_hours * 2)
        
        if len(future_prices) < slots_needed:
            logger.debug(f"Not enough future price slots ({len(future_prices)}) for duration {duration_hours} hours ({slots_needed} slots needed)")
            return None
        
        cheapest_block = None
        cheapest_avg = float('inf')
        
        # Sliding window approach on future prices only
        for i in range(len(future_prices) - slots_needed + 1):
            block = future_prices[i:i + slots_needed]
            try:
                total_price = sum(slot['value_inc_vat'] for slot in block)
                avg_price = total_price / slots_needed
                
                if avg_price < cheapest_avg:
                    cheapest_avg = avg_price
                    # Convert UTC times to UK times for display
                    start_time_uk = utc_to_uk(block[0]['valid_from'])
                    end_time_uk = utc_to_uk(block[-1]['valid_to'])
                    cheapest_block = {
                        'start_time': block[0]['valid_from'],  # Keep UTC for comparison
                        'end_time': block[-1]['valid_to'],  # Keep UTC for comparison
                        'start_time_uk': start_time_uk,  # UK timezone for display
                        'end_time_uk': end_time_uk,  # UK timezone for display
                        'average_price': round(avg_price, 2),
                        'total_cost': round(total_price, 2),
                        'slots': block
                    }
            except (KeyError, TypeError) as e:
                logger.error(f"Error processing future price block: {e}")
                continue
        
        return cheapest_block
    
    @staticmethod
    def calculate_daily_average_price(prices):
        """
        Calculate the average price for all prices (deprecated for multi-day data).
        
        NOTE: This method calculates across ALL prices regardless of calendar day.
        For per-day calculations, use calculate_daily_averages_by_date() instead.
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat'
        
        Returns:
            float: Average price in pence per kWh, or None if no prices
        """
        if not prices:
            return None
        
        try:
            total_price = sum(price['value_inc_vat'] for price in prices)
            avg_price = total_price / len(prices)
            return round(avg_price, 2)
        except (KeyError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating daily average price: {e}")
            return None
    
    @staticmethod
    def calculate_daily_averages_by_date(prices):
        """
        Calculate daily average prices grouped by UK calendar date.
        
        Groups price data by physical calendar day (UK local date) and calculates
        one average per date. Supports up to 2 calendar days of pricing data.
        
        Args:
            prices: List of price dictionaries with 'value_inc_vat' and 'valid_from'
        
        Returns:
            list: List of dicts with 'date' (YYYY-MM-DD), 'date_display' (DD/MM/YY), 
                  'average_price' (float). Empty list if no prices.
        """
        if not prices:
            return []
        
        from collections import defaultdict
        
        # Group prices by UK calendar date
        prices_by_date = defaultdict(list)
        for price in prices:
            try:
                dt_uk = utc_to_uk(price['valid_from'])
                date_key = dt_uk.date()
                prices_by_date[date_key].append(price)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error processing price for date grouping: {e}")
                continue
        
        daily_averages = []
        for date_obj in sorted(prices_by_date.keys()):
            date_prices = prices_by_date[date_obj]
            try:
                total_price = sum(p['value_inc_vat'] for p in date_prices)
                avg_price = total_price / len(date_prices)
                
                # Format date for display (DD/MM/YY)
                date_display = date_obj.strftime('%d/%m/%y')
                daily_averages.append({
                    'date': date_obj.strftime('%Y-%m-%d'),
                    'date_display': date_display,
                    'average_price': round(avg_price, 2)
                })
            except (KeyError, TypeError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating average for date {date_obj}: {e}")
                continue
        
        return daily_averages
    
    @staticmethod
    def group_prices_by_date(prices):
        """
        Group prices by UK calendar date.
        
        Args:
            prices: List of price dictionaries with 'valid_from'
        
        Returns:
            dict: Dictionary mapping date objects to lists of prices for that date
        """
        from collections import defaultdict
        
        prices_by_date = defaultdict(list)
        for price in prices:
            try:
                dt_uk = utc_to_uk(price['valid_from'])
                date_key = dt_uk.date()
                prices_by_date[date_key].append(price)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error grouping price by date: {e}")
                continue
        
        return prices_by_date

    @staticmethod
    def filter_prices_from_uk_date(prices, start_date_uk):
        """
        Filter prices so only slots whose UK-local 'valid_from' date is >= start_date_uk are kept.

        This is important when the cache contains "yesterday + today" after midnight:
        we should not display or compute "today" using a fully past UK day.
        """
        if not prices:
            return []

        filtered = []
        for price in prices:
            try:
                dt_uk = utc_to_uk(price["valid_from"])
                if dt_uk.date() >= start_date_uk:
                    filtered.append(price)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Error filtering price by date: {e}")
                continue
        return filtered
    
    @staticmethod
    def calculate_cheapest_per_day(prices, duration_hours, current_time_utc=None):
        """
        Calculate cheapest slot and blocks per calendar day.
        
        Groups prices by UK calendar date and calculates:
        - Lowest 30-minute price per day
        - Cheapest block per day
        - Cheapest remaining block per day (if current_time_utc provided)
        
        Args:
            prices: List of price dictionaries
            duration_hours: Block duration in hours
            current_time_utc: Current time in UTC (for future block calculation)
        
        Returns:
            list: List of dicts, one per day, containing:
                - 'date': date object
                - 'date_display': formatted date string (DD/MM/YY)
                - 'date_iso': ISO date string (YYYY-MM-DD)
                - 'lowest_price': lowest 30-min slot for this day
                - 'cheapest_block': cheapest block for this day
                - 'cheapest_remaining_block': cheapest remaining block for this day (if applicable)
        """
        if not prices:
            return []
        
        prices_by_date = PriceCalculator.group_prices_by_date(prices)
        results = []
        
        for date_obj in sorted(prices_by_date.keys()):
            # Sort prices by valid_from to ensure correct block calculation
            day_prices = sorted(prices_by_date[date_obj], key=lambda x: x.get('valid_from', ''))
            
            # Calculate lowest price for this day
            lowest_price = PriceCalculator.find_lowest_price(day_prices)
            
            # Calculate min and max prices for this day (actual price range)
            min_price = None
            max_price = None
            if day_prices:
                try:
                    prices_values = [p['value_inc_vat'] for p in day_prices if 'value_inc_vat' in p]
                    if prices_values:
                        min_price = min(prices_values)
                        max_price = max(prices_values)
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Error calculating min/max prices for {date_obj}: {e}")
            
            # Calculate cheapest block for this day
            cheapest_block = PriceCalculator.find_cheapest_block(day_prices, duration_hours)
            
            # Log cheapest block for debugging
            if cheapest_block:
                logger.debug(f"Cheapest block for {date_obj}: {cheapest_block.get('start_time_uk')} to {cheapest_block.get('end_time_uk')}, {len(cheapest_block.get('slots', []))} slots")
            
            # Calculate worst (most expensive) block for this day
            worst_block = PriceCalculator.find_worst_block(day_prices, duration_hours)
            
            # Log worst block for debugging
            if worst_block:
                logger.debug(f"Worst block for {date_obj}: {worst_block.get('start_time_uk')} to {worst_block.get('end_time_uk')}, {len(worst_block.get('slots', []))} slots")
            
            # Calculate cheapest remaining block for this day
            # This should exclude slots already in the cheapest_block for this day
            cheapest_remaining_block = None
            if current_time_utc:
                # Build set of cheapest block slot valid_from strings for exclusion
                cheapest_block_slots_utc = set()
                cheapest_block_started = False
                if cheapest_block and cheapest_block.get('slots'):
                    cheapest_block_slots_utc = {slot['valid_from'] for slot in cheapest_block['slots']}
                    logger.debug(f"Excluding cheapest block slots on {date_obj}: {sorted(cheapest_block_slots_utc)}")
                    # Check if cheapest block has started
                    if cheapest_block.get('start_time_uk'):
                        cheapest_block_start = cheapest_block['start_time_uk']
                        # Convert UTC datetime to UK timezone for comparison
                        current_time_uk = current_time_utc.astimezone(UK_TZ)
                        cheapest_block_started = cheapest_block_start <= current_time_uk
                
                # Filter remaining slots, excluding cheapest block slots
                # Important: If cheapest block has started, include ALL remaining slots (past and future)
                # so we preserve the cheapest remaining block even after it passes
                # Important: prices must remain sorted by time for find_cheapest_block to work correctly
                remaining_prices = []
                excluded_count = 0
                future_excluded_count = 0
                
                for price in day_prices:
                    try:
                        # Parse price time first
                        valid_from_str = price['valid_from']
                        if valid_from_str.endswith('Z'):
                            dt_str = valid_from_str.replace('Z', '+00:00')
                        else:
                            dt_str = valid_from_str
                        
                        price_time_utc = datetime.fromisoformat(dt_str)
                        if price_time_utc.tzinfo is None:
                            price_time_utc = price_time_utc.replace(tzinfo=timezone.utc)
                        
                        # Skip if in cheapest block
                        if price['valid_from'] in cheapest_block_slots_utc:
                            excluded_count += 1
                            if price_time_utc >= current_time_utc:
                                future_excluded_count += 1
                            continue
                        
                        # If cheapest block has started, include ALL remaining slots (to preserve past remaining blocks)
                        # Otherwise, include only future slots
                        if cheapest_block_started or price_time_utc >= current_time_utc:
                            remaining_prices.append(price)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Error processing price for remaining block on {date_obj}: {e}")
                        continue
                
                logger.debug(f"Filtered remaining prices for {date_obj}: {len(remaining_prices)} remaining (excluded {excluded_count} total, {future_excluded_count} future, cheapest_block_started={cheapest_block_started})")
                
                # Ensure remaining_prices are sorted by time (should already be, but verify)
                remaining_prices.sort(key=lambda x: x.get('valid_from', ''))
                
                # Calculate cheapest remaining block from filtered prices
                expected_slots = int(duration_hours * 2)
                if len(remaining_prices) >= expected_slots:
                    # Check if we have enough contiguous slots available
                    # Count maximum contiguous sequence length
                    max_contiguous = 1
                    current_contiguous = 1
                    for i in range(1, len(remaining_prices)):
                        if remaining_prices[i-1]['valid_to'] == remaining_prices[i]['valid_from']:
                            current_contiguous += 1
                            max_contiguous = max(max_contiguous, current_contiguous)
                        else:
                            current_contiguous = 1
                    
                    if max_contiguous < expected_slots:
                        logger.debug(f"Not enough contiguous slots for remaining block on {date_obj}: max contiguous={max_contiguous}, needed={expected_slots}")
                        cheapest_remaining_block = None
                    else:
                        cheapest_remaining_block = PriceCalculator.find_cheapest_block(remaining_prices, duration_hours)
                        if not cheapest_remaining_block:
                            logger.debug(f"Could not find contiguous cheapest remaining block on {date_obj} despite having {max_contiguous} contiguous slots")
                    
                    # Verify the remaining block doesn't overlap with cheapest block and has correct duration
                    if cheapest_remaining_block and cheapest_remaining_block.get('slots'):
                        remaining_block_slots_list = [slot['valid_from'] for slot in cheapest_remaining_block['slots']]
                        remaining_block_slots = set(remaining_block_slots_list)
                        
                        # First check: verify all slots are actually in remaining_prices (should be, but verify)
                        remaining_prices_set = {p['valid_from'] for p in remaining_prices}
                        invalid_slots = remaining_block_slots - remaining_prices_set
                        if invalid_slots:
                            logger.warning(f"Cheapest remaining block on {date_obj} contains slots not in remaining_prices: {sorted(invalid_slots)}")
                            cheapest_remaining_block = None
                        # Second check: verify no overlap with cheapest block
                        elif cheapest_block_slots_utc and (remaining_block_slots & cheapest_block_slots_utc):
                            overlap = remaining_block_slots & cheapest_block_slots_utc
                            logger.warning(f"Cheapest remaining block overlaps with cheapest block on {date_obj}: overlap={sorted(overlap)}")
                            logger.debug(f"  Cheapest block slots: {sorted(cheapest_block_slots_utc)}")
                            logger.debug(f"  Remaining block slots: {sorted(remaining_block_slots)}")
                            cheapest_remaining_block = None
                        # Third check: verify correct number of slots
                        elif len(remaining_block_slots_list) != expected_slots:
                            logger.error(f"Cheapest remaining block on {date_obj} has {len(remaining_block_slots_list)} slots, expected {expected_slots}. Slots: {sorted(remaining_block_slots_list)}")
                            cheapest_remaining_block = None
                        else:
                            # Additional validation: verify the block times make sense (critical check)
                            start_uk = cheapest_remaining_block.get('start_time_uk')
                            end_uk = cheapest_remaining_block.get('end_time_uk')
                            if start_uk and end_uk:
                                # Calculate time difference - this is the KEY validation
                                time_diff = end_uk - start_uk
                                expected_hours = duration_hours
                                actual_hours = time_diff.total_seconds() / 3600
                                # Allow small tolerance for half-hour boundaries (0.25 hours = 15 minutes)
                                if abs(actual_hours - expected_hours) > 0.25:
                                    logger.error(f"CRITICAL: Cheapest remaining block on {date_obj} duration mismatch: expected {expected_hours}h, got {actual_hours:.2f}h. Times: {start_uk} to {end_uk}")
                                    logger.error(f"  Block slots count: {len(remaining_block_slots_list)}, Slots (UTC): {sorted(remaining_block_slots_list)}")
                                    # Log the actual slot times to diagnose
                                    if cheapest_remaining_block.get('slots'):
                                        slot_times_uk = [utc_to_uk(slot['valid_from']) for slot in cheapest_remaining_block['slots']]
                                        logger.error(f"  Slot times (UK): {[str(st) for st in sorted(slot_times_uk)]}")
                                    cheapest_remaining_block = None
                                else:
                                    logger.debug(f"Cheapest remaining block for {date_obj}: {start_uk} to {end_uk}, {len(remaining_block_slots_list)} slots ({actual_hours:.2f}h)")
                            else:
                                logger.warning(f"Cheapest remaining block for {date_obj} missing time information")
                                cheapest_remaining_block = None
            
            date_display = date_obj.strftime('%d/%m/%y')
            day_result = {
                'date': date_obj,
                'date_display': date_display,
                'date_iso': date_obj.strftime('%Y-%m-%d'),
                'lowest_price': lowest_price,
                'min_price': min_price,
                'max_price': max_price,
                'cheapest_block': cheapest_block,
                'cheapest_remaining_block': cheapest_remaining_block,
                'worst_block': worst_block
            }
            
            results.append(day_result)
        
        return results
    
    @staticmethod
    def calculate_charging_cost(average_price, battery_capacity_kwh):
        """
        Calculate estimated cost to charge battery.
        
        Args:
            average_price: Average price in pence per kWh
            battery_capacity_kwh: Battery capacity in kWh
        
        Returns:
            float: Estimated cost in pounds, or None if invalid
        """
        if not average_price or not battery_capacity_kwh:
            return None
        
        if average_price < 0 or battery_capacity_kwh < 0:
            return None
        
        # Price is in pence per kWh
        cost_pence = average_price * battery_capacity_kwh
        cost_pounds = cost_pence / 100
        
        return round(cost_pounds, 2)
    
    @staticmethod
    def format_price_data(prices):
        """
        Format prices for chart display.
        Sorts prices chronologically and includes dates in labels when dates change.
        
        Args:
            prices: List of price dictionaries (should be pre-sorted)
        
        Returns:
            dict: Chart data with 'labels', 'prices', 'times'
        """
        chart_data = {
            'labels': [],
            'prices': [],
            'times': []
        }
        
        # Ensure prices are sorted chronologically
        try:
            sorted_prices = sorted(prices, key=lambda x: x.get('valid_from', ''))
        except Exception as e:
            logger.warning(f"Error sorting prices in format_price_data: {e}")
            sorted_prices = prices
        
        previous_date = None
        
        for price in sorted_prices:
            try:
                # Convert UTC to UK timezone
                dt_uk = utc_to_uk(price['valid_from'])
                current_date = dt_uk.date()
                
                # Format label: include date if it changed or if it's the first entry
                if previous_date is None or current_date != previous_date:
                    # Show date and time for first entry of a new date
                    label = format_uk_datetime_short(dt_uk)
                else:
                    # Show only time if same date
                    label = format_uk_time(dt_uk)
                
                chart_data['labels'].append(label)
                chart_data['prices'].append(price['value_inc_vat'])
                chart_data['times'].append(price['valid_from'])  # Keep UTC for reference
                
                previous_date = current_date
            except (KeyError, ValueError) as e:
                logger.error(f"Error formatting price data: {e}")
                continue
        
        return chart_data

