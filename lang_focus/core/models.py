from dataclasses import dataclass
from typing import Callable, Optional, List


@dataclass
class BotAction:
    """Represents a bot action that can be triggered by command or callback."""

    name: str
    handler: Callable
    requires_session: bool = False
    menu_text_key: str = ""
    emoji: str = ""
    callback_data: str = ""
    category: str = "basic"
    description: str = ""


@dataclass
class NavigationContext:
    """Navigation context for hierarchical menu navigation."""

    current_page: str
    parent_page: Optional[str] = None
    breadcrumb: List[str] = None

    def __post_init__(self):
        if self.breadcrumb is None:
            self.breadcrumb = []


@dataclass
class ActionContext:
    """Context information for executing an action."""

    user_id: int
    username: Optional[str]
    language: str
    is_callback: bool
    has_active_session: bool
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    callback_query = None
    navigation: Optional[NavigationContext] = None
