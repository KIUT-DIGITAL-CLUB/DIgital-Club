from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app.routes import auth_bp
from app.models import User, Member
from app import db
from app.id_generator import generate_digital_id
from datetime import datetime

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        course = request.form.get('course')
        year = request.form.get('year')
        
        # Validation
        if not all([email, password, confirm_password, full_name]):
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')
        
        # Create user
        user = User(email=email, role='student', is_approved=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create member profile
        member = Member(
            user_id=user.id,
            full_name=full_name,
            course=course,
            year=year
        )
        db.session.add(member)
        db.session.commit()
        
        flash('Registration successful! Your account is pending admin approval.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
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
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
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
