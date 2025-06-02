"""Learning module for language tricks system.

This module contains all components for the language learning system including:
- Session management
- Trick engine
- Feedback engine
- Progress tracking
- Data loading
"""

from .data_loader import LearningDataLoader
from .session_manager import LearningSessionManager
from .trick_engine import TrickEngine
from .feedback_engine import FeedbackEngine
from .progress_tracker import ProgressTracker

__all__ = [
    'LearningDataLoader',
    'LearningSessionManager', 
    'TrickEngine',
    'FeedbackEngine',
    'ProgressTracker'
]