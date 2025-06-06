"""Add learning tables for language tricks system

Revision ID: 002
Revises: 001
Create Date: 2025-01-06 01:31:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Language tricks table
    op.create_table(
        "language_tricks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Training statements table
    op.create_table(
        "training_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("difficulty IN ('легкий', 'средний', 'сложный')", name="check_difficulty"),
    )

    # User progress table
    op.create_table(
        "user_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("trick_id", sa.Integer(), nullable=False),
        sa.Column("mastery_level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correct_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_practiced", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["trick_id"],
            ["language_tricks.id"],
        ),
        sa.UniqueConstraint("user_id", "trick_id", name="unique_user_trick"),
        sa.CheckConstraint("mastery_level >= 0 AND mastery_level <= 100", name="check_mastery_level"),
        sa.CheckConstraint("total_attempts >= 0", name="check_total_attempts"),
        sa.CheckConstraint("correct_attempts >= 0", name="check_correct_attempts"),
        sa.CheckConstraint("correct_attempts <= total_attempts", name="check_correct_vs_total"),
    )

    # Learning sessions table
    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(50), server_default="practice", nullable=False),
        sa.Column("session_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("current_trick_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["training_statements.id"],
        ),
        sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="check_session_status"),
    )

    # User responses table
    op.create_table(
        "user_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("trick_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=False),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("analysis_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["learning_sessions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["trick_id"],
            ["language_tricks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["training_statements.id"],
        ),
        sa.CheckConstraint("similarity_score >= 0 AND similarity_score <= 1", name="check_similarity_score"),
    )

    # Create indexes for performance
    op.create_index("idx_user_progress_user_id", "user_progress", ["user_id"])
    op.create_index("idx_user_progress_trick_id", "user_progress", ["trick_id"])
    op.create_index("idx_learning_sessions_user_id", "learning_sessions", ["user_id"])
    op.create_index("idx_learning_sessions_status", "learning_sessions", ["status"])
    op.create_index("idx_user_responses_session_id", "user_responses", ["session_id"])
    op.create_index("idx_user_responses_user_id", "user_responses", ["user_id"])
    op.create_index("idx_training_statements_difficulty", "training_statements", ["difficulty"])
    op.create_index("idx_training_statements_category", "training_statements", ["category"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_training_statements_category", table_name="training_statements")
    op.drop_index("idx_training_statements_difficulty", table_name="training_statements")
    op.drop_index("idx_user_responses_user_id", table_name="user_responses")
    op.drop_index("idx_user_responses_session_id", table_name="user_responses")
    op.drop_index("idx_learning_sessions_status", table_name="learning_sessions")
    op.drop_index("idx_learning_sessions_user_id", table_name="learning_sessions")
    op.drop_index("idx_user_progress_trick_id", table_name="user_progress")
    op.drop_index("idx_user_progress_user_id", table_name="user_progress")

    # Drop tables in reverse order
    op.drop_table("user_responses")
    op.drop_table("learning_sessions")
    op.drop_table("user_progress")
    op.drop_table("training_statements")
    op.drop_table("language_tricks")
