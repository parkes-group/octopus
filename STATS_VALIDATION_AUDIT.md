# Historic 2025 Statistics Validation Audit Report (Revised)

**Date:** 2026-01-14  
**Auditor:** AI Assistant  
**Scope:** Re-run raw data ingestion for 2025, validate raw completeness, regenerate 2025 stats, and verify that the derived statistics accurately reflect the raw data and documented assumptions.

---

## Executive summary

### Bottom line

The historic 2025 statistics are now **reproducible, internally consistent, and defensible** against the raw Octopus pricing data in this repository.

Specifically:

- The raw 2025 dataset under `data/raw/` is **complete** for all 14 regions when queried with an explicit full-year UTC range and correct pagination.
- The regenerated stats under `data/stats/` are **consistent with the raw data** and match spot-check calculations.
- National statistics are confirmed to be an **equal-weighted average across the 14 regions** (a regional average, not consumption-weighted).

### Key verified facts (from the repo as-is)

- **Regions present:** 14/14 (A, B, C, D, E, F, G, H, J, K, L, M, N, P).
- **Expected half-hour slots for a full year (UTC half-hours):** \(365 \times 48 = 17{,}520\) slots per region.
- **Actual raw slots per region:** **17,520** (all regions).
- **UTC coverage:** **365 UTC dates**, each with **48 slots** (no missing UTC dates).
- **UK local-day DST sanity check:** exactly **two** non-48 local days per region:
  - **2025-03-30**: **46** slots (DST start; 23-hour local day)
  - **2025-10-26**: **50** slots (DST end; 25-hour local day)

Evidence is captured in `RAW_DATA_2025_COMPLETENESS_REPORT.md`.

---

## 1. Documentation intent (source of truth)

Documentation reviewed:

- `scripts/STATS_EXPLANATION.md`
- `README.md` (Historical Statistics section)
- `app/config.py` (assumptions)

Documented intent for historic 2025 stats:

- Use **calendar year 2025** Agile half-hourly prices (per region).
- Compute:
  - Avg cheapest **3.5h** block price across the year
  - Avg daily/overall price across the year
  - Savings vs daily average and vs price cap (using documented assumptions)
  - Negative/zero pricing statistics (slot count, hours, average negative price, estimated payment)
- Present national numbers as **an equal-weighted average across regions** (regional average), not a consumption-weighted national average.

---

## 2. Slot count consistency (corrected)

### 2.1 What “expected slots” should be

If you have complete half-hourly coverage for 2025, per region:

- **Expected annual slots:** \(365 \times 48 = 17{,}520\)

If you talk in **UK local time (Europe/London)**, DST affects *which local calendar day contains which UTC half-hours*, but it does **not** change the annual total number of half-hour periods. What changes is the **per-local-day slot count**:

- In 2025, UK DST:
  - **Starts:** 2025-03-30 (local day has **46** half-hour slots; 23-hour day)
  - **Ends:** 2025-10-26 (local day has **50** half-hour slots; 25-hour day)
  - All other local days have **48** half-hour slots

So, for *local-day counts* in 2025 you’d expect **363 days with 48**, **1 day with 46**, and **1 day with 50**.

### 2.2 What the repo’s raw data actually contains

For each region file `data/raw/{REGION}_2025.json` (A..P excluding I,O):

- **Total slots present:** **17,520**
- **Distinct UTC-date prefixes present:** **365**
- **UTC-day slot counts:** all UTC dates have **48** slots
- **UK-local-day anomalies:** exactly **2** (46-slot day on 2025-03-30, 50-slot day on 2025-10-26)

Important clarification:

- For historic auditing, **UTC-day grouping** should be used to verify completeness (365 days × 48 slots/day).
- **DST should only appear when grouping by UK local date**, and only on the two DST transition days.

---

## 3. Raw data completeness (confirmed)

Using the fixed ingestion process (explicit full-year UTC range + pagination), the raw dataset is confirmed complete:

- **All regions:** 17,520 slots
- **All UTC dates:** 365, each with 48 slots
- **No systematic partial-day gaps**

---

## 4. “Expected behavior” vs “acceptable imperfections” vs “errors/gaps”

### 4.1 Expected behavior (designed / normal)

- UK DST leads to **two** local calendar days per year having non-48 slot counts (46 and 50).
- National stats computed as an **equal-weighted average across the 14 regions** is a valid “regional average” approach if that’s what we intend to communicate.

### 4.2 Acceptable but imperfect (if explicitly disclosed)

- A small number of missing days can be acceptable for an educational “could have” display **if** it is disclosed and quantified.

### 4.3 Actual gaps in this repository’s dataset (not expected)

None detected after re-ingestion and validation.

---

## 5. Relationship between raw data completeness and the stats outputs

The `data/stats/*_2025.json` files report:

- `days_processed: 365`
- `days_failed: 0`

This aligns with the raw files having **364 dates with at least one price entry** and **one missing date**.

With complete raw data, the per-day computations are now performed over full UTC days (48 slots/day) across all 365 days.

---

## 6. National average methodology (confirm & clarify)

Confirmed behavior:

- `national_2025.json` is computed as an **equal-weighted mean of the 14 regional stats outputs** (each region contributes equally).
- This is mathematically coherent as a **regional average**.

Public-facing wording recommended (documentation + site copy):

- “**National (regional-average) figure:** calculated as the equal-weighted average of the 14 UK Agile regions. This is not consumption-weighted.”

Important limitation:

- None (raw coverage validated as complete).

---

## 7. Revised conclusion (safe to rely on / publish)

### 7.1 Final assessment

✅ **Yes** — with the regenerated raw dataset and regenerated stats, the 2025 historic statistics are accurate and defensible relative to the Octopus API data for 2025, given the documented assumptions.

---

## 8. What changed in this revised report (and why)

- **Re-ingested raw data correctly:** fixed the historic ingestion script to use an explicit full-year UTC range and traverse pagination, producing complete 2025 datasets.
- **Re-validated completeness:** generated `RAW_DATA_2025_COMPLETENESS_REPORT.md` to prove completeness and DST behavior.
- **Regenerated stats:** reran `scripts/generate_all_stats.py` and verified outputs match the raw inputs and national averages match manual averaging.

---

## Appendix: Evidence snapshot (recomputed from repo files)

See:

- `RAW_DATA_2025_COMPLETENESS_REPORT.md` (raw completeness evidence)
- `scripts/validate_stats.py` output (spot-checks and stats-vs-raw consistency)

