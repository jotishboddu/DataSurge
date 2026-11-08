import os
from dotenv import load_dotenv
from google import genai

print("1. Starting...")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
print("2. Connected. Asking the AI...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Say hello to the DataSurge team in one short sentence."
)

print("3. Got an answer:")
print(response.text)
