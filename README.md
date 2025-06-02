# Language Focus Learning Bot

A sophisticated Telegram bot for learning Russian language tricks (фокусы языка) - verbal reframing techniques that help change perception and improve communication skills. Built with AI-powered feedback and comprehensive progress tracking.

## 🎭 Features

### Language Learning System
- **14 Language Tricks**: Complete system for learning verbal reframing techniques
- **AI-Powered Feedback**: Intelligent analysis and scoring of user responses using OpenRouter
- **Adaptive Difficulty**: Personalized learning experience based on progress
- **Progress Tracking**: Detailed analytics and mastery level monitoring
- **Interactive Sessions**: Guided practice with real-time feedback
- **Achievement System**: Track learning streaks and milestones

### Technical Features
- **Clean Architecture**: Well-structured, maintainable codebase with clear separation of concerns
- **AI Integration**: Built-in support for OpenRouter API with multiple model options
- **Database Support**: PostgreSQL integration with async operations and migrations
- **Localization**: Multi-language support with easy locale management
- **Keyboard Management**: Dynamic inline and reply keyboard generation
- **Support Bot**: Optional secondary bot for monitoring and support
- **Migration System**: Alembic-based database migration management
- **Extensible Design**: Easy to add new features and handlers
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenRouter API Key (for AI-powered feedback)

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd lang-focus-tg-bot
```

2. **Install dependencies using uv (recommended) or pip:**
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run the setup script:**
```bash
python setup_learning_bot.py
```

This will:
- Apply database migrations
- Load language tricks and training statements
- Validate the setup

5. **Start the bot:**
```bash
python -m lang_focus.main
```

## 🤖 Bot Commands

### Learning Commands
- `/learn` - Start a new learning session
- `/continue` - Resume current learning session
- `/progress` - Show your learning progress
- `/tricks` - Browse all 14 language tricks
- `/stats` - View detailed learning statistics

### General Commands
- `/start` - Welcome message and bot introduction
- `/help` - Show available commands and instructions
- `/about` - Information about the bot

## 🎯 Language Tricks (Фокусы языка)

The bot teaches 14 verbal reframing techniques:

1. **Намерение** - Focus on intentions and desires
2. **Переопределение** - Replace words with different emotional coloring
3. **Последствия** - Point to consequences of actions
4. **Разделение** - Break down statements into specific parts
5. **Объединение** - Find general patterns and trends
6. **Аналогия** - Use comparisons and metaphors
7. **Модель мира** - Reference authoritative opinions
8. **Стратегия реальности** - Question the source of beliefs
9. **Иерархия критериев** - Focus on what's truly important
10. **Изменение размеров фрейма** - Change temporal/spatial perspective
11. **Другой результат** - Find unexpected positive effects
12. **Противоположный пример** - Provide exceptions to rules
13. **Метафрейм** - Evaluate the belief itself as a concept
14. **Применение к себе** - Check if logic applies to the person

## 📚 Learning Process

1. **Start Session**: Begin with `/learn` command
2. **Practice**: Apply language tricks to given statements
3. **Get Feedback**: Receive AI-powered analysis and suggestions
4. **Track Progress**: Monitor your mastery level for each trick
5. **Achieve Mastery**: Reach 80%+ proficiency in all tricks

## ⚙️ Configuration

### Environment Variables

```bash
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token
BOT_NAME="Language Focus Bot"
BOT_VERSION="1.0.0"

# Database
DATABASE_URL=postgresql://user:password@localhost/langfocus

# AI Provider (OpenRouter)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=anthropic/claude-3-sonnet

# Optional: Support Bot
SUPPORT_BOT_TOKEN=your_support_bot_token
SUPPORT_CHAT_ID=your_support_chat_id

# Learning Configuration
LEARNING_SESSION_TIMEOUT=3600
MAX_ATTEMPTS_PER_TRICK=3
MASTERY_THRESHOLD=80
PROMPTS_CONFIG_PATH=config/prompts.yaml
```

### Prompts Configuration

All AI prompts are stored in `config/prompts.yaml` for easy customization:

```yaml
prompts:
  feedback_analysis:
    system_prompt: |
      You are an expert in Russian language tricks...
    user_prompt_template: |
      Analyze this language trick usage...
  encouragement:
    high_score: |
      🎉 Отлично! Вы правильно применили фокус "{trick_name}"...
```

## 📁 Project Structure

```
lang_focus/
├── __init__.py
├── main.py                        # Entry point with click options
├── cli.py                         # CLI commands for migrations and data loading
├── config/
│   ├── __init__.py
│   └── settings.py               # Configuration management
├── core/
│   ├── __init__.py
│   ├── bot.py                    # Main bot class
│   ├── database.py               # Database operations
│   ├── migration_manager.py      # Alembic migration management
│   ├── locale_manager.py         # Localization support
│   ├── keyboard_manager.py       # Keyboard management
│   └── ai_provider.py            # OpenRouter integration
├── learning/                      # Learning system components
│   ├── __init__.py
│   ├── data_loader.py            # Load tricks and statements from JSON
│   ├── session_manager.py        # Learning session orchestration
│   ├── trick_engine.py           # Language trick management
│   ├── feedback_engine.py        # AI-powered feedback system
│   └── progress_tracker.py       # User progress analytics
├── models/
│   ├── __init__.py
│   ├── base.py                   # Base table definitions
│   ├── users.py                  # Users table schema
│   └── learning.py               # Learning-related database models
├── handlers/
│   ├── __init__.py
│   ├── basic.py                  # Basic commands (/start, /help, /about)
│   ├── message.py                # Message handling with AI
│   └── learning.py               # Learning-specific bot handlers
├── support/
│   ├── __init__.py
│   └── bot.py                    # Optional support bot
└── utils/
    ├── __init__.py
    └── helpers.py                # Utility functions

config/
└── prompts.yaml                  # AI prompts configuration

data/
├── language_patterns_json.json   # Language tricks definitions
└── training_statements.json      # Practice statements

alembic/                          # Database migration files
├── env.py                        # Alembic environment configuration
├── script.py.mako               # Migration template
└── versions/                     # Migration version files
    ├── 001_initial_users_table.py
    └── 002_add_learning_tables.py
```

## 🛠️ Development

### CLI Commands

```bash
# Database management
python -m lang_focus.cli db upgrade    # Apply migrations
python -m lang_focus.cli db current    # Show current revision
python -m lang_focus.cli db history    # Show migration history

# Learning data management
python -m lang_focus.cli init-data     # Load learning data from JSON files

# Run the bot
python -m lang_focus.main --debug      # Run with debug logging
python -m lang_focus.main --locale ru  # Run with Russian locale
```

### Adding New Language Tricks

1. Update `data/language_patterns_json.json` with new trick definition
2. Run `python -m lang_focus.cli init-data` to reload data
3. Update prompts in `config/prompts.yaml` if needed

### Customizing AI Feedback

Edit `config/prompts.yaml` to customize:
- Feedback analysis prompts
- Encouragement messages
- Learning tips
- Error messages

## 📊 Learning Analytics

The bot tracks comprehensive learning analytics:

- **Progress per trick**: Mastery level (0-100%)
- **Session statistics**: Duration, attempts, success rate
- **Learning streaks**: Consecutive days of practice
- **Achievement system**: Milestones and badges
- **Performance trends**: Improvement over time

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the configuration examples

## 🎯 Roadmap

- [ ] Voice message support for responses
- [ ] Group learning sessions
- [ ] Advanced analytics dashboard
- [ ] Mobile app integration
- [ ] Multi-language support for tricks
- [ ] Gamification features
- [ ] Export learning progress