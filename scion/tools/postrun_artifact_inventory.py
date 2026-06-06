#!/usr/bin/env python3
"""Inventory post-run Scion artifacts without judging research quality."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"


def build_inventory(run_root: Path | str) -> dict[str, Any]:
    run_root = Path(run_root)
    campaign_dir = run_root / "campaign"
    run_status = _read_json(run_root / "run_status.json")
    campaign_run_status = _read_json(campaign_dir / "run_status.json")
    campaign_status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")
    trace_index = _read_json(
        campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json"
    )
    session_index = _read_json(
        campaign_dir / "agentic_sessions" / "agentic_session_index.json"
    )

    db_path = campaign_dir / "scion.db"
    db_inventory = _read_db_inventory(db_path) if db_path.exists() else _empty_db_inventory()
    llm_traces = _read_llm_traces(
        campaign_dir / "llm_traces",
        trace_index=trace_index,
        session_index=session_index,
    )

    branches = _merge_branch_counts(
        db_inventory["branches"],
        session_counts=llm_traces["sessions_by_branch"],
        trace_counts=llm_traces["traces_by_branch"],
    )

    return {
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "run_name": _first_string(
            run_status,
            campaign_run_status,
            campaign_status,
            summary,
            keys=("run_name", "name", "campaign_id"),
        )
        or run_root.name,
        "validity": _validity(
            run_status, campaign_run_status, campaign_status, summary
        ),
        "counters": _counters(
            run_status, campaign_run_status, campaign_status, summary
        ),
        "llm_traces": {
            "trace_count": llm_traces["trace_count"],
            "by_kind": dict(sorted(llm_traces["by_kind"].items())),
            "by_status": dict(sorted(llm_traces["by_status"].items())),
            "index_trace_count": llm_traces["index_trace_count"],
            "index_session_count": llm_traces["index_session_count"],
        },
        "branches": branches,
        "events": db_inventory["events"],
        "hypotheses": db_inventory["hypotheses"],
        "analysis_handoff": HANDOFF_DOC,
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    validity = inventory["validity"]
    counters = inventory["counters"]
    llm = inventory["llm_traces"]
    events = inventory["events"]

    lines = [
        f"# Post-Run Artifact Inventory: {inventory['run_name']}",
        "",
        f"- Run root: `{inventory['run_root']}`",
        f"- Campaign dir: `{inventory['campaign_dir']}`",
        f"- Validity: `{validity['run_validity_status'] or 'unknown'}`",
        f"- Completeness: `{validity['run_completeness_status'] or 'unknown'}`",
        f"- Last stop reason: `{validity['last_stop_reason'] or 'unknown'}`",
    ]
    if validity["invalid_infra_only"]:
        lines.append("- INVALID INFRA-ONLY RUN: stop after proving infra-only status.")

    lines.extend(
        [
            "",
            "## Counters",
            "| Counter | Value |",
            "|---|---:|",
        ]
    )
    for key, value in counters.items():
        lines.append(f"| {key} | {_display(value)} |")

    lines.extend(["", "## Branches"])
    if inventory["branches"]:
        lines.extend(
            [
                "| Branch | State | Lineage | Hypotheses | Events | Sessions | Traces | Failures |",
                "|---|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for branch in inventory["branches"]:
            failures = ",".join(branch["failure_codes"]) or ""
            lines.append(
                "| {branch_id} | {state} | {lineage_id} | {hypothesis_count} | "
                "{event_count} | {session_count} | {trace_count} | {failures} |".format(
                    failures=failures,
                    **{key: _display(value) for key, value in branch.items()},
                )
            )
    else:
        lines.append("- No branch rows found.")

    lines.extend(
        [
            "",
            "## LLM Traces",
            f"- Trace files: {llm['trace_count']}",
            f"- Trace index entries: {llm['index_trace_count']}",
            f"- Session index entries: {llm['index_session_count']}",
            f"- By kind: {_counter_text(llm['by_kind'])}",
            f"- By status: {_counter_text(llm['by_status'])}",
            "",
            "## Events",
            f"- By kind: {_counter_text(events['by_kind'])}",
            f"- By decision: {_counter_text(events['by_decision'])}",
            f"- By stage: {_counter_text(events['by_stage'])}",
            "",
            f"Use `{inventory['analysis_handoff']}` for actual post-run analysis. "
            "This inventory lists artifacts and counts only; it does not judge research quality.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    inventory = build_inventory(Path(args.run_root))
    if args.format == "json":
        print(json.dumps(inventory, indent=2, sort_keys=True))
    else:
        print(render_markdown(inventory), end="")
    return 0


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _validity(*docs: Any) -> dict[str, Any]:
    run_validity_status = _first_string(
        *docs, keys=("run_validity_status", "validity_status")
    )
    run_completeness_status = _first_string(
        *docs, keys=("run_completeness_status", "completeness_status")
    )
    last_stop_reason = _first_string(
        *docs,
        keys=(
            "last_stop_reason",
            "stopped_reason",
            "stop_reason",
            "termination_reason",
            "failure_reason",
        ),
    )
    invalid_infra_only = any(_doc_says_invalid_infra_only(doc) for doc in docs)
    return {
        "run_validity_status": run_validity_status,
        "run_completeness_status": run_completeness_status,
        "last_stop_reason": last_stop_reason,
        "invalid_infra_only": invalid_infra_only,
    }


def _doc_says_invalid_infra_only(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("invalid_infra_only") is True:
        return True
    values: list[str] = []
    for key in (
        "run_validity_status",
        "validity_status",
        "run_completeness_status",
        "status",
        "last_stop_reason",
        "stopped_reason",
        "stop_reason",
        "termination_reason",
        "failure_category",
        "error_category",
    ):
        value = doc.get(key)
        if value is not None:
            values.append(str(value).strip().lower())
    provider_error = doc.get("provider_error")
    if isinstance(provider_error, dict):
        values.extend(str(value).strip().lower() for value in provider_error.values())
    if "invalid_infra_only" in values:
        return True
    joined = " ".join(values)
    return "infra" in joined and ("invalid" in joined or "failed_infra" in joined)


def _counters(*docs: Any) -> dict[str, int | None]:
    fields = {
        "requested_rounds": ("requested_rounds", "total_rounds", "max_rounds"),
        "effective_rounds_completed": (
            "effective_rounds_completed",
            "effective_rounds",
            "completed_rounds",
            "n_steps",
        ),
        "formal_screened_candidates": (
            "formal_screened_candidates",
            "screened_candidates",
            "screened_experiments",
        ),
        "protocol_evaluated_candidates": (
            "protocol_evaluated_candidates",
            "protocol_evaluations",
            "n_experiments",
        ),
        "screened_experiments": ("screened_experiments", "n_experiments"),
        "proposal_attempts_total": (
            "proposal_attempts_total",
            "proposal_attempts",
            "attempts",
        ),
    }
    return {
        name: _first_int(*docs, keys=keys)
        for name, keys in fields.items()
    }


def _read_llm_traces(
    trace_dir: Path,
    *,
    trace_index: Any,
    session_index: Any,
) -> dict[str, Any]:
    by_kind: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    file_traces_by_branch: Counter[str] = Counter()
    trace_files = sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []
    for path in trace_files:
        doc = _read_json(path)
        kind = _trace_kind(doc, path)
        status = _trace_status(doc)
        by_kind[kind] += 1
        by_status[status] += 1
        branch_id = _branch_id(doc)
        if branch_id:
            file_traces_by_branch[branch_id] += 1

    trace_entries = _trace_index_entries(trace_index)
    session_entries = _session_index_entries(session_index)

    index_traces_by_branch: Counter[str] = Counter()
    for entry in trace_entries:
        branch_id = _branch_id(entry)
        if branch_id:
            index_traces_by_branch[branch_id] += 1

    sessions_by_branch: Counter[str] = Counter()
    for entry in session_entries:
        branch_id = _branch_id(entry)
        if branch_id:
            sessions_by_branch[branch_id] += 1

    return {
        "trace_count": len(trace_files),
        "by_kind": by_kind,
        "by_status": by_status,
        "index_trace_count": len(trace_entries),
        "index_session_count": len(session_entries),
        "traces_by_branch": _max_counter(file_traces_by_branch, index_traces_by_branch),
        "sessions_by_branch": sessions_by_branch,
    }


def _trace_kind(doc: Any, path: Path) -> str:
    value = _first_string(
        doc,
        keys=(
            "trace_kind",
            "request_kind",
            "call_kind",
            "kind",
            "stage",
            "phase",
            "llm_stage",
        ),
    )
    if value:
        return value
    name = path.name.lower()
    if "hypothesis" in name:
        return "hypothesis"
    if "code" in name:
        return "code"
    return "unknown"


def _trace_status(doc: Any) -> str:
    value = _first_string(
        doc,
        keys=("status", "final_status", "result_status", "termination_reason"),
    )
    if value:
        return value
    if isinstance(doc, dict):
        if doc.get("ok") is True:
            return "ok"
        if doc.get("ok") is False:
            return "failed"
        response = doc.get("response")
        if isinstance(response, dict) and response.get("status"):
            return str(response["status"])
    return "unknown"


def _trace_index_entries(index_doc: Any) -> list[Any]:
    if isinstance(index_doc, list):
        return index_doc
    if isinstance(index_doc, dict):
        value = index_doc.get("traces")
        if isinstance(value, list):
            return value
        sessions = index_doc.get("sessions")
        if isinstance(sessions, list):
            entries: list[Any] = []
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                branch_id = _branch_id(session)
                traces = session.get("traces")
                if not isinstance(traces, list):
                    continue
                for trace in traces:
                    if isinstance(trace, dict) and branch_id and not _branch_id(trace):
                        trace = {**trace, "branch_id": branch_id}
                    entries.append(trace)
            return entries
        for key in ("entries", "items"):
            value = index_doc.get(key)
            if isinstance(value, list):
                return value
    return []


def _session_index_entries(index_doc: Any) -> list[Any]:
    if isinstance(index_doc, list):
        return index_doc
    if isinstance(index_doc, dict):
        for key in ("sessions", "entries", "items"):
            value = index_doc.get(key)
            if isinstance(value, list):
                return value
    return []


def _read_db_inventory(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = _tables(conn)
        branches = _branches(conn) if "branches" in tables else []
        events = _events(conn) if "experiment_events" in tables else _empty_events()
        hypotheses = (
            _hypotheses(conn) if "hypotheses" in tables else _empty_hypotheses()
        )
    return {"branches": branches, "events": events, "hypotheses": hypotheses}


def _empty_db_inventory() -> dict[str, Any]:
    return {
        "branches": [],
        "events": _empty_events(),
        "hypotheses": _empty_hypotheses(),
    }


def _empty_events() -> dict[str, dict[str, int]]:
    return {"by_kind": {}, "by_decision": {}, "by_stage": {}}


def _empty_hypotheses() -> dict[str, Any]:
    return {
        "count": 0,
        "by_status": {},
        "by_action": {},
        "by_change_locus": {},
    }


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _branches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = _columns(conn, "branches")
    wanted = (
        "branch_id",
        "state",
        "lineage_id",
        "base_champion_hash",
        "current_code_hash",
        "best_quality_checkpoint_id",
        "last_valid_checkpoint_id",
        "rollback_count",
        "failure_codes",
    )
    select_cols = [col for col in wanted if col in columns]
    rows = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM branches ORDER BY branch_id"
    ).fetchall()
    branches: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        branch_id = str(data.get("branch_id") or "")
        branches.append(
            {
                "branch_id": branch_id,
                "state": data.get("state"),
                "lineage_id": data.get("lineage_id") or branch_id,
                "base_champion_hash": data.get("base_champion_hash"),
                "current_code_hash": data.get("current_code_hash"),
                "best_quality_checkpoint_id": data.get("best_quality_checkpoint_id"),
                "last_valid_checkpoint_id": data.get("last_valid_checkpoint_id"),
                "rollback_count": int(data.get("rollback_count") or 0),
                "failure_codes": _string_list(data.get("failure_codes")),
                "hypothesis_count": _count_where(conn, "hypotheses", "branch_id", branch_id),
                "event_count": _count_where(
                    conn, "experiment_events", "branch_id", branch_id
                ),
                "session_count": 0,
                "trace_count": 0,
            }
        )
    return branches


def _events(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    return {
        "by_kind": _group_counts(conn, "experiment_events", "event_kind"),
        "by_decision": _group_counts(conn, "experiment_events", "decision"),
        "by_stage": _group_counts(conn, "experiment_events", "stage"),
    }


def _hypotheses(conn: sqlite3.Connection) -> dict[str, Any]:
    count = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
    return {
        "count": int(count or 0),
        "by_status": _group_counts(conn, "hypotheses", "status"),
        "by_action": _group_counts(conn, "hypotheses", "action"),
        "by_change_locus": _group_counts(conn, "hypotheses", "change_locus"),
    }


def _group_counts(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> dict[str, int]:
    if column not in _columns(conn, table):
        return {}
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) FROM {table} "
        f"WHERE {column} IS NOT NULL AND {column} != '' GROUP BY {column}"
    ).fetchall()
    return {str(key): int(count) for key, count in rows}


def _count_where(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    value: str,
) -> int:
    if table not in _tables(conn) or column not in _columns(conn, table):
        return 0
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
            (value,),
        ).fetchone()[0]
        or 0
    )


def _merge_branch_counts(
    branches: list[dict[str, Any]],
    *,
    session_counts: Counter[str],
    trace_counts: Counter[str],
) -> list[dict[str, Any]]:
    by_id = {branch["branch_id"]: dict(branch) for branch in branches}
    for branch_id in set(session_counts) | set(trace_counts):
        if branch_id not in by_id:
            by_id[branch_id] = {
                "branch_id": branch_id,
                "state": None,
                "lineage_id": branch_id,
                "base_champion_hash": None,
                "current_code_hash": None,
                "best_quality_checkpoint_id": None,
                "last_valid_checkpoint_id": None,
                "rollback_count": 0,
                "failure_codes": [],
                "hypothesis_count": 0,
                "event_count": 0,
                "session_count": 0,
                "trace_count": 0,
            }
        by_id[branch_id]["session_count"] = int(session_counts.get(branch_id, 0))
        by_id[branch_id]["trace_count"] = int(trace_counts.get(branch_id, 0))
    return [by_id[key] for key in sorted(by_id)]


def _max_counter(left: Counter[str], right: Counter[str]) -> Counter[str]:
    merged: Counter[str] = Counter()
    for key in set(left) | set(right):
        merged[key] = max(left.get(key, 0), right.get(key, 0))
    return merged


def _first_string(*docs: Any, keys: tuple[str, ...]) -> str | None:
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        for key in keys:
            value = doc.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _first_int(*docs: Any, keys: tuple[str, ...]) -> int | None:
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        value = _nested_first(doc, keys)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _nested_first(doc: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in doc:
            return doc[key]
    for value in doc.values():
        if isinstance(value, dict):
            nested = _nested_first(value, keys)
            if nested is not None:
                return nested
    return None


def _branch_id(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return None
    value = _nested_first(doc, ("branch_id", "branch"))
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [part.strip() for part in text.split(",") if part.strip()]
        return _string_list(parsed)
    return [str(value)]


def _counter_text(counter: dict[str, int]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
