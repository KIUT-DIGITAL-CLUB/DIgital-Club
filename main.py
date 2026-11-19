import os
import sys

from app import create_app, db
from app.models import User

app = create_app()

DEFAULT_ADMIN_EMAIL = "admin@digitalclub.kiut.ac.tz"


def _running_under_flask_cli():
    """True while a `flask ...` command (e.g. `flask db upgrade`) is running.

    The admin seed must not run then: during the very first `flask db upgrade`
    the tables do not exist yet, so querying User only produced a confusing
    error in the deploy log. The seed still runs when a server imports this
    module, which is the case that matters.
    """
    if os.environ.get("FLASK_RUN_FROM_CLI") == "true":
        return True
    return os.path.basename(sys.argv[0] or "").startswith("flask")


def init_db():
    """Create the initial admin account if it does not exist. Idempotent.

    Credentials come from ADMIN_EMAIL / ADMIN_PASSWORD when set. Set
    ADMIN_PASSWORD in the environment before the first deploy: the fallback
    below is a well-known value and is only meant for local development.
    """
    email = os.environ.get("ADMIN_EMAIL") or DEFAULT_ADMIN_EMAIL
    password = os.environ.get("ADMIN_PASSWORD") or "admin123"

    if User.query.filter_by(email=email).first():
        return

    admin_user = User(
        email=email,
        role="admin",
        is_approved=True,
        is_super_admin=True,
    )
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()

    print(f"Admin user created: {email}")
    if not os.environ.get("ADMIN_PASSWORD"):
        print(
            "WARNING: created with the default development password. "
            "Change it now, or set ADMIN_PASSWORD and recreate the account."
        )


def seed_admin_if_possible():
    """Run the seed, but never let it stop the app from starting."""
    if _running_under_flask_cli():
        return
    try:
        with app.app_context():
            init_db()
    except Exception as exc:
        # An unmigrated or unreachable database must not prevent boot; the
        # deploy's `flask db upgrade` step is what reports schema problems.
        print(f"Skipping admin seed: {exc}")


seed_admin_if_possible()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
