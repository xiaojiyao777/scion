#!/usr/bin/env python3
"""Inventory post-run Scion artifacts without judging research quality."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


HANDOFF_DOC = "scion/docs/operations/postrun-analysis-handoff.md"
LAUNCHER_ARTIFACTS = (
    "run.sh",
    "launch.env",
    "command.txt",
    "prepared_run_manifest.v1.json",
    "prepared_run_manifest.md",
    "prepared_handoff",
    "run.log",
    "exit.txt",
)
LAUNCHER_STATUS_KEYS = (
    "wrapper_exit_status",
    "pre_campaign_completion_preflight",
    "api_key_env_missing",
    "warehouse_data_root_missing",
    "git_runtime_dirty",
    "git_runtime_commit_mismatch",
)
RUN_LOG_MARKERS = (
    "COMPLETION_PREFLIGHT_FAILED",
    "COMPLETION_PREFLIGHT_OK",
    "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED",
    "GIT_COMMIT_MISMATCH",
    "GIT_RUNTIME_DIRTY",
    "POSTRUN_REPORT_DIR",
    "POSTRUN_REPORTS_FINISHED_AT",
    "POSTRUN_REPORTS_STARTED_AT",
)
EXIT_MARKERS = (
    "POSTRUN_ACCEPTANCE_DIR",
    "PRE_CAMPAIGN_COMPLETION_PREFLIGHT_FAILED",
    "WRAPPER_EXIT_STATUS",
)
POSTRUN_REPORT_DIRS = (
    "summaries",
    "failures",
    "research_efficiency",
    "manifests",
    "analysis_brief",
    "inventory",
    "rebuild",
)
PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
PREPARED_RUN_CONTRACT_SCHEMA = "scion.prepared_run_contract_inventory.v1"
SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = Path(__file__).resolve().parents[2]


def build_inventory(run_root: Path | str) -> dict[str, Any]:
    run_root = Path(run_root)
    campaign_dir = run_root / "campaign"
    run_status = _read_json(run_root / "run_status.json")
    prepared_manifest = _read_json(run_root / "prepared_run_manifest.v1.json")
    lifecycle = _lifecycle_inventory(run_status, prepared_manifest)
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
    postrun_reports = _postrun_report_inventory(run_root)
    phase4_coverage = _phase4_evidence_coverage(
        run_root=run_root,
        campaign_dir=campaign_dir,
        campaign_status=campaign_status,
        summary=summary,
        trace_index=trace_index,
        session_index=session_index,
        llm_traces=llm_traces,
        lifecycle=lifecycle,
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
        "lifecycle": lifecycle,
        "validity": _prepared_only_validity(lifecycle)
        if lifecycle["prepared_only"]
        else _pre_campaign_failure_validity(lifecycle)
        if lifecycle["pre_campaign_completion_preflight_failed"]
        else _validity(run_status, campaign_run_status, campaign_status, summary),
        "counters": _prepared_only_counters(prepared_manifest)
        if _launch_root_without_current_run(lifecycle)
        else _counters(run_status, campaign_run_status, campaign_status, summary),
        "llm_traces": {
            "trace_count": llm_traces["trace_count"],
            "by_kind": dict(sorted(llm_traces["by_kind"].items())),
            "by_status": dict(sorted(llm_traces["by_status"].items())),
            "index_trace_count": llm_traces["index_trace_count"],
            "index_session_count": llm_traces["index_session_count"],
        },
        "launcher": _launcher_inventory(run_root, run_status),
        "database": {
            "path": str(db_path),
            "present": db_path.exists(),
            "read_error": db_inventory.get("read_error"),
        },
        "postrun_reports": postrun_reports,
        "phase4_evidence_coverage": phase4_coverage,
        "branches": branches,
        "events": db_inventory["events"],
        "hypotheses": db_inventory["hypotheses"],
        "analysis_handoff": HANDOFF_DOC,
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    validity = inventory["validity"]
    counters = inventory["counters"]
    lifecycle = inventory.get("lifecycle") or {}
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
        f"- Evidence scope: `{lifecycle.get('evidence_scope') or 'postrun'}`",
    ]
    if lifecycle.get("prepared_only") is True:
        lines.append(
            "- PREPARED-ONLY ROOT: copied campaign artifacts are launch input, "
            "not current-run postrun evidence."
        )
    if lifecycle.get("pre_campaign_completion_preflight_failed") is True:
        lines.append(
            "- PRE-CAMPAIGN PREFLIGHT FAILED: no current Scion campaign ran; "
            "copied campaign artifacts are resume input, not current-run evidence."
        )
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
            "## Launcher Artifacts",
            f"- Present: {_existing_artifact_text(inventory['launcher']['artifacts'])}",
            "- Prepared contract complete: "
            f"{_display(inventory['launcher']['prepared_run_contract']['contract_complete'])}",
            "- Prepared problem/model: "
            f"{_display(inventory['launcher']['prepared_run_contract']['problem_family'])} / "
            f"{_display(inventory['launcher']['prepared_run_contract']['model'])}",
            "- Prepared control pair: "
            f"{_display(inventory['launcher']['prepared_run_contract']['control_pair_key'])}",
            f"- Status fields: {_mapping_text(inventory['launcher']['status_fields'])}",
            f"- run.log markers: {_counter_text(inventory['launcher']['run_log_markers'])}",
            f"- exit.txt markers: {_counter_text(inventory['launcher']['exit_markers'])}",
            "",
            "### Prepared Run Contract Checks",
            "| Check | Passed | Detail |",
            "|---|---:|---|",
        ]
    )
    for key, item in _prepared_contract_checks_for_markdown(
        inventory["launcher"]["prepared_run_contract"]
    ).items():
        lines.append(
            "| {key} | {passed} | {detail} |".format(
                key=key,
                passed=_display(item.get("passed")),
                detail=_display(item.get("detail")),
            )
        )

    research_focus = inventory["launcher"]["prepared_run_contract"].get(
        "research_focus"
    )
    if isinstance(research_focus, dict) and research_focus:
        lines.extend(
            [
                "",
                "### Prepared Research Focus",
                f"- Accepted checkpoint: {_display(research_focus.get('accepted_checkpoint'))}",
                f"- Question: {_display(research_focus.get('current_question'))}",
                "- Required evidence:",
            ]
        )
        required = research_focus.get("required_evidence")
        if isinstance(required, list) and required:
            lines.extend(f"  - {_display(item)}" for item in required)
        else:
            lines.append("  - None recorded in the prepared manifest.")
        lines.extend(
            [
                "- Default-avoid directions:",
            ]
        )
        avoid = research_focus.get("default_avoid_directions")
        if isinstance(avoid, list) and avoid:
            lines.extend(f"  - {_display(item)}" for item in avoid)
        else:
            lines.append("  - None recorded in the prepared manifest.")
        for key, label in (
            ("route_merge_exception_rule", "Route-merge exception"),
            ("construction_seed_rule", "Construction-seed rule"),
            ("decision_boundary", "Decision boundary"),
        ):
            value = research_focus.get(key)
            if value:
                lines.append(f"- {label}: {_display(value)}")

    lines.extend(
        [
            "",
            "## Postrun Reports",
            f"- Report dir: `{inventory['postrun_reports']['report_dir']}`",
            f"- Exists: {_display(inventory['postrun_reports']['exists'])}",
            f"- Counts: {_mapping_text(inventory['postrun_reports']['counts'])}",
            "",
            "## LLM Traces",
            f"- Trace files: {llm['trace_count']}",
            f"- Trace index entries: {llm['index_trace_count']}",
            f"- Session index entries: {llm['index_session_count']}",
            f"- By kind: {_counter_text(llm['by_kind'])}",
            f"- By status: {_counter_text(llm['by_status'])}",
            "",
            "## Phase 4 Evidence Coverage",
            "| Requirement | Available | Count | Source |",
            "|---|---:|---:|---|",
        ]
    )
    for key, item in _phase4_requirements_for_markdown(
        inventory.get("phase4_evidence_coverage")
    ).items():
        lines.append(
            "| {key} | {available} | {count} | {source} |".format(
                key=key,
                available=_display(item.get("available")),
                count=_display(item.get("count")),
                source=_display(item.get("source")),
            )
        )

    lines.extend(
        [
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
    if doc.get("pre_campaign_completion_preflight") == "failed":
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


def _lifecycle_inventory(run_status: Any, prepared_manifest: Any) -> dict[str, Any]:
    status_doc = run_status if isinstance(run_status, dict) else {}
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    manifest_is_prepared = manifest.get("schema_version") == PREPARED_RUN_MANIFEST_SCHEMA
    prepared_only = (
        status_doc.get("prepared_only") is True
        or (
            status_doc.get("schema") == "scion.launcher_prepare.v1"
            and status_doc.get("status") == "prepared"
        )
    )
    preflight_failed = (
        status_doc.get("pre_campaign_completion_preflight") == "failed"
        and manifest_is_prepared
    )
    resume_from = status_doc.get("resume_from_campaign")
    if resume_from is None:
        resume_from = manifest.get("resume_from_campaign")
    if prepared_only:
        evidence_scope = "prepared_launch_root_with_resume_snapshot"
    elif preflight_failed:
        evidence_scope = "pre_campaign_preflight_failed_with_resume_snapshot"
    else:
        evidence_scope = "postrun_campaign"
    return {
        "schema_version": "scion.launcher_lifecycle.v1",
        "prepared_only": bool(prepared_only),
        "pre_campaign_completion_preflight_failed": bool(preflight_failed),
        "current_run_evidence": not prepared_only and not preflight_failed,
        "status": _string_or_none(status_doc.get("status")),
        "prepared_status_schema": _string_or_none(status_doc.get("schema")),
        "resume_from_campaign": _string_or_none(resume_from),
        "copied_campaign_status_present": status_doc.get(
            "copied_campaign_status_present"
        ),
        "copied_campaign_summary_present": status_doc.get(
            "copied_campaign_summary_present"
        ),
        "evidence_scope": evidence_scope,
    }


def _launch_root_without_current_run(lifecycle: Mapping[str, Any]) -> bool:
    return (
        lifecycle.get("prepared_only") is True
        or lifecycle.get("pre_campaign_completion_preflight_failed") is True
    )


def _prepared_only_validity(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_validity_status": "prepared_only",
        "run_completeness_status": "not_started",
        "last_stop_reason": "prepared_only_not_launched",
        "invalid_infra_only": False,
    }


def _pre_campaign_failure_validity(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": "pre_campaign_completion_preflight_failed",
        "invalid_infra_only": True,
    }


def _prepared_only_counters(prepared_manifest: Any) -> dict[str, int | None]:
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        execution = {}
    return {
        "requested_rounds": _first_int(execution, keys=("rounds",)),
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }


def _launcher_inventory(run_root: Path, run_status: Any) -> dict[str, Any]:
    return {
        "artifacts": {
            name: (run_root / name).exists()
            for name in LAUNCHER_ARTIFACTS
        },
        "prepared_run_contract": _prepared_run_contract(run_root),
        "status_fields": _status_fields(run_status),
        "run_log_markers": _marker_counts(
            _read_text(run_root / "run.log"),
            RUN_LOG_MARKERS,
        ),
        "exit_markers": _marker_counts(
            _read_text(run_root / "exit.txt"),
            EXIT_MARKERS,
        ),
    }


def _postrun_report_inventory(run_root: Path) -> dict[str, Any]:
    report_dir = run_root / "postrun_acceptance"
    counts: dict[str, int] = {}
    files: dict[str, list[str]] = {}
    for name in POSTRUN_REPORT_DIRS:
        subdir = report_dir / name
        found = sorted(
            str(path.relative_to(report_dir))
            for path in subdir.glob("*.json")
            if path.is_file()
        ) if subdir.exists() else []
        counts[name] = len(found)
        files[name] = found
    return {
        "report_dir": str(report_dir),
        "exists": report_dir.exists(),
        "counts": counts,
        "files": files,
    }


def _prepared_run_contract(run_root: Path) -> dict[str, Any]:
    """Return report-only checks for a prepared launch root."""

    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    command_text = _read_text(run_root / "command.txt")
    checks: dict[str, dict[str, Any]] = {}

    def add_check(name: str, passed: bool, detail: Any = "") -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    manifest_is_dict = isinstance(manifest, dict)
    add_check("manifest_present", manifest_path.exists(), str(manifest_path))
    add_check("manifest_json_object", manifest_is_dict, type(manifest).__name__)
    if not manifest_is_dict:
        return {
            "schema_version": PREPARED_RUN_CONTRACT_SCHEMA,
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "manifest_path": str(manifest_path),
            "manifest_present": manifest_path.exists(),
            "contract_complete": False,
            "problem_family": None,
            "model": None,
            "analysis_intent": None,
            "acceptance_focus": [],
            "research_focus": {},
            "resume_from_campaign": None,
            "control_pair_key": None,
            "completion_preflight": None,
            "postrun_reports": None,
            "checks": checks,
        }

    rendered_manifest = json.dumps(manifest, sort_keys=True)
    run_root_text = str(manifest.get("run_root") or "")
    campaign_dir_text = str(manifest.get("campaign_dir") or "")
    report_metadata = manifest.get("report_metadata")
    if not isinstance(report_metadata, dict):
        report_metadata = {}
    model = manifest.get("model")
    if not isinstance(model, dict):
        model = {}
    git = manifest.get("git")
    if not isinstance(git, dict):
        git = {}
    config = manifest.get("config")
    if not isinstance(config, dict):
        config = {}

    add_check(
        "manifest_schema",
        manifest.get("schema_version") == PREPARED_RUN_MANIFEST_SCHEMA,
        manifest.get("schema_version"),
    )
    for key in ("report_only", "decision_features_excluded"):
        add_check(f"manifest_{key}", manifest.get(key) is True, manifest.get(key))
    for key in (
        "quality_judgment",
        "campaign_state_mutated",
        "scheduler_state_mutated",
        "promotion_state_mutated",
    ):
        add_check(f"manifest_{key}", manifest.get(key) is False, manifest.get(key))
    add_check(
        "manifest_secret_free",
        "SCION_API_KEY" not in rendered_manifest,
        "SCION_API_KEY absent",
    )
    add_check(
        "run_root_identity",
        _same_path_or_leaf(run_root_text, run_root),
        run_root_text,
    )
    add_check(
        "campaign_dir_identity",
        _same_path_or_leaf(campaign_dir_text, run_root / "campaign"),
        campaign_dir_text,
    )

    command = str(manifest.get("command") or "")
    add_check("command_txt_present", bool(command_text.strip()), "command.txt")
    add_check(
        "command_matches_manifest",
        bool(command and command in command_text),
        command,
    )
    add_check(
        "prepared_manifest_pointer",
        _command_points_to_prepared_manifest(command_text, run_root, run_root_text),
        "PREPARED_RUN_MANIFEST",
    )
    add_check("model_is_gpt55", model.get("name") == "gpt-5.5", model.get("name"))
    add_check(
        "completion_preflight_enabled",
        model.get("completion_preflight") is True,
        model.get("completion_preflight"),
    )
    add_check(
        "control_pair_key_present",
        bool(report_metadata.get("control_pair_key")),
        report_metadata.get("control_pair_key"),
    )
    add_check(
        "postrun_reports_enabled",
        report_metadata.get("postrun_reports") is True,
        report_metadata.get("postrun_reports"),
    )
    families = report_metadata.get("postrun_acceptance_families")
    missing_families = [
        family for family in POSTRUN_REPORT_DIRS if family not in (families or [])
    ]
    add_check(
        "postrun_families_complete",
        isinstance(families, list) and not missing_families,
        ",".join(missing_families),
    )
    missing_config_paths = _missing_manifest_config_paths(
        config,
        manifest_run_root=run_root_text,
        local_run_root=run_root,
    )
    add_check(
        "config_paths_resolvable",
        not missing_config_paths,
        ",".join(missing_config_paths),
    )
    git_consistency = _git_runtime_consistency(git)
    add_check(
        "git_runtime_consistent",
        git_consistency.get("consistent") is True,
        git_consistency.get("detail"),
    )

    return {
        "schema_version": PREPARED_RUN_CONTRACT_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "manifest_path": str(manifest_path),
        "manifest_present": True,
        "contract_complete": all(item["passed"] for item in checks.values()),
        "problem_family": manifest.get("problem_family"),
        "model": model.get("name"),
        "analysis_intent": _string_or_none(manifest.get("analysis_intent")),
        "acceptance_focus": _string_items(manifest.get("acceptance_focus")),
        "research_focus": _mapping_or_empty(manifest.get("research_focus")),
        "resume_from_campaign": _string_or_none(manifest.get("resume_from_campaign")),
        "git": git_consistency,
        "control_pair_key": report_metadata.get("control_pair_key"),
        "completion_preflight": model.get("completion_preflight"),
        "postrun_reports": report_metadata.get("postrun_reports"),
        "checks": checks,
    }


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _prepared_contract_checks_for_markdown(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    checks = value.get("checks")
    if not isinstance(checks, dict):
        return {}
    return {
        str(key): item
        for key, item in sorted(checks.items())
        if isinstance(item, dict)
    }


def _same_path_or_leaf(manifest_path: str, local_path: Path) -> bool:
    if not manifest_path:
        return False
    remote = Path(manifest_path)
    if remote == local_path:
        return True
    if remote.name == local_path.name and local_path.name != "campaign":
        return True
    return (
        remote.name == local_path.name
        and remote.parent.name == local_path.parent.name
    )


def _command_points_to_prepared_manifest(
    command_text: str,
    run_root: Path,
    manifest_run_root: str,
) -> bool:
    for line in command_text.splitlines():
        if not line.startswith("PREPARED_RUN_MANIFEST="):
            continue
        raw_path = line.split("=", 1)[1].strip()
        if raw_path == str(run_root / "prepared_run_manifest.v1.json"):
            return True
        if raw_path == str(Path(manifest_run_root) / "prepared_run_manifest.v1.json"):
            return True
        prepared_path = Path(raw_path)
        return (
            prepared_path.name == "prepared_run_manifest.v1.json"
            and prepared_path.parent.name == run_root.name
        )
    return False


def _missing_manifest_config_paths(
    config: dict[str, Any],
    *,
    manifest_run_root: str,
    local_run_root: Path,
) -> list[str]:
    missing: list[str] = []
    for key, value in sorted(config.items()):
        if not isinstance(value, str) or not value.strip():
            continue
        if key.endswith("data_root") or key in {
            "warehouse_data_root",
            "problem_data_root",
        }:
            continue
        if _manifest_path_resolves(value, manifest_run_root, local_run_root):
            continue
        missing.append(f"{key}={value}")
    return missing


def _manifest_path_resolves(
    value: str,
    manifest_run_root: str,
    local_run_root: Path,
) -> bool:
    path = Path(value)
    candidates = [path]
    if not path.is_absolute():
        candidates.extend(
            (SCION_PROJECT_DIR / path, SCION_PROJECT_DIR / "scion" / path)
        )
    if manifest_run_root and value.startswith(manifest_run_root):
        try:
            candidates.append(local_run_root / Path(value).relative_to(manifest_run_root))
        except ValueError:
            pass
    return any(candidate.exists() for candidate in candidates)


def _git_runtime_consistency(git: dict[str, Any]) -> dict[str, Any]:
    manifest_commit = str(git.get("commit") or "").strip()
    runtime_guard_paths = str(git.get("runtime_guard_paths") or "").strip()
    checkout_commit = _git_output(("rev-parse", "--short", "HEAD"))
    if not manifest_commit:
        return {
            "consistent": False,
            "manifest_commit": None,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "missing manifest git.commit",
        }
    if not checkout_commit:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": None,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "unable to read checkout HEAD",
        }
    if checkout_commit == manifest_commit:
        return {
            "consistent": True,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout matches manifest commit",
        }
    if not runtime_guard_paths:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs and runtime guard paths are missing",
        }
    pathspecs = runtime_guard_paths.split()
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_DIR),
            "diff",
            "--quiet",
            f"{manifest_commit}..HEAD",
            "--",
            *pathspecs,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        return {
            "consistent": True,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs, but runtime guard paths are unchanged",
        }
    if diff.returncode == 1:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs and runtime guard paths changed",
        }
    detail = (diff.stderr or diff.stdout or "git diff failed").strip()
    return {
        "consistent": False,
        "manifest_commit": manifest_commit,
        "checkout_commit": checkout_commit,
        "runtime_guard_paths": runtime_guard_paths,
        "detail": detail,
    }


def _git_output(args: tuple[str, ...]) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _phase4_evidence_coverage(
    *,
    run_root: Path,
    campaign_dir: Path,
    campaign_status: Any,
    summary: Any,
    trace_index: Any,
    session_index: Any,
    llm_traces: dict[str, Any],
    lifecycle: Mapping[str, Any],
) -> dict[str, Any]:
    """Return report-only coverage flags for Phase 4 postrun analysis inputs."""

    if _launch_root_without_current_run(lifecycle):
        return {
            "schema_version": "scion.postrun_phase4_evidence_coverage.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "evidence_scope": lifecycle.get("evidence_scope") or "launch_root",
            "prepared_only": lifecycle.get("prepared_only") is True,
            "pre_campaign_completion_preflight_failed": (
                lifecycle.get("pre_campaign_completion_preflight_failed") is True
            ),
            "current_run_evidence": False,
            "requirements": _empty_phase4_requirements(
                "not current-run evidence"
            ),
            "analysis_handoff": HANDOFF_DOC,
        }

    trace_coverage = _phase4_trace_coverage(
        campaign_dir=campaign_dir,
        trace_index=trace_index,
        session_index=session_index,
    )
    research_docs = _postrun_json_docs(run_root, "research_efficiency")
    manifest_docs = _postrun_json_docs(run_root, "manifests")
    source_docs = [
        doc for doc in (summary, campaign_status, *research_docs, *manifest_docs) if doc
    ]
    formal_rows = _jsonl_row_count(
        campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    prompt_manifest_loaded_count = sum(
        _nested_int(doc, ("prompt_manifest_loaded_count",)) or 0
        for doc in manifest_docs
    )
    prompt_manifest_refs = trace_coverage.get("prompt_manifest_ref_count", 0)
    measurement_readiness_count = sum(
        1
        for doc in (summary, campaign_status, *research_docs)
        if _contains_key_fragment(doc, ("measurement_readiness",))
    )
    effect_vs_mde_count = sum(
        1
        for doc in research_docs
        if _contains_key_fragment(doc, ("protocol_effects_vs_mde", "mde_source"))
    )
    branch_lesson_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(doc, ("branch_lesson", "cross_branch"))
    )
    runtime_feedback_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(
            doc,
            (
                "runtime_feedback",
                "runtime_budget",
                "fresh_runtime_replay",
                "runtime_regression",
            ),
        )
    )
    source_visibility_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(
            doc,
            ("source_visibility", "target_source_visibility", "visibility_ledger"),
        )
    )

    return {
        "schema_version": "scion.postrun_phase4_evidence_coverage.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "evidence_scope": lifecycle.get("evidence_scope") or "postrun_campaign",
        "prepared_only": lifecycle.get("prepared_only") is True,
        "pre_campaign_completion_preflight_failed": (
            lifecycle.get("pre_campaign_completion_preflight_failed") is True
        ),
        "current_run_evidence": True,
        "requirements": {
            "target_intent_trace": _coverage_item(
                trace_coverage.get("target_intent_trace_count", 0),
                "llm_traces or trace_index",
            ),
            "hypothesis_trace": _coverage_item(
                _int_or_zero(llm_traces.get("by_kind", {}).get("hypothesis")),
                "llm_traces",
            ),
            "code_trace": _coverage_item(
                _int_or_zero(llm_traces.get("by_kind", {}).get("code")),
                "llm_traces",
            ),
            "formal_candidate_artifact": _coverage_item(
                formal_rows,
                "campaign/artifacts/formal_candidates/index.jsonl",
            ),
            "proposal_trajectory_manifest": _coverage_item(
                len(manifest_docs),
                "postrun_acceptance/manifests",
            ),
            "prompt_manifest_loaded": _coverage_item(
                prompt_manifest_loaded_count or prompt_manifest_refs,
                "proposal_trajectory_manifest or trace_index prompt_manifest refs",
            ),
            "research_efficiency_report": _coverage_item(
                len(research_docs),
                "postrun_acceptance/research_efficiency",
            ),
            "measurement_readiness": _coverage_item(
                measurement_readiness_count,
                "campaign summary/status or research-efficiency report",
            ),
            "protocol_effect_vs_mde": _coverage_item(
                effect_vs_mde_count,
                "research-efficiency protocol_effects_vs_mde",
            ),
            "branch_lesson_transfer": _coverage_item(
                branch_lesson_count,
                "summary/status, research-efficiency, or trajectory manifest",
            ),
            "runtime_feedback": _coverage_item(
                runtime_feedback_count,
                "summary/status or research-efficiency runtime fields",
            ),
            "source_visibility": _coverage_item(
                source_visibility_count,
                "prompt manifests or trajectory visibility fingerprints",
            ),
        },
        "analysis_handoff": HANDOFF_DOC,
    }


def _empty_phase4_requirements(reason: str) -> dict[str, dict[str, Any]]:
    sources = {
        "target_intent_trace": "llm_traces or trace_index",
        "hypothesis_trace": "llm_traces",
        "code_trace": "llm_traces",
        "formal_candidate_artifact": "campaign/artifacts/formal_candidates/index.jsonl",
        "proposal_trajectory_manifest": "postrun_acceptance/manifests",
        "prompt_manifest_loaded": (
            "proposal_trajectory_manifest or trace_index prompt_manifest refs"
        ),
        "research_efficiency_report": "postrun_acceptance/research_efficiency",
        "measurement_readiness": (
            "campaign summary/status or research-efficiency report"
        ),
        "protocol_effect_vs_mde": "research-efficiency protocol_effects_vs_mde",
        "branch_lesson_transfer": (
            "summary/status, research-efficiency, or trajectory manifest"
        ),
        "runtime_feedback": "summary/status or research-efficiency runtime fields",
        "source_visibility": "prompt manifests or trajectory visibility fingerprints",
    }
    return {
        key: _coverage_item(0, f"{source}; {reason}")
        for key, source in sources.items()
    }


def _phase4_trace_coverage(
    *,
    campaign_dir: Path,
    trace_index: Any,
    session_index: Any,
) -> dict[str, int]:
    file_target_intent_count = 0
    index_target_intent_count = 0
    prompt_manifest_ref_count = 0
    for path in sorted((campaign_dir / "llm_traces").glob("*.json")):
        doc = _read_json(path)
        if _is_target_intent_trace(doc, path):
            file_target_intent_count += 1
        if _prompt_manifest_ref_present(doc):
            prompt_manifest_ref_count += 1
    for entry in _trace_index_entries(trace_index):
        if _is_target_intent_trace(entry, None):
            index_target_intent_count += 1
        if _prompt_manifest_ref_present(entry):
            prompt_manifest_ref_count += 1
    for entry in _session_index_entries(session_index):
        if _prompt_manifest_ref_present(entry):
            prompt_manifest_ref_count += 1
    return {
        "target_intent_trace_count": max(
            file_target_intent_count,
            index_target_intent_count,
        ),
        "prompt_manifest_ref_count": prompt_manifest_ref_count,
    }


def _coverage_item(count: int | None, source: str) -> dict[str, Any]:
    safe_count = _int_or_zero(count)
    return {"available": safe_count > 0, "count": safe_count, "source": source}


def _phase4_requirements_for_markdown(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    requirements = value.get("requirements")
    if not isinstance(requirements, dict):
        return {}
    return {
        str(key): item
        for key, item in sorted(requirements.items())
        if isinstance(item, dict)
    }


def _postrun_json_docs(run_root: Path, family: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    subdir = run_root / "postrun_acceptance" / family
    if not subdir.exists():
        return docs
    for path in sorted(subdir.glob("*.json")):
        doc = _read_json(path)
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


def _jsonl_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _contains_key_fragment(value: Any, fragments: tuple[str, ...]) -> bool:
    lowered_fragments = tuple(fragment.lower() for fragment in fragments)
    if isinstance(value, dict):
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(fragment in lowered_key for fragment in lowered_fragments):
                return True
            if _contains_key_fragment(item, fragments):
                return True
    elif isinstance(value, list):
        return any(_contains_key_fragment(item, fragments) for item in value)
    return False


def _status_fields(run_status: Any) -> dict[str, Any]:
    if not isinstance(run_status, dict):
        return {}
    return {
        key: run_status[key]
        for key in LAUNCHER_STATUS_KEYS
        if key in run_status
    }


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _marker_counts(text: str, markers: tuple[str, ...]) -> dict[str, int]:
    marker_set = set(markers)
    counts: Counter[str] = Counter()
    for raw_line in text.splitlines():
        key = raw_line.split(":", 1)[0].strip()
        if key in marker_set:
            counts[key] += 1
    return dict(sorted(counts.items()))


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
    name = path.name.lower()
    if "target_intent" in name:
        return "hypothesis_target_intent"
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
    if value and "target_intent" in value.lower():
        return "hypothesis_target_intent"
    if value:
        return value
    if "hypothesis" in name:
        return "hypothesis"
    if "code" in name:
        return "code"
    return "unknown"


def _is_target_intent_trace(doc: Any, path: Path | None) -> bool:
    if path is not None and "target_intent" in path.name.lower():
        return True
    if not isinstance(doc, dict):
        return False
    value = _first_string(
        doc,
        keys=("trace_kind", "request_kind", "call_kind", "kind", "phase", "stage"),
    )
    if value and "target_intent" in value.lower():
        return True
    return _contains_key_fragment(doc, ("target_intent",))


def _prompt_manifest_ref_present(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if _first_string(
        doc,
        keys=(
            "prompt_manifest_artifact_ref",
            "prompt_manifest_ref",
            "prompt_manifest",
        ),
    ):
        return True
    refs = doc.get("prompt_manifest_artifact_refs") or doc.get("prompt_manifest_refs")
    return isinstance(refs, list) and bool(refs)


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
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = _tables(conn)
            branches = _branches(conn) if "branches" in tables else []
            events = (
                _events(conn) if "experiment_events" in tables else _empty_events()
            )
            hypotheses = (
                _hypotheses(conn) if "hypotheses" in tables else _empty_hypotheses()
            )
    except sqlite3.DatabaseError as exc:
        empty = _empty_db_inventory()
        empty["read_error"] = f"{type(exc).__name__}: {exc}"
        return empty
    return {"branches": branches, "events": events, "hypotheses": hypotheses}


def _empty_db_inventory() -> dict[str, Any]:
    return {
        "branches": [],
        "events": _empty_events(),
        "hypotheses": _empty_hypotheses(),
        "read_error": None,
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
        value = _nested_int(doc, keys)
        if value is not None:
            return value
    return None


def _nested_int(doc: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    value = _nested_first(doc, keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _counter_text(counter: dict[str, int]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def _mapping_text(mapping: dict[str, Any]) -> str:
    if not mapping:
        return "none"
    return ", ".join(
        f"{key}={_display(value)}" for key, value in sorted(mapping.items())
    )


def _existing_artifact_text(artifacts: dict[str, bool]) -> str:
    present = [key for key, exists in sorted(artifacts.items()) if exists]
    return ", ".join(present) if present else "none"


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
