from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
import openai, os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# OpenAI API key from .env
openai.api_key = os.getenv("OPENAI_API_KEY")

# Hardcoded business info
CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
WHATSAPP_CONTACT = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    user_msg = form.get("Body")
    user_number = form.get("From")

    # Instruction to GPT
    system_prompt = f"""
    You are a friendly, helpful AI receptionist for a business called {BUSINESS_NAME}.
    When someone sends a WhatsApp message, follow these steps:
    1. Ask the customer for their name and what service they need.
    2. Ask what date and time they prefer.
    3. Then give them this booking link: {CALENDLY_URL}
    4. Tell them they’ll receive a WhatsApp confirmation after they book.

    Always sound polite, professional, and brief.
    """

    # GPT-3.5 response
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
    )

    reply = completion.choices[0].message.content

    # WhatsApp reply via Twilio
    twilio_resp = MessagingResponse()
    twilio_resp.message(
        reply + f"\n\n📅 Book here: {CALENDLY_URL}\n📞 Contact us at: {WHATSAPP_CONTACT}"
    )
    return str(twilio_resp)

