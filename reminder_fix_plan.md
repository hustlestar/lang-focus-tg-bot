
# Reminder System Fix Plan

## Problem Analysis
Only 1 user qualifies for reminders when there are 60+ users in the database because the `reminder_tracking` table only gets created when users interact with the learning system, not when they first start using the bot.

## Solution Overview
Create a combination of:
1. Migration script to initialize reminder_tracking for existing users
2. Modify ensure_user() to automatically create reminder_tracking records

## Implementation Details

### 1. Migration Script: `alembic/versions/005_initialize_reminder_tracking_for_existing_users.py`

```python
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
```

### 2. Modify `lang_focus/core/database.py` - Update `ensure_user()` method

Add automatic creation of reminder_tracking record when ensuring user exists:

```python
async def ensure_user(self, user_id: int, username: Optional[str] = None, language: str = "en") -> Dict[str, Any]:
    """Ensure user exists in database, create if not exists."""
    async with self._pool.acquire() as conn:
        # Try to get existing user
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

        if user:
            # Update username if provided and different
            if username and user["username"] != username:
                await conn.execute(
                    "UPDATE users SET username = $1, updated_at = $2 WHERE user_id = $3", username, datetime.utcnow(), user_id
                )
                logger.debug(f"Updated username for user {user_id}")

            # Ensure reminder tracking record exists
            await self._ensure_reminder_tracking(user_id, conn)

            return dict(user)
        else:
            # Create new user
            await conn.execute(
                """
                INSERT INTO users (user_id, username, language, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $4)
                """,
                user_id,
                username,
                language,
                datetime.utcnow(),
            )

            # Create reminder tracking record for new user
            await self._ensure_reminder_tracking(user_id, conn)

            # Get the created user
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

            logger.info(f"Created new user: {user_id} (@{username})")
            return dict(user)

async def _ensure_reminder_tracking(self, user_id: int, conn):
    """Ensure reminder tracking record exists for user."""
    # Check if tracking record exists
    check_query = "SELECT id FROM reminder_tracking WHERE user_id = $1"
    exists = await conn.fetchval(check_query, user_id)

    if not exists:
        # Create new tracking record with default values
        insert_query = """
            INSERT INTO reminder_tracking (user_id, reminders_enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4)
        """
        await conn.execute(insert_query, user_id, True, datetime.utcnow(), datetime.utcnow())
        logger.debug(f"Created reminder tracking record for user {user_id}")
```

### 3. Modify `lang_focus/core/reminder_scheduler.py` - Update `_get_users_to_remind()` method

Make the query more robust to handle edge cases:

```python
async def _get_users_to_remind(self, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """Get list of users who need reminders."""
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # SQL query to find users who:
    # 1. Have reminders enabled
    # 2. Haven't practiced in 7+ days OR haven't been reminded in 7+ days
    # 3. Handle NULL values properly
    query = """
        SELECT
            rt.user_id,
            u.username,
            rt.last_practice_date,
            rt.last_reminder_date,
            rt.reminder_count
        FROM reminder_tracking rt
        INNER JOIN users u ON rt.user_id = u.user_id
        WHERE
            rt.reminders_enabled = true
            AND (
                (rt.last_practice_date IS NULL OR rt.last_practice_date <= $1)
                OR (rt.last_reminder_date IS NULL OR rt.last_reminder_date <= $1)
            )
    """

    rows = await conn.fetch(query, seven_days_ago)
    users = [dict(row) for row in rows]

    # Log qualifying users for debugging
    if users:
        logger.info(f"Found {len(users)} users qualifying for reminders")
        for user in users:
            last_practice = user['last_practice_date'].strftime('%Y-%m-%d') if user['last_practice_date'] else 'never'
            last_reminder = user['last_reminder_date'].strftime('%Y-%m-%d') if user['last_reminder_date'] else 'never'
            logger.debug(f"  - User {user['user_id']} (@{user['username'] or 'unknown'}) - Last practice: {last_practice}, Last reminder: {last_reminder}")
    else:
        logger.info("No users qualify for reminders at this time")

    return users
```

## Testing Plan

1. Run the migration script to create reminder_tracking records for existing users
2. Verify that all users now have reminder_tracking records
3. Test the reminder scheduler to see if more users qualify for reminders
4. Test new user creation to ensure they get reminder_tracking records automatically
5. Verify the maintain