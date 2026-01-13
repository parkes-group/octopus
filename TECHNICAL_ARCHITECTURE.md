# Technical Architecture & Implementation Plan
## Octopus Energy Agile Pricing Assistant

**Version:** 1.0  
**Target:** Production-ready Flask application  
**Hosting:** PythonAnywhere

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────┐
│   Browser   │
│  (User)     │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────────────────────────┐
│         Flask Application           │
│  ┌───────────────────────────────┐  │
│  │      Routes & Controllers     │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │    Business Logic Layer       │  │
│  │  - Price Calculations         │  │
│  │  - Cache Management            │  │
│  │  - Authentication (Post-MVP)   │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │      Data Access Layer        │  │
│  │  - SQLAlchemy Models           │  │
│  │  - API Clients                 │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────┬───────────┘
       │                  │
       ▼                  ▼
┌─────────────┐    ┌──────────────┐
│   MySQL     │    │ Octopus API  │
│  Database   │    │   (External) │
│ (Post-MVP)  │    └──────────────┘
└─────────────┘           │
                          ▼
                   ┌─────────────┐
                   │ File Cache  │
                   │  (JSON)     │
                   │ (Pricing)   │
                   └─────────────┘
```

### 1.2 Technology Stack

**Backend:**
- Python 3.9+
- Flask 2.3+
- SQLAlchemy 2.0+
- Flask-WTF (CSRF protection)
- python-dotenv (environment variables)
- Requests (HTTP client)

**Frontend:**
- Jinja2 templates
- Chart.js (for price visualisation)
- Vanilla JavaScript (minimal, for interactivity)
- Bootstrap 5 or Tailwind CSS (responsive framework)

**Database:**
- MySQL 8.0+
- SQLAlchemy ORM

**Infrastructure:**
- PythonAnywhere (hosting)
- File-based caching (JSON)
- SMTP (email sending)

---

## 2. Flask Application Structure

### 2.1 Directory Structure

```
octopus_app/
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── config.py                   # Configuration classes
│   ├── models.py                   # SQLAlchemy models
│   ├── routes.py                   # Main routes
│   ├── auth.py                     # Authentication routes
│   ├── api_client.py               # Octopus API client
│   ├── cache_manager.py            # Caching logic
│   ├── price_calculator.py         # Price calculation logic
│   ├── email_service.py            # Email sending
│   ├── utils.py                    # Utility functions
│   ├── forms.py                    # WTForms forms
│   ├── errors.py                   # Error handlers
│   │
│   ├── templates/
│   │   ├── base.html               # Base template
│   │   ├── index.html              # Homepage
│   │   ├── prices.html             # Price display & calculations
│   │   ├── login.html              # Login/register
│   │   ├── preferences.html        # User preferences
│   │   ├── error.html              # Error pages
│   │   └── components/
│   │       ├── _header.html
│   │       ├── _footer.html
│   │       └── _price_chart.html
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── main.js
│   │   │   └── chart.js            # Chart.js integration
│   │   └── images/
│   │
│   └── cache/                      # File cache directory
│       └── .gitkeep
│
├── migrations/                     # Alembic migrations
├── tests/                          # Unit tests
│   ├── test_api_client.py
│   ├── test_price_calculator.py
│   └── test_routes.py
│
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Example env file
├── .gitignore
├── requirements.txt
├── wsgi.py                         # WSGI entry point (PythonAnywhere)
└── README.md
```

### 2.2 Flask App Factory Pattern

**app/__init__.py:**
```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    from app.routes import bp as main_bp
    from app.errors import bp as errors_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(errors_bp)
    
    # Post-MVP: Authentication blueprint
    # from app.auth import bp as auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/auth')
    
    return app
```

---

## 3. Database Schema Design

### 3.1 Entity Relationship Diagram

```
┌─────────────┐
│    User     │
├─────────────┤
│ id (PK)     │
│ email (UK)  │
│ name        │
│ created_at  │
│ updated_at  │
└──────┬──────┘
       │ 1
       │
       │ 1
       ▼
┌─────────────┐
│ Preferences │
├─────────────┤
│ id (PK)     │
│ user_id (FK)│
│ region      │
│ duration    │
│ created_at  │
│ updated_at  │
└─────────────┘

┌─────────────┐
│ LoginToken  │
├─────────────┤
│ id (PK)     │
│ token (UK)  │
│ user_id (FK)│
│ expires_at  │
│ used_at     │
│ created_at  │
└─────────────┘
```

### 3.2 SQLAlchemy Models

**app/models.py:**
```python
from datetime import datetime, timedelta
from app import db
from werkzeug.security import generate_password_hash
import secrets

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    preferences = db.relationship('UserPreferences', backref='user', uselist=False, cascade='all, delete-orphan')
    login_tokens = db.relationship('LoginToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserPreferences(db.Model):
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    region = db.Column(db.String(10))  # Octopus region code
    charging_duration = db.Column(db.Float, default=4.0)  # Hours (0.5-6.0, supports decimals e.g., 3.5)
    notify_negative_pricing = db.Column(db.Boolean, default=False)
    notify_cheapest_window = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserPreferences {self.user_id}>'

class LoginToken(db.Model):
    __tablename__ = 'login_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_valid(self):
        return not self.used_at and datetime.utcnow() < self.expires_at
    
    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)
    
    def __repr__(self):
        return f'<LoginToken {self.token[:8]}...>'
```

### 3.3 Database Migrations

Use Flask-Migrate (Alembic) for schema versioning:
- Initial migration: Create tables
- Future migrations: Add columns, indexes, etc.

---

## 4. API Integration Flow

### 4.1 Octopus Energy API Endpoints

**Base URL:** `https://api.octopus.energy/v1/`

**Key Endpoints:**
1. **Products Discovery:** `GET /products/` (with pagination support)
2. **Grid Supply Point Lookup (Postcode → Region):** `GET /industry/grid-supply-points/?postcode={POSTCODE}`
3. **Get Regions (Manual Fallback):** `GET /industry/grid-supply-points/?group_by=region`
4. **Get Prices:** `GET /products/{PRODUCT_CODE}/electricity-tariffs/E-1R-{PRODUCT_CODE}-{REGION}/standard-unit-rates/`

**Product Discovery Flow:**
1. On page load (index and prices pages), system calls Products API
2. System fetches all products (handling pagination)
3. System filters products where code contains "AGILE" (case-insensitive)
4. System filters by direction (IMPORT, EXPORT, or BOTH - configurable)
5. System filters for active products (available_to is null or in future)
6. If exactly one Agile product found: auto-select and use for price fetching
7. If multiple Agile products found: display dropdown for user selection
8. Selected product code is passed via form/query string and used for all price lookups

**Region Detection Flow:**
1. User enters UK postcode on homepage
2. System normalizes postcode (remove spaces, uppercase)
3. System calls Grid Supply Point API with postcode
4. API returns GSP data with `group_id` (e.g., `_A`, `_N`)
5. System extracts region code(s) by stripping leading underscore
6. If single region found: redirect to prices page with region and product
7. If multiple regions found: show filtered region dropdown
8. If lookup fails (zero results): show manual region dropdown with all regions
9. Region code is used for all subsequent price lookups

**API Client Design:**

**app/api_client.py:**
```python
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OctopusAPIClient:
    BASE_URL = "https://api.octopus.energy/v1"
    PRODUCT_CODE = "AGILE-18-02-21"
    
    @staticmethod
    def lookup_region_from_postcode(postcode):
        """Look up region code from UK postcode using Grid Supply Point API."""
        normalized = postcode.replace(' ', '').upper().strip()
        url = f"{OctopusAPIClient.BASE_URL}/industry/grid-supply-points/?postcode={normalized}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = data.get('results', [])
            if not results:
                return None
            # Extract region from group_id (e.g., '_A' -> 'A')
            group_id = results[0].get('group_id', '')
            return group_id.lstrip('_') if group_id else None
        except Exception as e:
            logger.error(f"Error looking up postcode {postcode}: {e}")
            raise
    
    @staticmethod
    def get_regions():
        """Fetch available regions from Octopus API (for manual selection)."""
        url = f"{OctopusAPIClient.BASE_URL}/industry/grid-supply-points/?group_by=region"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching regions: {e}")
            raise
    
    @staticmethod
    def get_prices(product_code, region_code):
        """Fetch half-hourly prices for a region and product."""
        url = f"{OctopusAPIClient.BASE_URL}/products/{product_code}/electricity-tariffs/E-1R-{product_code}-{region_code}/standard-unit-rates/"
        params = {
            'period_from': datetime.now().strftime('%Y-%m-%dT00:00:00Z'),
            'period_to': datetime.now().strftime('%Y-%m-%dT23:59:59Z'),
            'page_size': 48
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching prices for {region_code}: {e}")
            raise
```

### 4.2 API Response Structure

**Grid Supply Point (Postcode) Response:**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "group_id": "_N",
      "gsp": "N",
      ...
    }
  ]
}
```

**Regions Response:**
```json
{
  "count": 14,
  "next": null,
  "previous": null,
  "results": [
    {"region": "A", "name": "Eastern England"},
    {"region": "B", "name": "East Midlands"},
    ...
  ]
}
```

**Prices Response:**
```json
{
  "count": 48,
  "next": null,
  "previous": null,
  "results": [
    {
      "value_exc_vat": 15.234,
      "value_inc_vat": 16.0,
      "valid_from": "2024-01-15T00:00:00Z",
      "valid_to": "2024-01-15T00:30:00Z"
    },
    ...
  ]
}
```

### 4.3 Error Handling

- Network timeouts: 10-second timeout
- HTTP errors: Log and return None
- Invalid responses: Validate JSON structure
- Rate limiting: Implement request throttling (future)

---

## 5. Caching Strategy

### 5.1 Cache Architecture

**File-based JSON caching (MVP):**
- Store API responses as JSON files ONLY
- **Important:** Pricing data is NOT cached in database - only in JSON files
- **One persistent file per region:** Filename format: `{product_code}_{region_code}.json` (no date in filename)
- Files are updated in place when cache expires (not deleted and recreated)
- Include metadata: `fetched_at`, `expires_at`
- Cache directory: `app/cache/` (PythonAnywhere-compatible)
- **Rationale:** Prevents file accumulation, simpler logic, predictable state (exactly 14 files for 14 regions)
- **Adaptive Cache Expiry:** Cache expiry adapts to when Octopus publishes prices (see 5.3 Cache Expiry Logic below)

**app/cache_manager.py:**
```python
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
    """
    CACHE_DIR = Path('app/cache')
    
    @staticmethod
    def _get_cache_expiry_minutes():
        """Get cache expiry minutes from config, with fallback."""
        try:
            if current_app:
                return current_app.config.get('CACHE_EXPIRY_MINUTES', 5)
        except RuntimeError:
            pass
        from app.config import Config
        return Config.CACHE_EXPIRY_MINUTES
    
    @staticmethod
    def _get_cache_file(product_code, region_code):
        """Get cache file path for product and region."""
        CacheManager.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_product = product_code.replace('/', '_').replace('\\', '_')
        return CacheManager.CACHE_DIR / f"{safe_product}_{region_code}.json"
    
    @staticmethod
    def get_cached_prices(product_code, region_code):
        """Retrieve cached prices if valid."""
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
            except:
                pass
            return None
    
    @staticmethod
    def determine_cache_expiry_from_edge_prices(first_entry, last_entry):
        """
        Determine cache expiry based on first and last price entries.
        
        Checks both entries because Octopus returns prices in reverse chronological order.
        If either entry is for tomorrow (UK date): returns tomorrow at 16:00 UK time
        Otherwise: returns None (use existing expiry logic)
        """
        # Converts both entries' valid_to to UK timezone
        # Compares dates to today's UK date
        # Returns datetime or None
        ...
    
    @staticmethod
    def cache_prices(product_code, region_code, prices, expiry_minutes=None, expires_at=None):
        """
        Cache prices with expiry. Updates existing cache file in place.
        
        Args:
            expiry_minutes: Optional minutes-based expiry (fallback)
            expires_at: Optional datetime-based expiry (takes precedence)
        """
        cache_file = CacheManager._get_cache_file(product_code, region_code)
        
        # expires_at takes precedence, then expiry_minutes, then config default
        if expires_at is not None:
            expiry_datetime = expires_at
        elif expiry_minutes is not None:
            expiry_datetime = datetime.now() + timedelta(minutes=expiry_minutes)
        else:
            expiry_minutes = CacheManager._get_cache_expiry_minutes()
            expiry_datetime = datetime.now() + timedelta(minutes=expiry_minutes)
        
        data = {
            'prices': prices,
            'fetched_at': datetime.now().isoformat(),
            'expires_at': expiry_datetime.isoformat()
        }
        
        # Use atomic write (temp file then rename) for PythonAnywhere safety
        temp_file = cache_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, cache_file)
            logger.info(f"Cache refresh: Updated cache file for {product_code} {region_code}")
        except Exception as e:
            logger.error(f"Error writing cache file {cache_file}: {e}")
    
    @staticmethod
    def clear_legacy_cache():
        """Clean up legacy per-day cache files (old format with date in filename)."""
        # Removes files matching pattern: {product_code}_{region_code}_{date}.json
        # New format: {product_code}_{region_code}.json
        ...
```

### 5.2 Cache Usage Flow

1. Check cache for product/region (one persistent file per region)
2. If valid cache exists, return cached data (cache hit)
3. If no cache file exists or cache expired, fetch from API (cache miss/refresh)
4. Overwrite existing cache file with new data (in-place update)
5. Return data to user

**Key Behaviors:**
- **Cache Hit:** Valid, non-expired cache file exists → return immediately
- **Cache Miss:** No cache file exists → fetch from API, create cache file
- **Cache Refresh:** Cache file exists but expired → fetch from API, overwrite existing file
- **File Persistence:** Cache files remain until manually cleaned up or corrupted (then recreated)

### 5.3 Cache Expiry Logic

The cache system uses **adaptive expiry** that automatically adjusts based on when Octopus publishes the next day's prices.

**Problem:** Octopus does not provide a "last updated" timestamp in their API responses, so we cannot directly determine when prices were last refreshed. Additionally, Octopus returns price data in **reverse chronological order** (newest first).

**Solution:** Inspect both the first and last price entries in the API response to infer freshness:

1. **Extract edge entries:** Read the first and last entries from the price list (regardless of ordering direction)
2. **Convert to UK timezone:** Convert both `valid_to` timestamps to UK local time (Europe/London)
3. **Compare dates:** Compare the dates of both entries to today's UK date
4. **Set expiry:**
   - **If either entry is for tomorrow:** Octopus has published tomorrow's prices → cache expires at **tomorrow 16:00 UK time**
   - **If both entries are for today or earlier:** Tomorrow's prices not yet published → use **existing expiry logic** (default: 5 minutes from `CACHE_EXPIRY_MINUTES`)

**Why check both first and last entries?**
- Octopus returns prices in reverse chronological order (newest first)
- By checking both edges, we reliably detect next-day publication regardless of ordering
- This ensures correct behavior during the 16:00–17:00 publication window

**Implementation:**
- `CacheManager.determine_cache_expiry_from_edge_prices(first_entry, last_entry)` - Helper function that implements the logic
- Called automatically when prices are fetched from the API in `routes.py`
- Returns `datetime` if tomorrow's prices detected, `None` to use existing logic
- All date comparisons use UK timezone (handles BST/GMT transitions correctly)

**Benefits:**
- Reduces API calls once prices are published (long-lived cache until next day)
- Preserves existing expiry logic as fallback (no regressions)
- Handles reverse chronological ordering correctly
- No hard-coded dates or times
- Adapts automatically to Octopus publication schedule

**Logging:**
- Logs the dates of first and last price entries (UK time)
- Logs whether tomorrow's prices were detected
- Logs which expiry strategy was used (adaptive vs. existing logic)
- Logs the final expiry timestamp

**Example log entries:**
```
Next-day publication detected (first entry: 2026-01-14, last entry: 2026-01-13) → expiry set to 2026-01-14 16:00 UK
Next-day prices not detected (first entry: 2026-01-13, last entry: 2026-01-13) → using existing expiry logic
```

---

### 5.3 Region Request Tracking

**Purpose:** Track region usage for internal analytics (file-based, no database).

**File Location:** `data/stats/region_request_counts.json`

**File Format:**
```json
{
  "A": {
    "count": 132,
    "last_requested": "2026-01-12T14:21:03Z"
  },
  "B": {
    "count": 98,
    "last_requested": "2026-01-12T13:02:11Z"
  }
}
```

**When Region Requests Are Recorded:**
- Postcode resolves to a single region (auto-selected) → tracked immediately before redirect
- Postcode resolves to multiple regions, user selects one from dropdown → tracked when form submitted
- User manually selects a region without postcode → tracked when form submitted
- User changes region on prices page → tracked only if region differs from last tracked region (session-based)

**Not Recorded:**
- Invalid postcodes (zero API results)
- Postcode lookups that return zero regions
- Page loads where no region is chosen
- Failed price fetches (region not used for display)
- Page refreshes on prices page (same region already tracked)
- Changing duration, capacity, or other settings on prices page (region unchanged)
- Navigating away and returning to prices page with same region (session preserves tracking state)

**Implementation Details:**
- Uses session variable `last_tracked_region` to prevent duplicate tracking
- Tracking happens once per region selection, not per page view
- Session-based deduplication ensures accurate counts without over-counting

**Implementation:**

**app/region_request_tracker.py:**
```python
class RegionRequestTracker:
    STATS_DIR = Path('data/stats')
    COUNTS_FILE = STATS_DIR / 'region_request_counts.json'
    
    @staticmethod
    def record_region_request(region_code):
        """
        Record a region request by incrementing count and updating timestamp.
        Uses atomic file writes for concurrency safety.
        Never raises exceptions to ensure it doesn't block price rendering.
        """
        # Load existing counts
        # Increment count for region
        # Update last_requested timestamp (UTC, ISO-8601)
        # Save atomically (temp file + replace)
```

**Usage in Routes:**
```python
# In /prices route, after successful price retrieval
RegionRequestTracker.record_region_request(region)
```

**Key Behaviors:**
- **Atomic Writes:** Uses temporary file + `os.replace()` for safe concurrent access
- **Non-Blocking:** Errors are logged but never raise exceptions (stats never break price rendering)
- **Validation:** Only valid region codes (single uppercase letter) are accepted
- **Auto-Initialization:** Creates file and directory structure automatically if missing
- **Corruption Recovery:** Handles corrupted JSON files gracefully by resetting to empty structure

---

## 6. Price Calculation Logic

### 6.1 Price Calculator

**app/price_calculator.py:**

All price calculations are performed **per calendar day** (UK local date). When prices span multiple days (up to 2 days), calculations are performed independently for each day.

**Key Methods:**

```python
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PriceCalculator:
    @staticmethod
    def group_prices_by_date(prices):
        """Group prices by UK calendar date."""
        # Groups prices by date derived from valid_from timestamp (UK local time)
        # Returns dict mapping date objects to lists of prices
    
    @staticmethod
    def calculate_cheapest_per_day(prices, duration_hours, current_time_utc=None):
        """
        Calculate cheapest slot and blocks per calendar day.
        
        Groups prices by UK calendar date and calculates:
        - Lowest 30-minute price per day
        - Cheapest block per day
        - Cheapest remaining block per day (excludes that day's cheapest block)
        
        Returns list of day results, each containing:
        - date, date_display, date_iso
        - lowest_price (30-min slot for that day)
        - cheapest_block (cheapest block for that day)
        - cheapest_remaining_block (cheapest remaining block for that day)
        """
    
    @staticmethod
    def find_lowest_price(prices):
        """Find the lowest single 30-minute price from a list of prices."""
        if not prices:
            return None
        
        lowest = min(prices, key=lambda x: x['value_inc_vat'])
        return {
            'price': lowest['value_inc_vat'],
            'time_from': lowest['valid_from'],
            'time_to': lowest['valid_to']
        }
    
    @staticmethod
    def find_cheapest_block(prices, duration_hours):
        """Find cheapest contiguous block of N hours (supports decimals, e.g., 3.5 hours)."""
        if not prices or duration_hours < 0.5:
            return None
        
        slots_needed = int(duration_hours * 2)  # Convert hours to half-hour slots (e.g., 3.5 hours = 7 slots)
        
        if len(prices) < slots_needed:
            return None
        
        cheapest_block = None
        cheapest_avg = float('inf')
        
        # Sliding window approach
        for i in range(len(prices) - slots_needed + 1):
            block = prices[i:i + slots_needed]
            total_price = sum(slot['value_inc_vat'] for slot in block)
            avg_price = total_price / slots_needed
            
            if avg_price < cheapest_avg:
                cheapest_avg = avg_price
                cheapest_block = {
                    'start_time': block[0]['valid_from'],
                    'end_time': block[-1]['valid_to'],
                    'average_price': avg_price,
                    'total_cost': total_price,
                    'slots': block
                }
        
        return cheapest_block
```

**Per-Day Calculation Strategy:**

1. **Date Grouping**: Prices are grouped by UK calendar date using `group_prices_by_date()`
2. **Independent Calculations**: For each day:
   - `find_lowest_price()` is called on that day's prices
   - `find_cheapest_block()` is called on that day's prices
   - `find_cheapest_block()` is called on remaining prices (future slots, excluding cheapest block slots)
3. **Display**: Results are displayed with date labels when multiple days are present
4. **Backward Compatibility**: Single-day data displays without date labels (unchanged behavior)
    
    @staticmethod
    def calculate_charging_cost(average_price, battery_capacity_kwh):
        """Calculate estimated cost to charge battery."""
        if not average_price or not battery_capacity_kwh:
            return None
        
        # Price is in pence per kWh
        cost_pence = average_price * battery_capacity_kwh
        cost_pounds = cost_pence / 100
        
        return round(cost_pounds, 2)
    
    @staticmethod
    def format_price_data(prices):
        """Format prices for chart display."""
        chart_data = {
            'labels': [],
            'prices': [],
            'times': []
        }
        
        for price in prices:
            # Parse datetime
            dt = datetime.fromisoformat(price['valid_from'].replace('Z', '+00:00'))
            chart_data['labels'].append(dt.strftime('%H:%M'))
            chart_data['prices'].append(price['value_inc_vat'])
            chart_data['times'].append(price['valid_from'])
        
        return chart_data
```

---

## 7. Authentication Flow (Post-MVP)

**Note:** Authentication is designed for future extensibility but is NOT part of MVP. MVP should support anonymous usage only. This section documents the architecture for post-MVP implementation.

### 7.1 Passwordless Authentication (Post-MVP)

**Flow:**
1. User enters email on login page
2. System checks if user exists (create if not)
3. Generate secure token (32 bytes, URL-safe)
4. Store token in database (expires in 15 minutes)
5. Send email with magic link: `https://example.com/auth/login?token={token}`
6. User clicks link
7. System validates token (not used, not expired)
8. Log user in (set session)
9. Mark token as used
10. Redirect to preferences or homepage

**app/auth.py:**
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import User, LoginToken, UserPreferences
from app import db
from app.email_service import send_login_email
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'error')
            return render_template('login.html')
        
        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email)
            db.session.add(user)
            db.session.commit()
            
            # Create default preferences
            prefs = UserPreferences(user_id=user.id)
            db.session.add(prefs)
            db.session.commit()
        
        # Generate login token
        token = LoginToken.generate_token()
        login_token = LoginToken(
            token=token,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(login_token)
        db.session.commit()
        
        # Send email
        try:
            send_login_email(user.email, token)
            flash('Check your email for a login link!', 'success')
        except Exception as e:
            logger.error(f"Error sending login email: {e}")
            flash('Error sending email. Please try again.', 'error')
        
        return render_template('login.html')
    
    # GET request - check for token in query string
    token = request.args.get('token')
    if token:
        return verify_token(token)
    
    return render_template('login.html')

def verify_token(token):
    """Verify login token and authenticate user."""
    login_token = LoginToken.query.filter_by(token=token).first()
    
    if not login_token or not login_token.is_valid():
        flash('Invalid or expired login link.', 'error')
        return redirect(url_for('auth.login'))
    
    # Mark token as used
    login_token.used_at = datetime.utcnow()
    db.session.commit()
    
    # Set session
    session['user_id'] = login_token.user_id
    session.permanent = True
    
    flash('Successfully logged in!', 'success')
    return redirect(url_for('main.preferences'))
```

### 7.2 Session Management

- Use Flask sessions (server-side, signed cookies)
- Session timeout: 30 days (permanent sessions)
- Logout: Clear session

---

## 8. Routes & Controllers

### 8.1 Main Routes

**app/routes.py:**
```python
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.price_calculator import PriceCalculator
from app.models import User, UserPreferences
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Homepage - region selection."""
    try:
        regions = OctopusAPIClient.get_regions()
        return render_template('index.html', regions=regions.get('results', []))
    except Exception as e:
        logger.error(f"Error loading regions: {e}")
        return render_template('index.html', regions=[], error="Unable to load regions. Please try again later.")

@bp.route('/prices')
def prices():
    """Display prices and calculations."""
    region = request.args.get('region')
    duration = request.args.get('duration', type=float, default=4.0)
    capacity = request.args.get('capacity', type=float)
    
    if not region:
        return redirect(url_for('main.index'))
    
    # Validate duration (supports decimals, e.g., 3.5 hours)
    if duration < 0.5 or duration > 6.0:
        duration = 4.0
    
    # Get prices (with caching - one persistent file per region)
    prices_data = CacheManager.get_cached_prices(product_code, region_code)
    
    if not prices_data:
        try:
            api_response = OctopusAPIClient.get_prices(product_code, region_code)
            prices_data = api_response.get('results', [])
            CacheManager.cache_prices(product_code, region_code, prices_data)
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            flash('Unable to fetch current prices. Please try again later.', 'error')
            return redirect(url_for('main.index'))
    
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
    
    # Format for chart
    chart_data = PriceCalculator.format_price_data(prices_data)
    
    # Post-MVP: Get user preferences if logged in
    # user_prefs = None
    # if 'user_id' in session:
    #     user = User.query.get(session['user_id'])
    #     if user and user.preferences:
    #         user_prefs = user.preferences
    
    return render_template('prices.html',
                         region=region,
                         duration=duration,
                         capacity=capacity,
                         prices=prices_data,
                         lowest_price=lowest_price,
                         cheapest_block=cheapest_block,
                         estimated_cost=estimated_cost,
                         chart_data=chart_data)
                         # user_prefs=user_prefs  # Post-MVP
```

### 8.2 Error Handlers

**app/errors.py:**
```python
from flask import Blueprint, render_template
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, message="Page not found"), 404

@bp.app_errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    # Send email alert to admin (future)
    return render_template('error.html', error_code=500, message="An error occurred"), 500
```

---

## 9. Frontend Implementation

### 9.1 Base Template

**app/templates/base.html:**
- Bootstrap 5 or Tailwind CSS
- Responsive navigation
- Flash message display
- Footer with disclaimers
- Mobile-first design

### 9.2 Key Pages

**index.html:**
- Region selection dropdown
- Form to start price viewing
- Clear call-to-action

**prices.html:**
- Price chart (Chart.js)
- Lowest price display
- Duration selector (0.5-6 hours, supports decimals)
- Battery capacity input
- Results display (cheapest block, estimated cost)
- Update button to recalculate

**login.html (Post-MVP):**
- Email input form
- Instructions for passwordless login
- Success/error messages

**preferences.html (Post-MVP):**
- Region preference
- Default charging duration
- Save button
- Note: Notification preferences are post-MVP (Phase 2)

### 9.3 Chart.js Integration

**app/static/js/chart.js:**
```javascript
function renderPriceChart(chartData) {
    const ctx = document.getElementById('priceChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Price (p/kWh)',
                data: chartData.prices,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Price (p/kWh)'
                    }
                }
            }
        }
    });
}
```

---

## 10. Configuration Management

### 10.1 Config Classes

**app/config.py:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')  # MySQL required (no default)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Cache settings (MVP Required)
    CACHE_EXPIRY_MINUTES = int(os.environ.get('CACHE_EXPIRY_MINUTES', 5))
    
    # Logging (MVP Required)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Email configuration (Post-MVP - only needed for authentication)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Admin email for error alerts (Post-MVP)
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Use PythonAnywhere MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
```

### 10.2 Environment Variables

**.env.example:**

**MVP Required:**
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql://username:password@host/database
CACHE_EXPIRY_MINUTES=5
LOG_LEVEL=INFO
```

**Post-MVP (Authentication):**
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
ADMIN_EMAIL=admin@example.com
```

---

## 11. Logging & Observability

### 11.1 Logging Configuration

**app/__init__.py (logging setup):**
```python
import logging
from logging.handlers import SMTPHandler
from flask import Flask

def setup_logging(app):
    if not app.debug and not app.testing:
        # File logging
        file_handler = logging.FileHandler('app.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Email logging for critical errors
        if app.config.get('ADMIN_EMAIL'):
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr=app.config['MAIL_DEFAULT_SENDER'],
                toaddrs=[app.config['ADMIN_EMAIL']],
                subject='Octopus App Error',
                credentials=(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD']),
                secure=() if app.config['MAIL_USE_TLS'] else None
            )
            mail_handler.setLevel(logging.ERROR)
            mail_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            app.logger.addHandler(mail_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Octopus App startup')
```

### 11.2 Structured Logging

- Use consistent log format
- Include request context (user_id, region, etc.)
- Log all API calls (with sanitised data)
- Log all errors with stack traces
- Log performance metrics (response times)

---

## 12. Security Considerations

### 12.1 Security Measures

1. **CSRF Protection:**
   - Flask-WTF for all forms
   - CSRF tokens in forms

2. **SQL Injection Prevention:**
   - SQLAlchemy parameterised queries only
   - No raw SQL queries

3. **XSS Prevention:**
   - Jinja2 auto-escaping enabled
   - Sanitise user inputs

4. **Session Security:**
   - Secure, HTTP-only cookies
   - Strong SECRET_KEY
   - Session timeout

5. **Token Security:**
   - Cryptographically random tokens
   - Short expiry (15 minutes)
   - Single-use tokens

6. **Rate Limiting:**
   - Implement on authentication endpoints (future)
   - Prevent brute force attacks

7. **Input Validation:**
   - Validate all user inputs
   - Sanitise email addresses
   - Validate region codes
   - Validate numeric inputs (duration, capacity)

---

## 13. Testing Strategy

### 13.1 Test Structure

**tests/test_api_client.py:**
- Mock Octopus API responses
- Test error handling
- Test timeout scenarios

**tests/test_price_calculator.py:**
- Test lowest price calculation
- Test cheapest block calculation
- Test edge cases (empty data, insufficient slots)
- Test cost calculation

**tests/test_routes.py:**
- Test homepage
- Test price display
- Test calculations
- Test error handling

**tests/test_auth.py (Post-MVP):**
- Test token generation
- Test token validation
- Test login flow
- Test session management

### 13.2 Test Data

- Create fixtures for API responses
- Mock external API calls
- Use test database
- Clean up after tests

---

## 14. Deployment to PythonAnywhere

### 14.1 PythonAnywhere Setup

1. **Create Web App:**
   - Choose Flask
   - Python 3.9+

2. **Database Setup:**
   - Create MySQL database
   - Update DATABASE_URL in .env

3. **File Structure:**
   - Upload code to `/home/username/mysite/`
   - Ensure cache directory is writable

4. **WSGI Configuration:**
   - Point to `wsgi.py`
   - Set environment variables

5. **Static Files:**
   - Configure static files mapping
   - Configure media files (if needed)

### 14.2 wsgi.py

```python
import sys
import os

path = '/home/username/mysite'
if path not in sys.path:
    sys.path.insert(0, path)

from app import create_app
application = create_app('production')
```

### 14.3 Scheduled Tasks

- Set up daily cache cleanup (Bash script)
- Future: Scheduled price polling for notifications

---

## 15. Extensibility Considerations

### 15.1 Future Features Architecture

**Notifications Module:**
- Separate `notifications.py` module
- Background task queue (Celery or similar)
- Email/SMS service abstraction

**Subscription Module:**
- Separate `billing.py` module
- Stripe integration
- Subscription tiers management

**Inverter Integration:**
- Separate `integrations/` package
- Abstract base class for inverters
- Implementations for different brands

**API Endpoints:**
- RESTful API blueprint
- API authentication (API keys)
- Rate limiting
- API documentation (Swagger/OpenAPI)

### 15.2 Code Organization

- Keep business logic separate from routes
- Use service layer pattern
- Dependency injection for testability
- Plugin architecture for integrations

---

## 16. Performance Optimisation

### 16.1 Caching

- Aggressive API response caching
- Cache region list (changes infrequently)
- Cache invalidation strategy

### 16.2 Database Optimisation

- Add indexes on frequently queried columns
- Use database connection pooling
- Optimise queries (avoid N+1 problems)

### 16.3 Frontend Optimisation

- Minify CSS/JS (production)
- Lazy load charts
- Optimise images
- Use CDN for static assets (future)

---

## 17. Monitoring & Maintenance

### 17.1 Health Checks

- Health check endpoint: `/health`
- Database connectivity check
- API connectivity check
- Cache status

### 17.2 Error Monitoring

- Email alerts for critical errors
- Log aggregation (future: Sentry, Loggly)
- Performance monitoring (future: New Relic, DataDog)

### 17.3 Maintenance Tasks

- Daily cache cleanup
- Token cleanup (delete expired tokens)
- Database backups
- Log rotation

---

**Document Status:** Ready for Implementation
