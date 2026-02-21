"""
Tests for export tariff domain model.

Phase 1: Fixed and Agile Outgoing tariff behaviour.
"""
from datetime import datetime, timezone

import pytest

from app.export_tariff import (
    AgileOutgoingTariff,
    ExportProduct,
    FixedExportTariff,
    HalfHourlySlot,
)


class TestExportProduct:
    """Export product discovery model."""

    def test_valid_agile_outgoing(self):
        p = ExportProduct(
            code="AGILE-OUTGOING-19-05-13",
            display_name="Agile Outgoing Octopus",
            tariff_type="agile_outgoing",
            full_name="Agile Outgoing Octopus",
        )
        assert p.tariff_type == "agile_outgoing"

    def test_valid_fixed(self):
        p = ExportProduct(
            code="OUTGOING-19-05-13",
            display_name="Outgoing Octopus",
            tariff_type="fixed",
        )
        assert p.tariff_type == "fixed"

    def test_invalid_tariff_type_raises(self):
        with pytest.raises(ValueError, match="Invalid tariff_type"):
            ExportProduct(
                code="X",
                display_name="X",
                tariff_type="invalid",
            )


class TestFixedExportTariff:
    """Fixed export tariff (flat rate)."""

    def test_effective_rate_inc_vat(self):
        t = FixedExportTariff(
            product_code="OUTGOING-19",
            region_code="A",
            tariff_code="E-1R-OUTGOING-19-A",
            rate_p_per_kwh_exc_vat=14.0,
            rate_p_per_kwh_inc_vat=14.7,
        )
        assert t.effective_rate_p_per_kwh(inc_vat=True) == 14.7

    def test_effective_rate_exc_vat(self):
        t = FixedExportTariff(
            product_code="OUTGOING-19",
            region_code="A",
            tariff_code="E-1R-OUTGOING-19-A",
            rate_p_per_kwh_exc_vat=14.0,
            rate_p_per_kwh_inc_vat=14.7,
        )
        assert t.effective_rate_p_per_kwh(inc_vat=False) == 14.0

    def test_not_time_series(self):
        """Fixed tariff returns same rate for any timestamp."""
        t = FixedExportTariff(
            product_code="OUTGOING-19",
            region_code="A",
            tariff_code="E-1R-OUTGOING-19-A",
            rate_p_per_kwh_exc_vat=15.0,
            rate_p_per_kwh_inc_vat=15.75,
        )
        # Should return same rate regardless of when queried
        assert t.effective_rate_p_per_kwh() == 15.75


class TestAgileOutgoingTariff:
    """Agile Outgoing half-hourly tariff."""

    def test_slot_at_finds_correct_slot(self):
        slots = [
            HalfHourlySlot(
                valid_from="2024-01-15T12:00:00Z",
                valid_to="2024-01-15T12:30:00Z",
                value_exc_vat=5.0,
                value_inc_vat=5.25,
            ),
            HalfHourlySlot(
                valid_from="2024-01-15T12:30:00Z",
                valid_to="2024-01-15T13:00:00Z",
                value_exc_vat=-2.0,
                value_inc_vat=-2.1,
            ),
        ]
        t = AgileOutgoingTariff(
            product_code="AGILE-OUT",
            region_code="A",
            tariff_code="E-1R-AGILE-OUT-A",
            slots=slots,
        )
        # Timestamp in first slot
        ts = datetime(2024, 1, 15, 12, 15, 0, tzinfo=timezone.utc)
        s = t.slot_at(ts)
        assert s is not None
        assert s.value_inc_vat == 5.25
        # Timestamp in second slot (negative price)
        ts2 = datetime(2024, 1, 15, 12, 45, 0, tzinfo=timezone.utc)
        s2 = t.slot_at(ts2)
        assert s2 is not None
        assert s2.value_inc_vat == -2.1

    def test_slot_at_returns_none_outside_range(self):
        slots = [
            HalfHourlySlot(
                valid_from="2024-01-15T12:00:00Z",
                valid_to="2024-01-15T12:30:00Z",
                value_exc_vat=5.0,
                value_inc_vat=5.25,
            ),
        ]
        t = AgileOutgoingTariff(
            product_code="AGILE-OUT",
            region_code="A",
            tariff_code="E-1R-AGILE-OUT-A",
            slots=slots,
        )
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert t.slot_at(ts) is None

    def test_handles_negative_prices(self):
        """Agile Outgoing can have negative prices."""
        slot = HalfHourlySlot(
            valid_from="2024-01-15T03:00:00Z",
            valid_to="2024-01-15T03:30:00Z",
            value_exc_vat=-1.5,
            value_inc_vat=-1.575,
        )
        assert slot.value_inc_vat < 0
        assert slot.value_exc_vat < 0

    def test_slots_align_utc_half_hour(self):
        """Slots are 30-minute UTC intervals."""
        slot = HalfHourlySlot(
            valid_from="2024-01-15T00:00:00Z",
            valid_to="2024-01-15T00:30:00Z",
            value_exc_vat=10.0,
            value_inc_vat=10.5,
        )
        from datetime import datetime

        start = datetime.fromisoformat(slot.valid_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(slot.valid_to.replace("Z", "+00:00"))
        assert (end - start).total_seconds() == 1800
