"""Feedback Engine for AI-powered response analysis and feedback generation.

This module handles:
- AI-powered response analysis
- Feedback generation
- Response scoring
- Improvement suggestions
- Prompt management
"""

import json
import logging
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from lang_focus.core.ai_provider import OpenRouterProvider
from lang_focus.learning.trick_engine import TrickEngine, LanguageTrick

logger = logging.getLogger(__name__)


@dataclass
class ResponseAnalysis:
    """Result of AI response analysis."""

    is_correct: bool
    score: float  # 0-100
    feedback: str
    improvements: List[str]
    detected_trick: Optional[str]
    confidence: float
    analysis_data: Dict[str, Any]


@dataclass
class Feedback:
    """Complete feedback for user response."""

    analysis: ResponseAnalysis
    encouragement: str
    examples: List[str]
    tips: List[str]
    next_steps: str


class FeedbackEngine:
    """Provides intelligent feedback using AI."""

    def __init__(self, ai_provider: OpenRouterProvider, trick_engine: TrickEngine, prompts_config_path: str = "config/prompts.yaml"):
        self.ai_provider = ai_provider
        self.trick_engine = trick_engine
        self.prompts_config_path = prompts_config_path
        self._prompts_cache: Optional[Dict[str, Any]] = None

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON content from markdown-formatted response."""
        # Remove markdown code block markers
        response = response.strip()

        # Pattern to match ```json ... ``` or ``` ... ```
        json_pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(1).strip()

        # If no code blocks found, return the original response
        return response

    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from YAML configuration file."""
        if self._prompts_cache is not None:
            return self._prompts_cache

        prompts_file = Path(self.prompts_config_path)
        if not prompts_file.exists():
            raise FileNotFoundError(f"Prompts configuration file not found: {prompts_file}")

        with open(prompts_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._prompts_cache = config.get("prompts", {})
        return self._prompts_cache

    async def analyze_response(self, response: str, target_trick: LanguageTrick, statement: str) -> ResponseAnalysis:
        """Analyze user response using AI."""
        try:
            prompts = self._load_prompts()
            feedback_config = prompts.get("feedback_analysis", {})

            # Get examples for the target trick
            examples = await self.trick_engine.get_random_examples(target_trick.id, count=3)
            examples_text = "\n".join(f"- {example}" for example in examples)

            # Prepare the prompt
            system_prompt = feedback_config.get("system_prompt", "")
            user_prompt_template = feedback_config.get("user_prompt_template", "")

            user_prompt = user_prompt_template.format(
                statement=statement,
                trick_name=target_trick.name,
                trick_definition=target_trick.definition,
                user_response=response,
                examples=examples_text,
            )

            # Call AI provider
            ai_response = await self.ai_provider.get_response(message=user_prompt, system_prompt=system_prompt)

            # Parse AI response
            try:
                # Extract JSON from potential markdown formatting
                clean_json = self._extract_json_from_response(ai_response)
                analysis_data = json.loads(clean_json)

                return ResponseAnalysis(
                    is_correct=analysis_data.get("is_correct", False),
                    score=float(analysis_data.get("score", 0)),
                    feedback=analysis_data.get("feedback", ""),
                    improvements=analysis_data.get("improvements", []),
                    detected_trick=analysis_data.get("detected_trick"),
                    confidence=float(analysis_data.get("score", 0)) / 100,
                    analysis_data=analysis_data,
                )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"AI response was: {ai_response}")

                # Fallback analysis
                return await self._fallback_analysis(response, target_trick, statement)

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return await self._fallback_analysis(response, target_trick, statement)

    async def _fallback_analysis(self, response: str, target_trick: LanguageTrick, statement: str) -> ResponseAnalysis:
        """Fallback analysis when AI fails."""
        # Use trick engine for basic classification
        classification = await self.trick_engine.classify_response(response, target_trick.id)

        is_correct = classification.confidence >= 30.0
        score = classification.confidence

        feedback = f"Анализ выполнен базовым алгоритмом. {classification.explanation}"
        if not is_correct:
            feedback += f" Попробуйте использовать ключевые слова фокуса '{target_trick.name}': {', '.join(target_trick.keywords[:3])}"

        return ResponseAnalysis(
            is_correct=is_correct,
            score=score,
            feedback=feedback,
            improvements=["Используйте больше ключевых слов данного фокуса", "Изучите примеры применения"],
            detected_trick=target_trick.name if is_correct else None,
            confidence=score / 100,
            analysis_data={"fallback": True, "classification": classification},
        )

    async def generate_feedback(self, analysis: ResponseAnalysis, target_trick: LanguageTrick) -> Feedback:
        """Generate comprehensive feedback based on analysis."""
        prompts = self._load_prompts()

        # Get encouragement message
        encouragement = await self._get_encouragement_message(analysis.score, target_trick.name)

        # Get examples for the trick
        examples = await self.trick_engine.get_random_examples(target_trick.id, count=2)

        # Get tips for the specific trick
        tips = await self._get_trick_tips(target_trick.id)

        # Generate next steps
        next_steps = await self._generate_next_steps(analysis, target_trick)

        return Feedback(analysis=analysis, encouragement=encouragement, examples=examples, tips=tips, next_steps=next_steps)

    async def _get_encouragement_message(self, score: float, trick_name: str) -> str:
        """Get appropriate encouragement message based on score."""
        prompts = self._load_prompts()
        encouragement_config = prompts.get("encouragement", {})

        if score >= 70:
            template = encouragement_config.get("high_score", 'Отлично! Вы правильно применили фокус "{trick_name}".')
        elif score >= 40:
            template = encouragement_config.get("medium_score", "Хорошая попытка! Вы на правильном пути.")
        else:
            template = encouragement_config.get("low_score", "Не расстраивайтесь! Изучение фокусов языка требует практики.")

        return template.format(trick_name=trick_name, score=int(score))

    async def _get_trick_tips(self, trick_id: int) -> List[str]:
        """Get specific tips for a trick."""
        prompts = self._load_prompts()
        tips_config = prompts.get("learning_tips", {})

        # Get general tips
        general_tips = tips_config.get("general_tips", [])

        # Get trick-specific tip
        trick_specific_tips = tips_config.get("trick_specific_tips", {})
        specific_tip = trick_specific_tips.get(trick_id, f"Изучите примеры применения фокуса #{trick_id}")

        # Combine and return
        tips = [specific_tip]
        if general_tips:
            tips.extend(general_tips[:2])  # Add 2 general tips

        return tips

    async def _generate_next_steps(self, analysis: ResponseAnalysis, target_trick: LanguageTrick) -> str:
        """Generate next steps recommendation."""
        if analysis.score >= 80:
            return f"Отлично! Переходите к следующему фокусу или практикуйте более сложные утверждения."
        elif analysis.score >= 50:
            return ""
        else:
            return f"Изучите определение и примеры, затем попробуйте снова."

    async def score_response(self, response: str, target_trick: LanguageTrick, statement: str) -> float:
        """Score a response (0-100)."""
        analysis = await self.analyze_response(response, target_trick, statement)
        return analysis.score

    async def suggest_improvements(self, response: str, target_trick: LanguageTrick) -> List[str]:
        """Suggest specific improvements for a response."""
        # Basic improvement suggestions based on trick type
        improvements = []

        response_lower = response.lower()

        # Check for common issues
        if len(response) < 10:
            improvements.append("Сделайте ответ более развернутым")

        # Check for keyword usage
        keyword_found = any(keyword.lower() in response_lower for keyword in target_trick.keywords)
        if not keyword_found:
            improvements.append(f"Используйте ключевые слова фокуса: {', '.join(target_trick.keywords[:3])}")

        # Trick-specific suggestions
        trick_suggestions = {
            1: "Сфокусируйтесь на намерениях и желаниях собеседника",
            2: "Попробуйте заменить ключевое слово на синоним с другой окраской",
            3: "Подумайте о последствиях действия или бездействия",
            4: "Разбейте общее утверждение на конкретные части",
            5: "Найдите общую закономерность или тенденцию",
            6: "Используйте яркое сравнение или метафору",
            7: "Сошлитесь на авторитетное мнение или исследование",
            8: "Задайте вопрос об источнике этого убеждения",
            9: "Определите, что действительно важно в данной ситуации",
            10: "Измените временную или пространственную перспективу",
            11: "Найдите неожиданный положительный эффект",
            12: "Приведите пример исключения из этого правила",
            13: "Оцените само убеждение как концепцию",
            14: "Проверьте, применимо ли это к самому собеседнику",
        }

        if target_trick.id in trick_suggestions:
            improvements.append(trick_suggestions[target_trick.id])

        return improvements[:3]  # Limit to 3 suggestions

    async def get_encouraging_message(self, score: float, attempt_count: int, trick_name: str) -> str:
        """Get encouraging message based on performance."""
        if attempt_count == 1:
            if score >= 70:
                return f"🎉 Отличное начало с фокусом '{trick_name}'!"
            else:
                return f"💪 Первая попытка с '{trick_name}' - продолжайте практиковаться!"

        if score >= 80:
            return f"🏆 Превосходно! Вы мастерски владеете фокусом '{trick_name}'!"
        elif score >= 60:
            return f"👍 Хорошая работа! Фокус '{trick_name}' у вас получается все лучше!"
        elif score >= 40:
            return f"📈 Прогресс есть! Продолжайте изучать '{trick_name}'!"
        else:
            return f"🎯 Не сдавайтесь! Каждая попытка приближает вас к мастерству в '{trick_name}'!"

    async def classify_trick_in_response(self, response: str, available_tricks: List[LanguageTrick]) -> Optional[int]:
        """Classify which trick was used in response using AI."""
        try:
            prompts = self._load_prompts()
            classification_config = prompts.get("trick_classification", {})

            # Prepare tricks list for prompt
            tricks_list = "\n".join([f"{trick.id}. {trick.name} - {trick.definition}" for trick in available_tricks])

            system_prompt = classification_config.get("system_prompt", "")
            user_prompt_template = classification_config.get("user_prompt_template", "")

            user_prompt = user_prompt_template.format(
                statement="", user_response=response, available_tricks=tricks_list  # Not needed for classification
            )

            ai_response = await self.ai_provider.get_response(message=user_prompt, system_prompt=system_prompt)

            # Parse response
            try:
                # Extract JSON from potential markdown formatting
                clean_json = self._extract_json_from_response(ai_response)
                result = json.loads(clean_json)
                trick_id = result.get("detected_trick_id")
                confidence = result.get("confidence", 0)

                # Return trick ID only if confidence is high enough
                return trick_id if confidence >= 50 else None

            except json.JSONDecodeError:
                logger.error(f"Failed to parse trick classification response: {ai_response}")
                return None

        except Exception as e:
            logger.error(f"Error in trick classification: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear prompts cache."""
        self._prompts_cache = None
        logger.info("Feedback engine cache cleared")
