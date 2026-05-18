# Task Plan

1. **Initialization:**
   - Load configuration and target constraints.
   - Setup `execution_log` buffer.
   
2. **Action Iteration:**
   - Check dependency status (`depends_on`).
   - If dependency failed -> status `SKIPPED`.
   
3. **Execution Simulation:**
   - Generate `before_state`.
   - Run Failure Injection check (fail first `PUBLISH`).
   - If not failed -> simulate success and generate `after_state`.
   
4. **Analysis & Comparison:**
   - Compare `before_state` and `after_state`.
   - Highlight fields changed and unchanged.
   - List expected `side_effects`.
   
5. **Finalization:**
   - Compile `execution_summary`.
   - Output log for downstream processing (Stage 6/7).
