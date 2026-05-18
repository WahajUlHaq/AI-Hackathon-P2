# Reasoning

1.  **Why use `httpx` for LLM Async calls?**: The `module_llm_client.md` shows `requests` (sync), but in a real-time SSE stream architecture, a blocking network request could stall the async queue. Providing `call_deepseek_async` using `httpx` allows full non-blocking pipeline progression.
2.  **Why mock Orchestrator logic?**: Since this is a distributed 7-stage system, the Orchestrator needs to work regardless of the integration status of all individual agents. Adding `try/except ImportError` allows `orchestrator.py` to seamlessly fake the processing queue and outputs for UI and Postman testing.
3.  **Handling SSE state**: The `asyncio.Queue` mechanism is selected for the SSE `stream_thinking` endpoint to allow `orchestrator.py` to push thoughts while `api/main.py` pulls and streams them to clients.
