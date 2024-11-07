# ChOracle A Discord Chore Bot

## Summary
ChOracle is a sophisticated task management system designed to help communities maintain accountability for regular chores and responsibilities. Through automated reminders and peer verification, it creates a structured yet friendly environment for task completion and verification.

## Core Features
- **Scheduled Reminders**: Create daily, weekly, or monthly reminders for tasks
- **Peer Verification System**: Integrates a peer review system to verify task completion
- **Interactive Reactions**: Use simple emoji reactions for task management
- **Follow-up System**: Automated follow-ups for incomplete tasks
- **Flexible Scheduling**: Support for various time intervals and specific days

## How It Works

### Basic Flow
1. User sets up a reminder for a chore
2. Bot sends reminder at scheduled time
3. User marks task as complete (👍)
4. Peers verify completion
5. Bot schedules next reminder

### Peer Verification Process
1. When a user claims task completion:
   - Bot notifies peers for verification
   - Peers can confirm (👍) or reject (👎) the completion
2. On confirmation:
   - Task is marked complete
   - Next reminder is scheduled
3. On rejection:
   - User is notified to complete the task properly
   - Follow-up reminder is scheduled
   - Bot maintains the reminder cycle

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- Server with a role named "Peer"

### Required Packages
```bash
pip install disnake python-dotenv APScheduler aiosqlite
```

### Environment Setup
1. Create a `.env` file in the bot directory:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```

2. Server Configuration:
   - Create a role named exactly "Peer"
   - Assign the Peer role to trusted members

### Discord Bot Setup
1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application
3. Go to Bot section
4. Enable required Privileged Gateway Intents:
   - PRESENCE INTENT
   - SERVER MEMBERS INTENT
   - MESSAGE CONTENT INTENT
5. Copy bot token for .env file

### Starting the Bot
```bash
main.py
```

## Commands

### /schedule
Create a new chore reminder

**Parameters:**
- `chore_name`: Name of the chore/task
- `schedule_type`: Choose "daily", "weekly", or "monthly"
- `time`: Time in 24-hour format (HH:MM)
- `day`: For weekly (0-6, Monday-Sunday) or monthly (1-31)
- `confirmation_channel`: Optional channel for completion notifications

**Example:**
```
/schedule chore_name:Clean Room schedule_type:weekly time:18:00 day:1
```

### /list_reminders
View all your active reminders

### /delete_reminder
Remove a specific reminder
- Parameter: `chore_name`

### /pause_reminder
Temporarily pause a reminder
- Parameters:
  - `chore_name`
  - `duration_hours` (default: 24)

## User Interaction Guide

### Responding to Reminders
1. When you receive a reminder, react with:
   - 👍 to mark as complete
   - 👎 to postpone by 1 hour

### For Peers
1. When a user marks a task complete:
   - You'll receive a verification request
   - Check the task completion
   - React with 👍 to confirm or 👎 if incomplete

### Task Rejection Flow
If a peer rejects task completion:
1. User receives notification
2. Can react with 👍 when properly completed
3. Receives follow-up reminder after 1 hour
4. Regular reminder cycle continues

## Day Numbering Convention
For weekly schedules:
- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

## Best Practices
1. **Setting Reminders**:
   - Choose appropriate intervals
   - Set realistic times
   - Use clear, descriptive chore names

2. **Peer Verification**:
   - Verify tasks promptly
   - Provide constructive feedback
   - Be consistent with verification standards

3. **Managing Reminders**:
   - Regularly check /list_reminders
   - Remove obsolete reminders
   - Update schedules as needed

## Troubleshooting

### Common Issues
1. **Bot Not Responding**:
   - Check if bot is online
   - Verify bot has proper permissions
   - Ensure intents are enabled

2. **Commands Not Working**:
   - Check command syntax
   - Verify role permissions
   - Ensure bot has necessary permissions

3. **Peer Verification Issues**:
   - Verify "Peer" role exists
   - Check role spelling and case
   - Ensure peers have correct role

### Error Messages
- ❌ "Error: Peer role not found" - Create "Peer" role
- ❌ "Invalid time format" - Use 24-hour format (HH:MM)
- ❌ "Invalid day number" - Check day numbering convention

## Support
For additional support:
1. Check logs in `bot.log`
2. Verify all setup steps
3. Review error messages
4. Check Discord permissions

## Maintenance
1. Regular checks:
   - Monitor bot status
   - Review error logs
   - Update dependencies
2. Database maintenance:
   - Backup chores.db regularly
   - Monitor database size
   - Clean up old entries
