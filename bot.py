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
            [
                KeyboardButton(text="📅 Bugungi kun"),
                KeyboardButton(text="▶️ Keyingi kun")
            ],
            [
                KeyboardButton(text="📊 Natijam"),
                KeyboardButton(text="💬 Savol berish")
            ]
        ],
        resize_keyboard=True
    )

def upsell_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔓 30 kunni ochish",
                    callback_data="open_30"
                )
            ]
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
@router.message(CommandStart(), F.from_user.id == ADMIN_ID)
async def admin_start(message: Message):
    await message.answer(
        "🔐 <b>Admin panel</b>\n\n"
        "Quyidan bo‘lim tanlang 👇",
        reply_markup=admin_menu()
    )
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    users = load_json(USERS_PATH)

    total_users = len(users)
    day2_users = sum(1 for u in users.values() if u.get("day", 0) >= 2)
    day3_users = sum(1 for u in users.values() if u.get("day", 0) >= 3)
    paid_entry = sum(1 for u in users.values() if u.get("paid_entry"))
    paid_full = sum(1 for u in users.values() if u.get("paid_full"))

    text = (
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n\n"
        f"➡️ 2-kunga yetganlar: <b>{day2_users}</b>\n"
        f"➡️ 3-kunga yetganlar: <b>{day3_users}</b>\n\n"
        f"💰 1-kun to‘lov qilganlar: <b>{paid_entry}</b>\n"
        f"🔥 30 kun FULL olganlar: <b>{paid_full}</b>\n\n"
        "📈 <i>Statistika real vaqtda yangilanadi</i>"
    )

    await callback.message.edit_text(text, reply_markup=admin_menu())

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

@router.message(Form.weight, F.text)
async def weight(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer(
            "⚠️ Iltimos, vazningizni faqat raqam bilan kiriting.\n"
            "Masalan: 75"
        )
        return

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
        f"⚖️ Vazn: {user['weight']} kg\n"
        f"🆔 {message.from_user.id}"
    )

    await message.answer(
        "✅ Siz ro‘yxatdan muvaffaqiyatli o‘tdingiz!\n\n"
        "📅 Boshlash uchun <b>Bugungi kun</b> tugmasini bosing 👇",
        reply_markup=main_menu()
    )

    await state.clear()


# ---------------- DAYS ----------------
@router.message(F.text == "📅 Bugungi kun")
async def today(message: Message):
    user = get_user(message.from_user.id)
    day = user["day"]

    # 🔒 1-KUN — ENTRY to‘lovsiz yopiq
    if day == 1 and not user["paid_entry"]:
        await message.answer(
            "🔒 <b>1-KUN HOZIRCHA YOPIQ</b>\n\n"
            "Bu bosqichdan o‘tish uchun kichik start to‘lovi mavjud 👇\n\n"
            f"💰 <b>Boshlash narxi:</b> {ENTRY_PRICE:,} so‘m\n"
            f"💳 <b>Karta:</b> <code>{CARD_NUMBER}</code>\n"
            "👤 <b>Karta egasi:</b> B. Ne’matov\n\n"
            "📸 <b>To‘lovni amalga oshirib,</b>\n"
            "chekni shu yerga rasm qilib yuboring.\n\n"
            "✅ <i>Tasdiqlangach, 1-kun darhol ochiladi</i>"
        )
        return

    # ✅ 2-KUN — ochiq + yumshoq UPSELL
    if day == 2 and not user["paid_full"]:
        await message.answer(read_day(day), reply_markup=main_menu())

        if not user.get("upsell_shown"):
            user["upsell_shown"] = True
            set_user(message.from_user.id, user)

            await message.answer(
                "⚠️ <b>2-KUN — MUHIM ESLATMA</b>\n\n"
                "Tanangiz moslashishni boshladi.\n"
                "Asosiy yog‘ ketish jarayoni 4-kundan boshlanadi.\n\n"
                "💡 Ko‘pchilik aynan shu joyda to‘xtab qoladi.\n\n"
                f"🔥 30 kunlik to‘liq dastur — {UPSELL_PRICE:,} so‘m\n"
                "👇 Davom etish uchun hozir ochib qo‘ying",
                reply_markup=upsell_keyboard()
            )
        return

    # ⚠️ 3-KUN — OXIRGI BEPUL KUN (KUCHLI BOSIM)
    if day == 3 and not user["paid_full"]:
        await message.answer(read_day(day), reply_markup=main_menu())

        await message.answer(
            "⚠️ <b>3-KUN — OXIRGI BEPUL KUN</b>\n\n"
            "Bugundan keyin dastur yopiladi.\n\n"
            "⏳ Agar hozir to‘xtasangiz — yana boshidan boshlaysiz.\n"
            "🔥 Davom etsangiz — natija boshlanadi.\n\n"
            f"💎 30 kunlik to‘liq dastur — {UPSELL_PRICE:,} so‘m\n"
            "👇 Oxirgi imkoniyat — hozir oching",
            reply_markup=upsell_keyboard()
        )
        return

    # 🔒 4-KUNDAN BOSHLAB — FULLsiz yopiq
    if day > MAX_FREE_DAYS and not user["paid_full"]:
        idx = min(user["day4_attempts"], 2)
        user["day4_attempts"] += 1
        set_user(message.from_user.id, user)

        await message.answer(
            DAY4_BLOCKS[idx],
            reply_markup=upsell_keyboard()
        )
        return

    # ✅ FULL foydalanuvchilar uchun oddiy kunlar
    await message.answer(read_day(day), reply_markup=main_menu())


@router.message(F.text == "▶️ Keyingi kun")
async def next_day(message: Message):
    user = get_user(message.from_user.id)
    day = user["day"]

    # ❌ 1-kun: ENTRY to‘lovsiz o‘tmaydi
    if day == 1 and not user["paid_entry"]:
        await message.answer(
            "🔒 <b>1-kun yopiq</b>\n\n"
            "Davom etish uchun avval boshlash to‘lovini qiling 👇"
        )
        return

    # ❌ 4-kundan boshlab: FULLsiz o‘tmaydi
    if day >= MAX_FREE_DAYS and not user["paid_full"]:
        await message.answer(
            "🔒 Keyingi kunlar yopiq.\n\n"
            "30 kunlik dasturga o‘ting 👇",
            reply_markup=upsell_keyboard()
        )
        return

    # ✅ Hamma shart bajarildi — kunga o‘tamiz
    if day < TOTAL_DAYS:
        user["day"] += 1
        set_user(message.from_user.id, user)

    # 🔁 Har doim yangi kunni ko‘rsatamiz
    await today(message)


    # ✅ Hammasi joyida — keyingi kunga o‘tamiz
    if day < TOTAL_DAYS:
        user["day"] += 1
        set_user(message.from_user.id, user)

    await today(message)


@router.message(F.text == "📊 Natijam")
async def result(message: Message):
    user = get_user(message.from_user.id)
    d = user["day"]

    if d <= 2:
        text = (
            "🫧 <b>1–2-kun: Moslashuv bosqichi</b>\n\n"
            "Tanangiz yangi rejimga o‘rganmoqda.\n"
            "▫️ Shishlar kamayadi\n"
            "▫️ Ochlik sekin pasaya boshlaydi\n"
            "▫️ Oshqozon yengillashadi\n\n"
            "💚 Bu bosqich eng muhimidir — davom eting."
        )

    elif d <= 5:
        text = (
            "✨ <b>3–5-kun: Birinchi o‘zgarishlar</b>\n\n"
            "Ko‘pchilik aynan shu paytda farqni sezadi:\n"
            "▫️ Qorin yengillashadi\n"
            "▫️ Energiya ko‘payadi\n"
            "▫️ Tana tezroq uyg‘onadi\n\n"
            "🔥 Siz to‘g‘ri yo‘ldasiz."
        )

    elif d <= 10:
        text = (
            "🔥 <b>6–10-kun: Natija ko‘rina boshlaydi</b>\n\n"
            "▫️ Bel va qorin ancha bo‘shaydi\n"
            "▫️ Ishtaha nazoratga keladi\n"
            "▫️ Tarozida farq ko‘rina boshlaydi\n\n"
            "💪 Bu joydan qaytganlar kam bo‘ladi."
        )

    else:
        text = (
            "🏆 <b>Barqaror natija bosqichi</b>\n\n"
            "Siz tanani qayta sozlash jarayonidasiz:\n"
            "▫️ Vazn izchil tushmoqda\n"
            "▫️ Natija mustahkamlanmoqda\n"
            "▫️ Eski odatlar o‘rnini yangi tizim egalladi\n\n"
            "👏 Oxirigacha borganlar aynan shu yerdan chiqadi."
        )

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

    await message.answer("Chekingiz yuborildi, admin tomonidan tekshirilib tez orada qabul qilinadi")

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
