"""Bring an EMPTY database up to the current schema, then hand it to Alembic.

Why this exists
---------------
`flask db upgrade` cannot build this schema from scratch. The baseline revision
(b033ca5044ab) runs `batch_alter_table('user')`, i.e. it assumes the core tables
already exist -- they were originally created with `db.create_all()`, not by a
migration. Against a blank database the upgrade fails immediately with
`relation "user" does not exist`.

So for a brand-new database (a fresh managed Postgres, for example) the correct
sequence is:

    1. db.create_all()      -> build every table from the current models
    2. stamp 'head'         -> tell Alembic the schema is already current
    3. flask db upgrade     -> from now on, normal migrations apply

Usage
-----
    DATABASE_URL=postgresql://...  python scripts/bootstrap_db.py

Safe to re-run. It never drops anything:
  * tables that already exist are left untouched (create_all skips them)
  * an existing alembic_version row is never overwritten -- if one is present
    the script tells you to run `flask db upgrade` instead of stamping, so a
    restored database keeps its real migration position.

Do NOT use this to migrate an existing database. Restoring a dump from your
previous host is always preferable: it carries the data AND the correct
alembic_version with it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app import create_app, db


def current_alembic_version(inspector):
    """Return the stamped revision, or None if the database has never been stamped."""
    if "alembic_version" not in inspector.get_table_names():
        return None
    from sqlalchemy import text

    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def main():
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        print("Refusing to run: DATABASE_URL is not set.")
        print("Set it to the target database first, e.g.")
        print('  DATABASE_URL="postgresql://user:pass@host:5432/dbname" python scripts/bootstrap_db.py')
        return 1

    # Never print credentials.
    safe_target = database_url.split("@")[-1] if "@" in database_url else database_url
    print(f"Target database: ...@{safe_target}" if "@" in database_url else f"Target database: {safe_target}")

    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        before = set(inspector.get_table_names())
        print(f"Tables found before: {len(before)}")

        stamped = current_alembic_version(inspector)
        if stamped:
            print(f"\nThis database is already stamped at revision: {stamped}")
            print("It is not empty, so this script will not touch it.")
            print("Run `flask db upgrade` to apply any pending migrations instead.")
            return 0

        print("\nNo alembic_version found -> treating this as a fresh database.")
        print("Creating tables from the current models...")
        db.create_all()

        inspector = inspect(db.engine)
        after = set(inspector.get_table_names())
        created = sorted(after - before)
        print(f"Tables created: {len(created)}")
        for name in created:
            print(f"  + {name}")

        # Tell Alembic the schema matches the latest revision, so future
        # `flask db upgrade` runs start from the right place.
        from flask_migrate import stamp

        stamp(revision="head")

        inspector = inspect(db.engine)
        print(f"\nStamped at: {current_alembic_version(inspector)}")
        print(f"Total tables now: {len(inspector.get_table_names())}")
        print("\nDone. The admin user is created on app start by main.py:init_db().")
        print("Log in and change that password immediately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
