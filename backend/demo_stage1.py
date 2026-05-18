"""
demo_stage1.py — Exercise all 5 Stage 1 parser agents
======================================================
Run:  python demo_stage1.py
"""

import json
import sys
import os

# Make sure the project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from agents.stage1.runner import run

# ---------------------------------------------------------------------------
# Demo sources — matching the spec examples exactly
# ---------------------------------------------------------------------------

CSV_CONTENT = """\
Date,Close_Price,Volume
2026-05-12,162.00,8200000
2026-05-13,155.00,11400000
2026-05-14,148.00,14100000
2026-05-15,140.00,18700000
2026-05-16,133.00,21300000
"""

JSON_CONTENT = json.dumps([
    {
        "analyst": "Goldman Sachs",
        "rating": "SELL",
        "previous_target": 180,
        "new_target": 120,
        "date": "2026-05-16"
    },
    {
        "analyst": "Morgan Stanley",
        "rating": "UNDERWEIGHT",
        "previous_target": 175,
        "new_target": 115,
        "date": "2026-05-16"
    },
    {
        "analyst": "JP Morgan",
        "rating": "NEUTRAL",
        "previous_target": None,
        "new_target": 130,
        "date": "2026-05-16"
    },
])

FEED_CONTENT = json.dumps([
    {"text": "Just got laid off from TechCorp after 6 years. Updating my resume. #TechCorp #layoffs", "author": "employee_a"},
    {"text": "TechCorp stock crash incoming — sell everything. $TC", "author": "trader_1"},
    {"text": "847 posts about TechCorp layoffs confirmed in the last 6 hours #opentowork", "author": "analyst_bot"},
    {"text": "TechCorp job search group now has 312 members. Worried about my position.", "author": "employee_b"},
    {"text": "Stock sell-off accelerating. TechCorp down 17% in 5 days. Avoid.", "author": "fin_news"},
    {"text": "Updating my resume tonight — heard the layoffs are real. #TechLayoffs", "author": "employee_c"},
    {"text": "TechCorp layoffs confirmed — 156 posts mentioning stock sell-off today", "author": "news_aggregator"},
    {"text": "Looking for opportunities after TechCorp workforce restructuring news", "author": "employee_d"},
    {"text": "Job search #TechCorp — anyone hiring senior engineers?", "author": "employee_e"},
    {"text": "Worried about my team at TechCorp. Morale is terrible. Layoffs hit hard.", "author": "employee_f"},
    # Pad to simulate 847 posts by repeating patterns
    *[{"text": f"TechCorp layoffs discussion post #{i} — job search", "author": f"user_{i}"} for i in range(837)],
])

# PDF: use inline plain text since no real PDF is available in demo
PDF_DEMO_TEXT = (
    "To: All Department Heads. From: CEO Office. "
    "Subject: Workforce Restructuring. "
    "As part of our cost optimization initiative, we will be reducing our global workforce "
    "by 15%. This decision was finalized on May 12, 2026. "
    "All department heads are required to communicate this internally by May 17, 2026. "
    "Internal Memo — Confidential."
)

SOURCES = [
    {
        "label"      : "TechCorp Internal Memo",
        "type"       : "PDF",
        # We pass the raw text encoded as bytes so the agent can handle it,
        # but since this is a demo without a real PDF we inject via a trick:
        # the agent will fail to open it as file/base64 and mark it noise.
        # Override: we monkey-patch for demo purposes below.
        "content"    : "demo_placeholder",
        "received_at": "2026-05-13T10:00:00Z",
    },
    {
        "label"      : "Reuters — TechCorp Layoffs Report",
        "type"       : "URL",
        "content"    : "https://example.com",   # real scrape; replace with live URL
        "received_at": "2026-05-16T08:30:00Z",
    },
    {
        "label"      : "TechCorp Stock Price — 5 Day History",
        "type"       : "CSV",
        "content"    : CSV_CONTENT,
        "received_at": "2026-05-16T09:00:00Z",
    },
    {
        "label"      : "Analyst Ratings API — TechCorp",
        "type"       : "JSON",
        "content"    : JSON_CONTENT,
        "received_at": "2026-05-16T09:30:00Z",
    },
    {
        "label"      : "LinkedIn/Twitter Sentiment — TechCorp",
        "type"       : "Feed",
        "content"    : FEED_CONTENT,
        "received_at": "2026-05-16T10:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Demo: monkey-patch PDF agent to inject plain text for demo without real PDF
# ---------------------------------------------------------------------------
from agents.stage1 import agent1a_pdf as _pdf_agent

_original_parse = _pdf_agent.parse

def _demo_pdf_parse(source):
    """Override for demo: directly inject the sample text."""
    label       = source.get("label", "Unknown PDF")
    received_at = source.get("received_at", "")
    raw_text    = PDF_DEMO_TEXT
    credibility = _pdf_agent._compute_credibility(raw_text.lower())
    detected_date = _pdf_agent._detect_date(raw_text)
    is_stale    = _pdf_agent._check_stale(detected_date or received_at[:10])
    word_count  = len(raw_text.split())
    return {
        "source_type"       : "PDF",
        "source_label"      : label,
        "raw_text"          : raw_text,
        "timestamp"         : received_at,
        "credibility_score" : credibility,
        "domain"            : "news",
        "is_stale"          : is_stale,
        "is_noise"          : False,
        "noise_reason"      : None,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : "pdfplumber",
        "metadata"          : {
            "pages"         : 2,
            "author"        : "CEO Office",
            "has_tables"    : False,
            "detected_date" : detected_date,
            "fallback_used" : False,
            "stale_reason"  : None,
        },
    }

_pdf_agent.parse = _demo_pdf_parse   # patch for demo


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = run(SOURCES)

    print("=" * 60)
    print("FULL CONTENT BLOCKS (JSON)")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
