from flask import render_template, request, flash, redirect, url_for, current_app, send_file
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
    CompetitionReward,
    SessionWeek,
    SessionSchedule,
    SessionReport,
    Team,
    TeamMember,
)
from app import db
from app.id_generator import generate_digital_id, delete_digital_id
import os
import json
from datetime import datetime

def _normalize_name(value):
    parts = [p for p in (value or '').strip().split() if p]
    return ' '.join([p[:1].upper() + p[1:].lower() for p in parts])

@member_bp.route('/')
@login_required
def dashboard():
    if not current_user.member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.edit_profile'))
    
    disqualified = CompetitionEnrollment.query.filter_by(member_id=current_user.member.id, status='disqualified').join(Competition).order_by(CompetitionEnrollment.disqualified_at.desc()).all()
    member = current_user.member
    total_points = member.get_total_points()
    competitions_count = CompetitionSubmission.query.filter_by(member_id=member.id).count()
    best_rank = db.session.query(db.func.min(CompetitionSubmission.rank)).filter(
        CompetitionSubmission.member_id == member.id,
        CompetitionSubmission.rank.isnot(None)
    ).scalar()
    team_membership = TeamMember.query.filter_by(member_id=member.id).first()
    upcoming_sessions = []
    week = SessionWeek.query.filter_by(status='published').order_by(SessionWeek.week_start.desc()).first()
    if week:
        upcoming_sessions = week.sessions.order_by(SessionSchedule.session_date.asc(), SessionSchedule.start_time.asc()).limit(5).all()
    recent_rewards = member.reward_transactions.order_by(RewardTransaction.created_at.desc()).limit(5).all()
    return render_template(
        'member/dashboard.html',
        member=member,
        disqualified_enrollments=disqualified,
        total_points=total_points,
        competitions_count=competitions_count,
        best_rank=best_rank,
        team_membership=team_membership,
        upcoming_sessions=upcoming_sessions,
        recent_rewards=recent_rewards,
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
            'best_rank': best_rank,
        }
        if current_user.member and member.id == current_user.member.id:
            my_entry = entry
        leaderboard.append(entry)

    teams = Team.query.order_by(Team.rating.desc(), Team.name.asc()).all()
    team_members = {}
    for team in teams:
        members = team.members.join(Member).order_by(TeamMember.is_leader.desc(), Member.full_name.asc()).all()
        team_members[team.id] = members

    return render_template(
        'member/competitions_rankings.html',
        leaderboard=leaderboard,
        top_member=top_member,
        teams=teams,
        team_members=team_members,
        my_entry=my_entry,
    )


@member_bp.route('/sessions/timetable')
@login_required
def sessions_timetable():
    week = SessionWeek.query.filter_by(status='published').order_by(SessionWeek.week_start.desc()).first()
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
    week = SessionWeek.query.filter_by(status='published').order_by(SessionWeek.week_start.desc()).first()
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

# Competitions

def _member_is_judge(competition_id, user_id):
    return CompetitionJudge.query.filter_by(competition_id=competition_id, user_id=user_id, is_active=True).first()


def _member_can_submit(competition, member, user_id):
    if not member:
        return False, 'Profile required before submitting.'
    if _member_is_judge(competition.id, user_id):
        return False, 'Judges cannot submit to the same competition.'
    if competition.status != 'published':
        return False, 'Competition is not open for submissions.'
    now = datetime.now()
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


@member_bp.route('/competitions/weekly')
@login_required
def competitions_weekly():
    now = datetime.now()
    base = Competition.query.filter(Competition.frequency == 'weekly', Competition.status != 'draft')
    ongoing = base.filter(Competition.status == 'published', Competition.starts_at <= now, Competition.ends_at >= now).order_by(Competition.ends_at.asc()).all()
    past_query = base.filter(Competition.status == 'finalized').order_by(Competition.ends_at.desc())
    page = request.args.get('page', 1, type=int)
    past = past_query.paginate(page=page, per_page=6, error_out=False)
    return render_template('member/competitions_list.html', view_label='Weekly', ongoing=ongoing, past=past)


@member_bp.route('/competitions/monthly')
@login_required
def competitions_monthly():
    now = datetime.now()
    base = Competition.query.filter(Competition.frequency == 'monthly', Competition.status != 'draft')
    ongoing = base.filter(Competition.status == 'published', Competition.starts_at <= now, Competition.ends_at >= now).order_by(Competition.ends_at.asc()).all()
    past_query = base.filter(Competition.status == 'finalized').order_by(Competition.ends_at.desc())
    page = request.args.get('page', 1, type=int)
    past = past_query.paginate(page=page, per_page=6, error_out=False)
    return render_template('member/competitions_list.html', view_label='Monthly', ongoing=ongoing, past=past)


@member_bp.route('/competitions/<int:competition_id>')
@login_required
def competition_detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    member = current_user.member
    sponsor_links = competition.sponsors.order_by(CompetitionSponsorLink.display_order.asc()).all()
    eligible, reason = _member_can_submit(competition, member, current_user.id)
    submission = None
    enrollment = None
    if member:
        submission = CompetitionSubmission.query.filter_by(competition_id=competition.id, member_id=member.id).first()
        enrollment = CompetitionEnrollment.query.filter_by(competition_id=competition.id, member_id=member.id).first()
    is_judge = _member_is_judge(competition.id, current_user.id) is not None
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
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
        my_rank=my_rank,
        my_award=my_award,
        total_ranked=total_ranked,
    )


@member_bp.route('/competitions/<int:competition_id>/submit', methods=['POST'])
@login_required
def competition_submit(competition_id):
    competition = Competition.query.get_or_404(competition_id)
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
    db.session.add(submission)
    db.session.commit()

    flash('Submission received successfully.', 'success')
    return redirect(url_for('member.competition_detail', competition_id=competition.id))


@member_bp.route('/competitions/<int:competition_id>/leaderboard')
@login_required
def competition_leaderboard(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    submissions_query = competition.submissions.filter(CompetitionSubmission.status != 'disqualified').order_by(CompetitionSubmission.final_score.desc())
    page = request.args.get('page', 1, type=int)
    submissions_page = submissions_query.paginate(page=page, per_page=20, error_out=False)
    is_judge = _member_is_judge(competition.id, current_user.id) is not None
    rewards = competition.rewards.order_by(CompetitionReward.id.asc()).all()
    badges = _build_reward_badges(rewards, submissions_page.total)
    member = current_user.member
    my_submission = None
    my_rank = None
    my_award = None
    if member:
        for idx, s in enumerate(submissions_query.all(), start=1):
            if s.member_id == member.id:
                my_submission = s
                my_rank = idx
                my_award = badges.get(idx)
                break
    return render_template('member/competition_leaderboard.html', competition=competition, submissions=submissions_page, is_judge=is_judge, badges=badges, my_submission=my_submission, my_rank=my_rank, my_award=my_award)


@member_bp.route('/competitions/<int:competition_id>/score/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def competition_score_member(competition_id, submission_id):
    competition = Competition.query.get_or_404(competition_id)
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
    return render_template('member/competition_score.html', competition=competition, submission=submission, criteria=criteria, existing_scores=existing_scores)

@member_bp.route('/competitions/<int:competition_id>/enroll', methods=['POST'])
@login_required
def competition_enroll(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    member = current_user.member
    if not member:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('member.profile'))

    if _member_is_judge(competition.id, current_user.id):
        flash('Judges cannot enroll in this competition.', 'error')
        return redirect(url_for('member.competition_detail', competition_id=competition.id))

    now = datetime.now()
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

    agree = request.form.get('agree_terms')
    if not agree:
        flash('You must agree to the terms before enrolling.', 'error')
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
