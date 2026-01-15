"""
Validate completeness of raw historic price data under data/raw/{YEAR}/.

This is intentionally separate from stats generation:
- It checks *inputs* (raw data) before any derived stats are regenerated.
- It produces a clear report usable for audits.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Add the project root to the path (scripts are in scripts/ subdirectory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import Config

# Resolve paths relative to project root to avoid CWD issues (WSGI / different shells)
RAW_BASE_DIR = project_root / "data" / "raw"
DOCS_DIR = project_root / "documentation"
UK_TZ = ZoneInfo("Europe/London")


def expected_utc_dates_for_range(start: date, end: date) -> set[str]:
    out = set()
    cur = start
    while cur <= end:
        out.add(cur.isoformat())
        cur += timedelta(days=1)
    return out


def parse_utc_iso_z(ts: str) -> datetime:
    # valid_from is like "2025-01-01T00:00:00Z"
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_region(region: str, year: int, *, expected_end_utc: date) -> dict:
    raw_dir = RAW_BASE_DIR / str(year)
    path = raw_dir / f"{region}_{year}.json"
    if not path.exists():
        return {"region": region, "status": "missing_file", "path": str(path)}

    data = json.loads(path.read_text(encoding="utf-8"))
    prices = data.get("prices", [])

    # UTC-day grouping (date prefix in ISO Z timestamp)
    utc_dates = [p.get("valid_from", "")[:10] for p in prices if p.get("valid_from")]
    utc_counts = Counter(utc_dates)

    expected_dates = expected_utc_dates_for_range(date(year, 1, 1), expected_end_utc)
    present_dates = set(utc_counts.keys())
    missing_dates = sorted(expected_dates - present_dates)
    extra_dates = sorted(present_dates - expected_dates)

    # UTC per-day slots should be 48, except the current UTC day can legitimately be partial for year-to-date datasets.
    last_expected_utc = expected_end_utc.isoformat()
    partial_current_utc_day_slots = None
    abnormal_utc_days = {}
    for d, c in utc_counts.items():
        if c == 48:
            continue
        if d == last_expected_utc and expected_end_utc == datetime.now(timezone.utc).date() and c < 48:
            partial_current_utc_day_slots = c
            continue
        abnormal_utc_days[d] = c

    # UK-local-day grouping (for DST sanity checks)
    uk_counts = Counter()
    for p in prices:
        vf = p.get("valid_from")
        if not vf:
            continue
        dt_utc = parse_utc_iso_z(vf)
        dt_uk = dt_utc.astimezone(UK_TZ)
        uk_counts[dt_uk.date().isoformat()] += 1

    uk_abnormal_days = {d: c for d, c in uk_counts.items() if c != 48}

    return {
        "region": region,
        "path": str(path),
        "total_slots": len(prices),
        "utc_unique_dates": len(utc_counts),
        "utc_date_min": min(utc_counts.keys()) if utc_counts else None,
        "utc_date_max": max(utc_counts.keys()) if utc_counts else None,
        "utc_missing_dates": missing_dates,
        "utc_extra_dates": extra_dates,
        "utc_abnormal_day_counts": dict(sorted(abnormal_utc_days.items())),
        "utc_partial_current_day_slots": partial_current_utc_day_slots,
        "uk_unique_dates": len(uk_counts),
        "uk_abnormal_day_counts": dict(sorted(uk_abnormal_days.items())),
        "ingestion_meta": data.get("ingestion", {}),
        "status": "ok",
    }


def write_markdown_report(results: list[dict], year: int, out_path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Raw data completeness report ({year})")
    lines.append("")
    lines.append("This report validates the raw historic dataset under `data/raw/` *before* regenerating derived stats.")
    lines.append("")
    lines.append("## Expectations for a complete dataset")
    lines.append("")
    now_utc_date = datetime.now(timezone.utc).date()
    expected_end_utc = date(year, 12, 31) if year < now_utc_date.year else min(date(year, 12, 31), now_utc_date)
    expected_days = (expected_end_utc - date(year, 1, 1)).days + 1
    lines.append(f"- **Expected UTC coverage end:** {expected_end_utc.isoformat()} ({'year_to_date' if expected_end_utc != date(year, 12, 31) else 'full_year'})")
    lines.append(f"- **Expected UTC dates:** {expected_days} (from {year}-01-01)")
    lines.append("- **UTC per-day slots:** 48 for every UTC day (DST does not affect UTC-day counts)")
    lines.append("- **UK local-day DST sanity check:** DST affects UK local-day slot counts around the transition dates; this does not affect UTC-day counts")
    lines.append("")
    lines.append("## Per-region summary")
    lines.append("")
    lines.append("| Region | Total slots | UTC dates | UTC missing dates | UTC abnormal days | UK abnormal days | Pages fetched |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for r in results:
        if r.get("status") != "ok":
            lines.append(f"| {r.get('region')} | (missing) | (missing) | (missing) | (missing) | (missing) | (missing) |")
            continue
        pages = r.get("ingestion_meta", {}).get("pages_fetched", "")
        lines.append(
            f"| {r['region']} | {r['total_slots']} | {r['utc_unique_dates']} | {len(r['utc_missing_dates'])} | "
            f"{len(r['utc_abnormal_day_counts'])} | {len(r['uk_abnormal_day_counts'])} | {pages} |"
        )

    lines.append("")
    lines.append("## Details")
    lines.append("")
    for r in results:
        lines.append(f"### Region {r.get('region')}")
        lines.append("")
        if r.get("status") != "ok":
            lines.append(f"- **status**: {r.get('status')}")
            lines.append(f"- **path**: `{r.get('path')}`")
            lines.append("")
            continue
        lines.append(f"- **file**: `{r['path']}`")
        lines.append(f"- **total_slots**: {r['total_slots']}")
        lines.append(f"- **UTC dates**: {r['utc_unique_dates']} ({r['utc_date_min']} → {r['utc_date_max']})")
        lines.append(f"- **UTC missing dates**: {len(r['utc_missing_dates'])}")
        if r["utc_missing_dates"]:
            lines.append(f"  - {', '.join(r['utc_missing_dates'][:10])}{' ...' if len(r['utc_missing_dates']) > 10 else ''}")
        lines.append(f"- **UTC abnormal day counts (!=48)**: {len(r['utc_abnormal_day_counts'])}")
        if r["utc_abnormal_day_counts"]:
            sample = list(r["utc_abnormal_day_counts"].items())[:10]
            lines.append(
                "  - sample: "
                + ", ".join([f"{d}={c}" for d, c in sample])
                + (" ..." if len(r["utc_abnormal_day_counts"]) > 10 else "")
            )
        lines.append(f"- **UK local abnormal day counts (!=48)**: {len(r['uk_abnormal_day_counts'])}")
        if r["uk_abnormal_day_counts"]:
            # specifically highlight DST expectation days if present
            for k in ["2025-03-30", "2025-10-26"]:
                if k in r["uk_abnormal_day_counts"]:
                    lines.append(f"  - {k}: {r['uk_abnormal_day_counts'][k]} slots (UK local day)")
            # include small sample
            sample2 = list(r["uk_abnormal_day_counts"].items())[:10]
            lines.append(
                "  - sample: "
                + ", ".join([f"{d}={c}" for d, c in sample2])
                + (" ..." if len(r["uk_abnormal_day_counts"]) > 10 else "")
            )
        meta = r.get("ingestion_meta", {})
        if meta:
            lines.append(f"- **ingestion**: pages={meta.get('pages_fetched')}, page_size={meta.get('page_size')}, range={meta.get('period_from')}..{meta.get('period_to')}")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate raw historic price data completeness")
    parser.add_argument("--year", "-y", type=int, default=2025, help="Year (default: 2025)")
    args = parser.parse_args()

    year = args.year
    raw_dir = RAW_BASE_DIR / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    regions = list(Config.OCTOPUS_REGION_NAMES.keys())
    now_utc_date = datetime.now(timezone.utc).date()
    expected_end_utc = date(year, 12, 31) if year < now_utc_date.year else min(date(year, 12, 31), now_utc_date)
    results = [validate_region(r, year, expected_end_utc=expected_end_utc) for r in regions]

    out_path = DOCS_DIR / f"RAW_DATA_{year}_COMPLETENESS_REPORT.md"
    write_markdown_report(results, year, out_path)

    # Also print a concise verdict to stdout
    ok = [r for r in results if r.get("status") == "ok"]
    expected_days = (expected_end_utc - date(year, 1, 1)).days + 1
    all_utc_dates_ok = all(r["utc_unique_dates"] == expected_days and len(r["utc_missing_dates"]) == 0 and len(r["utc_abnormal_day_counts"]) == 0 for r in ok)

    print(f"Wrote {out_path}")
    print(f"Regions validated: {len(ok)}/{len(regions)}")
    print(f"UTC date coverage ok ({expected_days} dates, 48 slots except possible partial current UTC day): {all_utc_dates_ok}")


if __name__ == "__main__":
    main()

