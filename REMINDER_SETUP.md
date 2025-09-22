# Reminder System Setup

## Overview
The reminder system automatically sends notifications to users who haven't practiced in 7 days. It includes promotional messages about OverX products.

## Features
- **7-day reminder cycle**: Users get reminded 7 days after their last practice or last reminder
- **Smart tracking**: Prevents notification spam by tracking both practice and reminder dates
- **Promotional content**: Includes links to OverX products with UTM tracking
- **Maintainer controls**: Force send reminders and view statistics
- **User controls**: Enable/disable personal reminders
- **Maintainer notifications**: Automatic notifications on bot start/stop with statistics

## Database Migration
Run the migration to create the reminder tracking table:
```bash
alembic upgrade head
```

## Environment Configuration
Add maintainer chat ID to your `.env` file:
```bash
# Maintainer chat ID (your Telegram user ID)
MAINTAINER_CHAT_ID=123456789
```

**Note**: The reminder system runs daily at 12:00 UTC.

Replace with your actual Telegram user ID. To find your ID:
1. Message the bot
2. Check bot logs or use @userinfobot

## Commands

### User Commands
- `/reminders on` - Enable weekly reminders
- `/reminders off` - Disable reminders

### Maintainer Commands
- `/force_reminder` - Force send reminder to yourself
- `/force_reminder all` - Force send reminder to ALL users in database
- `/force_reminder [user_id]` - Force send reminder to specific user
- `/reminder_stats` - View reminder system statistics
- `/maintainer_help` - Show maintainer command help

## How It Works

1. **Practice Tracking**: When a user uses `/learn` or `/continue`, their practice timestamp is updated
2. **Scheduler**: Runs once daily at 12:00 UTC to check for users who need reminders
3. **7-Day Logic**: Sends reminder if:
   - 7+ days since last practice AND
   - 7+ days since last reminder (or never reminded)
4. **Auto-disable**: If user blocks bot, reminders are automatically disabled
5. **Maintainer Notifications**:
   - On bot start: Receives stats about users and reminder system
   - On bot stop: Receives final statistics before shutdown

## Promotional Messages
The system cycles through 3 Russian promotional messages featuring:
- Exchange Rates Pro (Chrome extension)
- Block Website (productivity blocker)
- Belarus Law Support Bot (@belarus_law_support_bot)
- Link to: overx.ai/products with UTM tracking

## Testing

### Test Reminder System
1. Set your user ID as maintainer in `.env` (MAINTAINER_CHAT_ID)
2. Start the bot (you'll receive a startup notification)
3. Use `/force_reminder` to test sending to yourself
4. Check `/reminder_stats` to verify tracking
5. Stop the bot (you'll receive a shutdown notification)

### Simulate 7-Day Cycle
For testing, you can manually update the database:
```sql
UPDATE reminder_tracking
SET last_practice_date = NOW() - INTERVAL '8 days'
WHERE user_id = YOUR_USER_ID;
```

## Monitoring
- Check logs for "Reminder scheduler started" on bot startup
- Use `/reminder_stats` to monitor active users and sent reminders
- Errors are logged with user IDs for debugging

## Troubleshooting

### Reminders Not Sending
1. Check MAINTAINER_CHAT_ID is configured correctly in .env
2. Verify database migration ran successfully
3. Check bot logs for scheduler errors
4. Ensure users have reminders enabled

### User Blocked Bot
- System automatically disables reminders when Telegram returns "bot was blocked" error
- Re-enable with `/reminders on` after unblocking

## Maintenance
- Reminder history is kept in `reminder_tracking` table
- Old reminder data can be cleaned if needed
- Statistics help track engagement