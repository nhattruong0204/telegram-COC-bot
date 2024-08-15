from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from .handlers import start, check_trophy
from .scheduler import setup_scheduler

def create_bot(token, chat_id):
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_trophy", check_trophy, chat_id=chat_id))
    application.add_handler(CallbackQueryHandler(check_trophy))
    setup_scheduler(application, chat_id)
    return application
