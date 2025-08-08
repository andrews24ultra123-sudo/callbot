from fastapi import FastAPI, Request
from dotenv import load_dotenv
from openai import OpenAI
import httpx, os, time, json, re
import dateparser
from datetime import datetime
from typing import Dict, Any, Optional

load_dotenv()

app = FastAPI()

# ---- ENV ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Test Company")
CALENDLY_URL = os.getenv("CALENDLY_URL", "https://calendly.com/andrews24ultra123/30min")

# ---- OpenAI (v1+) ----
client = OpenAI(api_key=OPENAI_API_KEY)

# ---- Simple in-memory session store (resets on deploy) ----
# slots: name, service, datetime_text, datetime_iso
SESSIONS: Dict[int, Dict[str, Any]] = {}

# ---- Settings ----
RATE_LIMIT_SECONDS = 1.5
DEFAULT_TZ = "Asia/Singapore"  # for date parsing

# ---------- Helpers ----------

def detect_lang(text: str) -> str:
    """Very simple detector: if contains CJK, treat as Chinese; else English."""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"

def parse_datetime_human(text: str, lang: str) -> (Optional[str], Optional[str]):
    """
    Parse user-provided datetime in EN/中文 into ISO 8601 (local SG time assumed).
    Returns (datetime_text, datetime_iso) — datetime_text is original/cleaned,
    datetime_iso like '2025-08-08T15:00:00+08:00' if parsing succeeded.
    """
    if not text:
        return None, None

    # Configure dateparser
    settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": DEFAULT_TZ,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PARSERS": ["relative-time", "absolute-time", "custom-formats"]
    }
    languages = ["zh"] if lang == "zh" else ["en"]
    dt = dateparser.parse(text, languages=languages, settings=settings)
    if not dt:
        return text, None
    # ISO format with timezone
    return text, dt.isoformat()

def t(msg_en: str, msg_zh: str, lang: str) -> str:
    return msg_zh if lang == "zh" else msg_en

async def tg_send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(url, json=payload)
        r.raise_for_status()

@app.get("/")
async def health():
    return {"ok": True}

@app.post("/telegram/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message") or data.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    user_text = (message.get("text") or "").strip()

    if not chat_id or not user_text:
        return {"ok": True}

    # --- auto language by user message ---
    lang = detect_lang(user_text)

    # --- init session + rate limit ---
    sess = SESSIONS.setdefault(chat_id, {
        "last_ts": 0.0,
        "slots": {"name": None, "service": None, "datetime_text": None, "datetime_iso": None},
        "lang": lang,
    })
    # update session language dynamically
    sess["lang"] = lang

    now = time.time()
    if now - sess["last_ts"] < RATE_LIMIT_SECONDS:
        await tg_send_message(chat_id, t("One moment… ⏳", "请稍等… ⏳", lang))
        return {"ok": True}
    sess["last_ts"] = now

    # --- commands ---
    if user_text.lower().startswith("/start"):
        msg = t(
            f"Hi! I’m the {BUSINESS_NAME} assistant. Tell me what you’d like to book.\n"
            "Commands:\n"
            "• /book – get the booking link now\n"
            "• /reset – clear our conversation\n"
            "• /help – quick tips",
            f"你好！我是 {BUSINESS_NAME} 的预约助理。请告诉我你想预约的服务。\n"
            "指令：\n"
            "• /book – 直接获取预约链接\n"
            "• /reset – 重置对话\n"
            "• /help – 查看使用说明",
            lang
        )
        await tg_send_message(chat_id, msg)
        return {"ok": True}

    if user_text.lower().startswith("/help"):
        msg = t(
            "You can type what you want to book, e.g. “haircut tomorrow 3pm”.\n"
            "I’ll ask for missing info and then share the booking link.\n"
            "Commands: /book /reset /start",
            "你可以直接输入要预约的服务，例如：“明天下午三点理发”。\n"
            "我会询问缺少的信息，然后给你预约链接。\n"
            "可用指令：/book /reset /start",
            lang
        )
        await tg_send_message(chat_id, msg)
        return {"ok": True}

    if user_text.lower().startswith("/reset"):
        SESSIONS[chat_id] = {
            "last_ts": now,
            "slots": {"name": None, "service": None, "datetime_text": None, "datetime_iso": None},
            "lang": lang,
        }
        await tg_send_message(chat_id, t("Conversation reset ✅. What would you like to book?",
                                         "已重置对话 ✅。你想预约什么服务？", lang))
        return {"ok": True}

    if user_text.lower().startswith("/book"):
        await tg_send_message(chat_id, t(f"📅 <b>Book here:</b> {CALENDLY_URL}",
                                         f"📅 <b>点击预约：</b> {CALENDLY_URL}", lang))
        return {"ok": True}

    # --- memory ---
    slots = sess["slots"]  # name, service, datetime_text, datetime_iso

    # --- Use GPT to extract fields (language-aware) ---
    system_prompt = f"""
You are a concise AI receptionist for {BUSINESS_NAME}.
Detect the user's language (English or Chinese) from their message; respond in that language.
Extract fields. OUTPUT ONLY JSON:

{{
  "name": <string or null>,
  "service": <string or null>,
  "datetime_text": <string or null>,  // keep user's phrasing for parsing
  "reply": <1-3 sentence reply that asks only for missing info; if complete, a short confirmation>
}}

Rules:
- If a field is not clearly provided, leave it null.
- Keep responses short, friendly, and professional.
- Do NOT include code fences or extra commentary—JSON only.
"""

    user_for_llm = (
        f"Known so far -> "
        f"name: {slots['name']}, service: {slots['service']}, datetime_text: {slots['datetime_text']}.\n"
        f"User said -> {user_text}"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_for_llm}
            ],
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("` \n")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        extracted = json.loads(raw)
    except Exception:
        extracted = {
            "name": None, "service": None, "datetime_text": None,
            "reply": t("Could you share your name, the service, and a preferred date/time?",
                       "请告诉我你的名字、想预约的服务，以及希望的日期/时间。", lang)
        }

    # --- update slots from GPT extraction ---
    for k in ("name", "service", "datetime_text"):
        v = extracted.get(k)
        if v:
            slots[k] = v

    # --- parse datetime_text into ISO using dateparser (EN/中文) ---
    if slots["datetime_text"] and not slots["datetime_iso"]:
        _, maybe_iso = parse_datetime_human(slots["datetime_text"], lang)
        slots["datetime_iso"] = maybe_iso

    have_all = all([slots["name"], slots["service"], slots["datetime_iso"]])

    if have_all:
        # Build summary in the user's language
        iso_display = slots["datetime_iso"]
        # Friendly local display if possible
        try:
            # Show SG local time in readable format
            dt = dateparser.parse(slots["datetime_text"], languages=["zh"] if lang == "zh" else ["en"],
                                  settings={"TIMEZONE": DEFAULT_TZ, "RETURN_AS_TIMEZONE_AWARE": True})
            if dt:
                iso_display = dt.strftime("%Y-%m-%d %H:%M (%Z)")
        except Exception:
            pass

        summary = t(
            f"Great! Noted:\n"
            f"• Name: {slots['name']}\n"
            f"• Service: {slots['service']}\n"
            f"• Preferred time: {iso_display}\n\n"
            f"📅 <b>Book here:</b> {CALENDLY_URL}\n"
            f"Once you book, I’ll confirm here.",
            f"太好了！已记录：\n"
            f"• 姓名：{slots['name']}\n"
            f"• 服务：{slots['service']}\n"
            f"• 时间：{iso_display}\n\n"
            f"📅 <b>点击预约：</b> {CALENDLY_URL}\n"
            f"预约完成后我会在这里确认。",
            lang
        )
        await tg_send_message(chat_id, summary)
        return {"ok": True}

    # If missing something, ask next best question (from GPT reply), localized fallback if missing
    reply = extracted.get("reply")
    if not reply:
        if not slots["name"]:
            reply = t("What’s your name?", "请问你的名字是？", lang)
        elif not slots["service"]:
            reply = t("What service would you like?", "你想预约什么服务？", lang)
        elif not slots["datetime_text"]:
            reply = t("What date/time works for you?", "你希望的日期/时间是？", lang)
        else:
            reply = t("Would you like the booking link now?", "需要我现在发预约链接给你吗？", lang)

    # If datetime_text present but parsing failed, ask for a clearer time
    if slots["datetime_text"] and not slots["datetime_iso"]:
        reply += t(
            "\n\n(If possible, share a clearer time like 'tomorrow 3pm' or 'Aug 12, 10:00'.)",
            "\n\n（麻烦提供更明确的时间，如“明天下午3点”或“8月12日10:00”。）",
            lang
        )

    await tg_send_message(chat_id, reply)
    return {"ok": True}
