import asyncio
import logging
import random
import re
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties


# =========================================================
# НАСТРОЙКИ
# =========================================================

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

ADMIN_ID = 7146654831

MANAGER_USERNAME = "WesolingManager"
PAYMENT_BAN_USERNAME = "oplatawesoling"
RULES_USERNAME = "WesolingRules"

DB_NAME = "wesoling.db"

CURRENCY_NAME = "WesoCoins"
CURRENCY_SHORT = "WESO"

# Цена покупки WESO за рубли.
# Скидок нет: 1 ₽ = 1 WESO.
WESO_PACKAGES = [
    (100, 100),
    (250, 250),
    (500, 500),
    (1000, 1000),
    (2500, 2500),
    (5000, 5000),
]

# UC: количество UC -> цена в WESO
UC_PRODUCTS = [
    (60, 100),
    (120, 205),
    (180, 310),
    (300, 500),
    (360, 595),
]


# =========================================================
# CUSTOM EMOJI
# =========================================================

EMOJI = {
    1: "5870994129244131212",
    2: "5870755659774955152",
    3: "5870718740236079262",
    4: "5870676941614354370",
    5: "5870684638195748414",
    6: "5870948572526022116",
    7: "5870930744116776638",
    8: "5870886806601338791",
    9: "5870998024779468554",
    10: "5873022839866527761",
    11: "5873225338984599714",
    12: "5870801633104891858",
    13: "5870450390679425417",
    14: "5870478797593120516",
    15: "5870609858520158157",
    16: "5870687545888607770",
    17: "6294238047886118173",
}


def emoji(number: int, fallback: str = "⭐") -> str:
    # Оставляем fallback, как и в предыдущей версии.
    return fallback


# =========================================================
# DB
# =========================================================

def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def column_names(cursor, table_name):
    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )
    return {
        row[1]
        for row in cursor.fetchall()
    }


def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    definition
):
    columns = column_names(
        cursor,
        table_name
    )

    if column_name not in columns:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # =====================================================
    # USERS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)

    add_column_if_missing(
        cursor,
        "users",
        "username",
        "TEXT"
    )

    add_column_if_missing(
        cursor,
        "users",
        "first_name",
        "TEXT"
    )

    add_column_if_missing(
        cursor,
        "users",
        "balance",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "users",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "users",
        "updated_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    # =====================================================
    # TOURNAMENTS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            max_players INTEGER NOT NULL DEFAULT 16,
            format TEXT NOT NULL DEFAULT '1x1',
            ticket_price INTEGER NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    add_column_if_missing(
        cursor,
        "tournaments",
        "max_players",
        "INTEGER NOT NULL DEFAULT 16"
    )

    add_column_if_missing(
        cursor,
        "tournaments",
        "format",
        "TEXT NOT NULL DEFAULT '1x1'"
    )

    add_column_if_missing(
        cursor,
        "tournaments",
        "ticket_price",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "tournaments",
        "status",
        "TEXT DEFAULT 'active'"
    )

    add_column_if_missing(
        cursor,
        "tournaments",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    # =====================================================
    # APPLICATIONS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            tournament_id INTEGER NOT NULL DEFAULT 0,

            user_id INTEGER NOT NULL DEFAULT 0,
            username TEXT,

            nickname TEXT NOT NULL DEFAULT '',
            timezone TEXT NOT NULL DEFAULT '',
            game_id TEXT NOT NULL DEFAULT '',

            nickname2 TEXT NOT NULL DEFAULT '',
            timezone2 TEXT NOT NULL DEFAULT '',
            game_id2 TEXT NOT NULL DEFAULT '',

            payment TEXT NOT NULL DEFAULT '',
            tg_username TEXT NOT NULL DEFAULT '',

            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT '',

            FOREIGN KEY (tournament_id)
            REFERENCES tournaments(id)
        )
    """)

    add_column_if_missing(
        cursor,
        "applications",
        "tournament_id",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "user_id",
        "INTEGER NOT NULL DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "username",
        "TEXT"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "nickname",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "timezone",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "game_id",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "nickname2",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "timezone2",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "game_id2",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "payment",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "tg_username",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "status",
        "TEXT DEFAULT 'pending'"
    )

    add_column_if_missing(
        cursor,
        "applications",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    # =====================================================
    # PASSES
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tournament_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',

            UNIQUE(user_id, tournament_id),

            FOREIGN KEY (tournament_id)
            REFERENCES tournaments(id)
        )
    """)

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL DEFAULT 0,
            transaction_type TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    # =====================================================
    # SHOP / UC ORDERS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            price INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT
        )
    """)

    # =====================================================
    # WESO PURCHASE REQUESTS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS currency_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            rubles INTEGER NOT NULL DEFAULT 0,
            weso INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT
        )
    """)

    # =====================================================
    # OLD DATA
    # =====================================================

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        UPDATE tournaments
        SET created_at = ?
        WHERE created_at IS NULL
        OR created_at = ''
    """, (now,))

    cursor.execute("""
        UPDATE tournaments
        SET status = 'active'
        WHERE status IS NULL
        OR status = ''
    """)

    cursor.execute("""
        UPDATE tournaments
        SET format = '1x1'
        WHERE format IS NULL
        OR format = ''
    """)

    cursor.execute("""
        UPDATE tournaments
        SET ticket_price = 0
        WHERE ticket_price IS NULL
    """)

    conn.commit()
    conn.close()


# =========================================================
# USERS / WALLET
# =========================================================

def ensure_user(
    user_id,
    username=None,
    first_name=None
):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        SELECT user_id
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE users

            SET
                username = ?,
                first_name = ?,
                updated_at = ?

            WHERE user_id = ?
        """, (
            username,
            first_name,
            now,
            user_id
        ))
    else:
        cursor.execute("""
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                balance,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 0, ?, ?)
        """, (
            user_id,
            username,
            first_name,
            now,
            now
        ))

    conn.commit()
    conn.close()


def get_balance(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT balance
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    conn.close()

    if not row:
        return 0

    return row[0]


def change_balance(
    user_id,
    amount,
    transaction_type,
    description
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT balance
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        raise ValueError(
            "Пользователь не найден."
        )

    current_balance = row[0]
    new_balance = current_balance + amount

    if new_balance < 0:
        conn.close()
        raise ValueError(
            "Недостаточно WesoCoins."
        )

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        UPDATE users
        SET
            balance = ?,
            updated_at = ?
        WHERE user_id = ?
    """, (
        new_balance,
        now,
        user_id
    ))

    cursor.execute("""
        INSERT INTO transactions
        (
            user_id,
            amount,
            balance_after,
            transaction_type,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        amount,
        new_balance,
        transaction_type,
        description,
        now
    ))

    conn.commit()
    conn.close()

    return new_balance


def find_user_by_username(username):
    username = username.strip()

    if username.startswith("@"):
        username = username[1:]

    username = username.lower()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            username,
            first_name,
            balance
        FROM users
        WHERE LOWER(username) = ?
        LIMIT 1
    """, (username,))

    row = cursor.fetchone()

    conn.close()

    return row


def get_transactions(user_id, limit=10):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            amount,
            balance_after,
            transaction_type,
            description,
            created_at
        FROM transactions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (
        user_id,
        limit
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# TOURNAMENTS
# =========================================================

def create_tournament(
    name,
    max_players,
    tournament_format,
    ticket_price
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tournaments
        (
            name,
            max_players,
            format,
            ticket_price,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, 'active', ?)
    """, (
        name,
        max_players,
        tournament_format,
        ticket_price,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    tournament_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tournament_id


def get_active_tournaments():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            ticket_price,
            status,
            created_at
        FROM tournaments
        WHERE status = 'active'
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_all_tournaments():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            ticket_price,
            status,
            created_at
        FROM tournaments
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_tournament(tournament_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            ticket_price,
            status,
            created_at
        FROM tournaments
        WHERE id = ?
    """, (tournament_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def delete_tournament(tournament_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM applications
        WHERE tournament_id = ?
    """, (tournament_id,))

    cursor.execute("""
        DELETE FROM passes
        WHERE tournament_id = ?
    """, (tournament_id,))

    cursor.execute("""
        DELETE FROM tournaments
        WHERE id = ?
    """, (tournament_id,))

    conn.commit()
    conn.close()


# =========================================================
# APPLICATIONS
# =========================================================

def get_accepted_players_count(tournament_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE tournament_id = ?
        AND status = 'accepted'
    """, (tournament_id,))

    count = cursor.fetchone()[0]

    conn.close()

    return count


def get_accepted_players(tournament_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            username,

            nickname,
            timezone,
            game_id,

            payment,
            tg_username,

            status,
            created_at,

            nickname2,
            timezone2,
            game_id2

        FROM applications

        WHERE tournament_id = ?
        AND status = 'accepted'

        ORDER BY id ASC
    """, (tournament_id,))

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_pending_applications():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            tournament_id,
            user_id,
            username,

            nickname,
            timezone,
            game_id,

            payment,
            tg_username,

            status,
            created_at,

            nickname2,
            timezone2,
            game_id2

        FROM applications

        WHERE status = 'pending'

        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def user_has_application(
    tournament_id,
    user_id
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            status

        FROM applications

        WHERE tournament_id = ?
        AND user_id = ?

        AND status IN (
            'pending',
            'accepted'
        )

        LIMIT 1
    """, (
        tournament_id,
        user_id
    ))

    row = cursor.fetchone()

    conn.close()

    return row


def game_id_already_used(
    tournament_id,
    game_id
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM applications

        WHERE tournament_id = ?

        AND status IN (
            'pending',
            'accepted'
        )

        AND (
            game_id = ?
            OR game_id2 = ?
        )

        LIMIT 1
    """, (
        tournament_id,
        game_id,
        game_id
    ))

    row = cursor.fetchone()

    conn.close()

    return row is not None


def save_application(
    tournament_id,
    user_id,
    username,

    nickname,
    timezone,
    game_id,

    tg_username,

    nickname2="",
    timezone2="",
    game_id2=""
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO applications
        (
            tournament_id,
            user_id,
            username,

            nickname,
            timezone,
            game_id,

            payment,
            tg_username,

            nickname2,
            timezone2,
            game_id2,

            status,
            created_at
        )

        VALUES (
            ?, ?, ?,
            ?, ?, ?,
            '', ?,
            ?, ?, ?,
            'pending', ?
        )
    """, (
        tournament_id,
        user_id,
        username,

        nickname,
        timezone,
        game_id,

        tg_username,

        nickname2,
        timezone2,
        game_id2,

        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    application_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return application_id


def get_application(application_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            tournament_id,
            user_id,
            username,

            nickname,
            timezone,
            game_id,

            payment,
            tg_username,

            status,
            created_at,

            nickname2,
            timezone2,
            game_id2

        FROM applications

        WHERE id = ?
    """, (application_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def update_application_status(
    application_id,
    status
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE applications
        SET status = ?
        WHERE id = ?
    """, (
        status,
        application_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# PASSES
# =========================================================

def get_pass_count(
    user_id,
    tournament_id
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT quantity
        FROM passes
        WHERE user_id = ?
        AND tournament_id = ?
    """, (
        user_id,
        tournament_id
    ))

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else 0


def add_pass(
    user_id,
    tournament_id,
    quantity=1
):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        SELECT quantity
        FROM passes
        WHERE user_id = ?
        AND tournament_id = ?
    """, (
        user_id,
        tournament_id
    ))

    row = cursor.fetchone()

    if row:
        cursor.execute("""
            UPDATE passes
            SET quantity = quantity + ?
            WHERE user_id = ?
            AND tournament_id = ?
        """, (
            quantity,
            user_id,
            tournament_id
        ))
    else:
        cursor.execute("""
            INSERT INTO passes
            (
                user_id,
                tournament_id,
                quantity,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            tournament_id,
            quantity,
            now
        ))

    conn.commit()
    conn.close()


def consume_pass(
    user_id,
    tournament_id
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT quantity
        FROM passes
        WHERE user_id = ?
        AND tournament_id = ?
    """, (
        user_id,
        tournament_id
    ))

    row = cursor.fetchone()

    if not row or row[0] <= 0:
        conn.close()
        return False

    cursor.execute("""
        UPDATE passes
        SET quantity = quantity - 1
        WHERE user_id = ?
        AND tournament_id = ?
    """, (
        user_id,
        tournament_id
    ))

    conn.commit()
    conn.close()

    return True


# =========================================================
# SHOP ORDERS
# =========================================================

def create_shop_order(
    user_id,
    item_type,
    item_name,
    amount,
    price
):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        INSERT INTO shop_orders
        (
            user_id,
            item_type,
            item_name,
            amount,
            price,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (
        user_id,
        item_type,
        item_name,
        amount,
        price,
        now
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_pending_shop_orders():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            item_type,
            item_name,
            amount,
            price,
            status,
            created_at
        FROM shop_orders
        WHERE status = 'pending'
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_shop_order(order_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            item_type,
            item_name,
            amount,
            price,
            status,
            created_at
        FROM shop_orders
        WHERE id = ?
    """, (order_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def update_shop_order_status(
    order_id,
    status
):
    conn = get_db()
    cursor = conn.cursor()

    completed_at = None

    if status == "completed":
        completed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    cursor.execute("""
        UPDATE shop_orders
        SET
            status = ?,
            completed_at = ?
        WHERE id = ?
    """, (
        status,
        completed_at,
        order_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# CURRENCY ORDERS
# =========================================================

def create_currency_order(
    user_id,
    rubles,
    weso
):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        INSERT INTO currency_orders
        (
            user_id,
            rubles,
            weso,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        rubles,
        weso,
        now
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_pending_currency_orders():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            rubles,
            weso,
            status,
            created_at
        FROM currency_orders
        WHERE status = 'pending'
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_currency_order(order_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            rubles,
            weso,
            status,
            created_at
        FROM currency_orders
        WHERE id = ?
    """, (order_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def update_currency_order_status(
    order_id,
    status
):
    conn = get_db()
    cursor = conn.cursor()

    completed_at = None

    if status == "completed":
        completed_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    cursor.execute("""
        UPDATE currency_orders
        SET
            status = ?,
            completed_at = ?
        WHERE id = ?
    """, (
        status,
        completed_at,
        order_id
    ))

    conn.commit()
    conn.close()


# =========================================================
# VALIDATION
# =========================================================

def is_valid_telegram_username(
    username
):
    if not username:
        return False

    if not username.startswith("@"):
        return False

    if username.startswith("@@"):
        return False

    value = username[1:]

    if len(value) < 1 or len(value) > 32:
        return False

    if not re.fullmatch(
        r"[A-Za-z0-9_]+",
        value
    ):
        return False

    return True


def is_digits_only(value):
    return bool(
        re.fullmatch(r"\d+", value)
    )


# =========================================================
# FSM
# =========================================================

class Registration(StatesGroup):
    tournament = State()

    nickname = State()
    timezone = State()
    game_id = State()

    nickname2 = State()
    timezone2 = State()
    game_id2 = State()

    tg_username = State()


class CreateTournament(StatesGroup):
    name = State()
    format = State()
    max_players = State()
    ticket_price = State()


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================================================
# HELPERS
# =========================================================

def admin_only(user_id):
    return user_id == ADMIN_ID


def format_tournament(tournament):
    (
        tournament_id,
        name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    return {
        "id": tournament_id,
        "name": name,
        "max_players": max_players,
        "format": tournament_format,
        "ticket_price": ticket_price,
        "status": status,
        "created_at": created_at,
    }


def tournament_button(
    tournament,
    prefix
):
    (
        tournament_id,
        name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    players = get_accepted_players_count(
        tournament_id
    )

    format_text = (
        "2×2"
        if tournament_format == "2x2"
        else "1×1"
    )

    if tournament_format == "2x2":
        count_text = (
            f"{players}/{max_players} команд"
        )
    else:
        count_text = (
            f"{players}/{max_players}"
        )

    return InlineKeyboardButton(
        text=(
            f"🏆 {name} "
            f"[{format_text}] "
            f"({count_text})"
        ),
        callback_data=(
            f"{prefix}:{tournament_id}"
        )
    )


def shop_main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎟️ Проходки",
                    callback_data="shop_passes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 UC",
                    callback_data="shop_uc"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Купить WesoCoins",
                    callback_data="shop_buy_weso"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 История",
                    callback_data="shop_history"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Баланс",
                    callback_data="shop_balance"
                )
            ]
        ]
    )


# =========================================================
# COMMANDS
# =========================================================

async def setup_commands():
    commands = [
        BotCommand(
            command="start",
            description="Запуск бота"
        ),
        BotCommand(
            command="help",
            description="Поддержка"
        ),
        BotCommand(
            command="reg",
            description="Регистрация"
        ),
        BotCommand(
            command="shop",
            description="Магазин Wesoling"
        ),
        BotCommand(
            command="balance",
            description="Баланс WesoCoins"
        ),
        BotCommand(
            command="rules",
            description="Правила"
        ),
        BotCommand(
            command="list",
            description="Список участников"
        ),
        BotCommand(
            command="setka",
            description="Сетка турнира"
        ),
        BotCommand(
            command="admin",
            description="Админ-панель"
        ),
    ]

    await bot.set_my_commands(commands)


# =========================================================
# /START
# =========================================================

@dp.message(Command("start"))
async def start_command(
    message: Message
):
    ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    text = (
        f"{emoji(6, '👋')} "
        "<b>Добро пожаловать "
        "в Wesoling Tournament!</b>\n\n"

        "Это бот поддержки турниров "
        "по PUBG Mobile.\n\n"

        "🏆 Турниры\n"
        "🪙 WesoCoins\n"
        "🛒 Магазин\n"
        "🎮 UC\n"
        "🎟️ Проходки\n\n"

        "Основные команды:\n\n"

        "📝 /reg — регистрация\n"
        "🛒 /shop — магазин\n"
        "💰 /balance — баланс\n"
        "📖 /rules — правила\n"
        "❓ /help — поддержка"
    )

    await message.answer(text)


# =========================================================
# /HELP
# =========================================================

@dp.message(Command("help"))
async def help_command(
    message: Message
):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать менеджеру",
                    url=(
                        f"https://t.me/"
                        f"{MANAGER_USERNAME}"
                    )
                )
            ]
        ]
    )

    await message.answer(
        "Если у тебя возник вопрос "
        "по поводу турнира, обратись "
        "к менеджеру.\n\n"

        "<i>Здравствуйте, возник вопрос "
        "по поводу турнира.</i>",
        reply_markup=keyboard
    )


# =========================================================
# /RULES
# =========================================================

@dp.message(Command("rules"))
async def rules_command(
    message: Message
):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Открыть правила",
                    url=(
                        f"https://t.me/"
                        f"{RULES_USERNAME}"
                    )
                )
            ]
        ]
    )

    await message.answer(
        "Правила турнира находятся "
        "в нашем официальном канале.",
        reply_markup=keyboard
    )


# =========================================================
# /BALANCE
# =========================================================

@dp.message(Command("balance"))
async def balance_command(
    message: Message
):
    ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    parts = message.text.split()

    if (
        admin_only(message.from_user.id)
        and len(parts) >= 2
    ):
        target = find_user_by_username(
            parts[1]
        )

        if not target:
            await message.answer(
                "❌ Пользователь с таким "
                "username не найден в базе."
            )
            return

        user_id, username, first_name, balance = target

        await message.answer(
            "💰 <b>Баланс</b>\n\n"
            f"👤 @{username}\n"
            f"🪙 {balance} {CURRENCY_SHORT}"
        )
        return

    balance = get_balance(
        message.from_user.id
    )

    await message.answer(
        "💰 <b>Ваш баланс</b>\n\n"
        f"🪙 <b>{balance}</b> "
        f"{CURRENCY_SHORT}"
    )


# =========================================================
# /SHOP
# =========================================================

@dp.message(Command("shop"))
async def shop_command(
    message: Message
):
    ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    balance = get_balance(
        message.from_user.id
    )

    await message.answer(
        "🛒 <b>МАГАЗИН WESOLING</b>\n\n"
        f"🪙 Ваш баланс: "
        f"<b>{balance} {CURRENCY_SHORT}</b>\n\n"
        "Выберите категорию:",
        reply_markup=shop_main_keyboard()
    )


# =========================================================
# SHOP — BALANCE
# =========================================================

@dp.callback_query(
    F.data == "shop_balance"
)
async def shop_balance(
    callback: CallbackQuery
):
    balance = get_balance(
        callback.from_user.id
    )

    await callback.answer(
        f"Баланс: {balance} WESO",
        show_alert=True
    )


# =========================================================
# SHOP — HISTORY
# =========================================================

@dp.callback_query(
    F.data == "shop_history"
)
async def shop_history(
    callback: CallbackQuery
):
    rows = get_transactions(
        callback.from_user.id,
        limit=15
    )

    if not rows:
        await callback.message.answer(
            "📜 История операций пока пустая."
        )

        await callback.answer()
        return

    text = "📜 <b>История WesoCoins</b>\n\n"

    for amount, balance_after, tx_type, description, created_at in rows:
        sign = "+" if amount >= 0 else ""

        text += (
            f"{'🟢' if amount >= 0 else '🔴'} "
            f"<b>{sign}{amount} WESO</b>\n"
            f"{description}\n"
            f"💰 Баланс: {balance_after} WESO\n"
            f"🕐 {created_at}\n\n"
        )

    await callback.message.answer(text)

    await callback.answer()


# =========================================================
# SHOP — PASSES
# =========================================================

@dp.callback_query(
    F.data == "shop_passes"
)
async def shop_passes(
    callback: CallbackQuery
):
    tournaments = get_active_tournaments()

    buttons = []

    for tournament in tournaments:
        (
            tournament_id,
            name,
            max_players,
            tournament_format,
            ticket_price,
            status,
            created_at
        ) = tournament

        if ticket_price <= 0:
            continue

        if get_accepted_players_count(
            tournament_id
        ) >= max_players:
            continue

        passes = get_pass_count(
            callback.from_user.id,
            tournament_id
        )

        format_text = (
            "2×2"
            if tournament_format == "2x2"
            else "1×1"
        )

        text = (
            f"🎟️ {name} "
            f"[{format_text}] — "
            f"{ticket_price} WESO"
        )

        if passes > 0:
            text += f" | Есть: {passes}"

        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=(
                    f"buy_pass:{tournament_id}"
                )
            )
        ])

    if not buttons:
        await callback.message.answer(
            "🎟️ <b>Проходки</b>\n\n"
            "Сейчас доступных проходок нет."
        )

        await callback.answer()
        return

    await callback.message.answer(
        "🎟️ <b>ПРОХОДКИ</b>\n\n"
        "Купленная проходка сохраняется "
        "в вашем аккаунте.\n\n"
        "Для 2×2 проходка рассчитана "
        "на всю команду.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# SHOP — BUY PASS
# =========================================================

@dp.callback_query(
    F.data.startswith("buy_pass:")
)
async def buy_pass(
    callback: CallbackQuery
):
    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    if status != "active":
        await callback.answer(
            "Турнир закрыт.",
            show_alert=True
        )
        return

    if ticket_price <= 0:
        await callback.answer(
            "Для этого турнира проходка бесплатная.",
            show_alert=True
        )
        return

    players = get_accepted_players_count(
        tournament_id
    )

    if players >= max_players:
        await callback.answer(
            "Турнир уже заполнен.",
            show_alert=True
        )
        return

    balance = get_balance(
        callback.from_user.id
    )

    if balance < ticket_price:
        await callback.answer(
            "Недостаточно WesoCoins.",
            show_alert=True
        )
        return

    try:
        new_balance = change_balance(
            callback.from_user.id,
            -ticket_price,
            "pass_purchase",
            f"Покупка проходки на турнир "
            f"#{tournament_id} {tournament_name}"
        )

        add_pass(
            callback.from_user.id,
            tournament_id,
            1
        )

    except ValueError as e:
        await callback.answer(
            str(e),
            show_alert=True
        )
        return

    format_text = (
        "2×2"
        if tournament_format == "2x2"
        else "1×1"
    )

    await callback.message.answer(
        "✅ <b>Проходка куплена!</b>\n\n"
        f"🏆 Турнир: <b>{tournament_name}</b>\n"
        f"🎮 Формат: <b>{format_text}</b>\n"
        f"💳 Стоимость: <b>{ticket_price} WESO</b>\n"
        f"💰 Новый баланс: <b>{new_balance} WESO</b>\n\n"
        "Теперь можно перейти к /reg "
        "и зарегистрироваться."
    )

    await callback.answer(
        "Проходка куплена!"
    )


# =========================================================
# SHOP — UC
# =========================================================

@dp.callback_query(
    F.data == "shop_uc"
)
async def shop_uc(
    callback: CallbackQuery
):
    buttons = []

    for uc_amount, price in UC_PRODUCTS:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🎮 {uc_amount} UC — "
                    f"{price} WESO"
                ),
                callback_data=(
                    f"buy_uc:{uc_amount}"
                )
            )
        ])

    await callback.message.answer(
        "🎮 <b>UC</b>\n\n"
        "Выберите пакет:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# SHOP — BUY UC
# =========================================================

@dp.callback_query(
    F.data.startswith("buy_uc:")
)
async def buy_uc(
    callback: CallbackQuery
):
    uc_amount = int(
        callback.data.split(":")[1]
    )

    price = None

    for amount, item_price in UC_PRODUCTS:
        if amount == uc_amount:
            price = item_price
            break

    if price is None:
        await callback.answer(
            "Товар не найден.",
            show_alert=True
        )
        return

    balance = get_balance(
        callback.from_user.id
    )

    if balance < price:
        await callback.answer(
            "Недостаточно WesoCoins.",
            show_alert=True
        )
        return

    try:
        new_balance = change_balance(
            callback.from_user.id,
            -price,
            "uc_purchase",
            f"Покупка {uc_amount} UC"
        )
    except ValueError as e:
        await callback.answer(
            str(e),
            show_alert=True
        )
        return

    order_id = create_shop_order(
        user_id=callback.from_user.id,
        item_type="uc",
        item_name=f"{uc_amount} UC",
        amount=uc_amount,
        price=price
    )

    await callback.message.answer(
        "✅ <b>Заказ создан!</b>\n\n"
        f"🎮 UC: <b>{uc_amount}</b>\n"
        f"🪙 Списано: <b>{price} WESO</b>\n"
        f"💰 Баланс: <b>{new_balance} WESO</b>\n"
        f"🧾 Заказ: <b>#{order_id}</b>\n\n"
        "Заказ передан администрации "
        "на выдачу UC."
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            "🎮 <b>Новый заказ UC</b>\n\n"
            f"🧾 Заказ: #{order_id}\n"
            f"🆔 Пользователь: "
            f"<code>{callback.from_user.id}</code>\n"
            f"👤 Username: "
            f"@{callback.from_user.username}"
            if callback.from_user.username
            else
            "🎮 <b>Новый заказ UC</b>\n\n"
            f"🧾 Заказ: #{order_id}\n"
            f"🆔 Пользователь: "
            f"<code>{callback.from_user.id}</code>\n"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ UC выдано",
                        callback_data=(
                            f"complete_order:{order_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Отменить",
                        callback_data=(
                            f"cancel_order:{order_id}"
                        )
                    )
                ]
            ]
        )

        await bot.send_message(
            ADMIN_ID,
            f"Товар: <b>{uc_amount} UC</b>\n"
            f"Стоимость: <b>{price} WESO</b>",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.exception(
            "Ошибка уведомления админа: %s",
            e
        )

    await callback.answer(
        "Заказ создан!"
    )


# =========================================================
# SHOP — BUY WESO
# =========================================================

@dp.callback_query(
    F.data == "shop_buy_weso"
)
async def shop_buy_weso(
    callback: CallbackQuery
):
    buttons = []

    for rubles, weso in WESO_PACKAGES:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🪙 {weso} WESO — "
                    f"{rubles} ₽"
                ),
                callback_data=(
                    f"buy_weso:{rubles}:{weso}"
                )
            )
        ])

    await callback.message.answer(
        "💳 <b>ПОКУПКА WESOCOINS</b>\n\n"
        "Курс:\n"
        "<b>1 ₽ = 1 WESO</b>\n\n"
        "Скидок за большие покупки нет.\n\n"
        "Выберите пакет:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# SHOP — CREATE WESO ORDER
# =========================================================

@dp.callback_query(
    F.data.startswith("buy_weso:")
)
async def buy_weso(
    callback: CallbackQuery
):
    parts = callback.data.split(":")

    if len(parts) != 3:
        await callback.answer(
            "Ошибка.",
            show_alert=True
        )
        return

    rubles = int(parts[1])
    weso = int(parts[2])

    order_id = create_currency_order(
        callback.from_user.id,
        rubles,
        weso
    )

    await callback.message.answer(
        "💳 <b>Заявка на покупку WesoCoins создана!</b>\n\n"
        f"💵 Сумма: <b>{rubles} ₽</b>\n"
        f"🪙 Вы получите: <b>{weso} WESO</b>\n"
        f"🧾 Заявка: <b>#{order_id}</b>\n\n"
        f"Напишите @{MANAGER_USERNAME} "
        "для оплаты.\n\n"
        f"Если у вас бан — "
        f"@{PAYMENT_BAN_USERNAME}"
    )

    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Оплата получена",
                        callback_data=(
                            f"currency_paid:{order_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=(
                            f"currency_reject:{order_id}"
                        )
                    )
                ]
            ]
        )

        await bot.send_message(
            ADMIN_ID,
            "💳 <b>Новая заявка "
            "на покупку WesoCoins</b>\n\n"
            f"🧾 Заявка: #{order_id}\n"
            f"🆔 User ID: "
            f"<code>{callback.from_user.id}</code>\n"
            f"👤 Username: "
            f"{('@' + callback.from_user.username) if callback.from_user.username else 'Не указан'}\n\n"
            f"💵 Сумма: <b>{rubles} ₽</b>\n"
            f"🪙 WESO: <b>{weso}</b>",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.exception(
            "Ошибка отправки заявки админу: %s",
            e
        )

    await callback.answer(
        "Заявка создана!"
    )


# =========================================================
# ADMIN — CONFIRM WESO PAYMENT
# =========================================================

@dp.callback_query(
    F.data.startswith("currency_paid:")
)
async def currency_paid(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    order_id = int(
        callback.data.split(":")[1]
    )

    order = get_currency_order(
        order_id
    )

    if not order:
        await callback.answer(
            "Заявка не найдена.",
            show_alert=True
        )
        return

    (
        order_id,
        user_id,
        rubles,
        weso,
        status,
        created_at
    ) = order

    if status != "pending":
        await callback.answer(
            "Заявка уже обработана.",
            show_alert=True
        )
        return

    try:
        new_balance = change_balance(
            user_id,
            weso,
            "weso_purchase",
            f"Покупка {weso} WESO "
            f"за {rubles} ₽"
        )

        update_currency_order_status(
            order_id,
            "completed"
        )

    except Exception as e:
        logging.exception(
            "Ошибка начисления WESO: %s",
            e
        )

        await callback.answer(
            "Ошибка начисления.",
            show_alert=True
        )
        return

    try:
        await bot.send_message(
            user_id,
            "✅ <b>Оплата подтверждена!</b>\n\n"
            f"🪙 Вам начислено: <b>{weso} WESO</b>\n"
            f"💰 Баланс: <b>{new_balance} WESO</b>"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "WESO начислены."
    )


# =========================================================
# ADMIN — REJECT WESO PAYMENT
# =========================================================

@dp.callback_query(
    F.data.startswith("currency_reject:")
)
async def currency_reject(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    order_id = int(
        callback.data.split(":")[1]
    )

    order = get_currency_order(
        order_id
    )

    if not order:
        await callback.answer(
            "Заявка не найдена.",
            show_alert=True
        )
        return

    if order[4] != "pending":
        await callback.answer(
            "Заявка уже обработана.",
            show_alert=True
        )
        return

    update_currency_order_status(
        order_id,
        "rejected"
    )

    try:
        await bot.send_message(
            order[1],
            "❌ <b>Заявка на покупку WesoCoins отклонена.</b>\n\n"
            "Если это ошибка, обратитесь "
            f"к @{MANAGER_USERNAME}."
        )
    except Exception:
        pass

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "Заявка отклонена."
    )


# =========================================================
# ADMIN — COMPLETE UC ORDER
# =========================================================

@dp.callback_query(
    F.data.startswith("complete_order:")
)
async def complete_order(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    order_id = int(
        callback.data.split(":")[1]
    )

    order = get_shop_order(
        order_id
    )

    if not order:
        await callback.answer(
            "Заказ не найден.",
            show_alert=True
        )
        return

    if order[6] != "pending":
        await callback.answer(
            "Заказ уже обработан.",
            show_alert=True
        )
        return

    update_shop_order_status(
        order_id,
        "completed"
    )

    try:
        await bot.send_message(
            order[1],
            "✅ <b>Заказ выполнен!</b>\n\n"
            f"🎮 Выдано: <b>{order[3]}</b>\n"
            f"🧾 Заказ: <b>#{order_id}</b>"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "Заказ выполнен."
    )


# =========================================================
# ADMIN — CANCEL UC ORDER / REFUND
# =========================================================

@dp.callback_query(
    F.data.startswith("cancel_order:")
)
async def cancel_order(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    order_id = int(
        callback.data.split(":")[1]
    )

    order = get_shop_order(
        order_id
    )

    if not order:
        await callback.answer(
            "Заказ не найден.",
            show_alert=True
        )
        return

    if order[6] != "pending":
        await callback.answer(
            "Заказ уже обработан.",
            show_alert=True
        )
        return

    update_shop_order_status(
        order_id,
        "cancelled"
    )

    try:
        new_balance = change_balance(
            order[1],
            order[5],
            "refund",
            f"Возврат за заказ #{order_id}"
        )

        await bot.send_message(
            order[1],
            "↩️ <b>Заказ отменён.</b>\n\n"
            f"Возвращено: <b>{order[5]} WESO</b>\n"
            f"Баланс: <b>{new_balance} WESO</b>"
        )

    except Exception as e:
        logging.exception(
            "Ошибка возврата средств: %s",
            e
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "Заказ отменён."
    )


# =========================================================
# /REG
# =========================================================

@dp.message(Command("reg"))
async def registration_command(
    message: Message,
    state: FSMContext
):
    ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await state.clear()

    tournaments = get_active_tournaments()

    buttons = []

    for tournament in tournaments:
        (
            tournament_id,
            name,
            max_players,
            tournament_format,
            ticket_price,
            status,
            created_at
        ) = tournament

        current_players = (
            get_accepted_players_count(
                tournament_id
            )
        )

        if current_players >= max_players:
            continue

        buttons.append([
            tournament_button(
                tournament,
                "reg_tournament"
            )
        ])

    if not buttons:
        await message.answer(
            "В данный момент нет активных турниров."
        )
        return

    await message.answer(
        "📝 <b>Выберите турнир:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await state.set_state(
        Registration.tournament
    )


# =========================================================
# REG — TOURNAMENT
# =========================================================

@dp.callback_query(
    F.data.startswith("reg_tournament:")
)
async def registration_tournament(
    callback: CallbackQuery,
    state: FSMContext
):
    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    if status != "active":
        await callback.answer(
            "Турнир закрыт.",
            show_alert=True
        )
        return

    current_players = (
        get_accepted_players_count(
            tournament_id
        )
    )

    if current_players >= max_players:
        await callback.answer(
            "Турнир уже заполнен.",
            show_alert=True
        )
        return

    existing = user_has_application(
        tournament_id,
        callback.from_user.id
    )

    if existing:
        if existing[1] == "accepted":
            await callback.answer(
                "Ты уже зарегистрирован.",
                show_alert=True
            )
        else:
            await callback.answer(
                "Твоя заявка уже рассматривается.",
                show_alert=True
            )
        return

    pass_count = get_pass_count(
        callback.from_user.id,
        tournament_id
    )

    if ticket_price > 0 and pass_count <= 0:
        await callback.message.answer(
            "🎟️ <b>Для регистрации нужна проходка.</b>\n\n"
            f"🏆 {tournament_name}\n"
            f"💰 Стоимость: "
            f"<b>{ticket_price} WESO</b>\n\n"
            "Купи проходку в /shop, "
            "затем снова используй /reg."
        )

        await callback.answer()
        return

    await state.update_data(
        tournament_id=tournament_id
    )

    if tournament_format == "2x2":
        text = (
            "👥 <b>Регистрация 2×2</b>\n\n"
            f"🏆 <b>{tournament_name}</b>\n\n"
            "Первый игрок.\n\n"
            "Введите ник:"
        )
    else:
        text = (
            "👤 <b>Регистрация 1×1</b>\n\n"
            f"🏆 <b>{tournament_name}</b>\n\n"
            "Введите ник:"
        )

    await callback.message.edit_text(text)

    await state.set_state(
        Registration.nickname
    )

    await callback.answer()


# =========================================================
# REG — NICKNAME
# =========================================================

@dp.message(Registration.nickname)
async def registration_nickname(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Отправь ник текстом."
        )
        return

    nickname = message.text.strip()

    if not nickname:
        await message.answer(
            "❌ Ник не может быть пустым."
        )
        return

    await state.update_data(
        nickname=nickname
    )

    data = await state.get_data()
    tournament = get_tournament(
        data["tournament_id"]
    )

    if tournament and tournament[3] == "2x2":
        text = (
            "👤 <b>Игрок 1</b>\n\n"
            "Укажи часовой пояс:"
        )
    else:
        text = (
            "🌍 <b>Часовой пояс</b>\n\n"
            "Укажи часовой пояс:"
        )

    await message.answer(text)

    await state.set_state(
        Registration.timezone
    )


# =========================================================
# REG — TIMEZONE
# =========================================================

@dp.message(Registration.timezone)
async def registration_timezone(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Укажи часовой пояс."
        )
        return

    timezone = message.text.strip()

    if not timezone:
        await message.answer(
            "❌ Часовой пояс не может быть пустым."
        )
        return

    await state.update_data(
        timezone=timezone
    )

    await message.answer(
        "🆔 <b>PUBG Mobile ID</b>\n\n"
        "Введите ID.\n"
        "Разрешены только цифры."
    )

    await state.set_state(
        Registration.game_id
    )


# =========================================================
# REG — GAME ID
# =========================================================

@dp.message(Registration.game_id)
async def registration_game_id(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Отправь PUBG Mobile ID."
        )
        return

    game_id = message.text.strip()

    if not is_digits_only(game_id):
        await message.answer(
            "❌ PUBG Mobile ID должен "
            "содержать только цифры.\n\n"
            "Например: <code>123456789</code>"
        )
        return

    data = await state.get_data()

    if game_id_already_used(
        data["tournament_id"],
        game_id
    ):
        await message.answer(
            "❌ Этот PUBG Mobile ID "
            "уже используется в этом турнире."
        )
        return

    await state.update_data(
        game_id=game_id
    )

    tournament = get_tournament(
        data["tournament_id"]
    )

    if tournament and tournament[3] == "2x2":
        await message.answer(
            "👤 <b>Игрок 2</b>\n\n"
            "Введите ник второго игрока:"
        )

        await state.set_state(
            Registration.nickname2
        )

        return

    await message.answer(
        "📱 <b>Telegram username</b>\n\n"
        "Обязательно с @.\n\n"
        "Например: <code>@username</code>"
    )

    await state.set_state(
        Registration.tg_username
    )


# =========================================================
# REG — PLAYER 2 NICKNAME
# =========================================================

@dp.message(Registration.nickname2)
async def registration_nickname2(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Отправь ник второго игрока."
        )
        return

    nickname2 = message.text.strip()

    if not nickname2:
        await message.answer(
            "❌ Ник не может быть пустым."
        )
        return

    await state.update_data(
        nickname2=nickname2
    )

    await message.answer(
        "🌍 <b>Игрок 2</b>\n\n"
        "Укажи часовой пояс:"
    )

    await state.set_state(
        Registration.timezone2
    )


# =========================================================
# REG — PLAYER 2 TIMEZONE
# =========================================================

@dp.message(Registration.timezone2)
async def registration_timezone2(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Укажи часовой пояс."
        )
        return

    timezone2 = message.text.strip()

    if not timezone2:
        await message.answer(
            "❌ Часовой пояс не может быть пустым."
        )
        return

    await state.update_data(
        timezone2=timezone2
    )

    await message.answer(
        "🆔 <b>PUBG Mobile ID игрока 2</b>\n\n"
        "Только цифры."
    )

    await state.set_state(
        Registration.game_id2
    )


# =========================================================
# REG — PLAYER 2 GAME ID
# =========================================================

@dp.message(Registration.game_id2)
async def registration_game_id2(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Отправь PUBG Mobile ID."
        )
        return

    game_id2 = message.text.strip()

    if not is_digits_only(game_id2):
        await message.answer(
            "❌ PUBG Mobile ID должен "
            "содержать только цифры."
        )
        return

    data = await state.get_data()

    if game_id2 == data.get("game_id"):
        await message.answer(
            "❌ ID второго игрока "
            "не может совпадать с ID первого."
        )
        return

    if game_id_already_used(
        data["tournament_id"],
        game_id2
    ):
        await message.answer(
            "❌ Этот PUBG Mobile ID "
            "уже используется в этом турнире."
        )
        return

    await state.update_data(
        game_id2=game_id2
    )

    await message.answer(
        "📱 <b>Telegram username</b>\n\n"
        "Укажи Telegram username "
        "капитана/контактного лица.\n\n"
        "Обязательно с @.\n"
        "Например: <code>@username</code>"
    )

    await state.set_state(
        Registration.tg_username
    )


# =========================================================
# REG — USERNAME
# =========================================================

@dp.message(Registration.tg_username)
async def registration_tg_username(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "❌ Отправь Telegram username."
        )
        return

    tg_username = message.text.strip()

    if not tg_username.startswith("@"):
        await message.answer(
            "❌ Username обязательно "
            "должен начинаться с @.\n\n"
            "Например: <code>@username</code>"
        )
        return

    if not is_valid_telegram_username(
        tg_username
    ):
        await message.answer(
            "❌ Некорректный Telegram username.\n\n"
            "Используй формат:\n"
            "<code>@username</code>\n\n"
            "Разрешены буквы, цифры и _."
        )
        return

    data = await state.get_data()

    tournament_id = data["tournament_id"]

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await state.clear()
        await message.answer(
            "❌ Турнир не найден."
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    if status != "active":
        await state.clear()
        await message.answer(
            "❌ Турнир закрыт."
        )
        return

    current_players = (
        get_accepted_players_count(
            tournament_id
        )
    )

    if current_players >= max_players:
        await state.clear()
        await message.answer(
            "❌ Турнир уже заполнен."
        )
        return

    existing = user_has_application(
        tournament_id,
        message.from_user.id
    )

    if existing:
        await state.clear()
        await message.answer(
            "❌ Ты уже отправлял заявку "
            "на этот турнир."
        )
        return

    # Дополнительная проверка ID
    if game_id_already_used(
        tournament_id,
        data["game_id"]
    ):
        await state.clear()
        await message.answer(
            "❌ PUBG ID первого игрока "
            "уже зарегистрирован "
            "в этом турнире."
        )
        return

    if tournament_format == "2x2":
        if game_id_already_used(
            tournament_id,
            data["game_id2"]
        ):
            await state.clear()
            await message.answer(
                "❌ PUBG ID второго игрока "
                "уже зарегистрирован "
                "в этом турнире."
            )
            return

    # =====================================================
    # ПОТРЕБЛЯЕМ ПРОХОДКУ
    # =====================================================

    if ticket_price > 0:
        if get_pass_count(
            message.from_user.id,
            tournament_id
        ) <= 0:
            await state.clear()

            await message.answer(
                "❌ У тебя нет проходки "
                "на этот турнир.\n\n"
                "Купи её в /shop."
            )
            return

        if not consume_pass(
            message.from_user.id,
            tournament_id
        ):
            await state.clear()

            await message.answer(
                "❌ Не удалось использовать "
                "проходку. Попробуй ещё раз."
            )
            return

    application_id = save_application(
        tournament_id=tournament_id,
        user_id=message.from_user.id,
        username=message.from_user.username,

        nickname=data["nickname"],
        timezone=data["timezone"],
        game_id=data["game_id"],

        tg_username=tg_username,

        nickname2=data.get(
            "nickname2",
            ""
        ),
        timezone2=data.get(
            "timezone2",
            ""
        ),
        game_id2=data.get(
            "game_id2",
            ""
        )
    )

    await state.clear()

    # =====================================================
    # USER
    # =====================================================

    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ожидайте ответа модерации.\n\n"
        "💳 <b>Для оплаты:</b>\n"
        f"Напишите @{MANAGER_USERNAME} "
        "для оплаты.\n\n"
        f"Если у вас бан - "
        f"@{PAYMENT_BAN_USERNAME}"
    )

    username_text = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Не указан"
    )

    format_text = (
        "2×2"
        if tournament_format == "2x2"
        else "1×1"
    )

    admin_text = (
        f"📨 <b>Новая заявка #{application_id}</b>\n\n"

        f"🏆 <b>Турнир:</b> {tournament_name}\n"
        f"🎮 <b>Формат:</b> {format_text}\n"
        f"🎟️ Проходка: "
        f"{ticket_price} WESO\n\n"

        f"👤 <b>Telegram:</b> "
        f"{username_text}\n"
        f"🆔 <b>Telegram ID:</b> "
        f"<code>{message.from_user.id}</code>\n\n"

        f"🎮 <b>Игрок 1:</b>\n"
        f"👤 Ник: {data['nickname']}\n"
        f"🌍 Часовой пояс: "
        f"{data['timezone']}\n"
        f"🆔 PUBG ID: "
        f"{data['game_id']}\n"
    )

    if tournament_format == "2x2":
        admin_text += (
            "\n"
            f"🎮 <b>Игрок 2:</b>\n"
            f"👤 Ник: "
            f"{data['nickname2']}\n"
            f"🌍 Часовой пояс: "
            f"{data['timezone2']}\n"
            f"🆔 PUBG ID: "
            f"{data['game_id2']}\n"
        )

    admin_text += (
        "\n"
        f"📱 <b>Контакт:</b> "
        f"{tg_username}\n\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=(
                        f"accept:{application_id}"
                    )
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=(
                        f"reject:{application_id}"
                    )
                )
            ]
        ]
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            admin_text,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.exception(
            "Не удалось отправить заявку админу: %s",
            e
        )


# =========================================================
# /ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ У тебя нет доступа."
        )
        return

    pending = len(
        get_pending_applications()
    )

    currency_pending = len(
        get_pending_currency_orders()
    )

    shop_pending = len(
        get_pending_shop_orders()
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Создать турнир",
                    callback_data="admin_create"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить турнир",
                    callback_data="admin_delete"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Турниры",
                    callback_data="admin_tournaments"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📨 Заявки ({pending})",
                    callback_data="admin_applications"
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        f"💳 Покупка WESO "
                        f"({currency_pending})"
                    ),
                    callback_data="admin_currency_orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        f"🎮 Заказы UC "
                        f"({shop_pending})"
                    ),
                    callback_data="admin_shop_orders"
                )
            ]
        ]
    )

    await message.answer(
        "🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        "Для выдачи валюты также доступны:\n\n"
        "<code>/giveweso @username 1000</code>\n"
        "<code>/takeweso @username 500</code>\n"
        "<code>/balance @username</code>\n\n"
        "Можно добавить комментарий:\n"
        "<code>/giveweso @username 1000 "
        "Победа в турнире</code>",
        reply_markup=keyboard
    )


# =========================================================
# ADMIN — CREATE TOURNAMENT
# =========================================================

@dp.callback_query(
    F.data == "admin_create"
)
async def admin_create(
    callback: CallbackQuery,
    state: FSMContext
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "🏆 <b>Создание турнира</b>\n\n"
        "Введите название:"
    )

    await state.set_state(
        CreateTournament.name
    )

    await callback.answer()


# =========================================================
# CREATE — NAME
# =========================================================

@dp.message(CreateTournament.name)
async def create_tournament_name(
    message: Message,
    state: FSMContext
):
    if not admin_only(
        message.from_user.id
    ):
        return

    if not message.text:
        await message.answer(
            "Введите название."
        )
        return

    name = message.text.strip()

    if not name:
        await message.answer(
            "Название не может быть пустым."
        )
        return

    await state.update_data(
        tournament_name=name
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 1×1",
                    callback_data="create_format:1x1"
                ),
                InlineKeyboardButton(
                    text="👥 2×2",
                    callback_data="create_format:2x2"
                )
            ]
        ]
    )

    await message.answer(
        "🎮 <b>Выберите формат:</b>",
        reply_markup=keyboard
    )

    await state.set_state(
        CreateTournament.format
    )


# =========================================================
# CREATE — FORMAT
# =========================================================

@dp.callback_query(
    F.data.startswith("create_format:")
)
async def create_tournament_format(
    callback: CallbackQuery,
    state: FSMContext
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_format = (
        callback.data.split(":")[1]
    )

    if tournament_format not in (
        "1x1",
        "2x2"
    ):
        await callback.answer(
            "Неверный формат.",
            show_alert=True
        )
        return

    await state.update_data(
        tournament_format=tournament_format
    )

    if tournament_format == "2x2":
        text = (
            "👥 <b>2×2</b>\n\n"
            "Введите максимальное "
            "количество команд.\n\n"
            "Например: <code>8</code>\n\n"
            "8 команд = 16 игроков."
        )
    else:
        text = (
            "👤 <b>1×1</b>\n\n"
            "Введите максимальное "
            "количество участников.\n\n"
            "Например: <code>16</code>"
        )

    await callback.message.edit_text(
        text
    )

    await state.set_state(
        CreateTournament.max_players
    )

    await callback.answer()


# =========================================================
# CREATE — MAX PLAYERS
# =========================================================

@dp.message(CreateTournament.max_players)
async def create_tournament_max_players(
    message: Message,
    state: FSMContext
):
    if not admin_only(
        message.from_user.id
    ):
        return

    if not message.text:
        await message.answer(
            "Введите число."
        )
        return

    try:
        max_players = int(
            message.text.strip()
        )
    except ValueError:
        await message.answer(
            "❌ Нужно число."
        )
        return

    if max_players < 2:
        await message.answer(
            "❌ Минимум — 2."
        )
        return

    if max_players > 1000:
        await message.answer(
            "❌ Максимум — 1000."
        )
        return

    await state.update_data(
        max_players=max_players
    )

    data = await state.get_data()

    format_text = (
        "2×2"
        if data["tournament_format"] == "2x2"
        else "1×1"
    )

    await message.answer(
        f"🎮 Формат: <b>{format_text}</b>\n"
        f"👥 Количество: "
        f"<b>{max_players}</b>\n\n"

        "🎟️ <b>Стоимость проходки</b>\n\n"
        f"Введите цену в WESO.\n"
        f"Например: <code>200</code>\n\n"

        "Для 1×1 — цена с одного игрока.\n"
        "Для 2×2 — цена с одной команды."
    )

    await state.set_state(
        CreateTournament.ticket_price
    )


# =========================================================
# CREATE — TICKET PRICE
# =========================================================

@dp.message(CreateTournament.ticket_price)
async def create_tournament_ticket_price(
    message: Message,
    state: FSMContext
):
    if not admin_only(
        message.from_user.id
    ):
        return

    if not message.text:
        await message.answer(
            "Введите цену."
        )
        return

    try:
        ticket_price = int(
            message.text.strip()
        )
    except ValueError:
        await message.answer(
            "❌ Введите цену числом."
        )
        return

    if ticket_price < 0:
        await message.answer(
            "❌ Цена не может быть отрицательной."
        )
        return

    if ticket_price > 1_000_000:
        await message.answer(
            "❌ Цена слишком большая."
        )
        return

    data = await state.get_data()

    tournament_id = create_tournament(
        name=data["tournament_name"],
        max_players=data["max_players"],
        tournament_format=data["tournament_format"],
        ticket_price=ticket_price
    )

    await state.clear()

    format_text = (
        "2×2"
        if data["tournament_format"] == "2x2"
        else "1×1"
    )

    total_players = (
        data["max_players"] * 2
        if data["tournament_format"] == "2x2"
        else data["max_players"]
    )

    await message.answer(
        "✅ <b>Турнир создан!</b>\n\n"
        f"🏆 <b>{data['tournament_name']}</b>\n"
        f"🎮 Формат: <b>{format_text}</b>\n"
        f"👥 Команд/участников: "
        f"<b>{data['max_players']}</b>\n"
        f"👤 Всего игроков: "
        f"<b>{total_players}</b>\n"
        f"🎟️ Проходка: "
        f"<b>{ticket_price} WESO</b>\n"
        f"🆔 ID: <b>{tournament_id}</b>\n\n"
        "Проходка автоматически появилась "
        "в магазине."
    )


# =========================================================
# ADMIN — TOURNAMENTS
# =========================================================

@dp.callback_query(
    F.data == "admin_tournaments"
)
async def admin_tournaments(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournaments = get_all_tournaments()

    if not tournaments:
        await callback.message.answer(
            "📭 Турниров пока нет."
        )
        await callback.answer()
        return

    text = "🏆 <b>ТУРНИРЫ</b>\n\n"

    for tournament in tournaments:
        (
            tournament_id,
            name,
            max_players,
            tournament_format,
            ticket_price,
            status,
            created_at
        ) = tournament

        players = (
            get_accepted_players_count(
                tournament_id
            )
        )

        format_text = (
            "2×2"
            if tournament_format == "2x2"
            else "1×1"
        )

        status_text = (
            "🟢 Активен"
            if status == "active"
            else "🔴 Закрыт"
        )

        text += (
            f"<b>#{tournament_id} {name}</b>\n"
            f"🎮 {format_text}\n"
            f"👥 {players}/{max_players}\n"
            f"🎟️ {ticket_price} WESO\n"
            f"{status_text}\n\n"
        )

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# ADMIN — APPLICATIONS
# =========================================================

@dp.callback_query(
    F.data == "admin_applications"
)
async def admin_applications(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    applications = (
        get_pending_applications()
    )

    if not applications:
        await callback.message.answer(
            "📭 Новых заявок нет."
        )
        await callback.answer()
        return

    sent = 0

    for application in applications:
        (
            app_id,
            tournament_id,
            user_id,
            username,

            nickname,
            timezone,
            game_id,

            payment,
            tg_username,

            status,
            created_at,

            nickname2,
            timezone2,
            game_id2
        ) = application

        tournament = get_tournament(
            tournament_id
        )

        if tournament:
            tournament_name = tournament[1]
            tournament_format = tournament[3]
            ticket_price = tournament[4]
        else:
            tournament_name = "Удалённый турнир"
            tournament_format = "1x1"
            ticket_price = 0

        format_text = (
            "2×2"
            if tournament_format == "2x2"
            else "1×1"
        )

        username_text = (
            f"@{username}"
            if username
            else "Не указан"
        )

        text = (
            f"📨 <b>Заявка #{app_id}</b>\n\n"
            f"🏆 <b>Турнир:</b> "
            f"{tournament_name}\n"
            f"🎮 <b>Формат:</b> "
            f"{format_text}\n"
            f"🎟️ <b>Проходка:</b> "
            f"{ticket_price} WESO\n\n"

            f"👤 <b>Telegram:</b> "
            f"{username_text}\n"
            f"🆔 <b>Telegram ID:</b> "
            f"<code>{user_id}</code>\n\n"

            f"🎮 <b>Игрок 1:</b>\n"
            f"👤 {nickname}\n"
            f"🌍 {timezone}\n"
            f"🆔 <code>{game_id}</code>\n"
        )

        if tournament_format == "2x2":
            text += (
                "\n"
                "🎮 <b>Игрок 2:</b>\n"
                f"👤 {nickname2}\n"
                f"🌍 {timezone2}\n"
                f"🆔 <code>{game_id2}</code>\n"
            )

        text += (
            "\n"
            f"📱 Контакт: {tg_username}\n"
            f"🕐 {created_at}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять",
                        callback_data=(
                            f"accept:{app_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=(
                            f"reject:{app_id}"
                        )
                    )
                ]
            ]
        )

        try:
            await bot.send_message(
                ADMIN_ID,
                text,
                reply_markup=keyboard
            )

            sent += 1

        except Exception as e:
            logging.exception(
                "Ошибка отправки заявки: %s",
                e
            )

    await callback.answer(
        f"Показано заявок: {sent}"
    )


# =========================================================
# ADMIN — CURRENCY ORDERS
# =========================================================

@dp.callback_query(
    F.data == "admin_currency_orders"
)
async def admin_currency_orders(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    orders = get_pending_currency_orders()

    if not orders:
        await callback.message.answer(
            "💳 Нет ожидающих заявок."
        )
        await callback.answer()
        return

    for order in orders:
        (
            order_id,
            user_id,
            rubles,
            weso,
            status,
            created_at
        ) = order

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=(
                            f"currency_paid:{order_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=(
                            f"currency_reject:{order_id}"
                        )
                    )
                ]
            ]
        )

        await callback.message.answer(
            "💳 <b>Покупка WesoCoins</b>\n\n"
            f"🧾 #{order_id}\n"
            f"🆔 User ID: "
            f"<code>{user_id}</code>\n"
            f"💵 {rubles} ₽\n"
            f"🪙 {weso} WESO\n"
            f"🕐 {created_at}",
            reply_markup=keyboard
        )

    await callback.answer()


# =========================================================
# ADMIN — SHOP ORDERS
# =========================================================

@dp.callback_query(
    F.data == "admin_shop_orders"
)
async def admin_shop_orders(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    orders = get_pending_shop_orders()

    if not orders:
        await callback.message.answer(
            "🎮 Ожидающих заказов нет."
        )
        await callback.answer()
        return

    for order in orders:
        (
            order_id,
            user_id,
            item_type,
            item_name,
            amount,
            price,
            status,
            created_at
        ) = order

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Выдано",
                        callback_data=(
                            f"complete_order:{order_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=(
                            f"cancel_order:{order_id}"
                        )
                    )
                ]
            ]
        )

        await callback.message.answer(
            "🎮 <b>Заказ UC</b>\n\n"
            f"🧾 #{order_id}\n"
            f"🆔 User ID: "
            f"<code>{user_id}</code>\n"
            f"🎮 {item_name}\n"
            f"🪙 {price} WESO\n"
            f"🕐 {created_at}",
            reply_markup=keyboard
        )

    await callback.answer()


# =========================================================
# ADMIN — DELETE
# =========================================================

@dp.callback_query(
    F.data == "admin_delete"
)
async def admin_delete(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournaments = get_all_tournaments()

    if not tournaments:
        await callback.message.answer(
            "📭 Турниров нет."
        )
        await callback.answer()
        return

    buttons = []

    for tournament in tournaments:
        (
            tournament_id,
            name,
            max_players,
            tournament_format,
            ticket_price,
            status,
            created_at
        ) = tournament

        format_text = (
            "2×2"
            if tournament_format == "2x2"
            else "1×1"
        )

        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"🗑 {name} "
                    f"[{format_text}]"
                ),
                callback_data=(
                    f"delete_tournament:"
                    f"{tournament_id}"
                )
            )
        ])

    await callback.message.answer(
        "🗑 <b>Выберите турнир:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# DELETE CONFIRM
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_tournament:")
)
async def delete_tournament_callback(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=(
                        f"confirm_delete:"
                        f"{tournament_id}"
                    )
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_delete"
                )
            ]
        ]
    )

    await callback.message.answer(
        "⚠️ <b>Удалить турнир?</b>\n\n"
        f"🏆 {tournament[1]}\n"
        f"👥 {tournament[2]}\n"
        f"🎮 {('2×2' if tournament[3] == '2x2' else '1×1')}\n"
        f"🎟️ {tournament[4]} WESO\n\n"
        "Все заявки удалятся.\n"
        "Купленные проходки пользователей "
        "на этот турнир останутся в базе.",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("confirm_delete:")
)
async def confirm_delete(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир уже удалён.",
            show_alert=True
        )
        return

    delete_tournament(
        tournament_id
    )

    await callback.message.edit_text(
        "✅ <b>Турнир удалён.</b>\n\n"
        f"🏆 {tournament[1]}"
    )

    await callback.answer(
        "Удалено."
    )


@dp.callback_query(
    F.data == "cancel_delete"
)
async def cancel_delete(
    callback: CallbackQuery
):
    await callback.message.edit_text(
        "❌ Удаление отменено."
    )

    await callback.answer()


# =========================================================
# /LIST
# =========================================================

@dp.message(Command("list"))
async def list_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Команда только для администратора."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "Нет активных турниров."
        )
        return

    buttons = []

    for tournament in tournaments:
        buttons.append([
            tournament_button(
                tournament,
                "list_tournament"
            )
        ])

    await message.answer(
        "📋 <b>Выберите турнир:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# LIST TOURNAMENT
# =========================================================

@dp.callback_query(
    F.data.startswith("list_tournament:")
)
async def list_tournament_callback(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    teams = get_accepted_players(
        tournament_id
    )

    if not teams:
        await callback.message.answer(
            f"🏆 <b>{tournament_name}</b>\n\n"
            "📭 Участников нет."
        )
        await callback.answer()
        return

    if tournament_format == "2x2":
        text = (
            f"🏆 <b>{tournament_name}</b>\n"
            "🎮 <b>2×2</b>\n\n"
            f"👥 Команд: "
            f"<b>{len(teams)}/{max_players}</b>\n\n"
        )

        for index, team in enumerate(
            teams,
            start=1
        ):
            (
                app_id,
                user_id,
                username,

                nickname,
                timezone,
                game_id,

                payment,
                tg_username,

                status,
                created_at,

                nickname2,
                timezone2,
                game_id2
            ) = team

            text += (
                "━━━━━━━━━━━━━━\n"
                f"🏆 <b>Команда {index}</b>\n\n"
                f"👤 {nickname}\n"
                f"🆔 <code>{game_id}</code>\n\n"
                f"👤 {nickname2}\n"
                f"🆔 <code>{game_id2}</code>\n\n"
                f"📱 {tg_username}\n"
            )

        text += "\n━━━━━━━━━━━━━━"

    else:
        text = (
            f"🏆 <b>{tournament_name}</b>\n"
            "🎮 <b>1×1</b>\n\n"
            f"👥 Участников: "
            f"<b>{len(teams)}/{max_players}</b>\n\n"
        )

        for index, player in enumerate(
            teams,
            start=1
        ):
            (
                app_id,
                user_id,
                username,

                nickname,
                timezone,
                game_id,

                payment,
                tg_username,

                status,
                created_at,

                nickname2,
                timezone2,
                game_id2
            ) = player

            text += (
                f"<b>{index}.</b> {nickname}\n"
                f"🆔 <code>{game_id}</code>\n"
                f"📱 {tg_username}\n\n"
            )

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# /SETKA
# =========================================================

@dp.message(Command("setka"))
async def setka_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Команда только для администратора."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "Нет активных турниров."
        )
        return

    buttons = []

    for tournament in tournaments:
        buttons.append([
            tournament_button(
                tournament,
                "setka_tournament"
            )
        ])

    await message.answer(
        "🎲 <b>Выберите турнир:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# SETKA
# =========================================================

@dp.callback_query(
    F.data.startswith("setka_tournament:")
)
async def setka_tournament_callback(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        status,
        created_at
    ) = tournament

    players = get_accepted_players(
        tournament_id
    )

    if len(players) < max_players:
        await callback.message.answer(
            "⛔ <b>Сетка пока недоступна.</b>\n\n"
            f"🏆 {tournament_name}\n"
            f"👥 {len(players)}/{max_players}\n\n"
            "Необходимо полностью "
            "набрать турнир."
        )
        await callback.answer()
        return

    random.shuffle(players)

    if len(players) % 2 != 0:
        await callback.message.answer(
            "⛔ Нельзя создать пары.\n"
            "Количество участников/команд "
            "должно быть чётным."
        )
        await callback.answer()
        return

    if tournament_format == "2x2":

        text = (
            "🎲 <b>СЕТКА</b>\n\n"
            f"🏆 <b>{tournament_name}</b>\n"
            "🎮 Формат: <b>2×2</b>\n"
            f"👥 Команд: <b>{len(players)}</b>\n\n"
        )

        for match_number, i in enumerate(
            range(0, len(players), 2),
            start=1
        ):
            team1 = players[i]
            team2 = players[i + 1]

            text += (
                "━━━━━━━━━━━━━━━━\n"
                f"⚔️ <b>МАТЧ {match_number}</b>\n\n"

                "🔵 <b>КОМАНДА 1</b>\n"
                f"👤 {team1[3]}\n"
                f"🆔 <code>{team1[5]}</code>\n"
                f"👤 {team1[10]}\n"
                f"🆔 <code>{team1[12]}</code>\n\n"

                "<b>VS</b>\n\n"

                "🔴 <b>КОМАНДА 2</b>\n"
                f"👤 {team2[3]}\n"
                f"🆔 <code>{team2[5]}</code>\n"
                f"👤 {team2[10]}\n"
                f"🆔 <code>{team2[12]}</code>\n"
            )

        text += (
            "\n━━━━━━━━━━━━━━━━"
        )

    else:

        text = (
            "🎲 <b>СЕТКА</b>\n\n"
            f"🏆 <b>{tournament_name}</b>\n"
            "🎮 Формат: <b>1×1</b>\n"
            f"👥 Игроков: <b>{len(players)}</b>\n\n"
        )

        for match_number, i in enumerate(
            range(0, len(players), 2),
            start=1
        ):
            player1 = players[i]
            player2 = players[i + 1]

            text += (
                "━━━━━━━━━━━━━━━━\n"
                f"⚔️ <b>МАТЧ {match_number}</b>\n\n"

                f"🔵 {player1[3]}\n"
                f"🆔 <code>{player1[5]}</code>\n\n"

                "<b>VS</b>\n\n"

                f"🔴 {player2[3]}\n"
                f"🆔 <code>{player2[5]}</code>\n"
            )

        text += (
            "\n━━━━━━━━━━━━━━━━"
        )

    await callback.message.answer(text)
    await callback.answer(
        "Сетка создана!"
    )


# =========================================================
# ACCEPT APPLICATION
# =========================================================

@dp.callback_query(
    F.data.startswith("accept:")
)
async def accept_application(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    application_id = int(
        callback.data.split(":")[1]
    )

    application = get_application(
        application_id
    )

    if not application:
        await callback.answer(
            "Заявка не найдена.",
            show_alert=True
        )
        return

    (
        app_id,
        tournament_id,
        user_id,
        username,

        nickname,
        timezone,
        game_id,

        payment,
        tg_username,

        status,
        created_at,

        nickname2,
        timezone2,
        game_id2
    ) = application

    if status != "pending":
        await callback.answer(
            "Заявка уже обработана.",
            show_alert=True
        )
        return

    tournament = get_tournament(
        tournament_id
    )

    if not tournament:
        update_application_status(
            application_id,
            "rejected"
        )

        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    (
        tournament_id,
        tournament_name,
        max_players,
        tournament_format,
        ticket_price,
        tournament_status,
        created_at
    ) = tournament

    if tournament_status != "active":
        update_application_status(
            application_id,
            "rejected"
        )

        await callback.answer(
            "Турнир закрыт.",
            show_alert=True
        )
        return

    if get_accepted_players_count(
        tournament_id
    ) >= max_players:
        await callback.answer(
            "Турнир уже заполнен.",
            show_alert=True
        )
        return

    update_application_status(
        application_id,
        "accepted"
    )

    try:
        await bot.send_message(
            user_id,
            "✅ <b>Ваша заявка принята!</b>\n\n"
            f"🏆 Турнир: "
            f"<b>{tournament_name}</b>\n\n"
            "💳 <b>Для оплаты:</b>\n"
            f"Напишите @{MANAGER_USERNAME} "
            "для оплаты.\n\n"
            f"Если у вас бан — "
            f"@{PAYMENT_BAN_USERNAME}"
        )
    except Exception as e:
        logging.exception(
            "Ошибка уведомления пользователя: %s",
            e
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "Заявка принята!"
    )


# =========================================================
# REJECT APPLICATION
# =========================================================

@dp.callback_query(
    F.data.startswith("reject:")
)
async def reject_application(
    callback: CallbackQuery
):
    if not admin_only(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    application_id = int(
        callback.data.split(":")[1]
    )

    application = get_application(
        application_id
    )

    if not application:
        await callback.answer(
            "Заявка не найдена.",
            show_alert=True
        )
        return

    (
        app_id,
        tournament_id,
        user_id,
        username,

        nickname,
        timezone,
        game_id,

        payment,
        tg_username,

        status,
        created_at,

        nickname2,
        timezone2,
        game_id2
    ) = application

    if status != "pending":
        await callback.answer(
            "Заявка уже обработана.",
            show_alert=True
        )
        return

    update_application_status(
        application_id,
        "rejected"
    )

    # Возвращаем проходку пользователю,
    # потому что заявка была отклонена.
    tournament = get_tournament(
        tournament_id
    )

    if tournament and tournament[4] > 0:
        add_pass(
            user_id,
            tournament_id,
            1
        )

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Ваша заявка отклонена.</b>\n\n"
            "Использованная проходка "
            "возвращена на ваш аккаунт.\n\n"
            f"Если есть вопросы — "
            f"@{MANAGER_USERNAME}"
        )
    except Exception as e:
        logging.exception(
            "Ошибка уведомления пользователя: %s",
            e
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "Заявка отклонена."
    )


# =========================================================
# /GIVEWESO
# =========================================================

@dp.message(Command("giveweso"))
async def giveweso_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    parts = message.text.split(
        maxsplit=3
    )

    if len(parts) < 3:
        await message.answer(
            "Использование:\n"
            "<code>/giveweso @username 1000</code>\n\n"
            "Или с причиной:\n"
            "<code>/giveweso @username 1000 "
            "Победа в турнире</code>"
        )
        return

    username = parts[1]

    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer(
            "❌ Количество должно быть числом."
        )
        return

    if amount <= 0:
        await message.answer(
            "❌ Количество должно быть больше 0."
        )
        return

    reason = (
        parts[3]
        if len(parts) >= 4
        else "Выдано администратором"
    )

    target = find_user_by_username(
        username
    )

    if not target:
        await message.answer(
            "❌ Пользователь не найден.\n\n"
            "Он должен хотя бы один раз "
            "запустить бота через /start."
        )
        return

    user_id = target[0]

    try:
        new_balance = change_balance(
            user_id,
            amount,
            "admin_give",
            reason
        )
    except ValueError as e:
        await message.answer(
            f"❌ {e}"
        )
        return

    try:
        await bot.send_message(
            user_id,
            "🪙 <b>Вам начислены WesoCoins!</b>\n\n"
            f"➕ {amount} WESO\n"
            f"📝 Причина: {reason}\n"
            f"💰 Баланс: {new_balance} WESO"
        )
    except Exception:
        pass

    await message.answer(
        "✅ <b>WesoCoins выданы.</b>\n\n"
        f"👤 {username}\n"
        f"➕ {amount} WESO\n"
        f"💰 Новый баланс: {new_balance} WESO"
    )


# =========================================================
# /TAKEWESO
# =========================================================

@dp.message(Command("takeweso"))
async def takeweso_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    parts = message.text.split(
        maxsplit=3
    )

    if len(parts) < 3:
        await message.answer(
            "Использование:\n"
            "<code>/takeweso @username 500</code>"
        )
        return

    username = parts[1]

    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer(
            "❌ Количество должно быть числом."
        )
        return

    if amount <= 0:
        await message.answer(
            "❌ Количество должно быть больше 0."
        )
        return

    reason = (
        parts[3]
        if len(parts) >= 4
        else "Списано администратором"
    )

    target = find_user_by_username(
        username
    )

    if not target:
        await message.answer(
            "❌ Пользователь не найден."
        )
        return

    user_id = target[0]

    try:
        new_balance = change_balance(
            user_id,
            -amount,
            "admin_take",
            reason
        )
    except ValueError as e:
        await message.answer(
            f"❌ {e}"
        )
        return

    try:
        await bot.send_message(
            user_id,
            "⚠️ <b>С вашего баланса списаны WesoCoins.</b>\n\n"
            f"➖ {amount} WESO\n"
            f"📝 Причина: {reason}\n"
            f"💰 Баланс: {new_balance} WESO"
        )
    except Exception:
        pass

    await message.answer(
        "✅ <b>WesoCoins списаны.</b>\n\n"
        f"👤 {username}\n"
        f"➖ {amount} WESO\n"
        f"💰 Новый баланс: {new_balance} WESO"
    )


# =========================================================
# ADMIN — GIVE WINNER SHORTCUT
# =========================================================

@dp.message(Command("winner"))
async def winner_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    parts = message.text.split(
        maxsplit=3
    )

    if len(parts) < 4:
        await message.answer(
            "Использование:\n"
            "<code>/winner @username 1000 "
            "Победа в турнире</code>"
        )
        return

    username = parts[1]

    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer(
            "❌ Сумма должна быть числом."
        )
        return

    reason = parts[3]

    target = find_user_by_username(
        username
    )

    if not target:
        await message.answer(
            "❌ Пользователь не найден."
        )
        return

    try:
        new_balance = change_balance(
            target[0],
            amount,
            "tournament_win",
            reason
        )
    except ValueError as e:
        await message.answer(
            f"❌ {e}"
        )
        return

    try:
        await bot.send_message(
            target[0],
            "🏆 <b>Награда за турнир!</b>\n\n"
            f"🪙 +{amount} WESO\n"
            f"📝 {reason}\n\n"
            f"💰 Баланс: {new_balance} WESO"
        )
    except Exception:
        pass

    await message.answer(
        "🏆 Награда выдана.\n\n"
        f"👤 {username}\n"
        f"🪙 +{amount} WESO\n"
        f"💰 Баланс: {new_balance} WESO"
    )


# =========================================================
# /PENDING
# =========================================================

@dp.message(Command("pending"))
async def pending_command(
    message: Message
):
    if not admin_only(
        message.from_user.id
    ):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    app_count = len(
        get_pending_applications()
    )

    currency_count = len(
        get_pending_currency_orders()
    )

    shop_count = len(
        get_pending_shop_orders()
    )

    await message.answer(
        "📊 <b>Ожидающие операции</b>\n\n"
        f"📨 Заявки: <b>{app_count}</b>\n"
        f"💳 WESO: <b>{currency_count}</b>\n"
        f"🎮 UC: <b>{shop_count}</b>"
    )


# =========================================================
# STARTUP
# =========================================================

async def main():
    logging.basicConfig(
        level=logging.INFO
    )

    init_db()

    await setup_commands()

    print(
        "==================================="
    )
    print(
        "🤖 Wesoling Tournament Bot"
    )
    print(
        "🚀 Бот запущен!"
    )
    print(
        "🪙 WesoCoins enabled"
    )
    print(
        "🛒 Shop enabled"
    )
    print(
        "🎟️ Passes enabled"
    )
    print(
        "==================================="
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
