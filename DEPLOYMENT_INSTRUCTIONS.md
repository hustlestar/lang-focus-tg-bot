# Deployment Instructions for Reminder Fix

## Quick Summary
Run these commands on your production server to fix the reminder system:

```bash
# 1. Pull the latest code
git pull origin main

# 2. Apply the migration and test
uv run python apply_reminder_fix.py

# 3. Restart the bot service
sudo systemctl restart lang-focus-bot

# 4. Verify the fix
sudo journalctl -u lang-focus-bot -f --since "1 minute ago"
```

## Important Fix: Reminder Frequency Logic
The corrected logic now ensures users receive reminders **only once every 7 days**, not daily after 7 days of inactivity:
- **Before**: Users who haven't practiced in 7+ days OR haven't been reminded in 7+ days (would send daily)
- **After**: Users who haven't practiced in 7+ days AND haven't been reminded in 7+ days (sends weekly)

## Detailed Step-by-Step Instructions

### Step 1: Update Code on Server
```bash
# Navigate to your bot directory
cd /path/to/your/lang-focus-tg-bot

# Pull the latest changes that include the fix
git pull origin main

# Verify the new files are present
ls -la alembic/versions/005_initialize_reminder_tracking_for_existing_users.py
ls -la apply_reminder_fix.py
```

### Step 2: Apply Migration and Test
```bash
# Run the automated script that applies migration and verifies the fix
uv run python apply_reminder_fix.py
```

This script will:
- Apply migration 005 to create reminder_tracking records for all existing users
- Show you statistics showing the before/after comparison
- Confirm that more users now qualify for reminders

**Expected output should show:**
- Total users: 60+ (your actual user count)
- Users with reminder tracking: Should match total users
- Users with reminders enabled: Should match total users  
- Users qualifying for reminders: Should be much higher than 1

### Step 3: Restart Bot Service
```bash
# Restart the bot to ensure all changes take effect
sudo systemctl restart lang-focus-bot

# Check that it started successfully
sudo systemctl status lang-focus-bot
```

### Step 4: Verify Fix is Working
```bash
# Watch the logs to confirm the fix is working
sudo journalctl -u lang-focus-bot -f --since "1 minute ago"
```

**Look for these log messages:**
- When the next daily reminder runs (at 12:00 UTC), you should see:
  ```
  Found XX users qualifying for reminders
  Starting reminder batch send to XX users
  ```

## Alternative: Manual Application

If the automated script doesn't work, you can apply the fix manually:

```bash
# 1. Apply migration
uv run alembic upgrade 005

# 2. Verify manually
uv run python -c "
import asyncio
from lang_focus.config.settings import BotConfig
from lang_focus.core.database import DatabaseManager
async def check():
    config = BotConfig.from_env()
    db = DatabaseManager(config.database_url)
    await db.setup()
    async with db._pool.acquire() as conn:
        total = await conn.fetchval('SELECT COUNT(*) FROM users')
        tracking = await conn.fetchval('SELECT COUNT(*) FROM reminder_tracking')
        enabled = await conn.fetchval('SELECT COUNT(*) FROM reminder_tracking WHERE reminders_enabled = true')
        print(f'Users: {total}, Tracking: {tracking}, Enabled: {enabled}')
    await db.close()
asyncio.run(check())
"

# 3. Restart bot
sudo systemctl restart lang-focus-bot
```

## Verification Checklist

After deployment, confirm:

- [ ] Migration applied successfully (`alembic current` shows `005`)
- [ ] All users have reminder_tracking records
- [ ] Bot restarts without errors
- [ ] Next daily reminder shows many more users qualifying
- [ ] Users actually receive reminder notifications

## Troubleshooting

### If migration fails:
```bash
# Check current migration status
uv run alembic current

# Check for pending migrations
uv run alembic show

# Force apply specific migration
uv run alembic upgrade 005
```

### If bot won't start:
```bash
# Check logs for errors
sudo journalctl -u lang-focus-bot -n 50

# Check configuration
uv run python -c "from lang_focus.config.settings import BotConfig; print('Config OK')"
```

### If reminders still don't work:
```bash
# Manually test reminder logic
uv run python -c "
import asyncio
from datetime import datetime, timedelta, timezone
from lang_focus.config.settings import BotConfig
from lang_focus.core.database import DatabaseManager
async def test():
    config = BotConfig.from_env()
    db = DatabaseManager(config.database_url)
    await db.setup()
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    async with db._pool.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) FROM reminder_tracking 
            WHERE reminders_enabled = true 
            AND (last_practice_date IS NULL OR last_practice_date <= \$1)
            AND (last_reminder_date IS NULL OR last_reminder_date <= \$1)
        ''', seven_days_ago)
        print(f'Qualifying users: {count}')
    await db.close()
asyncio.run(test())
"
```

## Expected Results

After successful deployment:
- **Before fix**: 1 user qualifying for reminders
- **After fix**: All 60+ users who haven't practiced in 7+ days should qualify
- **Daily reminder logs**: Should show "Found XX users qualifying for reminders" where XX >> 1
- **Users should start receiving**: Reminder notifications at 12:00 UTC daily

The maintainer should see a dramatic increase in reminder notifications being sent, and users should start receiving the practice reminders they were missing.