# 📦 Module: `llm_client.py`

## Overview

| Property | Value |
|---|---|
| **File** | `agents/llm_client.py` |
| **Role** | Shared DeepSeek API gateway used by all 7 agents |
| **Model** | `deepseek-chat` |
| **Output Mode** | `json_object` (guaranteed JSON response) |
| **Used By** | Every single agent in the pipeline |

---

## Purpose

`llm_client.py` is the **single point of contact** between the Python pipeline and the DeepSeek LLM API. Instead of each agent managing its own HTTP connection, authentication, and response parsing, they all call one shared function: `call_deepseek()`.

This design ensures:
- API key managed in one place (`.env`)
- All agents use identical request/response patterns
- Easy to swap model (e.g. switch to GPT-4, Gemini) with one change
- Centralized error handling and timeout control

---

## Architecture

```
Agent N
  │
  └──► call_deepseek(system_prompt, user_message, temperature)
              │
              ├── Load DEEPSEEK_API_KEY from .env
              ├── Build payload: {model, messages, temperature, response_format}
              ├── POST https://api.deepseek.com/v1/chat/completions
              ├── Raise HTTPError if non-200
              ├── Extract choices[0].message.content
              └── json.loads() → return dict
```

---

## Function Signature

```python
def call_deepseek(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1
) -> dict:
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `system_prompt` | `str` | required | The agent's identity and behavior instructions |
| `user_message` | `str` | required | The actual data/input for this invocation |
| `temperature` | `float` | `0.1` | Controls randomness. Low = deterministic JSON |

### Returns

| Type | Description |
|---|---|
| `dict` | Parsed JSON object from DeepSeek response |

### Raises

| Exception | When |
|---|---|
| `ValueError` | `DEEPSEEK_API_KEY` not set in `.env` |
| `requests.HTTPError` | Non-200 response from DeepSeek API |
| `json.JSONDecodeError` | Model returned non-parseable JSON (rare with `json_object` mode) |

---

## Full Source Code

```python
import os
import json
import requests
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

    response = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw)
```

---

## Request Payload Structure

```json
{
  "model": "deepseek-chat",
  "messages": [
    {
      "role": "system",
      "content": "<agent system prompt>"
    },
    {
      "role": "user",
      "content": "<input data as JSON string>"
    }
  ],
  "temperature": 0.1,
  "response_format": { "type": "json_object" }
}
```

---

## Why `response_format: json_object`?

DeepSeek's `json_object` mode forces the model to return **only valid JSON** — no markdown code fences, no prose, no explanation text. This is critical because:

1. All agents parse the response with `json.loads()` directly
2. Any non-JSON character in the response would crash parsing
3. Structured agent pipelines require strict schema adherence

---

## Temperature Guide (Per Agent)

| Agent | Temperature | Reason |
|---|---|---|
| Agent 1 — Ingestion | `0.1` | Deterministic parsing, no creativity needed |
| Agent 2 — Insight | `0.2` | Slight flexibility for pattern recognition |
| Agent 3 — Impact | `0.2` | Needs some reasoning flexibility |
| Agent 4 — Planner | `0.1` | Strict constraint validation |
| Agent 5 — Executor | `0.1` | Deterministic simulation |
| Agent 6 — Recovery | `0.1` | Strict decision logic |
| Agent 7 — Reporter | `0.1` | Deterministic summary generation |

---

## Environment Setup

Create a `.env` file in the project root:

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The client uses `python-dotenv` to load this automatically on import.

---

## Error Handling Best Practices

When calling from agents, wrap in try/except:

```python
try:
    result = call_deepseek(SYSTEM_PROMPT, user_message)
except ValueError as e:
    print(f"Config error: {e}")
except requests.HTTPError as e:
    print(f"API error {e.response.status_code}: {e.response.text}")
except json.JSONDecodeError as e:
    print(f"Response parse failed: {e}")
```

---

## Cost Estimation

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| `deepseek-chat` | ~$0.27 | ~$1.10 |

Estimated cost per full pipeline run (all 7 agents):
- Average tokens per call: ~3,000 input + ~2,000 output
- 7 calls total: ~21,000 input + ~14,000 output
- **Estimated cost per run: ~$0.02 USD**

---

## Scalability Notes

- Timeout set to `30s` — sufficient for complex JSON generation
- For 10x scale: add retry logic with exponential backoff
- For 100x scale: use async `httpx.AsyncClient` for parallel agent calls
- Rate limit: DeepSeek allows ~60 RPM on standard tier
