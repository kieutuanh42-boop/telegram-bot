import os
import asyncio
import random
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN chưa được cấu hình!")

ADMINS = ["DuRinn_LeTuanDiem", "TraMy_2011"]

BET_AMOUNTS = [1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]

players = {}
current_game = {"active": False, "bets": {"tai": {}, "xiu": {}}, "history": [], "round": 0}


def format_money(amount):
    return f"{amount:,}".replace(",", ".")


def get_player(user):
    if user.id not in players:
        players[user.id] = {
            "name": user.first_name,
            "username": user.username or "ẩn",
            "balance": 200_000,
            "win": 0,
        }
    return players[user.id]


def build_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🅣🅐🅘", callback_data="bet_tai"),
            InlineKeyboardButton("🅧🅘🅤", callback_data="bet_xiu"),
        ],
        [
            InlineKeyboardButton("1K", callback_data="bet_amount_1000"),
            InlineKeyboardButton("10K", callback_data="bet_amount_10000"),
            InlineKeyboardButton("100K", callback_data="bet_amount_100000"),
        ],
        [
            InlineKeyboardButton("1M", callback_data="bet_amount_1000000"),
            InlineKeyboardButton("10M", callback_data="bet_amount_10000000"),
            InlineKeyboardButton("100M", callback_data="bet_amount_100000000"),
        ],
        [
            InlineKeyboardButton("ALL IN", callback_data="bet_all"),
            InlineKeyboardButton("🔄 Reset", callback_data="reset_amount"),
        ],
        [InlineKeyboardButton("👤 Số dư", callback_data="check_balance")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_new_game(context, chat_id):
    current_game["round"] += 1
    current_game["bets"] = {"tai": {}, "xiu": {}}
    await context.bot.send_message(
        chat_id,
        f"🎮 <b>Phiên #{current_game['round']} bắt đầu!</b>\n⏳ 30s để cược...",
        reply_markup=build_keyboard(),
        parse_mode="HTML",
    )
    context.application.create_task(game_countdown(context, chat_id))


async def game_countdown(context, chat_id):
    for t in range(29, 0, -1):
        await asyncio.sleep(1)
        await context.bot.send_message(chat_id, f"⏳ Còn {t}s để cược...")
    await end_game(context, chat_id)


async def end_game(context, chat_id):
    await context.bot.send_message(chat_id, "🏁 Hết giờ! Đang quay xúc xắc...")

    # Nháy xúc xắc giả
    for _ in range(3):
        fake = [random.randint(1, 6) for _ in range(3)]
        dice_str = " ".join([f"🎲{d}" for d in fake])
        await context.bot.send_message(chat_id, f"Đang quay... {dice_str}")
        await asyncio.sleep(0.7)

    # Kết quả thật
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    current_game["history"].append(result)

    winners, losers = [], []
    for side in ("tai", "xiu"):
        for user_id, bet in current_game["bets"][side].items():
            player = players[user_id]
            if side == result:
                player["balance"] += bet * 2
                player["win"] += bet
                winners.append(f"✅ {player['name']} +{format_money(bet)}")
            else:
                losers.append(f"❌ {player['name']} -{format_money(bet)}")

    dice_str = " ".join([f"🎲{d}" for d in dice])
    text = f"""
🎲 <b>KẾT QUẢ Phiên #{current_game['round']}</b>
{dice_str} = <b>{total}</b> → {'🅣🅐🅘' if result == 'tai' else '🅧🅘🅤'}

🏆 <b>Người thắng:</b>
{chr(10).join(winners) if winners else '❌ Không có'}

💀 <b>Người thua:</b>
{chr(10).join(losers) if losers else '✔️ Không có'}

🔄 Ván mới sau 5s...
    """.strip()

    await context.bot.send_message(chat_id, text, parse_mode="HTML")
    await asyncio.sleep(5)
    await start_new_game(context, chat_id)


# --- Callback cược ---
async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    p = get_player(user)
    data = query.data

    if data == "check_balance":
        return await query.message.reply_text(
            f"👤 {p['name']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}"
        )
    if data == "reset_amount":
        context.user_data["bet_amount"] = 0
        return await query.answer("🔄 Đã reset tiền cược.", show_alert=True)
    if data.startswith("bet_amount_"):
        context.user_data["bet_amount"] = int(data.split("_")[-1])
        return await query.answer(
            f"💰 Chọn {format_money(context.user_data['bet_amount'])}",
            show_alert=True,
        )
    if data == "bet_all":
        context.user_data["bet_amount"] = p["balance"]
        return await query.answer(
            f"💰 ALL IN {format_money(p['balance'])}!", show_alert=True
        )

    if data in ("bet_tai", "bet_xiu"):
        amount = context.user_data.get("bet_amount", 0)
        if amount <= 0:
            return await query.answer("⚠️ Chọn số tiền trước!", show_alert=True)
        if p["balance"] < amount:
            return await query.answer("⚠️ Không đủ số dư!", show_alert=True)
        side = "tai" if data == "bet_tai" else "xiu"
        current_game["bets"][side][user.id] = (
            current_game["bets"][side].get(user.id, 0) + amount
        )
        p["balance"] -= amount
        return await query.message.reply_text(
            f"📌 {p['name']} cược {format_money(amount)} vào {'🅣🅐🅘' if side=='tai' else '🅧🅘🅤'}"
        )


# --- Lệnh ---
async def nhantienfree(update: Update, context):
    p = get_player(update.effective_user)
    if p["username"] in ADMINS:
        p["balance"] += 1_000_000_000
        await update.message.reply_text(
            f"💎 ADMIN nhận 1 tỷ! 💰 {format_money(p['balance'])}"
        )
    else:
        p["balance"] += 200_000
        await update.message.reply_text(
            f"💰 Nhận 200k! Số dư: {format_money(p['balance'])}"
        )


async def sodu(update: Update, context):
    p = get_player(update.effective_user)
    await update.message.reply_text(
        f"👤 {p['name']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}"
    )


async def top(update: Update, context):
    ranking = sorted(players.items(), key=lambda x: x[1]["balance"], reverse=True)
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n\n"
    for i, (_, data) in enumerate(ranking[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {data['name']} - 💰 {format_money(data['balance'])}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def ruttien(update: Update, context):
    await update.message.reply_text(
        "💸 Muốn rút tiền? Nhắn admin:\n@DuRinn_LeTuanDiem hoặc @TraMy_2011"
    )


async def ontaixiu(update: Update, context):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Chỉ admin bật được.")
    current_game["active"] = True
    await start_new_game(context, update.effective_chat.id)
    await update.message.reply_text("✅ Đã bật Tài Xỉu!")


async def offtaixiu(update: Update, context):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Chỉ admin tắt được.")
    current_game["active"] = False
    await update.message.reply_text("⛔ Đã tắt Tài Xỉu!")


# MAIN
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("nhantienfree", nhantienfree))
app.add_handler(CommandHandler("sodu", sodu))
app.add_handler(CommandHandler("top", top))
app.add_handler(CommandHandler("ruttien", ruttien))
app.add_handler(CommandHandler("ontaixiu", ontaixiu))
app.add_handler(CommandHandler("offtaixiu", offtaixiu))
app.add_handler(CallbackQueryHandler(bet_callback))

if __name__ == "__main__":
    logger.info("✅ Bot Tài Xỉu đã khởi động...")
    app.run_polling()
