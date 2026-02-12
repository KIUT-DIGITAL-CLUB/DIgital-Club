"""add daily active users

Revision ID: c20260212154000
Revises: c20260212130000
Create Date: 2026-02-12 15:40:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c20260212154000'
down_revision = 'c20260212130000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'daily_active_user' in tables:
        return

    op.create_table(
        'daily_active_user',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('activity_date', sa.Date(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'activity_date', name='uq_daily_active_user')
    )
    op.create_index('ix_daily_active_user_activity_date', 'daily_active_user', ['activity_date'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'daily_active_user' not in tables:
        return
    op.drop_index('ix_daily_active_user_activity_date', table_name='daily_active_user')
    op.drop_table('daily_active_user')
