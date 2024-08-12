import requests
import logging
import os
import html
import sqlite3
from datetime import datetime, timedelta
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
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TEST_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_TEST_CHAT_ID')

if not API_KEY or not CLAN_TAG or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    logging.error("API_KEY, CLAN_TAG, TELEGRAM_TOKEN, or TELEGRAM_CHAT_ID not set. Please check your .env file.")
    exit(1)

# Dictionary to store previous trophies using player tags
previous_trophies = {}

# Initialize database connection
def init_db():
    conn = sqlite3.connect('clash_of_clans.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_stats (
        tag TEXT,
        name TEXT,
        date DATE,
        trophies INTEGER,
        attacks INTEGER DEFAULT 0,
        defends INTEGER DEFAULT 0,
        attack_trophies INTEGER DEFAULT 0,
        defend_trophies INTEGER DEFAULT 0,
        PRIMARY KEY (tag, date)
    )
    ''')
    conn.commit()
    return conn

# Update or insert player data for a specific date
def update_player_data(conn, tag, name, trophies, date, attack_change=0, defend_change=0):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM player_stats WHERE tag = ? AND date = ?', (tag, date))
    result = cursor.fetchone()

    if result:
        attacks, defends, attack_trophies, defend_trophies = result[4], result[5], result[6], result[7]
        if attack_change > 0:
            attacks += 1
            attack_trophies += attack_change
        elif defend_change > 0:
            defends += 1
            defend_trophies += defend_change
        
        cursor.execute('''
            UPDATE player_stats
            SET name = ?, trophies = ?, attacks = ?, defends = ?, attack_trophies = ?, defend_trophies = ?
            WHERE tag = ? AND date = ?
        ''', (name, trophies, attacks, defends, attack_trophies, defend_trophies, tag, date))
    else:
        attacks = 1 if attack_change > 0 else 0
        defends = 1 if defend_change > 0 else 0
        attack_trophies = attack_change if attack_change > 0 else 0
        defend_trophies = defend_change if defend_change > 0 else 0
        cursor.execute('''
            INSERT INTO player_stats (tag, name, date, trophies, attacks, defends, attack_trophies, defend_trophies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tag, name, date, trophies, attacks, defends, attack_trophies, defend_trophies))
    conn.commit()

# Function to fetch top 15 clan members by trophies
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
        
        # Get the top 15 members
        top_members = sorted_members[:15]
        
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
    conn = init_db()
    current_date = datetime.utcnow().date()
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
            attack_change = trophy_difference if trophy_difference > 0 else 0
            defend_change = abs(trophy_difference) if trophy_difference < 0 else 0

            # Update the player data in the database for the current date
            update_player_data(conn, tag, name, trophies, current_date, attack_change, defend_change)

            # Escape any HTML special characters in player name and tag
            safe_name = html.escape(name)
            safe_tag = html.escape(tag)

            # Create and send the trophy change message using HTML formatting
            trophy_change_message = (
                f"<b>{idx}. {safe_name}</b> (Tag: <code>{safe_tag}</code>): <b>{trophies} trophies</b> "
                f"(Change: <i>{trophy_difference}</i>)\n"
                f"<b>Status Table:</b>\n{create_status_table_html(conn, tag, current_date)}"
            )
            logging.debug(f"Sending message: {trophy_change_message}")
            await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=trophy_change_message, parse_mode=ParseMode.HTML)

        # Update the previous trophies using the player's tag
        previous_trophies[tag] = trophies

    if not changes_detected:
        logging.info("No changes detected, no message sent.")

    conn.close()

# Function to create a table-like message for player status with HTML formatting
def create_status_table_html(conn, tag, date):
    cursor = conn.cursor()
    cursor.execute('SELECT attacks, defends, attack_trophies, defend_trophies FROM player_stats WHERE tag = ? AND date = ?', (tag, date))
    result = cursor.fetchone()

    if result:
        attacks, defends, attack_trophies, defend_trophies = result

        # Retrieve detailed attacks and defends data from player_stats table
        cursor.execute('SELECT attack_trophies, defend_trophies FROM player_stats WHERE tag = ? AND date = ?', (tag, date))
        rows = cursor.fetchall()

        # Initialize lists to store individual attack and defend trophy changes
        attack_lines = [row[0] for row in rows if row[0] > 0]
        defend_lines = [row[1] for row in rows if row[1] > 0]

        # Calculate net trophy gain/loss
        net_trophy_gain = attack_trophies - defend_trophies

        # Create a compact table using box-drawing characters
        table_message = f"<pre>"
        table_message += f"╔═══════════════╤═══════════════╗\n"
        table_message += f"║ Attacks: {attack_trophies:^4} │ Defends: {defend_trophies:^4} ║\n"
        table_message += f"╠═══════════════╪═══════════════╣\n"

        # Dynamically add rows for each attack and defense
        for attack, defend in zip(attack_lines, defend_lines):
            table_message += f"║ {str(attack):^13} │ {str(defend):^13} ║\n"

        # Handle cases where there are more attacks or defends than the other
        max_lines = max(len(attack_lines), len(defend_lines))
        for i in range(max_lines - len(attack_lines)):
            table_message += f"║ {'NA':^13} │ {str(defend_lines[i + len(attack_lines)]):^13} ║\n"
        for i in range(max_lines - len(defend_lines)):
            table_message += f"║ {str(attack_lines[i + len(defend_lines)]):^13} │ {'NA':^13} ║\n"

        # Add net gain/loss row
        table_message += f"╠═══════════════╧═══════════════╣\n"
        table_message += f"║ Net Gain: {net_trophy_gain:^5} ║\n"
        table_message += f"╚═══════════════════════════════╝\n"
        table_message += f"</pre>"

        return table_message

    return "<b>No data available for this player.</b>"

# Command handler to check trophy information
async def check_trophy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, trophy_list_message = fetch_top_clan_trophies()
    await update.message.reply_text(trophy_list_message, parse_mode=ParseMode.HTML)

# Command handler to check player status by tag
async def check_player_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Please provide a player tag. Usage: /check_status <player_tag>')
        return
    
    tag = context.args[0].strip()
    conn = init_db()
    current_date = datetime.utcnow().date()
    response_message = create_status_table_html(conn, tag, current_date)
    conn.close()
    await update.message.reply_text(response_message, parse_mode=ParseMode.HTML)

# Function to start the bot and display the check_trophy button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Check Trophy", callback_data='check_trophy')],
        [InlineKeyboardButton("Check Player Status", callback_data='check_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Use the buttons or commands to interact:', reply_markup=reply_markup)

# Callback query handler to process button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'check_trophy':
        _, trophy_list_message = fetch_top_clan_trophies()
        await context.bot.send_message(chat_id=query.message.chat_id, text=trophy_list_message, parse_mode=ParseMode.HTML)
    elif query.data == 'check_status':
        await query.message.reply_text('Please enter the player tag using /check_status <player_tag> command.')

# Function to reset player stats daily at 12:00 PM UTC+7
async def reset_player_stats(application):
    conn = init_db()
    cursor = conn.cursor()
    # Prepare for a new day
    current_date = datetime.utcnow().date()
    new_day_date = current_date + timedelta(days=1)
    
    # Insert initial records for the next day with the current trophies
    cursor.execute('''
    INSERT INTO player_stats (tag, name, date, trophies, attacks, defends, attack_trophies, defend_trophies)
    SELECT tag, name, ?, trophies, 0, 0, 0, 0
    FROM player_stats
    WHERE date = ?
    ''', (new_day_date, current_date))
    conn.commit()
    logging.info("Resetting player stats for a new day.")
    conn.close()

    # Send notification to Telegram
    new_day_message = "NEW LEGEND LEAGUE DAY START"
    await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=new_day_message)

def main():
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()

    # Register command and button handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_trophy", check_trophy))
    application.add_handler(CommandHandler("check_status", check_player_status))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Set up the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_trophy_differences, 'interval', seconds=45, args=[application])
    # Schedule reset of player stats at 12:00 PM UTC+7 daily
    scheduler.add_job(reset_player_stats, 'cron', hour=5, minute=0, args=[application])  # UTC+7 is UTC-2 in cron
    scheduler.start()

    # Run the application
    application.run_polling(timeout=60, drop_pending_updates=True)  # Set polling timeout

if __name__ == "__main__":
    main()
