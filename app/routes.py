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
from app.region_slugs import region_code_from_slug, region_slug_from_code, region_name_from_code
from urllib.parse import urlparse, parse_qs
from datetime import timezone
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

DEFAULT_DURATION_HOURS = 3.5
DEFAULT_CAPACITY_KWH = 10.0

PRODUCTION_SITE_URL = (Config.SITE_URL or "https://www.agilepricing.co.uk").rstrip("/")


def _production_url(path: str) -> str:
    """Build an absolute production URL (SEO canonical)."""
    if not path.startswith("/"):
        path = "/" + path
    return f"{PRODUCTION_SITE_URL}{path}"


def _og_image_url_for_region(region_slug: str) -> str:
    """
    Social preview image.
    - Prefer `/static/images/og-{region-slug}.png` if present
    - Fallback to `/static/images/og-default.png`
    """
    if region_slug:
        images_dir = Path(__file__).resolve().parent / "static" / "images"
        candidate = images_dir / f"og-{region_slug}.png"
        if candidate.exists():
            return _production_url(f"/static/images/og-{region_slug}.png")

    return _production_url("/static/images/og-default.png")


def _build_region_prices_seo(*, region_name: str, region_slug: str, uk_date_iso: str, daily_avg: float | None, cheapest_block_avg: float | None) -> dict:
    """
    Centralized SEO + structured-data builder for `/prices/<region_slug>` pages.

    Notes:
    - Canonical URLs always use the production domain (per SEO requirements).
    - Description is region-specific and includes daily metrics when available.
    """
    canonical_url = _production_url(url_for("main.prices_region", region_slug=region_slug))

    seo_title = f"Octopus Agile Electricity Prices – {region_name} | Cheapest Times Today"

    parts: list[str] = [
        f"Today’s Octopus Agile electricity prices for {region_name}.",
        "See the cheapest times to use electricity and compare half-hourly rates across the day.",
    ]
    if cheapest_block_avg is not None and daily_avg is not None:
        parts.append(
            f"Based on {uk_date_iso} pricing, the average cheapest 3.5h block is {cheapest_block_avg:.2f}p/kWh versus a daily average of {daily_avg:.2f}p/kWh."
        )
    elif daily_avg is not None:
        parts.append(f"Based on {uk_date_iso} pricing, the daily average is {daily_avg:.2f}p/kWh.")

    seo_description = " ".join(parts)

    dataset_name = f"Octopus Agile Half-Hourly Electricity Prices – {region_name}"
    dataset_description = (
        f"Half-hourly Octopus Agile unit rates for {region_name} on {uk_date_iso}. "
        "Use this dataset to find the cheapest times today."
    )

    return {
        "seo_title": seo_title,
        "seo_description": seo_description,
        "canonical_url": canonical_url,
        "seo_site_url": PRODUCTION_SITE_URL,
        "seo_dataset_name": dataset_name,
        "seo_dataset_description": dataset_description,
        "og_image_url": _og_image_url_for_region(region_slug),
        "twitter_image_url": _og_image_url_for_region(region_slug),
        "date_modified": uk_date_iso,
    }

def _select_latest_agile_product_code(agile_products):
    """
    Pick a default Agile product when multiple exist.
    Uses lexicographic max on product codes like 'AGILE-24-10-01'.
    """
    if not agile_products:
        return None
    codes = [p.get('code') for p in agile_products if p.get('code')]
    if not codes:
        return None
    return sorted(codes)[-1]

def _regions_list_with_slugs():
    regions = Config.get_regions_list()
    for r in regions:
        r['slug'] = region_slug_from_code(r.get('region'))
    return regions

def _prices_page_context(*, region_code, region_slug, product_code, duration, capacity, include_structured_data):
    """
    Shared prices page implementation used by:
    - /prices/<region_slug> (canonical, no redirect)
    - /prices?region=X (back-compat, canonical points to slug route)
    """
    # Discover Agile products for dropdown
    agile_products = []
    selected_product_name = None
    try:
        agile_products = OctopusAPIClient.get_agile_products()
    except Exception as e:
        logger.error(f"Error loading Agile products for prices page: {e}")

    raw_product_code = product_code
    raw_duration = duration
    raw_capacity = capacity

    # Default product: "latest" Agile product (derived dynamically)
    if not product_code:
        product_code = _select_latest_agile_product_code(agile_products)

    # Default duration/capacity (implied by the URL; keep query string clean when defaults)
    if duration is None:
        duration = DEFAULT_DURATION_HOURS
    if capacity is None:
        capacity = DEFAULT_CAPACITY_KWH

    if product_code and agile_products:
        matching = [p for p in agile_products if p.get('code') == product_code]
        if matching:
            selected_product_name = matching[0].get('full_name')
        else:
            flash('Invalid tariff version selected.', 'error')
            return None, redirect(url_for('main.index'))

    if not product_code:
        flash('Please select a tariff version.', 'error')
        return None, redirect(url_for('main.index'))

    if not region_code:
        flash('Please select a region.', 'error')
        return None, redirect(url_for('main.index'))

    # Validate duration (supports decimals, e.g., 3.5 hours)
    if duration < 0.5 or duration > 6.0:
        duration = 4.0

    # Get regions list for dropdown (static mapping)
    regions_list = _regions_list_with_slugs()

    # Cache-first pricing fetch
    prices_data = CacheManager.get_cached_prices(product_code, region_code)
    if not prices_data:
        logger.debug(f"Cache miss or expired for {product_code} {region_code}, fetching from API")
        try:
            api_response = OctopusAPIClient.get_prices(product_code, region_code)
            prices_data = api_response.get('results', [])

            expires_at = None
            if prices_data:
                first_entry = prices_data[0]
                last_entry = prices_data[-1]
                expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)

            if expires_at is not None:
                CacheManager.cache_prices(product_code, region_code, prices_data, expires_at=expires_at)
            else:
                CacheManager.cache_prices(product_code, region_code, prices_data)
        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            flash('Unable to fetch current prices. Please try again later.', 'error')
            return None, redirect(url_for('main.index'))

    # Track region usage (deduped by session)
    last_tracked_region = session.get('last_tracked_region')
    if region_code != last_tracked_region:
        RegionRequestTracker.record_region_request(region_code)
        session['last_tracked_region'] = region_code

    # Sort chronologically
    try:
        prices_data = sorted(prices_data, key=lambda x: x.get('valid_from', ''))
    except Exception as e:
        logger.warning(f"Error sorting prices: {e}")

    uk_now = get_uk_now()
    current_time_utc = uk_now.astimezone(timezone.utc)

    # Drop past UK-local days if cache spans yesterday+today after midnight
    try:
        prices_data = PriceCalculator.filter_prices_from_uk_date(prices_data, uk_now.date())
    except Exception as e:
        logger.warning(f"Error filtering prices to UK today+future: {e}")

    daily_averages_by_date = PriceCalculator.calculate_daily_averages_by_date(prices_data)
    cheapest_per_day = PriceCalculator.calculate_cheapest_per_day(prices_data, duration, current_time_utc)

    lowest_price = None
    absolute_cheapest_block = None
    future_cheapest_block = None
    worst_block = None
    if len(cheapest_per_day) == 1:
        day_data = cheapest_per_day[0]
        lowest_price = day_data['lowest_price']
        absolute_cheapest_block = day_data['cheapest_block']
        future_cheapest_block = day_data['cheapest_remaining_block']
        worst_block = day_data['worst_block']

    daily_average_price = daily_averages_by_date[0]['average_price'] if daily_averages_by_date else None
    daily_averages_map = {d['date']: d['average_price'] for d in daily_averages_by_date}

    estimated_cost = None
    cost_block = future_cheapest_block if future_cheapest_block else absolute_cheapest_block
    if capacity and cost_block:
        estimated_cost = PriceCalculator.calculate_charging_cost(cost_block['average_price'], capacity)

    chart_data = PriceCalculator.format_price_data(prices_data)

    # Per-day highlight dictionaries
    absolute_cheapest_block_times_by_date = {}
    future_cheapest_block_times_by_date = {}
    lowest_price_times_by_date = {}
    worst_block_times_by_date = {}
    show_cheapest_remaining_by_date = {}

    for day_data in cheapest_per_day:
        date_iso = day_data['date_iso']

        if day_data['cheapest_block'] and day_data['cheapest_block'].get('slots'):
            absolute_cheapest_block_times_by_date[date_iso] = [
                slot['valid_from'] for slot in day_data['cheapest_block']['slots']
            ]

        show_cheapest_remaining = False
        if day_data['cheapest_block'] and day_data['cheapest_block'].get('start_time_uk'):
            if day_data['cheapest_block']['start_time_uk'] <= uk_now:
                show_cheapest_remaining = True
        show_cheapest_remaining_by_date[date_iso] = show_cheapest_remaining

        if (
            show_cheapest_remaining
            and day_data['cheapest_remaining_block']
            and day_data['cheapest_remaining_block'].get('slots')
        ):
            future_cheapest_block_times_by_date[date_iso] = [
                slot['valid_from'] for slot in day_data['cheapest_remaining_block']['slots']
            ]

        if day_data['lowest_price']:
            lowest_price_times_by_date[date_iso] = day_data['lowest_price']['time_from']

        if day_data['worst_block'] and day_data['worst_block'].get('slots'):
            worst_block_times_by_date[date_iso] = [
                slot['valid_from'] for slot in day_data['worst_block']['slots']
            ]

    # Index maps (multi-day)
    lowest_price_indices_by_date = {}
    worst_block_indices_by_date = {}
    for day_data in cheapest_per_day:
        date_iso = day_data['date_iso']
        if day_data['lowest_price']:
            for idx, price in enumerate(prices_data):
                if price.get('valid_from') == day_data['lowest_price'].get('time_from'):
                    lowest_price_indices_by_date[date_iso] = idx
                    break
        if day_data['worst_block'] and day_data['worst_block'].get('slots'):
            worst_block_indices_by_date[date_iso] = []
            worst_slots = {slot['valid_from'] for slot in day_data['worst_block']['slots']}
            for idx, price in enumerate(prices_data):
                if price.get('valid_from') in worst_slots:
                    worst_block_indices_by_date[date_iso].append(idx)

    # Convert prices to UK-local display fields
    from app.timezone_utils import utc_to_uk, format_uk_time, format_uk_date
    prices_with_uk_times = []
    for price in prices_data:
        price_uk = price.copy()
        dt_uk = utc_to_uk(price['valid_from'])
        price_uk['time_uk'] = format_uk_time(dt_uk)
        price_uk['date_uk'] = format_uk_date(dt_uk)
        price_uk['date_iso'] = dt_uk.date().strftime('%Y-%m-%d')
        price_uk['datetime_uk'] = dt_uk
        prices_with_uk_times.append(price_uk)

    session['last_prices_state'] = {
        'region': region_code,
        'product': product_code,
        'duration': duration,
        'capacity': capacity,
        'product_is_default': raw_product_code in (None, ''),
        'duration_is_default': raw_duration is None,
        'capacity_is_default': raw_capacity is None,
    }

    from app.stats_loader import StatsLoader
    stats_2025 = StatsLoader.get_stats_for_display(region_code=region_code, year=2025)
    stats_2026 = StatsLoader.get_stats_for_display(region_code=region_code, year=2026)

    region_name = region_name_from_code(region_code) or f"Region {region_code}"

    # SEO / social / JSON-LD
    daily_avg_for_seo = daily_average_price
    cheapest_block_avg_for_seo = absolute_cheapest_block["average_price"] if absolute_cheapest_block else None
    uk_date_iso = uk_now.date().isoformat()

    seo = _build_region_prices_seo(
        region_name=region_name,
        region_slug=region_slug,
        uk_date_iso=uk_date_iso,
        daily_avg=daily_avg_for_seo,
        cheapest_block_avg=cheapest_block_avg_for_seo,
    ) if include_structured_data else {
        # Back-compat pages should still point canonical to production region URL.
        "seo_title": None,
        "seo_description": None,
        "canonical_url": _production_url(url_for("main.prices_region", region_slug=region_slug)),
        "seo_site_url": PRODUCTION_SITE_URL,
        "seo_dataset_name": None,
        "seo_dataset_description": None,
        "og_image_url": None,
        "twitter_image_url": None,
        "date_modified": uk_date_iso,
    }

    return {
        'region': region_code,
        'region_slug': region_slug,
        'region_name': region_name,
        'canonical_url': seo.get("canonical_url"),
        'seo_title': seo.get("seo_title"),
        'seo_description': seo.get("seo_description"),
        'og_image_url': seo.get("og_image_url"),
        'twitter_image_url': seo.get("twitter_image_url"),
        'seo_date_modified': seo.get("date_modified"),
        'seo_site_url': seo.get("seo_site_url"),
        'seo_dataset_name': seo.get("seo_dataset_name"),
        'seo_dataset_description': seo.get("seo_dataset_description"),
        'include_structured_data': include_structured_data,
        'product_code': product_code,
        'product_name': selected_product_name,
        'regions': regions_list,
        'agile_products': agile_products,
        'duration': duration,
        'capacity': capacity,
        'prices': prices_with_uk_times,
        'lowest_price': lowest_price,
        'absolute_cheapest_block': absolute_cheapest_block,
        'future_cheapest_block': future_cheapest_block,
        'daily_average_price': daily_average_price,
        'daily_averages_by_date': daily_averages_by_date,
        'cheapest_per_day': cheapest_per_day,
        'absolute_cheapest_block_times_by_date': absolute_cheapest_block_times_by_date,
        'future_cheapest_block_times_by_date': future_cheapest_block_times_by_date,
        'show_cheapest_remaining_by_date': show_cheapest_remaining_by_date,
        'lowest_price_times_by_date': lowest_price_times_by_date,
        'lowest_price_indices_by_date': lowest_price_indices_by_date,
        'worst_block_times_by_date': worst_block_times_by_date,
        'worst_block_indices_by_date': worst_block_indices_by_date,
        'daily_averages_map': daily_averages_map,
        'estimated_cost': estimated_cost,
        'chart_data': chart_data,
        'stats_2025': stats_2025,
        'stats_2026': stats_2026,
        'current_time_uk': uk_now,
        'page_name': 'prices',
    }, None

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
                slug = region_slug_from_code(submitted_region)
                if not slug:
                    logger.warning(f"Region slug resolution failed for code: {submitted_region}")
                    return redirect(url_for('main.prices', region=submitted_region, product=selected_product_code))
                latest_code = _select_latest_agile_product_code(agile_products)
                if latest_code and selected_product_code == latest_code:
                    return redirect(url_for('main.prices_region', region_slug=slug))
                return redirect(url_for('main.prices_region', region_slug=slug, product=selected_product_code))
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
                    slug = region_slug_from_code(region_result)
                    if not slug:
                        logger.warning(f"Region slug resolution failed for code: {region_result}")
                        return redirect(url_for('main.prices', region=region_result, product=selected_product_code))
                    latest_code = _select_latest_agile_product_code(agile_products)
                    if latest_code and selected_product_code == latest_code:
                        return redirect(url_for('main.prices_region', region_slug=slug))
                    return redirect(url_for('main.prices_region', region_slug=slug, product=selected_product_code))
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
    
    # Load statistics for display (national averages)
    from app.stats_loader import StatsLoader
    stats_2025 = StatsLoader.get_stats_for_display(region_code='national', year=2025)
    stats_2026 = StatsLoader.get_stats_for_display(region_code='national', year=2026)
    
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
                         stats_2026=stats_2026,
                         page_name='index')

@bp.route('/prices')
def prices():
    """Display prices and calculations."""
    region = request.args.get('region')
    product_code = request.args.get('product')
    duration = request.args.get('duration', type=float)
    capacity = request.args.get('capacity', type=float)

    # Backward compatibility: region code via query string.
    region_slug = region_slug_from_code(region) if region else None
    if not region_slug:
        flash('Please select a region.', 'error')
        return redirect(url_for('main.index'))

    context, response = _prices_page_context(
        region_code=region,
        region_slug=region_slug,
        product_code=product_code,
        duration=duration,
        capacity=capacity,
        include_structured_data=False,  # Structured data only on canonical region pages
    )
    if response is not None:
        return response
    return render_template('prices.html', **context)

@bp.route('/prices/<region_slug>')
def prices_region(region_slug):
    """Canonical, region-first prices page (SEO-friendly, crawlable)."""
    region_code = region_code_from_slug(region_slug)
    if not region_code:
        logger.info(f"Region resolution failed for slug: {region_slug}")
        from flask import abort
        abort(404)

    product_code = request.args.get('product')
    duration = request.args.get('duration', type=float)
    capacity = request.args.get('capacity', type=float)

    context, response = _prices_page_context(
        region_code=region_code,
        region_slug=region_slug,
        product_code=product_code,
        duration=duration,
        capacity=capacity,
        include_structured_data=True,
    )
    if response is not None:
        return response
    return render_template('prices.html', **context)

@bp.route('/prices/go')
def prices_go():
    """Region selector helper: navigates to /prices/<region_slug> preserving selections."""
    target_slug = request.args.get('region_slug')
    if not target_slug or not region_code_from_slug(target_slug):
        logger.info(f"Region resolution failed for slug in /prices/go: {target_slug}")
        flash('Invalid region selected.', 'error')
        return redirect(url_for('main.index'))

    product = request.args.get('product')
    duration = request.args.get('duration', type=float)
    capacity = request.args.get('capacity', type=float)

    default_product = None
    try:
        default_product = _select_latest_agile_product_code(OctopusAPIClient.get_agile_products())
    except Exception:
        default_product = None

    params = {}
    if product and (default_product is None or product != default_product):
        params['product'] = product
    if duration is not None and abs(duration - DEFAULT_DURATION_HOURS) > 1e-9:
        params['duration'] = duration
    if capacity is not None and abs(capacity - DEFAULT_CAPACITY_KWH) > 1e-9:
        params['capacity'] = capacity

    return redirect(url_for('main.prices_region', region_slug=target_slug, **params))

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
                    
                    # Determine cache expiry based on edge prices (handles reverse chronological order)
                    expires_at = None
                    if prices_data and len(prices_data) > 0:
                        first_entry = prices_data[0]
                        last_entry = prices_data[-1]
                        expires_at = CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)
                    
                    # Cache with adaptive expiry (or fallback to existing logic if expires_at is None)
                    if expires_at is not None:
                        CacheManager.cache_prices(product_code, region_code, prices_data, expires_at=expires_at)
                        logger.debug(f"Fetched and cached prices for region {region_code} with adaptive expiry")
                    else:
                        CacheManager.cache_prices(product_code, region_code, prices_data)
                        logger.debug(f"Fetched and cached prices for region {region_code} with existing expiry logic")
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
                'region_slug': region_slug_from_code(region_code),
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
    default_product_code = None
    try:
        agile_products = OctopusAPIClient.get_agile_products()
        default_product_code = _select_latest_agile_product_code(agile_products)
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
                         default_product_code=default_product_code,
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
        region_slug = request.args.get('region_slug')
        product = request.args.get('product')
        duration = request.args.get('duration')
        capacity = request.args.get('capacity')
        if product and (region_slug or region):
            if not region_slug and region:
                region_slug = region_slug_from_code(region)
            if region_slug:
                prices_url = url_for('main.prices_region', region_slug=region_slug,
                                     product=product, duration=duration, capacity=capacity)
            else:
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
        # Prefer canonical /prices/<slug> referrers
        path_parts = (parsed.path or '').strip('/').split('/')
        if len(path_parts) == 2 and path_parts[0] == 'prices':
            slug = path_parts[1]
            if region_code_from_slug(slug):
                prices_url = url_for(
                    'main.prices_region',
                    region_slug=slug,
                    product=params.get('product', [None])[0],
                    duration=params.get('duration', [None])[0],
                    capacity=params.get('capacity', [None])[0],
                )
        elif params.get('region') and params.get('product'):
            slug = region_slug_from_code(params['region'][0])
            if slug:
                prices_url = url_for(
                    'main.prices_region',
                    region_slug=slug,
                    product=params['product'][0],
                    duration=params.get('duration', [None])[0],
                    capacity=params.get('capacity', [None])[0],
                )
            else:
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
    response = make_response(render_template(
        'sitemap.xml',
        regions=_regions_list_with_slugs(),
        lastmod=get_uk_now().date().isoformat()
    ))
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
