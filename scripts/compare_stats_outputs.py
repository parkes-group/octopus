"""
Compare generated statistics against existing on-disk stats outputs for a given year.

This is intended as a lightweight backward-compatibility check after refactors:
- Recalculate stats using the current code
- Load the existing JSON outputs from data/stats/{YEAR}/
- Compare equality while ignoring timestamp fields that are expected to change
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to sys.path so `import app.*` works when executed from scripts/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import Config
from app.stats_calculator import StatsCalculator


IGNORED_TOP_LEVEL_FIELDS = {"calculation_date", "last_updated"}


def _strip_ignored(d: dict) -> dict:
    out = dict(d)
    for k in IGNORED_TOP_LEVEL_FIELDS:
        out.pop(k, None)
    return out


def load_existing(year: int, region_code: str) -> dict:
    stats_path = project_root / "data" / "stats" / str(year) / f"{region_code}_{year}.json"
    if region_code == "national":
        stats_path = project_root / "data" / "stats" / str(year) / f"national_{year}.json"
    return json.loads(stats_path.read_text(encoding="utf-8"))


def compare_dicts(label: str, baseline: dict, recalculated: dict) -> bool:
    b = _strip_ignored(baseline)
    r = _strip_ignored(recalculated)
    if b == r:
        print(f"[OK] {label} matches (excluding {', '.join(sorted(IGNORED_TOP_LEVEL_FIELDS))})")
        return True

    print(f"[ERROR] {label} mismatch (excluding {', '.join(sorted(IGNORED_TOP_LEVEL_FIELDS))})")
    all_keys = sorted(set(b.keys()) | set(r.keys()))
    for k in all_keys:
        if b.get(k) != r.get(k):
            print(f" - {k}: baseline={b.get(k)!r} recalculated={r.get(k)!r}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare recalculated stats against existing on-disk stats")
    parser.add_argument("--year", "-y", type=int, default=2025, help="Year (default: 2025)")
    parser.add_argument("--region", "-r", type=str, default="A", help="Region code to compare (default: A)")
    parser.add_argument("--product", "-p", type=str, default=Config.OCTOPUS_PRODUCT_CODE, help="Product code")
    parser.add_argument("--national", action="store_true", help="Also compare national_{YEAR}.json")
    args = parser.parse_args()

    year = args.year
    product = args.product
    region = args.region

    baseline_region = load_existing(year, region)
    if year == 2025:
        recalculated_region = StatsCalculator.calculate_2025_stats(product_code=product, region_code=region)
    else:
        current_year_utc = datetime.now(timezone.utc).year
        coverage = "year_to_date" if year == current_year_utc else "full_year"
        recalculated_region = StatsCalculator.calculate_year_stats(product_code=product, region_code=region, year=year, coverage=coverage)

    ok = compare_dicts(f"Region {region} ({year})", baseline_region, recalculated_region)

    if args.national:
        baseline_nat = load_existing(year, "national")
        recalculated_nat = StatsCalculator.calculate_national_averages(product_code=product, year=year)
        ok = compare_dicts(f"National ({year})", baseline_nat, recalculated_nat) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

