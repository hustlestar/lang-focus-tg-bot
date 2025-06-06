"""Data loader for language tricks and training statements.

This module loads the language patterns and training statements from JSON files
and populates the database with the initial data.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

import asyncpg

from lang_focus.models.learning import language_tricks_table, training_statements_table

logger = logging.getLogger(__name__)


class LearningDataLoader:
    """Loads learning data from JSON files into the database."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.data_dir = Path(__file__).parent.parent.parent / "data"

    async def load_all_data(self) -> None:
        """Load all learning data into the database."""
        try:
            logger.info("Starting to load learning data...")

            # Load language tricks
            await self.load_language_tricks()

            # Load training statements
            await self.load_training_statements()

            logger.info("Successfully loaded all learning data")

        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
            raise

    async def load_language_tricks(self) -> None:
        """Load language tricks from JSON file."""
        tricks_file = self.data_dir / "language_patterns_json.json"

        if not tricks_file.exists():
            raise FileNotFoundError(f"Language tricks file not found: {tricks_file}")

        with open(tricks_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        patterns = data.get("languagePatterns", {}).get("patterns", [])

        if not patterns:
            raise ValueError("No language patterns found in the JSON file")

        conn = await asyncpg.connect(self.database_url)
        try:
            # Check if data already exists
            existing_count = await conn.fetchval("SELECT COUNT(*) FROM language_tricks")
            if existing_count > 0:
                logger.info(f"Language tricks already loaded ({existing_count} records)")
                return

            # Prepare data for insertion
            tricks_data = []
            for pattern in patterns:
                trick_data = {
                    "id": pattern["id"],
                    "name": pattern["name"],
                    "definition": pattern["definition"],
                    "keywords": json.dumps(pattern["keywords"], ensure_ascii=False),
                    "examples": json.dumps(pattern["examples"], ensure_ascii=False),
                }
                tricks_data.append(trick_data)

            # Insert data
            insert_query = """
                INSERT INTO language_tricks (id, name, definition, keywords, examples)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            """

            for trick in tricks_data:
                await conn.execute(insert_query, trick["id"], trick["name"], trick["definition"], trick["keywords"], trick["examples"])

            logger.info(f"Loaded {len(tricks_data)} language tricks")

        finally:
            await conn.close()

    async def load_training_statements(self) -> None:
        """Load training statements from JSON file."""
        statements_file = self.data_dir / "training_statements.json"

        if not statements_file.exists():
            raise FileNotFoundError(f"Training statements file not found: {statements_file}")

        with open(statements_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        statements = data.get("trainingStatements", [])

        if not statements:
            raise ValueError("No training statements found in the JSON file")

        conn = await asyncpg.connect(self.database_url)
        try:
            # Check if data already exists
            existing_count = await conn.fetchval("SELECT COUNT(*) FROM training_statements")
            if existing_count > 0:
                logger.info(f"Training statements already loaded ({existing_count} records)")
                return

            # Insert data
            insert_query = """
                INSERT INTO training_statements (id, statement, category, difficulty)
                VALUES ($1, $2, $3, $4)
            """

            for statement in statements:
                await conn.execute(insert_query, statement["id"], statement["statement"], statement["category"], statement["difficulty"])

            logger.info(f"Loaded {len(statements)} training statements")

        finally:
            await conn.close()

    async def get_trick_by_id(self, trick_id: int) -> Dict[str, Any]:
        """Get a specific language trick by ID."""
        conn = await asyncpg.connect(self.database_url)
        try:
            query = """
                SELECT id, name, definition, keywords, examples
                FROM language_tricks
                WHERE id = $1
            """
            row = await conn.fetchrow(query, trick_id)

            if not row:
                raise ValueError(f"Language trick with ID {trick_id} not found")

            return {
                "id": row["id"],
                "name": row["name"],
                "definition": row["definition"],
                "keywords": row["keywords"],
                "examples": row["examples"],
            }

        finally:
            await conn.close()

    async def get_all_tricks(self) -> List[Dict[str, Any]]:
        """Get all language tricks."""
        conn = await asyncpg.connect(self.database_url)
        try:
            query = """
                SELECT id, name, definition, keywords, examples
                FROM language_tricks
                ORDER BY id
            """
            rows = await conn.fetch(query)

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "definition": row["definition"],
                    "keywords": row["keywords"],
                    "examples": row["examples"],
                }
                for row in rows
            ]

        finally:
            await conn.close()

    async def get_statement_by_id(self, statement_id: int) -> Dict[str, Any]:
        """Get a specific training statement by ID."""
        conn = await asyncpg.connect(self.database_url)
        try:
            query = """
                SELECT id, statement, category, difficulty
                FROM training_statements
                WHERE id = $1
            """
            row = await conn.fetchrow(query, statement_id)

            if not row:
                raise ValueError(f"Training statement with ID {statement_id} not found")

            return {"id": row["id"], "statement": row["statement"], "category": row["category"], "difficulty": row["difficulty"]}

        finally:
            await conn.close()

    async def get_statements_by_difficulty(self, difficulty: str) -> List[Dict[str, Any]]:
        """Get training statements by difficulty level."""
        conn = await asyncpg.connect(self.database_url)
        try:
            query = """
                SELECT id, statement, category, difficulty
                FROM training_statements
                WHERE difficulty = $1
                ORDER BY id
            """
            rows = await conn.fetch(query, difficulty)

            return [
                {"id": row["id"], "statement": row["statement"], "category": row["category"], "difficulty": row["difficulty"]}
                for row in rows
            ]

        finally:
            await conn.close()

    async def get_random_statement(self, difficulty: str = None) -> Dict[str, Any]:
        """Get a random training statement, optionally filtered by difficulty."""
        conn = await asyncpg.connect(self.database_url)
        try:
            if difficulty:
                query = """
                    SELECT id, statement, category, difficulty
                    FROM training_statements
                    WHERE difficulty = $1
                    ORDER BY RANDOM()
                    LIMIT 1
                """
                row = await conn.fetchrow(query, difficulty)
            else:
                query = """
                    SELECT id, statement, category, difficulty
                    FROM training_statements
                    ORDER BY RANDOM()
                    LIMIT 1
                """
                row = await conn.fetchrow(query)

            if not row:
                raise ValueError(f"No training statements found for difficulty: {difficulty}")

            return {"id": row["id"], "statement": row["statement"], "category": row["category"], "difficulty": row["difficulty"]}

        finally:
            await conn.close()

    async def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate the integrity of loaded data."""
        conn = await asyncpg.connect(self.database_url)
        try:
            # Check tricks count
            tricks_count = await conn.fetchval("SELECT COUNT(*) FROM language_tricks")

            # Check statements count
            statements_count = await conn.fetchval("SELECT COUNT(*) FROM training_statements")

            # Check for missing trick IDs (should be 1-14)
            missing_tricks = await conn.fetch(
                """
                SELECT generate_series(1, 14) AS expected_id
                EXCEPT
                SELECT id FROM language_tricks
                ORDER BY expected_id
            """
            )

            # Check difficulty distribution
            difficulty_stats = await conn.fetch(
                """
                SELECT difficulty, COUNT(*) as count
                FROM training_statements
                GROUP BY difficulty
                ORDER BY difficulty
            """
            )

            return {
                "tricks_count": tricks_count,
                "statements_count": statements_count,
                "missing_tricks": [row["expected_id"] for row in missing_tricks],
                "difficulty_distribution": {row["difficulty"]: row["count"] for row in difficulty_stats},
                "is_valid": tricks_count == 14 and len(missing_tricks) == 0 and statements_count > 0,
            }

        finally:
            await conn.close()
