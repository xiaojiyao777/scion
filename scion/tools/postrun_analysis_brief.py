#!/usr/bin/env python3
"""Build a report-only post-run analysis brief for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_artifact_inventory import HANDOFF_DOC, build_inventory  # noqa: E402


SCHEMA_VERSION = "scion.postrun_analysis_brief.v1"
ARCHITECTURE_DOC = "scion/design/scion-architecture-v3.md"
CURRENT_STATE_DOC = "scion/docs/status/current-state.md"

REQUIRED_QUESTIONS = (
    "Did the run complete enough formal candidates to be valid for its requested effective budget?",
    "Did the agent perform effective research, or only satisfy framework controls?",
    "Were branch hypotheses and code changes internally coherent?",
    "Did branch-local follow-up and rollback/checkpoint behavior make sense?",
    "Did the agent see enough of the declared problem object and selected surface before writing outputs?",
    "Were LLM tool calls relevant, non-looping, and useful?",
    "Did preview/smoke evidence and later prompts line up?",
    "Did sibling and historical lessons transfer without entering DecisionFeatures?",
    "Did research_continuity show same-mechanism follow-up, "
    "branch-lesson satisfaction or semantic gaps, and weak-positive transfer?",
    "Were repeated near-duplicate branches avoided or correctly diagnosed?",
    "Are failures framework/control regressions, provider/infra failures, or algorithm-quality failures?",
    "Is the next step repair, same-round rerun, or ladder advancement?",
)


def build_brief(run_root: Path | str) -> dict[str, Any]:
    inventory = build_inventory(run_root)
    run_root_path = Path(inventory["run_root"])
    campaign_dir = Path(inventory["campaign_dir"])
    return {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(run_root_path),
        "campaign_dir": str(campaign_dir),
        "handoff_doc": HANDOFF_DOC,
        "architecture_doc": ARCHITECTURE_DOC,
        "current_state_doc": CURRENT_STATE_DOC,
        "lifecycle": inventory["lifecycle"],
        "validity": inventory["validity"],
        "counters": inventory["counters"],
        "llm_traces": inventory["llm_traces"],
        "branches": {
            "count": len(inventory["branches"]),
            "ids": [branch["branch_id"] for branch in inventory["branches"]],
        },
        "resume_snapshot": inventory.get("resume_snapshot", {"present": False}),
        "artifact_checklist": _artifact_checklist(run_root_path, campaign_dir),
        "prepared_run_contract": inventory["launcher"]["prepared_run_contract"],
        "postrun_reports": inventory["postrun_reports"],
        "phase4_evidence_coverage": inventory["phase4_evidence_coverage"],
        "research_continuity_summary": _research_continuity_summary(
            run_root_path,
            inventory,
        ),
        "stop_conditions": _stop_conditions(inventory),
        "required_questions": list(REQUIRED_QUESTIONS),
    }


def render_markdown(brief: dict[str, Any]) -> str:
    validity = brief["validity"]
    counters = brief["counters"]
    lifecycle = brief.get("lifecycle") or {}
    prepared_only = lifecycle.get("prepared_only") is True
    title = "Prepared Analysis Brief" if prepared_only else "Post-Run Analysis Brief"
    lines = [
        f"# {title}: {Path(brief['run_root']).name}",
        "",
        "- Schema: `scion.postrun_analysis_brief.v1`",
        "- Scope: report-only delegated analysis input.",
        "- Boundary: tainted LLM traces and postrun diagnostics may guide analysis, "
        "but must not become `DecisionFeatures` or promotion input.",
        f"- Handoff doc: `{brief['handoff_doc']}`",
        f"- Architecture doc: `{brief['architecture_doc']}`",
        f"- Current state doc: `{brief['current_state_doc']}`",
        "",
        "## Inputs",
        f"- RUN_ROOT: `{brief['run_root']}`",
        f"- CAMPAIGN_DIR: `{brief['campaign_dir']}`",
        "",
        "## Lifecycle",
        f"- Prepared only: `{_display(lifecycle.get('prepared_only'))}`",
        f"- Evidence scope: `{_display(lifecycle.get('evidence_scope'))}`",
        "- Resume from campaign: "
        f"`{_display(lifecycle.get('resume_from_campaign'))}`",
        "",
        "## Stop Conditions",
    ]
    stop_conditions = brief.get("stop_conditions") or []
    if stop_conditions:
        lines.extend(f"- {condition}" for condition in stop_conditions)
    else:
        lines.append("- None from the inventory. Continue with branch-centric analysis.")

    resume_snapshot = brief.get("resume_snapshot")
    if isinstance(resume_snapshot, dict) and resume_snapshot.get("present") is True:
        lines.extend(
            [
                "",
                "## Resume Snapshot",
                "- Copied campaign artifacts are launch input, not current-run evidence.",
                "- Current-run evidence: "
                f"`{_display(resume_snapshot.get('current_run_evidence'))}`",
                "- Evidence scope: "
                f"`{_display(resume_snapshot.get('evidence_scope'))}`",
                "- Source campaign: "
                f"`{_display(resume_snapshot.get('resume_from_campaign'))}`",
                f"- Branches: {_display(resume_snapshot.get('branch_count'))}",
                f"- LLM traces: {_display(resume_snapshot.get('llm_trace_count'))}",
                "- Indexed LLM traces/sessions: "
                f"{_display(resume_snapshot.get('llm_index_trace_count'))} / "
                f"{_display(resume_snapshot.get('llm_index_session_count'))}",
                f"- LLM kinds: {_mapping_text(resume_snapshot.get('llm_by_kind'))}",
                f"- LLM statuses: {_mapping_text(resume_snapshot.get('llm_by_status'))}",
                f"- Events by kind: {_mapping_text(resume_snapshot.get('events_by_kind'))}",
                "- Events by decision: "
                f"{_mapping_text(resume_snapshot.get('events_by_decision'))}",
                f"- Events by stage: {_mapping_text(resume_snapshot.get('events_by_stage'))}",
                f"- Hypotheses: {_display(resume_snapshot.get('hypothesis_count'))}",
                "- Hypotheses by status: "
                f"{_mapping_text(resume_snapshot.get('hypotheses_by_status'))}",
            ]
        )

    lines.extend(
        [
            "",
            "## Validity And Counters",
            f"- Validity: `{validity.get('run_validity_status') or 'unknown'}`",
            f"- Completeness: `{validity.get('run_completeness_status') or 'unknown'}`",
            f"- Last stop reason: `{validity.get('last_stop_reason') or 'unknown'}`",
            "| Counter | Value |",
            "|---|---:|",
        ]
    )
    for key, value in counters.items():
        lines.append(f"| {key} | {_display(value)} |")

    lines.extend(
        [
            "",
            "## Artifact Checklist",
            "| Artifact | Present | Path |",
            "|---|---:|---|",
        ]
    )
    for item in brief["artifact_checklist"]:
        lines.append(
            "| {name} | {present} | `{path}` |".format(
                name=item["name"],
                present=_display(item["present"]),
                path=item["path"],
            )
        )

    prepared_contract = brief.get("prepared_run_contract") or {}
    lines.extend(
        [
            "",
            "## Prepared Run Contract",
            f"- Complete: `{_display(prepared_contract.get('contract_complete'))}`",
            "- Problem/model: "
            f"`{_display(prepared_contract.get('problem_family'))}` / "
            f"`{_display(prepared_contract.get('model'))}`",
            "- Control pair: "
            f"`{_display(prepared_contract.get('control_pair_key'))}`",
            "- Resume from campaign: "
            f"`{_display(prepared_contract.get('resume_from_campaign'))}`",
            f"- Analysis intent: {_display(prepared_contract.get('analysis_intent'))}",
            "- Acceptance focus:",
        ]
    )
    acceptance_focus = prepared_contract.get("acceptance_focus")
    if isinstance(acceptance_focus, list) and acceptance_focus:
        lines.extend(f"  - {_display(item)}" for item in acceptance_focus)
    else:
        lines.append("  - None recorded in the prepared manifest.")

    research_focus = prepared_contract.get("research_focus")
    if isinstance(research_focus, dict) and research_focus:
        lines.extend(
            [
                "- Current research focus:",
                f"  - Accepted checkpoint: {_display(research_focus.get('accepted_checkpoint'))}",
                f"  - Question: {_display(research_focus.get('current_question'))}",
                "  - Required evidence:",
            ]
        )
        required = research_focus.get("required_evidence")
        if isinstance(required, list) and required:
            lines.extend(f"    - {_display(item)}" for item in required)
        else:
            lines.append("    - None recorded in the prepared manifest.")
        lines.extend(
            [
                "  - Default-avoid directions:",
            ]
        )
        avoid = research_focus.get("default_avoid_directions")
        if isinstance(avoid, list) and avoid:
            lines.extend(f"    - {_display(item)}" for item in avoid)
        else:
            lines.append("    - None recorded in the prepared manifest.")
        for key, label in (
            ("route_merge_exception_rule", "Route-merge exception"),
            ("construction_seed_rule", "Construction-seed rule"),
            ("decision_boundary", "Decision boundary"),
        ):
            value = research_focus.get(key)
            if value:
                lines.append(f"  - {label}: {_display(value)}")

    lines.extend(
        [
            "| Check | Passed | Detail |",
            "|---|---:|---|",
        ]
    )
    checks = prepared_contract.get("checks")
    if isinstance(checks, dict):
        for key, item in sorted(checks.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {key} | {passed} | {detail} |".format(
                    key=key,
                    passed=_display(item.get("passed")),
                    detail=_display(item.get("detail")),
                )
            )

    phase4 = brief["phase4_evidence_coverage"]
    lines.extend(
        [
            "",
            "## Phase 4 Evidence Coverage",
            f"- Evidence scope: `{_display(phase4.get('evidence_scope'))}`",
            f"- Prepared only: `{_display(phase4.get('prepared_only'))}`",
            "| Requirement | Available | Count | Source |",
            "|---|---:|---:|---|",
        ]
    )
    requirements = phase4.get("requirements") if isinstance(phase4, dict) else {}
    if isinstance(requirements, dict):
        for key, item in sorted(requirements.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {key} | {available} | {count} | {source} |".format(
                    key=key,
                    available=_display(item.get("available")),
                    count=_display(item.get("count")),
                    source=_display(item.get("source")),
                )
            )

    continuity = brief.get("research_continuity_summary") or {}
    lines.extend(
        [
            "",
            "## Research Continuity Summary",
            "- Source: current-run research-efficiency `research_continuity` reports.",
            f"- Available: `{_display(continuity.get('available'))}`",
            "- Current-run evidence: "
            f"`{_display(continuity.get('current_run_evidence'))}`",
            "- Reports with continuity: "
            f"`{_display(continuity.get('continuity_report_count'))}`",
        ]
    )
    entries = continuity.get("entries")
    if isinstance(entries, list) and entries:
        lines.extend(
            [
                "| Report | Same-mechanism selected/observed | "
                "Branch lessons satisfied/required | Semantic gaps | "
                "Weak-positive accepted/observed | Max depth | Families |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            same_mechanism = _mapping_or_empty(
                entry.get("same_mechanism_followup")
            )
            lessons = _mapping_or_empty(entry.get("branch_lesson_usage"))
            transfer = _mapping_or_empty(entry.get("weak_positive_transfer"))
            shape = _mapping_or_empty(entry.get("research_shape_summary"))
            lines.append(
                "| {report} | {same_selected}/{same_observed} | "
                "{lesson_satisfied}/{lesson_required} | {semantic_gap} | "
                "{transfer_accepted}/{transfer_observed} | {max_depth} | "
                "{families} |".format(
                    report=_display(entry.get("report")),
                    same_selected=_display(
                        same_mechanism.get(
                            "selected_same_branch_refinement_count"
                        )
                    ),
                    same_observed=_display(
                        same_mechanism.get("observed_opportunity_count")
                    ),
                    lesson_satisfied=_display(lessons.get("satisfied_count")),
                    lesson_required=_display(lessons.get("requirement_count")),
                    semantic_gap=_display(lessons.get("semantic_gap_count")),
                    transfer_accepted=_display(transfer.get("accepted_count")),
                    transfer_observed=_display(
                        transfer.get("observed_opportunity_count")
                    ),
                    max_depth=_display(shape.get("max_branch_depth")),
                    families=_display(shape.get("mechanism_family_count")),
                )
            )
    else:
        lines.append(
            "- No current-run research_continuity block is available for delegated analysis."
        )

    llm = brief["llm_traces"]
    branches = brief["branches"]
    lines.extend(
        [
            "",
            "## Inventory Summary",
            f"- Branch count: {branches['count']}",
            f"- Branch ids: {_list_text(branches['ids'])}",
            f"- LLM trace files: {llm['trace_count']}",
            f"- LLM trace index entries: {llm['index_trace_count']}",
            f"- LLM sessions: {llm['index_session_count']}",
            f"- LLM trace kinds: {_mapping_text(llm['by_kind'])}",
            f"- LLM trace statuses: {_mapping_text(llm['by_status'])}",
            "",
            "## Minimum Delegated Analysis",
            "- Start branch-centric, then round/LLM-call centric.",
            "- For prepared-only roots, stop at launcher contract/readiness review; do not make research-quality conclusions until the root has been launched and postrun reports exist.",
            "- Cite artifact paths, branch ids, trace ids, SQL rows, or JSON fields for every conclusion.",
            "- For invalid infra-only runs, stop after proving the infra status.",
            "- For valid runs, inspect target intent, hypothesis, code, tool calls, formal candidates, Protocol/Decision, branch lessons, runtime feedback, and source visibility.",
            "- Decide whether the next action is repair, same-round rerun, or ladder advancement.",
            "",
            "## Required Answers",
        ]
    )
    for index, question in enumerate(brief["required_questions"], start=1):
        lines.append(f"{index}. {question}")

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

    brief = build_brief(Path(args.run_root))
    if args.format == "json":
        print(json.dumps(brief, indent=2, sort_keys=True))
    else:
        print(render_markdown(brief), end="")
    return 0


def _artifact_checklist(run_root: Path, campaign_dir: Path) -> list[dict[str, Any]]:
    paths = {
        "outer_run_status": run_root / "run_status.json",
        "outer_run_log": run_root / "run.log",
        "outer_exit": run_root / "exit.txt",
        "outer_command": run_root / "command.txt",
        "outer_launch_env": run_root / "launch.env",
        "prepared_run_manifest_json": run_root / "prepared_run_manifest.v1.json",
        "prepared_run_manifest_markdown": run_root / "prepared_run_manifest.md",
        "prepared_handoff": run_root / "prepared_handoff",
        "campaign_status": campaign_dir / "status.json",
        "campaign_run_status": campaign_dir / "run_status.json",
        "campaign_summary": campaign_dir / "campaign_summary.json",
        "campaign_database": campaign_dir / "scion.db",
        "agentic_session_index": campaign_dir
        / "agentic_sessions"
        / "agentic_session_index.json",
        "agentic_trace_index": campaign_dir
        / "agentic_sessions"
        / "agentic_session_trace_index.json",
        "llm_traces_dir": campaign_dir / "llm_traces",
        "metrics_dir": campaign_dir / "metrics",
        "postrun_acceptance": run_root / "postrun_acceptance",
    }
    return [
        {"name": name, "path": str(path), "present": path.exists()}
        for name, path in paths.items()
    ]


def _research_continuity_summary(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": "scion.postrun_research_continuity_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "report_count": 0,
        "continuity_report_count": 0,
        "entries": [],
    }
    if not current_run_evidence:
        return base

    report_paths = _research_efficiency_report_paths(run_root, inventory)
    entries = []
    for path in report_paths:
        doc = _read_json_object(path)
        continuity = doc.get("research_continuity")
        if not isinstance(continuity, Mapping) or not continuity:
            continue
        entries.append(
            {
                "report": path.name,
                "path": str(path),
                "same_mechanism_followup": _mapping_or_empty(
                    continuity.get("same_mechanism_followup")
                ),
                "branch_lesson_usage": _mapping_or_empty(
                    continuity.get("branch_lesson_usage")
                ),
                "weak_positive_transfer": _mapping_or_empty(
                    continuity.get("weak_positive_transfer")
                ),
                "lesson_action_counts": _mapping_or_empty(
                    continuity.get("lesson_action_counts")
                ),
                "research_shape_summary": _mapping_or_empty(
                    continuity.get("research_shape_summary")
                ),
            }
        )

    return {
        **base,
        "available": bool(entries),
        "report_count": len(report_paths),
        "continuity_report_count": len(entries),
        "entries": entries,
    }


def _research_efficiency_report_paths(
    run_root: Path,
    inventory: Mapping[str, Any],
) -> list[Path]:
    reports = _mapping_or_empty(inventory.get("postrun_reports"))
    files = reports.get("files")
    if isinstance(files, Mapping):
        research_files = files.get("research_efficiency")
        if isinstance(research_files, list):
            report_dir = run_root / "postrun_acceptance"
            return sorted(
                report_dir / str(path)
                for path in research_files
                if str(path).endswith(".json")
            )
    return sorted(
        path
        for path in (run_root / "postrun_acceptance" / "research_efficiency").glob(
            "*.json"
        )
        if path.is_file()
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _stop_conditions(inventory: dict[str, Any]) -> list[str]:
    lifecycle = inventory.get("lifecycle") or {}
    if lifecycle.get("prepared_only") is True:
        return [
            "PREPARED-ONLY ROOT: do not analyze copied campaign artifacts as current-run research evidence.",
            "Launch only after completion preflight succeeds, then regenerate/read postrun_acceptance reports before research-quality conclusions.",
        ]
    validity = inventory.get("validity") or {}
    counters = inventory.get("counters") or {}
    conditions: list[str] = []
    if validity.get("invalid_infra_only") is True:
        conditions.append(
            "INVALID INFRA-ONLY RUN: prove provider/proxy/account status and do not analyze as research behavior."
        )
    if _int_or_zero(counters.get("effective_rounds_completed")) == 0:
        conditions.append(
            "No effective rounds recorded: treat as invalid for research-quality conclusions until contradicted by stronger artifacts."
        )
    if _int_or_zero(counters.get("formal_screened_candidates")) == 0:
        conditions.append(
            "No formal screened candidates recorded: do not infer algorithm quality from this run."
        )
    return conditions


def _display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _list_text(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def _mapping_text(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "none"
    return ", ".join(f"{key}={value[key]}" for key in sorted(value))


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
