"""
Pytest configuration and fixtures.
"""
import pytest
from app import create_app
from app.config import DevelopmentConfig

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(DevelopmentConfig)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()

