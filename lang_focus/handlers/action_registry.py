from typing import Dict, Optional, List, Callable

from lang_focus.core.models import BotAction


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
