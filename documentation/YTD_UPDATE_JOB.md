# YTD Update Job (Scheduled Task)

This project includes a daily scheduled job that **incrementally updates**:

- **Raw year-to-date prices** (per region)
- **Derived year-to-date stats** (per region + national)
- **The app’s persistent price cache** (per region) using the existing adaptive expiry rules

## When it runs

- **19:05 UK time (Europe/London)** each day
- Intended for **PythonAnywhere Scheduled Tasks**

## Entry point

- `scripts/update_ytd_prices_and_stats.py`

## What it updates

### Raw data (incremental, not full re-fetch)

Writes per-region raw files to:

- `data/raw/2026/{REGION}_2026.json`

The job:

- Loads the existing raw file
- Finds the **latest `valid_to`** timestamp present
- Decides a fetch range:
  - If raw already includes **tomorrow’s prices** (UK local date), it **does not refetch tomorrow**
  - If raw only covers **today**, it fetches **today + tomorrow**
  - If raw is missing **more than 1 day**, it fetches from the last known timestamp forward
- Fetches prices with **pagination**
- **De-duplicates** slots by `valid_from`
- Sorts chronologically
- Writes atomically

### Stats (only if all regions succeed)

Outputs to:

- `data/stats/2026/{REGION}_2026.json`
- `data/stats/2026/national_2026.json`

If **any region fails**, stats generation is skipped and the job exits with an error.

### Cache refresh (only after stats succeed)

The job refreshes the app cache using existing rules:

- If data includes **tomorrow** → expiry set to **tomorrow at 16:00 UK**
- Otherwise → falls back to the existing short TTL behaviour

Cache files are the existing persistent files:

- `app/cache/{PRODUCT}_{REGION}.json`

## Logging & failure behaviour

Logs are written to stdout (PythonAnywhere task output). The script logs:

- Job start/end (timestamp, year)
- Per-region:
  - last timestamp before update
  - fetch plan + fetched slot count
  - validation result
- A clear **ERROR SUMMARY** at the end if any region fails

Exit codes:

- **0**: success (raw updated, stats regenerated, cache refreshed)
- **1**: failure (any region failed, or stats/cache step failed)

## How to run manually

From the project root:

```bash
python scripts/update_ytd_prices_and_stats.py --year 2026
```

Optional:

```bash
python scripts/update_ytd_prices_and_stats.py --year 2026 --product AGILE-24-10-01
```

## Tests

Tests are designed to avoid calling the live Octopus API:

- Fetch-window decision logic
- Pagination logic (mocked)
- Validation catching gaps/duplicates
- Idempotent dedupe behaviour

Run:

```bash
pytest -q
```

