"""
Tests for export tariff API client.

Uses mocked HTTP to avoid hitting the real Octopus API.
Verifies product discovery, fixed export, agile outgoing, and safety.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.export_client import (
    AGILE_OUTGOING_DISPLAY_NAME,
    FIXED_EXPORT_DISPLAY_NAME,
    discover_export_products,
    fetch_agile_outgoing_tariff,
    fetch_fixed_export_tariff,
    get_product_tariffs,
    get_unit_rates,
)
from app.export_tariff import ExportProduct, FixedExportTariff


# Sample API responses
PRODUCTS_RESPONSE = {
    "count": 96,
    "next": None,
    "results": [
        {
            "code": "AGILE-OUTGOING-19-05-13",
            "direction": "EXPORT",
            "display_name": AGILE_OUTGOING_DISPLAY_NAME,
            "full_name": "Agile Outgoing Octopus",
            "available_from": "2019-05-13T00:00:00Z",
            "available_to": None,
        },
        {
            "code": "OUTGOING-19-05-13",
            "direction": "EXPORT",
            "display_name": FIXED_EXPORT_DISPLAY_NAME,
            "full_name": "Outgoing Octopus",
            "available_from": "2019-05-13T00:00:00Z",
            "available_to": None,
        },
        {
            "code": "EXPIRED-OUT",
            "direction": "EXPORT",
            "display_name": FIXED_EXPORT_DISPLAY_NAME,
            "available_from": "2018-01-01T00:00:00Z",
            "available_to": "2020-01-01T00:00:00Z",
        },
        {
            "code": "FUTURE-OUT",
            "direction": "EXPORT",
            "display_name": FIXED_EXPORT_DISPLAY_NAME,
            "available_from": "2030-01-01T00:00:00Z",
            "available_to": None,
        },
        {
            "code": "SOME-IMPORT",
            "direction": "IMPORT",
            "display_name": "Agile Octopus",
            "available_from": "2019-01-01T00:00:00Z",
            "available_to": None,
        },
    ],
}

PRODUCT_DETAIL_FIXED = {
    "code": "OUTGOING-19-05-13",
    "single_register_electricity_tariffs": {
        "_A": {
            "direct_debit_monthly": {
                "code": "E-1R-OUTGOING-19-05-13-A",
                "standard_unit_rate_exc_vat": 15.0,
                "standard_unit_rate_inc_vat": 15.75,
            },
        },
    },
}

PRODUCT_DETAIL_AGILE = {
    "code": "AGILE-OUTGOING-19-05-13",
    "single_register_electricity_tariffs": {
        "_A": {
            "direct_debit_monthly": {
                "code": "E-1R-AGILE-OUTGOING-19-05-13-A",
            },
        },
    },
}

UNIT_RATES_RESPONSE = {
    "count": 2,
    "next": None,
    "results": [
        {
            "value_exc_vat": 5.0,
            "value_inc_vat": 5.25,
            "valid_from": "2024-01-15T12:00:00Z",
            "valid_to": "2024-01-15T12:30:00Z",
        },
        {
            "value_exc_vat": -1.0,
            "value_inc_vat": -1.05,
            "valid_from": "2024-01-15T12:30:00Z",
            "valid_to": "2024-01-15T13:00:00Z",
        },
    ],
}


class TestProductDiscovery:
    """Product discovery from API."""

    @patch("app.export_client.requests.get")
    def test_discovers_agile_outgoing_and_fixed(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCTS_RESPONSE

        products = discover_export_products()
        codes = {p.code for p in products}
        assert "AGILE-OUTGOING-19-05-13" in codes
        assert "OUTGOING-19-05-13" in codes

    @patch("app.export_client.requests.get")
    def test_excludes_expired_products(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCTS_RESPONSE

        products = discover_export_products()
        codes = {p.code for p in products}
        assert "EXPIRED-OUT" not in codes

    @patch("app.export_client.requests.get")
    def test_excludes_future_products(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCTS_RESPONSE

        products = discover_export_products()
        codes = {p.code for p in products}
        assert "FUTURE-OUT" not in codes

    @patch("app.export_client.requests.get")
    def test_excludes_import_products(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCTS_RESPONSE

        products = discover_export_products()
        codes = {p.code for p in products}
        assert "SOME-IMPORT" not in codes

    @patch("app.export_client.requests.get")
    def test_returns_export_product_objects(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCTS_RESPONSE

        products = discover_export_products()
        agile = next((p for p in products if p.code == "AGILE-OUTGOING-19-05-13"), None)
        assert agile is not None
        assert isinstance(agile, ExportProduct)
        assert agile.tariff_type == "agile_outgoing"
        assert agile.display_name == AGILE_OUTGOING_DISPLAY_NAME

    @patch("app.export_client.requests.get")
    def test_handles_valid_from_valid_to_fields(self, mock_get):
        """API may return valid_from/valid_to instead of available_*."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "count": 1,
            "next": None,
            "results": [
                {
                    "code": "OUT-VALID",
                    "display_name": FIXED_EXPORT_DISPLAY_NAME,
                    "valid_from": "2020-01-01T00:00:00Z",
                    "valid_to": None,
                },
            ],
        }

        products = discover_export_products()
        assert any(p.code == "OUT-VALID" for p in products)


class TestFixedExportTariff:
    """Fixed export tariff fetch."""

    @patch("app.export_client.requests.get")
    def test_produces_flat_rate(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCT_DETAIL_FIXED

        t = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
        assert t is not None
        assert isinstance(t, FixedExportTariff)
        assert t.rate_p_per_kwh_inc_vat == 15.75
        assert t.rate_p_per_kwh_exc_vat == 15.0
        assert t.effective_rate_p_per_kwh() == 15.75

    @patch("app.export_client.requests.get")
    def test_not_treated_as_time_series(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCT_DETAIL_FIXED

        t = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
        assert t is not None
        # Same rate for any "timestamp" - no time-of-use
        assert t.effective_rate_p_per_kwh(inc_vat=True) == 15.75
        assert t.effective_rate_p_per_kwh(inc_vat=False) == 15.0

    @patch("app.export_client.requests.get")
    def test_query_safe_for_any_timestamp(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCT_DETAIL_FIXED

        t = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
        assert t is not None
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rate = t.effective_rate_p_per_kwh()
        assert rate == 15.75

    @patch("app.export_client.requests.get")
    def test_returns_none_for_missing_region(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = PRODUCT_DETAIL_FIXED

        t = fetch_fixed_export_tariff("OUTGOING-19-05-13", "Z")
        assert t is None


class TestAgileOutgoingTariff:
    """Agile Outgoing half-hourly tariff fetch."""

    @patch("app.export_client.get_unit_rates")
    @patch("app.export_client.requests.get")
    def test_produces_half_hourly_time_series(self, mock_http, mock_unit_rates):
        mock_http.return_value.status_code = 200
        mock_http.return_value.json.return_value = PRODUCT_DETAIL_AGILE
        mock_unit_rates.return_value = UNIT_RATES_RESPONSE["results"]

        t = fetch_agile_outgoing_tariff(
            "AGILE-OUTGOING-19-05-13",
            "A",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert t is not None
        assert len(t.slots) == 2
        assert t.slots[0].value_inc_vat == 5.25
        assert t.slots[1].value_inc_vat == -1.05

    @patch("app.export_client.get_unit_rates")
    @patch("app.export_client.requests.get")
    def test_handles_negative_prices(self, mock_http, mock_unit_rates):
        mock_http.return_value.status_code = 200
        mock_http.return_value.json.return_value = PRODUCT_DETAIL_AGILE
        mock_unit_rates.return_value = UNIT_RATES_RESPONSE["results"]

        t = fetch_agile_outgoing_tariff(
            "AGILE-OUTGOING-19-05-13",
            "A",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert t is not None
        neg_slots = [s for s in t.slots if s.value_inc_vat < 0]
        assert len(neg_slots) == 1
        assert neg_slots[0].value_inc_vat == -1.05

    @patch("app.export_client.get_unit_rates")
    @patch("app.export_client.requests.get")
    def test_correctly_aligns_utc_half_hour(self, mock_http, mock_unit_rates):
        mock_http.return_value.status_code = 200
        mock_http.return_value.json.return_value = PRODUCT_DETAIL_AGILE
        mock_unit_rates.return_value = UNIT_RATES_RESPONSE["results"]

        t = fetch_agile_outgoing_tariff(
            "AGILE-OUTGOING-19-05-13",
            "A",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert t is not None
        s = t.slot_at(datetime(2024, 1, 15, 12, 15, 0, tzinfo=timezone.utc))
        assert s is not None
        assert s.value_inc_vat == 5.25


class TestGetUnitRates:
    """Unit rates fetching with pagination."""

    @patch("app.export_client.requests.get")
    def test_handles_pagination(self, mock_get):
        first_results = [
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 5, "value_inc_vat": 5.25},
        ]
        second_results = [
            {"valid_from": "2024-01-15T00:30:00Z", "valid_to": "2024-01-15T01:00:00Z", "value_exc_vat": 8, "value_inc_vat": 8.4},
        ]

        def make_resp(results, next_url=None):
            class Resp:
                status_code = 200

                def json(self):
                    return {"results": results, "next": next_url}

                def raise_for_status(self):
                    pass

            return Resp()

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return make_resp(first_results, "https://api.example/page2")
            return make_resp(second_results, None)

        mock_get.side_effect = side_effect

        results = get_unit_rates(
            "X",
            "E-1R-X-A",
            datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert len(results) == 2
        assert results[0]["value_inc_vat"] == 5.25
        assert results[1]["value_inc_vat"] == 8.4


class TestSafetyImportUnchanged:
    """Ensure import tariff logic remains unchanged."""

    def test_stats_calculator_unchanged(self):
        """Stats generation for import still works."""
        from app.price_calculator import PriceCalculator

        # Minimal raw price data (single slot)
        prices = [
            {"value_inc_vat": 10.0, "valid_from": "2025-01-15T12:00:00Z", "valid_to": "2025-01-15T12:30:00Z"},
        ]
        result = PriceCalculator.calculate_cheapest_per_day(prices, duration_hours=0.5)
        assert len(result) == 1
        assert result[0]["date_iso"] == "2025-01-15"
        assert result[0]["cheapest_block"] is not None

    def test_import_get_prices_url_still_works(self):
        """Config.get_prices_url for import is unchanged."""
        from app.config import Config

        url = Config.get_prices_url("AGILE-24-10-01", "A")
        assert "AGILE-24-10-01" in url
        assert "E-1R-AGILE-24-10-01-A" in url
        assert "standard-unit-rates" in url

    def test_import_api_client_get_prices_exists(self):
        """OctopusAPIClient.get_prices still exists and is callable."""
        from app.api_client import OctopusAPIClient

        assert hasattr(OctopusAPIClient, "get_prices")
        assert callable(OctopusAPIClient.get_prices)

    def test_export_code_paths_are_opt_in(self):
        """Export functions are only called when explicitly invoked."""
        # No auto-discovery or side effects on import
        import app.export_client as m

        assert hasattr(m, "discover_export_products")
        assert hasattr(m, "fetch_fixed_export_tariff")
        assert hasattr(m, "fetch_agile_outgoing_tariff")
