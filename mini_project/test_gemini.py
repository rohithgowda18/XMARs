from google import genai

client = genai.Client(api_key="AIzaSyD9DYqqi8ajtiBlwQIgwE80Etczbd_Akig")

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="hello"
)

print(response.text)