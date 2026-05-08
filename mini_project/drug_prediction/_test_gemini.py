"""Quick test of Gemini API connectivity."""
from google import genai
import time

time.sleep(5)  # Wait for rate limit to reset

client = genai.Client(api_key="AIzaSyDXOyLIe6qbKzeGWV9O31YjrV7SQjxQSYk")

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Say hello"
    )
    print("SUCCESS:", response.text)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:300])
    print("\nTrying gemini-2.5-flash...")
    time.sleep(2)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello"
        )
        print("SUCCESS with 2.5-flash:", response.text)
    except Exception as e2:
        print("ERROR 2:", str(e2)[:300])
