import os
from dotenv import load_dotenv
from bot.telegram_bot import create_bot

def main():
    load_dotenv()
    token = os.getenv('TELEGRAM_TEST_TOKEN')
    chat_id = os.getenv('TELEGRAM_TEST_CHAT_ID')  # Load TELEGRAM_TEST_CHAT_ID
    application = create_bot(token, chat_id)
    application.run_polling()

if __name__ == "__main__":
    main()
