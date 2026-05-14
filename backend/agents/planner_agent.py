"""
Planner Agent
Takes causal insights and produces a ranked action plan with typed parameters
that the Executor Agent can call directly against mock APIs.
"""
import json
from models import ParsedContent, Insight, ActionPlan, RecommendedAction, ActionType, ActionConstraint
import contract
from deepseek_client import generate as ds_generate

_SYSTEM_PROMPT = """
You are a Supply Chain Action Planner Agent.
Given parsed disruption data and causal insights, produce EXACTLY 3 to 5 RANKED,
INTERCONNECTED actions the logistics team must execute NOW.

Available action_type values and required parameters:
  reroute_shipment    → { "from_route_id", "to_route_id", "shipment_count" }
  activate_safety_stock → { "dc" }
  send_notification   → { "notification_type", "recipients", "subject", "body", "priority" }
  update_pricing      → { "region", "multiplier" }
  update_inventory    → { "dc", "sku", "delta" }

For each action you MUST include a constraints block:
  budget_usd          — maximum cost for this action in USD
  deadline_hours      — hours within which this must complete
  max_retries         — 1, 2, or 3
  rollback_on_failure — true if state should be restored on failure

Feasibility rules:
  - If an action violates its own constraints or system limits, set feasibility_status: "infeasible"
    and explain in feasibility_note. The executor will skip infeasible actions.
  - If you modified parameters to fit constraints, set feasibility_status: "modified".
  - Otherwise set feasibility_status: "feasible".

Action interdependency: use depends_on to list action_ids that must succeed first.
Example: notification after reroute should depend on reroute's action_id.

Return ONLY valid JSON:
{
  "ranked_actions": [
    {
      "action_id": "ACT-001",
      "action_type": "<type>",
      "title": "<short title>",
      "description": "<1-2 sentences with numbers>",
      "confidence_pct": <int 0-100>,
      "estimated_savings_usd": <number>,
      "parameters": { ... },
      "constraints": {
        "budget_usd": <number>,
        "deadline_hours": <int>,
        "max_retries": <1|2|3>,
        "rollback_on_failure": <bool>
      },
      "feasibility_status": "feasible|infeasible|modified",
      "feasibility_note": "<string or null>",
      "depends_on": []
    }
  ],
  "primary_action_id": "ACT-001",
  "rationale": "<2-3 sentences explaining prioritisation>",
  "total_budget_usd": <sum of all action budget_usd values>,
  "constraint_violations": ["<description of any infeasible/modified action>"]
}

Rules:
- Rank by estimated_savings_usd × confidence_pct DESC.
- parameters must be complete and verbatim-ready for the executor.
- DC names: lahore_dc, islamabad_dc, karachi_port.
- Route IDs: KHI-LHR-001 (disrupted primary), GWD-LHR-001 (alternate), KHI-ISB-001.
- Recipients for notifications: use ["ops@chainsight.io", "logistics@partner.com"] as defaults.
"""


async def run(parsed: ParsedContent, insight: Insight) -> ActionPlan:
    payload = {
        "parsed": json.loads(parsed.model_dump_json()),
        "insight": json.loads(insight.model_dump_json()),
    }
    base_contents = f"Generate an action plan for this supply chain disruption:\n\n{json.dumps(payload, indent=2)}"
    result: ActionPlan | None = None
    for attempt in range(3):
        contents = base_contents
        if attempt > 0 and result is not None:
            check = contract.check_plan(result)
            if check.verdict != "reject":
                break
            contents = check.correction_hint + "\n\n" + base_contents
        raw_text = await ds_generate(
            system_prompt=_SYSTEM_PROMPT,
            user_content=contents,
            json_mode=True,
            temperature=0.15,
        )
        raw = json.loads(raw_text)
        actions = []
        for a in raw.get("ranked_actions", []):
            try:
                action_type = ActionType(a["action_type"])
            except ValueError:
                action_type = ActionType.send_notification
            constraint = None
            if c := a.get("constraints"):
                constraint = ActionConstraint(
                    budget_usd=c.get("budget_usd", 50000),
                    deadline_hours=c.get("deadline_hours", 24),
                    max_retries=c.get("max_retries", 2),
                    rollback_on_failure=c.get("rollback_on_failure", True),
                )
            actions.append(
                RecommendedAction(
                    action_id=a["action_id"],
                    action_type=action_type,
                    title=a["title"],
                    description=a["description"],
                    confidence_pct=a["confidence_pct"],
                    estimated_savings_usd=a.get("estimated_savings_usd", 0),
                    parameters=a.get("parameters", {}),
                    constraints=constraint,
                    feasibility_status=a.get("feasibility_status", "feasible"),
                    feasibility_note=a.get("feasibility_note"),
                    depends_on=a.get("depends_on", []),
                )
            )
        result = ActionPlan(
            ranked_actions=actions,
            primary_action_id=raw.get("primary_action_id", actions[0].action_id if actions else ""),
            rationale=raw.get("rationale", ""),
            total_budget_usd=raw.get("total_budget_usd", 0.0),
            constraint_violations=raw.get("constraint_violations", []),
        )
        if contract.check_plan(result).verdict != "reject":
            break
    return result
