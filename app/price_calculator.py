"""
Price calculation logic.
Finds lowest prices and cheapest charging blocks.
"""
from datetime import datetime
import logging
from app.timezone_utils import utc_to_uk, format_uk_datetime_short, format_uk_time, format_uk_date

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

