import asyncio
import io
import os
import re
import yt_dlp
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PIL import Image as PILImage

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8927416207:AAFA2t6g7Ka5SMKfBLeaeGfcW8v8StI08eg")
BOT_USERNAME = "sarvar_image_bot"

# ============================================================
# PDF funksiyalari
# ============================================================
def create_pdf_from_text(text, title="Hujjat"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=18, spaceAfter=20)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=12, leading=18)
    story = [Paragraph(title, title_style), Spacer(1, 0.5*cm)]
    for line in text.split('\n'):
        if line.strip():
            safe = line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
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
    doc = SimpleDocTemplate(buffer, pagesize=page_size,
                            rightMargin=0, leftMargin=0,
                            topMargin=0, bottomMargin=0)
    page_w, page_h = page_size
    caption_height = 1*cm if caption else 0
    ratio = min(page_w / img_w, (page_h - caption_height) / img_h)
    rl_image = RLImage(io.BytesIO(image_bytes), width=img_w*ratio, height=img_h*ratio)
    story = [rl_image]
    if caption:
        styles = getSampleStyleSheet()
        cap_style = ParagraphStyle('Cap', parent=styles['Normal'], fontSize=10)
        safe_cap = caption.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(safe_cap, cap_style))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def create_pdf_from_multiple_images(images_list, title=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0, leftMargin=0,
                            topMargin=0, bottomMargin=0)
    story = []
    if title:
        styles = getSampleStyleSheet()
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 0.5*cm))
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

# ============================================================
# URL aniqlash
# ============================================================
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
    if urls:
        return urls[0]
    return None

def is_video_url(text):
    url = extract_url(text)
    if url:
        return any(site in url.lower() for site in VIDEO_SITES)
    return any(site in text.lower() for site in VIDEO_SITES)

# ============================================================
# Video yuklovchi
# ============================================================
def download_media(url):
    output_path = "/tmp/media_%(id)s.%(ext)s"
    
    # Har xil platformalar uchun sozlamalar
    if 'youtube.com' in url or 'youtu.be' in url:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
            }
        }
    elif 'instagram.com' in url:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
    elif 'tiktok.com' in url or 'vm.tiktok.com' in url:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            }
        }
    elif 'pinterest.com' in url or 'pin.it' in url:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            }
        }
    else:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            }
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        title = info.get('title', 'media')
        ext = info.get('ext', 'mp4')

    with open(filename, 'rb') as f:
        media_bytes = f.read()
    os.remove(filename)

    image_exts = ['jpg', 'jpeg', 'png', 'webp', 'gif']
    media_type = 'image' if ext.lower() in image_exts else 'video'
    return media_type, title, media_bytes, ext

# ============================================================
# Inline tugmalar
# ============================================================
def get_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Guruhga qo'shish",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                "🤖 @" + BOT_USERNAME,
                url=f"https://t.me/{BOT_USERNAME}"
            )
        ]
    ])

# ============================================================
# Handlerlar
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "➕ Guruhga qo'shish",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
        )]
    ])
    await update.message.reply_text(
        "Salom! Media yuklovchi bot!\n\n"
        "🎬 Havola yuboring — video yuklanadi\n"
        "🖼 Rasm yuboring — fayl sifatida saqlanadi\n"
        "📝 Matn yuboring — PDF bo'ladi\n\n"
        "✅ Qo'llab-quvvatlanadi:\n"
        "• YouTube\n"
        "• Instagram\n"
        "• TikTok\n"
        "• Pinterest\n"
        "• Facebook\n"
        "• Twitter/X\n\n"
        "/album — Ko'p rasmli PDF",
        reply_markup=keyboard
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    url = extract_url(text)
    if not url:
        if is_video_url(text):
            url = text
    
    if url and is_video_url(url):
        msg = await update.message.reply_text("⏳ Yuklanmoqda... Kuting.")
        try:
            media_type, title, media_bytes, ext = download_media(url)
            size_mb = len(media_bytes) / (1024 * 1024)
            
            if size_mb > 50:
                await msg.edit_text(
                    f"❌ Video {size_mb:.1f}MB — Telegram 50MB dan katta "
                    f"fayllarni qabul qilmaydi."
                )
                return

            caption = f"🎬 {title[:150]}\n\n⬇️ @{BOT_USERNAME} orqali yuklandi"
            
            await msg.delete()
            
            if media_type == 'image':
                await update.message.reply_document(
                    document=io.BytesIO(media_bytes),
                    filename=f"rasm.{ext}",
                    caption=caption,
                    reply_markup=get_keyboard()
                )
            else:
                await update.message.reply_video(
                    video=io.BytesIO(media_bytes),
                    filename="video.mp4",
                    caption=caption,
                    reply_markup=get_keyboard()
                )
        except Exception as e:
            err = str(e)
            if 'private' in err.lower() or 'login' in err.lower():
                await msg.edit_text(
                    "❌ Bu post yopiq yoki login talab qiladi.\n"
                    "Faqat ochiq postlar yuklanadi."
                )
            elif 'Sign in' in err:
                await msg.edit_text(
                    "❌ YouTube bot ekanligimizni aniqladi.\n"
                    "Boshqa video sinab ko'ring."
                )
            else:
                await msg.edit_text(f"❌ Xatolik: {err[:200]}")
    else:
        await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
        try:
            pdf_bytes = create_pdf_from_text(
                text,
                title=f"{update.message.from_user.first_name}ning Hujjati"
            )
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="hujjat.pdf",
                caption="✅ PDF tayyor!"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('album_mode'):
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        context.user_data.setdefault('album_images', []).append(img_bytes)
        count = len(context.user_data['album_images'])
        await update.message.reply_text(f"🖼 {count} ta rasm. /done yozing.")
        return

    await update.message.reply_text("⏳ Rasm saqlanmoqda...")
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        await update.message.reply_document(
            document=io.BytesIO(img_bytes),
            filename="rasm.jpg",
            caption=f"🖼 Rasm saqlandi!\n\n⬇️ @{BOT_USERNAME} orqali saqlandi",
            reply_markup=get_keyboard()
        )
        context.user_data['last_image'] = img_bytes
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
        try:
            file = await doc.get_file()
            img_bytes = bytes(await file.download_as_bytearray())
            pdf_bytes = create_pdf_from_image(img_bytes)
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="rasm.pdf",
                caption="✅ PDF tayyor!"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")

async def album_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['album_mode'] = True
    context.user_data['album_images'] = []
    await update.message.reply_text("📸 Rasmlarni yuboring, /done yozing.")

async def album_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get('album_images', [])
    if not images:
        await update.message.reply_text("⚠️ Rasm topilmadi.")
        return
    await update.message.reply_text(f"⏳ {len(images)} ta rasmdan PDF...")
    try:
        pdf_bytes = create_pdf_from_multiple_images(
            images,
            title=f"{update.message.from_user.first_name}ning Albomi"
        )
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="album.pdf",
            caption=f"✅ {len(images)} ta rasmli PDF tayyor!"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")
    finally:
        context.user_data['album_mode'] = False
        context.user_data['album_images'] = []

# ============================================================
# Ishga tushirish
# ============================================================
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("album", album_start))
    app.add_handler(CommandHandler("done", album_done))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("Bot ishga tushdi!")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
