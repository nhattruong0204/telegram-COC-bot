import requests
import logging
import os
import html
import sqlite3
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables from .env file
load_dotenv()

# Retrieve API_KEY, CLAN_TAG, TELEGRAM_TOKEN, and TELEGRAM_CHAT_ID from environment variables
API_KEY = os.getenv('API_KEY')
CLAN_TAG = os.getenv('CLAN_TAG')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not API_KEY or not CLAN_TAG or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    logging.error("API_KEY, CLAN_TAG, TELEGRAM_TOKEN, or TELEGRAM_CHAT_ID not set. Please check your .env file.")
    exit(1)

# Define the UTC-5 timezone
UTC_MINUS_5 = timezone(timedelta(hours=-5))

# Dictionary to store previous trophies using player tags
previous_trophies = {}

# Function to initialize the database with tables for a specific day
def init_db_for_date(date_str):
    conn = sqlite3.connect('clash_of_clans.db')
    cursor = conn.cursor()

    # Create player_events table for the specified date
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS player_events_{date_str} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT,
        name TEXT,
        date DATE,
        time TEXT, -- Store time as a string
        event_type TEXT, -- 'attack' or 'defend'
        trophy_change INTEGER
    )
    ''')

    # Create player_stats table for the specified date
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS player_stats_{date_str} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT,
        name TEXT,
        date DATE,
        total_attacks INTEGER,
        total_defends INTEGER,
        net_gain INTEGER
    )
    ''')

    conn.commit()
    return conn

# Record an event in the database for a specific day
def record_event(conn, date_str, tag, name, datetime, event_type, trophy_change):
    cursor = conn.cursor()
    if event_type == 'defend':
        trophy_change = -trophy_change  # Store defend trophies as negative

    # Split datetime into date and time, and convert time to string
    date = datetime.date()
    time = datetime.strftime('%H:%M:%S')  # Convert time to a string

    cursor.execute(f'''
    INSERT INTO player_events_{date_str} (tag, name, date, time, event_type, trophy_change)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (tag, name, date, time, event_type, trophy_change))
    conn.commit()

    # Update daily stats
    update_daily_stats(conn, date_str, tag, name, date)

# Function to update daily stats in the player_stats table for a specific day
def update_daily_stats(conn, date_str, tag, name, date):
    cursor = conn.cursor()

    # Calculate total attacks, defends, and net gain for the player
    cursor.execute(f'''
    SELECT
        COUNT(CASE WHEN event_type = 'attack' THEN 1 END) AS total_attacks,
        COUNT(CASE WHEN event_type = 'defend' THEN 1 END) AS total_defends,
        SUM(trophy_change) AS net_gain
    FROM player_events_{date_str}
    WHERE tag = ? AND date = ?
    ''', (tag, date))
    result = cursor.fetchone()

    if result:
        total_attacks, total_defends, net_gain = result

        # Check if the player already exists in the player_stats table
        cursor.execute(f'SELECT id FROM player_stats_{date_str} WHERE tag = ? AND date = ?', (tag, date))
        existing_record = cursor.fetchone()

        if existing_record:
            # Update the existing record
            cursor.execute(f'''
            UPDATE player_stats_{date_str}
            SET total_attacks = ?, total_defends = ?, net_gain = ?
            WHERE tag = ? AND date = ?
            ''', (total_attacks, total_defends, net_gain, tag, date))
        else:
            # Insert a new record
            cursor.execute(f'''
            INSERT INTO player_stats_{date_str} (tag, name, date, total_attacks, total_defends, net_gain)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (tag, name, date, total_attacks, total_defends, net_gain))

    conn.commit()

# Function to fetch top 20 clan members by trophies
def fetch_top_clan_trophies():
    logging.info("Fetching clan trophies...")
    url = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG.replace('#', '%23')}"
    headers = {
        'Authorization': f'Bearer {API_KEY}',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses
        logging.debug("Successfully fetched data from API.")
        
        data = response.json()
        members = data.get('memberList', [])
        
        # Sort members by trophies in descending order
        sorted_members = sorted(members, key=lambda member: member['trophies'], reverse=True)
        
        # Get the top 20 members
        top_members = sorted_members[:20]
        
        # Format the trophy list as a table
        trophy_list_message = format_trophy_table(top_members)

        return top_members, trophy_list_message
    
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        return None, "Failed to fetch data due to an HTTP error."
    except requests.exceptions.RequestException as err:
        logging.error(f"Request error occurred: {err}")
        return None, "Failed to fetch data due to a request error."
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None, "An unexpected error occurred."

# Function to format the trophy list as a table with reordered columns
def format_trophy_table(members):
    table_message = "<pre>"
    table_message += "╔═══╤════════╤═════════════════════\n"
    table_message += "║ # │ Trophy │ Name                \n"
    table_message += "╠═══╪════════╪═════════════════════\n"

    for idx, member in enumerate(members, start=1):
        name = member['name'][:25]  # Truncate names to fit within the table
        trophies = member['trophies']
        table_message += f"║{idx:<2} │ {trophies:^7}│ {name:<25}\n"

    table_message += "╚═══╧════════╧═════════════════════\n"
    table_message += "</pre>"

    return table_message

# Function to calculate trophy differences and record attack/defend outcomes
async def check_trophy_differences(application):
    logging.info("Checking for trophy changes...")
    current_datetime = datetime.now(UTC_MINUS_5)  # Use UTC-5 timezone
    date_str = current_datetime.strftime('%m%d')
    conn = init_db_for_date(date_str)
    top_members, _ = fetch_top_clan_trophies()
    if top_members is None:
        logging.error("Failed to fetch data for trophy differences check.")
        return

    changes_detected = False
    
    # Calculate trophy differences and record outcomes
    for idx, member in enumerate(top_members, start=1):
        name = member['name']
        tag = member['tag']
        trophies = member['trophies']
        previous_trophies_count = previous_trophies.get(tag, trophies)
        trophy_difference = trophies - previous_trophies_count

        if trophy_difference != 0:
            changes_detected = True
            
            # Determine if the change was an attack or defend
            event_type = 'attack' if trophy_difference > 0 else 'defend'
            record_event(conn, date_str, tag, name, current_datetime, event_type, abs(trophy_difference))

            # Escape any HTML special characters in player name and tag
            safe_name = html.escape(name)
            safe_tag = html.escape(tag)

            # Create and send the trophy change message using HTML formatting
            trophy_change_message = (
                f"<b>{idx}. {safe_name}</b> (Tag: <code>{safe_tag}</code>): <b>{trophies} trophies</b> "
                f"(Change: <i>{trophy_difference}</i>)\n"
                f"<b>Status Table:</b>\n{create_status_table_html(conn, tag, current_datetime.date(), date_str)}"
            )
            logging.debug(f"Sending message: {trophy_change_message}")
            await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=trophy_change_message, parse_mode=ParseMode.HTML)

        # Update the previous trophies using the player's tag
        previous_trophies[tag] = trophies

    if not changes_detected:
        logging.info("No changes detected, no message sent.")

    conn.close()

# Function to create a table-like message for player status with HTML formatting
def create_status_table_html(conn, tag, date, date_str):
    cursor = conn.cursor()
    cursor.execute(f'SELECT event_type, trophy_change FROM player_events_{date_str} WHERE tag = ? AND date = ?', (tag, date))
    rows = cursor.fetchall()

    # Separate attacks and defends
    attack_lines = [row[1] for row in rows if row[0] == 'attack']
    defend_lines = [row[1] for row in rows if row[0] == 'defend']

    # Calculate total trophies gained and lost
    total_attack_trophies = sum(attack_lines)
    total_defend_trophies = sum(defend_lines)

    # Calculate net trophy gain/loss
    net_trophy_gain = total_attack_trophies + total_defend_trophies

    # Create a compact table using box-drawing characters
    table_message = f"<pre>"
    table_message += f"╔════════════════╤════════════════\n"
    table_message += f"║ Attacks: {total_attack_trophies:^6}│ Defends: {total_defend_trophies:^6} \n"
    table_message += f"╠════════════════╪════════════════\n"

    # Dynamically add rows for each attack and defense
    max_lines = max(len(attack_lines), len(defend_lines))
    for i in range(max_lines):
        attack_value = str(attack_lines[i]) if i < len(attack_lines) else ''
        defend_value = str(defend_lines[i]) if i < len(defend_lines) else ''
        table_message += f"║ {attack_value:^14} │ {defend_value:^14}\n"

    # Add net gain/loss row
    table_message += f"╠════════════════╧════════════════\n"
    table_message += f"║ Net Gain: {net_trophy_gain:^15} \n"
    table_message += f"╚═════════════════════════════════\n"
    table_message += f"</pre>"

    return table_message

# Command handler to check trophy information
async def check_trophy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_members, trophy_list_message = fetch_top_clan_trophies()
    if top_members:
        logging.debug("Top clan members fetched successfully.")
        # Generate buttons for each player
        keyboard = [[InlineKeyboardButton(f"{member['name']} ({member['tag']})", callback_data=f"status_{member['tag']}")] for member in top_members]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the trophy list and buttons to the channel
        await update.message.reply_text(trophy_list_message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        logging.error("Failed to fetch top clan members.")
        await update.message.reply_text("Failed to fetch top clan members.", parse_mode=ParseMode.HTML)

# Function to start the bot and display the check_trophy button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Check Trophy", callback_data='check_trophy')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Use the buttons or commands to interact:', reply_markup=reply_markup)

# Callback query handler to process button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'check_trophy':
        logging.debug("Fetching top clan trophies...")
        top_members, trophy_list_message = fetch_top_clan_trophies()
        if top_members:
            logging.debug("Top clan members fetched successfully.")
            # Generate buttons for each player
            keyboard = [[InlineKeyboardButton(f"{member['name']} ({member['tag']})", callback_data=f"status_{member['tag']}")] for member in top_members]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send the trophy list and buttons to the channel
            await context.bot.send_message(chat_id=query.message.chat_id, text=trophy_list_message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            logging.error("Failed to fetch top clan members.")
            await query.message.reply_text("Failed to fetch top clan members.", parse_mode=ParseMode.HTML)

    elif query.data.startswith('status_'):
        tag = query.data.split('_')[1]
        logging.debug(f"Checking status for player with tag: {tag}")
        conn = init_db()
        current_date = datetime.now(UTC_MINUS_5).date()  # Use UTC-5 timezone
        response_message = create_status_table_html(conn, tag, current_date)
        conn.close()
        await query.message.reply_text(response_message, parse_mode=ParseMode.HTML)

# Function to reset player stats daily at 12:00 PM UTC-5
async def reset_player_stats(application):
    current_datetime = datetime.now(UTC_MINUS_5)  # Use UTC-5 timezone
    date_str = current_datetime.strftime('%m%d')
    new_day_date = current_datetime + timedelta(days=1)
    new_day_str = new_day_date.strftime('%m%d')

    # Initialize new tables for the new day
    conn = init_db_for_date(new_day_str)
    conn.commit()
    logging.info("Resetting player stats for a new day.")
    conn.close()

    # Send notification to Telegram
    formatted_date = new_day_date.strftime("%Y-%m-%d")
    new_day_message = f"NEW LEGEND LEAGUE DAY START: {formatted_date}"
    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=new_day_message)

def main():
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()

    # Register command and button handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_trophy", check_trophy))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Set up the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_trophy_differences, 'interval', seconds=45, args=[application])  # Run every 45 seconds
    # Adjust scheduler for resetting player stats at 12:00 PM UTC+7 daily (which mean 0:00AM UTC -5)
    scheduler.add_job(reset_player_stats, 'cron', hour=0, minute=0, args=[application])  

    scheduler.start()

    # Run the application
    application.run_polling(timeout=60, drop_pending_updates=True)  # Set polling timeout

if __name__ == "__main__":
    main()
