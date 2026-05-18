import json
import datetime
from typing import List, Dict, Any
import os



def calculate_days_old(timestamp_str: str) -> int:
    try:
        if not timestamp_str:
            return 0
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - dt
        return max(0, delta.days)
    except Exception:
        return 0

from agents.llm_client import call_deepseek


def call_deepseek_for_conflicts(content_blocks):
    """Use LLM to detect conflicts and assign correctness labels — works for ANY domain."""
    system_prompt = """You are FlagAgent, the fact-checker of an Autonomous Content-to-Action AI system.

You receive content blocks from multiple sources, each with a pre-computed trust_score.
Your job:
1. Detect factual conflicts between blocks (any domain: business, finance, logistics, policy, health, etc.)
2. For each conflict: resolve using trust_score (higher trust wins if margin > 0.20, else UNCERTAIN)
3. Assign correctness_label to EVERY block based on conflict outcomes and trust scores
4. Write clear human-readable resolution_reason and investigation_path

Rules:
- Conflict = two blocks make contradictory factual claims about the same specific thing
- If trust margin > 0.20: winner LIKELY_TRUE, loser LIKELY_FALSE
- If margin <= 0.20: both UNCERTAIN (cannot resolve)
- Block not in any conflict: LIKELY_TRUE if trust_score >= 0.50, else UNCERTAIN
- Noise blocks (is_noise=true): always LIKELY_FALSE, correctness_score = 0.0
- Stale blocks (is_stale=true): downgrade correctness_score by 0.7 multiplier

Output ONLY valid JSON:
{
  "conflicts": [
    {
      "id": "con_001",
      "topic": "brief description of the contradiction",
      "source_a": {"id": "cb_001", "trust_score": 0.315},
      "source_b": {"id": "cb_002", "trust_score": 0.850},
      "claim_a": "what source A claims",
      "claim_b": "what source B claims",
      "python_resolution": "prefer_b",
      "resolution_margin": 0.535,
      "resolution_basis": "trust_score",
      "resolution_reason": "Source B has 2.7x higher trust and is more recent",
      "investigation_path": "Cross-check with official statement or third independent source"
    }
  ],
  "false_flags": [
    {
      "block_id": "cb_001",
      "why_flagged": "Contradicts higher-trust source on the same metric",
      "what_to_verify": "Obtain official confirmation or third-party corroboration"
    }
  ],
  "block_verdicts": {
    "cb_001": {"correctness_score": 0.158, "correctness_label": "LIKELY_FALSE"},
    "cb_002": {"correctness_score": 0.850, "correctness_label": "LIKELY_TRUE"}
  }
}"""

    blocks_for_llm = []
    for block in content_blocks:
        blocks_for_llm.append({
            "id": block["id"],
            "source_label": block.get("source_label", ""),
            "source_type": block.get("source_type", ""),
            "trust_score": block.get("trust_score", 0.5),
            "credibility_score": block.get("credibility_score", 0.5),
            "domain": block.get("domain", "general"),
            "raw_text": block.get("raw_text", "")[:800],
            "timestamp": block.get("timestamp", ""),
            "is_noise": block.get("is_noise", False),
            "is_stale": block.get("is_stale", False)
        })

    user_message = json.dumps({"content_blocks": blocks_for_llm})
    try:
        response = call_deepseek(system_prompt, user_message, temperature=0.1)
        return response
    except Exception as e:
        print(f"[FlagAgent] LLM call failed: {e}. Using trust-score defaults.")
        fallback_verdicts = {}
        for block in content_blocks:
            if block.get("is_noise"):
                fallback_verdicts[block["id"]] = {"correctness_score": 0.0, "correctness_label": "LIKELY_FALSE"}
            elif block.get("trust_score", 0.5) >= 0.50:
                s = round(block.get("trust_score", 0.5), 3)
                fallback_verdicts[block["id"]] = {"correctness_score": s, "correctness_label": "LIKELY_TRUE"}
            else:
                s = round(block.get("trust_score", 0.5), 3)
                fallback_verdicts[block["id"]] = {"correctness_score": s, "correctness_label": "UNCERTAIN"}
        return {"conflicts": [], "false_flags": [], "block_verdicts": fallback_verdicts}


def run(content_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("[FlagAgent] Computing trust scores...")

    # Phase 1: PYTHON — Trust Scoring (deterministic, domain-agnostic)
    for block in content_blocks:
        days_old = calculate_days_old(block.get('timestamp', ''))
        recency_weight = max(0.1, 1.0 - (days_old * 0.1))
        credibility = block.get('credibility_score', 0.5)
        trust_score = credibility * recency_weight

        block['trust_score'] = round(trust_score, 3)
        print(f"  [{block['id']}] {block.get('source_label', '')[:30]:<30} credibility={credibility:.2f}  recency={recency_weight:.2f}  trust={block['trust_score']:.3f}")

    # Phase 2: LLM — Conflict Detection & Resolution (domain-agnostic)
    print("\n[FlagAgent] Calling LLM for conflict detection and truth scoring...")
    llm_output = call_deepseek_for_conflicts(content_blocks)

    conflicts = llm_output.get("conflicts", [])
    false_flags = llm_output.get("false_flags", [])
    block_verdicts = llm_output.get("block_verdicts", {})

    # Phase 3: PYTHON — Apply LLM Verdicts to Blocks
    print("\n[FlagAgent] Applying verdicts...")
    correctness_scores = {}
    correctness_labels = {}
    trust_scores_map = {}

    for block in content_blocks:
        b_id = block["id"]
        verdict = block_verdicts.get(b_id, {})
        if verdict:
            score = round(float(verdict.get("correctness_score", block["trust_score"])), 3)
            label = verdict.get("correctness_label", "LIKELY_TRUE")
        else:
            score = block["trust_score"]
            label = "LIKELY_TRUE" if score >= 0.50 else "LIKELY_FALSE"

        block["correctness_score"] = score
        block["correctness_label"] = label
        correctness_scores[b_id] = score
        correctness_labels[b_id] = label
        trust_scores_map[b_id] = block["trust_score"]

        icon = "✅" if label == "LIKELY_TRUE" else ("❓" if label == "UNCERTAIN" else "❌")
        print(f"  {b_id} trust={block['trust_score']:.3f} → score={score:.3f} → {label} {icon}")

    # Phase 4: Build Verified Pool
    trusted_blocks = [b["id"] for b in content_blocks if b["correctness_label"] == "LIKELY_TRUE"]
    uncertain_blocks = [b["id"] for b in content_blocks if b["correctness_label"] == "UNCERTAIN"]
    false_flagged_blocks = [b["id"] for b in content_blocks if b["correctness_label"] == "LIKELY_FALSE"]

    conflict_count = len(conflicts)
    resolved_count = sum(1 for c in conflicts if c.get("python_resolution") not in ("unresolved", None))
    unresolved_count = conflict_count - resolved_count

    print(f"\n[FlagAgent] Done — {len(trusted_blocks)} trusted, {len(uncertain_blocks)} uncertain, {len(false_flagged_blocks)} false-flagged")
    print(f"[FlagAgent] Conflicts: {conflict_count} detected, {resolved_count} resolved, {unresolved_count} unresolved")

    flag_summary = {
        "total_blocks": len(content_blocks),
        "trusted": len(trusted_blocks),
        "uncertain": len(uncertain_blocks),
        "false_flagged": len(false_flagged_blocks),
        "conflicts_detected": conflict_count,
        "conflicts_resolved": resolved_count,
        "conflicts_unresolved": unresolved_count
    }

    return {
        "verified_pool": {
            "trusted_blocks": trusted_blocks,
            "uncertain_blocks": uncertain_blocks,
            "false_flagged_blocks": false_flagged_blocks
        },
        "correctness_scores": {
            k: {"score": correctness_scores[k], "label": correctness_labels[k]}
            for k in correctness_scores
        },
        "conflicts": conflicts,
        "false_flags": false_flags,
        "flag_summary": flag_summary,
        "pipeline_state": {
            "trust_scores": trust_scores_map,
            "correctness_scores": correctness_scores,
            "correctness_labels": correctness_labels,
        },
        "agent_reasoning": (
            f"{conflict_count} conflict(s) detected via LLM analysis. "
            f"{len(false_flagged_blocks)} source(s) false-flagged. "
            f"{len(trusted_blocks)} of {len(content_blocks)} sources pass to Stage 3."
        ),
        "information_quality_summary": {
            "overall_data_quality": round(sum(correctness_scores.values()) / len(correctness_scores), 3) if correctness_scores else 0,
            "conflicting_sources": conflict_count,
            "false_flagged_count": len(false_flagged_blocks),
            "trusted_count": len(trusted_blocks),
            "recommendation": (
                "Proceed with caution — conflicts detected and resolved"
                if conflict_count > 0 else "All sources clear."
            )
        }
    }
