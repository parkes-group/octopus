import pytest
from datetime import datetime, timezone, timedelta

from app.ytd_update_job import (
    determine_fetch_plan,
    dedupe_sort_prices,
    validate_price_series,
    expected_slot_count,
)


def _slot(vf: str, vt: str) -> dict:
    return {"valid_from": vf, "valid_to": vt, "value_inc_vat": 10.0}


def test_determine_fetch_plan_skips_when_tomorrow_present():
    # Today UK = 2026-01-15; include a slot ending on 2026-01-16 in UK date terms.
    now_uk = datetime(2026, 1, 15, 19, 5, tzinfo=timezone.utc)  # fine; helper converts to UK
    prices = [
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
        _slot("2026-01-16T23:30:00Z", "2026-01-17T00:00:00Z"),
    ]
    plan = determine_fetch_plan(region="A", existing_prices=prices, now_uk=now_uk)
    assert plan is None


def test_determine_fetch_plan_fetches_today_and_tomorrow_when_only_today():
    now_uk = datetime(2026, 1, 15, 19, 5, tzinfo=timezone.utc)
    prices = [
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
        _slot("2026-01-15T23:30:00Z", "2026-01-16T00:00:00Z"),
    ]
    plan = determine_fetch_plan(region="A", existing_prices=prices, now_uk=now_uk)
    assert plan is not None
    assert plan.reason == "covers_today_fetch_today_and_tomorrow"
    assert plan.period_from_utc_z == "2026-01-16T00:00:00Z"


def test_determine_fetch_plan_gap_fetches_from_last_to_through_tomorrow():
    now_uk = datetime(2026, 1, 15, 19, 5, tzinfo=timezone.utc)
    prices = [
        _slot("2026-01-10T00:00:00Z", "2026-01-10T00:30:00Z"),
        _slot("2026-01-10T23:30:00Z", "2026-01-11T00:00:00Z"),
    ]
    plan = determine_fetch_plan(region="A", existing_prices=prices, now_uk=now_uk)
    assert plan is not None
    assert plan.reason == "gap_fetch_from_last_to_through_tomorrow"
    assert plan.period_from_utc_z == "2026-01-11T00:00:00Z"


def test_dedupe_sort_prices_is_idempotent():
    prices = [
        _slot("2026-01-15T00:30:00Z", "2026-01-15T01:00:00Z"),
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
    ]
    out = dedupe_sort_prices(prices)
    assert [p["valid_from"] for p in out] == ["2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"]
    out2 = dedupe_sort_prices(out)
    assert out2 == out


def test_validate_price_series_catches_duplicate_and_gap():
    prices = [
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
        _slot("2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z"),
        _slot("2026-01-15T01:30:00Z", "2026-01-15T02:00:00Z"),
    ]
    errs = validate_price_series(prices)
    assert any("duplicate" in e for e in errs)
    assert any("gap_or_overlap" in e for e in errs)


def test_expected_slot_count_30min_steps():
    assert expected_slot_count("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z") == 2

