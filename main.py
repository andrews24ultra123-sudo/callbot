from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
import openai, os
from dotenv import load_dotenv
from urllib.parse import parse_qs

load_dotenv()

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")

CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
DISPLAY_WHATSAPP_NUMBER = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    # Parse the body manually to avoid request.form() crash
    body_bytes = await request.body()
    form = parse_qs(body_bytes.decode())
    user_msg = form.get("Body", [""])[0]
    user_number = form.get("From", [""])[0]

    # GPT prompt
    system_prompt = f"""
    You are a friendly and helpful virtual receptionist for a business called {BUSINESS_NAME}.
    Your tasks are:
    1. Ask the customer for their name and what service they want.
    2. Ask what date/time they prefer.
    3. Share the booking link: {CALENDLY_URL}
    4. Let them know they'll get a WhatsApp confirmation after they book.
    Be short, polite, and helpful.
    """

    # Use GPT-3.5 for replies
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
    )

    reply = completion.choices[0].message.content

    # Build reply via Twilio
    twilio_resp = MessagingResponse()
    twilio_resp.message(
        reply +
        f"\n\n📅 Book now: {CALENDLY_URL}" +
        f"\n📞 Contact us at: {DISPLAY_WHATSAPP_NUMBER}"
    )
    return str(twilio_resp)
