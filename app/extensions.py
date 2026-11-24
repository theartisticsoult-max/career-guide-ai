"""Flask extensions shared by the application.

Kept separate from the models so the models can define tables without
importing the application factory.
"""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

sqlalchemy = SQLAlchemy()
migrate = Migrate()
