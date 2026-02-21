"""
Export tariff calculation and statistics.

Phase 2: Compute export metrics from Fixed and Agile Outgoing tariffs.
No API calls on import. Intended for:
- Export-only pages
- Import vs export comparisons
- Combined household import/export analysis

Does NOT modify existing import calculators or stats.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Union

from app.export_tariff import AgileOutgoingTariff, FixedExportTariff
from app.timezone_utils import utc_to_uk

ExportTariff = Union[FixedExportTariff, AgileOutgoingTariff]


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
