from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import parse_qs
import os

# Load environment variables from .env
load_dotenv()

# Initialize OpenAI client (for v1+ API)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI app
app = FastAPI()

# Business config
CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
DISPLAY_WHATSAPP_NUMBER = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    # Parse the form manually (Twilio sends x-www-form-urlencoded)
    body = await request.body()
    form = parse_qs(body.decode())
    user_msg = form.get("Body", [""])[0]
    user_number = form.get("From", [""])[0]

    # System instruction for GPT
    system_prompt = f"""
    You are a helpful and friendly AI receptionist for a business called {BUSINESS_NAME}.
    1. Ask the customer for their name and what service they need.
    2. Ask for their preferred date and time.
    3. Share the booking link: {CALENDLY_URL}
    4. Let them know they'll receive a WhatsApp confirmation after booking.
    Always keep replies short and polite.
    """

    # Generate GPT response
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
    )

    reply = response.choices[0].message.content

    # Send reply back via Twilio
    twilio_resp = MessagingResponse()
    twilio_resp.message(
        reply +
        f"\n\n📅 Book now: {CALENDLY_URL}" +
        f"\n📞 Contact us at: {DISPLAY_WHATSAPP_NUMBER}"
    )
    return str(twilio_resp)
