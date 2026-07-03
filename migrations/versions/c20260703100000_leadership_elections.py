"""leadership elections

Revision ID: c20260703100000
Revises: c20260305113000
Create Date: 2026-07-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c20260703100000'
down_revision = 'c20260305113000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'leadership_position_template' not in tables:
        op.create_table(
            'leadership_position_template',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(length=100), nullable=False),
            sa.Column('subtitle', sa.String(length=200)),
            sa.Column('description', sa.Text()),
            sa.Column('roles', sa.Text()),
            sa.Column('default_seats', sa.Integer(), server_default='1'),
            sa.Column('display_order', sa.Integer(), server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime()),
            sa.UniqueConstraint('title', name='uq_leadership_position_template_title'),
        )

    if 'election' not in tables:
        op.create_table(
            'election',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('term_label', sa.String(length=100)),
            sa.Column('status', sa.String(length=20), server_default='draft'),
            sa.Column('application_starts_at', sa.DateTime()),
            sa.Column('application_ends_at', sa.DateTime()),
            sa.Column('screening_ends_at', sa.DateTime()),
            sa.Column('voting_starts_at', sa.DateTime()),
            sa.Column('voting_ends_at', sa.DateTime()),
            sa.Column('requires_paid_membership', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('allow_multiple_positions', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('show_live_results', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('financial_period_id', sa.Integer(), sa.ForeignKey('financial_period.id')),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),
            sa.Column('finalized_at', sa.DateTime()),
            sa.Column('finalized_by', sa.Integer(), sa.ForeignKey('user.id')),
        )

    if 'election_position' not in tables:
        op.create_table(
            'election_position',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('election_id', sa.Integer(), sa.ForeignKey('election.id'), nullable=False),
            sa.Column('template_id', sa.Integer(), sa.ForeignKey('leadership_position_template.id')),
            sa.Column('title', sa.String(length=100), nullable=False),
            sa.Column('subtitle', sa.String(length=200)),
            sa.Column('description', sa.Text()),
            sa.Column('roles', sa.Text()),
            sa.Column('display_order', sa.Integer(), server_default='0'),
            sa.Column('seats_available', sa.Integer(), server_default='1'),
            sa.UniqueConstraint('election_id', 'title', name='_election_position_title_uc'),
        )

    if 'election_candidate' not in tables:
        op.create_table(
            'election_candidate',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('election_id', sa.Integer(), sa.ForeignKey('election.id'), nullable=False),
            sa.Column('election_position_id', sa.Integer(), sa.ForeignKey('election_position.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='draft'),
            sa.Column('manifesto', sa.Text()),
            sa.Column('passport_image', sa.String(length=255)),
            sa.Column('submitted_at', sa.DateTime()),
            sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('user.id')),
            sa.Column('reviewed_at', sa.DateTime()),
            sa.Column('review_note', sa.Text()),
            sa.Column('rejection_reason', sa.Text()),
            sa.Column('vote_count', sa.Integer(), server_default='0'),
            sa.Column('rank', sa.Integer()),
            sa.Column('is_winner', sa.Boolean(), server_default=sa.text('0')),
            sa.UniqueConstraint('election_position_id', 'member_id', name='_election_candidate_position_member_uc'),
        )

    if 'election_vote' not in tables:
        op.create_table(
            'election_vote',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('election_id', sa.Integer(), sa.ForeignKey('election.id'), nullable=False),
            sa.Column('election_position_id', sa.Integer(), sa.ForeignKey('election_position.id'), nullable=False),
            sa.Column('voter_member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('election_candidate.id'), nullable=False),
            sa.Column('cast_at', sa.DateTime()),
            sa.UniqueConstraint('election_position_id', 'voter_member_id', name='_election_vote_position_voter_uc'),
        )


def downgrade():
    op.drop_table('election_vote')
    op.drop_table('election_candidate')
    op.drop_table('election_position')
    op.drop_table('election')
    op.drop_table('leadership_position_template')
