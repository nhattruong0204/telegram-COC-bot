import requests
import logging
import os
import html
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
# Dictionary to record attack and defend statuses and trophies
player_stats = {}

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

# Function to format the trophy list as a table with centralized columns
def format_trophy_table(members):
    table_message = "<pre>"
    table_message += "╔════╤════════════════════════════╤════════════╤══════════╗\n"
    table_message += "║ #  │ Name                       │    Tag     │ Trophies ║\n"
    table_message += "╠════╪════════════════════════════╪════════════╪══════════╣\n"

    for idx, member in enumerate(members, start=1):
        name = member['name'][:25]  # Truncate names to fit within the table
        tag = member['tag']
        trophies = member['trophies']
        table_message += f"║ {idx:<2} │ {name:<25} │ {tag:^10} │ {trophies:^8} ║\n"

    table_message += "╚════╧════════════════════════════╧════════════╧══════════╝\n"
    table_message += "</pre>"

    return table_message

# Function to calculate trophy differences and record attack/defend outcomes
async def check_trophy_differences(application):
    logging.info("Checking for trophy changes...")
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
            
            # Record attack or defend based on trophy difference
            if tag not in player_stats:
                player_stats[tag] = {'attacks': [], 'defends': []}
            
            if trophy_difference > 0:
                player_stats[tag]['attacks'].append(trophy_difference)
            elif trophy_difference < 0:
                player_stats[tag]['defends'].append(abs(trophy_difference))

            # Trim lists to a maximum of 8 entries
            player_stats[tag]['attacks'] = player_stats[tag]['attacks'][-8:]
            player_stats[tag]['defends'] = player_stats[tag]['defends'][-8:]

            # Escape any HTML special characters in player name and tag
            safe_name = html.escape(name)
            safe_tag = html.escape(tag)

            # Create and send the trophy change message using HTML formatting
            trophy_change_message = (
                f"<b>{idx}. {safe_name}</b> (Tag: <code>{safe_tag}</code>): <b>{trophies} trophies</b> "
                f"(Change: <i>{trophy_difference}</i>)\n"
                f"<b>Status Table:</b>\n{create_status_table_html(tag)}"
            )
            logging.debug(f"Sending message: {trophy_change_message}")
            await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=trophy_change_message, parse_mode=ParseMode.HTML)

        # Update the previous trophies using the player's tag
        previous_trophies[tag] = trophies

    if not changes_detected:
        logging.info("No changes detected, no message sent.")

# Function to create a table-like message for player status with HTML formatting
def create_status_table_html(tag):
    stats = player_stats.get(tag, {'attacks': [], 'defends': []})
    attack_lines = stats['attacks']
    defend_lines = stats['defends']

    # Calculate total trophies gained and lost
    total_attack_trophies = sum(trophy for trophy in attack_lines if isinstance(trophy, int))
    total_defend_trophies = -sum(trophy for trophy in defend_lines if isinstance(trophy, int))  # Show as negative

    # Calculate net trophy gain/loss
    net_trophy_gain = total_attack_trophies + total_defend_trophies

    # Fill in with NA if there are fewer than 8 entries
    attack_lines.extend(['NA'] * (8 - len(attack_lines)))
    defend_lines.extend(['NA'] * (8 - len(defend_lines)))

    # Create a compact table using box-drawing characters
    table_message = f"<pre>"
    table_message += f"╔═══════════════╤═══════════════╗\n"
    table_message += f"║ Attacks: {total_attack_trophies:^4} │ Defends: {total_defend_trophies:^4} ║\n"
    table_message += f"╠═══════════════╪═══════════════╣\n"

    for attack, defend in zip(attack_lines, defend_lines):
        table_message += f"║ {str(attack):^13} │ {str(defend):^13} ║\n"

    # Add net gain/loss row
    table_message += f"╠═══════════════╧═══════════════╣\n"
    table_message += f"║ Net Gain: {net_trophy_gain:^5} ║\n"
    table_message += f"╚═══════════════════════════════╝\n"
    table_message += f"</pre>"

    return table_message

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
    response_message = create_status_table_html(tag)
    await update.message.reply_text(response_message, parse_mode=ParseMode.HTML)

# Command handler to check player global ranking by tag
async def check_player_global_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Please provide a player tag. Usage: /check_global_ranking <player_tag>')
        return
    
    tag = context.args[0].strip()
    response_message = fetch_player_global_rank(tag)
    await update.message.reply_text(response_message)

# Function to start the bot and display the check_trophy button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Check Trophy", callback_data='check_trophy')],
        [InlineKeyboardButton("Check Player Status", callback_data='check_status')],
        [InlineKeyboardButton("Check Player Global Ranking", callback_data='check_global_ranking')]
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
    elif query.data == 'check_global_ranking':
        await query.message.reply_text('Please enter the player tag using /check_global_ranking <player_tag> command.')

# Function to reset player stats daily at 12:00 PM UTC+7
def reset_player_stats():
    global player_stats
    logging.info("Resetting player stats for a new day.")
    player_stats = {}

def main():
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()

    # Register command and button handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_trophy", check_trophy))
    application.add_handler(CommandHandler("check_status", check_player_status))
    application.add_handler(CommandHandler("check_global_ranking", check_player_global_ranking))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Set up the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_trophy_differences, 'interval', seconds=90, args=[application])
    # Schedule reset of player stats at 12:00 PM UTC+7 daily
    scheduler.add_job(reset_player_stats, 'cron', hour=5, minute=0)  # UTC+7 is UTC-2 in cron
    scheduler.start()

    # Run the application
    application.run_polling(timeout=60, drop_pending_updates=True)  # Set polling timeout

if __name__ == "__main__":
    main()
