"""Helpers for leadership elections."""
from __future__ import annotations

import os
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

PASSPORT_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp')
PASSPORT_MAX_MB = 5


# Canonical KIUT Digital Club executive positions (from the roles document).
# Each: (title, subtitle, default_seats, [roles...])
DEFAULT_POSITIONS = [
    (
        'Chairperson',
        'Overall Leadership & Strategic Direction',
        1,
        [
            'Lead and oversee all club activities and official events',
            'Represent the club before the university, sponsors, and external organizations',
            'Ensure the club achieves its vision and objectives',
            'Supervise all executive members and make final decisions after consultation',
            'Build partnerships with companies and other organizations',
        ],
    ),
    (
        'Vice Chairperson',
        'Supports Leadership & Oversees Operations',
        1,
        [
            'Support the Chairperson in managing all club operations',
            'Coordinate committees and monitor progress of ongoing activities',
            'Take over leadership responsibilities when the Chairperson is unavailable',
            'Help resolve internal issues and ensure executive members fulfil their roles',
        ],
    ),
    (
        'Secretary',
        'Administration, Records & Documentation',
        1,
        [
            'Record minutes during meetings and prepare meeting agendas',
            'Keep and archive club records, documentation, and official correspondence',
            'Maintain the membership register and attendance records',
            'Send meeting notices and announcements to members',
        ],
    ),
    (
        'Deputy Secretary',
        'Supports Administration & Record Keeping',
        1,
        [
            'Take meeting minutes when the Secretary is absent',
            'Help organize documents, records, and communication scheduling',
            'Maintain attendance records and support administrative tasks during events',
        ],
    ),
    (
        'Project Managers',
        'Lead Technical Projects & Innovation',
        3,
        [
            'Propose innovative projects across Web Dev, Mobile, AI, Cybersecurity, or IoT',
            'Form and manage project teams; assign and monitor tasks and deadlines',
            'Present project updates to the executive committee',
            'Organize hackathons, coding challenges, and encourage portfolio building',
        ],
    ),
    (
        'Communication & Branding Officers',
        'Marketing, Publicity & Brand Identity',
        2,
        [
            'Manage social media accounts and engage with members online',
            'Design posters, promotional materials, and digital content',
            'Publicize club events and maintain the club website',
            "Handle photography and videography; build the club's brand identity",
        ],
    ),
    (
        'Treasurer',
        'Financial Management & Accountability',
        1,
        [
            'Prepare budgets and keep accurate financial records',
            'Collect membership fees and manage club funds responsibly',
            'Prepare financial reports and ensure transparency and accountability',
            'Process approved expenditures and assist in fundraising initiatives',
        ],
    ),
    (
        'Coordination Officers',
        'Internal Coordination & Member Engagement',
        2,
        [
            'Coordinate communication between executive members and committees',
            'Monitor committee activities and ensure tasks are completed on schedule',
            'Assist members with inquiries and help onboard new members',
            'Coordinate volunteers during events and support inter-departmental collaboration',
        ],
    ),
    (
        'Event Planning Officers',
        'Organize Workshops, Competitions & Club Events',
        2,
        [
            'Organize workshops, seminars, conferences, and hackathons',
            'Arrange guest speaker sessions and coordinate event volunteers',
            'Book venues, manage logistics, and prepare event schedules',
            'Evaluate event success and prepare post-event reports',
        ],
    ),
]


def election_passport_dir():
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'elections', 'passports')
    os.makedirs(path, exist_ok=True)
    return path


def save_election_passport(file, election_id: int, member_id: int) -> tuple[str | None, str]:
    if not file or not file.filename:
        return None, 'Passport photo is required.'
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in PASSPORT_EXTENSIONS:
        return None, f'Invalid image type. Allowed: {", ".join(PASSPORT_EXTENSIONS)}'
    file.stream.seek(0, os.SEEK_END)
    size_mb = file.stream.tell() / (1024 * 1024)
    file.stream.seek(0)
    if size_mb > PASSPORT_MAX_MB:
        return None, f'Image exceeds {PASSPORT_MAX_MB}MB limit.'
    stored = f'election_{election_id}_member_{member_id}_{int(datetime.utcnow().timestamp())}_{filename}'
    file.save(os.path.join(election_passport_dir(), stored))
    return stored, ''


def delete_election_passport(filename: str | None):
    if not filename:
        return
    path = os.path.join(election_passport_dir(), os.path.basename(filename))
    if os.path.isfile(path):
        os.remove(path)


def passport_static_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return f'uploads/elections/passports/{os.path.basename(filename)}'


def election_phase(election, now: datetime | None = None) -> str:
    now = now or datetime.now()
    if election.status == 'finalized':
        return 'finalized'
    if election.status == 'cancelled':
        return 'cancelled'
    if election.status == 'voting' or election.is_voting_open():
        return 'voting'
    if election.status == 'screening':
        return 'screening'
    if election.is_application_open():
        return 'nominations'
    if election.application_starts_at and now < election.application_starts_at:
        return 'upcoming'
    if election.voting_ends_at and now > election.voting_ends_at and election.status not in ('finalized', 'archived'):
        return 'closed'
    return election.status or 'draft'


def member_meets_election_eligibility(member, election) -> tuple[bool, str]:
    if not member:
        return False, 'Complete your member profile first.'
    user = member.user
    if not user or not user.is_approved:
        return False, 'Your account must be approved to participate.'
    if election.requires_paid_membership and not member.has_valid_membership():
        return False, 'Valid paid membership is required for this election.'
    return True, ''


def count_votes_for_position(election_position_id: int) -> dict[int, int]:
    from app.models import ElectionVote

    counts: dict[int, int] = {}
    rows = ElectionVote.query.filter_by(election_position_id=election_position_id).all()
    for row in rows:
        counts[row.candidate_id] = counts.get(row.candidate_id, 0) + 1
    return counts


def tally_election_results(election):
    from app import db
    from app.models import ElectionCandidate, ElectionPosition

    for position in election.positions.order_by(ElectionPosition.display_order.asc()).all():
        counts = count_votes_for_position(position.id)
        approved = position.candidates.filter(
            ElectionCandidate.status.in_(['approved', 'disqualified'])
        ).all()
        for c in approved:
            c.vote_count = counts.get(c.id, 0)
        ranked = sorted(approved, key=lambda c: c.vote_count or 0, reverse=True)
        seats = position.seats_available or 1
        for idx, candidate in enumerate(ranked, start=1):
            candidate.rank = idx
            candidate.is_winner = idx <= seats and candidate.status == 'approved'
        for c in approved:
            if c.status != 'approved':
                c.is_winner = False
    db.session.flush()


def install_election_winners(election):
    from app import db
    from app.models import ElectionCandidate, ElectionPosition, Leader

    for position in election.positions.order_by(ElectionPosition.display_order.asc()).all():
        winners = position.candidates.filter_by(is_winner=True, status='approved').order_by(
            ElectionCandidate.rank.asc()
        ).all()
        for winner in winners:
            member = winner.member
            if not member or not member.user_id:
                continue
            existing = Leader.query.filter_by(user_id=member.user_id).first()
            if existing:
                existing.position = position.title
                existing.display_order = position.display_order
            else:
                db.session.add(Leader(
                    user_id=member.user_id,
                    position=position.title,
                    display_order=position.display_order,
                ))
