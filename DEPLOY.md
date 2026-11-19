# Deployment

The system is one Python web process plus a Postgres database. No Docker, no
Redis, no background workers, no reverse proxy to configure.

```bash
pip install -r requirements.txt
flask db upgrade                            # schema check, every deploy
gunicorn -c gunicorn_conf.py main:app       # serve
```

`flask db upgrade` builds the entire schema from an empty database and is a
no-op once the database is current, so it is safe to run on every deploy and
should be wired into the deploy step rather than run by hand.

---

## Railway

### 1. Create the services

1. **New Project → Deploy from GitHub repo** → this repository, branch `master`.
   The build is detected automatically from `requirements.txt`; there is no
   Dockerfile any more.
2. **+ New → Database → Postgres.**

### 2. Settings → Deploy (on the web service)

| Setting | Value |
|---|---|
| Pre-deploy command | `flask db upgrade` |
| Start command | `gunicorn -c gunicorn_conf.py main:app` |
| Healthcheck path | `/healthz` |
| Healthcheck timeout | `300` |

`/healthz` returns `{"status":"ok"}` without touching the database or rendering
a template. Do not point the healthcheck at `/`: it redirects to `/home`, which
runs database queries.

### 3. Variables

Use the **Add Reference** picker for the database so the value is always right,
rather than typing a service name:

| Variable | Value |
|---|---|
| `DATABASE_URL` | reference → Postgres → `DATABASE_URL` |
| `SECRET_KEY` | a long random string, generated once and kept |
| `ADMIN_PASSWORD` | the first admin account's password |
| `GUNICORN_WORKERS` | `3` |
| `APP_TIMEZONE` | `Africa/Nairobi` |
| `APP_UTC_OFFSET_HOURS` | `3` |
| `TURNSTILE_SITE_KEY` | from Cloudflare |
| `TURNSTILE_SECRET_KEY` | from Cloudflare |
| `BEEM_API_KEY` / `BEEM_SECRET_KEY` | for SMS notifications (optional) |
| `SMTP_USERNAME` / `SMTP_PASSWORD` / `FROM_EMAIL` | for email (optional) |

Do **not** set:

- `PORT` — Railway injects it and routes the domain to that exact port. Setting
  it yourself breaks that guarantee unless the domain's target port matches.
- `SERVER_NAME` — when set, Flask returns 404 for any request whose `Host`
  header does not match, which breaks the healthcheck and the generated
  `*.up.railway.app` domain.

`.env` is gitignored and is not part of the deploy. Variables set in the
dashboard are the only ones the app sees.

### 4. Volume for uploaded files

Profile photos, generated digital ID cards, election passport photos,
competition submissions and gallery images are written to disk. The filesystem
is wiped on every deploy, so attach a volume:

**Settings → Volumes → mount path `/app/app/static/uploads`**

The doubled `app` is correct: the path is `<project>/app/static/uploads`.

For anything long-lived, object storage (S3, Cloudflare R2) is the better end
state — a volume pins the service to a single replica and is not backed up.
Every write already goes through `current_app.config['UPLOAD_FOLDER']`, so that
change is contained.

### 5. Go live

Verify on the generated `*.up.railway.app` domain first: log in, open a
member's digital ID, upload a profile photo, redeploy, and confirm the photo
survived — that last step is what proves the volume is working. Only then point
DNS at the custom domain under Settings → Networking.

---

## Required Turnstile keys

Login is gated on Cloudflare Turnstile being configured
(`app/routes/auth.py`): with `TURNSTILE_SITE_KEY` or `TURNSTILE_SECRET_KEY`
missing, every login attempt is refused with "Cloudflare Turnstile is not
configured yet." Set both before announcing the site.

---

## The first admin account

On first start the app creates a super-admin from `ADMIN_EMAIL` (default
`admin@digitalclub.kiut.ac.tz`) and `ADMIN_PASSWORD`. If `ADMIN_PASSWORD` is
unset it falls back to a default development password that is published in this
repository and logs a warning. Set `ADMIN_PASSWORD` before the first deploy.

---

## Migrating from an existing database

A database created before the migration history was squashed is already at the
right schema but is stamped at a revision that no longer exists, such as
`c20260703100000`. Alembic cannot place it and every command fails with:

```
Can't locate revision identified by 'c20260703100000'
```

Nothing needs to be done about this. `migrations/env.py` detects a stamped
revision that is not in `migrations/versions`, clears that one record, and lets
the migration run; the baseline then finds the existing schema, creates
nothing, and stamps the database at the current head. Tables and data are not
touched. The deploy log shows the warning:

```
Database is stamped at 'c20260703100000', which is not in migrations/versions
(the history was squashed). Clearing the stale record so the migration can
run; the schema itself is left alone.
```

A revision that *is* in `migrations/versions` is never cleared, so this cannot
skip a real migration. There is no need to edit `alembic_version` by hand, and
`flask db stamp` would itself fail on such a database — it has to resolve the
current revision before it can set a new one.

To move data from a previous host, dump and restore. Use the
database's **public** connection URL from outside the platform — internal
hostnames such as `*.railway.internal` only resolve from inside it.

```bash
# on the old host
pg_dump -U <user> -Fc <dbname> > dc.dump

# into the new database
pg_restore --no-owner --no-acl -d "<DATABASE_PUBLIC_URL>" dc.dump
```

Uploaded files live in `app/static/uploads` on the old host. Copy that
directory into the volume (`railway ssh`, then extract a tarball into
`/app/app/static/uploads`).

Quiz tables from before the quiz feature was removed are simply not referenced
any more. Drop them manually if you want the space back.

---

## Troubleshooting

**502 / "Application failed to respond"** — nothing is listening on the port
Railway routes to. Check the deploy log for gunicorn's
`Listening at: http://0.0.0.0:...` line. If workers boot in an endless climbing
list of pids, the container is being OOM-killed: set `GUNICORN_WORKERS=3`.

**`no such table: user` / `relation "user" does not exist`** — the pre-deploy
`flask db upgrade` did not run, or ran against a different database.

**`Can't locate revision identified by '<id>'`** — see *Migrating from an
existing database* above; this now recovers on its own, so if it still appears
the deploy is running an older copy of `migrations/env.py`.

**Startup banner `!! DATABASE_URL is not set`** — the variable is missing or
empty (a variable reference that fails to resolve is passed through as an empty
string). The app is running on throwaway SQLite until it is fixed.

**`ModuleNotFoundError: No module named 'psycopg'`** — dependencies were
installed from somewhere other than `requirements.txt`. Both Postgres drivers
are pinned there.
