"""Application factory.

Assembles configuration, extensions and blueprints into a Flask application.
"""
import os

from flask import Flask

from app.config import get_config
from app.extensions import db, login_manager, init_extensions


def create_app(config_name=None):
    """Create and configure a Flask application instance."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(get_config(config_name))
    app.config["SQLALCHEMY_DATABASE_URI"] = get_config(config_name).database_url()

    init_extensions(app)
    register_blueprints(app)
    register_cli(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        return db.session.get(User, int(user_id))

    return app


def register_blueprints(app):
    """Register every API and page blueprint."""
    from app.blueprints.pages import pages_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.content import content_bp
    from app.blueprints.search import search_bp
    from app.blueprints.ai import ai_bp
    from app.blueprints.admin import admin_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(content_bp, url_prefix="/api/content")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")


def register_cli(app):
    """Register helper CLI commands for setup and seeding."""
    from app.cli import init_db_command, seed_command

    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
