import asyncio
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # 🔑 Đổi token của bạn tại đây
ADMINS = ["DuRinn_LeTuanDiem", "TraMy_2011"]

players = {}
current_game = {"status": False, "bets": {"tai": {}, "xiu": {}}, "history": [], "message": None}
BET_AMOUNTS = [1000, 3000, 10000, 30000, 50000, 100000, 1_000_000, 10_000_000, 100_000_000]

def format_money(amount):
    if amount >= 1_000_000_000:
        return f"{amount/1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"{amount/1_000_000:.1f}M"
    if amount >= 1000:
        return f"{amount//1000}K"
    return str(amount)

def get_player(user):
    if user.id not in players:
        players[user.id] = {
            "name": user.full_name,
            "username": user.username or "NoUsername",
            "balance": 200_000,
            "win": 0
        }
    return players[user.id]

def build_game_message():
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())
    tai_count = len(current_game["bets"]["tai"])
    xiu_count = len(current_game["bets"]["xiu"])
    history_str = "".join("⚪" if r == "tai" else "⚫" for r in current_game["history"][-10:])

    text = f"""
🎲 <b>GAME TÀI XỈU</b> 🎲
<b>⏳ Đang mở cược (30s)...</b>

<b>🅣🅐🅘</b> 👥{tai_count} | 💰{format_money(tai_total)}
<b>🅧🅘🅤</b> 👥{xiu_count} | 💰{format_money(xiu_total)}

<b>Lịch sử:</b> {history_str or 'Chưa có'}
    """.strip()

    keyboard = [
        [
            InlineKeyboardButton("🅣🅐🅘", callback_data="bet_tai"),
            InlineKeyboardButton("🅧🅘🅤", callback_data="bet_xiu"),
        ],
        [InlineKeyboardButton(f"{format_money(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[:5]],
        [InlineKeyboardButton(f"{format_money(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[5:]],
        [
            InlineKeyboardButton("ALL IN", callback_data="bet_all"),
            InlineKeyboardButton("🔄 Reset", callback_data="reset_amount")
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)

async def start_new_game(context: ContextTypes.DEFAULT_TYPE, chat_id):
    if not current_game["status"]:
        return
    current_game["bets"] = {"tai": {}, "xiu": {}}

    text, keyboard = build_game_message()
    if current_game["message"]:
        try:
            await context.bot.edit_message_text(chat_id=chat_id,
                                                message_id=current_game["message"].message_id,
                                                text=text,
                                                reply_markup=keyboard,
                                                parse_mode="HTML")
        except:
            current_game["message"] = await context.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
    else:
        current_game["message"] = await context.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

    await asyncio.sleep(30)
    await end_game(context, chat_id)

async def end_game(context, chat_id):
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())
    tai_count = len(current_game["bets"]["tai"])
    xiu_count = len(current_game["bets"]["xiu"])

    # Đóng cược và thông báo tổng
    text = f"""
🏁 <b>ĐÓNG CƯỢC!</b>

🅣🅐🅘 👥 {tai_count} | 💰 {format_money(tai_total)}
🅧🅘🅤 👥 {xiu_count} | 💰 {format_money(xiu_total)}

🎲 Đang quay...
    """.strip()
    await context.bot.edit_message_text(chat_id=chat_id,
                                        message_id=current_game["message"].message_id,
                                        text=text,
                                        parse_mode="HTML")
    await asyncio.sleep(1)

    # Hiệu ứng quay xúc xắc 3 lần
    for _ in range(3):
        fake_dice = [random.randint(1, 6) for _ in range(3)]
        dice_str = " ".join([f"🎲{d}" for d in fake_dice])
        text = f"""
🏁 <b>ĐÓNG CƯỢC!</b>

🅣🅐🅘 👥 {tai_count} | 💰 {format_money(tai_total)}
🅧🅘🅤 👥 {xiu_count} | 💰 {format_money(xiu_total)}

🎲 Đang quay: {dice_str}
        """
        await context.bot.edit_message_text(chat_id=chat_id,
                                            message_id=current_game["message"].message_id,
                                            text=text,
                                            parse_mode="HTML")
        await asyncio.sleep(0.7)

    # Ra kết quả thật
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    current_game["history"].append(result)

    winners = current_game["bets"][result]
    for user_id, bet in winners.items():
        players[user_id]["balance"] += bet * 2
        players[user_id]["win"] += bet

    dice_str = " ".join([f"🎲{d}" for d in dice])
    text = f"""
🎲 <b>KẾT QUẢ</b>: {dice_str} = <b>{total}</b>
<b>KẾT QUẢ:</b> {'🅣🅐🅘' if result == 'tai' else '🅧🅘🅤'}

📊 <b>Tổng cược:</b> 
🅣🅐🅘: {format_money(tai_total)} | 🅧🅘🅤: {format_money(xiu_total)}

🔄 Ván mới bắt đầu sau 5s...
    """.strip()
    await context.bot.edit_message_text(chat_id=chat_id,
                                        message_id=current_game["message"].message_id,
                                        text=text,
                                        parse_mode="HTML")
    await asyncio.sleep(5)
    await start_new_game(context, chat_id)

async def ontaixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Bạn không có quyền bật game!")
    current_game["status"] = True
    await update.message.reply_text("✅ Đã bật game Tài Xỉu!")
    await start_new_game(context, update.effective_chat.id)

async def offtaixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Bạn không có quyền tắt game!")
    current_game["status"] = False
    await update.message.reply_text("⛔ Đã tắt game Tài Xỉu!")

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    p = get_player(user)

    data = query.data
    if data == "reset_amount":
        context.user_data["bet_amount"] = 0
        return await query.message.reply_text("🔄 Bạn đã reset số tiền cược về 0.")

    if data.startswith("bet_amount_"):
        amount = int(data.replace("bet_amount_", ""))
        context.user_data["bet_amount"] = amount
        return await query.message.reply_text(f"💰 Bạn đã chọn mức cược: {format_money(amount)}")
    elif data == "bet_all":
        context.user_data["bet_amount"] = p["balance"]
        return await query.message.reply_text(f"💰 Bạn đã chọn ALL IN ({format_money(p['balance'])})")
    elif data.startswith("bet_"):
        side = data.split("_")[1]
        amount = context.user_data.get("bet_amount", 0)
        if amount <= 0:
            return await query.message.reply_text("⚠️ Vui lòng chọn số tiền trước!")
        if p["balance"] < amount:
            return await query.message.reply_text("💸 Bạn không đủ tiền! Gõ /nhantienfree để nhận 200k.")
        p["balance"] -= amount
        current_game["bets"][side][user.id] = current_game["bets"][side].get(user.id, 0) + amount
        text, keyboard = build_game_message()
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

async def sodu(update: Update, context):
    p = get_player(update.effective_user)
    await update.message.reply_text(f"""
👤 Tên: {p['name']}
🔗 Username: @{p['username']}
💰 Số dư: {format_money(p['balance'])}
🏆 Tổng thắng: {format_money(p['win'])}
""".strip())

async def nhantienfree(update: Update, context):
    p = get_player(update.effective_user)
    if p["username"] in ADMINS:
        p["balance"] += 1_000_000_000
        await update.message.reply_text(f"💎 ADMIN nhận 1 tỷ! Số dư hiện tại: {format_money(p['balance'])}")
    else:
        p["balance"] += 200_000
        await update.message.reply_text(f"💰 Bạn đã nhận 200k! Số dư hiện tại: {format_money(p['balance'])}")

async def top(update: Update, context):
    if not players:
        return await update.message.reply_text("📊 Chưa có người chơi nào!")
    sorted_players = sorted(players.values(), key=lambda x: x["win"], reverse=True)
    msg = "🏆 <b>BẢNG XẾP HẠNG</b>\n"
    for i, p in enumerate(sorted_players, start=1):
        icon = "🏆" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
        msg += f"{icon} <b>TOP {i}</b> - {p['name']} | 💰{format_money(p['balance'])} | 🏆 {format_money(p['win'])}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def ruttien(update: Update, context):
    await update.message.reply_text("💸 Để rút tiền vui lòng liên hệ admin:\n👑 @DuRinn_LeTuanDiem hoặc 👑 @TraMy_2011")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("ontaixiu", ontaixiu))
    app.add_handler(CommandHandler("offtaixiu", offtaixiu))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("nhantienfree", nhantienfree))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("ruttien", ruttien))
    app.add_handler(CallbackQueryHandler(bet_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
