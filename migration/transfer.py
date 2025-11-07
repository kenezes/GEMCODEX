"""Data migration utility from legacy SQLite to PostgreSQL."""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.db.session import Base  # type: ignore  # noqa: E402
from app.models import *  # type: ignore  # noqa: F401,F403,E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()

parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
parser.add_argument("sqlite_path", type=Path, help="Path to legacy SQLite database")
parser.add_argument("dsn", type=str, help="SQLAlchemy DSN for PostgreSQL")
parser.add_argument("--dry-run", action="store_true", help="Run validation only")
parser.add_argument("--verbose", action="store_true", help="Verbose logging")

TABLES_IN_ORDER = [
    "part_categories",
    "part_analog_groups",
    "parts",
    "equipment_categories",
    "equipment",
    "equipment_parts",
    "counterparties",
    "counterparty_addresses",
    "orders",
    "order_items",
    "replacements",
    "colleagues",
    "tasks",
    "task_parts",
    "knife_tracking",
    "knife_status_log",
    "knife_sharpen_log",
    "periodic_tasks",
    "app_settings",
]

def main() -> None:
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.sqlite_path.exists():
        raise SystemExit(f"SQLite file {args.sqlite_path} does not exist")

    sqlite_conn = sqlite3.connect(args.sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    engine = sa.create_engine(args.dsn)
    if not args.dry_run:
        Base.metadata.create_all(engine)

    totals: dict[str, int] = defaultdict(int)

    with Session(engine) as session:
        sqlite_cur = sqlite_conn.cursor()
        for table in TABLES_IN_ORDER:
            rows = sqlite_cur.execute(f"SELECT * FROM {table}").fetchall()
            totals[table] = len(rows)
            logging.debug("Fetched %s rows from %s", len(rows), table)
            if args.dry_run:
                continue
            metadata_table = Base.metadata.tables.get(table)
            if metadata_table is None:
                logging.warning("Skipping unknown table %s", table)
                continue
            for row in rows:
                data = dict(row)
                session.execute(metadata_table.insert().values(**data))
        if not args.dry_run:
            session.commit()

    report_path = REPO_ROOT / "logs" / "migration_report.md"
    report_lines = ["# Migration Report", "", f"Source: {args.sqlite_path}", "", "## Table counts", ""]
    for table, count in totals.items():
        report_lines.append(f"- {table}: {count}")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logging.info("Migration completed. Report written to %s", report_path)


if __name__ == "__main__":
    main()
