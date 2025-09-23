import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv

# Load biến môi trường từ file .env (nếu chạy local)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# /start
def start(update: Update, context: CallbackContext):
    message = (
        "🤖 Xin chào! Tôi là Bot hỗ trợ tải ứng dụng do Nhà phát triển **Tô Minh Điềm** phát hành.\n\n"
        "✨ Chức năng chính:\n"
        "- Cung cấp link tải các ứng dụng mới nhất.\n"
        "- Giúp bạn dễ dàng truy cập và cài đặt phần mềm.\n"
        "- Hoàn toàn miễn phí và an toàn.\n\n"
        "👉 Để nhận danh sách ứng dụng, hãy gõ lệnh /app\n\n"
        "👤 Admin hỗ trợ: @DuRinn_LeTuanDiem"
    )
    update.message.reply_text(message, parse_mode="Markdown")

# /app
def app(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎵 Music Player", callback_data="music")],
        [InlineKeyboardButton("📝 Note", callback_data="note")],
        [InlineKeyboardButton("📡 Wifi-Transfer", callback_data="wifi")],
        [InlineKeyboardButton("⚡ PowerApp", callback_data="powerapp")],
        [InlineKeyboardButton("📂 Tổng hợp file", callback_data="all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("📥 Chọn ứng dụng bạn muốn tải:", reply_markup=reply_markup)

# Xử lý khi bấm nút
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    links = {
        "music": "https://drive.google.com/file/d/1aNYQkDTkPDmGSLUCexv2oi5U2z1kXmi2/view?usp=drive_link",
        "note": "https://drive.google.com/file/d/1QrjAqiUupkRKj95bXyQ1zi2GntrrpnHx/view?usp=drive_link",
        "wifi": "https://drive.google.com/file/d/1Zf0juk9mq7oQydLNOrwhg-DipyqYluZg/view?usp=drive_link",
        "powerapp": "https://drive.google.com/file/d/1WeHvFTvKUeOW387eF5aoh_7OoBUHm-ji/view?usp=drive_link",
        "all": "https://drive.google.com/drive/folders/1PBhampNPloB2fVj4AJCuFd4fzc3FouPu?usp=drive_link"
    }

    text_map = {
        "music": "🎵 Link tải Music Player:",
        "note": "📝 Link tải Note:",
        "wifi": "📡 Link tải Wifi-Transfer:",
        "powerapp": "⚡ Link tải PowerApp:",
        "all": "📂 Link tải toàn bộ ứng dụng:"
    }

    link = links.get(query.data, None)
    if link:
        query.edit_message_text(f"{text_map[query.data]} {link}")

def main():
    if not TOKEN:
        print("⚠️ Chưa tìm thấy BOT_TOKEN trong biến môi trường!")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("app", app))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
