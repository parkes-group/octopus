"""
Configuration classes for Flask application.
MVP: Minimal configuration, no database or email required.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class."""
    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Cache settings (MVP Required)
    CACHE_EXPIRY_MINUTES = int(os.environ.get('CACHE_EXPIRY_MINUTES', 5))
    
    # Logging (MVP Required)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Octopus Energy API Configuration
    OCTOPUS_API_BASE_URL = os.environ.get('OCTOPUS_API_BASE_URL', 'https://api.octopus.energy/v1')
    OCTOPUS_PRODUCT_CODE = os.environ.get('OCTOPUS_PRODUCT_CODE', 'AGILE-24-10-01')  # Fallback/default, will be overridden by discovery
    OCTOPUS_API_TIMEOUT = int(os.environ.get('OCTOPUS_API_TIMEOUT', 10))  # seconds
    
    # Product discovery configuration
    OCTOPUS_PRODUCT_DIRECTION_FILTER = os.environ.get('OCTOPUS_PRODUCT_DIRECTION_FILTER', 'IMPORT')  # IMPORT, EXPORT, or BOTH
    
    # Region code to name mapping
    OCTOPUS_REGION_NAMES = {
        'A': 'Eastern England',
        'B': 'East Midlands',
        'C': 'London',
        'D': 'Merseyside and Northern Wales',
        'E': 'West Midlands',
        'F': 'North Eastern England',
        'G': 'North Western England',
        'H': 'Southern England',
        'J': 'South Eastern England',
        'K': 'Southern Wales',
        'L': 'South Western England',
        'M': 'Yorkshire',
        'N': 'Southern Scotland',
        'P': 'Northern Scotland'
    }
    
    @staticmethod
    def get_regions_url():
        """Get the URL for fetching regions."""
        return f"{Config.OCTOPUS_API_BASE_URL}/industry/grid-supply-points/?group_by=region"
    
    @staticmethod
    def get_products_url():
        """Get the URL for fetching all products."""
        return f"{Config.OCTOPUS_API_BASE_URL}/products/"
    
    @staticmethod
    def get_prices_url(product_code, region_code):
        """
        Get the URL for fetching prices for a region and product.
        
        Args:
            product_code: Octopus product code (e.g., 'AGILE-24-10-01')
            region_code: Octopus region code (e.g., 'A', 'B', etc.)
        
        Returns:
            str: Complete URL for fetching prices
        """
        return f"{Config.OCTOPUS_API_BASE_URL}/products/{product_code}/electricity-tariffs/E-1R-{product_code}-{region_code}/standard-unit-rates/"
    
    @staticmethod
    def get_gsp_lookup_url(postcode):
        """
        Get the URL for Grid Supply Point lookup by postcode.
        
        Args:
            postcode: UK postcode (will be normalized)
        
        Returns:
            str: Complete URL for GSP lookup
        """
        # Normalize postcode: remove spaces, convert to uppercase
        normalized = postcode.replace(' ', '').upper()
        return f"{Config.OCTOPUS_API_BASE_URL}/industry/grid-supply-points/?postcode={normalized}"
    
    # Post-MVP: Database configuration (commented out)
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    # SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Post-MVP: Email configuration (commented out)
    # MAIL_SERVER = os.environ.get('MAIL_SERVER')
    # MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    # MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    # MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    # MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    # MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    # ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

