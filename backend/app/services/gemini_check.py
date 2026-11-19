import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

root = Path(__file__).resolve().parents[3]
load_dotenv(root / ".env")

key = os.getenv("CORTEX_MODEL_API_KEY")
model = os.getenv("CORTEX_MODEL_NAME")

if not key or not model:
    raise SystemExit("Missing API key or model name in .env")

try:
    client = genai.Client(api_key=key)

    response = client.interactions.create(
        model=model,
        input="Reply with exactly: Cortex Lock connected",
        generation_config={"max_output_tokens": 64},
    )

    print(response.output_text or "No text returned.")

except Exception as error:
    print("Connection failed.")
    print("Error type:", type(error).__name__)
    print("Error code:", getattr(error, "code", "unavailable"))