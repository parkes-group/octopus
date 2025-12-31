"""
Main application routes.
MVP: Anonymous usage only, no authentication required.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.price_calculator import PriceCalculator
from app.forms import RegionSelectionForm, PriceCalculationForm, PostcodeForm
from app.timezone_utils import get_uk_date_string
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

def normalize_postcode(postcode):
    """
    Normalize UK postcode: remove spaces, convert to uppercase.
    
    Args:
        postcode: Raw postcode string
    
    Returns:
        str: Normalized postcode
    """
    if not postcode:
        return ''
    return postcode.replace(' ', '').upper().strip()

# Note: Postcode validation is now handled by the Octopus API
# We only do basic normalization (remove spaces, uppercase)
# The API will return 0 results if the postcode is invalid

@bp.route('/', methods=['GET', 'POST'])
def index():
    """Homepage - postcode-first region detection with manual fallback and product selection."""
    postcode_form = PostcodeForm()
    region_form = RegionSelectionForm()
    show_region_dropdown = False
    error_message = None
    submitted_postcode = None
    
    # Discover Agile products first
    agile_products = []
    selected_product_code = None
    selected_product_name = None
    show_product_dropdown = False
    
    try:
        agile_products = OctopusAPIClient.get_agile_products()
        if len(agile_products) == 0:
            logger.error("No Agile products found")
            error_message = "No Agile products are currently available. Please try again later."
        elif len(agile_products) == 1:
            # Single product: auto-select
            selected_product_code = agile_products[0]['code']
            selected_product_name = agile_products[0]['full_name']
            show_product_dropdown = False
        else:
            # Multiple products: show dropdown
            show_product_dropdown = True
            # Check if product was already selected via query param
            selected_product_code = request.args.get('product')
            if selected_product_code:
                # Validate the selected product exists
                matching = [p for p in agile_products if p['code'] == selected_product_code]
                if matching:
                    selected_product_name = matching[0]['full_name']
                else:
                    selected_product_code = None
    except Exception as e:
        logger.error(f"Error loading Agile products: {e}", exc_info=True)
        if not error_message:
            error_message = "Unable to load tariff information. Please try again later."
    
    # Load regions for fallback dropdown
    try:
        regions = OctopusAPIClient.get_regions()
        regions_list = regions.get('results', [])
        # Populate region form choices
        region_form.region.choices = [(r['region'], f"{r['region']} - {r['name']}") for r in regions_list]
    except Exception as e:
        logger.error(f"Error loading regions: {e}")
        regions_list = []
        if not error_message:
            error_message = "Unable to load regions. Please try again later."
    
    # Handle POST: form submission (includes postcode, region if applicable, and product)
    if request.method == 'POST':
        submitted_region = request.form.get('region')
        submitted_product = request.form.get('product')
        form_postcode = request.form.get('postcode', '')
        
        # Get product from form data (if multiple products, required field)
        if show_product_dropdown:
            if submitted_product:
                matching = [p for p in agile_products if p['code'] == submitted_product]
                if matching:
                    selected_product_code = submitted_product
                    selected_product_name = matching[0]['full_name']
                else:
                    error_message = "Please select a valid tariff version."
                    submitted_postcode = form_postcode
            else:
                error_message = "Please select a tariff version."
                submitted_postcode = form_postcode
        else:
            # Single product, use auto-selected one
            selected_product_code = agile_products[0]['code'] if len(agile_products) == 1 else None
        
        # Check if postcode has changed from what was previously submitted
        postcode_changed = False
        if submitted_postcode and form_postcode:
            # Normalize both for comparison
            normalized_previous = normalize_postcode(submitted_postcode) if submitted_postcode else ''
            normalized_current = normalize_postcode(form_postcode) if form_postcode else ''
            postcode_changed = normalized_current != normalized_previous
        elif form_postcode and not submitted_postcode:
            # New postcode entered (no previous submission)
            postcode_changed = True
        
        # If region is provided and postcode hasn't changed, use it directly (skip postcode lookup)
        if submitted_region and selected_product_code and not postcode_changed:
            # Validate region exists
            if any(r['region'] == submitted_region for r in regions_list):
                logger.info(f"Region {submitted_region} selected manually")
                return redirect(url_for('main.prices', region=submitted_region, product=selected_product_code))
            else:
                error_message = "Invalid region selected. Please try again."
                show_region_dropdown = True
                submitted_postcode = form_postcode
        
        # If postcode changed or no region provided, validate postcode form and do postcode lookup
        elif postcode_form.validate_on_submit() and selected_product_code:
            submitted_postcode = postcode_form.postcode.data
            
            # Normalize postcode (remove spaces, uppercase)
            normalized_postcode = normalize_postcode(submitted_postcode)
            
            # Look up region from postcode (let API determine validity)
            try:
                region_result = OctopusAPIClient.lookup_region_from_postcode(normalized_postcode)
                
                if region_result is None:
                    # No results from API: show region dropdown
                    logger.info(f"No region found for postcode: {normalized_postcode}")
                    error_message = f"No region found for postcode '{submitted_postcode}'. Please select your region below."
                    show_region_dropdown = True
                elif isinstance(region_result, str):
                    # Single region: redirect to prices page with product
                    logger.info(f"Postcode {normalized_postcode} successfully mapped to single region {region_result}")
                    return redirect(url_for('main.prices', region=region_result, product=selected_product_code))
                elif isinstance(region_result, list):
                    # Multiple regions: show dropdown with matching regions only
                    logger.info(f"Postcode {normalized_postcode} mapped to multiple regions: {region_result}")
                    error_message = f"Postcode '{submitted_postcode}' matches multiple regions. Please select your region below:"
                    show_region_dropdown = True
                    # Filter regions list to only show matching regions
                    matching_regions = [r for r in regions_list if r['region'] in region_result]
                    if matching_regions:
                        # Update regions_list for template
                        regions_list = matching_regions
                else:
                    # Unexpected return type
                    logger.warning(f"Unexpected return type from lookup_region_from_postcode: {type(region_result)}")
                    error_message = f"Unable to process postcode '{submitted_postcode}'. Please select your region below."
                    show_region_dropdown = True
                    
            except Exception as e:
                # API error: show region dropdown
                logger.error(f"Error looking up postcode {normalized_postcode}: {e}", exc_info=True)
                error_message = f"Unable to look up postcode '{submitted_postcode}'. Please select your region below."
                show_region_dropdown = True
        elif request.method == 'POST':
            # Form validation failed or missing product
            submitted_postcode = request.form.get('postcode', '')
    
    # Render template
    return render_template('index.html',
                         postcode_form=postcode_form,
                         region_form=region_form,
                         regions=regions_list,
                         agile_products=agile_products,
                         selected_product_code=selected_product_code,
                         selected_product_name=selected_product_name,
                         show_region_dropdown=show_region_dropdown,
                         show_product_dropdown=show_product_dropdown,
                         error=error_message,
                         submitted_postcode=submitted_postcode)

@bp.route('/prices')
def prices():
    """Display prices and calculations."""
    region = request.args.get('region')
    product_code = request.args.get('product')
    duration = request.args.get('duration', type=float, default=3.5)
    capacity = request.args.get('capacity', type=float)
    
    # Discover Agile products for dropdown
    agile_products = []
    selected_product_name = None
    try:
        agile_products = OctopusAPIClient.get_agile_products()
        if product_code:
            matching = [p for p in agile_products if p['code'] == product_code]
            if matching:
                selected_product_name = matching[0]['full_name']
            else:
                # Invalid product code
                flash('Invalid tariff version selected.', 'error')
                return redirect(url_for('main.index'))
    except Exception as e:
        logger.error(f"Error loading Agile products for prices page: {e}")
    
    # Get regions list for dropdown
    try:
        regions_data = OctopusAPIClient.get_regions()
        regions_list = regions_data.get('results', [])
    except Exception as e:
        logger.error(f"Error loading regions for prices page: {e}")
        regions_list = []
    
    if not region:
        flash('Please select a region.', 'error')
        return redirect(url_for('main.index'))
    
    if not product_code:
        # Try to auto-select if only one product
        if len(agile_products) == 1:
            product_code = agile_products[0]['code']
            selected_product_name = agile_products[0]['full_name']
            # Redirect to include product in URL
            return redirect(url_for('main.prices', region=region, product=product_code, 
                                   duration=duration, capacity=capacity))
        else:
            flash('Please select a tariff version.', 'error')
            return redirect(url_for('main.index'))
    
    # Validate duration (supports decimals, e.g., 3.5 hours)
    if duration < 0.5 or duration > 6.0:
        duration = 4.0
    
    # Get prices (with caching) - use UK date
    date_str = get_uk_date_string()
    prices_data = CacheManager.get_cached_prices(product_code, region, date_str)
    
    if not prices_data:
        try:
            api_response = OctopusAPIClient.get_prices(product_code, region)
            prices_data = api_response.get('results', [])
            CacheManager.cache_prices(product_code, region, date_str, prices_data)
        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            # Try to use stale cache if available
            flash('Unable to fetch current prices. Please try again later.', 'error')
            return redirect(url_for('main.index'))
    
    # Sort prices chronologically by valid_from
    try:
        prices_data = sorted(prices_data, key=lambda x: x.get('valid_from', ''))
    except Exception as e:
        logger.warning(f"Error sorting prices: {e}")
    
    # Calculate results
    lowest_price = PriceCalculator.find_lowest_price(prices_data)
    cheapest_block = PriceCalculator.find_cheapest_block(prices_data, duration)
    
    # Calculate cost if capacity provided
    estimated_cost = None
    if capacity and cheapest_block:
        estimated_cost = PriceCalculator.calculate_charging_cost(
            cheapest_block['average_price'],
            capacity
        )
    
    # Format for chart (include highlighting data)
    chart_data = PriceCalculator.format_price_data(prices_data)
    
    # Create set of cheapest block time slots for template highlighting
    cheapest_block_times = set()
    if cheapest_block and cheapest_block.get('slots'):
        cheapest_block_times = {slot['valid_from'] for slot in cheapest_block['slots']}
    
    # Add highlighting information for chart
    if cheapest_block:
        # Find indices of cheapest block slots in the prices array
        cheapest_block_indices = []
        for idx, price in enumerate(prices_data):
            if price['valid_from'] in cheapest_block_times:
                cheapest_block_indices.append(idx)
        chart_data['cheapest_block_indices'] = cheapest_block_indices
    else:
        chart_data['cheapest_block_indices'] = []
    
    # Find index of lowest price for chart highlighting
    lowest_price_index = None
    if lowest_price:
        for idx, price in enumerate(prices_data):
            if price['valid_from'] == lowest_price['time_from']:
                lowest_price_index = idx
                break
    chart_data['lowest_price_index'] = lowest_price_index
    
    # Prepare UK timezone data for template display
    # Convert all price times to UK timezone for template
    from app.timezone_utils import utc_to_uk, format_uk_time, format_uk_date
    prices_with_uk_times = []
    for price in prices_data:
        price_uk = price.copy()
        dt_uk = utc_to_uk(price['valid_from'])
        price_uk['time_uk'] = format_uk_time(dt_uk)
        price_uk['date_uk'] = format_uk_date(dt_uk)
        price_uk['datetime_uk'] = dt_uk
        prices_with_uk_times.append(price_uk)
    
    # Post-MVP: Get user preferences if logged in
    # user_prefs = None
    # if 'user_id' in session:
    #     user = User.query.get(session['user_id'])
    #     if user and user.preferences:
    #         user_prefs = user.preferences
    
    # Create set of cheapest block time slots for efficient template lookup
    cheapest_block_time_set = set()
    if cheapest_block and cheapest_block.get('slots'):
        cheapest_block_time_set = {slot['valid_from'] for slot in cheapest_block['slots']}
    
    return render_template('prices.html',
                         region=region,
                         product_code=product_code,
                         product_name=selected_product_name,
                         regions=regions_list,
                         agile_products=agile_products,
                         duration=duration,
                         capacity=capacity,
                         prices=prices_with_uk_times,
                         lowest_price=lowest_price,
                         cheapest_block=cheapest_block,
                         cheapest_block_times=cheapest_block_time_set,
                         estimated_cost=estimated_cost,
                         chart_data=chart_data)

