# wsgi.py - WSGI entry point for Gunicorn
import sys
import os
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Import your Flask app
from app import app 

# Optional: For production logging
import logging

# Configure logging for production
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

# Health check endpoint lives in app/blueprints/main.py so it is available
# both under Gunicorn and when running the app directly.

# The application object is named 'app' for Gunicorn
