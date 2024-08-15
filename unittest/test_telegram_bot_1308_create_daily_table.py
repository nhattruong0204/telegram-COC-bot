import pytest
import asyncio
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import sqlite3
from telegram_bot_1308_create_daily_table import init_db_for_date, reset_player_stats

# Define the UTC-5 timezone
UTC_MINUS_5 = timezone(timedelta(hours=-5))

@pytest.fixture
def setup_db():
    """Fixture to set up a temporary database for testing."""
    conn = sqlite3.connect(':memory:')  # Use an in-memory database for testing
    yield conn
    conn.close()

@pytest.mark.asyncio
async def test_reset_player_stats(setup_db):
    """Test that the reset_player_stats function creates new tables for the next day."""
    conn = setup_db

    with patch('telegram_bot_1308_create_daily_table.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 8, 12, 23, 0, 0, tzinfo=UTC_MINUS_5)

        # Determine the string for the new day's tables
        new_day_str = (mock_datetime.now() + timedelta(days=1)).strftime('%m%d')

        # Initialize the database with tables for the next day
        init_db_for_date(new_day_str)

        # Await the asynchronous function
        await reset_player_stats(conn)

        # Check if new tables for the next day were created
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='player_events_{new_day_str}'")
        new_events_table_exists = cursor.fetchone()

        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='player_stats_{new_day_str}'")
        new_stats_table_exists = cursor.fetchone()

        assert new_events_table_exists is not None, "New player_events table should be created for the next day."
        assert new_stats_table_exists is not None, "New player_stats table should be created for the next day."
