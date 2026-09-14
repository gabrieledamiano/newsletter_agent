import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

for m in client.models.list():
    
    if "generateContent" in getattr(m , "supported_actions", []) or True:
        print(f"{m.name:<50} | {getattr(m, 'supported_actions', 'n/d')}")