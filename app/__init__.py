from flask import Flask, flash, redirect, url_for, request, current_app, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from app.time_utils import utc_to_app_naive, app_timezone_label
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # whoops i checked that line above amd the secret key is secret not the default
    
    database_url = (os.environ.get('DATABASE_URL') or '').strip()
    if not database_url:
        # Do not let this fail silently: on a hosted platform the SQLite file
        # lives on an ephemeral disk, so the app would come up looking healthy
        # with an empty database and lose every write on the next deploy.
        print(
            "\n" + "!" * 72 +
            "\n!! DATABASE_URL is not set - falling back to local SQLite."
            "\n!! In production this means: EMPTY DATABASE, DATA LOST ON EVERY DEPLOY."
            "\n!! Set DATABASE_URL to your Postgres connection string."
            "\n" + "!" * 72 + "\n",
            flush=True,
        )
        database_url = 'sqlite:///digital_club_01.db'
    elif database_url.startswith('postgres://'):
        # Some providers hand out the legacy "postgres://" scheme, which
        # SQLAlchemy rejects. Normalise it to the scheme it accepts.
        database_url = 'postgresql://' + database_url[len('postgres://'):]
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['TURNSTILE_SITE_KEY'] = os.environ.get('TURNSTILE_SITE_KEY', '')
    app.config['TURNSTILE_SECRET_KEY'] = os.environ.get('TURNSTILE_SECRET_KEY', '')
    app.config['APP_TIMEZONE'] = os.environ.get('APP_TIMEZONE', 'Africa/Nairobi')
    app.config['APP_UTC_OFFSET_HOURS'] = os.environ.get('APP_UTC_OFFSET_HOURS', '3')
    # Session / remember-me settings
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=int(os.environ.get('SESSION_LIFETIME_DAYS', '30')))
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=int(os.environ.get('REMEMBER_LIFETIME_DAYS', '30')))
    app.config['REMEMBER_COOKIE_SECURE'] = os.environ.get('REMEMBER_COOKIE_SECURE', '1') == '1'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # URL generation (for emails, etc.)
    # Leave SERVER_NAME unset in hosted environments (Railway, etc.): when it is set,
    # Flask returns 404 for any request whose Host header does not match it, which breaks
    # platform healthchecks and *.up.railway.app domains. Unset, url_for(_external=True)
    # derives the host from the incoming request, which is what we want.
    # Only set SERVER_NAME when URLs must be built outside a request context.
    app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME') or None
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Schema changes go through Alembic only: `flask db upgrade` on deploy.
    
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
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'elections', 'passports'), exist_ok=True)

    @app.route('/healthz')
    def healthz():
        """Lightweight liveness probe for hosted platforms (no DB, no templates).

        Use this as the platform healthcheck path: '/' returns a 302 to /home,
        and /home renders the full homepage with database queries.
        """
        return jsonify(status='ok'), 200

    @app.template_filter('app_local')
    def app_local_filter(value):
        return utc_to_app_naive(value)

    @app.context_processor
    def inject_member_notification_counts():
        unread_member_notifications = 0
        try:
            from app.models import MemberNotification
            if current_user.is_authenticated and current_user.role != 'admin' and getattr(current_user, 'member', None):
                unread_member_notifications = MemberNotification.query.filter_by(
                    member_id=current_user.member.id,
                    is_read=False
                ).count()
        except Exception:
            unread_member_notifications = 0
        return {
            'unread_member_notifications': unread_member_notifications
        }

    @app.context_processor
    def inject_guards():
        try:
            from app.models import CompetitionGuard
            all_guards = CompetitionGuard.query.order_by(
                CompetitionGuard.created_at.desc(),
                CompetitionGuard.id.desc()
            ).all()
            # Keep the latest guard per level so widget always shows current champions by level.
            seen_levels = set()
            guards = []
            for g in all_guards:
                if g.level in seen_levels:
                    continue
                guards.append(g)
                seen_levels.add(g.level)
                if len(guards) >= 3:
                    break
            guards.sort(key=lambda item: item.level)
        except Exception:
            db.session.rollback()
            guards = []
        return {
            'guards_week': guards,
            'current_year': datetime.now().year,
            'app_timezone_label': app_timezone_label()
        }

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
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            local_date = utc_to_app_naive(now_utc).date()
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
    
    # Register blueprints (election route modules must import before register_blueprint)
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.member import member_bp
    from app.routes.verification import verification_bp
    from app.routes import election_admin  # noqa: F401
    from app.routes import election_member  # noqa: F401

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(member_bp, url_prefix='/member')
    app.register_blueprint(verification_bp)

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return redirect(url_for('main.index'))

    return app
