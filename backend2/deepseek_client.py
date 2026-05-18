"""
DeepSeek client for agent text generation.

Uses the OpenAI-compatible DeepSeek API (https://api.deepseek.com).
Model: deepseek-chat (DeepSeek-V4-Flash, non-thinking mode) — supports JSON output.

Used by: parser_agent, insight_agent, planner_agent, executor_agent.
NOT used by: orchestrator.py (stays on Gemini for Antigravity function-calling).
"""
import asyncio
import json
import os
import re

import httpx

_BASE_URL = "https://api.deepseek.com/chat/completions"
_MODEL = "deepseek-chat"  # V4-Flash non-thinking — fast + cheap ($0.14/1M in)


def _parse_retry_after(exc: Exception | str) -> float:
    msg = str(exc)
    m = re.search(r"retry[_ ](?:in|after)[: ]+([0-9.]+)\s*s", msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 1.0
    return 30.0


async def generate(
    system_prompt: str,
    user_content: str,
    json_mode: bool = True,
    temperature: float = 0.1,
    max_retries: int = 3,
) -> str:
    """
    Call DeepSeek and return the response text.
    Automatically retries on 429 with the retry delay from the error.
    Raises RuntimeError if all retries are exhausted.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set in environment.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(_BASE_URL, headers=headers, json=payload)

            if resp.status_code == 429:
                delay = _parse_retry_after(resp.text)
                await asyncio.sleep(delay)
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 429:
                delay = _parse_retry_after(exc.response.text)
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
                continue
            raise

    raise RuntimeError(f"DeepSeek: all {max_retries} retries failed. Last error: {last_exc}")


def mcp_tools_to_openai(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP TOOLS list to OpenAI-compatible tool definitions for DeepSeek."""
    result = []
    for t in mcp_tools:
        schema = t.get("inputSchema", {})
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        })
    return result


async def run_agentic_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict],          # OpenAI-format tools (from mcp_tools_to_openai)
    tool_executor,              # async callable: (name, args) -> (result_str, is_error)
    sse_emit=None,              # optional async callable for SSE events
    max_turns: int = 20,
) -> str:
    """
    DeepSeek agentic loop with tool calling — mirrors the Gemini orchestrator.
    DeepSeek-V4-Flash supports OpenAI-compatible function calling.

    Returns the final assistant text response.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set in environment.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    tool_call_count = 0
    final_text = ""

    for _turn in range(max_turns):
        payload = {
            "model": _MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }

        # Call DeepSeek with retry on 429
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(_BASE_URL, headers=headers, json=payload)
            if resp.status_code == 429:
                await asyncio.sleep(_parse_retry_after(resp.text))
                continue
            resp.raise_for_status()
            break

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "")

        # Add assistant message to history
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            # No more tool calls — done
            final_text = msg.get("content") or ""
            break

        # Execute each tool call and collect results
        tool_results = []
        for tc in tool_calls:
            tool_call_count += 1
            fn = tc["function"]
            name = fn["name"]
            try:
                args = json.loads(fn["arguments"])
            except Exception:
                args = {}

            if sse_emit:
                await sse_emit("tool_call", {
                    "tool": name,
                    "args": args,
                    "call_number": tool_call_count,
                })

            result_str, is_error = await tool_executor(name, args)

            if sse_emit:
                try:
                    result_json = json.loads(result_str)
                except Exception:
                    result_json = {"raw": result_str}
                await sse_emit("tool_result", {
                    "tool": name,
                    "call_number": tool_call_count,
                    "success": not is_error,
                    "result": result_json,
                })

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

        messages.extend(tool_results)

    return final_text

