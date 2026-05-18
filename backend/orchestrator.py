import asyncio
import json
import time
from datetime import datetime, timezone

# Trying to import actual agents, fallback to mock if they don't exist
try:
    from agents.stage1 import runner as stage1_runner
    from agents import agent2_flag, agent3_insight, agent4_plan, agent5_executor, agent6_recovery, agent7_reporter
except ImportError as e:
    print(f"ImportError: {e}")
    pass

DEMO_SOURCES = [
    {
        "label": "Global Grain Supply — UN Food Agency Report (PDF)",
        "type": "PDF",
        "content": "base64_or_filepath",
        "received_at": "2025-11-01T08:00:00Z"
    },
    {
        "label": "Reuters — Ukraine Harvest Disruption Coverage",
        "type": "URL",
        "content": "https://reuters.com/world/ukraine-grain-harvest-2025",
        "received_at": "2025-11-03T09:30:00Z"
    },
    {
        "label": "Chicago Board of Trade — Wheat Futures CSV",
        "type": "CSV",
        "content": "Date,Close,Volume\n2025-10-28,512.00,42000\n2025-10-29,525.50,55000\n2025-10-30,543.75,61000\n2025-10-31,561.00,70000\n2025-11-01,580.25,83000",
        "received_at": "2025-11-03T10:00:00Z"
    },
    {
        "label": "USDA Export Inspection API",
        "type": "JSON",
        "content": '{"weekly_inspections":[{"week":"2025-W43","wheat_inspected_MT":850000,"vs_prior_week_pct":-34.2},{"week":"2025-W44","wheat_inspected_MT":610000,"vs_prior_week_pct":-28.2}]}',
        "received_at": "2025-11-03T10:30:00Z"
    },
    {
        "label": "Twitter/LinkedIn — Commodity Trader Sentiment Feed",
        "type": "MockFeed",
        "content": "1,240 posts in 12h. Top: wheat shortage (482), food security alert (376), buy grain ETFs (264). Sentiment: -0.64",
        "received_at": "2025-11-03T11:00:00Z"
    }
]

CONSTRAINTS = {
    "alert_budget_usd": 0,
    "publish_deadline_hours": 6,
    "analyze_budget_usd": 1000,
    "available_resources": [
        "notification_service",
        "document_portal",
        "risk_system",
        "analytics_engine",
        "monitoring_scheduler"
    ],
    "api_rate_limits": {
        "document_portal": "10 calls/hour",
        "analytics_engine": "5 calls/hour"
    },
    "output_language": "English",
    "sensitivity_level": "INTERNAL"
}

async def run_pipeline_async(sources, constraints, thought_queue=None, job_id="demo_job"):
    start_time = time.time()
    
    async def emit(agent, stage, type_, emoji, thought):
        if thought_queue:
            await thought_queue.put({
                "job_id": job_id,
                "stage": stage,
                "agent": agent,
                "type": type_,
                "emoji": emoji,
                "thought": thought,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        else:
            print(f"[{stage}] {emoji} {agent}: {thought}")

    await emit("Orchestrator", 0, "start", "🔍", "Alright, I'm kicking off the pipeline and reading all the sources you provided simultaneously to save time.")

    # Stage 1
    await emit("IngestionAgent", 1, "start", "🔍", "I'm spinning up the parallel parsers to process everything as quickly as possible.")
    stage1_result = await asyncio.to_thread(stage1_runner.run, sources)
    content_blocks = stage1_result["content_blocks"]
    ingestion_summary = stage1_result["ingestion_summary"]
    await emit("IngestionAgent", 1, "result", "✅", f"I've successfully parsed {len(content_blocks)} sources and filtered out {ingestion_summary['noise_filtered']} pieces of noisy data.")

    # Stage 2
    await emit("FlagAgent", 2, "start", "🔍", "Now I'm evaluating the credibility of the sources and resolving any conflicting information I find.")
    stage2_result = await asyncio.to_thread(agent2_flag.run, content_blocks)
    verified_pool = stage2_result["verified_pool"]
    await emit("FlagAgent", 2, "result", "✅", f"Verification complete. I've narrowed it down to {len(verified_pool['trusted_blocks'])} highly trusted sources.")

    # Stage 3
    await emit("InsightAgent", 3, "start", "🔍", "I'm diving deep into the verified data to uncover the real signals and extract actionable insights.")
    stage3_result = await asyncio.to_thread(agent3_insight.run, content_blocks, stage2_result)
    await emit("InsightAgent", 3, "result", "✅", f"I've generated {len(stage3_result.get('insights', []))} deep insights from the data.")

    # Stage 4
    await emit("ActionPlannerAgent", 4, "start", "🔍", "I'm putting together a strategic, step-by-step action plan while respecting your budget and resource constraints.")
    stage4_result = await asyncio.to_thread(agent4_plan.run, stage3_result, constraints)
    action_plan = stage4_result.get("action_plan", [])
    await emit("ActionPlannerAgent", 4, "result", "✅", f"Great, I've built a solid {len(action_plan)}-step action plan.")

    # Stage 5
    await emit("ExecutorAgent", 5, "start", "🔍", "I'm going to start executing the action plan step by step now. Wish me luck!")
    stage5_result = await asyncio.to_thread(agent5_executor.run, stage4_result)
    execution_log = stage5_result.get("execution_log", [])
    exec_summary = stage5_result.get("execution_summary", {})
    if exec_summary.get("failed", 0) > 0:
        await emit("ExecutorAgent", 5, "warning", "⚠️", f"Uh oh, {exec_summary['failed']} actions failed during execution. I'll need to handle those.")
    else:
        await emit("ExecutorAgent", 5, "result", "✅", "Awesome, all actions executed flawlessly on the first try!")
    
    # Stage 6
    await emit("RecoveryAgent", 6, "start", "🔍", "I'm stepping in to handle the failures. Let's see if I can recover them using the predefined fallbacks.")
    stage6_result = await asyncio.to_thread(agent6_recovery.run, execution_log, action_plan)
    recovered_actions = stage6_result.get("recovered_actions", [])
    if len(recovered_actions) > 0:
        await emit("RecoveryAgent", 6, "recovery", "🔄", f"Phew! I successfully recovered {len(recovered_actions)} failed actions.")
    await emit("RecoveryAgent", 6, "result", "✅", "The recovery phase is complete. We're back on track.")

    # Stage 7
    await emit("ReporterAgent", 7, "start", "🔍", "Finally, I'm compiling the complete trace and generating the final report for you.")
    
    stage_outputs = {
        "stage1": stage1_result,
        "stage2": stage2_result,
        "stage3": stage3_result,
        "stage4": stage4_result,
        "stage5": stage5_result,
        "stage6": stage6_result,
    }
    
    reporter = agent7_reporter.ReporterAgent(output_dir="output")
    final_report = await asyncio.to_thread(reporter.generate_report, stage_outputs)
    
    trace = final_report.get("antigravity_trace", {})
    outcome = trace.get("final_outcome", "Pipeline complete.")
    await emit("ReporterAgent", 7, "done", "🎯", f"I'm all done! Here's the final outcome: {outcome}")

    duration_ms = int((time.time() - start_time) * 1000)

    result = {
        "job_id": job_id,
        "status": "completed",
        "pipeline_duration_ms": duration_ms,
        "ingestion": stage1_result,
        "insights": stage3_result,
        "action_plan": stage4_result,
        "execution": stage5_result,
        "recovery": stage6_result,
        "final_report": final_report
    }

    # Save to output file
    import os
    os.makedirs("output", exist_ok=True)
    with open(f"output/pipeline_result_{job_id}.json", "w") as f:
        json.dump(result, f, indent=2)

    return result

def run_pipeline(sources=None, constraints=None):
    if sources is None:
        sources = DEMO_SOURCES
    if constraints is None:
        constraints = CONSTRAINTS
    return asyncio.run(run_pipeline_async(sources, constraints))

if __name__ == "__main__":
    print("Running default pipeline...")
    res = run_pipeline()
    print("Pipeline complete. Outcome:")
    print(res["final_report"]["antigravity_trace"]["final_outcome"])
