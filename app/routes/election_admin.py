"""Admin routes for leadership elections."""
from datetime import datetime

from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app import db
from app.routes import admin_bp
from app.models import (
    Election, ElectionPosition, ElectionCandidate, ElectionVote,
    LeadershipPositionTemplate, Leader, Member, User,
)
from app.election_utils import (
    election_phase, tally_election_results, install_election_winners,
    delete_election_passport,
)


def _parse_dt(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%dT%H:%M')


from app.routes.admin import admin_required


@admin_bp.route('/elections/positions')
@login_required
@admin_required
def election_positions():
    templates = LeadershipPositionTemplate.query.order_by(
        LeadershipPositionTemplate.display_order.asc(),
        LeadershipPositionTemplate.title.asc(),
    ).all()
    return render_template('admin/elections/position_templates.html', templates=templates)


def _clean_roles(raw):
    if not raw:
        return None
    lines = [l.strip().lstrip('•').strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]
    return '\n'.join(lines) if lines else None


@admin_bp.route('/elections/positions/add', methods=['POST'])
@login_required
@admin_required
def election_positions_add():
    title = (request.form.get('title') or '').strip()
    if not title:
        flash('Position title is required.', 'error')
        return redirect(url_for('admin.election_positions'))
    if LeadershipPositionTemplate.query.filter_by(title=title).first():
        flash('Position title already exists.', 'error')
        return redirect(url_for('admin.election_positions'))
    max_order = db.session.query(db.func.max(LeadershipPositionTemplate.display_order)).scalar() or 0
    db.session.add(LeadershipPositionTemplate(
        title=title,
        subtitle=(request.form.get('subtitle') or '').strip() or None,
        description=request.form.get('description'),
        roles=_clean_roles(request.form.get('roles')),
        default_seats=int(request.form.get('default_seats') or 1),
        display_order=max_order + 1,
        is_active=bool(request.form.get('is_active')),
    ))
    db.session.commit()
    flash('Leadership position template added.', 'success')
    return redirect(url_for('admin.election_positions'))


@admin_bp.route('/elections/positions/<int:template_id>/edit', methods=['POST'])
@login_required
@admin_required
def election_positions_edit(template_id):
    tpl = LeadershipPositionTemplate.query.get_or_404(template_id)
    title = (request.form.get('title') or '').strip()
    if not title:
        flash('Position title is required.', 'error')
        return redirect(url_for('admin.election_positions'))
    existing = LeadershipPositionTemplate.query.filter_by(title=title).first()
    if existing and existing.id != tpl.id:
        flash('Another position already uses that title.', 'error')
        return redirect(url_for('admin.election_positions'))
    tpl.title = title
    tpl.subtitle = (request.form.get('subtitle') or '').strip() or None
    tpl.description = request.form.get('description')
    tpl.roles = _clean_roles(request.form.get('roles'))
    tpl.default_seats = int(request.form.get('default_seats') or 1)
    tpl.is_active = bool(request.form.get('is_active'))
    db.session.commit()
    flash('Position template updated.', 'success')
    return redirect(url_for('admin.election_positions'))


@admin_bp.route('/elections/positions/reorder', methods=['POST'])
@login_required
@admin_required
def election_positions_reorder():
    order = request.get_json(silent=True) or {}
    ids = order.get('order') or []
    for idx, tid in enumerate(ids):
        tpl = LeadershipPositionTemplate.query.get(int(tid))
        if tpl:
            tpl.display_order = idx + 1
    db.session.commit()
    return {'ok': True}


@admin_bp.route('/elections/positions/<int:template_id>/delete', methods=['POST'])
@login_required
@admin_required
def election_positions_delete(template_id):
    tpl = LeadershipPositionTemplate.query.get_or_404(template_id)
    db.session.delete(tpl)
    db.session.commit()
    flash('Position template removed.', 'success')
    return redirect(url_for('admin.election_positions'))


@admin_bp.route('/elections')
@login_required
@admin_required
def elections():
    status = request.args.get('status')
    query = Election.query
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Election.created_at.desc()).all()
    stats = {}
    for e in items:
        stats[e.id] = {
            'positions': e.positions.count(),
            'candidates': e.candidates.count(),
            'approved': e.candidates.filter_by(status='approved').count(),
            'votes': e.votes.count(),
        }
    return render_template('admin/elections/index.html', elections=items, stats=stats, status_filter=status)


@admin_bp.route('/elections/add', methods=['GET', 'POST'])
@login_required
@admin_required
def elections_add():
    templates = LeadershipPositionTemplate.query.filter_by(is_active=True).order_by(
        LeadershipPositionTemplate.display_order.asc()
    ).all()
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        if not title:
            flash('Election title is required.', 'error')
            return redirect(url_for('admin.elections_add'))
        election = Election(
            title=title,
            description=request.form.get('description'),
            term_label=(request.form.get('term_label') or '').strip() or None,
            status=request.form.get('status', 'draft'),
            application_starts_at=_parse_dt(request.form.get('application_starts_at')),
            application_ends_at=_parse_dt(request.form.get('application_ends_at')),
            screening_ends_at=_parse_dt(request.form.get('screening_ends_at')),
            voting_starts_at=_parse_dt(request.form.get('voting_starts_at')),
            voting_ends_at=_parse_dt(request.form.get('voting_ends_at')),
            requires_paid_membership=bool(request.form.get('requires_paid_membership')),
            allow_multiple_positions=bool(request.form.get('allow_multiple_positions')),
            show_live_results=bool(request.form.get('show_live_results')),
            created_by=current_user.id,
        )
        db.session.add(election)
        db.session.flush()
        selected = request.form.getlist('position_templates')
        for idx, tid in enumerate(selected):
            tpl = LeadershipPositionTemplate.query.get(int(tid))
            if tpl:
                db.session.add(ElectionPosition(
                    election_id=election.id,
                    template_id=tpl.id,
                    title=tpl.title,
                    subtitle=tpl.subtitle,
                    description=tpl.description,
                    roles=tpl.roles,
                    display_order=idx,
                    seats_available=tpl.default_seats or 1,
                ))
        db.session.commit()
        flash('Election created. Review positions and publish when ready.', 'success')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    return render_template('admin/elections/form.html', election=None, templates=templates)


@admin_bp.route('/elections/<int:election_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def elections_edit(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status == 'finalized':
        flash('Finalized elections cannot be edited.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    templates = LeadershipPositionTemplate.query.filter_by(is_active=True).order_by(
        LeadershipPositionTemplate.display_order.asc()
    ).all()
    if request.method == 'POST':
        election.title = request.form.get('title')
        election.description = request.form.get('description')
        election.term_label = (request.form.get('term_label') or '').strip() or None
        election.status = request.form.get('status', election.status)
        election.application_starts_at = _parse_dt(request.form.get('application_starts_at'))
        election.application_ends_at = _parse_dt(request.form.get('application_ends_at'))
        election.screening_ends_at = _parse_dt(request.form.get('screening_ends_at'))
        election.voting_starts_at = _parse_dt(request.form.get('voting_starts_at'))
        election.voting_ends_at = _parse_dt(request.form.get('voting_ends_at'))
        election.requires_paid_membership = bool(request.form.get('requires_paid_membership'))
        election.allow_multiple_positions = bool(request.form.get('allow_multiple_positions'))
        election.show_live_results = bool(request.form.get('show_live_results'))
        db.session.commit()
        flash('Election updated.', 'success')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    return render_template('admin/elections/form.html', election=election, templates=templates)


@admin_bp.route('/elections/<int:election_id>')
@login_required
@admin_required
def elections_view(election_id):
    election = Election.query.get_or_404(election_id)
    positions = election.positions.order_by(ElectionPosition.display_order.asc()).all()
    templates = LeadershipPositionTemplate.query.filter_by(is_active=True).order_by(
        LeadershipPositionTemplate.display_order.asc()
    ).all()
    existing_titles = {p.title for p in positions}
    stats = {
        'candidates': election.candidates.count(),
        'pending': election.candidates.filter(ElectionCandidate.status.in_(['submitted', 'under_review'])).count(),
        'approved': election.candidates.filter_by(status='approved').count(),
        'votes': election.votes.count(),
    }
    return render_template(
        'admin/elections/detail.html',
        election=election,
        positions=positions,
        templates=templates,
        existing_titles=existing_titles,
        stats=stats,
        phase=election_phase(election),
    )


@admin_bp.route('/elections/<int:election_id>/positions/add', methods=['POST'])
@login_required
@admin_required
def elections_position_add(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status == 'finalized':
        flash('Cannot modify finalized election.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    template_id = request.form.get('template_id')
    title = (request.form.get('title') or '').strip()
    subtitle = (request.form.get('subtitle') or '').strip() or None
    description = request.form.get('description')
    roles = _clean_roles(request.form.get('roles'))
    seats = int(request.form.get('seats_available') or 1)
    if template_id:
        tpl = LeadershipPositionTemplate.query.get(int(template_id))
        if tpl:
            title = tpl.title
            subtitle = tpl.subtitle
            description = tpl.description
            roles = tpl.roles
            if not request.form.get('seats_available'):
                seats = tpl.default_seats or 1
    if not title:
        flash('Position title is required.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    if ElectionPosition.query.filter_by(election_id=election.id, title=title).first():
        flash('Position already exists in this election.', 'warning')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    max_order = db.session.query(db.func.max(ElectionPosition.display_order)).filter_by(
        election_id=election.id
    ).scalar() or 0
    db.session.add(ElectionPosition(
        election_id=election.id,
        template_id=int(template_id) if template_id else None,
        title=title,
        subtitle=subtitle,
        description=description,
        roles=roles,
        display_order=max_order + 1,
        seats_available=seats,
    ))
    db.session.commit()
    flash('Position added to election.', 'success')
    return redirect(url_for('admin.elections_view', election_id=election.id))


@admin_bp.route('/elections/<int:election_id>/positions/<int:position_id>/edit', methods=['POST'])
@login_required
@admin_required
def elections_position_edit(election_id, position_id):
    election = Election.query.get_or_404(election_id)
    if election.status == 'finalized':
        flash('Cannot modify finalized election.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    position = ElectionPosition.query.filter_by(id=position_id, election_id=election.id).first_or_404()
    title = (request.form.get('title') or '').strip()
    if not title:
        flash('Position title is required.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    dup = ElectionPosition.query.filter_by(election_id=election.id, title=title).first()
    if dup and dup.id != position.id:
        flash('Another position already uses that title.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    position.title = title
    position.subtitle = (request.form.get('subtitle') or '').strip() or None
    position.description = request.form.get('description')
    position.roles = _clean_roles(request.form.get('roles'))
    position.seats_available = int(request.form.get('seats_available') or 1)
    db.session.commit()
    flash('Position updated.', 'success')
    return redirect(url_for('admin.elections_view', election_id=election.id))


@admin_bp.route('/elections/<int:election_id>/positions/reorder', methods=['POST'])
@login_required
@admin_required
def elections_positions_reorder(election_id):
    election = Election.query.get_or_404(election_id)
    order = request.get_json(silent=True) or {}
    ids = order.get('order') or []
    for idx, pid in enumerate(ids):
        pos = ElectionPosition.query.filter_by(id=int(pid), election_id=election.id).first()
        if pos:
            pos.display_order = idx
    db.session.commit()
    return {'ok': True}


@admin_bp.route('/elections/<int:election_id>/positions/<int:position_id>/delete', methods=['POST'])
@login_required
@admin_required
def elections_position_delete(election_id, position_id):
    election = Election.query.get_or_404(election_id)
    if election.status == 'finalized':
        flash('Cannot modify finalized election.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    position = ElectionPosition.query.filter_by(id=position_id, election_id=election.id).first_or_404()
    db.session.delete(position)
    db.session.commit()
    flash('Position removed.', 'success')
    return redirect(url_for('admin.elections_view', election_id=election.id))


@admin_bp.route('/elections/<int:election_id>/applications')
@login_required
@admin_required
def elections_applications(election_id):
    election = Election.query.get_or_404(election_id)
    status = request.args.get('status')
    query = election.candidates.join(Member).order_by(ElectionCandidate.submitted_at.desc())
    if status:
        query = query.filter(ElectionCandidate.status == status)
    candidates = query.all()
    return render_template(
        'admin/elections/applications.html',
        election=election,
        candidates=candidates,
        status_filter=status,
    )


@admin_bp.route('/elections/<int:election_id>/candidates/<int:candidate_id>/review', methods=['POST'])
@login_required
@admin_required
def elections_candidate_review(election_id, candidate_id):
    election = Election.query.get_or_404(election_id)
    candidate = ElectionCandidate.query.filter_by(id=candidate_id, election_id=election.id).first_or_404()
    action = (request.form.get('action') or '').strip()
    note = request.form.get('review_note')
    now = datetime.utcnow()
    if action == 'approve':
        candidate.status = 'approved'
        candidate.rejection_reason = None
    elif action == 'reject':
        candidate.status = 'rejected'
        candidate.rejection_reason = request.form.get('rejection_reason') or note
    elif action == 'disqualify':
        candidate.status = 'disqualified'
        candidate.rejection_reason = request.form.get('rejection_reason') or note
    else:
        flash('Invalid review action.', 'error')
        return redirect(url_for('admin.elections_applications', election_id=election.id))
    candidate.reviewed_by = current_user.id
    candidate.reviewed_at = now
    candidate.review_note = note
    db.session.commit()
    try:
        from app.utils import get_notification_service
        if candidate.member and candidate.member.phone:
            svc = get_notification_service()
            label = action.replace('_', ' ')
            svc.send_sms(
                candidate.member.phone,
                f'Digital Club election update: your candidacy for {candidate.position.title} was {label}.'
            )
    except Exception:
        pass
    flash(f'Application {action}d.', 'success')
    return redirect(url_for('admin.elections_applications', election_id=election.id))


@admin_bp.route('/elections/<int:election_id>/results')
@login_required
@admin_required
def elections_results(election_id):
    election = Election.query.get_or_404(election_id)
    positions = election.positions.order_by(ElectionPosition.display_order.asc()).all()
    results = []
    for position in positions:
        cands = position.candidates.filter(
            ElectionCandidate.status.in_(['approved', 'disqualified'])
        ).order_by(ElectionCandidate.vote_count.desc(), ElectionCandidate.rank.asc()).all()
        results.append({'position': position, 'candidates': cands})
    voter_count = db.session.query(ElectionVote.voter_member_id).filter_by(
        election_id=election.id
    ).distinct().count()
    return render_template(
        'admin/elections/results.html',
        election=election,
        results=results,
        voter_count=voter_count,
    )


@admin_bp.route('/elections/<int:election_id>/finalize', methods=['POST'])
@login_required
@admin_required
def elections_finalize(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status == 'finalized':
        flash('Election already finalized.', 'info')
        return redirect(url_for('admin.elections_results', election_id=election.id))
    if election.positions.count() == 0:
        flash('Add at least one position before finalizing.', 'error')
        return redirect(url_for('admin.elections_view', election_id=election.id))
    tally_election_results(election)
    install_election_winners(election)
    election.status = 'finalized'
    election.finalized_at = datetime.utcnow()
    election.finalized_by = current_user.id
    db.session.commit()
    flash('Election finalized. Winners installed to leadership team.', 'success')
    return redirect(url_for('admin.elections_results', election_id=election.id))
