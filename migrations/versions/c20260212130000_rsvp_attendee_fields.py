"""add rsvp attendee fields

Revision ID: c20260212130000
Revises: c20260212123000
Create Date: 2026-02-12 13:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c20260212130000'
down_revision = 'c20260212123000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('rsvp')}
    if 'attendee_type' not in cols:
        op.add_column('rsvp', sa.Column('attendee_type', sa.String(length=20)))
    if 'study_field' not in cols:
        op.add_column('rsvp', sa.Column('study_field', sa.String(length=100)))
    if 'study_year' not in cols:
        op.add_column('rsvp', sa.Column('study_year', sa.String(length=20)))
    if 'non_student_role' not in cols:
        op.add_column('rsvp', sa.Column('non_student_role', sa.String(length=30)))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('rsvp')}
    if 'non_student_role' in cols:
        op.drop_column('rsvp', 'non_student_role')
    if 'study_year' in cols:
        op.drop_column('rsvp', 'study_year')
    if 'study_field' in cols:
        op.drop_column('rsvp', 'study_field')
    if 'attendee_type' in cols:
        op.drop_column('rsvp', 'attendee_type')

