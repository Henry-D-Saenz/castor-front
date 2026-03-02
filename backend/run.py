"""
Entry point for CASTOR ELECCIONES backend.
Replaces the monolithic main.py with the modular Flask application.
"""
from app import create_app
from config import Config
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create Flask app
app = create_app('development')

if __name__ == '__main__':
    print(f"Starting CASTOR ELECCIONES backend on {Config.HOST}:{Config.PORT}")
    print(f"API available at http://{Config.HOST}:{Config.PORT}/api")
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )

