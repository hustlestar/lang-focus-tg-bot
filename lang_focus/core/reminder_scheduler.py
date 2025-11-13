"""Reminder scheduler for language learning practice notifications."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import asyncpg
from telegram import Bot
from telegram.error import TelegramError

from lang_focus.core.database import DatabaseManager
from lang_focus.core.locale_manager import LocaleManager

logger = logging.getLogger(__name__)

# Promotional messages in Russian
PROMOTIONAL_MESSAGES = [
    """🎯 Пора практиковаться!

Прошла неделя с вашей последней тренировки. Давайте продолжим развивать навыки речевых трюков!

💡 Кстати, попробуйте наши другие продукты:
• 💱 [Exchange Rates Pro](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=exchange_rates) - конвертер валют для Chrome
• 🚫 [Block Website](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=site_blocker) - блокировщик сайтов для Chrome
• 📚 @world\_word\_war\_bot - изучение слов с интервальным повторением
• ⚖️ @belarus\_law\_support\_bot - юридическая помощь по Беларуси

🔗 [Все продукты OverX](https://www.overx.ai/products?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder)

Нажмите /learn чтобы начать тренировку!""",

    """📚 Время для практики!

7 дней без тренировки - самое время вернуться к обучению речевым трюкам.

🛠 Наши полезные инструменты:
• [Exchange Rates Pro](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=exchange_rates) - 100+ валют в Chrome
• [Block Website](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=site_blocker) - контроль отвлечений в Chrome
• @world\_word\_war\_bot - продвинутая лексика и синонимы
• @belarus\_law\_support\_bot - белорусское право 24/7

Начните с /learn или /continue""",

    """🧠 Не забывайте практиковаться!

Неделя прошла! Продолжайте совершенствовать речевые трюки.

✨ Попробуйте также:
• [Конвертер валют](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=exchange_rates) для Chrome
• [Блокировщик сайтов](https://www.overx.ai/api/products/redirect?utm_source=lang_focus_tg_bot&utm_medium=telegram&utm_campaign=reminder&utm_content=site_blocker) для Chrome
• Изучение слов @world\_word\_war\_bot
• @belarus\_law\_support\_bot - юрист по законам Беларуси

Команда /learn ждет вас!"""
]


class ReminderScheduler:
    """Manages reminder notifications for users."""

    def __init__(self, database: DatabaseManager, bot: Bot, locale_manager: LocaleManager):
        self.database = database
        self.bot = bot
        self.locale_manager = locale_manager
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._message_index = 0

    async def start(self):
        """Start the reminder scheduler."""
        if self.is_running:
            logger.warning("Reminder scheduler is already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Reminder scheduler started")

    async def stop(self):
        """Stop the reminder scheduler."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Reminder scheduler stopped")

    async def _run_scheduler(self):
        """Main scheduler loop - runs once daily at 12:00 UTC."""
        while self.is_running:
            try:
                # Calculate time until next 12:00 UTC
                now = datetime.now(timezone.utc)
                next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)

                # If it's already past 12:00 today, schedule for tomorrow
                if now >= next_run:
                    next_run = next_run + timedelta(days=1)

                # Calculate seconds until next run
                seconds_until_run = (next_run - now).total_seconds()

                logger.info(f"Next reminder check scheduled for {next_run} UTC (in {seconds_until_run/3600:.1f} hours)")

                # Wait until scheduled time
                await asyncio.sleep(seconds_until_run)

                # Check and send reminders
                if self.is_running:
                    logger.info("Running daily reminder check at 12:00 UTC")
                    await self._check_and_send_reminders()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                # On error, wait 1 hour before retrying
                await asyncio.sleep(3600)

    async def _check_and_send_reminders(self):
        """Check which users need reminders and send them."""
        try:
            async with self.database._pool.acquire() as conn:
                # Get users who need reminders
                users_to_remind = await self._get_users_to_remind(conn)

                logger.info(f"Starting reminder batch send to {len(users_to_remind)} users")

                for user_data in users_to_remind:
                    try:
                        await self._send_reminder(
                            user_data['user_id'],
                            user_data.get('username'),
                            conn
                        )
                    except Exception as e:
                        user_handle = f"@{user_data.get('username')}" if user_data.get('username') else "unknown"
                        logger.error(f"Failed to send reminder to User {user_data['user_id']} ({user_handle}): {e}")

                logger.info(f"Completed reminder batch send")

        except Exception as e:
            logger.error(f"Error checking reminders: {e}")

    async def _get_users_to_remind(self, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        """Get list of users who need reminders."""
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # SQL query to find users who:
        # 1. Have reminders enabled
        # 2. Haven't practiced in 7+ days OR haven't been reminded in 7+ days
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
                    AND (rt.last_reminder_date IS NULL OR rt.last_reminder_date <= $1)
                )
        """

        rows = await conn.fetch(query, seven_days_ago)
        users = [dict(row) for row in rows]

        # Log qualifying users for debugging
        if users:
            logger.info(f"Found {len(users)} users qualifying for reminders")
            for user in users:
                logger.debug(f"  - User {user['user_id']} (@{user['username'] or 'unknown'})")
        else:
            logger.info("No users qualify for reminders at this time")

        return users

    async def _send_reminder(self, user_id: int, username: Optional[str], conn: asyncpg.Connection):
        """Send reminder notification to a user."""
        user_handle = f"@{username}" if username else "unknown"
        try:
            # Log start of send attempt
            logger.info(f"Sending reminder to User {user_id} ({user_handle})")

            # Get promotional message (cycle through them)
            message = PROMOTIONAL_MESSAGES[self._message_index % len(PROMOTIONAL_MESSAGES)]
            self._message_index += 1

            # Send message
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

            # Update reminder tracking
            update_query = """
                UPDATE reminder_tracking
                SET
                    last_reminder_date = $1,
                    reminder_count = reminder_count + 1,
                    updated_at = $2
                WHERE user_id = $3
            """

            await conn.execute(
                update_query,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                user_id
            )

            logger.info(f"Successfully sent reminder to User {user_id} ({user_handle})")

        except TelegramError as e:
            error_msg = str(e).lower()
            if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                # Disable reminders for this user
                await self._disable_reminders(user_id, conn)
                logger.info(f"User {user_id} ({user_handle}) has blocked the bot - disabling reminders")
                logger.warning(f"User {user_id} ({user_handle}) has blocked the bot - disabling reminders")
            else:
                logger.info(f"Failed to send reminder to User {user_id} ({user_handle}): {e}")
                logger.error(f"Telegram error sending reminder to User {user_id} ({user_handle}): {e}")
        except Exception as e:
            logger.info(f"Error sending reminder to User {user_id} ({user_handle}): {e}")
            logger.error(f"Error sending reminder to User {user_id} ({user_handle}): {e}")

    async def _disable_reminders(self, user_id: int, conn: asyncpg.Connection):
        """Disable reminders for a user (e.g., if they blocked the bot)."""
        try:
            update_query = """
                UPDATE reminder_tracking
                SET
                    reminders_enabled = false,
                    updated_at = $1
                WHERE user_id = $2
            """

            await conn.execute(
                update_query,
                datetime.now(timezone.utc),
                user_id
            )

            logger.info(f"Disabled reminders for user {user_id}")
        except Exception as e:
            logger.error(f"Error disabling reminders for {user_id}: {e}")

    async def force_send_reminder_to_all(self) -> int:
        """Force send reminders to all users in the database."""
        sent_count = 0
        failed_count = 0

        try:
            async with self.database._pool.acquire() as conn:
                # Get all user IDs and usernames from database
                query = "SELECT DISTINCT user_id, username FROM users ORDER BY user_id"
                rows = await conn.fetch(query)

                logger.info(f"Sending reminders to {len(rows)} users...")

                for row in rows:
                    user_id = row['user_id']
                    username = row['username']
                    user_handle = f"@{username}" if username else "unknown"
                    try:
                        # Use rotating messages
                        message = PROMOTIONAL_MESSAGES[self._message_index % len(PROMOTIONAL_MESSAGES)]
                        self._message_index += 1

                        await self.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )

                        sent_count += 1
                        logger.info(f"Sent reminder to User {user_id} ({user_handle})")

                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.1)

                    except TelegramError as e:
                        error_msg = str(e).lower()
                        if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                            logger.info(f"User {user_id} ({user_handle}) has blocked the bot")
                            # Optionally disable reminders for this user
                            await self._disable_reminders(user_id, conn)
                        else:
                            logger.info(f"Failed to send reminder to User {user_id} ({user_handle}): {e}")
                            logger.error(f"Failed to send reminder to User {user_id} ({user_handle}): {e}")
                        failed_count += 1
                    except Exception as e:
                        logger.info(f"Unexpected error sending to User {user_id} ({user_handle}): {e}")
                        logger.error(f"Unexpected error sending to User {user_id} ({user_handle}): {e}")
                        failed_count += 1

                logger.info(f"Force sent reminders: {sent_count} successful, {failed_count} failed")
                return sent_count

        except Exception as e:
            logger.error(f"Error in force_send_reminder_to_all: {e}")
            return sent_count

    async def force_send_reminder(self, user_id: int) -> bool:
        """Force send a reminder to a specific user (maintainer command)."""
        try:
            async with self.database._pool.acquire() as conn:
                # Check if user exists and get username
                user_query = "SELECT user_id, username FROM users WHERE user_id = $1"
                user_row = await conn.fetchrow(user_query, user_id)
                if not user_row:
                    logger.warning(f"User {user_id} not found")
                    return False

                username = user_row['username']
                user_handle = f"@{username}" if username else "unknown"

                # Send reminder
                message = PROMOTIONAL_MESSAGES[0]  # Use first message for forced reminders

                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )

                logger.info(f"Force sent reminder to User {user_id} ({user_handle})")
                return True

        except TelegramError as e:
            error_msg = str(e).lower()
            if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                logger.info(f"User {user_id} has blocked the bot")
                logger.warning(f"User {user_id} has blocked the bot")
                # Optionally disable reminders for this user
                async with self.database._pool.acquire() as conn:
                    await self._disable_reminders(user_id, conn)
            else:
                logger.info(f"Telegram error force sending reminder to User {user_id}: {e}")
                logger.error(f"Telegram error force sending reminder to User {user_id}: {e}")
            return False
        except Exception as e:
            logger.info(f"Error force sending reminder to User {user_id}: {e}")
            logger.error(f"Error force sending reminder to User {user_id}: {e}")
            return False

    async def update_practice_timestamp(self, user_id: int):
        """Update the last practice timestamp for a user."""
        try:
            async with self.database._pool.acquire() as conn:
                # Check if tracking record exists
                check_query = "SELECT id FROM reminder_tracking WHERE user_id = $1"
                exists = await conn.fetchval(check_query, user_id)

                now = datetime.now(timezone.utc)

                if exists:
                    # Update existing record
                    update_query = """
                        UPDATE reminder_tracking
                        SET
                            last_practice_date = $1,
                            updated_at = $2
                        WHERE user_id = $3
                    """
                    await conn.execute(update_query, now, now, user_id)
                else:
                    # Create new tracking record
                    insert_query = """
                        INSERT INTO reminder_tracking (user_id, last_practice_date, created_at, updated_at)
                        VALUES ($1, $2, $3, $4)
                    """
                    await conn.execute(insert_query, user_id, now, now, now)

                logger.debug(f"Updated practice timestamp for user {user_id}")

        except Exception as e:
            logger.error(f"Error updating practice timestamp for {user_id}: {e}")

    async def toggle_reminders(self, user_id: int, enabled: bool) -> bool:
        """Toggle reminders for a user."""
        try:
            async with self.database._pool.acquire() as conn:
                # Ensure tracking record exists
                check_query = "SELECT id FROM reminder_tracking WHERE user_id = $1"
                exists = await conn.fetchval(check_query, user_id)

                now = datetime.now(timezone.utc)

                if exists:
                    update_query = """
                        UPDATE reminder_tracking
                        SET
                            reminders_enabled = $1,
                            updated_at = $2
                        WHERE user_id = $3
                    """
                    await conn.execute(update_query, enabled, now, user_id)
                else:
                    insert_query = """
                        INSERT INTO reminder_tracking (user_id, reminders_enabled, created_at, updated_at)
                        VALUES ($1, $2, $3, $4)
                    """
                    await conn.execute(insert_query, user_id, enabled, now, now)

                logger.info(f"{'Enabled' if enabled else 'Disabled'} reminders for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error toggling reminders for {user_id}: {e}")
            return False

    async def get_reminder_stats(self) -> Dict[str, Any]:
        """Get reminder statistics."""
        try:
            async with self.database._pool.acquire() as conn:
                stats_query = """
                    SELECT
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN reminders_enabled THEN 1 END) as enabled_count,
                        COUNT(CASE WHEN last_reminder_date IS NOT NULL THEN 1 END) as sent_count,
                        AVG(reminder_count) as avg_reminders_per_user
                    FROM reminder_tracking
                """

                row = await conn.fetchrow(stats_query)

                return {
                    "total_tracked_users": row["total_users"],
                    "reminders_enabled": row["enabled_count"],
                    "users_reminded": row["sent_count"],
                    "avg_reminders_per_user": float(row["avg_reminders_per_user"] or 0)
                }

        except Exception as e:
            logger.error(f"Error getting reminder stats: {e}")
            return {}