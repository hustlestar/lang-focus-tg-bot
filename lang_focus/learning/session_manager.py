"""Learning Session Manager for orchestrating learning sessions and user flow.

This module handles:
- Session creation and management
- Learning flow orchestration
- Challenge generation
- Session state management
- Adaptive difficulty
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import asyncpg

from lang_focus.learning.trick_engine import TrickEngine, LanguageTrick
from lang_focus.learning.feedback_engine import FeedbackEngine, Feedback
from lang_focus.learning.progress_tracker import ProgressTracker
from lang_focus.learning.data_loader import LearningDataLoader

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session status enumeration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class Challenge:
    """Represents a learning challenge."""

    statement_id: int
    statement_text: str
    statement_category: str
    statement_difficulty: str
    target_trick_id: int
    target_trick_name: str
    target_trick_definition: str
    examples: List[str]
    attempt_number: int


@dataclass
class LearningSession:
    """Represents a learning session."""

    id: int
    user_id: int
    statement_id: int
    session_type: str
    session_data: Dict[str, Any]
    status: SessionStatus
    current_trick_index: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    @property
    def duration(self) -> Optional[timedelta]:
        """Get session duration."""
        if self.completed_at:
            # Ensure both datetimes have the same timezone awareness
            if self.completed_at.tzinfo is not None and self.started_at.tzinfo is None:
                # completed_at is timezone-aware, started_at is naive
                return self.completed_at - self.started_at.replace(tzinfo=self.completed_at.tzinfo)
            elif self.completed_at.tzinfo is None and self.started_at.tzinfo is not None:
                # completed_at is naive, started_at is timezone-aware
                return self.completed_at.replace(tzinfo=self.started_at.tzinfo) - self.started_at
            else:
                # Both have same timezone awareness
                return self.completed_at - self.started_at

        # For ongoing sessions, use current time
        now = datetime.now()
        if self.started_at.tzinfo is not None and now.tzinfo is None:
            # started_at is timezone-aware, now is naive
            now = now.replace(tzinfo=self.started_at.tzinfo)
        elif self.started_at.tzinfo is None and now.tzinfo is not None:
            # started_at is naive, now is timezone-aware
            return now - self.started_at.replace(tzinfo=now.tzinfo)

        return now - self.started_at

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE


@dataclass
class SessionSummary:
    """Summary of completed learning session."""

    session_id: int
    user_id: int
    duration: timedelta
    tricks_practiced: int
    total_attempts: int
    correct_attempts: int
    average_score: float
    mastered_tricks: List[str]
    recommendations: List[str]


class LearningSessionManager:
    """Orchestrates learning sessions and manages user flow."""

    def __init__(self, database_url: str, trick_engine: TrickEngine, feedback_engine: FeedbackEngine, progress_tracker: ProgressTracker):
        self.database_url = database_url
        self.trick_engine = trick_engine
        self.feedback_engine = feedback_engine
        self.progress_tracker = progress_tracker
        self.data_loader = LearningDataLoader(database_url)

    async def start_session(self, user_id: int, session_type: str = "practice") -> LearningSession:
        """Start a new learning session."""
        # Check for existing active session
        existing_session = await self.get_active_session(user_id)
        if existing_session:
            logger.info(f"User {user_id} already has an active session {existing_session.id}")
            return existing_session

        # Get appropriate statement based on user level
        difficulty = await self.get_adaptive_difficulty(user_id)
        statement = await self.data_loader.get_random_statement(difficulty)

        conn = await asyncpg.connect(self.database_url)
        try:
            # Create new session
            session_id = await conn.fetchval(
                """
                INSERT INTO learning_sessions 
                (user_id, statement_id, session_type, session_data, status, current_trick_index)
                VALUES ($1, $2, $3, $4, $5, 0)
                RETURNING id
            """,
                user_id,
                statement["id"],
                session_type,
                json.dumps({}),
                SessionStatus.ACTIVE.value,
            )

            session = LearningSession(
                id=session_id,
                user_id=user_id,
                statement_id=statement["id"],
                session_type=session_type,
                session_data={},
                status=SessionStatus.ACTIVE,
                current_trick_index=0,
                started_at=datetime.now(),
            )

            logger.info(f"Started new session {session_id} for user {user_id}")
            return session

        finally:
            await conn.close()

    async def resume_session(self, user_id: int) -> Optional[LearningSession]:
        """Resume an existing active session."""
        return await self.get_active_session(user_id)

    async def get_active_session(self, user_id: int) -> Optional[LearningSession]:
        """Get user's active session if any."""
        conn = await asyncpg.connect(self.database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, statement_id, session_type, session_data, 
                       status, current_trick_index, started_at, completed_at
                FROM learning_sessions
                WHERE user_id = $1 AND status = $2
                ORDER BY started_at DESC
                LIMIT 1
            """,
                user_id,
                SessionStatus.ACTIVE.value,
            )

            if not row:
                return None

            return LearningSession(
                id=row["id"],
                user_id=row["user_id"],
                statement_id=row["statement_id"],
                session_type=row["session_type"],
                session_data=row["session_data"] or {},
                status=SessionStatus(row["status"]),
                current_trick_index=row["current_trick_index"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )

        finally:
            await conn.close()

    async def get_next_challenge(self, session: LearningSession) -> Optional[Challenge]:
        """Get the next challenge for the session."""
        # Handle None values for current_trick_index
        current_index = session.current_trick_index or 0

        # Check if session is complete (all 14 tricks practiced)
        if current_index >= 14:
            return None

        # Get the next trick to practice
        next_trick_id = current_index + 1

        # Get trick and statement data
        trick = await self.trick_engine.get_trick_by_id(next_trick_id)
        statement = await self.data_loader.get_statement_by_id(session.statement_id)
        examples = await self.trick_engine.get_random_examples(next_trick_id, count=2)

        # Get attempt number for this trick in this session
        attempt_number = await self._get_attempt_number(session.id, next_trick_id)

        return Challenge(
            statement_id=statement["id"],
            statement_text=statement["statement"],
            statement_category=statement["category"],
            statement_difficulty=statement["difficulty"],
            target_trick_id=trick.id,
            target_trick_name=trick.name,
            target_trick_definition=trick.definition,
            examples=examples,
            attempt_number=attempt_number,
        )

    async def _get_attempt_number(self, session_id: int, trick_id: int) -> int:
        """Get the attempt number for a trick in this session."""
        conn = await asyncpg.connect(self.database_url)
        try:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM user_responses
                WHERE session_id = $1 AND trick_id = $2
            """,
                session_id,
                trick_id,
            )
            return count + 1
        finally:
            await conn.close()

    async def process_user_response(self, session: LearningSession, response: str, trick_id: int) -> Feedback:
        """Process user response and generate feedback."""
        # Get trick and statement data
        trick = await self.trick_engine.get_trick_by_id(trick_id)
        statement = await self.data_loader.get_statement_by_id(session.statement_id)

        # Analyze response
        analysis = await self.feedback_engine.analyze_response(response, trick, statement["statement"])

        # Generate comprehensive feedback
        feedback = await self.feedback_engine.generate_feedback(analysis, trick)

        # Store response in database
        await self._store_user_response(session.id, session.user_id, trick_id, session.statement_id, response, feedback, analysis)

        # Update progress
        await self.progress_tracker.update_progress(session.user_id, trick_id, analysis.score, analysis.is_correct)

        # Update session progress
        await self.update_session_progress(session, trick_id)

        logger.info(f"Processed response for user {session.user_id}, trick {trick_id}, score: {analysis.score}")
        return feedback

    async def _store_user_response(
        self, session_id: int, user_id: int, trick_id: int, statement_id: int, response: str, feedback: Feedback, analysis
    ) -> None:
        """Store user response and feedback in database."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Prepare analysis data for JSON serialization
            analysis_data_json = {}
            if hasattr(analysis, "analysis_data") and analysis.analysis_data:
                # Convert any non-serializable objects to strings
                for key, value in analysis.analysis_data.items():
                    try:
                        json.dumps(value)  # Test if serializable
                        analysis_data_json[key] = value
                    except (TypeError, ValueError):
                        analysis_data_json[key] = str(value)

            await conn.execute(
                """
                INSERT INTO user_responses
                (session_id, user_id, trick_id, statement_id, user_response,
                 ai_feedback, similarity_score, is_correct, analysis_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                session_id,
                user_id,
                trick_id,
                statement_id,
                response,
                feedback.analysis.feedback,
                analysis.score / 100,
                analysis.is_correct,
                json.dumps(analysis_data_json),
            )
        finally:
            await conn.close()

    async def update_session_progress(self, session: LearningSession, completed_trick_id: int) -> None:
        """Update session progress after completing a trick."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Update current trick index - handle None values
            current_index = session.current_trick_index or 0
            trick_id = completed_trick_id or 0
            new_index = max(current_index, trick_id)

            await conn.execute(
                """
                UPDATE learning_sessions
                SET current_trick_index = $1
                WHERE id = $2
            """,
                new_index,
                session.id,
            )

            session.current_trick_index = new_index

        finally:
            await conn.close()

    async def complete_session(self, session: LearningSession) -> SessionSummary:
        """Complete a learning session and generate summary."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Mark session as completed
            await conn.execute(
                """
                UPDATE learning_sessions
                SET status = $1, completed_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """,
                SessionStatus.COMPLETED.value,
                session.id,
            )

            # Get session statistics
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(DISTINCT trick_id) as tricks_practiced,
                    COUNT(*) as total_attempts,
                    COUNT(CASE WHEN is_correct THEN 1 END) as correct_attempts,
                    AVG(similarity_score * 100) as average_score
                FROM user_responses
                WHERE session_id = $1
            """,
                session.id,
            )

            # Get mastered tricks in this session
            mastered_tricks = await conn.fetch(
                """
                SELECT DISTINCT lt.name
                FROM user_responses ur
                JOIN language_tricks lt ON ur.trick_id = lt.id
                WHERE ur.session_id = $1 AND ur.similarity_score >= 0.8
            """,
                session.id,
            )

            # Generate recommendations
            recommendations = await self._generate_session_recommendations(session.user_id, stats)

            session.status = SessionStatus.COMPLETED
            # Ensure completed_at has same timezone awareness as started_at
            now = datetime.now()
            if session.started_at.tzinfo is not None:
                # If started_at is timezone-aware, make completed_at timezone-aware too
                session.completed_at = now.replace(tzinfo=session.started_at.tzinfo)
            else:
                # If started_at is naive, keep completed_at naive
                session.completed_at = now

            summary = SessionSummary(
                session_id=session.id,
                user_id=session.user_id,
                duration=session.duration or timedelta(0),
                tricks_practiced=stats["tricks_practiced"],
                total_attempts=stats["total_attempts"],
                correct_attempts=stats["correct_attempts"],
                average_score=float(stats["average_score"] or 0),
                mastered_tricks=[row["name"] for row in mastered_tricks],
                recommendations=recommendations,
            )

            logger.info(f"Completed session {session.id} for user {session.user_id}")
            return summary

        finally:
            await conn.close()

    async def _generate_session_recommendations(self, user_id: int, session_stats: Dict) -> List[str]:
        """Generate recommendations based on session performance."""
        recommendations = []

        # Handle None values safely - ensure all values are numbers
        average_score = float(session_stats.get("average_score") or 0)
        correct_attempts = int(session_stats.get("correct_attempts") or 0)
        total_attempts = int(session_stats.get("total_attempts") or 0)
        success_rate = (correct_attempts / max(total_attempts, 1)) * 100 if total_attempts > 0 else 0

        if average_score >= 80:
            recommendations.append("Отличная работа! Вы готовы к более сложным утверждениям.")
        elif average_score >= 60:
            recommendations.append("Хороший прогресс! Продолжайте практиковаться для закрепления.")
        else:
            recommendations.append("Изучите примеры и определения фокусов перед следующей сессией.")

        if success_rate < 50:
            recommendations.append("Сосредоточьтесь на понимании ключевых слов каждого фокуса.")

        # Get personalized recommendations from progress tracker
        progress_recommendations = await self.progress_tracker.get_learning_recommendations(user_id)
        for rec in progress_recommendations[:2]:  # Add top 2 recommendations
            recommendations.append(f"Практикуйте '{rec.trick_name}': {rec.reason}")

        return recommendations

    async def abandon_session(self, session: LearningSession) -> None:
        """Mark session as abandoned."""
        conn = await asyncpg.connect(self.database_url)
        try:
            await conn.execute(
                """
                UPDATE learning_sessions
                SET status = $1
                WHERE id = $2
            """,
                SessionStatus.ABANDONED.value,
                session.id,
            )

            session.status = SessionStatus.ABANDONED
            logger.info(f"Abandoned session {session.id} for user {session.user_id}")

        finally:
            await conn.close()

    async def get_adaptive_difficulty(self, user_id: int) -> str:
        """Get adaptive difficulty based on user progress."""
        overall_progress = await self.progress_tracker.calculate_overall_progress(user_id)

        # Handle None values safely
        average_mastery = overall_progress.average_mastery or 0

        if average_mastery >= 70:
            return "сложный"
        elif average_mastery >= 40:
            return "средний"
        else:
            return "легкий"

    async def get_session_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's session history."""
        conn = await asyncpg.connect(self.database_url)
        try:
            rows = await conn.fetch(
                """
                SELECT 
                    ls.id, ls.session_type, ls.status, ls.started_at, ls.completed_at,
                    ts.statement, ts.difficulty,
                    COUNT(ur.id) as responses_count,
                    COUNT(CASE WHEN ur.is_correct THEN 1 END) as correct_count,
                    AVG(ur.similarity_score * 100) as avg_score
                FROM learning_sessions ls
                JOIN training_statements ts ON ls.statement_id = ts.id
                LEFT JOIN user_responses ur ON ls.id = ur.session_id
                WHERE ls.user_id = $1
                GROUP BY ls.id, ts.statement, ts.difficulty
                ORDER BY ls.started_at DESC
                LIMIT $2
            """,
                user_id,
                limit,
            )

            return [
                {
                    "session_id": row["id"],
                    "session_type": row["session_type"],
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "statement": row["statement"],
                    "difficulty": row["difficulty"],
                    "responses_count": row["responses_count"],
                    "correct_count": row["correct_count"],
                    "success_rate": (row["correct_count"] / max(row["responses_count"], 1)) * 100,
                    "average_score": float(row["avg_score"] or 0),
                }
                for row in rows
            ]

        finally:
            await conn.close()

    async def cleanup_old_sessions(self, days_old: int = 7) -> int:
        """Clean up old abandoned sessions."""
        conn = await asyncpg.connect(self.database_url)
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)

            # Mark old active sessions as abandoned
            count = await conn.fetchval(
                """
                UPDATE learning_sessions
                SET status = $1
                WHERE status = $2 AND started_at < $3
                RETURNING COUNT(*)
            """,
                SessionStatus.ABANDONED.value,
                SessionStatus.ACTIVE.value,
                cutoff_date,
            )

            logger.info(f"Cleaned up {count} old sessions")
            return count

        finally:
            await conn.close()
