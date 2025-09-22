"""Add reminder tracking table

Revision ID: 004
Revises: 003
Create Date: 2025-01-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create reminder_tracking table
    op.create_table(
        'reminder_tracking',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('last_practice_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reminder_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reminder_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )

    # Create indexes
    op.create_index('idx_reminder_tracking_user_id', 'reminder_tracking', ['user_id'])
    op.create_index('idx_reminder_tracking_last_practice', 'reminder_tracking', ['last_practice_date'])
    op.create_index('idx_reminder_tracking_reminders_enabled', 'reminder_tracking', ['reminders_enabled'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_reminder_tracking_reminders_enabled', 'reminder_tracking')
    op.drop_index('idx_reminder_tracking_last_practice', 'reminder_tracking')
    op.drop_index('idx_reminder_tracking_user_id', 'reminder_tracking')

    # Drop table
    op.drop_table('reminder_tracking')