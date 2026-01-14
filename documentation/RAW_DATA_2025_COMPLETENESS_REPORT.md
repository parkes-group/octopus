# Raw data completeness report (2025)

This report validates the raw historic dataset under `data/raw/` *before* regenerating derived stats.

## Expectations for a complete dataset

- **Annual slots per region (UTC half-hours):** 17520 (365 days × 48 slots/day)
- **UTC date coverage:** 2025-01-01 through 2025-12-31 (365 distinct UTC dates)
- **UTC per-day slots:** 48 for every UTC day (DST does not affect UTC-day counts)
- **UK local-day DST sanity check:** one 46-slot local day (DST start) and one 50-slot local day (DST end); other local days 48

## Per-region summary

| Region | Total slots | UTC dates | UTC missing dates | UTC abnormal days | UK abnormal days | Pages fetched |
|---|---:|---:|---:|---:|---:|---:|
| A | 17520 | 365 | 0 | 0 | 2 | 18 |
| B | 17520 | 365 | 0 | 0 | 2 | 18 |
| C | 17520 | 365 | 0 | 0 | 2 | 18 |
| D | 17520 | 365 | 0 | 0 | 2 | 18 |
| E | 17520 | 365 | 0 | 0 | 2 | 18 |
| F | 17520 | 365 | 0 | 0 | 2 | 18 |
| G | 17520 | 365 | 0 | 0 | 2 | 18 |
| H | 17520 | 365 | 0 | 0 | 2 | 18 |
| J | 17520 | 365 | 0 | 0 | 2 | 18 |
| K | 17520 | 365 | 0 | 0 | 2 | 18 |
| L | 17520 | 365 | 0 | 0 | 2 | 18 |
| M | 17520 | 365 | 0 | 0 | 2 | 18 |
| N | 17520 | 365 | 0 | 0 | 2 | 18 |
| P | 17520 | 365 | 0 | 0 | 2 | 18 |

## Details

### Region A

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\A_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region B

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\B_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region C

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\C_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region D

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\D_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region E

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\E_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region F

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\F_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region G

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\G_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region H

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\H_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region J

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\J_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region K

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\K_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region L

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\L_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region M

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\M_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region N

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\N_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

### Region P

- **file**: `D:\VisualStudio\Projects\Octopus\data\raw\P_2025.json`
- **total_slots**: 17520
- **UTC dates**: 365 (2025-01-01 → 2025-12-31)
- **UTC missing dates**: 0
- **UTC abnormal day counts (!=48)**: 0
- **UK local abnormal day counts (!=48)**: 2
  - 2025-03-30: 46 slots (UK local day)
  - 2025-10-26: 50 slots (UK local day)
  - sample: 2025-03-30=46, 2025-10-26=50
- **ingestion**: pages=18, page_size=1000, range=2025-01-01T00:00:00Z..2025-12-31T23:59:59Z

