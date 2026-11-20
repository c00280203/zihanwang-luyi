"""Real PostgreSQL API/constraint tests in a disposable, uniquely named schema.

Run: python -m unittest discover -s tests -v
No public application tables are written by this suite.
"""
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from pypdf import PdfWriter
from sqlalchemy import select, func, event, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env', override=False)
SCHEMA = 'cw_test_' + uuid.uuid4().hex
os.environ['SOE206_DB_SCHEMA'] = SCHEMA
from app import app
from models import db, Course, KnowledgePoint, KnowledgePointAlias, Resource, ResourceLocation
from search_service import search_knowledge_points
from database_setup import initialise_database


def pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(path)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(
            host=os.getenv('PGHOST', 'localhost'), port=os.getenv('PGPORT', '5432'),
            user=os.getenv('PGUSER'), password=os.getenv('PGPASSWORD'),
            dbname=os.getenv('PGDATABASE'), connect_timeout=5,
        )
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_static = app.static_folder
        app.static_folder = cls.temp.name
        folder = Path(cls.temp.name) / 'pdfs'
        folder.mkdir()
        pdf(folder/'a.pdf', 4)
        pdf(folder/'b.pdf', 2)
        (folder/'fake.pdf').write_bytes(b'%PDF-1.4\nnot a real PDF')
        with app.app_context():
            initialise_database()
        app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        with cls.conn.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(SCHEMA)))
        cls.conn.close()
        app.static_folder = cls.old_static
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = app.app_context(); self.ctx.push()
        # Search path was set to this suite's private schema before engine creation.
        self.assertEqual(db.session.scalar(text('SELECT current_schema()')), SCHEMA)
        db.session.execute(text('TRUNCATE course CASCADE')); db.session.commit()
        a = Course(course_code='A', title='Course A'); b = Course(course_code='B', title='Course B')
        db.session.add_all([a,b]); db.session.flush()
        self.a, self.b = a.course_id, b.course_id
        p = KnowledgePoint(course_id=self.a,name='Natural Join',normalized_name='natural join')
        q = KnowledgePoint(course_id=self.b,name='Natural Join',normalized_name='natural join')
        r = Resource(course_id=self.a,title='PDF A',file_url='/static/pdfs/a.pdf',total_pages=4)
        z = Resource(course_id=self.b,title='PDF B',file_url='/static/pdfs/b.pdf',total_pages=2)
        db.session.add_all([p,q,r,z]); db.session.flush()
        self.p, self.q, self.r, self.z = p.knowledge_point_id,q.knowledge_point_id,r.resource_id,z.resource_id
        db.session.add_all([
            KnowledgePointAlias(knowledge_point_id=self.p,alias='NJ',normalized_alias='nj'),
            KnowledgePointAlias(knowledge_point_id=self.p,alias='join',normalized_alias='join'),
            ResourceLocation(course_id=self.a,knowledge_point_id=self.p,resource_id=self.r,page_number=2),
            ResourceLocation(course_id=self.b,knowledge_point_id=self.q,resource_id=self.z,page_number=1),
        ])
        db.session.commit()
        self.client=app.test_client()

    def tearDown(self):
        db.session.rollback(); db.session.remove(); self.ctx.pop()

    def locations(self, point=None):
        return f'/api/admin/knowledge-points/{point or self.p}/locations'

    def post_location(self, **overrides):
        body=dict(course_code='A',resource_id=self.r,page_number=3,note='test')
        body.update(overrides)
        return self.client.post(self.locations(),json=body)

    def assert_rejected_write(self, record):
        before=db.session.scalar(select(func.count()).select_from(type(record)))
        db.session.add(record)
        with self.assertRaises(IntegrityError): db.session.commit()
        db.session.rollback()
        self.assertEqual(db.session.scalar(select(func.count()).select_from(type(record))),before)

    def test_search_name_alias_normalisation_and_no_duplicates(self):
        for term in ['Natural Join','  NATURAL   JOIN ', 'NJ','join']:
            response=self.client.get('/api/search',query_string={'course':'a','q':term})
            self.assertEqual(response.status_code,200)
            result=response.json['results']; self.assertEqual(len(result),1)
            self.assertEqual(result[0]['knowledge_point_id'],self.p)
            self.assertEqual(result[0]['locations'][0]['page_number'],2)

    def test_course_isolation_browse_empty_and_invalid_inputs(self):
        r=self.client.get('/api/search?course=B&q=Natural%20Join')
        self.assertEqual(r.json['results'][0]['knowledge_point_id'],self.q)
        self.assertEqual(self.client.get('/api/search?course=A&q=').json['count'],1)
        self.assertEqual(self.client.get('/api/search?course=A&q=absent').json['count'],0)
        self.assertEqual(self.client.get('/api/search?q=join').status_code,400)
        self.assertEqual(self.client.get('/api/search?course=MISSING').status_code,404)
        self.assertEqual(self.client.get('/api/search',query_string={'course':'A','q':'a'*201}).status_code,400)

    def test_literal_wildcards_and_sql_injection_string(self):
        for term in ['%','_',"' OR 1=1 --"]:
            self.assertEqual(search_knowledge_points('A',term),[])
        db.session.add(KnowledgePoint(course_id=self.a,name='100%_literal',normalized_name='100%_literal'))
        db.session.commit()
        for term in ['%','_']: self.assertEqual(len(search_knowledge_points('A',term)),1)

    def test_seed_reproduces_demo_and_refuses_overwrite(self):
        from seed import seed_demo
        db.session.execute(text('TRUNCATE course CASCADE')); db.session.commit()
        temporary_static = app.static_folder
        app.static_folder = self.old_static
        try:
            seed_demo()
            self.assertEqual(db.session.scalar(select(func.count()).select_from(Course)), 2)
            self.assertEqual(db.session.scalar(select(func.count()).select_from(ResourceLocation)), 9)
            results = search_knowledge_points('SOE206TC', 'Natural Join')
            self.assertEqual(len(results), 1)
            self.assertEqual({x['page_number'] for x in results[0]['locations']}, {8, 13, 14})
            db.session.rollback()
            with self.assertRaises(ValueError):
                seed_demo()
        finally:
            app.static_folder = temporary_static

    def test_batch_search_is_two_selects(self):
        db.session.add_all([KnowledgePoint(course_id=self.a,name=f'Concept {i}',normalized_name=f'concept {i}') for i in range(10)])
        db.session.commit(); statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'): statements.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try: results=search_knowledge_points('A','')
        finally: event.remove(db.engine,'before_cursor_execute',capture)
        self.assertEqual(len(results),11); self.assertEqual(len(statements),2)

    def test_knowledge_point_crud_and_duplicate_rollback(self):
        url='/api/admin/knowledge-points'
        r=self.client.post(url,json={'course_code':'A','name':'  SQL   Views ','description':'test'})
        self.assertEqual(r.status_code,201); point=r.json['id']
        self.assertEqual(self.client.post(url,json={'course_code':'A','name':'sql views'}).status_code,409)
        self.assertEqual(self.client.put(f'{url}/{point}',json={'course_code':'A','name':'Views'}).status_code,200)
        self.assertEqual(self.client.put(f'{url}/{point}',json={'course_code':'B','name':'Bad'}).status_code,404)
        self.assertEqual(self.client.delete(f'{url}/{point}?course=A').status_code,200)
        self.assertEqual(search_knowledge_points('A','views'),[])

    def test_alias_crud_and_duplicate_rollback(self):
        url=f'/api/admin/knowledge-points/{self.p}/aliases'
        r=self.client.post(url,json={'course_code':'A','alias':'  NAT JOIN '})
        self.assertEqual(r.status_code,201); alias=r.json['id']
        self.assertEqual(self.client.post(url,json={'course_code':'A','alias':'nat join'}).status_code,409)
        self.assertEqual(self.client.put(f'{url}/{alias}',json={'course_code':'A','alias':'NATURAL'}).status_code,200)
        self.assertEqual(self.client.delete(f'{url}/{alias}?course=A').status_code,200)

    def test_location_crud_and_search_visibility(self):
        r=self.post_location(); self.assertEqual(r.status_code,201); loc=r.json['id']
        self.assertEqual(len(search_knowledge_points('A','NJ')[0]['locations']),2)
        url=f'{self.locations()}/{loc}'
        self.assertEqual(self.client.put(url,json={'course_code':'A','page_number':4}).status_code,200)
        self.assertEqual(self.client.delete(url+'?course=A').status_code,200)
        self.assertEqual(len(search_knowledge_points('A','NJ')[0]['locations']),1)

    def test_invalid_cross_course_and_duplicate_locations(self):
        for n in [0,-1,5,True,'3']:
            self.assertEqual(self.post_location(page_number=n).status_code,400)
        self.assertEqual(self.post_location(resource_id=self.z).status_code,400)
        self.assertEqual(self.post_location(page_number=2).status_code,409)
        self.assertEqual(self.post_location().status_code,201)

    def test_database_constraints_even_when_bypassing_api(self):
        self.assert_rejected_write(ResourceLocation(course_id=self.a,knowledge_point_id=self.p,resource_id=self.z,page_number=1))
        self.assert_rejected_write(ResourceLocation(course_id=self.a,knowledge_point_id=self.p,resource_id=self.r,page_number=0))
        self.assert_rejected_write(Resource(course_id=self.a,title='Duplicate',file_url='/static/pdfs/a.pdf',total_pages=4))
        self.assert_rejected_write(KnowledgePoint(course_id=self.a,name='Natural Join',normalized_name='natural join'))

    def test_resource_parser_missing_file_and_page_count(self):
        url='/api/admin/resources'
        for path,pages in [('/static/pdfs/missing.pdf',2),('/static/pdfs/fake.pdf',1),('/static/pdfs/b.pdf',99),('/static/pdfs/../b.pdf',2)]:
            r=self.client.post(url,json={'course_code':'A','title':'Bad','file_url':path,'total_pages':pages})
            self.assertEqual(r.status_code,400)
        r=self.client.post(url,json={'course_code':'A','title':'B in A','file_url':'/static/pdfs/b.pdf','total_pages':2})
        self.assertEqual(r.status_code,201)
        rid=r.json['id']
        self.assertEqual(self.client.put(f'{url}/{rid}',json={'course_code':'A','title':'Changed','file_url':'/static/pdfs/b.pdf','total_pages':2}).status_code,200)
        self.assertEqual(self.client.delete(f'{url}/{rid}?course=A').status_code,200)

    def test_mapped_resource_delete_restricted_at_api_and_database(self):
        self.assertEqual(self.client.delete(f'/api/admin/resources/{self.r}?course=A').status_code,409)
        db.session.delete(db.session.get(Resource,self.r))
        with self.assertRaises(IntegrityError): db.session.commit()
        db.session.rollback()
        self.assertIsNotNone(db.session.get(Resource,self.r))

    def test_loaded_aliases_cascade_when_point_deleted(self):
        point=db.session.get(KnowledgePoint,self.p)
        self.assertEqual(len(point.aliases),2)
        db.session.delete(point); db.session.commit()
        self.assertEqual(db.session.scalar(select(func.count()).select_from(KnowledgePointAlias)),0)
        self.assertEqual(db.session.scalar(select(func.count()).select_from(ResourceLocation).where(ResourceLocation.course_id==self.a)),0)

    def test_resource_update_cannot_invalidate_mappings(self):
        url=f'/api/admin/resources/{self.r}'
        self.assertEqual(self.client.put(url,json={'course_code':'A','title':'A','file_url':'/static/pdfs/b.pdf','total_pages':2}).status_code,409)
        self.assertEqual(self.client.put(url,json={'course_code':'A','title':'A','file_url':'/static/pdfs/a.pdf','total_pages':1}).status_code,400)
        self.assertEqual(db.session.get(Resource,self.r).total_pages,4)

    def test_stale_pdf_page_count_blocks_new_mapping(self):
        path=Path(app.static_folder)/'pdfs/a.pdf'
        try:
            pdf(path,1)
            self.assertEqual(self.post_location().status_code,409)
        finally: pdf(path,4)

    def test_pages_render_and_pdf_is_served(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/admin').status_code,200)
        with self.client.get('/static/pdfs/a.pdf') as response:
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.data.startswith(b'%PDF-'))

    def test_setup_is_repeatable(self):
        db.session.remove()
        initialise_database(); initialise_database()
        self.assertEqual(db.session.scalar(select(func.count()).select_from(Course)),2)


if __name__ == '__main__': unittest.main(verbosity=2)
