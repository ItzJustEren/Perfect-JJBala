import sqlite3

DB_PATH = "pfjjbala.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id TEXT PRIMARY KEY,
            personality TEXT DEFAULT 'شما یک دستیار مفید و رسمی هستید.',
            search_mode INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            chat_id TEXT,
            user_id TEXT,
            personality TEXT DEFAULT 'شما یک دستیار مفید و رسمی هستید.',
            search_mode INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_text TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            memory_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_mood (
            chat_id TEXT,
            user_id TEXT,
            last_mood TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_personality(chat_id: str, user_id: str = None) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT personality FROM user_settings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]
    cursor.execute("SELECT personality FROM chat_settings WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "شما یک دستیار مفید و رسمی هستید."

def set_user_personality(chat_id: str, user_id: str, personality: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (chat_id, user_id, personality) VALUES (?, ?, ?)",
        (chat_id, user_id, personality)
    )
    conn.commit()
    conn.close()

def get_search_mode(chat_id: str, user_id: str = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT search_mode FROM user_settings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        row = cursor.fetchone()
        if row:
            conn.close()
            return bool(row[0])
    cursor.execute("SELECT search_mode FROM chat_settings WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def toggle_search_mode(chat_id: str, user_id: str = None):
    conn = get_connection()
    if user_id:
        current = get_search_mode(chat_id, user_id)
        new_val = 0 if current else 1
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (chat_id, user_id, search_mode) VALUES (?, ?, ?)",
            (chat_id, user_id, new_val)
        )
    else:
        current = get_search_mode(chat_id)
        new_val = 0 if current else 1
        conn.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, search_mode) VALUES (?, ?)",
            (chat_id, new_val)
        )
    conn.commit()
    conn.close()

def save_history(chat_id: str, user_text: str, bot_response: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (chat_id, user_text, bot_response) VALUES (?, ?, ?)",
        (chat_id, user_text, bot_response)
    )
    conn.execute(
        "DELETE FROM chat_history WHERE chat_id = ? AND id NOT IN (SELECT id FROM chat_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT 20)",
        (chat_id, chat_id)
    )
    conn.commit()
    conn.close()

def get_history(chat_id: str, limit: int = 20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_text, bot_response FROM chat_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
        (chat_id, limit)
    )
    rows = cursor.fetchall()[::-1]
    conn.close()
    return [{"user": r[0], "bot": r[1]} for r in rows]

def clear_history(chat_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def add_group(chat_id: str):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO groups (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def get_all_groups():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM groups")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def save_memory(chat_id: str, user_id: str, memory_text: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO long_term_memory (chat_id, user_id, memory_text) VALUES (?, ?, ?)",
        (chat_id, user_id, memory_text)
    )
    conn.commit()
    conn.close()

def get_memories(chat_id: str, user_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT memory_text FROM long_term_memory WHERE chat_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10",
        (chat_id, user_id)
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_mood(chat_id: str, user_id: str, mood: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO user_mood (chat_id, user_id, last_mood) VALUES (?, ?, ?)",
        (chat_id, user_id, mood)
    )
    conn.commit()
    conn.close()

def get_mood(chat_id: str, user_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_mood FROM user_mood WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
