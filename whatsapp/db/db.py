import sqlite3
import uuid


DB_FILE = "user_sessions.db"


def check_entity_id(user_id: str) -> bool:

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            entity_id TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_connections (
            entity_id TEXT,
            app_name TEXT,
            account_id TEXT,
            UNIQUE(entity_id, app_name)
        )
    """
    )
    conn.commit()

    cursor.execute("SELECT entity_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        return row[0]
    return False


def get_or_create_entity_id(user_id: str) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            entity_id TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_connections (
            entity_id TEXT,
            app_name TEXT,
            account_id TEXT,
            UNIQUE(entity_id, app_name)
        )
    """
    )
    conn.commit()

    cursor.execute("SELECT entity_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        entity_id = row[0]
    else:
        entity_id = f"session-{uuid.uuid4()}"
        cursor.execute(
            "INSERT INTO users (user_id, entity_id) VALUES (?, ?)", (user_id, entity_id)
        )
        conn.commit()

    conn.close()
    return entity_id


def get_app_connections(entity_id: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT app_name, account_id FROM app_connections WHERE entity_id = ?",
        (entity_id,),
    )
    rows = cursor.fetchall()

    conn.close()
    return {row[0]: row[1] for row in rows}


def store_app_connection(entity_id: str, app_name: str, account_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO app_connections (entity_id, app_name, account_id)
        VALUES (?, ?, ?)
    """,
        (entity_id, app_name, account_id),
    )

    conn.commit()
    conn.close()
