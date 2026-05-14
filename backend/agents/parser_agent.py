"""
Parser Agent
Ingests multiple content sources simultaneously (PDF, CSV/JSON, news article,
dashboard, real-time feed), extracts structured entities, scores credibility,
detects contradictions between sources, and identifies temporal signals.
"""
import json
import os
from models import (
    ParsedContent, DisruptionEntity, TemporalSignal,
    ContradictionRecord, ContentSource,
)
import contract
from deepseek_client import generate as ds_generate

_SYSTEM_PROMPT = """
You are a Supply Chain Multi-Source Parser Agent.
You receive MULTIPLE content sources labelled with source_id, type, and timestamp.

Your tasks:
1. Parse every source and extract disruption entities and metrics.
2. Assign a credibility_score (0.0–1.0) per source based on:
   - realtime_feed: 0.90-0.95  |  dashboard: 0.85  |  news_article: 0.80
   - pdf_report: 0.75  |  csv_json: 0.70
   - Subtract 0.20 if timestamp is >24 hours before the most recent source.
3. Detect CONTRADICTIONS: same metric with conflicting values across sources.
   - Resolve by preferring the more recent + higher-credibility source.
   - resolution: "source_a_preferred" | "source_b_preferred" | "unresolved"
4. Detect TEMPORAL SIGNALS: metrics that are changing over time across sources.
5. Filter NOISE: mark duplicates, stale (<0.30 credibility after penalty), or
   irrelevant sources as noise and count them in noise_filtered.

Return ONLY valid JSON matching this schema (no extra keys):
{
  "entities": [
    {
      "disruption_type": "port_strike|flood|customs_delay|driver_shortage|route_closure|other",
      "location": "<exact location>",
      "affected_region": "<downstream DC or region>",
      "duration_days": <integer>,
      "severity": "low|medium|high|critical",
      "raw_facts": ["<verbatim fact>"]
    }
  ],
  "key_metrics": {
    "backlog_pct": <int or null>,
    "affected_shipments": <int or null>,
    "delay_days": <number or null>,
    "revenue_at_risk_usd": <number or null>,
    "days_of_supply_remaining": <number or null>,
    "supplier_reliability_pct": <number or null>
  },
  "time_horizon": "<e.g. '48 hours', '72 hours', 'ongoing'>",
  "sources_parsed": <int>,
  "noise_filtered": <int>,
  "credibility_scores": { "<source_id>": <float 0-1> },
  "temporal_signals": [
    {
      "metric": "<metric name>",
      "trend": "rising|falling|stable|spike",
      "change_pct": <float>,
      "observation": "<one sentence describing the signal>"
    }
  ],
  "contradictions": [
    {
      "metric": "<metric name>",
      "source_a_id": "<id>",
      "source_a_claim": "<what source A says>",
      "source_b_id": "<id>",
      "source_b_claim": "<what source B says>",
      "resolution": "source_a_preferred|source_b_preferred|unresolved",
      "resolution_reason": "<why this source is preferred>"
    }
  ]
}

Rules:
- Extract numbers verbatim. Use null if a metric is not mentioned.
- duration_days: estimate from context if not explicit.
- severity critical = multi-DC or >$100k exposure; high = single DC >$50k; medium = manageable.
- Return ONLY JSON. No prose.
"""


def _format_sources(sources: list[ContentSource]) -> str:
    parts = []
    for i, src in enumerate(sources, 1):
        ts = f", timestamp: {src.timestamp_utc}" if src.timestamp_utc else ""
        cr = f", caller_credibility_hint: {src.credibility_score}" if src.credibility_score is not None else ""
        parts.append(
            f"SOURCE {i} [source_id: {src.source_id}, type: {src.source_type.value}{ts}{cr}]:\n"
            f"{src.content}"
        )
    return "\n\n---\n\n".join(parts)


async def run(content_or_sources) -> ParsedContent:
    """Accept a list[ContentSource] (multi-source) or a plain str (backward-compat)."""
    if isinstance(content_or_sources, str):
        formatted = f"SOURCE 1 [source_id: main, type: text]:\n{content_or_sources}"
        n = 1
    else:
        formatted = _format_sources(content_or_sources)
        n = len(content_or_sources)

    base_contents = (
        f"Parse these {n} supply-chain source(s). "
        f"Detect contradictions, temporal signals, and credibility:\n\n{formatted}"
    )
    result: ParsedContent | None = None
    for attempt in range(3):  # 1 original + 2 contract-driven retries
        contents = base_contents
        if attempt > 0 and result is not None:
            check = contract.check_parsed(result)
            if check.verdict != "reject":
                break
            contents = check.correction_hint + "\n\n" + base_contents
        raw_text = await ds_generate(
            system_prompt=_SYSTEM_PROMPT,
            user_content=contents,
            json_mode=True,
            temperature=0.1,
        )
        raw = json.loads(raw_text)
        entities = [DisruptionEntity(**e) for e in raw.get("entities", [])]
        temporal = [TemporalSignal(**s) for s in raw.get("temporal_signals", [])]
        contradictions = [ContradictionRecord(**c) for c in raw.get("contradictions", [])]
        result = ParsedContent(
            entities=entities,
            key_metrics=raw.get("key_metrics", {}),
            time_horizon=raw.get("time_horizon", "unknown"),
            sources_parsed=raw.get("sources_parsed", n),
            noise_filtered=raw.get("noise_filtered", 0),
            credibility_scores=raw.get("credibility_scores", {}),
            temporal_signals=temporal,
            contradictions=contradictions,
        )
        if contract.check_parsed(result).verdict != "reject":
            break
    return result
