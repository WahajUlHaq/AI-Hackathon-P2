# Decisions

1.  **FastAPI Architecture chosen over Flask**: Due to built-in async support, easy SSE streaming, and out-of-the-box Swagger documentation.
2.  **In-Memory Job Storage**: To avoid complex database setups for the API (like PostgreSQL or Redis) initially, jobs and queues are tracked via Python native memory (`jobs` dict).
3.  **Modular Client Design**: Decided to build `agents/llm_client.py` exactly as requested but extended it with `async` via `httpx` to accommodate the eventual fully async Orchestrator.
