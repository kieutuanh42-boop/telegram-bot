import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

BALANCES = {}  # user_id -> số dư
CURRENT_GAME = {}  # chat_id -> {"bets": {"tai": [], "xiu": []}, "amount": 0, "msg_id": None, "open": False}


def fmt_money(n):
    """Định dạng tiền cho đẹp"""
    if n >= 1_000_000:
        return f"{n // 1_000_000}m"
    if n >= 1_000:
        return f"{n // 1_000}k"
    return str(n)


async def nhan_tien_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    BALANCES[user_id] = BALANCES.get(user_id, 0) + 200_000
    await update.message.reply_text(f"💰 Bạn đã nhận 200k! Số dư: {fmt_money(BALANCES[user_id])}")


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BALANCES:
        await update.message.reply_text("📉 Chưa ai có tiền để xếp hạng.")
        return
    ranking = sorted(BALANCES.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 TOP GIÀU NHẤT:\n"
    for i, (uid, money) in enumerate(ranking[:10], start=1):
        try:
            user = await context.bot.get_chat(uid)
            name = user.first_name
        except:
            name = f"User {uid}"
        text += f"{i}. {name}: {fmt_money(money)}\n"
    await update.message.reply_text(text)


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    CURRENT_GAME[chat_id] = {"bets": {"tai": [], "xiu": []}, "amount": 0, "msg_id": None, "open": True}
    keyboard = [
        [InlineKeyboardButton("🎲 Tài", callback_data="bet_tai"),
         InlineKeyboardButton("🎲 Xỉu", callback_data="bet_xiu")],
        [InlineKeyboardButton("1k", callback_data="amt_1000"),
         InlineKeyboardButton("2k", callback_data="amt_2000"),
         InlineKeyboardButton("5k", callback_data="amt_5000")],
        [InlineKeyboardButton("10k", callback_data="amt_10000"),
         InlineKeyboardButton("50k", callback_data="amt_50000"),
         InlineKeyboardButton("100k", callback_data="amt_100000")],
        [InlineKeyboardButton("1m", callback_data="amt_1000000"),
         InlineKeyboardButton("10m", callback_data="amt_10000000"),
         InlineKeyboardButton("100m", callback_data="amt_100000000"),
         InlineKeyboardButton("All-in", callback_data="amt_all")],
        [InlineKeyboardButton("✅ Chốt kèo", callback_data="close_game")]
    ]
    msg = await update.message.reply_text(
        "🎰 Game Tài Xỉu bắt đầu!\nChọn số tiền và bên để cược.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    CURRENT_GAME[chat_id]["msg_id"] = msg.message_id


async def update_board_message(context, chat_id, game):
    tai_names = ", ".join([f"{name}({fmt_money(a)})" for name, _, a in game["bets"]["tai"]]) or "Chưa ai"
    xiu_names = ", ".join([f"{name}({fmt_money(a)})" for name, _, a in game["bets"]["xiu"]]) or "Chưa ai"
    text = (f"🎲 Game Tài Xỉu đang mở!\n"
            f"💰 Cược: {fmt_money(game['amount']) if game['amount'] else 'Chưa chọn'}\n\n"
            f"🔥 Tài ({len(game['bets']['tai'])}): {tai_names}\n"
            f"❄️ Xỉu ({len(game['bets']['xiu'])}): {xiu_names}")
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["msg_id"],
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Tài", callback_data="bet_tai"),
                 InlineKeyboardButton("🎲 Xỉu", callback_data="bet_xiu")],
                [InlineKeyboardButton("1k", callback_data="amt_1000"),
                 InlineKeyboardButton("2k", callback_data="amt_2000"),
                 InlineKeyboardButton("5k", callback_data="amt_5000")],
                [InlineKeyboardButton("10k", callback_data="amt_10000"),
                 InlineKeyboardButton("50k", callback_data="amt_50000"),
                 InlineKeyboardButton("100k", callback_data="amt_100000")],
                [InlineKeyboardButton("1m", callback_data="amt_1000000"),
                 InlineKeyboardButton("10m", callback_data="amt_10000000"),
                 InlineKeyboardButton("100m", callback_data="amt_100000000"),
                 InlineKeyboardButton("All-in", callback_data="amt_all")],
                [InlineKeyboardButton("✅ Chốt kèo", callback_data="close_game")]
            ])
        )
    except:
        pass


async def close_game(chat_id, context):
    game = CURRENT_GAME.get(chat_id)
    if not game:
        return
    game["open"] = False

    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    winners = game["bets"][result]

    text = f"🎲 Kết quả: {' + '.join(map(str, dice))} = {total} → {'TÀI' if result == 'tai' else 'XỈU'}\n"
    if winners:
        text += "🏆 Người thắng:\n"
        for name, uid, amt in winners:
            win_amt = amt * 2
            BALANCES[uid] = BALANCES.get(uid, 0) + win_amt
            text += f" - {name}: +{fmt_money(win_amt)} (số dư: {fmt_money(BALANCES[uid])})\n"
    else:
        text += "😢 Không ai thắng ván này."

    await context.bot.send_message(chat_id, text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        return  # callback đã hết hạn, bỏ qua

    user = query.from_user
    chat_id = query.message.chat_id
    game = CURRENT_GAME.get(chat_id)

    if not game or not game["open"]:
        await query.edit_message_text("⚠️ Không có ván cược đang mở. Gõ /taixiu để mở ván mới.")
        return

    if query.data.startswith("amt_"):
        amount = query.data.split("_")[1]
        if amount == "all":
            game["amount"] = BALANCES.get(user.id, 0)
        else:
            game["amount"] = int(amount)
        await query.answer(f"💵 Chọn {fmt_money(game['amount'])}")
        return

    if query.data.startswith("bet_"):
        if game["amount"] <= 0:
            await query.answer("⚠️ Chưa chọn số tiền!", show_alert=True)
            return

        BALANCES[user.id] = BALANCES.get(user.id, 0)
        if BALANCES[user.id] < game["amount"]:
            await query.answer("💸 Không đủ tiền!", show_alert=True)
            return

        side = "tai" if query.data == "bet_tai" else "xiu"
        BALANCES[user.id] -= game["amount"]
        game["bets"][side].append((user.first_name, user.id, game["amount"]))
        await update_board_message(context, chat_id, game)

    if query.data == "close_game":
        await close_game(chat_id, context)


def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa được đặt!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("nhantienfree", nhan_tien_free))
    app.add_handler(CommandHandler("taixiu", start_game))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot Tài Xỉu (fix callback + /top) đã khởi động...")
    app.run_polling()


if __name__ == "__main__":
    main()
