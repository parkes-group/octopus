"""
Export tariff API routes.

Phase 3: Expose export tariffs and stats via JSON API.
All routes under /api/export/ - opt-in, no impact on import routes.

Uses export_client for fetching, export_stats for calculations.
"""
from datetime import datetime, timezone, timedelta
import logging

from flask import Blueprint, request, jsonify

from app.config import Config
from app.export_client import (
    discover_export_products,
    fetch_agile_outgoing_tariff,
    fetch_fixed_export_tariff,
)
from app.export_stats import (
    _slots_to_price_dicts,
    calculate_export_blocks_per_day,
    compute_agile_daily_stats,
    compute_fixed_effective_rate,
    get_export_rate,
    EXPORT_BLOCK_DURATION_HOURS,
    EXPORT_DEFAULT_CAPACITY_KWH,
)
from app.region_slugs import region_code_from_slug

logger = logging.getLogger(__name__)

bp = Blueprint("export_api", __name__, url_prefix="/api/export")


def _parse_timestamp(value: str | None) -> datetime:
    """Parse ISO 8601 timestamp; naive treated as UTC. Default: now UTC."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        s = (value or "").replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return datetime.now(timezone.utc)


def _parse_date(value: str) -> str | None:
    """Parse YYYY-MM-DD; returns None if invalid."""
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (ValueError, TypeError):
        return None


def _region_code_from_request(region_param: str | None) -> str | None:
    """
    Resolve region: accepts region code (e.g. A) or slug (e.g. eastern-england).
    Returns None if invalid.
    """
    if not region_param:
        return None
    region_param = region_param.strip()
    # Check if it's a known code
    regions = {r["region"]: r for r in Config.get_regions_list()}
    if region_param in regions:
        return region_param
    # Try slug -> code
    code = region_code_from_slug(region_param)
    return code


def _product_by_tariff_type(products: list, tariff_type: str):
    """Find first product matching tariff_type (fixed | agile_outgoing)."""
    for p in products:
        tt = getattr(p, "tariff_type", None) or (p.get("tariff_type") if isinstance(p, dict) else None)
        if tt == tariff_type:
            return p
    return None


@bp.route("/tariffs", methods=["GET"])
def list_tariffs():
    """
    List available export tariffs.

    Returns:
        JSON: { tariffs: [{ tariff_type, display_name, product_code, regions, vat_info }] }
    """
    try:
        products = discover_export_products()
    except Exception as e:
        logger.error(f"Error discovering export products: {e}", exc_info=True)
        return jsonify({"error": "Unable to fetch export tariffs"}), 500

    regions_list = Config.get_regions_list()
    region_codes = [r["region"] for r in regions_list]

    tariffs = []
    for p in products:
        tariff_type = getattr(p, "tariff_type", None) or p.get("tariff_type", "")
        display_name = getattr(p, "display_name", None) or p.get("display_name", "")
        code = getattr(p, "code", None) or p.get("code", "")

        tariffs.append({
            "tariff_type": tariff_type,
            "display_name": display_name,
            "product_code": code,
            "regions": region_codes,
            "vat_info": "rates available with inc_vat and exc_vat",
        })

    return jsonify({"tariffs": tariffs})


@bp.route("/rate", methods=["GET"])
def get_rate():
    """
    Get export rate p/kWh for a tariff/region/timestamp.

    Params:
        tariff_type: fixed | agile_outgoing
        region: region code (A, B, ...) or slug
        timestamp: ISO 8601 (optional; default: now UTC)
        inc_vat: true | false (default: true)

    Returns:
        JSON: { p_per_kwh: float | null }
    """
    tariff_type = request.args.get("tariff_type", "").strip().lower()
    region_param = request.args.get("region")
    timestamp_str = request.args.get("timestamp")
    inc_vat_str = request.args.get("inc_vat", "true").lower()
    inc_vat = inc_vat_str not in ("false", "0", "no")

    if not tariff_type:
        return jsonify({"error": "tariff_type required"}), 400
    if tariff_type not in ("fixed", "agile_outgoing"):
        return jsonify({"error": "tariff_type must be 'fixed' or 'agile_outgoing'"}), 400

    region_code = _region_code_from_request(region_param)
    if not region_code:
        return jsonify({"error": "region required and must be valid"}), 400

    ts = _parse_timestamp(timestamp_str)

    try:
        products = discover_export_products()
    except Exception as e:
        logger.error(f"Error discovering export products: {e}", exc_info=True)
        return jsonify({"error": "Unable to fetch export tariffs"}), 500

    product = _product_by_tariff_type(products, tariff_type)
    if not product:
        return jsonify({"error": f"No export product found for tariff_type '{tariff_type}'"}), 404

    product_code = getattr(product, "code", None) or product.get("code", "")

    tariff = None
    if tariff_type == "fixed":
        tariff = fetch_fixed_export_tariff(product_code, region_code)
    else:
        # Agile: fetch from start of day containing ts
        period_from = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        tariff = fetch_agile_outgoing_tariff(product_code, region_code, period_from)

    if tariff is None:
        return jsonify({"p_per_kwh": None})

    rate = get_export_rate(tariff, ts, inc_vat=inc_vat)
    return jsonify({"p_per_kwh": rate})


@bp.route("/daily-stats", methods=["GET"])
def get_daily_stats():
    """
    Get daily export stats (avg, min, max) for a tariff/region/date range.

    Params:
        tariff_type: fixed | agile_outgoing
        region: region code or slug
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        inc_vat: true | false (default: true)

    Returns:
        JSON: { days: [{ date_iso, date_display, avg_p_per_kwh, min_p_per_kwh, max_p_per_kwh }] }
    """
    tariff_type = request.args.get("tariff_type", "").strip().lower()
    region_param = request.args.get("region")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    inc_vat_str = request.args.get("inc_vat", "true").lower()
    inc_vat = inc_vat_str not in ("false", "0", "no")

    if not tariff_type:
        return jsonify({"error": "tariff_type required"}), 400
    if tariff_type not in ("fixed", "agile_outgoing"):
        return jsonify({"error": "tariff_type must be 'fixed' or 'agile_outgoing'"}), 400

    region_code = _region_code_from_request(region_param)
    if not region_code:
        return jsonify({"error": "region required and must be valid"}), 400

    start_date = _parse_date(start_date_str)
    end_date = _parse_date(end_date_str)
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date required (YYYY-MM-DD)"}), 400
    if start_date > end_date:
        return jsonify({"error": "start_date must be <= end_date"}), 400

    try:
        products = discover_export_products()
    except Exception as e:
        logger.error(f"Error discovering export products: {e}", exc_info=True)
        return jsonify({"error": "Unable to fetch export tariffs"}), 500

    product = _product_by_tariff_type(products, tariff_type)
    if not product:
        return jsonify({"error": f"No export product found for tariff_type '{tariff_type}'"}), 404

    product_code = getattr(product, "code", None) or product.get("code", "")

    if tariff_type == "fixed":
        tariff = fetch_fixed_export_tariff(product_code, region_code)
        if tariff is None:
            return jsonify({"days": []})
        rate = compute_fixed_effective_rate(tariff, inc_vat=inc_vat)
        # One row per day in range
        from datetime import date, timedelta

        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        days = []
        d = start_d
        while d <= end_d:
            days.append({
                "date_iso": d.isoformat(),
                "date_display": d.strftime("%d/%m/%y"),
                "avg_p_per_kwh": round(rate, 2),
                "min_p_per_kwh": round(rate, 2),
                "max_p_per_kwh": round(rate, 2),
            })
            d += timedelta(days=1)
        return jsonify({"days": days})

    # Agile Outgoing
    period_from = datetime.fromisoformat(start_date + "T00:00:00+00:00")
    tariff = fetch_agile_outgoing_tariff(product_code, region_code, period_from)
    if tariff is None:
        return jsonify({"days": []})

    stats = compute_agile_daily_stats(tariff, inc_vat=inc_vat)
    # Filter by date range
    filtered = [s for s in stats if start_date <= s["date_iso"] <= end_date]
    return jsonify({"days": filtered})


@bp.route("/blocks", methods=["GET"])
def get_blocks():
    """
    Get best, worst, and best-remaining export blocks for Agile Outgoing.

    Params:
        region: region code or slug
        inc_vat: true | false (default: true)
        duration: block duration in hours (default: 3.5)
        capacity: kWh for estimated cost (default: 10.0)

    Returns:
        JSON with best_block, worst_block, best_remaining_block, daily_avg,
        current_time_uk (ISO), duration, capacity.
        Block structure: { average_price, start_time_uk, end_time_uk, ... }
    """
    region_param = request.args.get("region")
    inc_vat_str = request.args.get("inc_vat", "true").lower()
    inc_vat = inc_vat_str not in ("false", "0", "no")
    duration = float(request.args.get("duration", EXPORT_BLOCK_DURATION_HOURS))
    capacity = float(request.args.get("capacity", EXPORT_DEFAULT_CAPACITY_KWH))

    region_code = _region_code_from_request(region_param)
    if not region_code:
        return jsonify({"error": "region required and must be valid"}), 400

    try:
        products = discover_export_products()
    except Exception as e:
        logger.error(f"Error discovering export products: {e}", exc_info=True)
        return jsonify({"error": "Unable to fetch export tariffs"}), 500

    product = _product_by_tariff_type(products, "agile_outgoing")
    if not product:
        return jsonify({"error": "No Agile Outgoing product found"}), 404

    product_code = getattr(product, "code", None) or product.get("code", "")
    period_from = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    tariff = fetch_agile_outgoing_tariff(product_code, region_code, period_from)
    if tariff is None:
        return jsonify({
            "best_block": None,
            "worst_block": None,
            "best_remaining_block": None,
            "daily_avg": None,
            "current_time_uk": None,
            "duration": duration,
            "capacity": capacity,
            "product_code": None,
            "product_name": None,
            "prices": [],
            "chart": {"labels": [], "prices": [], "best_block_indices": [], "worst_block_indices": [], "best_remaining_indices": []},
            "best_block_times_by_date": {},
            "worst_block_times_by_date": {},
            "best_remaining_times_by_date": {},
            "highest_price_times_by_date": {},
            "summary_below": {},
            "today_stats": {},
            "tomorrow_stats": {},
            "tomorrow_best_block": None,
            "tomorrow_worst_block": None,
            "tomorrow_summary_below": {},
        })

    from app.timezone_utils import utc_to_uk, get_uk_now

    prices_for_calc = _slots_to_price_dicts(tariff.slots, inc_vat)
    if not prices_for_calc:
        return jsonify({
            "best_block": None,
            "worst_block": None,
            "best_remaining_block": None,
            "daily_avg": None,
            "current_time_uk": None,
            "duration": duration,
            "capacity": capacity,
            "product_code": product_code,
            "product_name": getattr(product, "full_name", None) or product.get("full_name", "Agile Outgoing"),
            "prices": [],
            "chart": {"labels": [], "prices": [], "best_block_indices": [], "worst_block_indices": [], "best_remaining_indices": []},
            "best_block_times_by_date": {},
            "worst_block_times_by_date": {},
            "best_remaining_times_by_date": {},
            "highest_price_times_by_date": {},
            "summary_below": {},
            "today_stats": {},
            "tomorrow_stats": {},
            "tomorrow_best_block": None,
            "tomorrow_worst_block": None,
            "tomorrow_summary_below": {},
        })

    uk_now = get_uk_now()
    current_time_utc = uk_now.astimezone(timezone.utc)
    blocks_per_day = calculate_export_blocks_per_day(prices_for_calc, duration, current_time_utc)

    today_uk = datetime.now(timezone.utc).date()
    today_iso = today_uk.isoformat()
    tomorrow_iso = (today_uk + timedelta(days=1)).isoformat()

    today_data = next((d for d in blocks_per_day if d["date_iso"] == today_iso), None)
    tomorrow_data = next((d for d in blocks_per_day if d["date_iso"] == tomorrow_iso), None)

    best = today_data["best_block"] if today_data else None
    worst = today_data["worst_block"] if today_data else None
    best_remaining = today_data["best_remaining_block"] if today_data else None

    today_prices_for_avg = [p["value_inc_vat"] for p in prices_for_calc if utc_to_uk(p["valid_from"]).date() == today_uk]
    daily_avg = round(sum(today_prices_for_avg) / len(today_prices_for_avg), 2) if today_prices_for_avg else None
    current_uk = uk_now

    def _block_status(start_uk, end_uk, now_uk):
        if end_uk < now_uk:
            return "passed"
        if start_uk <= now_uk <= end_uk:
            delta = end_uk - now_uk
            h = int(delta.total_seconds() // 3600)
            m = int((delta.total_seconds() % 3600) / 60)
            return {"status": "in_block", "hours_remaining": h, "minutes_remaining": m}
        return "upcoming"

    def _block_to_json(block, diff_pct=None, diff_label=None):
        """diff_pct: e.g. 20.3 for best (higher than avg), -15.2 for worst (lower than avg). diff_label: 'higher' or 'lower'."""
        if not block:
            return None
        start_uk = block["start_time_uk"]
        end_uk = block["end_time_uk"]
        status = _block_status(start_uk, end_uk, current_uk)
        out = {
            "average_price": block["average_price"],
            "start_display": start_uk.strftime("%d/%m %H:%M") if hasattr(start_uk, "strftime") else "",
            "end_display": end_uk.strftime("%H:%M") if hasattr(end_uk, "strftime") else "",
            "estimated_cost": round((block["average_price"] * capacity) / 100, 2),
        }
        if diff_pct is not None and diff_label:
            out["diff_pct"] = round(diff_pct, 1)
            out["diff_label"] = diff_label
        if isinstance(status, dict):
            out["status"] = status["status"]
            out["hours_remaining"] = status["hours_remaining"]
            out["minutes_remaining"] = status["minutes_remaining"]
        else:
            out["status"] = status
        return out

    def _diff_pct(block_price, avg):
        if not avg or avg == 0:
            return None, None
        pct = ((block_price - avg) / abs(avg)) * 100
        return pct, "higher" if pct > 0 else "lower"

    # Only show best_remaining when best block has started (like prices page)
    show_best_remaining = best_remaining and best and best.get("start_time_uk") and current_uk
    if show_best_remaining and best["start_time_uk"] > current_uk:
        show_best_remaining = False

    dp_best, lbl_best = _diff_pct(best["average_price"], daily_avg) if best else (None, None)
    dp_worst, lbl_worst = _diff_pct(worst["average_price"], daily_avg) if worst else (None, None)
    dp_rem, lbl_rem = _diff_pct(best_remaining["average_price"], daily_avg) if best_remaining else (None, None)

    # Summary below: "earn X% more... avoid periods that are Y% lower"
    summary_below = {}
    if daily_avg and best and worst:
        best_pct = ((best["average_price"] - daily_avg) / abs(daily_avg) * 100) if daily_avg else 0
        worst_pct = ((daily_avg - worst["average_price"]) / abs(daily_avg) * 100) if daily_avg and worst["average_price"] < daily_avg else 0
        summary_below = {"best_pct_higher": round(best_pct, 1), "worst_pct_lower": round(worst_pct, 1)}

    if show_best_remaining:
        best_remaining_json = _block_to_json(best_remaining, dp_rem, lbl_rem)
    else:
        best_remaining_json = None

    # Build prices list for table and chart (same shape as import prices page)
    # Sort slots by valid_from ascending for chronological display
    from app.timezone_utils import utc_to_uk
    slots_sorted = sorted(tariff.slots, key=lambda s: s.valid_from or "")
    prices_out = []
    best_block_times_by_date = {}
    worst_block_times_by_date = {}
    best_remaining_times_by_date = {}
    highest_price_times_by_date = {}
    chart_labels = []
    chart_prices = []
    best_block_indices = []
    worst_block_indices = []
    best_remaining_indices = []

    for i, slot in enumerate(slots_sorted):
        val = slot.value_inc_vat if inc_vat else slot.value_exc_vat
        dt_uk = utc_to_uk(slot.valid_from)
        date_iso = dt_uk.date().isoformat()
        date_uk = dt_uk.strftime("%d/%m/%y")
        time_uk = dt_uk.strftime("%H:%M")
        dt_end = utc_to_uk(slot.valid_to)
        prices_out.append({
            "date_iso": date_iso,
            "date_uk": date_uk,
            "time_uk": time_uk,
            "value_inc_vat": round(val, 2),
            "valid_from": slot.valid_from,
            "valid_to": slot.valid_to,
            "datetime_uk": dt_uk.isoformat(),
            "datetime_uk_end": dt_end.isoformat(),
        })
        chart_labels.append(time_uk if len(chart_labels) < 48 else date_uk + " " + time_uk)
        chart_prices.append(val)
        if best and best.get("slots"):
            slot_times = {s["valid_from"] for s in best["slots"]}
            if slot.valid_from in slot_times:
                best_block_times_by_date.setdefault(date_iso, []).append(slot.valid_from)
                best_block_indices.append(i)
        if worst and worst.get("slots"):
            slot_times = {s["valid_from"] for s in worst["slots"]}
            if slot.valid_from in slot_times:
                worst_block_times_by_date.setdefault(date_iso, []).append(slot.valid_from)
                worst_block_indices.append(i)
        if best_remaining and best_remaining.get("slots"):
            slot_times = {s["valid_from"] for s in best_remaining["slots"]}
            if slot.valid_from in slot_times:
                best_remaining_times_by_date.setdefault(date_iso, []).append(slot.valid_from)
                best_remaining_indices.append(i)
        # Tomorrow's best/worst (per-day context)
        if tomorrow_data and date_iso == tomorrow_iso:
            t_b = tomorrow_data.get("best_block")
            t_w = tomorrow_data.get("worst_block")
            if t_b and t_b.get("slots"):
                t_b_times = {s["valid_from"] for s in t_b["slots"]}
                if slot.valid_from in t_b_times:
                    best_block_times_by_date.setdefault(date_iso, []).append(slot.valid_from)
                    best_block_indices.append(i)
            if t_w and t_w.get("slots"):
                t_w_times = {s["valid_from"] for s in t_w["slots"]}
                if slot.valid_from in t_w_times:
                    worst_block_times_by_date.setdefault(date_iso, []).append(slot.valid_from)
                    worst_block_indices.append(i)

    # Highest single slot per day (for "Highest" badge like "Lowest" on import)
    by_date = {}
    for p in prices_out:
        d = p["date_iso"]
        if d not in by_date or p["value_inc_vat"] > by_date[d]["value_inc_vat"]:
            by_date[d] = p
    for d, p in by_date.items():
        highest_price_times_by_date[d] = p["valid_from"]

    # Today's min, max, avg for summary
    today_uk = datetime.now(timezone.utc).date()
    today_iso = today_uk.isoformat()
    today_prices = [p["value_inc_vat"] for p in prices_out if p["date_iso"] == today_iso]
    today_stats = {}
    if today_prices:
        today_stats = {
            "min_p_per_kwh": round(min(today_prices), 2),
            "max_p_per_kwh": round(max(today_prices), 2),
            "avg_p_per_kwh": round(sum(today_prices) / len(today_prices), 2),
        }

    # Tomorrow's blocks from per-day calculation (best/worst in context of tomorrow only)
    tomorrow_stats = {}
    tomorrow_best_block = None
    tomorrow_worst_block = None
    tomorrow_summary_below = {}
    if tomorrow_data:
        t_vals = [p["value_inc_vat"] for p in prices_out if p["date_iso"] == tomorrow_iso]
        if t_vals:
            tomorrow_stats = {
                "min_p_per_kwh": round(min(t_vals), 2),
                "max_p_per_kwh": round(max(t_vals), 2),
                "avg_p_per_kwh": round(sum(t_vals) / len(t_vals), 2),
                "date_display": tomorrow_data["date_display"],
            }
            t_best = tomorrow_data["best_block"]
            t_worst = tomorrow_data["worst_block"]
            t_avg = tomorrow_stats["avg_p_per_kwh"]
            dp_t_best, lbl_t_best = _diff_pct(t_best["average_price"], t_avg) if t_best else (None, None)
            dp_t_worst, lbl_t_worst = _diff_pct(t_worst["average_price"], t_avg) if t_worst else (None, None)

            def _block_to_json_tomorrow(block, diff_pct=None, diff_label=None):
                """Same as _block_to_json but status is always 'upcoming' for tomorrow."""
                if not block:
                    return None
                start_uk = block["start_time_uk"]
                end_uk = block["end_time_uk"]
                out = {
                    "average_price": block["average_price"],
                    "start_display": start_uk.strftime("%d/%m %H:%M") if hasattr(start_uk, "strftime") else "",
                    "end_display": end_uk.strftime("%H:%M") if hasattr(end_uk, "strftime") else "",
                    "estimated_cost": round((block["average_price"] * capacity) / 100, 2),
                    "status": "upcoming",
                }
                if diff_pct is not None and diff_label:
                    out["diff_pct"] = round(diff_pct, 1)
                    out["diff_label"] = diff_label
                return out

            tomorrow_best_block = _block_to_json_tomorrow(t_best, dp_t_best, lbl_t_best)
            tomorrow_worst_block = _block_to_json_tomorrow(t_worst, dp_t_worst, lbl_t_worst)

            # Tomorrow summary below (same format as today)
            if t_avg and t_best and t_worst:
                t_best_pct = ((t_best["average_price"] - t_avg) / abs(t_avg) * 100) if t_avg else 0
                t_worst_pct = ((t_avg - t_worst["average_price"]) / abs(t_avg) * 100) if t_avg and t_worst["average_price"] < t_avg else 0
                tomorrow_summary_below = {"best_pct_higher": round(t_best_pct, 1), "worst_pct_lower": round(t_worst_pct, 1)}

    return jsonify({
        "best_block": _block_to_json(best, dp_best, lbl_best),
        "worst_block": _block_to_json(worst, dp_worst, lbl_worst),
        "best_remaining_block": best_remaining_json,
        "daily_avg": daily_avg,
        "current_time_uk": current_uk.isoformat() if current_uk else None,
        "duration": duration,
        "capacity": capacity,
        "product_code": product_code,
        "product_name": getattr(product, "full_name", None) or product.get("full_name", "Agile Outgoing"),
        "prices": prices_out,
        "chart": {
            "labels": chart_labels,
            "prices": chart_prices,
            "best_block_indices": best_block_indices,
            "worst_block_indices": worst_block_indices,
            "best_remaining_indices": best_remaining_indices,
        },
        "best_block_times_by_date": best_block_times_by_date,
        "worst_block_times_by_date": worst_block_times_by_date,
        "best_remaining_times_by_date": best_remaining_times_by_date,
        "highest_price_times_by_date": highest_price_times_by_date,
        "summary_below": summary_below,
        "today_stats": today_stats,
        "tomorrow_stats": tomorrow_stats,
        "tomorrow_best_block": tomorrow_best_block,
        "tomorrow_worst_block": tomorrow_worst_block,
        "tomorrow_summary_below": tomorrow_summary_below,
    })
