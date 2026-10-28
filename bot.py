import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()

WELCOME = (
    "سلام! به پنل مدیریت دعوت خوش آمدی.\n\n"
    "این ربات می‌تواند لینک گروه‌ها را ثبت کند، لینک دعوت گروه مقصد را نگه دارد "
    "و برای افرادی که خودشان شروع به گفتگو با ربات کرده‌اند، دعوت‌نامه بفرستد.\n\n"
    "محدودیت مهم: ربات‌های تلگرام نمی‌توانند فهرست اعضای هر گروه دلخواه را استخراج کنند "
    "یا بدون دسترسی و اجازه، کاربران را به گروه دیگری اضافه کنند."
)

def is_admin(update: Update) -> bool:
    if not ADMIN_ID:
        return False
    user = update.effective_user
    return bool(user and str(user.id) == ADMIN_ID)

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ثبت گروه مبدأ", callback_data="source")],
        [InlineKeyboardButton("🎯 ثبت لینک دعوت گروه مقصد", callback_data="destination")],
        [InlineKeyboardButton("📋 نمایش تنظیمات", callback_data="status")],
        [InlineKeyboardButton("ℹ️ راهنما و محدودیت‌ها", callback_data="help")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("این ربات خصوصی است و فقط مدیر تعیین‌شده می‌تواند از پنل استفاده کند.")
        return
    await update.message.reply_text(WELCOME, reply_markup=main_menu())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(update):
        await q.edit_message_text("دسترسی مجاز نیست.")
        return

    if q.data == "source":
        context.user_data["awaiting"] = "source"
        await q.edit_message_text(
            "لینک گروه مبدأ را بفرست (عمومی یا لینک دعوت خصوصی).\n"
            "این نسخه لینک را ثبت می‌کند؛ صرف داشتن لینک به معنی دسترسی به فهرست اعضا نیست."
        )
    elif q.data == "destination":
        context.user_data["awaiting"] = "destination"
        await q.edit_message_text(
            "لینک دعوت گروه مقصد را بفرست.\n"
            "ابتدا ربات را در گروه مقصد با مجوزهای لازم اضافه کن و لینک دعوت را از تلگرام بساز."
        )
    elif q.data == "status":
        sources = context.application.bot_data.get("sources", [])
        dest = context.application.bot_data.get("destination", "ثبت نشده")
        source_text = "\n".join(f"• {s}" for s in sources) or "هیچ گروهی ثبت نشده"
        await q.edit_message_text(
            f"گروه‌های مبدأ:\n{source_text}\n\nگروه مقصد:\n{dest}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="home")]])
        )
    elif q.data == "help":
        await q.edit_message_text(
            "راهنما:\n"
            "۱) گروه مبدأ را ثبت کن.\n"
            "۲) لینک دعوت گروه مقصد را ثبت کن.\n"
            "۳) برای دعوت افراد، لینک دعوت را در محتوای مجاز منتشر کن یا آن را فقط برای کسانی بفرست که خودشان با ربات شروع کرده‌اند.\n\n"
            "این ربات پیام انبوه ناخواسته نمی‌فرستد، اعضای گروه‌های دیگر را استخراج نمی‌کند و عضویت اجباری انجام نمی‌دهد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="home")]])
        )
    elif q.data == "home":
        await q.edit_message_text("پنل مدیریت:", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    mode = context.user_data.get("awaiting")
    if not mode:
        await update.message.reply_text("از دکمه‌های منو استفاده کن.", reply_markup=main_menu())
        return
    value = update.message.text.strip()
    if not (value.startswith("https://t.me/") or value.startswith("http://t.me/") or value.startswith("t.me/")):
        await update.message.reply_text("لطفاً یک لینک تلگرام با قالب t.me/... بفرست.")
        return
    if mode == "source":
        sources = context.application.bot_data.setdefault("sources", [])
        if value not in sources:
            sources.append(value)
        await update.message.reply_text("لینک گروه مبدأ در حافظه این اجرای ربات ثبت شد.", reply_markup=main_menu())
    elif mode == "destination":
        context.application.bot_data["destination"] = value
        await update.message.reply_text("لینک دعوت گروه مقصد در حافظه این اجرای ربات ثبت شد.", reply_markup=main_menu())
    context.user_data.pop("awaiting", None)

class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass

def start_health_server():
    """Render Web Services need an open port; Background Workers don't."""
    port = os.getenv("PORT")
    if not port:
        return
    server = HTTPServer(("0.0.0.0", int(port)), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Health server listening on port %s", port)

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in your hosting provider's environment variables.")
    if not ADMIN_ID:
        log.warning("ADMIN_ID is not set: the panel will reject everyone.")
    start_health_server()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    log.info("Bot is starting.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
