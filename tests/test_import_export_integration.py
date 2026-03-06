"""
Tests for import/export UI integration: postcode persistence, redirects, cross-links.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest


def _prices_for_today():
    """Generate mock price entries for today (UK) so they pass date filtering."""
    from app.timezone_utils import get_uk_now
    uk_now = get_uk_now()
    base = uk_now.replace(hour=0, minute=0, second=0, microsecond=0)
    base_utc = base.astimezone(timezone.utc)
    slots = []
    for i in range(48):
        start = base_utc + timedelta(minutes=30 * i)
        end = start + timedelta(minutes=30)
        slots.append({
            "valid_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "valid_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "value_exc_vat": 10,
            "value_inc_vat": 10.5,
        })
    return slots


class TestPostcodePersistence:
    """Session stores region_slug after postcode entry; redirects use it."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    @patch("app.routes.OctopusAPIClient.lookup_region_from_postcode")
    @patch("app.routes.CacheManager.get_cached_prices")
    def test_postcode_on_import_then_export_redirects(
        self, mock_cache, mock_lookup, mock_products, client
    ):
        """User enters postcode on import page; session has region_slug; visiting /export redirects to /export/<region_slug>."""
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        mock_lookup.return_value = "A"  # Eastern England
        mock_cache.return_value = _prices_for_today()

        # POST postcode on index (import) -> redirects to /prices/eastern-england
        r = client.post(
            "/",
            data={"postcode": "SW1A 1AA", "product": "AGILE-24-10-01"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/prices/eastern-england" in r.headers.get("Location", "")

        # Follow redirect to establish session, then GET /export -> should redirect to /export/eastern-england
        client.post(
            "/",
            data={"postcode": "SW1A 1AA", "product": "AGILE-24-10-01"},
            follow_redirects=True,
        )
        r_export = client.get("/export", follow_redirects=False)
        assert r_export.status_code == 302
        assert "/export/agile/eastern-england" in r_export.headers.get("Location", "")

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    @patch("app.routes.OctopusAPIClient.lookup_region_from_postcode")
    def test_postcode_on_export_then_prices_redirects(
        self, mock_lookup, mock_products, client
    ):
        """User enters postcode on export page; session has region_slug; visiting /prices redirects to /prices/<region_slug>."""
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        mock_lookup.return_value = "C"  # London -> london

        # POST postcode on /export -> redirects to /export/agile/london
        r = client.post(
            "/export",
            data={"postcode": "SW1A 1AA"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"london" in r.data or b"London" in r.data

        # Now GET /prices (no region in query) -> should redirect to /prices/london
        r2 = client.get("/prices", follow_redirects=False)
        assert r2.status_code == 302
        assert "/prices/london" in r2.headers.get("Location", "")


class TestRegionCrossLinks:
    """Import and export region pages contain cross-links to each other."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    @patch("app.routes.CacheManager.get_cached_prices")
    def test_import_region_page_has_link_to_export_region(
        self, mock_cache, mock_products, client
    ):
        """Import region page contains link to /export/<region_slug>."""
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        mock_cache.return_value = [
            {"valid_from": "2024-01-15T00:00:00Z", "valid_to": "2024-01-15T00:30:00Z", "value_exc_vat": 10, "value_inc_vat": 10.5}
        ] * 48

        r = client.get("/prices/eastern-england")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        assert "/export/agile/eastern-england" in html
        assert "View export prices for this region" in html

    def test_export_region_page_has_link_to_import_region(self, client):
        """Export region page contains link to /prices/<region_slug>."""
        r = client.get("/export/agile/eastern-england")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        assert "/prices/eastern-england" in html
        assert "View import prices for this region" in html


class TestNavigationLabels:
    """Navigation shows Import Prices and Export Prices."""

    @patch("app.routes.OctopusAPIClient.get_agile_products")
    def test_nav_has_import_prices_and_export_prices(self, mock_products, client):
        mock_products.return_value = [{"code": "AGILE-24-10-01", "full_name": "Agile Octopus"}]
        r = client.get("/")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        assert "Import Prices" in html
        assert "Export Prices" in html
        assert "/prices" in html
        assert "/export" in html
