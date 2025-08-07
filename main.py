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
    1.
