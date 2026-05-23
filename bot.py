import asyncio
import io
import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PIL import Image as PILImage

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

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

VIDEO_SITES = [
    'youtube.com', 'youtu.be',
    'instagram.com',
    'tiktok.com', 'vm.tiktok.com',
    'pinterest.com', 'pin.it',
    'facebook.com', 'fb.watch',
    'twitter.com', 'x.com',
    'reddit.com', 'vimeo.com',
]

def is_video_url(text):
    return any(site in text.lower() for site in VIDEO_SITES)

def download_media(url):
    output_path = "/tmp/media_%(id)s.%(ext)s"
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Media yuklovchi bot!\n\n"
        "Rasm yuboring — fayl sifatida saqlanadi\n"
        "Matn yuboring — PDF bo'ladi\n"
        "Havola yuboring — video yuklanadi\n\n"
        "YouTube, Instagram, TikTok\n"
        "Pinterest, Facebook, Twitter\n\n"
        "/album — Ko'p rasmli PDF"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if is_video_url(text):
        msg = await update.message.reply_text("Yuklanmoqda... Kuting.")
        try:
            media_type, title, media_bytes, ext = download_media(text)
            size_mb = len(media_bytes) / (1024 * 1024)
            if size_mb > 50:
                await msg.edit_text(f"Fayl {size_mb:.1f}MB — 50MB dan katta!")
                return
            await msg.edit_text(f"Yuklandi ({size_mb:.1f}MB)! Yuborilyapti...")
            if media_type == 'image':
                await update.message.reply_document(
                    document=io.BytesIO(media_bytes),
                    filename=f"rasm.{ext}",
                    caption=f"{title[:100]}"
                )
            else:
                await update.message.reply_video(
                    video=io.BytesIO(media_bytes),
                    filename="video.mp4",
                    caption=f"{title[:100]}"
                )
        except Exception as e:
            err = str(e)[:200]
            if 'private' in err.lower():
                await msg.edit_text("Bu post yopiq (private).")
            else:
                await msg.edit_text(f"Xatolik: {err}")
    else:
        await update.message.reply_text("PDF tayyorlanmoqda...")
        try:
            pdf_bytes = create_pdf_from_text(text,
                        title=f"{update.message.from_user.first_name}ning Hujjati")
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="hujjat.pdf",
                caption="PDF tayyor!"
            )
        except Exception as e:
            await update.message.reply_text(f"Xatolik: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('album_mode'):
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        context.user_data.setdefault('album_images', []).append(img_bytes)
        count = len(context.user_data['album_images'])
        await update.message.reply_text(f"{count} ta rasm. /done yozing.")
        return
    await update.message.reply_text("Rasm saqlanmoqda...")
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        img_bytes = bytes(await file.download_as_bytearray())
        await update.message.reply_document(
            document=io.BytesIO(img_bytes),
            filename="rasm.jpg",
            caption="Rasm fayl sifatida saqlandi!"
        )
        context.user_data['last_image'] = img_bytes
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await update.message.reply_text("PDF tayyorlanmoqda...")
        try:
            file = await doc.get_file()
            img_bytes = bytes(await file.download_as_bytearray())
            pdf_bytes = create_pdf_from_image(img_bytes)
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename="rasm.pdf",
                caption="PDF tayyor!"
            )
        except Exception as e:
            await update.message.reply_text(f"Xatolik: {e}")

async def album_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['album_mode'] = True
    context.user_data['album_images'] = []
    await update.message.reply_text("Rasmlarni yuboring, /done yozing.")

async def album_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get('album_images', [])
    if not images:
        await update.message.reply_text("Rasm topilmadi.")
        return
    await update.message.reply_text(f"{len(images)} ta rasmdan PDF...")
    try:
        pdf_bytes = create_pdf_from_multiple_images(images,
                    title=f"{update.message.from_user.first_name}ning Albomi")
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="album.pdf",
            caption=f"{len(images)} ta rasmli PDF tayyor!"
        )
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")
    finally:
        context.user_data['album_mode'] = False
        context.user_data['album_images'] = []

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("album", album_start))
    app.add_handler(CommandHandler("done", album_done))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("Bot ishga tushdi!")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
