# 🌊 Thinking Stream — Live AI Narrative Feed

## Overview

| Property | Value |
|---|---|
| **File** | `api/stream.py` |
| **Protocol** | Server-Sent Events (SSE) |
| **Endpoint** | `GET /api/v1/stream/{job_id}` |
| **Content-Type** | `text/event-stream` |
| **Queue** | `asyncio.Queue` — shared between all agents and the SSE endpoint |
| **Language** | Super-human, first-person, narrative — NOT logs |

---

## What It Is

The Thinking Stream is a real-time feed of the AI's internal reasoning narrated in plain English. Every agent emits "thoughts" as it works — the client receives them instantly via SSE.

This is NOT:
- System logs (no timestamps, no stack traces)
- JSON data (no schema, no fields)
- Summaries (not written after the fact)

This IS:
- First-person narration ("I'm reading... I noticed... I decided...")
- Real-time (emitted WHILE each agent processes, not after)
- Human-readable (a 10-year-old should understand it)
- Opinionated (the AI expresses uncertainty, surprise, confidence)

---

## Implementation Architecture

```
orchestrator.run_pipeline()
│
│  creates: thought_queue = asyncio.Queue()
│  passes thought_queue to every agent as parameter
│
├── Agent 1a, 1b, 1c, 1d, 1e (parallel)
│     Each calls: await emit(queue, agent, step, type, thought)
│
├── Agent 2 (Flag)
│     Calls emit() before/after each Python decision
│     Calls emit() after each DeepSeek explanation
│
├── ... (all agents)
│
└── SSE endpoint (GET /api/v1/stream/{job_id})
      async for thought in queue:
          yield f"data: {json.dumps(thought)}\n\n"
      when pipeline.done:
          yield "event: done\ndata: {}\n\n"
```

---

## Thought Event Schema

```json
{
  "job_id": "job_a3f92b1c",
  "stage": 2,
  "agent": "FlagAgent",
  "type": "conflict",
  "emoji": "⚡",
  "thought": "Wait — the internal memo says 15% cuts, but Reuters says 25%. These two sources are directly contradicting each other. I need to figure out which one to believe.",
  "timestamp": "2026-05-16T08:50:12Z"
}
```

---

## Thought Types

| Type | Emoji | When | Tone |
|---|---|---|---|
| `start` | 🔍 | Agent begins | Focused, scanning |
| `observation` | 💭 | Notices data | Curious, analytical |
| `decision` | ✅ | Makes a choice | Confident, clear |
| `conflict` | ⚡ | Finds contradiction | Surprised, investigative |
| `action` | 🚀 | Executing a step | Active, purposeful |
| `warning` | ⚠️ | Something wrong | Alert, concerned |
| `recovery` | 🔄 | Fixing failure | Determined, resourceful |
| `result` | ✅ | Step complete | Satisfied, summary |
| `done` | 🎯 | Pipeline finished | Conclusive, proud |
| `false_flag` | 🚨 | False info found | Serious, cautionary |

---

## Full Thought Stream — Demo Scenario

### Stage 1 — Parallel Parsers

```
🔍 [Stage 1]   "Starting all 5 parsers simultaneously — reading PDF, scraping Reuters, parsing stock data, checking analyst API, and scanning social feeds all at once."

💭 [Agent 1a]  "Reading the TechCorp internal memo... it's a 2-page PDF. The key line: 'We will be reducing our global workforce by 15%.' Interesting. Let me note the date — this was written on May 13th, three days ago."

💭 [Agent 1b]  "Scraping the Reuters article... good — it loaded cleanly, no paywall. Reuters is citing three independent sources saying the cut is 25%. That's a very different number from the memo."

💭 [Agent 1c]  "Parsing the stock price CSV. Five days of data. Price started at $162.00 and ended at $133.00. That's an 18% drop. And volume is up 160% — a lot of people are selling."

💭 [Agent 1d]  "Parsing the analyst API response. Three analysts downgraded in 48 hours. Goldman Sachs cut their target from $180 to $120. That's a 33% slash. Wall Street is not happy."

💭 [Agent 1e]  "Scanning the social feed. 847 posts in 6 hours mentioning TechCorp. The #1 topic: employees saying they're updating their resumes. That's a pre-announcement panic signal."

✅ [Stage 1]   "All 5 sources parsed in 1.5 seconds. Ready for fact-checking."
```

### Stage 2 — Flag Agent

```
🔍 [Stage 2]   "Time to figure out what's actually true here. I'm going to score each source by how much I should trust it."

💭 [Stage 2]   "The Reuters article: published today, from reuters.com — credibility 0.85, recency 1.0. Trust score: 0.85. That's high."

💭 [Stage 2]   "The internal memo: unverified leak, 3 days old. Credibility 0.45, recency 0.70. Trust score: 0.315. Much lower."

⚡ [Stage 2]   "Found a conflict. The memo says 15% cuts. Reuters says 25%. Same company, same event, completely different numbers. They can't both be right."

💭 [Stage 2]   "Comparing trust scores: memo=0.315 vs Reuters=0.850. Margin of 0.535 — that's well above my 0.20 threshold for a clear winner. Reuters wins."

🚨 [Stage 2]   "Flagging the memo's 15% claim as LIKELY FALSE. Correctness score: 0.158. This number will NOT appear in any output or recommendation. If we published it, we'd be spreading misinformation."

✅ [Stage 2]   "Done. 4 sources verified as LIKELY_TRUE. 1 false-flagged. Conflict resolved. Passing only clean data to the insight stage."
```

### Stage 3 — Insight Agent

```
🔍 [Stage 3]   "Now I'm looking at the verified facts and asking: what does this actually mean? Not what happened — but why it matters and what it signals."

💭 [Stage 3]   "Here's what I see: 25% layoffs, 18% stock drop, 160% volume spike, 3 analyst downgrades, and 400% employee panic on social media — all happening at the same time. This isn't a routine restructuring. This is a simultaneous collapse of investor, analyst, and employee confidence."

💭 [Stage 3]   "The volume spike is suspicious. When price falls but volume surges like this, it usually means large holders are exiting — institutional investors who know something. The leaked memo circulated 3 days ago. It's possible the memo reached financial circles before retail investors knew."

💭 [Stage 3]   "The social media data is the most alarming signal. Employees are publicly searching for jobs BEFORE the official announcement. That means internal management has already been communicating this informally. The announcement is a formality — this is already in motion."

✅ [Stage 3]   "3 insights extracted. This is a systemic confidence crisis, not a cost-cutting exercise. Confidence: 82%."
```

### Stage 4 — Plan Agent

```
🔍 [Stage 4]   "We have a clear picture of what's happening. Now I need to figure out what to do about it — within the given constraints."

💭 [Stage 4]   "First and most urgent: the investment team needs to know right now. Not in an hour. Right now. An email alert with the verified facts — not the memo number, only the Reuters-confirmed 25%."

💭 [Stage 4]   "Second: we need to publish a formal investor brief. The team will want something they can forward to clients. I'll use the investor portal API."

💭 [Stage 4]   "Third: portfolio dashboard needs to flag TechCorp as CRISIS_WATCH so every portfolio manager sees it at a glance."

💭 [Stage 4]   "Fourth: trigger deep due diligence. We need a proper analysis of TechCorp's position, cash runway, and recovery scenarios."

💭 [Stage 4]   "Fifth: set up hourly monitoring so we catch any new developments — earnings update, official statement, further analyst reactions — immediately."

✅ [Stage 4]   "5-action plan ready. All feasible within constraints. No budget required. Estimated resolution: 4 hours."
```

### Stage 5 — Execution Agent

```
🔍 [Stage 5]   "Executing the plan now. Step by step."

🚀 [Stage 5]   "Step 1: Sending critical alert to the investment team..."
✅ [Stage 5]   "Alert sent. 8 team members reached. Message ID: alert_7741."

🚀 [Stage 5]   "Step 2: Publishing investor brief to the portal..."
⚠️ [Stage 5]   "The investor portal API isn't responding. It's been 5 seconds — that's a timeout."
💭 [Stage 5]   "Step 4 is now blocked. It depends on this step completing. I need recovery to take over."

🚀 [Stage 5]   "Step 3: Flagging TechCorp in the portfolio dashboard..."
✅ [Stage 5]   "Done. Flag set to CRISIS_WATCH, risk level HIGH."

⏭ [Stage 5]   "Step 4 skipped — waiting on step 2 to be recovered."

🚀 [Stage 5]   "Step 5: Setting up hourly monitoring..."
✅ [Stage 5]   "Monitoring job created. Next check in 1 hour, active for 24 hours."

✅ [Stage 5]   "3 done, 1 failed, 1 blocked. Handing the failure to Recovery."
```

### Stage 6 — Recovery Agent

```
🔍 [Stage 6]   "The investor portal timed out. Let me figure out how to fix this."

💭 [Stage 6]   "Timeout errors are usually temporary — a server hiccup. Worth retrying before giving up."

⚠️ [Stage 6]   "Retry 1: still timing out after 5 seconds."
⚠️ [Stage 6]   "Retry 2: still timing out. The portal is definitely down."

💭 [Stage 6]   "But I have a fallback: send the brief as an email attachment. It actually reaches more people — 12 recipients vs 8 portal users."

🔄 [Stage 6]   "Sending brief via email fallback..."
✅ [Stage 6]   "Brief delivered. 12 recipients. ID: brief_email_4492. This actually has wider reach than the portal would have."

💭 [Stage 6]   "Now I can unblock step 4 — the deep analysis job was waiting on the brief to be published."
🚀 [Stage 6]   "Triggering deep due diligence analysis..."
✅ [Stage 6]   "Analysis job_9934 started. Completion in 45 minutes."

✅ [Stage 6]   "Fully recovered. Everything is running."
```

### Stage 7 — Reporter

```
🔍 [Stage 7]   "Pulling everything together for the final report."

💭 [Stage 7]   "Before we started: investment team unaware, no brief, portfolio unflagged, no monitoring."
💭 [Stage 7]   "After: 20 people notified, TechCorp flagged as crisis, deep analysis running, monitoring active."
💭 [Stage 7]   "And crucially: the false 15% claim from the leaked memo did not appear in any output. We only published the Reuters-verified 25% figure."

🎯 [Stage 7]   "All 5 actions completed — 1 needed a fallback but it actually reached more people. 20 stakeholders notified. 1 false claim identified and blocked. Portfolio protected. System confidence: 82%."
```

---

## React Native Integration

```javascript
import EventSource from 'react-native-event-source';

const subscribeToThinkingStream = (jobId, onThought, onDone) => {
  const es = new EventSource(
    `http://localhost:8000/api/v1/stream/${jobId}`
  );

  es.onmessage = (event) => {
    const thought = JSON.parse(event.data);
    onThought(thought);  // { stage, agent, type, emoji, thought }
  };

  es.addEventListener('done', () => {
    onDone();
    es.close();
  });

  return es;
};

// Usage:
const stream = subscribeToThinkingStream(
  jobId,
  (thought) => setThoughts(prev => [...prev, thought]),
  ()        => setComplete(true)
);
```

---

## UI Rendering Guide

```
┌──────────────────────────────────────────────────────┐
│  🤖 AI Thinking Live                                  │
├──────────────────────────────────────────────────────┤
│  Stage 1 · Parsing Sources                           │
│  🔍  Starting all 5 parsers simultaneously...        │
│  💭  Reuters says 25% cuts. Memo says 15%.           │
│  ✅  5 sources parsed in 1.5 seconds.                │
│                                                      │
│  Stage 2 · Checking Facts                            │
│  ⚡  Found a conflict — two different numbers!       │
│  🚨  Memo flagged as likely false (score: 0.158)     │
│  ✅  4 sources verified. 1 false claim blocked.      │
│                                                      │
│  Stage 5 · Executing Actions                         │
│  🚀  Publishing investor brief...                    │
│  ⚠️   Portal timed out. Switching to email.          │
│  ✅  Brief sent to 12 recipients via fallback.       │
│                                                      │
│  Stage 7 · Final Report                              │
│  🎯  All done. 20 notified. False claim excluded.    │
└──────────────────────────────────────────────────────┘
```
