from flask import render_template, request, flash, redirect, url_for, current_app, send_file, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from app.routes import member_bp
from app.models import (
    Member,
    Project,
    User,
    RewardTransaction,
    Trophy,
    MembershipPayment,
    RSVP,
    FinancialPeriod,
    Competition,
    CompetitionJudge,
    CompetitionCriteria,
    CompetitionSubmission,
    CompetitionScore,
    CompetitionSponsorLink,
    CompetitionEnrollment,
    CompetitionTeamEnrollment,
    CompetitionTeamEnrollmentMember,
    CompetitionTeamSubmission,
    TeamCompetitionPoint,
    CompetitionReward,
    SessionWeek,
    SessionSchedule,
    SessionReport,
    Team,
    TeamMember,
    Event,
    Quiz,
    QuizQuestion,
    QuizOption,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizViolation,
    QuizLeaderboard,
    QuizReminderPreference,
    QuizReminderNotification,
    MemberNotification,
)
from app import db
from app.utils import get_notification_service
from app.id_generator import generate_digital_id, delete_digital_id
from app.member_requirements import is_allowed_course
from app.quiz_constants import QUIZ_MAX_VIOLATIONS
from app.time_utils import app_now_naive
import os
import json
import math
from datetime import datetime, timedelta
import random
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

def _normalize_name(value):
    parts = [p for p in (value or '').strip().split() if p]
    return ' '.join([p[:1].upper() + p[1:].lower() for p in parts])


@member_bp.before_request
def enforce_profile_completion():
    """Require core profile fields before accessing most member panel pages."""
    if not current_user.is_authenticated:
        return None
    if current_user.role == 'admin':
        return None

    endpoint = request.endpoint or ''
    allowed_endpoints = {
        'member.profile',
        'member.edit_profile',
        'member.change_password',
    }
    if endpoint in allowed_endpoints:
        return None

    member = current_user.member
    if not member or not (member.phone or '').strip() or not is_allowed_course(member.course):
        flash('Please complete your profile (valid course and phone number) before accessing the dashboard.', 'warning')
        return redirect(url_for('member.profile'))
    return None


@member_bp.route('/members/search')
@login_required
def members_search():
    """Live search endpoint for approved members."""
    q = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', default=10, type=int) or 10
    limit = max(1, min(limit, 30))

    query = Member.query.join(User).filter(User.is_approved == True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Member.full_name.ilike(like),
                Member.member_id_number.ilike(like),
                User.email.ilike(like),
                Member.course.ilike(like),
            )
        )

    members = query.order_by(Member.full_name.asc()).limit(limit).all()
    return jsonify({
        'results': [
            {
                'id': m.id,
                'full_name': m.full_name,
                'email': m.user.email if m.user else '',
                'member_id_number': m.member_id_number or '',
                'course': m.course or '',
                'year': m.year or '',
            }
            for m in members
        ]
    })


def _sessions_tables_available():
    try:
        table_names = set(inspect(db.engine).get_table_names())
        return 'session_week' in table_names and 'session_schedule' in table_names
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Failed to inspect sessions tables')
        return False
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to inspect sessions tables')
        return False


def _latest_published_session_week():
    if not _sessions_tables_available():
        return None
    try:
        return SessionWeek.query.filter_by(status='published').order_by(SessionWeek.week_start.desc()).first()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Failed to load latest published session week')
        return None
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to load latest published session week')
        return None

@member_bp.route('/')
@login_required
def dashboard():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    notices = CompetitionEnrollment.query.filter(
        CompetitionEnrollment.member_id == current_user.member.id,
        db.or_(
            CompetitionEnrollment.status == 'disqualified',
            CompetitionEnrollment.admin_notice.isnot(None)
        )
    ).join(Competition).order_by(
        db.func.coalesce(
            CompetitionEnrollment.disqualified_at,
            CompetitionEnrollment.admin_notice_at,
            CompetitionEnrollment.enrolled_at
        ).desc()
    ).all()
    member = current_user.member
    total_points = member.get_total_points()
    competitions_count = CompetitionSubmission.query.filter_by(member_id=member.id).count()
    best_rank = db.session.query(db.func.min(CompetitionSubmission.rank)).filter(
        CompetitionSubmission.member_id == member.id,
        CompetitionSubmission.rank.isnot(None)
    ).scalar()
    team_membership = TeamMember.query.filter_by(member_id=member.id).first()
    upcoming_sessions = []
    week = _latest_published_session_week()
    if week:
        upcoming_sessions = week.sessions.order_by(SessionSchedule.session_date.asc(), SessionSchedule.start_time.asc()).limit(5).all()
    recent_rewards = member.reward_transactions.order_by(RewardTransaction.created_at.desc()).limit(5).all()
    membership_status = member.get_membership_status()
    latest_membership_payment = member.get_latest_payment()
    return render_template(
        'member/dashboard.html',
        member=member,
        competition_notices=notices,
        total_points=total_points,
        competitions_count=competitions_count,
        best_rank=best_rank,
        team_membership=team_membership,
        upcoming_sessions=upcoming_sessions,
        recent_rewards=recent_rewards,
        membership_status=membership_status,
        latest_membership_payment=latest_membership_payment,
        current_date=datetime.now(),
    )

@member_bp.route('/profile')
@login_required
def profile():
    member = current_user.member

    # Fetch current financial period summary for members to view
    current_period = FinancialPeriod.query.filter_by(status='open').order_by(FinancialPeriod.start_date.desc()).first()
    period_totals = None
    if current_period:
        total_revenue = current_period.get_total_revenue()
        total_expenses = current_period.get_total_expenses()
        period_totals = {
            'revenue': total_revenue,
            'expenses': total_expenses,
            'net': total_revenue - total_expenses,
            'revenue_count': current_period.transactions.filter_by(transaction_type='revenue').count(),
            'expense_count': current_period.transactions.filter_by(transaction_type='expense').count(),
            'transaction_count': current_period.get_transaction_count(),
        }
    
    return render_template(
        'member/profile.html',
        member=member,
        current_period=current_period,
        period_totals=period_totals,
    )

@member_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'GET':
        return redirect(url_for('member.profile'))

    member = current_user.member
    
    if request.method == 'POST':
        # Update member information
        if not member:
            member = Member(user_id=current_user.id)
            db.session.add(member)
        
        member.full_name = _normalize_name(request.form.get('full_name'))
        member.title = request.form.get('title')
        member.bio = request.form.get('bio')
        member.course = (request.form.get('course') or '').strip()
        member.year = request.form.get('year')
        member.status = request.form.get('status')
        member.phone = (request.form.get('phone') or '').strip()
        member.github = request.form.get('github')
        member.linkedin = request.form.get('linkedin')
        member.areas_of_interest = request.form.get('areas_of_interest')
        
        if not member.phone:
            flash('Phone number is required.', 'error')
            return redirect(url_for('member.profile'))

        if not is_allowed_course(member.course):
            flash('Please select a valid course from the available list.', 'error')
            return redirect(url_for('member.profile'))

        # Handle projects (JSON format)
        projects_text = request.form.get('projects')
        if projects_text:
            try:
                projects_list = json.loads(projects_text)
                member.set_projects(projects_list)
            except:
                flash('Invalid projects format. Please use valid JSON.', 'error')
                return redirect(url_for('member.profile'))
        
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
                    return redirect(url_for('member.profile'))
        
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
        return redirect(url_for('member.profile'))

@member_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'GET':
        return redirect(url_for('member.profile'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('member.profile'))
        
        # Validate new password
        if not new_password or len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return redirect(url_for('member.profile'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('member.profile'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password updated successfully!', 'success')
        return redirect(url_for('member.profile'))

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
        return redirect(url_for('member.profile'))
    
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


@member_bp.route('/rewards')
@login_required
def rewards():
    """View member's rewards, points, and trophies"""
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    member = current_user.member
    
    # Get total points
    total_points = member.get_total_points()
    
    # Get earned trophies
    trophies = member.get_current_trophies()
    
    # Get all trophies for progress tracking
    all_trophies = Trophy.query.filter_by(is_active=True).order_by(Trophy.points_required.asc()).all()
    
    # Calculate progress to next trophy
    next_trophy = None
    points_to_next = 0
    for trophy in all_trophies:
        if total_points < trophy.points_required:
            next_trophy = trophy
            points_to_next = trophy.points_required - total_points
            break
    
    # Get recent transactions
    recent_transactions = member.reward_transactions.order_by(RewardTransaction.created_at.desc()).limit(20).all()
    
    # Get attendance history
    attendance = RSVP.query.filter_by(member_id=member.id, checked_in=True).order_by(RSVP.checked_in_at.desc()).all()
    
    return render_template('member/rewards.html',
                         member=member,
                         total_points=total_points,
                         trophies=trophies,
                         all_trophies=all_trophies,
                         next_trophy=next_trophy,
                         points_to_next=points_to_next,
                         recent_transactions=recent_transactions,
                         attendance=attendance)


@member_bp.route('/membership')
@login_required
def membership():
    """View member's membership payment status and history"""
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    member = current_user.member
    
    # Get membership status
    membership_status = member.get_membership_status()
    latest_payment = member.get_latest_payment()
    days_expired = member.get_days_since_expiration()
    
    # Get all payment history
    payments = member.membership_payments.order_by(MembershipPayment.payment_date.desc()).all()
    
    return render_template('member/membership.html',
                         member=member,
                         membership_status=membership_status,
                         latest_payment=latest_payment,
                         days_expired=days_expired,
                         payments=payments)


def _member_primary_team(member_id):
    return TeamMember.query.filter_by(member_id=member_id, status='approved').first()


def _team_is_leader(team_id, member_id):
    return TeamMember.query.filter_by(team_id=team_id, member_id=member_id, status='approved', is_leader=True).first() is not None


@member_bp.route('/teams', methods=['GET', 'POST'])
@login_required
def teams_hub():
    member = current_user.member
    if not member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.profile'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        if action == 'create':
            name = (request.form.get('name') or '').strip()
            description = (request.form.get('description') or '').strip()
            if not name:
                flash('Team name is required.', 'error')
                return redirect(url_for('member.teams_hub'))
            if Team.query.filter(db.func.lower(Team.name) == name.lower()).first():
                flash('Team name already exists.', 'error')
                return redirect(url_for('member.teams_hub'))
            if _member_primary_team(member.id):
                flash('You are already in an approved team.', 'error')
                return redirect(url_for('member.teams_hub'))
            team = Team(
                name=name,
                description=description,
                rating=0,
                created_by_member_id=member.id,
                is_open=True,
            )
            db.session.add(team)
            db.session.flush()
            db.session.add(TeamMember(
                team_id=team.id,
                member_id=member.id,
                is_leader=True,
                status='approved',
                requested_at=datetime.utcnow(),
                approved_at=datetime.utcnow(),
                approved_by_member_id=member.id,
            ))
            db.session.commit()
            flash('Team created. You are now the team leader.', 'success')
            return redirect(url_for('member.teams_hub'))

        if action == 'request_join':
            team_id = request.form.get('team_id', type=int)
            team = Team.query.get_or_404(team_id)
            if team.is_suspended:
                flash('This team is currently suspended and not accepting requests.', 'error')
                return redirect(url_for('member.teams_hub'))
            if not team.is_open:
                flash('This team is not open for join requests.', 'error')
                return redirect(url_for('member.teams_hub'))
            if _member_primary_team(member.id):
                flash('You are already in an approved team.', 'error')
                return redirect(url_for('member.teams_hub'))
            existing = TeamMember.query.filter_by(team_id=team.id, member_id=member.id).first()
            if existing:
                if existing.status == 'pending':
                    flash('You already requested to join this team.', 'info')
                elif existing.status == 'approved':
                    flash('You are already in this team.', 'info')
                else:
                    existing.status = 'pending'
                    existing.requested_at = datetime.utcnow()
                    existing.approved_at = None
                    existing.approved_by_member_id = None
                    db.session.commit()
                    flash('Join request re-submitted.', 'success')
                return redirect(url_for('member.teams_hub'))
            db.session.add(TeamMember(
                team_id=team.id,
                member_id=member.id,
                is_leader=False,
                status='pending',
                requested_at=datetime.utcnow(),
            ))
            db.session.commit()
            try:
                get_notification_service().send_team_join_request_sms_to_admins(member, team)
            except Exception:
                current_app.logger.exception('Failed to send team join request SMS to admins')
            flash('Join request sent to team leader.', 'success')
            return redirect(url_for('member.teams_hub'))

    my_team_membership = _member_primary_team(member.id)
    my_team = my_team_membership.team if my_team_membership else None
    my_pending_requests = TeamMember.query.filter_by(member_id=member.id, status='pending').all()
    leader_of = TeamMember.query.filter_by(member_id=member.id, status='approved', is_leader=True).all()
    pending_for_my_teams = []
    leader_team_ids = [tm.team_id for tm in leader_of]
    if leader_team_ids:
        pending_for_my_teams = TeamMember.query.filter(
            TeamMember.team_id.in_(leader_team_ids),
            TeamMember.status == 'pending'
        ).join(Member, Member.id == TeamMember.member_id).order_by(TeamMember.requested_at.asc()).all()
    open_teams = Team.query.filter(
        Team.is_open == True,
        Team.is_suspended == False
    ).order_by(Team.rating.desc(), Team.name.asc()).all()
    return render_template(
        'member/teams_hub.html',
        my_team=my_team,
        my_team_membership=my_team_membership,
        my_pending_requests=my_pending_requests,
        pending_for_my_teams=pending_for_my_teams,
        open_teams=open_teams,
    )


@member_bp.route('/teams/<int:team_id>/requests/<int:team_member_id>/<decision>', methods=['POST'])
@login_required
def teams_decide_request(team_id, team_member_id, decision):
    member = current_user.member
    if not member:
        flash('Profile required.', 'error')
        return redirect(url_for('member.profile'))
    if not _team_is_leader(team_id, member.id):
        flash('Only team leader can decide requests.', 'error')
        return redirect(url_for('member.teams_hub'))

    req = TeamMember.query.get_or_404(team_member_id)
    if req.team_id != team_id or req.status != 'pending':
        flash('Invalid request.', 'error')
        return redirect(url_for('member.teams_hub'))

    if decision == 'approve':
        already = TeamMember.query.filter_by(member_id=req.member_id, status='approved').first()
        if already and already.team_id != team_id:
            flash(f'{req.member.full_name} is already approved in another team.', 'error')
            return redirect(url_for('member.teams_hub'))
        req.status = 'approved'
        req.approved_at = datetime.utcnow()
        req.approved_by_member_id = member.id
        db.session.commit()
        try:
            get_notification_service().send_team_join_decision_sms(req.member, req.team, decision='approved')
        except Exception:
            current_app.logger.exception('Failed to send team join approval SMS')
        flash('Member request approved.', 'success')
    elif decision == 'reject':
        req.status = 'rejected'
        req.approved_at = datetime.utcnow()
        req.approved_by_member_id = member.id
        db.session.commit()
        try:
            get_notification_service().send_team_join_decision_sms(req.member, req.team, decision='rejected')
        except Exception:
            current_app.logger.exception('Failed to send team join rejection SMS')
        flash('Member request rejected.', 'warning')
    else:
        flash('Invalid decision.', 'error')
    return redirect(url_for('member.teams_hub'))




@member_bp.route('/competitions/rankings')
@login_required
def competitions_rankings():
    points_rows = db.session.query(
        Member,
        db.func.coalesce(db.func.sum(RewardTransaction.points), 0).label('points')
    ).select_from(Member).join(User, User.id == Member.user_id).outerjoin(
        RewardTransaction,
        RewardTransaction.member_id == Member.id
    ).filter(
        User.is_approved == True
    ).group_by(Member.id).order_by(db.desc('points')).all()

    top_member = points_rows[0] if points_rows else None

    warmup_counts = dict(
        db.session.query(
            QuizAttempt.member_id,
            db.func.count(QuizAttempt.id)
        ).filter(
            QuizAttempt.status.in_(['submitted', 'timed_out', 'auto_submitted'])
        ).group_by(QuizAttempt.member_id).all()
    )

    leaderboard = []
    my_entry = None
    for idx, (member, points) in enumerate(points_rows, start=1):
        submissions = CompetitionSubmission.query.filter_by(member_id=member.id).all()
        competitions_count = len(submissions)
        ranks = [s.rank for s in submissions if s.rank]
        best_rank = min(ranks) if ranks else None
        entry = {
            'rank': idx,
            'member': member,
            'points': int(points or 0),
            'competitions': competitions_count,
            'warmups_done': int(warmup_counts.get(member.id, 0) or 0),
            'best_rank': best_rank,
        }
        if current_user.member and member.id == current_user.member.id:
            my_entry = entry
        leaderboard.append(entry)
    leaderboard = leaderboard[:50]

    teams = Team.query.filter(
        Team.is_suspended == False
    ).order_by(Team.total_points.desc(), Team.rating.desc(), Team.name.asc()).all()
    team_rows = []
    team_members = {}
    for idx, team in enumerate(teams, start=1):
        approved_memberships = team.members.filter_by(status='approved').join(
            Member, TeamMember.member_id == Member.id
        ).order_by(TeamMember.is_leader.desc(), Member.full_name.asc()).all()
        team_members[team.id] = approved_memberships
        participations = CompetitionTeamEnrollment.query.filter_by(team_id=team.id).count()
        team_rows.append({
            'rank': idx,
            'team': team,
            'points': int(team.total_points or 0),
            'participations': participations,
            'members_count': len(approved_memberships),
        })

    return render_template(
        'member/competitions_rankings.html',
        leaderboard=leaderboard,
        top_member=top_member,
        teams=team_rows,
        team_members=team_members,
        my_entry=my_entry,
    )


@member_bp.route('/rankings/points-transactions')
@login_required
def points_transactions():
    page = request.args.get('page', 1, type=int)
    member_id = request.args.get('member_id', type=int)
    selected_member = Member.query.get(member_id) if member_id else None

    if not selected_member:
        pagination = None
        transactions = []
    else:
        query = RewardTransaction.query.filter(
            RewardTransaction.member_id == selected_member.id
        ).order_by(
            RewardTransaction.created_at.desc(),
            RewardTransaction.id.desc()
        )
        pagination = query.paginate(page=page, per_page=25, error_out=False)
        transactions = pagination.items

    return render_template(
        'member/points_transactions.html',
        transactions=transactions,
        pagination=pagination,
        selected_member=selected_member,
        member_id=member_id,
    )


@member_bp.route('/notifications')
@login_required
def notifications():
    member = current_user.member
    page = request.args.get('page', 1, type=int)
    query = MemberNotification.query.filter_by(member_id=member.id).order_by(
        MemberNotification.created_at.desc(),
        MemberNotification.id.desc()
    )
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    unread_count = MemberNotification.query.filter_by(member_id=member.id, is_read=False).count()
    return render_template(
        'member/notifications.html',
        notifications=pagination.items,
        pagination=pagination,
        unread_count=unread_count,
    )


@member_bp.route('/notifications/<int:notification_id>')
@login_required
def notification_detail(notification_id):
    member = current_user.member
    notification = MemberNotification.query.filter_by(id=notification_id, member_id=member.id).first_or_404()
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
    return render_template('member/notification_detail.html', notification=notification)
  
  
@member_bp.route('/events')
@login_required
def events():
    member = current_user.member
    now = datetime.utcnow()
    query = Event.query.filter(Event.target_audience.in_(['members', 'paid_members']))
    if not (member and member.has_valid_membership()):
        query = query.filter(Event.target_audience == 'members')
    events_all = query.order_by(Event.event_date.asc()).all()
    upcoming_events = [e for e in events_all if e.event_date >= now]
    past_events = [e for e in events_all if e.event_date < now]

    my_rsvps = {}
    if member and events_all:
        rsvps = RSVP.query.filter(
            RSVP.member_id == member.id,
            RSVP.event_id.in_([e.id for e in events_all]),
        ).all()
        my_rsvps = {r.event_id: r for r in rsvps}

    return render_template(
        'member/events.html',
        upcoming_events=upcoming_events,
        past_events=past_events,
        my_rsvps=my_rsvps,
        now=now,
    )


@member_bp.route('/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
def event_rsvp(event_id):
    event = Event.query.get_or_404(event_id)
    member = current_user.member
    if not member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.profile'))
    if event.target_audience not in ['members', 'paid_members']:
        flash('This event RSVP is available on the public events page.', 'warning')
        return redirect(url_for('member.events'))
    if event.target_audience == 'paid_members' and not member.has_valid_membership():
        flash('This event requires an active paid membership.', 'error')
        return redirect(url_for('member.events'))

    existing = RSVP.query.filter_by(event_id=event.id, member_id=member.id).first()
    if existing:
        flash('You already submitted RSVP for this event.', 'info')
        return redirect(url_for('member.events'))

    if event.max_attendees:
        approved_count = RSVP.query.filter_by(event_id=event.id, status='approved').count()
        if approved_count >= event.max_attendees:
            flash('This event is at capacity.', 'error')
            return redirect(url_for('member.events'))

    rsvp = RSVP(
        event_id=event.id,
        member_id=member.id,
        full_name=member.full_name or current_user.email,
        email=current_user.email,
        phone=member.phone,
        course=member.course,
        year=member.year,
        dietary_requirements=(request.form.get('dietary_requirements') or '').strip() or None,
        emergency_contact=(request.form.get('emergency_contact') or '').strip() or None,
        emergency_phone=(request.form.get('emergency_phone') or '').strip() or None,
        additional_notes=(request.form.get('additional_notes') or '').strip() or None,
    )
    db.session.add(rsvp)
    db.session.commit()
    flash('RSVP submitted. You will be notified after review.', 'success')
    return redirect(url_for('member.events'))


@member_bp.route('/sessions/timetable')
@login_required
def sessions_timetable():
    week = _latest_published_session_week()
    sessions_by_day = []
    if week:
        sessions = week.sessions.order_by(SessionSchedule.session_date.asc(), SessionSchedule.start_time.asc()).all()
        day_map = {}
        for session in sessions:
            day_map.setdefault(session.session_date, []).append(session)
        sessions_by_day = sorted(day_map.items(), key=lambda item: item[0])
    return render_template(
        'member/sessions_timetable.html',
        week=week,
        sessions_by_day=sessions_by_day,
        now=datetime.now(),
        datetime=datetime,
    )


@member_bp.route('/sessions/instructors')
@login_required
def sessions_instructors():
    week = _latest_published_session_week()
    instructors = []
    if week:
        sessions = week.sessions.all()
        seen = set()
        for session in sessions:
            if session.instructor_user_id not in seen:
                instructors.append(session.instructor)
                seen.add(session.instructor_user_id)
    return render_template('member/sessions_instructors.html', week=week, instructors=instructors)


@member_bp.route('/sessions/<int:session_id>/report', methods=['GET', 'POST'])
@login_required
def session_report_submit(session_id):
    session = SessionSchedule.query.get_or_404(session_id)
    if session.instructor_user_id != current_user.id:
        flash('You are not assigned as instructor for this session.', 'error')
        return redirect(url_for('member.sessions_timetable'))

    existing = SessionReport.query.filter_by(session_id=session.id, instructor_user_id=current_user.id).first()
    if request.method == 'POST':
        winner_username = request.form.get('winner_username', '').strip()
        participant_count = request.form.get('participant_count', '0').strip()
        notes = request.form.get('notes', '').strip()

        if not winner_username:
            flash('Winner username is required.', 'error')
            return redirect(url_for('member.session_report_submit', session_id=session.id))

        try:
            participant_count_val = int(participant_count)
        except ValueError:
            participant_count_val = 0

        if existing and existing.status == 'approved':
            flash('Report already approved. Contact admin for changes.', 'warning')
            return redirect(url_for('member.sessions_timetable'))

        if not existing:
            existing = SessionReport(
                session_id=session.id,
                instructor_user_id=current_user.id,
            )
            db.session.add(existing)

        existing.winner_username = winner_username
        existing.participant_count = participant_count_val
        existing.notes = notes
        existing.status = 'pending'
        existing.submitted_at = datetime.utcnow()
        db.session.commit()
        flash('Session report submitted for review.', 'success')
        return redirect(url_for('member.sessions_timetable'))

    return render_template('member/session_report.html', session=session, report=existing)


# Quizzes
def _quiz_is_live(quiz):
    if quiz.status != 'published':
        return False
    if quiz.scheduled_start_at and app_now_naive() < quiz.scheduled_start_at:
        return False
    return True


def _quiz_attempt_expired(attempt):
    now = app_now_naive()
    expires_at = attempt.expires_at
    quiz_end = _quiz_end_at(attempt.quiz)
    if quiz_end and (not expires_at or quiz_end < expires_at):
        expires_at = quiz_end
    return bool(expires_at and now >= expires_at)


def _quiz_end_at(quiz):
    start_at = quiz.scheduled_start_at or quiz.published_at or quiz.created_at
    if not start_at:
        return None
    return start_at + timedelta(minutes=(quiz.duration_minutes or 0))


def _quiz_has_ended(quiz):
    end_at = _quiz_end_at(quiz)
    return bool(end_at and app_now_naive() >= end_at)


def _quiz_results_release_due(quiz):
    end_at = _quiz_end_at(quiz)
    if not end_at:
        return False
    return app_now_naive() >= (end_at + timedelta(minutes=1))


def _ordered_quiz_questions_for_attempt(quiz, attempt):
    questions = quiz.questions.filter_by(is_active=True).order_by(QuizQuestion.order_index.asc()).all()
    seed = attempt.random_seed or f"{attempt.member_id}-{quiz.id}"
    rng = random.Random(str(seed))
    rng.shuffle(questions)
    return questions


def _calculate_quiz_attempt_scores(attempt):
    answers = attempt.answers.all()
    total = attempt.quiz.questions.filter_by(is_active=True).count()
    correct = sum(1 for a in answers if a.is_correct)
    raw_score = (correct / total) * 100 if total else 0
    confidence_factor = max(0, 1 - (attempt.violation_count * 0.05))
    adjusted = round(raw_score - (attempt.violation_count * 5), 2)
    attempt.total_count = total
    attempt.correct_count = correct
    attempt.score = round(raw_score, 2)
    attempt.confidence_factor = round(confidence_factor, 2)
    attempt.confidence_adjusted_score = adjusted


def _award_quiz_points_and_leaderboard(quiz):
    if QuizLeaderboard.query.filter_by(quiz_id=quiz.id).first():
        return

    QuizLeaderboard.query.filter_by(quiz_id=quiz.id).delete(synchronize_session=False)
    RewardTransaction.query.filter(
        RewardTransaction.transaction_type == 'quiz',
        RewardTransaction.reason.ilike(f"Quiz {quiz.id} -%")
    ).delete(synchronize_session=False)
    attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).filter(
        QuizAttempt.status.in_(['submitted', 'timed_out', 'auto_submitted'])
    ).all()
    attempts.sort(
        key=lambda a: (
            -(a.confidence_adjusted_score or 0),
            a.submitted_at or datetime.max,
            a.started_at or datetime.max,
        )
    )

    notification_service = get_notification_service()

    for rank, att in enumerate(attempts, start=1):
        if rank == 1:
            points = 30
        elif rank == 2:
            points = 20
        elif rank == 3:
            points = 10
        else:
            points = 5

        db.session.add(
            QuizLeaderboard(
                quiz_id=quiz.id,
                attempt_id=att.id,
                member_id=att.member_id,
                rank=rank,
                score=att.confidence_adjusted_score or 0,
                points_awarded=points,
            )
        )
        db.session.add(
            RewardTransaction(
                member_id=att.member_id,
                points=points,
                transaction_type='quiz',
                reason=f"Quiz {quiz.id} - {quiz.title} (Rank {rank})",
                admin_id=quiz.approved_by_user_id or quiz.created_by_user_id
            )
        )
        if (att.confidence_adjusted_score or 0) < 0:
            db.session.add(
                RewardTransaction(
                    member_id=att.member_id,
                    points=-5,
                    transaction_type='quiz',
                    reason=f"Quiz {quiz.id} - Penalty (negative adjusted score)",
                    admin_id=quiz.approved_by_user_id or quiz.created_by_user_id
                )
            )
            member = Member.query.get(att.member_id)
            if member and member.phone:
                try:
                    notification_service.send_sms(
                        member.phone,
                        f"Quiz update: You received a -5 points penalty for {quiz.title} due to negative adjusted score after violation penalties."
                    )
                except Exception:
                    pass
    db.session.commit()


def _finalize_quiz_results_if_due(quiz):
    if quiz.status != 'published' or not _quiz_results_release_due(quiz):
        return False

    changed = False
    now_local = app_now_naive()

    in_progress = QuizAttempt.query.filter_by(quiz_id=quiz.id, status='in_progress').all()
    for attempt in in_progress:
        attempt.status = 'timed_out'
        attempt.submitted_at = attempt.expires_at or now_local
        _calculate_quiz_attempt_scores(attempt)
        changed = True

    scored_attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).filter(
        QuizAttempt.status.in_(['submitted', 'timed_out', 'auto_submitted'])
    ).all()
    for attempt in scored_attempts:
        if attempt.score is None or attempt.confidence_adjusted_score is None:
            _calculate_quiz_attempt_scores(attempt)
            changed = True

    if changed:
        db.session.commit()

    _award_quiz_points_and_leaderboard(quiz)
    return True


@member_bp.route('/quizzes')
@login_required
def quizzes():
    now = app_now_naive()
    page = request.args.get('page', 1, type=int)
    published_query = Quiz.query.filter_by(status='published').order_by(
        Quiz.scheduled_start_at.asc(),
        Quiz.created_at.desc()
    )
    pagination = published_query.paginate(page=page, per_page=12, error_out=False)
    published_quizzes = pagination.items
    for quiz in published_quizzes:
        _finalize_quiz_results_if_due(quiz)

    pending_quizzes = []
    completed_quizzes = []
    for quiz in published_quizzes:
        end_at = _quiz_end_at(quiz)
        if end_at and now >= end_at:
            completed_quizzes.append({'quiz': quiz, 'end_at': end_at})
        else:
            pending_quizzes.append({'quiz': quiz, 'end_at': end_at})
    completed_quizzes.sort(key=lambda item: item['end_at'] or datetime.min, reverse=True)

    return render_template(
        'member/quizzes/index.html',
        quizzes=published_quizzes,
        pending_quizzes=pending_quizzes,
        completed_quizzes=completed_quizzes,
        pagination=pagination,
        now=now,
    )


@member_bp.route('/quizzes/<int:quiz_id>')
@login_required
def quiz_detail(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    if not member:
        flash('Profile required.', 'error')
        return redirect(url_for('member.profile'))
    if quiz.status != 'published':
        abort(404)
    _finalize_quiz_results_if_due(quiz)
    is_creator = (current_user.id == quiz.created_by_user_id)
    reminder_pref = QuizReminderPreference.query.filter_by(member_id=member.id).first()

    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first()
    can_start = _quiz_is_live(quiz) and not attempt and not _quiz_has_ended(quiz) and not is_creator
    return render_template(
        'member/quizzes/detail.html',
        quiz=quiz,
        attempt=attempt,
        can_start=can_start,
        quiz_end_at=_quiz_end_at(quiz),
        quiz_ended=_quiz_has_ended(quiz),
        is_creator=is_creator,
        reminder_pref=reminder_pref,
    )


@member_bp.route('/quizzes/<int:quiz_id>/start', methods=['POST'])
@login_required
def quiz_start(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    if not member:
        flash('Profile required.', 'error')
        return redirect(url_for('member.profile'))
    if current_user.id == quiz.created_by_user_id:
        flash('Quiz creators cannot attempt their own quiz.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    if not _quiz_is_live(quiz) or _quiz_has_ended(quiz):
        flash('Quiz is not active yet.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    existing = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first()
    if existing:
        return redirect(url_for('member.quiz_take', quiz_id=quiz.id))

    now_local = app_now_naive()
    quiz_end_at = _quiz_end_at(quiz)
    expires_at = now_local + timedelta(minutes=quiz.duration_minutes)
    if quiz_end_at and quiz_end_at < expires_at:
        expires_at = quiz_end_at
    if expires_at <= now_local:
        flash('Quiz time window has already ended.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        member_id=member.id,
        status='in_progress',
        started_at=now_local,
        expires_at=expires_at,
        random_seed=str(member.id * 100000 + quiz.id),
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for('member.quiz_take', quiz_id=quiz.id))


@member_bp.route('/quizzes/<int:quiz_id>/reminder', methods=['POST'])
@login_required
def quiz_reminder_toggle(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    if not member:
        flash('Profile required.', 'error')
        return redirect(url_for('member.profile'))

    pref = QuizReminderPreference.query.filter_by(member_id=member.id).first()
    if not pref:
        pref = QuizReminderPreference(member_id=member.id)
        db.session.add(pref)

    if pref.is_blocked:
        flash('Reminder notifications are blocked after 5 consecutive missed warmups.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))

    enabled = '1' in request.form.getlist('reminder_enabled')
    pref.is_enabled = enabled
    db.session.commit()
    flash('Warmup reminder preference updated.', 'success')
    return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))


@member_bp.route('/quizzes/<int:quiz_id>/take')
@login_required
def quiz_take(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if current_user.id == quiz.created_by_user_id:
        flash('Quiz creators cannot attempt their own quiz.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    member = current_user.member
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first()
    if not attempt:
        flash('Start quiz first.', 'warning')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    if attempt.status != 'in_progress':
        return redirect(url_for('member.quiz_result', quiz_id=quiz.id))
    if _quiz_attempt_expired(attempt) or _quiz_has_ended(quiz):
        attempt.status = 'timed_out'
        attempt.submitted_at = app_now_naive()
        _calculate_quiz_attempt_scores(attempt)
        db.session.commit()
        _finalize_quiz_results_if_due(quiz)
        return redirect(url_for('member.quiz_result', quiz_id=quiz.id))

    questions = _ordered_quiz_questions_for_attempt(quiz, attempt)
    answers = {a.question_id: a for a in attempt.answers.all()}
    quiz_end_at = _quiz_end_at(quiz)
    effective_expires_at = attempt.expires_at
    if quiz_end_at and (not effective_expires_at or quiz_end_at < effective_expires_at):
        effective_expires_at = quiz_end_at

    return render_template(
        'member/quizzes/take.html',
        quiz=quiz,
        attempt=attempt,
        questions=questions,
        answers=answers,
        max_violations=QUIZ_MAX_VIOLATIONS,
        remaining_seconds=max(0, int((effective_expires_at - app_now_naive()).total_seconds())) if effective_expires_at else 0
    )


@member_bp.route('/quizzes/<int:quiz_id>/answer', methods=['POST'])
@login_required
def quiz_answer(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first_or_404()
    if attempt.status != 'in_progress':
        return ('', 204)
    question_id = request.form.get('question_id', type=int)
    selected_option_id = request.form.get('selected_option_id', type=int)
    time_spent = request.form.get('time_spent_seconds', type=int) or 0
    question = QuizQuestion.query.get_or_404(question_id)
    if question.quiz_id != quiz.id:
        abort(400)
    option = QuizOption.query.get_or_404(selected_option_id)
    if option.question_id != question.id:
        abort(400)

    answer = QuizAttemptAnswer.query.filter_by(attempt_id=attempt.id, question_id=question.id).first()
    if not answer:
        answer = QuizAttemptAnswer(attempt_id=attempt.id, question_id=question.id)
        db.session.add(answer)
    answer.selected_option_id = option.id
    answer.is_correct = bool(option.is_correct)
    answer.time_spent_seconds = max(0, time_spent)
    answer.submitted_at = datetime.utcnow()
    db.session.commit()
    return ('', 204)


@member_bp.route('/quizzes/<int:quiz_id>/violation', methods=['POST'])
@login_required
def quiz_violation(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first_or_404()
    if attempt.status != 'in_progress':
        return {'status': 'ignored'}, 200
    violation_type = (request.form.get('violation_type') or '').strip().lower()
    details = (request.form.get('details') or '').strip()
    if violation_type not in ['tab_switch', 'blur', 'paste', 'inactivity']:
        return {'status': 'invalid'}, 400

    if violation_type == 'tab_switch':
        attempt.tab_switch_count += 1
    elif violation_type == 'blur':
        attempt.blur_count += 1
    elif violation_type == 'paste':
        attempt.paste_attempt_count += 1
    elif violation_type == 'inactivity':
        attempt.inactivity_count += 1
    attempt.violation_count += 1
    db.session.add(QuizViolation(attempt_id=attempt.id, violation_type=violation_type, details=details))

    auto_submitted = False
    if attempt.violation_count >= QUIZ_MAX_VIOLATIONS:
        attempt.status = 'auto_submitted'
        attempt.auto_submit_reason = 'max_violations'
        attempt.submitted_at = app_now_naive()
        _calculate_quiz_attempt_scores(attempt)
        auto_submitted = True
    db.session.commit()
    return {'status': 'ok', 'violations': attempt.violation_count, 'auto_submitted': auto_submitted}, 200


@member_bp.route('/quizzes/<int:quiz_id>/submit', methods=['POST'])
@login_required
def quiz_submit(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    member = current_user.member
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first_or_404()
    if attempt.status != 'in_progress':
        return redirect(url_for('member.quiz_result', quiz_id=quiz.id))
    if _quiz_has_ended(quiz):
        attempt.status = 'timed_out'
        attempt.submitted_at = app_now_naive()
        _calculate_quiz_attempt_scores(attempt)
        db.session.commit()
        _finalize_quiz_results_if_due(quiz)
        flash('Quiz window has ended. Your attempt was auto-closed.', 'warning')
        return redirect(url_for('member.quiz_result', quiz_id=quiz.id))

    attempt.status = 'submitted'
    attempt.submitted_at = app_now_naive()
    _calculate_quiz_attempt_scores(attempt)
    db.session.commit()
    flash('Quiz submitted successfully. Rankings will be published after quiz window closes.', 'success')
    return redirect(url_for('member.quiz_result', quiz_id=quiz.id))


@member_bp.route('/quizzes/<int:quiz_id>/result')
@login_required
def quiz_result(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    _finalize_quiz_results_if_due(quiz)
    member = current_user.member
    attempt = QuizAttempt.query.filter_by(quiz_id=quiz.id, member_id=member.id).first_or_404()
    my_row = QuizLeaderboard.query.filter_by(quiz_id=quiz.id, member_id=member.id).first() if _quiz_results_release_due(quiz) else None
    penalty_tx = RewardTransaction.query.filter_by(
        member_id=member.id,
        transaction_type='quiz'
    ).filter(
        RewardTransaction.reason == f"Quiz {quiz.id} - Penalty (negative adjusted score)"
    ).first()
    questions = _ordered_quiz_questions_for_attempt(quiz, attempt)
    answer_map = {a.question_id: a for a in attempt.answers.all()}
    question_rows = []
    for q in questions:
        selected_answer = answer_map.get(q.id)
        selected_option = selected_answer.selected_option if selected_answer else None
        correct_option = q.options.filter_by(is_correct=True).first()
        if not selected_answer:
            status = 'not_answered'
        elif selected_answer.is_correct:
            status = 'correct'
        else:
            status = 'incorrect'
        question_rows.append({
            'question': q,
            'selected_option': selected_option,
            'correct_option': correct_option,
            'status': status,
        })
    return render_template(
        'member/quizzes/result.html',
        quiz=quiz,
        attempt=attempt,
        my_row=my_row,
        quiz_ended=_quiz_results_release_due(quiz),
        question_rows=question_rows,
        penalty_applied=bool(penalty_tx),
        quiz_end_at=_quiz_end_at(quiz),
    )


@member_bp.route('/quizzes/<int:quiz_id>/leaderboard')
@login_required
def quiz_leaderboard(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    _finalize_quiz_results_if_due(quiz)
    if not _quiz_results_release_due(quiz):
        flash('Leaderboard will be available after quiz duration ends.', 'info')
        return redirect(url_for('member.quiz_detail', quiz_id=quiz.id))
    page = request.args.get('page', 1, type=int)
    pagination = QuizLeaderboard.query.filter_by(quiz_id=quiz.id).join(
        Member, Member.id == QuizLeaderboard.member_id
    ).order_by(QuizLeaderboard.rank.asc()).paginate(page=page, per_page=20, error_out=False)
    rows = pagination.items
    member = current_user.member
    my_row = None
    participant_count = QuizLeaderboard.query.filter_by(quiz_id=quiz.id).count()
    if member:
        my_row = QuizLeaderboard.query.filter_by(quiz_id=quiz.id, member_id=member.id).first()
    return render_template(
        'member/quizzes/leaderboard.html',
        quiz=quiz,
        rows=rows,
        pagination=pagination,
        my_row=my_row,
        participant_count=participant_count,
    )


# Competitions

def _member_is_judge(competition_id, user_id):
    return CompetitionJudge.query.filter_by(competition_id=competition_id, user_id=user_id, is_active=True).first()


def _member_visible_competitions():
    return Competition.query.filter(~Competition.status.in_(['draft', 'cancelled']))


def _competition_effective_enrollment_counts(competition_ids):
    """Count unique enrolled members per competition, including team snapshots."""
    if not competition_ids:
        return {}

    counts = {cid: set() for cid in competition_ids}

    individual_rows = CompetitionEnrollment.query.filter(
        CompetitionEnrollment.competition_id.in_(competition_ids),
        CompetitionEnrollment.status == 'enrolled'
    ).with_entities(
        CompetitionEnrollment.competition_id,
        CompetitionEnrollment.member_id
    ).all()
    for competition_id, member_id in individual_rows:
        if competition_id in counts and member_id:
            counts[competition_id].add(member_id)

    team_rows = db.session.query(
        CompetitionTeamEnrollment.competition_id,
        CompetitionTeamEnrollmentMember.member_id
    ).join(
        CompetitionTeamEnrollmentMember,
        CompetitionTeamEnrollmentMember.enrollment_id == CompetitionTeamEnrollment.id
    ).filter(
        CompetitionTeamEnrollment.competition_id.in_(competition_ids),
        CompetitionTeamEnrollment.status == 'enrolled'
    ).all()
    for competition_id, member_id in team_rows:
        if competition_id in counts and member_id:
            counts[competition_id].add(member_id)

    return {cid: len(member_ids) for cid, member_ids in counts.items()}


def _member_ongoing_competitions_for_frequency(frequency, user_id):
    now = app_now_naive()
    base = _member_visible_competitions().filter(Competition.frequency == frequency)
    active_for_members = base.filter(
        Competition.status == 'published',
        Competition.starts_at <= now,
        Competition.ends_at >= now
    )
    judge_extra = base.join(
        CompetitionJudge,
        db.and_(
            CompetitionJudge.competition_id == Competition.id,
            CompetitionJudge.user_id == user_id,
            CompetitionJudge.is_active == True
        )
    ).filter(Competition.status.in_(['published', 'judging']))
    return active_for_members.union(judge_extra).order_by(Competition.ends_at.asc()).all()


def _member_can_submit(competition, member, user_id):
    if not member:
        return False, 'Profile required before submitting.'
    if _member_is_judge(competition.id, user_id):
        return False, 'Judges cannot submit to the same competition.'
    if _member_team_for_competition(member.id, competition.id):
        return False, 'You are enrolled under a team for this competition. Only team leader submits.'
    if competition.status != 'published':
        return False, 'Competition is not open for submissions.'
    now = app_now_naive()
    if now < competition.starts_at or now > competition.ends_at:
        return False, 'Submission window is closed.'
    if competition.requires_paid_membership and not member.has_valid_membership():
        return False, 'Valid membership is required to enroll.'
    allowed_years = competition.get_allowed_years()
    if member.year and allowed_years and member.year not in allowed_years:
        return False, 'You are not eligible for this level.'
    enrollment = CompetitionEnrollment.query.filter_by(competition_id=competition.id, member_id=member.id).first()
    if not enrollment:
        return False, 'Please enroll before submitting.'
    if enrollment.status == 'disqualified':
        return False, 'You have been disqualified from this competition.'
    existing = CompetitionSubmission.query.filter_by(competition_id=competition.id, member_id=member.id).first()
    if existing:
        return False, 'You have already submitted for this competition.'
    return True, ''


def _member_team_membership(member_id):
    return TeamMember.query.filter_by(member_id=member_id, status='approved').first()


def _member_team_for_competition(member_id, competition_id):
    return db.session.query(CompetitionTeamEnrollment).join(
        CompetitionTeamEnrollmentMember,
        CompetitionTeamEnrollmentMember.enrollment_id == CompetitionTeamEnrollment.id
    ).filter(
        CompetitionTeamEnrollment.competition_id == competition_id,
        CompetitionTeamEnrollmentMember.member_id == member_id,
        CompetitionTeamEnrollment.status != 'disqualified'
    ).first()


def _member_can_team_enroll(competition, member, user_id):
    if not member:
        return False, 'Profile required before team enrollment.'
    if _member_is_judge(competition.id, user_id):
        return False, 'Judges cannot enroll teams in this competition.'
    if competition.status != 'published':
        return False, 'Competition is not open for team enrollment.'
    now = app_now_naive()
    if now < competition.starts_at or now > competition.ends_at:
        return False, 'Competition enrollment window is closed.'
    membership = _member_team_membership(member.id)
    if not membership:
        return False, 'You are not in an approved team.'
    if not membership.is_leader:
        return False, 'Only team leader can enroll the team.'
    team = membership.team
    if not team:
        return False, 'Team not found.'
    if team.is_suspended:
        return False, f'Team is suspended by admin. {team.suspension_reason or ""}'.strip()
    if _member_team_for_competition(member.id, competition.id):
        return False, 'Your team is already enrolled in this competition.'
    approved_members = team.members.filter_by(status='approved').join(
        Member, TeamMember.member_id == Member.id
    ).all()
    allowed_years = competition.get_allowed_years()
    ineligible = []
    unpaid = []
    for tm in approved_members:
        m = tm.member
        if m and m.year and allowed_years and m.year not in allowed_years:
            ineligible.append(f'{m.full_name} ({m.year})')
        if competition.requires_paid_membership and m and not m.has_valid_membership():
            unpaid.append(m.full_name)
    if ineligible:
        return False, f'Team enrollment blocked due to eligibility year mismatch: {", ".join(ineligible)}'
    if unpaid:
        return False, f'Team enrollment blocked. Valid membership required for: {", ".join(unpaid)}'
    blocked = []
    for tm in approved_members:
        conflict = _member_team_for_competition(tm.member_id, competition.id)
        if conflict and conflict.team_id != team.id:
            blocked.append(tm.member.full_name)
    if blocked:
        return False, f'Team enrollment blocked. Already enrolled in another team for this competition: {", ".join(blocked)}'

    individual_conflicts = []
    for tm in approved_members:
        individual = CompetitionEnrollment.query.filter_by(
            competition_id=competition.id,
            member_id=tm.member_id,
            status='enrolled'
        ).first()
        if individual:
            individual_conflicts.append(tm.member.full_name)
    if individual_conflicts:
        return False, f'Team enrollment blocked. Already individually enrolled: {", ".join(individual_conflicts)}'
    return True, ''


def _calculate_submission_scores(submission):
    competition = submission.competition
    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    judges = competition.judges.filter_by(is_active=True).all()

    judge_totals = []
    for judge in judges:
        total = 0
        scored_any = False
        for c in criteria:
            score_row = CompetitionScore.query.filter_by(
                submission_id=submission.id,
                judge_id=judge.user_id,
                criteria_id=c.id
            ).first()
            if score_row:
                scored_any = True
                max_points = c.max_points or 1
                total += (score_row.score / max_points) * (c.weight_percent or 0)
        if scored_any:
            judge_totals.append(total)

    submission.total_score = round(sum(judge_totals) / len(judge_totals), 2) if judge_totals else 0
    submission.final_score = round(submission.total_score + (submission.bonus_points or 0), 2)


def _submission_judge_progress(competition, submission):
    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    criteria_count = len(criteria)
    judges = competition.judges.filter_by(is_active=True).all()
    rows = CompetitionScore.query.filter_by(submission_id=submission.id).all()
    score_map = {(r.judge_id, r.criteria_id): r.score for r in rows}

    progress = []
    for j in judges:
        total = 0.0
        scored_count = 0
        for c in criteria:
            key = (j.user_id, c.id)
            if key in score_map:
                scored_count += 1
                max_points = c.max_points or 1
                total += (score_map[key] / max_points) * (c.weight_percent or 0)
        judge_user = j.judge
        progress.append({
            'judge_id': j.user_id,
            'name': judge_user.member.full_name if getattr(judge_user, 'member', None) else judge_user.email,
            'email': judge_user.email,
            'is_chair': j.is_chair,
            'scored_count': scored_count,
            'criteria_count': criteria_count,
            'graded': scored_count > 0,
            'total_score': round(total, 2),
        })
    return progress


@member_bp.route('/competitions/weekly')
@login_required
def competitions_weekly():
    base = _member_visible_competitions().filter(Competition.frequency == 'weekly')
    ongoing = _member_ongoing_competitions_for_frequency('weekly', current_user.id)
    enrollment_counts = _competition_effective_enrollment_counts([c.id for c in ongoing])
    past_query = base.filter(Competition.status == 'finalized').order_by(Competition.ends_at.desc())
    page = request.args.get('page', 1, type=int)
    past = past_query.paginate(page=page, per_page=10, error_out=False)
    return render_template(
        'member/competitions_list.html',
        view_label='Weekly',
        view_type='weekly',
        ongoing=ongoing,
        past=past,
        enrollment_counts=enrollment_counts
    )


@member_bp.route('/competitions/monthly')
@login_required
def competitions_monthly():
    base = _member_visible_competitions().filter(Competition.frequency == 'monthly')
    ongoing = _member_ongoing_competitions_for_frequency('monthly', current_user.id)
    enrollment_counts = _competition_effective_enrollment_counts([c.id for c in ongoing])
    past_query = base.filter(Competition.status == 'finalized').order_by(Competition.ends_at.desc())
    page = request.args.get('page', 1, type=int)
    past = past_query.paginate(page=page, per_page=10, error_out=False)
    return render_template(
        'member/competitions_list.html',
        view_label='Monthly',
        view_type='monthly',
        ongoing=ongoing,
        past=past,
        enrollment_counts=enrollment_counts
    )


@member_bp.route('/competitions/<int:competition_id>')
@login_required
def competition_detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    member = current_user.member
    sponsor_links = competition.sponsors.order_by(CompetitionSponsorLink.display_order.asc()).all()
    eligible, reason = _member_can_submit(competition, member, current_user.id)
    submission = None
    enrollment = None
    team_membership = None
    team_enrollment = None
    team_submission = None
    member_team_competition_enrollment = None
    can_team_enroll = False
    can_team_enroll_reason = ''
    if member:
        submission = CompetitionSubmission.query.filter_by(competition_id=competition.id, member_id=member.id).first()
        enrollment = CompetitionEnrollment.query.filter_by(competition_id=competition.id, member_id=member.id).first()
        team_membership = _member_team_membership(member.id)
        member_team_competition_enrollment = _member_team_for_competition(member.id, competition.id)
        if team_membership:
            team_enrollment = CompetitionTeamEnrollment.query.filter_by(
                competition_id=competition.id,
                team_id=team_membership.team_id
            ).first()
            if team_enrollment:
                team_submission = CompetitionTeamSubmission.query.filter_by(
                    competition_id=competition.id,
                    team_id=team_membership.team_id
                ).first()
        can_team_enroll, can_team_enroll_reason = _member_can_team_enroll(competition, member, current_user.id)
    is_judge = _member_is_judge(competition.id, current_user.id) is not None
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
    visible_criteria = competition.criteria.filter_by(is_visible_to_members=True).order_by(CompetitionCriteria.id.asc()).all()
    my_rank = None
    my_award = None
    total_ranked = 0
    if competition.status == 'finalized' and member:
        ranked = competition.submissions.filter(CompetitionSubmission.status != 'disqualified').order_by(CompetitionSubmission.final_score.desc()).all()
        total_ranked = len(ranked)
        if ranked:
            badges = _build_reward_badges(rewards, len(ranked))
            for idx, s in enumerate(ranked, start=1):
                if s.member_id == member.id:
                    my_rank = idx
                    my_award = badges.get(idx)
                    break
    return render_template(
        'member/competition_detail.html',
        competition=competition,
        eligible=eligible,
        reason=reason,
        submission=submission,
        enrollment=enrollment,
        is_judge=is_judge,
        sponsors=sponsor_links,
        rewards=rewards,
        visible_criteria=visible_criteria,
        my_rank=my_rank,
        my_award=my_award,
        total_ranked=total_ranked,
        team_membership=team_membership,
        team_enrollment=team_enrollment,
        team_submission=team_submission,
        can_team_enroll=can_team_enroll,
        can_team_enroll_reason=can_team_enroll_reason,
        member_team_competition_enrollment=member_team_competition_enrollment,
    )


@member_bp.route('/competitions/<int:competition_id>/submit', methods=['POST'])
@login_required
def competition_submit(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    member = current_user.member
    eligible, reason = _member_can_submit(competition, member, current_user.id)
    if not eligible:
        flash(reason, 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    submission_value = ''
    if competition.submission_type in ['video', 'report']:
        file = request.files.get('submission_file')
        if not file or not file.filename:
            flash('Submission file is required.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        filename = secure_filename(file.filename)
        ext = filename.lower().split('.')[-1]
        if competition.submission_type == 'video' and ext not in ['mp4', 'mov', 'avi', 'webm']:
            flash('Invalid video file type.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        if competition.submission_type == 'report' and ext not in ['pdf', 'doc', 'docx']:
            flash('Invalid report file type.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))

        file.stream.seek(0, os.SEEK_END)
        size_mb = file.stream.tell() / (1024 * 1024)
        file.stream.seek(0)
        if size_mb > (competition.submission_max_mb or 10):
            flash(f'File exceeds {competition.submission_max_mb}MB limit.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))

        timestamp = int(datetime.utcnow().timestamp())
        upload_name = f"comp_{competition.id}_member_{member.id}_{timestamp}_{filename}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'competitions', upload_name)
        file.save(upload_path)
        submission_value = upload_name
    else:
        submission_value = request.form.get('submission_url', '').strip()
        if not submission_value:
            flash('Submission link is required.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))

    submission = CompetitionSubmission(
        competition_id=competition.id,
        member_id=member.id,
        submission_type=competition.submission_type,
        submission_value=submission_value,
    )
    enrollment = CompetitionEnrollment.query.filter_by(
        competition_id=competition.id,
        member_id=member.id
    ).first()
    if enrollment and enrollment.admin_notice:
        enrollment.admin_notice = None
        enrollment.admin_notice_at = None
        enrollment.admin_notice_by = None
    db.session.add(submission)
    db.session.commit()

    flash('Submission received successfully.', 'success')
    return redirect(url_for('member.competition_detail', competition_id=competition.id))


@member_bp.route('/competitions/<int:competition_id>/leaderboard')
@login_required
def competition_leaderboard(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    is_judge = _member_is_judge(competition.id, current_user.id) is not None
    if competition.status != 'finalized' and not is_judge:
        flash('Leaderboard will be available after competition finalization.', 'info')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))
    individual_rows = competition.submissions.filter(CompetitionSubmission.status != 'disqualified').all()
    team_rows = CompetitionTeamSubmission.query.filter_by(
        competition_id=competition.id
    ).filter(CompetitionTeamSubmission.status != 'disqualified').all()

    combined = []
    for s in individual_rows:
        combined.append({
            'record_type': 'individual',
            'participant_name': s.member.full_name if s.member else f"Member #{s.member_id}",
            'participant_email': (
                s.member.user.email
                if s.member and getattr(s.member, 'user', None)
                else '-'
            ),
            'participant_avatar': s.member.profile_image if s.member else None,
            'submitted_at': s.submitted_at,
            'final_score': s.final_score,
            'submission_type': s.submission_type,
            'submission_value': s.submission_value,
            'submission_id': s.id,
            'team_members': [],
            'team_member_ids': [],
        })
    for ts in team_rows:
        team_members = []
        team_member_ids = []
        if ts.enrollment:
            for snap in ts.enrollment.members.all():
                if not snap.member:
                    continue
                team_member_ids.append(snap.member_id)
                team_members.append({
                    'full_name': snap.member.full_name,
                    'course': snap.member.course,
                    'year': snap.member.year,
                    'profile_image': snap.member.profile_image,
                })
        combined.append({
            'record_type': 'team',
            'participant_name': ts.team.name if ts.team else f"Team #{ts.team_id}",
            'participant_email': (
                ts.submitted_by_member.user.email
                if ts.submitted_by_member and getattr(ts.submitted_by_member, 'user', None)
                else '-'
            ),
            'participant_avatar': None,
            'submitted_at': ts.submitted_at,
            'final_score': ts.final_score,
            'submission_type': ts.submission_type,
            'submission_value': ts.submission_value,
            'submission_id': None,
            'team_members': team_members,
            'team_member_ids': team_member_ids,
        })

    combined.sort(key=lambda row: row.get('final_score') or 0, reverse=True)
    page = request.args.get('page', 1, type=int)
    submissions_page = _ListPagination(combined, page=page, per_page=20)
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
    badges = _build_reward_badges(rewards, submissions_page.total)
    member = current_user.member
    my_submission = None
    my_rank = None
    my_award = None
    if member:
        for idx, row in enumerate(combined, start=1):
            is_me = False
            if row['record_type'] == 'individual':
                submission_id = row.get('submission_id')
                is_me = any(s.id == submission_id and s.member_id == member.id for s in individual_rows)
            else:
                is_me = member.id in (row.get('team_member_ids') or [])
            if is_me:
                my_submission = row
                my_rank = idx
                my_award = badges.get(idx)
                break
    return render_template('member/competition_leaderboard.html', competition=competition, submissions=submissions_page, is_judge=is_judge, badges=badges, my_submission=my_submission, my_rank=my_rank, my_award=my_award)


@member_bp.route('/competitions/<int:competition_id>/score/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def competition_score_member(competition_id, submission_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    submission = CompetitionSubmission.query.get_or_404(submission_id)
    if submission.competition_id != competition.id:
        flash('Invalid submission for this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))
    if competition.status == 'finalized':
        flash('Competition is finalized. Scoring is locked.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))
    judge = _member_is_judge(competition.id, current_user.id)
    if not judge:
        flash('You are not assigned to judge this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    criteria = competition.criteria.order_by(CompetitionCriteria.id.asc()).all()
    if request.method == 'POST':
        for c in criteria:
            value = float(request.form.get(f'criteria_{c.id}') or 0)
            if value > c.max_points:
                value = c.max_points
            score_row = CompetitionScore.query.filter_by(
                submission_id=submission.id,
                judge_id=current_user.id,
                criteria_id=c.id
            ).first()
            if not score_row:
                score_row = CompetitionScore(
                    submission_id=submission.id,
                    judge_id=current_user.id,
                    criteria_id=c.id
                )
                db.session.add(score_row)
            score_row.score = value
            score_row.comment = request.form.get(f'comment_{c.id}')
        db.session.commit()
        _calculate_submission_scores(submission)
        db.session.commit()
        flash('Scores saved.', 'success')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    existing_scores = {s.criteria_id: s for s in submission.scores.filter_by(judge_id=current_user.id).all()}
    judge_progress = _submission_judge_progress(competition, submission)
    return render_template(
        'member/competition_score.html',
        competition=competition,
        submission=submission,
        criteria=criteria,
        existing_scores=existing_scores,
        judge_progress=judge_progress
    )

@member_bp.route('/competitions/<int:competition_id>/enroll', methods=['POST'])
@login_required
def competition_enroll(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    member = current_user.member
    if not member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.profile'))

    if _member_is_judge(competition.id, current_user.id):
        flash('Judges cannot enroll in this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    now = app_now_naive()
    if competition.status != 'published' or now < competition.starts_at or now > competition.ends_at:
        flash('Competition is not open for enrollment.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    if competition.requires_paid_membership and not member.has_valid_membership():
        flash('Valid membership is required to enroll.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    allowed_years = competition.get_allowed_years()
    if member.year and allowed_years and member.year not in allowed_years:
        flash('You are not eligible for this level.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    existing = CompetitionEnrollment.query.filter_by(competition_id=competition.id, member_id=member.id).first()
    if existing:
        flash('You are already enrolled.', 'info')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    if _member_team_for_competition(member.id, competition.id):
        flash('You are already enrolled via a team for this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    agree = request.form.get('agree_terms')
    if not agree:
        flash('You must agree to the terms before enrolling.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    enroll_mode = (request.form.get('enroll_mode') or 'individual').strip().lower()
    if enroll_mode == 'team':
        allowed, reason = _member_can_team_enroll(competition, member, current_user.id)
        if not allowed:
            flash(reason, 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        team_membership = _member_team_membership(member.id)
        team = team_membership.team
        approved_members = team.members.filter_by(status='approved').join(
            Member, TeamMember.member_id == Member.id
        ).all()
        team_enrollment = CompetitionTeamEnrollment(
            competition_id=competition.id,
            team_id=team.id,
            leader_member_id=member.id,
            status='enrolled',
            enrolled_at=datetime.utcnow(),
        )
        db.session.add(team_enrollment)
        db.session.flush()
        for tm in approved_members:
            db.session.add(CompetitionTeamEnrollmentMember(
                enrollment_id=team_enrollment.id,
                member_id=tm.member_id
            ))
        db.session.commit()
        flash(f'Team "{team.name}" enrolled successfully. Only team leader can submit.', 'success')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    enrollment = CompetitionEnrollment(
        competition_id=competition.id,
        member_id=member.id,
        status='enrolled',
        enrolled_at=datetime.now()
    )
    db.session.add(enrollment)
    db.session.commit()
    flash('Enrollment successful. You may submit once.', 'success')
    return redirect(url_for('member.competition_detail', competition_id=competition.id))


@member_bp.route('/competitions/<int:competition_id>/team-enroll', methods=['POST'])
@login_required
def competition_team_enroll(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    member = current_user.member
    allowed, reason = _member_can_team_enroll(competition, member, current_user.id)
    if not allowed:
        flash(reason, 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    team_membership = _member_team_membership(member.id)
    team = team_membership.team
    approved_members = team.members.filter_by(status='approved').join(
        Member, TeamMember.member_id == Member.id
    ).all()

    enrollment = CompetitionTeamEnrollment(
        competition_id=competition.id,
        team_id=team.id,
        leader_member_id=member.id,
        status='enrolled',
        enrolled_at=datetime.utcnow(),
    )
    db.session.add(enrollment)
    db.session.flush()
    for tm in approved_members:
        db.session.add(CompetitionTeamEnrollmentMember(
            enrollment_id=enrollment.id,
            member_id=tm.member_id
        ))
    db.session.commit()
    flash(f'Team "{team.name}" enrolled successfully.', 'success')
    return redirect(url_for('member.competition_detail', competition_id=competition.id))


@member_bp.route('/competitions/<int:competition_id>/team-submit', methods=['POST'])
@login_required
def competition_team_submit(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if competition.status in ['draft', 'cancelled']:
        abort(404)
    member = current_user.member
    if not member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.profile'))
    team_membership = _member_team_membership(member.id)
    if not team_membership or not team_membership.is_leader:
        flash('Only team leader can submit for team.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    now = app_now_naive()
    if competition.status != 'published' or now < competition.starts_at or now > competition.ends_at:
        flash('Competition is not open for submissions.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    team = team_membership.team
    enrollment = CompetitionTeamEnrollment.query.filter_by(
        competition_id=competition.id,
        team_id=team.id,
        status='enrolled'
    ).first()
    if not enrollment:
        flash('Enroll your team first.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))
    existing = CompetitionTeamSubmission.query.filter_by(competition_id=competition.id, team_id=team.id).first()
    if existing:
        flash('Team already submitted for this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    submission_value = ''
    if competition.submission_type in ['video', 'report']:
        file = request.files.get('submission_file')
        if not file or not file.filename:
            flash('Submission file is required.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        filename = secure_filename(file.filename)
        ext = filename.lower().split('.')[-1]
        if competition.submission_type == 'video' and ext not in ['mp4', 'mov', 'avi', 'webm']:
            flash('Invalid video file type.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        if competition.submission_type == 'report' and ext not in ['pdf', 'doc', 'docx']:
            flash('Invalid report file type.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        file.stream.seek(0, os.SEEK_END)
        size_mb = file.stream.tell() / (1024 * 1024)
        file.stream.seek(0)
        if size_mb > (competition.submission_max_mb or 10):
            flash(f'File exceeds {competition.submission_max_mb}MB limit.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))
        timestamp = int(datetime.utcnow().timestamp())
        upload_name = f"comp_{competition.id}_team_{team.id}_{timestamp}_{filename}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'competitions', upload_name)
        file.save(upload_path)
        submission_value = upload_name
    else:
        submission_value = request.form.get('submission_url', '').strip()
        if not submission_value:
            flash('Submission link is required.', 'error')
            return redirect(url_for('member.competition_detail', competition_id=competition.id))

    submission = CompetitionTeamSubmission(
        competition_id=competition.id,
        enrollment_id=enrollment.id,
        team_id=team.id,
        submitted_by_member_id=member.id,
        submission_type=competition.submission_type,
        submission_value=submission_value,
    )
    db.session.add(submission)
    db.session.commit()
    flash('Team submission received successfully.', 'success')
    return redirect(url_for('member.competition_detail', competition_id=competition.id))


def _build_reward_badges(rewards, total_submissions):
    badges = {}
    if total_submissions == 0:
        return badges
    for reward in rewards:
        if reward.reward_type == "percent" and reward.percent:
            count = max(1, int((reward.percent / 100.0) * total_submissions))
            for rank in range(1, count + 1):
                badges[rank] = (reward.points or 0, reward.prize_title, reward.prize_description, f"Top {reward.percent}%")
        else:
            start = reward.rank_from or 1
            end = reward.rank_to or start
            for rank in range(start, end + 1):
                badges[rank] = (reward.points or 0, reward.prize_title, reward.prize_description, f"Rank {start}-{end}")
    return badges


class _ListPagination:
    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.page = max(1, page)
        self.per_page = per_page
        self.pages = max(1, math.ceil(self.total / float(self.per_page))) if self.total else 1
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        self.items = items[start:end]
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1
        self.next_num = self.page + 1

    def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or num > self.pages - right_edge
                or (self.page - left_current <= num <= self.page + right_current)
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
