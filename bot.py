import asyncio
import logging
import secrets
import string

import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

# ============ КОНФИГ ============
BOT_TOKEN = "8805698610:AAGSvGd0b8ooEtHeROze8A-cG9CA84i-_gQ"
BOT_USERNAME = "@arrenda_nft_bot"
BRAND_NAME = "Arrenda NFT"
MANAGER_USERNAME = "@godwez"
SUPPORT_USERNAME = "@godwez"
STATS_CONTACT = "@godwez"
ADMIN_IDS = [8861315128]
DB_PATH = "arrenda_rent.db"

SUPPORT_PHOTO = "https://i.imgur.com/F6UddrX.jpeg"
BALANCE_PHOTO = "https://i.imgur.com/kumwHxs.jpeg"
REQUISITES_PHOTO = "https://i.imgur.com/TBrOAbO.jpeg"
MAIN_PHOTO = "https://tetchange.com/wp-content/uploads/photo-2024-10-10-08-44-07.jpg"

logging.basicConfig(level=logging.INFO)

# ============ ID ПРЕМИУМ-ЭМОДЗИ ============
E_GIFT = "5276422526350681413"
E_BRIEFCASE = "5276037216244624892"
E_ROCKET = "5206401524200145033"
E_HOURGLASS = "5276412364458059956"
E_EXCHANGE = "5276398496008663230"
E_MONEY = "5278227821364275264"
E_DIAMOND = "5278778882848220741"
E_BANK = "5238132025323444613"
E_CHECK = "5776375003280838798"
E_ONE = "5244961448525848230"
E_TWO = "5242293676834579345"
E_THREE = "5242652525647127686"
E_FOUR = "5242287453426969423"
E_STAR = "5206476089127372379"
E_CROWN = "5276229330131772747"
E_INFO = "5278753302023004775"
E_MSG = "5278589204207528856"
E_SHIELD = "5276262671962892944"
E_CART = "5276314275994954605"
E_SOS = "5278647306525108244"
E_USER = "5275979556308674886"
E_BACK = "5278413853577734640"
E_CARD = "5192689390136089826"
E_GLOBE = "5239963889004732575"
E_LINK = "5278305362703835500"

# ============ СОСТОЯНИЯ ============
class RentCreation(StatesGroup):
    entering_nft = State()
    entering_period = State()
    choosing_payment = State()
    entering_daily_price = State()

class Requisites(StatesGroup):
    entering_ton = State()
    choosing_region = State()
    entering_card = State()

# ============ УТИЛИТЫ ============
def generate_deal_code(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def get_currency(payment_method, user=None, region=None):
    if payment_method == "TON":
        return "TON"
    if payment_method == "Звёзды":
        return "⭐"
    if payment_method == "Карта/СБП":
        reg = region or (user["card_region"] if user else None) or "RU"
        return {"RU": "₽", "KZ": "₸", "UA": "₴", "BY": "Br"}.get(reg, "₽")
    return "$"

# ============ БАЗА ДАННЫХ ============
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                lang TEXT DEFAULT 'ru',
                balance REAL DEFAULT 0,
                successful_deals INTEGER DEFAULT 0,
                ton_wallet TEXT,
                card_region TEXT,
                card_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_code TEXT UNIQUE,
                seller_id INTEGER,
                buyer_id INTEGER,
                nft TEXT,
                period TEXT,
                payment_method TEXT,
                currency TEXT,
                daily_price REAL,
                status TEXT DEFAULT 'pending',
                start_date TIMESTAMP,
                last_paid_day INTEGER DEFAULT 0,
                total_paid REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await db.commit()

async def get_user(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return await cur.fetchone()

async def create_user(tg_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)",
            (tg_id, username or ""),
        )
        await db.commit()

async def set_user_lang(tg_id, lang):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET lang = ? WHERE tg_id = ?", (lang, tg_id))
        await db.commit()

async def set_ton_wallet(tg_id, wallet):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET ton_wallet = ? WHERE tg_id = ?", (wallet, tg_id))
        await db.commit()

async def set_card(tg_id, region, number):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET card_region = ?, card_number = ? WHERE tg_id = ?",
            (region, number, tg_id),
        )
        await db.commit()

async def create_deal(code, seller_id, nft, period, payment_method, currency, daily_price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO deals (deal_code, seller_id, nft, period, payment_method, currency, daily_price)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, seller_id, nft, period, payment_method, currency, daily_price),
        )
        await db.commit()

async def get_deal_by_code(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM deals WHERE deal_code = ?", (code,))
        return await cur.fetchone()

async def get_active_deal_by_seller(seller_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM deals WHERE seller_id = ? AND status = 'paid' ORDER BY id DESC LIMIT 1",
            (seller_id,),
        )
        return await cur.fetchone()

async def set_deal_buyer(code, buyer_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deals SET buyer_id = ? WHERE deal_code = ?", (buyer_id, code))
        await db.commit()

async def set_deal_status(code, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deals SET status = ? WHERE deal_code = ?", (status, code))
        await db.commit()

async def add_balance(tg_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, tg_id))
        await db.commit()

async def inc_deals(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET successful_deals = successful_deals + 1 WHERE tg_id = ?", (tg_id,)
        )
        await db.commit()

async def start_rent(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE deals
               SET status = 'active',
                   start_date = CURRENT_TIMESTAMP,
                   last_paid_day = 0,
                   total_paid = 0
               WHERE deal_code = ?""",
            (code,),
        )
        await db.commit()

async def get_active_rents():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM deals WHERE status = 'active'")
        return await cur.fetchall()

async def pay_day(code, new_day, paid_amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE deals
               SET last_paid_day = ?, total_paid = total_paid + ?
               WHERE deal_code = ?""",
            (new_day, paid_amount, code),
        )
        await db.commit()

async def close_rent(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE deals
               SET status = 'completed',
                   completed_at = CURRENT_TIMESTAMP
               WHERE deal_code = ?""",
            (code,),
        )
        await db.commit()

# ============ ТЕКСТЫ ============
TEXTS = {
    "ru": {
        "choose_lang": "<tg-emoji emoji-id='" + E_GLOBE + "'>🌐</tg-emoji> Выберите язык / Choose language / اختر اللغة:",
        "welcome": (
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> "
            "<b>ПРЕВРАТИ СВОИ NFT ПОДАРКИ В РЕАЛЬНЫЙ ДОХОД!</b> "
            "<tg-emoji emoji-id='" + E_STAR + "'>⭐</tg-emoji>\n\n"
            "Каждый NFT-подарок — это не просто знак внимания, "
            "а ценный цифровой актив, который может работать на тебя.\n\n"
            "<tg-emoji emoji-id='" + E_BRIEFCASE + "'>💼</tg-emoji> <b>Как это работает:</b>\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Ты сдаёшь свой NFT-подарок в аренду\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Получаешь фиксированную оплату <b>каждый день</b>\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Срок аренды выбираешь сам\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Мы берём на себя безопасность сделки и поиск арендатора\n\n"
            "<tg-emoji emoji-id='" + E_ROCKET + "'>🚀</tg-emoji> Нажми <b>«Заработать»</b>, чтобы начать."
        ),
        "btn_earn": "Заработать",
        "btn_support": "Поддержка",
        "btn_stats": "Статистика",
        "btn_profile": "Профиль",
        "btn_requisites": "Реквизиты",
        "btn_how": "Как работает",
        "btn_back_menu": "Вернуться в меню",
        "btn_paid": "Я оплатил",
        "btn_item_sent": "NFT передан менеджеру",
        "btn_add_ton": "Добавить/изменить GRAM-кошелёк",
        "btn_add_card": "Добавить карту/номер телефона",
        "btn_ton": "На GRAM-кошелёк",
        "btn_card": "Перевод на карту/СБП",
        "btn_stars": "Звёзды",
        "support_menu": "<tg-emoji emoji-id='" + E_SOS + "'>🆘</tg-emoji> Для связи с поддержкой нажмите на кнопку ниже:",
        "stats": (
            "<tg-emoji emoji-id='" + E_INFO + "'>ℹ️</tg-emoji> <b>Сводка по платформе</b>\n\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Оборот · $12 839\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> Сделок · 543\n"
            "<tg-emoji emoji-id='" + E_STAR + "'>⭐</tg-emoji> Рейтинг · 4.9 / 5.0\n"
            "<tg-emoji emoji-id='" + E_USER + "'>👤</tg-emoji> Онлайн · 68\n\n"
            "· · ·\n\n"
            "<tg-emoji emoji-id='" + E_SHIELD + "'>🛡️</tg-emoji> <b>Стандарт безопасности</b>\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Эскроу для каждой сделки\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Анти-фрод корпоративного уровня\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Верифицированные контрагенты\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Поддержка без выходных\n\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> <i>Данные обновляются каждые 5 минут</i>"
        ),
        "how_works": (
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> <b>Как устроен процесс аренды вашего NFT:</b>\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Создание сделки.</b>\n"
            "Вы заходите в наш официальный бот и открываете новую сделку под запрос покупателя.\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Оплата.</b>\n"
            "Покупатель вносит всю необходимую сумму, и средства замораживаются в системе для вашей безопасности.\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Подтверждение.</b>\n"
            "Мы одобряем сделку с нашей стороны, подтверждая её чистоту.\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Передача NFT.</b>\n"
            "Вы передаёте свой NFT нашему гарант-менеджеру.\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Получение дохода.</b>\n"
            "Вы ежедневно получаете фиксированную выплату на свой счёт "
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> на протяжении всего срока аренды."
        ),
        "earn_intro": (
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> <b>Сдача NFT в аренду</b>\n\n"
            "Чтобы начать зарабатывать на своём NFT-подарке, "
            "выполни 4 простых шага:\n\n"
            "<tg-emoji emoji-id='" + E_ONE + "'>1️⃣</tg-emoji> Скопируй <b>ссылку на свой NFT-подарок</b> и отправь её сюда\n"
            "<tg-emoji emoji-id='" + E_TWO + "'>2️⃣</tg-emoji> Укажи <b>срок аренды</b> (сколько дней сдаёшь)\n"
            "<tg-emoji emoji-id='" + E_THREE + "'>3️⃣</tg-emoji> Выбери <b>метод получения оплаты</b>\n"
            "<tg-emoji emoji-id='" + E_FOUR + "'>4️⃣</tg-emoji> Укажи <b>стоимость за 1 день</b> — сколько хочешь получать ежедневно\n\n"
            "<tg-emoji emoji-id='" + E_ROCKET + "'>🚀</tg-emoji> После этого мы сформируем сделку и пришлём ссылку для арендатора."
        ),
        "enter_nft_link": (
            "<tg-emoji emoji-id='" + E_LINK + "'>🔗</tg-emoji> <b>Шаг 1 из 4</b>\n\n"
            "Скопируйте <b>ссылку на NFT-подарок</b> и отправьте её сюда.\n\n"
            "Пример: <code>https://t.me/nft/Pepe-1234</code>"
        ),
        "enter_period": (
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> <b>Шаг 2 из 4</b>\n\n"
            "Укажите <b>срок аренды</b> в днях.\n\n"
            "Пример: <code>7</code> или <code>30</code>"
        ),
        "choose_payment": (
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> <b>Шаг 3 из 4</b>\n\n"
            "Выберите, <b>куда вы хотите получать оплату</b>:"
        ),
        "enter_daily_price": (
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> <b>Шаг 4 из 4</b>\n\n"
            "Укажите <b>стоимость аренды за 1 день</b> — сколько вы хотите получать ежедневно.\n\n"
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> Валюта: <b>{currency}</b>\n\n"
            "Пример: <code>15.5</code>"
        ),
        "invalid_number": "<tg-emoji emoji-id='" + E_CHECK + "'>❌</tg-emoji> Введите корректное число, например: <code>100.5</code>",
        "invalid_period": "<tg-emoji emoji-id='" + E_CHECK + "'>❌</tg-emoji> Срок должен быть целым числом больше 0",
        "req_not_added_ton": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>❌</tg-emoji> <b>TON-кошелёк не добавлен</b>\n\n"
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> Добавьте его в разделе «Реквизиты» и попробуйте снова."
        ),
        "req_not_added_card": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>❌</tg-emoji> <b>Карта/СБП не добавлены</b>\n\n"
            "<tg-emoji emoji-id='" + E_CARD + "'>💳</tg-emoji> Добавьте их в разделе «Реквизиты» и попробуйте снова."
        ),
        "deal_created": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Сделка аренды создана!</b>\n\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: <b>{nft}</b>\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> Срок: <b>{period} дн.</b>\n"
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> Способ оплаты: <b>{payment_method}</b>\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Оплата в день: <b>{daily_price} {currency}</b>\n"
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> Итого за срок: <b>{total} {currency}</b>\n\n"
            "<tg-emoji emoji-id='" + E_LINK + "'>🔗</tg-emoji> <b>Ссылка для арендатора:</b>\n{link}\n\n"
            "<i>Скопируйте ссылку и отправьте арендатору</i>"
        ),
        "profile": (
            "<tg-emoji emoji-id='" + E_BRIEFCASE + "'>💼</tg-emoji> <b>ВАШ ПРОФИЛЬ</b>\n\n"
            "<tg-emoji emoji-id='" + E_USER + "'>👤</tg-emoji> Пользователь: @{username}\n\n"
            "Доступные средства:\n"
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> <b>{balance}</b>\n\n"
            "<tg-emoji emoji-id='" + E_BANK + "'>🏦</tg-emoji> <b>ВЫВОД ОТ 3-Х СДЕЛОК</b>\n\n"
            "<tg-emoji emoji-id='" + E_BANK + "'>🏦</tg-emoji> <b>Информация о выводе средств:</b>\n"
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> TON-кошелёк: {ton}\n"
            "<tg-emoji emoji-id='" + E_CARD + "'>💳</tg-emoji> Карта / СБП: {card}\n\n"
            "<tg-emoji emoji-id='" + E_BRIEFCASE + "'>💼</tg-emoji> Успешных сделок: <b>{deals}</b>"
        ),
        "req_menu": (
            "<tg-emoji emoji-id='" + E_MSG + "'>📨</tg-emoji> <b>Управление реквизитами</b>\n\n"
            "<tg-emoji emoji-id='" + E_INFO + "'>ℹ️</tg-emoji> Используйте кнопки ниже чтобы добавить/изменить реквизиты 🔽"
        ),
        "enter_ton": (
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> <b>Добавьте ваш TON-кошелёк:</b>\n\n"
            "Пожалуйста, отправьте адрес вашего кошелька"
        ),
        "ton_added": "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Адрес успешно добавлен</b>",
        "choose_region": "<tg-emoji emoji-id='" + E_GLOBE + "'>🌍</tg-emoji> <b>Выберите регион вашей карты / телефона:</b>",
        "enter_card": "<tg-emoji emoji-id='" + E_CARD + "'>💳</tg-emoji> Отправьте номер карты или телефона:",
        "card_added": "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>Реквизиты успешно добавлены</b>",
        "not_added": "🚫 не добавлен",
        "not_added_req": "🚫 Реквизиты не добавлены",
        "empty": "0.00 (Пусто)",
        "join_deal": (
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> <b>Сделка аренды #{code}</b>\n\n"
            "<tg-emoji emoji-id='" + E_USER + "'>👤</tg-emoji> Владелец NFT: @{seller}\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: {nft}\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> Срок: <b>{period} дн.</b>\n"
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> Способ оплаты: <b>{payment_method}</b>\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Оплата в день: <b>{daily_price} {currency}</b>\n"
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> Итого: <b>{total} {currency}</b>\n\n"
            "Нажмите «Я оплатил» после перевода."
        ),
        "buyer_paid": "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Вы подтвердили оплату. Ожидайте подтверждения от менеджера.",
        "item_sent_ok": "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> NFT передан менеджеру. Ожидайте запуска аренды.",
        "payment_confirmed_seller": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>🎉</tg-emoji> <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Арендатор @{buyer} подтвердил оплату\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> Сделка: <b>#{code}</b>\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: {nft}\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> Срок: <b>{period} дн.</b>\n"
            "<tg-emoji emoji-id='" + E_EXCHANGE + "'>💱</tg-emoji> Способ оплаты: <b>{payment_method}</b>\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Оплата в день: <b>{daily_price} {currency}</b>\n\n"
            "<tg-emoji emoji-id='" + E_INFO + "'>⚠️</tg-emoji> <b>ТРЕБУЕТСЯ ВАШЕ ДЕЙСТВИЕ:</b>\n"
            "<tg-emoji emoji-id='" + E_ONE + "'>1️⃣</tg-emoji> Передайте NFT менеджеру {manager}\n"
            "<tg-emoji emoji-id='" + E_TWO + "'>2️⃣</tg-emoji> После передачи нажмите кнопку ниже\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>🚫</tg-emoji> <b>Не передавайте NFT арендатору напрямую!</b>"
        ),
        "deal_started_seller": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>АРЕНДА ЗАПУЩЕНА!</b>\n\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: <b>{nft}</b>\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Начисление: <b>{daily_price} {currency} / день</b>\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> Срок: <b>{period} дн.</b>\n\n"
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Средства будут поступать на ваш баланс <b>каждый день</b>.\n"
            "<tg-emoji emoji-id='" + E_BRIEFCASE + "'>💼</tg-emoji> Проверить: раздел «Профиль»"
        ),
        "daily_payout_notify": (
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> <b>Начисление за аренду</b>\n\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: <b>{nft}</b>\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> День: <b>{day} / {period}</b>\n"
            "<tg-emoji emoji-id='" + E_DIAMOND + "'>💎</tg-emoji> Зачислено: <b>{amount} {currency}</b>"
        ),
        "rent_finished_seller": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> <b>АРЕНДА ЗАВЕРШЕНА</b>\n\n"
            "<tg-emoji emoji-id='" + E_GIFT + "'>🎁</tg-emoji> NFT: <b>{nft}</b>\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> Все выплаты за срок аренды зачислены на ваш баланс."
        ),
        "seller_item_sent_notify": (
            "<tg-emoji emoji-id='" + E_GIFT + "'>📦</tg-emoji> Владелец NFT нажал на кнопку:\n"
            "«NFT передан менеджеру»"
        ),
        "deal_not_found": "<tg-emoji emoji-id='" + E_CHECK + "'>❌</tg-emoji> Сделка не найдена.",
        "no_active_deals": "Нет активных сделок в статусе paid",
        "no_buyer": "Нет арендатора",
        "deal_already_done": "Сделка уже обработана",
        "error": "Ошибка",
        "admin_deal_started": (
            "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Аренда #{code} запущена\n"
            "<tg-emoji emoji-id='" + E_MONEY + "'>💰</tg-emoji> В день: {daily} {currency}\n"
            "<tg-emoji emoji-id='" + E_HOURGLASS + "'>⏳</tg-emoji> Срок: {period} дней"
        ),
        "admin_set_deals_usage": "Использование: /set_my_deals <число>",
        "admin_set_deals_ok": "<tg-emoji emoji-id='" + E_CHECK + "'>✅</tg-emoji> Установлено {n} успешных сделок",
    },
}

TEXTS["en"] = TEXTS["ru"]
TEXTS["zh"] = TEXTS["ru"]

def t(lang, key):
    return TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"].get(key, key))

def get_lang(user):
    return user["lang"] if user and user["lang"] else "ru"

# ============ КЛАВИАТУРЫ ============
def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
        InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang:zh"),
    ]])

def main_menu_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_earn"),
            callback_data="earn",
            icon_custom_emoji_id=E_CART,
        )],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_profile"),
                callback_data="balance",
                icon_custom_emoji_id=E_BRIEFCASE,
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_requisites"),
                callback_data="requisites",
                icon_custom_emoji_id=E_MSG,
            ),
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_how"),
                callback_data="how_works",
                icon_custom_emoji_id=E_INFO,
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_stats"),
                callback_data="stats",
                icon_custom_emoji_id=E_INFO,
            ),
        ],
        [InlineKeyboardButton(
            text=t(lang, "btn_support"),
            callback_data="support",
            icon_custom_emoji_id=E_SOS,
        )],
    ])

def back_menu_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )]
    ])

def support_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_support"),
            url="https://t.me/" + SUPPORT_USERNAME.lstrip('@'),
            icon_custom_emoji_id=E_SOS,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

def earn_start_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Начать",
            callback_data="earn_start",
            icon_custom_emoji_id=E_ROCKET,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

def payment_method_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_ton"),
            callback_data="method:TON",
            icon_custom_emoji_id=E_DIAMOND,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_card"),
            callback_data="method:Карта/СБП",
            icon_custom_emoji_id=E_CARD,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_stars"),
            callback_data="method:Звёзды",
            icon_custom_emoji_id=E_STAR,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

def item_sent_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_item_sent"), callback_data="item_sent")],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

def buyer_pay_kb(code, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_paid"),
            callback_data="paid:" + code,
            icon_custom_emoji_id=E_CHECK,
        )]
    ])

def req_menu_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang, "btn_add_ton"),
            callback_data="req:ton",
            icon_custom_emoji_id=E_DIAMOND,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_add_card"),
            callback_data="req:card",
            icon_custom_emoji_id=E_CARD,
        )],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

def region_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="region:RU")],
        [InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="region:KZ")],
        [InlineKeyboardButton(text="🇺🇦 Украина", callback_data="region:UA")],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data="region:BY")],
        [InlineKeyboardButton(
            text=t(lang, "btn_back_menu"),
            callback_data="main_menu",
            icon_custom_emoji_id=E_BACK,
        )],
    ])

# ============ РОУТЕРЫ ============
start_router = Router()
menu_router = Router()
earn_router = Router()
balance_router = Router()
req_router = Router()
support_router = Router()
stats_router = Router()
how_router = Router()
deal_router = Router()
admin_router = Router()

# ---------- /start ----------
@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await create_user(message.from_user.id, message.from_user.username)

    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1]:
        await handle_buyer_entry(message, args[1])
        return

    await message.answer(TEXTS["ru"]["choose_lang"], reply_markup=lang_kb())

@start_router.callback_query(F.data.startswith("lang:"))
async def set_lang(cb: CallbackQuery, state: FSMContext):
    lang = cb.data.split(":")[1]
    await set_user_lang(cb.from_user.id, lang)
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer_photo(
        photo=MAIN_PHOTO,
        caption=t(lang, "welcome"),
        reply_markup=main_menu_kb(lang),
    )
    await cb.answer()

# ---------- Главное меню ----------
@menu_router.callback_query(F.data == "main_menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer_photo(
        photo=MAIN_PHOTO,
        caption=t(lang, "welcome"),
        reply_markup=main_menu_kb(lang),
    )
    await cb.answer()

# ---------- Как работает ----------
@how_router.callback_query(F.data == "how_works")
async def how_works_handler(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "how_works"), reply_markup=back_menu_kb(lang))
    await cb.answer()

# ---------- Статистика ----------
@stats_router.callback_query(F.data == "stats")
async def stats_handler(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "stats"), reply_markup=back_menu_kb(lang))
    await cb.answer()

# ---------- Поддержка ----------
@support_router.callback_query(F.data == "support")
async def support_handler(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer_photo(
        photo=SUPPORT_PHOTO,
        caption=t(lang, "support_menu"),
        reply_markup=support_kb(lang),
    )
    await cb.answer()

# ---------- Заработать ----------
@earn_router.callback_query(F.data == "earn")
async def earn_intro(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "earn_intro"), reply_markup=earn_start_kb(lang))
    await cb.answer()

@earn_router.callback_query(F.data == "earn_start")
async def earn_start(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    await state.update_data(lang=lang)
    await state.set_state(RentCreation.entering_nft)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "enter_nft_link"), reply_markup=back_menu_kb(lang))
    await cb.answer()

@earn_router.message(RentCreation.entering_nft)
async def enter_nft(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    nft = message.text.strip()
    if not nft:
        await message.answer(t(lang, "enter_nft_link"), reply_markup=back_menu_kb(lang))
        return
    await state.update_data(nft=nft)
    await state.set_state(RentCreation.entering_period)
    await message.answer(t(lang, "enter_period"), reply_markup=back_menu_kb(lang))

@earn_router.message(RentCreation.entering_period)
async def enter_period(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    try:
        period = int(message.text.strip())
        if period <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t(lang, "invalid_period"), reply_markup=back_menu_kb(lang))
        return
    await state.update_data(period=period)
    await state.set_state(RentCreation.choosing_payment)
    await message.answer(t(lang, "choose_payment"), reply_markup=payment_method_kb(lang))

@earn_router.callback_query(F.data.startswith("method:"), RentCreation.choosing_payment)
async def choose_method(cb: CallbackQuery, state: FSMContext):
    method = cb.data.split(":", 1)[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")

    user = await get_user(cb.from_user.id)
    if method == "TON" and not user["ton_wallet"]:
        await cb.answer()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(t(lang, "req_not_added_ton"), reply_markup=back_menu_kb(lang))
        return
    if method == "Карта/СБП" and not user["card_number"]:
        await cb.answer()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(t(lang, "req_not_added_card"), reply_markup=back_menu_kb(lang))
        return

    currency = get_currency(method, user=user)
    await state.update_data(payment_method=method, currency=currency)
    await state.set_state(RentCreation.entering_daily_price)

    msg = t(lang, "enter_daily_price").replace("{currency}", str(currency))
    await cb.message.edit_text(msg, reply_markup=back_menu_kb(lang))
    await cb.answer()

@earn_router.message(RentCreation.entering_daily_price)
async def enter_daily_price(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    try:
        daily_price = float(message.text.replace(",", "."))
        if daily_price <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t(lang, "invalid_number"), reply_markup=back_menu_kb(lang))
        return

    nft = data["nft"]
    period = data["period"]
    payment_method = data["payment_method"]
    currency = data["currency"]
    total = round(daily_price * period, 2)

    code = generate_deal_code()
    await create_deal(code, message.from_user.id, nft, period, payment_method, currency, daily_price)
    await state.clear()

    bot_info = await bot.get_me()
    link = "https://t.me/" + bot_info.username + "?start=" + code

    msg = t(lang, "deal_created")
    msg = msg.replace("{nft}", str(nft))
    msg = msg.replace("{period}", str(period))
    msg = msg.replace("{payment_method}", str(payment_method))
    msg = msg.replace("{daily_price}", str(daily_price))
    msg = msg.replace("{total}", str(total))
    msg = msg.replace("{currency}", str(currency))
    msg = msg.replace("{link}", str(link))

    await message.answer(
        msg,
        reply_markup=back_menu_kb(lang),
        disable_web_page_preview=True,
    )

# ---------- Вход арендатора ----------
async def handle_buyer_entry(message: Message, code: str):
    deal = await get_deal_by_code(code)
    if not deal:
        await message.answer(TEXTS["ru"]["deal_not_found"])
        return
    await set_deal_buyer(code, message.from_user.id)
    seller = await get_user(deal["seller_id"])
    seller_username = seller["username"] if seller else "unknown"
    buyer = await get_user(message.from_user.id)
    lang = get_lang(buyer)

    total = round(deal["daily_price"] * int(deal["period"]), 2)
    currency = deal["currency"] or "$"

    msg = t(lang, "join_deal")
    msg = msg.replace("{code}", str(deal["deal_code"]))
    msg = msg.replace("{seller}", str(seller_username))
    msg = msg.replace("{nft}", str(deal["nft"]))
    msg = msg.replace("{period}", str(deal["period"]))
    msg = msg.replace("{payment_method}", str(deal["payment_method"]))
    msg = msg.replace("{daily_price}", str(deal["daily_price"]))
    msg = msg.replace("{total}", str(total))
    msg = msg.replace("{currency}", str(currency))

    await message.answer(msg, reply_markup=buyer_pay_kb(code, lang))

@deal_router.callback_query(F.data.startswith("paid:"))
async def buyer_paid(cb: CallbackQuery, bot: Bot):
    code = cb.data.split(":", 1)[1]
    deal = await get_deal_by_code(code)
    if not deal:
        await cb.answer(TEXTS["ru"]["deal_not_found"], show_alert=True)
        return
    if deal["status"] != "pending":
        await cb.answer(TEXTS["ru"]["deal_already_done"], show_alert=True)
        return

    await set_deal_status(code, "paid")
    buyer = await get_user(cb.from_user.id)
    lang = get_lang(buyer)
    await cb.message.edit_text(t(lang, "buyer_paid"))
    await cb.answer()

    buyer_username = cb.from_user.username or str(cb.from_user.id)
    seller = await get_user(deal["seller_id"])
    seller_lang = get_lang(seller) if seller else "ru"
    currency = deal["currency"] or "$"

    msg = t(seller_lang, "payment_confirmed_seller")
    msg = msg.replace("{buyer}", str(buyer_username))
    msg = msg.replace("{code}", str(code))
    msg = msg.replace("{nft}", str(deal["nft"]))
    msg = msg.replace("{period}", str(deal["period"]))
    msg = msg.replace("{payment_method}", str(deal["payment_method"]))
    msg = msg.replace("{daily_price}", str(deal["daily_price"]))
    msg = msg.replace("{currency}", str(currency))
    msg = msg.replace("{manager}", str(MANAGER_USERNAME))

    try:
        await bot.send_message(
            deal["seller_id"],
            msg,
            reply_markup=item_sent_kb(seller_lang),
        )
    except Exception as e:
        logging.error(f"Не смог отправить владельцу: {e}")

@deal_router.callback_query(F.data == "item_sent")
async def item_sent(cb: CallbackQuery, bot: Bot):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    await cb.message.edit_text(t(lang, "item_sent_ok"), reply_markup=back_menu_kb(lang))
    await cb.answer()

    deal = await get_active_deal_by_seller(cb.from_user.id)
    if deal and deal["buyer_id"]:
        buyer = await get_user(deal["buyer_id"])
        buyer_lang = get_lang(buyer) if buyer else "ru"
        try:
            await bot.send_message(deal["buyer_id"], t(buyer_lang, "seller_item_sent_notify"))
        except Exception as e:
            logging.error(f"Не смог отправить арендатору: {e}")

# ---------- Профиль ----------
@balance_router.callback_query(F.data == "balance")
async def show_balance(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    if not user:
        await cb.answer(TEXTS["ru"]["error"], show_alert=True)
        return
    lang = get_lang(user)
    balance_str = f"{user['balance']:.2f}" if user["balance"] else t(lang, "empty")
    ton = user["ton_wallet"] if user["ton_wallet"] else t(lang, "not_added")
    card = (
        f"{user['card_region']} · {user['card_number']}"
        if user["card_number"] else t(lang, "not_added_req")
    )

    msg = t(lang, "profile")
    msg = msg.replace("{username}", str(user["username"] or str(user["tg_id"])))
    msg = msg.replace("{balance}", str(balance_str))
    msg = msg.replace("{ton}", str(ton))
    msg = msg.replace("{card}", str(card))
    msg = msg.replace("{deals}", str(user["successful_deals"]))

    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer_photo(
        photo=BALANCE_PHOTO,
        caption=msg,
        reply_markup=back_menu_kb(lang),
    )
    await cb.answer()

# ---------- Реквизиты ----------
@req_router.callback_query(F.data == "requisites")
async def req_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer_photo(
        photo=REQUISITES_PHOTO,
        caption=t(lang, "req_menu"),
        reply_markup=req_menu_kb(lang),
    )
    await cb.answer()

@req_router.callback_query(F.data == "req:ton")
async def req_ton(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    await state.update_data(lang=lang)
    await state.set_state(Requisites.entering_ton)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "enter_ton"), reply_markup=back_menu_kb(lang))
    await cb.answer()

@req_router.message(Requisites.entering_ton)
async def save_ton(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await set_ton_wallet(message.from_user.id, message.text.strip())
    await state.clear()
    await message.answer(t(lang, "ton_added"), reply_markup=back_menu_kb(lang))

@req_router.callback_query(F.data == "req:card")
async def req_card(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = get_lang(user)
    await state.update_data(lang=lang)
    await state.set_state(Requisites.choosing_region)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "choose_region"), reply_markup=region_kb(lang))
    await cb.answer()

@req_router.callback_query(F.data.startswith("region:"))
async def choose_region(cb: CallbackQuery, state: FSMContext):
    region = cb.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(region=region)
    await state.set_state(Requisites.entering_card)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(t(lang, "enter_card"), reply_markup=back_menu_kb(lang))
    await cb.answer()

@req_router.message(Requisites.entering_card)
async def save_card(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await set_card(message.from_user.id, data["region"], message.text.strip())
    await state.clear()
    await message.answer(t(lang, "card_added"), reply_markup=back_menu_kb(lang))

# ---------- Служебные команды ----------
@admin_router.message(Command("rteam"))
async def cmd_rteam(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM deals WHERE status = 'paid' ORDER BY id DESC LIMIT 1"
        )
        deal = await cur.fetchone()
    if not deal:
        await message.answer(TEXTS["ru"]["no_active_deals"])
        return
    if not deal["buyer_id"]:
        await message.answer(TEXTS["ru"]["no_buyer"])
        return

    await start_rent(deal["deal_code"])
    currency = deal["currency"] or "$"

    seller = await get_user(deal["seller_id"])
    seller_lang = get_lang(seller) if seller else "ru"

    msg = t(seller_lang, "deal_started_seller")
    msg = msg.replace("{nft}", str(deal["nft"]))
    msg = msg.replace("{daily_price}", str(deal["daily_price"]))
    msg = msg.replace("{currency}", str(currency))
    msg = msg.replace("{period}", str(deal["period"]))

    try:
        await message.bot.send_message(deal["seller_id"], msg)
    except Exception as e:
        logging.error(e)

    msg2 = t("ru", "admin_deal_started")
    msg2 = msg2.replace("{code}", str(deal["deal_code"]))
    msg2 = msg2.replace("{daily}", str(deal["daily_price"]))
    msg2 = msg2.replace("{currency}", str(currency))
    msg2 = msg2.replace("{period}", str(deal["period"]))

    await message.answer(msg2)

@admin_router.message(Command("set_my_deals"))
async def cmd_set_my_deals(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer(t("ru", "admin_set_deals_usage"))
        return
    n = int(args[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET successful_deals = ? WHERE tg_id = ?",
            (n, message.from_user.id),
        )
        await db.commit()
    msg = t("ru", "admin_set_deals_ok").replace("{n}", str(n))
    await message.answer(msg)

# ============ ФОНОВОЕ НАЧИСЛЕНИЕ ============
async def daily_payout_loop(bot: Bot):
    while True:
        try:
            rents = await get_active_rents()
            for deal in rents:
                async with aiosqlite.connect(DB_PATH) as db:
                    db.row_factory = aiosqlite.Row
                    cur = await db.execute(
                        """SELECT
                             CAST((julianday('now') - julianday(start_date)) AS INTEGER) AS days_passed
                           FROM deals WHERE deal_code = ?""",
                        (deal["deal_code"],),
                    )
                    row = await cur.fetchone()
                days_passed = row["days_passed"] if row else 0

                period = int(deal["period"])
                last_paid = deal["last_paid_day"] or 0
                currency = deal["currency"] or "$"

                while last_paid < days_passed and last_paid < period:
                    last_paid += 1
                    amount = round(deal["daily_price"], 2)
                    await add_balance(deal["seller_id"], amount)
                    await pay_day(deal["deal_code"], last_paid, amount)

                    seller = await get_user(deal["seller_id"])
                    seller_lang = get_lang(seller) if seller else "ru"

                    msg = t(seller_lang, "daily_payout_notify")
                    msg = msg.replace("{nft}", str(deal["nft"]))
                    msg = msg.replace("{day}", str(last_paid))
                    msg = msg.replace("{period}", str(period))
                    msg = msg.replace("{amount}", str(amount))
                    msg = msg.replace("{currency}", str(currency))

                    try:
                        await bot.send_message(deal["seller_id"], msg)
                    except Exception as e:
                        logging.error(f"Не смог уведомить о начислении: {e}")

                if last_paid >= period:
                    await close_rent(deal["deal_code"])
                    await inc_deals(deal["seller_id"])
                    seller = await get_user(deal["seller_id"])
                    seller_lang = get_lang(seller) if seller else "ru"

                    msg = t(seller_lang, "rent_finished_seller").replace("{nft}", str(deal["nft"]))
                    try:
                        await bot.send_message(deal["seller_id"], msg)
                    except Exception as e:
                        logging.error(e)

        except Exception as e:
            logging.error(f"Ошибка в daily_payout_loop: {e}")

        await asyncio.sleep(3600)

# ============ ЗАПУСК ============
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(how_router)
    dp.include_router(stats_router)
    dp.include_router(support_router)
    dp.include_router(earn_router)
    dp.include_router(deal_router)
    dp.include_router(balance_router)
    dp.include_router(req_router)
    dp.include_router(admin_router)

    asyncio.create_task(daily_payout_loop(bot))

    print("🚀 " + BRAND_NAME + " bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
