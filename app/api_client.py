"""
Octopus Energy API Client.
Fetches region and pricing data from Octopus Energy public APIs.
"""
import requests
from datetime import datetime, timezone
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class OctopusAPIClient:
    """Client for interacting with Octopus Energy API."""
    
    @staticmethod
    def _get_config():
        """Get current config values, with fallback defaults."""
        from app.config import Config
        
        try:
            # Try to get from Flask app context
            if current_app:
                return {
                    'base_url': current_app.config.get('OCTOPUS_API_BASE_URL', Config.OCTOPUS_API_BASE_URL),
                    'product_code': current_app.config.get('OCTOPUS_PRODUCT_CODE', Config.OCTOPUS_PRODUCT_CODE),
                    'timeout': current_app.config.get('OCTOPUS_API_TIMEOUT', Config.OCTOPUS_API_TIMEOUT),
                    'region_names': current_app.config.get('OCTOPUS_REGION_NAMES', Config.OCTOPUS_REGION_NAMES),
                    'get_regions_url': lambda: current_app.config.get('OCTOPUS_API_BASE_URL', Config.OCTOPUS_API_BASE_URL) + '/industry/grid-supply-points/?group_by=region',
                    'get_products_url': Config.get_products_url,
                    'get_prices_url': Config.get_prices_url,
                    'get_gsp_lookup_url': lambda postcode: Config.get_gsp_lookup_url(postcode),
                    'direction_filter': current_app.config.get('OCTOPUS_PRODUCT_DIRECTION_FILTER', Config.OCTOPUS_PRODUCT_DIRECTION_FILTER)
                }
        except RuntimeError:
            # Not in Flask app context, use defaults
            pass
        
        # Fallback to defaults (for testing or non-Flask usage)
        return {
            'base_url': Config.OCTOPUS_API_BASE_URL,
            'product_code': Config.OCTOPUS_PRODUCT_CODE,
            'timeout': Config.OCTOPUS_API_TIMEOUT,
            'region_names': Config.OCTOPUS_REGION_NAMES,
            'get_regions_url': Config.get_regions_url,
            'get_products_url': Config.get_products_url,
            'get_prices_url': Config.get_prices_url,
            'get_gsp_lookup_url': Config.get_gsp_lookup_url,
            'direction_filter': Config.OCTOPUS_PRODUCT_DIRECTION_FILTER
        }
    
    @staticmethod
    def get_regions():
        """
        Fetch available regions from Octopus API.
        
        Returns:
            dict: API response with regions list in format {'results': [{'region': 'A', 'name': '...'}, ...]}
            
        Raises:
            requests.RequestException: If API request fails
        """
        # Get config values
        config = OctopusAPIClient._get_config()
        
        # Use URL from config
        url = config['get_regions_url']()
        try:
            logger.info(f"API Call: GET {url}")
            response = requests.get(url, timeout=config['timeout'])
            response.raise_for_status()
            data = response.json()
            logger.info(f"API Response: Status {response.status_code}, Regions found: {len(data.get('results', []))}")
            
            # Get region names from config
            region_names = config['region_names']
            
            # Transform the data to match expected format
            # group_id is like '_A', '_B', etc. - we need to strip the underscore
            regions = []
            for item in data.get('results', []):
                group_id = item.get('group_id', '')
                # Remove leading underscore if present
                region_code = group_id.lstrip('_')
                if region_code:
                    # Get region name from mapping or use default
                    region_name = region_names.get(region_code, f"Region {region_code}")
                    regions.append({
                        'region': region_code,
                        'name': region_name
                    })
            
            return {'results': regions}
        except requests.exceptions.Timeout:
            logger.error("Timeout fetching regions from Octopus API")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching regions: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching regions: {e}")
            raise
    
    @staticmethod
    def get_agile_products(direction_filter=None):
        """
        Discover active Agile products from Octopus API.
        
        Args:
            direction_filter: Filter by direction - 'IMPORT', 'EXPORT', or 'BOTH'. 
                             If None, uses config default.
        
        Returns:
            list: List of product dictionaries with 'code' and 'full_name' keys
        
        Raises:
            requests.RequestException: If API request fails
        """
        config = OctopusAPIClient._get_config()
        direction = direction_filter or config.get('direction_filter', 'IMPORT')
        
        url = config['get_products_url']()
        all_products = []
        next_url = url
        
        try:
            # Handle pagination
            while next_url:
                logger.info(f"API Call: GET {next_url}")
                response = requests.get(next_url, timeout=config['timeout'])
                response.raise_for_status()
                data = response.json()
                
                products = data.get('results', [])
                all_products.extend(products)
                
                # Check for next page
                next_url = data.get('next')
            
            logger.info(f"API Response: Total products fetched: {len(all_products)}")
            
            # Filter Agile products
            agile_products = []
            for product in all_products:
                code = product.get('code', '').upper()
                if 'AGILE' not in code:
                    continue
                
                # Check direction filter
                product_direction = product.get('direction', '').upper()
                if direction == 'BOTH' or product_direction == direction:
                    # Check if product is active
                    available_to = product.get('available_to')
                    if available_to is None:
                        # Product is currently available (no end date)
                        agile_products.append({
                            'code': product.get('code'),
                            'full_name': product.get('full_name', product.get('code'))
                        })
                    else:
                        # Check if available_to is in the future
                        try:
                            # Parse ISO format datetime
                            available_to_dt = datetime.fromisoformat(available_to.replace('Z', '+00:00'))
                            if available_to_dt > datetime.now(timezone.utc):
                                agile_products.append({
                                    'code': product.get('code'),
                                    'full_name': product.get('full_name', product.get('code'))
                                })
                        except (ValueError, AttributeError):
                            # If parsing fails, skip this product
                            logger.warning(f"Could not parse available_to date for product {product.get('code')}: {available_to}")
                            continue
            
            logger.info(f"Filtered Agile products found: {len(agile_products)} (direction={direction})")
            if len(agile_products) == 0:
                logger.warning("No active Agile products found matching criteria")
            elif len(agile_products) > 1:
                logger.info(f"Multiple Agile products found: {[p['code'] for p in agile_products]}")
            
            return agile_products
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching products from {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching products: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching products: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_prices(product_code, region_code):
        """
        Fetch half-hourly prices for a region and product.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code (e.g., 'A', 'B', etc.)
        
        Returns:
            dict: API response with prices list
            
        Raises:
            requests.RequestException: If API request fails
        """
        # Get config values
        config = OctopusAPIClient._get_config()
        
        # Use URL from config
        url = config['get_prices_url'](product_code, region_code)
        
        # Get today's date in UK timezone, then convert to UTC for API call
        from app.timezone_utils import get_uk_now
        uk_now = get_uk_now()
        # Round down to nearest half hour
        uk_now = uk_now.replace(minute=(0 if uk_now.minute < 30 else 30), second=0, microsecond=0)
        # Convert UK time to UTC for API
        today_utc = uk_now.astimezone(timezone.utc)

        params = {
            'period_from': today_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'page_size': 96  # 48 half-hour slots per day
        }

        try:
            logger.info(f"API Call: GET {url} with params {params}")
            response = requests.get(url, params=params, timeout=config['timeout'])
            response.raise_for_status()
            data = response.json()
            logger.info(f"API Response: Status {response.status_code}, Prices found: {len(data.get('results', []))}")
            return data
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching prices for region {region_code}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching prices for {region_code}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching prices for {region_code}: {e}")
            raise
    
    @staticmethod
    def lookup_region_from_postcode(postcode):
        """
        Look up region codes from UK postcode using Grid Supply Point API.
        
        Args:
            postcode: UK postcode (will be normalized)
        
        Returns:
            str or list: Single region code (e.g., 'A') if one result, list of region codes if multiple, None if no results
            
        Raises:
            requests.RequestException: If API request fails (not for zero results)
        """
        # Normalize postcode: remove spaces, convert to uppercase
        normalized = postcode.replace(' ', '').upper().strip()
        
        if not normalized:
            logger.warning("Empty postcode provided for region lookup")
            return None
        
        # Get config values
        config = OctopusAPIClient._get_config()
        
        # Use URL from config
        url = config['get_gsp_lookup_url'](normalized)
        
        try:
            logger.info(f"API Call: GET {url} (postcode lookup)")
            response = requests.get(url, timeout=config['timeout'])
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            logger.info(f"API Response: Status {response.status_code}, GSP results found: {len(results)}")
            
            if not results:
                logger.warning(f"No Grid Supply Points found for postcode: {normalized}")
                return None
            
            # Extract unique region codes from all results
            # group_id format is like '_A', '_B', '_N', etc.
            region_codes = set()
            for result in results:
                group_id = result.get('group_id', '')
                if group_id:
                    # Remove leading underscore if present
                    region_code = group_id.lstrip('_')
                    if region_code:
                        region_codes.add(region_code)
            
            if not region_codes:
                logger.warning(f"No valid group_ids found in GSP results for postcode: {normalized}")
                return None
            
            # Convert to sorted list for consistent ordering
            region_codes_list = sorted(list(region_codes))
            
            if len(region_codes_list) == 1:
                # Single region: return as string for backward compatibility
                logger.info(f"Postcode {normalized} mapped to single region: {region_codes_list[0]}")
                return region_codes_list[0]
            else:
                # Multiple regions: return as list
                logger.info(f"Postcode {normalized} mapped to multiple regions: {region_codes_list}")
                return region_codes_list
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching GSP data for postcode: {normalized}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GSP data for postcode {normalized}: {e}")
            raise
        except (KeyError, TypeError) as e:
            logger.error(f"Unexpected API response format for postcode {normalized}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error looking up postcode {normalized}: {e}")
            return None

