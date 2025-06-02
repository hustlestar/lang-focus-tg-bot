"""Trick Engine for managing language tricks and their application.

This module handles the 14 language tricks (фокусы языка) including:
- Trick data management
- Example generation
- Trick classification
- Difficulty assessment
"""

import json
import logging
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class LanguageTrick:
    """Represents a language trick with all its data."""
    id: int
    name: str
    definition: str
    keywords: List[str]
    examples: Dict[str, List[str]]
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'LanguageTrick':
        """Create LanguageTrick from database row."""
        return cls(
            id=row['id'],
            name=row['name'],
            definition=row['definition'],
            keywords=row['keywords'] if isinstance(row['keywords'], list) else [],
            examples=row['examples'] if isinstance(row['examples'], dict) else {}
        )


@dataclass
class TrickClassification:
    """Result of trick classification."""
    detected_trick_id: Optional[int]
    confidence: float
    explanation: str


class TrickEngine:
    """Manages the 14 language tricks and their application."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._tricks_cache: Dict[int, LanguageTrick] = {}
        self._all_tricks_cache: Optional[List[LanguageTrick]] = None

    async def load_tricks(self) -> List[LanguageTrick]:
        """Load all language tricks from database."""
        if self._all_tricks_cache is not None:
            return self._all_tricks_cache

        conn = await asyncpg.connect(self.database_url)
        try:
            query = """
                SELECT id, name, definition, keywords, examples
                FROM language_tricks
                ORDER BY id
            """
            rows = await conn.fetch(query)
            
            tricks = []
            for row in rows:
                trick = LanguageTrick.from_db_row(dict(row))
                tricks.append(trick)
                self._tricks_cache[trick.id] = trick
            
            self._all_tricks_cache = tricks
            logger.info(f"Loaded {len(tricks)} language tricks")
            return tricks
            
        finally:
            await conn.close()

    async def get_trick_by_id(self, trick_id: int) -> LanguageTrick:
        """Get a specific language trick by ID."""
        if trick_id in self._tricks_cache:
            return self._tricks_cache[trick_id]

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
            
            trick = LanguageTrick.from_db_row(dict(row))
            self._tricks_cache[trick_id] = trick
            return trick
            
        finally:
            await conn.close()

    async def get_examples_for_trick(self, trick_id: int, context: str = "everyday") -> List[str]:
        """Get examples for a specific trick and context."""
        trick = await self.get_trick_by_id(trick_id)
        
        examples = trick.examples.get(context, [])
        if not examples and context != "everyday":
            # Fallback to everyday examples if specific context not found
            examples = trick.examples.get("everyday", [])
        
        return examples

    async def get_random_examples(self, trick_id: int, count: int = 3, context: str = "everyday") -> List[str]:
        """Get random examples for a trick."""
        examples = await self.get_examples_for_trick(trick_id, context)
        
        if not examples:
            return []
        
        # Return random sample, but don't exceed available examples
        sample_size = min(count, len(examples))
        return random.sample(examples, sample_size)

    async def classify_response(self, response: str, target_trick_id: int) -> TrickClassification:
        """Classify which trick was used in the response."""
        # This is a simplified classification - in a real implementation,
        # you might use more sophisticated NLP techniques or AI
        
        target_trick = await self.get_trick_by_id(target_trick_id)
        response_lower = response.lower()
        
        # Check for keywords
        keyword_matches = 0
        total_keywords = len(target_trick.keywords)
        
        for keyword in target_trick.keywords:
            if keyword.lower() in response_lower:
                keyword_matches += 1
        
        # Simple confidence calculation based on keyword matches
        confidence = (keyword_matches / total_keywords) * 100 if total_keywords > 0 else 0
        
        # Check against all tricks to see if another trick might be a better match
        all_tricks = await self.load_tricks()
        best_match_id = target_trick_id
        best_confidence = confidence
        
        for trick in all_tricks:
            if trick.id == target_trick_id:
                continue
                
            trick_keyword_matches = 0
            for keyword in trick.keywords:
                if keyword.lower() in response_lower:
                    trick_keyword_matches += 1
            
            trick_confidence = (trick_keyword_matches / len(trick.keywords)) * 100 if trick.keywords else 0
            
            if trick_confidence > best_confidence:
                best_match_id = trick.id
                best_confidence = trick_confidence

        detected_trick_id = best_match_id if best_confidence > 20 else None
        
        explanation = f"Обнаружено совпадений ключевых слов: {keyword_matches}/{total_keywords}"
        if detected_trick_id != target_trick_id:
            detected_trick = await self.get_trick_by_id(detected_trick_id) if detected_trick_id else None
            if detected_trick:
                explanation += f". Возможно, использован фокус '{detected_trick.name}'"

        return TrickClassification(
            detected_trick_id=detected_trick_id,
            confidence=best_confidence,
            explanation=explanation
        )

    async def suggest_next_trick(self, user_id: int, current_progress: Dict[int, int]) -> int:
        """Suggest the next trick to practice based on user progress."""
        # Load all tricks
        all_tricks = await self.load_tricks()
        
        # Find tricks with lowest mastery levels
        trick_scores = []
        for trick in all_tricks:
            mastery_level = current_progress.get(trick.id, 0)
            trick_scores.append((trick.id, mastery_level))
        
        # Sort by mastery level (ascending) and then by trick ID for consistency
        trick_scores.sort(key=lambda x: (x[1], x[0]))
        
        # Return the trick with lowest mastery
        return trick_scores[0][0]

    async def get_trick_difficulty(self, trick_id: int, user_level: int) -> float:
        """Calculate trick difficulty based on trick complexity and user level."""
        # Difficulty mapping based on trick complexity
        # These values can be adjusted based on actual user performance data
        difficulty_map = {
            1: 0.2,   # Намерение - relatively easy
            2: 0.3,   # Переопределение - easy to medium
            3: 0.4,   # Последствия - medium
            4: 0.5,   # Разделение - medium
            5: 0.6,   # Объединение - medium to hard
            6: 0.4,   # Аналогия - medium (people understand analogies)
            7: 0.7,   # Модель мира - hard
            8: 0.8,   # Стратегия реальности - hard
            9: 0.9,   # Иерархия критериев - very hard
            10: 0.6,  # Изменение размеров фрейма - medium to hard
            11: 0.5,  # Другой результат - medium
            12: 0.7,  # Противоположный пример - hard
            13: 0.8,  # Метафрейм - hard
            14: 0.6   # Применение к себе - medium to hard
        }
        
        base_difficulty = difficulty_map.get(trick_id, 0.5)
        
        # Adjust based on user level (0-100)
        # Higher user level = lower perceived difficulty
        user_factor = 1.0 - (user_level / 200)  # Reduce difficulty by up to 50%
        
        adjusted_difficulty = base_difficulty * user_factor
        return max(0.1, min(1.0, adjusted_difficulty))  # Clamp between 0.1 and 1.0

    async def get_trick_keywords_formatted(self, trick_id: int) -> str:
        """Get formatted keywords for a trick."""
        trick = await self.get_trick_by_id(trick_id)
        return ", ".join(trick.keywords)

    async def get_all_tricks_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all tricks for display purposes."""
        tricks = await self.load_tricks()
        
        summary = []
        for trick in tricks:
            summary.append({
                'id': trick.id,
                'name': trick.name,
                'definition': trick.definition[:100] + "..." if len(trick.definition) > 100 else trick.definition,
                'keyword_count': len(trick.keywords),
                'example_count': sum(len(examples) for examples in trick.examples.values())
            })
        
        return summary

    async def validate_trick_response(self, response: str, trick_id: int) -> Tuple[bool, float, str]:
        """Validate if a response correctly uses the specified trick."""
        if not response or len(response.strip()) < 5:
            return False, 0.0, "Ответ слишком короткий"
        
        classification = await self.classify_response(response, trick_id)
        
        # Consider response valid if confidence is above threshold
        is_valid = classification.confidence >= 30.0
        
        feedback = classification.explanation
        if not is_valid:
            feedback += ". Попробуйте использовать ключевые слова и подходы этого фокуса."
        
        return is_valid, classification.confidence, feedback

    def clear_cache(self) -> None:
        """Clear the tricks cache."""
        self._tricks_cache.clear()
        self._all_tricks_cache = None
        logger.info("Tricks cache cleared")