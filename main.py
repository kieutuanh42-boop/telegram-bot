import os
import asyncio
import random
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== TOKEN ==================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN chưa được cấu hình!")

# ================== CẤU HÌNH ==================
ADMINS = ["DuRinn_LeTuanDiem", "TraMy_2011"]
BET_AMOUNTS = [1000, 3000, 10_000, 30_000, 50_000, 100_000, 1_000_000, 10_000_000, 100_000_000]

players = {}
current_game = {"active": False, "bets": {"tai": {}, "xiu": {}}, "history": [], "message": None, "chat_id": None}

# ================== HÀM HỖ TRỢ ==================
def format_money(amount): 
    return f"{amount:,}".replace(",", ".")

def get_player(user):
    if user.id not in players:
        players[user.id] = {"name": user.first_name, "username": user.username, "balance": 200_000, "win": 0}
    return players[user.id]

def build_game_message(time_left: int):
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())
    tai_count = len(current_game["bets"]["tai"])
    xiu_count = len(current_game["bets"]["xiu"])
    history_str = "".join("⚪" if r == "tai" else "⚫" for r in current_game["history"][-10:])
    text = f"""
🎲 <b>GAME TÀI XỈU</b> 🎲
<b>⏳ Còn {time_left}s để đặt cược...</b>

<b>🅣🅐🅘</b> 👥{tai_count} | 💰{format_money(tai_total)}
<b>🅧🅘🅤</b> 👥{xiu_count} | 💰{format_money(xiu_total)}

<b>Lịch sử:</b> {history_str or 'Chưa có'}
    """.strip()
    keyboard = [
        [InlineKeyboardButton("🅣🅐🅘", callback_data="bet_tai"), InlineKeyboardButton("🅧🅘🅤", callback_data="bet_xiu")],
        [InlineKeyboardButton(f"{format_money(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[:5]],
        [InlineKeyboardButton(f"{format_money(x)}", callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[5:]],
        [InlineKeyboardButton("ALL IN", callback_data="bet_all"), InlineKeyboardButton("🔄 Reset", callback_data="reset_amount")],
        [InlineKeyboardButton("👤 Số dư", callback_data="check_balance")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# ================== GAME ==================
async def start_new_game(context, chat_id):
    current_game["bets"] = {"tai": {}, "xiu": {}}
    current_game["chat_id"] = chat_id
    text, markup = build_game_message(30)
    current_game["message"] = await context.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    context.application.create_task(game_countdown(context))

async def game_countdown(context):
    for t in range(30, 0, -1):
        text, markup = build_game_message(t)
        try:
            await context.bot.edit_message_text(chat_id=current_game["chat_id"], message_id=current_game["message"].message_id,
                                                text=text, reply_markup=markup, parse_mode="HTML")
        except:
            return
        await asyncio.sleep(1)
    await end_game(context)

async def end_game(context):
    chat_id = current_game["chat_id"]
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())

    # Quay xúc xắc
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    current_game["history"].append(result)

    winners = current_game["bets"][result]
    losers = current_game["bets"]["tai"] if result == "xiu" else current_game["bets"]["xiu"]

    winners_text = []
    for user_id, bet in winners.items():
        players[user_id]["balance"] += bet * 2
        players[user_id]["win"] += bet
        winners_text.append(f"✅ <b>{players[user_id]['name']}</b> thắng {format_money(bet)}")

    losers_text = []
    for user_id, bet in losers.items():
        losers_text.append(f"❌ <b>{players[user_id]['name']}</b> thua {format_money(bet)}")

    dice_str = " ".join([f"🎲{d}" for d in dice])
    result_text = f"""
🎲 <b>KẾT QUẢ</b>: {dice_str} = <b>{total}</b>
<b>KẾT QUẢ:</b> {'🅣🅐🅘' if result == 'tai' else '🅧🅘🅤'}

📊 <b>Tổng cược:</b>
🅣🅐🅘: {format_money(tai_total)} | 🅧🅘🅤: {format_money(xiu_total)}

🏆 <b>Người thắng:</b>
{chr(10).join(winners_text) if winners_text else '❌ Không ai thắng'}

💀 <b>Người thua:</b>
{chr(10).join(losers_text) if losers_text else '❌ Không ai thua'}

🔄 Ván mới sẽ bắt đầu sau ít giây...
    """.strip()

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=current_game["message"].message_id,
        text=result_text,
        parse_mode="HTML"
    )

    # Giữ kết quả 10s
    await asyncio.sleep(10)

    # Xoá message cũ
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=current_game["message"].message_id)
    except Exception as e:
        logger.warning(f"⚠️ Không xóa được message cũ: {e}")

    # Gửi phiên mới
    await start_new_game(context, chat_id)

# ================== CÁC HÀNH ĐỘNG ==================
async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    p = get_player(user)
    data = query.data

    if data == "check_balance":
        return await query.message.reply_text(f"👤 {p['name']}\n🔗 @{p['username']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}")
    if data == "reset_amount":
        context.user_data["bet_amount"] = 0
        return await query.answer("🔄 Đã reset tiền cược.", show_alert=True)
    if data.startswith("bet_amount_"):
        context.user_data["bet_amount"] = int(data.split("_")[-1])
        return await query.answer(f"💰 Chọn {format_money(context.user_data['bet_amount'])}", show_alert=True)
    if data == "bet_all":
        context.user_data["bet_amount"] = p["balance"]
        return await query.answer(f"💰 ALL IN {format_money(p['balance'])}!", show_alert=True)

    if data in ("bet_tai", "bet_xiu"):
        amount = context.user_data.get("bet_amount", 0)
        if amount <= 0:
            return await query.answer("⚠️ Chọn số tiền trước!", show_alert=True)
        if p["balance"] < amount:
            return await query.answer("⚠️ Hết tiền! Dùng /nhantienfree.", show_alert=True)
        side = "tai" if data == "bet_tai" else "xiu"
        current_game["bets"][side][user.id] = current_game["bets"][side].get(user.id, 0) + amount
        p["balance"] -= amount

# ================== LỆNH ==================
async def nhantienfree(update: Update, context):
    p = get_player(update.effective_user)
    if p["username"] in ADMINS:
        p["balance"] += 1_000_000_000
        await update.message.reply_text(f"💎 ADMIN nhận 1 tỷ! 💰 {format_money(p['balance'])}")
    else:
        p["balance"] += 200_000
        await update.message.reply_text(f"💰 Nhận 200k! 💰 {format_money(p['balance'])}")

async def sodu(update: Update, context):
    p = get_player(update.effective_user)
    await update.message.reply_text(f"👤 {p['name']}\n🔗 @{p['username']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}")

async def top(update: Update, context):
    ranking = sorted(players.items(), key=lambda x: x[1]["balance"], reverse=True)
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n\n"
    for i, (_, data) in enumerate(ranking[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {data['name']} - 💰 {format_money(data['balance'])} | 🏆 {format_money(data['win'])}\n"
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

# ================== MAIN ==================
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
