# Decisions

- **DECISION 1**: Triggered fallback logic for `act_002`.
  - *Rationale*: Stage 5 explicitly flagged this action with `requires_recovery=True`.
- **DECISION 2**: Used `email_draft` as the target system instead of retrying `investor_portal_api`.
  - *Rationale*: A timeout on the portal API suggests an infrastructure issue. Retries might exacerbate the problem, so switching to an entirely different delivery mechanism (email) is the safest fallback.
- **DECISION 3**: Flagged `act_004` as `UNBLOCKED`.
  - *Rationale*: Since the brief content was successfully delivered via the fallback, the analytical system can now proceed with its deep due diligence using the distributed brief.
