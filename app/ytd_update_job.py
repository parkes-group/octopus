"""
Year-to-date (YTD) update job helpers.

These helpers are used by the scheduled task script:
`scripts/update_ytd_prices_and_stats.py`.

Design goals:
- Reuse existing Octopus API + cache expiry logic patterns
- Incremental updates (no full-year refetch)
- Safe to re-run (dedupe + stable ordering)
- Easy to unit test (pure helpers where possible)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time, date
from typing import Iterable, Optional

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

UK_TZ = ZoneInfo("Europe/London")


def parse_utc_iso_z(ts: str) -> datetime:
    """
    Parse ISO-8601 strings like '2026-01-15T19:00:00Z' into an aware UTC datetime.
    """
    if not ts:
        raise ValueError("Empty timestamp")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def dt_to_utc_z(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt_utc.isoformat().replace("+00:00", "Z")


def end_of_uk_day_exclusive_utc(day_uk: date) -> datetime:
    """
    Return the UTC datetime corresponding to the *start* of the next UK-local day.
    This is suitable as an exclusive 'period_to' boundary.
    """
    start_next_uk = datetime.combine(day_uk + timedelta(days=1), time(0, 0)).replace(tzinfo=UK_TZ)
    return start_next_uk.astimezone(timezone.utc)


def latest_valid_to_utc(prices: list[dict]) -> Optional[datetime]:
    if not prices:
        return None
    # Prices should already be chronological, but be defensive.
    latest = max(prices, key=lambda p: p.get("valid_to", "")).get("valid_to")
    return parse_utc_iso_z(latest) if latest else None


def prices_include_tomorrow_edge(prices: list[dict], *, now_uk: datetime) -> bool:
    """
    Determine whether a price list includes "tomorrow" prices in UK local date terms,
    using only edge entries (first and last), matching the cache expiry decision approach.
    """
    if not prices:
        return False
    first = prices[0]
    last = prices[-1]
    # Use valid_from for "which day is covered" checks: a "today-only" dataset ends at 00:00 tomorrow
    # but the final slot still belongs to today (valid_from at 23:30 today).
    first_uk = parse_utc_iso_z(first.get("valid_from", "")).astimezone(UK_TZ)
    last_uk = parse_utc_iso_z(last.get("valid_from", "")).astimezone(UK_TZ)
    today_uk = now_uk.astimezone(UK_TZ).date()
    return first_uk.date() > today_uk or last_uk.date() > today_uk


@dataclass(frozen=True)
class FetchPlan:
    region: str
    period_from_utc_z: str
    period_to_utc_z: str
    reason: str


def determine_fetch_plan(
    *,
    region: str,
    existing_prices: list[dict],
    now_uk: datetime,
) -> Optional[FetchPlan]:
    """
    Determine the incremental Octopus fetch window for YTD raw updates.

    Rules:
    - If data already includes tomorrow (UK date), do not fetch.
    - If data only covers today, fetch through end of tomorrow UK day.
    - If missing >1 UK day (gap), fetch from last_valid_to forward through end of tomorrow UK day.
    """
    now_uk = now_uk.astimezone(UK_TZ)
    today_uk = now_uk.date()
    tomorrow_uk = today_uk + timedelta(days=1)

    if existing_prices and prices_include_tomorrow_edge(existing_prices, now_uk=now_uk):
        return None

    last_to = latest_valid_to_utc(existing_prices)
    if last_to is None:
        # Fresh file / missing: start at year boundary (caller can choose year start; here we use "now" day start)
        # For safety we start at the beginning of the current UK day.
        start_today_uk = datetime.combine(today_uk, time(0, 0)).replace(tzinfo=UK_TZ).astimezone(timezone.utc)
        period_from = start_today_uk
        period_to = end_of_uk_day_exclusive_utc(tomorrow_uk)
        return FetchPlan(region=region, period_from_utc_z=dt_to_utc_z(period_from), period_to_utc_z=dt_to_utc_z(period_to), reason="no_existing_data_fetch_today_and_tomorrow")

    last_to_uk_date = last_to.astimezone(UK_TZ).date()
    if last_to_uk_date <= today_uk - timedelta(days=2):
        # Gap of >=2 days in UK-local terms
        period_to = end_of_uk_day_exclusive_utc(tomorrow_uk)
        return FetchPlan(region=region, period_from_utc_z=dt_to_utc_z(last_to), period_to_utc_z=dt_to_utc_z(period_to), reason="gap_fetch_from_last_to_through_tomorrow")

    # Covers today but not tomorrow → fetch today + tomorrow
    period_to = end_of_uk_day_exclusive_utc(tomorrow_uk)
    return FetchPlan(region=region, period_from_utc_z=dt_to_utc_z(last_to), period_to_utc_z=dt_to_utc_z(period_to), reason="covers_today_fetch_today_and_tomorrow")


def dedupe_sort_prices(prices: Iterable[dict]) -> list[dict]:
    """
    De-duplicate by valid_from and return prices sorted chronologically by valid_from.
    """
    seen: dict[str, dict] = {}
    for p in prices:
        vf = p.get("valid_from")
        if not vf:
            continue
        # First win is fine; duplicates should be identical.
        if vf not in seen:
            seen[vf] = p
    return sorted(seen.values(), key=lambda x: x.get("valid_from", ""))


def validate_price_series(prices: list[dict]) -> list[str]:
    """
    Validate that prices are:
    - Strictly increasing in time
    - Contiguous in 30-minute steps (valid_from == prev.valid_to)
    - No duplicate valid_from timestamps
    """
    errors: list[str] = []
    if not prices:
        return errors

    # Ensure chronological order
    prices_sorted = sorted(prices, key=lambda p: p.get("valid_from", ""))

    seen = set()
    prev_to: Optional[datetime] = None
    prev_from: Optional[datetime] = None
    for idx, p in enumerate(prices_sorted):
        vf_s = p.get("valid_from")
        vt_s = p.get("valid_to")
        if not vf_s or not vt_s:
            errors.append(f"missing valid_from/valid_to at index={idx}")
            continue

        if vf_s in seen:
            errors.append(f"duplicate valid_from {vf_s}")
        seen.add(vf_s)

        vf = parse_utc_iso_z(vf_s)
        vt = parse_utc_iso_z(vt_s)

        if prev_from and vf <= prev_from:
            errors.append(f"backwards_or_equal_time at {vf_s}")
        if vt <= vf:
            errors.append(f"invalid_interval {vf_s} -> {vt_s}")

        if prev_to is not None:
            # Contiguity: expect this slot to start exactly at previous slot end.
            if vf != prev_to:
                delta = (vf - prev_to).total_seconds() / 60.0
                errors.append(f"gap_or_overlap between {dt_to_utc_z(prev_to)} and {vf_s} (delta_minutes={delta})")

        # Ensure slot duration is 30 minutes
        dur_minutes = (vt - vf).total_seconds() / 60.0
        if abs(dur_minutes - 30.0) > 0.001:
            errors.append(f"unexpected_slot_duration {vf_s}->{vt_s} ({dur_minutes}m)")

        prev_from = vf
        prev_to = vt

    return errors


def expected_slot_count(period_from_utc_z: str, period_to_utc_z: str) -> int:
    """
    Expected number of 30-minute slots in [period_from, period_to) if perfectly aligned.
    """
    start = parse_utc_iso_z(period_from_utc_z)
    end = parse_utc_iso_z(period_to_utc_z)
    if end <= start:
        return 0
    delta_minutes = (end - start).total_seconds() / 60.0
    return int(delta_minutes // 30)

