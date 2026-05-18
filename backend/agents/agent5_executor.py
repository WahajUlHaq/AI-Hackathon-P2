import json
from datetime import datetime, timezone
from typing import List, Dict, Any

def get_current_time_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_before_state(action_type: str, target_system: str) -> Dict[str, Any]:
    """Generic before-state for any domain, keyed by action type."""
    state = {"system": target_system}
    if action_type == "ALERT":
        state.update({"notification_sent": False, "last_notification": "N/A", "pending_count": 0})
    elif action_type == "PUBLISH":
        state.update({"document_published": False, "portal_status": "unknown", "last_published": "N/A"})
    elif action_type == "UPDATE":
        state.update({"record_updated": False, "current_flag": "none", "risk_level": "normal", "last_updated": "stale"})
    elif action_type == "ANALYZE":
        state.update({"analysis_active": False, "active_jobs": 0, "last_analysis": "N/A"})
    elif action_type == "MONITOR":
        state.update({"monitoring_active": False, "monitoring_job": None, "interval": None})
    else:
        state.update({"action_completed": False})
    return state

def execute_action(action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("type")
    target_system = action.get("target_system", "system")
    action_id = action.get("action_id", "act_000")
    title = action.get("title", "Action")
    description = action.get("description", "")
    stakeholder = action.get("stakeholder", "Team")
    sensitivity = action.get("constraints", {}).get("sensitivity", "INTERNAL")
    uid = action_id.split("_")[-1] if action_id else "000"

    before_state = generate_before_state(action_type, target_system)
    after_state = before_state.copy()

    status = "SUCCESS"
    error = None
    requires_recovery = False
    duration_ms = 0
    comparison = {}
    simulation_output = {}
    side_effects = []

    # FAILURE INJECTION: first PUBLISH action fails to demonstrate recovery flow
    if action_type == "PUBLISH" and not context.get("first_publish_injected", False):
        context["first_publish_injected"] = True
        status = "FAILED"
        error = f"API_TIMEOUT: {target_system} did not respond within 5000ms"
        requires_recovery = True
        duration_ms = 5020

        after_state["portal_status"] = "timeout"
        after_state["document_published"] = False

        comparison = {
            "fields_changed": ["portal_status"],
            "fields_unchanged": ["document_published", "last_published"],
            "change_summary": f"{title} FAILED — portal timed out. Document NOT published.",
            "impact_magnitude": "CRITICAL — downstream actions blocked, fallback required"
        }
        simulation_output = {
            "api_endpoint": f"POST /{target_system.replace('_', '-')}/documents",
            "request_payload": {"title": title, "description": description[:200], "sensitivity": sensitivity},
            "response": "TIMEOUT after 5020ms — no response received"
        }
        all_actions = context.get("all_actions", [])
        for dep_action in all_actions:
            if action_id in dep_action.get("depends_on", []):
                side_effects.append(
                    f"{dep_action['action_id']} ({dep_action['type']}) is now BLOCKED — depends on this action"
                )
        if not side_effects:
            side_effects.append("Downstream actions may be BLOCKED — depends on recovery outcome")

    else:
        # Successful simulation — generic, domain-agnostic state changes
        duration_map = {"ALERT": 250, "PUBLISH": 380, "UPDATE": 340, "ANALYZE": 420, "MONITOR": 90}
        duration_ms = duration_map.get(action_type, 200)

        endpoint_map = {
            "ALERT":   f"POST /{target_system.replace('_', '-')}/notifications",
            "PUBLISH": f"POST /{target_system.replace('_', '-')}/documents",
            "UPDATE":  f"PATCH /{target_system.replace('_', '-')}/records",
            "ANALYZE": f"POST /{target_system.replace('_', '-')}/jobs",
            "MONITOR": f"POST /{target_system.replace('_', '-')}/schedules",
        }

        if action_type == "ALERT":
            after_state.update({
                "notification_sent": True,
                "last_notification": get_current_time_iso(),
                "message_id": f"msg_{uid}",
                "recipients": 8
            })
            comparison = {
                "fields_changed": ["notification_sent", "last_notification", "message_id"],
                "fields_unchanged": ["pending_count"],
                "change_summary": f"{title}: notification sent to 8 recipients.",
                "impact_magnitude": "HIGH — stakeholders now informed, response can begin"
            }
            simulation_output = {
                "api_endpoint": endpoint_map["ALERT"],
                "request_payload": {"title": title, "description": description[:200], "stakeholder": stakeholder, "sensitivity": sensitivity, "priority": "URGENT"},
                "response": {"message_id": f"msg_{uid}", "status": "delivered", "recipients": 8}
            }
            side_effects = ["Stakeholders now expect follow-up action", "Notification logged in audit trail"]

        elif action_type == "PUBLISH":
            after_state.update({
                "document_published": True,
                "portal_status": "live",
                "published_at": get_current_time_iso(),
                "document_id": f"doc_{uid}"
            })
            comparison = {
                "fields_changed": ["document_published", "portal_status", "published_at"],
                "fields_unchanged": [],
                "change_summary": f"{title}: document published successfully.",
                "impact_magnitude": "HIGH — information now accessible to stakeholders"
            }
            simulation_output = {
                "api_endpoint": endpoint_map["PUBLISH"],
                "request_payload": {"title": title, "body": description[:300], "sensitivity": sensitivity},
                "response": {"document_id": f"doc_{uid}", "status": "published", "url": f"/{target_system}/docs/{uid}"}
            }
            side_effects = ["Document now accessible to authorized stakeholders"]

        elif action_type == "UPDATE":
            after_state.update({
                "record_updated": True,
                "current_flag": "WATCH",
                "risk_level": "HIGH",
                "last_updated": get_current_time_iso(),
                "records_changed": 1
            })
            comparison = {
                "fields_changed": ["record_updated", "current_flag", "risk_level", "last_updated"],
                "fields_unchanged": [],
                "change_summary": f"{title}: records updated, flag=WATCH, risk=HIGH.",
                "impact_magnitude": "MEDIUM — automated risk systems will pick up new flag"
            }
            simulation_output = {
                "api_endpoint": endpoint_map["UPDATE"],
                "request_payload": {"target": title, "flag": "WATCH", "risk": "HIGH"},
                "response": {"records_updated": 1, "new_flag": "WATCH", "new_risk": "HIGH"}
            }
            side_effects = ["Risk dashboard now shows elevated flag", "Automated monitoring may trigger"]

        elif action_type == "ANALYZE":
            job_id = f"job_{uid}"
            after_state.update({"analysis_active": True, "job_id": job_id, "active_jobs": 1, "estimated_completion": "T+60min"})
            comparison = {
                "fields_changed": ["analysis_active", "job_id", "active_jobs"],
                "fields_unchanged": [],
                "change_summary": f"{title}: analysis job {job_id} queued, ~60 min.",
                "impact_magnitude": "MEDIUM — deep analysis pipeline initiated"
            }
            simulation_output = {
                "api_endpoint": endpoint_map["ANALYZE"],
                "request_payload": {"job_type": title, "description": description[:200]},
                "response": {"job_id": job_id, "status": "queued", "estimated_minutes": 60}
            }
            side_effects = ["System compute resources allocated"]

        elif action_type == "MONITOR":
            job_id = f"mon_{uid}"
            after_state.update({"monitoring_active": True, "monitoring_job": job_id, "interval": "1h", "next_run": get_current_time_iso()})
            comparison = {
                "fields_changed": ["monitoring_active", "monitoring_job", "interval", "next_run"],
                "fields_unchanged": [],
                "change_summary": f"{title}: monitoring job {job_id} created, running hourly.",
                "impact_magnitude": "LOW — background monitoring active"
            }
            simulation_output = {
                "api_endpoint": endpoint_map["MONITOR"],
                "request_payload": {"job_name": title, "interval": "1h"},
                "response": {"job_id": job_id, "status": "scheduled", "interval": "1h", "next_run": get_current_time_iso()}
            }
            side_effects = ["Background job registered in global scheduler"]

        else:
            after_state.update({"action_completed": True, "completed_at": get_current_time_iso()})
            comparison = {"change_summary": f"{title} completed.", "impact_magnitude": "MEDIUM"}
            simulation_output = {
                "api_endpoint": f"POST /{target_system.replace('_', '-')}/execute",
                "request_payload": {"action": title},
                "response": {"status": "success"}
            }

    return {
        "action_id": action_id,
        "step": action.get("step"),
        "title": title,
        "type": action_type,
        "triggered_by_insight": action.get("triggered_by_insight", ""),
        "metric_before": action.get("metric_before", ""),
        "expected_outcome": action.get("expected_outcome", ""),
        "executed_at": get_current_time_iso() if status != "SKIPPED" else None,
        "duration_ms": duration_ms,
        "status": status,
        "error": error,
        "requires_recovery": requires_recovery,
        "before_state": before_state,
        "after_state": after_state,
        "comparison": comparison,
        "simulation_output": simulation_output,
        "side_effects": side_effects
    }


def run(action_plan_data: Dict[str, Any]) -> Dict[str, Any]:
    action_plan = action_plan_data.get("action_plan", [])
    
    print(f"[ExecutorAgent] Simulating {len(action_plan)} actions...")
    
    execution_log = []
    context = {"first_publish_injected": False, "all_actions": action_plan}
    action_status_map = {}
    
    succeeded = 0
    failed = 0
    skipped = 0
    failed_action_ids = []
    skipped_action_ids = []
    total_duration_ms = 0
    
    start_time = get_current_time_iso()
    failure_reason = None
    
    for action in action_plan:
        action_id = action.get("action_id")
        action_type = action.get("type")
        depends_on = action.get("depends_on", [])
        
        # Check dependencies
        can_execute = True
        blocked_by = None
        for dep in depends_on:
            if action_status_map.get(dep) != "SUCCESS":
                can_execute = False
                blocked_by = dep
                break
                
        print(f"\nStep {action.get('step')}: {action_type} — {action.get('title')}")
        
        if not can_execute:
            print(f"  SKIPPED — blocked by {blocked_by} failure ⏭")
            log_entry = {
                "action_id": action_id,
                "step": action.get("step"),
                "title": action.get("title"),
                "type": action_type,
                "executed_at": None,
                "duration_ms": None,
                "status": "SKIPPED",
                "error": f"Blocked — {blocked_by} failed. depends_on not satisfied.",
                "requires_recovery": False,
                "before_state": {},
                "after_state": {},
                "comparison": {
                    "fields_changed": [],
                    "change_summary": "No execution — blocked by upstream failure.",
                    "impact_magnitude": "MEDIUM — dependent action delayed"
                },
                "simulation_output": {},
                "side_effects": [f"Action {action_id} delayed until {blocked_by} is recovered"]
            }
            execution_log.append(log_entry)
            action_status_map[action_id] = "SKIPPED"
            skipped += 1
            skipped_action_ids.append(action_id)
            continue
            
        # Execute action
        log_entry = execute_action(action, context)
        execution_log.append(log_entry)
        
        status = log_entry["status"]
        action_status_map[action_id] = status
        total_duration_ms += log_entry["duration_ms"]
        
        before_summary = ", ".join([f"{k}={v}" for k, v in list(log_entry["before_state"].items())[:2] if k != "system"])
        after_summary = ", ".join([f"{k}={v}" for k, v in list(log_entry["after_state"].items())[:2] if k != "system"])
        
        print(f"  Before: {before_summary}")
        print(f"  Executing {log_entry['simulation_output'].get('api_endpoint', 'UNKNOWN')}... ({log_entry['duration_ms']}ms)")
        
        if status == "FAILED":
            print(f"  ⚠ {log_entry['error'].split(':')[0]} — {log_entry['error'].split(':')[1].strip()}")
            print(f"  After:  {after_summary}")
            print(f"  Change: {log_entry['comparison']['change_summary']} ❌")
            print(f"  Side effect: {log_entry['side_effects'][0]}")
            failed += 1
            failed_action_ids.append(action_id)
            if not failure_reason:
                failure_reason = f"{action_id} — {action.get('target_system')} timeout"
        else:
            print(f"  After:  {after_summary}")
            print(f"  Change: {log_entry['comparison']['change_summary']} ✅")
            succeeded += 1
            
    print(f"\n[ExecutorAgent] Done — {succeeded} succeeded, {failed} failed, {skipped} skipped ({total_duration_ms}ms total)")

    summary = {
        "total_actions": len(action_plan),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "failed_action_ids": failed_action_ids,
        "skipped_action_ids": skipped_action_ids,
        "execution_start": start_time,
        "execution_end": get_current_time_iso(),
        "total_duration_ms": total_duration_ms,
        "failure_reason": failure_reason,
        "recovery_needed": failed > 0
    }
    
    return {
        "execution_log": execution_log,
        "execution_summary": summary
    }

if __name__ == "__main__":
    import os
    import sys
    
    # Try importing from agent4_plan to run a full mock pipeline for demo
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        import agent4_plan
        # mock inputs
        mock_insight_packet = {
            "insights": [
                {"id": "ins_001", "urgency": "CRITICAL", "confidence": 0.86, "supporting_sources": ["cb_002", "cb_003"]},
                {"id": "ins_002", "urgency": "HIGH", "confidence": 0.80, "supporting_sources": ["cb_004"]},
                {"id": "ins_003", "urgency": "HIGH", "confidence": 0.75, "supporting_sources": ["cb_005"]}
            ],
            "sources_used": ["cb_002", "cb_003", "cb_004", "cb_005"]
        }
        mock_constraints = {
            "alert_budget_usd": 0, "publish_deadline_hours": 4, "analyze_budget_usd": 500,
            "available_resources": ["investment_team_email", "investor_portal_api", "portfolio_dashboard", "analytics_engine", "monitoring_scheduler"],
            "api_rate_limits": {"investor_portal_api": "10 calls/hour", "analytics_engine": "5 calls/hour"},
            "output_language": "English", "sensitivity_level": "CONFIDENTIAL"
        }
        plan_output = agent4_plan.run(mock_insight_packet, mock_constraints)
        print("\n--- Transitioning to Stage 5 ---\n")
        
        executor_output = run(plan_output)
        
        # Save output for inspection
        with open("agent5_executor_output.json", "w", encoding="utf-8") as f:
            json.dump(executor_output, f, indent=2)
            
    except Exception as e:
        print(f"Failed to run demo: {e}")
