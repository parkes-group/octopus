"""
Flask Application Factory
MVP: Anonymous usage only, no authentication or database
"""
from flask import Flask
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# Initialize logging before app creation
def setup_logging(app):
    """Configure logging for the application."""
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
    
    # File logging (always enabled)
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Prevent duplicate logs
    app.logger.propagate = False
    
    app.logger.info('Octopus App startup')

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
    
    # Make config values available to all templates
    @app.context_processor
    def inject_config():
        """Inject configuration values into template context."""
        from flask import session, url_for
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
        
        return {
            'github_feedback_url': app.config.get('GITHUB_FEEDBACK_URL', 'https://github.com/parkes-group/octopus/issues/new/choose'),
            'site_name': app.config.get('SITE_NAME', 'Octopus Energy Agile Pricing Assistant'),
            'site_url': app.config.get('SITE_URL', 'https://octopus-pricing.parkes-group.com'),
            'site_description': app.config.get('SITE_DESCRIPTION', 'Find the cheapest Agile Octopus electricity prices today.'),
            'seo_pages': app.config.get('SEO_PAGES', {}),
            'has_prices_history': has_prices_history,
            'prices_url': prices_url
        }
    
    return app

