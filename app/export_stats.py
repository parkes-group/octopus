"""
Export tariff calculation and statistics.

Phase 2: Compute export metrics from Fixed and Agile Outgoing tariffs.
No API calls on import. Intended for:
- Export-only pages
- Import vs export comparisons
- Combined household import/export analysis

Does NOT modify existing import calculators or stats.

Export block semantics (mirrors import calculate_cheapest_per_day):
- best_block = highest rate block for the day (import: cheapest = lowest)
- worst_block = lowest rate block for the day (import: worst = highest)
- best_remaining_block = next highest block from remaining slots today (import: cheapest_remaining)
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Union

from app.export_tariff import AgileOutgoingTariff, FixedExportTariff, HalfHourlySlot
from app.price_calculator import PriceCalculator
from app.timezone_utils import utc_to_uk, get_uk_now

ExportTariff = Union[FixedExportTariff, AgileOutgoingTariff]

# Default block duration and capacity for export (matches import prices page)
EXPORT_BLOCK_DURATION_HOURS = 3.5
EXPORT_DEFAULT_CAPACITY_KWH = 10.0


def get_export_rate(
    tariff: ExportTariff,
    utc_timestamp: datetime,
    inc_vat: bool = True,
) -> float | None:
    """
    Return export rate p/kWh for the given timestamp.

    For Fixed: always returns the flat rate (same for any timestamp).
    For Agile: returns the half-hour slot rate, or None if out of range.

    Args:
        tariff: FixedExportTariff or AgileOutgoingTariff
        utc_timestamp: Timestamp (UTC); naive datetimes treated as UTC
        inc_vat: If True return inc-VAT rate, else exc-VAT

    Returns:
        Rate in pence per kWh, or None if no slot for that time (Agile only)
    """
    ts = utc_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if isinstance(tariff, FixedExportTariff):
        return tariff.effective_rate_p_per_kwh(inc_vat=inc_vat)

    if isinstance(tariff, AgileOutgoingTariff):
        slot = tariff.slot_at(ts)
        if slot is None:
            return None
        return slot.value_inc_vat if inc_vat else slot.value_exc_vat

    return None


def compute_agile_daily_stats(
    tariff: AgileOutgoingTariff,
    inc_vat: bool = True,
) -> list[dict]:
    """
    Compute per-day statistics for an Agile Outgoing tariff.

    Groups slots by UK calendar date (matches import stats pattern).
    Handles negative prices correctly (included in avg, min, max).

    Args:
        tariff: AgileOutgoingTariff with slots
        inc_vat: Use VAT-inclusive rates

    Returns:
        List of dicts with date_iso, date_display, avg_p_per_kwh, min_p_per_kwh,
        max_p_per_kwh, slot_count. Sorted by date ascending.
    """
    if not tariff.slots:
        return []

    # Group slots by UK date (reuse timezone pattern from import)
    by_date: dict[date, list[float]] = defaultdict(list)
    for slot in tariff.slots:
        try:
            dt_uk = utc_to_uk(slot.valid_from)
            date_key = dt_uk.date()
            rate = slot.value_inc_vat if inc_vat else slot.value_exc_vat
            by_date[date_key].append(rate)
        except (ValueError, AttributeError, KeyError):
            continue

    results = []
    for date_obj in sorted(by_date.keys()):
        rates = by_date[date_obj]
        if not rates:
            continue
        results.append({
            "date_iso": date_obj.strftime("%Y-%m-%d"),
            "date_display": date_obj.strftime("%d/%m/%y"),
            "avg_p_per_kwh": round(sum(rates) / len(rates), 2),
            "min_p_per_kwh": round(min(rates), 2),
            "max_p_per_kwh": round(max(rates), 2),
            "slot_count": len(rates),
        })

    return results


def compute_fixed_effective_rate(
    tariff: FixedExportTariff,
    inc_vat: bool = True,
) -> float:
    """
    Return the flat export rate for a Fixed tariff.

    Same rate for any timestamp. Convenience wrapper for consistency
    with the get_export_rate interface.
    """
    return tariff.effective_rate_p_per_kwh(inc_vat=inc_vat)


def _slots_to_price_dicts(slots: list[HalfHourlySlot], inc_vat: bool) -> list[dict]:
    """Convert AgileOutgoingTariff slots to format expected by PriceCalculator."""
    result = []
    for s in slots:
        val = s.value_inc_vat if inc_vat else s.value_exc_vat
        result.append({
            "value_inc_vat": val,
            "valid_from": s.valid_from,
            "valid_to": s.valid_to,
        })
    return result


def compute_export_blocks(
    tariff: AgileOutgoingTariff,
    duration_hours: float = EXPORT_BLOCK_DURATION_HOURS,
    inc_vat: bool = True,
    current_time_utc: datetime | None = None,
) -> dict | None:
    """
    Compute best, worst, and best-remaining blocks for export (Agile Outgoing).

    For export: best = highest rate, worst = lowest rate, best_remaining = next highest from now.

    Returns:
        dict with best_block, worst_block, best_remaining_block, daily_avg, current_time_uk;
        or None if no slots.
    """
    if not tariff.slots:
        return None

    if current_time_utc is None:
        current_time_utc = get_uk_now().astimezone(timezone.utc)
    if current_time_utc.tzinfo is None:
        current_time_utc = current_time_utc.replace(tzinfo=timezone.utc)

    prices = _slots_to_price_dicts(tariff.slots, inc_vat)
    if not prices:
        return None

    # Best block = highest rate (like find_worst_block for import)
    best_block = PriceCalculator.find_worst_block(prices, duration_hours)
    # Worst block = lowest rate (like find_cheapest_block for import)
    worst_block = PriceCalculator.find_cheapest_block(prices, duration_hours)
    # Best remaining = highest rate from now onwards
    best_remaining_block = PriceCalculator.find_future_worst_block(
        prices, duration_hours, current_time_utc
    )

    # Daily average for today (UK date)
    today_uk = get_uk_now().date()
    today_rates = [
        p["value_inc_vat"] for p in prices
        if utc_to_uk(p["valid_from"]).date() == today_uk
    ]
    daily_avg = round(sum(today_rates) / len(today_rates), 2) if today_rates else None

    return {
        "best_block": best_block,
        "worst_block": worst_block,
        "best_remaining_block": best_remaining_block,
        "daily_avg": daily_avg,
        "current_time_uk": get_uk_now(),
    }


def calculate_export_blocks_per_day(
    prices: list[dict],
    duration_hours: float,
    current_time_utc: datetime | None = None,
) -> list[dict]:
    """
    Calculate best, worst, and best-remaining export blocks per calendar day.

    Mirrors PriceCalculator.calculate_cheapest_per_day for import, but with export semantics:
    - best_block = highest rate block for the day (find_worst_block)
    - worst_block = lowest rate block for the day (find_cheapest_block)
    - best_remaining_block = next highest block from remaining slots (exclude best, valid_to > now)

    Args:
        prices: List of price dicts with value_inc_vat, valid_from, valid_to
        duration_hours: Block duration in hours
        current_time_utc: Current time UTC (for remaining block calculation)

    Returns:
        List of dicts per day: date, date_iso, date_display, min_price, max_price,
        best_block, worst_block, best_remaining_block
    """
    if not prices:
        return []

    today_uk = get_uk_now().date()
    prices = PriceCalculator.filter_prices_from_uk_date(prices, today_uk)
    if not prices:
        return []

    prices_by_date = PriceCalculator.group_prices_by_date(prices)
    results = []

    for date_obj in sorted(prices_by_date.keys()):
        day_prices = sorted(prices_by_date[date_obj], key=lambda x: x.get("valid_from", ""))

        best_block = PriceCalculator.find_worst_block(day_prices, duration_hours)
        worst_block = PriceCalculator.find_cheapest_block(day_prices, duration_hours)

        min_price = None
        max_price = None
        if day_prices:
            vals = [p["value_inc_vat"] for p in day_prices if "value_inc_vat" in p]
            if vals:
                min_price = min(vals)
                max_price = max(vals)

        best_remaining_block = None
        if current_time_utc and best_block and best_block.get("slots"):
            best_block_slots_utc = {slot["valid_from"] for slot in best_block["slots"]}

            remaining_prices = []
            remaining_prices_future = []
            for price in day_prices:
                try:
                    vf = price["valid_from"]
                    vt = price["valid_to"]
                    dt_str = (vf or "").replace("Z", "+00:00") if isinstance(vf, str) else vf
                    to_str = (vt or "").replace("Z", "+00:00") if isinstance(vt, str) else vt
                    price_time_utc = datetime.fromisoformat(dt_str)
                    price_end_utc = datetime.fromisoformat(to_str)
                    if price_time_utc.tzinfo is None:
                        price_time_utc = price_time_utc.replace(tzinfo=timezone.utc)
                    if price_end_utc.tzinfo is None:
                        price_end_utc = price_end_utc.replace(tzinfo=timezone.utc)

                    if price["valid_from"] in best_block_slots_utc:
                        continue
                    if price_end_utc > current_time_utc:
                        remaining_prices.append(price)
                        if price_time_utc >= current_time_utc:
                            remaining_prices_future.append(price)
                except (KeyError, ValueError, TypeError):
                    continue

            remaining_prices.sort(key=lambda x: x.get("valid_from", ""))
            remaining_prices_future.sort(key=lambda x: x.get("valid_from", ""))

            requested_slots = int(duration_hours * 2)
            MAX_PAST_FRACTION = 0.20

            def _calc_block(pool):
                if not pool:
                    return None, None
                max_slots = min(requested_slots, len(pool))
                for slots_try in range(max_slots, 0, -1):
                    duration_try = slots_try / 2.0
                    candidate = PriceCalculator.find_worst_block(pool, duration_try)
                    if candidate:
                        return candidate, slots_try
                return None, None

            best_remaining_block, slots_used = _calc_block(remaining_prices)

            if best_remaining_block and slots_used is not None:
                try:
                    start_val = best_remaining_block.get("start_time") or (
                        best_remaining_block.get("slots") or [{}]
                    )[0].get("valid_from")
                    if start_val:
                        if isinstance(start_val, datetime):
                            start_utc = start_val if start_val.tzinfo else start_val.replace(tzinfo=timezone.utc)
                        else:
                            start_dt_str = (str(start_val) or "").replace("Z", "+00:00")
                            start_utc = datetime.fromisoformat(start_dt_str)
                            if start_utc.tzinfo is None:
                                start_utc = start_utc.replace(tzinfo=timezone.utc)
                        elapsed_seconds = max(0.0, (current_time_utc - start_utc).total_seconds())
                        duration_seconds = (slots_used / 2.0) * 3600.0
                        past_fraction = (elapsed_seconds / duration_seconds) if duration_seconds > 0 else 0.0
                        if past_fraction > MAX_PAST_FRACTION:
                            best_remaining_block, slots_used = _calc_block(remaining_prices_future)
                except Exception:
                    pass

        date_display = date_obj.strftime("%d/%m/%y")
        results.append({
            "date": date_obj,
            "date_iso": date_obj.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "min_price": min_price,
            "max_price": max_price,
            "best_block": best_block,
            "worst_block": worst_block,
            "best_remaining_block": best_remaining_block,
        })

    return results
