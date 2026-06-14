#!/usr/bin/env python3
"""
🎬 X-LINE PRODUCTION MANAGER + WORKFLOW TRACKER
================================================
TO'LIQ BOT — buyruqlar + mustaqil kuzatuv

BUYRUQLAR (so'rovga javob):
  /today, /tasks, /videos, /content, /meetings, /clients, /stats

MUSTAQIL KUZATUV (avtomatik):
  📸 STORY  — har kuni 09:00, 14:00, 19:00
      1) Mijoz guruhiga "ma'lumot tashlang"
      2) +10 daq → storymaker'ga "berdimi?" [Ha/Yo'q]
      3) Ha → "nechta?" [1/2/3]  (3 ga yetguncha eslatadi)
      4) Yo'q → mijoz guruhiga "tashlamadingiz"
  📤 POST   — har kuni 17:00 storymaker'ga "yuklandimi?"
  ⏰ VAZIFA — har soatda mas'ulga eslatma
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

import gspread
import pytz
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials as SA

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

# ═══════════════════════════════════════════════
#  SOZLAMALAR
# ═══════════════════════════════════════════════
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_CHAT_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))
SHEET_ID       = os.getenv("SHEET_ID", "")
TIMEZONE       = os.getenv("TIMEZONE", "Asia/Samarkand")

STORY_HOURS   = [9, 14, 19]   # story eslatma soatlari
POST_HOUR     = 17            # post eslatma soati
ASK_DELAY_MIN = 10            # storymaker'dan so'rashdan oldin kutish (daqiqa)
STORY_TARGET  = 3             # kuniga kerakli story soni

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TZ = pytz.timezone(TIMEZONE)

logging.basicConfig(
    format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO
)
logger = logging.getLogger("xline")

# ═══════════════════════════════════════════════
#  GOOGLE SHEETS
# ═══════════════════════════════════════════════
_client = None


def get_credentials():
    try:
        cj = os.getenv("CREDENTIALS_JSON")
        if cj:
            return SA.from_service_account_info(json.loads(cj), scopes=SCOPES)
        if os.path.exists("credentials.json"):
            return SA.from_service_account_file("credentials.json", scopes=SCOPES)
        logger.error("❌ Credentials topilmadi")
        return None
    except Exception as e:
        logger.error(f"❌ Credentials xatosi: {e}")
        return None


def get_book():
    global _client
    try:
        if _client is None:
            creds = get_credentials()
            if not creds:
                return None
            _client = gspread.authorize(creds)
        return _client.open_by_key(SHEET_ID)
    except Exception as e:
        logger.error(f"❌ Sheet ulanish xatosi: {e}")
        return None


def clean_keys(row: Dict) -> Dict:
    return {str(k).strip(): v for k, v in row.items()}


def esc(text) -> str:
    """Telegram Markdown uchun xavfli belgilarni tozalaydi.
    Sheetdagi ma'lumotda *, _, [, ` bo'lsa, parse xatosini oldini oladi.
    """
    s = str(text) if text is not None else ""
    for ch in ("*", "_", "[", "]", "`"):
        s = s.replace(ch, "")
    return s


def read_sheet(tab: str) -> List[Dict]:
    try:
        book = get_book()
        if not book:
            return []
        ws = book.worksheet(tab)
        return [clean_keys(r) for r in ws.get_all_records()]
    except Exception as e:
        logger.error(f"❌ '{tab}' o'qishda xato: {e}")
        return []


def get_or_create_ws(title: str, headers: List[str]):
    book = get_book()
    if not book:
        return None
    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=title, rows=300, cols=max(12, len(headers)))
        ws.append_row(headers)
        logger.info(f"✅ '{title}' sahifasi yaratildi")
        return ws


# ── Sahifa sxemalari ──
TRACKER_HEADERS = [
    "Sana", "Mijoz ID", "Mijoz nomi", "Guruh ID",
    "Storymaker", "Storymaker TG ID",
    "Story holati", "Story soni", "Video holati",
    "Post holati", "Oxirgi yangilanish",
]
GROUPS_HEADERS = [
    "Mijoz ID", "Mijoz nomi", "Guruh ID",
    "Storymaker nomi", "Storymaker TG ID", "Aktiv",
]


def ensure_sheets():
    # MIJOZ_BOT allaqachon mavjud — faqat TRACKER kerak
    get_or_create_ws("TRACKER", TRACKER_HEADERS)


# ═══════════════════════════════════════════════
#  DATA — asosiy sahifalar (buyruqlar uchun)
# ═══════════════════════════════════════════════
def _parse_date(s: str):
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def get_vazifalar(limit=20):
    data = read_sheet("VAZIFALAR")
    p = [t for t in data if "Yo'q" in str(t.get("Bajarildi", ""))]
    p.sort(key=lambda x: str(x.get("Deadline", "")))
    return p[:limit]


def get_videos():
    data = read_sheet("VIDEO ISHLAB CHIQARISH")
    return [v for v in data if "Jarayonda" in str(v.get("Holat", ""))
            or "Kutilmoqda" in str(v.get("Holat", ""))]


def get_kontent():
    data = read_sheet("KONTENT KALENDAR")
    today = date.today()
    out = []
    for it in data:
        d = _parse_date(str(it.get("Sana", "")))
        if d and today <= d <= today + timedelta(days=7):
            out.append(it)
    return out


def get_mijozlar():
    return [m for m in read_sheet("MIJOZLAR") if "Aktiv" in str(m.get("Holat", ""))]


def get_uchrashuvlar():
    return [u for u in read_sheet("UCHRASHUVLAR") if "Kutilmoqda" in str(u.get("Holat", ""))]


# ═══════════════════════════════════════════════
#  WORKFLOW — guruhlar va tracker
# ═══════════════════════════════════════════════
def today_str():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _norm_group(r: Dict) -> Dict:
    """MIJOZ_BOT ustunlarini bot ichki nomlariga moslaydi.

    MIJOZ_BOT:  Mijoz ID | Mijoz nomi | Mijoz TG ID | Mas'ul ismi |
                Mas'ul TG ID | Kunlik kontent | Guruh ID | Holat | ...
    """
    return {
        "Mijoz ID":          r.get("Mijoz ID", ""),
        "Mijoz nomi":        r.get("Mijoz nomi", ""),
        "Guruh ID":          r.get("Guruh ID", ""),
        "Storymaker nomi":   r.get("Mas'ul ismi", "") or r.get("Mas'ul", ""),
        "Storymaker TG ID":  r.get("Mas'ul TG ID", ""),
        "Mijoz TG ID":       r.get("Mijoz TG ID", ""),
        "Kunlik kontent":    r.get("Kunlik kontent", STORY_TARGET),
        "Holat":             r.get("Holat", ""),
    }


def get_groups():
    """MIJOZ_BOT sahifasidan aktiv mijozlarni o'qiydi."""
    rows = read_sheet("MIJOZ_BOT")
    out = []
    for r in rows:
        g = _norm_group(r)
        # Guruh ID bo'lmasa, kuzatib bo'lmaydi — o'tkazib yuboramiz
        if not str(g.get("Guruh ID", "")).strip():
            continue
        # 'Holat' bo'sh yoki "tugagan/pauza" bo'lmasa — aktiv hisoblaymiz
        holat = str(g.get("Holat", "")).strip().lower()
        if "tugagan" in holat or "pauza" in holat or "❌" in holat or "⏸" in holat:
            continue
        out.append(g)
    return out


def get_today_row(mid):
    rows = read_sheet("TRACKER")
    for r in rows:
        if str(r.get("Mijoz ID", "")).strip() == str(mid).strip() \
                and str(r.get("Sana", "")).strip() == today_str():
            return r
    return None


def get_story_count(mid):
    r = get_today_row(mid)
    if not r:
        return 0
    try:
        return int(r.get("Story soni", 0) or 0)
    except (ValueError, TypeError):
        return 0


def get_target(g: Dict) -> int:
    """Mijozning kunlik story maqsadi (Kunlik kontent ustuni)."""
    try:
        t = int(str(g.get("Kunlik kontent", "")).strip() or STORY_TARGET)
        return t if t > 0 else STORY_TARGET
    except (ValueError, TypeError):
        return STORY_TARGET


def init_today_tracker():
    ws = get_or_create_ws("TRACKER", TRACKER_HEADERS)
    if not ws:
        return
    existing = set()
    for r in [clean_keys(x) for x in ws.get_all_records()]:
        if str(r.get("Sana", "")).strip() == today_str():
            existing.add(str(r.get("Mijoz ID", "")).strip())
    for g in get_groups():
        mid = str(g.get("Mijoz ID", "")).strip()
        if mid and mid not in existing:
            ws.append_row([
                today_str(), mid, g.get("Mijoz nomi", ""), g.get("Guruh ID", ""),
                g.get("Storymaker nomi", ""), g.get("Storymaker TG ID", ""),
                "kutilmoqda", "0", "kutilmoqda", "kutilmoqda",
                datetime.now(TZ).strftime("%H:%M"),
            ])
    logger.info("✅ Bugungi tracker tayyor")


def update_tracker(mid, field, value):
    ws = get_or_create_ws("TRACKER", TRACKER_HEADERS)
    if not ws:
        return False
    headers = [h.strip() for h in ws.row_values(1)]
    try:
        col = headers.index(field) + 1
    except ValueError:
        return False
    rows = ws.get_all_records()
    for i, r in enumerate(rows, start=2):
        r = clean_keys(r)
        if str(r.get("Mijoz ID", "")).strip() == str(mid).strip() \
                and str(r.get("Sana", "")).strip() == today_str():
            ws.update_cell(i, col, value)
            try:
                tcol = headers.index("Oxirgi yangilanish") + 1
                ws.update_cell(i, tcol, datetime.now(TZ).strftime("%H:%M"))
            except ValueError:
                pass
            return True
    return False


# ── Xabar yuborish ──
async def send_group(ctx, gid, text, markup=None):
    try:
        await ctx.bot.send_message(chat_id=int(gid), text=text,
                                   parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ Guruh ({gid}) xato: {e}")


async def send_user(ctx, uid, text, markup=None):
    try:
        await ctx.bot.send_message(chat_id=int(uid), text=text,
                                   parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ User ({uid}) xato: {e}")


# ═══════════════════════════════════════════════
#  STORY WORKFLOW
# ═══════════════════════════════════════════════
async def story_notify_group(ctx: ContextTypes.DEFAULT_TYPE):
    for g in get_groups():
        mid = str(g.get("Mijoz ID", "")).strip()
        if get_story_count(mid) >= get_target(g):
            continue
        gid = g.get("Guruh ID", "")
        if not gid:
            continue
        await send_group(ctx, gid,
            "🎬 *Story uchun ma'lumot*\n\n"
            "Assalomu alaykum! Bugun story uchun rasm, video yoki "
            "ma'lumot tashlab berishingizni so'raymiz. 🙏")
        ctx.job_queue.run_once(
            story_ask_sm, when=ASK_DELAY_MIN * 60,
            data={"mid": mid},
            name=f"ask_{mid}_{datetime.now(TZ).strftime('%H%M%S')}")


async def story_ask_sm(ctx: ContextTypes.DEFAULT_TYPE):
    mid = ctx.job.data.get("mid")
    g = next((x for x in get_groups()
              if str(x.get("Mijoz ID", "")).strip() == str(mid)), None)
    if not g:
        return
    sm = g.get("Storymaker TG ID", "")
    if not sm:
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha", callback_data=f"info::yes::{mid}"),
        InlineKeyboardButton("❌ Yo'q", callback_data=f"info::no::{mid}"),
    ]])
    await send_user(ctx, sm, f"❓ *{esc(g.get('Mijoz nomi',''))}* ma'lumot berdilarmi?", kb)


async def post_ask(ctx: ContextTypes.DEFAULT_TYPE):
    for g in get_groups():
        sm = g.get("Storymaker TG ID", "")
        mid = str(g.get("Mijoz ID", "")).strip()
        if not sm:
            continue
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ha", callback_data=f"post::yes::{mid}"),
            InlineKeyboardButton("❌ Yo'q", callback_data=f"post::no::{mid}"),
        ]])
        await send_user(ctx, sm, f"📤 *{esc(g.get('Mijoz nomi',''))}* uchun post yuklandimi?", kb)


# ═══════════════════════════════════════════════
#  VAZIFA ESLATMA (har soatda)
# ═══════════════════════════════════════════════
def get_person_tg(name):
    for sheet in ("Hodimlar", "JAMOA"):
        for r in read_sheet(sheet):
            ism = str(r.get("Ism", "")).strip()
            tg = r.get("Tg id") or r.get("Telegram ID") or r.get("TG ID")
            if ism and name and ism.lower() in name.lower() and tg:
                return str(tg).strip()
    return None


async def hourly_tasks(ctx: ContextTypes.DEFAULT_TYPE):
    hour = datetime.now(TZ).hour
    if hour < 9 or hour > 21:   # faqat 09:00–21:00
        return
    by_person = {}
    for r in read_sheet("VAZIFALAR"):
        if "Yo'q" in str(r.get("Bajarildi", "")):
            p = str(r.get("Javobgar", "")).strip()
            by_person.setdefault(p, []).append(r)
    for person, tasks in by_person.items():
        tg = get_person_tg(person)
        if not tg:
            continue
        text = f"⏰ *Bajarilmagan vazifalar ({len(tasks)} ta):*\n\n"
        for t in tasks[:10]:
            text += f"  {esc(t.get('Muhimligi',''))} {esc(t.get('Vazifa',''))} — 📅 {esc(t.get('Deadline',''))}\n"
        await send_user(ctx, tg, text)


# ═══════════════════════════════════════════════
#  CALLBACK
# ═══════════════════════════════════════════════
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("::")
    act = parts[0]

    if act == "info":
        ans, mid = parts[1], parts[2]
        if ans == "yes":
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("1", callback_data=f"count::1::{mid}"),
                InlineKeyboardButton("2", callback_data=f"count::2::{mid}"),
                InlineKeyboardButton("3", callback_data=f"count::3::{mid}"),
            ]])
            await q.edit_message_text("👍 Ajoyib! Nechta kontent berildi?", reply_markup=kb)
        else:
            update_tracker(mid, "Story holati", "ma'lumot berilmadi")
            g = next((x for x in get_groups()
                      if str(x.get("Mijoz ID", "")).strip() == str(mid)), None)
            if g and g.get("Guruh ID"):
                await send_group(ctx, g.get("Guruh ID"),
                    f"⚠️ *{esc(g.get('Mijoz nomi',''))}*, siz hali story uchun ma'lumot "
                    f"tashlamadingiz. Iltimos, tashlab bering. 🙏")
            await q.edit_message_text("✅ Mijoz guruhiga eslatma yuborildi.")

    elif act == "count":
        cnt, mid = int(parts[1]), parts[2]
        update_tracker(mid, "Story soni", str(cnt))
        update_tracker(mid, "Story holati", f"{cnt} ta olindi")
        g = next((x for x in get_groups()
                  if str(x.get("Mijoz ID", "")).strip() == str(mid)), None)
        target = get_target(g) if g else STORY_TARGET
        if cnt >= target:
            await q.edit_message_text(f"✅ {cnt} ta kontent olindi! Bugun story tayyor. 🎉")
        else:
            await q.edit_message_text(
                f"✅ {cnt} ta olindi. Bugun yana {target - cnt} marta eslatiladi.")

    elif act == "post":
        ans, mid = parts[1], parts[2]
        if ans == "yes":
            update_tracker(mid, "Post holati", "yuklandi")
            await q.edit_message_text("✅ Post yuklandi! 🎉")
        else:
            update_tracker(mid, "Post holati", "yuklanmadi")
            await q.edit_message_text("⚠️ Post hali yuklanmadi. Iltimos, yuklang!")

    elif act == "done":
        # /today dan kelgan "bajarildi" tugmasi
        tid = parts[1] if len(parts) > 1 else ""
        ok = _mark_task_done(tid)
        if ok:
            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text(f"✅ Vazifa {tid} bajarildi!")
        else:
            await q.message.reply_text(f"⚠️ {tid} topilmadi.")


def _mark_task_done(tid):
    try:
        book = get_book()
        ws = book.worksheet("VAZIFALAR")
        headers = [h.strip() for h in ws.row_values(1)]
        col = headers.index("Bajarildi") + 1 if "Bajarildi" in headers else 6
        for i, r in enumerate(ws.get_all_records(), start=2):
            if str(clean_keys(r).get("ID", "")).strip() == str(tid).strip():
                ws.update_cell(i, col, "✅ Ha")
                return True
    except Exception as e:
        logger.error(f"mark done xato: {e}")
    return False


# ═══════════════════════════════════════════════
#  BUYRUQLAR
# ═══════════════════════════════════════════════
async def cmd_start(update: Update, ctx):
    await update.message.reply_text(
        "🎬 *X-LINE BOT*\n\n"
        "*Buyruqlar:*\n"
        "📋 /today — bugungi 3 vazifa\n"
        "🎯 /tasks — barcha vazifalar\n"
        "🎬 /videos — jarayondagi videolar\n"
        "📅 /content — yaqin kontent\n"
        "🤝 /meetings — uchrashuvlar\n"
        "👥 /clients — mijozlar\n"
        "📊 /stats — statistika\n\n"
        "*Kuzatuv:*\n"
        "📊 /holat — bugungi story/post holati\n"
        "🔄 /setup — sahifalarni tayyorlash\n"
        "▶️ /test_story — story sinash\n\n"
        "_Bot mustaqil ishlaydi: story 9/14/19, post 17:00, vazifa har soat._",
        parse_mode="Markdown")


async def cmd_today(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    tasks = get_vazifalar(3)
    if not tasks:
        await m.edit_text("✅ Barcha vazifalar bajarilgan! 🎉")
        return
    text = f"☀️ *BUGUNGI 3 VAZIFA — {datetime.now(TZ):%d-%m-%Y}*\n\n"
    kb = []
    for t in tasks:
        text += f"{esc(t.get('Muhimligi',''))} *{esc(t.get('Vazifa',''))}*\n   👤 {esc(t.get('Javobgar',''))}  📅 {esc(t.get('Deadline',''))}\n\n"
        kb.append([InlineKeyboardButton(f"✅ {esc(t.get('Vazifa',''))[:25]}",
                                        callback_data=f"done::{t.get('ID','')}")])
    await m.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def cmd_tasks(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    tasks = get_vazifalar(20)
    if not tasks:
        await m.edit_text("✅ Bajarilmagan vazifa yo'q!")
        return
    text = f"📋 *BAJARILMAGAN ({len(tasks)} ta):*\n\n"
    for t in tasks:
        text += f"{esc(t.get('Muhimligi',''))} *{esc(t.get('Vazifa',''))}*\n   👤 {esc(t.get('Javobgar',''))}  📅 {esc(t.get('Deadline',''))}\n\n"
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_videos(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    vids = get_videos()
    if not vids:
        await m.edit_text("✅ Jarayondagi video yo'q!")
        return
    text = f"🎬 *VIDEOLAR ({len(vids)} ta):*\n\n"
    for v in vids:
        text += f"🎥 *{esc(v.get('ID',''))}* — {esc(v.get('Mavzu','') or '—')}\n   {esc(v.get('Holat',''))}  📅 {esc(v.get('Deadline',''))}\n\n"
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_content(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    cs = get_kontent()
    if not cs:
        await m.edit_text("❌ Yaqin 7 kunda kontent yo'q.")
        return
    text = f"📅 *KONTENT ({len(cs)} ta):*\n\n"
    for c in cs:
        text += f"{esc(c.get('Holat',''))} *{esc(c.get('Sana',''))} {esc(c.get('Vaqt',''))}*\n   🎬 {esc(c.get('Loyiha',''))} | {esc(c.get('Platforma',''))}\n   📝 {esc(c.get('Turi',''))} — {esc(c.get('Mavzu',''))}\n\n"
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_meetings(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    us = get_uchrashuvlar()
    if not us:
        await m.edit_text("✅ Kutilayotgan uchrashuv yo'q!")
        return
    text = f"🤝 *UCHRASHUVLAR ({len(us)} ta):*\n\n"
    for u in us:
        text += f"📌 *{esc(u.get('Sana',''))} {esc(u.get('Vaqt',''))}*\n   👤 {esc(u.get('Kim bilan',''))}\n   🎯 {esc(u.get('Maqsad',''))}\n\n"
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_clients(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    cs = get_mijozlar()
    if not cs:
        await m.edit_text("❌ Aktiv mijoz topilmadi.")
        return
    text = f"👥 *MIJOZLAR ({len(cs)} ta):*\n\n"
    for c in cs:
        masul = c.get("Mas'ul", "")
        yord = c.get("Yordamchi", "")
        text += f"👤 *{esc(c.get('Mijoz',''))}*\n   📱 {esc(c.get('Platforma',''))}\n   👨‍💼 {esc(masul)} / {esc(yord)}\n\n"
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_stats(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    text = ("📊 *STATISTIKA*\n\n"
            f"👥 Mijozlar: *{len(get_mijozlar())}*\n"
            f"📋 Vazifalar: *{len(get_vazifalar())}*\n"
            f"🎬 Videolar: *{len(get_videos())}*\n"
            f"📅 Kontent: *{len(get_kontent())}*\n"
            f"🤝 Uchrashuvlar: *{len(get_uchrashuvlar())}*\n")
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_setup(update: Update, ctx):
    await update.message.reply_text("⏳ Tayyorlanmoqda...")
    ensure_sheets()
    await update.message.reply_text(
        "✅ *Tayyor!*\n\n"
        "Bot mavjud *MIJOZ_BOT* sahifangizdan o'qiydi.\n"
        "Har mijoz uchun quyidagilar to'ldirilgan bo'lsin:\n\n"
        "• *Mijoz nomi* — mijoz ismi\n"
        "• *Guruh ID* — mijoz guruhi (manfiy son: -100...)\n"
        "• *Mas'ul ismi* — storymaker ismi\n"
        "• *Mas'ul TG ID* — storymaker Telegram ID\n"
        "• *Kunlik kontent* — kuniga nechta story (masalan 3)\n"
        "• *Holat* — bo'sh yoki ✅ (tugagan/pauza bo'lmasin)\n\n"
        "📊 *TRACKER* sahifasi avtomatik to'ladi.\n\n"
        "⚠️ Botni har mijoz guruhiga *admin* qilib qo'shing!",
        parse_mode="Markdown")


async def cmd_holat(update: Update, ctx):
    m = await update.message.reply_text("⏳...")
    rows = [r for r in read_sheet("TRACKER")
            if str(r.get("Sana", "")).strip() == today_str()]
    if not rows:
        await m.edit_text("📊 Bugun uchun ma'lumot yo'q. Guruhlar kiritilganmi? /setup")
        return
    text = f"📊 *BUGUNGI HOLAT — {today_str()}*\n\n"
    for r in rows:
        text += (f"👤 *{esc(r.get('Mijoz nomi',''))}*\n"
                 f"   📸 Story: {esc(r.get('Story soni','0'))}/3 ({esc(r.get('Story holati',''))})\n"
                 f"   📤 Post: {esc(r.get('Post holati',''))}\n\n")
    await m.edit_text(text, parse_mode="Markdown")


async def cmd_test_story(update: Update, ctx):
    await update.message.reply_text("▶️ Story so'rovi yuborilmoqda...")
    init_today_tracker()
    await story_notify_group(ctx)
    await update.message.reply_text("✅ Yuborildi! (guruhlar kiritilgan bo'lsa)")


# ═══════════════════════════════════════════════
#  SCHEDULER
# ═══════════════════════════════════════════════
def setup_jobs(app: Application):
    jq = app.job_queue
    if not jq:
        logger.error("❌ JobQueue yo'q!")
        return

    async def _init(ctx):
        init_today_tracker()

    jq.run_daily(_init, time=datetime.now(TZ).replace(
        hour=8, minute=55, second=0, microsecond=0).timetz(), name="init")

    for h in STORY_HOURS:
        jq.run_daily(story_notify_group, time=datetime.now(TZ).replace(
            hour=h, minute=0, second=0, microsecond=0).timetz(), name=f"story_{h}")

    jq.run_daily(post_ask, time=datetime.now(TZ).replace(
        hour=POST_HOUR, minute=0, second=0, microsecond=0).timetz(), name="post")

    jq.run_repeating(hourly_tasks, interval=3600, first=120, name="tasks")
    logger.info("✅ Jobs rejalashtirildi")


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════
def main():
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN yo'q!")
        return
    try:
        ensure_sheets()
    except Exception as e:
        logger.warning(f"ensure_sheets: {e}")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    cmds = [
        ("start", cmd_start), ("today", cmd_today), ("tasks", cmd_tasks),
        ("videos", cmd_videos), ("content", cmd_content), ("meetings", cmd_meetings),
        ("clients", cmd_clients), ("stats", cmd_stats), ("setup", cmd_setup),
        ("holat", cmd_holat), ("test_story", cmd_test_story),
    ]
    for name, fn in cmds:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(on_cb))

    setup_jobs(app)
    logger.info("🚀 X-LINE BOT ISHGA TUSHDI!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
