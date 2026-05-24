import io
import os
import re
import tempfile
import asyncio
import httpx
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PIL import Image as PILImage

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8927416207:AAFA2t6g7Ka5SMKfBLeaeGfcW8v8StI08eg")
RAPID_API_KEY = os.environ.get("RAPID_API_KEY", "5e826a9b24msheafeaf09a41a683p12ab3fjsncd1c35b1f313")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "sarvar_image_bot")


def create_pdf_from_text(text, title="Hujjat"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, spaceAfter=20)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=12, leading=18)
    story = [Paragraph(title, title_style), Spacer(1, 0.5*cm)]
    for line in text.split('\n'):
        if line.strip():
            safe = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe, body_style))
        else:
            story.append(Spacer(1, 0.3*cm))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def create_pdf_from_image(image_bytes, caption=""):
    buffer = io.BytesIO()
    img = PILImage.open(io.BytesIO(image_bytes))
    img_w, img_h = img.size
    page_size = (A4[1], A4[0]) if img_w > img_h else A4
    doc = SimpleDocTemplate(buffer, pagesize=page_size, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=0)
    page_w, page_h = page_size
    caption_height = 1*cm if caption else 0
    ratio = min(page_w / img_w, (page_h - caption_height) / img_h)
    rl_image = RLImage(io.BytesIO(image_bytes), width=img_w*ratio, height=img_h*ratio)
    story = [rl_image]
    if caption:
        styles = getSampleStyleSheet()
        cap_style = ParagraphStyle('Cap', parent=styles['Normal'], fontSize=10)
        safe_cap = caption.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(safe_cap, cap_style))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def create_pdf_from_multiple_images(images_list):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=0)
    story = []
    page_w, page_h = A4
    for i, img_bytes in enumerate(images_list):
        img = PILImage.open(io.BytesIO(img_bytes))
        img_w, img_h = img.size
        ratio = min(page_w / img_w, page_h / img_h)
        rl_image = RLImage(io.BytesIO(img_bytes), width=img_w*ratio, height=img_h*ratio)
        story.append(rl_image)
        if i < len(images_list) - 1:
            story.append(PageBreak())
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


VIDEO_SITES = [
    'youtube.com', 'youtu.be',
    'instagram.com',
    'tiktok.com', 'vm.tiktok.com',
    'pinterest.com', 'pin.it',
    'facebook.com', 'fb.watch',
    'twitter.com', 'x.com',
]


def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None


def is_video_url(url):
    return any(site in url.lower() for site in VIDEO_SITES)


def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][filesize<50M]/best[ext=mp4]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'Video')
        ext = info.get('ext', 'mp4')
        filesize = info.get('filesize') or info.get('filesize_approx') or 0
        direct_url = info.get('url', '')
        return title, ext, filesize, direct_url


async def get_video_info_async(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_video_info, url)


def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(f"🤖 @{BOT_USERNAME}", url=f"https://t.me/{BOT_USERNAME}")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot imkoniyatlari:*\n\n"
        "🎬 Havola yuboring — video yuklanadi\n"
        "🖼 Rasm yuboring — saqlab olish\n"
        "📄 /pdf matn — PDF yaratish\n"
        "📸 /album — rasmlardan PDF\n\n"
        "• YouTube • Instagram • TikTok\n"
        "• Pinterest • Twitter • Facebook",
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 Masalan: `/pdf Salom dunyo`", parse_mode="Markdown")
        return
    text = ' '.join(context.args)
    msg = await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
    try:
        pdf_bytes = create_pdf_from_text(text)
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="hujjat.pdf",
            caption="✅ PDF tayyor!"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url = extract_url(text)
    if url and is_video_url(url):
        msg = await update.message.reply_text("⏳ Yuklanmoqda...")
        try:
            title, ext, filesize, direct_url = await get_video_info_async(url)
            size_mb = filesize / (1024 * 1024) if filesize else 0
            if filesize and size_mb > 50:
                await msg.edit_text(f"❌ Fayl {size_mb:.1f}MB — juda katta!")
                return
            caption = f"🎬 {title[:100]}\n📦 {f'{size_mb:.1f}MB' if size_mb else ''}\n\n⬇️ @{BOT_USERNAME}"
            await msg.delete()
            await update.message.reply_video(
                video=direct_url,
                caption=caption,
                supports_streaming=True
            )
        except Exception as e:
            await msg.edit_text(f"❌ Yuklab bo'lmadi: {str(e)[:300]}")
    else:
        msg = await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
        try:
            pdf_bytes = create_pdf_from_text(text)
            await msg.delete()
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="hujjat.pdf",
                caption="✅ PDF tayyor!"
            )
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('album_mode'):
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        context.user_data.setdefault('album_images', []).append(img_bytes)
        count = len(context.user_data['album_images'])
        await update.message.reply_text(f"🖼 {count} ta rasm. Tugash: /done")
        return
    msg = await update.message.reply_text("⏳ Saqlanmoqda...")
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(img_bytes),
            filename="rasm.jpg",
            caption=f"🖼 Rasm saqlandi!\n\n⬇️ @{BOT_USERNAME}"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        msg = await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
        try:
            file = await doc.get_file()
            img_bytes = bytes(await file.download_as_bytearray())
            caption = update.message.caption or ""
            pdf_bytes = create_pdf_from_image(img_bytes, caption)
            await msg.delete()
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="rasm.pdf",
                caption="✅ Rasm PDF ga aylantirildi!"
            )
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {e}")


async def album_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['album_mode'] = True
    context.user_data['album_images'] = []
    await update.message.reply_text(
        "📸 *Album rejimi yoqildi!*\n\nRasmlarni yuboring, tugatgach /done yozing.",
        parse_mode="Markdown"
    )


async def album_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get('album_images', [])
    if not images:
        await update.message.reply_text("⚠️ Rasm topilmadi!")
        return
    msg = await update.message.reply_text(f"⏳ {len(images)} ta rasmdan PDF...")
    try:
        pdf_bytes = create_pdf_from_multiple_images(images)
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="album.pdf",
            caption=f"✅ {len(images)} ta rasmli PDF tayyor!"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")
    finally:
        context.user_data['album_mode'] = False
        context.user_data['album_images'] = []


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pdf", handle_pdf))
    app.add_handler(CommandHandler("album", album_start))
    app.add_handler(CommandHandler("done", album_done))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
