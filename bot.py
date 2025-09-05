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
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery

from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")  # .env ichida BOT_TOKEN=... bo'lsin

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

USERS_PATH = "database/users.json"
TOKENS_PATH = "database/tokens.json"
ADMIN_ID = 983517327  # o'zingizning admin ID ni qo'ying
OZISH_BOT_URL = "https://t.me/OzishChatBot"  # murojaat tugmasi uchun

os.makedirs("database", exist_ok=True)
if not os.path.exists(TOKENS_PATH):
    with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False)

class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()

# ---------------- Helper: users ----------------
def load_users():
    if not os.path.exists(USERS_PATH):
        return {}
    try:
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_users(users):
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


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

# ---------------- Helper: tokens ----------------
def load_tokens():
    if not os.path.exists(TOKENS_PATH):
        return {}
    try:
        with open(TOKENS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_tokens(tokens):
    with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

# ---------------- Day files ----------------
def read_day_file(weight, day):
    folder = "data/days_plus" if weight >= 100 else "data/days"
    path = os.path.join(folder, f"day{day}.txt")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi."

# ---------------- Payment text (faqat 4-kun) ----------------
def get_payment_text():
    return (
        "🎉 Siz 3 kunlik <b>bepul dasturdan</b> muvaffaqiyatli o‘tdingiz!

"
        "👉 Endi <b>premium bosqichni</b> davom ettirish uchun to‘lov qilishingiz kerak.

"
        "✅ Natijada:
"
        "▫️ 30 kunda <b>-16 kg</b>
"
        "▫️ 40 kunda <b>-19 kg</b>

"
        "💳 <b>To‘lov narxi:</b> <s>199,000 so‘m</s> ➝ <b>145,000 so‘m</b>
"
        "(kuniga ~4,800 so‘m, ya’ni bir choy narxi)

"
        "💳 Karta raqami: <code>9860 3501 1046 1737</code>
"
        "👤 Karta egasi: <b>B.Nematov</b>

"
        "📸 <b>To‘lov chekini shu botga yuboring.</b>
"
        "⏱ <i>10 daqiqa ichida admin tasdiqlaydi</i> va keyingi kuningiz ochiladi!

"
        "⚡️ <b>Eslatma:</b> Agar bugun to‘lamasangiz, dastur <u>to‘xtab qoladi</u> "
        "va natija <u>kechikadi</u>."
    )

# ---------------- Keyboard builder ----------------
def build_days_keyboard(weight, current_day):
    total_days = 40 if weight >= 100 else 30

    # Build rows: first row = Murojaat, next rows = days (4 per row)
    rows = []
    rows.append([
        InlineKeyboardButton(text="📩 Murojaat qilish", url=OZISH_BOT_URL)
    ])

    row = []
    for day in range(1, total_days + 1):
        if day == current_day:
            btn = InlineKeyboardButton(text=f"💚 Kun {day}", callback_data=f"day_{day}")
        elif day < current_day:
            btn = InlineKeyboardButton(text=f"✅ Kun {day}", callback_data=f"day_{day}")
        else:
            btn = InlineKeyboardButton(text=f"🔒 Kun {day}", callback_data="locked")
        row.append(btn)
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)

# ---------------- Handlers ----------------
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await message.answer(
        "🎯 <b>Marafon haqida:</b>
"
        "- Bu shunchaki bot emas, bu — dietolog va trenerlar tayyorlagan maxsus dastur.
"
        "- Sizga 30 kunlik individual menyu, mashqlar va motivatsiya beriladi.
"
        "- Natijada: 30 kunda -16 kg, 40 kunda -19 kg.

"
        "✅ <b>Birinchi 3 kun — mutlaqo bepul!</b>
"
        "4-kundan boshlab premium ishtirokchilar davom ettirishlari mumkin.

"
        "Dietolog huzuriga 1 soat borish 100 ming so‘m. "
        "Biz esa butun oyni — atigi <b>145 ming so‘m</b>ga taqdim qilamiz!

"
        "Ismingizni kiriting:"
    )
    await state.set_state(Form.name)

@router.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Ism juda qisqa. Iltimos, to‘liq ismingizni yozing.")
        return
    await state.update_data(name=message.text.strip())
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Form.surname)

@router.message(Form.surname)
async def get_surname(message: Message, state: FSMContext):
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Familiya juda qisqa. Iltimos, to‘liq familiyangizni yozing.")
        return
    await state.update_data(surname=message.text.strip())
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

    # Admin'ga xabar
    admin_text = (
        f"🆕 Yangi foydalanuvchi!

"
        f"👤 Ism: {user_data['name']}
"
        f"👤 Familiya: {user_data['surname']}
"
        f"🎂 Yosh: {user_data['age']} da
"
        f"⚖️ Vazn: {user_data['weight']} kg"
    )
    await message.bot.send_message(ADMIN_ID, admin_text)

    # keyboard: murojaat + barcha kunlar
    keyboard = build_days_keyboard(weight, 1)

    await message.answer(
        "✅ Ma’lumotlaringiz qabul qilindi!

"
        "🎯 Endi siz o‘zingizni sog‘lom va eng yaxshi holatingizga olib boradigan yo‘lni boshladingiz!
"
        "Har bir kun sizni orzuyingizdagi natijaga yaqinlashtiradi.

"
        "🔥 Bu marafon faqat ovqatlanish emas — bu hayotingizni o‘zgartiradigan yo‘l!

"
        "⚡️ Esda tuting: dasturdan 3 kun bepul foydalanishingiz mumkin. Agar haqiqiy o‘zgarishni his qilsangiz, albatta davom etasiz.
"
        "👉 Siz bunga loyiqsiz!

"
        "▶️ Pastdagi tugmalardan boshlashingiz mumkin 👇",
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
    weight = user.get("weight", 0)
    current_day = user.get("day", 1)
    total_days = 40 if weight >= 100 else 30

    if day > current_day:
        await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)
        return

    # Agar 4-kunda va to'lov qilinmagan bo'lsa, to'lov matnini ko'rsatamiz va payment-flag qo'yamiz
    if day == 4 and 4 not in user.get("paid_days", []):
        # belgilanmagan bo'lsa awaiting_payment ni qo'yamiz
        user.setdefault('awaiting_payment', 4)
        set_user_data(user_id, user)
        await callback.message.edit_text(get_payment_text(), reply_markup=build_days_keyboard(weight, current_day))
        return

    # Normal matnni ko'rsatish
    text = read_day_file(weight, day)
    text += "

❓ Savollar bo‘lsa dietologga murojaat qiling 👇"

    # Agar bu hozirgi kun bo'lsa, keyingi kunni ochamiz
    if day == current_day and current_day < total_days:
        user['day'] = current_day + 1
        # agar awaiting_payment bor va foydalanuvchi o'tib yuborgan bo'lsa uni olib tashlash
        if user.get('awaiting_payment') and user['awaiting_payment'] <= user['day']:
            user.pop('awaiting_payment', None)
        set_user_data(user_id, user)

    await callback.message.edit_text(text, reply_markup=build_days_keyboard(weight, user.get('day', current_day)))

@router.callback_query(F.data == "locked")
async def locked_day(callback: CallbackQuery):
    await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)

@router.message(F.photo)
async def handle_payment_photo(message: Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        return
    user = get_user_data(user_id)
    if not user:
        return

    # Foydalanuvchida awaiting_payment flag bo'lishi kerak
    stage = user.get('awaiting_payment')
    if not stage:
        await message.answer("⛔ Sizda hozir to‘lov bosqichi yo‘q. Iltimos, to‘lov uchun 4-kunni ochib ko‘ring.")
        return

    photo_id = message.photo[-1].file_id

    token = f"KUN{stage}-{uuid.uuid4().hex[:6]}"
    tokens = load_tokens()
    tokens[token] = {"user_id": user_id, "stage": stage, "photo_file_id": photo_id}
    save_tokens(tokens)

    # Adminga yuborish
    caption = (
        f"💳 <b>Yangi to‘lov cheki</b>
"
        f"ID: <code>{user_id}</code>
"
        f"Ism: <b>{user.get('name','-')} {user.get('surname','-')}</b>
"
        f"✅ <b>Tasdiqlash kodi:</b> <code>{token}</code>"
    )
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=caption, parse_mode="HTML")

    await message.answer("✅ Chekingiz yuborildi. Admin ko‘rib chiqadi. Tasdiqlash kodi adminga yuborildi.")

@router.message(F.text.startswith("KUN"))
async def confirm_payment_token(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    token = message.text.strip()

    tokens = load_tokens()
    if token not in tokens:
        await message.answer("❌ Noto‘g‘ri yoki eskirgan token.")
        return

    info = tokens.pop(token)
    save_tokens(tokens)

    user_id = info['user_id']
    stage = info['stage']

    user = get_user_data(user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi.")
        return

    # Mark paid
    user.setdefault('paid_days', [])
    if stage not in user['paid_days']:
        user['paid_days'].append(stage)

    # O'tgan await flagni olib tashlaymiz
    if user.get('awaiting_payment') == stage:
        user.pop('awaiting_payment', None)

    # Foydalanuvchining day qiymatini stage+1 ga olib chiqamiz agar kerak bo'lsa
    if user.get('day', 1) <= stage:
        user['day'] = stage + 1

    set_user_data(user_id, user)

    await bot.send_message(chat_id=user_id, text=f"✅ To‘lov tasdiqlandi! {stage}-kun ochildi.")
    await message.answer(f"☑️ {user.get('name','-')} uchun {stage}-kun ochildi.")

@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar haqida", callback_data="stats")],
        [InlineKeyboardButton(text="📎  Savollarga javob berish", url=OZISH_BOT_URL)]
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
        f"📊 <b>Foydalanuvchilar statistikasi:</b>

"
        f"🔹 Jami: <b>{total}</b>
"
        f"⚖️ 100 kg dan kam: <b>{count_100_minus}</b>
"
        f"⚖️ 100 kg va undan ortiq: <b>{count_100_plus}</b>
"
        f"💰 To‘lov qilganlar: <b>{tolovchilar}</b>",
        parse_mode="HTML"
    )

# ----- Start polling -----
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
