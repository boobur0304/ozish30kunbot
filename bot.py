# improved_bot.py
import logging
import json
import os
import uuid
import asyncio
from datetime import datetime, timedelta

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
PROMOS_PATH = "database/promos.json"
RESULT_CHANNEL_LINK = os.getenv("RESULT_CHANNEL_LINK", "https://t.me/ozishchatbot")
OZISH_BOT = os.getenv("OZISH_BOT", "https://t.me/OzishChatBot")

os.makedirs("database", exist_ok=True)
# ensure files exist
for p in (TOKENS_PATH, USERS_PATH, PROMOS_PATH):
    if not os.path.exists(p):
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)

# Locks to protect file access inside the same process
users_lock = asyncio.Lock()
tokens_lock = asyncio.Lock()
promos_lock = asyncio.Lock()

class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()

class PromoForm(StatesGroup):
    code = State()

# ---- Helper: safe read/write users/tokens/promos with locks ----
async def load_users():
    async with users_lock:
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

# promos (async)
async def load_promos():
    async with promos_lock:
        try:
            with open(PROMOS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.warning("promos.json JSONDecodeError — returning empty dict")
            return {}
        except Exception as e:
            logging.exception("load_promos error: %s", e)
            return {}

async def save_promos(promos):
    async with promos_lock:
        try:
            tmp = PROMOS_PATH + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(promos, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PROMOS_PATH)
        except Exception as e:
            logging.exception("save_promos error: %s", e)

def mask_card(number: str) -> str:
    s = number.replace(" ", "")
    if len(s) >= 16:
        return f"{s[:4]} {s[4:8]} **** {s[-4:]}"
    return number

# ---- content helpers ----
def read_day_file(weight, day):
    folder = "data/days_plus" if weight >= 100 else "data/days"
    path = os.path.join(folder, f"day{day}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi."

def get_payment_text(weight, day):
    # only 4-kun requires payment in this design
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

def build_days_keyboard(weight, current_day, extra_buttons: list = None):
    """
    Barcha kun tugmalari chiqadi: ochilganlar ✅, hozirgi kun 💚, yopiq kunlar 🔒.
    Agar extra_buttons berilsa ularni oxirgi qator sifatida qo'shadi.
    extra_buttons — list of InlineKeyboardButton
    """
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
    # add extra buttons row (promo, etc.)
    if extra_buttons:
        # add each as its own button in a new row
        for btn in extra_buttons:
            # InlineKeyboardBuilder.row accepts button-like elements,
            # we can add InlineKeyboardButton directly.
            builder.row(btn)
    # add contact button as last row
    builder.row(InlineKeyboardButton(text="💬 Murojaat qilish", url=OZISH_BOT))
    return builder.as_markup()

# --- Kunlik eslatma funksiyasi ---
async def send_daily_reminders():
    while True:
        now = datetime.now()
        # Eslatma yuboriladigan vaqt (09:00)
        send_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now > send_time:
            send_time += timedelta(days=1)
        wait_seconds = (send_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        users = await load_users()
        for user_id, user in users.items():
            try:
                current_day = user.get("day", 1)
                weight = user.get("weight", 0)
                text = (
                    f"☀️ <b>Xayrli tong, {user.get('name', '')}!</b>\n\n"
                    f"🔥 Bugungi mashqlar va menyu tayyor.\n"
                    f"👉 Pastdagi tugma orqali <b>{current_day}-kun</b> ni boshlang!"
                )
                await bot.send_message(
                    chat_id=int(user_id),
                    text=text,
                    reply_markup=build_days_keyboard(weight, current_day)
                )
            except Exception as e:
                logging.error(f"Eslatma yuborishda xato ({user_id}): {e}")

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

    # --- Admin’ga xabar yuborish ---
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

    # --- Foydalanuvchiga tasdiq xabar va kun tugmalari ---
    days_keyboard = build_days_keyboard(weight, 1)

    user_text = (
        f"✅ <b>Ma’lumotlaringiz qabul qilindi!</b>\n\n"
        f"👤 Ism: <b>{user_data['name']}</b>\n"
        f"👤 Familiya: <b>{user_data['surname']}</b>\n"
        f"🎂 Yosh: <b>{user_data['age']} da</b>\n"
        f"⚖️ Vazn: <b>{user_data['weight']} kg</b>\n\n"
        "▶️ Pastdan <b>1-kun</b> tugmasini bosing va boshlang 👇"
    )

    await message.answer(user_text, reply_markup=days_keyboard)
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
        # show payment text with promo button appended
        markup = build_days_keyboard(weight, current_day, extra_buttons=[
            InlineKeyboardButton(text="🎁 Promokod bor", callback_data="promo")
        ])
        await callback.message.edit_text(get_payment_text(weight, day), reply_markup=markup)
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

# ----- Promokod oqimi: foydalanuvchi tomon -----
@router.callback_query(F.data == "promo")
async def ask_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎁 Iltimos, promokodingizni kiriting (masalan: PROMO30):")
    await state.set_state(PromoForm.code)

@router.message(PromoForm.code)
async def check_promo(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    promos = await load_promos()
    if code not in promos:
        await message.answer("❌ Noto‘g‘ri promokod yoki u bekor qilingan.")
        await state.clear()
        return

    value = promos[code]
    # determine price: if value is int -> fixed price, if percent like "30%" -> percent
    if isinstance(value, int):
        narx = value
    elif isinstance(value, str) and value.endswith("%"):
        percent = int(value[:-1])
        # base price for premium = 145000 (as used in messaging)
        base = 145000
        narx = int(base * (100 - percent) / 100)
    else:
        narx = 145000

    user_id = message.from_user.id
    user = await get_user_data(user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi. /start orqali qayta ro‘yxatdan o‘ting.")
        await state.clear()
        return

    # saqlaymiz: promo va discounted_price
    user['promo_code'] = code
    user['discounted_price'] = narx
    await set_user_data(user_id, user)

    await message.answer(
        f"✅ Promokod qabul qilindi: <b>{code}</b>\n"
        f"💳 Sizning chegirmali narxingiz: <b>{narx:,} so‘m</b>\n\n"
        "Iltimos, to‘lov qilganingizdan so‘ng chekni shu botga rasm qilib yuboring."
    )
    await state.clear()

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
    # include promo and price info for admin
    price = user.get('discounted_price', 145000)
    promo = user.get('promo_code')
    tokens[token] = {"user_id": user_id, "stage": stage, "price": price, "promo": promo}
    await save_tokens(tokens)

    caption = (
        f"💳 <b>Yangi to‘lov cheki</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"Ism: <b>{user.get('name','')} {user.get('surname','')}</b>\n"
        f"Narx: <b>{price:,} so'm</b>\n"
    )
    if promo:
        caption += f"Promokod: <b>{promo}</b>\n"
    caption += f"\n✅ <b>Tasdiqlash kodi:</b> <code>{token}</code>"

    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=caption, parse_mode="HTML")
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
    # optionally price/promo available:
    price = tokens[token].get('price')
    promo = tokens[token].get('promo')
    del tokens[token]
    await save_tokens(tokens)

    user = await get_user_data(user_id)
    if not user:
        await message.answer("❗ Foydalanuvchi topilmadi.")
        return

    if stage == 4 and user.get('day', 1) < 4:
        user['day'] = 4

    user.setdefault("paid_days", []).append(stage)
    # clear promo fields after confirmation to avoid reuse
    user.pop('discounted_price', None)
    user.pop('promo_code', None)
    await set_user_data(user_id, user)

    try:
        await bot.send_message(chat_id=user_id, text=f"✅ To‘lov tasdiqlandi! {stage}-kun ochildi.")
    except Exception as e:
        logging.exception("Failed to notify user about payment confirmation: %s", e)
    await message.answer(f"☑️ {user.get('name','')} uchun {stage}-kun ochildi.")

@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar haqida", callback_data="stats")],
        [InlineKeyboardButton(text="📎  Savollarga javob berish", url=RESULT_CHANNEL_LINK)]
    ])
    await message.answer("🔧 Admin menyusi:", reply_markup=keyboard)

@router.message(Command("addpromo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Foydalanish: /addpromo KOD chegirma\n"
                             "Masalan:\n"
                             "/addpromo PROMO30 30 (foiz)\n"
                             "/addpromo START99 99000 (fiks narx)")
        return

    code = args[1].upper()
    value = args[2]

    promos = await load_promos()

    # if value ends with % or is digit
    if value.endswith("%"):
        try:
            percent = int(value[:-1])
            promos[code] = f"{percent}%"
        except Exception:
            await message.answer("❌ Noto‘g‘ri foiz formati. Masalan: 30% yoki 30")
            return
    elif value.isdigit():
        # if user passed digits like 30 treat as percent OR fixed? we'll interpret:
        # if value length >=5 assume it's fixed price like 99000 else percent
        if len(value) >= 5:
            promos[code] = int(value)  # fixed price
        else:
            promos[code] = f"{int(value)}%"
    else:
        try:
            percent = int(value)
            promos[code] = f"{percent}%"
        except Exception:
            await message.answer("❌ Noto‘g‘ri qiymat.")
            return

    await save_promos(promos)
    await message.answer(f"✅ Promokod qo‘shildi: {code} → {promos[code]}")

@router.message(Command("sendall"))
async def send_all(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Xabar matnini olish
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("⚠️ Foydalanish: /sendall Xabar matni")
        return

    text = args[1]

    users = await load_users()
    count = 0
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), text)
            count += 1
        except Exception as e:
            logging.warning(f"{user_id} ga yuborilmadi: {e}")

    await message.answer(f"✅ Xabar {count} foydalanuvchiga yuborildi.")

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
    loop = asyncio.get_event_loop()
    # Kunlik eslatma taskini parallel ishga tushiramiz
    loop.create_task(send_daily_reminders())
    loop.run_until_complete(dp.start_polling(bot))
