# Octopus Energy Agile Pricing Assistant

A Flask web application that helps UK households with solar panels and home batteries identify optimal electricity pricing on Octopus Energy's Agile tariff.

## MVP Features

- **Dynamic Agile product discovery** - Automatically discovers available Agile tariff versions from Octopus API
- **Automatic product selection** - Single Agile product is auto-selected; multiple products show selection dropdown
- **Postcode-based region detection** - Enter your UK postcode to automatically determine your energy pricing region
- **Manual region selection fallback** - Select your region manually if postcode lookup fails or returns multiple regions
- View today's half-hourly Agile Octopus prices for selected product (anonymous usage)
- Find lowest 30-minute price
- Calculate absolute cheapest continuous charging block (0.5-6 hours, supports decimals e.g., 3.5 hours) across all prices for the day
- Calculate cheapest remaining (future) continuous charging block (only considers time slots after current time)
- Display daily average price (average of all half-hour slots for the day)
- Estimate charging costs (uses future block if available, otherwise absolute block)
- Visual price charts with visual distinction between absolute and future cheapest blocks
- **Region Summary Comparison** - Compare prices across all UK regions in one view (mobile cards / desktop table)
- **Feature Interest Voting** - Configuration-driven inline voting component with percentage results and optional feature suggestions
- File-based JSON caching (pricing data NOT stored in database)
- **Mobile-First Design** - Fully responsive, works on phones, tablets, and desktop
- **Accessibility (WCAG-aligned)** - Semantic HTML, ARIA labels, keyboard navigation, screen reader support
- **SEO & AI Discovery Optimized** - Structured data, semantic HTML, and clear content for search engines and AI assistants

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
- `CACHE_EXPIRY_MINUTES`: Cache expiry time in minutes (default: 5)
- `LOG_LEVEL`: Logging level (default: INFO)

### Example .env file

```
SECRET_KEY=your-secret-key-here
CACHE_EXPIRY_MINUTES=5
LOG_LEVEL=INFO
```

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
│   ├── vote_manager.py       # Feature voting and suggestions storage
│   ├── forms.py              # WTForms
│   ├── errors.py             # Error handlers
│   ├── templates/            # Jinja templates
│   ├── static/               # CSS, JS
│   ├── cache/                # JSON cache files
│   └── votes/                # Feature votes and suggestions (JSON/JSONL)
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
