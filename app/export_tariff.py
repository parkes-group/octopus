"""
Export tariff domain model.

Supports two export tariff types:
- Fixed Export (Outgoing Octopus): flat rate, no time-of-use variation
- Agile Outgoing: half-hourly prices, mirrors wholesale market

Phase 1: backend + domain only. No UI, no combined import/export maths.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ExportTariffType = Literal["fixed", "agile_outgoing"]


@dataclass(frozen=True)
class ExportProduct:
    """Discovered export product from Octopus API."""

    code: str
    display_name: str
    tariff_type: ExportTariffType
    full_name: str | None = None

    def __post_init__(self) -> None:
        if self.tariff_type not in ("fixed", "agile_outgoing"):
            raise ValueError(f"Invalid tariff_type: {self.tariff_type}")


@dataclass
class FixedExportTariff:
    """
    Fixed export tariff (e.g. Outgoing Octopus).

    Single rate for all times. Not a time-series.
    """

    product_code: str
    region_code: str
    tariff_code: str
    rate_p_per_kwh_exc_vat: float
    rate_p_per_kwh_inc_vat: float

    def effective_rate_p_per_kwh(self, inc_vat: bool = True) -> float:
        """Return the flat rate for any timestamp (no time-of-use variation)."""
        return self.rate_p_per_kwh_inc_vat if inc_vat else self.rate_p_per_kwh_exc_vat


@dataclass
class HalfHourlySlot:
    """Single half-hour price slot (UTC)."""

    valid_from: str
    valid_to: str
    value_exc_vat: float
    value_inc_vat: float


@dataclass
class AgileOutgoingTariff:
    """
    Agile Outgoing export tariff.

    Half-hourly time-series. Aligns to UTC 30-minute settlement periods.
    Handles negative prices.
    """

    product_code: str
    region_code: str
    tariff_code: str
    slots: list[HalfHourlySlot]

    def slot_at(self, utc_timestamp: datetime) -> HalfHourlySlot | None:
        """
        Return the slot that contains the given UTC timestamp, or None.
        """
        from datetime import timezone

        ts = utc_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        for slot in self.slots:
            try:
                start = datetime.fromisoformat(slot.valid_from.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(slot.valid_to.replace("Z", "+00:00"))
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                if start <= ts < end:
                    return slot
            except (ValueError, AttributeError):
                continue
        return None
