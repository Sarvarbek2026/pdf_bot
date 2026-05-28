import os
import logging
import nest_asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, VIDEO_SITES
from services import create_pdf_from_images, download_video_via_api

nest_asyncio.apply()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Foydalanuvchilar ma'lumotlarini vaqtincha saqlash xotirasi
user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot ishga tushganda chiqadigan toza va chiroyli menyu"""
    user_id = update.effective_user.id
    user_data_store[user_id] = {'images': [], 'mode': None}
    
    keyboard = [['🖼️ Rasm -> PDF', '📥 Video Yuklash']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"Xush kelibsiz, {update.effective_user.first_name}!\n\n"
        "Men sizga rasmlarni sifatli PDF qilishda va ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube) video yuklashda yordam beraman.\n\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        user_data_store[user_id] = {'images': [], 'mode': None}

    if text == '🖼️ Rasm -> PDF':
        user_data_store[user_id]['mode'] = 'pdf'
        user_data_store[user_id]['images'] = []
        await update.message.reply_text("Menga PDF qilmoqchi bo'lgan rasmlaringizni ketma-ket yuboring. Rasmlar tugagach, **'📄 PDF yaratish'** tugmasini bosing.")
    
    elif text == '📥 Video Yuklash':
        user_data_store[user_id]['mode'] = 'video'
        await update.message.reply_text("Menga video havolasini (linkini) yuboring, men uni sizga yuklab beraman.")
        
    elif text == '📄 PDF yaratish':
        if user_data_store[user_id]['mode'] == 'pdf' and user_data_store[user_id]['images']:
            msg = await update.message.reply_text("PDF fayl tayyorlanmoqda, iltimos kuting...")
            output_pdf = f"fayl_{user_id}.pdf"
            
            # PDF yaratish funksiyasini chaqiramiz
            create_pdf_from_images(user_data_store[user_id]['images'], output_pdf)
            
            with open(output_pdf, 'rb') as f:
                await update.message.reply_document(document=f, filename="Smart_Document.pdf")
            
            await msg.delete()
            # Tozalash
            for img in user_data_store[user_id]['images']:
                if os.path.exists(img): os.remove(img)
            if os.path.exists(output_pdf): os.remove(output_pdf)
            user_data_store[user_id]['images'] = []
        else:
            await update.message.reply_text("Hali rasm yubormadingiz!")
            
    elif any(site in text for site in VIDEO_SITES):
        # Agar havola yuborilsa
        msg = await update.message.reply_text("Video yuklanmoqda, biroz kuting...")
        video_url = await download_video_via_api(text)
        
        if video_url:
            await update.message.reply_video(video=video_url)
            await msg.delete()
        else:
            await msg.edit_text("Videoni yuklab bo'lmadi. Havola xato yoki serverda muammo.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store or user_data_store[user_id]['mode'] != 'pdf':
        await update.message.reply_text("Iltimos, avval menyudan '🖼️ Rasm -> PDF' bo'limini tanlang.")
        return
        
    photo_file = await update.message.photo[-1].get_file()
    os.makedirs('downloads', exist_ok=True)
    file_path = f"downloads/{photo_file.file_id}.jpg"
    await photo_file.download_to_drive(file_path)
    
    user_data_store[user_id]['images'].append(file_path)
    
    keyboard = [['📄 PDF yaratish'], ['🖼️ Rasm -> PDF', '📥 Video Yuklash']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"{len(user_data_store[user_id]['images'])} ta rasm qabul qilindi. Yana yuborishingiz mumkin.",
        reply_markup=reply_markup
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("✅ Bot yangi tizimda, polling rejimida muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
