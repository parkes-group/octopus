"""
Error handlers for the application.
"""
from flask import Blueprint, render_template
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('error.html', error_code=404, message="Page not found"), 404

@bp.app_errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    # Post-MVP: Send email alert to admin
    # if current_app.config.get('ADMIN_EMAIL'):
    #     send_error_email(error)
    return render_template('error.html', error_code=500, message="An error occurred. Please try again later."), 500

@bp.app_errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors."""
    return render_template('error.html', error_code=403, message="Access forbidden"), 403

