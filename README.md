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
- Optionally: **uv** or **pip** for dependency management (this project already includes `pyproject.toml` and `uv.lock`).

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

With the virtual environment activated, install dependencies defined in `pyproject.toml`.

#### Option A – Using `pip`

```bash
pip install uv
uv pip sync
```

This uses `uv` to sync dependencies from `uv.lock`.  
If you prefer plain `pip` only:

```bash
pip install -e .
```

#### Option B – Using `uv` Directly

If you already have `uv` installed:

```bash
uv sync
```

---

## Configuration

The app reads configuration mainly from:
- Environment variables (via `python-dotenv`)
- The Flask `app.config` in `app/__init__.py`
- Optional `config.py` (for email/SMS, based on `config_example.py`)

### 1. Basic `.env` Setup

Create a `.env` file in the **project root**:

```bash
cp config_example.1env config.py  # (Linux/macOS)
```

On **Windows** (PowerShell), just copy the file using Explorer or:

```powershell
Copy-Item config_example.1env config.py
```

Then, create a `.env` file (using any editor) with at least:

```env
SECRET_KEY=your-very-secret-key
DATABASE_URL=sqlite:///digital_club_01.db
FLASK_ENV=development
```

- `SECRET_KEY`: used by Flask for sessions and security (keep it secret in real deployments).
- `DATABASE_URL`: database connection string.
  - For local SQLite (default): `sqlite:///digital_club_01.db`
  - For PostgreSQL: something like `postgresql+psycopg2://digital_club_user:digital_club_password@db:5432/digital_club_db`

> In `app/__init__.py`, if `DATABASE_URL` is not set, it falls back to `sqlite:///digital_club_01.db` in the project root.
### 2. Email & SMS (Optional)

For email/SMS notifications, configure values in `.env` (copied from `config_example.1env`):

```python
BEEM_API_KEY = '19example62d4ee1b0726e'
BEEM_SECRET_KEY = 'example_MGMwNGJlZWM5NNlMDA1YmNiYjk0U4OGZlY2I0OY2MDzY4NWNlNTMzdDZlYjE5NTE1ZWkYTk2MTVlOTQ4YzJhNg=='

```

These are used by the `NotificationService` in `app/utils.py` and `app/sms.py` to send emails and SMS (e.g., confirmations, alerts).
Also used to attach dockerized postgresql in `app/__init__.py`
> For learning purposes you can skip real credentials and keep email/SMS features disabled; the rest of the app will still work.

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

This project includes a `migrations/` folder and uses **Flask-Migrate**:

Common commands (from the project root, with venv active):

```bash
flask db init        # only once, already done in this repo
flask db migrate -m "Your message"
flask db upgrade
```

This lets you evolve the database schema safely as you change the models in `app/models.py`.

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
│  └─ digital_club_01.db   # Default SQLite DB (if used)
├─ migrations/             # Alembic migration scripts
├─ scripts/                # Data migration and maintenance scripts
├─ tests/                  # Automated tests
├─ main.py                 # Application entrypoint
├─ config_example.py       # Example email/SMS configuration
├─ pyproject.toml          # Project metadata & dependencies
├─ Dockerfile              # Container image definition
├─ docker-compose.yml      # Multi-service (e.g., app + DB) setup
├─ gunicorn_conf.py        # Gunicorn configuration
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

## Scripts & Data Migration

The `scripts/` folder includes maintenance and migration utilities, for example:

- `scripts/migration/migrate_digital_ids.py`
- `scripts/migration/migrate_rewards_system.py`
- `scripts/migration/migrate_rsvp.py`
- `scripts/migration/migrate_super_admin.py`

These are great resources to learn:
- How to write one-off data migration scripts
- How to interact with the models outside of normal request/response flow

You can run them with:

```bash
python scripts/migration/migrate_rsvp.py
```

> Tip: Always back up your database before running migration scripts in a real deployment.

---

## Deployment Notes (Educational Overview)

This repo includes:
- `Dockerfile` – how to build a Docker image for the app
- `docker-compose.yml` – how to run the app together with services like PostgreSQL
- `gunicorn_conf.py` – configuration for Gunicorn (a production WSGI server)

Typical high-level steps (conceptual):
1. Build the image: `docker build -t digital-club .`
2. Run with Docker Compose: `docker compose up`
3. Serve via Gunicorn and a reverse proxy (like Nginx)

As a student, you can explore these files to understand **how a Flask app moves from your laptop to a server**.

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
