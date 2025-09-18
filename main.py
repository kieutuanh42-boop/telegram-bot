import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import chess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
GAMES = {}  # chat_id -> {"board": ..., "mode": ..., "selected": ..., "msg_id": ...}

UNICODE_PIECES = {
    "P": "♙", "p": "♟",
    "R": "♖", "r": "♜",
    "N": "♘", "n": "♞",
    "B": "♗", "b": "♝",
    "Q": "♕", "q": "♛",
    "K": "♔", "k": "♚",
}


def make_board_keyboard(board: chess.Board, selected=None):
    keyboard = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            square = rank * 8 + file
            piece = board.piece_at(square)
            symbol = UNICODE_PIECES.get(piece.symbol(), " ") if piece else "·"
            text = f"[{symbol}]" if selected == square else symbol
            row.append(InlineKeyboardButton(text, callback_data=f"square_{square}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


async def update_board_message(context, chat_id, game):
    """Cập nhật lại tin nhắn bàn cờ thay vì gửi tin mới"""
    board = game["board"]
    turn = "Trắng" if board.turn == chess.WHITE else "Đen"
    caption = f"Lượt: {turn}"
    if board.is_check():
        caption += " ⚠️ Chiếu!"
    if board.is_game_over():
        caption += " ✅ Kết thúc ván!"
    markup = make_board_keyboard(board, game["selected"])
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["msg_id"],
            text=caption,
            reply_markup=markup
        )
    except:
        # Nếu message bị xóa, gửi lại mới
        msg = await context.bot.send_message(chat_id, caption, reply_markup=markup)
        game["msg_id"] = msg.message_id


async def ai_move(chat_id, context):
    game = GAMES.get(chat_id)
    if not game:
        return
    board = game["board"]
    if board.is_game_over():
        return
    move = random.choice(list(board.legal_moves))
    board.push(move)
    await update_board_message(context, chat_id, game)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Nhà phát triển: Tô Minh Điềm\nChọn chế độ chơi:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Chơi 2 người", callback_data="mode_pvp")],
            [InlineKeyboardButton("🤖 Chơi với máy", callback_data="mode_ai")]
        ])
    )


async def chess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = {"board": chess.Board(), "mode": "pvp", "selected": None, "msg_id": None}
    GAMES[chat_id] = game
    msg = await update.message.reply_text("Ván mới bắt đầu!", reply_markup=make_board_keyboard(game["board"]))
    game["msg_id"] = msg.message_id
    await update_board_message(context, chat_id, game)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 Hướng dẫn cơ bản:\n\n"
        "♔ Vua: đi 1 ô (ngang, dọc, chéo)\n"
        "♕ Hậu: đi ngang/dọc/chéo bao xa cũng được\n"
        "♖ Xe: đi ngang/dọc\n"
        "♗ Tượng: đi chéo\n"
        "♘ Mã: đi chữ L\n"
        "♙ Tốt: đi thẳng, ăn chéo\n\n"
        "💡 Chỉ cần bấm ô quân ➜ bấm ô đích.\n"
        "Bot sẽ cập nhật bàn cờ ngay trong 1 tin nhắn duy nhất."
    )
    await update.message.reply_text(text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data.startswith("mode_"):
        mode = "ai" if query.data == "mode_ai" else "pvp"
        game = {"board": chess.Board(), "mode": mode, "selected": None, "msg_id": query.message.message_id}
        GAMES[chat_id] = game
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=query.message.message_id,
            text=f"Đã chọn chế độ: {'Chơi với máy 🤖' if mode=='ai' else 'Chơi 2 người 👥'}",
            reply_markup=None
        )
        await update_board_message(context, chat_id, game)
        return

    if query.data.startswith("square_"):
        square = int(query.data.split("_")[1])
        game = GAMES.get(chat_id)
        if not game:
            await query.edit_message_text("Chưa có ván. Gõ /chess để bắt đầu.")
            return

        board = game["board"]
        if game["selected"] is None:
            piece = board.piece_at(square)
            if piece and piece.color == board.turn:
                game["selected"] = square
            await update_board_message(context, chat_id, game)
        else:
            move = chess.Move(game["selected"], square)
            if move in board.legal_moves:
                board.push(move)
            game["selected"] = None
            await update_board_message(context, chat_id, game)
            if game["mode"] == "ai" and not board.is_game_over():
                await ai_move(chat_id, context)


def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa được đặt.")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chess", chess_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot cờ vua nút bấm (1 tin nhắn) đang chạy...")
    app.run_polling()


if __name__ == "__main__":
    main()
