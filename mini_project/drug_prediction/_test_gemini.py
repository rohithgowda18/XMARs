import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load .env
load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

try:
    print("API Key Loaded:", bool(API_KEY))

    # Create client
    client = genai.Client(api_key=API_KEY)

    # Generate response
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Say hello"
    )

    print("✅ Gemini API key is working!")
    print("Response:", response.text)

except Exception as e:
    print("❌ Gemini API failed")
    print("Error:", str(e))