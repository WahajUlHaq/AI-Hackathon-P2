"""
Insight Agent
Converts parsed supply-chain entities into quantitative, causal insights.
Avoids generic summaries — must produce dollar figures and causal chains.
"""
import json
from models import ParsedContent, Insight, CausalChain  # noqa: F401
import contract
from deepseek_client import generate as ds_generate

_SYSTEM_PROMPT = """
You are a Supply Chain Insight Agent.
You receive structured supply-chain disruption data (already parsed from multiple sources)
and must produce QUANTITATIVE CAUSAL insights, including analysis of contradictions and
temporal trends found by the parser.

CRITICAL rules:
- Every causal chain must state CAUSE → IMMEDIATE EFFECT → DOWNSTREAM EFFECT with dollar figures.
- Use realistic Pakistani logistics figures: PKR-USD at 278; pallet holding ~$45/day; SLA penalty ~$0.50/pallet/day.
- If contradictions exist in the input, explain how they were resolved in contradiction_resolutions.
- If temporal_signals exist, reference them in the causal chains.
- urgency: "immediate" if penalty accrues today; "24h" if exposure < 24h; "48h" or "week" otherwise.

Return ONLY valid JSON matching this schema:
{
  "title": "<1-sentence non-generic title>",
  "causal_chains": [
    {
      "cause": "<root cause, specific>",
      "immediate_effect": "<first-order consequence with numbers>",
      "downstream_effect": "<second-order business consequence with numbers>",
      "financial_impact_usd": <number>,
      "probability_pct": <integer 0-100>
    }
  ],
  "total_exposure_usd": <number>,
  "urgency": "immediate|24h|48h|week",
  "affected_skus": ["<sku1>"],
  "key_risks": ["<risk sentence 1>", "<risk sentence 2>"],
  "contradiction_resolutions": ["<one sentence per contradiction explaining the resolution>"]
}
"""


async def run(parsed: ParsedContent) -> Insight:
    payload = parsed.model_dump_json(indent=2)
    base_contents = f"Generate causal insights from this parsed disruption data:\n\n{payload}"
    result: Insight | None = None
    for attempt in range(3):
        contents = base_contents
        if attempt > 0 and result is not None:
            check = contract.check_insight(result, parsed)
            if check.verdict != "reject":
                break
            contents = check.correction_hint + "\n\n" + base_contents
        try:
            raw_text = await ds_generate(
                system_prompt=_SYSTEM_PROMPT,
                user_content=contents,
                json_mode=True,
                temperature=0.2,
            )
            raw = json.loads(raw_text)
        except Exception:
            continue  # retry on parse or API error
        chains = [CausalChain(**c) for c in raw.get("causal_chains", [])]
        result = Insight(
            title=raw["title"],
            causal_chains=chains,
            total_exposure_usd=raw.get("total_exposure_usd", 0),
            urgency=raw.get("urgency", "immediate"),
            affected_skus=raw.get("affected_skus", []),
            key_risks=raw.get("key_risks", []),
            contradiction_resolutions=raw.get("contradiction_resolutions", []),
        )
        if contract.check_insight(result, parsed).verdict != "reject":
            break
    return result
