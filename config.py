import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RASA_SERVER_URL = "http://localhost:5005/webhooks/rest/webhook"  # Update if needed
