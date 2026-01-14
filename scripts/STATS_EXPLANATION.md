# Historical Statistics System - Complete Guide

## Overview

The historical statistics system calculates and stores data-driven insights about Agile Octopus pricing for calendar year 2025. Statistics are calculated once and stored in JSON files for efficient frontend display.

This system includes:
- **Raw data download scripts**: Download full year's price data for each region
- **Statistics generation scripts**: Calculate statistics from raw data or API
- **Admin route**: Web-based interface for generating stats
- **Frontend display**: Automatic loading and display of statistics

## Quick Start

### Recommended Workflow

1. **Download raw data** (one-time, takes ~1-2 hours):
   ```bash
   python scripts/download_raw_data.py
   ```

2. **Generate statistics for all regions** (uses raw data, much faster):
   ```bash
   python scripts/generate_all_stats.py
   ```

3. **Statistics are automatically displayed** on the website:
   - Homepage shows national averages
   - Prices page shows regional statistics

## Scripts Overview

All scripts are located in the `scripts/` directory and can be run from the project root.

### 1. `download_raw_data.py` - Download Raw Price Data

**Purpose**: Downloads a full year's worth of price data for each region and saves it to `data/raw/` directory. This is a one-time operation that significantly speeds up subsequent statistics generation.

**Usage**:
```bash
# Download data for all regions (recommended)
python scripts/download_raw_data.py

# Download data for a specific region
python scripts/download_raw_data.py --region A

# Download data for a specific year (default: 2025)
python scripts/download_raw_data.py --year 2025

# Specify product code (default: from config)
python scripts/download_raw_data.py --product AGILE-24-10-01
```

**What it does**:
- Downloads a full year's worth of half-hourly prices for each region from Octopus API
- Uses an **explicit UTC range**:
  - `period_from = 2025-01-01T00:00:00Z`
  - `period_to   = 2025-12-31T23:59:59Z`
- Traverses **pagination** by following the API response `next` link until exhausted
- Saves complete year's data to `data/raw/{region_code}_{year}.json`

**Expected size (complete dataset)**:
- **17,520** price slots per region for 2025 (365 days × 48 half-hour slots per UTC day)

**DST note (important for audits)**:
- DST does **not** affect UTC-day slot counts (still 48 per UTC day)
- When grouping by **UK local date (Europe/London)**, you should expect:
  - One 46-slot local day (DST start: 2025-03-30)
  - One 50-slot local day (DST end: 2025-10-26)

**Output**:
- Files saved to: `data/raw/A_2025.json`, `data/raw/B_2025.json`, etc.
- One file per region containing the entire year's data

**Time**: Typically minutes for all 14 regions (depends on API response times and pagination).

**Why use this**: Once raw data is downloaded, statistics generation is much faster because it reads from local files instead of making API calls.

### 2. `generate_stats.py` - Generate Statistics for a Single Region

**Purpose**: Generates statistics for a single region. Can use raw data files if available, otherwise fetches from API.

**Usage**:
```bash
# Generate stats for region A
python scripts/generate_stats.py --region A

# Generate stats for region B with specific product
python scripts/generate_stats.py --region B --product AGILE-24-10-01

# Generate stats for a specific year
python scripts/generate_stats.py --region A --year 2025
```

**What it does**:
- Loads raw data from `data/raw/{region_code}_{year}.json` if available
- Otherwise fetches data from Octopus API (slower)
- Calculates:
  - Cheapest block averages
  - Daily average prices
  - Negative pricing statistics (including zero-price slots)
  - Savings vs daily average and price cap
- Saves results to `data/stats/{region_code}_{year}.json`

**Output**:
- File saved to: `data/stats/A_2025.json`, `data/stats/B_2025.json`, etc.

**Time**:
- With raw data: ~30 seconds per region
- Without raw data: much slower (requires many API calls / pagination)

### 3. `generate_all_stats.py` - Generate Statistics for All Regions

**Purpose**: Generates statistics for all 14 regions and then calculates national averages. This is the recommended way to generate complete statistics.

**Usage**:
```bash
# Generate stats for all regions and national averages
python scripts/generate_all_stats.py

# Specify product code
python scripts/generate_all_stats.py --product AGILE-24-10-01

# Specify year
python scripts/generate_all_stats.py --year 2025
```

**What it does**:
1. Loops through all 14 regions (A, B, C, D, E, F, G, H, J, K, L, M, N, P)
2. For each region:
   - Calls `generate_stats.py` logic
   - Saves regional stats to `data/stats/{region_code}_{year}.json`
3. After all regions are processed:
   - Calculates national averages from all regional stats
   - Saves national stats to `data/stats/national_{year}.json`

**Output**:
- 14 regional files: `data/stats/A_2025.json` through `data/stats/P_2025.json`
- 1 national file: `data/stats/national_2025.json`

**Time**:
- With raw data: ~10-15 minutes for all regions
- Without raw data: significantly slower (requires many API calls / pagination)

**Recommended**: Use this script after downloading raw data for fastest results.

### 4. `generate_national_stats.py` - Generate National Averages Only

**Purpose**: Calculates national averages from existing regional statistics files. Use this if you've already generated regional stats and just need to update the national averages.

**Usage**:
```bash
# Generate national averages from existing regional stats
python scripts/generate_national_stats.py

# Specify product code
python scripts/generate_national_stats.py --product AGILE-24-10-01

# Specify year
python scripts/generate_national_stats.py --year 2025
```

**What it does**:
- Loads all regional statistics files from `data/stats/`
- Calculates averages across all regions
- Saves national averages to `data/stats/national_{year}.json`

**Prerequisites**: Regional stats files must already exist in `data/stats/`

**Time**: ~1-2 seconds (just reads and processes existing files)

**When to use**: After regenerating individual regional stats and needing to update national averages.

## Admin Route: `/admin/generate-stats`

### Overview

The admin route provides a web-based interface for generating statistics. It's useful for one-off generations but the standalone scripts are recommended for bulk operations.

### How It Works

The admin route is a `POST` endpoint that generates statistics:

```
POST /admin/generate-stats?password=YOUR_PASSWORD&product_code=AGILE-24-10-01&region_code=A
```

### Parameters

- **`password`** (required): Admin password set via `ADMIN_STATS_PASSWORD` environment variable or app config
- **`product_code`** (optional): Octopus product code (defaults to `Config.OCTOPUS_PRODUCT_CODE`)
- **`region_code`** (optional): Region code ('A', 'B', 'C', etc.)
  - If **not provided**: Generates stats for ALL 14 regions, then calculates national averages
  - If provided: Generates stats for the specified region only
- **`year`** (optional): Year to calculate (default: 2025, currently only 2025 is supported)

### Authentication

The route requires a password match:
1. Password is checked against `ADMIN_STATS_PASSWORD` environment variable or `app.config['ADMIN_STATS_PASSWORD']`
2. Password can be provided via query parameter (`?password=...`) or form data
3. If password doesn't match or is missing, returns 403 Forbidden

### Example Usage

#### Generate for ALL Regions (Recommended)
This will generate stats for all 14 regions AND create national averages automatically:
```bash
curl -X POST "http://localhost:5000/admin/generate-stats?password=your-password&product_code=AGILE-24-10-01"
```

#### Generate Single Region Statistics
```bash
# Region A
curl -X POST "http://localhost:5000/admin/generate-stats?password=your-password&product_code=AGILE-24-10-01&region_code=A"

# Region B
curl -X POST "http://localhost:5000/admin/generate-stats?password=your-password&product_code=AGILE-24-10-01&region_code=B"
```

**Note**: The 14 regions are: A, B, C, D, E, F, G, H, J, K, L, M, N, P (I and O are not used)

### Processing Time

The calculation processes all 365 days of 2025. This can take:
- **Several minutes** for a single region (many API calls / pagination)
- **Much longer** for all regions mode (many API calls / pagination)
  - The route will return once ALL regions are processed and national averages are calculated

**Recommendation**: Use the standalone scripts (`download_raw_data.py` + `generate_all_stats.py`) instead of the admin route for bulk operations, as they're more reliable for long-running tasks.

## Frontend Display

### Homepage (Index Route)

The homepage displays **national statistics**:
- Loads stats from `data/stats/national_2025.json`
- Shows 4 headline stat cards with key metrics:
  - Average cheapest block price
  - Annual savings vs daily average
  - Annual savings vs price cap
  - Negative pricing statistics
- Uses `StatsLoader.get_stats_for_display(region_code='national')`

### Prices Page

The prices page displays **regional statistics** based on the user's selected region:
- Loads stats from `data/stats/{region_code}_{year}.json` where `{region_code}` is the selected region
- Shows the same 4 stat cards, but with data specific to that region
- Uses `StatsLoader.get_stats_for_display(region_code=region)` where `region` is from the URL parameter

### Fallback Behavior

If statistics for a region are not available:
- The stats component simply doesn't render (the `{% if stats_2025 %}` check fails)
- No error is shown to users
- The page continues to function normally

## File Structure

```
data/
├── raw/                          # Raw price data (full year per region)
│   ├── A_2025.json              # Region A - full year's prices
│   ├── B_2025.json              # Region B - full year's prices
│   └── ...                      # Other regions
│
└── stats/                        # Calculated statistics
    ├── national_2025.json       # National averages
    ├── A_2025.json              # Region A statistics
    ├── B_2025.json              # Region B statistics
    └── ...                      # Other regions

scripts/                          # Statistics generation scripts
    ├── download_raw_data.py     # Download raw price data
    ├── generate_stats.py         # Generate stats for one region
    ├── generate_all_stats.py    # Generate stats for all regions
    ├── generate_national_stats.py # Generate national averages
    └── STATS_EXPLANATION.md     # This file
```

## Configuration

### Environment Variables

Set the admin password for the web route:
```bash
ADMIN_STATS_PASSWORD=your-secure-password-here
```

### App Configuration

Other configuration is in `app/config.py`:
- `OFGEM_PRICE_CAP_P_PER_KWH`: Price cap unit rate (default: 28.6 p/kWh)
- `STATS_DAILY_KWH`: Average daily usage assumption (default: 11.0 kWh)
- `STATS_BATTERY_CHARGE_POWER_KW`: Battery charge rate (default: 3.5 kW)
- `STATS_CHEAPEST_BLOCK_USAGE_PERCENT`: Percentage of daily usage in cheapest block (default: 35.0%)

## Statistics Calculations

### What Gets Calculated

For each region and the national average:

1. **Cheapest Block Statistics**:
   - Average price of the cheapest 3.5-hour block across all days
   - Based on 35% of daily usage shifted to cheapest blocks

2. **Daily Average Statistics**:
   - Average of all half-hourly prices across the year

3. **Savings Calculations**:
   - Annual savings vs daily average (if using cheapest blocks)
   - Annual savings vs Ofgem price cap

4. **Negative Pricing Statistics**:
   - Total negative/zero-price slots (includes zero-price periods)
   - Total negative hours
   - Average negative price per kWh
   - Total amount Octopus could have paid (based on battery charge power)
   - Average payment per day

### Assumptions

All calculations use these assumptions (configurable in `app/config.py`):
- Daily usage: 11.0 kWh/day
- Battery charge power: 3.5 kW
- Cheapest block usage: 35% of daily usage
- Price cap: 28.6 p/kWh (Ofgem standard variable tariff)

## Important Notes

1. **One-time Calculation**: Statistics are calculated once and stored. No recalculation happens on page load.

2. **National vs Regional**: 
   - **National stats**: Displayed on homepage, calculated as averages across all regions
   - **Regional stats**: Displayed on prices page based on selected region

3. **File Naming**: 
   - Regional stats: `{region_code}_{year}.json` (e.g., `A_2025.json`)
   - National stats: `national_{year}.json` (e.g., `national_2025.json`)

4. **Missing Stats**: If stats for a region don't exist, the component won't display (graceful degradation)

5. **Time Investment**: 
   - Downloading raw data: ~1-2 hours (one-time)
   - Generating stats with raw data: ~10-15 minutes
   - Generating stats without raw data: ~1-2 hours

6. **Zero-Price Slots**: Negative pricing calculations include both negative prices (where Octopus pays you) and zero prices (free electricity)

7. **National Averages**: National statistics are calculated by averaging regional statistics, not by summing them. This ensures accurate representation of the same time period across all regions.

## Troubleshooting

### Scripts can't find the app module

Make sure you're running scripts from the project root:
```bash
# Correct
python scripts/generate_all_stats.py

# Incorrect (if run from scripts directory)
cd scripts
python generate_all_stats.py  # This will fail
```

### Statistics not appearing on website

1. Check that stats files exist in `data/stats/`
2. Verify file naming matches expected format: `{region_code}_2025.json` or `national_2025.json`
3. Check that the region code matches what's selected on the prices page
4. Verify JSON files are valid (not corrupted)

### Raw data download fails

1. Check internet connection
2. Verify Octopus API is accessible
3. Check that product code is correct
4. If validation shows missing slots/dates, verify pagination is working and rerun the download

### Validate raw data completeness (recommended)

After downloading, validate that the dataset is complete **before** regenerating stats:

```bash
python scripts/validate_raw_data.py
```

This will generate: `RAW_DATA_2025_COMPLETENESS_REPORT.md`

Validate derived stats (recommended after regeneration):

```bash
python scripts/validate_stats.py
```

**Pass criteria for a complete 2025 dataset (per region):**
- Total slots: **17,520**
- UTC dates: **365** (2025-01-01 → 2025-12-31)
- UTC abnormal days: **0** (every UTC day should have 48 slots)
- UK local abnormal days: **2** (46-slot day on 2025-03-30, 50-slot day on 2025-10-26)

### Statistics generation is slow

1. **Use raw data**: Download raw data first with `download_raw_data.py` - this makes stats generation 10-20x faster
2. **Use standalone scripts**: The admin route has timeout limitations for long-running operations
3. **Generate regions individually**: If one region fails, you can regenerate just that region

## Best Practices

1. **Download raw data first**: Always download raw data before generating statistics for faster processing
2. **Use `generate_all_stats.py`**: This is the most efficient way to generate complete statistics
3. **Regenerate after config changes**: If you change assumptions in `app/config.py`, regenerate all stats
4. **Keep raw data**: Don't delete `data/raw/` files - they're needed for fast regeneration
5. **Version control**: Don't commit `data/` directory to git (already in `.gitignore`)

