# Step-by-Step Implementation Plan
## Octopus Energy Agile Pricing Assistant

**Purpose:** Detailed, actionable guide for AI coding assistant to build production-ready Flask application.

**Prerequisites:**
- Python 3.9+ installed
- MySQL database access (local for dev, PythonAnywhere for production)
- Git repository initialized
- Virtual environment capability

---

## Phase 1: Project Setup & Foundation

### Step 1.1: Initialize Project Structure

**Tasks:**
1. Create project directory structure (as defined in TECHNICAL_ARCHITECTURE.md)
2. Initialize Git repository (if not already done)
3. Create `.gitignore` file
4. Create `requirements.txt` with initial dependencies
5. Create `README.md` with setup instructions

**Files to Create:**
```
.gitignore
requirements.txt
README.md
```

**Dependencies for requirements.txt:**
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.5
Flask-WTF==1.2.1
Flask-Mail
WTForms==3.1.0
python-dotenv==1.0.0
requests==2.31.0
email-validator==2.1.0
```

**Acceptance Criteria:**
- ✅ Directory structure matches architecture document
- ✅ `.gitignore` excludes `.env`, `__pycache__`, `*.pyc`, `app/cache/*.json`
- ✅ `requirements.txt` includes all necessary packages
- ✅ Project can be cloned and dependencies installed

---

### Step 1.2: Create Configuration System

**Tasks:**
1. Create `app/config.py` with Config classes
2. Create `.env.example` file
3. Create `.env` file (gitignored) for local development
4. Set up environment variable loading

**Files to Create/Edit:**
- `app/config.py`
- `.env.example`
- `.env` (local, gitignored)

**Key Configuration Values:**
- SECRET_KEY (generate secure random key)
- DATABASE_URL (MySQL for both development and production - environment-based credentials)
- Email settings (SMTP)
- Cache settings
- Logging settings

**Acceptance Criteria:**
- ✅ Config classes defined (Development, Production)
- ✅ Environment variables loaded correctly
- ✅ `.env.example` documents all required variables
- ✅ Config can be imported and used

---

### Step 1.3: Initialize Flask Application

**Tasks:**
1. Create `app/__init__.py` with Flask app factory
2. Initialize SQLAlchemy and Flask-Migrate
3. Set up logging configuration
4. Register blueprints (create placeholder blueprints)
5. Create `wsgi.py` for production deployment

**Files to Create/Edit:**
- `app/__init__.py`
- `wsgi.py`

**Acceptance Criteria:**
- ✅ Flask app factory pattern implemented
- ✅ Database initialized
- ✅ Logging configured
- ✅ App can be run with `flask run`
- ✅ No import errors

---

### Step 1.4: Set Up Database Models (POST-MVP)

**IMPORTANT:** Database models are NOT required for MVP. MVP supports anonymous usage only. This step should be skipped during MVP implementation. The models are documented here for future extensibility.

**Tasks (Post-MVP):**
1. Create `app/models.py`
2. Define User model
3. Define UserPreferences model
4. Define LoginToken model
5. Set up relationships between models
6. Create initial database migration

**Files to Create/Edit:**
- `app/models.py`

**Database Migration:**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

**Acceptance Criteria (Post-MVP):**
- ✅ All three models defined correctly
- ✅ Relationships configured
- ✅ Migration created successfully
- ✅ Database tables created
- ✅ Models can be imported without errors

**MVP Note:** Skip this step entirely. MVP does not require database or models.

---

## Phase 2: Core API Integration

### Step 2.1: Create Octopus API Client

**Tasks:**
1. Create `app/api_client.py`
2. Implement `get_regions()` method
3. Implement `get_prices(region_code)` method
4. Add error handling and logging
5. Add request timeout configuration
6. Test API calls manually

**Files to Create/Edit:**
- `app/api_client.py`

**Testing:**
- Test region fetching
- Test price fetching for different regions
- Test error handling (invalid region, network error)

**Acceptance Criteria:**
- ✅ Can fetch regions from Octopus API
- ✅ Can fetch prices for valid region codes
- ✅ Error handling works correctly
- ✅ Logging captures API errors
- ✅ Timeout configured (10 seconds)

---

### Step 2.2: Implement Caching System

**Tasks:**
1. Create `app/cache_manager.py`
2. Implement `get_cached_prices()` method
3. Implement `cache_prices()` method
4. Implement cache expiry logic
5. Implement `clear_old_cache()` method
6. Create `app/cache/` directory
7. Add cache directory to `.gitignore`

**Files to Create/Edit:**
- `app/cache_manager.py`
- `app/cache/.gitkeep`

**Acceptance Criteria:**
- ✅ Cache files stored as JSON
- ✅ Cache expiry works (5 minutes default)
- ✅ Old cache files can be cleaned up
- ✅ Cache directory created automatically
- ✅ Cache files include metadata (fetched_at, expires_at)

---

### Step 2.3: Integrate API Client with Caching

**Tasks:**
1. Update API client to use cache manager
2. Implement cache-first strategy:
   - Check cache first
   - If cache valid, return cached data
   - If cache invalid/missing, fetch from API
   - Cache new data
   - Return data
3. Add fallback to cache on API failure
4. Test caching behavior

**Files to Edit:**
- `app/api_client.py` (or create service layer)

**Acceptance Criteria:**
- ✅ Cache checked before API call
- ✅ Valid cache returned immediately
- ✅ Expired cache triggers API call
- ✅ API failure falls back to stale cache (if available)
- ✅ New API responses cached correctly

---

## Phase 3: Business Logic

### Step 3.1: Implement Price Calculator

**Tasks:**
1. Create `app/price_calculator.py`
2. Implement `find_lowest_price()` method
3. Implement `find_cheapest_block()` method
4. Implement `calculate_charging_cost()` method
5. Implement `format_price_data()` for charts
6. Add input validation
7. Handle edge cases (empty data, insufficient slots)

**Files to Create/Edit:**
- `app/price_calculator.py`

**Edge Cases to Handle:**
- Empty price list
- Duration longer than available slots
- Invalid duration (< 0.5 or > 6 hours, must support decimals)
- Invalid battery capacity

**Acceptance Criteria:**
- ✅ Lowest price calculation correct
- ✅ Cheapest block calculation correct (sliding window)
- ✅ Cost calculation accurate (pence to pounds conversion)
- ✅ Chart data formatted correctly
- ✅ Edge cases handled gracefully

---

### Step 3.2: Create Forms with WTForms

**Tasks:**
1. Create `app/forms.py`
2. Create RegionSelectionForm
3. Create PriceCalculationForm (duration as FloatField supporting 0.5-6.0 hours, capacity)
4. Add validation rules (duration: 0.5-6.0, supports decimals)
5. Add CSRF protection

**Files to Create/Edit:**
- `app/forms.py`

**Forms Needed (MVP):**
- RegionSelectionForm
- PriceCalculationForm

**Forms Needed (Post-MVP):**
- LoginForm (email)
- PreferencesForm (duration as FloatField supporting 0.5-6.0 hours)

**Acceptance Criteria:**
- ✅ All forms defined with proper validation
- ✅ CSRF tokens included
- ✅ Validation messages user-friendly
- ✅ Forms can be rendered in templates

---

## Phase 4: Authentication System (POST-MVP)

**IMPORTANT:** Authentication is NOT part of MVP. This phase should be skipped during MVP implementation. The architecture is documented here for future extensibility.

### Step 4.1: Implement Email Service (Post-MVP)

**Tasks:**
1. Create `app/email_service.py`
2. Configure Flask-Mail or use SMTP directly
3. Implement `send_login_email()` function
4. Create email templates (plain text and HTML)
5. Test email sending locally
6. Add error handling and logging

**Files to Create/Edit:**
- `app/email_service.py`
- `app/templates/emails/login_email.html` (optional)

**Email Content:**
- Subject: "Your login link for Octopus Pricing Assistant"
- Body: Magic link with token
- Expiry notice (15 minutes)
- Security notice

**Acceptance Criteria:**
- ✅ Emails can be sent via SMTP
- ✅ Login links generated correctly
- ✅ Email templates render properly
- ✅ Errors logged if email fails

---

### Step 4.2: Implement Authentication Routes

**Tasks:**
1. Create `app/auth.py` blueprint
2. Implement `/auth/login` route (GET and POST)
3. Implement token generation logic
4. Implement token verification logic
5. Implement session management
6. Implement logout route
7. Add token expiry cleanup (scheduled task or on-demand)

**Files to Create/Edit:**
- `app/auth.py`

**Routes:**
- `GET /auth/login` - Show login form
- `POST /auth/login` - Process email, send magic link
- `GET /auth/login?token=xxx` - Verify token, log in
- `GET /auth/logout` - Log out user

**Acceptance Criteria:**
- ✅ Users can request login link via email
- ✅ Magic links work correctly
- ✅ Tokens expire after 15 minutes
- ✅ Tokens are single-use
- ✅ Sessions created on successful login
- ✅ Logout clears session

---

### Step 4.3: Create Authentication Decorators

**Tasks:**
1. Create `login_required` decorator
2. Create `optional_login` helper (for pages that work with or without login)
3. Add user context to templates (current_user)
4. Test decorators

**Files to Create/Edit:**
- `app/utils.py` (or `app/decorators.py`)

**Acceptance Criteria:**
- ✅ `@login_required` protects routes
- ✅ Unauthenticated users redirected to login
- ✅ `current_user` available in templates
- ✅ Optional login works for anonymous users

---

## Phase 5: Main Application Routes

### Step 5.1: Create Homepage Route

**Tasks:**
1. Create `app/routes.py` blueprint
2. Implement `GET /` route (homepage)
3. **Discover Agile products from Octopus Products API**
   - Call `OctopusAPIClient.get_agile_products()`
   - Auto-select if exactly one product found
   - Show dropdown if multiple products found
   - Display product code and full name
4. Fetch regions from API (with caching)
5. **Implement postcode-first region detection**
   - Accept UK postcode input
   - Call Grid Supply Point API for region lookup
   - Handle single/multiple/zero results
   - Show manual region dropdown as fallback
6. Render combined form (postcode, region if needed, product if needed)
7. Handle errors gracefully
8. Create `app/templates/index.html`

**Files to Create/Edit:**
- `app/routes.py`
- `app/templates/index.html`
- `app/templates/base.html` (base template)

**Acceptance Criteria:**
- ✅ Homepage loads with postcode input field
- ✅ Agile products discovered dynamically
- ✅ Single product auto-selected, multiple products show dropdown
- ✅ Postcode lookup works for region detection
- ✅ Manual region dropdown shown when needed
- ✅ Form submission works (combined form)
- ✅ Error messages display if API fails
- ✅ Mobile-responsive design

---

### Step 5.2: Create Prices Display Route

**Tasks:**
1. Implement `GET /prices` route
2. Accept query parameters: region, product, duration, capacity
3. **Discover Agile products for dropdown (if multiple available)**
   - Allow product selection to be changed on prices page
   - Display selected product code and full name
4. Fetch prices (with caching) for selected product and region
5. Calculate lowest price
6. Calculate cheapest block
7. Calculate estimated cost (if capacity provided)
8. Format data for chart
9. Render `app/templates/prices.html`

**Files to Create/Edit:**
- `app/routes.py`
- `app/templates/prices.html`

**Query Parameters:**
- `region` (required)
- `product` (required - product code, e.g., 'AGILE-24-10-01')
- `duration` (optional, default 4.0, supports decimals e.g., 3.5)
- `capacity` (optional, for cost calculation)

**Acceptance Criteria:**
- ✅ Prices displayed for selected product and region
- ✅ Product selection visible and changeable
- ✅ Lowest price highlighted
- ✅ Cheapest block calculated correctly
- ✅ Cost estimated if capacity provided
- ✅ Chart renders with price data
- ✅ Form allows updating region, product, duration/capacity
- ✅ Mobile-responsive

---

### Step 5.3: Create Preferences Route (POST-MVP)

**Note:** This step is POST-MVP and should be skipped during MVP implementation.

**Tasks:**
1. Implement `GET /preferences` route (requires login)
2. Implement `POST /preferences` route (update preferences)
3. Load user preferences from database
4. Pre-populate form with saved preferences
5. Save preferences on submit
6. Create `app/templates/preferences.html`

**Files to Create/Edit:**
- `app/routes.py`
- `app/templates/preferences.html`

**Acceptance Criteria:**
- ✅ Preferences page requires login
- ✅ Form pre-populated with saved preferences
- ✅ Preferences save correctly
- ✅ Success message on save
- ✅ Preferences used to personalise other pages

---

### Step 5.4: Create Error Handlers

**Tasks:**
1. Create `app/errors.py` blueprint
2. Implement 404 error handler
3. Implement 500 error handler
4. Implement 403 error handler (if needed)
5. Create `app/templates/error.html`
6. Add email alerts for 500 errors (production)

**Files to Create/Edit:**
- `app/errors.py`
- `app/templates/error.html`

**Acceptance Criteria:**
- ✅ 404 errors show custom page
- ✅ 500 errors show user-friendly message
- ✅ Critical errors logged
- ✅ Email alerts sent for 500 errors (production)

---

## Phase 6: Frontend Implementation

### Step 6.1: Create Base Template

**Tasks:**
1. Create `app/templates/base.html`
2. Include Bootstrap 5 or Tailwind CSS
3. Create responsive navigation
4. Add flash message display
5. Add footer with disclaimers
6. Include Chart.js CDN
7. Create header and footer components

**Files to Create/Edit:**
- `app/templates/base.html`
- `app/templates/components/_header.html`
- `app/templates/components/_footer.html`

**Acceptance Criteria:**
- ✅ Base template renders correctly
- ✅ Navigation responsive (mobile menu)
- ✅ Flash messages display
- ✅ Footer includes disclaimers
- ✅ Chart.js loaded
- ✅ Consistent styling across pages

---

### Step 6.2: Implement Price Chart

**Tasks:**
1. Create `app/static/js/chart.js`
2. Implement `renderPriceChart()` function
3. Integrate Chart.js
4. Style chart appropriately
5. Add interactivity (tooltips, hover effects)
6. Highlight lowest price and cheapest block on chart

**Files to Create/Edit:**
- `app/static/js/chart.js`
- `app/templates/components/_price_chart.html`

**Chart Features:**
- Line chart showing prices over time
- X-axis: Time (HH:MM)
- Y-axis: Price (p/kWh)
- Highlight lowest price point
- Highlight cheapest block (if selected)

**Acceptance Criteria:**
- ✅ Chart renders with price data
- ✅ Chart responsive (mobile-friendly)
- ✅ Lowest price highlighted
- ✅ Cheapest block highlighted (if duration selected)
- ✅ Tooltips show exact prices
- ✅ Chart updates when duration changes

---

### Step 6.3: Create Static Assets

**Tasks:**
1. Create `app/static/css/style.css`
2. Add custom styles (if not using framework)
3. Ensure mobile-first responsive design
4. Create `app/static/js/main.js` for general JavaScript
5. Add form validation (client-side)
6. Add loading indicators

**Files to Create/Edit:**
- `app/static/css/style.css`
- `app/static/js/main.js`

**Acceptance Criteria:**
- ✅ Styles applied correctly
- ✅ Mobile-responsive (test on multiple screen sizes)
- ✅ Forms validate client-side
- ✅ Loading indicators show during API calls
- ✅ Accessible (keyboard navigation, screen readers)

---

### Step 6.4: Complete All Templates

**Tasks:**
1. Finalize `index.html` (homepage)
2. Finalize `prices.html` (price display)
3. Finalize `login.html` (authentication)
4. Finalize `preferences.html` (user settings)
5. Finalize `error.html` (error pages)
6. Ensure all templates extend base.html
7. Add proper form handling
8. Add user feedback (success/error messages)

**Files to Create/Edit:**
- All template files

**Acceptance Criteria:**
- ✅ All pages render correctly
- ✅ Forms submit properly
- ✅ User feedback displayed
- ✅ Consistent design language
- ✅ Mobile-responsive
- ✅ Accessible

---

## Phase 7: User Preferences Integration (POST-MVP)

**IMPORTANT:** User preferences and personalisation are NOT part of MVP. This phase should be skipped during MVP implementation. MVP focuses on anonymous usage.

### Step 7.1: Personalise Homepage (Post-MVP)

**Tasks:**
1. Update homepage to pre-select user's saved region
2. Redirect logged-in users with saved region to prices page (optional)
3. Show welcome message for logged-in users

**Files to Edit:**
- `app/routes.py` (index route)
- `app/templates/index.html`

**Acceptance Criteria:**
- ✅ Logged-in users see pre-selected region
- ✅ Anonymous users see default state
- ✅ Preferences respected

---

### Step 7.2: Personalise Prices Page

**Tasks:**
1. Pre-fill duration from user preferences
2. Pre-fill region from user preferences
3. Show personalised recommendations
4. Add "Save as default" option (if not already saved)

**Files to Edit:**
- `app/routes.py` (prices route)
- `app/templates/prices.html`

**Acceptance Criteria:**
- ✅ Preferences pre-filled for logged-in users
- ✅ Anonymous users see defaults
- ✅ Preferences can be updated from prices page

---

## Phase 8: Error Handling & Logging

### Step 8.1: Enhance Error Handling

**Tasks:**
1. Add try-catch blocks to all routes
2. Create user-friendly error messages
3. Log all errors with context
4. Implement fallback strategies (cache on API failure)
5. Add error recovery mechanisms

**Files to Edit:**
- All route files
- `app/errors.py`

**Error Scenarios:**
- API timeout
- API returns error
- Invalid region code
- Invalid user input
- Database errors

**Acceptance Criteria:**
- ✅ All errors handled gracefully
- ✅ User sees helpful error messages
- ✅ Errors logged with context
- ✅ System recovers from errors (fallbacks)

---

### Step 8.2: Implement Structured Logging

**Tasks:**
1. Configure structured logging (JSON format)
2. Add request context to logs (user_id, region, etc.)
3. Log all API calls
4. Log all calculations
5. Log authentication events
6. Set up log rotation

**Files to Edit:**
- `app/__init__.py` (logging setup)
- All modules (add logging statements)

**Log Levels:**
- DEBUG: Detailed information
- INFO: General information
- WARNING: Warning messages
- ERROR: Error messages
- CRITICAL: Critical errors

**Acceptance Criteria:**
- ✅ Logs structured and readable
- ✅ Request context included
- ✅ Log levels appropriate
- ✅ Logs written to file
- ✅ Critical errors trigger email alerts

---

## Phase 9: Testing

### Step 9.1: Create Test Structure

**Tasks:**
1. Create `tests/` directory
2. Create `tests/__init__.py`
3. Create `tests/conftest.py` (pytest fixtures)
4. Set up test database
5. Create test configuration

**Files to Create:**
- `tests/__init__.py`
- `tests/conftest.py`

**Test Configuration:**
- Use MySQL test database (separate from production)
- Mock external API calls
- Create test fixtures

**Acceptance Criteria:**
- ✅ Test structure created
- ✅ Tests can be run with `pytest`
- ✅ Test database isolated from production

---

### Step 9.2: Write Unit Tests

**Tasks:**
1. Test API client (`test_api_client.py`)
2. Test cache manager (`test_cache_manager.py`)
3. Test price calculator (`test_price_calculator.py`)
4. Test authentication (`test_auth.py`) - Post-MVP
5. Test models (`test_models.py`) - Post-MVP

**Files to Create (MVP):**
- `tests/test_api_client.py`
- `tests/test_cache_manager.py`
- `tests/test_price_calculator.py`

**Files to Create (Post-MVP):**
- `tests/test_auth.py`
- `tests/test_models.py`

**Acceptance Criteria:**
- ✅ All core functions have tests
- ✅ Edge cases covered
- ✅ Tests pass consistently
- ✅ Test coverage > 70%

---

### Step 9.3: Write Integration Tests

**Tasks:**
1. Test routes (`test_routes.py`)
2. Test price calculation flow
3. Test error handling
4. Test authentication flow (Post-MVP)
5. Test preferences flow (Post-MVP)

**Files to Create:**
- `tests/test_routes.py`

**Acceptance Criteria:**
- ✅ Key user flows tested
- ✅ Integration tests pass
- ✅ Error scenarios tested

---

## Phase 10: Security Hardening

### Step 10.1: Implement CSRF Protection

**Tasks:**
1. Ensure Flask-WTF configured
2. Add CSRF tokens to all forms
3. Test CSRF protection
4. Add CSRF error handling

**Files to Edit:**
- All templates with forms
- `app/config.py`

**Acceptance Criteria:**
- ✅ All forms have CSRF tokens
- ✅ CSRF attacks prevented
- ✅ User-friendly CSRF error messages

---

### Step 10.2: Input Validation & Sanitisation

**Tasks:**
1. Validate all user inputs
2. Sanitise email addresses
3. Validate region codes
4. Validate numeric inputs (duration, capacity)
5. Prevent SQL injection (SQLAlchemy handles this)
6. Prevent XSS (Jinja2 auto-escaping)

**Files to Edit:**
- All route handlers
- `app/forms.py`

**Acceptance Criteria:**
- ✅ All inputs validated
- ✅ Invalid inputs rejected with clear messages
- ✅ No SQL injection vulnerabilities
- ✅ No XSS vulnerabilities

---

### Step 10.3: Session Security

**Tasks:**
1. Configure secure session cookies
2. Set appropriate session timeout
3. Implement session regeneration on login
4. Add session cleanup

**Files to Edit:**
- `app/config.py`
- `app/auth.py`

**Acceptance Criteria:**
- ✅ Sessions secure (HTTP-only, secure flag)
- ✅ Session timeout configured
- ✅ Sessions invalidated on logout

---

## Phase 11: Performance Optimisation

### Step 11.1: Optimise Database Queries

**Tasks:**
1. Add database indexes
2. Optimise queries (avoid N+1)
3. Use eager loading where appropriate
4. Add query logging (development)

**Files to Edit:**
- `app/models.py` (add indexes)
- All routes (optimise queries)

**Indexes Needed:**
- `users.email` (unique)
- `login_tokens.token` (unique)
- `login_tokens.user_id`
- `user_preferences.user_id` (unique)

**Acceptance Criteria:**
- ✅ Database indexes added
- ✅ Queries optimised
- ✅ No N+1 query problems

---

### Step 11.2: Optimise Caching

**Tasks:**
1. Review cache expiry times
2. Implement cache warming (optional)
3. Add cache statistics (optional)
4. Optimise cache file I/O

**Files to Edit:**
- `app/cache_manager.py`

**Acceptance Criteria:**
- ✅ Cache strategy optimal
- ✅ Cache reduces API calls significantly
- ✅ Cache files managed efficiently

---

## Phase 12: Documentation

### Step 12.1: Create User Documentation

**Tasks:**
1. Update `README.md` with:
   - Project description
   - Setup instructions
   - Configuration guide
   - Deployment instructions
2. Add inline code comments
3. Document API endpoints (if applicable)

**Files to Edit:**
- `README.md`
- Code files (add docstrings)

**Acceptance Criteria:**
- ✅ README comprehensive
- ✅ Setup instructions clear
- ✅ Code well-documented
- ✅ Deployment guide included

---

### Step 12.2: Create Developer Documentation

**Tasks:**
1. Document architecture decisions
2. Document database schema
3. Document API integration
4. Document extension points
5. Create development guide

**Files to Create/Edit:**
- `DEVELOPMENT.md` (optional)
- Code docstrings

**Acceptance Criteria:**
- ✅ Architecture documented
- ✅ Extension points clear
- ✅ New developers can understand codebase

---

## Phase 13: Deployment Preparation

### Step 13.1: Prepare for PythonAnywhere

**Tasks:**
1. Update `wsgi.py` for production
2. Create production configuration
3. Set up environment variables
4. Test production configuration locally
5. Create deployment checklist

**Files to Edit:**
- `wsgi.py`
- `app/config.py`
- Create `DEPLOYMENT.md`

**PythonAnywhere Specific:**
- Update `DATABASE_URL` for MySQL
- Configure static files mapping
- Set up scheduled tasks (cache cleanup)
- Configure email settings

**Acceptance Criteria:**
- ✅ Production config ready
- ✅ Environment variables documented
- ✅ Deployment checklist complete

---

### Step 13.2: Database Migration for Production

**Tasks:**
1. Test migrations locally
2. Create production migration script
3. Document migration process
4. Create database backup strategy

**Files to Create:**
- Migration scripts
- Backup scripts

**Acceptance Criteria:**
- ✅ Migrations tested
- ✅ Migration process documented
- ✅ Backup strategy defined

---

## Phase 14: Final Testing & Launch

### Step 14.1: End-to-End Testing

**Tasks:**
1. Test complete user journey (anonymous)
2. Test complete user journey (registered)
3. Test all error scenarios
4. Test on multiple browsers
5. Test on mobile devices
6. Performance testing

**Acceptance Criteria:**
- ✅ All user journeys work
- ✅ No critical bugs
- ✅ Performance acceptable
- ✅ Mobile experience good

---

### Step 14.2: Security Audit

**Tasks:**
1. Review all security measures
2. Test for common vulnerabilities
3. Review error messages (no sensitive data)
4. Review logging (no sensitive data)
5. Test authentication security

**Acceptance Criteria:**
- ✅ No security vulnerabilities
- ✅ Sensitive data protected
- ✅ Authentication secure

---

### Step 14.3: Launch Checklist

**Tasks:**
1. Deploy to PythonAnywhere
2. Run database migrations
3. Configure domain (if applicable)
4. Set up monitoring
5. Test live site
6. Create initial admin account (if needed)
7. Monitor for errors

**Acceptance Criteria:**
- ✅ Site live and accessible
- ✅ All features working
- ✅ No critical errors
- ✅ Monitoring active

---

## Implementation Order Summary

**Week 1: Foundation**
- Phase 1: Project Setup
- Phase 2: API Integration
- Phase 3: Business Logic

**Week 2: Core Features (MVP)**
- Phase 4: Authentication (SKIP - Post-MVP)
- Phase 5: Main Routes (MVP core)
- Phase 6: Frontend (Part 1)

**Week 3: Polish (MVP)**
- Phase 6: Frontend (Part 2)
- Phase 7: User Preferences (SKIP - Post-MVP)
- Phase 8: Error Handling

**Week 4: Quality & Launch**
- Phase 9: Testing
- Phase 10: Security
- Phase 11: Performance
- Phase 12: Documentation
- Phase 13: Deployment
- Phase 14: Launch

---

## Success Criteria for MVP

✅ **Functional (MVP):**
- Users can select region and view prices (anonymous)
- Users can find lowest price
- Users can find cheapest block for selected duration
- Users can calculate estimated cost
- System caches API responses (file-based JSON, NOT database)

✅ **Technical (MVP):**
- API integration working
- File-based JSON caching working (pricing data NOT in database)
- Error handling working
- Logging working

✅ **Post-MVP (Not Required for MVP):**
- Database and authentication (designed for future extensibility)
- User preferences and personalisation

✅ **Quality:**
- Mobile-responsive
- Accessible
- Secure
- Well-tested
- Documented
- Deployed

---

**Document Status:** Ready for AI Implementation
