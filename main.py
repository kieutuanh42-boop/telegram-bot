# main.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import chess

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load token
TOKEN = os.getenv("BOT_TOKEN")  # ensure BOT_TOKEN is set in Pella env

# In-memory games per chat
GAMES = {}  # chat_id -> chess.Board()

# Helpers
def board_to_text(board: chess.Board) -> str:
    """
    Return a unicode board plus info (turn, castling, legal moves count).
    """
    b = board.unicode(borders=True)
    turn = "Trắng" if board.turn == chess.WHITE else "Đen"
    info = f"\n\nLượt: {turn}\nĐã đi: {board.fullmove_number}\nTrạng thái: {'Hết cờ' if board.is_game_over() else 'Đang chơi'}"
    if board.is_check():
        info += "\n(Chiếu!)"
    if board.is_game_over():
        result = "Hòa" if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() else "Thắng"
        info += f"\nKết quả: {result}"
    return b + info

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Nhà phát triển: Tô Minh Điềm. vui lòng bấm /chess. để chơi"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Bắt đầu chơi ( /chess )", callback_data="start_chess")]])
    await update.message.reply_text(text, reply_markup=kb)

async def chess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    board = chess.Board()
    GAMES[chat_id] = board
    await update.message.reply_text("Ván cờ mới đã được tạo! Dùng lệnh /move để đi quân.\n\nVí dụ: /move e2e4  hoặc  /move Nf3\n\nCác lệnh: /board /move /resign /help")
    await update.message.reply_text(board_to_text(board))

async def move_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GAMES:
        await update.message.reply_text("Chưa có ván cờ. Bấm /chess để bắt đầu ván mới.")
        return

    board = GAMES[chat_id]
    if board.is_game_over():
        await update.message.reply_text("Ván này đã kết thúc. Dùng /chess để tạo ván mới.")
        return

    if not context.args:
        await update.message.reply_text("Cú pháp: /move <cú pháp đi>\nVí dụ: /move e2e4 hoặc /move Nf3")
        return

    move_text = context.args[0].strip()
    move = None

    # Try UCI first (e2e4, g1f3, e7e8q)
    try:
        move = chess.Move.from_uci(move_text)
        if move not in board.legal_moves:
            move = None
    except Exception:
        move = None

    # If UCI failed, try SAN (Nf3, O-O, etc.)
    if move is None:
        try:
            move = board.parse_san(move_text)
        except Exception:
            move = None

    if move is None:
        await update.message.reply_text("Nét đi không hợp lệ hoặc không phải cú pháp UCI/SAN. Thử lại.\nVí dụ hợp lệ: e2e4  hoặc  Nf3  hoặc  O-O")
        return

    board.push(move)
    # After move, show board and status
    await update.message.reply_text(f"Bạn đi: {move.uci()}")
    await update.message.reply_text(board_to_text(board))

    if board.is_game_over():
        outcome = "Hòa" if board.is_stalemate() else "Kết thúc"
        await update.message.reply_text(f"Ván đã kết thúc. Kết quả: {board.result()} ({outcome})\nDùng /chess để bắt đầu ván mới.")
        # Optionally delete game to force new start
        # del GAMES[chat_id]

async def board_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GAMES:
        await update.message.reply_text("Chưa có ván cờ. Bấm /chess để bắt đầu ván mới.")
        return
    board = GAMES[chat_id]
    await update.message.reply_text(board_to_text(board))

async def resign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in GAMES:
        await update.message.reply_text("Chưa có ván cờ để chịu thua.")
        return
    del GAMES[chat_id]
    await update.message.reply_text("Bạn đã chịu thua. Ván cờ đã bị xóa. Dùng /chess để bắt đầu ván mới.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Hướng dẫn chơi bot cờ vua:\n\n"
        "/chess - Tạo ván cờ mới\n"
        "/move <đi> - Đi một nước. Hỗ trợ UCI (e2e4) hoặc SAN (Nf3)\n"
        "/board - Hiển thị bàn cờ hiện tại\n"
        "/resign - Chịu thua, xóa ván\n"
        "/help - Hiện hướng dẫn\n\n"
        "Ví dụ: /move e2e4  hoặc  /move Nf3"
    )
    await update.message.reply_text(text)

# Main
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa được đặt. Vui lòng set biến môi trường BOT_TOKEN.")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chess", chess_cmd))
    app.add_handler(CommandHandler("move", move_cmd))
    app.add_handler(CommandHandler("board", board_cmd))
    app.add_handler(CommandHandler("resign", resign_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    logger.info("Bot cờ vua đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
