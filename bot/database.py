import sqlite3
from datetime import datetime

def init_db_for_date(date_str):
    conn = sqlite3.connect('clash_of_clans.db')
    cursor = conn.cursor()
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS player_events_{date_str} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT, name TEXT, date DATE, time TEXT, event_type TEXT, trophy_change INTEGER
    )''')
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS player_stats_{date_str} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT, name TEXT, date DATE, total_attacks INTEGER, total_defends INTEGER, net_gain INTEGER
    )''')
    conn.commit()
    return conn

def record_event(conn, date_str, tag, name, datetime, event_type, trophy_change):
    cursor = conn.cursor()
    trophy_change = -trophy_change if event_type == 'defend' else trophy_change
    date = datetime.date()
    time = datetime.strftime('%H:%M:%S')
    cursor.execute(f'''
    INSERT INTO player_events_{date_str} (tag, name, date, time, event_type, trophy_change)
    VALUES (?, ?, ?, ?, ?, ?)''', (tag, name, date, time, event_type, trophy_change))
    conn.commit()
    update_daily_stats(conn, date_str, tag, name, date)

def update_daily_stats(conn, date_str, tag, name, date):
    cursor = conn.cursor()
    cursor.execute(f'''
    SELECT COUNT(CASE WHEN event_type = 'attack' THEN 1 END) AS total_attacks,
           COUNT(CASE WHEN event_type = 'defend' THEN 1 END) AS total_defends,
           SUM(trophy_change) AS net_gain
    FROM player_events_{date_str}
    WHERE tag = ? AND date = ?''', (tag, date))
    result = cursor.fetchone()
    if result:
        total_attacks, total_defends, net_gain = result
        cursor.execute(f'''
        INSERT OR REPLACE INTO player_stats_{date_str} (tag, name, date, total_attacks, total_defends, net_gain)
        VALUES (?, ?, ?, ?, ?, ?)''', (tag, name, date, total_attacks, total_defends, net_gain))
    conn.commit()
