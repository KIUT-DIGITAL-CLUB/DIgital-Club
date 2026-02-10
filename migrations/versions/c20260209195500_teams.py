"""teams

Revision ID: c20260209195500
Revises: c20260209193000
Create Date: 2026-02-09 19:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260209195500'
down_revision = 'c20260209193000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'team' not in existing:
        op.create_table(
            'team',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False, unique=True),
            sa.Column('description', sa.Text()),
            sa.Column('rating', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime()),
        )

    if 'team_member' not in existing:
        op.create_table(
            'team_member',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('team.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('is_leader', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('joined_at', sa.DateTime()),
            sa.UniqueConstraint('team_id', 'member_id', name='_team_member_uc')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'team_member' in existing:
        op.drop_table('team_member')
    if 'team' in existing:
        op.drop_table('team')
