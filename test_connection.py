import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Load settings from .env
load_dotenv(override=True)

# Create the database connection URL
db_url = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    database=os.getenv("PGDATABASE"),
)

# Connect to PostgreSQL
engine = create_engine(db_url)

with engine.connect() as connection:
    database_name = connection.execute(
        text("SELECT current_database()")
    ).scalar()

    point_count = connection.execute(
        text("SELECT COUNT(*) FROM knowledge_point")
    ).scalar()

    location_count = connection.execute(
        text("SELECT COUNT(*) FROM resource_location")
    ).scalar()

    print("Database connection successful!")
    print("Connected database:", database_name)
    print("Knowledge points:", point_count)
    print("Resource locations:", location_count)

engine.dispose()
