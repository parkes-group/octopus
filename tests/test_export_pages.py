"""
Phase 4: Tests for export tariff pages.

Verifies pages load, correct API endpoints in page scripts, no wrong data requests.
Mock API responses; no real Octopus API calls.
"""
from unittest.mock import patch

import pytest


class TestExportPagesLoad:
    """Export pages return 200 and render without error."""

    def test_export_overview_loads(self, client):
        r = client.get("/export")
        assert r.status_code == 200
        assert b"Export Tariffs" in r.data
        assert b"Fixed" in r.data
        assert b"Agile" in r.data

    def test_export_fixed_loads(self, client):
        r = client.get("/export/fixed")
        assert r.status_code == 200
        assert b"Fixed Export" in r.data
        assert b"Outgoing Octopus" in r.data
        assert b"region-select" in r.data
        assert b"VAT" in r.data

    def test_export_agile_loads(self, client):
        r = client.get("/export/agile/eastern-england")
        assert r.status_code == 200
        assert b"Agile Outgoing" in r.data
        assert b"negative" in r.data.lower()
        assert b"region-select" in r.data

    def test_export_agile_redirects_without_region(self, client):
        """ /export/agile without region redirects to export index."""
        r = client.get("/export/agile", follow_redirects=False)
        assert r.status_code == 302
        assert "/export" in r.headers.get("Location", "")

    def test_export_agile_404_invalid_region(self, client):
        """ /export/agile/<invalid> returns 404."""
        r = client.get("/export/agile/invalid-region-slug-xyz")
        assert r.status_code == 404


class TestExportPagesAPIDataRequests:
    """Verify correct API endpoints are referenced; no wrong data requests."""

    def test_fixed_page_requests_rate_only(self, client):
        """Fixed page uses /api/export/rate with tariff_type=fixed; no daily-stats."""
        r = client.get("/export/fixed")
        html = r.data.decode("utf-8")
        assert "/api/export/rate" in html
        assert "tariff_type=fixed" in html
        assert "/api/export/daily-stats" not in html

    def test_agile_page_requests_blocks(self, client):
        """Agile page uses blocks API (includes prices, chart data, today_stats)."""
        r = client.get("/export/agile/eastern-england")
        html = r.data.decode("utf-8")
        assert "/api/export/blocks" in html

    def test_agile_page_does_not_request_fixed_rates(self, client):
        """Agile page never requests tariff_type=fixed."""
        r = client.get("/export/agile/eastern-england")
        html = r.data.decode("utf-8")
        # agile_outgoing appears; fixed should not appear in API URLs
        assert "tariff_type=fixed" not in html

    def test_export_overview_makes_no_api_calls_in_markup(self, client):
        """Overview page has no fetch to export API in initial HTML (data loads on sub-pages)."""
        r = client.get("/export")
        html = r.data.decode("utf-8")
        assert "/api/export/rate" not in html
        assert "/api/export/daily-stats" not in html
        assert "/api/export/blocks" not in html
        assert "/api/export/tariffs" not in html


class TestExportPageStructure:
    """SEO-safe structure: titles, headings."""

    def test_export_overview_has_title_and_h1(self, client):
        r = client.get("/export")
        assert b"<title>" in r.data
        assert b"Export" in r.data
        assert b"<h1" in r.data

    def test_fixed_page_has_title_and_h1(self, client):
        r = client.get("/export/fixed")
        assert b"<title>" in r.data
        assert b"Fixed" in r.data or b"Outgoing" in r.data
        assert b"<h1" in r.data

    def test_agile_page_loads_with_heading(self, client):
        r = client.get("/export/agile/eastern-england")
        assert r.status_code == 200
        assert b"Agile Outgoing" in r.data or b"Export" in r.data


class TestImportPagesUnchanged:
    """Regression: import pages still work; no export data on import paths."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_index_loads(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r = client.get("/")
        assert r.status_code == 200

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_regions_loads(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        with patch("app.routes.CacheManager.get_cached_prices") as mock_cache:
            mock_cache.return_value = [
                {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 10, "value_inc_vat": 10.5}
            ]
            r = client.get("/regions?product=AGILE-24-10-01")
        assert r.status_code == 200

    def test_about_loads(self, client):
        r = client.get("/about")
        assert r.status_code == 200

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_index_does_not_contain_export_api_calls(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r = client.get("/")
        html = r.data.decode("utf-8")
        assert "/api/export/" not in html


class TestNavigation:
    """Export link in navigation."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_export_link_in_header(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r = client.get("/")
        assert r.status_code == 200
        assert b"/export" in r.data
