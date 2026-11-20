"""CLI commands for database setup and seeding."""
import click
from flask.cli import with_appcontext

from app.extensions import db


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create all database tables."""
    db.create_all()
    click.echo("Database tables created.")


@click.command("seed-db")
@with_appcontext
def seed_command():
    """Seed accounts, courses and courseware from the reference folders."""
    from app.seeder import seed_all

    seed_all()
