#!/usr/bin/env python3
"""
Setup script for Language Focus Learning Bot

This script helps set up the bot by:
1. Running database migrations
2. Loading initial learning data
3. Validating the setup
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lang_focus.config.settings import BotConfig
from lang_focus.core.migration_manager import MigrationManager
from lang_focus.learning import LearningDataLoader


async def setup_bot():
    """Set up the language learning bot."""
    print("🚀 Setting up Language Focus Learning Bot...")
    print("=" * 50)
    
    try:
        # Load configuration
        print("📋 Loading configuration...")
        config = BotConfig.from_env()
        print(f"✅ Configuration loaded for: {config.bot_name}")
        
        # Run database migrations
        print("\n🗄️  Setting up database...")
        migration_manager = MigrationManager(config.database_url)
        
        if migration_manager.has_pending_migrations():
            print("🔄 Applying database migrations...")
            if migration_manager.apply_migrations():
                print("✅ Database migrations applied successfully")
            else:
                print("❌ Database migration failed")
                return False
        else:
            print("✅ Database is up to date")
        
        # Load learning data
        print("\n📚 Loading learning data...")
        loader = LearningDataLoader(config.database_url)
        await loader.load_all_data()
        
        # Validate data
        print("🔍 Validating data integrity...")
        validation = await loader.validate_data_integrity()
        
        print(f"📊 Data Summary:")
        print(f"  • Language tricks: {validation['tricks_count']}")
        print(f"  • Training statements: {validation['statements_count']}")
        print(f"  • Difficulty distribution: {validation['difficulty_distribution']}")
        
        if validation['is_valid']:
            print("✅ All data is valid and ready for use!")
        else:
            print("⚠️  Data validation issues detected:")
            if validation['missing_tricks']:
                print(f"  • Missing tricks: {validation['missing_tricks']}")
            return False
        
        # Final setup check
        print("\n🎯 Setup Summary:")
        print(f"  • Bot Name: {config.bot_name}")
        print(f"  • AI Support: {'✅' if config.has_ai_support else '❌'}")
        print(f"  • Support Bot: {'✅' if config.has_support_bot else '❌'}")
        print(f"  • Database: ✅ Ready")
        print(f"  • Learning Data: ✅ Loaded")
        
        print("\n🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Set your environment variables (see .env.example)")
        print("2. Run the bot: python -m lang_focus.main")
        print("3. Start learning with /learn command")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check your database connection")
        print("2. Ensure all environment variables are set")
        print("3. Verify data files exist in data/ directory")
        return False


def main():
    """Main setup function."""
    success = asyncio.run(setup_bot())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()