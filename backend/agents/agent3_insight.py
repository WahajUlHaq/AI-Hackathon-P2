import re
import json
from typing import List, Dict, Any

from agents.llm_client import call_deepseek


def call_deepseek_real(verified_blocks, conflict_resolutions, excluded_count):
    system_prompt = """You are InsightAgent, the deep analysis engine of an Autonomous Content-to-Action AI system.

You receive VERIFIED content blocks from multiple sources. The system is domain-agnostic.
Do NOT summarize. Extract DEEP insights that COMBINE multiple sources.

Each insight must:
- Synthesize information ACROSS sources (not just restate one source)
- Identify the root cause behind the signal
- State the forward implication (what happens if nothing is done)
- Assign urgency and time horizon

Also extract temporal signals: metrics that are changing over time.

Output ONLY valid JSON:
{
  "insights": [
    {
      "id": "ins_001",
      "title": "concise insight title",
      "description": "multi-source synthesis: what is happening, why it matters, root cause",
      "signal_type": "risk|trend|anomaly|opportunity|systemic",
      "root_cause": "underlying reason this is happening",
      "forward_implication": "what happens if no action is taken",
      "time_horizon": "immediate|short-term|medium-term|long-term",
      "supporting_sources": ["cb_001", "cb_002"],
      "urgency": "CRITICAL|HIGH|MEDIUM|LOW",
      "metric_impact": "quantified business impact: e.g. '$2.4M revenue at risk', '22% decline in throughput', '40% cost overrun projected', 'N/A if not quantifiable'"
    }
  ],
  "temporal_signals": [
    {
      "metric": "metric name",
      "direction": "increasing|decreasing|stable|volatile",
      "change_description": "how it changed and over what period",
      "observed_in": ["cb_002"]
    }
  ],
  "agent_reasoning": "1-2 sentence summary of the key multi-source synthesis insight"
}"""
    user_message = json.dumps({
        "verified_blocks": [
            {
                "id": b["id"],
                "source_label": b.get("source_label", ""),
                "source_type": b.get("source_type", ""),
                "domain": b.get("domain", "general"),
                "trust_score": b.get("trust_score", 0.5),
                "raw_text": b.get("raw_text", "")[:1200],
                "timestamp": b.get("timestamp", "")
            }
            for b in verified_blocks
        ],
        "conflict_resolutions": conflict_resolutions,
        "excluded_block_count": excluded_count
    })

    try:
        response = call_deepseek(system_prompt, user_message, temperature=0.3)
        return response
    except Exception as e:
        print(f"[InsightAgent] LLM call failed: {e}")
        return {"insights": [], "temporal_signals": [], "agent_reasoning": "LLM unavailable"}


def compute_confidence(insight: Dict[str, Any], verified_blocks: List[Dict[str, Any]]) -> float:
    """
    confidence = (avg_correctness * 0.6) + (source_diversity * 0.4)
    capped at 0.95
    """
    supporting = insight.get("supporting_sources", [])
    if not supporting:
        return 0.0

    blocks_dict = {b["id"]: b for b in verified_blocks}
    
    correctness_sum = 0.0
    domains = set()
    
    for s_id in supporting:
        if s_id in blocks_dict:
            b = blocks_dict[s_id]
            # Use correctness_score from Agent 2
            correctness_sum += b.get("correctness_score", 0.0)
            domains.add(b.get("domain", "general"))

    avg_correctness = (correctness_sum / len(supporting)) if len(supporting) > 0 else 0.0
    source_diversity = min(len(domains) / 4.0, 1.0) # max 4 domains
    
    base_confidence = (avg_correctness * 0.6) + (source_diversity * 0.4)
    
    urgency = insight.get("urgency", "LOW")
    urgency_weight = {"CRITICAL": 0.08, "HIGH": 0.04, "MEDIUM": 0.02, "LOW": 0.0}
    
    confidence = base_confidence + urgency_weight.get(urgency, 0.0)
    return min(confidence, 0.95)

def run(content_blocks: List[Dict[str, Any]], agent2_output: Dict[str, Any]) -> Dict[str, Any]:
    # Extract data from Agent 2 output
    trusted_ids = agent2_output.get("verified_pool", {}).get("trusted_blocks", [])
    false_flagged_ids = agent2_output.get("verified_pool", {}).get("false_flagged_blocks", [])
    
    # Get correctness scores to inject into verified blocks
    correctness_scores = agent2_output.get("correctness_scores", {})
    
    # Build verified_blocks
    verified_blocks = []
    excluded_sources = []
    
    for block in content_blocks:
        b_id = block["id"]
        # update correctness score
        if b_id in correctness_scores:
            block["correctness_score"] = correctness_scores[b_id]["score"]
            block["correctness_label"] = correctness_scores[b_id]["label"]
            
        if b_id in trusted_ids:
            verified_blocks.append(block)
        elif b_id in false_flagged_ids:
            excluded_sources.append(f"{b_id} — {block.get('correctness_label', 'LIKELY_FALSE')}, excluded from insight generation")
            
    print(f"[InsightAgent] Processing {len(verified_blocks)} verified blocks ({len(excluded_sources)} excluded)...")

    # Build conflict context from agent2 output
    conflict_resolutions = [
        {
            "topic": c.get("topic", ""),
            "resolution": c.get("python_resolution", ""),
            "reason": c.get("resolution_reason", "")
        }
        for c in agent2_output.get("conflicts", [])
    ]

    # Call LLM for full insight extraction (domain-agnostic)
    print("[InsightAgent] Calling LLM for insight extraction...")
    llm_output = call_deepseek_real(verified_blocks, conflict_resolutions, len(excluded_sources))
    
    insights = llm_output.get("insights", [])
    temporal_signals = llm_output.get("temporal_signals", [])
    
    # 3. Compute Confidences
    for ins in insights:
        ins["confidence"] = round(compute_confidence(ins, verified_blocks), 2)
        
    # Calculate overall confidence
    overall_confidence = 0.0
    if insights:
        overall_confidence = round(sum(ins["confidence"] for ins in insights) / len(insights), 2)
        
    print(f"[InsightAgent] Done — {len(insights)} insights, {len(temporal_signals)} temporal signals, confidence={overall_confidence:.2f}")

    # Build excluded reason from actual FlagAgent false_flags data
    false_flag_data = agent2_output.get("false_flags", [])
    if false_flag_data:
        excluded_reason = "; ".join(
            f"{ff.get('block_id', '?')} — {ff.get('why_flagged', 'LIKELY_FALSE')}"
            for ff in false_flag_data
        )
    else:
        excluded_reason = f"{len(excluded_sources)} source(s) excluded as LIKELY_FALSE by FlagAgent" if excluded_sources else "No sources excluded."

    return {
        "insights": insights,
        "temporal_signals": temporal_signals,
        "overall_confidence": overall_confidence,
        "sources_used": trusted_ids,
        "sources_excluded": false_flagged_ids,
        "excluded_reason": excluded_reason,
        "agent_reasoning": llm_output.get("agent_reasoning", "")
    }
