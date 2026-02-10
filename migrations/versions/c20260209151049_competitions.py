"""competitions

Revision ID: c20260209151049
Revises: b033ca5044ab
Create Date: 2026-02-09 15:10:49.068365

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260209151049'
down_revision = 'b033ca5044ab'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'competition_sponsor' not in existing:
        op.create_table(
            'competition_sponsor',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('website', sa.String(length=200)),
            sa.Column('logo', sa.String(length=200)),
            sa.Column('description', sa.Text()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime()),
            sa.UniqueConstraint('name', name='uq_competition_sponsor_name')
        )

    if 'competition' not in existing:
        op.create_table(
            'competition',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('frequency', sa.String(length=20), nullable=False),
            sa.Column('level', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('eligibility_rule', sa.String(length=20), nullable=False, server_default='default'),
            sa.Column('eligibility_years', sa.String(length=100)),
            sa.Column('requires_paid_membership', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('submission_type', sa.String(length=20), nullable=False),
            sa.Column('submission_max_mb', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('starts_at', sa.DateTime(), nullable=False),
            sa.Column('ends_at', sa.DateTime(), nullable=False),
            sa.Column('assessment_mode', sa.String(length=20), nullable=False, server_default='online'),
            sa.Column('assessment_instructions', sa.Text()),
            sa.Column('assessment_link', sa.String(length=200)),
            sa.Column('assessment_location', sa.String(length=200)),
            sa.Column('assessment_date', sa.DateTime()),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),
        )

    if 'competition_sponsor_link' not in existing:
        op.create_table(
            'competition_sponsor_link',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('sponsor_id', sa.Integer(), sa.ForeignKey('competition_sponsor.id'), nullable=False),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.UniqueConstraint('competition_id', 'sponsor_id', name='_competition_sponsor_uc')
        )

    if 'competition_judge' not in existing:
        op.create_table(
            'competition_judge',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('is_chair', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('assigned_at', sa.DateTime()),
            sa.UniqueConstraint('competition_id', 'user_id', name='_competition_judge_uc')
        )

    if 'competition_criteria' not in existing:
        op.create_table(
            'competition_criteria',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('max_points', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('weight_percent', sa.Integer(), nullable=False, server_default='0'),
            sa.UniqueConstraint('competition_id', 'name', name='_competition_criteria_uc')
        )

    if 'competition_submission' not in existing:
        op.create_table(
            'competition_submission',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('submission_type', sa.String(length=20), nullable=False),
            sa.Column('submission_value', sa.String(length=255), nullable=False),
            sa.Column('submitted_at', sa.DateTime()),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='submitted'),
            sa.Column('total_score', sa.Float(), nullable=False, server_default='0'),
            sa.Column('bonus_points', sa.Float(), nullable=False, server_default='0'),
            sa.Column('final_score', sa.Float(), nullable=False, server_default='0'),
            sa.Column('rank', sa.Integer()),
            sa.Column('points_awarded', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_winner', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.UniqueConstraint('competition_id', 'member_id', name='_competition_submission_uc')
        )

    if 'competition_score' not in existing:
        op.create_table(
            'competition_score',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('submission_id', sa.Integer(), sa.ForeignKey('competition_submission.id'), nullable=False),
            sa.Column('judge_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('criteria_id', sa.Integer(), sa.ForeignKey('competition_criteria.id'), nullable=False),
            sa.Column('score', sa.Float(), nullable=False, server_default='0'),
            sa.Column('comment', sa.Text()),
            sa.Column('created_at', sa.DateTime()),
            sa.UniqueConstraint('submission_id', 'judge_id', 'criteria_id', name='_competition_score_uc')
        )

    if 'competition_reward' not in existing:
        op.create_table(
            'competition_reward',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('reward_type', sa.String(length=20), nullable=False, server_default='position'),
            sa.Column('rank_from', sa.Integer()),
            sa.Column('rank_to', sa.Integer()),
            sa.Column('percent', sa.Integer()),
            sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('prize_title', sa.String(length=150)),
            sa.Column('prize_description', sa.Text())
        )

    if 'competition_winner' not in existing:
        op.create_table(
            'competition_winner',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('level', sa.Integer(), nullable=False),
            sa.Column('rank', sa.Integer(), nullable=False),
            sa.Column('points_awarded', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('prize_title', sa.String(length=150)),
            sa.Column('prize_description', sa.Text()),
            sa.Column('created_at', sa.DateTime())
        )

    if 'competition_guard' not in existing:
        op.create_table(
            'competition_guard',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('level', sa.Integer(), nullable=False),
            sa.Column('week_start', sa.Date(), nullable=False),
            sa.Column('week_end', sa.Date(), nullable=False),
            sa.Column('title', sa.String(length=150)),
            sa.Column('work_link', sa.String(length=255)),
            sa.Column('created_at', sa.DateTime())
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    for table in [
        'competition_guard',
        'competition_winner',
        'competition_reward',
        'competition_score',
        'competition_submission',
        'competition_criteria',
        'competition_judge',
        'competition_sponsor_link',
        'competition',
        'competition_sponsor',
    ]:
        if table in existing:
            op.drop_table(table)
