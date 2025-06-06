"""Progress Tracker for user learning analytics and progress management.

This module handles:
- User progress tracking
- Mastery level calculation
- Learning recommendations
- Achievement tracking
- Learning streaks
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class UserProgress:
    """Represents user progress for a specific trick."""

    user_id: int
    trick_id: int
    mastery_level: int
    total_attempts: int
    correct_attempts: int
    last_practiced: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.correct_attempts / self.total_attempts) * 100

    @property
    def is_mastered(self) -> bool:
        """Check if trick is mastered (80%+ mastery level)."""
        return (self.mastery_level or 0) >= 80


@dataclass
class OverallProgress:
    """Represents user's overall learning progress."""

    user_id: int
    total_tricks: int
    mastered_tricks: int
    average_mastery: float
    total_attempts: int
    total_correct: int
    learning_streak: int
    last_session: Optional[datetime]

    @property
    def completion_percentage(self) -> float:
        """Calculate overall completion percentage."""
        return (self.mastered_tricks / self.total_tricks) * 100 if self.total_tricks > 0 else 0.0

    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate."""
        return (self.total_correct / self.total_attempts) * 100 if self.total_attempts > 0 else 0.0


@dataclass
class Recommendation:
    """Learning recommendation for user."""

    type: str  # 'practice', 'review', 'new_trick'
    trick_id: int
    trick_name: str
    reason: str
    priority: int  # 1-5, where 1 is highest priority


class ProgressTracker:
    """Tracks user learning progress and provides analytics."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def update_progress(self, user_id: int, trick_id: int, score: float, is_correct: bool) -> None:
        """Update user progress after a practice attempt."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Get current progress
            current_progress = await conn.fetchrow(
                """
                SELECT mastery_level, total_attempts, correct_attempts
                FROM user_progress
                WHERE user_id = $1 AND trick_id = $2
            """,
                user_id,
                trick_id,
            )

            if current_progress:
                # Update existing progress
                new_total = current_progress["total_attempts"] + 1
                new_correct = current_progress["correct_attempts"] + (1 if is_correct else 0)

                # Calculate new mastery level using weighted average
                # Recent performance has more weight
                current_mastery = current_progress["mastery_level"]
                score_weight = 0.3  # 30% weight for new score
                new_mastery = int(current_mastery * (1 - score_weight) + score * score_weight)
                new_mastery = max(0, min(100, new_mastery))  # Clamp between 0-100

                await conn.execute(
                    """
                    UPDATE user_progress
                    SET mastery_level = $1, total_attempts = $2, correct_attempts = $3,
                        last_practiced = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $4 AND trick_id = $5
                """,
                    new_mastery,
                    new_total,
                    new_correct,
                    user_id,
                    trick_id,
                )
            else:
                # Create new progress record
                initial_mastery = int(score)
                await conn.execute(
                    """
                    INSERT INTO user_progress 
                    (user_id, trick_id, mastery_level, total_attempts, correct_attempts, last_practiced)
                    VALUES ($1, $2, $3, 1, $4, CURRENT_TIMESTAMP)
                """,
                    user_id,
                    trick_id,
                    initial_mastery,
                    1 if is_correct else 0,
                )

            logger.info(f"Updated progress for user {user_id}, trick {trick_id}: score={score}, correct={is_correct}")

        finally:
            await conn.close()

    async def get_user_progress(self, user_id: int) -> List[UserProgress]:
        """Get all progress records for a user."""
        conn = await asyncpg.connect(self.database_url)
        try:
            rows = await conn.fetch(
                """
                SELECT user_id, trick_id, mastery_level, total_attempts, correct_attempts,
                       last_practiced, created_at, updated_at
                FROM user_progress
                WHERE user_id = $1
                ORDER BY trick_id
            """,
                user_id,
            )

            return [UserProgress(**dict(row)) for row in rows]

        finally:
            await conn.close()

    async def get_progress_for_trick(self, user_id: int, trick_id: int) -> Optional[UserProgress]:
        """Get progress for a specific trick."""
        conn = await asyncpg.connect(self.database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT user_id, trick_id, mastery_level, total_attempts, correct_attempts,
                       last_practiced, created_at, updated_at
                FROM user_progress
                WHERE user_id = $1 AND trick_id = $2
            """,
                user_id,
                trick_id,
            )

            return UserProgress(**dict(row)) if row else None

        finally:
            await conn.close()

    async def get_mastery_level(self, user_id: int, trick_id: int) -> int:
        """Get mastery level for a specific trick."""
        progress = await self.get_progress_for_trick(user_id, trick_id)
        return progress.mastery_level if progress else 0

    async def calculate_overall_progress(self, user_id: int) -> OverallProgress:
        """Calculate user's overall learning progress."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Get progress statistics
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as practiced_tricks,
                    COUNT(CASE WHEN mastery_level >= 80 THEN 1 END) as mastered_tricks,
                    COALESCE(AVG(mastery_level), 0) as avg_mastery,
                    COALESCE(SUM(total_attempts), 0) as total_attempts,
                    COALESCE(SUM(correct_attempts), 0) as total_correct,
                    MAX(last_practiced) as last_session
                FROM user_progress
                WHERE user_id = $1
            """,
                user_id,
            )

            # Calculate learning streak
            streak = await self._calculate_learning_streak(user_id)

            return OverallProgress(
                user_id=user_id,
                total_tricks=14,  # Total number of language tricks
                mastered_tricks=stats["mastered_tricks"],
                average_mastery=float(stats["avg_mastery"]),
                total_attempts=stats["total_attempts"],
                total_correct=stats["total_correct"],
                learning_streak=streak,
                last_session=stats["last_session"],
            )

        finally:
            await conn.close()

    async def _calculate_learning_streak(self, user_id: int) -> int:
        """Calculate consecutive days of learning."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Get distinct practice dates in descending order
            rows = await conn.fetch(
                """
                SELECT DISTINCT DATE(last_practiced) as practice_date
                FROM user_progress
                WHERE user_id = $1 AND last_practiced IS NOT NULL
                ORDER BY practice_date DESC
            """,
                user_id,
            )

            if not rows:
                return 0

            streak = 0
            current_date = datetime.now().date()

            for row in rows:
                practice_date = row["practice_date"]

                # Check if this date is consecutive
                expected_date = current_date - timedelta(days=streak)

                if practice_date == expected_date:
                    streak += 1
                elif practice_date == expected_date - timedelta(days=1):
                    # Allow for yesterday if today hasn't been practiced yet
                    streak += 1
                else:
                    break

            return streak

        finally:
            await conn.close()

    async def get_learning_recommendations(self, user_id: int) -> List[Recommendation]:
        """Get personalized learning recommendations."""
        progress_list = await self.get_user_progress(user_id)
        overall_progress = await self.calculate_overall_progress(user_id)

        recommendations = []

        # Create progress map for easier lookup
        progress_map = {p.trick_id: p for p in progress_list}

        # Get trick names from database
        conn = await asyncpg.connect(self.database_url)
        try:
            trick_names = await conn.fetch("SELECT id, name FROM language_tricks ORDER BY id")
            trick_name_map = {row["id"]: row["name"] for row in trick_names}
        finally:
            await conn.close()

        # Recommendation 1: Practice tricks with low mastery
        for trick_id in range(1, 15):  # Tricks 1-14
            progress = progress_map.get(trick_id)
            trick_name = trick_name_map.get(trick_id, f"Фокус {trick_id}")

            if not progress:
                # New trick
                recommendations.append(
                    Recommendation(
                        type="new_trick", trick_id=trick_id, trick_name=trick_name, reason="Новый фокус для изучения", priority=2
                    )
                )
            elif (progress.mastery_level or 0) < 50:
                # Low mastery - needs practice
                recommendations.append(
                    Recommendation(
                        type="practice",
                        trick_id=trick_id,
                        trick_name=trick_name,
                        reason=f"Низкий уровень мастерства ({progress.mastery_level or 0}%)",
                        priority=1,
                    )
                )
            elif (progress.mastery_level or 0) < 80 and progress.last_practiced:
                # Medium mastery - check if needs review
                days_since_practice = (datetime.now(tz=UTC) - progress.last_practiced).days
                if days_since_practice > 7:
                    recommendations.append(
                        Recommendation(
                            type="review",
                            trick_id=trick_id,
                            trick_name=trick_name,
                            reason=f"Не практиковался {days_since_practice} дней",
                            priority=3,
                        )
                    )

        # Sort by priority and limit to top 5
        recommendations.sort(key=lambda x: (x.priority, x.trick_id))
        return recommendations[:5]

    async def track_learning_streak(self, user_id: int) -> int:
        """Track and return current learning streak."""
        return await self._calculate_learning_streak(user_id)

    async def get_achievement_progress(self, user_id: int) -> Dict[str, Any]:
        """Get user's achievement progress."""
        overall_progress = await self.calculate_overall_progress(user_id)
        progress_list = await self.get_user_progress(user_id)

        achievements = {
            "first_steps": {
                "name": "Первые шаги",
                "description": "Попробовать первый фокус",
                "completed": len(progress_list) > 0,
                "progress": min(1, len(progress_list)),
            },
            "dedicated_learner": {
                "name": "Усердный ученик",
                "description": "Практиковаться 7 дней подряд",
                "completed": overall_progress.learning_streak >= 7,
                "progress": min(7, overall_progress.learning_streak),
            },
            "trick_master": {
                "name": "Мастер фокусов",
                "description": "Освоить 5 фокусов",
                "completed": overall_progress.mastered_tricks >= 5,
                "progress": min(5, overall_progress.mastered_tricks),
            },
            "perfectionist": {
                "name": "Перфекционист",
                "description": "Достичь 90% точности",
                "completed": overall_progress.overall_success_rate >= 90,
                "progress": min(90, overall_progress.overall_success_rate),
            },
            "language_guru": {
                "name": "Гуру языка",
                "description": "Освоить все 14 фокусов",
                "completed": overall_progress.mastered_tricks >= 14,
                "progress": min(14, overall_progress.mastered_tricks),
            },
        }

        return achievements

    async def get_learning_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get detailed learning statistics for the past N days."""
        conn = await asyncpg.connect(self.database_url)
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Get session statistics
            session_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(DISTINCT DATE(started_at)) as active_days,
                    COUNT(*) as total_sessions,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))/60) as avg_session_minutes
                FROM learning_sessions
                WHERE user_id = $1 AND started_at >= $2 AND completed_at IS NOT NULL
            """,
                user_id,
                cutoff_date,
            )

            # Get response statistics
            response_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_responses,
                    COUNT(CASE WHEN is_correct THEN 1 END) as correct_responses,
                    AVG(similarity_score) as avg_similarity
                FROM user_responses
                WHERE user_id = $1 AND created_at >= $2
            """,
                user_id,
                cutoff_date,
            )

            # Get trick-specific statistics
            trick_stats = await conn.fetch(
                """
                SELECT 
                    lt.name as trick_name,
                    COUNT(ur.id) as attempts,
                    COUNT(CASE WHEN ur.is_correct THEN 1 END) as correct,
                    AVG(ur.similarity_score) as avg_score
                FROM user_responses ur
                JOIN language_tricks lt ON ur.trick_id = lt.id
                WHERE ur.user_id = $1 AND ur.created_at >= $2
                GROUP BY lt.id, lt.name
                ORDER BY attempts DESC
            """,
                user_id,
                cutoff_date,
            )

            return {
                "period_days": days,
                "active_days": session_stats["active_days"] or 0,
                "total_sessions": session_stats["total_sessions"] or 0,
                "avg_session_minutes": float(session_stats["avg_session_minutes"] or 0),
                "total_responses": response_stats["total_responses"] or 0,
                "correct_responses": response_stats["correct_responses"] or 0,
                "success_rate": (
                    (response_stats["correct_responses"] / response_stats["total_responses"] * 100)
                    if response_stats["total_responses"]
                    else 0
                ),
                "avg_similarity": float(response_stats["avg_similarity"] or 0),
                "trick_performance": [
                    {
                        "trick_name": row["trick_name"],
                        "attempts": row["attempts"],
                        "correct": row["correct"],
                        "success_rate": (row["correct"] / row["attempts"] * 100) if row["attempts"] else 0,
                        "avg_score": float(row["avg_score"] or 0),
                    }
                    for row in trick_stats
                ],
            }

        finally:
            await conn.close()
