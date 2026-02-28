"""
Tests for export tariff caching.

Verifies cache hit (no API call), cache miss (API called), expiry, region isolation.
Uses mocks - no real Octopus API calls. No regression to import cache.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.cache_manager import CacheManager
from app.export_client import fetch_agile_outgoing_tariff, fetch_fixed_export_tariff
from app.export_tariff import FixedExportTariff


# Fixed cache format (single element with tariff_code)
FIXED_CACHED = [
    {
        "value_exc_vat": 15.0,
        "value_inc_vat": 15.75,
        "tariff_code": "E-1R-OUTGOING-19-05-13-A",
        "product_code": "OUTGOING-19-05-13",
        "region_code": "A",
    }
]

# Agile cache format (time-series with valid_from, valid_to)
AGILE_CACHED = [
    {
        "value_exc_vat": 5.0,
        "value_inc_vat": 5.25,
        "valid_from": "2024-01-15T12:00:00Z",
        "valid_to": "2024-01-15T12:30:00Z",
        "_tariff_code": "E-1R-AGILE-OUTGOING-19-05-13-A",
    },
    {
        "value_exc_vat": -1.0,
        "value_inc_vat": -1.05,
        "valid_from": "2024-01-15T12:30:00Z",
        "valid_to": "2024-01-15T13:00:00Z",
    },
]


class TestExportCacheHit:
    """Cache hit: no API call when valid cache exists."""

    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_fixed_cache_hit_no_api_call(self, mock_get_cached):
        mock_get_cached.return_value = FIXED_CACHED
        with patch("app.export_client.CacheManager.cache_prices") as mock_cache_write:
            result = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
            assert result is not None
            assert isinstance(result, FixedExportTariff)
            assert result.rate_p_per_kwh_inc_vat == 15.75
            mock_cache_write.assert_not_called()
        mock_get_cached.assert_called_once_with("OUTGOING-19-05-13", "A")

    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_agile_cache_hit_no_api_call(self, mock_get_cached):
        mock_get_cached.return_value = AGILE_CACHED
        with patch("app.export_client.CacheManager.cache_prices") as mock_cache_write:
            result = fetch_agile_outgoing_tariff(
                "AGILE-OUTGOING-19-05-13", "A", datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
            )
            assert result is not None
            assert len(result.slots) == 2
            assert result.slots[0].value_inc_vat == 5.25
            mock_cache_write.assert_not_called()


class TestExportCacheMiss:
    """Cache miss: API called and result cached."""

    @patch("app.export_client.CacheManager.cache_prices")
    @patch("app.export_client.get_product_tariffs")
    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_fixed_cache_miss_calls_api_and_caches(self, mock_get_cached, mock_tariffs, mock_cache_prices):
        mock_get_cached.return_value = None
        mock_tariffs.return_value = {
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
        result = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
        assert result is not None
        mock_tariffs.assert_called_once()
        mock_cache_prices.assert_called_once()
        call_args = mock_cache_prices.call_args
        assert call_args[0][0] == "OUTGOING-19-05-13"
        assert call_args[0][1] == "A"
        assert len(call_args[0][2]) == 1
        assert call_args[0][2][0]["tariff_code"] == "E-1R-OUTGOING-19-05-13-A"

    @patch("app.export_client.CacheManager.cache_prices")
    @patch("app.export_client.get_unit_rates")
    @patch("app.export_client.get_product_tariffs")
    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_agile_cache_miss_calls_api_and_caches(self, mock_get_cached, mock_tariffs, mock_unit_rates, mock_cache_prices):
        mock_get_cached.return_value = None
        mock_tariffs.return_value = {
            "single_register_electricity_tariffs": {
                "_A": {
                    "direct_debit_monthly": {"code": "E-1R-AGILE-OUTGOING-19-05-13-A"},
                },
            },
        }
        mock_unit_rates.return_value = [
            {"value_exc_vat": 5.0, "value_inc_vat": 5.25, "valid_from": "2024-01-15T12:00:00Z", "valid_to": "2024-01-15T12:30:00Z"},
        ]
        result = fetch_agile_outgoing_tariff(
            "AGILE-OUTGOING-19-05-13", "A", datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        )
        assert result is not None
        mock_unit_rates.assert_called_once()
        mock_cache_prices.assert_called_once()
        cached = mock_cache_prices.call_args[0][2]
        assert len(cached) == 1
        assert "_tariff_code" in cached[0]


class TestExportCacheExpiry:
    """Expired cache triggers refresh."""

    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_expired_returns_none_then_fetches(self, mock_get_cached):
        mock_get_cached.return_value = None  # expired or missing
        with patch("app.export_client.get_product_tariffs") as mock_tariffs:
            mock_tariffs.return_value = {
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
            with patch("app.export_client.CacheManager.cache_prices"):
                result = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
                assert result is not None
                mock_tariffs.assert_called_once()


class TestExportCacheRegionIsolation:
    """Cache is per region; region A does not affect region B."""

    @patch("app.export_client.CacheManager.cache_prices")
    @patch("app.export_client.get_product_tariffs")
    @patch("app.export_client.CacheManager.get_cached_prices")
    def test_region_a_cache_not_used_for_region_b(self, mock_get_cached, mock_tariffs, mock_cache_write):
        def side_effect(product_code, region_code):
            if region_code == "A":
                return FIXED_CACHED
            return None

        mock_get_cached.side_effect = side_effect
        mock_tariffs.return_value = {
            "single_register_electricity_tariffs": {
                "_B": {
                    "direct_debit_monthly": {
                        "code": "E-1R-OUTGOING-19-05-13-B",
                        "standard_unit_rate_exc_vat": 12.0,
                        "standard_unit_rate_inc_vat": 12.6,
                    },
                },
            },
        }
        result_a = fetch_fixed_export_tariff("OUTGOING-19-05-13", "A")
        result_b = fetch_fixed_export_tariff("OUTGOING-19-05-13", "B")
        assert result_a is not None
        assert result_a.region_code == "A"
        assert result_a.rate_p_per_kwh_inc_vat == 15.75
        assert result_b is not None
        assert result_b.region_code == "B"
        assert result_b.rate_p_per_kwh_inc_vat == 12.6
        # A used cache (no get_product_tariffs), B used API
        assert mock_get_cached.call_count == 2
        calls = [c[0] for c in mock_get_cached.call_args_list]
        assert ("OUTGOING-19-05-13", "A") in calls
        assert ("OUTGOING-19-05-13", "B") in calls


class TestImportCacheUnchanged:
    """Regression: import cache behaviour unchanged."""

    def test_import_cache_file_naming_unchanged(self):
        path = CacheManager._get_cache_file("AGILE-24-10-01", "A")
        assert "AGILE-24-10-01" in str(path)
        assert "_A.json" in str(path)

    def test_export_cache_file_naming_separate(self):
        path_import = CacheManager._get_cache_file("AGILE-24-10-01", "A")
        path_export_agile = CacheManager._get_cache_file("AGILE-OUTGOING-19-05-13", "A")
        path_export_fixed = CacheManager._get_cache_file("OUTGOING-19-05-13", "A")
        assert path_import != path_export_agile
        assert path_import != path_export_fixed
        assert path_export_agile != path_export_fixed
