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
- File-based JSON caching (pricing data NOT stored in database)
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
│   ├── forms.py              # WTForms
│   ├── errors.py             # Error handlers
│   ├── templates/            # Jinja templates
│   ├── static/               # CSS, JS
│   └── cache/                # JSON cache files
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
5. Ensure `app/cache/` directory is writable

## MVP Scope

**Included:**
- Anonymous price viewing
- Dynamic Agile product discovery and selection
- Postcode-based region detection (automatic)
- Manual region selection (fallback)
- Price calculations
- File-based caching
- Error handling

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

We welcome feedback, bug reports, and feature requests!

**Report Issues or Suggest Features:**
- Click the "💬 Feedback & Feature Requests" link in the footer (available on all pages)
- This will take you to GitHub Issues where you can:
  - Report bugs
  - Suggest new features
  - Ask questions

**No account required:** You don't need an account on this website to submit feedback. You'll only need a GitHub account to create an issue (GitHub accounts are free).

The feedback link uses GitHub Issues to maintain a clear, transparent feedback loop and ensure all issues are tracked properly.
