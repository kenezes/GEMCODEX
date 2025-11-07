# Data Migration Guide

This document describes the process of moving historical data from the legacy SQLite database bundled with the original desktop application into the PostgreSQL schema used by the FastAPI backend.

## Prerequisites

* The legacy `app.db` file (default location `./data/app.db`).
* PostgreSQL 15+ instance reachable from your workstation.
* Python 3.11+ with Poetry (or system interpreter if executing directly).
* Environment variables defined in `.env` (or provide DSN manually).

## Steps

1. **Prepare PostgreSQL**
   ```bash
   docker compose up db -d
   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'SELECT 1;'
   ```
2. **Run Alembic migrations**
   ```bash
   docker compose exec api alembic upgrade head
   ```
3. **Dry-run migration**
   ```bash
   python migration/transfer.py /path/to/app.db postgresql+psycopg://user:pass@host:5432/gemcodex --dry-run --verbose
   ```
   Review console output for integrity warnings.
4. **Execute migration**
   ```bash
   python migration/transfer.py /path/to/app.db postgresql+psycopg://user:pass@host:5432/gemcodex --verbose
   ```
5. **Validate**
   * Inspect `logs/migration_report.md` for per-table counts.
   * Run smoke tests via API: `curl -H "Authorization: Bearer <token>" https://host/api/parts`.

The migration script is idempotent: rerunning it will reinsert data using simple inserts. If you need upsert semantics extend `migration/transfer.py` with conflict handling logic for specific tables.
