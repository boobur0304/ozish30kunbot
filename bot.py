# ================================
# FINAL BOT — OZISH 30 KUNLIK (STABLE)
# 1-kun pullik, 2-kun upsell, 4-kun aqlli blok
# Admin xabarlari + Natijam + Savol-javob
# 30 kun FULL ochish to‘liq ishlaydi
# Aiogram v3
# ================================

import logging
import json
import os
import uuid
import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 983517327
CARD_NUMBER = "9860 3501 1046 1737"

ENTRY_PRICE = 12000
UPSELL_PRICE = 59000
MAX_FREE_DAYS = 3
TOTAL_DAYS = 30

# ---------------- INIT ----------------
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
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

def get_user(uid):
    return load_json(USERS_PATH).get(str(uid))

def set_user(uid, data):
    users = load_json(USERS_PATH)
    users[str(uid)] = data
    save_json(USERS_PATH, users)

def read_day(day):
    path = f"data/days/day{day}.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi"

# ---------------- KEYBOARDS ----------------
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📅 Bugungi kun"), KeyboardButton("▶️ Keyingi kun")],
            [KeyboardButton("📊 Natijam"), KeyboardButton("💬 Savol berish")]
        ],
        resize_keyboard=True
    )

def upsell_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔓 30 kunni ochish", callback_data="open_30")]
        ]
    )

# ---------------- TEXTS ----------------
START_TEXT = (
    "🥗 Agar qorin va bel ketmayotgan bo‘lsa, bu sizning aybingiz emas.\n\n"
    "Bu — 30 kunlik aniq tizim.\n"
    "Ko‘pchilik 7–10 kunda farqni sezadi.\n\n"
    "💰 Boshlash uchun minimal summa — 12 000 so‘m\n\n"
    "👇 Boshlash uchun ismingizni yozing"
)

UPSELL_TEXT = (
    "🌱 Siz allaqachon boshladingiz.\n\n"
    "Keyingi 28 kunda:\n"
    "• qorin va bel sekin kamayadi\n"
    "• ochlik pasayadi\n"
    "• vazn barqaror tushadi\n\n"
    f"🔥 30 kunlik to‘liq dastur — {UPSELL_PRICE:,} so‘m"
)

DAY4_BLOCKS = [
    "🔒 4-kun yopiq.\n\nAsosiy o‘zgarishlar aynan shu yerdan boshlanadi.",
    "ℹ️ Ko‘pchilik 5–7-kunlarda aniq farqni sezadi.",
    "⏳ Bu safar oxirigacha borganlar natija oladi."
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
        "day4_attempts": 0,
        "payment_mode": "ENTRY"
    }
    set_user(message.from_user.id, user)

    await bot.send_message(
        ADMIN_ID,
        f"🆕 Yangi foydalanuvchi\n"
        f"👤 {user['name']} {user['surname']}\n"
        f"🆔 {message.from_user.id}"
    )

    await message.answer("Boshladik!", reply_markup=main_menu())
    await state.clear()

# ---------------- DAYS ----------------
@router.message(F.text == "📅 Bugungi kun")
async def today(message: Message):
    user = get_user(message.from_user.id)
    day = user["day"]

    if day == 1 and not user["paid_entry"]:
        await message.answer(
            f"🔒 1-kun yopiq\n\n"
            f"💰 {ENTRY_PRICE:,} so‘m\n"
            f"💳 {CARD_NUMBER}\n\n"
            "📸 Chekni yuboring"
        )
        return

    if day > MAX_FREE_DAYS and not user["paid_full"]:
        idx = min(user["day4_attempts"], 2)
        user["day4_attempts"] += 1
        set_user(message.from_user.id, user)
        await message.answer(DAY4_BLOCKS[idx], reply_markup=upsell_keyboard())
        return

    await message.answer(read_day(day), reply_markup=main_menu())

    if day == 2 and not user["upsell_shown"]:
        user["upsell_shown"] = True
        set_user(message.from_user.id, user)
        await message.answer(UPSELL_TEXT, reply_markup=upsell_keyboard())

@router.message(F.text == "▶️ Keyingi kun")
async def next_day(message: Message):
    user = get_user(message.from_user.id)
    if user["day"] < TOTAL_DAYS:
        user["day"] += 1
        set_user(message.from_user.id, user)
    await today(message)

@router.message(F.text == "📊 Natijam")
async def result(message: Message):
    d = get_user(message.from_user.id)["day"]
    if d <= 2:
        text = "🫧 Tana moslashmoqda. Shish va ochlik pasayadi."
    elif d <= 5:
        text = "✨ Birinchi yengillik va energiya sezila boshlaydi."
    else:
        text = "🔥 Natija mustahkamlanmoqda. Siz to‘g‘ri yo‘ldasiz."
    await message.answer(text)

# ---------------- SUPPORT ----------------
@router.message(F.text == "💬 Savol berish")
async def ask(message: Message, state: FSMContext):
    await message.answer("Savolingizni yozing:")
    await state.set_state(Form.question)

@router.message(Form.question)
async def handle_question(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    await bot.send_message(
        ADMIN_ID,
        f"❓ Savol\n"
        f"👤 {user['name']} {user['surname']}\n"
        f"🆔 {message.from_user.id}\n\n"
        f"{message.text}"
    )
    await message.answer("✅ Savolingiz yuborildi")
    await state.clear()

@router.message(F.reply_to_message)
async def admin_reply(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if "🆔" in message.reply_to_message.text:
        uid = int(message.reply_to_message.text.split("🆔")[1].strip().split()[0])
        await bot.send_message(uid, f"💬 Admin javobi:\n\n{message.text}")

# ---------------- OPEN 30 ----------------
@router.callback_query(F.data == "open_30")
async def open30(c: CallbackQuery):
    user = get_user(c.from_user.id)
    user["payment_mode"] = "FULL"
    set_user(c.from_user.id, user)

    await c.message.answer(
        f"🔓 30 kunlik dastur\n\n"
        f"💰 {UPSELL_PRICE:,} so‘m\n"
        f"💳 {CARD_NUMBER}\n\n"
        "📸 Chekni yuboring"
    )

# ---------------- PAYMENTS ----------------
@router.message(F.photo)
async def payment(message: Message):
    user = get_user(message.from_user.id)
    mode = user.get("payment_mode", "ENTRY")
    token = f"{mode}-{uuid.uuid4().hex[:6]}"

    tokens = load_json(TOKENS_PATH)
    tokens[token] = {"uid": message.from_user.id, "type": mode}
    save_json(TOKENS_PATH, tokens)

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            "💳 Yangi chek\n"
            f"👤 {user['name']} {user['surname']}\n"
            f"🆔 {message.from_user.id}\n"
            f"🔖 To‘lov turi: {mode}\n"
            f"🔑 Token: {token}"
        )
    )

    await message.answer("Chekingiz yuborildi, admin tekshiradi")

@router.message(F.text.startswith(("ENTRY-", "FULL-")))
async def confirm(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    tokens = load_json(TOKENS_PATH)
    data = tokens.pop(message.text, None)
    save_json(TOKENS_PATH, tokens)

    if not data:
        await message.answer("❌ Token topilmadi")
        return

    user = get_user(data["uid"])

    if data["type"] == "ENTRY":
        user["paid_entry"] = True
        note = "1-kun ochildi"
    else:
        user["paid_full"] = True
        note = "30 kunlik dastur ochildi"

    set_user(data["uid"], user)

    await bot.send_message(data["uid"], f"✅ To‘lov tasdiqlandi. {note}")
    await message.answer("☑️ Tasdiqlandi")

# ---------------- MAIN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
