# Reasoning: Stage 3 — Insight Agent

## Structural Design
- The Python script `agent3_insight.py` needs to maintain the identical mock-LLM methodology used in Agent 2 to allow the system to run locally without incurring API costs during structural development.
- Deep, multi-dimensional insights must be explicitly defined rather than dynamically generated for this phase to test the pipeline determinism.

## Formula Adjustments
- **Observation:** `confidence = (avg_correctness * 0.6) + (source_diversity * 0.4)`
- **Reasoning:** The document notes a confidence jump from 0.785 to ~0.86 based on an urgency weight. The delta is ~0.075.
- **Conclusion:** Mapped urgency to specific numeric weights to strictly adhere to the specification:
  - `CRITICAL`: +0.08
  - `HIGH`: +0.04
  - `MEDIUM`: +0.02
  - `LOW`: +0.00
  
## Integration
- `demo_stage3.py` must import all previous stages and pipe the outputs sequentially. This models the behavior of the future Orchestrator component.
