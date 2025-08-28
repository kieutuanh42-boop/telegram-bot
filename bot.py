import os
import asyncio
from typing import Dict, Optional
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
from openai import AsyncOpenAI
import httpx
import google.generativeai as genai

# ========= CONFIG =========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

OPENAI_MODEL = "gpt-4o-mini"
XAI_MODEL = "grok-2-latest"
GEMINI_MODEL = "gemini-1.5-flash"

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN")

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
httpx_client = httpx.AsyncClient(timeout=60.0) if XAI_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL)
else:
    gemini_model = None

SESSION_MODE: Dict[int, str] = {}

# ========= AI HANDLERS =========
async def ask_gpt(prompt: str) -> str:
    if not openai_client:
        return "⚠️ Chưa cấu hình OPENAI_API_KEY."
    try:
        resp = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ GPT lỗi: {e}"

async def ask_grok(prompt: str) -> str:
    if not httpx_client:
        return "⚠️ Chưa cấu hình XAI_API_KEY."
    try:
        r = await httpx_client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_API_KEY}"},
            json={"model": XAI_MODEL, "messages":[{"role":"user","content":prompt}]},
        )
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"❌ Grok lỗi: {e}"

async def ask_gemini(prompt: str) -> str:
    if not gemini_model:
        return "⚠️ Chưa cấu hình GEMINI_API_KEY."
    try:
        resp = await asyncio.to_thread(lambda: gemini_model.generate_content(prompt))
        return resp.text.strip()
    except Exception as e:
        return f"❌ Gemini lỗi: {e}"

# ========= TELEGRAM HANDLERS =========
WELCOME = (
    "👋 Chào bạn đến với bot Telegram của nhà phát triển **Tô Minh Điềm**.\n"
    "Chat với ai, bấm /help để xem lệnh.\n\n"
    "• /gpt – Chat với GPT (OpenAI)\n"
    "• /grok – Chat với Grok (xAI)\n"
    "• /gemini – Chat với Gemini (Google)\n"
)

HELP = (
    "🆘 Hướng dẫn:\n"
    "/gpt <câu hỏi>\n"
    "/grok <câu hỏi>\n"
    "/gemini <câu hỏi>\n\n"
    "Hoặc gõ lệnh không có câu hỏi để vào chế độ chat liên tục."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(WELCOME)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    chat_id = update.effective_chat.id
    SESSION_MODE[chat_id] = mode
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text(f"✅ Đang ở chế độ {mode.upper()}. Gõ tin nhắn để chat.")
        return
    if mode == "gpt": ans = await ask_gpt(prompt)
    elif mode == "grok": ans = await ask_grok(prompt)
    else: ans = await ask_gemini(prompt)
    await update.message.reply_text(ans)

async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "gpt")

async def grok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "grok")

async def gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "gemini")

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    mode = SESSION_MODE.get(chat_id)
    if not mode:
        await update.message.reply_text("Chọn AI bằng /gpt, /grok, hoặc /gemini.")
        return
    if mode == "gpt": ans = await ask_gpt(text)
    elif mode == "grok": ans = await ask_grok(text)
    else: ans = await ask_gemini(text)
    await update.message.reply_text(ans)

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("gpt", gpt))
    app.add_handler(CommandHandler("grok", grok))
    app.add_handler(CommandHandler("gemini", gemini))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.run_polling()

if __name__ == "__main__":
    main()
