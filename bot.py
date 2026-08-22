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
PAYMENT_USERNAME = "oplatawesoling"
RULES_USERNAME = "WesolingRules"

DB_NAME = "wesoling.db"

# 1 рубль = 1 WesoCoin
COIN_PRICE_RUB = 1


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
    # Для custom emoji Telegram нужен специальный HTML.
    # Если ID не используется, возвращаем обычный emoji.
    return fallback


# =========================================================
# DATABASE HELPERS
# =========================================================

def column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table_name, column_name, definition):
    columns = column_names(cursor, table_name)

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN "
            f"{column_name} {definition}"
        )


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    # -----------------------------------------------------
    # TOURNAMENTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            max_players INTEGER NOT NULL DEFAULT 16,
            format TEXT NOT NULL DEFAULT '1x1',
            entry_price INTEGER NOT NULL DEFAULT 0,
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
        "entry_price",
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

    # -----------------------------------------------------
    # APPLICATIONS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER NOT NULL DEFAULT 0,
            username TEXT,
            nickname TEXT NOT NULL DEFAULT '',
            timezone TEXT NOT NULL DEFAULT '',
            game_id TEXT NOT NULL DEFAULT '',
            payment TEXT NOT NULL DEFAULT '',
            tg_username TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    fields = [
        ("tournament_id", "INTEGER NOT NULL DEFAULT 0"),
        ("user_id", "INTEGER NOT NULL DEFAULT 0"),
        ("username", "TEXT"),
        ("nickname", "TEXT NOT NULL DEFAULT ''"),
        ("timezone", "TEXT NOT NULL DEFAULT ''"),
        ("game_id", "TEXT NOT NULL DEFAULT ''"),
        ("payment", "TEXT NOT NULL DEFAULT ''"),
        ("tg_username", "TEXT NOT NULL DEFAULT ''"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ]

    for name, definition in fields:
        add_column_if_missing(
            cursor,
            "applications",
            name,
            definition
        )

    # -----------------------------------------------------
    # TEAMMATES / SECOND PLAYERS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS application_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            player_number INTEGER NOT NULL,
            nickname TEXT NOT NULL DEFAULT '',
            timezone TEXT NOT NULL DEFAULT '',
            game_id TEXT NOT NULL DEFAULT '',
            tg_username TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (application_id)
                REFERENCES applications(id)
        )
    """)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE tournaments
        SET created_at = ?
        WHERE created_at IS NULL OR created_at = ''
    """, (now,))

    cursor.execute("""
        UPDATE tournaments
        SET status = 'active'
        WHERE status IS NULL OR status = ''
    """)

    conn.commit()
    conn.close()


# =========================================================
# USERS / COINS
# =========================================================

def ensure_user(user_id, username=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE users
            SET username = ?
            WHERE user_id = ?
        """, (username, user_id))
    else:
        cursor.execute("""
            INSERT INTO users
            (user_id, username, coins, created_at)
            VALUES (?, ?, 0, ?)
        """, (
            user_id,
            username,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    conn.close()


def get_balance(user_id):
    ensure_user(user_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT coins FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else 0


def add_coins(user_id, amount):
    ensure_user(user_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET coins = coins + ?
        WHERE user_id = ?
    """, (amount, user_id))

    conn.commit()
    conn.close()


def remove_coins(user_id, amount):
    ensure_user(user_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET coins = coins - ?
        WHERE user_id = ?
        AND coins >= ?
    """, (amount, user_id, amount))

    success = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return success


def find_user_by_username(username):
    username = username.strip().lstrip("@").lower()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, username, coins
        FROM users
        WHERE LOWER(username) = ?
        LIMIT 1
    """, (username,))

    row = cursor.fetchone()

    conn.close()

    return row


# =========================================================
# TOURNAMENTS
# =========================================================

def create_tournament(name, max_players, tournament_format, entry_price):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tournaments
        (
            name,
            max_players,
            format,
            entry_price,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, 'active', ?)
    """, (
        name,
        max_players,
        tournament_format,
        entry_price,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    tournament_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tournament_id


def get_active_tournaments():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            entry_price,
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            entry_price,
            status,
            created_at
        FROM tournaments
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_tournament(tournament_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            max_players,
            format,
            entry_price,
            status,
            created_at
        FROM tournaments
        WHERE id = ?
    """, (tournament_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def delete_tournament(tournament_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM application_players
        WHERE application_id IN (
            SELECT id
            FROM applications
            WHERE tournament_id = ?
        )
    """, (tournament_id,))

    cursor.execute("""
        DELETE FROM applications
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
    tournament = get_tournament(tournament_id)

    if not tournament:
        return 0

    tournament_format = tournament[3]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE tournament_id = ?
        AND status = 'accepted'
    """, (tournament_id,))

    applications_count = cursor.fetchone()[0]

    conn.close()

    if tournament_format == "2x2":
        return applications_count * 2

    return applications_count


def get_accepted_applications(tournament_id):
    conn = sqlite3.connect(DB_NAME)
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
            created_at
        FROM applications
        WHERE tournament_id = ?
        AND status = 'accepted'
        ORDER BY id ASC
    """, (tournament_id,))

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_application_players(application_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            player_number,
            nickname,
            timezone,
            game_id,
            tg_username
        FROM application_players
        WHERE application_id = ?
        ORDER BY player_number ASC
    """, (application_id,))

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_pending_applications():
    conn = sqlite3.connect(DB_NAME)
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
            created_at
        FROM applications
        WHERE status = 'pending'
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def user_has_application(tournament_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, status
        FROM applications
        WHERE tournament_id = ?
        AND user_id = ?
        AND status IN ('pending', 'accepted')
        LIMIT 1
    """, (tournament_id, user_id))

    row = cursor.fetchone()

    conn.close()

    return row


def save_application(
    tournament_id,
    user_id,
    username,
    nickname,
    timezone,
    game_id,
    payment,
    tg_username,
    second_player=None
):
    conn = sqlite3.connect(DB_NAME)
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
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        tournament_id,
        user_id,
        username,
        nickname,
        timezone,
        game_id,
        payment,
        tg_username,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    application_id = cursor.lastrowid

    # Первый игрок
    cursor.execute("""
        INSERT INTO application_players
        (
            application_id,
            player_number,
            nickname,
            timezone,
            game_id,
            tg_username
        )
        VALUES (?, 1, ?, ?, ?, ?)
    """, (
        application_id,
        nickname,
        timezone,
        game_id,
        tg_username
    ))

    # Второй игрок
    if second_player:
        cursor.execute("""
            INSERT INTO application_players
            (
                application_id,
                player_number,
                nickname,
                timezone,
                game_id,
                tg_username
            )
            VALUES (?, 2, ?, ?, ?, ?)
        """, (
            application_id,
            second_player["nickname"],
            second_player["timezone"],
            second_player["game_id"],
            second_player["tg_username"]
        ))

    conn.commit()
    conn.close()

    return application_id


def get_application(application_id):
    conn = sqlite3.connect(DB_NAME)
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
            created_at
        FROM applications
        WHERE id = ?
    """, (application_id,))

    row = cursor.fetchone()

    conn.close()

    return row


def update_application_status(application_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE applications
        SET status = ?
        WHERE id = ?
    """, (status, application_id))

    conn.commit()
    conn.close()


# =========================================================
# VALIDATION
# =========================================================

def valid_username(text):
    if not text.startswith("@"):
        return False

    username = text[1:]

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9_]{5,32}",
            username
        )
    )


def valid_game_id(text):
    return bool(re.fullmatch(r"\d+", text.strip()))


# =========================================================
# FSM
# =========================================================

class Registration(StatesGroup):
    tournament = State()

    player1_nickname = State()
    player1_timezone = State()
    player1_game_id = State()
    player1_tg_username = State()

    player2_nickname = State()
    player2_timezone = State()
    player2_game_id = State()
    player2_tg_username = State()

    payment = State()


class CreateTournament(StatesGroup):
    name = State()
    format = State()
    max_players = State()
    entry_price = State()


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


def tournament_button(tournament, prefix):
    (
        tournament_id,
        name,
        max_players,
        tournament_format,
        entry_price,
        status,
        created_at
    ) = tournament

    players = get_accepted_players_count(tournament_id)

    return InlineKeyboardButton(
        text=(
            f"🏆 {name} "
            f"[{tournament_format}] "
            f"({players}/{max_players})"
        ),
        callback_data=f"{prefix}:{tournament_id}"
    )


def tournament_info(tournament):
    (
        tournament_id,
        name,
        max_players,
        tournament_format,
        entry_price,
        status,
        created_at
    ) = tournament

    if tournament_format == "2x2":
        places = max_players // 2
        registered = get_accepted_players_count(tournament_id) // 2
        participants_text = f"{registered}/{places} команд"
    else:
        registered = get_accepted_players_count(tournament_id)
        participants_text = f"{registered}/{max_players} игроков"

    return (
        f"🏆 <b>{name}</b>\n"
        f"🎮 Формат: <b>{tournament_format}</b>\n"
        f"👥 {participants_text}\n"
        f"💰 Проходка: <b>{entry_price} WesoCoins</b>"
    )


# =========================================================
# COMMANDS MENU
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
            description="Регистрация на турнир"
        ),
        BotCommand(
            command="shop",
            description="Магазин WesoCoins"
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
async def start_command(message: Message):
    ensure_user(
        message.from_user.id,
        message.from_user.username
    )

    balance = get_balance(message.from_user.id)

    text = (
        "👋 <b>Добро пожаловать в Wesoling Tournament!</b>\n\n"
        "Это бот поддержки турниров по PUBG Mobile.\n\n"
        "🏆 /reg — регистрация\n"
        "🛒 /shop — магазин WesoCoins\n"
        "💰 /balance — баланс\n"
        "📖 /rules — правила\n"
        "❓ /help — поддержка\n\n"
        f"💎 Ваш баланс: <b>{balance} WesoCoins</b>"
    )

    await message.answer(text)


# =========================================================
# /HELP
# =========================================================

@dp.message(Command("help"))
async def help_command(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать менеджеру",
                    url=f"https://t.me/{MANAGER_USERNAME}"
                )
            ]
        ]
    )

    await message.answer(
        "Если у тебя возник вопрос по поводу турнира, "
        "обратись к менеджеру.\n\n"
        "<i>Здравствуйте, возник вопрос по поводу турнира.</i>",
        reply_markup=keyboard
    )


# =========================================================
# /RULES
# =========================================================

@dp.message(Command("rules"))
async def rules_command(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Открыть правила",
                    url=f"https://t.me/{RULES_USERNAME}"
                )
            ]
        ]
    )

    await message.answer(
        "Правила турнира находятся в официальном канале.",
        reply_markup=keyboard
    )


# =========================================================
# /BALANCE
# =========================================================

@dp.message(Command("balance"))
async def balance_command(message: Message):
    ensure_user(
        message.from_user.id,
        message.from_user.username
    )

    balance = get_balance(message.from_user.id)

    await message.answer(
        "💰 <b>Ваш баланс</b>\n\n"
        f"💎 WesoCoins: <b>{balance}</b>\n\n"
        "1 WesoCoin = 1 ₽."
    )


# =========================================================
# /SHOP
# =========================================================

@dp.message(Command("shop"))
async def shop_command(message: Message):
    balance = get_balance(message.from_user.id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Купить WesoCoins",
                    callback_data="shop_buy_coins"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Проходки",
                    callback_data="shop_passes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 Как получить WesoCoins?",
                    callback_data="shop_info"
                )
            ]
        ]
    )

    await message.answer(
        "🛒 <b>МАГАЗИН WESOLING</b>\n\n"
        f"💎 Ваш баланс: <b>{balance} WesoCoins</b>\n\n"
        "WesoCoins можно использовать для оплаты "
        "проходок на турниры.\n\n"
        "💰 1 ₽ = 1 WesoCoin.",
        reply_markup=keyboard
    )


# =========================================================
# SHOP — BUY COINS
# =========================================================

@dp.callback_query(F.data == "shop_buy_coins")
async def shop_buy_coins(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Купить WesoCoins",
                    url=f"https://t.me/{PAYMENT_USERNAME}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="shop_back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💎 <b>Покупка WesoCoins</b>\n\n"
        "Курс:\n"
        "<b>1 ₽ = 1 WesoCoin</b>\n\n"
        "Например:\n"
        "100 ₽ = 100 WesoCoins\n"
        "250 ₽ = 250 WesoCoins\n"
        "500 ₽ = 500 WesoCoins\n\n"
        "Для покупки напишите:\n"
        f"@{PAYMENT_USERNAME}",
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# SHOP — PASSES
# =========================================================

@dp.callback_query(F.data == "shop_passes")
async def shop_passes(callback: CallbackQuery):
    tournaments = get_active_tournaments()

    buttons = []

    for tournament in tournaments:
        if tournament[4] > 0:
            buttons.append([
                tournament_button(
                    tournament,
                    "shop_tournament"
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="shop_back"
        )
    ])

    await callback.message.edit_text(
        "🏆 <b>Проходки на турниры</b>\n\n"
        "Выберите турнир:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# SHOP — TOURNAMENT
# =========================================================

@dp.callback_query(F.data.startswith("shop_tournament:"))
async def shop_tournament(callback: CallbackQuery):
    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(tournament_id)

    if not tournament or tournament[5] != "active":
        await callback.answer(
            "Турнир недоступен.",
            show_alert=True
        )
        return

    price = tournament[4]
    balance = get_balance(callback.from_user.id)

    if tournament[3] == "2x2":
        text = (
            f"🏆 <b>{tournament[1]}</b>\n\n"
            "🎮 Формат: <b>2×2</b>\n"
            f"💰 Проходка команды: <b>{price} WesoCoins</b>\n\n"
            "Проходка оплачивается одним человеком "
            "при регистрации команды.\n\n"
            f"💎 Ваш баланс: <b>{balance}</b>"
        )
    else:
        text = (
            f"🏆 <b>{tournament[1]}</b>\n\n"
            "🎮 Формат: <b>1×1</b>\n"
            f"💰 Проходка: <b>{price} WesoCoins</b>\n\n"
            f"💎 Ваш баланс: <b>{balance}</b>"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Зарегистрироваться",
                    callback_data=f"shop_reg:{tournament_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="shop_passes"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# SHOP INFO
# =========================================================

@dp.callback_query(F.data == "shop_info")
async def shop_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="shop_back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "🎁 <b>Как получить WesoCoins?</b>\n\n"
        "💰 Купить за рубли\n"
        "🏆 Получить за победу в турнире\n"
        "🎉 Получить в розыгрыше\n"
        "🎁 Получить от администратора\n\n"
        "WesoCoins можно тратить на проходки "
        "турниров.",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data == "shop_back")
async def shop_back(callback: CallbackQuery):
    balance = get_balance(callback.from_user.id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Купить WesoCoins",
                    callback_data="shop_buy_coins"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Проходки",
                    callback_data="shop_passes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 Как получить WesoCoins?",
                    callback_data="shop_info"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "🛒 <b>МАГАЗИН WESOLING</b>\n\n"
        f"💎 Ваш баланс: <b>{balance} WesoCoins</b>\n\n"
        "1 ₽ = 1 WesoCoin.",
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# SHOP -> REGISTRATION
# =========================================================

@dp.callback_query(F.data.startswith("shop_reg:"))
async def shop_registration(
    callback: CallbackQuery,
    state: FSMContext
):
    tournament_id = int(
        callback.data.split(":")[1]
    )

    tournament = get_tournament(tournament_id)

    if not tournament or tournament[5] != "active":
        await callback.answer(
            "Турнир недоступен.",
            show_alert=True
        )
        return

    if tournament[4] > get_balance(callback.from_user.id):
        await callback.answer(
            "Недостаточно WesoCoins.",
            show_alert=True
        )
        return

    await state.clear()

    await state.update_data(
        tournament_id=tournament_id
    )

    await callback.message.edit_text(
        f"📝 <b>Регистрация</b>\n\n"
        f"🏆 {tournament[1]}\n"
        f"🎮 Формат: {tournament[3]}\n"
        f"💰 Проходка: {tournament[4]} WesoCoins\n\n"
        "<b>1/5</b>\n"
        "Введите ник первого игрока:"
    )

    await state.set_state(
        Registration.player1_nickname
    )

    await callback.answer()


# =========================================================
# /REG
# =========================================================

@dp.message(Command("reg"))
async def registration_command(
    message: Message,
    state: FSMContext
):
    await state.clear()

    tournaments = get_active_tournaments()

    buttons = []

    for tournament in tournaments:
        players = get_accepted_players_count(
            tournament[0]
        )

        if players >= tournament[2]:
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
        "📝 <b>Выберите турнир для регистрации:</b>",
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

    tournament = get_tournament(tournament_id)

    if not tournament or tournament[5] != "active":
        await callback.answer(
            "Турнир больше недоступен.",
            show_alert=True
        )
        return

    current_players = get_accepted_players_count(
        tournament_id
    )

    if current_players >= tournament[2]:
        await callback.answer(
            "Максимальное количество участников набрано.",
            show_alert=True
        )
        return

    existing = user_has_application(
        tournament_id,
        callback.from_user.id
    )

    if existing:
        if existing[1] == "accepted":
            text = "Ты уже зарегистрирован на этот турнир."
        else:
            text = "Твоя заявка уже находится на рассмотрении."

        await callback.answer(
            text,
            show_alert=True
        )
        return

    price = tournament[4]

    if price > get_balance(callback.from_user.id):
        await callback.answer(
            f"Недостаточно WesoCoins.\n"
            f"Нужно: {price}\n"
            f"У вас: {get_balance(callback.from_user.id)}",
            show_alert=True
        )
        return

    await state.update_data(
        tournament_id=tournament_id
    )

    await callback.message.edit_text(
        f"📝 <b>Регистрация</b>\n\n"
        f"🏆 <b>{tournament[1]}</b>\n"
        f"🎮 Формат: <b>{tournament[3]}</b>\n"
        f"💰 Проходка: <b>{price} WesoCoins</b>\n\n"
        "<b>1/5</b>\n"
        "Введите ник первого игрока:"
    )

    await state.set_state(
        Registration.player1_nickname
    )

    await callback.answer()


# =========================================================
# PLAYER 1 NICK
# =========================================================

@dp.message(Registration.player1_nickname)
async def registration_player1_nickname(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите ник текстом."
        )
        return

    await state.update_data(
        player1_nickname=message.text.strip()
    )

    await message.answer(
        "<b>2/5</b>\n"
        "Введите часовой пояс первого игрока:"
    )

    await state.set_state(
        Registration.player1_timezone
    )


# =========================================================
# PLAYER 1 TIMEZONE
# =========================================================

@dp.message(Registration.player1_timezone)
async def registration_player1_timezone(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите часовой пояс."
        )
        return

    await state.update_data(
        player1_timezone=message.text.strip()
    )

    await message.answer(
        "<b>3/5</b>\n"
        "Введите PUBG Mobile ID первого игрока.\n\n"
        "⚠️ ID должен содержать только цифры."
    )

    await state.set_state(
        Registration.player1_game_id
    )


# =========================================================
# PLAYER 1 GAME ID
# =========================================================

@dp.message(Registration.player1_game_id)
async def registration_player1_game_id(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите PUBG Mobile ID."
        )
        return

    if not valid_game_id(message.text):
        await message.answer(
            "❌ ID должен содержать исключительно цифры.\n"
            "Например: <code>123456789</code>"
        )
        return

    await state.update_data(
        player1_game_id=message.text.strip()
    )

    await message.answer(
        "<b>4/5</b>\n"
        "Введите Telegram username первого игрока.\n\n"
        "⚠️ Обязательно с символом @\n"
        "Например: <code>@Wesoling</code>"
    )

    await state.set_state(
        Registration.player1_tg_username
    )


# =========================================================
# PLAYER 1 TG
# =========================================================

@dp.message(Registration.player1_tg_username)
async def registration_player1_tg_username(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите Telegram username."
        )
        return

    username = message.text.strip()

    if not valid_username(username):
        await message.answer(
            "❌ Username должен начинаться с @.\n\n"
            "Пример:\n"
            "<code>@Wesoling</code>"
        )
        return

    await state.update_data(
        player1_tg_username=username
    )

    data = await state.get_data()

    tournament = get_tournament(
        data["tournament_id"]
    )

    if tournament[3] == "2x2":
        await message.answer(
            "👥 <b>Второй игрок</b>\n\n"
            "Введите ник второго игрока:"
        )

        await state.set_state(
            Registration.player2_nickname
        )
    else:
        await message.answer(
            "<b>5/5</b>\n"
            "Как будете оплачивать участие?\n\n"
            "Напишите: <b>Рубли</b> или <b>WesoCoins</b>\n\n"
            "Для оплаты:\n"
            f"@{MANAGER_USERNAME}\n"
            f"Если у вас бан — @{PAYMENT_USERNAME}"
        )

        await state.set_state(
            Registration.payment
        )


# =========================================================
# PLAYER 2 NICK
# =========================================================

@dp.message(Registration.player2_nickname)
async def registration_player2_nickname(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите ник второго игрока."
        )
        return

    await state.update_data(
        player2_nickname=message.text.strip()
    )

    await message.answer(
        "Введите часовой пояс второго игрока:"
    )

    await state.set_state(
        Registration.player2_timezone
    )


# =========================================================
# PLAYER 2 TIMEZONE
# =========================================================

@dp.message(Registration.player2_timezone)
async def registration_player2_timezone(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите часовой пояс."
        )
        return

    await state.update_data(
        player2_timezone=message.text.strip()
    )

    await message.answer(
        "Введите PUBG Mobile ID второго игрока.\n\n"
        "⚠️ Только цифры."
    )

    await state.set_state(
        Registration.player2_game_id
    )


# =========================================================
# PLAYER 2 GAME ID
# =========================================================

@dp.message(Registration.player2_game_id)
async def registration_player2_game_id(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите PUBG Mobile ID."
        )
        return

    if not valid_game_id(message.text):
        await message.answer(
            "❌ ID должен состоять только из цифр."
        )
        return

    await state.update_data(
        player2_game_id=message.text.strip()
    )

    await message.answer(
        "Введите Telegram username второго игрока.\n\n"
        "⚠️ Обязательно с @\n"
        "Например: <code>@Wesoling</code>"
    )

    await state.set_state(
        Registration.player2_tg_username
    )


# =========================================================
# PLAYER 2 TG
# =========================================================

@dp.message(Registration.player2_tg_username)
async def registration_player2_tg_username(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Введите Telegram username."
        )
        return

    username = message.text.strip()

    if not valid_username(username):
        await message.answer(
            "❌ Username должен начинаться с @."
        )
        return

    await state.update_data(
        player2_tg_username=username
    )

    await message.answer(
        "<b>5/5</b>\n"
        "Как будете оплачивать участие?\n\n"
        "Напишите: <b>WesoCoins</b>\n\n"
        "Для оплаты:\n"
        f"@{MANAGER_USERNAME}\n"
        f"Если у вас бан — @{PAYMENT_USERNAME}"
    )

    await state.set_state(
        Registration.payment
    )


# =========================================================
# PAYMENT / SAVE APPLICATION
# =========================================================

@dp.message(Registration.payment)
async def registration_payment(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Укажите способ оплаты."
        )
        return

    payment = message.text.strip()

    if payment.lower() not in (
        "weso",
        "wesocoins",
        "рубли",
        "рубль",
        "руб"
    ):
        await message.answer(
            "Напишите <b>Рубли</b> или "
            "<b>WesoCoins</b>."
        )
        return

    data = await state.get_data()

    tournament_id = data["tournament_id"]

    tournament = get_tournament(
        tournament_id
    )

    if not tournament or tournament[5] != "active":
        await state.clear()

        await message.answer(
            "Турнир больше не существует или закрыт."
        )
        return

    current_players = get_accepted_players_count(
        tournament_id
    )

    if current_players >= tournament[2]:
        await state.clear()

        await message.answer(
            "К сожалению, пока ты заполнял форму, "
            "турнир уже заполнился."
        )
        return

    existing = user_has_application(
        tournament_id,
        message.from_user.id
    )

    if existing:
        await state.clear()

        await message.answer(
            "Ты уже отправлял заявку на этот турнир."
        )
        return

    price = tournament[4]

    # В этом боте регистрация через WesoCoins.
    if payment.lower() in (
        "weso",
        "wesocoins"
    ):
        if get_balance(message.from_user.id) < price:
            await message.answer(
                "❌ Недостаточно WesoCoins.\n\n"
                f"Нужно: <b>{price}</b>\n"
                f"У вас: <b>{get_balance(message.from_user.id)}</b>"
            )
            return

    second_player = None

    if tournament[3] == "2x2":
        second_player = {
            "nickname": data["player2_nickname"],
            "timezone": data["player2_timezone"],
            "game_id": data["player2_game_id"],
            "tg_username": data["player2_tg_username"],
        }

    application_id = save_application(
        tournament_id=tournament_id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        nickname=data["player1_nickname"],
        timezone=data["player1_timezone"],
        game_id=data["player1_game_id"],
        payment=payment,
        tg_username=data["player1_tg_username"],
        second_player=second_player
    )

    # Если оплачивается WesoCoins — списываем сразу.
    if payment.lower() in (
        "weso",
        "wesocoins"
    ):
        remove_coins(
            message.from_user.id,
            price
        )

    await state.clear()

    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ожидайте ответа от модерации.\n\n"
        "💳 Для оплаты напишите:\n"
        f"@{MANAGER_USERNAME}\n"
        f"Если у вас бан — @{PAYMENT_USERNAME}"
    )

    admin_text = (
        f"📨 <b>Новая заявка #{application_id}</b>\n\n"
        f"🏆 <b>Турнир:</b> {tournament[1]}\n"
        f"🎮 <b>Формат:</b> {tournament[3]}\n"
        f"💰 <b>Стоимость:</b> {price} WesoCoins\n\n"
        f"👤 Регистратор: "
        f"@{message.from_user.username or 'Не указан'}\n"
        f"🆔 Telegram ID: "
        f"<code>{message.from_user.id}</code>\n\n"
        f"👤 <b>Игрок 1</b>\n"
        f"🎮 Ник: {data['player1_nickname']}\n"
        f"🌍 Часовой пояс: {data['player1_timezone']}\n"
        f"🆔 PUBG ID: {data['player1_game_id']}\n"
        f"📱 TG: {data['player1_tg_username']}\n"
    )

    if tournament[3] == "2x2":
        admin_text += (
            "\n"
            "👤 <b>Игрок 2</b>\n"
            f"🎮 Ник: {data['player2_nickname']}\n"
            f"🌍 Часовой пояс: {data['player2_timezone']}\n"
            f"🆔 PUBG ID: {data['player2_game_id']}\n"
            f"📱 TG: {data['player2_tg_username']}\n"
        )

    admin_text += (
        f"\n💳 <b>Оплата:</b> {payment}\n"
        f"🕐 <b>Время:</b> "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"accept:{application_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{application_id}"
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
    except Exception:
        logging.exception(
            "Не удалось отправить заявку админу"
        )


# =========================================================
# /ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ У тебя нет доступа к админ-панели."
        )
        return

    pending = len(
        get_pending_applications()
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
                    text="📋 Активные турниры",
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
                    text="💎 Выдать WesoCoins",
                    callback_data="admin_coins"
                )
            ]
        ]
    )

    await message.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выбери действие:",
        reply_markup=keyboard
    )


# =========================================================
# ADMIN — CREATE
# =========================================================

@dp.callback_query(F.data == "admin_create")
async def admin_create(
    callback: CallbackQuery,
    state: FSMContext
):
    if not admin_only(callback.from_user.id):
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


@dp.message(CreateTournament.name)
async def create_tournament_name(
    message: Message,
    state: FSMContext
):
    if not admin_only(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "Введите название."
        )
        return

    await state.update_data(
        tournament_name=message.text.strip()
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1×1",
                    callback_data="create_format:1x1"
                ),
                InlineKeyboardButton(
                    text="2×2",
                    callback_data="create_format:2x2"
                )
            ]
        ]
    )

    await message.answer(
        "🎮 Выберите формат турнира:",
        reply_markup=keyboard
    )

    await state.set_state(
        CreateTournament.format
    )


@dp.callback_query(
    F.data.startswith("create_format:")
)
async def create_tournament_format(
    callback: CallbackQuery,
    state: FSMContext
):
    if not admin_only(callback.from_user.id):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    tournament_format = callback.data.split(":")[1]

    await state.update_data(
        tournament_format=tournament_format
    )

    if tournament_format == "2x2":
        await callback.message.answer(
            "👥 Введите количество игроков.\n\n"
            "Например: <code>16</code>\n\n"
            "Для 2×2 это означает "
            "<b>8 команд</b>."
        )
    else:
        await callback.message.answer(
            "👥 Введите максимальное количество игроков.\n\n"
            "Например: <code>16</code>"
        )

    await state.set_state(
        CreateTournament.max_players
    )

    await callback.answer()


@dp.message(CreateTournament.max_players)
async def create_tournament_max_players(
    message: Message,
    state: FSMContext
):
    if not admin_only(message.from_user.id):
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
            "❌ Введите число."
        )
        return

    data = await state.get_data()

    if data["tournament_format"] == "2x2":
        if max_players < 2:
            await message.answer(
                "❌ Минимум 2 игрока."
            )
            return

        if max_players % 2 != 0:
            await message.answer(
                "❌ Для формата 2×2 количество игроков "
                "должно быть чётным."
            )
            return
    else:
        if max_players < 2:
            await message.answer(
                "❌ Минимум 2 игрока."
            )
            return

    if max_players > 1000:
        await message.answer(
            "❌ Слишком большое количество."
        )
        return

    await state.update_data(
        max_players=max_players
    )

    await message.answer(
        "💰 Введите стоимость проходки в WesoCoins.\n\n"
        "Например:\n"
        "<code>100</code>\n\n"
        "Если турнир бесплатный — <code>0</code>."
    )

    await state.set_state(
        CreateTournament.entry_price
    )


@dp.message(CreateTournament.entry_price)
async def create_tournament_entry_price(
    message: Message,
    state: FSMContext
):
    if not admin_only(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "Введите стоимость."
        )
        return

    try:
        entry_price = int(
            message.text.strip()
        )
    except ValueError:
        await message.answer(
            "❌ Введите число."
        )
        return

    if entry_price < 0:
        await message.answer(
            "❌ Стоимость не может быть отрицательной."
        )
        return

    data = await state.get_data()

    tournament_id = create_tournament(
        data["tournament_name"],
        data["max_players"],
        data["tournament_format"],
        entry_price
    )

    await state.clear()

    if data["tournament_format"] == "2x2":
        teams = data["max_players"] // 2

        places_text = (
            f"{data['max_players']} игроков / "
            f"{teams} команд"
        )
    else:
        places_text = (
            f"{data['max_players']} игроков"
        )

    await message.answer(
        "✅ <b>Турнир создан!</b>\n\n"
        f"🏆 Название: <b>{data['tournament_name']}</b>\n"
        f"🎮 Формат: <b>{data['tournament_format']}</b>\n"
        f"👥 Места: <b>{places_text}</b>\n"
        f"💰 Проходка: <b>{entry_price} WesoCoins</b>\n"
        f"🆔 ID: <code>{tournament_id}</code>"
    )


# =========================================================
# ADMIN — TOURNAMENTS
# =========================================================

@dp.callback_query(F.data == "admin_tournaments")
async def admin_tournaments(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
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

    text = "🏆 <b>Турниры</b>\n\n"

    for tournament in tournaments:
        (
            tournament_id,
            name,
            max_players,
            tournament_format,
            entry_price,
            status,
            created_at
        ) = tournament

        players = get_accepted_players_count(
            tournament_id
        )

        status_text = (
            "🟢 Активен"
            if status == "active"
            else "🔴 Закрыт"
        )

        text += (
            f"<b>#{tournament_id} {name}</b>\n"
            f"🎮 {tournament_format}\n"
            f"👥 {players}/{max_players}\n"
            f"💰 {entry_price} WesoCoins\n"
            f"{status_text}\n\n"
        )

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# ADMIN — APPLICATIONS
# =========================================================

@dp.callback_query(F.data == "admin_applications")
async def admin_applications(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    applications = get_pending_applications()

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
            created_at
        ) = application

        tournament = get_tournament(
            tournament_id
        )

        if not tournament:
            continue

        players = get_application_players(
            app_id
        )

        text = (
            f"📨 <b>Заявка #{app_id}</b>\n\n"
            f"🏆 Турнир: <b>{tournament[1]}</b>\n"
            f"🎮 Формат: <b>{tournament[3]}</b>\n\n"
            f"👤 Регистратор: "
            f"@{username or 'Не указан'}\n"
            f"🆔 Telegram ID: "
            f"<code>{user_id}</code>\n\n"
        )

        for number, p_nick, p_tz, p_id, p_tg in players:
            text += (
                f"👤 <b>Игрок {number}</b>\n"
                f"🎮 Ник: {p_nick}\n"
                f"🌍 Часовой пояс: {p_tz}\n"
                f"🆔 PUBG ID: <code>{p_id}</code>\n"
                f"📱 TG: {p_tg}\n\n"
            )

        text += (
            f"💳 Оплата: {payment}\n"
            f"🕐 Время: {created_at}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять",
                        callback_data=f"accept:{app_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject:{app_id}"
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
        except Exception:
            logging.exception(
                "Ошибка отправки заявки"
            )

    await callback.answer(
        f"Показано заявок: {sent}"
    )


# =========================================================
# ADMIN — DELETE
# =========================================================

@dp.callback_query(F.data == "admin_delete")
async def admin_delete(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
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
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {tournament[1]}",
                callback_data=(
                    f"delete_tournament:{tournament[0]}"
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


@dp.callback_query(
    F.data.startswith("delete_tournament:")
)
async def delete_tournament_callback(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
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
                        f"confirm_delete:{tournament_id}"
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
        f"🎮 Формат: {tournament[3]}\n"
        f"💰 Проходка: {tournament[4]} WesoCoins\n\n"
        "Все заявки также будут удалены.",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("confirm_delete:")
)
async def confirm_delete(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
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
        "Турнир удалён."
    )


@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(
    callback: CallbackQuery
):
    await callback.message.edit_text(
        "❌ Удаление отменено."
    )

    await callback.answer()


# =========================================================
# ADMIN — GIVE COINS
# =========================================================

@dp.callback_query(F.data == "admin_coins")
async def admin_coins(
    callback: CallbackQuery
):
    if not admin_only(callback.from_user.id):
        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "💎 <b>Выдача WesoCoins</b>\n\n"
        "Используйте команду:\n\n"
        "<code>/givecoins @username количество</code>\n\n"
        "Например:\n"
        "<code>/givecoins @Wesoling 500</code>\n\n"
        "Также можно по Telegram ID:\n"
        "<code>/givecoins 123456789 500</code>"
    )

    await callback.answer()


@dp.message(Command("givecoins"))
async def givecoins_command(
    message: Message
):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    if not message.text:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "Использование:\n"
            "<code>/givecoins @username количество</code>"
        )
        return

    target = parts[1]

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

    user_id = None

    if target.startswith("@"):
        user = find_user_by_username(target)

        if not user:
            await message.answer(
                "❌ Пользователь не найден в базе.\n\n"
                "Он должен хотя бы один раз запустить бота."
            )
            return

        user_id = user[0]

    elif target.isdigit():
        user_id = int(target)

    else:
        await message.answer(
            "❌ Укажи @username или Telegram ID."
        )
        return

    add_coins(
        user_id,
        amount
    )

    await message.answer(
        "✅ <b>WesoCoins выданы!</b>\n\n"
        f"👤 Получатель: <code>{target}</code>\n"
        f"💎 Выдано: <b>{amount}</b>\n"
        f"💰 Новый баланс: "
        f"<b>{get_balance(user_id)}</b>"
    )

    try:
        await bot.send_message(
            user_id,
            "🎁 <b>Вам начислены WesoCoins!</b>\n\n"
            f"💎 Начислено: <b>{amount}</b>\n"
            f"💰 Баланс: <b>{get_balance(user_id)}</b>"
        )
    except Exception:
        logging.exception(
            "Не удалось уведомить пользователя"
        )


# =========================================================
# ADMIN — WINNER REWARD
# =========================================================

@dp.message(Command("reward"))
async def reward_command(
    message: Message
):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Нет доступа."
        )
        return

    if not message.text:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "Использование:\n"
            "<code>/reward @username количество</code>"
        )
        return

    target = parts[1]

    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer(
            "Количество должно быть числом."
        )
        return

    if amount <= 0:
        await message.answer(
            "Количество должно быть больше 0."
        )
        return

    user = find_user_by_username(target)

    if not user:
        await message.answer(
            "Пользователь не найден.\n"
            "Он должен запустить бота."
        )
        return

    user_id = user[0]

    add_coins(
        user_id,
        amount
    )

    await message.answer(
        "🏆 <b>Награда выдана!</b>\n\n"
        f"👤 {target}\n"
        f"💎 +{amount} WesoCoins"
    )

    try:
        await bot.send_message(
            user_id,
            "🏆 <b>Вы получили награду!</b>\n\n"
            f"💎 +{amount} WesoCoins\n"
            f"💰 Баланс: {get_balance(user_id)}"
        )
    except Exception:
        pass


# =========================================================
# /LIST
# =========================================================

@dp.message(Command("list"))
async def list_command(
    message: Message
):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Эта команда доступна только администратору."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "Активных турниров нет."
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
    if not admin_only(callback.from_user.id):
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

    applications = get_accepted_applications(
        tournament_id
    )

    if not applications:
        await callback.message.answer(
            f"🏆 <b>{tournament[1]}</b>\n\n"
            "📭 Участников пока нет."
        )
        await callback.answer()
        return

    text = (
        f"🏆 <b>{tournament[1]}</b>\n"
        f"🎮 Формат: <b>{tournament[3]}</b>\n\n"
    )

    for index, application in enumerate(
        applications,
        start=1
    ):
        app_id = application[0]

        players = get_application_players(
            app_id
        )

        if tournament[3] == "2x2":
            text += f"<b>Команда {index}</b>\n"

            for number, nickname, tz, game_id, tg in players:
                text += (
                    f"👤 {nickname}\n"
                    f"🆔 <code>{game_id}</code>\n"
                    f"📱 {tg}\n"
                )

            text += "\n"

        else:
            nickname = application[3]
            game_id = application[5]
            tg = application[7]

            text += (
                f"<b>{index}.</b> {nickname}\n"
                f"🆔 <code>{game_id}</code>\n"
                f"📱 {tg}\n\n"
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
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Эта команда доступна только администратору."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "Активных турниров нет."
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
    if not admin_only(callback.from_user.id):
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

    applications = get_accepted_applications(
        tournament_id
    )

    players_count = get_accepted_players_count(
        tournament_id
    )

    if players_count < tournament[2]:
        await callback.message.answer(
            "⛔ <b>Сетка пока недоступна.</b>\n\n"
            f"🏆 {tournament[1]}\n"
            f"🎮 Формат: {tournament[3]}\n"
            f"👥 Зарегистрировано: "
            f"{players_count}/{tournament[2]}\n\n"
            "Сетка будет доступна после полного набора."
        )

        await callback.answer()
        return

    random.shuffle(applications)

    text = (
        "🎲 <b>СЕТКА ТУРНИРА</b>\n\n"
        f"🏆 <b>{tournament[1]}</b>\n"
        f"🎮 Формат: <b>{tournament[3]}</b>\n\n"
    )

    # -----------------------------------------------------
    # 1x1
    # -----------------------------------------------------

    if tournament[3] == "1x1":
        if len(applications) % 2 != 0:
            await callback.message.answer(
                "⛔ Для генерации пар количество "
                "участников должно быть чётным."
            )
            await callback.answer()
            return

        for pair_number in range(
            0,
            len(applications),
            2
        ):
            p1 = applications[pair_number]
            p2 = applications[pair_number + 1]

            text += (
                f"🥊 <b>Матч {pair_number // 2 + 1}</b>\n"
                f"👤 {p1[3]} "
                f"VS "
                f"{p2[3]}\n\n"
            )

    # -----------------------------------------------------
    # 2x2
    # -----------------------------------------------------

    else:
        for match_number in range(
            0,
            len(applications),
            2
        ):
            team1 = applications[match_number]
            team2 = applications[match_number + 1]

            team1_players = get_application_players(
                team1[0]
            )

            team2_players = get_application_players(
                team2[0]
            )

            text += (
                f"⚔️ <b>Матч {match_number // 2 + 1}</b>\n\n"
                "🔵 <b>Команда 1</b>\n"
            )

            for _, nickname, _, _, _ in team1_players:
                text += f"• {nickname}\n"

            text += "\n🔴 <b>Команда 2</b>\n"

            for _, nickname, _, _, _ in team2_players:
                text += f"• {nickname}\n"

            text += "\n"

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
    if not admin_only(callback.from_user.id):
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
        created_at
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

    if not tournament or tournament[5] != "active":
        update_application_status(
            application_id,
            "rejected"
        )

        await callback.answer(
            "Турнир больше недоступен.",
            show_alert=True
        )
        return

    players_count = get_accepted_players_count(
        tournament_id
    )

    team_size = 2 if tournament[3] == "2x2" else 1

    if players_count + team_size > tournament[2]:
        await callback.answer(
            "Свободных мест больше нет.",
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
            f"🏆 Турнир: <b>{tournament[1]}</b>\n"
            f"🎮 Формат: <b>{tournament[3]}</b>\n\n"
            "💬 Свяжитесь с менеджером:\n"
            f"@{MANAGER_USERNAME}\n\n"
            "Если у вас бан:\n"
            f"@{PAYMENT_USERNAME}"
        )
    except Exception:
        logging.exception(
            "Не удалось уведомить пользователя"
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
    if not admin_only(callback.from_user.id):
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
        created_at
    ) = application

    if status != "pending":
        await callback.answer(
            "Заявка уже обработана.",
            show_alert=True
        )
        return

    # Если WesoCoins были списаны при отправке заявки,
    # при отклонении возвращаем их.
    tournament = get_tournament(
        tournament_id
    )

    if tournament and payment.lower() in (
        "weso",
        "wesocoins"
    ):
        add_coins(
            user_id,
            tournament[4]
        )

    update_application_status(
        application_id,
        "rejected"
    )

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Ваша заявка отклонена.</b>\n\n"
            "Если вы считаете, что произошла ошибка, "
            "обратитесь в поддержку."
        )
    except Exception:
        logging.exception(
            "Не удалось уведомить пользователя"
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
# FALLBACK FOR UNKNOWN CALLBACKS
# =========================================================

@dp.callback_query()
async def unknown_callback(
    callback: CallbackQuery
):
    await callback.answer()


# =========================================================
# STARTUP
# =========================================================

async def main():
    logging.basicConfig(
        level=logging.INFO
    )

    init_db()

    await setup_commands()

    print("===================================")
    print("🤖 Wesoling Tournament Bot")
    print("🚀 Бот запущен!")
    print("===================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
