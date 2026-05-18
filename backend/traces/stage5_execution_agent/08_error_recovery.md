# Error Recovery

### Detected Error
- **Action**: `act_002` (Publish Investor Brief)
- **Error Type**: `API_TIMEOUT`
- **Context**: Endpoint `/investor-portal/briefs` failed to respond within limits.

### Impact Analysis
- Action `act_004` (Trigger Deep Due Diligence Analysis) is blocked.
- Brief delivery is stalled.

### Hand-off to Stage 6
- `requires_recovery` flag successfully set to `true`.
- Fallback route identified in action plan: "Send as formatted email attachment to distribution list".
- Stage 6 (Recovery Agent) will consume this failure and trigger the fallback strategy.
