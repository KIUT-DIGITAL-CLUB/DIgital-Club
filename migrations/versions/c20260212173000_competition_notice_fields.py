"""add competition enrollment notice fields

Revision ID: c20260212173000
Revises: c20260212154000
Create Date: 2026-02-12 17:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c20260212173000'
down_revision = 'c20260212154000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('competition_enrollment')}
    if 'admin_notice' not in cols:
        op.add_column('competition_enrollment', sa.Column('admin_notice', sa.Text(), nullable=True))
    if 'admin_notice_by' not in cols:
        op.add_column('competition_enrollment', sa.Column('admin_notice_by', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_competition_enrollment_admin_notice_by_user',
            'competition_enrollment',
            'user',
            ['admin_notice_by'],
            ['id']
        )
    if 'admin_notice_at' not in cols:
        op.add_column('competition_enrollment', sa.Column('admin_notice_at', sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('competition_enrollment')}
    if 'admin_notice_by' in cols:
        try:
            op.drop_constraint('fk_competition_enrollment_admin_notice_by_user', 'competition_enrollment', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('competition_enrollment', 'admin_notice_by')
    if 'admin_notice_at' in cols:
        op.drop_column('competition_enrollment', 'admin_notice_at')
    if 'admin_notice' in cols:
        op.drop_column('competition_enrollment', 'admin_notice')
