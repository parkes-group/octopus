"""Pytest fixtures and configuration."""
import pytest


@pytest.fixture
def app():
    """Create Flask application for testing."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()
