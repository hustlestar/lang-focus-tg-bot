"""Learning-related database models for SQLAlchemy Core.

This module defines the learning tables schema for the language tricks system.
"""

from sqlalchemy import Table, Column, Integer, String, Text, DateTime, Boolean, Float, BigInteger, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import metadata

# Language tricks table
language_tricks_table = Table(
    "language_tricks",
    metadata,
    Column("id", Integer, primary_key=True, comment="Unique trick ID"),
    Column("name", String(100), nullable=False, comment="Trick name (e.g., 'Намерение')"),
    Column("definition", Text, nullable=False, comment="Trick definition and explanation"),
    Column("keywords", JSONB, nullable=False, comment="Keywords and phrases for this trick"),
    Column("examples", JSONB, nullable=False, comment="Examples of trick usage"),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Trick creation timestamp",
    ),
)

# Training statements table
training_statements_table = Table(
    "training_statements",
    metadata,
    Column("id", Integer, primary_key=True, comment="Unique statement ID"),
    Column("statement", Text, nullable=False, comment="The statement to practice with"),
    Column("category", String(100), nullable=False, comment="Statement category"),
    Column("difficulty", String(20), nullable=False, comment="Difficulty level"),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Statement creation timestamp",
    ),
    CheckConstraint("difficulty IN ('легкий', 'средний', 'сложный')", name="check_difficulty"),
)

# User progress table
user_progress_table = Table(
    "user_progress",
    metadata,
    Column("id", Integer, primary_key=True, comment="Unique progress record ID"),
    Column("user_id", BigInteger, ForeignKey("users.user_id"), nullable=False, comment="User ID"),
    Column("trick_id", Integer, ForeignKey("language_tricks.id"), nullable=False, comment="Language trick ID"),
    Column("mastery_level", Integer, nullable=False, default=0, server_default="0", comment="Mastery level (0-100)"),
    Column("total_attempts", Integer, nullable=False, default=0, server_default="0", comment="Total practice attempts"),
    Column("correct_attempts", Integer, nullable=False, default=0, server_default="0", comment="Correct attempts"),
    Column("last_practiced", DateTime(timezone=True), nullable=True, comment="Last practice timestamp"),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Progress record creation timestamp",
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Last update timestamp",
    ),
    UniqueConstraint("user_id", "trick_id", name="unique_user_trick"),
    CheckConstraint("mastery_level >= 0 AND mastery_level <= 100", name="check_mastery_level"),
    CheckConstraint("total_attempts >= 0", name="check_total_attempts"),
    CheckConstraint("correct_attempts >= 0", name="check_correct_attempts"),
    CheckConstraint("correct_attempts <= total_attempts", name="check_correct_vs_total"),
)

# Learning sessions table
learning_sessions_table = Table(
    "learning_sessions",
    metadata,
    Column("id", Integer, primary_key=True, comment="Unique session ID"),
    Column("user_id", BigInteger, ForeignKey("users.user_id"), nullable=False, comment="User ID"),
    Column("statement_id", Integer, ForeignKey("training_statements.id"), nullable=False, comment="Training statement ID"),
    Column("session_type", String(50), nullable=False, default="practice", server_default="practice", comment="Session type"),
    Column("session_data", JSONB, nullable=True, comment="Session metadata and state"),
    Column("status", String(20), nullable=False, default="active", server_default="active", comment="Session status"),
    Column("current_trick_index", Integer, nullable=False, default=0, server_default="0", comment="Current trick being practiced"),
    Column(
        "started_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Session start timestamp",
    ),
    Column("completed_at", DateTime(timezone=True), nullable=True, comment="Session completion timestamp"),
    CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="check_session_status"),
)

# User responses table
user_responses_table = Table(
    "user_responses",
    metadata,
    Column("id", Integer, primary_key=True, comment="Unique response ID"),
    Column("session_id", Integer, ForeignKey("learning_sessions.id"), nullable=False, comment="Learning session ID"),
    Column("user_id", BigInteger, ForeignKey("users.user_id"), nullable=False, comment="User ID"),
    Column("trick_id", Integer, ForeignKey("language_tricks.id"), nullable=False, comment="Target trick ID"),
    Column("statement_id", Integer, ForeignKey("training_statements.id"), nullable=False, comment="Training statement ID"),
    Column("user_response", Text, nullable=False, comment="User's response text"),
    Column("ai_feedback", Text, nullable=True, comment="AI-generated feedback"),
    Column("similarity_score", Float, nullable=True, comment="Response similarity score (0-1)"),
    Column("is_correct", Boolean, nullable=True, comment="Whether the response was correct"),
    Column("analysis_data", JSONB, nullable=True, comment="Detailed analysis data from AI"),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=func.current_timestamp(),
        server_default=func.current_timestamp(),
        comment="Response creation timestamp",
    ),
    CheckConstraint("similarity_score >= 0 AND similarity_score <= 1", name="check_similarity_score"),
)

# Indexes for performance optimization
user_progress_user_id_index = Index("idx_user_progress_user_id", user_progress_table.c.user_id)
user_progress_trick_id_index = Index("idx_user_progress_trick_id", user_progress_table.c.trick_id)
learning_sessions_user_id_index = Index("idx_learning_sessions_user_id", learning_sessions_table.c.user_id)
learning_sessions_status_index = Index("idx_learning_sessions_status", learning_sessions_table.c.status)
user_responses_session_id_index = Index("idx_user_responses_session_id", user_responses_table.c.session_id)
user_responses_user_id_index = Index("idx_user_responses_user_id", user_responses_table.c.user_id)
training_statements_difficulty_index = Index("idx_training_statements_difficulty", training_statements_table.c.difficulty)
training_statements_category_index = Index("idx_training_statements_category", training_statements_table.c.category)