# -*- coding: utf-8 -*-
"""Qurilish Radar — O'zbekiston bo'ylab yangi qurilish/novostroykalarni topib,
Telegram'ga xabar beradi (quruvchisi bilan). Mijoz jalb qilish uchun.

Env (Railway):
  BOT_TOKEN   — Telegram bot tokeni (@BotFather)
  OWNER_ID    — xabarlar keladigan Telegram ID (default 7589459697)
  CHECK_HOURS — necha soatda bir tekshirsin (default 3)
"""
import os
import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import db
import manbalar

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("radar")

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.getenv("OWNER_ID", "7589459697"))
CHECK_HOURS = float(os.getenv("CHECK_HOURS", "3"))


def _qabul():
    """Xabar keladigan ID lar. Vergul bilan QABUL_IDS qo'shsa ham bo'ladi."""
    ids = {OWNER_ID}
    for x in (os.getenv("QABUL_IDS") or "").replace(" ", "").split(","):
        if x.strip().lstrip("-").isdigit():
            ids.add(int(x))
    return ids


def _xabar_matn(it):
    q = []
    q.append("🏗 *Yangi qurilish topildi*")
    q.append("")
    q.append("🏢 *%s*" % (it.get("nom") or "—"))
    if it.get("joy"):
        q.append("📍 %s" % it["joy"])
    if it.get("quruvchi"):
        q.append("👷 Quruvchi: *%s*  _(potensial mijoz)_" % it["quruvchi"])
    if it.get("holat") and it["holat"] != "yangilik":
        q.append("📅 Holat: %s" % it["holat"])
    if it.get("sana"):
        q.append("🗓 %s" % it["sana"])
    q.append("")
    q.append("💡 _Lesa / opalubka kerak bo'lishi mumkin — birinchi bo'lib bog'laning._")
    if it.get("url"):
        q.append("🔗 %s" % it["url"])
    q.append("· manba: %s" % (it.get("manba") or "—"))
    return "\n".join(q)


async def _yubor(app, it):
    matn = _xabar_matn(it)
    for uid in _qabul():
        try:
            await app.bot.send_message(uid, matn, parse_mode=ParseMode.MARKDOWN,
                                       disable_web_page_preview=False)
        except Exception as e:
            log.info("yuborishda xato %s: %s", uid, e)


async def _skan_qil(app, report_to=None):
    """Bir marta skan: yangi obyektlarni topib yuboradi. Qaytadi: (yangi_soni, hisobot)."""
    obyektlar, hisobot = await asyncio.to_thread(manbalar.hammasi)
    yangi = 0
    for it in obyektlar:
        if db.yangi_mi(it["kalit"]):
            if db.qosh(it):
                await _yubor(app, it)
                db.yuborildi_belgila(it["kalit"])
                yangi += 1
    log.info("skan: %s obyekt, %s yangi, manba: %s", len(obyektlar), yangi, hisobot)
    if report_to is not None:
        satur = ", ".join("%s: %s" % (k, v) for k, v in hisobot.items())
        await app.bot.send_message(
            report_to,
            "🔎 Tekshiruv tugadi.\nTopildi: %s ta obyekt\nYangi (yuborildi): %s ta\nManbalar: %s\nBazada jami: %s"
            % (len(obyektlar), yangi, satur, db.jami()))
    return yangi, hisobot


async def skan_loop(app):
    await asyncio.sleep(10)
    while True:
        try:
            await _skan_qil(app)
        except Exception:
            log.exception("skan_loop")
        await asyncio.sleep(max(600, int(CHECK_HOURS * 3600)))


# ---------------- Buyruqlar ----------------
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗 *Qurilish Radar*\n\n"
        "O'zbekiston bo'ylab yangi qurilish va novostroykalarni topib, quruvchisi bilan "
        "shu yerga yuboraman — siz birinchi bo'lib lesa/opalubka taklif qilasiz.\n\n"
        "Buyruqlar:\n"
        "/test — hoziroq tekshirib ko'rish\n"
        "/oxirgi — oxirgi topilganlar\n"
        "/id — sizning Telegram ID",
        parse_mode=ParseMode.MARKDOWN)


async def test_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in _qabul():
        return
    await update.message.reply_text("⏳ Tekshiryapman… (manbalarni skan qilyapman)")
    try:
        await _skan_qil(ctx.application, report_to=update.effective_chat.id)
    except Exception as e:
        log.exception("test_cmd")
        await update.message.reply_text("❌ Xato: %s" % e)


async def oxirgi_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in _qabul():
        return
    rows = db.oxirgilar(15)
    if not rows:
        await update.message.reply_text("Hozircha hech narsa topilmagan. /test bilan sinab ko'ring.")
        return
    q = ["🗂 *Oxirgi topilganlar:*", ""]
    for r in rows:
        q.append("🏢 %s%s%s" % (r["nom"],
                                " — %s" % r["joy"] if r["joy"] else "",
                                " · 👷 %s" % r["quruvchi"] if r["quruvchi"] else ""))
    await update.message.reply_text("\n".join(q)[:4000], parse_mode=ParseMode.MARKDOWN)


async def id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sizning ID: %s" % update.effective_user.id)


async def run():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(CommandHandler("oxirgi", oxirgi_cmd))
    app.add_handler(CommandHandler("id", id_cmd))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    asyncio.create_task(skan_loop(app))
    log.info("Qurilish Radar ishga tushdi. OWNER_ID=%s, har %s soatda", OWNER_ID, CHECK_HOURS)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run())
