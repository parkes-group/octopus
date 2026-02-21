"""
Export tariff API routes.

Phase 3: Expose export tariffs and stats via JSON API.
All routes under /api/export/ - opt-in, no impact on import routes.

Uses export_client for fetching, export_stats for calculations.
"""
from datetime import datetime, timezone
import logging

from flask import Blueprint, request, jsonify

from app.config import Config
from app.export_client import (
    discover_export_products,
    fetch_agile_outgoing_tariff,
    fetch_fixed_export_tariff,
)
from app.export_stats import compute_agile_daily_stats, compute_fixed_effective_rate, get_export_rate
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
