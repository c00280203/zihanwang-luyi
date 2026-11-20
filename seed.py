"""Load the supplied demonstration records into an empty database only."""
import json
from pathlib import Path
from sqlalchemy import select, func
from app import app
from models import db, Course, KnowledgePoint, KnowledgePointAlias, Resource, ResourceLocation
from database_setup import initialise_database
from pdf_service import validate_registered_pdf


def seed_demo():
    initialise_database()
    tables = [('course', Course, 'course_id'), ('knowledge_point', KnowledgePoint, 'knowledge_point_id'),
              ('knowledge_point_alias', KnowledgePointAlias, 'alias_id'), ('resource', Resource, 'resource_id'),
              ('resource_location', ResourceLocation, 'location_id')]
    if any(db.session.scalar(select(func.count()).select_from(model)) for _, model, _ in tables):
        raise ValueError('Demo loading requires empty tables. Existing records were not changed.')
    data = json.loads((Path(__file__).parent / 'data/demo_data.json').read_text())
    ids = {}
    try:
        for table, model, pk in tables:
            ids[pk] = {}
            for record in data[table]:
                values = dict(record)
                old_id = values.pop(pk)
                for field in ('course_id', 'knowledge_point_id', 'resource_id'):
                    if field in values:
                        values[field] = ids[field][values[field]]
                if model is Resource:
                    validate_registered_pdf(app.static_folder, values['file_url'], values['total_pages'])
                if model is ResourceLocation:
                    resource = db.session.get(Resource, values['resource_id'])
                    if not 1 <= values['page_number'] <= resource.total_pages:
                        raise ValueError('Demo mapping has an invalid page number.')
                row = model(**values)
                db.session.add(row)
                db.session.flush()
                ids[pk][old_id] = getattr(row, pk)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


if __name__ == '__main__':
    with app.app_context():
        seed_demo()
        print('Demonstration records loaded. TEST002 is synthetic, not a real course.')
