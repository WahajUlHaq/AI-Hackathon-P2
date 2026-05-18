# Stage 4 Trace: Agent Reasoning

## Prioritization Logic
- The agent determined that addressing the confidence crisis and volume anomaly took precedence over everything else. The insight `ins_001` (Confidence Crisis) was marked CRITICAL with high confidence (0.86) supported by multiple sources. Thus, the first action must be an ALERT directed to the primary stakeholder: the Investment Team.

## Action Dependencies
- **Publishing (act_002) and Updating (act_003)**: The agent reasoned that it is unsafe to update dashboards or publish briefs externally before the investment team is aware. Therefore, `act_002` and `act_003` are strictly dependent on the completion of `act_001`.
- **Deeper Analysis (act_004)**: Initiating a resource-heavy due diligence analysis is only valuable if the dashboard tracking is active and the preliminary brief is published. Hence, it depends on `act_002` and `act_003`.
- **Monitoring (act_005)**: Monitoring must be instituted immediately after updating the dashboard to track ongoing fallout.

## Fallback Reasoning
- The agent reasoned that if primary communication tools (Email API, Portal API) fail during a crisis window, lower-fidelity but highly reliable alternatives (SMS, direct email drafts, spreadsheet exports) must be instantly actionable to avoid systemic delay.
