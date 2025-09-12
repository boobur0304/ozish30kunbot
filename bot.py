# improved_bot_with_tz.py
# Yangilangan va qayta tekshirilgan versiya: Toshkent (Asia/Tashkent) vaqtiga mos reminder
# Muallif: ChatGPT yordamida yangilandi

import logging
import json
import os
import uuid
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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

# ---------- States (MUST be defined before handlers) ----------
class Form(StatesGroup):
    name = State()
    surname = State()
    age = State()
    weight = State()

class PromoForm(StatesGroup):
    code = State()

# ---------- Config (env override possible) ----------
API_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "983517327"))
except Exception:
    ADMIN_ID = 983517327
CARD_NUMBER = os.getenv("CARD_NUMBER", "9860350110461737")
INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "https://www.instagram.com/ozish30kunbot")
RESULT_CHANNEL_LINK = os.getenv("RESULT_CHANNEL_LINK", "https://t.me/ozishchatbot")
OZISH_BOT = os.getenv("OZISH_BOT", "https://t.me/OzishChatBot")
# Reminder hour in Tashkent time (default 7)
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "7"))

# Timezone
UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Database files
USERS_PATH = "database/users.json"
TOKENS_PATH = "database/tokens.json"
PROMOS_PATH = "database/promos.json"

os.makedirs("database", exist_ok=True)
# ensure files exist
for p in (TOKENS_PATH, USERS_PATH, PROMOS_PATH):
    if not os.path.exists(p):
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)

# Locks
users_lock = asyncio.Lock()
tokens_lock = asyncio.Lock()
promos_lock = asyncio.Lock()

# ---------- Generic JSON helpers ----------
async def load_json(path: str, lock: asyncio.Lock):
    async with lock:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("%s JSONDecodeError — returning empty dict", path)
            return {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.exception("load_json(%s) error: %s", path, e)
            return {}

async def save_json(path: str, lock: asyncio.Lock, data: dict):
    async with lock:
        try:
            tmp = path + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.exception("save_json(%s) error: %s", path, e)

# Specific wrappers
async def load_users():
    return await load_json(USERS_PATH, users_lock)

async def save_users(users: dict):
    await save_json(USERS_PATH, users_lock, users)

async def load_tokens():
    return await load_json(TOKENS_PATH, tokens_lock)

async def save_tokens(tokens: dict):
    await save_json(TOKENS_PATH, tokens_lock, tokens)

async def load_promos():
    return await load_json(PROMOS_PATH, promos_lock)

async def save_promos(promos: dict):
    await save_json(PROMOS_PATH, promos_lock, promos)

# ---------- Utility: get/set user data (kept before handlers for clarity) ----------
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

# ---------- Helpers ----------

def mask_card(number: str) -> str:
    s = number.replace(" ", "")
    if len(s) >= 16:
        return f"{s[:4]} {s[4:8]} **** {s[-4:]}"
    return number


def read_day_file(weight, day):
    folder = "data/days_plus" if weight >= 100 else "data/days"
    path = os.path.join(folder, f"day{day}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Ushbu kun uchun ma'lumot topilmadi."


def get_payment_text(weight, day):
    if day == 4:
        return (
            f"🎉 Siz 3 kunlik <b>bepul dasturdan</b> muvaffaqiyatli o‘tdingiz!

"
            "👉 Endi <b>premium bosqichni</b> davom ettirish uchun to‘lov qilishingiz kerak.

"
            "✅ Natijada:
"
            "▫️ 30 kunda <b>-16 kg</b>
"
            "▫️ 40 kunda <b>-19 kg</b>

"
            f"💳 <b>To‘lov narxi:</b> <s>199,000 so‘m</s> ➝ <b>145,000 so‘m</b>
"
            "(kuniga ~4,800 so‘m, ya’ni bir choy narxi)

"
            f"💳 <b>Karta raqami:</b> <code>{CARD_NUMBER}</code>
"
            "👤 <b>Karta egasi:</b> <b>B.Nematov</b>

"
            "📸 <b>To‘lov chekini shu botga yuboring.</b>
"
            "⏱ <i>10 daqiqa ichida admin tasdiqlaydi</i> va keyingi kuningiz ochiladi!

"
            "⚡️ <b>Eslatma:</b> Agar bugun to‘lamasangiz, dastur <u>to‘xtab qoladi</u> va natija <u>kechikadi</u>.

"
            "━━━━━━━━━━━━━━━━━━━

"
            "✨ <b>Siz bu narxga yana chegirma olishingiz mumkin!</b>

"
            "📲 Buning uchun:
"
            "1️⃣ <b>Instagram sahifamizga o‘ting</b> va sahifaga obuna bo‘ling.
"
            "2️⃣ <b>Promokod oling</b> (sahifada e’lon qilinadi).
"
            "3️⃣ Botdagi <b>“🎁 Promokod bor”</b> tugmasini bosing va kodingizni kiriting.

"
            "✅ Shunda adminlar sizga chegirma qo‘llashadi.

"
            "❓ Savollar bo‘lsa, pastdagi <b>“💬 Murojaat qilish”</b> tugmasini bosing."
        )
    return ""


def build_days_keyboard(weight, current_day, extra_buttons: list = None):
    """
    Instagram tugmasi yuqorida (sala keng), keyin kun tugmalari 4 tadan guruhlangan,
    keyin extra_buttons (har biri o'z satrida) va oxirida murojaat tugmasi.
    """
    total_days = 40 if weight >= 100 else 30

    rows = []

    # instagram row
    rows.append([
        InlineKeyboardButton(
            text="🎁 Instagramdan PROMOKOD olish",
            url=INSTAGRAM_URL
        )
    ])

    day_buttons = []
    for day in range(1, total_days + 1):
        if day == current_day:
            day_buttons.append(InlineKeyboardButton(text=f"💚 Kun {day}", callback_data=f"day_{day}"))
        elif day < current_day:
            day_buttons.append(InlineKeyboardButton(text=f"✅ Kun {day}", callback_data=f"day_{day}"))
        else:
            day_buttons.append(InlineKeyboardButton(text=f"🔒 Kun {day}", callback_data="locked"))

    for i in range(0, len(day_buttons), 4):
        rows.append(day_buttons[i:i+4])

    if extra_buttons:
        for btn in extra_buttons:
            rows.append([btn])

    rows.append([InlineKeyboardButton(text="💬 Murojaat qilish", url=OZISH_BOT)])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# ---------- Reminder task (Toshkent vaqti bilan) ----------
async def send_daily_reminders():
    """Background task that wakes up at REMINDER_HOUR (Asia/Tashkent) every day and sends reminders."""
    hour = REMINDER_HOUR
    tz = UZBEKISTAN_TZ
    logger.info("send_daily_reminders started (Tashkent timezone) — hour=%s", hour)

    while True:
        now = datetime.now(tz)
        # next occurrence at today:hour:00
        send_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now >= send_time:
            send_time += timedelta(days=1)

        wait_seconds = (send_time - now).total_seconds()
        logger.info("Next reminders at %s (in %.0f seconds)", send_time.isoformat(), wait_seconds)

        try:
            # sleep until next scheduled time
            await asyncio.sleep(wait_seconds)
        except asyncio.CancelledError:
            logger.info("send_daily_reminders cancelled — exiting task")
            return
        except Exception as e:
            logger.exception("Unexpected error while sleeping in reminder task: %s", e)
            # small delay to avoid tight loop on unexpected errors
            await asyncio.sleep(60)
            continue

        # it's time to send reminders
        users = await load_users()
        for user_id, user in list(users.items()):
            try:
                current_day = user.get("day", 1)
                weight = user.get("weight", 0)
                text = (
                    f"☀️ <b>Xayrli tong, {user.get('name', '')}!</b>

"
                    "🔥 Bugungi mashqlar va menyu tayyor.
"
                    f"👉 Pastdagi tugma orqali <b>{current_day}-kun</b> ni boshlang!"
                )
                await bot.send_message(
                    chat_id=int(user_id),
                    text=text,
                    reply_markup=build_days_keyboard(weight, current_day)
                )
            except Exception as e:
                # if chat blocked or other error, just log and continue
                logger.exception("Eslatma yuborishda xato (%s): %s", user_id, e)

# ---------- Handlers (unchanged logic, but kept robust) ----------
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
        "🎁 Chegirma olish uchun promokod faqat Instagram kanalimizda tarqatiladi —
"
        f"👉 <a href=\"{INSTAGRAM_URL}\">Instagramga o‘tish</a>

"
        "Ismingizni kiriting:",
        parse_mode="HTML"
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

    # Admin notification
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
    try:
        await bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        logger.exception("Failed to send admin notification: %s", e)

    days_keyboard = build_days_keyboard(weight, 1)

    user_text = (
        f"✅ <b>Ma’lumotlaringiz qabul qilindi!</b>

"
        f"👤 Ism: <b>{user_data['name']}</b>
"
        f"👤 Familiya: <b>{user_data['surname']}</b>
"
        f"🎂 Yosh: <b>{user_data['age']} da</b>
"
        f"⚖️ Vazn: <b>{user_data['weight']} kg</b>

"
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

    text = read_day_file(weight, day)
    text += "

❓ Savollar bo‘lsa dietologga murojaat qiling 👇"
    if day == current_day and current_day < total_days:
        user["day"] = current_day + 1
        await set_user_data(user_id, user)
    await callback.message.edit_text(text, reply_markup=build_days_keyboard(weight, user["day"]))


@router.callback_query(F.data == "locked")
async def locked_day(callback: CallbackQuery):
    await callback.answer("⛔ Bu kun hali ochilmagan!", show_alert=True)

# ---------- Promokod oqimi: foydalanuvchi tomon ----------
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
    if isinstance(value, int):
        narx = value
    elif isinstance(value, str) and value.endswith("%"):
        percent = int(value[:-1])
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

    user['promo_code'] = code
    user['discounted_price'] = narx
    await set_user_data(user_id, user)

    await message.answer(
        f"✅ Promokod qabul qilindi: <b>{code}</b>
"
        f"💳 Sizning chegirmali narxingiz: <b>{narx:,} so‘m</b>

"
        "Iltimos, to‘lov qilganingizdan so‘ng chekni shu botga rasm qilib yuboring."
    )
    await state.clear()

# ---------- Payment photo handling (user sends check) ----------
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
    if day == 4:
        stage = 4
    else:
        await message.answer("⛔ Sizda hozir to‘lov bosqichi yo‘q.")
        return

    token = f"KUN{stage}-{uuid.uuid4().hex[:6]}"
    tokens = await load_tokens()
    price = user.get('discounted_price', 145000)
    promo = user.get('promo_code')
    tokens[token] = {"user_id": user_id, "stage": stage, "price": price, "promo": promo}
    await save_tokens(tokens)

    caption = (
        f"💳 <b>Yangi to‘lov cheki</b>
"
        f"ID: <code>{user_id}</code>
"
        f"Ism: <b>{user.get('name','')} {user.get('surname','')}</b>
"
        f"Narx: <b>{price:,} so'm</b>
"
    )
    if promo:
        caption += f"Promokod: <b>{promo}</b>
"
    caption += f"
✅ <b>Tasdiqlash kodi:</b> <code>{token}</code>"

    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.exception("Failed to forward payment photo to admin: %s", e)

    await message.answer("✅ Chekingiz yuborildi. Admin ko‘rib chiqadi.")

# ---------- Admin confirms token ----------
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
    user.pop('discounted_price', None)
    user.pop('promo_code', None)
    await set_user_data(user_id, user)

    try:
        await bot.send_message(chat_id=user_id, text=f"✅ To‘lov tasdiqlandi! {stage}-kun ochildi.")
    except Exception as e:
        logger.exception("Failed to notify user about payment confirmation: %s", e)
    await message.answer(f"☑️ {user.get('name','')} uchun {stage}-kun ochildi.")

# ---------- Admin menu ----------
@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Foydalanuvchilar haqida", callback_data="stats")],
        [InlineKeyboardButton(text="📎  Savollarga javob berish", url=RESULT_CHANNEL_LINK)]
    ])
    await message.answer("🔧 Admin menyusi:", reply_markup=keyboard)

# ---------- Add / Delete promo (admin) ----------
@router.message(Command("addpromo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Foydalanish: /addpromo KOD chegirma
"
                             "Masalan:
"
                             "/addpromo PROMO30 30 (foiz) yoki /addpromo START99 99000 (fiks narx)")
        return

    code = args[1].upper()
    value = args[2]

    promos = await load_promos()

    if value.endswith("%"):
        try:
            percent = int(value[:-1])
            promos[code] = f"{percent}%"
        except Exception:
            await message.answer("❌ Noto‘g‘ri foiz formati. Masalan: 30% yoki 30")
            return
    elif value.isdigit():
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


@router.message(Command("delpromo"))
async def delete_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("⚠️ Foydalanish: /delpromo PROMOKOD
Masalan: /delpromo PROMO30")
        return

    code = args[1].upper()
    promos = await load_promos()
    if code not in promos:
        await message.answer("❌ Bunday promokod topilmadi.")
        return

    promos.pop(code)
    await save_promos(promos)
    await message.answer(f"✅ Promokod o‘chirildi: {code}")

# ---------- Broadcast (admin) ----------
@router.message(Command("sendall"))
async def send_all(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

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
            logger.warning("%s ga yuborilmadi: %s", user_id, e)

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

# ---------- Startup task registration ----------
async def _on_startup():
    """Called by aiogram dispatcher at startup. We create background task here."""
    # create background task to send reminders
    asyncio.create_task(send_daily_reminders())

# register startup hook
dp.startup.register(_on_startup)

# ---------- Run ----------
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        dp.run_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by signal")
    except Exception as e:
        logger.exception("Bot stopped with error: %s", e)
