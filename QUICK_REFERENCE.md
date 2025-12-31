# Quick Reference Guide
## Octopus Energy Agile Pricing Assistant

**Purpose:** Quick reference for AI coding assistant during implementation.

---

## Document Structure

1. **PRD.md** - Product Requirements Document
   - Problem statement, user personas, features, success metrics
   - Use for: Understanding product goals and requirements

2. **TECHNICAL_ARCHITECTURE.md** - System Architecture
   - Flask structure, database schema, API integration, caching
   - Use for: Understanding technical design and code structure

3. **IMPLEMENTATION_PLAN.md** - Step-by-Step Build Guide
   - Detailed tasks, file creation, acceptance criteria
   - Use for: Following implementation order and tasks

4. **QUICK_REFERENCE.md** - This document
   - Key information, common patterns, quick lookups
   - Use for: Quick answers during coding

---

## Key Technical Decisions

### Architecture
- **Pattern:** Flask App Factory
- **ORM:** SQLAlchemy 2.0+
- **Migrations:** Flask-Migrate (Alembic)
- **Forms:** Flask-WTF
- **Caching:** File-based JSON (PythonAnywhere-compatible)
- **Authentication:** Passwordless (magic links) - POST-MVP, not required for MVP

### Database
- **Type:** MySQL (both development and production - environment-based credentials)
- **MVP:** Database optional (only needed if authentication implemented - POST-MVP)
- **Post-MVP Tables:** users, user_preferences, login_tokens
- **Relationships:** User 1:1 Preferences, User 1:Many LoginTokens (Post-MVP)
- **Important:** Pricing data is NOT stored in database - only cached in JSON files

### API Integration
- **Base URL:** `https://api.octopus.energy/v1/`
- **Product:** AGILE-18-02-21
- **Caching:** 5-minute expiry
- **Fallback:** Use stale cache on API failure

### Frontend
- **Framework:** Bootstrap 5 or Tailwind CSS
- **Charts:** Chart.js
- **JavaScript:** Minimal vanilla JS
- **Responsive:** Mobile-first

---

## File Structure Quick Reference

```
octopus_app/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration
│   ├── models.py                 # Database models
│   ├── routes.py                 # Main routes
│   ├── auth.py                   # Authentication routes
│   ├── api_client.py             # Octopus API client
│   ├── cache_manager.py          # Caching logic
│   ├── price_calculator.py       # Price calculations
│   ├── email_service.py          # Email sending
│   ├── forms.py                  # WTForms
│   ├── errors.py                 # Error handlers
│   ├── utils.py                  # Utilities
│   ├── templates/                # Jinja templates
│   ├── static/                   # CSS, JS, images
│   └── cache/                    # JSON cache files
├── migrations/                   # Database migrations
├── tests/                        # Unit tests
├── .env                          # Environment variables
├── requirements.txt              # Dependencies
└── wsgi.py                       # Production entry point
```

---

## Database Models Quick Reference

### User
```python
- id: Integer (PK)
- email: String(120), unique, indexed
- name: String(100)
- created_at: DateTime
- updated_at: DateTime
```

### UserPreferences
```python
- id: Integer (PK)
- user_id: Integer (FK to User, unique)
- region: String(10)
- charging_duration: Float (0.5-6.0, default 4.0)  # Supports decimals (e.g., 3.5 hours)
- battery_capacity: Integer (1-50, default 10)
- notify_negative_pricing: Boolean (default False)
- notify_cheapest_window: Boolean (default False)
- created_at: DateTime
- updated_at: DateTime
```

### LoginToken
```python
- id: Integer (PK)
- token: String(64), unique, indexed
- user_id: Integer (FK to User)
- expires_at: DateTime
- used_at: DateTime (nullable)
- created_at: DateTime
```

---

## API Endpoints Quick Reference

### Octopus Energy API

**Get Regions:**
```
GET https://api.octopus.energy/v1/products/AGILE-18-02-21/region-code/
Response: { "results": [{"region": "A", "name": "Eastern England"}, ...] }
```

**Get Prices:**
```
GET https://api.octopus.energy/v1/products/AGILE-18-02-21/electricity-tariffs/E-1R-AGILE-18-02-21-{REGION}/standard-unit-rates/
Params: period_from, period_to, page_size=48
Response: { "results": [{"value_inc_vat": 16.0, "valid_from": "...", "valid_to": "..."}, ...] }
```

### Application Routes

**Public:**
- `GET /` - Homepage (region selection)
- `GET /prices?region=X&duration=Y&capacity=Z` - Price display
- `GET /auth/login` - Login page
- `POST /auth/login` - Request magic link
- `GET /auth/login?token=XXX` - Verify token, log in
- `GET /auth/logout` - Logout

**Protected (requires login - POST-MVP):**
- `GET /preferences` - View preferences (POST-MVP)
- `POST /preferences` - Update preferences (POST-MVP)

---

## Price Calculation Logic

### Lowest Price
```python
lowest = min(prices, key=lambda x: x['value_inc_vat'])
```

### Cheapest Block (N hours, supports decimals)
```python
# Sliding window: find contiguous block of int(N*2) slots with lowest average
# Example: 3.5 hours = 7 slots (int(3.5 * 2))
# Return: start_time, end_time, average_price, total_cost
```

### Cost Estimation
```python
cost_pence = average_price * battery_capacity_kwh
cost_pounds = cost_pence / 100
```

---

## Caching Strategy

**Important:** Pricing data is cached in JSON files ONLY, NOT in database.

### Cache File Format
```json
{
  "prices": [...],
  "fetched_at": "2024-01-15T10:00:00",
  "expires_at": "2024-01-15T10:05:00"
}
```

### Cache Flow
1. Check cache for region/date
2. If valid → return cached data
3. If invalid/missing → fetch from API
4. Cache new response
5. Return data

### Cache Expiry
- Default: 5 minutes
- Auto-cleanup: Delete files older than 1 day

---

## Authentication Flow (POST-MVP)

**Note:** Authentication is NOT part of MVP. MVP supports anonymous usage only.

1. User enters email → `POST /auth/login`
2. System finds/creates user
3. Generate token (32 bytes, URL-safe)
4. Store token (expires 15 minutes)
5. Send email with magic link
6. User clicks link → `GET /auth/login?token=XXX`
7. Verify token (not used, not expired)
8. Set session (`session['user_id'] = user_id`)
9. Mark token as used
10. Redirect to preferences/homepage

---

## Environment Variables

```bash
# MVP Required
SECRET_KEY=your-secret-key
DATABASE_URL=mysql://user:pass@host/db  # Only if authentication implemented (POST-MVP)
CACHE_EXPIRY_MINUTES=5
LOG_LEVEL=INFO

# Post-MVP (Authentication)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
ADMIN_EMAIL=admin@example.com
```

---

## Common Code Patterns

### Flask Route Pattern
```python
@bp.route('/path')
def route_name():
    try:
        # Logic here
        return render_template('template.html', data=data)
    except Exception as e:
        logger.error(f"Error: {e}")
        flash('Error message', 'error')
        return redirect(url_for('main.index'))
```

### Database Query Pattern
```python
# Get user
user = User.query.filter_by(email=email).first()

# Create user
user = User(email=email)
db.session.add(user)
db.session.commit()

# Get with relationship
user = User.query.get(user_id)
prefs = user.preferences
```

### Cache Pattern
```python
# Get from cache
cached = CacheManager.get_cached_prices(region, date_str)
if cached:
    return cached

# Fetch and cache
data = OctopusAPIClient.get_prices(region)
CacheManager.cache_prices(region, date_str, data)
return data
```

### Authentication Check
```python
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

---

## Error Handling Patterns

### API Error
```python
try:
    data = OctopusAPIClient.get_prices(region)
except Exception as e:
    logger.error(f"API error: {e}")
    # Try cache fallback
    cached = CacheManager.get_cached_prices(region, date_str)
    if cached:
        data = cached
    else:
        flash('Unable to fetch prices. Please try again later.', 'error')
        return redirect(url_for('main.index'))
```

### Validation Error
```python
if not region or region not in valid_regions:
    flash('Please select a valid region.', 'error')
    return redirect(url_for('main.index'))
```

### Database Error
```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    logger.error(f"Database error: {e}")
    flash('An error occurred. Please try again.', 'error')
```

---

## Testing Patterns

### Unit Test
```python
def test_find_lowest_price():
    prices = [
        {'value_inc_vat': 20.0, 'valid_from': '...', 'valid_to': '...'},
        {'value_inc_vat': 15.0, 'valid_from': '...', 'valid_to': '...'},
    ]
    result = PriceCalculator.find_lowest_price(prices)
    assert result['price'] == 15.0
```

### Route Test
```python
def test_prices_route(client):
    response = client.get('/prices?region=A&duration=4')
    assert response.status_code == 200
    assert b'Price' in response.data
```

---

## Security Checklist

- [ ] CSRF protection on all forms
- [ ] SQL injection prevention (SQLAlchemy)
- [ ] XSS prevention (Jinja2 auto-escaping)
- [ ] Secure session cookies
- [ ] Strong SECRET_KEY
- [ ] Token expiry (15 minutes)
- [ ] Single-use tokens
- [ ] Input validation
- [ ] Error messages don't leak sensitive data
- [ ] Logs don't contain sensitive data

---

## Performance Checklist

- [ ] Database indexes on frequently queried columns
- [ ] API responses cached
- [ ] Cache expiry configured
- [ ] No N+1 database queries
- [ ] Static files optimized
- [ ] Chart.js loaded from CDN
- [ ] Images optimized

---

## Deployment Checklist

- [ ] Environment variables set
- [ ] Database created and migrated
- [ ] Static files configured
- [ ] WSGI file configured
- [ ] Email service configured
- [ ] Logging configured
- [ ] Error monitoring set up
- [ ] Cache directory writable
- [ ] Scheduled tasks configured (cache cleanup)

---

## Common Issues & Solutions

### Issue: API rate limiting
**Solution:** Aggressive caching, increase cache expiry

### Issue: Cache files not persisting
**Solution:** Check directory permissions, ensure cache directory exists

### Issue: Email not sending
**Solution:** Check SMTP credentials, test with simple script

### Issue: Database connection errors
**Solution:** Check DATABASE_URL, verify MySQL is running

### Issue: Session not persisting
**Solution:** Check SECRET_KEY, verify session configuration

### Issue: CSRF token errors
**Solution:** Ensure Flask-WTF configured, tokens in all forms

---

## Key Dependencies

```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.5
Flask-WTF==1.2.1
WTForms==3.1.0
python-dotenv==1.0.0
requests==2.31.0
email-validator==2.1.0
```

---

## Next Steps After MVP

1. **Notifications:** Email/SMS alerts for negative pricing
2. **Automation:** Background jobs for price polling
3. **Premium Features:** Historical analysis, API access
4. **Integrations:** Inverter APIs, smart home platforms
5. **Billing:** Subscription management, payment processing

---

**Use this document as a quick lookup during implementation. Refer to detailed documents (PRD, TECHNICAL_ARCHITECTURE, IMPLEMENTATION_PLAN) for comprehensive information.**
