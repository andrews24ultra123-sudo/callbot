from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load your API keys from .env or Railway Variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up your FastAPI app
app = FastAPI()

# Your business info
CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
DISPLAY_WHATSAPP_NUMBER = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    # Parse Twilio form input manually
    body = await request.body()
    form = parse_qs(body.decode())
    user_msg = form.get("Body", [""])[0]

    # GPT-3.5 system prompt
    system_prompt = f"""
    You are a helpful, polite AI receptionist for a business called {BUSINESS_NAME}.
    When someone sends a message:
    1. Greet them.
    2. Ask for their name and what service they need.
    3. Ask for their preferred date and time.
    4. Give them this booking link: {CALENDLY_URL}
    5. Say they'll receive confirmation after booking.

    Keep replies short and friendly.
    """

    # Call GPT-3.5
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
        reply_text = "Sorry! There was an error talking to OpenAI. Please try again later."

    # Build Twilio WhatsApp response
    twilio_resp = MessagingResponse()
    twilio_resp.message(
        reply_text +
        f"\n\n📅 Book here: {CALENDLY_URL}" +
        f"\n📞 Contact us at: {DISPLAY_WHATSAPP_NUMBER}"
    )
    return str(twilio_resp)
