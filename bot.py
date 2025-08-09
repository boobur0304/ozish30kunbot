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

API_TOKEN = os.getenv("BOT_TOKEN")  # <-- bu joyda token keladi

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

USERS_PATH = "database/users.json"
TOKENS_PATH = "database/tokens.json"
ADMIN_ID = 983517327
RESULT_CHANNEL_LINK = "https://t.me/ozishchatbot"

os.makedirs("database", exist_ok=True)
if not os.path.exists(TOKENS_PATH):
    with open(TOKENS_PATH, 'w') as f:
        json.dump({}, f)

class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()

def load_users():
    if not os.path.exists(USERS_PATH):
        return {}
    with open(USERS_PATH, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_PATH, 'w') as f:
        json.dump(users, f, indent=2)

def get_user_data(user_id):
    users = load_users()
    user = users.get(str(user_id))
    if user and "paid_days" not in user:
        user["paid_days"] = []
    return user

def set_user_data(user_id, data):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def read_day_file(weight, day):
    folder = "data/days_plus" if weight >= 100 else "data/days"
    path = os.path.join(folder, f"day{day}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi."

def get_payment_text(weight, day):
    if weight < 100:
        if 11 <= day <= 20:
            amount = "29,000 so‘m"
        elif 21 <= day <= 30:
            amount = "39,000 so‘m"
        else:
            return ""
    else:
        if 11 <= day <= 20:
            amount = "39,000 so‘m"
        elif 21 <= day <= 30:
            amount = "49,000 so‘m"
        elif 31 <= day <= 40:
            amount = "59,000 so‘m"
        else:
            return ""

    return (f"⛔ Keyingi kunlar uchun to'lov qilishingiz kerak.\n\n"
            f"To‘lov narxi: {amount}\n"
            f"💳 Karta: 9860350110461737\n"
            f"👤 Karta egasi: B.Nematov\n"
            f"✅ Chekni shu botga yuboring.\n"
            f"🕓 Tez orada to‘lovingiz tasdiqlanadi.")

def build_days_keyboard(weight, current_day):
    total_days = 40 if weight >= 100 else 30
    builder = InlineKeyboardBuilder()
    
    for day in range(1, total_days + 1):
        if day == current_day:
            # Hozirgi kun — yashil yurak
            builder.button(text=f"💚 Kun {day}", callback_data=f"day_{day}")
        elif day < current_day:
            builder.button(text=f"✅ Kun {day}", callback_data="old_day")
        else:
            builder.button(text=f"🔒 Kun {day}", callback_data="locked")
    
    builder.adjust(4)  # Har qatorda 4 ta tugma
    return builder.as_markup()

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await message.answer(
        "🎯 <b>Marafon haqida:</b>\n"
        "- Har kuni sizga menyu, mashqlar va motivatsiya beriladi.\n"
        "- Ozish bo‘yicha sinovdan o‘tgan 30–40 kunlik dastur.\n"
        "- Natijaga erishish uchun to'liq 30 yoki 40 kunlik rejadagi kunlarni o'tishingiz kerak. 100 kg dan yengillar uchun 30 kun. 100 kgdan yuqorilar uchun 40 kun.\n"
        "- Bot sizning vazningizga qarab avtomatik reja tuzadi.\n\n"
        "<b>♻️ Qoidalar:</b>\n"
        "- Har kuni faqat navbatdagi kun ochiladi.\n"
        "- Hech qanday buyruqsiz, faqat tugmalar orqali ishlaydi.\n\n"
        "🔥 <b>Sizni kutyotgan natijalar:</b>\n"
        f"<a href='{RESULT_CHANNEL_LINK}'>👉 Dietologga murojat</a>\n"
        "- 30 kunda -6 kg\n"
        "- 40 kunda -9 kg\n\n"
        "Boshlaymiz!👇\n\n"
        "Ismingizni kiriting:")
    await state.set_state(Form.name)

@router.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Form.surname)

@router.message(Form.surname)
async def get_surname(message: Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("Yoshingizni kiriting:")
    await state.set_state(Form.age)

@router.message(Form.age)
async def get_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Vazningizni kiriting (kg):")
    await state.set_state(Form.weight)

@router.message(Form.weight)
async def get_weight(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    weight = int(message.text)
    user_data = {
        "name": data['name'],
        "surname": data['surname'],
        "age": data['age'],
        "weight": weight,
        "day": 1,
        "paid_days": []
    }
    set_user_data(user_id, user_data)
    await message.answer("✅ Ma'lumotlar saqlandi!\nQuyidan 1-kunni tanlang:", reply_markup=build_days_keyboard(weight, 1))
    await state.clear()

@router.callback_query(F.data.startswith("day_"))
async def show_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user_data(user_id)
    if not user:
        await callback.message.answer("❗ Iltimos, /start tugmasini bosing.")
        return

    day = int(callback.data.split("_")[1])
    weight = user["weight"]
    current_day = user["day"]

    if day > current_day:
        await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)
        return

    if day in range(11, 21) and 11 not in user.get("paid_days", []):
        await callback.message.edit_text(get_payment_text(weight, day), reply_markup=build_days_keyboard(weight, current_day))
        return
    if day in range(21, 31) and 21 not in user.get("paid_days", []):
        await callback.message.edit_text(get_payment_text(weight, day), reply_markup=build_days_keyboard(weight, current_day))
        return
    if day in range(31, 41) and 31 not in user.get("paid_days", []):
        await callback.message.edit_text(get_payment_text(weight, day), reply_markup=build_days_keyboard(weight, current_day))
        return

    text = read_day_file(weight, day)
    if day == current_day and day < (40 if weight >= 100 else 30):
        user["day"] += 1
        set_user_data(user_id, user)

    await callback.message.edit_text(text, reply_markup=build_days_keyboard(weight, user["day"]))

@router.callback_query(F.data == "locked")
async def locked_day(callback: CallbackQuery):
    await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)

@router.callback_query(F.data == "old_day")
async def old_day(callback: CallbackQuery):
    await callback.answer("✅ Bu kun allaqachon ochilgan!", show_alert=True)

@router.message(F.photo)
async def handle_payment_photo(message: Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    if user_id == ADMIN_ID:
        return
    user = get_user_data(user_id)
    if not user:
        return

    day = user.get("day", 1)
    if 11 <= day <= 20:
        stage = 11
    elif 21 <= day <= 30:
        stage = 21
    elif 31 <= day <= 40:
        stage = 31
    else:
        await message.answer("⛔ Sizda to‘lov bosqichi yo‘q.")
        return

    token = f"KUN{stage}-{uuid.uuid4().hex[:6]}"
    with open(TOKENS_PATH, 'r+') as f:
        data = json.load(f)
        data[token] = {"user_id": user_id, "stage": stage}
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

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
    await message.answer("✅ Chekingiz yuborildi. Admin ko‘rib chiqadi.")

@router.message(F.text.startswith("KUN"))
async def confirm_payment_token(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    token = message.text.strip()
    if not os.path.exists(TOKENS_PATH):
        return

    with open(TOKENS_PATH, 'r+') as f:
        tokens = json.load(f)
        if token not in tokens:
            await message.answer("❌ Noto‘g‘ri yoki eskirgan token.")
            return
        user_id = tokens[token]['user_id']
        stage = tokens[token]['stage']
        del tokens[token]
        f.seek(0)
        json.dump(tokens, f, indent=2)
        f.truncate()

    user = get_user_data(user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi.")
        return

    if stage == 11 and user['day'] < 11:
        user['day'] = 11
    elif stage == 21 and user['day'] < 21:
        user['day'] = 21
    elif stage == 31 and user['day'] < 31:
        user['day'] = 31

    user.setdefault("paid_days", []).append(stage)
    set_user_data(user_id, user)

    await bot.send_message(chat_id=user_id, text=f"✅ To‘lov tasdiqlandi! {stage}-kun ochildi.")
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
    users = load_users()
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
