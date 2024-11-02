# main.py
import os
import sys
import logging
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Union
from collections import namedtuple
import disnake
from disnake.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define ReminderData named tuple for clearer field access
ReminderData = namedtuple('ReminderData', [
    'id', 'user_id', 'channel_id', 'chore_name',
    'schedule_type', 'schedule_value', 'next_reminder',
    'confirmation_channel_id', 'retry_count',
    'last_message_id', 'verification_message_id'
])

# Load and validate environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Validate token
if not TOKEN:
    logger.error("No Discord token found. Please make sure you have created a .env file with DISCORD_TOKEN=your_token_here")
    print("""
ERROR: Discord token not found!

Please create a .env file in the same directory as main.py with the following content:
DISCORD_TOKEN=your_token_here

To get your bot token:
1. Go to https://discord.com/developers/applications
2. Click on your application (or create a new one)
3. Go to the 'Bot' section
4. Click 'Reset Token' or 'Copy' to get your token
5. Paste the token in the .env file as shown above
""")
    sys.exit(1)

# Set up intents explicitly
intents = disnake.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

try:
    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        reload=True
    )
except Exception as e:
    logger.error(f"Failed to initialize bot: {str(e)}")
    print("""
ERROR: Failed to initialize bot. Please make sure you have:
1. Enabled the required intents in the Discord Developer Portal:
   - Go to https://discord.com/developers/applications
   - Select your application
   - Click on 'Bot' in the left sidebar
   - Scroll down to 'Privileged Gateway Intents'
   - Enable:
     * PRESENCE INTENT
     * SERVER MEMBERS INTENT
     * MESSAGE CONTENT INTENT
2. Given the bot the required permissions when adding it to your server
""")
    sys.exit(1)

# Initialize scheduler
scheduler = AsyncIOScheduler()

# Database functions
async def create_tables():
    """Create necessary database tables if they don't exist."""
    async with aiosqlite.connect('chores.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                chore_name TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                next_reminder TIMESTAMP NOT NULL,
                confirmation_channel_id INTEGER,
                retry_count INTEGER DEFAULT 0,
                last_message_id INTEGER,
                verification_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def get_reminder(reminder_id: int) -> Optional[ReminderData]:
    """Get reminder details from database."""
    async with aiosqlite.connect('chores.db') as db:
        cursor = await db.execute('''
            SELECT 
                id, user_id, channel_id, chore_name,
                schedule_type, schedule_value, next_reminder,
                confirmation_channel_id, retry_count,
                last_message_id, verification_message_id
            FROM reminders 
            WHERE id = ?
        ''', (reminder_id,))
        reminder = await cursor.fetchone()
        return ReminderData._make(reminder) if reminder else None

async def add_reminder(
    user_id: int,
    channel_id: int,
    chore_name: str,
    schedule_type: str,
    schedule_value: str,
    confirmation_channel_id: Optional[int] = None
) -> int:
    """Add a new reminder to the database."""
    async with aiosqlite.connect('chores.db') as db:
        next_reminder = calculate_next_reminder(schedule_type, schedule_value)
        cursor = await db.execute('''
            INSERT INTO reminders (
                user_id, channel_id, chore_name, schedule_type, 
                schedule_value, next_reminder, confirmation_channel_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, channel_id, chore_name, schedule_type, 
              schedule_value, next_reminder, confirmation_channel_id))
        await db.commit()
        return cursor.lastrowid

# Reminder calculation and scheduling functions
def calculate_next_reminder(schedule_type: str, schedule_value: str) -> str:
    """Calculate the next reminder time based on schedule type and value."""
    now = datetime.now()
    if schedule_type == "daily":
        hour, minute = map(int, schedule_value.split(':'))
        next_time = now.replace(hour=hour, minute=minute)
        if next_time <= now:
            next_time += timedelta(days=1)
    elif schedule_type == "weekly":
        day_of_week, time = schedule_value.split(',')
        hour, minute = map(int, time.split(':'))
        days_ahead = int(day_of_week) - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_time = now + timedelta(days=days_ahead)
        next_time = next_time.replace(hour=hour, minute=minute)
    else:  # monthly
        day_of_month, time = schedule_value.split(',')
        hour, minute = map(int, time.split(':'))
        next_time = now.replace(day=int(day_of_month), hour=hour, minute=minute)
        if next_time <= now:
            if now.month == 12:
                next_time = next_time.replace(year=now.year + 1, month=1)
            else:
                next_time = next_time.replace(month=now.month + 1)
    
    return next_time.strftime('%Y-%m-%d %H:%M:%S')

async def send_reminder(reminder_id: int) -> None:
    """Send a reminder message and handle reactions."""
    try:
        reminder = await get_reminder(reminder_id)
        if not reminder:
            logger.error(f"Reminder {reminder_id} not found in database")
            return
        
        channel = bot.get_channel(reminder.channel_id)
        if not channel:
            logger.error(f"Channel {reminder.channel_id} not found")
            return
        
        message = await channel.send(
            f"<@{reminder.user_id}> Reminder: Time to do your chore: {reminder.chore_name}! "
            "React with 👍 when done or 👎 if you need to postpone."
        )
        
        await message.add_reaction("👍")
        await message.add_reaction("👎")

        # Update database with message ID
        async with aiosqlite.connect('chores.db') as db:
            await db.execute('''
                UPDATE reminders 
                SET last_message_id = ? 
                WHERE id = ?
            ''', (message.id, reminder_id))
            await db.commit()

    except Exception as e:
        logger.error(f"Error sending reminder {reminder_id}: {str(e)}")

async def send_followup_reminder(reminder_id: int):
    """Send a follow-up reminder after a peer rejection."""
    try:
        reminder = await get_reminder(reminder_id)
        if not reminder:
            logger.error(f"Reminder {reminder_id} not found in database")
            return
        
        channel = bot.get_channel(reminder.channel_id)
        if not channel:
            logger.error(f"Channel {reminder.channel_id} not found")
            return
        
        # Send friendly follow-up message
        follow_up_msg = await channel.send(
            f"⏰ Hey <@{reminder.user_id}>, just checking in!\n\n"
            f"Don't forget to complete your chore: '{reminder.chore_name}'\n"
            "React with 👍 when you're done, and we'll get it verified! 💪"
        )
        
        # Add thumbs up reaction
        await follow_up_msg.add_reaction("👍")
        
        # Update the last_message_id in database
        async with aiosqlite.connect('chores.db') as db:
            await db.execute('''
                UPDATE reminders 
                SET last_message_id = ?
                WHERE id = ?
            ''', (follow_up_msg.id, reminder_id))
            await db.commit()

    except Exception as e:
        logger.error(f"Error sending follow-up reminder {reminder_id}: {str(e)}")

# Event handlers
@bot.event
async def on_ready():
    """Handle bot startup."""
    try:
        await create_tables()
        scheduler.start()
        logger.info(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
        logger.info(f'Connected to {len(bot.guilds)} guilds')
        logger.info('Bot is ready!')
        
        print(f"""
Bot is ready! 

Configuration URLs:
1. Bot Settings: https://discord.com/developers/applications/{bot.user.id}/bot
2. OAuth2 URL: https://discord.com/developers/applications/{bot.user.id}/oauth2
3. Server Invite URL: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=2147483648&scope=bot%20applications.commands

Make sure you have:
1. Enabled all privileged intents in the Bot Settings
2. Added the bot to your server using the Server Invite URL
3. Given the bot the necessary permissions in your server
""")
        
        # Reschedule existing reminders
        async with aiosqlite.connect('chores.db') as db:
            cursor = await db.execute('SELECT id, next_reminder FROM reminders')
            reminders = await cursor.fetchall()
            for reminder_id, next_reminder in reminders:
                scheduler.add_job(
                    send_reminder,
                    'date',
                    run_date=datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S'),
                    args=[reminder_id],
                    id=f"reminder_{reminder_id}"
                )
    except Exception as e:
        logger.error(f"Error in on_ready: {str(e)}")
        print(f"Error during bot startup: {str(e)}")

@bot.event
async def on_reaction_add(reaction: disnake.Reaction, user: disnake.User):
    """Handle reaction responses to reminders."""
    try:
        if user.bot:
            return

        message = reaction.message
        if len(message.mentions) == 0:
            return

        mentioned_user = message.mentions[0]
        # Check if the reaction is from a peer verifying
        is_peer_verification = any(role.name.lower() == "peer" for role in user.roles)
        
        # If it's the original user marking as complete
        if user.id == mentioned_user.id:
            # Only handle reactions on bot's reminder messages
            if message.author.id != bot.user.id:
                return

            async with aiosqlite.connect('chores.db', timeout=30.0) as db:
                cursor = await db.execute('''
                    SELECT 
                        id, chore_name, confirmation_channel_id,
                        schedule_type, schedule_value, retry_count
                    FROM reminders 
                    WHERE user_id = ? AND channel_id = ?
                ''', (mentioned_user.id, message.channel.id))
                reminder = await cursor.fetchone()

                if not reminder:
                    return

                if str(reaction.emoji) == "👍":
                    try:
                        # Get the Peer role mention
                        guild = message.guild
                        peer_role = disnake.utils.get(guild.roles, name="Peer")
                        if not peer_role:
                            await message.channel.send(
                                "❌ Error: Peer role not found. Please make sure a role named 'Peer' exists in the server."
                            )
                            return

                        # Send peer verification request
                        verification_msg = await message.channel.send(
                            f"✨ Let's verify this completion! {peer_role.mention}\n\n"
                            f"Has {mentioned_user.mention} completed their chore: '{reminder[1]}'?\n"
                            f"Please react with 👍 to confirm or 👎 if it's not done correctly!\n\n"
                            "Let's keep each other accountable! 💪"
                        )
                        
                        await verification_msg.add_reaction("👍")
                        await verification_msg.add_reaction("👎")

                        # Store the verification message ID
                        await db.execute('''
                            UPDATE reminders 
                            SET verification_message_id = ?
                            WHERE id = ?
                        ''', (verification_msg.id, reminder[0]))
                        await db.commit()

                    except Exception as e:
                        logger.error(f"Error processing completion claim: {str(e)}")
                        await message.channel.send(
                            "❌ Error processing completion. Please try again or contact an administrator."
                        )

                elif str(reaction.emoji) == "👎":
                    try:
                        # Postpone reminder by 1 hour
                        next_reminder = (datetime.now() + timedelta(hours=1)).strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                        
                        new_retry_count = reminder[5] + 1 if reminder[5] is not None else 1
                        
                        await db.execute('''
                            UPDATE reminders 
                            SET next_reminder = ?, retry_count = ? 
                            WHERE id = ?
                        ''', (next_reminder, new_retry_count, reminder[0]))
                        await db.commit()

                        scheduler.add_job(
                            send_reminder,
                            'date',
                            run_date=datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S'),
                            args=[reminder[0]],
                            id=f"reminder_{reminder[0]}"
                        )

                        await message.channel.send(
                            f"⏰ No worries, {mentioned_user.mention}! Your reminder has been postponed by 1 hour.\n"
                            f"Next reminder: {next_reminder}"
                        )

                    except Exception as e:
                        logger.error(f"Error processing postpone request: {str(e)}")
                        await message.channel.send(
                            "❌ Error postponing reminder. Please try again or contact an administrator."
                        )
# Handle peer verification reactions
        elif is_peer_verification:
            async with aiosqlite.connect('chores.db', timeout=30.0) as db:
                cursor = await db.execute('''
                    SELECT 
                        id, chore_name, schedule_type, schedule_value,
                        verification_message_id
                    FROM reminders 
                    WHERE user_id = ? AND channel_id = ?
                ''', (mentioned_user.id, message.channel.id))
                reminder = await cursor.fetchone()

                if not reminder or reminder[4] != message.id:
                    return

                if str(reaction.emoji) == "👍":
                    try:
                        # Calculate next reminder time
                        next_reminder = calculate_next_reminder(
                            reminder[2],  # schedule_type
                            reminder[3]   # schedule_value
                        )
                        
                        await db.execute('''
                            UPDATE reminders 
                            SET next_reminder = ?, 
                                retry_count = 0,
                                verification_message_id = NULL
                            WHERE id = ?
                        ''', (next_reminder, reminder[0]))
                        await db.commit()

                        # Schedule next reminder
                        job_id = f"reminder_{reminder[0]}"
                        if scheduler.get_job(job_id):
                            scheduler.remove_job(job_id)
                        
                        scheduler.add_job(
                            send_reminder,
                            'date',
                            run_date=datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S'),
                            args=[reminder[0]],
                            id=job_id
                        )

                        await message.channel.send(
                            f"🎉 Awesome! {mentioned_user.mention}'s task completion has been verified by {user.mention}!\n"
                            f"Next reminder scheduled for: {next_reminder}\n"
                            "Keep up the great work! 💪"
                        )

                    except Exception as e:
                        logger.error(f"Error processing peer verification: {str(e)}")
                        await message.channel.send(
                            "❌ Error processing verification. Please try again or contact an administrator."
                        )

                elif str(reaction.emoji) == "👎":
                    try:
                        # Send rejection message with reaction
                        rejection_msg = await message.channel.send(
                            f"👀 Hmm, it looks like the task needs a bit more attention, {mentioned_user.mention}!\n"
                            f"A peer ({user.mention}) has indicated it's not quite complete.\n"
                            "Please make sure everything is done properly and try again! 💪\n"
                            "React with 👍 when done!"
                        )
                        
                        # Add thumbs up reaction
                        await rejection_msg.add_reaction("👍")
                        
                        # Schedule a follow-up reminder in 1 hour
                        next_reminder = (datetime.now() + timedelta(hours=1)).strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                        
                        # Update database with new reminder time and message ID
                        await db.execute('''
                            UPDATE reminders 
                            SET next_reminder = ?,
                                verification_message_id = NULL,
                                last_message_id = ?
                            WHERE id = ?
                        ''', (next_reminder, rejection_msg.id, reminder[0]))
                        await db.commit()

                        # Schedule reminder
                        job_id = f"reminder_{reminder[0]}"
                        if scheduler.get_job(job_id):
                            scheduler.remove_job(job_id)
                        
                        scheduler.add_job(
                            send_reminder,
                            'date',
                            run_date=datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S'),
                            args=[reminder[0]],
                            id=job_id
                        )

                        # Schedule follow-up reminder
                        follow_up_job_id = f"followup_{reminder[0]}"
                        scheduler.add_job(
                            send_followup_reminder,
                            'date',
                            run_date=datetime.now() + timedelta(hours=1),
                            args=[reminder[0]],
                            id=follow_up_job_id
                        )

                    except Exception as e:
                        logger.error(f"Error processing peer rejection: {str(e)}")
                        await message.channel.send(
                            "❌ Error processing verification. Please try again or contact an administrator."
                        )

    except Exception as e:
        logger.error(f"Error handling reaction: {str(e)}")
        try:
            await message.channel.send(
                "❌ An error occurred while processing your reaction. Please try again or contact an administrator."
            )
        except:
            pass

async def update_reminder_time(
    reminder_id: int,
    next_reminder: str,
    retry_count: Optional[int] = None
) -> None:
    """Update the next reminder time in the database."""
    async with aiosqlite.connect('chores.db') as db:
        if retry_count is not None:
            await db.execute('''
                UPDATE reminders 
                SET next_reminder = ?, retry_count = ? 
                WHERE id = ?
            ''', (next_reminder, retry_count, reminder_id))
        else:
            await db.execute('''
                UPDATE reminders 
                SET next_reminder = ?
                WHERE id = ?
            ''', (next_reminder, reminder_id))
        await db.commit()

async def schedule_next_reminder(
    reminder_id: int,
    next_reminder: Union[str, datetime]
) -> None:
    """Schedule the next reminder using APScheduler."""
    if isinstance(next_reminder, str):
        next_reminder = datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S')
    
    job_id = f"reminder_{reminder_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=next_reminder,
        args=[reminder_id],
        id=job_id
    )

@bot.slash_command()
async def schedule(
    inter: disnake.ApplicationCommandInteraction,
    chore_name: str,
    schedule_type: str = commands.Param(
        choices=["daily", "weekly", "monthly"]
    ),
    time: str = commands.Param(description="Time in HH:MM format (24-hour format)"),
    day: Optional[int] = commands.Param(
        description="For weekly: 0=Monday through 6=Sunday. For monthly: day of month (1-31)",
        default=None
    ),
    confirmation_channel: Optional[disnake.TextChannel] = None
):
    """Schedule a new chore reminder."""
    try:
        # Validate time format
        hour, minute = map(int, time.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(
                "Invalid time format. Please use 24-hour format (e.g., 14:30 for 2:30 PM)"
            )

        # Prepare schedule value based on type
        if schedule_type == "daily":
            schedule_value = time
        elif schedule_type == "weekly":
            if day is None:
                await inter.response.send_message(
                    "Please provide a day number (0-6) for weekly reminders:\n"
                    "0 = Monday\n"
                    "1 = Tuesday\n"
                    "2 = Wednesday\n"
                    "3 = Thursday\n"
                    "4 = Friday\n"
                    "5 = Saturday\n"
                    "6 = Sunday"
                )
                return
            if not (0 <= day <= 6):
                await inter.response.send_message(
                    "Invalid day number. Please use:\n"
                    "0 = Monday\n"
                    "1 = Tuesday\n"
                    "2 = Wednesday\n"
                    "3 = Thursday\n"
                    "4 = Friday\n"
                    "5 = Saturday\n"
                    "6 = Sunday"
                )
                return
            schedule_value = f"{day},{time}"
        else:  # monthly
            if day is None or not (1 <= day <= 31):
                await inter.response.send_message(
                    "Please provide a valid day of month (1-31) for monthly reminders."
                )
                return
            schedule_value = f"{day},{time}"

        # Add reminder to database
        reminder_id = await add_reminder(
            inter.author.id,
            inter.channel_id,
            chore_name,
            schedule_type,
            schedule_value,
            confirmation_channel.id if confirmation_channel else None
        )

        # Calculate and schedule next reminder
        next_reminder = calculate_next_reminder(schedule_type, schedule_value)
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=datetime.strptime(next_reminder, '%Y-%m-%d %H:%M:%S'),
            args=[reminder_id],
            id=f"reminder_{reminder_id}"
        )

        # Format response message
        schedule_info = (
            f"Daily at {time}" if schedule_type == "daily"
            else f"Weekly on {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day]} at {time}" if schedule_type == "weekly"
            else f"Monthly on day {day} at {time}"
        )

        await inter.response.send_message(
            f"✅ Reminder '{chore_name}' scheduled!\n"
            f"📅 Schedule: {schedule_info}\n"
            f"⏰ Next reminder: {next_reminder}"
        )

    except ValueError as e:
        await inter.response.send_message(
            f"Error scheduling reminder: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in schedule command: {str(e)}")
        await inter.response.send_message(
            "An error occurred while scheduling the reminder."
        )

@bot.slash_command()
async def list_reminders(inter: disnake.ApplicationCommandInteraction):
    """List all active reminders for the user."""
    try:
        async with aiosqlite.connect('chores.db') as db:
            cursor = await db.execute('''
                SELECT chore_name, schedule_type, schedule_value, next_reminder 
                FROM reminders 
                WHERE user_id = ? 
                ORDER BY next_reminder
            ''', (inter.author.id,))
            reminders = await cursor.fetchall()

        if not reminders:
            await inter.response.send_message("You have no active reminders.")
            return

        reminder_list = "Your active reminders:\n\n"
        for chore, schedule_type, schedule_value, next_reminder in reminders:
            # Format schedule information
            if schedule_type == "daily":
                schedule_info = f"Daily at {schedule_value}"
            elif schedule_type == "weekly":
                day, time = schedule_value.split(',')
                day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][int(day)]
                schedule_info = f"Weekly on {day_name} at {time}"
            else:  # monthly
                day, time = schedule_value.split(',')
                schedule_info = f"Monthly on day {day} at {time}"

            reminder_list += f"• {chore}\n"
            reminder_list += f"  Schedule: {schedule_info}\n"
            reminder_list += f"  Next reminder: {next_reminder}\n\n"

        await inter.response.send_message(reminder_list)
    except Exception as e:
        logger.error(f"Error in list_reminders command: {str(e)}")
        await inter.response.send_message(
            "An error occurred while fetching your reminders."
        )

@bot.slash_command()
async def delete_reminder(
    inter: disnake.ApplicationCommandInteraction,
    chore_name: str
):
    """Delete a specific reminder."""
    try:
        async with aiosqlite.connect('chores.db') as db:
            # Check if reminder exists
            cursor = await db.execute('''
                SELECT id FROM reminders 
                WHERE user_id = ? AND chore_name = ?
            ''', (inter.author.id, chore_name))
            reminder = await cursor.fetchone()

            if not reminder:
                await inter.response.send_message(
                    f"No reminder found with name: {chore_name}"
                )
                return

            # Delete the reminder
            await db.execute('''
                DELETE FROM reminders 
                WHERE id = ?
            ''', (reminder[0],))
            await db.commit()

            # Remove scheduled job if it exists
            job_id = f"reminder_{reminder[0]}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

            # Also remove any follow-up jobs if they exist
            follow_up_job_id = f"followup_{reminder[0]}"
            if scheduler.get_job(follow_up_job_id):
                scheduler.remove_job(follow_up_job_id)

            await inter.response.send_message(
                f"✅ Successfully deleted reminder: {chore_name}"
            )
    except Exception as e:
        logger.error(f"Error in delete_reminder command: {str(e)}")
        await inter.response.send_message(
            "An error occurred while deleting the reminder."
        )

@bot.slash_command()
async def pause_reminder(
    inter: disnake.ApplicationCommandInteraction,
    chore_name: str,
    duration_hours: int = 24
):
    """Pause a reminder for a specified number of hours."""
    try:
        async with aiosqlite.connect('chores.db') as db:
            cursor = await db.execute('''
                SELECT id, next_reminder 
                FROM reminders 
                WHERE user_id = ? AND chore_name = ?
            ''', (inter.author.id, chore_name))
            reminder = await cursor.fetchone()

            if not reminder:
                await inter.response.send_message(
                    f"No reminder found with name: {chore_name}"
                )
                return

            if duration_hours < 1:
                await inter.response.send_message(
                    "Please specify a positive number of hours to pause."
                )
                return

            # Calculate new reminder time
            current_time = datetime.strptime(
                reminder[1],
                '%Y-%m-%d %H:%M:%S'
            )
            new_time = current_time + timedelta(hours=duration_hours)
            
            # Update database and scheduler
            await update_reminder_time(
                reminder[0],
                new_time.strftime('%Y-%m-%d %H:%M:%S')
            )
            await schedule_next_reminder(reminder[0], new_time)

            await inter.response.send_message(
                f"✅ Reminder '{chore_name}' paused for {duration_hours} hours.\n"
                f"⏰ Next reminder: {new_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        logger.error(f"Error in pause_reminder command: {str(e)}")
        await inter.response.send_message(
            "An error occurred while pausing the reminder."
        )

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler for uncaught exceptions."""
    logger.error(f"Uncaught exception in {event}:", exc_info=sys.exc_info())

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        print(f"""
ERROR: Failed to start bot: {str(e)}

Please check:
1. Your Discord token is correct
2. You have an internet connection
3. Discord's services are operational
4. All required intents are enabled in the Discord Developer Portal
""")
        sys.exit(1)