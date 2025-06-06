"""Add subscription fields to users table

Revision ID: 003
Revises: 002
Create Date: 2025-06-06 17:38:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add subscription fields to users table."""
    # Add subscription fields to users table with proper server defaults
    op.add_column('users', sa.Column('is_subscribed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('subscription_checked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove subscription fields from users table."""
    op.drop_column('users', 'subscription_checked_at')
    op.drop_column('users', 'is_subscribed')