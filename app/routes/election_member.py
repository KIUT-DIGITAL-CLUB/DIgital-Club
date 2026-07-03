"""Member routes for leadership elections."""
from datetime import datetime

from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user

from app import db
from app.routes import member_bp
from app.models import Election, ElectionPosition, ElectionCandidate, ElectionVote, Member
from app.election_utils import (
    election_phase,
    member_meets_election_eligibility,
    save_election_passport,
    delete_election_passport,
    passport_static_url,
    tally_election_results,
)


def _visible_elections():
    return Election.query.filter(~Election.status.in_(['draft', 'cancelled']))


@member_bp.route('/elections')
@login_required
def elections_browse():
    tab = request.args.get('tab', 'active')
    now = datetime.now()
    all_visible = _visible_elections().order_by(Election.created_at.desc()).all()
    active, upcoming, past = [], [], []
    for e in all_visible:
        phase = election_phase(e, now)
        if e.status == 'finalized' or phase == 'finalized':
            past.append(e)
        elif phase == 'upcoming':
            upcoming.append(e)
        else:
            active.append(e)
    member = current_user.member
    my_apps = {}
    my_votes = set()
    if member:
        for c in ElectionCandidate.query.filter_by(member_id=member.id).all():
            my_apps[c.election_id] = c
        for v in ElectionVote.query.filter_by(voter_member_id=member.id).all():
            my_votes.add(v.election_position_id)
    return render_template(
        'member/elections/list.html',
        tab=tab,
        active=active,
        upcoming=upcoming,
        past=past,
        my_apps=my_apps,
        my_votes=my_votes,
    )


@member_bp.route('/elections/<int:election_id>')
@login_required
def election_detail(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status in ('draft', 'cancelled'):
        abort(404)
    member = current_user.member
    positions = election.positions.order_by(ElectionPosition.display_order.asc()).all()
    eligible, reason = member_meets_election_eligibility(member, election)
    phase = election_phase(election)
    my_candidates = {}
    voted_positions = set()
    if member:
        for c in ElectionCandidate.query.filter_by(election_id=election.id, member_id=member.id).all():
            my_candidates[c.election_position_id] = c
        for v in ElectionVote.query.filter_by(election_id=election.id, voter_member_id=member.id).all():
            voted_positions.add(v.election_position_id)
    approved_by_position = {}
    for p in positions:
        approved_by_position[p.id] = p.candidates.filter_by(status='approved').order_by(
            ElectionCandidate.submitted_at.asc()
        ).all()
    return render_template(
        'member/elections/detail.html',
        election=election,
        positions=positions,
        phase=phase,
        eligible=eligible,
        reason=reason,
        my_candidates=my_candidates,
        voted_positions=voted_positions,
        approved_by_position=approved_by_position,
        can_apply=election.is_application_open() and eligible,
        can_vote=election.is_voting_open() and eligible,
    )


@member_bp.route('/elections/<int:election_id>/apply/<int:position_id>', methods=['GET', 'POST'])
@login_required
def election_apply(election_id, position_id):
    election = Election.query.get_or_404(election_id)
    if election.status in ('draft', 'cancelled', 'finalized'):
        abort(404)
    position = ElectionPosition.query.filter_by(id=position_id, election_id=election.id).first_or_404()
    member = current_user.member
    eligible, reason = member_meets_election_eligibility(member, election)
    if not eligible:
        flash(reason, 'error')
        return redirect(url_for('member.election_detail', election_id=election.id))
    if not election.is_application_open():
        flash('Application window is closed.', 'error')
        return redirect(url_for('member.election_detail', election_id=election.id))
    existing = ElectionCandidate.query.filter_by(
        election_position_id=position.id, member_id=member.id
    ).first()
    if not election.allow_multiple_positions:
        other = ElectionCandidate.query.filter(
            ElectionCandidate.election_id == election.id,
            ElectionCandidate.member_id == member.id,
            ElectionCandidate.election_position_id != position.id,
            ~ElectionCandidate.status.in_(['withdrawn', 'rejected']),
        ).first()
        if other:
            flash('You may only apply for one position in this election.', 'error')
            return redirect(url_for('member.election_detail', election_id=election.id))
    if request.method == 'POST':
        manifesto = (request.form.get('manifesto') or '').strip()
        if len(manifesto) < 50:
            flash('Manifesto must be at least 50 characters.', 'error')
            return redirect(url_for('member.election_apply', election_id=election.id, position_id=position.id))
        submit_now = request.form.get('action') == 'submit'
        candidate = existing or ElectionCandidate(
            election_id=election.id,
            election_position_id=position.id,
            member_id=member.id,
            status='draft',
        )
        candidate.manifesto = manifesto
        if 'passport_image' in request.files:
            f = request.files['passport_image']
            if f and f.filename:
                saved, err = save_election_passport(f, election.id, member.id)
                if err:
                    flash(err, 'error')
                    return redirect(url_for('member.election_apply', election_id=election.id, position_id=position.id))
                if candidate.passport_image:
                    delete_election_passport(candidate.passport_image)
                candidate.passport_image = saved
        if submit_now:
            if not candidate.passport_image:
                flash('Passport photo is required to submit.', 'error')
                return redirect(url_for('member.election_apply', election_id=election.id, position_id=position.id))
            candidate.status = 'submitted'
            candidate.submitted_at = datetime.utcnow()
        if not existing:
            db.session.add(candidate)
        db.session.commit()
        flash('Application submitted for review.' if submit_now else 'Draft saved.', 'success')
        return redirect(url_for('member.election_detail', election_id=election.id))
    return render_template(
        'member/elections/apply.html',
        election=election,
        position=position,
        candidate=existing,
    )


@member_bp.route('/elections/<int:election_id>/withdraw/<int:candidate_id>', methods=['POST'])
@login_required
def election_withdraw(election_id, candidate_id):
    election = Election.query.get_or_404(election_id)
    member = current_user.member
    candidate = ElectionCandidate.query.filter_by(
        id=candidate_id, election_id=election.id, member_id=member.id
    ).first_or_404()
    if candidate.status in ('withdrawn', 'disqualified'):
        flash('Application already closed.', 'info')
        return redirect(url_for('member.election_detail', election_id=election.id))
    candidate.status = 'withdrawn'
    db.session.commit()
    flash('Application withdrawn.', 'success')
    return redirect(url_for('member.election_detail', election_id=election.id))


@member_bp.route('/elections/<int:election_id>/vote', methods=['GET', 'POST'])
@login_required
def election_vote(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status in ('draft', 'cancelled', 'finalized'):
        abort(404)
    member = current_user.member
    eligible, reason = member_meets_election_eligibility(member, election)
    if not eligible:
        flash(reason, 'error')
        return redirect(url_for('member.election_detail', election_id=election.id))
    if not election.is_voting_open():
        flash('Voting window is closed.', 'error')
        return redirect(url_for('member.election_detail', election_id=election.id))
    positions = election.positions.order_by(ElectionPosition.display_order.asc()).all()
    existing_votes = {
        v.election_position_id: v
        for v in ElectionVote.query.filter_by(election_id=election.id, voter_member_id=member.id).all()
    }
    if request.method == 'POST':
        for position in positions:
            if position.id in existing_votes:
                continue
            key = f'vote_{position.id}'
            candidate_id = request.form.get(key, type=int)
            if not candidate_id:
                flash(f'Please select a candidate for {position.title}.', 'error')
                return redirect(url_for('member.election_vote', election_id=election.id))
            candidate = ElectionCandidate.query.filter_by(
                id=candidate_id,
                election_position_id=position.id,
                status='approved',
            ).first()
            if not candidate:
                flash('Invalid candidate selection.', 'error')
                return redirect(url_for('member.election_vote', election_id=election.id))
            if candidate.member_id == member.id:
                flash('You cannot vote for yourself.', 'error')
                return redirect(url_for('member.election_vote', election_id=election.id))
            db.session.add(ElectionVote(
                election_id=election.id,
                election_position_id=position.id,
                voter_member_id=member.id,
                candidate_id=candidate.id,
            ))
        db.session.commit()
        if election.show_live_results:
            tally_election_results(election)
            db.session.commit()
        flash('Your vote has been recorded. Thank you for participating.', 'success')
        return redirect(url_for('member.election_detail', election_id=election.id))
    ballot = []
    for position in positions:
        candidates = position.candidates.filter_by(status='approved').order_by(
            ElectionCandidate.submitted_at.asc()
        ).all()
        ballot.append({
            'position': position,
            'candidates': candidates,
            'already_voted': position.id in existing_votes,
        })
    return render_template(
        'member/elections/vote.html',
        election=election,
        ballot=ballot,
        existing_votes=existing_votes,
    )


@member_bp.route('/elections/<int:election_id>/results')
@login_required
def election_results(election_id):
    election = Election.query.get_or_404(election_id)
    if election.status not in ('finalized', 'voting', 'counting') and not election.show_live_results:
        flash('Results are not published yet.', 'info')
        return redirect(url_for('member.election_detail', election_id=election.id))
    if election.status != 'finalized' and not election.show_live_results:
        flash('Results will be available after finalization.', 'info')
        return redirect(url_for('member.election_detail', election_id=election.id))
    positions = election.positions.order_by(ElectionPosition.display_order.asc()).all()
    results = []
    for position in positions:
        cands = position.candidates.filter(
            ElectionCandidate.status.in_(['approved', 'disqualified'])
        ).order_by(ElectionCandidate.vote_count.desc()).all()
        results.append({'position': position, 'candidates': cands})
    return render_template('member/elections/results.html', election=election, results=results)
