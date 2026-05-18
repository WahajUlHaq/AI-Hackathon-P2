# Workplan: Stage 3 — Insight Agent

## Objective
Develop the Insight Agent (Agent 3) according to the specifications provided in `agent3_insight.md`.

## Scope
1. Implement `agents/agent3_insight.py` to process `verified_pool` from Agent 2.
2. Develop deterministic Python pre-processing for numeric extraction and convergence tagging.
3. Integrate a mock structure for the `deepseek-chat` LLM call to generate complex insights and temporal signals.
4. Implement the deterministic confidence scoring formula `(avg_correctness * 0.6) + (source_diversity * 0.4)` with urgency weighting.
5. Create an orchestration script `demo_stage3.py` to validate the end-to-end flow from Stage 1 through Stage 3.
6. Generate comprehensive trace documentation.

## Timeline
- **Phase 1:** Analyze specifications and existing codebase context.
- **Phase 2:** Implement core logic in `agent3_insight.py`.
- **Phase 3:** Develop and run tests via `demo_stage3.py`.
- **Phase 4:** Trace documentation generation.
