# Tool Calls

```json
[
  {
    "tool": "POST_API",
    "target": "/notifications/email",
    "payload": {
      "to": "investment-team@firm.com",
      "subject": "CRITICAL: TechCorp Confidence Crisis — Action Required"
    },
    "result": "SUCCESS",
    "duration_ms": 250
  },
  {
    "tool": "POST_API",
    "target": "/investor-portal/briefs",
    "payload": {
      "title": "TechCorp Confidence Crisis — Verified Analysis"
    },
    "result": "TIMEOUT",
    "duration_ms": 5020
  },
  {
    "tool": "PATCH_API",
    "target": "/portfolio/flags",
    "payload": {
      "target": "TechCorp",
      "flag": "CRISIS_WATCH",
      "risk": "HIGH"
    },
    "result": "SUCCESS",
    "duration_ms": 340
  },
  {
    "tool": "POST_API",
    "target": "/scheduler/jobs",
    "payload": {
      "target": "TechCorp",
      "interval": "1h"
    },
    "result": "SUCCESS",
    "duration_ms": 90
  }
]
```
