"""Create a fresh schema or migrate the draft's resource constraints safely."""
from sqlalchemy import inspect, text
from models import db


def initialise_database():
    db.create_all()
    # This migration changes constraints only, never drops application tables.
    with db.engine.begin() as conn:
        conn.execute(text('LOCK TABLE resource, resource_location IN SHARE ROW EXCLUSIVE MODE'))
        inspector = inspect(conn)
        uniques = {u['name'] for u in inspector.get_unique_constraints('resource')}
        if 'uq_resource_file_in_course' not in uniques:
            duplicate = conn.execute(text('''
                SELECT 1 FROM resource GROUP BY course_id, file_url
                HAVING count(*) > 1 LIMIT 1
            ''')).first()
            if duplicate:
                raise ValueError('Duplicate resource paths exist. Review them before migrating.')
            conn.execute(text('''ALTER TABLE resource ADD CONSTRAINT uq_resource_file_in_course
                                 UNIQUE (course_id, file_url)'''))
        foreign_keys = {fk['name']: fk for fk in inspector.get_foreign_keys('resource_location')}
        fk = foreign_keys.get('fk_location_resource_same_course')
        if fk and fk.get('options', {}).get('ondelete') != 'RESTRICT':
            conn.execute(text('ALTER TABLE resource_location DROP CONSTRAINT fk_location_resource_same_course'))
            conn.execute(text('''ALTER TABLE resource_location
                ADD CONSTRAINT fk_location_resource_same_course
                FOREIGN KEY (resource_id, course_id)
                REFERENCES resource(resource_id, course_id) ON DELETE RESTRICT'''))


if __name__ == '__main__':
    from app import app
    with app.app_context():
        initialise_database()
        print('Schema initialised; resource constraints verified. Existing rows preserved.')
