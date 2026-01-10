# Product Requirements Document (PRD)
## Octopus Energy Agile Pricing Assistant

**Version:** 1.0  
**Date:** 2024  
**Status:** MVP Planning

---

## 1. Problem Statement

UK households with solar panels and home batteries on Octopus Energy's Agile tariff face a critical challenge: identifying the optimal times to charge their batteries to minimise electricity costs. With 30-minute pricing that can vary dramatically throughout the day, manually calculating the cheapest charging windows is time-consuming and error-prone.

**Current Pain Points:**
- Users must manually check Octopus Energy's website or app multiple times daily
- No automated way to identify the cheapest continuous charging blocks
- No alerts for negative pricing events (when Octopus pays users to consume)
- Difficulty comparing different charging duration options
- No personalised recommendations based on user preferences

**Solution:**
A consumer-facing web application that automatically fetches Agile Octopus pricing data, calculates optimal charging windows, and provides clear, actionable insights to help users minimise their electricity costs.

---

## 2. Target Users

### Primary Users
- **UK households with home batteries** (e.g., Tesla Powerwall, GivEnergy, Solax, etc.)
- **Solar panel owners** on Agile Octopus tariff
- **Energy-conscious consumers** seeking to optimise electricity costs
- **Tech-savvy early adopters** comfortable with web-based tools

### User Personas

**Persona 1: "The Optimiser"**
- Age: 35-55
- Tech comfort: High
- Goal: Minimise electricity bills through strategic battery charging
- Behaviour: Checks prices multiple times daily, wants detailed data

**Persona 2: "The Set-and-Forget"**
- Age: 40-60
- Tech comfort: Medium
- Goal: Simple recommendations without constant monitoring
- Behaviour: Wants alerts and automation, less interested in manual calculations

**Persona 3: "The Explorer"**
- Age: 25-45
- Tech comfort: High
- Goal: Understand energy pricing patterns and trends
- Behaviour: Enjoys visualisations and historical comparisons

---

## 3. MVP Scope vs Future Features

### MVP Features (Phase 1)

**Core Functionality:**
1. ✅ Postcode-based region detection (automatic via Octopus Grid Supply Point API)
2. ✅ Manual region selection fallback (when postcode lookup fails)
3. ✅ Dynamic Agile product discovery (automatically discovers available Agile tariff versions from Octopus API)
4. ✅ Automatic product selection when only one Agile product exists
5. ✅ Product selection dropdown when multiple Agile products exist
6. ✅ Display today's half-hourly Agile prices for selected product
7. ✅ Identify lowest single 30-minute price
8. ✅ Calculate absolute cheapest continuous block for user-selected duration (0.5-6 hours, supports decimals e.g., 3.5 hours) across all prices for the day
9. ✅ Calculate cheapest remaining (future) continuous block for user-selected duration (only considers time slots after current time)
10. ✅ Display daily average price(s) - calculates one average per UK calendar day. If prices span two days, displays two averages with date labels
11. ✅ Cost estimation based on user-provided kWh (uses future block if available, otherwise absolute block)
12. ✅ Visual price chart (Chart.js) with visual distinction between absolute and future cheapest blocks and accessible text alternatives
13. ✅ Region summary comparison page - compare prices across all UK regions (mobile cards / desktop table)
14. ✅ Mobile-first responsive design (works on phones, tablets, desktop)
15. ✅ Accessibility features (WCAG-aligned: semantic HTML, ARIA labels, keyboard navigation, screen reader support)
16. ✅ Anonymous browsing (no account required)

**Optional MVP Enhancement (Post-MVP):**
- Email-based account creation (passwordless authentication)
- Save user preferences (region, duration, capacity)
- Note: Authentication and user accounts are designed for future extensibility but are NOT required for MVP core functionality

**Technical MVP:**
- Flask backend
- Jinja templates
- MySQL database (only if authentication implemented - see note above)
- Octopus API integration with file-based JSON caching
- Error handling and logging
- **Mobile-first responsive design** - Works on phones, tablets, and desktop
- **Accessibility (WCAG-aligned)** - Semantic HTML, ARIA labels, keyboard navigation, screen reader support
- **Mobile-first responsive design** - Works on phones, tablets, and desktop
- **Accessibility (WCAG-aligned)** - Semantic HTML, ARIA labels, keyboard navigation, screen reader support
- **Note:** Pricing data is cached in files (JSON), NOT in database

### Future Features (Post-MVP)

**Phase 2: Notifications**
- Email alerts for negative pricing
- Email/SMS alerts for cheapest charging windows
- Customisable alert thresholds
- Notification preferences management

**Phase 3: Automation**
- Scheduled background price polling
- Automated charge window recommendations
- Integration with home battery inverters (API-based)
- Automated charge scheduling

**Phase 4: Premium Features**
- Historical price analysis
- Price trend predictions
- Multi-day optimisation
- Export optimisation (for solar users)
- Subscription billing integration
- API access for advanced users

**Phase 5: Partnerships**
- Affiliate partnerships (battery manufacturers, EV chargers, installers)
- Integration marketplace
- White-label solutions

---

## 4. Success Metrics

### MVP Success Criteria

**User Engagement:**
- 100+ unique visitors in first month
- 50%+ return visitor rate
- Average session duration > 2 minutes
- 20%+ account creation rate (of returning visitors)

**Technical Performance:**
- 99%+ uptime
- API response time < 2 seconds (with caching)
- Zero critical errors in production
- Mobile traffic > 40% of total

**User Satisfaction:**
- Positive user feedback on clarity and usefulness
- Low bounce rate (< 40%)
- High feature adoption (charging duration selector used by > 60% of users)

### Long-Term Metrics

**Business Metrics:**
- Conversion to paid subscriptions (target: 5-10% of registered users)
- Monthly recurring revenue (MRR)
- Customer lifetime value (LTV)
- Churn rate < 5% monthly

**Product Metrics:**
- Daily active users (DAU)
- Notification open rates (> 30%)
- Feature usage analytics
- User retention (30-day, 90-day)

---

## 5. Monetisation Strategy

### Freemium Model

**Free Tier:**
- Manual price viewing
- Basic cheapest block calculations
- Today's prices only
- Anonymous browsing
- Basic price chart

**Premium Tier (£4.99/month or £49/year):**
- Email & SMS notifications
- Negative pricing alerts
- Cheapest charging window alerts
- Saved preferences and personalisation
- Historical price analysis (last 7 days)
- Price trend visualisations
- Priority support

**Pro Tier (£9.99/month or £99/year):**
- All Premium features
- Extended historical analysis (30 days)
- Multi-day optimisation
- Export optimisation recommendations
- API access (rate-limited)
- Advanced automation features
- Early access to new features

### Additional Revenue Streams

**Affiliate Partnerships:**
- Battery manufacturers (commission on referrals)
- EV charger installers
- Solar panel installers
- Energy consultants

**Enterprise/API Access:**
- B2B API access for energy management companies
- White-label solutions
- Custom integrations

**Future Considerations:**
- One-time setup fees for advanced integrations
- Consulting services for complex installations
- Data licensing for research institutions

---

## 6. User Stories

### MVP User Stories

**As an anonymous user:**
- I want to enter my UK postcode so the system can automatically determine my energy region
- I want to manually select my region if postcode lookup fails so I can still access pricing information
- I want to see today's half-hourly prices in a chart so I can visualise price patterns
- I want to see the lowest 30-minute price so I know the absolute cheapest time
- I want to select how many hours I want to charge (0.5-6 hours, supports decimals e.g., 3.5 hours) so I can find the best block for my needs
- I want to see the cheapest continuous block for my selected duration so I can plan my charging
- I want to enter my battery capacity (kWh) so I can see the estimated cost to charge
- I want to see the estimated cost clearly displayed so I can make informed decisions

**As a registered user (Post-MVP):**
- I want to create an account with just my email (no password) so I can save my preferences
- I want to save my region preference so I don't have to select it every time
- I want to save my preferred charging duration so it's pre-selected when I visit
- I want to save my battery storage capacity so it's pre-selected when I visit
- I want to update my preferences easily so I can adapt to changing needs

**Note:** User accounts and preferences are post-MVP features. MVP focuses on anonymous usage.

**As a site owner:**
- I want to cache Octopus API responses so I don't exceed rate limits
- I want to see structured logs so I can debug issues
- I want to receive email alerts for critical errors so I can respond quickly
- I want graceful error handling so users see helpful messages when APIs fail

---

## 7. Functional Requirements

### 7.1 Pricing & Calculations

**FR-1: Region Detection**
- System MUST accept UK postcode input as primary method for region detection
- System MUST use Octopus Grid Supply Point API to map postcode to region code
- System MUST validate postcode format before API call
- System MUST provide manual region selection fallback when postcode lookup fails (zero results)
- System MUST support all UK regions (retrieved dynamically from API)
- System MUST handle postcode lookup errors gracefully

**FR-2: Agile Product Discovery**
- System MUST dynamically discover available Agile products from Octopus Products API
- System MUST filter products by code containing "AGILE" (case-insensitive)
- System MUST filter products by direction (IMPORT, EXPORT, or BOTH - configurable)
- System MUST only include active products (available_to is null or in the future)
- System MUST handle API pagination for product discovery
- System MUST auto-select product when exactly one Agile product exists
- System MUST display product selection dropdown when multiple Agile products exist
- System MUST display selected product code and full name on index and prices pages
- System MUST allow product selection to be changed on prices page

**FR-3: Price Fetching**
- System MUST fetch half-hourly Agile prices from Octopus public APIs for the selected product
- System MUST only display today's prices (current day in UK timezone)
- System MUST handle timezone correctly (GMT/BST)

**FR-4: Price Display**
- System MUST display prices in pence per kWh
- System MUST show all 48 half-hour slots for today
- System MUST highlight the lowest single 30-minute slot
- System MUST display prices in a visual chart (Chart.js)

**FR-5: Cheapest Block Calculation**
- System MUST allow users to select charging duration (0.5-6 hours, supports decimal values e.g., 3.5 hours)
- System MUST calculate two types of cheapest blocks:
  - **Absolute cheapest block**: The cheapest contiguous block of N hours across ALL prices for the day (may include past time slots)
  - **Future cheapest block**: The cheapest contiguous block of N hours considering ONLY time slots where valid_from >= current_time (upcoming slots only)
- System MUST display both blocks when available, with clear labels indicating "Absolute Cheapest" and "Cheapest Remaining"
- System MUST indicate if the absolute cheapest block has already passed (show "Already passed" vs "Upcoming")
- System MUST display the start time, end time, and average price for each block
- System MUST handle edge cases (e.g., if no future block exists, show "No remaining cheap blocks today")
- System MUST use timezone-aware datetime comparisons to distinguish past vs future slots

**FR-5.1: Daily Average Price**
- System MUST calculate daily averages grouped by UK calendar date (physical day)
- System MUST calculate one average per calendar day when prices span multiple days
- System MUST display a single daily average when all prices belong to one calendar day
- System MUST display multiple daily averages with date labels (e.g., "09/01/26 – 16.25 p/kWh") when prices span two calendar days
- System MUST NOT combine prices from different calendar dates into a single average
- System MUST use value_inc_vat consistently for all price calculations

**FR-5.2: Region Summary Comparison**
- System MUST aggregate existing price calculations across all Octopus regions
- System MUST reuse existing calculation functions (find_lowest_price, find_cheapest_block, calculate_daily_average_price)
- System MUST display region summaries in mobile-friendly cards on small screens
- System MUST display region summaries in a table format on desktop
- System MUST highlight regions with cheapest daily average price
- System MUST highlight regions with cheapest block average price
- System MUST gracefully handle per-region errors (continue processing other regions if one fails)
- System MUST use default block duration of 3.5 hours (same as single-region view)
- System MUST NOT duplicate pricing logic - all calculations must use existing PriceCalculator methods

**FR-6: Cost Estimation**
- System MUST allow users to input battery capacity (kWh)
- System MUST calculate estimated cost: `(average_price * capacity) / 100` (convert pence to pounds)
- System MUST display cost in pounds (£) with 2 decimal places
- System MUST handle invalid inputs gracefully

### 7.2 Caching Strategy

**FR-7: API Caching**
- System MUST cache Octopus API responses
- Cache MUST be file-based JSON (PythonAnywhere-compatible)
- **Important:** Pricing data is NOT cached in database - only in JSON files
- Cache MUST expire automatically (recommended: 5 minutes)
- System MUST fallback to cached data if live API call fails
- Cache files MUST be stored in a dedicated directory (e.g., `app/cache/`)
- Cache files MUST include timestamp metadata

**FR-8: Cache Invalidation**
- Cache MUST be invalidated when:
  - Cache age exceeds expiry time
  - New day begins (UK timezone)
  - Manual cache clear (admin function)

### 7.3 Accessibility & Usability

**FR-9: Mobile-First Design**
- System MUST be designed mobile-first (small screens first)
- All pages MUST render correctly on phones (iOS + Android), tablets, and desktop
- No horizontal scrolling on mobile devices
- Text MUST be readable without zooming (minimum 16px base font size)
- Touch targets (buttons, dropdowns) MUST be at least 44x44px
- Forms MUST use appropriate input modes for mobile keyboards

**FR-10: WCAG Accessibility**
- System MUST use semantic HTML (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`)
- All form elements MUST have associated `<label>` tags
- System MUST provide sufficient color contrast (WCAG AA minimum)
- All interactive elements MUST have visible focus states for keyboard users
- System MUST NOT rely on color alone to convey meaning (use icons, labels, or patterns)
- Charts MUST have text summaries and accessible table equivalents
- System MUST support keyboard navigation
- System MUST work with screen readers (ARIA labels where semantic HTML insufficient)
- Headings MUST form a logical hierarchy and describe content meaningfully

**FR-11: Typography & Readability**
- Base font size MUST be at least 16px
- Clear visual hierarchy (headings visually distinct)
- Prices and key numbers MUST be emphasised
- Line length MUST be comfortable for reading on mobile (max 65ch recommended)

### 7.4 Error Handling

**FR-12: API Error Handling**
- System MUST handle Octopus API failures gracefully
- System MUST display user-friendly error messages
- System MUST attempt to use cached data when available
- System MUST log all API errors with context
- System MUST not expose technical error details to users

**FR-10: User Input Validation**
- System MUST validate postcode format (UK postcode pattern)
- System MUST validate region selection (when manually selected)
- System MUST validate charging duration (0.5-6 hours, supports decimal values)
- System MUST validate battery capacity (positive number, reasonable range)
- System MUST provide clear error messages for invalid inputs

### 7.4 User Accounts & Authentication (Post-MVP)

**Note:** Authentication and user accounts are NOT part of MVP. The architecture is designed for future extensibility, but MVP should focus on anonymous usage only.

**FR-11: Passwordless Authentication (Post-MVP)**
- System MUST support email-based login (magic links) - POST-MVP
- System MUST NOT store passwords
- System MUST generate secure, time-limited tokens
- Tokens MUST be single-use
- Tokens MUST expire after 15 minutes
- System MUST email login links to users

**FR-12: User Preferences (Post-MVP)**
- System MUST store user region preference - POST-MVP
- System MUST store preferred charging duration - POST-MVP
- System MUST allow users to update preferences - POST-MVP
- Preferences MUST be used to personalise the UI - POST-MVP
- **MVP:** System MUST support anonymous users only (no preferences saved)

**FR-13: Account Management (Post-MVP)**
- Users MUST be able to view their saved preferences - POST-MVP
- Users MUST be able to update their email address - POST-MVP
- Users MUST be able to delete their account - POST-MVP

### 7.5 Data & Database

**FR-13: Database Schema**
- System MUST use MySQL database (both development and production)
- System MUST use SQLAlchemy ORM
- System MUST support database migrations
- **MVP:** Database is optional (only needed if authentication is implemented - POST-MVP)
- **Post-MVP:** System MUST store:
  - User accounts (email, name, created_at, updated_at)
  - User preferences (region, charging_duration, battery_capacity)
  - Login tokens (token, user_id, expires_at, used_at)
- **Important:** Pricing data is NOT stored in database - only cached in JSON files

**FR-14: Data Privacy**
- System MUST comply with GDPR
- System MUST allow users to delete their data
- System MUST not share user data with third parties (except as required for service)
- System MUST store data securely

---

## 8. Non-Functional Requirements

### 8.1 Performance
- Page load time < 2 seconds (with caching)
- API response time < 500ms (cached)
- Support 100+ concurrent users
- Graceful degradation under load

### 8.2 Security
- HTTPS only
- Secure token generation (cryptographically random)
- SQL injection prevention (SQLAlchemy parameterised queries)
- XSS prevention (Jinja auto-escaping)
- CSRF protection (Flask-WTF)
- Rate limiting on authentication endpoints
- No API keys exposed client-side

### 8.3 Usability
- Mobile-first responsive design
- Accessible (WCAG 2.1 AA minimum)
- Clear, non-technical language
- Intuitive navigation
- Helpful error messages
- Loading indicators for async operations

### 8.4 Reliability
- 99%+ uptime target
- Automated error monitoring
- Email alerts for critical errors
- Graceful fallbacks for API failures
- Data backup strategy

### 8.5 Observability
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Request/response logging (sanitised)
- Performance metrics
- Error tracking and alerting

---

## 9. Technical Constraints

- **Hosting:** PythonAnywhere (shared hosting limitations)
- **Database:** MySQL (PythonAnywhere MySQL)
- **Timezone:** UK only (GMT/BST)
- **Tariff:** Agile Octopus only
- **Region:** UK only
- **Pricing timeframe:** Today's prices only (MVP)
- **No real-time updates:** Cached data with periodic refresh

---

## 10. Out of Scope (MVP)

**Explicitly Excluded from MVP:**
- User authentication and accounts (passwordless magic links - post-MVP)
- Email/SMS notifications
- Inverter API integrations
- Subscription billing and payment processing
- Historical price analysis
- Multi-day optimisation
- User analytics dashboard
- Admin panel
- API documentation
- Mobile apps (iOS/Android)
- Social media integration
- User reviews/ratings

**Note:** Authentication architecture is documented for future implementation but should NOT be built in MVP phase.

---

## 11. Assumptions

1. Users have internet access and a modern web browser
2. Users understand basic energy concepts (kWh, pricing)
3. Users are on Agile Octopus tariff (or considering it)
4. Octopus Energy APIs remain publicly accessible
5. API rate limits are sufficient for expected traffic
6. PythonAnywhere hosting is sufficient for MVP scale
7. Users are comfortable with email-based authentication
8. UK timezone handling is sufficient (no international users)

---

## 12. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Octopus API changes/outages | High | Medium | Caching, fallback to cached data, error handling |
| Rate limiting | Medium | Low | Aggressive caching, request throttling |
| PythonAnywhere limitations | Medium | Low | Optimise code, consider alternative hosting if needed |
| Low user adoption | High | Medium | Marketing, SEO, user feedback, iterate on UX |
| Data accuracy issues | High | Low | Validation, testing, clear disclaimers |
| Security vulnerabilities | High | Low | Security best practices, regular updates, audits |

---

## 13. Dependencies

**External APIs:**
- Octopus Energy Agile Pricing API
- Octopus Energy Regions API
- Email service (SMTP or SendGrid/Mailgun)

**Libraries:**
- Flask (web framework)
- SQLAlchemy (ORM)
- Requests (HTTP client)
- Jinja2 (templating)
- Chart.js (client-side charts)
- Flask-WTF (CSRF protection)
- python-dotenv (environment variables)

**Infrastructure:**
- PythonAnywhere account
- MySQL database
- SMTP server (or email service)

---

## 14. Acceptance Criteria

### MVP Acceptance Criteria

1. ✅ User can select region and see today's prices
2. ✅ User can see lowest 30-minute price
3. ✅ User can select charging duration and see cheapest block
4. ✅ User can calculate estimated cost
5. ✅ System caches API responses effectively (file-based JSON, NOT database)
6. ✅ System handles errors gracefully
7. ✅ Site is mobile-responsive
8. ✅ All critical paths tested and working

**Post-MVP:**
- User can create account with email (passwordless)
- User can save and update preferences

---

## 15. Future Considerations

- Migration to cloud hosting (AWS, Heroku, Railway) for scale
- Real-time WebSocket updates for price changes
- Machine learning for price predictions
- Integration with smart home platforms (Home Assistant, etc.)
- Mobile app development (React Native or Flutter)
- International expansion (other countries with similar tariffs)
- Community features (forums, user tips)

---

## 11. Feedback & Community

### 11.1 Feedback Loop

**GitHub Issues Integration:**
- System MUST provide a clear feedback mechanism via GitHub Issues
- Users can report bugs and suggest features through GitHub Issues
- Feedback link MUST be visible on all pages (preferably in footer)
- Link MUST open in new tab and clearly indicate it goes to GitHub

**User Experience:**
- No account required on the application itself to access feedback
- Users only need a GitHub account to submit issues (GitHub accounts are free)
- Feedback link should be clearly labeled (e.g., "💬 Feedback & Feature Requests")

**Technical Implementation:**
- GitHub Issues URL stored in configuration (`GITHUB_FEEDBACK_URL`)
- URL made available to all templates via Flask context processor
- Link uses `target="_blank"` and `rel="noopener noreferrer"` for security
- Link is keyboard accessible and has appropriate hover/focus styling

**Why GitHub Issues:**
- Transparent feedback loop (all issues visible to community)
- Built-in issue tracking and management
- Support for bug reports and feature requests with templates
- No custom infrastructure required
- Maintains open communication channel with users

**Acceptance Criteria:**
- ✅ Feedback link visible on index and prices pages
- ✅ Link opens GitHub Issues in new tab
- ✅ Link is accessible (keyboard navigation, screen readers)
- ✅ Link is configurable via environment variable
- ✅ Works on mobile and desktop
- Open source components

---

---

## 16. SEO & AI Discovery Strategy

### 16.1 Search Engine Optimization (SEO)

**Traditional SEO:**
- Dynamic, page-specific meta titles (≤ 60 characters) and descriptions (≤ 160 characters)
- Canonical URLs to prevent duplicate content issues
- OpenGraph tags for social media sharing
- Semantic HTML5 structure with proper heading hierarchy (one `<h1>` per page)
- `robots.txt` allowing all crawlers
- `sitemap.xml` with all public pages

**Content Strategy:**
- Visible, human-readable explanations on all pages
- Clear descriptions of what Agile Octopus is
- Explanation of who the tool is for (UK households, solar + battery owners)
- Plain English, no marketing fluff or keyword stuffing
- All content server-side rendered (Jinja templates)

### 16.2 AI Assistant Discovery

**Optimization for LLMs:**
- Structured data (JSON-LD) with WebSite and SoftwareApplication schemas
- `/about` page with comprehensive information for AI ingestion
- Clear data source attribution (Octopus Energy public API)
- Explicit disclaimers about informational vs. financial advice
- Semantic HTML that clearly communicates purpose and functionality

**Why This Matters:**
- AI assistants (ChatGPT, Claude, Gemini, etc.) can accurately summarize the tool
- Users asking "best time to charge battery on Agile Octopus" will get helpful responses
- Transparent data sources build trust with both users and AI systems

### 16.3 Privacy & Tracking

**No Tracking Policy:**
- No tracking pixels or analytics cookies
- No third-party scripts for advertising
- No user behavior tracking
- Focus on user value, not data collection

**Benefits:**
- Faster page loads
- Better privacy for users
- No cookie banners required
- Clear, transparent user experience

### 16.4 Technical Implementation

**Configuration:**
- All SEO text stored in `config.py` (not hard-coded in templates)
- Page-specific SEO content via `SEO_PAGES` dictionary
- Template inheritance used properly (base.html for common elements)
- Context processor makes SEO config available to all templates

**Structured Data:**
- JSON-LD schemas injected into base template
- WebSite schema with search action
- SoftwareApplication schema with operating area (UK) and purpose
- Valid JSON, properly escaped for Jinja templates

**Acceptance Criteria:**
- ✅ All pages have meaningful titles and descriptions
- ✅ Content is understandable by humans and LLMs
- ✅ Site can be correctly summarized by an AI assistant
- ✅ Google Search Console reports no critical SEO errors
- ✅ No regressions in functionality
- ✅ All pages fully accessible without JavaScript

---

**Document Status:** Ready for Technical Architecture Design
