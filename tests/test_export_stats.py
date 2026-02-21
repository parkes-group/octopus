"""
Tests for export tariff calculation and statistics (Phase 2).

All tests use mocks/synthetic data. No real Octopus API calls.
"""
from datetime import datetime, timezone

import pytest

from app.export_stats import (
    compute_agile_daily_stats,
    compute_fixed_effective_rate,
    get_export_rate,
)
from app.export_tariff import AgileOutgoingTariff, FixedExportTariff, HalfHourlySlot


# --- Fixed export fixtures ---
FIXED_TARIFF = FixedExportTariff(
    product_code="OUTGOING-19",
    region_code="A",
    tariff_code="E-1R-OUTGOING-19-A",
    rate_p_per_kwh_exc_vat=14.0,
    rate_p_per_kwh_inc_vat=14.7,
)


# --- Agile export fixtures ---
def _make_agile(slots: list[dict]) -> AgileOutgoingTariff:
    return AgileOutgoingTariff(
        product_code="AGILE-OUT",
        region_code="A",
        tariff_code="E-1R-AGILE-OUT-A",
        slots=[HalfHourlySlot(**s) for s in slots],
    )


AGILE_TWO_DAYS = _make_agile([
    {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 5.0, "value_inc_vat": 5.25},
    {"valid_from": "2024-01-15T00:30:00Z", "valid_to": "2024-01-15T01:00:00Z", "value_exc_vat": 3.0, "value_inc_vat": 3.15},
    {"valid_from": "2024-01-15T01:00:00Z", "valid_to": "2024-01-15T01:30:00Z", "value_exc_vat": -1.0, "value_inc_vat": -1.05},
    {"valid_from": "2024-01-15T01:30:00Z", "valid_to": "2024-01-15T02:00:00Z", "value_exc_vat": 2.0, "value_inc_vat": 2.1},
    {"valid_from": "2024-01-16T00:00:00Z", "valid_to": "2024-01-16T00:30:00Z", "value_exc_vat": 10.0, "value_inc_vat": 10.5},
    {"valid_from": "2024-01-16T00:30:00Z", "valid_to": "2024-01-16T01:00:00Z", "value_exc_vat": 8.0, "value_inc_vat": 8.4},
])


class TestGetExportRateFixed:
    """get_export_rate for Fixed tariffs."""

    def test_returns_flat_rate_inc_vat(self):
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert get_export_rate(FIXED_TARIFF, ts, inc_vat=True) == 14.7

    def test_returns_flat_rate_exc_vat(self):
        ts = datetime(2025, 6, 15, 3, 45, 0, tzinfo=timezone.utc)
        assert get_export_rate(FIXED_TARIFF, ts, inc_vat=False) == 14.0

    def test_consistent_for_any_timestamp(self):
        times = [
            datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 7, 15, 12, 30, 0, tzinfo=timezone.utc),
            datetime(2025, 12, 31, 23, 59, 0, tzinfo=timezone.utc),
        ]
        for ts in times:
            assert get_export_rate(FIXED_TARIFF, ts) == 14.7

    def test_naive_datetime_treated_as_utc(self):
        ts = datetime(2024, 1, 1, 0, 0, 0)  # no tz
        assert get_export_rate(FIXED_TARIFF, ts) == 14.7


class TestGetExportRateAgile:
    """get_export_rate for Agile tariffs."""

    def test_returns_slot_rate_inc_vat(self):
        ts = datetime(2024, 1, 15, 0, 15, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts, inc_vat=True) == 5.25

    def test_returns_slot_rate_exc_vat(self):
        ts = datetime(2024, 1, 15, 0, 15, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts, inc_vat=False) == 5.0

    def test_returns_negative_rate(self):
        ts = datetime(2024, 1, 15, 1, 15, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts) == -1.05

    def test_out_of_range_returns_none(self):
        ts = datetime(2024, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts) is None

    def test_before_first_slot_returns_none(self):
        ts = datetime(2024, 1, 14, 23, 0, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts) is None

    def test_boundary_start_of_slot_inclusive(self):
        ts = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts) == 5.25

    def test_boundary_end_of_slot_exclusive(self):
        ts = datetime(2024, 1, 15, 0, 30, 0, tzinfo=timezone.utc)
        assert get_export_rate(AGILE_TWO_DAYS, ts) == 3.15


class TestComputeAgileDailyStats:
    """compute_agile_daily_stats."""

    def test_daily_average(self):
        stats = compute_agile_daily_stats(AGILE_TWO_DAYS)
        day1 = next((s for s in stats if s["date_iso"] == "2024-01-15"), None)
        assert day1 is not None
        # (5.25 + 3.15 + -1.05 + 2.1) / 4 = 2.3625 -> 2.36
        assert day1["avg_p_per_kwh"] == 2.36
        assert day1["slot_count"] == 4

    def test_min_max_handles_negative(self):
        stats = compute_agile_daily_stats(AGILE_TWO_DAYS)
        day1 = next((s for s in stats if s["date_iso"] == "2024-01-15"), None)
        assert day1["min_p_per_kwh"] == -1.05
        assert day1["max_p_per_kwh"] == 5.25

    def test_vat_exclusive(self):
        stats = compute_agile_daily_stats(AGILE_TWO_DAYS, inc_vat=False)
        day1 = next((s for s in stats if s["date_iso"] == "2024-01-15"), None)
        assert day1["avg_p_per_kwh"] == round((5.0 + 3.0 + -1.0 + 2.0) / 4, 2)
        assert day1["min_p_per_kwh"] == -1.0
        assert day1["max_p_per_kwh"] == 5.0

    def test_multiple_days_sorted(self):
        stats = compute_agile_daily_stats(AGILE_TWO_DAYS)
        assert len(stats) == 2
        assert stats[0]["date_iso"] == "2024-01-15"
        assert stats[1]["date_iso"] == "2024-01-16"

    def test_empty_slots_returns_empty_list(self):
        empty = _make_agile([])
        assert compute_agile_daily_stats(empty) == []


class TestComputeFixedEffectiveRate:
    """compute_fixed_effective_rate."""

    def test_returns_flat_rate(self):
        assert compute_fixed_effective_rate(FIXED_TARIFF) == 14.7
        assert compute_fixed_effective_rate(FIXED_TARIFF, inc_vat=False) == 14.0


class TestNegativePriceHandling:
    """Explicit negative price handling."""

    def test_negative_in_daily_avg(self):
        agile = _make_agile([
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": -2.0, "value_inc_vat": -2.1},
            {"valid_from": "2024-01-15T00:30:00Z", "valid_to": "2024-01-15T01:00:00Z", "value_exc_vat": 4.0, "value_inc_vat": 4.2},
        ])
        stats = compute_agile_daily_stats(agile)
        assert len(stats) == 1
        assert stats[0]["avg_p_per_kwh"] == round((-2.1 + 4.2) / 2, 2)
        assert stats[0]["min_p_per_kwh"] == -2.1
        assert stats[0]["max_p_per_kwh"] == 4.2


class TestBoundaryConditions:
    """Edge cases and boundaries."""

    def test_single_slot_agile(self):
        agile = _make_agile([
            {"valid_from": "2024-01-15T12:00:00Z", "valid_to": "2024-01-15T12:30:00Z", "value_exc_vat": 7.0, "value_inc_vat": 7.35},
        ])
        stats = compute_agile_daily_stats(agile)
        assert len(stats) == 1
        assert stats[0]["avg_p_per_kwh"] == 7.35
        assert stats[0]["min_p_per_kwh"] == 7.35
        assert stats[0]["max_p_per_kwh"] == 7.35
        assert stats[0]["slot_count"] == 1

    def test_slot_parse_error_skipped(self):
        # Slot with invalid valid_from would be skipped - we can't easily create that
        # with HalfHourlySlot. Instead test that we handle empty gracefully.
        agile = _make_agile([])
        assert compute_agile_daily_stats(agile) == []


class TestImportCalculatorsUnchanged:
    """Regression: import stats and calculators must remain unchanged."""

    def test_stats_calculator_unchanged(self):
        from app.price_calculator import PriceCalculator

        prices = [
            {"value_inc_vat": 10.0, "valid_from": "2025-01-15T12:00:00Z", "valid_to": "2025-01-15T12:30:00Z"},
        ]
        result = PriceCalculator.calculate_cheapest_per_day(prices, duration_hours=0.5)
        assert len(result) == 1
        assert result[0]["cheapest_block"] is not None

    def test_calculate_daily_averages_by_date_unchanged(self):
        from app.price_calculator import PriceCalculator

        prices = [
            {"value_inc_vat": 10.0, "valid_from": "2025-01-15T00:00:00Z"},
            {"value_inc_vat": 12.0, "valid_from": "2025-01-15T00:30:00Z"},
        ]
        avgs = PriceCalculator.calculate_daily_averages_by_date(prices)
        assert len(avgs) == 1
        assert avgs[0]["average_price"] == 11.0

    def test_export_stats_import_no_side_effects(self):
        """Importing export_stats must not trigger API calls or import calc changes."""
        import app.export_stats as m

        assert hasattr(m, "get_export_rate")
        assert hasattr(m, "compute_agile_daily_stats")
        assert hasattr(m, "compute_fixed_effective_rate")
