"""Prepare the database for a deploy: bootstrap it if empty, migrate it if not.

Run this as the deploy-time database step (Railway: "Pre-deploy Command"):

    python scripts/prepare_db.py

It is the one command that is correct in both situations, so it never needs to
be changed between the first deploy and later ones:

  * Fresh, empty database -> db.create_all() builds every table from the current
    models, then Alembic is stamped at 'head'.
  * Existing database (including one restored from a dump) -> `flask db upgrade`
    applies any pending migrations and nothing else.

Why not just `flask db upgrade`?
--------------------------------
It cannot build this schema from scratch. The baseline revision b033ca5044ab
runs `batch_alter_table('user')`, i.e. it assumes the core tables already
exist -- they were originally created with db.create_all(), and no migration
creates user, member, event, news, blog or rsvp. Against a blank database the
upgrade fails at the first revision with `NoSuchTableError: user`.

Safety
------
Nothing here drops or rewrites data. create_all() skips tables that already
exist, and the bootstrap branch only runs when there is no alembic_version row
at all, so a restored dump keeps its real migration position and is only ever
migrated forward. DATABASE_URL must be set explicitly: the script refuses to
run rather than silently initialising a local SQLite file.

Running it from your own machine against a managed database works too, but use
the database's PUBLIC connection URL -- internal hostnames such as
*.railway.internal only resolve from inside the platform's network:

    DATABASE_URL="postgresql://...public-host.../railway" python scripts/prepare_db.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app import create_app, db


def current_alembic_version():
    """Return the stamped revision, or None if the database has never been stamped."""
    inspector = inspect(db.engine)
    if "alembic_version" not in inspector.get_table_names():
        return None
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def bootstrap():
    """Build the schema from the models, then stamp Alembic at head."""
    from flask_migrate import stamp

    before = set(inspect(db.engine).get_table_names())
    print(f"Tables found: {len(before)}")
    print("No alembic_version -> treating this as a fresh database.")
    print("Creating tables from the current models...")

    db.create_all()

    created = sorted(set(inspect(db.engine).get_table_names()) - before)
    print(f"Tables created: {len(created)}")
    for name in created:
        print(f"  + {name}")

    stamp(revision="head")
    print(f"Stamped at: {current_alembic_version()}")
    print("\nThe admin user is created on app start by main.py:init_db().")
    print("Log in and change that password immediately.")


def migrate_forward(stamped):
    """Apply any pending migrations to an existing database."""
    from flask_migrate import upgrade

    print(f"Existing database, stamped at: {stamped}")
    print("Applying any pending migrations...")

    upgrade()

    now = current_alembic_version()
    if now == stamped:
        print(f"Already up to date at: {now}")
    else:
        print(f"Upgraded to: {now}")


def main():
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        print("Refusing to run: DATABASE_URL is not set.")
        print("Set it to the target database first, e.g.")
        print('  DATABASE_URL="postgresql://user:pass@host:5432/dbname" python scripts/prepare_db.py')
        return 1

    # Log where we are pointed, without ever printing credentials.
    host_part = database_url.split("@")[-1] if "@" in database_url else database_url
    print(f"Target database: {host_part}")

    app = create_app()
    with app.app_context():
        stamped = current_alembic_version()
        if stamped:
            migrate_forward(stamped)
        else:
            bootstrap()

        print(f"\nTotal tables now: {len(inspect(db.engine).get_table_names())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
