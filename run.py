"""
Development server runner.
"""
from app import create_app
from app.config import DevelopmentConfig

if __name__ == '__main__':
    app = create_app(DevelopmentConfig)
    app.run(debug=True, host='0.0.0.0', port=5000)

