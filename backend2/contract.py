"""
Contract Enforcement Layer (AMCE-Inspired)

Validates every agent's output before it passes to the next stage.
Verdict: PASS | WARN | REJECT

On REJECT the calling agent re-generates with a correction hint injected
into the prompt (up to 2 retries). WARN lets the output pass but records
the issues in the returned ContractResult so the SSE trace can surface them.

Checks performed per agent:
  parser  → content non-empty, sources actually processed, contradiction IDs valid
  insight → at least 1 causal chain, exposure > 0, contradictions resolved
  plan    → 3-5 actions, primary_action_id exists, no self-referencing depends_on
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Any

from models import ParsedContent, Insight, ActionPlan


@dataclass
class ContractResult:
    verdict: Literal["pass", "warn", "reject"]
    issues: list[str] = field(default_factory=list)
    correction_hint: str = ""


# ── Parser contract ───────────────────────────────────────────────────────────

def check_parsed(p: ParsedContent) -> ContractResult:
    issues: list[str] = []

    if p.sources_parsed == 0:
        issues.append("sources_parsed is 0 — no source was processed")

    has_content = bool(p.entities) or any(
        v is not None for v in p.key_metrics.values()
    )
    if not has_content:
        issues.append(
            "entities list is empty AND all key_metrics are null "
            "— no useful data was extracted from the sources"
        )

    if p.sources_parsed > 0 and p.noise_filtered >= p.sources_parsed:
        issues.append(
            f"All {p.sources_parsed} source(s) were marked as noise "
            "— review source quality or lower noise threshold"
        )

    for c in p.contradictions:
        if not c.source_a_id or not c.source_b_id:
            issues.append(
                f"Contradiction on '{c.metric}' is missing source IDs — fill source_a_id and source_b_id"
            )

    if not issues:
        return ContractResult(verdict="pass")

    is_reject = not has_content or p.sources_parsed == 0
    hint = (
        f"CONTRACT REJECT — your previous output failed validation. "
        f"Issues: {'; '.join(issues)}. "
        "Extract at least one entity or one non-null key_metric. "
        "Return valid JSON only."
    )
    return ContractResult(
        verdict="reject" if is_reject else "warn",
        issues=issues,
        correction_hint=hint,
    )


# ── Insight contract ──────────────────────────────────────────────────────────

def check_insight(i: Insight, p: ParsedContent) -> ContractResult:
    issues: list[str] = []

    if not i.causal_chains:
        issues.append("causal_chains is empty — produce at least 1 causal chain")

    if i.total_exposure_usd <= 0:
        issues.append(
            "total_exposure_usd is 0 — compute a realistic dollar exposure "
            "(use PKR/USD 278, $45/pallet/day holding, $0.50/pallet/day SLA penalty)"
        )

    for chain in i.causal_chains:
        if chain.financial_impact_usd <= 0:
            issues.append(
                f"Causal chain '{chain.cause[:50]}...' has zero financial_impact_usd"
            )
            break  # one warning is enough

    if p.contradictions and not i.contradiction_resolutions:
        issues.append(
            f"{len(p.contradictions)} contradiction(s) were detected by the parser "
            "but contradiction_resolutions is empty — explain each resolution"
        )

    if not issues:
        return ContractResult(verdict="pass")

    is_reject = not i.causal_chains or i.total_exposure_usd <= 0
    hint = (
        f"CONTRACT REJECT — your previous output failed validation. "
        f"Issues: {'; '.join(issues)}. "
        "Produce at least 1 causal chain with positive financial_impact_usd. "
        "Use realistic logistics figures. Return valid JSON only."
    )
    return ContractResult(
        verdict="reject" if is_reject else "warn",
        issues=issues,
        correction_hint=hint,
    )


# ── Plan contract ─────────────────────────────────────────────────────────────

def check_plan(plan: ActionPlan) -> ContractResult:
    issues: list[str] = []
    action_ids = {a.action_id for a in plan.ranked_actions}

    if len(plan.ranked_actions) < 3:
        issues.append(
            f"Only {len(plan.ranked_actions)} action(s) — must produce 3 to 5 ranked actions"
        )
    elif len(plan.ranked_actions) > 5:
        issues.append(
            f"{len(plan.ranked_actions)} actions — maximum allowed is 5"
        )

    if plan.primary_action_id not in action_ids:
        issues.append(
            f"primary_action_id '{plan.primary_action_id}' not found in ranked_actions "
            f"(valid IDs: {sorted(action_ids)})"
        )

    for a in plan.ranked_actions:
        for dep in (a.depends_on or []):
            if dep == a.action_id:
                issues.append(f"{a.action_id} depends_on itself — circular reference")
            elif dep not in action_ids:
                issues.append(
                    f"{a.action_id} depends_on '{dep}' which is not in the plan"
                )

    if not issues:
        return ContractResult(verdict="pass")

    is_reject = (
        len(plan.ranked_actions) < 3
        or plan.primary_action_id not in action_ids
    )
    hint = (
        f"CONTRACT REJECT — your previous output failed validation. "
        f"Issues: {'; '.join(issues)}. "
        "Produce exactly 3-5 ranked actions. "
        "primary_action_id must match one of the action_ids in ranked_actions. "
        "No action may depend on itself. Return valid JSON only."
    )
    return ContractResult(
        verdict="reject" if is_reject else "warn",
        issues=issues,
        correction_hint=hint,
    )
