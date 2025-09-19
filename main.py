import os
import asyncio
import random
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN chưa được cấu hình!")

ADMINS = ["DuRinn_LeTuanDiem", "TraMy_2011"]
BET_AMOUNTS = [1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]
HOUSE_FEE = 0.05  # 5% phí nhà cái

# ---------------- STATE ----------------
players = {}
current_game = {"active": False, "bets": {"tai": {}, "xiu": {}}, "message": None, "chat_id": None, "round": 0, "history": []}

# ---------------- HELPERS ----------------
def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def get_player(user):
    if user.id not in players:
        players[user.id] = {"name": user.first_name, "username": user.username, "balance": 200_000, "win": 0, "lose": 0}
    return players[user.id]

def build_game_message(time_left: int):
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())
    tai_count = len(current_game["bets"]["tai"])
    xiu_count = len(current_game["bets"]["xiu"])
    history_str = "".join("🅣" if r == "tai" else "🅧" for r in current_game["history"][-10:])

    text = f"""
🎮 <b>Phiên #{current_game['round']}</b>
⏳ Còn {time_left}s

🅣🅐🅘 👥 {tai_count} | 💰 {fmt(tai_total)}
🅧🅘🅤 👥 {xiu_count} | 💰 {fmt(xiu_total)}

📊 Lịch sử: {history_str or 'Chưa có'}
    """.strip()

    keyboard = [
        [InlineKeyboardButton("🅣🅐🅘", callback_data="bet_tai"),
         InlineKeyboardButton("🅧🅘🅤", callback_data="bet_xiu")],
        [InlineKeyboardButton(f"{fmt(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[:3]],
        [InlineKeyboardButton(f"{fmt(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[3:]],
        [InlineKeyboardButton("ALL IN", callback_data="bet_all"),
         InlineKeyboardButton("🔄 Reset", callback_data="reset_amount")],
        [InlineKeyboardButton("👤 Số dư", callback_data="check_balance")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# ---------------- GAME FLOW ----------------
async def start_new_game(context, chat_id):
    current_game["bets"] = {"tai": {}, "xiu": {}}
    current_game["chat_id"] = chat_id
    current_game["round"] += 1
    text, markup = build_game_message(30)
    current_game["message"] = await context.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    context.application.create_task(game_countdown(context))

async def game_countdown(context):
    for t in range(30, 0, -1):
        text, markup = build_game_message(t)
        try:
            await context.bot.edit_message_text(chat_id=current_game["chat_id"],
                                                message_id=current_game["message"].message_id,
                                                text=text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(1)
    await end_game(context)

async def end_game(context):
    chat_id = current_game["chat_id"]
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())

    # Xúc xắc
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    current_game["history"].append(result)

    winners = current_game["bets"][result]
    losers = current_game["bets"]["tai" if result == "xiu" else "xiu"]

    winners_text = []
    losers_text = []

    for user_id, bet in winners.items():
        win_amount = int(bet * 2 * (1 - HOUSE_FEE))  # thắng trừ phí
        players[user_id]["balance"] += win_amount
        players[user_id]["win"] += win_amount - bet
        winners_text.append(f"✅ <b>{players[user_id]['name']}</b> +{fmt(win_amount)} 🪙")

    for user_id, bet in losers.items():
        players[user_id]["lose"] += bet
        losers_text.append(f"❌ <b>{players[user_id]['name']}</b> -{fmt(bet)} 🪙")

    dice_str = " ".join([f"🎲{d}" for d in dice])
    result_text = f"""
🎲 <b>KẾT QUẢ PHIÊN #{current_game['round']}</b>
{dice_str} = <b>{total}</b> → {'🅣🅐🅘' if result == 'tai' else '🅧🅘🅤'}

🥇 <b>Người thắng:</b>
{chr(10).join(winners_text) if winners_text else '❌ Không ai thắng'}

💀 <b>Người thua:</b>
{chr(10).join(losers_text) if losers_text else 'Không có'}

🏦 Phí nhà cái: {int(HOUSE_FEE*100)}%
🔄 Ván mới sau 5s...
    """.strip()

    await context.bot.edit_message_text(chat_id=chat_id,
                                        message_id=current_game["message"].message_id,
                                        text=result_text, parse_mode="HTML")
    await asyncio.sleep(5)
    await start_new_game(context, chat_id)

# ---------------- CALLBACKS ----------------
async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    p = get_player(user)
    data = query.data

    if data == "check_balance":
        return await query.message.reply_text(
            f"👤 {p['name']} (@{p['username']})\n💰 {fmt(p['balance'])}\n🏆 Thắng: {fmt(p['win'])} | 💀 Thua: {fmt(p['lose'])}"
        )
    if data == "reset_amount":
        context.user_data["bet_amount"] = 0
        return await query.answer("🔄 Đã reset tiền cược.", show_alert=True)
    if data.startswith("bet_amount_"):
        context.user_data["bet_amount"] = int(data.split("_")[-1])
        return await query.answer(f"💰 Chọn {fmt(context.user_data['bet_amount'])}", show_alert=True)
    if data == "bet_all":
        context.user_data["bet_amount"] = p["balance"]
        return await query.answer(f"💰 ALL IN {fmt(p['balance'])}!", show_alert=True)

    if data in ("bet_tai", "bet_xiu"):
        amount = context.user_data.get("bet_amount", 0)
        if amount <= 0:
            return await query.answer("⚠️ Chọn số tiền trước!", show_alert=True)
        if p["balance"] < amount:
            return await query.answer("⚠️ Không đủ tiền!", show_alert=True)
        side = "tai" if data == "bet_tai" else "xiu"
        current_game["bets"][side][user.id] = current_game["bets"][side].get(user.id, 0) + amount
        p["balance"] -= amount

# ---------------- COMMANDS ----------------
async def nhantienfree(update: Update, context):
    p = get_player(update.effective_user)
    if p["username"] in ADMINS:
        p["balance"] += 1_000_000_000
        await update.message.reply_text(f"💎 ADMIN nhận 1 tỷ! 💰 {fmt(p['balance'])}")
    else:
        p["balance"] += 200_000
        await update.message.reply_text(f"💰 Nhận 200k! 💰 {fmt(p['balance'])}")

async def sodu(update: Update, context):
    p = get_player(update.effective_user)
    await update.message.reply_text(
        f"👤 {p['name']} (@{p['username']})\n💰 {fmt(p['balance'])}\n🏆 Thắng: {fmt(p['win'])} | 💀 Thua: {fmt(p['lose'])}"
    )

async def top(update: Update, context):
    ranking = sorted(players.items(), key=lambda x: x[1]["balance"], reverse=True)
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n\n"
    for i, (_, data) in enumerate(ranking[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {data['name']} - 💰 {fmt(data['balance'])} | 🏆 {fmt(data['win'])} | 💀 {fmt(data['lose'])}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def ruttien(update: Update, context):
    await update.message.reply_text("💸 Muốn rút tiền? Nhắn admin:\n@DuRinn_LeTuanDiem hoặc @TraMy_2011")

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

# ---------------- MAIN ----------------
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
