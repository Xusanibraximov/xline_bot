#!/usr/bin/env python3
"""
🎬 X-LINE PRODUCTION MANAGER BOT
─────────────────────────────────
Google Sheets + Telegram + Railway

Imkoniyatlar:
  • Google Sheets dan real-time data o'qish
  • Har kuni 09:00 da bugungi reja (3 ta vazifa)
  • Tugma orqali "Bajarildi" status update qilish
  • Jarayondagi videolar, kontent kalendar, mijozlar
  • Har 3 kunda mijozlarga eslatma
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict

import gspread
import pytz
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ═══════════════════════════════════════════════
#  SOZLAMALAR (Environment Variables)
# ═══════════════════════════════════════════════

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
SHEET_ID = os.getenv("SHEET_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Samarkand")
DAILY_HOUR = int(os.getenv("DAILY_HOUR", "9"))
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ═══════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("xline-bot")

TZ = pytz.timezone(TIMEZONE)


# ═══════════════════════════════════════════════
#  GOOGLE AUTH (Service Account)
# ═══════════════════════════════════════════════

def get_credentials():
    """Service Account credentials olish.

    Railway:  CREDENTIALS_JSON env variable (to'liq JSON matn)
    Local:    credentials.json fayli
    """
    try:
        creds_json = os.getenv("CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            return ServiceAccountCredentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )

        if os.path.exists("credentials.json"):
            return ServiceAccountCredentials.from_service_account_file(
                "credentials.json", scopes=SCOPES
            )

        logger.error("❌ Credentials topilmadi (CREDENTIALS_JSON yoki credentials.json kerak)")
        return None
    except Exception as e:
        logger.error(f"❌ Credentials xatosi: {e}")
        return None


_gc_cache = None


def get_sheet():
    """Google Sheet obyektini qaytaradi (cache bilan)."""
    global _gc_cache
    try:
        if _gc_cache is None:
            creds = get_credentials()
            if not creds:
                return None
            _gc_cache = gspread.authorize(creds)
        return _gc_cache.open_by_key(SHEET_ID)
    except Exception as e:
        logger.error(f"❌ Sheet ulanish xatosi: {e}")
        return None


def clean_keys(row: Dict) -> Dict:
    """Ustun nomlaridagi ortiqcha bo'sh joyni olib tashlaydi.
    Masalan: 'Javobgar ' → 'Javobgar'
    """
    return {str(k).strip(): v for k, v in row.items()}


def read_sheet(tab_name: str) -> List[Dict]:
    """Berilgan sahifadan barcha qatorlarni o'qiydi (tozalangan kalitlar bilan)."""
    try:
        sheet = get_sheet()
        if not sheet:
            return []
        worksheet = sheet.worksheet(tab_name)
        return [clean_keys(r) for r in worksheet.get_all_records()]
    except Exception as e:
        logger.error(f"❌ '{tab_name}' o'qishda xato: {e}")
        return []


# ═══════════════════════════════════════════════
#  DATA FUNKSIYALAR
# ═══════════════════════════════════════════════

def get_vazifalar(limit: int = 20) -> List[Dict]:
    """Bajarilmagan vazifalar (Bajarildi = ❌ Yo'q)."""
    data = read_sheet("VAZIFALAR")
    pending = [t for t in data if "Yo'q" in str(t.get("Bajarildi", ""))]
    pending.sort(key=lambda x: str(x.get("Deadline", "")))
    return pending[:limit]


def get_videos() -> List[Dict]:
    """Jarayondagi videolar (Holat = Jarayonda / Kutilmoqda)."""
    data = read_sheet("VIDEO ISHLAB CHIQARISH")
    return [
        v for v in data
        if "Jarayonda" in str(v.get("Holat", ""))
        or "Kutilmoqda" in str(v.get("Holat", ""))
    ]


def get_kontent() -> List[Dict]:
    """Yaqin 7 kun ichidagi kontentlar."""
    data = read_sheet("KONTENT KALENDAR")
    today = date.today()
    results = []
    for item in data:
        sana_str = str(item.get("Sana", "")).strip()
        if not sana_str:
            continue
        parsed = _parse_date(sana_str)
        if parsed and today <= parsed <= today + timedelta(days=7):
            results.append(item)
    results.sort(key=lambda x: str(x.get("Sana", "")))
    return results


def get_mijozlar() -> List[Dict]:
    """Aktiv mijozlar (Holat = ✅ Aktiv)."""
    data = read_sheet("MIJOZLAR")
    return [m for m in data if "Aktiv" in str(m.get("Holat", ""))]


def get_uchrashuvlar() -> List[Dict]:
    """Kutilayotgan uchrashuvlar."""
    data = read_sheet("UCHRASHUVLAR")
    return [u for u in data if "Kutilmoqda" in str(u.get("Holat", ""))]


def update_task_status(task_id: str, new_status: str = "✅ Ha") -> bool:
    """VAZIFALAR sheetda 'Bajarildi' ustunini yangilaydi."""
    try:
        sheet = get_sheet()
        if not sheet:
            return False
        worksheet = sheet.worksheet("VAZIFALAR")
        records = [clean_keys(r) for r in worksheet.get_all_records()]

        # 'Bajarildi' ustunining indeksini topish
        headers = [h.strip() for h in worksheet.row_values(1)]
        try:
            col_index = headers.index("Bajarildi") + 1
        except ValueError:
            col_index = 6  # zaxira: F ustun

        for i, row in enumerate(records, start=2):  # 2 = header + 1-index
            if str(row.get("ID", "")).strip() == str(task_id).strip():
                worksheet.update_cell(i, col_index, new_status)
                return True
        return False
    except Exception as e:
        logger.error(f"❌ Status update xatosi: {e}")
        return False


def _parse_date(date_str: str):
    """Turli formatdagi sanani parse qiladi."""
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════════════
#  BOT BUYRUQLARI
# ═══════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🎬 *X-LINE PRODUCTION MANAGER*\n\n"
        "Assalomu alaykum! Men produksiya yordamchingizman.\n\n"
        "*Buyruqlar:*\n"
        "📋 /today — Bugungi 3 ta asosiy vazifa\n"
        "🎯 /tasks — Barcha bajarilmagan vazifalar\n"
        "🎬 /videos — Jarayondagi videolar\n"
        "📅 /content — Yaqin kontent rejasi\n"
        "🤝 /meetings — Kutilayotgan uchrashuvlar\n"
        "👥 /clients — Aktiv mijozlar\n"
        "📊 /stats — Umumiy statistika\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    tasks = get_vazifalar(limit=3)

    today_str = datetime.now(TZ).strftime("%d-%m-%Y, %A")
    text = f"☀️ *BUGUNGI REJA — {today_str}*\n\n"

    if not tasks:
        await msg.edit_text("✅ Barcha vazifalar bajarilgan! 🎉")
        return

    text += "📋 *3 ta asosiy vazifa:*\n\n"
    keyboard = []
    for t in tasks:
        tid = t.get("ID", "")
        title = t.get("Vazifa", "")
        deadline = t.get("Deadline", "")
        priority = t.get("Muhimligi", "")
        javobgar = t.get("Javobgar", "")
        text += f"{priority}  *{title}*\n"
        text += f"      👤 {javobgar}   📅 {deadline}\n\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ {title[:28]}", callback_data=f"done::{tid}")
        ])

    await msg.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    tasks = get_vazifalar(limit=20)

    if not tasks:
        await msg.edit_text("✅ Bajarilmagan vazifa yo'q!")
        return

    text = f"📋 *BAJARILMAGAN VAZIFALAR ({len(tasks)} ta):*\n\n"
    for t in tasks:
        priority = t.get("Muhimligi", "")
        title = t.get("Vazifa", "")
        javobgar = t.get("Javobgar", "")
        deadline = t.get("Deadline", "")
        text += f"{priority}  *{title}*\n      👤 {javobgar}   📅 {deadline}\n\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    videos = get_videos()

    if not videos:
        await msg.edit_text("✅ Jarayondagi video yo'q!")
        return

    text = f"🎬 *JARAYONDAGI VIDEOLAR ({len(videos)} ta):*\n\n"
    for v in videos:
        vid = v.get("ID", "")
        mavzu = v.get("Mavzu", "") or "—"
        loyiha = v.get("Loyiha", "") or "—"
        holat = v.get("Holat", "")
        deadline = v.get("Deadline", "")
        text += f"🎥 *{vid}* — {mavzu}\n      🎬 {loyiha}\n      {holat}   📅 {deadline}\n\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    contents = get_kontent()

    if not contents:
        await msg.edit_text("❌ Yaqin 7 kunda kontent yo'q.")
        return

    text = f"📅 *YAQIN KONTENT ({len(contents)} ta):*\n\n"
    for c in contents:
        sana = c.get("Sana", "")
        vaqt = c.get("Vaqt", "")
        loyiha = c.get("Loyiha", "")
        platforma = c.get("Platforma", "")
        turi = c.get("Turi", "")
        mavzu = c.get("Mavzu", "")
        holat = c.get("Holat", "")
        text += f"{holat}  *{sana}  {vaqt}*\n      🎬 {loyiha} | {platforma}\n      📝 {turi} — {mavzu}\n\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_meetings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    meetings = get_uchrashuvlar()

    if not meetings:
        await msg.edit_text("✅ Kutilayotgan uchrashuv yo'q!")
        return

    text = f"🤝 *KUTILAYOTGAN UCHRASHUVLAR ({len(meetings)} ta):*\n\n"
    for u in meetings:
        sana = u.get("Sana", "")
        vaqt = u.get("Vaqt", "")
        kim = u.get("Kim bilan", "")
        maqsad = u.get("Maqsad", "")
        text += f"📌 *{sana}  {vaqt}*\n      👤 {kim}\n      🎯 {maqsad}\n\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    clients = get_mijozlar()

    if not clients:
        await msg.edit_text("❌ Aktiv mijoz topilmadi.")
        return

    text = f"👥 *AKTIV MIJOZLAR ({len(clients)} ta):*\n\n"
    for c in clients:
        name = c.get("Mijoz", "")
        platforma = c.get("Platforma", "")
        masul = c.get("Mas'ul", "")
        yordamchi = c.get("Yordamchi", "")
        text += f"👤 *{name}*\n      📱 {platforma}\n      👨‍💼 {masul} / {yordamchi}\n\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("⏳ Yuklanmoqda...")
    tasks = get_vazifalar()
    videos = get_videos()
    contents = get_kontent()
    clients = get_mijozlar()
    meetings = get_uchrashuvlar()

    text = (
        "📊 *UMUMIY STATISTIKA*\n\n"
        f"👥 Aktiv mijozlar:  *{len(clients)}* ta\n"
        f"📋 Bajarilmagan vazifalar:  *{len(tasks)}* ta\n"
        f"🎬 Jarayondagi videolar:  *{len(videos)}* ta\n"
        f"📅 Yaqin kontent:  *{len(contents)}* ta\n"
        f"🤝 Kutilayotgan uchrashuvlar:  *{len(meetings)}* ta\n"
    )
    await msg.edit_text(text, parse_mode="Markdown")


# ═══════════════════════════════════════════════
#  CALLBACK (Tugma bosilganda)
# ═══════════════════════════════════════════════

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("done::"):
        task_id = query.data.split("::", 1)[1]
        ok = update_task_status(task_id, "✅ Ha")
        if ok:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"✅ Vazifa *{task_id}* bajarildi deb belgilandi!",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                f"⚠️ Vazifa {task_id} topilmadi yoki update bo'lmadi."
            )


# ═══════════════════════════════════════════════
#  AVTOMATIK VAZIFALAR (Scheduler)
# ═══════════════════════════════════════════════

async def job_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni ertalab bugungi reja yuborish."""
    if not ADMIN_CHAT_ID:
        return

    tasks = get_vazifalar(limit=3)
    videos = get_videos()

    today_str = datetime.now(TZ).strftime("%d-%m-%Y")
    text = f"🌅 *XAYRLI TONG! — {today_str}*\n\n"

    if tasks:
        text += "📋 *Bugungi 3 ta asosiy vazifa:*\n\n"
        keyboard = []
        for t in tasks:
            tid = t.get("ID", "")
            title = t.get("Vazifa", "")
            priority = t.get("Muhimligi", "")
            text += f"{priority}  {title}\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ {title[:28]}", callback_data=f"done::{tid}")
            ])
        text += f"\n🎬 Jarayondagi videolar: {len(videos)} ta"
        markup = InlineKeyboardMarkup(keyboard)
    else:
        text += "🎉 Bugun bajarilmagan vazifa yo'q!"
        markup = None

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID, text=text,
        parse_mode="Markdown", reply_markup=markup
    )


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════

def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN o'rnatilmagan!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("videos", cmd_videos))
    app.add_handler(CommandHandler("content", cmd_content))
    app.add_handler(CommandHandler("meetings", cmd_meetings))
    app.add_handler(CommandHandler("clients", cmd_clients))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_button))

    # Har kuni ertalabki hisobot
    if app.job_queue:
        report_time = datetime.now(TZ).replace(
            hour=DAILY_HOUR, minute=0, second=0, microsecond=0
        ).timetz()
        app.job_queue.run_daily(job_daily_report, time=report_time, name="daily_report")

    logger.info("🚀 X-LINE BOT ISHGA TUSHDI!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
