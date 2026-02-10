"""sessions

Revision ID: c20260209193000
Revises: c20260209165003
Create Date: 2026-02-09 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260209193000'
down_revision = 'c20260209165003'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'session_week' not in existing:
        op.create_table(
            'session_week',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(length=150)),
            sa.Column('week_start', sa.Date(), nullable=False),
            sa.Column('week_end', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('published_at', sa.DateTime()),
            sa.Column('published_by', sa.Integer(), sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime()),
        )

    if 'session_schedule' not in existing:
        op.create_table(
            'session_schedule',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('week_id', sa.Integer(), sa.ForeignKey('session_week.id'), nullable=False),
            sa.Column('session_date', sa.Date(), nullable=False),
            sa.Column('day_of_week', sa.Integer(), nullable=False),
            sa.Column('start_time', sa.Time(), nullable=False),
            sa.Column('topic', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=80), nullable=False),
            sa.Column('mode', sa.String(length=20), nullable=False, server_default='online'),
            sa.Column('meeting_link', sa.String(length=255)),
            sa.Column('location', sa.String(length=200)),
            sa.Column('teaching_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('questions_minutes', sa.Integer(), nullable=False, server_default='15'),
            sa.Column('instructor_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),
        )

    if 'session_report' not in existing:
        op.create_table(
            'session_report',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('session_id', sa.Integer(), sa.ForeignKey('session_schedule.id'), nullable=False),
            sa.Column('instructor_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('winner_username', sa.String(length=120)),
            sa.Column('winner_user_id', sa.Integer(), sa.ForeignKey('user.id')),
            sa.Column('participant_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('notes', sa.Text()),
            sa.Column('submitted_at', sa.DateTime()),
            sa.Column('approved_at', sa.DateTime()),
            sa.Column('approved_by', sa.Integer(), sa.ForeignKey('user.id')),
            sa.Column('points_awarded', sa.Integer(), nullable=False, server_default='0'),
            sa.UniqueConstraint('session_id', 'instructor_user_id', name='_session_report_uc')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'session_report' in existing:
        op.drop_table('session_report')
    if 'session_schedule' in existing:
        op.drop_table('session_schedule')
    if 'session_week' in existing:
        op.drop_table('session_week')
