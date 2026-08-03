# Lead Generator

Scrapes and enriches business leads (Google Maps, Facebook, web search), scores them, and
provides a CRM-style frontend for outreach — with AI-assisted website audits and a sales
chatbot per lead.

```
/backend   FastAPI + PostgreSQL + Redis/ARQ (scraping, enrichment, API)
/frontend  React + Vite (CRM UI)
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (running locally, or reachable via `DATABASE_URL`)
- Redis-compatible server (e.g. [Memurai](https://www.memurai.com/) on Windows, or Redis itself on macOS/Linux)

## 1. Clone and configure

```bash
git clone <repo-url>
cd Lead_Generator
```

## 2. Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

Create `backend/.env` from the example and fill in your local values:

```bash
cp .env.example .env
```

At minimum, set `DATABASE_URL` to point at a Postgres instance/database that exists, and
`REDIS_URL` to your local Redis/Memurai instance. All other keys (Serper, PageSpeed,
Hunter, OpenCorporates, Groq) are optional — the app runs without them, just with those
specific enrichment/AI features disabled.

> **Windows note:** use `127.0.0.1` instead of `localhost` in `DATABASE_URL`/`REDIS_URL` —
> some local setups resolve `localhost` to IPv6 first, which can hang the connection if the
> server only binds IPv4.

Create the database (if it doesn't exist yet), then run migrations:

```bash
# create the DB once, e.g. via psql:
# psql -U postgres -c "CREATE DATABASE lead_generator;"

alembic upgrade head
```

### Run the backend

```bash
# from backend/, with the venv activated
uvicorn app.main:app --reload --port 7000
```

This also auto-starts the ARQ worker as a subprocess (see `auto_start_arq_worker` in
`app/core/config.py`). On Windows, `scripts/dev.ps1` starts the API and worker in separate
PowerShell windows instead — useful if you want to see worker logs and API logs separately,
or if you disable the auto-start:

```powershell
.\scripts\dev.ps1
```

The API is now running at **http://127.0.0.1:7000** (docs at `/docs`, health check at `/health`).

## 3. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

`frontend/.env` sets `VITE_API_BASE_URL` — make sure it matches the backend port above
(`http://localhost:7000` by default).

Vite will print the local URL, typically **http://localhost:5173** (it falls forward to
5174, 5175, etc. if the port is already in use).

> If you change the frontend port and it's not 5173, add it to `cors_allowed_origins` in
> `backend/app/core/config.py` (or via `CORS_ALLOWED_ORIGINS` in `backend/.env`), otherwise
> the browser will block API requests with a CORS error.

## Running tests

```bash
# backend
cd backend
pytest

# frontend
cd frontend
npm test
```

## Troubleshooting

- **"Database connection failed" from `/health`** — check `DATABASE_URL` credentials and
  that Postgres is running and the database exists.
- **CORS errors in the browser console** — the frontend's origin (check the exact
  `http://host:port` in your browser's address bar) isn't in `cors_allowed_origins`.
- **Backend won't bind to its port** — another process is already using it; stop that
  process or pick a different `--port` (and update `VITE_API_BASE_URL` to match).
