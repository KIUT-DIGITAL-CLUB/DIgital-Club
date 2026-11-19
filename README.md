## Digital Club – University Tech Club Platform (Flask)

Digital Club is a full-featured web platform built with Flask to help university technology clubs manage their community:
- **Student profiles & public portfolios**
- **Events & RSVPs**
- **News, blogs, and gallery**
- **Rewards, trophies, and membership payments**
- **Admin dashboard with analytics**
- **Digital member IDs & PDFs**

It is designed **for students to learn from**: the codebase is a practical example of how to build and structure a real Flask application that uses authentication, databases, file uploads, background tasks, and more.

---

## Features

- **Authentication & Roles**
  - Student registration and login
  - Admin / super-admin roles
  - Approval workflow before new users gain full access

- **Member Profiles & Portfolios**
  - Detailed member profiles (`name`, `course`, `year`, `bio`, social links, areas of interest)
  - Projects attached to each member
  - Public member profile pages for showcasing work

- **Digital Member IDs**
  - Unique member ID generation (e.g. `DC-2025-0001`)
  - ID image generation and storage under `static/uploads/digital_ids/`
  - PDF generation for IDs and membership documents

- **Events, RSVPs & Attendance**
  - Create and manage events
  - RSVP pages and status views
  - Event check-in and verification screens

- **News, Blogs & Gallery**
  - Admin can create news posts and blog posts
  - Public-facing blog and news pages
  - Image gallery of events and projects

- **Rewards, Trophies & Finance**
  - Reward points and reward history for members
  - Trophies and achievements
  - Membership payments and financial categories/periods
  - Basic financial reports

- **Admin Dashboard**
  - Overview of members, events, RSVPs, finances, and more
  - Admin-only management pages for content and members

---

## Tech Stack

- **Backend**
  - `Flask` – core web framework
  - `Flask-Login` – user sessions and authentication
  - `Flask-SQLAlchemy` – ORM for database models
  - `Flask-Migrate` – database migrations (Alembic)
  - `Werkzeug` – password hashing and utilities

- **Database**
  - **SQLite** by default (local development)
  - **PostgreSQL** supported via `psycopg2-binary` (production-ready)

- **Other Python Libraries**
  - `python-dotenv` – environment variable management
  - `Pillow` – image handling (profile pictures, IDs, gallery)
  - `qrcode` & `cairosvg` – QR codes / SVG rendering
  - `reportlab` – PDF generation
  - `requests` – HTTP requests (e.g., APIs, SMS gateways)

- **Frontend**
  - HTML templates using **Jinja2**
  - CSS (`app/static/css`)
  - JavaScript (`app/static/js`)

---

## Getting Started

### 1. Prerequisites

- **Python**: version specified in `pyproject.toml`:

```toml
[project]
requires-python = ">=3.13"
```

If you don’t have Python installed:
- On **Windows**: install from `https://www.python.org` and check “Add Python to PATH”.
- On **macOS**: use the official installer or a package manager like Homebrew (`brew install python`).

You also need:
- **Git** (to clone the repository)
- **pip** (bundled with Python) for installing dependencies from `requirements.txt`

---

### 2. Clone the Repository

Open **Terminal** (macOS) or **PowerShell** (Windows) and run:

```bash
git clone https://github.com/snavid/Digital-Club.git
cd "Digital Club"
```

> On Windows, if the folder has a space in the name (like `Digital Club`), make sure to wrap it in quotes when using `cd`.

---

### 3. Create & Activate a Virtual Environment

Using the **standard `venv` module**:

#### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If execution policy blocks the script, run PowerShell as Administrator and:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
```

#### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

Your prompt should now show `(.venv)` indicating the virtual environment is active.

---

### 4. Install Dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

Versions in `requirements.txt` are pinned, and `pyproject.toml` lists the same
pins. That is deliberate: unpinned ranges once let a deploy install a newer
SQLAlchemy that changed the default Postgres driver, so the server broke while
every laptop kept working. To upgrade something, change the pin in **both**
files, test, then deploy.

---

## Configuration

All configuration comes from environment variables, read in the app factory in
`app/__init__.py`. Locally they are loaded from a `.env` file by
`python-dotenv`; in production they are set on the host. `.env` is gitignored
and is never deployed.

### 1. Basic `.env` Setup

Copy the example file and fill it in. Every variable is documented there.

```bash
cp .env.example .env            # Linux/macOS
```

```powershell
Copy-Item .env.example .env     # Windows PowerShell
```

The two that matter most:

- `SECRET_KEY` – signs sessions **and** derives the key that encrypts secrets
  stored in the database (`app/secret_crypto.py`). Changing it logs everyone
  out and makes previously encrypted settings unreadable, so generate it once
  and keep it.
- `DATABASE_URL` – connection string.
  - local SQLite: `sqlite:///digital_club_01.db`
  - Postgres: `postgresql://user:password@host:5432/dbname`

> If `DATABASE_URL` is empty the app falls back to local SQLite and prints a
> warning at startup. On a hosted platform that fallback means an empty
> database that is wiped on every deploy, so always set it in production.
### 2. Email & SMS (Optional)

Email and SMS are optional. Set them in `.env`:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
FROM_EMAIL=

BEEM_API_KEY=
BEEM_SECRET_KEY=
```

These are read by `NotificationService` in `app/utils.py` and by `app/sms.py`.
Left empty, sending is skipped with a logged warning and the rest of the app
works normally. Never hardcode credentials in source: they end up in git
history, and this repository is public.

---
> For learning purposes you can skip real credentials and keep email/SMS features disabled; the rest of the app will still work.

---

## Running the App (Development)

Make sure:
- Your **virtual environment is active**
- You are in the project root (`Digital Club`)

### Option 1 – Run via `python main.py`

This is the simplest and recommended for students:

```bash
python main.py
```

What this does:
- Imports `create_app()` from `app/__init__.py`
- Initializes the database and ensures an **admin** user exists:
  - Email: `admin@digitalclub.kiut.ac.tz`
  - Password: `admin123`
    (for **development only**, do not use these in production)
- Starts Flask on `http://0.0.0.0:5051` with `debug=True`

Open your browser and navigate to:

```text
http://localhost:5051
```

Login with the admin credentials above to explore the admin dashboard.

### Option 2 – Run via `flask run`

If you prefer the `flask` CLI:

```bash
export FLASK_APP=main.py      # macOS / Linux
set FLASK_APP=main.py         # Windows cmd
$env:FLASK_APP = "main.py"    # Windows PowerShell

flask run --port 5051
```

---

## Database Migrations (Flask-Migrate)

Schema changes go through Alembic only. Nothing creates or alters tables at
runtime.

```bash
flask db upgrade                      # apply migrations (also run on deploy)
flask db migrate -m "what changed"    # after editing app/models.py
flask db upgrade                      # apply what you just generated
```

`flask db upgrade` builds the whole schema from an empty database, so a new
environment needs nothing else.

The history was squashed into a single baseline
(`migrations/versions/bacaa08da2ca_initial_schema.py`). The previous 18
revisions could not build a database from scratch: the first one altered the
`user` table, assuming it already existed because the tables had originally
been created with `db.create_all()`. If you have a database created before the
squash, point it at the new history once:

```bash
flask db stamp bacaa08da2ca
```

---

## Project Structure

High-level structure (simplified):

```text
Digital Club/
├─ app/
│  ├─ __init__.py          # Flask app factory, DB & login setup
│  ├─ models.py            # All database models (User, Member, Event, etc.)
│  ├─ id_generator.py      # Generates unique member IDs and assets
│  ├─ pdf_generator.py     # Utilities for generating PDFs (IDs, etc.)
│  ├─ utils.py             # Notification service, helpers (email/SMS, etc.)
│  ├─ sms.py               # SMS sending integration
│  ├─ routes/
│  │  ├─ __init__.py
│  │  ├─ main.py           # Public pages (home, about, events, etc.)
│  │  ├─ auth.py           # Registration, login, password reset, approval
│  │  ├─ admin.py          # Admin dashboard & management routes
│  │  ├─ member.py         # Logged-in member dashboard & profile routes
│  │  └─ verification.py   # ID / membership verification routes
│  ├─ templates/           # All Jinja2 HTML templates
│  │  ├─ admin/            # Admin dashboard views
│  │  ├─ auth/             # Login/register/reset templates
│  │  ├─ member/           # Member dashboard & profile templates
│  │  └─ *.html            # Public pages (index, about, blogs, etc.)
│  └─ static/
│     ├─ css/              # Stylesheets
│     ├─ js/               # Frontend JS
│     ├─ uploads/          # Uploaded images (profiles, gallery, blogs, IDs)
│     └─ DigitalClub_LOGO* # Logos and assets
├─ instance/
│  └─ digital_club_01.db   # Default SQLite DB (local development only)
├─ migrations/             # Alembic migrations (single baseline)
├─ tests/                  # Automated tests
├─ main.py                 # Application entrypoint (gunicorn loads main:app)
├─ .env.example            # Documented environment variables
├─ requirements.txt        # Pinned dependencies
├─ pyproject.toml          # Project metadata (same pins)
├─ Procfile                # Start command for platforms that read one
├─ gunicorn_conf.py        # Gunicorn configuration
├─ DEPLOY.md               # Deployment guide
├─ LICENSE                 # MIT License
└─ README.md               # This file
```

---

## Learning Guide – Where to Look in the Code

This project is intentionally rich so students can explore many real-world concepts.

- **1. Flask App Factory & Extensions**
  - File: `app/__init__.py`
  - Learn how `create_app()` configures the app, initializes `SQLAlchemy`, `LoginManager`, and `Migrate`, and registers blueprints.
  - See how upload folders and database tables are created at startup.

- **2. Database Models & Relationships**
  - File: `app/models.py`
  - Study how `User`, `Member`, `Project`, `Event`, `RewardTransaction`, `MembershipPayment`, `Trophy`, etc. are modeled.
  - Learn about:
    - Primary/foreign keys
    - One-to-one and one-to-many relationships
    - JSON fields, helper methods (e.g. `get_projects`, `get_areas_list`)

- **3. Authentication & Authorization**
  - Files: `app/routes/auth.py`, `app/models.py`, `app/__init__.py`
  - See how:
    - Registration and login are implemented
    - Passwords are hashed using Werkzeug
    - Flask-Login manages sessions and `login_required`
    - Roles (`admin`, `student`, `is_super_admin`) control access

- **4. Blueprints & Routing**
  - Files: `app/routes/main.py`, `admin.py`, `member.py`, `verification.py`
  - Learn:
    - How to organize routes with blueprints
    - How to separate public, member-only, and admin-only views
    - How URL prefixes (`/admin`, `/member`, etc.) are configured

- **5. Templates & Frontend Integration**
  - Directory: `app/templates/`
  - Study:
    - `base.html` and layout inheritance
    - How forms, tables, and modals are rendered
    - How Jinja2 templating is used to loop over data from the database

- **6. File Uploads & Media Handling**
  - Directories: `app/static/uploads/`, relevant routes in `member.py` and `admin.py`
  - Learn how user profile images, gallery images, blog images, and ID images are uploaded, validated, and served.

- **7. Digital ID & PDF Generation**
  - Files: `app/id_generator.py`, `app/pdf_generator.py`
  - See how:
    - Member IDs are generated and stored
    - Images and PDFs are created (e.g., for digital ID cards)

- **8. Notifications & Background Tasks**
  - File: `app/utils.py`
  - Contains `NotificationService` which:
    - Sends emails (synchronously and in background threads)
    - Integrates with SMS (e.g., Twilio)
  - Learn about working with background threads and app contexts in Flask.

---

## Running Tests

If you want to explore basic testing:

1. Install test dependencies (if any are listed in `pyproject.toml` or `dev` dependencies).
2. From the project root, run:

```bash
python -m pytest
```

or

```bash
pytest
```

The `tests/` folder (e.g., `tests/test_rsvp.py`) contains example tests to learn how to test Flask routes and database logic.

---

## Deployment

There is no Docker, no Redis and no background worker. The whole system is one
Python web process plus a Postgres database:

```bash
pip install -r requirements.txt
flask db upgrade                            # on every deploy
gunicorn -c gunicorn_conf.py main:app       # serve
```

`gunicorn_conf.py` binds `0.0.0.0:$PORT` and sizes its worker pool from the
container's CPU quota, so it works on a managed platform without tuning.

See **[DEPLOY.md](DEPLOY.md)** for the full step-by-step guide, the environment
variables to set, and how to keep uploaded files across deploys.

---

## Contributing (For Students)

This project is an **open learning playground**. Here’s how you can contribute:

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally and create a new branch:

   ```bash
   git checkout -b my-feature
   ```

3. Make changes (fix a bug, improve UI, add documentation, write tests, etc.).
4. Run the app and tests to ensure everything works.
5. **Commit** your changes with a clear message and **push** the branch.
6. Open a **Pull Request** describing what you changed and why.

### Good First Ideas

- Improve or add comments to `app/models.py` or route handlers.
- Create new tests in `tests/`.
- Enhance front-end styling in `app/static/css/`.
- Add new learning notes or mini-tutorials to this README.

---

## FAQ

- **Q: I get an error about the database. What should I do?**
  - Ensure your virtual environment is active.
  - Check that `DATABASE_URL` is correct in `.env`.
  - Delete `instance/digital_club_01.db` (for a clean slate) and run `python main.py` again.

- **Q: Can I use a different port instead of 5051?**
  - Yes. Set the `PORT` environment variable before running:
    - macOS/Linux: `export PORT=5000`
    - Windows PowerShell: `$env:PORT = 5000`

- **Q: Is it safe to use the default admin credentials?**
  - **No, not in production.** They are for **local development and learning only**. Always change them in a real deployment.

---

## Acknowledgements

<!-- - **Special thanks to Yunus (`snavid` on GitHub)** – for envisioning and building Digital Club so that university students have a real, modern codebase to learn from.
  Your work turns a dream of a connected, empowered developer community into reality. -->

- Thanks to the open-source ecosystem around **Flask**, **SQLAlchemy**, and many other libraries that make this project possible.

---

## License

This project is licensed under the **MIT License**.
See the `LICENSE` file for full details.
