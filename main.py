from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = FastAPI()

CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
DISPLAY_WHATSAPP_NUMBER = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    body = await request.body()
    form = parse_qs(body.decode())
    user_msg = form.get("Body", [""])[0]

    system_prompt = f"""
    You are a helpful and friendly AI receptionist for a business called {BUSINESS_NAME}.
    1. Ask for the customer's name and what service they need.
    2. Ask for a preferred date/time.
    3. Share this booking link: {CALENDLY_URL}
    4. Let them know they’ll get WhatsApp confirmation after booking.
    Keep replies short and friendly.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ]
        )
        reply_text = response.choices[0].message.content
    except Exception as e:
        # Log the error to Railway console
        print("❌ OpenAI error:", e)
        reply_text = "Sorry, I had trouble replying just now. Please try again later."

    twilio_resp = MessagingResponse()
    twilio_resp.message(
        reply_text +
        f"\n\n📅 Book here: {CALENDLY_URL}" +
        f"\n📞 Contact us at: {DISPLAY_WHATSAPP_NUMBER}"
    )
    return str(twilio_resp)
