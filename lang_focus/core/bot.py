"""Main bot class for the Telegram bot template."""

import asyncio
import logging
from typing import Optional

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from lang_focus.config.settings import BotConfig
from lang_focus.core.ai_provider import OpenRouterProvider, MockAIProvider
from lang_focus.core.database import DatabaseManager
from lang_focus.core.keyboard_manager import KeyboardManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.handlers.basic import BasicHandlers
from lang_focus.handlers.message import MessageHandler as MessageHandlerClass
from lang_focus.handlers.learning import LearningHandlers
from lang_focus.handlers.unified_handler import UnifiedBotHandler
from lang_focus.handlers.maintainer import MaintainerHandlers
from lang_focus.support.bot import SupportBot
from lang_focus.learning import LearningDataLoader
from lang_focus.utils.helpers import setup_logging
from lang_focus.core.reminder_scheduler import ReminderScheduler

# Set up enhanced logging
setup_logging()
logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram bot class."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.app: Optional[Application] = None
        self.database: Optional[DatabaseManager] = None
        self.locale_manager: Optional[LocaleManager] = None
        self.keyboard_manager: Optional[KeyboardManager] = None
        self.ai_provider: Optional[OpenRouterProvider] = None
        self.support_bot: Optional[SupportBot] = None
        self.reminder_scheduler: Optional[ReminderScheduler] = None

        # Handlers
        self.basic_handlers: Optional[BasicHandlers] = None
        self.message_handler: Optional[MessageHandlerClass] = None
        self.learning_handlers: Optional[LearningHandlers] = None
        self.unified_handler: Optional[UnifiedBotHandler] = None
        self.maintainer_handlers: Optional[MaintainerHandlers] = None

        # Learning components
        self.data_loader: Optional[LearningDataLoader] = None

        logger.info(f"Bot initialized: {config.bot_name} v{config.bot_version}")

    async def setup(self) -> None:
        """Setup all bot components."""
        try:
            # Setup logging
            self.config.setup_logging()

            # Validate configuration
            self.config.validate()

            # Initialize database
            self.database = DatabaseManager(self.config.database_url)
            await self.database.setup()
            logger.info("Database initialized")

            # Initialize locale manager
            self.locale_manager = LocaleManager(default_language=self.config.default_language)
            logger.info("Locale manager initialized")

            # Initialize keyboard manager
            self.keyboard_manager = KeyboardManager(self.locale_manager)
            logger.info("Keyboard manager initialized")

            # Initialize AI provider if configured
            if self.config.has_ai_support:
                self.ai_provider = OpenRouterProvider(api_key=self.config.openrouter_api_key, model=self.config.openrouter_model)

                # Test AI connection
                if await self.ai_provider.test_connection():
                    logger.info(f"AI provider initialized: {self.config.openrouter_model}")
                else:
                    logger.warning("AI provider connection test failed, using mock provider")
                    self.ai_provider = MockAIProvider()
            else:
                logger.info("AI support not configured")

            # Initialize support bot if configured
            if self.config.has_support_bot:
                self.support_bot = SupportBot(
                    support_token=self.config.support_bot_token,
                    support_chat_id=self.config.support_chat_id,
                    locale_manager=self.locale_manager,
                )
                await self.support_bot.setup()
                logger.info("Support bot initialized")

            # Initialize learning data loader and load initial data
            self.data_loader = LearningDataLoader(self.config.database_url)
            await self.data_loader.load_all_data()
            logger.info("Learning data loaded")

            # Initialize handlers
            self.basic_handlers = BasicHandlers(
                locale_manager=self.locale_manager, keyboard_manager=self.keyboard_manager, database=self.database, config=self.config
            )

            self.message_handler = MessageHandlerClass(
                locale_manager=self.locale_manager,
                keyboard_manager=self.keyboard_manager,
                database=self.database,
                ai_provider=self.ai_provider,
                config=self.config,
            )

            # Initialize learning handlers if AI is available
            if self.ai_provider:
                self.learning_handlers = LearningHandlers(
                    locale_manager=self.locale_manager,
                    keyboard_manager=self.keyboard_manager,
                    database=self.database,
                    ai_provider=self.ai_provider,
                    config=self.config,
                    reminder_scheduler=None  # Will be set after app is created
                )
                logger.info("Learning handlers initialized")

            # Initialize unified handler
            self.unified_handler = UnifiedBotHandler(
                locale_manager=self.locale_manager,
                keyboard_manager=self.keyboard_manager,
                database=self.database,
                ai_provider=self.ai_provider,
                config=self.config,
            )

            # Set handlers for unified handler
            self.unified_handler.set_handlers(self.basic_handlers, self.learning_handlers)
            logger.info("Unified handler initialized")

            # Create Telegram application
            self.app = Application.builder().token(self.config.bot_token).build()
            self.unified_handler.enable_subscription_manager(self.app.bot)

            # Initialize reminder scheduler
            self.reminder_scheduler = ReminderScheduler(
                database=self.database,
                bot=self.app.bot,
                locale_manager=self.locale_manager
            )
            logger.info("Reminder scheduler initialized")

            # Update learning handlers with reminder scheduler
            if self.learning_handlers:
                self.learning_handlers.reminder_scheduler = self.reminder_scheduler

            # Update unified handler with reminder scheduler
            if self.unified_handler:
                self.unified_handler.set_reminder_scheduler(self.reminder_scheduler)

            # Initialize maintainer handlers
            self.maintainer_handlers = MaintainerHandlers(
                locale_manager=self.locale_manager,
                keyboard_manager=self.keyboard_manager,
                database=self.database,
                config=self.config,
                reminder_scheduler=self.reminder_scheduler
            )
            logger.info("Maintainer handlers initialized")

            # Add handlers to application
            self._add_handlers()

            logger.info("Bot setup completed successfully")

        except Exception as e:
            logger.error(f"Bot setup failed: {e}")
            raise

    def _add_handlers(self) -> None:
        """Add all handlers to the application."""
        if not self.app:
            raise RuntimeError("Application not initialized")

        # Command handlers - route through unified handler
        self.app.add_handler(CommandHandler("start", self.unified_handler.handle_start_command))
        self.app.add_handler(CommandHandler("help", lambda u, c: self.unified_handler.handle_command(u, c, "help")))
        self.app.add_handler(CommandHandler("about", lambda u, c: self.unified_handler.handle_command(u, c, "about")))

        # Learning command handlers (if learning handlers are available)
        if self.learning_handlers:
            self.app.add_handler(CommandHandler("learn", lambda u, c: self.unified_handler.handle_command(u, c, "learn")))
            self.app.add_handler(CommandHandler("continue", lambda u, c: self.unified_handler.handle_command(u, c, "continue")))
            self.app.add_handler(CommandHandler("progress", lambda u, c: self.unified_handler.handle_command(u, c, "progress")))
            self.app.add_handler(CommandHandler("tricks", lambda u, c: self.unified_handler.handle_command(u, c, "tricks")))
            self.app.add_handler(CommandHandler("stats", lambda u, c: self.unified_handler.handle_command(u, c, "stats")))

        # Maintainer commands
        self.app.add_handler(CommandHandler("force_reminder", self.maintainer_handlers.handle_force_reminder))
        self.app.add_handler(CommandHandler("reminder_stats", self.maintainer_handlers.handle_reminder_stats))
        self.app.add_handler(CommandHandler("reminders", self.maintainer_handlers.handle_toggle_reminders))
        self.app.add_handler(CommandHandler("maintainer_help", self.maintainer_handlers.handle_maintainer_help))

        # Unified callback query handler
        self.app.add_handler(CallbackQueryHandler(self.unified_handler.handle_callback))

        # Message handlers - prioritize learning responses if in session
        if self.learning_handlers:
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.learning_handlers.handle_learning_response))
        else:
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler.handle_text_message))

        self.app.add_handler(MessageHandler(filters.PHOTO, self.message_handler.handle_photo))

        self.app.add_handler(MessageHandler(filters.Document.ALL, self.message_handler.handle_document))

        self.app.add_handler(MessageHandler(filters.VOICE, self.message_handler.handle_voice))

        self.app.add_handler(MessageHandler(filters.Sticker.ALL, self.message_handler.handle_sticker))

        self.app.add_handler(MessageHandler(filters.LOCATION, self.message_handler.handle_location))

        self.app.add_handler(MessageHandler(filters.CONTACT, self.message_handler.handle_contact))

        logger.info("All handlers added to application")

    async def start(self) -> None:
        """Start the bot."""
        if not self.app:
            await self.setup()

        try:
            # Initialize and start main bot
            await self.app.initialize()
            await self.app.start()

            # Start support bot if configured
            if self.support_bot:
                await self.support_bot.start()

            # Start reminder scheduler
            if self.reminder_scheduler:
                await self.reminder_scheduler.start()
                logger.info("Reminder scheduler started")

            # Send startup notification
            await self._send_startup_notification()

            # Start polling
            await self.app.updater.start_polling(drop_pending_updates=False, allowed_updates=None)

            logger.info(f"{self.config.bot_name} is now running...")

        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

    async def stop(self) -> None:
        """Stop the bot."""
        try:
            # Send shutdown notification
            await self._send_shutdown_notification()

            # Stop main bot
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()

            # Stop reminder scheduler
            if self.reminder_scheduler:
                await self.reminder_scheduler.stop()

            # Stop support bot
            if self.support_bot:
                await self.support_bot.stop()

            # Close database
            if self.database:
                await self.database.close()

            logger.info("Bot stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

    async def run(self) -> None:
        """Run the bot (blocking)."""
        try:
            await self.start()

            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Bot runtime error: {e}")
        finally:
            await self.stop()

    async def _send_startup_notification(self) -> None:
        """Send startup notification to support and maintainer."""
        message = f"🚀 **{self.config.bot_name}** запущен успешно!\n\n"
        message += f"Версия: {self.config.bot_version}\n"
        message += f"AI поддержка: {'✅' if self.config.has_ai_support else '❌'}\n"
        message += f"Support Bot: {'✅' if self.config.has_support_bot else '❌'}\n"
        message += f"Система напоминаний: ✅\n\n"

        # Get database stats
        if self.database:
            try:
                stats = await self.database.get_stats()
                message += f"📊 Статистика:\n"
                message += f"Всего пользователей: {stats.get('total_users', 0)}\n"
                message += f"Активных пользователей: {stats.get('active_users', 0)}\n"
            except Exception as e:
                logger.error(f"Error getting stats for startup notification: {e}")

        # Send to support bot if configured
        if self.support_bot:
            await self.support_bot.send_notification(message)

        # Send to maintainer if configured
        if self.config.maintainer_id and self.app and self.app.bot:
            try:
                await self.app.bot.send_message(
                    chat_id=self.config.maintainer_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent startup notification to maintainer {self.config.maintainer_id}")
            except Exception as e:
                error_msg = str(e).lower()
                if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                    logger.warning(f"Maintainer {self.config.maintainer_id} has blocked the bot or is deactivated")
                else:
                    logger.error(f"Failed to send startup notification to maintainer: {e}")

    async def _send_shutdown_notification(self) -> None:
        """Send shutdown notification to support and maintainer."""
        message = f"🛑 **{self.config.bot_name}** остановлен.\n"

        # Get final stats if available
        if self.reminder_scheduler:
            try:
                reminder_stats = await self.reminder_scheduler.get_reminder_stats()
                message += f"\n📊 Статистика напоминаний:\n"
                message += f"Отслеживаемых: {reminder_stats.get('total_tracked_users', 0)}\n"
                message += f"С включенными: {reminder_stats.get('reminders_enabled', 0)}\n"
            except Exception as e:
                logger.error(f"Error getting reminder stats for shutdown: {e}")

        # Send to support bot if configured
        if self.support_bot:
            await self.support_bot.send_notification(message)

        # Send to maintainer if configured
        if self.config.maintainer_id and self.app and self.app.bot:
            try:
                await self.app.bot.send_message(
                    chat_id=self.config.maintainer_id,
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent shutdown notification to maintainer {self.config.maintainer_id}")
            except Exception as e:
                error_msg = str(e).lower()
                if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                    logger.warning(f"Maintainer {self.config.maintainer_id} has blocked the bot or is deactivated")
                else:
                    logger.error(f"Failed to send shutdown notification to maintainer: {e}")

    async def get_stats(self) -> dict:
        """Get bot statistics."""
        stats = {
            "bot_name": self.config.bot_name,
            "bot_version": self.config.bot_version,
            "ai_support": self.config.has_ai_support,
            "support_bot": self.config.has_support_bot,
        }

        if self.database:
            db_stats = await self.database.get_stats()
            stats.update(db_stats)

        if self.ai_provider:
            ai_info = self.ai_provider.get_model_info()
            stats["ai_provider"] = ai_info

        return stats

    async def send_stats_to_support(self) -> bool:
        """Send bot statistics to support."""
        if not self.support_bot:
            return False

        try:
            stats = await self.get_stats()
            return await self.support_bot.send_stats(stats)
        except Exception as e:
            logger.error(f"Error sending stats to support: {e}")
            return False

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self.app is not None and self.app.running

    def get_config(self) -> BotConfig:
        """Get bot configuration."""
        return self.config

    async def reload_locales(self) -> None:
        """Reload locale files."""
        if self.locale_manager:
            self.locale_manager.reload_locales()
            logger.info("Locales reloaded")

    async def clear_keyboard_cache(self) -> None:
        """Clear keyboard cache."""
        if self.keyboard_manager:
            self.keyboard_manager.clear_cache()
            logger.info("Keyboard cache cleared")
