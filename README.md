# Discord Chores Bot

A Discord bot that helps manage and remind users about their chores through scheduled messages and reaction-based confirmations.

## Setup Instructions

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   - Create a `.env` file in the root directory
   - Add your Discord bot token:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```

3. **Create Discord Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to the Bot section
   - Create a bot and copy the token
   - Enable necessary intents (Message Content, Server Members, Reactions)

4. **Run the Bot**
   ```bash
   python main.py
   ```

## Bot Commands

- `/schedule` - Schedule a new chore reminder
  - Parameters:
    - chore_name: Name of the chore
    - schedule_type: daily/weekly/monthly
    - time: Time in HH:MM format
    - day: Day of week (0-6) for weekly or day of month (1-31) for monthly
    - confirmation_channel: Optional channel for completion notifications

- `/list_reminders` - View all your active reminders

## Features

- Customizable reminder schedules (daily, weekly, monthly)
- Reaction-based completion tracking
- Confirmation notifications
- Persistent storage of reminders
- Automatic rescheduling after bot restarts

## File Structure

- `main.py` - Main bot code
- `.env` - Environment variables
- `requirements.txt` - Python dependencies
- `bot.log` - Auto-generated log file
- `chores.db` - SQLite database (auto-generated)

## Notes

- The bot requires Python 3.8 or higher
- Make sure to keep your bot token secret
- The bot must have proper permissions in your Discord server
- Database and log files will be created automatically on first run