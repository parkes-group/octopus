"""
Phase 3: Tests for export API routes.

Verifies JSON structure, fixed/agile behavior, VAT, negative prices, boundaries.
Uses mocks - no real Octopus API calls.
Regression tests ensure import behavior unchanged.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.export_tariff import ExportProduct, FixedExportTariff
from app.export_tariff import AgileOutgoingTariff, HalfHourlySlot


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _fixed_tariff(inc_vat: float = 15.75, exc_vat: float = 15.0) -> FixedExportTariff:
    return FixedExportTariff(
        product_code="OUTGOING-19-05-13",
        region_code="A",
        tariff_code="E-1R-OUTGOING-A",
        rate_p_per_kwh_exc_vat=exc_vat,
        rate_p_per_kwh_inc_vat=inc_vat,
    )


def _agile_tariff(slots: list[dict]) -> AgileOutgoingTariff:
    return AgileOutgoingTariff(
        product_code="AGILE-OUTGOING-19-05-13",
        region_code="A",
        tariff_code="E-1R-AGILE-OUTGOING-A",
        slots=[HalfHourlySlot(**s) for s in slots],
    )


EXPORT_PRODUCTS = [
    ExportProduct(
        code="OUTGOING-19-05-13",
        display_name="Outgoing Octopus",
        tariff_type="fixed",
        full_name="Outgoing Octopus",
    ),
    ExportProduct(
        code="AGILE-OUTGOING-19-05-13",
        display_name="Agile Outgoing Octopus",
        tariff_type="agile_outgoing",
        full_name="Agile Outgoing Octopus",
    ),
]


# ---------------------------------------------------------------------------
# GET /api/export/tariffs
# ---------------------------------------------------------------------------


class TestExportTariffsEndpoint:
    """GET /api/export/tariffs"""

    @patch("app.export_routes.discover_export_products")
    def test_returns_tariffs_structure(self, mock_discover, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        r = client.get("/api/export/tariffs")
        assert r.status_code == 200
        data = r.get_json()
        assert "tariffs" in data
        assert isinstance(data["tariffs"], list)
        assert len(data["tariffs"]) == 2

    @patch("app.export_routes.discover_export_products")
    def test_tariff_has_required_fields(self, mock_discover, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        r = client.get("/api/export/tariffs")
        data = r.get_json()
        t = data["tariffs"][0]
        assert "tariff_type" in t
        assert "display_name" in t
        assert "product_code" in t
        assert "regions" in t
        assert "vat_info" in t

    @patch("app.export_routes.discover_export_products")
    def test_includes_fixed_and_agile_outgoing(self, mock_discover, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        r = client.get("/api/export/tariffs")
        data = r.get_json()
        types = {t["tariff_type"] for t in data["tariffs"]}
        assert "fixed" in types
        assert "agile_outgoing" in types

    @patch("app.export_routes.discover_export_products")
    def test_returns_500_on_discovery_error(self, mock_discover, client):
        mock_discover.side_effect = Exception("API error")
        r = client.get("/api/export/tariffs")
        assert r.status_code == 500
        assert "error" in r.get_json()


# ---------------------------------------------------------------------------
# GET /api/export/rate
# ---------------------------------------------------------------------------


class TestExportRateEndpoint:
    """GET /api/export/rate"""

    @patch("app.export_routes.fetch_fixed_export_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_fixed_returns_same_rate_any_timestamp(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _fixed_tariff(inc_vat=15.75, exc_vat=15.0)

        for ts in ["2024-01-15T12:00:00Z", "2024-06-20T03:30:00Z", "2025-12-31T23:59:59Z"]:
            r = client.get(f"/api/export/rate?tariff_type=fixed&region=A&timestamp={ts}&inc_vat=true")
            assert r.status_code == 200
            data = r.get_json()
            assert data["p_per_kwh"] == 15.75

    @patch("app.export_routes.fetch_fixed_export_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_fixed_inc_vat_vs_exc_vat(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _fixed_tariff(inc_vat=15.75, exc_vat=15.0)

        r_inc = client.get("/api/export/rate?tariff_type=fixed&region=A&inc_vat=true")
        r_exc = client.get("/api/export/rate?tariff_type=fixed&region=A&inc_vat=false")
        assert r_inc.get_json()["p_per_kwh"] == 15.75
        assert r_exc.get_json()["p_per_kwh"] == 15.0

    @patch("app.export_routes.fetch_agile_outgoing_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_agile_returns_correct_slot_rate(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _agile_tariff([
            {"valid_from": "2024-01-15T12:00:00Z", "valid_to": "2024-01-15T12:30:00Z", "value_exc_vat": 5.0, "value_inc_vat": 5.25},
            {"valid_from": "2024-01-15T12:30:00Z", "valid_to": "2024-01-15T13:00:00Z", "value_exc_vat": -1.0, "value_inc_vat": -1.05},
        ])
        r = client.get("/api/export/rate?tariff_type=agile_outgoing&region=A&timestamp=2024-01-15T12:15:00Z&inc_vat=true")
        assert r.status_code == 200
        assert r.get_json()["p_per_kwh"] == 5.25

    @patch("app.export_routes.fetch_agile_outgoing_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_agile_returns_negative_rate(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _agile_tariff([
            {"valid_from": "2024-01-15T12:30:00Z", "valid_to": "2024-01-15T13:00:00Z", "value_exc_vat": -1.0, "value_inc_vat": -1.05},
        ])
        r = client.get("/api/export/rate?tariff_type=agile_outgoing&region=A&timestamp=2024-01-15T12:45:00Z&inc_vat=true")
        assert r.status_code == 200
        assert r.get_json()["p_per_kwh"] == -1.05

    @patch("app.export_routes.fetch_agile_outgoing_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_agile_out_of_range_returns_null(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _agile_tariff([
            {"valid_from": "2024-01-15T12:00:00Z", "valid_to": "2024-01-15T12:30:00Z", "value_exc_vat": 5.0, "value_inc_vat": 5.25},
        ])
        r = client.get("/api/export/rate?tariff_type=agile_outgoing&region=A&timestamp=2024-01-20T00:00:00Z&inc_vat=true")
        assert r.status_code == 200
        assert r.get_json()["p_per_kwh"] is None

    @patch("app.export_routes.fetch_fixed_export_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_fixed_null_when_tariff_unavailable(self, mock_discover, mock_fetch, client):
        """When fetch returns None (e.g. region not supported for product), p_per_kwh is null."""
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = None
        r = client.get("/api/export/rate?tariff_type=fixed&region=A&inc_vat=true")
        assert r.status_code == 200
        assert r.get_json()["p_per_kwh"] is None

    @patch("app.export_routes.discover_export_products")
    def test_accepts_region_slug(self, mock_discover, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        with patch("app.export_routes.fetch_fixed_export_tariff") as mock_fetch:
            mock_fetch.return_value = _fixed_tariff()
            r = client.get("/api/export/rate?tariff_type=fixed&region=eastern-england&inc_vat=true")
            assert r.status_code == 200
            assert r.get_json()["p_per_kwh"] == 15.75

    def test_missing_tariff_type_returns_400(self, client):
        r = client.get("/api/export/rate?region=A")
        assert r.status_code == 400

    def test_invalid_tariff_type_returns_400(self, client):
        r = client.get("/api/export/rate?tariff_type=invalid&region=A")
        assert r.status_code == 400

    def test_missing_region_returns_400(self, client):
        r = client.get("/api/export/rate?tariff_type=fixed")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/export/daily-stats
# ---------------------------------------------------------------------------


class TestExportDailyStatsEndpoint:
    """GET /api/export/daily-stats"""

    @patch("app.export_routes.fetch_fixed_export_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_fixed_returns_flat_rate_per_day(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _fixed_tariff(inc_vat=15.75, exc_vat=15.0)
        r = client.get(
            "/api/export/daily-stats?tariff_type=fixed&region=A&start_date=2024-01-15&end_date=2024-01-17&inc_vat=true"
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "days" in data
        assert len(data["days"]) == 3
        for d in data["days"]:
            assert d["avg_p_per_kwh"] == 15.75
            assert d["min_p_per_kwh"] == 15.75
            assert d["max_p_per_kwh"] == 15.75
            assert "date_iso" in d
            assert "date_display" in d

    @patch("app.export_routes.fetch_agile_outgoing_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_agile_daily_stats_structure(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _agile_tariff([
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 10.0, "value_inc_vat": 10.5},
            {"valid_from": "2024-01-15T00:30:00Z", "valid_to": "2024-01-15T01:00:00Z", "value_exc_vat": -2.0, "value_inc_vat": -2.1},
        ])
        r = client.get(
            "/api/export/daily-stats?tariff_type=agile_outgoing&region=A&start_date=2024-01-15&end_date=2024-01-15&inc_vat=true"
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "days" in data
        assert len(data["days"]) == 1
        day = data["days"][0]
        assert "avg_p_per_kwh" in day
        assert "min_p_per_kwh" in day
        assert "max_p_per_kwh" in day
        assert day["min_p_per_kwh"] == -2.1  # negative handled
        assert day["max_p_per_kwh"] == 10.5

    @patch("app.export_routes.fetch_agile_outgoing_tariff")
    @patch("app.export_routes.discover_export_products")
    def test_agile_vat_exclusive(self, mock_discover, mock_fetch, client):
        mock_discover.return_value = EXPORT_PRODUCTS
        mock_fetch.return_value = _agile_tariff([
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 10.0, "value_inc_vat": 10.5},
        ])
        r = client.get(
            "/api/export/daily-stats?tariff_type=agile_outgoing&region=A&start_date=2024-01-15&end_date=2024-01-15&inc_vat=false"
        )
        assert r.status_code == 200
        assert r.get_json()["days"][0]["avg_p_per_kwh"] == 10.0

    def test_missing_dates_returns_400(self, client):
        r = client.get("/api/export/daily-stats?tariff_type=fixed&region=A")
        assert r.status_code == 400

    def test_start_after_end_returns_400(self, client):
        r = client.get(
            "/api/export/daily-stats?tariff_type=fixed&region=A&start_date=2024-01-20&end_date=2024-01-15"
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Import regression
# ---------------------------------------------------------------------------


class TestImportEndpointsUnchanged:
    """Regression: import routes still behave correctly."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_regions_page_still_works(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        minimal_prices = [
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 10, "value_inc_vat": 10.5}
        ]
        with patch("app.routes.CacheManager.get_cached_prices") as mock_cache:
            mock_cache.return_value = minimal_prices
            r = client.get("/regions?product=AGILE-24-10-01")
        assert r.status_code == 200

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_index_still_works(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r = client.get("/")
        assert r.status_code == 200

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_export_and_import_routes_coexist(self, mock_products, client):
        """Export API does not break import flow."""
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r_index = client.get("/")
        with patch("app.export_routes.discover_export_products") as mock_exp:
            mock_exp.return_value = EXPORT_PRODUCTS
            r_export = client.get("/api/export/tariffs")
        assert r_index.status_code == 200
        assert r_export.status_code == 200
