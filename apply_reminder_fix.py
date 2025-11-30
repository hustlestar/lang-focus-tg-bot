#!/usr/bin/env python3
"""
Script to apply the reminder system fix.

This script will:
1. Apply the migration to initialize reminder_tracking for existing users
2. Verify the fix by checking how many users now qualify for reminders
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from lang_focus.config.settings import BotConfig
from lang_focus.core.database import DatabaseManager
from lang_focus.core.reminder_scheduler import ReminderScheduler
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.core.migration_manager import MigrationManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to apply the reminder fix."""
    try:
        # Load configuration
        config = BotConfig.from_env()
        logger.info("Loaded configuration")

        # Initialize migration manager and apply migration
        logger.info("Applying migration to initialize reminder tracking...")
        migration_manager = MigrationManager(config.database_url)
        
        # Apply the specific migration
        success = migration_manager.apply_migrations("005")
        if not success:
            logger.error("Failed to apply migration")
            return False
        
        logger.info("Migration applied successfully")

        # Initialize database and test the fix
        logger.info("Testing the fix...")
        database = DatabaseManager(config.database_url)
        await database.setup()

        # Check total users and reminder tracking records
        async with database._pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            reminder_tracking_users = await conn.fetchval("SELECT COUNT(*) FROM reminder_tracking")
            enabled_reminders = await conn.fetchval("SELECT COUNT(*) FROM reminder_tracking WHERE reminders_enabled = true")
            
            logger.info(f"Total users in database: {total_users}")
            logger.info(f"Users with reminder tracking: {reminder_tracking_users}")
            logger.info(f"Users with reminders enabled: {enabled_reminders}")

        # Test reminder scheduler
        from telegram import Bot
        bot = Bot(token=config.bot_token)
        locale_manager = LocaleManager()
        reminder_scheduler = ReminderScheduler(database, bot, locale_manager)

        # Get users who qualify for reminders
        async with database._pool.acquire() as conn:
            qualifying_users = await reminder_scheduler._get_users_to_remind(conn)
            logger.info(f"Users qualifying for reminders: {len(qualifying_users)}")

        await database.close()
        
        logger.info("✅ Fix applied successfully!")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Total users: {total_users}")
        logger.info(f"   - Users with reminder tracking: {reminder_tracking_users}")
        logger.info(f"   - Users with reminders enabled: {enabled_reminders}")
        logger.info(f"   - Users qualifying for reminders: {len(qualifying_users)}")
        
        return True

    except Exception as e:
        logger.error(f"Error applying fix: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)