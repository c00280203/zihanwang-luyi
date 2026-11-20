import os

from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import select, func
from sqlalchemy.engine import URL

from models import (
    db,
    Course,
    KnowledgePoint,
    KnowledgePointAlias,
    Resource,
    ResourceLocation,
)

# Read the existing database settings
load_dotenv(override=True)

db_url = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    database=os.getenv("PGDATABASE"),
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    # Check the number of records in each table
    models = [
        Course,
        KnowledgePoint,
        KnowledgePointAlias,
        Resource,
        ResourceLocation,
    ]

    print("ORM models connected successfully!")

    for model in models:
        count = db.session.scalar(
            select(func.count()).select_from(model)
        )
        print(f"{model.__tablename__}: {count}")

    # Read the PDF locations with JOIN
    statement = (
        select(
            Course.course_code,
            KnowledgePoint.name,
            Resource.title,
            ResourceLocation.page_number,
        )
        .select_from(ResourceLocation)
        .join(
            Course,
            ResourceLocation.course_id == Course.course_id,
        )
        .join(
            KnowledgePoint,
            ResourceLocation.knowledge_point_id
            == KnowledgePoint.knowledge_point_id,
        )
        .join(
            Resource,
            ResourceLocation.resource_id == Resource.resource_id,
        )
        .order_by(Course.course_code, Resource.title)
    )

    print("\nMapped PDF locations:")

    results = db.session.execute(statement).all()

    for row in results:
        print(
            f"{row.course_code} | {row.name} | "
            f"{row.title} | Page {row.page_number}"
        )
