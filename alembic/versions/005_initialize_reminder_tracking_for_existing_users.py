"""Initialize reminder tracking for existing users

Revision ID: 005
Revises: 004
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Initialize reminder_tracking for all existing users who don't have records
    # Set last_practice_date and last_reminder_date to 8 days ago to make them eligible for reminders
    
    connection = op.get_bind()
    
    # Insert reminder tracking records for users who don't have them
    # Set dates to 8 days ago so they qualify for reminders (need 7+ days)
    query = text("""
        INSERT INTO reminder_tracking (user_id, last_practice_date, last_reminder_date, reminder_count, reminders_enabled, created_at, updated_at)
        SELECT u.user_id, 
               CURRENT_TIMESTAMP - INTERVAL '8 days',
               CURRENT_TIMESTAMP - INTERVAL '8 days', 
               0, 
               true, 
               CURRENT_TIMESTAMP,
               CURRENT_TIMESTAMP
        FROM users u
        LEFT JOIN reminder_tracking rt ON u.user_id = rt.user_id
        WHERE rt.user_id IS NULL
    """)
    
    result = connection.execute(query)
    inserted_count = result.rowcount
    
    # Log the result
    print(f"Initialized reminder tracking for {inserted_count} existing users")


def downgrade() -> None:
    # Remove the reminder tracking records that were added by this migration
    # Note: This will only remove records that were created by this specific migration
    # We need to be careful not to remove records that might have been created legitimately
    
    connection = op.get_bind()
    
    # Delete reminder tracking records for users who have never practiced
    # and were created at the same time as their user record (indicating they were added by migration)
    query = text("""
        DELETE FROM reminder_tracking 
        WHERE user_id IN (
            SELECT rt.user_id 
            FROM reminder_tracking rt
            INNER JOIN users u ON rt.user_id = u.user_id
            WHERE rt.last_practice_date <= u.created_at + INTERVAL '1 minute'
            AND rt.last_reminder_date <= u.created_at + INTERVAL '1 minute'
            AND rt.reminder_count = 0
        )
    """)
    
    connection.execute(query)