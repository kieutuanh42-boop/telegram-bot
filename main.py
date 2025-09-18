# main.py
import os, io, logging, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import chess
import chess.svg
from PIL import Image
import cairosvg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
GAMES = {}  # chat_id -> {"board": chess.Board(), "mode": "pvp"/"ai", "selected": None}

# === Helpers ===
def render_board(board: chess.Board) -> InputFile:
    """Trả về ảnh bàn cờ dưới dạng InputFile để gửi Telegram."""
    svg_data = chess.svg.board(board=board)
    png_data = cairosvg.svg2png(bytestring=svg_data)
    image = Image.open(io.BytesIO(png_data))
    out = io.BytesIO()
    image.save(out, format="PNG")
    out.seek(0)
    return InputFile(out, filename="board.png")

def make_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Chơi với người", callback_data="mode_pvp")],
        [InlineKeyboardButton("🤖 Chơi với máy", callback_data="mode_ai")]
    ])

async def send_board(update_or_ctx, chat_id, game):
    board_img = render_board(game["board"])
    keyboard = [[InlineKeyboardButton("Chọn quân", callback_data="select")]]
    await update_or_ctx.bot.send_photo(chat_id, photo=board_img, caption="Bàn cờ hiện tại", reply_markup=InlineKeyboardMarkup(keyboard))

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Nhà phát triển: Tô Minh Điềm\nChọn chế độ chơi:", reply_markup=make_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 Hướng dẫn cơ bản:\n"
        "- Quân vua: đi 1 ô (ngang/dọc/chéo)\n"
        "- Quân hậu: đi ngang/dọc/chéo thoải mái\n"
        "- Quân xe: đi ngang/dọc\n"
        "- Quân tượng: đi chéo\n"
        "- Quân mã: đi chữ L\n"
        "- Tốt: đi lên 1 ô (nước đầu có thể đi 2), ăn chéo\n\n"
        "Bạn không cần gõ lệnh e2e4 — chỉ cần bấm vào quân và bấm ô muốn đi.\n"
        "Dùng /start để chọn chế độ, hoặc /help để xem hướng dẫn lại."
    )
    await update.message.reply_text(text)

# === Callbacks ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data.startswith("mode_"):
        mode = "ai" if query.data == "mode_ai" else "pvp"
        GAMES[chat_id] = {"board": chess.Board(), "mode": mode, "selected": None}
        await query.edit_message_text(f"Đã chọn chế độ: {'Chơi với máy 🤖' if mode=='ai' else 'Chơi 2 người 👥'}")
        await send_board(context, chat_id, GAMES[chat_id])

    # (Có thể mở rộng: chọn quân, chọn ô, v.v. - do đây là bản rút gọn)
    # Thực tế bạn có thể tạo inline keyboard 8x8 để người chơi chọn quân và ô.

async def move_random_ai(chat_id, context):
    game = GAMES.get(chat_id)
    if not game:
        return
    board = game["board"]
    if board.is_game_over():
        return
    move = random.choice(list(board.legal_moves))
    board.push(move)
    await send_board(context, chat_id, game)

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa đặt.")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot cờ vua đang chạy với nút bấm + AI.")
    app.run_polling()

if __name__ == "__main__":
    main()
