import os
import json
import requests
import httpx
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"


def call_deepseek(system_prompt: str, user_message: str, temperature: float = 0.1) -> dict:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set in .env file")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"}
    }

    response = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw)

async def call_deepseek_async(system_prompt: str, user_message: str, temperature: float = 0.1) -> dict:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set in .env file")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(DEEPSEEK_BASE_URL, headers=headers, json=payload)
        response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw)
