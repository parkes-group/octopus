"""
Main application routes.
MVP: Anonymous usage only, no authentication required.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, session, make_response, jsonify, current_app
from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.price_calculator import PriceCalculator
from app.forms import RegionSelectionForm, PriceCalculationForm, PostcodeForm
from app.timezone_utils import get_uk_now
from app.config import Config
from app.vote_manager import VoteManager
from app.region_request_tracker import RegionRequestTracker
from urllib.parse import urlparse, parse_qs
from datetime import timezone
import logging
import os

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
    
    # Load regions from static mapping (no API call needed)
    regions_list = Config.get_regions_list()
    # Populate region form choices
    region_form.region.choices = [(r['region'], f"{r['region']} - {r['name']}") for r in regions_list]
    
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
        
        # Get the last postcode from session (for comparison)
        last_postcode = session.get('last_postcode_index', '')
        
        # Check if postcode has changed from what was previously submitted
        postcode_changed = False
        if last_postcode and form_postcode:
            # Normalize both for comparison
            normalized_previous = normalize_postcode(last_postcode) if last_postcode else ''
            normalized_current = normalize_postcode(form_postcode) if form_postcode else ''
            postcode_changed = normalized_current != normalized_previous
        elif form_postcode and not last_postcode:
            # New postcode entered (no previous submission)
            postcode_changed = True
        
        # If region is provided and postcode hasn't changed, use it directly (skip postcode lookup)
        if submitted_region and selected_product_code and not postcode_changed:
            # Validate region exists
            if any(r['region'] == submitted_region for r in regions_list):
                logger.info(f"Region {submitted_region} selected manually")
                # Record region request for analytics (manual region selection)
                RegionRequestTracker.record_region_request(submitted_region)
                # Store last tracked region in session to prevent duplicate tracking
                session['last_tracked_region'] = submitted_region
                # Clear the stored postcode since we're redirecting
                session.pop('last_postcode_index', None)
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
                    # Store the postcode in session for comparison on next submission
                    session['last_postcode_index'] = normalized_postcode
                elif isinstance(region_result, str):
                    # Single region: redirect to prices page with product
                    logger.debug(f"Postcode {normalized_postcode} successfully mapped to single region {region_result}")
                    # Record region request for analytics (postcode resolved to single region)
                    RegionRequestTracker.record_region_request(region_result)
                    # Store last tracked region in session to prevent duplicate tracking
                    session['last_tracked_region'] = region_result
                    # Clear the stored postcode since we're redirecting
                    session.pop('last_postcode_index', None)
                    return redirect(url_for('main.prices', region=region_result, product=selected_product_code))
                elif isinstance(region_result, list):
                    # Multiple regions: show dropdown with matching regions only
                    logger.debug(f"Postcode {normalized_postcode} mapped to multiple regions: {region_result}")
                    error_message = f"Postcode '{submitted_postcode}' matches multiple regions. Please select your region below:"
                    show_region_dropdown = True
                    # Store the postcode in session for comparison on next submission
                    session['last_postcode_index'] = normalized_postcode
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
                    # Store the postcode in session for comparison on next submission
                    if form_postcode:
                        session['last_postcode_index'] = normalized_postcode
                    
            except Exception as e:
                # API error: show region dropdown
                logger.error(f"Error looking up postcode {normalized_postcode}: {e}", exc_info=True)
                error_message = f"Unable to look up postcode '{submitted_postcode}'. Please select your region below."
                show_region_dropdown = True
                # Store the postcode in session for comparison on next submission
                if form_postcode:
                    session['last_postcode_index'] = normalized_postcode
        elif request.method == 'POST':
            # Form validation failed or missing product
            submitted_postcode = request.form.get('postcode', '')
    
    # Load 2025 statistics for display (national averages)
    from app.stats_loader import StatsLoader
    stats_2025 = StatsLoader.get_stats_for_display(region_code='national')
    
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
                         submitted_postcode=submitted_postcode,
                         stats_2025=stats_2025,
                         page_name='index')

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
    
    # Get regions list for dropdown (from static mapping, no API call needed)
    regions_list = Config.get_regions_list()
    
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
    
    # Get prices (check cache first - will use cached data if not expired)
    prices_data = CacheManager.get_cached_prices(product_code, region)
    
    if not prices_data:
        # Cache miss or expired - fetch from API
        logger.debug(f"Cache miss or expired for {product_code} {region}, fetching from API")
        try:
            api_response = OctopusAPIClient.get_prices(product_code, region)
            prices_data = api_response.get('results', [])
            CacheManager.cache_prices(product_code, region, prices_data)
            logger.debug(f"Fetched and cached prices for {product_code} {region}")
        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            # Try to use stale cache if available
            flash('Unable to fetch current prices. Please try again later.', 'error')
            return redirect(url_for('main.index'))
    
    # Record region request for analytics only if region has changed from last tracked region
    # This prevents duplicate tracking on page refreshes, settings changes, or navigation returns
    last_tracked_region = session.get('last_tracked_region')
    if region != last_tracked_region:
        # Region has changed - record the request
        RegionRequestTracker.record_region_request(region)
        # Update session with new tracked region
        session['last_tracked_region'] = region
    
    # Sort prices chronologically by valid_from
    try:
        prices_data = sorted(prices_data, key=lambda x: x.get('valid_from', ''))
    except Exception as e:
        logger.warning(f"Error sorting prices: {e}")
    
    # Get current time in UK timezone, convert to UTC for comparisons
    from app.timezone_utils import get_uk_now
    from datetime import timezone
    uk_now = get_uk_now()
    current_time_utc = uk_now.astimezone(timezone.utc)
    
    # Calculate results
    lowest_price = PriceCalculator.find_lowest_price(prices_data)
    absolute_cheapest_block = PriceCalculator.find_cheapest_block(prices_data, duration)
    future_cheapest_block = PriceCalculator.find_future_cheapest_block(prices_data, duration, current_time_utc)
    daily_average_price = PriceCalculator.calculate_daily_average_price(prices_data)
    
    # Calculate cost if capacity provided (use future block if available, otherwise absolute)
    estimated_cost = None
    cost_block = future_cheapest_block if future_cheapest_block else absolute_cheapest_block
    if capacity and cost_block:
        estimated_cost = PriceCalculator.calculate_charging_cost(
            cost_block['average_price'],
            capacity
        )
    
    # Format for chart (include highlighting data)
    chart_data = PriceCalculator.format_price_data(prices_data)
    
    # Create sets of block time slots for template highlighting
    absolute_cheapest_block_times = set()
    if absolute_cheapest_block and absolute_cheapest_block.get('slots'):
        absolute_cheapest_block_times = {slot['valid_from'] for slot in absolute_cheapest_block['slots']}
    
    future_cheapest_block_times = set()
    if future_cheapest_block and future_cheapest_block.get('slots'):
        future_cheapest_block_times = {slot['valid_from'] for slot in future_cheapest_block['slots']}
    
    # Add highlighting information for chart (both blocks)
    absolute_cheapest_block_indices = []
    if absolute_cheapest_block:
        for idx, price in enumerate(prices_data):
            if price['valid_from'] in absolute_cheapest_block_times:
                absolute_cheapest_block_indices.append(idx)
    
    future_cheapest_block_indices = []
    if future_cheapest_block:
        for idx, price in enumerate(prices_data):
            if price['valid_from'] in future_cheapest_block_times:
                future_cheapest_block_indices.append(idx)
    
    chart_data['absolute_cheapest_block_indices'] = absolute_cheapest_block_indices
    chart_data['future_cheapest_block_indices'] = future_cheapest_block_indices
    
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
    
    # Store prices page state in session for navigation
    session['last_prices_state'] = {
        'region': region,
        'product': product_code,
        'duration': duration,
        'capacity': capacity
    }
    
    # Load 2025 statistics for display (use selected region)
    from app.stats_loader import StatsLoader
    stats_2025 = StatsLoader.get_stats_for_display(region_code=region)
    
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
                         absolute_cheapest_block=absolute_cheapest_block,
                         future_cheapest_block=future_cheapest_block,
                         absolute_cheapest_block_times=absolute_cheapest_block_times,
                         future_cheapest_block_times=future_cheapest_block_times,
                         daily_average_price=daily_average_price,
                         estimated_cost=estimated_cost,
                         chart_data=chart_data,
                         stats_2025=stats_2025,
                         current_time_uk=uk_now,
                         page_name='prices')

def _calculate_region_summaries(product_code, duration_hours=3.5):
    """
    Calculate price summaries for all regions.
    Reuses existing calculation functions.
    
    Args:
        product_code: Octopus product code
        duration_hours: Block duration in hours (default 3.5)
    
    Returns:
        list: Region summaries with calculation results, or empty list on error
    """
    region_summaries = []
    
    # Get all regions from static mapping (no API call needed)
    from app.config import Config
    regions_list = Config.get_regions_list()
    
    # Get current time in UTC for future block calculations
    uk_now = get_uk_now()
    current_time_utc = uk_now.astimezone(timezone.utc)
    
    # Track min/max dates from price data (for data range display)
    min_date_time_uk = None
    max_date_time_uk = None
    
    # Process each region
    for region_info in regions_list:
        region_code = region_info.get('region')
        region_name = region_info.get('name', f"Region {region_code}")
        
        if not region_code:
            continue
        
        try:
            # Get prices (check cache first - will use cached data if not expired)
            prices_data = CacheManager.get_cached_prices(product_code, region_code)
            
            if not prices_data:
                # Cache miss or expired - fetch from API
                logger.debug(f"Cache miss or expired for region {region_code}, fetching from API")
                try:
                    api_response = OctopusAPIClient.get_prices(product_code, region_code)
                    prices_data = api_response.get('results', [])
                    CacheManager.cache_prices(product_code, region_code, prices_data)
                    logger.debug(f"Fetched and cached prices for region {region_code}")
                except Exception as e:
                    logger.warning(f"Error fetching prices for region {region_code}: {e}")
                    # Skip this region, continue with others
                    continue
            
            # Sort prices chronologically
            try:
                prices_data = sorted(prices_data, key=lambda x: x.get('valid_from', ''))
            except Exception as e:
                logger.warning(f"Error sorting prices for region {region_code}: {e}")
                continue
            
            # Track min/max dates (from first successful region, all should have same range)
            if prices_data and min_date_time_uk is None:
                from app.timezone_utils import utc_to_uk
                first_price_uk = utc_to_uk(prices_data[0]['valid_from'])
                last_price_uk = utc_to_uk(prices_data[-1]['valid_to'])
                min_date_time_uk = first_price_uk
                max_date_time_uk = last_price_uk
            
            # Use existing calculation functions (caching ensures data is fetched efficiently)
            lowest_price_info = PriceCalculator.find_lowest_price(prices_data)
            cheapest_block = PriceCalculator.find_cheapest_block(prices_data, duration_hours)
            future_cheapest_block = PriceCalculator.find_future_cheapest_block(prices_data, duration_hours, current_time_utc)
            
            # Build summary
            summary = {
                'region_code': region_code,
                'region_name': region_name,
                'cheapest_slot_price': lowest_price_info['price'] if lowest_price_info else None,
                'cheapest_slot_time_from_uk': lowest_price_info['time_from_uk'] if lowest_price_info else None,
                'cheapest_block_average': cheapest_block['average_price'] if cheapest_block else None,
                'cheapest_block_start_uk': cheapest_block['start_time_uk'] if cheapest_block else None,
                'cheapest_block_end_uk': cheapest_block['end_time_uk'] if cheapest_block else None,
                'future_block_average': future_cheapest_block['average_price'] if future_cheapest_block else None,
                'future_block_start_uk': future_cheapest_block['start_time_uk'] if future_cheapest_block else None,
                'future_block_end_uk': future_cheapest_block['end_time_uk'] if future_cheapest_block else None,
                'error': None
            }
            
            region_summaries.append(summary)
            
        except Exception as e:
            logger.error(f"Error processing region {region_code}: {e}", exc_info=True)
            # Add error entry but continue processing other regions
            region_summaries.append({
                'region_code': region_code,
                'region_name': region_name,
                'cheapest_slot_price': None,
                'cheapest_slot_time_from_uk': None,
                'cheapest_block_average': None,
                'cheapest_block_start_uk': None,
                'cheapest_block_end_uk': None,
                'future_block_average': None,
                'future_block_start_uk': None,
                'future_block_end_uk': None,
                'error': str(e)
            })
            continue
    
    return region_summaries, min_date_time_uk, max_date_time_uk

@bp.route('/regions')
def regions():
    """Region summary page - shows aggregated calculations across all regions."""
    # Get product code from query params or use default
    product_code = request.args.get('product')
    
    # Discover Agile products
    agile_products = []
    selected_product_name = None
    try:
        agile_products = OctopusAPIClient.get_agile_products()
        if product_code:
            matching = [p for p in agile_products if p['code'] == product_code]
            if matching:
                selected_product_name = matching[0]['full_name']
            else:
                product_code = None
    except Exception as e:
        logger.error(f"Error loading Agile products for regions page: {e}")
    
    # Auto-select if only one product
    if not product_code and len(agile_products) == 1:
        product_code = agile_products[0]['code']
        selected_product_name = agile_products[0]['full_name']
    
    if not product_code:
        flash('Please select a tariff version.', 'error')
        return redirect(url_for('main.index'))
    
    # Default block duration: 3.5 hours
    duration_hours = 3.5
    
    # Calculate summaries for all regions (uses cached data via CacheManager)
    region_summaries, min_date_time_uk, max_date_time_uk = _calculate_region_summaries(product_code, duration_hours)
    
    return render_template('regions.html',
                         region_summaries=region_summaries,
                         product_code=product_code,
                         product_name=selected_product_name,
                         agile_products=agile_products,
                         duration_hours=duration_hours,
                         min_date_time_uk=min_date_time_uk,
                         max_date_time_uk=max_date_time_uk)

@bp.route('/about')
def about():
    """About page explaining how the tool works."""
    # Log configuration mode (development or production)
    config_mode = 'development' if current_app.config.get('DEBUG', False) else 'production'
    logger.info(f"About page accessed - Configuration mode: {config_mode}")
    
    # Check if user came from prices page (via referrer or query param)
    referrer = request.referrer
    came_from_prices = False
    prices_url = None
    
    # Check query parameter first (if explicitly passed)
    if request.args.get('from') == 'prices':
        came_from_prices = True
        # Reconstruct prices URL from query params if available
        region = request.args.get('region')
        product = request.args.get('product')
        duration = request.args.get('duration')
        capacity = request.args.get('capacity')
        if region and product:
            prices_url = url_for('main.prices', region=region, product=product, 
                                duration=duration, capacity=capacity)
        else:
            prices_url = url_for('main.prices')
    # Check referrer header
    elif referrer and '/prices' in referrer:
        came_from_prices = True
        # Extract query params from referrer if available
        parsed = urlparse(referrer)
        params = parse_qs(parsed.query)
        if params.get('region') and params.get('product'):
            prices_url = url_for('main.prices', 
                                region=params['region'][0],
                                product=params['product'][0],
                                duration=params.get('duration', [None])[0],
                                capacity=params.get('capacity', [None])[0])
        else:
            prices_url = url_for('main.prices')
    
    return render_template('about.html', 
                         page_name='about',
                         came_from_prices=came_from_prices,
                         prices_url=prices_url)

@bp.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    response = make_response(render_template('robots.txt'))
    response.mimetype = 'text/plain'
    return response

@bp.route('/sitemap.xml')
def sitemap_xml():
    """Serve sitemap.xml for search engines."""
    response = make_response(render_template('sitemap.xml'))
    response.mimetype = 'application/xml'
    return response

@bp.route('/feature-vote', methods=['POST'])
def feature_vote():
    """Handle feature voting - records a vote for a feature."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        feature_id = data.get('feature')
        
        if not feature_id:
            return jsonify({'error': 'Feature ID required'}), 400
        
        # Validate feature ID exists in config
        valid_feature_ids = [item['id'] for item in Config.FEATURE_VOTING_ITEMS]
        if feature_id not in valid_feature_ids:
            return jsonify({'error': 'Invalid feature ID'}), 400
        
        # Record the vote
        votes = VoteManager.record_vote(feature_id)
        
        # Get updated percentages
        percentages = VoteManager.get_vote_percentages()
        
        logger.info(f"Recorded vote for feature {feature_id}. New count: {votes[feature_id]}")
        
        return jsonify({
            'success': True,
            'feature': feature_id,
            'votes': votes,
            'percentages': percentages
        }), 200
        
    except Exception as e:
        logger.error(f"Error recording feature vote: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/feature-suggestion', methods=['POST'])
def feature_suggestion():
    """Handle feature suggestion submission."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        suggestion_text = data.get('suggestion', '').strip()
        
        if not suggestion_text:
            return jsonify({'error': 'Suggestion text required'}), 400
        
        # Validate length
        if len(suggestion_text) > VoteManager.MAX_SUGGESTION_LENGTH:
            return jsonify({'error': f'Suggestion too long (max {VoteManager.MAX_SUGGESTION_LENGTH} characters)'}), 400
        
        # Save suggestion
        success = VoteManager.save_suggestion(suggestion_text)
        
        if success:
            logger.debug(f"Saved suggestion: {suggestion_text}")
            return jsonify({
                'success': True,
                'message': 'Thanks for the suggestion!'
            }), 200
        else:
            return jsonify({'error': 'Failed to save suggestion'}), 500
        
    except ValueError as e:
        logger.warning(f"Invalid suggestion request: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error saving suggestion: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/feature-votes', methods=['GET'])
def get_feature_votes():
    """Get current vote counts and percentages (for display)."""
    try:
        percentages = VoteManager.get_vote_percentages()
        return jsonify({
            'success': True,
            'percentages': percentages
        }), 200
    except Exception as e:
        logger.error(f"Error getting vote percentages: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/admin/generate-stats', methods=['POST'])
def generate_stats():
    """
    Admin-only route to generate 2025 historical statistics.
    Requires password authentication via query parameter or environment variable.
    
    If region_code is not supplied, generates stats for all regions and then creates national averages.
    """
    from app.stats_calculator import StatsCalculator
    
    # Simple password check (in production, use proper authentication)
    admin_password = request.args.get('password') or request.form.get('password')
    expected_password = current_app.config.get('ADMIN_STATS_PASSWORD') or os.environ.get('ADMIN_STATS_PASSWORD')
    
    if not expected_password:
        logger.warning("Admin stats password not configured")
        return jsonify({'error': 'Admin access not configured'}), 403
    
    if not admin_password or admin_password != expected_password:
        logger.warning("Unauthorized attempt to generate stats")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get parameters
        product_code = request.args.get('product_code') or request.form.get('product_code') or Config.OCTOPUS_PRODUCT_CODE
        region_code = request.args.get('region_code') or request.form.get('region_code')
        year = int(request.args.get('year') or request.form.get('year') or 2025)
        
        if year != 2025:
            return jsonify({'error': 'Only 2025 statistics are supported'}), 400
        
        # If no region_code specified, generate for all regions
        if not region_code:
            logger.info(f"Starting stats generation for ALL regions: {product_code} (year {year})")
            
            region_codes = list(Config.OCTOPUS_REGION_NAMES.keys())
            generated_files = []
            failed_regions = []
            
            # Generate stats for each region
            for region in region_codes:
                try:
                    logger.info(f"Processing region {region} ({Config.OCTOPUS_REGION_NAMES.get(region, 'Unknown')})")
                    stats_data = StatsCalculator.calculate_2025_stats(
                        product_code=product_code,
                        region_code=region
                    )
                    filepath = StatsCalculator.save_stats(stats_data)
                    generated_files.append({
                        'region': region,
                        'filepath': str(filepath)
                    })
                    logger.info(f"Completed region {region}")
                except Exception as e:
                    logger.error(f"Error generating stats for region {region}: {e}", exc_info=True)
                    failed_regions.append(region)
            
            # Calculate national averages from all regional stats
            logger.info("Calculating national averages from regional statistics")
            try:
                national_stats = StatsCalculator.calculate_national_averages(
                    product_code=product_code,
                    year=year
                )
                if national_stats:
                    national_filepath = StatsCalculator.save_national_stats(national_stats, year=year)
                    logger.info(f"National averages saved to {national_filepath}")
                else:
                    logger.warning("Failed to calculate national averages")
            except Exception as e:
                logger.error(f"Error calculating national averages: {e}", exc_info=True)
            
            return jsonify({
                'success': True,
                'message': f'Statistics generated for {len(generated_files)} regions',
                'generated_files': generated_files,
                'failed_regions': failed_regions,
                'national_averages_generated': national_stats is not None if 'national_stats' in locals() else False
            }), 200
        
        else:
            # Single region specified
            logger.info(f"Starting stats generation for {product_code} region {region_code} (year {year})")
            
            # Calculate statistics
            stats_data = StatsCalculator.calculate_2025_stats(
                product_code=product_code,
                region_code=region_code
            )
            
            # Save to file
            filepath = StatsCalculator.save_stats(stats_data)
            
            return jsonify({
                'success': True,
                'message': 'Statistics generated successfully',
                'filepath': str(filepath),
                'stats': stats_data
            }), 200
        
    except Exception as e:
        logger.error(f"Error generating statistics: {e}", exc_info=True)
        return jsonify({'error': f'Error generating statistics: {str(e)}'}), 500
