"""
Flask Application Factory
MVP: Anonymous usage only, no authentication or database
"""
from flask import Flask
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
from datetime import datetime, timedelta

# Initialize logging before app creation
def setup_logging(app):
    """Configure logging for the application with daily rotation and 5-day retention."""
    # Ensure log directory exists
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Set logging level based on config
    log_level = getattr(app.config, 'LOG_LEVEL', 'INFO')
    app.logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Console logging (always enabled for visibility)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    
    # File logging with daily rotation (rotates at midnight)
    # backupCount=5 means keep 5 days of logs (current + 4 backups)
    file_handler = TimedRotatingFileHandler(
        'logs/app.log',
        when='midnight',
        interval=1,  # Rotate every day
        backupCount=5,  # Keep 5 days of logs
        encoding='utf-8'
    )
    file_handler.suffix = '%Y-%m-%d'  # Log file suffix format: app.log.2026-01-01
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Clean up old log files (older than 5 days) on startup
    cleanup_old_logs(log_dir, days=5)
    
    # Prevent duplicate logs
    app.logger.propagate = False
    
    app.logger.info('Octopus App startup')

def cleanup_old_logs(log_dir, days=5):
    """
    Remove log files older than specified number of days.
    
    Args:
        log_dir: Path to log directory
        days: Number of days to keep logs (default: 5)
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for log_file in log_dir.glob('app.log.*'):
            try:
                # Extract date from filename (app.log.YYYY-MM-DD)
                date_str = log_file.name.replace('app.log.', '')
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    logging.getLogger(__name__).debug(f"Removed old log file: {log_file.name}")
            except (ValueError, OSError) as e:
                # Skip files that don't match the expected format or can't be deleted
                logging.getLogger(__name__).warning(f"Could not process log file {log_file.name}: {e}")
    except Exception as e:
        # Don't fail startup if cleanup fails
        logging.getLogger(__name__).warning(f"Error cleaning up old log files: {e}")

def create_app(config_class=None):
    """
    Create and configure Flask application.
    
    Args:
        config_class: Configuration class (defaults to DevelopmentConfig)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_class is None:
        from app.config import DevelopmentConfig
        config_class = DevelopmentConfig
    
    app.config.from_object(config_class)
    
    # Setup logging
    setup_logging(app)
    
    # Register blueprints
    from app.routes import bp as main_bp
    from app.errors import bp as errors_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(errors_bp)
    
    # Post-MVP: Authentication blueprint (commented out)
    # from app.auth import bp as auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Ensure cache directory exists
    cache_dir = Path('app/cache')
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure votes directory exists
    votes_dir = Path('app/votes')
    votes_dir.mkdir(parents=True, exist_ok=True)
    
    # Make config values available to all templates
    @app.context_processor
    def inject_config():
        """Inject configuration values into template context."""
        from flask import session, url_for, request
        # Check if user has visited prices page before
        has_prices_history = False
        prices_url = None
        if 'last_prices_state' in session:
            state = session['last_prices_state']
            if state.get('region') and state.get('product'):
                has_prices_history = True
                prices_url = url_for('main.prices', 
                                    region=state['region'],
                                    product=state['product'],
                                    duration=state.get('duration'),
                                    capacity=state.get('capacity'))
        
        # Use dynamic site URL based on current request
        # This allows localhost for development and production URL for production
        try:
            # Use request.url_root which gives us the full URL (e.g., http://localhost:5000/ or https://example.com/)
            dynamic_site_url = request.url_root.rstrip('/')
        except RuntimeError:
            # Not in request context (e.g., during testing), fall back to config
            dynamic_site_url = app.config.get('SITE_URL', 'https://octopus-pricing.parkes-group.com')
        
        from datetime import datetime
        from app.config import Config
        return {
            'github_feedback_url': app.config.get('GITHUB_FEEDBACK_URL', 'https://github.com/parkes-group/octopus/issues/new/choose'),
            'octopus_referral_url': app.config.get('OCTOPUS_REFERRAL_URL', 'https://share.octopus.energy/clean-prawn-337'),
            'site_name': app.config.get('SITE_NAME', 'Octopus Energy Agile Pricing Assistant'),
            'site_url': dynamic_site_url,
            'site_description': app.config.get('SITE_DESCRIPTION', 'Find the cheapest Agile Octopus electricity prices today.'),
            'seo_pages': app.config.get('SEO_PAGES', {}),
            'has_prices_history': has_prices_history,
            'prices_url': prices_url,
            'current_year': datetime.now().year,
            'config': Config  # Make Config available in templates for FEATURE_VOTING_ITEMS
        }
    
    return app

