# ================================
# FINAL BOT — OZISH 30 KUNLIK (YAKUNIY)
# 1-kun pullik, 2-kun upsell, 4-kun aqlli blok
# Start + Natijam + Upsell + 4-kun blok integratsiya qilingan
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
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram import Router

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 983517327
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
    "🥗 Agar qorin va bel ketmayotgan bo‘lsa,\n"
    "bu sizning aybingiz emas.\n\n"
    "Muammo ko‘pincha noto‘g‘ri ovqatlanish va tartibsiz rejimda bo‘ladi.\n\n"
    "✨ Bu esa 30 kunlik aniq tizim.\n"
    "Ko‘pchilik 7–10 kunda farqni sezadi.\n\n"
    "💰 Boshlash uchun minimal summa — 12 000 so‘m\n\n"
    "👇 Boshlash uchun ismingizni yozing"
)

UPSELL_TEXT = (
    "🌱 Agar shu joygacha kelgan bo‘lsang — demak, sen boshlading.\n\n"
    "Oxirgi 2 kun ichida tanang moslashdi.\n"
    "Endi asosiy jarayon boshlanadi.\n\n"
    "Keyingi 28 kunda:\n"
    "• qorin va bel sekin-asta ketadi\n"
    "• ochlik kamayadi\n"
    "• vazn barqaror tushadi\n\n"
    f"🔥 30 kunlik to‘liq dastur — {UPSELL_PRICE:,} so‘m"
)

DAY4_BLOCKS = [
    "🔒 4-KUN HOZIRCHA YOPIQ\n\nSen 3 kunni ortda qoldirding. Asosiy o‘zgarishlar endi boshlanadi.",
    "ℹ️ MUHIM ESLATMA\n\nKo‘pchilik 5–7-kunlarda aniq farqni sezadi. Faqat davom etganlar natija ko‘radi.",
    "⏳ HAL QILUVCHI NUQTA\n\nBu safar oxirigacha boradiganlar natija oladi. Tanlov seniki."
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
            f"🔒 1-kun yopiq\n\nBoshlash uchun minimal summa: {ENTRY_PRICE:,} so‘m\n"
            f"💳 Karta: {CARD_NUMBER}\n\n📸 Chekni rasm qilib botga yuboring"
        )
        return

    if day > MAX_FREE_DAYS and not user.get("paid_full"):
        idx = min(user["day4_attempts"], 2)
        user["day4_attempts"] += 1
        set_user(message.from_user.id, user)
        await message.answer(DAY4_BLOCKS[idx], reply_markup=upsell_keyboard())
        return

    await message.answer(read_day(day), reply_markup=main_menu())

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
        text = "🫧 Tanangiz moslashmoqda. Eng muhim narsa — davom etish."
    elif d <= 5:
        text = "✨ Birinchi yengillik sezila boshlaydi."
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
        f"❓ Savol\n👤 {user['name']} {user['surname']}\n🆔 {message.from_user.id}\n\n{message.text}"
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

# ---------------- PAYMENTS ----------------
@router.message(F.photo)
async def payment(message: Message):
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
