# Action Execution

### Action 1 (`act_001`): ALERT
- **Execution**: Mock POST request to `/notifications/email`
- **Result**: Success. Email dispatched. Team alerted.

### Action 2 (`act_002`): PUBLISH
- **Execution**: Mock POST request to `/investor-portal/briefs`
- **Result**: FAILED. API timeout after 5020ms. State unchanged. Requires recovery.

### Action 3 (`act_003`): UPDATE
- **Execution**: Mock PATCH request to `/portfolio/flags`
- **Result**: Success. System flagged. Risk level elevated.

### Action 4 (`act_004`): ANALYZE
- **Execution**: None.
- **Result**: SKIPPED. Downstream dependency (`act_002`) failed.

### Action 5 (`act_005`): MONITOR
- **Execution**: Mock POST request to `/scheduler/jobs`
- **Result**: Success. Job `job_mon_005` created.
