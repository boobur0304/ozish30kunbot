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

API_TOKEN = os.getenv("BOT_TOKEN")

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
    if day == 4:  # ✅ faqat 4-kunda to'lov
        return (
            "🎉 Siz 3 kunlik <b>bepul dasturdan</b> muvaffaqiyatli o‘tdingiz!\n\n"
            "👉 Endi <b>premium bosqichni</b> davom ettirish uchun to‘lov qilishingiz kerak.\n\n"
            "✅ Natijada:\n"
            "▫️ 30 kunda <b>-16 kg</b>\n"
            "▫️ 40 kunda <b>-19 kg</b>\n\n"
            "💳 <b>To‘lov narxi:</b> <s>199,000 so‘m</s> ➝ <b>145,000 so‘m</b>\n"
            "(kuniga ~4,800 so‘m, ya’ni bir choy narxi)\n\n"
            "💳 Karta raqami: <code>9860 3501 1046 1737</code>\n"
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

    # 📩 Murojaat qilish tugmasi yuqorida
    builder.button(text="📩 Murojaat qilish", url="https://t.me/ozishchatbot")

    for day in range(1, total_days + 1):
        if day == current_day:
            builder.button(text=f"💚 Kun {day}", callback_data=f"day_{day}")
        elif day < current_day:
            builder.button(text=f"✅ Kun {day}", callback_data=f"day_{day}")
        else:
            builder.button(text=f"🔒 Kun {day}", callback_data="locked")

    builder.adjust(1, 4)
    return builder.as_markup()

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
    if len(message.text) < 2:
        await message.answer("⚠️ Ism juda qisqa. Iltimos, to‘liq ismingizni yozing.")
        return
    await state.update_data(name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Form.surname)

@router.message(Form.surname)
async def get_surname(message: Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("⚠️ Familiya juda qisqa. Iltimos, to‘liq familiyangizni yozing.")
        return
    await state.update_data(surname=message.text)
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

    set_user_data(user_id, user_data)

    text = (
        f"🆕 Yangi foydalanuvchi!\n\n"
        f"👤 Ism: {user_data['name']}\n"
        f"👤 Familiya: {user_data['surname']}\n"
        f"🎂 Yosh: {user_data['age']} da\n"
        f"⚖️ Vazn: {user_data['weight']} kg"
    )
    await message.bot.send_message(ADMIN_ID, text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ 1-kun", callback_data="day_1")]
    ])

    await message.answer(
        "✅ Ma’lumotlaringiz qabul qilindi!\n\n"
        "🎯 Endi siz o‘zingizni sog‘lom va eng yaxshi holatingizga olib boradigan yo‘lni boshladingiz!\n"
        "Har bir kun sizni orzuyingizdagi natijaga yaqinlashtiradi.\n\n"
        "🔥 Bu marafon faqat ovqatlanish emas — bu hayotingizni o‘zgartiradigan yo‘l!\n\n"
        "⚡️ Esda tuting: dasturdan 3 kun bepul foydalanishingiz mumkin. Agar haqiqiy o‘zgarishni his qilsangiz, albatta davom etasiz.\n"
        "👉 Siz bunga loyiqsiz!\n\n"
        "▶️ Boshlash uchun pastdagi <b>1-kun</b> tugmasini bosing 👇",
        reply_markup=keyboard
    )
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

    if day == 4 and 4 not in user.get("paid_days", []):
        await callback.message.edit_text(get_payment_text(weight, day),
                                         reply_markup=build_days_keyboard(weight, current_day))
        return

    text = read_day_file(weight, day)
    text += "\n\n❓ Savollar bo‘lsa dietologga murojaat qiling 👇"

    if day == current_day and day < (40 if weight >= 100 else 30):
        user["day"] += 1
        set_user_data(user_id, user)

    await callback.message.edit_text(text, reply_markup=build_days_keyboard(weight, user["day"]))

@router.callback_query(F.data == "locked")
async def locked_day(callback: CallbackQuery):
    await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
