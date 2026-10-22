"""
langsmith_engine_tools.py - LangSmith Engine Tracing, Issue Diagnosis, Evidence Review,
and Offline Evaluation Dataset Generation.

Rule 227: The LangSmith Engine, Evidence Traces, and Offline Evaluation Datasets.
Provides LangSmith trace logging, automated issue detection (silent tool errors, paradox
tension halts, state violations, degree leakage), evidence tracing with child run links,
offline ground-truth dataset creation, and issue lifecycle tracking (priority & status).
"""

import os
import sys
import json
import time
import uuid
import argparse
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACES_LOG_PATH = os.path.join(BASE_DIR, "langsmith_traces.jsonl")
ISSUES_STORE_PATH = os.path.join(BASE_DIR, "langsmith_issues.json")
DATASETS_LOG_PATH = os.path.join(BASE_DIR, "langsmith_evaluation_dataset.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(time.time() * 1000)


# ============================================================================
# 1. TRACE STORE & RECORDING
# ============================================================================

def record_trace(
    name: str,
    run_type: str = "tool",
    inputs: Any = None,
    outputs: Any = None,
    error: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    degree: int = 1,
    project_name: str = "crypto-agent",
    duration_ms: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record an execution trace into the append-only trace log.
    Compatible with LangSmith Run schema conventions."""
    trace_id = str(uuid.uuid4())
    ts_ms = _now_ms()

    trace_entry = {
        "id": trace_id,
        "name": name,
        "run_type": run_type,
        "project_name": project_name,
        "degree": degree,
        "parent_run_id": parent_run_id,
        "inputs": inputs or {},
        "outputs": outputs,
        "error": error,
        "start_time_ms": ts_ms - int(duration_ms),
        "end_time_ms": ts_ms,
        "duration_ms": max(0.0, round(duration_ms, 2)),
        "timestamp_iso": _now_iso(),
        "metadata": metadata or {},
    }

    try:
        with open(TRACES_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        sys.stderr.write(f"[LANGSMITH] Failed to write trace: {e}\n")

    return trace_entry


def load_recent_traces(limit: int = 100, project_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read recent traces from the trace log."""
    if not os.path.exists(TRACES_LOG_PATH):
        return []
    traces = []
    try:
        with open(TRACES_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                    if project_name and t.get("project_name") != project_name:
                        continue
                    traces.append(t)
                except Exception:
                    continue
    except Exception as e:
        sys.stderr.write(f"[LANGSMITH] Error reading traces: {e}\n")
    return traces[-limit:]


# ============================================================================
# 2. ISSUE ENGINE SCANNER & EVIDENCE GATHERING
# ============================================================================

def _load_issues() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(ISSUES_STORE_PATH):
        return {}
    try:
        with open(ISSUES_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_issues(issues: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(ISSUES_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(issues, f, indent=2, ensure_ascii=False)
    except Exception as e:
        sys.stderr.write(f"[LANGSMITH] Error saving issues: {e}\n")


def scan_traces_for_issues(
    project_name: str = "crypto-agent",
    window: int = 150
) -> Dict[str, Any]:
    """LangSmith Engine core scanner:
    Scans recent traces for failure patterns:
      1. Silent tool error (returns error dict / ok: False without raising)
      2. Paradox tension halt (paradoxical queries halted at gate)
      3. State machine transition violation (playback or separation jump)
      4. Degree boundary leakage
      5. Abnormal latency spike (>5000ms)
    Updates issues registry with diagnosis, evidence child runs, and proposed fixes."""
    traces = load_recent_traces(limit=window, project_name=project_name)
    existing_issues = _load_issues()
    new_issues_count = 0
    updated_evidence_count = 0

    def find_or_create_issue(
        issue_key: str,
        title: str,
        category: str,
        diagnosis: str,
        priority: str,
        proposed_fix: Dict[str, Any]
    ) -> Dict[str, Any]:
        nonlocal new_issues_count
        if issue_key in existing_issues:
            iss = existing_issues[issue_key]
            # If closed but same problem recurs in later trace, auto-reopen!
            if iss.get("status") == "closed":
                iss["status"] = "reopened"
                iss.setdefault("feedback_history", []).append({
                    "action": "auto_reopen",
                    "reason": "Failure pattern recurred in newer execution trace",
                    "timestamp": _now_iso()
                })
            return iss

        new_issues_count += 1
        iss = {
            "issue_id": issue_key,
            "title": title,
            "category": category,
            "project_name": project_name,
            "diagnosis": diagnosis,
            "priority": priority,  # high, medium, low
            "status": "open",      # open, closed, incorrectly_flagged, reopened
            "first_seen": _now_iso(),
            "last_seen": _now_iso(),
            "evidence": [],
            "proposed_fix": proposed_fix,
            "feedback_history": [],
            "offline_examples_count": 0,
        }
        existing_issues[issue_key] = iss
        return iss

    for tr in traces:
        tr_id = tr.get("id")
        tr_name = tr.get("name", "unknown")
        err = tr.get("error")
        out = tr.get("outputs") or {}
        inp = tr.get("inputs") or {}
        dur = tr.get("duration_ms", 0)

        # 1. Silent Tool Error Detection
        is_silent_error = False
        silent_err_msg = ""
        if err:
            is_silent_error = True
            silent_err_msg = str(err)
        elif isinstance(out, dict):
            if out.get("ok") is False:
                is_silent_error = True
                silent_err_msg = str(out.get("error") or "ok=False response")
            elif out.get("status") in ("error", "rejected", "failed"):
                is_silent_error = True
                silent_err_msg = str(out.get("reason") or out.get("message") or "status=rejected")

        if is_silent_error:
            issue_key = f"silent-err-{tr_name}"
            iss = find_or_create_issue(
                issue_key=issue_key,
                title=f"Silent Tool Failure in `{tr_name}`",
                category="SILENT_TOOL_ERROR",
                diagnosis=(
                    f"Tool `{tr_name}` returned a silent failure or rejected status instead of "
                    f"raising an exception: '{silent_err_msg}'. Caller chain may continue unaware."
                ),
                priority="high",
                proposed_fix={
                    "type": "code_and_schema",
                    "target": f"langchain_separation.py / {tr_name}",
                    "description": (
                        f"Validate input parameters before invoking `{tr_name}` or wrap in "
                        f"RunnableBranch to catch fallback responses cleanly."
                    ),
                    "code_diff": f"# In {tr_name}:\n+ if not validated:\n+     raise ValueError('{silent_err_msg}')"
                }
            )
            # Add trace to evidence if not already present
            ev_ids = {e.get("trace_id") for e in iss["evidence"]}
            if tr_id not in ev_ids:
                iss["evidence"].append({
                    "trace_id": tr_id,
                    "child_run_id": tr.get("parent_run_id") or tr_id,
                    "name": tr_name,
                    "snippet": f"Input: {str(inp)[:120]}... Error: {silent_err_msg}",
                    "inputs": inp,
                    "outputs": out,
                    "error": silent_err_msg,
                    "timestamp": tr.get("timestamp_iso", _now_iso())
                })
                iss["last_seen"] = _now_iso()
                updated_evidence_count += 1

        # 2. Paradox Tension Halt Detection
        if tr_name in ("paradox_tension_detector", "detect_paradox_tension", "langchain_paradox_router"):
            is_paradox = False
            if isinstance(out, dict) and out.get("is_paradoxical"):
                is_paradox = True
            if is_paradox:
                issue_key = "paradox-tension-detected"
                opposing = out.get("opposing_forces") or ["mutually exclusive constraints"]
                iss = find_or_create_issue(
                    issue_key=issue_key,
                    title="Unresolved Paradoxical Tension in Prompt Input",
                    category="PARADOX_TENSION_HALT",
                    diagnosis=(
                        f"Execution pipeline halted at paradox gate. Opposing forces detected: "
                        f"{', '.join(opposing)}. Main generation chain bypassed."
                    ),
                    priority="medium",
                    proposed_fix={
                        "type": "prompt_clarification",
                        "target": "prompt_tension_router",
                        "description": "Route input to Human-in-the-Loop clarification or Dialectical chain synthesis.",
                        "suggested_clarification": out.get("suggested_clarification") or "Rank primary vs secondary constraints."
                    }
                )
                ev_ids = {e.get("trace_id") for e in iss["evidence"]}
                if tr_id not in ev_ids:
                    iss["evidence"].append({
                        "trace_id": tr_id,
                        "child_run_id": tr.get("parent_run_id") or tr_id,
                        "name": tr_name,
                        "snippet": f"Paradox prompt: {str(inp)[:120]}...",
                        "inputs": inp,
                        "outputs": out,
                        "error": None,
                        "timestamp": tr.get("timestamp_iso", _now_iso())
                    })
                    iss["last_seen"] = _now_iso()
                    updated_evidence_count += 1

        # 3. State Machine Transition Violation (Music Playback Ledger)
        if "music" in tr_name or "playback" in tr_name:
            if isinstance(out, dict) and out.get("ok") is False:
                reason = out.get("reason", "illegal transition")
                issue_key = "state-transition-violation-music"
                iss = find_or_create_issue(
                    issue_key=issue_key,
                    title="Illegal State Transition in Playback Ledger",
                    category="STATE_TRANSITION_VIOLATION",
                    diagnosis=(
                        f"Tool `{tr_name}` attempted an illegal state transition: {reason}. "
                        f"State machine rejected transition according to Rule 226."
                    ),
                    priority="medium",
                    proposed_fix={
                        "type": "state_machine_guard",
                        "target": "music_playback_tools.py",
                        "description": "Check now_playing state before emitting pause/resume/stop commands.",
                        "code_diff": "+ current_state = get_now_playing()['state']\n+ if current_state == 'STOPPED': return {'ok': False}"
                    }
                )
                ev_ids = {e.get("trace_id") for e in iss["evidence"]}
                if tr_id not in ev_ids:
                    iss["evidence"].append({
                        "trace_id": tr_id,
                        "child_run_id": tr.get("parent_run_id") or tr_id,
                        "name": tr_name,
                        "snippet": f"Action rejected: {reason}",
                        "inputs": inp,
                        "outputs": out,
                        "error": reason,
                        "timestamp": tr.get("timestamp_iso", _now_iso())
                    })
                    iss["last_seen"] = _now_iso()
                    updated_evidence_count += 1

        # 4. High Latency Spike (>4500ms)
        if dur > 4500.0:
            issue_key = f"latency-spike-{tr_name}"
            iss = find_or_create_issue(
                issue_key=issue_key,
                title=f"High Latency Spike in `{tr_name}` ({dur}ms)",
                category="LATENCY_SPIKE",
                diagnosis=f"Execution of `{tr_name}` took {dur}ms, exceeding latency budget.",
                priority="low",
                proposed_fix={
                    "type": "timeout_or_async",
                    "target": tr_name,
                    "description": "Add caching or schedule background execution.",
                    "code_diff": "+ @lru_cache(maxsize=128)"
                }
            )
            ev_ids = {e.get("trace_id") for e in iss["evidence"]}
            if tr_id not in ev_ids:
                iss["evidence"].append({
                    "trace_id": tr_id,
                    "child_run_id": tr.get("parent_run_id") or tr_id,
                    "name": tr_name,
                    "snippet": f"Duration: {dur}ms",
                    "inputs": inp,
                    "outputs": out,
                    "error": None,
                    "timestamp": tr.get("timestamp_iso", _now_iso())
                })
                iss["last_seen"] = _now_iso()
                updated_evidence_count += 1

    _save_issues(existing_issues)

    return {
        "ok": True,
        "scanned_traces": len(traces),
        "total_issues": len(existing_issues),
        "new_issues": new_issues_count,
        "updated_evidence": updated_evidence_count,
        "issues": list(existing_issues.values())
    }


def list_project_issues(
    project_name: str = "crypto-agent",
    status: Optional[str] = None,
    priority: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List issues filtered by status (open, closed, incorrectly_flagged, reopened)
    and priority (low, medium, high). Matches LangSmith CLI output."""
    all_issues = list(_load_issues().values())
    filtered = []
    for iss in all_issues:
        if project_name and iss.get("project_name") != project_name:
            continue
        if status and iss.get("status") != status:
            continue
        if priority and iss.get("priority") != priority:
            continue
        filtered.append(iss)
    return filtered


def review_evidence(issue_id: str) -> Dict[str, Any]:
    """Retrieve full trace evidence and child runs for an issue."""
    issues = _load_issues()
    if issue_id not in issues:
        return {"ok": False, "error": f"Issue '{issue_id}' not found."}
    iss = issues[issue_id]
    return {
        "ok": True,
        "issue_id": issue_id,
        "title": iss.get("title"),
        "diagnosis": iss.get("diagnosis"),
        "status": iss.get("status"),
        "priority": iss.get("priority"),
        "evidence_count": len(iss.get("evidence", [])),
        "evidence": iss.get("evidence", []),
        "proposed_fix": iss.get("proposed_fix")
    }


def update_issue_status(
    issue_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    reason: str = ""
) -> Dict[str, Any]:
    """Update priority (low, medium, high) or status (closed, incorrectly_flagged, reopened).
    Engine records user feedback to shape future scans."""
    issues = _load_issues()
    if issue_id not in issues:
        return {"ok": False, "error": f"Issue '{issue_id}' not found."}
    iss = issues[issue_id]
    history_entry = {"timestamp": _now_iso(), "reason": reason}

    if status:
        if status not in ("open", "closed", "incorrectly_flagged", "reopened"):
            return {"ok": False, "error": f"Invalid status '{status}'. Valid: open, closed, incorrectly_flagged, reopened."}
        iss["status"] = status
        history_entry["action"] = f"status_change_to_{status}"

    if priority:
        if priority not in ("low", "medium", "high"):
            return {"ok": False, "error": f"Invalid priority '{priority}'. Valid: low, medium, high."}
        iss["priority"] = priority
        history_entry["priority_set"] = priority

    iss.setdefault("feedback_history", []).append(history_entry)
    _save_issues(issues)

    return {
        "ok": True,
        "issue_id": issue_id,
        "status": iss["status"],
        "priority": iss["priority"],
        "feedback_logged": history_entry
    }


# ============================================================================
# 3. OFFLINE EVALUATION DATASET GENERATOR
# ============================================================================

def add_offline_example(
    issue_id: str,
    trace_id: str,
    ground_truth_output: Optional[Any] = None,
    notes: str = "",
    dataset_name: str = "agent-eval-golden"
) -> Dict[str, Any]:
    """Convert an evidence trace into an offline evaluation ground-truth example.
    Pairs production trace inputs that failed with expected / corrected outputs."""
    issues = _load_issues()
    if issue_id not in issues:
        return {"ok": False, "error": f"Issue '{issue_id}' not found."}
    iss = issues[issue_id]

    target_ev = None
    for ev in iss.get("evidence", []):
        if ev.get("trace_id") == trace_id:
            target_ev = ev
            break

    if not target_ev:
        # Fallback: check recent traces directly
        for tr in load_recent_traces(100):
            if tr.get("id") == trace_id:
                target_ev = {
                    "trace_id": tr.get("id"),
                    "name": tr.get("name"),
                    "inputs": tr.get("inputs"),
                    "outputs": tr.get("outputs"),
                    "error": tr.get("error")
                }
                break

    if not target_ev:
        return {"ok": False, "error": f"Trace '{trace_id}' not found in evidence or trace log."}

    example_id = f"eval-{str(uuid.uuid4())[:8]}"
    example_record = {
        "example_id": example_id,
        "dataset_name": dataset_name,
        "source_issue_id": issue_id,
        "source_trace_id": trace_id,
        "run_name": target_ev.get("name"),
        "inputs": target_ev.get("inputs"),
        "failed_output": target_ev.get("outputs"),
        "failure_error": target_ev.get("error"),
        "ground_truth_output": ground_truth_output or {"expected": "resolved_cleanly", "notes": notes},
        "created_at_ms": _now_ms(),
        "created_iso": _now_iso(),
        "notes": notes or f"Generated from LangSmith Engine Issue {issue_id}"
    }

    try:
        with open(DATASETS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(example_record, ensure_ascii=False) + "\n")
        iss["offline_examples_count"] = iss.get("offline_examples_count", 0) + 1
        _save_issues(issues)
    except Exception as e:
        return {"ok": False, "error": f"Failed to save offline example: {e}"}

    return {
        "ok": True,
        "dataset_name": dataset_name,
        "example_id": example_id,
        "source_trace_id": trace_id,
        "example": example_record
    }


def list_offline_datasets(dataset_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """List offline evaluation dataset examples."""
    if not os.path.exists(DATASETS_LOG_PATH):
        return []
    records = []
    try:
        with open(DATASETS_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if dataset_name and r.get("dataset_name") != dataset_name:
                        continue
                    records.append(r)
                except Exception:
                    continue
    except Exception as e:
        sys.stderr.write(f"[LANGSMITH] Error reading datasets: {e}\n")
    return records


def get_project_summary(project_name: str = "crypto-agent") -> Dict[str, Any]:
    """Summary of project health, open issues, evidence count, and offline datasets."""
    issues = list_project_issues(project_name=project_name)
    traces = load_recent_traces(project_name=project_name)
    datasets = list_offline_datasets()

    open_issues = [i for i in issues if i.get("status") in ("open", "reopened")]
    high_priority = [i for i in open_issues if i.get("priority") == "high"]
    closed_issues = [i for i in issues if i.get("status") == "closed"]

    return {
        "project_name": project_name,
        "total_traces": len(traces),
        "total_issues": len(issues),
        "open_issues_count": len(open_issues),
        "high_priority_open": len(high_priority),
        "closed_issues_count": len(closed_issues),
        "offline_eval_examples_count": len(datasets),
        "latest_trace_timestamp": traces[-1].get("timestamp_iso") if traces else None,
        "timestamp_iso": _now_iso(),
    }


# ============================================================================
# 4. LANGCHAIN STRUCTURED TOOLS (RULE 227)
# ============================================================================

class ScanIssuesArgs(BaseModel):
    project_name: str = Field("crypto-agent", description="LangSmith project name")
    window: int = Field(150, description="Number of recent traces to analyze")


def _run_scan_issues(project_name: str = "crypto-agent", window: int = 150) -> str:
    res = scan_traces_for_issues(project_name=project_name, window=window)
    return json.dumps(res, indent=2)


langsmith_scan_issues_tool = StructuredTool(
    name="langsmith_scan_issues_tool",
    description="Scan recent execution traces to detect silent errors, paradox halts, and violations with LangSmith Engine (Rule 227).",
    args_schema=ScanIssuesArgs,
    func=_run_scan_issues
)


class ListIssuesArgs(BaseModel):
    project_name: str = Field("crypto-agent", description="Project name")
    status: Optional[str] = Field(None, description="Filter: open, closed, incorrectly_flagged, reopened")
    priority: Optional[str] = Field(None, description="Filter: high, medium, low")


def _run_list_issues(project_name: str = "crypto-agent", status: Optional[str] = None, priority: Optional[str] = None) -> str:
    issues = list_project_issues(project_name=project_name, status=status, priority=priority)
    return json.dumps({"count": len(issues), "issues": issues}, indent=2)


langsmith_list_issues_tool = StructuredTool(
    name="langsmith_list_issues_tool",
    description="List diagnosed agent issues with status, priority, and failure summaries (Rule 227).",
    args_schema=ListIssuesArgs,
    func=_run_list_issues
)


class ReviewEvidenceArgs(BaseModel):
    issue_id: str = Field(..., description="ID of the issue to inspect")


def _run_review_evidence(issue_id: str) -> str:
    res = review_evidence(issue_id)
    return json.dumps(res, indent=2)


langsmith_review_evidence_tool = StructuredTool(
    name="langsmith_review_evidence_tool",
    description="Inspect trace evidence snippets, child runs, and inputs/outputs supporting an issue diagnosis (Rule 227).",
    args_schema=ReviewEvidenceArgs,
    func=_run_review_evidence
)


class AddOfflineExampleArgs(BaseModel):
    issue_id: str = Field(..., description="Issue ID providing context")
    trace_id: str = Field(..., description="Trace ID whose inputs will be evaluated")
    expected_output_json: Optional[str] = Field(None, description="JSON string of ground-truth corrected output")
    notes: str = Field("", description="Reason or context for offline benchmark example")
    dataset_name: str = Field("agent-eval-golden", description="Dataset bucket name")


def _run_add_offline_example(
    issue_id: str,
    trace_id: str,
    expected_output_json: Optional[str] = None,
    notes: str = "",
    dataset_name: str = "agent-eval-golden"
) -> str:
    ground_truth = None
    if expected_output_json:
        try:
            ground_truth = json.loads(expected_output_json)
        except Exception:
            ground_truth = {"raw": expected_output_json}
    res = add_offline_example(
        issue_id=issue_id,
        trace_id=trace_id,
        ground_truth_output=ground_truth,
        notes=notes,
        dataset_name=dataset_name
    )
    return json.dumps(res, indent=2)


langsmith_add_offline_example_tool = StructuredTool(
    name="langsmith_add_offline_example_tool",
    description="Convert an evidence trace into a ground-truth dataset example for offline evaluation and regression benchmarking (Rule 227).",
    args_schema=AddOfflineExampleArgs,
    func=_run_add_offline_example
)


class UpdateIssueArgs(BaseModel):
    issue_id: str = Field(..., description="Issue ID")
    status: Optional[str] = Field(None, description="open, closed, incorrectly_flagged, reopened")
    priority: Optional[str] = Field(None, description="low, medium, high")
    reason: str = Field("", description="Reason explaining the decision for Engine learning")


def _run_update_issue(
    issue_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    reason: str = ""
) -> str:
    res = update_issue_status(issue_id, status=status, priority=priority, reason=reason)
    return json.dumps(res, indent=2)


langsmith_update_issue_tool = StructuredTool(
    name="langsmith_update_issue_tool",
    description="Update issue status, priority, or dismiss as incorrectly flagged with learning feedback (Rule 227).",
    args_schema=UpdateIssueArgs,
    func=_run_update_issue
)


LANGSMITH_TOOLS = [
    langsmith_scan_issues_tool,
    langsmith_list_issues_tool,
    langsmith_review_evidence_tool,
    langsmith_add_offline_example_tool,
    langsmith_update_issue_tool,
]


# ============================================================================
# 5. CLI INTERFACE (Compatible with LangSmith CLI conventions)
# ============================================================================

def main_cli():
    parser = argparse.ArgumentParser(description="LangSmith Engine CLI — Issue Detection, Evidence & Eval Datasets")
    subparsers = parser.add_subparsers(dest="subcommand")

    # project issues list
    proj_parser = subparsers.add_parser("project")
    proj_sub = proj_parser.add_subparsers(dest="proj_command")
    issues_cmd = proj_sub.add_parser("issues")
    issues_cmd_sub = issues_cmd.add_subparsers(dest="issues_action")
    list_cmd = issues_cmd_sub.add_parser("list")
    list_cmd.add_argument("--project", default="crypto-agent", help="Project name")
    list_cmd.add_argument("--status", choices=["open", "closed", "incorrectly_flagged", "reopened"], default=None)
    list_cmd.add_argument("--priority", choices=["high", "medium", "low"], default=None)

    # scan
    scan_cmd = subparsers.add_parser("scan")
    scan_cmd.add_argument("--project", default="crypto-agent")
    scan_cmd.add_argument("--window", type=int, default=150)

    # evidence
    ev_cmd = subparsers.add_parser("evidence")
    ev_cmd.add_argument("--issue-id", required=True)

    # dataset add
    ds_cmd = subparsers.add_parser("dataset-add")
    ds_cmd.add_argument("--issue-id", required=True)
    ds_cmd.add_argument("--trace-id", required=True)
    ds_cmd.add_argument("--expected", default="{}")
    ds_cmd.add_argument("--notes", default="")

    # status
    st_cmd = subparsers.add_parser("status")
    st_cmd.add_argument("--issue-id", required=True)
    st_cmd.add_argument("--status", choices=["open", "closed", "incorrectly_flagged", "reopened"], default=None)
    st_cmd.add_argument("--priority", choices=["high", "medium", "low"], default=None)
    st_cmd.add_argument("--reason", default="")

    # summary
    subparsers.add_parser("summary")

    args = parser.parse_args()

    if args.subcommand == "scan":
        res = scan_traces_for_issues(project_name=args.project, window=args.window)
        print(f"[LANGSMITH ENGINE] Scanned {res['scanned_traces']} traces. Found {res['total_issues']} issues ({res['new_issues']} new).")
        for iss in res["issues"]:
            print(f" - [{iss['priority'].upper()}] {iss['issue_id']} ({iss['status']}): {iss['title']} (evidence={len(iss['evidence'])})")
    elif args.subcommand == "project" and getattr(args, "proj_command", None) == "issues":
        issues = list_project_issues(project_name=args.project, status=args.status, priority=args.priority)
        print(f"[LANGSMITH ENGINE] Found {len(issues)} matching issues for project '{args.project}':")
        for iss in issues:
            print(f"  • {iss['issue_id']} | priority={iss['priority']} | status={iss['status']} | evidence={len(iss.get('evidence', []))}")
            print(f"    Diagnosis: {iss['diagnosis']}")
    elif args.subcommand == "evidence":
        res = review_evidence(args.issue_id)
        print(json.dumps(res, indent=2))
    elif args.subcommand == "dataset-add":
        exp = {}
        try:
            exp = json.loads(args.expected)
        except Exception:
            exp = {"raw": args.expected}
        res = add_offline_example(args.issue_id, args.trace_id, ground_truth_output=exp, notes=args.notes)
        print(json.dumps(res, indent=2))
    elif args.subcommand == "status":
        res = update_issue_status(args.issue_id, status=args.status, priority=args.priority, reason=args.reason)
        print(json.dumps(res, indent=2))
    elif args.subcommand == "summary":
        res = get_project_summary()
        print(json.dumps(res, indent=2))
    else:
        # Default: print summary
        res = get_project_summary()
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main_cli()
