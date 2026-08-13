import asyncio
import logging
import random
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

# ВСТАВЬ СЮДА НОВЫЙ токен от BotFather.
# Старый токен, который был отправлен в чат, обязательно отзови.
BOT_TOKEN = "8352231785:AAFwRrscwdWahXXPZrO02sZ9bSa9N7z0RYk"

# ID администратора
ADMIN_ID = 7146654831

# Username поддержки БЕЗ @
MANAGER_USERNAME = "WesolingManager"

# Канал с правилами БЕЗ @
RULES_USERNAME = "WesolingRules"

DB_NAME = "wesoling.db"


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
    emoji_id = EMOJI.get(number)
    if not emoji_id:
        return fallback
    return fallback


# =========================================================
# DATABASE
# =========================================================

def column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table_name, column_name, definition):
    columns = column_names(cursor, table_name)
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -----------------------------------------------------
    # Турниры
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            max_players INTEGER NOT NULL DEFAULT 16,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    # Миграция старой БД:
    # если таблица tournaments уже существовала,
    # SQLite сам новые колонки не добавляет.
    add_column_if_missing(
        cursor, "tournaments", "max_players",
        "INTEGER NOT NULL DEFAULT 16"
    )
    add_column_if_missing(
        cursor, "tournaments", "status",
        "TEXT DEFAULT 'active'"
    )
    add_column_if_missing(
        cursor, "tournaments", "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    # -----------------------------------------------------
    # Заявки
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
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        )
    """)

    # Миграция старой таблицы applications.
    add_column_if_missing(
        cursor, "applications", "tournament_id",
        "INTEGER NOT NULL DEFAULT 0"
    )
    add_column_if_missing(
        cursor, "applications", "user_id",
        "INTEGER NOT NULL DEFAULT 0"
    )
    add_column_if_missing(
        cursor, "applications", "username",
        "TEXT"
    )
    add_column_if_missing(
        cursor, "applications", "nickname",
        "TEXT NOT NULL DEFAULT ''"
    )
    add_column_if_missing(
        cursor, "applications", "timezone",
        "TEXT NOT NULL DEFAULT ''"
    )
    add_column_if_missing(
        cursor, "applications", "game_id",
        "TEXT NOT NULL DEFAULT ''"
    )
    add_column_if_missing(
        cursor, "applications", "payment",
        "TEXT NOT NULL DEFAULT ''"
    )
    add_column_if_missing(
        cursor, "applications", "tg_username",
        "TEXT NOT NULL DEFAULT ''"
    )
    add_column_if_missing(
        cursor, "applications", "status",
        "TEXT DEFAULT 'pending'"
    )
    add_column_if_missing(
        cursor, "applications", "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    # Исправляем старые записи, если created_at был пустым.
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
# TOURNAMENTS
# =========================================================

def create_tournament(name, max_players):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tournaments
        (name, max_players, status, created_at)
        VALUES (?, ?, 'active', ?)
    """, (
        name,
        max_players,
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
        SELECT id, name, max_players, status, created_at
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
        SELECT id, name, max_players, status, created_at
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
        SELECT id, name, max_players, status, created_at
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
# PLAYERS / APPLICATIONS
# =========================================================

def get_accepted_players_count(tournament_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, user_id, username, nickname, timezone,
            game_id, payment, tg_username, status, created_at
        FROM applications
        WHERE tournament_id = ?
        AND status = 'accepted'
        ORDER BY id ASC
    """, (tournament_id,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_pending_applications():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, tournament_id, user_id, username, nickname,
            timezone, game_id, payment, tg_username,
            status, created_at
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
    tg_username
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

    conn.commit()
    conn.close()
    return application_id


def get_application(application_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, tournament_id, user_id, username, nickname,
            timezone, game_id, payment, tg_username,
            status, created_at
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
# FSM
# =========================================================

class Registration(StatesGroup):
    tournament = State()
    nickname = State()
    timezone = State()
    game_id = State()
    payment = State()
    tg_username = State()


class CreateTournament(StatesGroup):
    name = State()
    max_players = State()


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
    tournament_id, name, max_players, status, created_at = tournament
    players = get_accepted_players_count(tournament_id)

    return InlineKeyboardButton(
        text=f"🏆 {name} ({players}/{max_players})",
        callback_data=f"{prefix}:{tournament_id}"
    )


# =========================================================
# COMMANDS MENU
# =========================================================

async def setup_commands():
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="help", description="Поддержка"),
        BotCommand(command="reg", description="Регистрация на турнир"),
        BotCommand(command="rules", description="Правила"),
        BotCommand(command="list", description="Список участников"),
        BotCommand(command="setka", description="Сетка турнира"),
        BotCommand(command="admin", description="Админ-панель"),
    ]

    await bot.set_my_commands(commands)


# =========================================================
# /START
# =========================================================

@dp.message(Command("start"))
async def start_command(message: Message):
    text = (
        f"{emoji(6, '👋')} <b>Добро пожаловать в Wesoling Tournament!</b>\n\n"
        "Привет! Это бот поддержки турниров по PUBG Mobile.\n\n"
        "Чтобы быстро перейти к делу, используй команды:\n\n"
        f"{emoji(10, '🔹')} Хочешь участвовать? — /reg\n"
        f"{emoji(10, '🔹')} Хочешь посмотреть правила? — /rules\n"
        f"{emoji(15, '❓')} Возник вопрос? — /help"
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

    text = (
        "Если у тебя возник вопрос по поводу турнира, "
        "обратись к администратору.\n\n"
        "<i>Здравствуйте, возник вопрос по поводу турнира.</i>"
    )

    await message.answer(text, reply_markup=keyboard)


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
        "Правила турнира находятся в нашем официальном канале.",
        reply_markup=keyboard
    )


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
        tournament_id, name, max_players, status, created_at = tournament
        current_players = get_accepted_players_count(tournament_id)

        if current_players >= max_players:
            continue

        buttons.append([
            tournament_button(tournament, "reg_tournament")
        ])

    if not buttons:
        await message.answer(
            "В данный момент нету активных турниров."
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        f"{emoji(13, '📝')} <b>Выберите турнир для регистрации:</b>",
        reply_markup=keyboard
    )

    await state.set_state(Registration.tournament)


# =========================================================
# REG — ВЫБОР ТУРНИРА
# =========================================================

@dp.callback_query(F.data.startswith("reg_tournament:"))
async def registration_tournament(
    callback: CallbackQuery,
    state: FSMContext
):
    tournament_id = int(callback.data.split(":")[1])
    tournament = get_tournament(tournament_id)

    if not tournament or tournament[3] != "active":
        await callback.answer(
            "Турнир больше недоступен.",
            show_alert=True
        )
        return

    current_players = get_accepted_players_count(tournament_id)

    if current_players >= tournament[2]:
        await callback.answer(
            "На этот турнир уже набрано максимальное количество участников.",
            show_alert=True
        )
        return

    existing = user_has_application(
        tournament_id,
        callback.from_user.id
    )

    if existing:
        status = existing[1]
        if status == "accepted":
            await callback.answer(
                "Ты уже зарегистрирован на этот турнир.",
                show_alert=True
            )
        else:
            await callback.answer(
                "Твоя заявка уже находится на рассмотрении.",
                show_alert=True
            )
        return

    await state.update_data(tournament_id=tournament_id)

    await callback.message.edit_text(
        f"{emoji(13, '📝')} <b>Регистрация на турнир</b>\n\n"
        f"🏆 <b>{tournament[1]}</b>\n\n"
        "<b>1/5</b>\n"
        "Ваш ник:"
    )

    await state.set_state(Registration.nickname)
    await callback.answer()


# =========================================================
# REG — НИК
# =========================================================

@dp.message(Registration.nickname)
async def registration_nickname(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer("Пожалуйста, отправь свой ник текстом.")
        return

    await state.update_data(nickname=message.text.strip())

    await message.answer(
        "<b>2/5</b>\n"
        "Часовой пояс:"
    )

    await state.set_state(Registration.timezone)


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
            "Пожалуйста, укажи часовой пояс текстом."
        )
        return

    await state.update_data(timezone=message.text.strip())

    await message.answer(
        "<b>3/5</b>\n"
        "Айди:\n"
        "<i>(В PUBG Mobile)</i>"
    )

    await state.set_state(Registration.game_id)


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
            "Пожалуйста, отправь игровой ID."
        )
        return

    await state.update_data(game_id=message.text.strip())

    await message.answer(
        "<b>4/5</b>\n"
        "Оплата участия в:\n\n"
        "Напиши: Рубли или Звёзды"
    )

    await state.set_state(Registration.payment)


# =========================================================
# REG — PAYMENT
# =========================================================

@dp.message(Registration.payment)
async def registration_payment(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Пожалуйста, укажи способ оплаты."
        )
        return

    await state.update_data(payment=message.text.strip())

    await message.answer(
        "<b>5/5</b>\n"
        "ТГ юзернейм:\n"
        f"({emoji(9, '@')} в профиле)"
    )

    await state.set_state(Registration.tg_username)


# =========================================================
# REG — TG USERNAME / СОЗДАНИЕ ЗАЯВКИ
# =========================================================

@dp.message(Registration.tg_username)
async def registration_tg_username(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer(
            "Пожалуйста, отправь свой Telegram username."
        )
        return

    tg_username = message.text.strip()
    data = await state.get_data()
    tournament_id = data["tournament_id"]

    tournament = get_tournament(tournament_id)

    if not tournament or tournament[3] != "active":
        await state.clear()
        await message.answer("Турнир больше не существует или закрыт.")
        return

    current_players = get_accepted_players_count(tournament_id)

    if current_players >= tournament[2]:
        await state.clear()
        await message.answer(
            "К сожалению, пока ты заполнял форму, "
            "на этот турнир уже набрали максимальное количество участников."
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

    application_id = save_application(
        tournament_id=tournament_id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        nickname=data["nickname"],
        timezone=data["timezone"],
        game_id=data["game_id"],
        payment=data["payment"],
        tg_username=tg_username
    )

    await state.clear()

    await message.answer(
        f"{emoji(16, '✅')} <b>Заявка отправлена!</b>\n\n"
        "Ожидайте ответа от модерации."
    )

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Не указан"
    )

    admin_text = (
        f"📨 <b>Новая заявка #{application_id}</b>\n\n"
        f"🏆 <b>Турнир:</b> {tournament[1]}\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"🎮 <b>Ник:</b> {data['nickname']}\n"
        f"🌍 <b>Часовой пояс:</b> {data['timezone']}\n"
        f"🆔 <b>PUBG Mobile ID:</b> {data['game_id']}\n"
        f"💳 <b>Оплата:</b> {data['payment']}\n"
        f"📱 <b>ТГ юзернейм:</b> {tg_username}\n\n"
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
    except Exception as e:
        logging.exception(
            "Не удалось отправить заявку админу: %s",
            e
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

    pending = len(get_pending_applications())

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
            ]
        ]
    )

    await message.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выбери нужное действие:",
        reply_markup=keyboard
    )


# =========================================================
# ADMIN — СОЗДАНИЕ
# =========================================================

@dp.callback_query(F.data == "admin_create")
async def admin_create(
    callback: CallbackQuery,
    state: FSMContext
):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.message.answer(
        "🏆 <b>Создание турнира</b>\n\n"
        "Введите название турнира:"
    )

    await state.set_state(CreateTournament.name)
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
            "Введите название турнира текстом."
        )
        return

    await state.update_data(
        tournament_name=message.text.strip()
    )

    await message.answer(
        "Введите максимальное количество участников:\n\n"
        "Например: <code>16</code>"
    )

    await state.set_state(CreateTournament.max_players)


@dp.message(CreateTournament.max_players)
async def create_tournament_max_players(
    message: Message,
    state: FSMContext
):
    if not admin_only(message.from_user.id):
        return

    if not message.text:
        await message.answer("Введите число участников.")
        return

    try:
        max_players = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Нужно ввести именно число.\n\n"
            "Например: <code>16</code>"
        )
        return

    if max_players < 2:
        await message.answer(
            "❌ Минимальное количество участников — 2."
        )
        return

    if max_players > 1000:
        await message.answer(
            "❌ Слишком большое количество участников."
        )
        return

    data = await state.get_data()

    tournament_id = create_tournament(
        data["tournament_name"],
        max_players
    )

    await state.clear()

    await message.answer(
        f"{emoji(16, '✅')} <b>Турнир создан!</b>\n\n"
        f"🏆 <b>Название:</b> {data['tournament_name']}\n"
        f"👥 <b>Участников:</b> {max_players}\n"
        f"🆔 <b>ID:</b> {tournament_id}"
    )


# =========================================================
# ADMIN — СПИСОК ТУРНИРОВ
# =========================================================

@dp.callback_query(F.data == "admin_tournaments")
async def admin_tournaments(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournaments = get_all_tournaments()

    if not tournaments:
        await callback.message.answer("📭 Турниров пока нет.")
        await callback.answer()
        return

    text = "🏆 <b>Турниры:</b>\n\n"

    for tournament in tournaments:
        tournament_id, name, max_players, status, created_at = tournament
        players = get_accepted_players_count(tournament_id)

        status_text = "🟢 Активен" if status == "active" else "🔴 Закрыт"

        text += (
            f"<b>#{tournament_id} {name}</b>\n"
            f"👥 {players}/{max_players}\n"
            f"{status_text}\n\n"
        )

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# ADMIN — ЗАЯВКИ
# =========================================================

@dp.callback_query(F.data == "admin_applications")
async def admin_applications(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    applications = get_pending_applications()

    if not applications:
        await callback.message.answer(
            "📭 Новых заявок на рассмотрении нет."
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

        tournament = get_tournament(tournament_id)
        tournament_name = tournament[1] if tournament else "Удалённый турнир"

        username_text = (
            f"@{username}"
            if username
            else "Не указан"
        )

        text = (
            f"📨 <b>Заявка #{app_id}</b>\n\n"
            f"🏆 <b>Турнир:</b> {tournament_name}\n"
            f"👤 <b>Telegram:</b> {username_text}\n"
            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n\n"
            f"🎮 <b>Ник:</b> {nickname}\n"
            f"🌍 <b>Часовой пояс:</b> {timezone}\n"
            f"🆔 <b>PUBG Mobile ID:</b> {game_id}\n"
            f"💳 <b>Оплата:</b> {payment}\n"
            f"📱 <b>ТГ юзернейм:</b> {tg_username}\n"
            f"🕐 <b>Время:</b> {created_at}"
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
        except Exception as e:
            logging.exception(
                "Ошибка при выводе заявки #%s: %s",
                app_id,
                e
            )

    await callback.answer(f"Показано заявок: {sent}")


# =========================================================
# ADMIN — УДАЛЕНИЕ
# =========================================================

@dp.callback_query(F.data == "admin_delete")
async def admin_delete(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournaments = get_all_tournaments()

    if not tournaments:
        await callback.message.answer("📭 Турниров нет.")
        await callback.answer()
        return

    buttons = []

    for tournament in tournaments:
        tournament_id, name, max_players, status, created_at = tournament

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {name}",
                callback_data=f"delete_tournament:{tournament_id}"
            )
        ])

    await callback.message.answer(
        "🗑 <b>Выберите турнир для удаления:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("delete_tournament:"))
async def delete_tournament_callback(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournament_id = int(callback.data.split(":")[1])
    tournament = get_tournament(tournament_id)

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
                    callback_data=f"confirm_delete:{tournament_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_delete"
                )
            ]
        ]
    )

    await callback.message.answer(
        f"⚠️ <b>Удалить турнир?</b>\n\n"
        f"🏆 {tournament[1]}\n"
        f"👥 Максимум: {tournament[2]}\n\n"
        "Все заявки этого турнира также будут удалены.",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournament_id = int(callback.data.split(":")[1])
    tournament = get_tournament(tournament_id)

    if not tournament:
        await callback.answer(
            "Турнир уже удалён.",
            show_alert=True
        )
        return

    delete_tournament(tournament_id)

    await callback.message.edit_text(
        f"{emoji(16, '✅')} <b>Турнир удалён.</b>\n\n"
        f"🏆 {tournament[1]}"
    )

    await callback.answer("Турнир удалён.")


@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")
    await callback.answer()


# =========================================================
# /LIST
# =========================================================

@dp.message(Command("list"))
async def list_command(message: Message):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Эта команда доступна только администратору."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "В данный момент нету активных турниров."
        )
        return

    buttons = []

    for tournament in tournaments:
        buttons.append([
            tournament_button(tournament, "list_tournament")
        ])

    await message.answer(
        "📋 <b>Выберите турнир:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("list_tournament:"))
async def list_tournament_callback(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournament_id = int(callback.data.split(":")[1])
    tournament = get_tournament(tournament_id)

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    players = get_accepted_players(tournament_id)

    if not players:
        await callback.message.answer(
            f"🏆 <b>{tournament[1]}</b>\n\n"
            "📭 Участников пока нет."
        )
        await callback.answer()
        return

    text = (
        f"🏆 <b>{tournament[1]}</b>\n\n"
        f"👥 Участники: <b>{len(players)}/{tournament[2]}</b>\n\n"
    )

    for index, player in enumerate(players, start=1):
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
            created_at
        ) = player

        text += (
            f"<b>{index}.</b> {nickname}\n"
            f"🆔 <code>{game_id}</code>\n"
        )

        if tg_username:
            text += f"📱 {tg_username}\n"

        text += "\n"

    await callback.message.answer(text)
    await callback.answer()


# =========================================================
# /SETKA
# =========================================================

@dp.message(Command("setka"))
async def setka_command(message: Message):
    if not admin_only(message.from_user.id):
        await message.answer(
            "⛔ Эта команда доступна только администратору."
        )
        return

    tournaments = get_active_tournaments()

    if not tournaments:
        await message.answer(
            "В данный момент нету активных турниров."
        )
        return

    buttons = []

    for tournament in tournaments:
        buttons.append([
            tournament_button(tournament, "setka_tournament")
        ])

    await message.answer(
        "🎲 <b>Выберите турнир для генерации сетки:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("setka_tournament:"))
async def setka_tournament_callback(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    tournament_id = int(callback.data.split(":")[1])
    tournament = get_tournament(tournament_id)

    if not tournament:
        await callback.answer(
            "Турнир не найден.",
            show_alert=True
        )
        return

    players = get_accepted_players(tournament_id)
    max_players = tournament[2]

    if len(players) < max_players:
        await callback.message.answer(
            f"⛔ <b>Сетка пока недоступна.</b>\n\n"
            f"🏆 Турнир: <b>{tournament[1]}</b>\n"
            f"👥 Зарегистрировано: <b>{len(players)}/{max_players}</b>\n\n"
            "Сетка будет доступна после набора "
            "максимального количества участников."
        )
        await callback.answer()
        return

    if len(players) % 2 != 0:
        await callback.message.answer(
            "⛔ Невозможно создать пары.\n\n"
            "Количество участников должно быть чётным."
        )
        await callback.answer()
        return

    random.shuffle(players)

    text = (
        f"🎲 <b>Сетка турнира</b>\n\n"
        f"🏆 <b>{tournament[1]}</b>\n"
        f"👥 Участников: <b>{len(players)}</b>\n\n"
    )

    for pair_number, i in enumerate(
        range(0, len(players), 2),
        start=1
    ):
        nickname1 = players[i][3]
        nickname2 = players[i + 1][3]

        text += (
            f"<b>{pair_number}.</b> "
            f"{nickname1} VS {nickname2}\n"
        )

    await callback.message.answer(text)
    await callback.answer("Сетка создана!")


# =========================================================
# ПРИНЯТЬ ЗАЯВКУ
# =========================================================

@dp.callback_query(F.data.startswith("accept:"))
async def accept_application(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    application_id = int(callback.data.split(":")[1])
    application = get_application(application_id)

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
            "Эта заявка уже обработана.",
            show_alert=True
        )
        return

    tournament = get_tournament(tournament_id)

    if not tournament or tournament[3] != "active":
        update_application_status(application_id, "rejected")

        await callback.answer(
            "Турнир больше недоступен.",
            show_alert=True
        )
        return

    players_count = get_accepted_players_count(tournament_id)

    if players_count >= tournament[2]:
        await callback.answer(
            "Максимальное количество участников уже набрано.",
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
            f"{emoji(8, '✅')} <b>Ваша заявка принята!</b>\n\n"
            f"🏆 Турнир: <b>{tournament[1]}</b>\n\n"
            f"{emoji(8, '📩')} Свяжитесь с "
            f"@{MANAGER_USERNAME}"
        )
    except Exception as e:
        logging.exception(
            "Не удалось уведомить пользователя: %s",
            e
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer("Заявка принята!")


# =========================================================
# ОТКЛОНИТЬ ЗАЯВКУ
# =========================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_application(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    application_id = int(callback.data.split(":")[1])
    application = get_application(application_id)

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
            "Эта заявка уже обработана.",
            show_alert=True
        )
        return

    update_application_status(
        application_id,
        "rejected"
    )

    try:
        await bot.send_message(
            user_id,
            f"{emoji(2, '❌')} <b>Ваша заявка отклонена.</b>\n\n"
            "Если вы считаете, что произошла ошибка, "
            "обратитесь в поддержку."
        )
    except Exception as e:
        logging.exception(
            "Не удалось уведомить пользователя: %s",
            e
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer("Заявка отклонена.")


# =========================================================
# ЗАПУСК
# =========================================================

async def main():
    logging.basicConfig(level=logging.INFO)

    init_db()
    await setup_commands()

    print("===================================")
    print("🤖 Wesoling Tournament Bot")
    print("🚀 Бот запущен!")
    print("===================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())