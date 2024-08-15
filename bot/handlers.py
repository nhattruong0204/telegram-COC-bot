from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .coc_api import fetch_top_clan_trophies

async def check_trophy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_members = fetch_top_clan_trophies()
    if top_members:
        keyboard = [[InlineKeyboardButton(f"{member['name']} ({member['tag']})", callback_data=f"status_{member['tag']}")] for member in top_members]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Top 25 Clan Members", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Failed to fetch top clan members.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Check Trophy", callback_data='check_trophy')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Use the buttons or commands to interact:', reply_markup=reply_markup)
