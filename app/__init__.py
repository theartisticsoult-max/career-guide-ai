"""Career Guide AI Flask application.

Setup only: configuration, data loading, template filters and blueprint
registration. Route logic lives in app/blueprints and app/services.
"""
import json
import os
import secrets

from dotenv import load_dotenv
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

load_dotenv()

# Project root is the directory that contains templates/, static/ and data/.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if not FLASK_DEBUG:
        raise RuntimeError('SECRET_KEY environment variable is required')
    # Development convenience only: never a hardcoded or committed value.
    secret_key = secrets.token_hex(32)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, 'templates'),
    static_folder=os.path.join(PROJECT_ROOT, 'static'),
)
app.config['SECRET_KEY'] = secret_key
app.config['DEBUG'] = FLASK_DEBUG

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])

from app.models import db  # noqa: E402


@app.template_filter('from_json')
def from_json_filter(value):
    """Convert JSON string to Python object"""
    if not value:
        return {}
    try:
        return json.loads(value)
    except:
        return {}


# Load career data on startup
from app.services import career_data  # noqa: E402

with app.app_context():
    career_data.load_career_data()

# Register routes
from app.blueprints.admin import admin_bp  # noqa: E402
from app.blueprints.api import api_bp  # noqa: E402
from app.blueprints.auth import auth_bp  # noqa: E402
from app.blueprints.main import main_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)


if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG)
