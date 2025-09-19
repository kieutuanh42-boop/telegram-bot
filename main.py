# main.py
import os
import asyncio
import random
import logging
from typing import Dict

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ========== CẤU HÌNH ==========
TOKEN = os.getenv("BOT_TOKEN")  # hoặc đặt trực tiếp: TOKEN = "123:ABC..."
if not TOKEN:
    raise ValueError("BOT_TOKEN chưa được cấu hình. Đặt biến môi trường BOT_TOKEN.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMINS = ["DuRinn_LeTuanDiem", "TraMy_2011"]
BET_AMOUNTS = [1000, 3000, 10_000, 30_000, 50_000, 100_000, 1_000_000]

# ========== TRẠNG THÁI ==========
players: Dict[int, dict] = {}
current_game = {
    "active": False,
    "bets": {"tai": {}, "xiu": {}},
    "history": [],            # lưu kết quả vài ván gần nhất
    "message": None,          # message object hiện tại (countdown)
    "chat_id": None,
    "time_left": 0,           # thời gian còn lại (giây)
    "countdown_task": None,   # asyncio.Task của countdown (nếu cần hủy)
}

# ========== TIỆN ÍCH ==========
def format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")

def get_player(user) -> dict:
    if user.id not in players:
        players[user.id] = {
            "name": user.first_name or "Người chơi",
            "username": user.username or "",
            "balance": 200_000,
            "win": 0,   # tổng thắng tích lũy
        }
    return players[user.id]

def build_game_message(time_left: int):
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())
    tai_count = len(current_game["bets"]["tai"])
    xiu_count = len(current_game["bets"]["xiu"])
    history_str = "".join("⚪" if r == "tai" else "⚫" for r in current_game["history"][-10:])

    text = (
        f"🎲 <b>GAME TÀI XỈU</b> 🎲\n"
        f"<b>⏳ Còn {time_left}s để đặt cược...</b>\n\n"
        f"<b>🅣🅐🅘</b> 👥{tai_count} | 💰{format_money(tai_total)}\n"
        f"<b>🅧🅘🅤</b> 👥{xiu_count} | 💰{format_money(xiu_total)}\n\n"
        f"<b>Lịch sử:</b> {history_str or 'Chưa có'}"
    )

    keyboard = [
        [
            InlineKeyboardButton("🅣🅐🅘", callback_data="bet_tai"),
            InlineKeyboardButton("🅧🅘🅤", callback_data="bet_xiu"),
        ],
        [InlineKeyboardButton(format_money(x), callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[:4]],
        [InlineKeyboardButton(format_money(x), callback_data=f"bet_amount_{x}") for x in BET_AMOUNTS[4:]],
        [
            InlineKeyboardButton("ALL IN", callback_data="bet_all"),
            InlineKeyboardButton("🔄 Reset", callback_data="reset_amount"),
        ],
        [InlineKeyboardButton("👤 Số dư", callback_data="check_balance")],
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_top_winners_text(limit: int = 5) -> str:
    if not players:
        return "❌ Chưa có người chơi."
    sorted_p = sorted(players.items(), key=lambda x: x[1].get("win", 0), reverse=True)
    lines = []
    for i, (uid, info) in enumerate(sorted_p[:limit], start=1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} {info['name']} - 🏆 {format_money(info.get('win',0))}")
    return "\n".join(lines) if lines else "❌ Chưa có"

# ========== GAME LOGIC ==========
async def start_new_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    # Nếu đã active thì tạo phiên mới (không xóa phiên cũ)
    current_game["bets"] = {"tai": {}, "xiu": {}}
    current_game["chat_id"] = chat_id
    current_game["time_left"] = 30

    text, markup = build_game_message(current_game["time_left"])
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="HTML")
        current_game["message"] = msg
    except Exception as e:
        logger.exception("Gửi message phiên mới thất bại: %s", e)
        current_game["message"] = None
        return

    # nếu có task countdown đang chạy thì không tạo thêm (bảo vệ)
    if current_game.get("countdown_task") and not current_game["countdown_task"].done():
        return

    # tạo task đếm ngược
    async def countdown():
        try:
            for t in range(30, 0, -1):
                current_game["time_left"] = t
                if not current_game.get("message"):
                    break
                text, markup = build_game_message(t)
                try:
                    await context.bot.edit_message_text(
                        chat_id=current_game["chat_id"],
                        message_id=current_game["message"].message_id,
                        text=text,
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
                except Exception:
                    # có thể message bị xóa / quyền chỉnh sửa => bỏ qua
                    pass
                await asyncio.sleep(1)
        finally:
            # Kết thúc phiên -> xử lý kết quả
            await end_game(context, chat_id)

    current_game["countdown_task"] = asyncio.create_task(countdown())

async def end_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    # Tính tổng cược hiện tại
    tai_total = sum(current_game["bets"]["tai"].values())
    xiu_total = sum(current_game["bets"]["xiu"].values())

    # Quay xúc xắc (nháy giả 3 lần)
    # (gửi animation bằng edit message nếu có, nhưng an toàn là gửi kết quả sau)
    # Sinh kết quả thật
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if total >= 11 else "xiu"
    current_game["history"].append(result)

    winners = dict(current_game["bets"][result])  # dict copy
    losers = dict(current_game["bets"]["tai"] if result == "xiu" else current_game["bets"]["xiu"])

    winners_text_lines = []
    for uid, bet in winners.items():
        if uid not in players:
            # bảo vệ: nếu player mất (chưa đăng ký) thì tạo mặc định
            players[uid] = {"name": f"User{uid}", "username": "", "balance": 0, "win": 0}
        players[uid]["balance"] += bet * 2
        players[uid]["win"] += bet
        winners_text_lines.append(f"✅ <b>{players[uid]['name']}</b> thắng {format_money(bet)}")

    losers_text_lines = []
    for uid, bet in losers.items():
        if uid not in players:
            players[uid] = {"name": f"User{uid}", "username": "", "balance": 0, "win": 0}
        losers_text_lines.append(f"❌ <b>{players[uid]['name']}</b> thua {format_money(bet)}")

    dice_str = " ".join([f"🎲{d}" for d in dice])
    result_text = (
        f"🎲 <b>KẾT QUẢ</b>: {dice_str} = <b>{total}</b>\n"
        f"<b>KẾT QUẢ:</b> {'🅣🅐🅘' if result == 'tai' else '🅧🅘🅤'}\n\n"
        f"📊 <b>Tổng cược:</b>\n🅣🅐🅘: {format_money(tai_total)} | 🅧🅘🅤: {format_money(xiu_total)}\n\n"
        f"🏆 <b>Người thắng:</b>\n"
        f"{chr(10).join(winners_text_lines) if winners_text_lines else '❌ Không ai thắng'}\n\n"
        f"💀 <b>Người thua:</b>\n"
        f"{chr(10).join(losers_text_lines) if losers_text_lines else '❌ Không ai thua'}\n\n"
        f"📊 <b>TOP CAO THỦ:</b>\n{get_top_winners_text()}\n\n"
        f"🔄 Ván mới sẽ được mở tự động sau 5s..."
    )

    # Gửi message kết quả (không edit message countdown để tránh lỗi nếu không còn quyền)
    try:
        await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode="HTML")
    except Exception as e:
        logger.exception("Không gửi được message kết quả: %s", e)

    # reset message hiện tại (countdown) để tránh edit sau này
    current_game["message"] = None
    current_game["time_left"] = 0
    # hủy task countdown nếu vẫn chạy
    task = current_game.get("countdown_task")
    if task and not task.done():
        try:
            task.cancel()
        except Exception:
            pass
    current_game["countdown_task"] = None

    # đợi 5s rồi tự mở phiên mới nếu game vẫn active
    await asyncio.sleep(5)
    if current_game.get("active"):
        await start_new_game(context, chat_id)
    else:
        # nếu admin đã tắt game trong lúc chờ, giữ trạng thái inactive
        logger.info("Game inactive — không mở phiên mới.")

# ========== CALLBACK xử lý cược ==========
async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    p = get_player(user)
    data = query.data

    # Các hành động không phải đặt tai/xiu
    if data == "check_balance":
        return await query.message.reply_text(
            f"👤 {p['name']}\n🔗 @{p['username']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}"
        )
    if data == "reset_amount":
        context.user_data["bet_amount"] = 0
        return await query.answer("🔄 Đã reset tiền cược.", show_alert=True)
    if data.startswith("bet_amount_"):
        context.user_data["bet_amount"] = int(data.split("_")[-1])
        return await query.answer(f"💰 Chọn {format_money(context.user_data['bet_amount'])}", show_alert=True)
    if data == "bet_all":
        context.user_data["bet_amount"] = p["balance"]
        return await query.answer(f"💰 ALL IN {format_money(p['balance'])}!", show_alert=True)

    # Đặt cược tai/xiu
    if data in ("bet_tai", "bet_xiu"):
        amount = context.user_data.get("bet_amount", 0)
        if amount <= 0:
            return await query.answer("⚠️ Chọn số tiền trước!", show_alert=True)
        if p["balance"] < amount:
            return await query.answer("⚠️ Hết tiền! Dùng /nhantienfree.", show_alert=True)
        side = "tai" if data == "bet_tai" else "xiu"
        current_game["bets"][side][user.id] = current_game["bets"][side].get(user.id, 0) + amount
        p["balance"] -= amount

        # khi cược chỉ edit message countdown để cập nhật số người & tiền — dùng time_left lưu trong state
        time_left = current_game.get("time_left", 30)
        text, markup = build_game_message(time_left)
        try:
            if current_game.get("message"):
                await context.bot.edit_message_text(
                    chat_id=current_game["chat_id"],
                    message_id=current_game["message"].message_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode="HTML",
                )
        except Exception:
            # không quan trọng nếu edit thất bại (ví dụ bot không có quyền)
            pass

        # trả lời ngắn để tránh spam group (alert)
        return await query.answer(f"✅ Đã cược {format_money(amount)} vào {'TÀI' if side=='tai' else 'XỈU'}", show_alert=False)

# ========== COMMANDS ==========
async def nhantienfree(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)
    if update.effective_user.username in ADMINS:
        p["balance"] += 1_000_000_000
        await update.message.reply_text(f"💎 ADMIN nhận 1 tỷ! 💰 {format_money(p['balance'])}")
    else:
        p["balance"] += 200_000
        await update.message.reply_text(f"💰 Nhận 200k! 💰 {format_money(p['balance'])}")

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_user)
    await update.message.reply_text(
        f"👤 {p['name']}\n🔗 @{p['username']}\n💰 {format_money(p['balance'])}\n🏆 {format_money(p['win'])}"
    )

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 <b>TOP CAO THỦ</b>\n\n{get_top_winners_text()}", parse_mode="HTML")

async def ruttien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💸 Muốn rút tiền? Nhắn admin:\n@DuRinn_LeTuanDiem hoặc @TraMy_2011")

async def ontaixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Chỉ admin bật được.")
    if current_game.get("active"):
        return await update.message.reply_text("✅ Game đang bật rồi.")
    current_game["active"] = True
    await start_new_game(context, update.effective_chat.id)
    await update.message.reply_text("✅ Đã bật Tài Xỉu!")

async def offtaixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username not in ADMINS:
        return await update.message.reply_text("⛔ Chỉ admin tắt được.")
    current_game["active"] = False
    # hủy countdown nếu có
    task = current_game.get("countdown_task")
    if task and not task.done():
        try:
            task.cancel()
        except Exception:
            pass
    current_game["countdown_task"] = None
    await update.message.reply_text("⛔ Đã tắt Tài Xỉu!")

# ========== MAIN ==========
def main():
    app = Application.builder().token(TOKEN).build()

    # commands
    app.add_handler(CommandHandler("nhantienfree", nhantienfree))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("ruttien", ruttien))
    app.add_handler(CommandHandler("ontaixiu", ontaixiu))
    app.add_handler(CommandHandler("offtaixiu", offtaixiu))

    # callback (bets)
    app.add_handler(CallbackQueryHandler(bet_callback, pattern="^bet_"))

    logger.info("✅ Bot Tài Xỉu đã khởi động...")
    app.run_polling()

if __name__ == "__main__":
    main()
