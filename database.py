import sqlite3
from datetime import datetime, timedelta


DB_NAME = "tournament.db"


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            telegram_username TEXT,
            nickname TEXT NOT NULL,
            timezone TEXT NOT NULL,
            game_id TEXT NOT NULL,
            payment TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_application(
    telegram_id,
    telegram_username,
    nickname,
    timezone,
    game_id,
    payment
):
    conn = connect()
    cursor = conn.cursor()

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO applications (
            telegram_id,
            telegram_username,
            nickname,
            timezone,
            game_id,
            payment,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        telegram_username,
        nickname,
        timezone,
        game_id,
        payment,
        "pending",
        created_at
    ))

    application_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return application_id


def get_recent_applications(days=2):
    conn = connect()
    cursor = conn.cursor()

    since = datetime.now() - timedelta(days=days)
    since_string = since.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT
            id,
            telegram_id,
            telegram_username,
            nickname,
            timezone,
            game_id,
            payment,
            status,
            created_at
        FROM applications
        WHERE created_at >= ?
        ORDER BY id DESC
    """, (since_string,))

    applications = cursor.fetchall()

    conn.close()

    return applications


def get_application(application_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            telegram_id,
            telegram_username,
            nickname,
            timezone,
            game_id,
            payment,
            status,
            created_at
        FROM applications
        WHERE id = ?
    """, (application_id,))

    application = cursor.fetchone()

    conn.close()

    return application


def update_application_status(application_id, status):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE applications
        SET status = ?
        WHERE id = ?
    """, (status, application_id))

    conn.commit()
    conn.close()