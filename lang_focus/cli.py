"""Command-line interface for the Telegram bot template.

This module provides CLI commands for database migration management
and other administrative tasks.
"""

import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from .config.settings import BotConfig
from .core.migration_manager import MigrationManager
from .learning import LearningDataLoader
import asyncio

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Language Focus Telegram Bot CLI."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option("--message", "-m", required=True, help="Migration description")
@click.option("--autogenerate/--no-autogenerate", default=True, help="Auto-generate migration from model changes")
def revision(message: str, autogenerate: bool):
    """Create a new migration revision."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        revision_id = migration_manager.create_migration(message, autogenerate)
        click.echo(f"Created migration revision: {revision_id}")

    except Exception as e:
        click.echo(f"Error creating migration: {e}", err=True)
        sys.exit(1)


@db.command()
@click.option("--target", "-t", default="head", help="Target revision (default: head)")
def upgrade(target: str):
    """Apply migrations to upgrade the database."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        current = migration_manager.get_current_revision()
        click.echo(f"Current revision: {current}")

        if migration_manager.apply_migrations(target):
            new_revision = migration_manager.get_current_revision()
            click.echo(f"Successfully upgraded to revision: {new_revision}")
        else:
            click.echo("Migration failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error applying migrations: {e}", err=True)
        sys.exit(1)


@db.command()
@click.option("--target", "-t", default="-1", help="Target revision (default: -1 for previous)")
def downgrade(target: str):
    """Rollback migrations to downgrade the database."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        current = migration_manager.get_current_revision()
        click.echo(f"Current revision: {current}")

        if migration_manager.rollback_migration(target):
            new_revision = migration_manager.get_current_revision()
            click.echo(f"Successfully downgraded to revision: {new_revision}")
        else:
            click.echo("Rollback failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error rolling back migrations: {e}", err=True)
        sys.exit(1)


@db.command()
def current():
    """Show current migration revision."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        current = migration_manager.get_current_revision()
        head = migration_manager.get_head_revision()

        click.echo(f"Current revision: {current}")
        click.echo(f"Head revision: {head}")

        if migration_manager.has_pending_migrations():
            click.echo("⚠️  Pending migrations detected!")
        else:
            click.echo("✅ Database is up to date")

    except Exception as e:
        click.echo(f"Error checking migration status: {e}", err=True)
        sys.exit(1)


@db.command()
def history():
    """Show migration history."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        history = migration_manager.get_migration_history()

        if not history:
            click.echo("No migrations found")
            return

        click.echo("Migration History:")
        click.echo("-" * 50)

        for migration in history:
            status = "✅ CURRENT" if migration["is_current"] else ""
            click.echo(f"{migration['revision']}: {migration['description']} {status}")

    except Exception as e:
        click.echo(f"Error getting migration history: {e}", err=True)
        sys.exit(1)


@db.command()
@click.option("--revision", "-r", default="head", help="Revision to stamp (default: head)")
def stamp(revision: str):
    """Stamp the database with a specific revision without running migrations."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        if migration_manager.stamp_database(revision):
            click.echo(f"Successfully stamped database with revision: {revision}")
        else:
            click.echo("Stamp operation failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error stamping database: {e}", err=True)
        sys.exit(1)


@db.command()
def status():
    """Show detailed database and migration status."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        current = migration_manager.get_current_revision()
        head = migration_manager.get_head_revision()
        has_pending = migration_manager.has_pending_migrations()

        click.echo("Database Status:")
        click.echo("-" * 30)
        click.echo(f"Database URL: {config.database_url}")
        click.echo(f"Current revision: {current or 'None'}")
        click.echo(f"Head revision: {head or 'None'}")
        click.echo(f"Pending migrations: {'Yes' if has_pending else 'No'}")

        if has_pending:
            click.echo("\n⚠️  Run 'telegram-bot-template db upgrade' to apply pending migrations")
        else:
            click.echo("\n✅ Database is up to date")

    except Exception as e:
        click.echo(f"Error checking database status: {e}", err=True)
        sys.exit(1)


@cli.command()
def migrate():
    """Shortcut command to apply all pending migrations."""
    try:
        config = BotConfig.from_env()
        migration_manager = MigrationManager(config.database_url)

        if not migration_manager.has_pending_migrations():
            click.echo("✅ No pending migrations")
            return

        current = migration_manager.get_current_revision()
        head = migration_manager.get_head_revision()

        click.echo(f"Applying migrations from {current} to {head}...")

        if migration_manager.apply_migrations():
            click.echo("✅ All migrations applied successfully")
        else:
            click.echo("❌ Migration failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error applying migrations: {e}", err=True)
        sys.exit(1)


@cli.command()
def init_data():
    """Initialize learning data from JSON files."""
    async def _init():
        try:
            config = BotConfig.from_env()
            loader = LearningDataLoader(config.database_url)
            
            click.echo("🔄 Loading language tricks and training statements...")
            await loader.load_all_data()
            
            # Validate data integrity
            validation = await loader.validate_data_integrity()
            
            click.echo(f"✅ Data loaded successfully!")
            click.echo(f"📚 Language tricks: {validation['tricks_count']}")
            click.echo(f"💬 Training statements: {validation['statements_count']}")
            click.echo(f"📊 Difficulty distribution: {validation['difficulty_distribution']}")
            
            if validation['is_valid']:
                click.echo("🎉 All data is valid and ready for use!")
            else:
                click.echo("⚠️  Data validation issues detected")
                if validation['missing_tricks']:
                    click.echo(f"Missing tricks: {validation['missing_tricks']}")
                    
        except Exception as e:
            click.echo(f"❌ Error loading data: {e}", err=True)
    
    asyncio.run(_init())


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
