"""add user active account flag

Revision ID: c20260212110000
Revises: c20260209195500
Create Date: 2026-02-12 11:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260212110000'
down_revision = 'c20260209195500'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('user')}
    if 'is_active_account' not in cols:
        op.add_column(
            'user',
            sa.Column('is_active_account', sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('user')}
    if 'is_active_account' in cols:
        op.drop_column('user', 'is_active_account')
