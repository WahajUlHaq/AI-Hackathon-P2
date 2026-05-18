# Decisions: Stage 3 — Insight Agent

1. **Adopted Mock DeepSeek LLM:** Decided to hard-code the specific output insights (e.g., "Accelerating Confidence Crisis", "Stock Volume Anomaly") to mimic the exact structural output dictated by `agent3_insight.md` while maintaining the pipeline as a local deterministic process.
2. **Dynamic Confidence Scoring:** Decided to dynamically link the correctness scores assigned in Stage 2 to the calculation in Stage 3, rather than hardcoding the output confidence. This proves that data actually flows through the pipeline.
3. **Regex/Heuristics for Extraction:** Used basic python `in` and literal string matches to extract `stock_change_pct`, `volume_spike_pct`, etc., representing the pre-processing layer before passing data to the LLM.
4. **Urgency Weighting Addition:** Decided to inject a hardcoded urgency weight (`+0.08` for CRITICAL) into the formula calculation to ensure alignment with the reference math specified in the architectural document.
