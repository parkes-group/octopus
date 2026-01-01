"""
Price calculation logic.
Finds lowest prices and cheapest charging blocks.
"""
from datetime import datetime, timezone
import logging
from app.timezone_utils import utc_to_uk, format_uk_datetime_short, format_uk_time, format_uk_date, get_uk_now

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
        
        # Sliding window approach
        for i in range(len(prices) - slots_needed + 1):
            block = prices[i:i + slots_needed]
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
                logger.error(f"Error processing price block: {e}")
                continue
        
        return cheapest_block
    
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
        Calculate the average price for all prices in the day.
        
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

