"""Flask extension instances.

Kept in a dedicated module so blueprints and models can import them without
circular imports. They are initialised inside the application factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from app.config import Config


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login_page"
login_manager.login_message = "Please log in to access this page."


def init_extensions(app):
    """Attach all extensions to the given Flask application."""
    db.init_app(app)
    login_manager.init_app(app)
