import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from config import BOT_TOKEN, VIDEO_SITES
from services import create_pdf_from_images, download_media

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_store[uid] = {'images': [], 'mode': None}
    kb = [['🖼️ Rasm -> PDF', '📥 Video Yuklash']]
    await update.message.reply_text(
        f"Xush kelibsiz, {update.effective_user.first_name}!\n\n"
        "📷 Rasmlarni PDF ga aylantiraman\n"
        "🎬 Instagram, TikTok, YouTube videolarini yuklayman\n\n"
        "Quyidan tanlang:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if uid not in user_store:
        user_store[uid] = {'images': [], 'mode': None}

    if text == '🖼️ Rasm -> PDF':
        user_store[uid] = {'images': [], 'mode': 'pdf'}
        await update.message.reply_text(
            "Rasmlarni yuboring. Hammasi tayyor bo'lgach "
            "'📄 PDF yaratish' tugmasini bosing."
        )

    elif text == '📥 Video Yuklash':
        user_store[uid]['mode'] = 'video'
        await update.message.reply_text(
            "Video havolasini yuboring 👇"
        )

    elif text == '📄 PDF yaratish':
        images = user_store[uid].get('images', [])
        if not images:
            await update.message.reply_text("Hali rasm yubormagansiz!")
            return
        msg = await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
        out = f"pdf_{uid}.pdf"
        try:
            create_pdf_from_images(images, out)
            with open(out, 'rb') as f:
                await update.
