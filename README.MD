# Clash of Clans Trophy Tracker Bot

This repository contains a Python-based Telegram bot designed to track and report Clash of Clans trophy changes for clan members. The bot uses the Clash of Clans API to fetch data, stores it in a SQLite database, and sends updates via Telegram. The bot is scheduled to check for trophy updates every 45 seconds and reset player stats daily.

## Features

- **Real-time Trophy Tracking**: Fetches and monitors the top 25 clan members' trophies.
- **Database Storage**: Stores daily event data in a SQLite database.
- **Telegram Notifications**: Sends messages to a designated Telegram chat about trophy changes.
- **Daily Stats Reset**: Automatically resets player stats at midnight UTC-5.

## Project Structure
```markdown
clash_bot/
│
├── bot/
│   ├── __init__.py
│   ├── handlers.py
│   ├── scheduler.py
│   ├── database.py
│   ├── coc_api.py
│   ├── utils.py
│   └── telegram_bot.py
│
├── tests/
│   ├── __init__.py
│   ├── test_handlers.py
│   ├── test_scheduler.py
│   ├── test_database.py
│   └── test_coc_api.py
│
├── .env
├── .gitignore
├── README.md
└── main.py
```

- **bot/**: Contains all the modules responsible for the bot's functionality, including handling API requests, managing the database, setting up the scheduler, and interacting with Telegram.
- **tests/**: Contains unit tests for the various modules.

## Installation

1. **Clone the Repository**:
```bash
   git clone https://github.com/yourusername/clash_bot.git
   cd clash_bot
```

2. **Set Up a Virtual Environment** (optional but recommended):
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use \`venv\Scripts\activate\`
```

3. **Install the Required Packages**:
```bash
   pip install -r requirements.txt
```

4. **Set Up Environment Variables**:
   Create a `.env` file in the root directory and add the following:

```dotenv
   TELEGRAM_TEST_TOKEN=your-telegram-bot-token
   TELEGRAM_TEST_CHAT_ID=your-chat-id
   API_KEY=your-clash-of-clans-api-key
   CLAN_TAG=your-clan-tag
```

## Usage

1. **Run the Bot**:
```bash
   python main.py
```

2. **Interacting with the Bot**:
   - Start the bot with the `/start` command in your Telegram chat.
   - Use the provided buttons or `/check_trophy` command to manually fetch and check the top 25 clan members' trophies.

3. **Automated Features**:
   - The bot will automatically check for trophy changes every 45 seconds.
   - Daily stats will be reset automatically at midnight (UTC-5).

## Testing

Unit tests are provided in the `tests/` directory. You can run the tests using:

```bash
python -m unittest discover tests
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Acknowledgments

- Thanks to [Supercell](https://supercell.com/en/) for providing the [Clash of Clans API](https://developer.clashofclans.com/).
- Thanks to the [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library for making it easy to create Telegram bots.

## Author

- **La Nhat Truong** - [nhattruong0204](https://github.com/nhattruong0204, nhattruong0204@gmail.com)

Feel free to reach out for any questions or contributions!