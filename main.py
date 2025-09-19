import os
import random
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

BALANCES = {}  # user_id -> số dư
CURRENT_GAME = {}  # chat_id -> {"bets": {"tai": [], "xiu": []}, "amount": 0, "msg_id": None, "open": False}


def fmt_money(n):
    if n >= 1_000_000:
        return f"{n // 1_000_000}m"
    if n >= 1_000:
        return f"{n // 1_000}k"
    return str(n)


async def nhan_tien_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    BALANCES[user_id] = BALANCES.get(user_id, 0) + 200_000
    await update.message.reply_text(f"💰 Bạn nhận 200k! Số dư: {fmt_money(BALANCES[user_id])}")


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


async def start_round(context: ContextTypes.DEFAULT_TYPE, chat_id):
    # tạo ván mới
    CURRENT_GAME[chat_id] = {"bets": {"tai": [], "xiu": []}, "amount": 0, "msg_id": None, "open": True}
    keyboard = [
        [InlineKeyboardButton("🎲 TÀI", callback_data="bet_tai"),
         InlineKeyboardButton("🎲 XỈU", callback_data="bet_xiu")],
        [InlineKeyboardButton("1k", callback_data="amt_1000"),
         InlineKeyboardButton("10k", callback_data="amt_10000"),
         InlineKeyboardButton("100k", callback_data="amt_100000")],
        [InlineKeyboardButton("1m", callback_data="amt_1000000"),
         InlineKeyboardButton("10m", callback_data="amt_10000000"),
         InlineKeyboardButton("All-in", callback_data="amt_all")]
    ]
    msg = await context.bot.send_message(
        chat_id,
        "🎮 Ván Tài Xỉu mới bắt đầu!\n⏳ Bạn có 30s để cược.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    CURRENT_GAME[chat_id]["msg_id"] = msg.message_id

    # đợi 30 giây rồi chốt kèo
    await asyncio.sleep(30)
    await close_round(context, chat_id)


async def update_board_message(context, chat_id, game):
    tai_list = "\n".join([f"🎲 {name} ({fmt_money(a)})" for name, _, a in game["bets"]["tai"]]) or "Chưa ai"
    xiu_list = "\n".join([f"🎲 {name} ({fmt_money(a)})" for name, _, a in game["bets"]["xiu"]]) or "Chưa ai"
    text = (f"🎮 ĐANG CƯỢC...\n"
            f"💰 Mức: {fmt_money(game['amount']) if game['amount'] else 'Chưa chọn'}\n\n"
            f"🔴 Tài:\n{tai_list}\n\n🔵 Xỉu:\n{xiu_list}")
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["msg_id"],
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 TÀI", callback_data="bet_tai"),
                 InlineKeyboardButton("🎲 XỈU", callback_data="bet_xiu")],
                [InlineKeyboardButton("1k", callback_data="amt_1000"),
                 InlineKeyboardButton("10k", callback_data="amt_10000"),
                 InlineKeyboardButton("100k", callback_data="amt_100000")],
                [InlineKeyboardButton("1m", callback_data="amt_1000000"),
                 InlineKeyboardButton("10m", callback_data="amt_10000000"),
                 InlineKeyboardButton("All-in", callback_data="amt_all")]
            ])
        )
    except:
        pass


async def close_round(context, chat_id):
    game = CURRENT_GAME.get(chat_id)
    if not game or not game["open"]:
        return
    game["open"] = False

    # tung 3 xúc xắc
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"

    # hiển thị xúc xắc bằng emoji 🎲
    dice_emoji = "".join(["🎲" for _ in dice])
    text = f"🎯 Kết quả: {dice_emoji} = {total} → {'TÀI' if result == 'tai' else 'XỈU'}\n"

    winners = game["bets"][result]
    if winners:
        text += "🏆 Người thắng:\n"
        for name, uid, amt in winners:
            win_amt = amt * 2
            BALANCES[uid] = BALANCES.get(uid, 0) + win_amt
            text += f" - {name}: +{fmt_money(win_amt)} (số dư: {fmt_money(BALANCES[uid])})\n"
    else:
        text += "😢 Không ai thắng ván này."

    await context.bot.send_message(chat_id, text)

    # mở ván mới tự động
    await asyncio.sleep(3)
    await start_round(context, chat_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        return

    user = query.from_user
    chat_id = query.message.chat_id
    game = CURRENT_GAME.get(chat_id)

    if not game or not game["open"]:
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


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🎲 Tài Xỉu Auto đã bật! Mỗi 30s sẽ mở ván mới.")
    await start_round(context, chat_id)


def main():
    if not TOKEN:
        logger.error("BOT_TOKEN chưa được đặt!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("nhantienfree", nhan_tien_free))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("taixiu", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot Tài Xỉu Auto đã khởi động...")
    app.run_polling()


if __name__ == "__main__":
    main()
