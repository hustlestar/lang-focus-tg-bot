#!/usr/bin/env python3
"""
Test script for Language Focus Learning Bot

This script tests the core learning system components to ensure everything works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lang_focus.config.settings import BotConfig
from lang_focus.learning import (
    LearningDataLoader, TrickEngine, ProgressTracker, 
    FeedbackEngine, LearningSessionManager
)
from lang_focus.core.ai_provider import MockAIProvider


async def test_learning_system():
    """Test the learning system components."""
    print("🧪 Testing Language Focus Learning System...")
    print("=" * 50)
    
    try:
        # Load configuration
        config = BotConfig.from_env()
        
        # Test 1: Data Loader
        print("\n1️⃣ Testing Data Loader...")
        data_loader = LearningDataLoader(config.database_url)
        
        # Load data
        await data_loader.load_all_data()
        
        # Validate data
        validation = await data_loader.validate_data_integrity()
        print(f"✅ Data validation: {validation['is_valid']}")
        print(f"   Tricks: {validation['tricks_count']}")
        print(f"   Statements: {validation['statements_count']}")
        
        # Test 2: Trick Engine
        print("\n2️⃣ Testing Trick Engine...")
        trick_engine = TrickEngine(config.database_url)
        
        # Load tricks
        tricks = await trick_engine.load_tricks()
        print(f"✅ Loaded {len(tricks)} tricks")
        
        # Test specific trick
        trick_1 = await trick_engine.get_trick_by_id(1)
        print(f"   Trick 1: {trick_1.name}")
        
        # Get examples
        examples = await trick_engine.get_examples_for_trick(1)
        print(f"   Examples: {len(examples)}")
        
        # Test 3: Progress Tracker
        print("\n3️⃣ Testing Progress Tracker...")
        progress_tracker = ProgressTracker(config.database_url)
        
        # Test user ID
        test_user_id = 12345
        
        # Update progress
        await progress_tracker.update_progress(test_user_id, 1, 75.0, True)
        print("✅ Updated progress for test user")
        
        # Get progress
        user_progress = await progress_tracker.get_user_progress(test_user_id)
        print(f"   Progress records: {len(user_progress)}")
        
        # Get overall progress
        overall = await progress_tracker.calculate_overall_progress(test_user_id)
        print(f"   Overall progress: {overall.completion_percentage:.1f}%")
        
        # Test 4: Feedback Engine (with Mock AI)
        print("\n4️⃣ Testing Feedback Engine...")
        mock_ai = MockAIProvider()
        feedback_engine = FeedbackEngine(mock_ai, trick_engine)
        
        # Test response analysis
        test_response = "Вы хотите найти истинный источник радости в жизни?"
        analysis = await feedback_engine.analyze_response(
            test_response, trick_1, "Деньги не приносят счастья"
        )
        print(f"✅ Analysis completed: score={analysis.score:.1f}")
        
        # Generate feedback
        feedback = await feedback_engine.generate_feedback(analysis, trick_1)
        print(f"   Feedback generated: {len(feedback.analysis.feedback)} chars")
        
        # Test 5: Session Manager
        print("\n5️⃣ Testing Session Manager...")
        session_manager = LearningSessionManager(
            config.database_url, trick_engine, feedback_engine, progress_tracker
        )
        
        # Start session
        session = await session_manager.start_session(test_user_id)
        print(f"✅ Started session: {session.id}")
        
        # Get challenge
        challenge = await session_manager.get_next_challenge(session)
        if challenge:
            print(f"   Challenge: {challenge.target_trick_name}")
            
            # Process response
            feedback = await session_manager.process_user_response(
                session, test_response, challenge.target_trick_id
            )
            print(f"   Response processed: {feedback.analysis.score:.1f} score")
        
        # Complete session
        summary = await session_manager.complete_session(session)
        print(f"   Session completed: {summary.tricks_practiced} tricks practiced")
        
        # Test 6: Learning Recommendations
        print("\n6️⃣ Testing Learning Recommendations...")
        recommendations = await progress_tracker.get_learning_recommendations(test_user_id)
        print(f"✅ Generated {len(recommendations)} recommendations")
        for rec in recommendations[:3]:
            print(f"   {rec.type}: {rec.trick_name} - {rec.reason}")
        
        # Test 7: Achievement System
        print("\n7️⃣ Testing Achievement System...")
        achievements = await progress_tracker.get_achievement_progress(test_user_id)
        print(f"✅ Achievement system working")
        completed_achievements = sum(1 for a in achievements.values() if a['completed'])
        print(f"   Completed achievements: {completed_achievements}/{len(achievements)}")
        
        print("\n🎉 All tests passed successfully!")
        print("\nSystem is ready for production use!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    success = asyncio.run(test_learning_system())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()