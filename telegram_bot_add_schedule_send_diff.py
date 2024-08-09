import requests
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

# Dictionary to store previous trophies using player tags
previous_trophies = {}

# Function to fetch top 15 clan members by trophies
def fetch_top_clan_trophies():
    logging.info("Fetching clan trophies...")
    url = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG.replace('#', '%23')}"
    headers = {
        'Authorization': f'Bearer {API_KEY}',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        logging.debug("Successfully fetched data from API.")
        
        data = response.json()
        members = data.get('memberList', [])
        
        # Sort members by trophies in descending order
        sorted_members = sorted(members, key=lambda member: member['trophies'], reverse=True)
        
        # Get the top 15 members
        top_members = sorted_members[:15]
        
        # Prepare the trophy list message
        trophy_list_message = "Top 15 Clan Members by Trophies:\n"
        for idx, member in enumerate(top_members, start=1):
            name = member['name']
            tag = member['tag']
            trophies = member['trophies']
            trophy_list_message += f"{idx}. {name} (Tag: {tag}): {trophies} trophies\n"

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

# Function to calculate trophy differences and send updates
async def check_trophy_differences(application):
    logging.info("Checking for trophy changes...")
    top_members, _ = fetch_top_clan_trophies()
    if top_members is None:
        logging.error("Failed to fetch data for trophy differences check.")
        return

    trophy_list_message = "Changes in Clan Members' Trophies:\n"
    changes_detected = False
    
    # Calculate trophy differences
    for idx, member in enumerate(top_members, start=1):
        name = member['name']
        tag = member['tag']
        trophies = member['trophies']
        previous_trophies_count = previous_trophies.get(tag, trophies)
        trophy_difference = trophies - previous_trophies_count

        if trophy_difference != 0:
            trophy_list_message += f"{idx}. {name} (Tag: {tag}): {trophies} trophies (Change: {trophy_difference})\n"
            changes_detected = True
        
        # Update the previous trophies using the player's tag
        previous_trophies[tag] = trophies

    if changes_detected:
        logging.info("Changes detected, sending message to Telegram.")
        await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=trophy_list_message)
    else:
        logging.info("No changes detected, no message sent.")

# Command handler to send current trophy list
async def check_trophy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, trophy_list_message = fetch_top_clan_trophies()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=trophy_list_message)

# Function to start the bot and display the check_trophy button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Check Trophy", callback_data='check_trophy')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Press the button to check trophies:', reply_markup=reply_markup)

# Callback query handler to process button presses
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'check_trophy':
        _, trophy_list_message = fetch_top_clan_trophies()
        await context.bot.send_message(chat_id=query.message.chat_id, text=trophy_list_message)

def main():
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Register the start command handler
    application.add_handler(CommandHandler("start", start))

    # Register the button handler
    application.add_handler(CallbackQueryHandler(button_handler))

    # Register the check_trophy command handler
    application.add_handler(CommandHandler("check_trophy", check_trophy))

    # Set up the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_trophy_differences, 'interval', seconds=90, args=[application])
    scheduler.start()

    # Run the application
    application.run_polling()

if __name__ == "__main__":
    main()
