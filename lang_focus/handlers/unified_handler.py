"""Unified handler for both commands and callbacks.

This module provides a unified system for handling both Telegram bot commands
and callback queries, ensuring consistent behavior regardless of input method.
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from lang_focus.config.settings import BotConfig
from lang_focus.core.ai_provider import OpenRouterProvider
from lang_focus.core.database import DatabaseManager
from lang_focus.core.keyboard_manager import KeyboardManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.core.models import BotAction, ActionContext
from lang_focus.core.subscription_manager import SubscriptionManager
from lang_focus.handlers.action_registry import ActionRegistry

logger = logging.getLogger(__name__)


class UnifiedBotHandler:
    """Unified handler for both commands and callbacks."""

    def __init__(
            self,
            locale_manager: LocaleManager,
            keyboard_manager: KeyboardManager,
            database: DatabaseManager,
            ai_provider: Optional[OpenRouterProvider],
            config: BotConfig,
    ):
        self.locale_manager = locale_manager
        self.keyboard_manager = keyboard_manager
        self.database = database
        self.ai_provider = ai_provider
        self.config = config

        self.action_registry = ActionRegistry()

        # Initialize subscription manager
        self.subscription_manager = None
        # Initialize handlers (will be set by bot setup)
        self.basic_handlers = None
        self.learning_handlers = None

        logger.info("Unified bot handler initialized")

    def enable_subscription_manager(self, bot):
        self.subscription_manager = SubscriptionManager(bot, self.config, self.database, self.locale_manager)

    def set_handlers(self, basic_handlers, learning_handlers=None):
        """Set the basic and learning handlers."""
        self.basic_handlers = basic_handlers
        self.learning_handlers = learning_handlers

        # Set action handlers
        self._setup_action_handlers()

    def _setup_action_handlers(self):
        """Setup handlers for all actions."""
        # Basic action handlers
        if self.basic_handlers:
            self.action_registry.set_handler("help", self._handle_help_action)
            self.action_registry.set_handler("about", self._handle_about_action)
            self.action_registry.set_handler("settings", self._handle_settings_action)

        # Learning action handlers
        if self.learning_handlers:
            self.action_registry.set_handler("learn", self._handle_learn_action)
            self.action_registry.set_handler("continue", self._handle_continue_action)
            self.action_registry.set_handler("progress", self._handle_progress_action)
            self.action_registry.set_handler("tricks", self._handle_tricks_action)
            self.action_registry.set_handler("stats", self._handle_stats_action)

    async def handle_subscription(self, update: Update):
        user = update.effective_user

        if not user:
            return True

        # Ensure user exists in database
        user_data = await self.database.ensure_user(user_id=user.id, username=user.username, language=self.config.default_language)
        user_language = user_data.get("language", self.config.default_language)
        # Check subscription if required
        if self.subscription_manager and self.config.subscription_required:
            is_subscribed = await self.subscription_manager.is_subscribed(user.id)

            if not is_subscribed:
                # Show subscription required message
                subscription_text = self.locale_manager.get("subscription_required", user_language)
                keyboard = self.subscription_manager.get_subscription_keyboard(user_language)
                await update.message.reply_text(subscription_text, reply_markup=keyboard, parse_mode="Markdown")
                logger.info(f"User {user.id} (@{user.username}) needs to subscribe")
                return True

        return False

    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with enhanced main menu."""
        user = update.effective_user

        if not user:
            return

        try:
            # Ensure user exists in database
            user_data = await self.database.ensure_user(user_id=user.id, username=user.username, language=self.config.default_language)

            user_language = user_data.get("language", self.config.default_language)

            if await self.handle_subscription(update):
                return
            # Check if user is first-time or returning
            is_first_time = await self._is_first_time_user(user.id)

            if is_first_time:
                # First-time user welcome
                welcome_text = self.locale_manager.get("first_time", user_language)
            else:
                # Returning user welcome with progress
                welcome_text = await self._get_returning_user_welcome(user.id, user_language)

            # Get user context for keyboard
            action_context = await self.extract_context(update, is_callback=False)
            user_context = {"has_active_session": action_context.has_active_session}

            # Get main menu keyboard with context
            keyboard = self.keyboard_manager.get_main_menu_keyboard(user_language, user_context)

            await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

            logger.info(f"User {user.id} (@{user.username}) started the bot")

        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("Sorry, something went wrong. Please try again.")

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action_name: str):
        """Handle both commands and callbacks uniformly."""
        try:
            if await self.handle_subscription(update):
                return
            action_context = await self.extract_context(update, is_callback=False)
            action = self.action_registry.get_action(action_name)

            if action and action.handler:
                return await self.execute_action(action, update, action_context)
            else:
                logger.warning(f"No handler found for action: {action_name}")
                return await self.handle_unknown_action(update, action_context)

        except Exception as e:
            logger.error(f"Error handling command {action_name}: {e}")
            await self._send_error_message(update, action_name)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route callbacks to appropriate actions."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        try:
            action_name = self.extract_action_from_callback(query.data)
            action_context = await self.extract_context(update, is_callback=True)
            action_context.callback_query = query

            action = self.action_registry.get_action(action_name)

            if action and action.handler:
                return await self.execute_action(action, update, action_context)
            else:
                # Handle special callback data that doesn't map to actions
                if query.data == "get_recommendations":
                    await self._handle_recommendations_callback(query, action_context)
                elif query.data == "trick_details":
                    await self._handle_trick_details_callback(query, action_context)
                elif query.data == "end_session":
                    await self._handle_end_session_callback(query, action_context)
                elif query.data.startswith("hint_"):
                    trick_id = int(query.data.split("_")[1])
                    await self._handle_hint_callback(query, action_context, trick_id)
                elif query.data.startswith("skip_"):
                    await self._handle_skip_callback(update, action_context) # Pass the main update object
                # Learning action handlers
                elif query.data.startswith("retry_trick"):
                    await self._handle_retry_trick_callback(update, action_context)
                elif query.data.startswith("next_trick"):
                    await self._handle_next_trick_callback(update, action_context)
                # Subscription handlers
                elif query.data == "check_subscription":
                    await self._handle_subscription_check_callback(query, action_context)
                # Navigation handlers
                elif query.data == "back_to_main":
                    await self._handle_back_to_main(query, action_context)
                elif query.data == "back_to_challenge":
                    await self._handle_back_to_challenge(query, action_context)
                else:
                    # Try to handle with existing basic handlers for backward compatibility
                    return await self._handle_legacy_callback(update, context)

        except Exception as e:
            logger.error(f"Error handling callback {query.data}: {e}")
            await query.answer("❌ An error occurred. Please try again.")

    async def extract_context(self, update: Update, is_callback: bool = False) -> ActionContext:
        """Extract context from either command or callback."""
        user = update.effective_user
        if not user:
            raise ValueError("No user found in update")

        # Check for active learning session
        has_active_session = False
        if self.learning_handlers:
            try:
                session = await self.learning_handlers.session_manager.resume_session(user.id)
                has_active_session = session is not None
            except Exception as e:
                logger.warning(f"Error checking session for user {user.id}: {e}")

        # Get user language
        try:
            user_language = await self.database.get_user_language(user.id)
        except Exception as e:
            logger.warning(f"Error getting user language for {user.id}: {e}")
            user_language = self.config.default_language

        return ActionContext(
            user_id=user.id,
            username=user.username,
            language=user_language,
            is_callback=is_callback,
            has_active_session=has_active_session,
            message_id=update.effective_message.message_id if update.effective_message else None,
            chat_id=update.effective_chat.id if update.effective_chat else None,
        )

    async def _check_subscription(self, user_id: int, language: str) -> bool:
        """Check if user has valid subscription."""
        if not self.subscription_manager or not self.config.subscription_required:
            return True

        return await self.subscription_manager.is_subscribed(user_id)

    async def execute_action(self, action: BotAction, update: Update, context: ActionContext):
        """Execute an action with proper context."""
        # Check subscription first (except for basic actions like help/about)
        if action.category == "learning" and not await self._check_subscription(context.user_id, context.language):
            return await self._handle_subscription_required(update, context)

        # Check if action requires session and user has one
        if action.requires_session and not context.has_active_session:
            return await self.handle_session_required(update, context, action)

        # Execute the action
        logger.info(f"Executing action '{action.name}' for user {context.user_id}")
        return await action.handler(update, context)

    def extract_action_from_callback(self, callback_data: str) -> str:
        """Extract action name from callback data."""
        if callback_data.startswith("cmd_"):
            return callback_data[4:]  # Remove "cmd_" prefix
        return callback_data

    async def handle_session_required(self, update: Update, context: ActionContext, action: BotAction):
        """Handle case when action requires session but user doesn't have one."""
        message = self.locale_manager.get("session_required", context.language)

        # Create keyboard with "Start Learning" button
        keyboard = [[InlineKeyboardButton(f"📚 {self.locale_manager.get('learn_button', context.language)}", callback_data="cmd_learn")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if context.is_callback:
            await context.callback_query.edit_message_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, reply_markup=reply_markup)

    async def _handle_subscription_required(self, update: Update, context: ActionContext):
        """Handle case when subscription is required but user is not subscribed."""
        if not self.subscription_manager:
            return

        message = self.locale_manager.get("subscription_required", context.language)
        keyboard = self.subscription_manager.get_subscription_keyboard(context.language)

        if context.is_callback:
            await context.callback_query.edit_message_text(message, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode="Markdown")

    async def handle_unknown_action(self, update: Update, context: ActionContext):
        """Handle unknown action."""
        message = self.locale_manager.get("unknown_command", context.language)

        if context.is_callback:
            await context.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)

    async def _handle_legacy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callbacks with legacy basic handlers."""
        if self.basic_handlers:
            return await self.basic_handlers.callback_query_handler(update, context)

    async def _send_response(self, update: Update, context: ActionContext,
                             text: str, reply_markup=None, parse_mode=None):
        """Unified method to send response via command or callback."""
        try:
            if context.is_callback:
                await context.callback_query.edit_message_text(
                    text, reply_markup=reply_markup, parse_mode=parse_mode
                )
            else:
                await update.message.reply_text(
                    text, reply_markup=reply_markup, parse_mode=parse_mode
                )
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            # Fallback error message
            error_text = "❌ An error occurred. Please try again."
            if context.is_callback:
                await context.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)

    async def _send_error_message(self, update: Update, action_name: str):
        """Send error message to user."""
        try:
            user = update.effective_user
            if user:
                user_language = await self.database.get_user_language(user.id)
            else:
                user_language = self.config.default_language

            message = self.locale_manager.get("error_occurred", user_language)

            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)

        except Exception as e:
            logger.error(f"Error sending error message: {e}")

    # Action handler methods
    async def _handle_help_action(self, update: Update, context: ActionContext):
        """Handle help action."""
        if context.is_callback:
            # Create a new update object for the basic handler
            return await self.basic_handlers._show_help(context.callback_query, context.language)
        else:
            return await self.basic_handlers.help_command(update, None)

    async def _handle_about_action(self, update: Update, context: ActionContext):
        """Handle about action."""
        if context.is_callback:
            return await self.basic_handlers._show_about(context.callback_query, context.language)
        else:
            return await self.basic_handlers.about_command(update, None)

    async def _handle_settings_action(self, update: Update, context: ActionContext):
        """Handle settings action."""
        if context.is_callback:
            return await self.basic_handlers._show_settings(context.callback_query, context.language)
        else:
            # Settings doesn't have a command, show via callback method
            settings_text = "⚙️ Settings"
            keyboard = self.keyboard_manager.get_settings_keyboard(context.language)
            await update.message.reply_text(settings_text, reply_markup=keyboard)

    async def _handle_learn_action(self, update: Update, context: ActionContext):
        """Handle learn action."""
        if context.is_callback:
            # For callbacks, we need to create a mock update with message-like interface
            return await self._handle_learning_callback(update, context, "learn")
        else:
            return await self.learning_handlers.learn_command(update, None)

    async def _handle_continue_action(self, update: Update, context: ActionContext):
        """Handle continue action."""
        if context.is_callback:
            return await self._handle_learning_callback(update, context, "continue")
        else:
            return await self.learning_handlers.continue_command(update, None)

    async def _handle_progress_action(self, update: Update, context: ActionContext):
        """Handle progress action."""
        if context.is_callback:
            return await self._handle_learning_callback(update, context, "progress")
        else:
            return await self.learning_handlers.progress_command(update, None)

    async def _handle_tricks_action(self, update: Update, context: ActionContext):
        """Handle tricks action."""
        if context.is_callback:
            return await self._handle_learning_callback(update, context, "tricks")
        else:
            return await self.learning_handlers.tricks_command(update, None)

    async def _handle_stats_action(self, update: Update, context: ActionContext):
        """Handle stats action."""
        if context.is_callback:
            return await self._handle_learning_callback(update, context, "stats")
        else:
            return await self.learning_handlers.stats_command(update, None)

    async def _handle_learning_callback(self, update: Update, context: ActionContext, action_type: str):
        """Handle learning actions triggered by callbacks."""
        query = context.callback_query

        try:
            if action_type == "learn":
                # Start new learning session
                session = await self.learning_handlers.session_manager.start_session(context.user_id)
                challenge = await self.learning_handlers.session_manager.get_next_challenge(session)

                if challenge:
                    await self.learning_handlers._present_challenge_callback(query, challenge, session)
                else:
                    await query.edit_message_text("❌ Не удалось создать учебную сессию. Попробуйте позже.")

            elif action_type == "continue":
                # Continue existing session
                session = await self.learning_handlers.session_manager.resume_session(context.user_id)

                if not session:
                    await query.edit_message_text("📚 У вас нет активной сессии. Начните новую.")
                    return

                challenge = await self.learning_handlers.session_manager.get_next_challenge(session)

                if challenge:
                    await self.learning_handlers._present_challenge_callback(query, challenge, session)
                else:
                    summary = await self.learning_handlers.session_manager.complete_session(session)
                    await self.learning_handlers._present_session_summary_callback(query, summary)

            elif action_type == "progress":
                # Show progress
                await self._show_progress_callback(query, context)

            elif action_type == "tricks":
                # Show all tricks
                await self._show_tricks_callback(query, context)

            elif action_type == "stats":
                # Show statistics
                await self._show_stats_callback(query, context)

        except Exception as e:
            logger.error(f"Error in learning callback {action_type}: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

    async def _show_progress_callback(self, query, context: ActionContext):
        """Show progress via callback."""
        try:
            # Get overall progress
            overall_progress = await self.learning_handlers.progress_tracker.calculate_overall_progress(context.user_id)

            # Get individual trick progress
            user_progress = await self.learning_handlers.progress_tracker.get_user_progress(context.user_id)

            # Format progress message
            message = f"📊 **Ваш прогресс в изучении языковых фокусов**\n\n"
            message += f"🎯 Общий прогресс: {overall_progress.completion_percentage:.1f}%\n"
            message += f"🏆 Освоено фокусов: {overall_progress.mastered_tricks}/14\n"
            message += f"📈 Средний уровень мастерства: {overall_progress.average_mastery:.1f}%\n"
            message += f"✅ Общая точность: {overall_progress.overall_success_rate:.1f}%\n"
            message += f"🔥 Серия обучения: {overall_progress.learning_streak} дней\n\n"

            if user_progress:
                message += "**Прогресс по фокусам:**\n"
                for progress in user_progress:
                    trick = await self.learning_handlers.trick_engine.get_trick_by_id(progress.trick_id)
                    status_emoji = "🏆" if progress.is_mastered else "📚"
                    message += f"{status_emoji} {trick.name}: {progress.mastery_level}% "
                    message += f"({progress.correct_attempts}/{progress.total_attempts})\n"

            # Add keyboard for actions with back button
            keyboard = [
                [InlineKeyboardButton("📚 Продолжить обучение", callback_data="cmd_learn")],
                [InlineKeyboardButton("🎯 Рекомендации", callback_data="get_recommendations")],
                [InlineKeyboardButton("📈 Статистика", callback_data="cmd_stats")],
                [InlineKeyboardButton(self.locale_manager.get("back_to_main", context.language), callback_data="back_to_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing progress: {e}")
            await query.edit_message_text("❌ Ошибка при получении прогресса.")

    async def _show_tricks_callback(self, query, context: ActionContext):
        """Show all tricks via callback."""
        try:
            tricks_summary = await self.learning_handlers.trick_engine.get_all_tricks_summary()

            message = "🎭 **14 языковых фокусов (фокусы языка)**\n\n"
            message += "Техники вербального рефрейминга для изменения восприятия:\n\n"

            for trick in tricks_summary:
                message += f"**{trick['id']}. {trick['name']}**\n"
                message += f"{trick['definition']}\n"
                message += f"Примеров: {trick['example_count']}\n\n"

            # Add keyboard for learning with back button
            keyboard = [
                [InlineKeyboardButton("🚀 Начать изучение", callback_data="cmd_learn")],
                [InlineKeyboardButton("📖 Подробнее о фокусе", callback_data="trick_details")],
                [InlineKeyboardButton(self.locale_manager.get("back_to_main", context.language), callback_data="back_to_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing tricks: {e}")
            await query.edit_message_text("❌ Ошибка при получении списка фокусов.")

    async def _show_stats_callback(self, query, context: ActionContext):
        """Show statistics via callback."""
        try:
            # Get learning statistics
            stats = await self.learning_handlers.progress_tracker.get_learning_statistics(context.user_id, days=30)

            message = f"📊 **Статистика за последние 30 дней**\n\n"
            message += f"📅 Активных дней: {stats['active_days']}/30\n"
            message += f"🎯 Всего сессий: {stats['total_sessions']}\n"
            message += f"⏱ Среднее время сессии: {stats['avg_session_minutes']:.1f} мин\n"
            message += f"💬 Всего ответов: {stats['total_responses']}\n"
            message += f"✅ Правильных ответов: {stats['correct_responses']}\n"
            message += f"📈 Процент успеха: {stats['success_rate']:.1f}%\n"
            message += f"🎯 Средний балл: {stats['avg_similarity']:.1f}/100\n\n"

            if stats["trick_performance"]:
                message += "**Производительность по фокусам:**\n"
                for perf in stats["trick_performance"][:5]:  # Top 5
                    message += f"• {perf['trick_name']}: {perf['success_rate']:.1f}% "
                    message += f"({perf['correct']}/{perf['attempts']})\n"

            # Add back button
            keyboard = [[InlineKeyboardButton(self.locale_manager.get("back_to_main", context.language), callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await query.edit_message_text("❌ Ошибка при получении статистики.")

    async def _handle_recommendations_callback(self, query, context: ActionContext):
        """Handle recommendations callback."""
        try:
            # Get user progress to provide personalized recommendations
            user_progress = await self.learning_handlers.progress_tracker.get_user_progress(context.user_id)

            message = "🎯 **Персональные рекомендации**\n\n"

            if not user_progress:
                message += "📚 Начните с изучения основных фокусов языка:\n"
                message += "• Фокус 1: Намерение\n"
                message += "• Фокус 2: Переопределение\n"
                message += "• Фокус 3: Последствия\n\n"
                message += "Рекомендуем начать с команды /learn"
            else:
                # Find tricks that need improvement
                weak_tricks = [p for p in user_progress if p.mastery_level < 50]
                strong_tricks = [p for p in user_progress if p.mastery_level >= 80]

                if weak_tricks:
                    message += "📈 **Фокусы для улучшения:**\n"
                    for progress in weak_tricks[:3]:
                        trick = await self.learning_handlers.trick_engine.get_trick_by_id(progress.trick_id)
                        message += f"• {trick.name} ({progress.mastery_level}%)\n"
                    message += "\n"

                if strong_tricks:
                    message += "🏆 **Хорошо освоенные фокусы:**\n"
                    for progress in strong_tricks[:3]:
                        trick = await self.learning_handlers.trick_engine.get_trick_by_id(progress.trick_id)
                        message += f"• {trick.name} ({progress.mastery_level}%)\n"
                    message += "\n"

                message += "💡 **Рекомендации:**\n"
                if len(weak_tricks) > len(strong_tricks):
                    message += "• Сосредоточьтесь на слабых фокусах\n"
                    message += "• Практикуйте по 10-15 минут в день\n"
                else:
                    message += "• Изучите новые фокусы\n"
                    message += "• Повторите сложные примеры\n"

            keyboard = [
                [InlineKeyboardButton("📚 Начать обучение", callback_data="cmd_learn")],
                [InlineKeyboardButton(self.locale_manager.get("back_to_progress", context.language), callback_data="cmd_progress")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing recommendations: {e}")
            await query.edit_message_text("❌ Ошибка при получении рекомендаций.")

    async def _handle_trick_details_callback(self, query, context: ActionContext):
        """Handle trick details callback."""
        try:
            message = "📖 **Подробнее о фокусах языка**\n\n"
            message += "Фокусы языка - это техники вербального рефрейминга, которые помогают изменить восприятие ситуации.\n\n"
            message += "**Основные категории:**\n"
            message += "• 🎯 Фокусы намерения (1-3)\n"
            message += "• 🔄 Фокусы переопределения (4-6)\n"
            message += "• 📊 Фокусы обобщения (7-9)\n"
            message += "• 🎭 Фокусы реальности (10-12)\n"
            message += "• 🧠 Мета-фокусы (13-14)\n\n"
            message += "Каждый фокус имеет свои ключевые слова и примеры применения."

            keyboard = [
                [InlineKeyboardButton("🎭 Все фокусы", callback_data="cmd_tricks")],
                [InlineKeyboardButton("📚 Начать изучение", callback_data="cmd_learn")],
                [InlineKeyboardButton(self.locale_manager.get("back_to_tricks", context.language), callback_data="cmd_tricks")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing trick details: {e}")
            await query.edit_message_text("❌ Ошибка при получении информации.")

    async def _handle_end_session_callback(self, query, context: ActionContext):
        """Handle end session callback."""
        try:
            session = await self.learning_handlers.session_manager.resume_session(context.user_id)
            if session:
                # Ensure session has valid current_trick_index
                if session.current_trick_index is None:
                    session.current_trick_index = 0

                summary = await self.learning_handlers.session_manager.complete_session(session)
                await self.learning_handlers._present_session_summary_callback(query, summary)
            else:
                # Add back button when no session
                keyboard = [[InlineKeyboardButton(self.locale_manager.get("back_to_main", context.language), callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("📚 У вас нет активной сессии для завершения.", reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            # Add back button on error
            keyboard = [[InlineKeyboardButton(self.locale_manager.get("back_to_main", context.language), callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Ошибка при завершении сессии.", reply_markup=reply_markup)

    async def _handle_hint_callback(self, query, context: ActionContext, trick_id: int):
        """Handle hint callback."""
        try:
            trick = await self.learning_handlers.trick_engine.get_trick_by_id(trick_id)
            examples = await self.learning_handlers.trick_engine.get_random_examples(trick_id, count=1)

            message = f'💡 **Подсказка для фокуса "{trick.name}":**\n\n'
            message += f"🔑 **Ключевые слова:** {', '.join(trick.keywords[:3])}\n\n"

            if examples:
                message += f"📝 **Пример:** {examples[0]}\n\n"

            message += "Попробуйте использовать эти подходы в своем ответе!"

            keyboard = [
                [InlineKeyboardButton("🔙 Назад к заданию", callback_data="back_to_challenge")],
                [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{trick_id}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing hint: {e}")
            await query.edit_message_text("❌ Ошибка при получении подсказки.")

    async def _handle_skip_callback(self, update: Update, context: ActionContext): # Changed signature
        """Handle skip callback by calling the refactored LearningHandlers._skip_trick."""
        if not self.learning_handlers:
            await update.callback_query.edit_message_text("❌ Learning handlers not available.")
            return

        try:
            # Extract trick_id from callback_data (e.g., "skip_123")
            trick_id_to_skip = int(update.callback_query.data.split("_")[1])
            # Call the refactored method in LearningHandlers
            # The context object in _skip_trick (ContextTypes.DEFAULT_TYPE) is not used,
            # so passing ActionContext should be fine.
            # _skip_trick in LearningHandlers will now send new messages for challenge/summary,
            # and edit message on error using update.callback_query.
            await self.learning_handlers._skip_trick(update, context, trick_id_to_skip)
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing trick_id from skip callback_data '{update.callback_query.data}': {e}")
            await update.callback_query.edit_message_text("❌ Ошибка: неверный формат данных для пропуска.")
        except Exception as e:
            logger.error(f"Error in _handle_skip_callback: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при пропуске фокуса.")

    def get_action_registry(self) -> ActionRegistry:
        """Get the action registry."""
        return self.action_registry

    async def _handle_back_to_main(self, query, context: ActionContext):
        """Handle back to main menu navigation."""
        try:
            # Get user context for keyboard
            user_context = {"has_active_session": context.has_active_session}

            user_data = await self.database.get_user(user_id=query.from_user.id)
            # Get welcome message
            welcome_text = await self._get_returning_user_welcome(query.from_user.id, user_data.get('language', self.config.default_language))

            # Get main menu keyboard with context
            keyboard = self.keyboard_manager.get_main_menu_keyboard(context.language, user_context)

            await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error navigating back to main: {e}")
            await query.edit_message_text("❌ Ошибка навигации.")

    async def _handle_back_to_challenge(self, query, context: ActionContext):
        """Handle back to challenge navigation."""
        try:
            session = await self.learning_handlers.session_manager.resume_session(context.user_id)
            if session:
                challenge = await self.learning_handlers.session_manager.get_next_challenge(session)
                if challenge:
                    await self.learning_handlers._present_challenge_callback(query, challenge, session)
                else:
                    await query.edit_message_text("📚 Нет активного задания.")
            else:
                await query.edit_message_text("📚 У вас нет активной сессии.")

        except Exception as e:
            logger.error(f"Error navigating back to challenge: {e}")
            await query.edit_message_text("❌ Ошибка навигации.")

    async def _is_first_time_user(self, user_id: int) -> bool:
        """Check if user is using the bot for the first time."""
        try:
            if not self.learning_handlers:
                return True

            # Check if user has any learning sessions
            session_history = await self.learning_handlers.session_manager.get_session_history(user_id, limit=1)
            return len(session_history) == 0

        except Exception as e:
            logger.warning(f"Error checking first-time user status for {user_id}: {e}")
            return True  # Default to first-time if we can't determine

    async def _get_returning_user_welcome(self, user_id: int, language: str) -> str:
        """Get welcome message for returning users with progress data."""
        try:
            if not self.learning_handlers:
                return self.locale_manager.get("first_time", language)

            # Get user progress
            overall_progress = await self.learning_handlers.progress_tracker.calculate_overall_progress(user_id)

            # Get last session info
            session_history = await self.learning_handlers.session_manager.get_session_history(user_id, limit=1)
            last_session = "никогда"  # "never" in Russian

            if session_history:
                last_session_data = session_history[0]
                if last_session_data.get("completed_at"):
                    # Format the date nicely
                    from datetime import datetime
                    completed_at = last_session_data["completed_at"]
                    if isinstance(completed_at, str):
                        # Parse if it's a string
                        try:
                            completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        except:
                            pass

                    if hasattr(completed_at, 'strftime'):
                        last_session = completed_at.strftime("%d.%m.%Y")
                    else:
                        last_session = "недавно"  # "recently"
                else:
                    last_session = "в процессе"  # "in progress"

            # Format the returning user message
            welcome_text = self.locale_manager.format(
                "returning_user",
                language=language,
                mastered_tricks=overall_progress.mastered_tricks or 0,
                overall_progress=f"{overall_progress.completion_percentage:.1f}" if overall_progress.completion_percentage else "0.0",
                last_session=last_session
            )

            return welcome_text

        except Exception as e:
            logger.error(f"Error getting returning user welcome for {user_id}: {e}")
            # Fallback to first-time message
            return self.locale_manager.get("first_time", language)

    async def _handle_subscription_check_callback(self, query, context: ActionContext):
        """Handle subscription verification callback."""
        try:
            if not self.subscription_manager:
                await query.edit_message_text("❌ Subscription manager not available.")
                return

            is_subscribed, message = await self.subscription_manager.handle_subscription_check(
                context.user_id, context.language
            )

            if is_subscribed:
                # Subscription verified, show welcome message
                is_first_time = await self._is_first_time_user(context.user_id)

                if is_first_time:
                    welcome_text = self.locale_manager.get("first_time", context.language)
                else:
                    welcome_text = await self._get_returning_user_welcome(context.user_id, context.language)

                # Get user context for keyboard
                user_context = {"has_active_session": context.has_active_session}
                keyboard = self.keyboard_manager.get_main_menu_keyboard(context.language, user_context)

                await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
                logger.info(f"User {context.user_id} subscription verified")
            else:
                # Subscription failed, show error with retry option
                keyboard = self.subscription_manager.get_subscription_keyboard(context.language)
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode="Markdown")
                logger.info(f"User {context.user_id} subscription verification failed")

        except Exception as e:
            logger.error(f"Error handling subscription check: {e}")
            await query.edit_message_text("❌ Ошибка при проверке подписки.")

    async def _handle_retry_trick_callback(self, update, context: ActionContext):
        """Handle retry trick callback."""
        if not self.learning_handlers:
            await update.callback_query.edit_message_text("❌ Learning handlers not available.")
            return

        # Extract trick_id from callback_data (e.g., "retry_trick_123")
        try:
            trick_id_to_retry = int(update.callback_query.data.split("_")[2])
            await self.learning_handlers.retry_current_trick(update, context, trick_id_to_retry)
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing trick_id from callback_data '{update.callback_query.data}': {e}")
            await update.callback_query.edit_message_text("❌ Ошибка: неверный формат данных для повтора.")


    async def _handle_next_trick_callback(self, update, context: ActionContext):
        """Handle next trick callback."""
        if not self.learning_handlers:
            await update.callback_query.edit_message_text("❌ Learning handlers not available.")
            return

        # Extract trick_id from callback_data (e.g., "next_trick_123")
        try:
            current_trick_id = int(update.callback_query.data.split("_")[2])
            await self.learning_handlers.proceed_to_next_trick(update, context, current_trick_id)
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing trick_id from callback_data '{update.callback_query.data}': {e}")
            await update.callback_query.edit_message_text("❌ Ошибка: неверный формат данных для перехода к следующему.")
