from flask import render_template, request, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from app.routes import member_bp
from app.models import Member, Project, User
from app import db
from app.id_generator import generate_digital_id, delete_digital_id
import os
import json
from datetime import datetime

@member_bp.route('/')
@login_required
def dashboard():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    return render_template('member/dashboard.html', member=current_user.member)

@member_bp.route('/profile')
@login_required
def profile():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    return render_template('member/profile.html', member=current_user.member)

@member_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    member = current_user.member
    
    if request.method == 'POST':
        # Update member information
        if not member:
            member = Member(user_id=current_user.id)
            db.session.add(member)
        
        member.full_name = request.form.get('full_name')
        member.title = request.form.get('title')
        member.bio = request.form.get('bio')
        member.course = request.form.get('course')
        member.year = request.form.get('year')
        member.status = request.form.get('status')
        member.phone = request.form.get('phone')
        member.github = request.form.get('github')
        member.linkedin = request.form.get('linkedin')
        member.areas_of_interest = request.form.get('areas_of_interest')
        
        # Handle projects (JSON format)
        projects_text = request.form.get('projects')
        if projects_text:
            try:
                projects_list = json.loads(projects_text)
                member.set_projects(projects_list)
            except:
                flash('Invalid projects format. Please use valid JSON.', 'error')
                return render_template('member/edit_profile.html', member=member)
        
        # Handle profile image upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    # Create unique filename
                    timestamp = str(int(datetime.utcnow().timestamp()))
                    filename = f"{current_user.id}_{timestamp}_{filename}"
                    
                    # Save file
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
                    file.save(upload_path)
                    
                    # Delete old image if exists
                    if member.profile_image:
                        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', member.profile_image)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    member.profile_image = filename
                else:
                    flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'error')
                    return render_template('member/edit_profile.html', member=member)
        
        db.session.commit()
        
        # Auto-regenerate digital ID after profile update
        try:
            if member.digital_id_path:
                delete_digital_id(member)
            generate_digital_id(member)
            db.session.commit()
        except Exception as e:
            # Don't fail the profile update if ID generation fails
            print(f"Error regenerating digital ID: {e}")
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('member.dashboard'))
    
    return render_template('member/edit_profile.html', member=member)

@member_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('member/change_password.html')
        
        # Validate new password
        if not new_password or len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return render_template('member/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('member/change_password.html')
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password updated successfully!', 'success')
        return redirect(url_for('member.dashboard'))
    
    return render_template('member/change_password.html')

@member_bp.route('/projects')
@login_required
def my_projects():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    # Get member's projects
    projects = Project.query.filter_by(member_id=current_user.member.id).order_by(Project.created_at.desc()).all()
    return render_template('member/my_projects.html', projects=projects)

@member_bp.route('/projects/add', methods=['GET', 'POST'])
@login_required
def add_project():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        github_link = request.form.get('github_link')
        demo_link = request.form.get('demo_link')
        technologies = request.form.get('technologies')
        is_public = 'is_public' in request.form
        
        project = Project(
            title=title,
            description=description,
            image=request.form.get('image'),
            github_link=github_link,
            demo_link=demo_link,
            technologies=technologies,
            member_id=current_user.member.id,
            is_public=is_public,
            is_admin_project=False
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash('Project added successfully!', 'success')
        return redirect(url_for('member.my_projects'))
    
    return render_template('member/add_project.html')

@member_bp.route('/projects/edit/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    project = Project.query.filter_by(id=project_id, member_id=current_user.member.id).first_or_404()
    
    if request.method == 'POST':
        project.title = request.form.get('title')
        project.description = request.form.get('description')
        project.image = request.form.get('image')
        project.github_link = request.form.get('github_link')
        project.demo_link = request.form.get('demo_link')
        project.technologies = request.form.get('technologies')
        project.is_public = 'is_public' in request.form
        
        db.session.commit()
        
        flash('Project updated successfully!', 'success')
        return redirect(url_for('member.my_projects'))
    
    return render_template('member/edit_project.html', project=project)

@member_bp.route('/projects/delete/<int:project_id>')
@login_required
def delete_project(project_id):
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    project = Project.query.filter_by(id=project_id, member_id=current_user.member.id).first_or_404()
    
    db.session.delete(project)
    db.session.commit()
    
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('member.my_projects'))

@member_bp.route('/digital-id')
@login_required
def digital_id():
    """Display member's digital ID card"""
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    member = current_user.member
    
    # Generate ID if it doesn't exist or needs regeneration
    if member.needs_id_regeneration():
        try:
            generate_digital_id(member)
            db.session.commit()
            flash('Digital ID generated successfully!', 'success')
        except Exception as e:
            flash(f'Error generating digital ID: {str(e)}', 'error')
            return redirect(url_for('member.dashboard'))
    
    return render_template('member/digital_id.html', member=member)

@member_bp.route('/download-id')
@member_bp.route('/download-id/<side>')
@login_required
def download_id(side='front'):
    """Download member's digital ID card as an image (front or back)"""
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    member = current_user.member
    
    # Generate ID if it doesn't exist
    if member.needs_id_regeneration():
        try:
            generate_digital_id(member)
            db.session.commit()
        except Exception as e:
            flash(f'Error generating digital ID: {str(e)}', 'error')
            return redirect(url_for('member.dashboard'))
    
    # Determine which side to download
    if side == 'back':
        filename = member.digital_id_path.replace('_front.png', '_back.png')
        if not filename.endswith('_back.png'):
            # Handle old format
            filename = member.digital_id_path.replace('.png', '_back.png')
        download_name = f'DigitalClub_ID_{member.member_id_number}_back.png'
    else:
        filename = member.digital_id_path
        download_name = f'DigitalClub_ID_{member.member_id_number}_front.png'
    
    # Send file for download
    id_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_ids', filename)
    
    if not os.path.exists(id_path):
        flash(f'ID card {side} file not found. Please regenerate.', 'error')
        return redirect(url_for('member.digital_id'))
    
    return send_file(
        id_path,
        as_attachment=True,
        download_name=download_name,
        mimetype='image/png'
    )

@member_bp.route('/regenerate-id')
@login_required
def regenerate_id():
    """Manually regenerate member's digital ID card"""
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    member = current_user.member
    
    try:
        # Delete old ID if exists
        if member.digital_id_path:
            delete_digital_id(member)
        
        # Generate new ID
        generate_digital_id(member)
        db.session.commit()
        
        flash('Digital ID regenerated successfully!', 'success')
    except Exception as e:
        flash(f'Error regenerating digital ID: {str(e)}', 'error')
    
    return redirect(url_for('member.digital_id'))
