from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs

app = FastAPI()

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    # Read and parse incoming form data from Twilio
    body = await request.body()
    form = parse_qs(body.decode())
    user_msg = form.get("Body", [""])[0]

    # Simple static reply to confirm everything is working
    reply_text = f"Hi! 👋 You said: {user_msg}\n\nThis confirms your WhatsApp bot is working ✅"

    # Build the Twilio WhatsApp response
    twilio_resp = MessagingResponse()
    twilio_resp.message(reply_text)
    return str(twilio_resp)
