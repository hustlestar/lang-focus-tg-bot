"""Maintainer handlers for bot maintenance commands."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from lang_focus.core.database import DatabaseManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.core.keyboard_manager import KeyboardManager
from lang_focus.core.reminder_scheduler import ReminderScheduler
from lang_focus.config.settings import BotConfig

logger = logging.getLogger(__name__)


class MaintainerHandlers:
    """Handler for maintainer commands."""

    def __init__(
        self,
        locale_manager: LocaleManager,
        keyboard_manager: KeyboardManager,
        database: DatabaseManager,
        config: BotConfig,
        reminder_scheduler: Optional[ReminderScheduler] = None
    ):
        self.locale_manager = locale_manager
        self.keyboard_manager = keyboard_manager
        self.database = database
        self.config = config
        self.reminder_scheduler = reminder_scheduler

    def is_maintainer(self, user_id: int) -> bool:
        """Check if user is the maintainer."""
        return self.config.maintainer_id and user_id == self.config.maintainer_id

    async def handle_force_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Force send a reminder to a specific user or all users."""
        if not update.effective_user or not update.message:
            return

        user_id = update.effective_user.id

        # Check maintainer permission
        if not self.is_maintainer(user_id):
            await update.message.reply_text("❌ У вас нет прав maintainer.")
            return

        if not self.reminder_scheduler:
            await update.message.reply_text("❌ Система напоминаний не активна.")
            return

        # Parse command arguments
        if context.args and len(context.args) > 0:
            arg = context.args[0].lower()

            if arg == "all":
                # Send to all users
                sent_count = await self.reminder_scheduler.force_send_reminder_to_all()
                await update.message.reply_text(
                    f"✅ Напоминания отправлены {sent_count} пользователям"
                )
            else:
                # Try to parse as user ID
                try:
                    target_user_id = int(context.args[0])
                    success = await self.reminder_scheduler.force_send_reminder(target_user_id)

                    if success:
                        await update.message.reply_text(
                            f"✅ Напоминание отправлено пользователю {target_user_id}"
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Не удалось отправить напоминание пользователю {target_user_id}"
                        )
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверный формат.\n\n"
                        "Использование:\n"
                        "/force_reminder - отправить себе\n"
                        "/force_reminder all - отправить всем\n"
                        "/force_reminder [user_id] - отправить конкретному пользователю"
                    )
        else:
            # No args - send to self
            success = await self.reminder_scheduler.force_send_reminder(user_id)

            if success:
                await update.message.reply_text(
                    f"✅ Напоминание отправлено вам"
                )
            else:
                await update.message.reply_text(
                    f"❌ Не удалось отправить напоминание"
                )

    async def handle_reminder_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show reminder system statistics."""
        if not update.effective_user or not update.message:
            return

        user_id = update.effective_user.id

        # Check maintainer permission
        if not self.is_maintainer(user_id):
            await update.message.reply_text("❌ У вас нет прав maintainer.")
            return

        if not self.reminder_scheduler:
            await update.message.reply_text("❌ Система напоминаний не активна.")
            return

        stats = await self.reminder_scheduler.get_reminder_stats()

        message = "📊 **Статистика напоминаний:**\n\n"
        message += f"👥 Всего пользователей: {stats.get('total_tracked_users', 0)}\n"
        message += f"✅ С включенными напоминаниями: {stats.get('reminders_enabled', 0)}\n"
        message += f"📬 Получили напоминания: {stats.get('users_reminded', 0)}\n"
        message += f"📈 Среднее кол-во напоминаний: {stats.get('avg_reminders_per_user', 0):.1f}\n"

        await update.message.reply_text(message, parse_mode="Markdown")

    async def handle_toggle_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Toggle reminders for a user."""
        if not update.effective_user or not update.message:
            return

        user_id = update.effective_user.id

        if not self.reminder_scheduler:
            await update.message.reply_text("❌ Система напоминаний не активна.")
            return

        # Parse command
        if context.args and len(context.args) > 0:
            action = context.args[0].lower()
            enable = action in ['on', 'включить', 'enable']
            disable = action in ['off', 'выключить', 'disable']

            if not enable and not disable:
                await update.message.reply_text(
                    "Использование: /reminders [on|off]\n"
                    "Например: /reminders off"
                )
                return

            success = await self.reminder_scheduler.toggle_reminders(user_id, enable)

            if success:
                if enable:
                    await update.message.reply_text(
                        "✅ Напоминания включены!\n"
                        "Вы будете получать уведомления каждые 7 дней."
                    )
                else:
                    await update.message.reply_text(
                        "🔕 Напоминания отключены.\n"
                        "Вы больше не будете получать уведомления."
                    )
            else:
                await update.message.reply_text("❌ Не удалось изменить настройки напоминаний.")
        else:
            await update.message.reply_text(
                "Использование: /reminders [on|off]\n"
                "Например: /reminders off"
            )

    async def handle_maintainer_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show maintainer help."""
        if not update.effective_user or not update.message:
            return

        user_id = update.effective_user.id

        if not self.is_maintainer(user_id):
            await update.message.reply_text("❌ У вас нет прав maintainer.")
            return

        help_text = """🔧 **Команды maintainer:**

/force_reminder - Отправить напоминание себе
/force_reminder all - Отправить всем пользователям
/force_reminder [user_id] - Отправить конкретному пользователю
/reminder_stats - Статистика системы напоминаний
/maintainer_help - Это сообщение

**Команды для пользователей:**
/reminders on - Включить напоминания
/reminders off - Отключить напоминания"""

        await update.message.reply_text(help_text, parse_mode="Markdown")