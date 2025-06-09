"""Learning-specific bot handlers for language tricks system.

This module handles all learning-related bot interactions including:
- Learning commands
- Session management
- Response processing
- Progress display
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from lang_focus.config.settings import BotConfig
from lang_focus.core.database import DatabaseManager
from lang_focus.core.keyboard_manager import KeyboardManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.core.ai_provider import OpenRouterProvider
from lang_focus.learning import LearningSessionManager, TrickEngine, FeedbackEngine, ProgressTracker, LearningDataLoader
from lang_focus.learning.session_manager import LearningSession, Challenge

logger = logging.getLogger(__name__)


class LearningHandlers:
    """Handles learning-specific bot interactions."""

    def __init__(
            self,
            locale_manager: LocaleManager,
            keyboard_manager: KeyboardManager,
            database: DatabaseManager,
            ai_provider: OpenRouterProvider,
            config: BotConfig,
    ):
        self.locale_manager = locale_manager
        self.keyboard_manager = keyboard_manager
        self.database = database
        self.ai_provider = ai_provider
        self.config = config

        # Initialize learning components
        self.data_loader = LearningDataLoader(config.database_url)
        self.trick_engine = TrickEngine(config.database_url)
        self.progress_tracker = ProgressTracker(config.database_url)
        self.feedback_engine = FeedbackEngine(ai_provider, self.trick_engine)
        self.session_manager = LearningSessionManager(config.database_url, self.trick_engine, self.feedback_engine, self.progress_tracker)

    async def learn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /learn command to start a new learning session."""
        user = update.effective_user
        if not user:
            return

        try:
            # Ensure user exists in database
            await self.database.ensure_user(user.id, user.username)

            # Start new learning session
            session = await self.session_manager.start_session(user.id)

            # Get first challenge
            challenge = await self.session_manager.get_next_challenge(session)

            if challenge:
                await self._present_challenge(update, challenge, session)
            else:
                await update.message.reply_text("❌ Не удалось создать учебную сессию. Попробуйте позже.")

        except Exception as e:
            logger.error(f"Error in learn command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при создании сессии. Попробуйте позже.")

    async def continue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /continue command to resume existing session."""
        user = update.effective_user
        if not user:
            return

        try:
            # Try to resume existing session
            session = await self.session_manager.resume_session(user.id)

            if not session:
                await update.message.reply_text("📚 У вас нет активной сессии. Начните новую командой /learn")
                return

            # Get next challenge
            challenge = await self.session_manager.get_next_challenge(session)

            if challenge:
                await self._present_challenge(update, challenge, session)
            else:
                # Session is complete
                summary = await self.session_manager.complete_session(session)
                await self._present_session_summary(update, summary)

        except Exception as e:
            logger.error(f"Error in continue command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при восстановлении сессии.")

    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /progress command to show learning progress."""
        user = update.effective_user
        if not user:
            return

        try:
            # Get overall progress
            overall_progress = await self.progress_tracker.calculate_overall_progress(user.id)

            # Get individual trick progress
            user_progress = await self.progress_tracker.get_user_progress(user.id)

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
                    trick = await self.trick_engine.get_trick_by_id(progress.trick_id)
                    status_emoji = "🏆" if progress.is_mastered else "📚"
                    message += f"{status_emoji} {trick.name}: {progress.mastery_level}% "
                    message += f"({progress.correct_attempts}/{progress.total_attempts})\n"

            # Add keyboard for actions
            keyboard = [
                [InlineKeyboardButton("📚 Продолжить обучение", callback_data="continue_learning")],
                [InlineKeyboardButton("🎯 Рекомендации", callback_data="get_recommendations")],
                [InlineKeyboardButton("📈 Статистика", callback_data="detailed_stats")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in progress command: {e}")
            await update.message.reply_text("❌ Ошибка при получении прогресса.")

    async def tricks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tricks command to show all language tricks."""
        try:
            tricks_summary = await self.trick_engine.get_all_tricks_summary()

            message = "🎭 **14 языковых фокусов (фокусы языка)**\n\n"
            message += "Техники вербального рефрейминга для изменения восприятия:\n\n"

            for trick in tricks_summary:
                message += f"**{trick['id']}. {trick['name']}**\n"
                message += f"{trick['definition']}\n"
                message += f"Примеров: {trick['example_count']}\n\n"

            # Add keyboard for learning
            keyboard = [
                [InlineKeyboardButton("🚀 Начать изучение", callback_data="start_learning")],
                [InlineKeyboardButton("📖 Подробнее о фокусе", callback_data="trick_details")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in tricks command: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка фокусов.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command to show detailed statistics."""
        user = update.effective_user
        if not user:
            return

        try:
            # Get learning statistics
            stats = await self.progress_tracker.get_learning_statistics(user.id, days=30)

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

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики.")

    async def handle_learning_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user response during learning session."""
        user = update.effective_user
        message_text = update.message.text

        if not user or not message_text:
            return

        try:
            # Get active session
            session = await self.session_manager.resume_session(user.id)

            if not session:
                # No active session, suggest starting one
                await update.message.reply_text("📚 У вас нет активной сессии обучения. Начните новую командой /learn")
                return

            # Get current challenge
            challenge = await self.session_manager.get_current_challenge(session)
            logger.info(f"Handling challenge response {challenge.target_trick_id} {challenge.target_trick_name}")
            if not challenge:
                # Session complete
                summary = await self.session_manager.complete_session(session)
                await self._present_session_summary(update, summary)
                return

            # Process the response
            feedback = await self.session_manager.process_user_response(session, message_text, challenge.target_trick_id)

            # Present feedback
            await self._present_feedback(update, feedback, challenge)

            # Check if we should continue to next trick
            if feedback.analysis.score >= 60:  # Good enough to continue
                next_challenge = await self.session_manager.get_next_challenge(session)
                if next_challenge:
                    await self._present_challenge(update, next_challenge, session)
                else:
                    # Session complete
                    summary = await self.session_manager.complete_session(session)
                    await self._present_session_summary(update, summary)

        except Exception as e:
            logger.error(f"Error handling learning response: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке ответа. Попробуйте еще раз.")

    async def _present_challenge(self, update: Update, challenge: Challenge, session: LearningSession) -> None:
        """Present a learning challenge to the user."""
        message = f"🎯 **Фокус {challenge.target_trick_id}: {challenge.target_trick_name}**\n\n"
        message += f"📝 **Определение:** {challenge.target_trick_definition}\n\n"
        message += f'💭 **Утверждение для работы:**\n*"{challenge.statement_text}"*\n\n'
        message += f'🎭 **Ваша задача:** Примените фокус "{challenge.target_trick_name}" к данному утверждению.\n\n'

        if challenge.statement_difficulty != "сложный":
            if challenge.examples:
                message += f"💡 **Примеры применения:**\n"
                for example in challenge.examples:
                    message += f"• {example}\n"
                message += "\n"

            if challenge.keywords:
                message += f"🔐 **Ключевые слова:**\n"
                for keyword in challenge.keywords:
                    message += f"• {keyword}\n"
                message += "\n"

        message += f"✍️ Напишите свой ответ, используя этот фокус:"

        # Add keyboard for help and skip
        keyboard = [
            [InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{challenge.target_trick_id}")],
            [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{challenge.target_trick_id}")],
            [InlineKeyboardButton("🛑 Завершить сессию", callback_data="end_session")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.session_manager.update_session_progress(session, challenge.target_trick_id)

        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    async def _present_feedback(self, update: Update, feedback, challenge: Challenge) -> None:
        """Present feedback to the user."""
        analysis = feedback.analysis

        # Score emoji
        if analysis.score >= 80:
            score_emoji = "🏆"
        elif analysis.score >= 60:
            score_emoji = "👍"
        elif analysis.score >= 40:
            score_emoji = "📈"
        else:
            score_emoji = "💪"

        message = f"{score_emoji} **Оценка: {analysis.score:.0f}/100**\n\n"
        message += f"📝 **Обратная связь:**\n{analysis.feedback}\n\n"

        if feedback.encouragement:
            message += f"💬 {feedback.encouragement}\n\n"

        if analysis.improvements:
            message += f"🎯 **Рекомендации для улучшения:**\n"
            for improvement in analysis.improvements:
                message += f"• {improvement}\n"
            message += "\n"

        if feedback.examples:
            message += f"💡 **Дополнительные примеры:**\n"
            for example in feedback.examples:
                message += f"• {example}\n"
            message += "\n"

        message += feedback.next_steps

        # Add keyboard for next actions
        keyboard = []
        if analysis.score < 60:
            keyboard.append([InlineKeyboardButton("🔄 Попробовать еще раз", callback_data=f"retry_trick_{challenge.target_trick_id}")])
            keyboard.append([InlineKeyboardButton("➡️ Следующий фокус", callback_data=f"next_trick_{challenge.target_trick_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    async def _present_session_summary(self, update: Update, summary) -> None:
        """Present session completion summary."""
        duration_minutes = summary.duration.total_seconds() / 60

        message = f"🎓 **Сессия завершена!**\n\n"
        message += f"⏱ Время: {duration_minutes:.1f} минут\n"
        message += f"🎯 Изучено фокусов: {summary.tricks_practiced}/14\n"
        message += f"💬 Всего ответов: {summary.total_attempts}\n"
        message += f"✅ Правильных: {summary.correct_attempts}\n"
        message += f"📊 Средний балл: {summary.average_score:.1f}/100\n\n"

        if summary.mastered_tricks:
            message += f"🏆 **Освоенные фокусы:**\n"
            for trick in summary.mastered_tricks:
                message += f"• {trick}\n"
            message += "\n"

        if summary.recommendations:
            message += f"🎯 **Рекомендации:**\n"
            for rec in summary.recommendations:
                message += f"• {rec}\n"

        # Add keyboard for next actions
        keyboard = [
            [InlineKeyboardButton("🚀 Новая сессия", callback_data="start_new_session")],
            [InlineKeyboardButton("📊 Общий прогресс", callback_data="show_overall_progress")],
            [InlineKeyboardButton("🎭 Все фокусы", callback_data="show_all_tricks")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        try:
            if query.data == "continue_learning":
                await self.continue_command(update, context)
            elif query.data == "start_learning":
                await self.learn_command(update, context)
            elif query.data == "show_progress":
                await self.progress_command(update, context)
            elif query.data == "show_all_tricks":
                await self.tricks_command(update, context)
            elif query.data.startswith("hint_"):
                trick_id = int(query.data.split("_")[1])
                await self._show_hint(update, trick_id)
            elif query.data.startswith("skip_"):
                trick_id_to_skip = int(query.data.split("_")[1])
                await self._skip_trick(update, context, trick_id_to_skip)
            elif query.data == "end_session":
                await self._end_session(update, context)
            elif query.data.startswith("retry_trick_"):
                trick_id_to_retry = int(query.data.split("_")[2])
                await self.retry_current_trick(update, context, trick_id_to_retry)
            elif query.data.startswith("next_trick_"):
                current_trick_id = int(query.data.split("_")[2])
                await self.proceed_to_next_trick(update, context, current_trick_id)
            # Add more callback handlers as needed

        except Exception as e:
            logger.error(f"Error handling callback query {query.data}: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

    async def _show_hint(self, update: Update, trick_id: int) -> None:
        """Show hint for a specific trick."""
        try:
            trick = await self.trick_engine.get_trick_by_id(trick_id)
            examples = await self.trick_engine.get_random_examples(trick_id, count=1)

            message = f'💡 **Подсказка для фокуса "{trick.name}":**\n\n'
            message += f"🔑 **Ключевые слова:** {', '.join(trick.keywords[:3])}\n\n"

            if examples:
                message += f"📝 **Пример:** {examples[0]}\n\n"

            message += "Попробуйте использовать эти подходы в своем ответе!"

            await update.callback_query.edit_message_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error showing hint: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при получении подсказки.")

    async def _skip_trick(self, update: Update, context: ContextTypes.DEFAULT_TYPE, trick_id_to_skip: int) -> None:
        """Skip current trick and move to next."""
        user = update.effective_user
        if not user:
            return

        try:
            session = await self.session_manager.resume_session(user.id)
            if session:
                # Mark the skipped trick as processed
                await self.session_manager.update_session_progress(session, trick_id_to_skip + 1)

                next_challenge = await self.session_manager.get_current_challenge(session)
                if next_challenge:
                    await self._present_challenge(update, next_challenge, session)
                else:
                    summary = await self.session_manager.complete_session(session)
                    await self._present_session_summary(update, summary)

        except Exception as e:
            logger.error(f"Error skipping trick: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при пропуске фокуса.")

    async def _end_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """End current learning session."""
        user = update.effective_user
        if not user:
            return

        try:
            session = await self.session_manager.resume_session(user.id)
            if session:
                summary = await self.session_manager.complete_session(session)
                await self._present_session_summary(update, summary)

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при завершении сессии.")

    async def retry_current_trick(self, update: Update, context: ContextTypes.DEFAULT_TYPE, trick_id_to_retry: int) -> None:
        """Retry current trick with same statement."""
        user = update.effective_user
        if not user:
            return

        try:
            session = await self.session_manager.resume_session(user.id)
            if not session:
                await update.callback_query.answer("❌ Нет активной сессии.")
                return
            # The session's current_trick_index should reflect the trick we are about to retry.
            # update_session_progress will ensure current_trick_index is set to trick_id_to_retry.
            # This allows get_current_challenge to fetch the correct challenge.
            await self.session_manager.update_session_progress(session, trick_id_to_retry)

            # Get current challenge (same trick, same statement)
            challenge = await self.session_manager.get_current_challenge(session)  # This will use the updated session.current_trick_index
            if challenge:
                # Send new message instead of editing
                await update.callback_query.answer("🔄 Попробуем еще раз!")
                await self._send_challenge_message(update, challenge, session)
            else:
                await update.callback_query.answer("❌ Не удалось получить текущий фокус.")

        except Exception as e:
            logger.error(f"Error retrying trick: {e}")
            await update.callback_query.answer("❌ Ошибка при повторе фокуса.")

    async def proceed_to_next_trick(self, update: Update, context: ContextTypes.DEFAULT_TYPE, current_trick_id: int) -> None:
        """Proceed to next trick, sending new message."""
        user = update.effective_user
        if not user:
            return

        try:
            session = await self.session_manager.resume_session(user.id)
            if not session:
                await update.callback_query.answer("❌ Нет активной сессии.")
                return

            # Mark the current trick as processed.
            # update_session_progress will set session.current_trick_index to current_trick_id.
            await self.session_manager.update_session_progress(session, current_trick_id + 1)

            # Get next challenge
            # get_next_challenge will use the updated session.current_trick_index (which is current_trick_id)
            # to determine the actual next trick (current_trick_id + 1).
            next_challenge = await self.session_manager.get_current_challenge(session)
            if next_challenge:
                # Send new message instead of editing
                await update.callback_query.answer("➡️ Переходим к следующему фокусу!")
                await self._send_challenge_message(update, next_challenge, session)
            else:
                # Session complete
                await update.callback_query.answer("🎓 Сессия завершена!")
                summary = await self.session_manager.complete_session(session)
                await self._present_session_summary_callback(None, summary, is_send=True, update=update)

        except Exception as e:
            logger.error(f"Error proceeding to next trick: {e}")
            await update.callback_query.answer("❌ Ошибка при переходе к следующему фокусу.")

    async def _present_challenge_callback(self, query, challenge: Challenge, session: LearningSession) -> None:
        """Present a learning challenge via callback query."""
        message = f"🎯 **Фокус {challenge.target_trick_id}: {challenge.target_trick_name}**\n\n"
        message += f"📝 **Определение:** {challenge.target_trick_definition}\n\n"
        message += f'💭 **Утверждение для работы:**\n*"{challenge.statement_text}"*\n\n'
        message += f'🎭 **Ваша задача:** Примените фокус "{challenge.target_trick_name}" к данному утверждению.\n\n'

        if challenge.statement_difficulty != "сложный":
            if challenge.examples:
                message += f"💡 **Примеры применения:**\n"
                for example in challenge.examples:
                    message += f"• {example}\n"
                message += "\n"

            if challenge.keywords:
                message += f"🔐 **Ключевые слова:**\n"
                for keyword in challenge.keywords:
                    message += f"• {keyword}\n"
                message += "\n"

        message += f"✍️ Напишите свой ответ, используя этот фокус:"

        # Add keyboard for help and skip
        keyboard = [
            [InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{challenge.target_trick_id}")],
            [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{challenge.target_trick_id}")],
            [InlineKeyboardButton("🛑 Завершить сессию", callback_data="end_session")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    async def _present_session_summary_callback(self, query, summary, is_send=False, update=None) -> None:
        """Present session completion summary via callback query."""
        duration_minutes = summary.duration.total_seconds() / 60

        message = f"🎓 **Сессия завершена!**\n\n"
        message += f"⏱ Время: {duration_minutes:.1f} минут\n"
        message += f"🎯 Изучено фокусов: {summary.tricks_practiced}/14\n"
        message += f"💬 Всего ответов: {summary.total_attempts}\n"
        message += f"✅ Правильных: {summary.correct_attempts}\n"
        message += f"📊 Средний балл: {summary.average_score:.1f}/100\n\n"

        if summary.mastered_tricks:
            message += f"🏆 **Освоенные фокусы:**\n"
            for trick in summary.mastered_tricks:
                message += f"• {trick}\n"
            message += "\n"

        if summary.recommendations:
            message += f"🎯 **Рекомендации:**\n"
            for rec in summary.recommendations:
                message += f"• {rec}\n"

        # Add keyboard for next actions
        keyboard = [
            [InlineKeyboardButton("🚀 Новая сессия", callback_data="cmd_learn")],
            [InlineKeyboardButton("📊 Общий прогресс", callback_data="cmd_progress")],
            [InlineKeyboardButton("🎭 Все фокусы", callback_data="cmd_tricks")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if not is_send and query:
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")
        elif update and is_send:
            await update.effective_chat.send_message(message, reply_markup=reply_markup, parse_mode="Markdown")

    async def _send_challenge_message(self, update: Update, challenge: Challenge, session: LearningSession) -> None:
        """Send a new challenge message from callback query."""
        message = f"🎯 **Фокус {challenge.target_trick_id}: {challenge.target_trick_name}**\n\n"
        message += f"📝 **Определение:** {challenge.target_trick_definition}\n\n"
        message += f'💭 **Утверждение для работы:**\n*"{challenge.statement_text}"*\n\n'
        message += f'🎭 **Ваша задача:** Примените фокус "{challenge.target_trick_name}" к данному утверждению.\n\n'

        if challenge.statement_difficulty != "сложный":
            if challenge.examples:
                message += f"💡 **Примеры применения:**\n"
                for example in challenge.examples:
                    message += f"• {example}\n"
                message += "\n"

            if challenge.keywords:
                message += f"🔐 **Ключевые слова:**\n"
                for keyword in challenge.keywords:
                    message += f"• {keyword}\n"
                message += "\n"

        message += f"✍️ Напишите свой ответ, используя этот фокус:"

        # Add keyboard for help and skip
        keyboard = [
            [InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{challenge.target_trick_id}")],
            [InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{challenge.target_trick_id}")],
            [InlineKeyboardButton("🛑 Завершить сессию", callback_data="end_session")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send new message to the chat
        await update.effective_chat.send_message(message, reply_markup=reply_markup, parse_mode="Markdown")
