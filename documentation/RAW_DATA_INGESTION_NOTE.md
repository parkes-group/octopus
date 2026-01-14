## Raw data ingestion (historic 2025 Agile prices)

### Entry point

- `scripts/download_raw_data.py`

### What it does (high level)

- Builds an explicit UTC time range for the requested year:
  - `period_from = 2025-01-01T00:00:00Z`
  - `period_to   = 2025-12-31T23:59:59Z`
- Calls Octopus “standard-unit-rates” endpoint for each region:
  - URL built by `Config.get_prices_url(product_code, region_code)`
- Traverses Octopus pagination by following the `next` URL until it is `null`
- Writes one file per region to `data/raw/{REGION}_2025.json` (atomic replace)

### Key functions in `scripts/download_raw_data.py`

- `_year_utc_range(year)`:
  - Builds the explicit UTC range strings for the full year.
- `fetch_prices_paginated(product_code, region_code, year, page_size, sleep_seconds)`:
  - Sends the initial request with `period_from`, `period_to`, `page_size`
  - Follows `next` links, appending `results` from each page
  - Returns the combined list and a small `ingestion` metadata dict
- `download_region_data(product_code, region_code, year)`:
  - Orchestrates the fetch and sorts results chronologically (`valid_from`)
- `save_raw_data(raw_data, region_code, year)`:
  - Writes to `data/raw/{REGION}_{YEAR}.json.tmp` then `os.replace()` to the final path

### Logging / counters

During ingestion, the script logs:

- Page number per region (`pages_fetched`)
- Total slots retrieved per region (`total_price_slots`)
- The exact range requested (`period_from`/`period_to`)

