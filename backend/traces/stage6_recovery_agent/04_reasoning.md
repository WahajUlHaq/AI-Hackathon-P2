# Reasoning

- **Fallback Execution**: When the primary mechanism (`investor_portal_api`) fails due to a timeout, a resilient system must rely on a secondary mechanism to fulfill the action's intent. Sending an email draft fulfills the `PUBLISH` intent, albeit via a different medium.
- **State Reconciliation**: Recovering an action means we must also update the state of dependent actions. `act_004` was correctly skipped in Stage 5, but its blockage is removed once the recovery logic satisfies the dependency requirement.
- **Auditability**: We explicitly log the `fallback_used` and the result to ensure full transparency of the system's fault-tolerance mechanisms, proving to auditors that the failure was gracefully handled.
