import io
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, BOT_USERNAME
import services

def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *AI Assistant Bot* muvaffaqiyatli ishga tushdi!\n\n"
        "✅ Imkoniyatlar:\n"
        "🎬 *Havola yuboring* — video yuklanadi\n"
        "🖼 *Rasm yuboring* — hujjat sifatida saqlash\n"
        "📄 `/pdf matn` — matndan PDF yaratish\n"
        "📸 `/album` — ko'p rasmli PDF yaratish\n\n"
        "Tizim toza va bo'laklangan rejimda ishlamoqda.",
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
        pdf_bytes = services.create_pdf_from_text(text)
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="hujjat.pdf",
            caption="✅ PDF tayyor!"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url = services.extract_url(text)

    if url and services.is_video_url(url):
        msg = await update.message.reply_text("⏳ Yuklanmoqda, kuting...")
        try:
            media_type, title, media_bytes, ext = await services.download_media(url)
            size_mb = len(media_bytes) / (1024 * 1024)

            if size_mb > 50:
                await msg.edit_text(f"❌ Fayl {size_mb:.1f}MB — juda katta!")
                return

            caption = f"🎬 {title[:100]}\n📦 {size_mb:.1f}MB\n\n⬇️ @{BOT_USERNAME}"
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
                    caption=caption
                )
        except Exception as e:
            await msg.edit_text(f"❌ Yuklab bo'lmadi: {str(e)[:300]}")
    else:
        await update.message.reply_text(
            "👆 Havola yuboring yoki:\n"
            "📄 /pdf — matndan PDF\n"
            "📸 /album — rasmlardan PDF"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = bytes(await file.download_as_bytearray())

    if context.user_data.get('album_mode'):
        context.user_data.setdefault('album_images', []).append(img_bytes)
        count = len(context.user_data['album_images'])
        await update.message.reply_text(f"🖼 {count} ta rasm yig'ildi. Tugatish uchun: /done")
        return

    msg = await update.message.reply_text("⏳ Saqlanmoqda...")
    try:
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(img_bytes),
            filename="rasm.jpg",
            caption=f"🖼 Rasm hujjat sifatida saqlandi!\n\n⬇️ @{BOT_USERNAME}"
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
            pdf_bytes = services.create_pdf_from_image(img_bytes, caption)
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
        "📸 *Album rejimi yoqildi!*\n\n"
        "Rasmlarni ketma-ket yuboring, tugatgach /done deb yozing.",
        parse_mode="Markdown"
    )

async def album_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get('album_images', [])
    if not images:
        await update.message.reply_text("⚠️ Rasm yuborilmadi!")
        return

    msg = await update.message.reply_text(f"⏳ {len(images)} ta rasmdan bitta PDF tayyorlanmoqda...")
    try:
        pdf_bytes = services.create_pdf_from_multiple_images(images)
        await msg.delete()
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename="album.pdf",
            caption=f"✅ {len(images)} ta rasmdan iborat PDF tayyor bo'ldi!"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {e}")
    finally:
        context.user_data['album_mode'] = False
        context.user_data['album_images'] = []

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pdf", handle_pdf))
    app.add_handler(CommandHandler("album", album_start))
    app.add_handler(CommandHandler("done", album_done))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("✅ Bot polling rejimida ishga tushmoqda...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
