"""competition enrollment

Revision ID: c20260209165003
Revises: c20260209151049
Create Date: 2026-02-09 16:50:03.202442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260209165003'
down_revision = 'c20260209151049'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'competition_enrollment' not in existing:
        op.create_table(
            'competition_enrollment',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competition.id'), nullable=False),
            sa.Column('member_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='enrolled'),
            sa.Column('disqualified_reason', sa.Text()),
            sa.Column('disqualified_by', sa.Integer(), sa.ForeignKey('user.id')),
            sa.Column('disqualified_at', sa.DateTime()),
            sa.Column('enrolled_at', sa.DateTime()),
            sa.UniqueConstraint('competition_id', 'member_id', name='_competition_enrollment_uc')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if 'competition_enrollment' in existing:
        op.drop_table('competition_enrollment')
