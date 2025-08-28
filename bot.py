import os
import asyncio
from typing import Dict, Optional

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# --- OpenAI (GPT)
from openai import AsyncOpenAI

# --- xAI (Grok)
import httpx

# --- Google Gemini
import google.generativeai as genai


"""
HƯỚNG DẪN TRIỂN KHAI (tóm tắt):
1) Tạo bot và lấy TELEGRAM_BOT_TOKEN từ BotFather.
2) Thiết lập biến môi trường:
   - TELEGRAM_BOT_TOKEN
   - OPENAI_API_KEY
   - XAI_API_KEY
   - GEMINI_API_KEY
   (trên Heroku: Settings > Config Vars)
3) Deploy lên Heroku (hoặc nền tảng khác) và bật dyno 'worker'.
"""

# =========================
# Cấu hình & Khởi tạo SDKs
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model mặc định (có thể đổi bằng biến môi trường)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-2-latest")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN")

# OpenAI (GPT)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# xAI (Grok) dùng httpx
httpx_client = httpx.AsyncClient(timeout=60.0) if XAI_API_KEY else None

# Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL)
else:
    gemini_model = None

# Lưu chế độ chat theo chat_id: {'mode': 'gpt'|'grok'|'gemini'}
SESSION_MODE: Dict[int, str] = {}


# ============
# AI helpers
# ============
async def ask_gpt(prompt: str, user_id: int) -> str:
    if not openai_client:
        return "⚠️ Chưa cấu hình OPENAI_API_KEY."
    try:
        resp = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Bạn là một trợ lý thân thiện, trả lời ngắn gọn và hữu ích."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"❌ Lỗi GPT: {e}"


async def ask_grok(prompt: str, user_id: int) -> str:
    if not httpx_client:
        return "⚠️ Chưa cấu hình XAI_API_KEY."
    try:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": XAI_MODEL,
            "messages": [
                {"role": "system", "content": "Bạn là một trợ lý ngắn gọn, chính xác."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        r = await httpx_client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return (text or "").strip() or "⚠️ Grok không trả về nội dung."
    except Exception as e:
        return f"❌ Lỗi Grok: {e}"


async def ask_gemini(prompt: str, user_id: int) -> str:
    if not gemini_model:
        return "⚠️ Chưa cấu hình GEMINI_API_KEY."
    try:
        # Thư viện Gemini hiện đồng bộ -> chạy trong thread để không chặn loop
        def _run():
            resp = gemini_model.generate_content(prompt)
            return (resp.text or "").strip()
        text = await asyncio.to_thread(_run)
        return text or "⚠️ Gemini không trả về nội dung."
    except Exception as e:
        return f"❌ Lỗi Gemini: {e}"


# =================
# Telegram Handlers
# =================
WELCOME = (
    "👋 Chào bạn đến với bot Telegram của nhà phát triển **Tô Minh Điềm**.\n"
    "Bạn có thể trò chuyện với các AI sau. Gõ /help để xem lệnh.\n\n"
    "• /gpt – Chat với GPT (OpenAI)\n"
    "• /grok – Chat với Grok (xAI)\n"
    "• /gemini – Chat với Gemini (Google)\n"
)

HELP_TEXT = (
    "🆘 Hướng dẫn lệnh:\n"
    "• /gpt <câu hỏi> — hỏi nhanh với GPT\n"
    "• /grok <câu hỏi> — hỏi nhanh với Grok\n"
    "• /gemini <câu hỏi> — hỏi nhanh với Gemini\n\n"
    "Mẹo: Bạn có thể vào chế độ hội thoại liên tục với một AI bằng cách gõ mỗi lệnh *không kèm câu hỏi*.\n"
    "Ví dụ: gõ `/gpt` rồi gửi tin nhắn bình thường, bot sẽ hiểu là nhắn cho GPT cho đến khi đổi lệnh khác."
)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(WELCOME)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(HELP_TEXT)


def extract_prompt(args: list[str]) -> str:
    return " ".join(args).strip() if args else ""


async def set_mode_and_optionally_ask(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode: str
):
    chat_id = update.effective_chat.id
    SESSION_MODE[chat_id] = mode

    prompt = extract_prompt(context.args)
    if not prompt:
        await update.message.reply_text(
            f"✅ Đã chuyển sang chế độ {mode.upper()}. Hãy gửi tin nhắn để trò chuyện!"
        )
        return

    await update.message.chat.send_action(action="typing")
    if mode == "gpt":
        answer = await ask_gpt(prompt, chat_id)
    elif mode == "grok":
        answer = await ask_grok(prompt, chat_id)
    else:
        answer = await ask_gemini(prompt, chat_id)

    await update.message.reply_text(answer)


async def gpt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode_and_optionally_ask(update, context, "gpt")


async def grok_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode_and_optionally_ask(update, context, "grok")


async def gemini_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode_and_optionally_ask(update, context, "gemini")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    mode: Optional[str] = SESSION_MODE.get(chat_id)
    if not mode:
        # Chưa chọn AI -> gợi ý lệnh
        await update.message.reply_text(
            "Bạn muốn chat với AI nào?\nDùng /gpt, /grok, hoặc /gemini (có thể kèm câu hỏi)."
        )
        return

    await update.message.chat.send_action(action="typing")
    if mode == "gpt":
        answer = await ask_gpt(text, chat_id)
    elif mode == "grok":
        answer = await ask_grok(text, chat_id)
    else:
        answer = await ask_gemini(text, chat_id)

    await update.message.reply_text(answer)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log nhẹ nhàng, trả lời người dùng
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("❌ Đã xảy ra lỗi không mong muốn. Vui lòng thử lại.")
    finally:
        print(f"Exception: {context.error}")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    app.add_handler(CommandHandler("gpt", gpt_cmd))
    app.add_handler(CommandHandler("grok", grok_cmd))
    app.add_handler(CommandHandler("gemini", gemini_cmd))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(error_handler)

    # Dùng long-polling (phù hợp dyno worker)
    print("Bot is running…")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Đóng httpx client nếu có
        if httpx_client:
            asyncio.get_event_loop().run_until_complete(httpx_client.aclose())
