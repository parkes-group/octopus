"""
WSGI entry point for PythonAnywhere deployment.
"""
import sys
import os

# Add project directory to path
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

from app import create_app
from app.config import ProductionConfig

# Create application instance
application = create_app(ProductionConfig)

