# improved_bot.py
import logging
import json
import os
import uuid
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv
load_dotenv()

# Config from env (safer)
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "983517327"))  # o'zingizni env ga qo'ying
CARD_NUMBER = os.getenv("CARD_NUMBER", "9860350110461737")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

USERS_PATH = "database/users.json"
TOKENS_PATH = "database/tokens.json"
RESULT_CHANNEL_LINK = os.getenv("RESULT_CHANNEL_LINK", "https://t.me/ozishchatbot")
OZISH_BOT = os.getenv("OZISH_BOT", "https://t.me/OzishChatBot")

os.makedirs("database", exist_ok=True)
if not os.path.exists(TOKENS_PATH):
    with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False)

# Locks to protect file access inside the same process
users_lock = asyncio.Lock()
tokens_lock = asyncio.Lock()

class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()

# ---- Helper: safe read/write users/tokens with locks ----
async def load_users():
    async with users_lock:
        if not os.path.exists(USERS_PATH):
            return {}
        try:
            with open(USERS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.warning("users.json JSONDecodeError — returning empty dict")
            return {}
        except Exception as e:
            logging.exception("load_users error: %s", e)
            return {}

async def save_users(users):
    async with users_lock:
        try:
            tmp = USERS_PATH + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            os.replace(tmp, USERS_PATH)
        except Exception as e:
            logging.exception("save_users error: %s", e)

async def get_user_data(user_id):
    users = await load_users()
    user = users.get(str(user_id))
    if user and "paid_days" not in user:
        user["paid_days"] = []
    return user

async def set_user_data(user_id, data):
    users = await load_users()
    users[str(user_id)] = data
    await save_users(users)

async def load_tokens():
    async with tokens_lock:
        if not os.path.exists(TOKENS_PATH):
            return {}
        try:
            with open(TOKENS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.warning("tokens.json JSONDecodeError — returning empty dict")
            return {}
        except Exception as e:
            logging.exception("load_tokens error: %s", e)
            return {}

async def save_tokens(tokens):
    async with tokens_lock:
        try:
            tmp = TOKENS_PATH + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(tokens, f, ensure_ascii=False, indent=2)
            os.replace(tmp, TOKENS_PATH)
        except Exception as e:
            logging.exception("save_tokens error: %s", e)

def mask_card(number: str) -> str:
    s = number.replace(" ", "")
    if len(s) >= 16:
        return f"{s[:4]} {s[4:8]} **** {s[-4:]}"
    return s

# ---- content helpers ----
def read_day_file(weight, day):
    folder = "data/days_plus" if weight >= 100 else "data/days"
    path = os.path.join(folder, f"day{day}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi."

def get_payment_text(weight, day):
    # <-- faqat 4-kun to'lov talabi (agar 21 ham kerak bo'lsa, oson qo'shish mumkin)
    if day == 4:
        return (
            "🎉 Siz 3 kunlik <b>bepul dasturdan</b> muvaffaqiyatli o‘tdingiz!\n\n"
            "👉 Endi <b>premium bosqichni</b> davom ettirish uchun to‘lov qilishingiz kerak.\n\n"
            "✅ Natijada:\n"
            "▫️ 30 kunda <b>-16 kg</b>\n"
            "▫️ 40 kunda <b>-19 kg</b>\n\n"
            f"💳 <b>To‘lov narxi:</b> <s>199,000 so‘m</s> ➝ <b>145,000 so‘m</b>\n"
            "(kuniga ~4,800 so‘m, ya’ni bir choy narxi)\n\n"
            f"💳 Karta raqami: <code>{mask_card(CARD_NUMBER)}</code>\n"
            "👤 Karta egasi: <b>B.Nematov</b>\n\n"
            "📸 <b>To‘lov chekini shu botga yuboring.</b>\n"
            "⏱ <i>10 daqiqa ichida admin tasdiqlaydi</i> va keyingi kuningiz ochiladi!\n\n"
            "⚡️ <b>Eslatma:</b> Agar bugun to‘lamasangiz, dastur <u>to‘xtab qoladi</u> "
            "va natija <u>kechikadi</u>."
        )
    return ""

def build_days_keyboard(weight, current_day):
    total_days = 40 if weight >= 100 else 30
    builder = InlineKeyboardBuilder()
    for day in range(1, total_days + 1):
        if day == current_day:
            builder.button(text=f"💚 Kun {day}", callback_data=f"day_{day}")
        elif day < current_day:
            builder.button(text=f"✅ Kun {day}", callback_data=f"day_{day}")
        else:
            builder.button(text=f"🔒 Kun {day}", callback_data="locked")
    builder.adjust(4)
    # add contact button
    builder.row(InlineKeyboardButton(text="💬 Murojaat qilish", url=OZISH_BOT))
    return builder.as_markup()

# ----- Handlers -----
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await message.answer(
        "🎯 <b>Marafon haqida:</b>\n"
        "- Bu shunchaki bot emas, bu — dietolog va trenerlar tayyorlagan maxsus dastur.\n"
        "- Sizga 30 kunlik individual menyu, mashqlar va motivatsiya beriladi.\n"
        "- Natijada: 30 kunda -16 kg, 40 kunda -19 kg.\n\n"
        "✅ <b>Birinchi 3 kun — mutlaqo bepul!</b>\n"
        "4-kundan boshlab premium ishtirokchilar davom ettirishlari mumkin.\n\n"
        "Dietolog huzuriga 1 soat borish 100 ming so‘m. "
        "Biz esa butun oyni — atigi <b>145 ming so‘m</b>ga taqdim qilamiz!\n\n"
        "Ismingizni kiriting:"
    )
    await state.set_state(Form.name)

@router.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    txt = message.text.strip()
    if len(txt) < 2:
        await message.answer("⚠️ Ism juda qisqa. Iltimos, to‘liq ismingizni yozing.")
        return
    await state.update_data(name=txt)
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Form.surname)

@router.message(Form.surname)
async def get_surname(message: Message, state: FSMContext):
    txt = message.text.strip()
    if len(txt) < 2:
        await message.answer("⚠️ Familiya juda qisqa. Iltimos, to‘liq familiyangizni yozing.")
        return
    await state.update_data(surname=txt)
    await message.answer("Yoshingizni kiriting (faqat raqam, masalan: 25):")
    await state.set_state(Form.age)

@router.message(Form.age)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Yosh faqat raqam bo‘lishi kerak (masalan: 25).")
        return
    age = int(message.text)
    if age < 10 or age > 100:
        await message.answer("⚠️ Yosh 10 va 100 orasida bo‘lishi kerak.")
        return
    await state.update_data(age=age)
    await message.answer("Vazningizni kiriting (kg, masalan: 78):")
    await state.set_state(Form.weight)

@router.message(Form.weight)
async def get_weight(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    if not message.text.isdigit():
        await message.answer("⚠️ Vazn faqat raqam bo‘lishi kerak (masalan: 78).")
        return
    weight = int(message.text)
    if weight < 30 or weight > 300:
        await message.answer("⚠️ Vazn 30 dan 300 kg orasida bo‘lishi kerak.")
        return
    user_data = {
        "name": data['name'],
        "surname": data['surname'],
        "age": data['age'],
        "weight": weight,
        "day": 1,
        "paid_days": []
    }
    await set_user_data(user_id, user_data)
    # send admin notification (log error if fails)
    admin_text = (
        f"🆕 Yangi foydalanuvchi!\n\n"
        f"👤 Ism: {user_data['name']}\n"
        f"👤 Familiya: {user_data['surname']}\n"
        f"🎂 Yosh: {user_data['age']} da\n"
        f"⚖️ Vazn: {user_data['weight']} kg"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        logging.exception("Failed to send admin notification: %s", e)
    # reply with keyboard (1-kun ochiq)
    days_keyboard = build_days_keyboard(weight, 1)
    await message.answer(
        "✅ Ma’lumotlaringiz qabul qilindi!\n\n"
        "▶️ Pastdan <b>1-kun</b> tugmasini bosing va boshlang 👇",
        reply_markup=days_keyboard
    )
    await state.clear()

@router.callback_query(F.data.startswith("day_"))
async def show_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user_data(user_id)
    if not user:
        await callback.message.answer("❗ Iltimos, /start tugmasini bosing.")
        return
    day = int(callback.data.split("_")[1])
    weight = user.get("weight", 0)
    current_day = user.get("day", 1)
    total_days = 40 if weight >= 100 else 30
    if day > current_day:
        await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)
        return
    # only 4-kun requires payment in this design
    if day == 4 and 4 not in user.get("paid_days", []):
        await callback.message.edit_text(get_payment_text(weight, day), reply_markup=build_days_keyboard(weight, current_day))
        return
    # read day content
    text = read_day_file(weight, day)
    text += "\n\n❓ Savollar bo‘lsa dietologga murojaat qiling 👇"
    # if user saw current day, open next one (atomic via set_user_data lock)
    if day == current_day and current_day < total_days:
        user["day"] = current_day + 1
        await set_user_data(user_id, user)
    await callback.message.edit_text(text, reply_markup=build_days_keyboard(weight, user["day"]))

@router.callback_query(F.data == "locked")
async def locked_day(callback: CallbackQuery):
    await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)

@router.message(F.photo)
async def handle_payment_photo(message: Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    if user_id == ADMIN_ID:
        return
    user = await get_user_data(user_id)
    if not user:
        return
    day = user.get("day", 1)
    # only stage 4 requires payment in current design
    if day == 4:
        stage = 4
    else:
        await message.answer("⛔ Sizda hozir to‘lov bosqichi yo‘q.")
        return
    token = f"KUN{stage}-{uuid.uuid4().hex[:6]}"
    tokens = await load_tokens()
    tokens[token] = {"user_id": user_id, "stage": stage}
    await save_tokens(tokens)
    try:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=(
                f"💳 <b>Yangi to‘lov cheki</b>\n"
                f"ID: <code>{user_id}</code>\n"
                f"Ism: <b>{user['name']} {user['surname']}</b>\n"
                f"✅ <b>Tasdiqlash kodi:</b> <code>{token}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.exception("Failed to forward payment photo to admin: %s", e)
    await message.answer("✅ Chekingiz yuborildi. Admin ko‘rib chiqadi.")

@router.message(F.text.startswith("KUN"))
async def confirm_payment_token(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    token = message.text.strip()
    tokens = await load_tokens()
    if token not in tokens:
        await message.answer("❌ Noto‘g‘ri yoki eskirgan token.")
        return
    user_id = tokens[token]['user_id']
    stage = tokens[token]['stage']
    del tokens[token]
    await save_tokens(tokens)
    user = await get_user_data(user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi.")
        return
    if stage == 4 and user.get('day', 1) < 4:
        user['day'] = 4
    user.setdefault("paid_days", []).append(stage)
    await set_user_data(user_id, user)
    try:
        await bot.send_message(chat_id=user_id, text=f"✅ To‘lov tasdiqlandi! {stage}-kun ochildi.")
    except Exception as e:
        logging.exception("Failed to notify user about payment confirmation: %s", e)
    await message.answer(f"☑️ {user['name']} uchun {stage}-kun ochildi.")

@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar haqida", callback_data="stats")],
        [InlineKeyboardButton(text="📎  Savollarga javob berish", url=RESULT_CHANNEL_LINK)]
    ])
    await message.answer("🔧 Admin menyusi:", reply_markup=keyboard)

@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    users = await load_users()
    total = len(users)
    count_100_plus = sum(1 for u in users.values() if u.get('weight', 0) >= 100)
    count_100_minus = total - count_100_plus
    tolovchilar = sum(1 for u in users.values() if u.get("paid_days"))
    await callback.message.edit_text(
        f"📊 <b>Foydalanuvchilar statistikasi:</b>\n\n"
        f"🔹 Jami: <b>{total}</b>\n"
        f"⚖️ 100 kg dan kam: <b>{count_100_minus}</b>\n"
        f"⚖️ 100 kg va undan ortiq: <b>{count_100_plus}</b>\n"
        f"💰 To‘lov qilganlar: <b>{tolovchilar}</b>",
        parse_mode="HTML"
    )

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
