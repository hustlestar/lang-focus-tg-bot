"""
Subscription verification module for the Language Learning Bot
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
import asyncpg

from lang_focus.core.database import DatabaseManager
from lang_focus.core.locale_manager import LocaleManager
from lang_focus.config.settings import BotConfig

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Manager for channel subscription verification
    """

    def __init__(self, bot: Bot, config: BotConfig, database: DatabaseManager, locale_manager: LocaleManager):
        """
        Initialize subscription manager

        Args:
            bot: Telegram bot instance
            config: Bot configuration
            database: Database manager
            locale_manager: Locale manager for translations
        """
        self.bot = bot
        self.config = config
        self.database = database
        self.locale_manager = locale_manager
        
        # Channel configuration
        self.channel_username = getattr(config, 'channel_username', None)
        self.channel_id = getattr(config, 'channel_id', None)
        self.subscription_required = getattr(config, 'subscription_required', False)
        
        logger.info(
            f"Subscription manager initialized - Required: {self.subscription_required}, "
            f"Channel: {self.channel_username} ({self.channel_id})"
        )

    async def is_subscribed(self, user_id: int) -> bool:
        """
        Check if user is subscribed to the channel

        Args:
            user_id: Telegram user ID

        Returns:
            bool: True if user is subscribed or subscription not required
        """
        # If subscription is not required, always return True
        if not self.subscription_required or not self.channel_id:
            return True
            
        try:
            # Get chat member status
            chat_member = await self.bot.get_chat_member(
                chat_id=self.channel_id, user_id=user_id
            )

            # Check if user is a member of the channel
            is_member = chat_member.status in [
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER
            ]

            # Update subscription status in database
            await self._update_subscription_status(user_id, is_member)

            logger.info(f"User {user_id} subscription status: {is_member}")
            return is_member

        except Exception as e:
            logger.error(f"Error checking subscription for user {user_id}: {str(e)}")
            return False

    async def _update_subscription_status(self, user_id: int, is_subscribed: bool) -> None:
        """Update user subscription status in database."""
        try:
            conn = await asyncpg.connect(self.database.database_url)
            try:
                await conn.execute(
                    """
                    UPDATE users
                    SET is_subscribed = $1, subscription_checked_at = $2
                    WHERE user_id = $3
                    """,
                    is_subscribed,
                    datetime.now(),
                    user_id
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error updating subscription status for user {user_id}: {e}")

    def get_subscription_keyboard(self, language: str) -> InlineKeyboardMarkup:
        """
        Get keyboard with subscription button

        Args:
            language: User language code

        Returns:
            InlineKeyboardMarkup: Keyboard with subscription button
        """
        if not self.channel_username:
            return InlineKeyboardMarkup([])
            
        keyboard = [
            [
                InlineKeyboardButton(
                    self.locale_manager.get("ask_to_subscribe", language),
                    url=f"https://t.me/{self.channel_username.lstrip('@')}"
                )
            ],
            [
                InlineKeyboardButton(
                    self.locale_manager.get("user_confirm_subscribed", language),
                    callback_data="check_subscription"
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_subscription_check(self, user_id: int, language: str) -> tuple[bool, str]:
        """
        Handle subscription verification callback

        Args:
            user_id: Telegram user ID
            language: User language code

        Returns:
            tuple: (is_subscribed, message)
        """
        is_subscribed = await self.is_subscribed(user_id)
        
        if is_subscribed:
            message = self.locale_manager.get("subscription_verified", language)
        else:
            message = self.locale_manager.get("subscription_failed", language)
            
        return is_subscribed, message
