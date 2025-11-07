# GEMCODEX Platform

GEMCODEX has been refactored into a client–server platform composed of a FastAPI backend, a React-based mobile-friendly web client (PWA), and the existing desktop client reworked to consume HTTP APIs.

## Architecture Overview

```
┌─────────────┐        ┌────────────────┐        ┌─────────────┐
│ Desktop App │ <────▶ │ FastAPI (API)  │ ◀────▶ │ React PWA   │
└─────────────┘        └────────────────┘        └─────────────┘
        │                         │                        │
        │                         ▼                        │
        └─────────────▶ PostgreSQL 15 ◀────────────────────┘
```

* **backend/** – FastAPI application with JWT auth, SQLAlchemy models, and WebSocket endpoint for realtime updates.
* **webapp/** – React + TypeScript Progressive Web App optimised for Android browsers.
* **migration/** – tools for moving legacy SQLite data into PostgreSQL.
* **docker-compose.yml** – development/prod orchestration (API, PostgreSQL, nginx, static web client).

## Quick Start (Development)

1. Copy `.env.sample` to `.env` and adjust secrets.
2. Build containers: `docker compose build`.
3. Launch stack: `docker compose up`.
4. Run Alembic migrations inside the API container if not executed automatically: `docker compose exec api alembic upgrade head`.
5. Open the PWA at https://localhost (nginx terminates TLS; place dev certs in `deploy/certs`).

## Local Tooling

* **Backend** – `poetry run pytest`, `poetry run alembic revision --autogenerate`, `poetry run alembic upgrade head`.
* **Frontend** – `npm install`, `npm run dev`, `npm run lint`, `npm run type-check`.

## Repository Layout

```
backend/      FastAPI app, SQLAlchemy models, Alembic migrations
webapp/       React + TS PWA
migration/    Data migration scripts from legacy SQLite
deploy/       nginx reverse proxy config and TLS placeholder
logs/         Runtime and migration logs
```

For in-depth API documentation see [`docs/API_EXAMPLES.md`](API_EXAMPLES.md); for the domain model see [`docs/DOMAIN.md`](DOMAIN.md); data migration workflow is described in [`docs/MIGRATION.md`](MIGRATION.md).

## Desktop client configuration

Set the environment variables `API_BASE_URL` (e.g. `https://localhost/api`) and `API_TOKEN` for the desktop application so it can authenticate against the FastAPI backend. When these variables are absent the client falls back to the legacy embedded SQLite database.
