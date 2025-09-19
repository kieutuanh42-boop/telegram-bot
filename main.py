import os
import random
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

BALANCES = {}       # user_id -> số dư
NAMES = {}          # user_id -> tên (để /top hiển thị)
CURRENT_GAME = {}   # chat_id -> thông tin ván hiện tại
HISTORY = {}        # chat_id -> list kết quả (⚪=Tài, ⚫=Xỉu)
AUTO_TAIXIU = {}    # chat_id -> True/False (đang bật hay không)


def fmt_money(n):
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n//1_000_000}M"
    if n >= 1_000:
        return f"{n//1_000}K"
    return str(n)


async def nhan_tien_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    NAMES[user_id] = user.first_name
    BALANCES[user_id] = BALANCES.get(user_id, 0) + 200_000
    await update.message.reply_text(f"💰 Bạn nhận 200K! Số dư: {fmt_money(BALANCES[user_id])}")


def build_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 TÀI", callback_data="bet_tai"),
         InlineKeyboardButton("🎲 XỈU", callback_data="bet_xiu")],
        [InlineKeyboardButton("1K", callback_data="amt_1000"),
         InlineKeyboardButton("3K", callback_data="amt_3000"),
         InlineKeyboardButton("10K", callback_data="amt_10000"),
         InlineKeyboardButton("30K", callback_data="amt_30000")],
        [InlineKeyboardButton("50K", callback_data="amt_50000"),
         InlineKeyboardButton("100K", callback_data="amt_100000"),
         InlineKeyboardButton("1M", callback_data="amt_1000000")],
        [InlineKeyboardButton("10M", callback_data="amt_10000000"),
         InlineKeyboardButton("100M", callback_data="amt_100000000"),
         InlineKeyboardButton("ALL-IN", callback_data="amt_all")],
        [InlineKeyboardButton("❌ Hủy Cược", callback_data="cancel_bet")]
    ])


async def build_game_text(chat_id):
    game = CURRENT_GAME.get(chat_id)
    if not game:
        return "Chưa có ván nào."
    tai_total = sum(a for _, _, a in game["bets"]["tai"])
    xiu_total = sum(a for _, _, a in game["bets"]["xiu"])
    tai_count = len(game["bets"]["tai"])
    xiu_count = len(game["bets"]["xiu"])
    dice_display = " ".join([random.choice(["🎲1", "🎲2", "🎲3", "🎲4", "🎲5", "🎲6"]) for _ in range(3)]) if game["open"] else " ".join(game["dice"])
    history_text = "".join(HISTORY.get(chat_id, []))

    return (f"{history_text}\n\n"
            f"🔴 TÀI 💰{fmt_money(tai_total)} ({tai_count})"
            f"     {dice_display}     "
            f"🔵 XỈU 💰{fmt_money(xiu_total)} ({xiu_count})\n"
            f"⏳ Còn {game['countdown']}s\n"
            f"💰 Đặt: {fmt_money(game['amount']) if game['amount'] else 'Chưa chọn'}")


async def update_board(context, chat_id):
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=CURRENT_GAME[chat_id]["msg_id"],
            text=await build_game_text(chat_id),
            reply_markup=build_keyboard()
        )
    except:
        pass


async def start_round(context: ContextTypes.DEFAULT_TYPE, chat_id):
    if not AUTO_TAIXIU.get(chat_id, False):
        return
    CURRENT_GAME[chat_id] = {"bets": {"tai": [], "xiu": []},
                             "amount": 0,
                             "msg_id": None,
                             "open": True,
                             "countdown": 30,
                             "dice": ["🎲1", "🎲2", "🎲3"]}
    msg = await context.bot.send_message(chat_id, await build_game_text(chat_id),
                                         reply_markup=build_keyboard())
    CURRENT_GAME[chat_id]["msg_id"] = msg.message_id
    asyncio.create_task(countdown_timer(context, chat_id))


async def countdown_timer(context, chat_id):
    while chat_id in CURRENT_GAME and CURRENT_GAME[chat_id]["open"] and CURRENT_GAME[chat_id]["countdown"] > 0:
        await asyncio.sleep(3)
        CURRENT_GAME[chat_id]["countdown"] -= 3
        await update_board(context, chat_id)

    if chat_id in CURRENT_GAME and CURRENT_GAME[chat_id]["open"]:
        await close_round(context, chat_id)


async def close_round(context, chat_id):
    game = CURRENT_GAME.get(chat_id)
    if not game:
        return
    game["open"] = False

    dice_values = [random.randint(1, 6) for _ in range(3)]
    game["dice"] = [f"🎲{v}" for v in dice_values]
    await update_board(context, chat_id)

    total = sum(dice_values)
    result = "tai" if total >= 11 else "xiu"

    HISTORY.setdefault(chat_id, [])
    HISTORY[chat_id].append("⚪" if result == "tai" else "⚫")
    if len(HISTORY[chat_id]) > 10:
        HISTORY[chat_id].pop(0)

    winners = game["bets"][result]
    text = f"🎯 Kết quả: {' '.join(game['dice'])} = {total} → {'TÀI' if result == 'tai' else 'XỈU'}\n"
    if winners:
        text += "🏆 Người thắng:\n"
        for name, uid, amt in winners:
            BALANCES[uid] = BALANCES.get(uid, 0) + amt * 2
            text += f" - {name}: +{fmt_money(amt*2)}\n"
    else:
        text += "😢 Không ai thắng."

    await context.bot.send_message(chat_id, text)
    await asyncio.sleep(5)
    if AUTO_TAIXIU.get(chat_id, False):
        await start_round(context, chat_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        return
    user = query.from_user
    chat_id = query.message.chat_id
    NAMES[user.id] = user.first_name
    game = CURRENT_GAME.get(chat_id)
    if not game or not game["open"]:
        return

    if query.data.startswith("amt_"):
        if query.data.endswith("all"):
            game["amount"] = BALANCES.get(user.id, 0)
        else:
            game["amount"] = int(query.data.split("_")[1])
        await update_board(context, chat_id)
        return

    if query.data == "cancel_bet":
        for side in ["tai", "xiu"]:
            game["bets"][side] = [b for b in game["bets"][side] if b[1] != user.id]
        await update_board(context, chat_id)
        return

    if query.data.startswith("bet_"):
        if game["amount"] <= 0:
            await query.answer("⚠️ Chọn số tiền trước!", show_alert=True)
            return
        BALANCES[user.id] = BALANCES.get(user.id, 0)
        if BALANCES[user.id] < game["amount"]:
            await query.answer("💸 Không đủ tiền!", show_alert=True)
            return

        side = "tai" if query.data == "bet_tai" else "xiu"
        BALANCES[user.id] -= game["amount"]
        game["bets"][side].append((user.first_name, user.id, game["amount"]))
        await update_board(context, chat_id)


async def on_taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    AUTO_TAIXIU[chat_id] = True
    await update.message.reply_text("✅ Đã bật Tài Xỉu AUTO!")
    await start_round(context, chat_id)


async def off_taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    AUTO_TAIXIU[chat_id] = False
    CURRENT_GAME.pop(chat_id, None)
    await update.message.reply_text("🛑 Đã tắt Tài Xỉu AUTO!")


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BALANCES:
        await update.message.reply_text("📉 Chưa có ai chơi.")
        return
    top_players = sorted(BALANCES.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 **TOP NGƯỜI GIÀU** 🏆\n"
    for i, (uid, money) in enumerate(top_players, 1):
        text += f"{i}. {NAMES.get(uid, 'Ẩn danh')}: 💰{fmt_money(money)}\n"
    await update.message.reply_text(text)


def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa được đặt!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("nhantienfree", nhan_tien_free))
    app.add_handler(CommandHandler("ontaixiu", on_taixiu))
    app.add_handler(CommandHandler("offtaixiu", off_taixiu))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot Tài Xỉu đã khởi động...")
    app.run_polling()


if __name__ == "__main__":
    main()
