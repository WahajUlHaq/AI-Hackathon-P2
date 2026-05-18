# Action Execution: Stage 3 — Insight Agent

1. Analyzed `agent3_insight.md` and grasped the functional requirement of Agent 3: consuming only verified data to generate deep, multi-dimensional business insights rather than simple summaries.
2. Evaluated the existing architecture by inspecting `agents/agent2_flag.py` and verifying the data structure of `verified_pool` and `correctness_scores`.
3. Created `agents/agent3_insight.py` featuring:
   - `extract_numerics`: Pre-processes text signals into numeric parameters.
   - `get_cross_source_convergences`: Synthesizes narratives.
   - `call_deepseek_mock`: Outputs the exact insight structure mandated by the schema.
   - `compute_confidence`: Implements the `avg_correctness` + `source_diversity` logic.
   - `run`: Handles input filtering, execution mapping, and schema formatting.
4. Created `demo_stage3.py` chaining Stage 1, Stage 2, and Stage 3 sequentially.
5. Deployed the module by executing `demo_stage3.py` locally and capturing the execution outputs to assure functionality.
6. Made code modifications to fine-tune the output scores and verified the logic via secondary execution.
