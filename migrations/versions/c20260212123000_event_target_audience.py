"""add event target audience

Revision ID: c20260212123000
Revises: c20260212110000
Create Date: 2026-02-12 12:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c20260212123000'
down_revision = 'c20260212110000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('event')}
    if 'target_audience' not in cols:
        op.add_column(
            'event',
            sa.Column('target_audience', sa.String(length=20), nullable=False, server_default='everyone')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('event')}
    if 'target_audience' in cols:
        op.drop_column('event', 'target_audience')

