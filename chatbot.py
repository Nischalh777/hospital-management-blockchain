import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get API key from .env
API_KEY = os.getenv("GEMINI_API_KEY")
print("Gemini API Key Loaded:", API_KEY)  # Debugging

# Configure Gemini
genai.configure(api_key=API_KEY)

# Initialize model (latest recommended)
model = genai.GenerativeModel("gemini-2.5-flash")

def process_text(extracted_text):
    try:
        prompt = f"Based on this medical report, suggest some medical advice and precautions:\n\n{extracted_text}"
        response = model.generate_content(prompt)

        if response and response.candidates:
            advice = response.candidates[0].content.parts[0].text.strip()
        else:
            advice = "No response from Gemini API."

    except Exception as e:
        advice = f"Error: {str(e)}"

    return advice
