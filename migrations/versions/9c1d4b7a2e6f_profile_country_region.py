"""Add optional country and region to profiles

Revision ID: 9c1d4b7a2e6f
Revises: 0ee5b0a5c117
Create Date: 2026-11-24 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c1d4b7a2e6f'
down_revision = '0ee5b0a5c117'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('profiles', sa.Column('country', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('region', sa.String(), nullable=True))


def downgrade():
    op.drop_column('profiles', 'region')
    op.drop_column('profiles', 'country')
