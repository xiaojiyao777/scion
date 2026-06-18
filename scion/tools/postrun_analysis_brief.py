#!/usr/bin/env python3
"""Build a report-only post-run analysis brief for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
        "validity": inventory["validity"],
        "counters": inventory["counters"],
        "llm_traces": inventory["llm_traces"],
        "branches": {
            "count": len(inventory["branches"]),
            "ids": [branch["branch_id"] for branch in inventory["branches"]],
        },
        "artifact_checklist": _artifact_checklist(run_root_path, campaign_dir),
        "postrun_reports": inventory["postrun_reports"],
        "phase4_evidence_coverage": inventory["phase4_evidence_coverage"],
        "stop_conditions": _stop_conditions(inventory),
        "required_questions": list(REQUIRED_QUESTIONS),
    }


def render_markdown(brief: dict[str, Any]) -> str:
    validity = brief["validity"]
    counters = brief["counters"]
    lines = [
        f"# Post-Run Analysis Brief: {Path(brief['run_root']).name}",
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
        "## Stop Conditions",
    ]
    stop_conditions = brief.get("stop_conditions") or []
    if stop_conditions:
        lines.extend(f"- {condition}" for condition in stop_conditions)
    else:
        lines.append("- None from the inventory. Continue with branch-centric analysis.")

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

    phase4 = brief["phase4_evidence_coverage"]
    lines.extend(
        [
            "",
            "## Phase 4 Evidence Coverage",
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


def _stop_conditions(inventory: dict[str, Any]) -> list[str]:
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


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
