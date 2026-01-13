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
    
    # GitHub Issues URL for feedback and bug reports
    GITHUB_FEEDBACK_URL = os.environ.get('GITHUB_FEEDBACK_URL', 'https://github.com/parkes-group/octopus/issues/new/choose')
    
    # Octopus Energy referral link (supports site hosting and development)
    OCTOPUS_REFERRAL_URL = os.environ.get('OCTOPUS_REFERRAL_URL', 'https://share.octopus.energy/clean-prawn-337')
    
    # SEO Configuration
    SITE_NAME = os.environ.get('SITE_NAME', 'Agile Pricing | Octopus Energy Pricing Assistant')
    SITE_URL = os.environ.get('SITE_URL', 'https://www.agilepricing.co.uk') 
    SITE_DESCRIPTION = os.environ.get('SITE_DESCRIPTION', 'Find the cheapest Agile Octopus electricity prices today. Identify the best 30-minute charging windows for home batteries and EVs in the UK.')
    
    # Historical Statistics Configuration
    # Ofgem price cap unit rate (p/kWh, excluding standing charge)
    # Update this when the price cap changes
    OFGEM_PRICE_CAP_P_PER_KWH = float(os.environ.get('OFGEM_PRICE_CAP_P_PER_KWH', 28.6))
    
    # Default assumptions for statistics calculations
    STATS_DAILY_KWH = float(os.environ.get('STATS_DAILY_KWH', 11.0))  # Average daily usage
    STATS_BATTERY_CHARGE_POWER_KW = float(os.environ.get('STATS_BATTERY_CHARGE_POWER_KW', 3.5))  # Battery charge rate
    STATS_CHEAPEST_BLOCK_USAGE_PERCENT = float(os.environ.get('STATS_CHEAPEST_BLOCK_USAGE_PERCENT', 35.0))  # Percentage of daily usage in cheapest block
    
    # Admin password for statistics generation (set via environment variable)
    ADMIN_STATS_PASSWORD = os.environ.get('ADMIN_STATS_PASSWORD')
    
    # SEO Page-Specific Content
    SEO_PAGES = {
        'index': {
            'title': 'Octopus Agile Pricing | Agile Prices | Cheapest Prices UK',
            'description': 'View today’s Agile Octopus electricity prices and instantly find the cheapest 30-minute charging windows for home batteries and EVs across the UK'
        },
        'prices': {
            'title': 'Prices | Today’s Octopus Agile Pricing | Cheapest Charging',
            'description': 'See today’s half-hourly Agile Octopus prices, daily averages, and the cheapest charging blocks for home batteries and EVs'
        },
        'about': {
            'title': 'How Octopus Agile Pricing Works | Price Analysis Tool',
            'description': 'Learn how we analyse Agile Octopus half-hourly pricing using Octopus Energy’s public API to help UK households reduce electricity costs'
        },
        'regions': {
            'title': 'Octopus Agile Pricing by Region | UK Comparison Tool',
            'description': 'Compare Agile Octopus electricity prices across all UK regions. See daily averages and cheapest charging windows to optimise battery charging'
        }
    }
    
    # Feature Voting Configuration
    FEATURE_VOTING_ITEMS = [
        {
            "id": "daily_cheapest_email",
            "title": "Daily chosen cheapest block email",
            "description": "Get a daily email showing your chosen duration's cheapest block",
            "display_order": 1
        },
        {
            "id": "negative_price_alert",
            "title": "Negative pricing alerts",
            "description": "Get notified when electricity prices go negative",
            "display_order": 2
        }
    ]
    
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
    def get_regions_list():
        """
        Get list of all regions from static mapping.
        No API call required - regions are static.
        
        Returns:
            list: List of region dictionaries with 'region' and 'name' keys
        """
        return [
            {'region': code, 'name': name}
            for code, name in Config.OCTOPUS_REGION_NAMES.items()
        ]
    
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

