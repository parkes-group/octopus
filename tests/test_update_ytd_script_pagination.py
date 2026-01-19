import pytest

from scripts.update_ytd_prices_and_stats import fetch_prices_paginated_range
from scripts.update_ytd_prices_and_stats import is_slot_count_reasonable


class DummyResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_prices_paginated_range_follows_next_and_concatenates(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResp(
                {
                    "results": [
                        {"valid_from": "2026-01-01T00:00:00Z", "valid_to": "2026-01-01T00:30:00Z"},
                        {"valid_from": "2026-01-01T00:30:00Z", "valid_to": "2026-01-01T01:00:00Z"},
                    ],
                    "next": "https://example.com/next",
                }
            )
        return DummyResp(
            {
                "results": [
                    # Include a duplicate to validate that caller can dedupe (this function just fetches)
                    {"valid_from": "2026-01-01T00:30:00Z", "valid_to": "2026-01-01T01:00:00Z"},
                    {"valid_from": "2026-01-01T01:00:00Z", "valid_to": "2026-01-01T01:30:00Z"},
                ],
                "next": None,
            }
        )

    import scripts.update_ytd_prices_and_stats as mod

    monkeypatch.setattr(mod.requests, "get", fake_get)

    results, meta = fetch_prices_paginated_range(
        product_code="AGILE-24-10-01",
        region="A",
        period_from="2026-01-01T00:00:00Z",
        period_to="2026-01-02T00:00:00Z",
        page_size=2,
    )

    assert calls["n"] == 2
    assert len(results) == 4
    assert meta["pages_fetched"] == 2


def test_is_slot_count_reasonable_allows_boundary_slack():
    assert is_slot_count_reasonable(actual=247, expected=249, boundary_slack=2) is True
    assert is_slot_count_reasonable(actual=246, expected=249, boundary_slack=2) is False

