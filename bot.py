import asyncio
import io
import os
import re
import httpx
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PIL import Image as PILImage

# ============ KALITLAR ============
BOT_TOKEN = "8927416207:AAFA2t6g7Ka5SMKfBLeaeGfcW8v8StI08eg"
RAPID_API_KEY = "5e826a9b24msheafeaf09a41a683p12ab3fjsncd1c35b1f313"
GROQ_API_KEY = "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"
BOT_USERNAME = "sarvar_image_bot"

print(f"🤖 Bot: @{BOT_USERNAME}")
print(f"🔑 RapidAPI: {RAPID_API_KEY[:10]}...")
print(f"🎯 Groq: {GROQ_API_KEY[:10]}...")

# PDF funksiyalari
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
]

def extract_url(text):
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

def is_video_url(url):
    return any(site in url.lower() for site in VIDEO_SITES)

# YouTube yuklab olish (RapidAPI)
async def download_youtube_rapidapi(url):
    """RapidAPI orqali YouTube video yuklash"""
    if 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
    elif 'shorts' in url:
        video_id = url.split('/shorts/')[-1].split('?')[0]
    else:
        video_id = url.split('v=')[-1].split('&')[0]
    
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "youtube-video-download-info.p.rapidapi.com"
    }
    
    api_url = f"https://youtube-video-download-info.p.rapidapi.com/dl?id={video_id}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(api_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Formatni topish
            if 'formats' in data:
                for fmt in data['formats']:
                    if fmt.get('ext') == 'mp4' and fmt.get('url'):
                        video_url = fmt['url']
                        title = data.get('title', 'YouTube Video')
                        
                        # Videoni yuklab olish
                        video_response = await client.get(video_url)
                        return 'video', title, video_response.content, 'mp4'
        
        raise Exception("YouTube video topilmadi")

# yt-dlp bilan yuklash
async def download_with_ytdlp(url):
    """yt-dlp orqali yuklab olish"""
    def sync_download():
        ydl_opts = {
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_download)

async def download_media(url):
    """Asosiy yuklab olish funksiyasi"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return await download_youtube_rapidapi(url)
    else:
        return await download_with_ytdlp(url)

# Groq AI
async def ask_groq_async(question, history=[]):
    if not GROQ_API_KEY:
        return "⚠️ Groq API kaliti yo'q"
    
    messages = [
        {"role": "system", "content": "Siz foydali AI assistantsiz. O'zbek tilida javob bering."}
    ]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": messages,
                "max_tokens": 500
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Groq xatosi: {response.status_code}")
        
        data = response.json()
        return data['choices'][0]['message']['content']

def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(f"🤖 @{BOT_USERNAME}", url=f"https://t.me/{BOT_USERNAME}")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *AI Assistant Bot*\n\n"
        "✅ Quyidagi imkoniyatlar mavjud:\n\n"
        "💬 *Matn yozing* — AI javob beradi\n"
        "🎬 *Havola yuboring* — video/rasm yuklanadi\n"
        "🖼 *Rasm yuboring* — saqlab olish mumkin\n"
        "📄 `/pdf matn` — PDF yaratadi\n"
        "📸 `/album` — ko'p rasmli PDF\n\n"
        "*Qo'llab-quvvatlanadi:*\n"
        "• YouTube • Instagram • TikTok",
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 Matn yozing! Masalan: `/pdf Salom`", parse_mode="Markdown")
        return
    text = ' '.join(context.args)
    await update.message.reply_text("⏳ PDF tayyor...")
    try:
        pdf_bytes = create_pdf_from_text(text)
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="hujjat.pdf",
            caption="✅ PDF tayyor!"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url = extract_url(text)
    
    if url and is_video_url(url):
        msg = await update.message.reply_text("⏳ Yuklanmoqda...")
        try:
            media_type, title, media_bytes, ext = await download_media(url)
            size_mb = len(media_bytes) / (1024 * 1024)
            
            if size_mb > 50:
                await msg.edit_text(f"❌ Fayl {size_mb:.1f}MB - 50MB dan katta!")
                return
            
            caption = f"🎬 {title[:100]}\n\n⬇️ @{BOT_USERNAME}"
            await msg.delete()
            
            if media_type == 'image':
                await update.message.reply_document(
                    document=io.BytesIO(media_bytes),
                    filename=f"rasm.{ext}",
                    caption=caption
                )
            else:
                await update.message.reply_video(
                    video=io.BytesIO(media_bytes),
                    filename=f"video.{ext}",
                    caption=caption
                )
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {str(e)[:200]}")
    else:
        msg = await update.message.reply_text("🤗 O'ylayapti...")
        try:
            answer = await ask_groq_async(text)
            await msg.edit_text(f"🤖 {answer}")
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {str(e)[:200]}")

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
            caption=f"🖼 Rasm saqlandi!\n\n⬇️ @{BOT_USERNAME}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith('image/'):
        await update.message.reply_text("⏳ PDF tayyor...")
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
        pdf_bytes = create_pdf_from_multiple_images(images)
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="album.pdf",
            caption=f"✅ {len(images)} ta rasmli PDF!"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")
    finally:
        context.user_data['album_mode'] = False
        context.user_data['album_images'] = []

async def main():
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
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
