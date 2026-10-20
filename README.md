# UGHS Student Management

Agentic student roster uploader: an LLM agent maps and cleans messy `.xlsx`/`.csv` rosters and writes them through backend tools; the UI reads data back through plain REST endpoints.

## Layout

```
backend/    FastAPI + SQLAlchemy 2 + Alembic (Python 3.12, managed by uv)
frontend/   React + TypeScript + Vite
```

The two apps are decoupled: they share nothing but the HTTP API under `/api`. In dev, Vite proxies `/api` to `http://localhost:8000`.

## Prerequisites

- PostgreSQL 16 — `brew install postgresql@16 && brew services start postgresql@16`, or `docker compose up -d db`
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Node 20.19+ (npm 11 recommended; npm 10.8 hits an install bug with this dependency tree, so `make install` uses `npx npm@11`)

## First-time setup

```bash
# Database (skip if using docker compose)
psql -d postgres -c "CREATE ROLE ughs WITH LOGIN PASSWORD 'ughs_dev' CREATEDB;"
createdb -O ughs ughs_students

cp backend/.env.example backend/.env
make install
make migrate
```

## Run

```bash
make backend    # http://localhost:8000  (API docs at /docs)
make frontend   # http://localhost:5173
```

## Checks

```bash
make test
make lint
```
