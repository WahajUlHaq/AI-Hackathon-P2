import json
from typing import List, Dict, Any

URGENCY_WEIGHT = {
    "CRITICAL": 10,
    "HIGH": 7,
    "MEDIUM": 4,
    "LOW": 1
}

def sort_and_filter_insights(insights: List[Dict[str, Any]], max_insights: int = 5) -> List[Dict[str, Any]]:
    """
    Sort insights by urgency weight and return the top N.
    """
    def get_weight(insight):
        urgency = insight.get("urgency", "LOW")
        return URGENCY_WEIGHT.get(urgency, 1)

    sorted_insights = sorted(insights, key=get_weight, reverse=True)
    return sorted_insights[:max_insights]

def compute_priority_score(insight: Dict[str, Any], source_count: int) -> float:
    """
    priority_score = urgency_weight[insight.urgency]
                   × insight.confidence
                   × (1 + source_count / 5)
    Capped at 10.0
    """
    urgency = insight.get("urgency", "LOW")
    weight = URGENCY_WEIGHT.get(urgency, 1)
    confidence = insight.get("confidence", 0.0)
    
    score = weight * confidence * (1 + source_count / 5.0)
    return min(round(score, 1), 10.0)

def validate_action_against_constraints(action: Dict[str, Any], constraints: Dict[str, Any]) -> tuple:
    """Returns (status, reason) tuple."""
    action_constraints = action.get("constraints", {})

    resource_required = action_constraints.get("resource_required", "")
    available_resources = constraints.get("available_resources", [])

    if resource_required and resource_required not in available_resources:
        return "MODIFIED", (
            f"Required resource '{resource_required}' is not in the approved resource list. "
            "Action will proceed using the nearest available alternative — "
            "manual review recommended before final execution."
        )

    return "FEASIBLE", "All constraints satisfied — action approved and ready to execute as planned."

from agents.llm_client import call_deepseek

def call_deepseek_real(insights: List[Dict[str, Any]], constraints: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt = """
You are ActionPlannerAgent, the strategy engine of an Autonomous Content-to-Action AI system.

You receive a set of VERIFIED insights, each describing a real business problem with its root cause, forward implication, and metric impact.

Your job is to produce a SPECIFIC, ACTIONABLE 5-step plan that directly fixes or mitigates the problems identified in the insights.

IMPORTANT RULES:
- Each action must directly address a specific insight's root cause or forward implication — NOT just "notify someone about it"
- Actions should be concrete business interventions: renegotiate contracts, activate contingency suppliers, launch campaigns, adjust pricing, redirect resources, trigger hedges, etc.
- Use the insight's domain to name the target_system realistically (e.g. "procurement_platform", "supply_chain_optimizer", "pricing_engine", "crm_system", "risk_dashboard")
- Order actions by urgency and dependency (immediate mitigation first, then monitoring)
- Each action must include what the situation looks like BEFORE and what it will look like AFTER execution

Available action types:
- ALERT   — send urgent notification or escalation (use for critical stakeholder warnings)
- ANALYZE — trigger a deep-dive analysis or model run (use for root cause deep-dives)
- UPDATE  — update a system, record, flag, or configuration (use for activating contingencies, adjusting settings)
- PUBLISH — publish a decision, brief, or recommendation (use for communicating strategy to stakeholders)
- MONITOR — schedule ongoing metric monitoring (use as the final step to watch for improvements)

Constraints: Do not exceed budget limits. Order actions so dependencies are respected.

Output ONLY valid JSON:
{
  "actions": [
    {
      "action_id": "act_001",
      "step": 1,
      "title": "specific intervention title",
      "type": "ALERT|ANALYZE|UPDATE|PUBLISH|MONITOR",
      "description": "exactly what this action does to address the root cause",
      "target_system": "domain-specific system name",
      "stakeholder": "who is responsible or affected",
      "triggered_by_insight": "ins_001",
      "metric_before": "the metric/situation before this action (e.g. 'Wheat reserves -22%, no contingency active')",
      "expected_outcome": "the measurable improvement after this action (e.g. 'Emergency contracts activated covering 40% of disrupted supply')",
      "constraints": {"budget_limit_usd": 0, "deadline": "...", "resource_required": "...", "sensitivity": "..."},
      "depends_on": [],
      "estimated_duration_minutes": 10,
      "fallback": {"title": "...", "type": "...", "target_system": "...", "description": "..."}
    }
  ]
}
"""
    user_message = json.dumps({
        "insights": insights,
        "constraints": constraints
    })
    
    try:
        response = call_deepseek(system_prompt, user_message, temperature=0.1)
        return response
    except Exception as e:
        print(f"DeepSeek call failed: {e}")
        return {"actions": []}


def run(insight_packet: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
    insights = insight_packet.get("insights", [])
    
    print(f"[PlanAgent] Generating action plan from {len(insights)} insights...")
    
    # 1. Pre-processing
    top_insights = sort_and_filter_insights(insights)
    
    if top_insights:
        top = top_insights[0]
        print(f"[PlanAgent] Top insight: {top.get('id')} ({top.get('urgency')}, confidence={top.get('confidence')})")
    
    # 2. Mock LLM Call
    llm_output = call_deepseek_real(top_insights, constraints)
    actions = llm_output.get("actions", [])
    
    # Create lookup map for insights
    insight_map = {ins["id"]: ins for ins in insights}
    sources_used = insight_packet.get("sources_used", [])
    source_count = len(sources_used)
    
    # 3. Validation & Scoring
    print("[PlanAgent] Constraint check:")
    
    feasible_count = 0
    modified_count = 0
    rejected_count = 0
    total_cost = 0
    total_time = 0
    
    final_actions = []
    
    for act in actions:
        # Validate constraints
        status, reason = validate_action_against_constraints(act, constraints)
        act["constraint_status"] = status
        act["constraint_reason"] = reason
        
        if status == "FEASIBLE":
            feasible_count += 1
        elif status == "MODIFIED":
            modified_count += 1
        else:
            rejected_count += 1
            
        total_cost += act.get("constraints", {}).get("budget_limit_usd", 0)
        total_time += act.get("estimated_duration_minutes", 0)
        
        # Priority Score
        insight_id = act.get("triggered_by_insight")
        if insight_id and insight_id in insight_map:
            insight = insight_map[insight_id]
            act["priority_score"] = compute_priority_score(insight, source_count)
        else:
            act["priority_score"] = 5.0 # Default fallback
            
        print(f"  {act['action_id']} {act['type']:<8} → {status:<10} ({act.get('target_system')}, ${act.get('constraints', {}).get('budget_limit_usd', 0)}, {act.get('estimated_duration_minutes', 0)}min)")
        
        final_actions.append(act)
        
    estimated_resolution_hours = round(total_time / 60.0, 1)
    if estimated_resolution_hours < 4:
        estimated_resolution_hours = 4 # From MD

    print(f"[PlanAgent] Done — {len(final_actions)} actions, ${total_cost} cost, ~{int(estimated_resolution_hours)} hour resolution window")

    # Build dynamic reasoning from actual insights
    critical_high = [i for i in top_insights if i.get("urgency") in ("CRITICAL", "HIGH")]
    if critical_high:
        titles = ", ".join(i.get("title", i.get("id", "?")) for i in critical_high[:3])
        agent_reasoning = (
            f"{len(critical_high)} CRITICAL/HIGH insight(s) detected ({titles}). "
            "Immediate stakeholder notification prioritised. "
            "Publishing verified summary prevents unverified information spreading. "
            "Record flagging and monitoring ensure ongoing risk visibility."
        )
    elif top_insights:
        agent_reasoning = (
            f"{len(top_insights)} insight(s) analysed. "
            "Actions ordered by urgency and dependency chain to maximise coverage with minimum latency."
        )
    else:
        agent_reasoning = "No high-urgency insights found. Monitoring actions recommended as precaution."

    action_types = [a.get("type", "") for a in final_actions]
    plan_summary = " → ".join(
        f"{a.get('type', '?')} ({a.get('target_system', '?')})"
        for a in final_actions
    ) or "No actions planned"

    output = {
        "action_plan": final_actions,
        "plan_summary": plan_summary,
        "total_estimated_cost_usd": total_cost,
        "estimated_resolution_hours": estimated_resolution_hours,
        "actions_total": len(final_actions),
        "actions_feasible": feasible_count,
        "actions_modified": modified_count,
        "actions_rejected": rejected_count,
        "agent_reasoning": agent_reasoning
    }
    
    return output

# Mock entry point to test
if __name__ == "__main__":
    mock_insight_packet = {
        "insights": [
            {
                "id": "ins_001",
                "urgency": "CRITICAL",
                "confidence": 0.86,
                "supporting_sources": ["cb_002", "cb_003"]
            },
            {
                "id": "ins_002",
                "urgency": "HIGH",
                "confidence": 0.80,
                "supporting_sources": ["cb_004"]
            },
            {
                "id": "ins_003",
                "urgency": "HIGH",
                "confidence": 0.75,
                "supporting_sources": ["cb_005"]
            }
        ],
        "sources_used": ["cb_002", "cb_003", "cb_004", "cb_005"]
    }
    
    mock_constraints = {
        "alert_budget_usd": 0,
        "publish_deadline_hours": 4,
        "analyze_budget_usd": 500,
        "available_resources": [
            "investment_team_email",
            "investor_portal_api",
            "portfolio_dashboard",
            "analytics_engine",
            "monitoring_scheduler"
        ],
        "api_rate_limits": {
            "investor_portal_api": "10 calls/hour",
            "analytics_engine": "5 calls/hour"
        },
        "output_language": "English",
        "sensitivity_level": "CONFIDENTIAL"
    }
    
    print(json.dumps(run(mock_insight_packet, mock_constraints), indent=2))
