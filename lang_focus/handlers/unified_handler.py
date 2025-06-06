"""Unified handler for both commands and callbacks.

This module provides a unified system for handling both Telegram bot commands
and callback queries, ensuring consistent behavior regardless of input method.
"""

import logging
from typing import Optional, Callable, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from lang_focus.core.database import DatabaseManager
from lang_focus.core.keyboard_manager import KeyboardManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.core.ai_provider import OpenRouterProvider
from lang_focus.config.settings import BotConfig
from lang_focus.core.models import BotAction, ActionContext

logger = logging.getLogger(__name__)


class ActionRegistry:
    """Registry for all bot actions."""

    def __init__(self):
        self.actions: Dict[str, BotAction] = {}
        self._initialize_actions()

    def _initialize_actions(self):
        """Initialize all available actions."""
        # Learning Actions
        self.actions.update(
            {
                "learn": BotAction(
                    name="learn",
                    handler=None,  # Will be set by UnifiedBotHandler
                    requires_session=False,
                    menu_text_key="learn_button",
                    emoji="📚",
                    callback_data="cmd_learn",
                    category="learning",
                    description="Start a new learning session",
                ),
                "continue": BotAction(
                    name="continue",
                    handler=None,
                    requires_session=True,
                    menu_text_key="continue_button",
                    emoji="▶️",
                    callback_data="cmd_continue",
                    category="learning",
                    description="Continue existing learning session",
                ),
                "progress": BotAction(
                    name="progress",
                    handler=None,
                    requires_session=False,
                    menu_text_key="progress_button",
                    emoji="📊",
                    callback_data="cmd_progress",
                    category="learning",
                    description="Show learning progress",
                ),
                "tricks": BotAction(
                    name="tricks",
                    handler=None,
                    requires_session=False,
                    menu_text_key="tricks_button",
                    emoji="🎭",
                    callback_data="cmd_tricks",
                    category="learning",
                    description="Show all language tricks",
                ),
                "stats": BotAction(
                    name="stats",
                    handler=None,
                    requires_session=False,
                    menu_text_key="stats_button",
                    emoji="📈",
                    callback_data="cmd_stats",
                    category="learning",
                    description="Show detailed statistics",
                ),
                # Basic Actions
                "help": BotAction(
                    name="help",
                    handler=None,
                    requires_session=False,
                    menu_text_key="help",
                    emoji="ℹ️",
                    callback_data="help",
                    category="basic",
                    description="Show help information",
                ),
                "about": BotAction(
                    name="about",
                    handler=None,
                    requires_session=False,
                    menu_text_key="about",
                    emoji="ℹ️",
                    callback_data="about",
                    category="basic",
                    description="Show bot information",
                ),
                "settings": BotAction(
                    name="settings",
                    handler=None,
                    requires_session=False,
                    menu_text_key="settings",
                    emoji="⚙️",
                    callback_data="settings",
                    category="basic",
                    description="Show settings menu",
                ),
            }
        )

    def get_action(self, name: str) -> Optional[BotAction]:
        """Get action by name."""
        return self.actions.get(name)

    def get_actions_by_category(self, category: str) -> List[BotAction]:
        """Get all actions in a category."""
        return [action for action in self.actions.values() if action.category == category]

    def get_available_actions(self, has_active_session: bool = False) -> List[BotAction]:
        """Get actions available based on context."""
        available = []
        for action in self.actions.values():
            if action.requires_session and not has_active_session:
                continue
            available.append(action)
        return available

    def register_action(self, action: BotAction):
        """Register a new action."""
        self.actions[action.name] = action

    def set_handler(self, action_name: str, handler: Callable):
        """Set handler for an action."""
        if action_name in self.actions:
            self.actions[action_name].handler = handler


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

        # Initialize handlers (will be set by bot setup)
        self.basic_handlers = None
        self.learning_handlers = None

        logger.info("Unified bot handler initialized")

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

    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with enhanced main menu."""
        user = update.effective_user
        chat = update.effective_chat

        if not user:
            return

        try:
            # Ensure user exists in database
            user_data = await self.database.ensure_user(user_id=user.id, username=user.username, language=self.config.default_language)

            user_language = user_data.get("language", self.config.default_language)

            # Get welcome message
            welcome_text = self.locale_manager.format(
                "welcome_message",
                language=user_language,
                bot_name=self.config.bot_name,
                description=self.config.bot_description,
                version=self.config.bot_version,
            )

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
                    await self._handle_skip_callback(query, action_context)
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
            await query.edit_message_text("❌ An error occurred. Please try again.")

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

    async def execute_action(self, action: BotAction, update: Update, context: ActionContext):
        """Execute an action with proper context."""
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

    async def _handle_skip_callback(self, query, context: ActionContext):
        """Handle skip callback."""
        try:
            session = await self.learning_handlers.session_manager.resume_session(context.user_id)
            if session:
                # Move to next trick
                await self.learning_handlers.session_manager.update_session_progress(session, session.current_trick_index + 1)

                next_challenge = await self.learning_handlers.session_manager.get_next_challenge(session)
                if next_challenge:
                    await self.learning_handlers._present_challenge_callback(query, next_challenge, session)
                else:
                    summary = await self.learning_handlers.session_manager.complete_session(session)
                    await self.learning_handlers._present_session_summary_callback(query, summary)
            else:
                await query.edit_message_text("📚 У вас нет активной сессии.")

        except Exception as e:
            logger.error(f"Error skipping trick: {e}")
            await query.edit_message_text("❌ Ошибка при пропуске фокуса.")

    def get_action_registry(self) -> ActionRegistry:
        """Get the action registry."""
        return self.action_registry

    async def _handle_back_to_main(self, query, context: ActionContext):
        """Handle back to main menu navigation."""
        try:
            # Get user context for keyboard
            user_context = {"has_active_session": context.has_active_session}

            # Get welcome message
            welcome_text = self.locale_manager.format(
                "welcome_message",
                language=context.language,
                bot_name=self.config.bot_name,
                description=self.config.bot_description,
                version=self.config.bot_version,
            )

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
