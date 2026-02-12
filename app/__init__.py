from flask import Flask, flash, redirect, url_for, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
import os
from datetime import datetime
from dotenv import load_dotenv
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def _migrate_password_hash_column():
    """Migrate password_hash column from varchar(128) to varchar(256) if needed"""
    try:
        from sqlalchemy import text
        
        # Check if using PostgreSQL
        db_uri = db.engine.url
        if 'postgresql' in str(db_uri):
            # PostgreSQL: Use ALTER TABLE
            with db.engine.connect() as conn:
                # Check current column type
                result = conn.execute(text("""
                    SELECT character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'user' 
                    AND column_name = 'password_hash'
                """))
                row = result.fetchone()
                
                if row and row[0] == 128:
                    print("Migrating password_hash column from varchar(128) to varchar(256)...")
                    conn.execute(text("ALTER TABLE \"user\" ALTER COLUMN password_hash TYPE VARCHAR(256)"))
                    conn.commit()
                    print("✓ Successfully migrated password_hash column to VARCHAR(256)")
                elif row and row[0] == 256:
                    pass  # Already correct, no action needed
        # SQLite doesn't need migration as it doesn't enforce length constraints
    except Exception as e:
        # Silently fail - migration is optional and might fail if column doesn't exist yet
        pass


def _migrate_user_active_account_column():
    """Compatibility migration: add user.is_active_account if missing."""
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        if 'user' not in inspector.get_table_names():
            return

        cols = {c['name'] for c in inspector.get_columns('user')}
        if 'is_active_account' in cols:
            return

        db_uri = str(db.engine.url)
        with db.engine.connect() as conn:
            if 'postgresql' in db_uri:
                conn.execute(
                    text('ALTER TABLE "user" ADD COLUMN is_active_account BOOLEAN NOT NULL DEFAULT TRUE')
                )
            else:
                # SQLite and others
                conn.execute(
                    text('ALTER TABLE "user" ADD COLUMN is_active_account BOOLEAN NOT NULL DEFAULT 1')
                )
            conn.commit()
    except Exception:
        # Keep startup resilient; proper Alembic migration still exists.
        pass


def _migrate_event_target_audience_column():
    """Compatibility migration: add event.target_audience if missing."""
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        if 'event' not in inspector.get_table_names():
            return

        cols = {c['name'] for c in inspector.get_columns('event')}
        if 'target_audience' in cols:
            return

        db_uri = str(db.engine.url)
        with db.engine.connect() as conn:
            if 'postgresql' in db_uri:
                conn.execute(
                    text("ALTER TABLE event ADD COLUMN target_audience VARCHAR(20) NOT NULL DEFAULT 'everyone'")
                )
            else:
                conn.execute(
                    text("ALTER TABLE event ADD COLUMN target_audience VARCHAR(20) NOT NULL DEFAULT 'everyone'")
                )
            conn.commit()
    except Exception:
        pass


def _migrate_rsvp_attendee_fields():
    """Compatibility migration: add RSVP attendee fields if missing."""
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        if 'rsvp' not in inspector.get_table_names():
            return
        cols = {c['name'] for c in inspector.get_columns('rsvp')}
        with db.engine.connect() as conn:
            if 'attendee_type' not in cols:
                conn.execute(text("ALTER TABLE rsvp ADD COLUMN attendee_type VARCHAR(20)"))
            if 'study_field' not in cols:
                conn.execute(text("ALTER TABLE rsvp ADD COLUMN study_field VARCHAR(100)"))
            if 'study_year' not in cols:
                conn.execute(text("ALTER TABLE rsvp ADD COLUMN study_year VARCHAR(20)"))
            if 'non_student_role' not in cols:
                conn.execute(text("ALTER TABLE rsvp ADD COLUMN non_student_role VARCHAR(30)"))
            conn.commit()
    except Exception:
        pass

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # whoops i checked that line above amd the secret key is secret not the default
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///digital_club_01.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['TURNSTILE_SITE_KEY'] = os.environ.get('TURNSTILE_SITE_KEY', '')
    app.config['TURNSTILE_SECRET_KEY'] = os.environ.get('TURNSTILE_SECRET_KEY', '')
    app.config['APP_TIMEZONE'] = os.environ.get('APP_TIMEZONE', 'UTC')
    
    # URL generation (for emails, etc.)
    # In production, set SERVER_NAME and PREFERRED_URL_SCHEME via environment variables:
    #   SERVER_NAME=digitalclub.kiut.ac.tz
    #   PREFERRED_URL_SCHEME=https
    app.config['SERVER_NAME'] = "digitalclub.kiut.ac.tz" # os.environ.get('SERVER_NAME')
    app.config['PREFERRED_URL_SCHEME'] = "https" #os.environ.get('PREFERRED_URL_SCHEME', 'https')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Do not auto-create tables here; schema changes must go through Alembic migrations.
    with app.app_context():
        # Keep this compatibility migration for existing databases.
        _migrate_password_hash_column()
        _migrate_user_active_account_column()
        _migrate_event_target_audience_column()
        _migrate_rsvp_attendee_fields()
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Create upload directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'gallery'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'digital_ids'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'competitions'), exist_ok=True)

    @app.context_processor
    def inject_guards():
        try:
            from app.models import CompetitionGuard
            today = datetime.now().date()
            guards = CompetitionGuard.query.filter(CompetitionGuard.week_end >= today).order_by(CompetitionGuard.week_start.desc()).all()
        except Exception:
            db.session.rollback()
            guards = []
        return {'guards_week': guards, 'current_year': datetime.now().year}

    @app.before_request
    def enforce_active_accounts():
        if current_user.is_authenticated and not getattr(current_user, 'is_active_account', True):
            logout_user()
            flash('Your account has been deactivated. Please contact an administrator.', 'error')
            return redirect(url_for('auth.login'))

    def _get_app_timezone():
        return None

    @app.before_request
    def track_daily_active_users():
        if not current_user.is_authenticated:
            return
        if request.endpoint == 'static' or request.path.startswith('/static/'):
            return
        if not (request.path.startswith('/admin') or request.path.startswith('/member')):
            return
        try:
            from app.models import DailyActiveUser
            local_date = datetime.utcnow().date()
            now_utc = datetime.utcnow()
            entry = DailyActiveUser.query.filter_by(
                user_id=current_user.id,
                activity_date=local_date
            ).first()
            if entry:
                entry.last_seen_at = now_utc
            else:
                entry = DailyActiveUser(
                    user_id=current_user.id,
                    activity_date=local_date,
                    first_seen_at=now_utc,
                    last_seen_at=now_utc
                )
                db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    # User loader for Flask-Login
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.member import member_bp
    from app.routes.verification import verification_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(member_bp, url_prefix='/member')
    app.register_blueprint(verification_bp)
    
    return app
