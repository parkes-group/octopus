# Octopus Energy Agile Pricing Assistant

A Flask web application that helps UK households with solar panels and home batteries identify optimal electricity pricing on Octopus Energy's Agile tariff.

## MVP Features

- **Dynamic Agile product discovery** - Automatically discovers available Agile tariff versions from Octopus API
- **Automatic product selection** - Single Agile product is auto-selected; multiple products show selection dropdown
- **Postcode-based region detection** - Enter your UK postcode to automatically determine your energy pricing region
- **Manual region selection fallback** - Select your region manually if postcode lookup fails or returns multiple regions
- View today's half-hourly Agile Octopus prices for selected product (anonymous usage)
- Find lowest 30-minute price per calendar day - calculates and displays separately for each day when prices span multiple days
- Calculate absolute cheapest continuous charging block (0.5-6 hours, supports decimals e.g., 3.5 hours) per calendar day - each day gets its own cheapest block calculation
- Calculate cheapest remaining (future) continuous charging block per calendar day - excludes that day's cheapest block, calculated independently for each day
- Display daily average price(s) - calculates one average per calendar day (UK local date). If prices span two days, displays two averages with date labels
- Estimate charging costs (uses future block if available, otherwise absolute block)
- Visual price charts with visual distinction between absolute and future cheapest blocks
- **Region Summary Comparison** - Compare prices across all UK regions in one view (mobile cards / desktop table)
- **Feature Interest Voting** - Configuration-driven inline voting component with percentage results and optional feature suggestions
- **2025 Historical Statistics** - Data-driven analysis showing potential savings, price cap comparisons, and negative pricing opportunities
- **Region Usage Analytics** - Anonymous region request tracking for internal analytics (file-based, no personal data)
- File-based JSON caching (pricing data NOT stored in database)
- **Mobile-First Design** - Fully responsive, works on phones, tablets, and desktop
- **Accessibility (WCAG-aligned)** - Semantic HTML, ARIA labels, keyboard navigation, screen reader support
- **SEO & AI Discovery Optimized** - Page-specific structured data (JSON-LD), semantic HTML, canonical tags, and clear content for search engines and AI assistants

## Quick Start

### Prerequisites

- Python 3.9+
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Octopus
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
# Edit .env and set SECRET_KEY
```

5. Run the application:
```bash
flask run
```

6. Open your browser to `http://localhost:5000`

## Configuration

### Required Environment Variables (MVP)

- `SECRET_KEY`: Flask secret key for session security
- `CACHE_EXPIRY_MINUTES`: Cache expiry time in minutes (default: 5, used as fallback)
- `LOG_LEVEL`: Logging level (default: INFO)

### Example .env file

```
SECRET_KEY=your-secret-key-here
CACHE_EXPIRY_MINUTES=5
LOG_LEVEL=INFO
```

### Cache Expiry Logic

The application uses **adaptive cache expiry** that automatically adjusts based on when Octopus publishes the next day's prices:

- **When tomorrow's prices are available**: If either the first or last price entry in the API response is for tomorrow (UK date), the cache expires at **tomorrow 16:00 UK time**. This prevents unnecessary API calls once prices are published.

- **When tomorrow's prices are not yet published**: If both the first and last entries are for today or earlier, the cache uses the **existing expiry logic** (default: 5 minutes from `CACHE_EXPIRY_MINUTES`).

**Why check both first and last entries?**
- Octopus returns price data in **reverse chronological order** (newest first)
- By checking both edges of the price list, we can reliably detect next-day publication regardless of ordering direction
- This ensures the cache adapts correctly during the 16:00–17:00 publication window

**Why this approach?**
- Octopus does not provide a "last updated" timestamp in their API responses
- Prices are typically published around 4:00 PM UK time each day
- This adaptive logic reduces API calls while ensuring fresh data is available as soon as prices are published

**Note:** The `CACHE_EXPIRY_MINUTES` environment variable is used as a fallback when next-day prices are not detected.

## Project Structure

```
octopus_app/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py             # Configuration
│   ├── routes.py             # Main routes
│   ├── api_client.py         # Octopus API client
│   ├── cache_manager.py      # File-based caching
│   ├── price_calculator.py   # Price calculations
│   ├── stats_calculator.py   # Historical statistics calculator
│   ├── stats_loader.py       # Statistics loader for frontend
│   ├── vote_manager.py       # Feature voting and suggestions storage
│   ├── forms.py              # WTForms
│   ├── errors.py             # Error handlers
│   ├── templates/            # Jinja templates
│   ├── static/               # CSS, JS
│   ├── cache/                # JSON cache files
│   ├── votes/                # Feature votes and suggestions (JSON/JSONL)
├── scripts/                  # Statistics generation scripts
│   ├── download_raw_data.py  # Download raw price data for all regions
│   ├── generate_stats.py     # Generate stats for a single region
│   ├── generate_all_stats.py # Generate stats for all regions + national
│   ├── generate_national_stats.py # Generate national averages only
│   └── STATS_EXPLANATION.md  # Complete guide to statistics system
├── data/
│   ├── raw/                  # Raw price data (full year per region)
│   └── stats/                 # Calculated statistics (JSON files)
│       ├── {region}_2025.json  # Historical statistics per region
│       └── region_request_counts.json  # Region usage analytics (auto-generated)
├── tests/                    # Unit tests
├── logs/                     # Application logs
├── requirements.txt          # Dependencies
└── wsgi.py                   # Production entry point
```

## Testing

Run tests with pytest:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app tests/
```

## Deployment

### PythonAnywhere

1. Upload code to `/home/username/mysite/`
2. Create MySQL database (if needed for post-MVP)
3. Configure WSGI file to point to `wsgi.py`
4. Set environment variables in PythonAnywhere dashboard
5. Ensure `app/cache/` and `app/votes/` directories are writable

## MVP Scope

**Included:**
- Anonymous price viewing
- Dynamic Agile product discovery and selection
- Postcode-based region detection (automatic)
- Manual region selection (fallback)
- Price calculations
- File-based caching
- Error handling
- Feature interest voting (configuration-driven, percentage results, optional suggestions)

**Post-MVP (Not Included):**
- User authentication
- Database storage
- User preferences
- Email/SMS notifications
- Inverter integrations
- Subscription billing

## License

[Your License Here]

## Support & Feedback

### Supporting This Project

This site is free to use and is supported through an Octopus Energy referral program. If you're thinking of switching energy suppliers, you can [join Octopus Energy using our referral link](https://share.octopus.energy/clean-prawn-337) to support the hosting costs and ongoing development of this tool. This helps us keep the site free for everyone.

### Feedback & Contributions

We welcome feedback, bug reports, and feature requests!

**Report Issues or Suggest Features:**
- Click the "💬 Feedback & Feature Requests" link in the footer (available on all pages)
- This will take you to GitHub Issues where you can:
  - Report bugs
  - Suggest new features
  - Ask questions

**No account required:** You don't need an account on this website to submit feedback. You'll only need a GitHub account to create an issue (GitHub accounts are free).

The feedback link uses GitHub Issues to maintain a clear, transparent feedback loop and ensure all issues are tracked properly.

## Feature Interest Voting

The site includes a configuration-driven feature voting component that appears on the Prices, Regions, and About pages. This component allows users to express interest in potential future features with a single click and view live voting results as percentages.

### How It Works

- **Configuration-driven**: Voting items are defined in `app/config.py` as `FEATURE_VOTING_ITEMS`
- **Click-only voting**: Users click on a feature card to vote (no forms, no Yes/No buttons)
- **Session-based**: One vote per browser session (enforced via sessionStorage)
- **Live percentage results**: After voting, results are displayed as percentages with progress bars
- **Optional suggestions**: Users can submit free-text feature suggestions (max 200 characters)
- **No personal data**: No cookies, no email capture, no tracking
- **File-based storage**: Votes stored in `app/votes/feature_votes.json`, suggestions in `app/votes/feature_suggestions.jsonl`
- **Privacy-first**: Completely anonymous, no PII collected

### Configuration

Voting items are configured in `app/config.py`:

```python
FEATURE_VOTING_ITEMS = [
    {
        "id": "daily_cheapest_email",
        "title": "Daily cheapest charging email",
        "description": "Get a daily email showing the cheapest time to charge",
        "display_order": 1
    },
    {
        "id": "negative_price_alert",
        "title": "Negative pricing alerts",
        "description": "Get notified when electricity prices go negative",
        "display_order": 2
    }
]
```

The UI automatically adapts when items are added, removed, or reordered in the configuration.

### Technical Details

- **Backend routes**:
  - `POST /feature-vote` - Records a vote and returns updated percentages
  - `POST /feature-suggestion` - Saves a feature suggestion
  - `GET /feature-votes` - Returns current vote percentages
- **Storage**:
  - Votes: JSON file (`app/votes/feature_votes.json`)
  - Suggestions: JSONL file (`app/votes/feature_suggestions.jsonl`) - one JSON object per line
- **Client-side**: JavaScript handles voting UI, sessionStorage enforcement, and percentage display
- **Component**: Reusable Jinja partial (`components/_feature_voting.html`)

### Vote Data Structure

Votes are stored as:
```json
{
  "daily_cheapest_email": 18,
  "negative_price_alert": 11
}
```

Percentages are calculated server-side: `(votes_for_feature / total_votes) * 100`

### Suggestion Data Structure

Suggestions are stored as JSONL (one JSON object per line):
```json
{"timestamp": "2026-01-01T14:22:00Z", "suggestion": "Integration with Tesla Powerwall"}
{"timestamp": "2026-01-01T15:30:00Z", "suggestion": "Mobile app notifications"}
```

## Historical Statistics (2025)

The site includes a historical statistics system that calculates and displays data-driven insights about Agile Octopus pricing for calendar year 2025. These statistics are calculated once and stored in JSON files for efficient frontend display.

### What It Calculates

1. **Cheapest Block vs Daily Average**
   - Average price of cheapest 3.5-hour blocks across 2025
   - Average daily Agile price
   - Potential annual savings (percentage and absolute)

2. **Comparison vs Price Cap**
   - Comparison against Ofgem price cap unit rates
   - Illustrative annual savings assuming all usage in cheapest blocks

3. **Negative Pricing Analysis**
   - Total number of negative price slots in 2025
   - Total hours with negative prices
   - Total amount Octopus could have paid (GBP)
   - Average payment per day

### Configuration

Statistics calculations use configurable assumptions (in `app/config.py`):

- `OFGEM_PRICE_CAP_P_PER_KWH`: Ofgem price cap unit rate (default: 28.6 p/kWh)
- `STATS_DAILY_KWH`: Average daily usage assumption (default: 11.0 kWh)
- `STATS_BATTERY_CHARGE_POWER_KW`: Battery charge rate for negative pricing (default: 3.5 kW)

### Generating Statistics

Statistics can be generated using standalone scripts (recommended) or via an admin-only web route.

#### Recommended: Using Standalone Scripts

The fastest and most reliable way to generate statistics is using the scripts in the `scripts/` directory:

1. **Download raw data** (one-time, ~1-2 hours):
   ```bash
   python scripts/download_raw_data.py
   ```

2. **Generate statistics for all regions** (uses raw data, ~10-15 minutes):
   ```bash
   python scripts/generate_all_stats.py
   ```

For detailed usage instructions, see `scripts/STATS_EXPLANATION.md`.

**Available Scripts:**
- `scripts/download_raw_data.py` - Download full year's price data for all regions
- `scripts/generate_stats.py` - Generate stats for a single region
- `scripts/generate_all_stats.py` - Generate stats for all regions + national averages
- `scripts/generate_national_stats.py` - Generate national averages from existing regional stats

#### Alternative: Admin Web Route

Statistics can also be generated via an admin-only route. You can generate statistics for:
- **All regions at once** (recommended) - generates stats for all 14 regions AND creates national averages
- **Single region** - generates stats for one specific region

**Generate for ALL Regions (Recommended)**:
```bash
POST /admin/generate-stats?password=YOUR_ADMIN_PASSWORD&product_code=AGILE-24-10-01
```
(Note: No `region_code` parameter = process all regions)

**Generate Single Region Statistics**:
```bash
POST /admin/generate-stats?password=YOUR_ADMIN_PASSWORD&product_code=AGILE-24-10-01&region_code=B
```

Set the admin password via environment variable:
```bash
ADMIN_STATS_PASSWORD=your-secure-password
```

**Note**: The admin route is subject to web server timeouts for long-running operations. For bulk operations, use the standalone scripts instead.

**National Averages**: When generating all regions, the system automatically calculates national averages from all regional statistics and saves them to `national_2025.json`, which is displayed on the homepage.

### Storage

Statistics are stored in `data/stats/` as JSON files:
- Format: `{region_code}_{year}.json` for regional stats, `national_{year}.json` for national averages
- Examples:
  - `national_2025.json` - National statistics (used on homepage)
  - `A_2025.json` - Region A statistics (used on prices page when region A is selected)
  - `B_2025.json` - Region B statistics (used on prices page when region B is selected)
  - `C_2025.json` - Region C statistics (used on prices page when region C is selected)
  - `region_request_counts.json` - Region usage analytics (auto-generated when regions are used)

Raw price data (optional, speeds up regeneration) is stored in `data/raw/`:
- Format: `{region_code}_{year}.json`
- Each file contains a full year's worth of half-hourly price data

### Frontend Display

Statistics are displayed on:
- **Homepage**: 4 headline stat cards showing **national statistics** (from `national_2025.json`)
- **Prices page**: 4 headline stat cards showing **regional statistics** for the user's selected region

All statistics use "could have" wording and clearly state assumptions to avoid guarantees or promises.

If statistics for a region are not available, the stats component gracefully doesn't display (no error shown to users).

### Complete Documentation

For complete documentation on the statistics system, including:
- Detailed script usage instructions
- Workflow recommendations
- Troubleshooting guide
- Configuration options

See: `scripts/STATS_EXPLANATION.md`

### Statistics File Format

```json
{
  "year": 2025,
  "region_code": "A",
  "product_code": "AGILE-24-10-01",
  "calculation_date": "2026-01-01T12:00:00+00:00",
  "days_processed": 365,
  "days_failed": 0,
  "cheapest_block": {
    "block_hours": 3.5,
    "avg_price_p_per_kwh": 12.4
  },
  "daily_average": {
    "avg_price_p_per_kwh": 22.1
  },
  "savings_vs_daily_average": {
    "savings_p_per_kwh": 9.7,
    "savings_percentage": 43.9,
    "annual_saving_gbp": 412.00
  },
  "price_cap_comparison": {
    "cap_price_p_per_kwh": 28.6,
    "savings_p_per_kwh": 16.2,
    "annual_saving_gbp": 650.00
  },
  "negative_pricing": {
    "total_negative_slots": 1842,
    "total_negative_hours": 921.0,
    "total_paid_gbp": 312.40,
    "avg_payment_per_day_gbp": 0.856
  },
  "assumptions": {
    "daily_kwh": 11.0,
    "battery_charge_power_kw": 3.5,
    "usage_shifted_to_cheapest_blocks": true,
    "usage_limited_to_negative_slots": true
  }
}
```

### Important Notes

- Statistics are calculated once and stored locally (no recalculation on page load)
- All calculations are transparent and assumptions are clearly stated
- Uses "could have" wording to avoid guarantees
- No database required - file-based storage only
- Statistics generation is admin-only and password-protected
