# Knowledge Hub

A course knowledge-point navigation system built as a SOE206TC coursework prototype. Students search knowledge points, see which courseware file and page covers them, read PDF/PPT materials, and generate AI summaries with DeepSeek. Administrators manage accounts and courseware.

## Features

- **Accounts**: built-in admin (`admin@123.com` / `123456`) and student (`student@123.com` / `123456`). A public landing page links to log in and self-registration; students can self-register; only an administrator can create admin accounts and delete any account.
- **Courses**: four courses (AIP202TC, CSI205TC, ENT207TC, SOE206TC) with full 2026/27 semester codes.
- **Search**: coarse fuzzy match on knowledge point names and aliases (English and Chinese) across one course or all four courses by default, returning the courseware files and page numbers where each point appears.
- **AI search**: the **AI Search** button interprets natural-language questions (e.g. "I wanna study Algorithm" or "我想学第三范式"), ranks the knowledge-point catalog by meaning with DeepSeek, and returns a short answer plus the exact courseware pages. It falls back to keyword search automatically when the AI provider is unavailable.
- **AI summaries**: extract text from a PDF/PPTX on the server and ask DeepSeek to produce key points in English or Chinese.
- **Courseware**: students get a complete courseware library on the home page — every PDF and PPT listed with course, file type, page/slide count, direct open/download and AI summary, filterable by course.
- **UX**: minimal, light interface, subtle Web Audio sound effects, a rotating-blade spinner only while AI thinks, and an EN/中文 language toggle. English is the default.
- **Admin upload**: drag-and-drop area accepts multiple PDF/PPTX files at once; titles default to file names.
- **Database**: PostgreSQL, a relational SQL database. Knowledge points, aliases, resources and page mappings are stored in normalized tables with foreign keys, unique constraints, CHECK constraints and indexes. All queries are parameterized.

## Architecture

The code is split into layers with a single responsibility each:

```
app/
  config.py          # environment-based configuration
  extensions.py      # Flask extension instances
  models.py          # database models
  seeder.py          # built-in accounts, courses, courseware import
  kp_seeder.py       # curated knowledge-point seeds
  cli.py             # flask init-db / flask seed-db commands
  blueprints/        # API and page routes (auth, content, search, ai, admin, pages)
  services/          # business logic (auth, search, ai, storage, content)
  utils/             # decorators and text extraction helpers
api/index.py         # Vercel serverless entry point
wsgi.py              # local / WSGI entry point
```

Services never touch request objects; routes never build SQL. Storage and AI providers sit behind service interfaces so the app can switch between local and hosted backends via environment variables.

## Local setup

Prerequisites: Python 3.11+, PostgreSQL.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your database password and DeepSeek API key. Then:

```sh
flask --app wsgi init-db
flask --app wsgi seed-db
python wsgi.py
```

Open http://127.0.0.1:5001 .

The seeder imports PDF/PPTX files from the `大三上课程` folder into `static/courseware/` and creates knowledge-point seeds with page-1 mappings. Administrators can refine exact pages later. The school permits free educational use of these materials, so `static/courseware/` is committed to Git (94 files, about 220 MB, no single file over 50 MB).

## Deploying to Vercel + Supabase

Supabase provides the PostgreSQL database and the object storage. Vercel runs the Flask app as a serverless function.

### Free cloud databases

Registration is only needed for online deployment. Both free tiers are enough for this coursework:

| Provider | Free database | Free file storage | Notes |
|---|---|---|---|
| Supabase | 500 MB PostgreSQL per project | 1 GB, max 50 MB per file | Database + storage in one place; projects pause after one week of inactivity. Recommended here. |
| Neon | 1 GB PostgreSQL per project | 5 GB object storage | Alternative if you prefer Neon; use a separate object store or its Storage feature. |

If you do **not** register any cloud database: the app still runs locally with the bundled PostgreSQL, but Vercel cannot be used for a working online demo — serverless functions have no persistent disk and no local database, so pages would load while searches, accounts and uploads fail. In that case deploy on your own server instead (Gunicorn + Nginx + local PostgreSQL).

### 1. Supabase

1. Create a free project at supabase.com.
2. In Project Settings > Database, copy the **Connection string** (URI). You need the password you set when creating the project.
3. In Storage, create a public bucket named `courseware`.
4. In Project Settings > API, copy the **Project URL** and the **service_role** key.

### 2. GitHub

1. Create a new repository and push this project. Make sure `.env` is NOT committed (it is in `.gitignore`).
2. Never commit real API keys or passwords.

### 3. Vercel

1. Log in to vercel.com and choose "Add New > Project", then import your GitHub repository.
2. Framework preset: Other. Vercel detects `vercel.json` and `@vercel/python`.
3. Add these environment variables in Project Settings > Environment Variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Supabase connection string (`postgresql://...`) |
   | `FLASK_SECRET_KEY` | a long random string |
   | `FLASK_ENV` | `production` |
   | `STORAGE_MODE` | `supabase` |
   | `SUPABASE_URL` | Supabase Project URL |
   | `SUPABASE_KEY` | Supabase service_role key |
   | `SUPABASE_BUCKET` | `courseware` |
   | `DEEPSEEK_API_KEY` | your DeepSeek API key |

4. Deploy. On the first deployment the tables do not exist yet. Create them by running `flask --app wsgi init-db` and `flask --app wsgi seed-db` against the Supabase database from your local machine (point `DATABASE_URL` at Supabase in a temporary `.env`, or use the Supabase SQL editor). Then redeploy if needed.

Note: Vercel serverless functions have no persistent local disk, so all courseware must live in Supabase Storage (`STORAGE_MODE=supabase`). The committed `static/courseware/` files make the local demo complete; on Vercel, an administrator can upload copies through the admin page, or you can point the storage layer at the committed static files if the deployment size is acceptable.

## API overview

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | public | log in |
| POST | `/api/auth/register` | public | student registration |
| GET | `/api/auth/me` | public | current user |
| POST | `/api/auth/logout` | public | log out |
| GET | `/api/content/courses` | public | list courses |
| GET | `/api/content/resources` | student | list courseware |
| POST | `/api/content/upload` | admin | upload courseware |
| DELETE | `/api/content/resources/<id>` | admin | delete courseware |
| GET | `/api/search/?course=all&q=` | student | fuzzy/coarse search with page mappings (`course=all` searches every course) |
| GET | `/api/search/ai?course=all&q=&lang=en` | student | AI semantic search with answer, reasons and page mappings |
| POST | `/api/ai/summary/<id>` | student | generate AI summary |
| GET/POST/DELETE | `/api/admin/accounts` | admin | manage accounts |

## Notes

- DeepSeek calls happen only on the server. The API key never reaches the browser.
- Password hashes use werkzeug's salted hash; plaintext passwords are never stored.
- The system is a localhost/coursework prototype. Add proper hardening before any public production use.

## Coursework rubric alignment

- **Creativity (30)**: the improvement targets a real LMO pain point — finding the exact slide for a concept — with AI key-point extraction and coarse cross-course search.
- **Completeness & depth (30)**: the report should include the five required diagrams, an OLTP/OLAP statement (this system is OLTP) and module-calling explanations.
- **Correctness (20)**: PostgreSQL with normalized tables, constraints and parameterized queries; this project uses an ORM (SQLAlchemy) for maintainability while the underlying SQL is generated safely, which the rubric explicitly allows if justified in the report.
- **Documentation & demo (20)**: keep the report under 20 pages (A4, 12 pt), record a 1-minute demo video and add the AI disclosure section.
