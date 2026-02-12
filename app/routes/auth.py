from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from urllib.parse import urlparse
from app.routes import auth_bp
from app.models import User, Member
from app import db
from app.id_generator import generate_digital_id
from app.utils import get_notification_service
from app.member_requirements import ALLOWED_COURSES, ALLOWED_YEARS, is_allowed_course, is_allowed_year
from datetime import datetime


def _get_serializer():
    """Create a serializer for generating secure tokens."""
    secret_key = current_app.config.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError("SECRET_KEY is not configured")
    return URLSafeTimedSerializer(secret_key, salt='password-reset-salt')


def generate_password_reset_token(user):
    """Generate a time-limited password reset token for a user."""
    s = _get_serializer()
    return s.dumps({'user_id': user.id, 'email': user.email})


def verify_password_reset_token(token, max_age=3600 * 24):
    """Verify a password reset token and return the user if valid."""
    s = _get_serializer()
    try:
        data = s.loads(token, max_age=max_age)
    except SignatureExpired:
        return None  # Token valid but expired
    except BadSignature:
        return None  # Invalid token

    user_id = data.get('user_id')
    email = data.get('email')
    if not user_id or not email:
        return None

    user = User.query.get(user_id)
    if not user or user.email != email:
        return None

    return user


def _is_safe_next_url(target):
    """Allow only local redirects for `next`."""
    if not target:
        return False
    parsed = urlparse(target)
    return parsed.scheme == '' and parsed.netloc == '' and target.startswith('/')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = (request.form.get('full_name') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        course = (request.form.get('course') or '').strip()
        year = (request.form.get('year') or '').strip()
        
        # Validation
        if not all([email, password, confirm_password, full_name, phone, course, year]):
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)

        if not is_allowed_course(course):
            flash('Please select a valid course from the list.', 'error')
            return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)

        if not is_allowed_year(year):
            flash('Please select a valid year from the list.', 'error')
            return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)
        
        # Create user
        user = User(email=email, role='student', is_approved=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        def _normalize_name(value):
            parts = [p for p in (value or '').strip().split() if p]
            return ' '.join([p[:1].upper() + p[1:].lower() for p in parts])

        # Create member profile
        member = Member(
            user_id=user.id,
            full_name=_normalize_name(full_name),
            phone=phone,
            course=course,
            year=year
        )
        db.session.add(member)
        db.session.commit()
        
        flash('Registration successful! Your account is pending admin approval.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', allowed_courses=ALLOWED_COURSES, allowed_years=ALLOWED_YEARS)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active_account:
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
                return render_template('auth/login.html')
            if not user.is_approved and user.role == 'student':
                flash('Your account is pending admin approval.', 'warning')
                return render_template('auth/approval_pending.html')
            
            login_user(user)
            
            # Auto-generate digital ID if member doesn't have one
            if user.member and user.member.needs_id_regeneration():
                try:
                    generate_digital_id(user.member)
                    db.session.commit()
                except Exception as e:
                    # Don't fail login if ID generation fails
                    print(f"Error generating digital ID on login: {e}")
            
            next_page = request.args.get('next')
            if _is_safe_next_url(next_page):
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            member = user.member
            if not member or not (member.phone or '').strip() or not is_allowed_course(member.course):
                flash('Please complete your profile details (valid course and phone number) to continue.', 'warning')
                return redirect(url_for('member.profile'))
            return redirect(url_for('member.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/approval-pending')
def approval_pending():
    return render_template('auth/approval_pending.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset link via email."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        print("this part was excuted 456")
        email = request.form.get('email')
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/forgot_password.html')

        user = User.query.filter_by(email=email).first()
        member : Member = Member.query.filter_by(user_id=user.id).first()

        # For security, always show the same message even if the email is not registered
        if user:
            try:
                token = generate_password_reset_token(user)
                reset_url = url_for('auth.reset_password', token=token, _external=True)

                subject = "Reset your Digital Club password"
                html_body = render_template('auth/email_reset_password.html', reset_url=reset_url, user=user)
                print("this part was excuted 123")
                notification_service = get_notification_service()
                notification_service.send_email(
                    to_email=user.email,
                    subject=subject,
                    message=html_body,
                    is_html=True
                )
                print(member.phone)
                print(reset_url)
                print("sending sms")
                notification_service.send_sms(member.phone, "We received a request to reset your password. Use the link below to set a new one: \n"  + reset_url + " \n \n If you did not request this, please ignore this message")
            except Exception as e:
                current_app.logger.error(f"Error sending password reset email: {e}")
                # Still show generic message below

        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using a token sent via email."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = verify_password_reset_token(token)
    if not user:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)

        # Update password
        user.set_password(password)
        db.session.commit()

        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
