import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")

# Foydalanuvchi so'rovlarini saqlash
user_requests = {}

FORMATS = [
    ("🎬 1080p (Full HD)", "bestvideo[height<=1080]+bestaudio/best[height<=1080]", "mp4"),
    ("📺 720p (HD)", "bestvideo[height<=720]+bestaudio/best[height<=720]", "mp4"),
    ("📱 480p", "bestvideo[height<=480]+bestaudio/best[height<=480]", "mp4"),
    ("📱 360p", "bestvideo[height<=360]+bestaudio/best[height<=360]", "mp4"),
    ("🔹 240p", "bestvideo[height<=240]+bestaudio/best[height<=240]", "mp4"),
    ("🎵 MP3 Audio", "bestaudio/best", "mp3"),
]

SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "facebook.com", "fb.watch",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "vimeo.com",
    "dailymotion.com",
]


def is_supported_url(url: str) -> bool:
    return any(site in url.lower() for site in SUPPORTED_SITES)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Assalomu alaykum!*\n\n"
        "Men video yuklovchi botman 🎬\n\n"
        "📌 *Qo'llab-quvvatlanadigan saytlar:*\n"
        "• YouTube 🎥\n"
        "• Facebook 📘\n"
        "• Instagram 📸\n"
        "• TikTok 🎵\n"
        "• X.com (Twitter) 🐦\n"
        "• Vimeo & Dailymotion\n\n"
        "✅ Video yoki audio yuklab olish uchun shunchaki *havola yuboring!*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Foydalanish yo'riqnomasi:*\n\n"
        "1️⃣ Video havolasini yuboring\n"
        "2️⃣ Format tanlang (1080p, 720p, MP3...)\n"
        "3️⃣ Bot yuklab, sizga yuboradi\n\n"
        "⚠️ *Eslatma:* Telegram 50MB gacha fayl yuboradi.\n"
        "Katta fayllar uchun pastroq sifat tanlang."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    if not is_supported_url(url):
        await update.message.reply_text(
            "❌ Bu havola qo'llab-quvvatlanmaydi.\n\n"
            "YouTube, Facebook, Instagram, TikTok, X.com havolalarini yuboring."
        )
        return

    # URL ni saqlash
    user_requests[user_id] = url

    # Video ma'lumotini olish
    status_msg = await update.message.reply_text("🔍 Havola tekshirilmoqda...")

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')[:50]
            duration = info.get('duration', 0)
            mins = duration // 60
            secs = duration % 60

        # Format tugmalarini yaratish
        keyboard = []
        for label, fmt, ext in FORMATS:
            callback_data = f"dl_{FORMATS.index((label, fmt, ext))}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.edit_text(
            f"✅ *Video topildi!*\n\n"
            f"📌 *Sarlavha:* {title}\n"
            f"⏱ *Davomiyligi:* {mins}:{secs:02d}\n\n"
            f"📥 *Qaysi formatda yuklab olmoqchisiz?*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        await status_msg.edit_text(
            f"❌ Havola ochilmadi.\n\n"
            f"Sabab: {str(e)[:100]}\n\n"
            "Havolani tekshirib, qayta urinib ko'ring."
        )


async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        return

    if user_id not in user_requests:
        await query.edit_message_text("⚠️ Havola topilmadi. Qaytadan yuboring.")
        return

    fmt_index = int(query.data.replace("dl_", ""))
    label, fmt, ext = FORMATS[fmt_index]
    url = user_requests[user_id]

    await query.edit_message_text(f"⏳ *{label}* formatida yuklanmoqda...\n\nIltimos kuting ⌛", parse_mode="Markdown")

    output_path = f"/tmp/{user_id}_video.%(ext)s"

    try:
        if ext == "mp3":
            ydl_opts = {
                'format': fmt,
                'outtmpl': output_path,
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            ydl_opts = {
                'format': fmt,
                'outtmpl': output_path,
                'quiet': True,
                'merge_output_format': 'mp4',
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')[:40]

        # Yuklab olingan faylni topish
        import glob
        files = glob.glob(f"/tmp/{user_id}_video.*")
        if not files:
            raise FileNotFoundError("Fayl topilmadi")

        file_path = files[0]
        file_size = os.path.getsize(file_path)

        # Telegram 50MB chekovi
        if file_size > 50 * 1024 * 1024:
            os.remove(file_path)
            await query.edit_message_text(
                "⚠️ *Fayl juda katta!* (50MB dan oshadi)\n\n"
                "Pastroq sifat tanlang:\n"
                "• 480p, 360p yoki 240p",
                parse_mode="Markdown"
            )
            return

        await query.edit_message_text(f"📤 Telegramga yuborilmoqda...")

        with open(file_path, 'rb') as f:
            if ext == "mp3":
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    title=title,
                    caption=f"🎵 {title}"
                )
            else:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=f"🎬 {title}\n{label}",
                    supports_streaming=True
                )

        os.remove(file_path)
        await query.edit_message_text(f"✅ *Yuborildi!* {label}\n\n📌 {title}", parse_mode="Markdown")

        # So'rovni o'chirish
        del user_requests[user_id]

    except Exception as e:
        # Fayllarni tozalash
        import glob
        for f in glob.glob(f"/tmp/{user_id}_video.*"):
            try:
                os.remove(f)
            except:
                pass

        await query.edit_message_text(
            f"❌ Yuklashda xatolik:\n\n`{str(e)[:150]}`\n\n"
            "Boshqa format tanlang yoki keyinroq urinib ko'ring.",
            parse_mode="Markdown"
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_format_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
