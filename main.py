from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
import openai, os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
CALENDLY_URL = "https://calendly.com/andrews24ultra123/30min"
BUSINESS_NAME = "Test Company"
WHATSAPP_CONTACT = "+6592222590"

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await requ
