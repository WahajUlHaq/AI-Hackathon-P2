# Workplan: Orchestrator, LLM Client & API Development

## Objective
Develop the core coordination, communication, and API exposure layers for the Autonomous Content-to-Action multi-agent system.

## Scope
1.  **Orchestrator (`orchestrator.py`)**: The central entry point orchestrating all 7 pipeline stages. Manages the execution flow and the thinking stream queue.
2.  **LLM Client (`agents/llm_client.py`)**: A centralized DeepSeek API gateway for all 7 agents, providing sync and async inference methods.
3.  **API (`api/main.py`)**: A FastAPI server exposing endpoints for running the pipeline (async/sync), polling status, retrieving results, and opening an SSE stream for live agent narration.
4.  **Postman Collection**: Export a JSON collection to test the above endpoints.
