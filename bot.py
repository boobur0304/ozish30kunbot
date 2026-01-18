# ================================
# FINAL BOT — OZISH 30 KUNLIK
# Model: 1-kun pullik, 2-kun upsell, 4-kun aqlli blok
# Support: savol → admin → reply orqali javob
# Aiogram v3
# ================================

import logging
import json
import os
import uuid
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
# Karta raqami (to‘g‘ridan-to‘g‘ri yozilgan)
CARD_NUMBER = "9860 3501 1046 1737"

ENTRY_PRICE = 12000
UPSELL_PRICE = 59000
MAX_FREE_DAYS = 3

# ---------------- INIT ----------------
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

logging.basicConfig(level=logging.INFO)

# ---------------- FILES ----------------
USERS_PATH = "database/users.json"
TOKENS_PATH = "database/tokens.json"

os.makedirs("database", exist_ok=True)
for p in (USERS_PATH, TOKENS_PATH):
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump({}, f)

# ---------------- STATES ----------------
class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()
    question = State()

# ---------------- HELPERS ----------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    users = load_json(USERS_PATH)
    return users.get(str(user_id))

def set_user(user_id, data):
    users = load_json(USERS_PATH)
    users[str(user_id)] = data
    save_json(USERS_PATH, users)

def read_day(day):
    path = f"data/day{day}.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi"

# ---------------- KEYBOARDS ----------------
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Bugungi kun"), KeyboardButton(text="▶️ Keyingi kun")],
            [KeyboardButton(text="📊 Natijam"), KeyboardButton(text="💬 Savol berish")]
        ],
        resize_keyboard=True
    )

def upsell_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔓 30 kunni ochish", callback_data="open_30")]]
    )

# ---------------- TEXTS ----------------
START_TEXT = (
    "Agar qorin va bel ketmayotgan bo‘lsa,\n"
    "muammo sizda emas.\n\n"
    "Bu 30 kunlik aniq tizim.\n"
    "Ko‘pchilik 7–10 kundan keyin farqni sezadi.\n\n"
    "Boshlash uchun minimal summa — 12 000 so‘m\n\n"
    "Boshlash uchun ismingizni yozing 👇"
)

UPSELL_TEXT = (
    "Agar shu yerga yetib kelgan bo‘lsang — sen boshlading.\n\n"
    "Keyingi 28 kunda:\n"
    "• qorin va bel ketadi\n"
    "• ochlik kamayadi\n"
    "• vazn barqaror tushadi\n\n"
    f"🔥 30 kunlik davom ettirish — {UPSELL_PRICE:,} so‘m"
)

DAY4_BLOCKS = [
    "🔒 4-kun hozircha yopiq. Asosiy natijalar endi boshlanadi.",
    "ℹ️ Ko‘pchilik aynan shu joyda tashlab ketadi.",
    "⏳ To‘xtasang — yana boshidan. Davom etsang — natija bo‘ladi."
]

# ---------------- START ----------------
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer(START_TEXT)
    await state.set_state(Form.name)

@router.message(Form.name)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Form.surname)

@router.message(Form.surname)
async def surname(message: Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("Yoshingizni kiriting:")
    await state.set_state(Form.age)

@router.message(Form.age)
async def age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Vazningizni kiriting:")
    await state.set_state(Form.weight)

@router.message(Form.weight)
async def weight(message: Message, state: FSMContext):
    data = await state.get_data()
    user = {
        **data,
        "weight": message.text,
        "day": 1,
        "paid_entry": False,
        "paid_full": False,
        "upsell_shown": False,
        "day4_attempts": 0
    }
    set_user(message.from_user.id, user)
    await message.answer("Boshladik!", reply_markup=main_menu())
    await state.clear()

# ---------------- DAYS ----------------
@router.message(F.text == "📅 Bugungi kun")
async def today(message: Message):
    user = get_user(message.from_user.id)
    day = user["day"]

    if day == 1 and not user.get("paid_entry"):
        await message.answer(
            f"🔒 1-kun yopiq\n\n"
            f"Boshlash uchun minimal summa: {ENTRY_PRICE:,} so‘m\n"
            f"Karta: {CARD_NUMBER}\n\n"
            "📸 Chekni rasm qilib botga yuboring"
        )
        return

    if day > MAX_FREE_DAYS and not user.get("paid_full"):
        idx = min(user["day4_attempts"], 2)
        user["day4_attempts"] += 1
        set_user(message.from_user.id, user)
        await message.answer(DAY4_BLOCKS[idx], reply_markup=upsell_keyboard())
        return

    text = read_day(day)
    await message.answer(text, reply_markup=main_menu())

    if day == 2 and not user.get("upsell_shown"):
        user["upsell_shown"] = True
        set_user(message.from_user.id, user)
        await message.answer(UPSELL_TEXT, reply_markup=upsell_keyboard())

@router.message(F.text == "▶️ Keyingi kun")
async def next_day(message: Message):
    user = get_user(message.from_user.id)
    user["day"] += 1
    set_user(message.from_user.id, user)
    await today(message)

@router.message(F.text == "📊 Natijam")
async def result(message: Message):
    user = get_user(message.from_user.id)
    d = user["day"]
    if d <= 2:
        text = "Tanangiz moslashmoqda."
    elif d <= 5:
        text = "Birinchi o‘zgarishlar boshlandi."
    else:
        text = "Natija mustahkamlanmoqda."
    await message.answer(text)

# ---------------- SUPPORT ----------------
@router.message(F.text == "💬 Savol berish")
async def ask(message: Message, state: FSMContext):
    await message.answer("Savolingizni yozing:")
    await state.set_state(Form.question)

@router.message(Form.question)
async def handle_question(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    text = (
        f"❓ Yangi savol\n"
        f"👤 {user['name']} {user['surname']}\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"✍️ {message.text}\n\n"
        "↩️ Javob berish uchun reply qiling"
    )
    await bot.send_message(ADMIN_ID, text)
    await message.answer("✅ Savolingiz yuborildi")
    await state.clear()

@router.message(F.reply_to_message)
async def admin_reply(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if "🆔 ID:" in message.reply_to_message.text:
        uid = int(message.reply_to_message.text.split("🆔 ID:")[1].split()[0])
        await bot.send_message(uid, f"💬 Admin javobi:\n\n{message.text}")

# ---------------- PAYMENTS ----------------
@router.message(F.photo)
async def payment(message: Message):
    user = get_user(message.from_user.id)
    token = f"PAY-{uuid.uuid4().hex[:6]}"
    tokens = load_json(TOKENS_PATH)
    tokens[token] = message.from_user.id
    save_json(TOKENS_PATH, tokens)

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"To‘lov cheki\nID: {message.from_user.id}\nToken: {token}"
    )
    await message.answer("Chek yuborildi. Tasdiqlanishini kuting")

@router.message(F.text.startswith("PAY-"))
async def confirm(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    tokens = load_json(TOKENS_PATH)
    uid = tokens.pop(message.text, None)
    save_json(TOKENS_PATH, tokens)
    if not uid:
        return
    user = get_user(uid)
    if not user.get("paid_entry"):
        user["paid_entry"] = True
    else:
        user["paid_full"] = True
    set_user(uid, user)
    await bot.send_message(uid, "✅ To‘lov tasdiqlandi")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
