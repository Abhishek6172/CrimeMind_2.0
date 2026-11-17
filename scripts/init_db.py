#!/usr/bin/env python3
"""Create role + database, apply versioned migrations, load the SQL module registry and correlation rules.

Usage:  python scripts/init_db.py [--db crimemind] [--reset]
Env:    CM_ADMIN_URL_BASE (default postgresql://postgres:postgres@localhost:5432), CM_APP_PASSWORD (default cm_app_dev)
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

MIGRATIONS = ROOT / "db" / "migrations"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crimemind")
    ap.add_argument("--reset", action="store_true", help="drop and recreate the database")
    args = ap.parse_args()
    base = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")
    app_pw = os.environ.get("CM_APP_PASSWORD", "cm_app_dev")

    with psycopg.connect(f"{base}/postgres", autocommit=True, row_factory=dict_row) as c:
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='cm_app'").fetchone():
            c.execute(sql.SQL("CREATE ROLE cm_app LOGIN PASSWORD {}").format(sql.Literal(app_pw)))
        else:
            c.execute(sql.SQL("ALTER ROLE cm_app PASSWORD {}").format(sql.Literal(app_pw)))
        exists = c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (args.db,)).fetchone()
        if exists and args.reset:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(args.db)))
            exists = None
        if not exists:
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args.db)))
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(args.db)))
        c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO cm_app").format(sql.Identifier(args.db)))

    from app.correlation.rules import sync_rules
    from app.registry import sync_registry

    with psycopg.connect(f"{base}/{args.db}", row_factory=dict_row) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations(
                          filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())""")
        done = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            conn.execute(f.read_text())
            conn.execute("INSERT INTO schema_migrations(filename) VALUES (%s)", (f.name,))
            print("applied", f.name)
        sync_rules(conn)
        sync_registry(conn)
        conn.commit()
    print(f"database '{args.db}' ready")


if __name__ == "__main__":
    main()
