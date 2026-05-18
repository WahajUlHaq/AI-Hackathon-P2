"""
Executor Agent
Executes the full 3-5 action chain produced by the Planner.
Per action: captures before/after state, retries on failure (up to max_retries),
rolls back state if rollback_on_failure=True, sends a failure alert as fallback,
and skips actions whose dependencies did not succeed.
"""
import asyncio
import time
import httpx
import state
from models import (
    ActionPlan, ExecutionResult, ExecutionStep, StateSnapshot,
    ChainStepResult, RecommendedAction,
)

BASE_URL = "http://localhost:8000"


def _to_snapshot(s: dict) -> StateSnapshot:
    return StateSnapshot(
        inventory=s["inventory"],
        routes=s["routes"],
        pricing=s["pricing"],
        notifications_count=len(s["notifications"]),
        penalty_exposure_usd=float(s.get("penalty_exposure_usd", 0)),
    )


async def _call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    step_num: int,
    payload: dict | None = None,
    params: dict | None = None,
) -> ExecutionStep:
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = await client.get(f"{BASE_URL}{path}", params=params)
        else:
            r = await client.post(f"{BASE_URL}{path}", json=payload, params=params)
        latency = int((time.monotonic() - t0) * 1000)
        r.raise_for_status()
        return ExecutionStep(
            step=step_num,
            action=f"{method} {path}",
            endpoint=f"{BASE_URL}{path}",
            request_payload=payload or params or {},
            response_payload=r.json(),
            latency_ms=latency,
            success=True,
        )
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        return ExecutionStep(
            step=step_num,
            action=f"{method} {path}",
            endpoint=f"{BASE_URL}{path}",
            request_payload=payload or params or {},
            response_payload={},
            latency_ms=latency,
            success=False,
            error=str(e),
        )


async def _dispatch(
    client: httpx.AsyncClient,
    action: RecommendedAction,
    start_step: int,
) -> list[ExecutionStep]:
    """Dispatch one action to its mock API endpoint(s)."""
    p = action.parameters
    n = start_step
    steps: list[ExecutionStep] = []

    if action.action_type.value == "reroute_shipment":
        steps.append(await _call(
            client, "POST", "/mock/routing/reroute", n,
            payload={
                "from_route_id":  p.get("from_route_id", "KHI-LHR-001"),
                "to_route_id":    p.get("to_route_id",   "GWD-LHR-001"),
                "shipment_count": p.get("shipment_count", 500),
            },
        ))

    elif action.action_type.value == "activate_safety_stock":
        steps.append(await _call(
            client, "POST", "/mock/inventory/safety-stock/activate", n,
            params={"dc": p.get("dc", "lahore_dc")},
        ))

    elif action.action_type.value == "send_notification":
        steps.append(await _call(
            client, "POST", "/mock/notifications/send", n,
            payload={
                "notification_type": p.get("notification_type", "email"),
                "recipients":        p.get("recipients", ["ops@chainsight.io"]),
                "subject":           p.get("subject", "Supply Chain Alert"),
                "body":              p.get("body", "Disruption detected."),
                "priority":          p.get("priority", "high"),
            },
        ))

    elif action.action_type.value == "update_pricing":
        steps.append(await _call(
            client, "POST", "/mock/pricing/update", n,
            payload={
                "region":     p.get("region", "lahore"),
                "multiplier": p.get("multiplier", 1.2),
            },
        ))

    elif action.action_type.value == "update_inventory":
        steps.append(await _call(
            client, "POST", "/mock/inventory/adjust", n,
            payload={
                "dc":    p.get("dc", "lahore_dc"),
                "sku":   p.get("sku", "SKU-A001"),
                "delta": p.get("delta", 0),
            },
        ))

    return steps


async def run_single_action(
    plan: ActionPlan,
    action_id: str,
    completed_ids: set[str],
) -> ChainStepResult:
    """
    Execute ONE action by action_id.
    Called by Antigravity via MCP execute_action tool — one call per action.
    completed_ids: set of action_ids that already succeeded (for depends_on check).
    """
    action = next((a for a in plan.ranked_actions if a.action_id == action_id), None)
    if not action:
        raise ValueError(f"Action {action_id} not found in plan")

    # Skip infeasible
    if action.feasibility_status == "infeasible":
        snap = _to_snapshot(state.snapshot())
        return ChainStepResult(
            action_id=action_id, action_type=action.action_type.value,
            action_title=action.title, status="skipped", attempt=0,
            api_steps=[], state_before=snap, state_after=snap,
            recovery_note="Skipped — marked infeasible by planner.", latency_ms=0,
        )

    # Skip if dependency not met
    if action.depends_on and not all(dep in completed_ids for dep in action.depends_on):
        snap = _to_snapshot(state.snapshot())
        return ChainStepResult(
            action_id=action_id, action_type=action.action_type.value,
            action_title=action.title, status="skipped", attempt=0,
            api_steps=[], state_before=snap, state_after=snap,
            recovery_note=f"Skipped — dependency {action.depends_on} not completed.",
            latency_ms=0,
        )

    max_retries = action.constraints.max_retries if action.constraints else 2
    do_rollback = action.constraints.rollback_on_failure if action.constraints else False
    raw_before = state.snapshot()
    snap_before = _to_snapshot(raw_before)
    t_action = time.monotonic()
    action_steps: list[ExecutionStep] = []
    last_error: str | None = None
    success = False
    attempt = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_retries + 2):
            new_steps = await _dispatch(client, action, len(action_steps) + 1)
            action_steps.extend(new_steps)
            if all(s.success for s in new_steps):
                success = True
                break
            last_error = next((s.error for s in new_steps if not s.success), "unknown")
            if attempt <= max_retries:
                await asyncio.sleep(0.15)

        snap_after = _to_snapshot(state.snapshot())
        latency = int((time.monotonic() - t_action) * 1000)

        if success:
            status = "retried_ok" if attempt > 1 else "success"
            recovery_note = f"Succeeded on attempt {attempt}." if attempt > 1 else None
        else:
            if do_rollback:
                state.restore(raw_before)
                snap_after = _to_snapshot(state.snapshot())
                status = "rolled_back"
                recovery_note = f"Failed after {attempt} attempt(s); state rolled back. Error: {last_error}"
            else:
                status = "failed"
                recovery_note = f"Failed after {attempt} attempt(s): {last_error}. Chain continues."
            # Send failure alert
            alert = await _call(
                client, "POST", "/mock/notifications/send", len(action_steps) + 1,
                payload={
                    "notification_type": "email",
                    "recipients": ["ops@chainsight.io"],
                    "subject": f"ACTION FAILED: {action.title}",
                    "body": f"{action_id} failed after {attempt} attempt(s). Rollback: {do_rollback}. Error: {last_error}",
                    "priority": "critical",
                },
            )
            action_steps.append(alert)

    return ChainStepResult(
        action_id=action_id, action_type=action.action_type.value,
        action_title=action.title, status=status, attempt=attempt,
        api_steps=action_steps, state_before=snap_before, state_after=snap_after,
        error=last_error if not success else None,
        recovery_note=recovery_note, latency_ms=latency,
    )


async def run(plan: ActionPlan) -> ExecutionResult:
    t_total = time.monotonic()
    before_all = _to_snapshot(state.snapshot())
    chain_steps: list[ChainStepResult] = []
    all_api_steps: list[ExecutionStep] = []
    succeeded = 0
    failed = 0
    global_step = 1

    feasible = [a for a in plan.ranked_actions if a.feasibility_status != "infeasible"]
    completed_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for action in feasible:
            raw_snap_now = state.snapshot()

            # ── Skip if a required predecessor did not complete ──────────────
            if action.depends_on and not all(dep in completed_ids for dep in action.depends_on):
                snap = _to_snapshot(raw_snap_now)
                chain_steps.append(ChainStepResult(
                    action_id=action.action_id,
                    action_type=action.action_type.value,
                    action_title=action.title,
                    status="skipped",
                    attempt=0,
                    api_steps=[],
                    state_before=snap,
                    state_after=snap,
                    recovery_note=(
                        f"Skipped — dependency {action.depends_on} did not complete successfully."
                    ),
                    latency_ms=0,
                ))
                continue

            max_retries = action.constraints.max_retries if action.constraints else 2
            do_rollback = action.constraints.rollback_on_failure if action.constraints else False

            snap_before = _to_snapshot(raw_snap_now)
            raw_before  = raw_snap_now   # saved for potential rollback

            t_action = time.monotonic()
            action_steps: list[ExecutionStep] = []
            last_error: str | None = None
            success = False
            attempt = 0

            # ── Retry loop ───────────────────────────────────────────────────
            for attempt in range(1, max_retries + 2):   # +2 → 1 original + retries
                new_steps = await _dispatch(client, action, global_step)
                action_steps.extend(new_steps)
                all_api_steps.extend(new_steps)
                global_step += len(new_steps)

                if all(s.success for s in new_steps):
                    success = True
                    break
                last_error = next((s.error for s in new_steps if not s.success), "unknown error")
                if attempt <= max_retries:
                    await asyncio.sleep(0.15)   # brief pause before retry

            snap_after = _to_snapshot(state.snapshot())
            latency = int((time.monotonic() - t_action) * 1000)

            # ── Outcome ──────────────────────────────────────────────────────
            if success:
                status = "retried_ok" if attempt > 1 else "success"
                recovery_note = f"Succeeded on attempt {attempt}." if attempt > 1 else None
                succeeded += 1
                completed_ids.add(action.action_id)
            else:
                failed += 1
                if do_rollback:
                    state.restore(raw_before)
                    snap_after = _to_snapshot(state.snapshot())
                    status = "rolled_back"
                    recovery_note = (
                        f"Failed after {attempt} attempt(s); state rolled back. "
                        f"Error: {last_error}"
                    )
                else:
                    status = "failed"
                    recovery_note = (
                        f"Failed after {attempt} attempt(s): {last_error}. "
                        "Chain continues with remaining actions."
                    )
                # Side-effect: failure alert notification
                alert = await _call(
                    client, "POST", "/mock/notifications/send", global_step,
                    payload={
                        "notification_type": "email",
                        "recipients": ["ops@chainsight.io"],
                        "subject": f"ACTION FAILED: {action.title}",
                        "body": (
                            f"Action {action.action_id} ({action.action_type.value}) "
                            f"failed after {attempt} attempt(s). Error: {last_error}. "
                            f"Rollback applied: {do_rollback}."
                        ),
                        "priority": "critical",
                    },
                )
                action_steps.append(alert)
                all_api_steps.append(alert)
                global_step += 1

            chain_steps.append(ChainStepResult(
                action_id=action.action_id,
                action_type=action.action_type.value,
                action_title=action.title,
                status=status,
                attempt=attempt,
                api_steps=action_steps,
                state_before=snap_before,
                state_after=snap_after,
                error=last_error if not success else None,
                recovery_note=recovery_note,
                latency_ms=latency,
            ))

    after_all = _to_snapshot(state.snapshot())
    total_ms = int((time.monotonic() - t_total) * 1000)

    # ── Compute chain-level deltas ───────────────────────────────────────────
    primary = plan.ranked_actions[0] if plan.ranked_actions else None
    p = primary.parameters if primary else {}
    src_route = p.get("from_route_id", "KHI-LHR-001")
    dst_route = p.get("to_route_id",   "GWD-LHR-001")
    eta_before = before_all.routes.get(src_route, {}).get("eta_days", 0)
    eta_after  = after_all.routes.get(dst_route,  {}).get("eta_days", eta_before)
    eta_improvement  = max(0.0, float(eta_before - eta_after))
    penalty_reduction = max(0.0, before_all.penalty_exposure_usd - after_all.penalty_exposure_usd)

    attempted = len([s for s in chain_steps if s.status != "skipped"])

    return ExecutionResult(
        chain_steps=chain_steps,
        before_state=before_all,
        after_state=after_all,
        total_actions_attempted=attempted,
        total_actions_succeeded=succeeded,
        total_actions_failed=failed,
        outcome_summary=(
            f"Executed {len(feasible)}-step action chain: "
            f"{succeeded}/{attempted} succeeded, {failed} failed. "
            f"Penalty exposure reduced by ${penalty_reduction:,.0f}. "
            f"ETA improved by {eta_improvement:.1f} day(s)."
        ),
        penalty_reduction_usd=penalty_reduction,
        eta_improvement_days=eta_improvement,
        total_latency_ms=total_ms,
        action_id=primary.action_id if primary else "",
        action_type=primary.action_type.value if primary else "",
        steps=all_api_steps,
    )
