#!/usr/bin/env python3
"""Inventory post-run Scion artifacts without judging research quality."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))

from scion.postrun.inventory.loader import HANDOFF_DOC  # noqa: E402
from scion.postrun.inventory.prepared_contract import (
    command_has_shell_flag,
)  # noqa: E402
from scion.problems.postrun_inventory import (
    build_problem_inventory as build_inventory,
)  # noqa: E402


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
    if lifecycle.get("launcher_status_unavailable") is True:
        lines.append(
            "- LAUNCHER STATUS UNAVAILABLE: root `run_status.json` is missing "
            "or unreadable, so copied campaign artifacts are not current-run "
            "postrun evidence."
        )
    if lifecycle.get("pre_campaign_completion_preflight_failed") is True:
        lines.append(
            "- PRE-CAMPAIGN PREFLIGHT FAILED: no current Scion campaign ran; "
            "copied campaign artifacts are resume input, not current-run evidence."
        )
    if lifecycle.get("pre_campaign_infra_failed") is True:
        keys = ", ".join(lifecycle.get("pre_campaign_infra_failure_keys") or [])
        lines.append(
            "- PRE-CAMPAIGN INFRA FAILURE: no current Scion campaign ran; "
            f"failure keys `{keys}` mark copied campaign artifacts as resume input, "
            "not current-run evidence."
        )
    if lifecycle.get("campaign_execution_artifacts_unavailable") is True:
        lines.append(
            "- CAMPAIGN EXECUTION ARTIFACTS UNAVAILABLE: root launcher status "
            "is not enough to prove current-run research evidence; copied or "
            "partial campaign artifacts are treated as resume snapshots."
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

    resume_snapshot = inventory.get("resume_snapshot")
    if isinstance(resume_snapshot, dict) and resume_snapshot.get("present") is True:
        lines.extend(
            [
                "",
                "## Resume Snapshot",
                "- Copied campaign artifacts are launch input, not current-run evidence.",
                f"- Source: {_display(resume_snapshot.get('resume_from_campaign'))}",
                f"- Branches: {_display(resume_snapshot.get('branch_count'))}",
                f"- LLM traces: {_display(resume_snapshot.get('llm_trace_count'))}",
                f"- Events: {_counter_text(resume_snapshot.get('events_by_kind', {}))}",
                f"- Hypotheses: {_display(resume_snapshot.get('hypothesis_count'))}",
            ]
        )
        branches = resume_snapshot.get("branches")
        if isinstance(branches, list) and branches:
            lines.extend(
                [
                    "",
                    "### Resume Snapshot Branches",
                    "| Branch | State | Lineage | Mechanisms | Next action | Follow-up | Failures |",
                    "|---|---|---|---|---|---|---|",
                ]
            )
            for branch in branches:
                if not isinstance(branch, Mapping):
                    continue
                followup = _resume_branch_followup_text(branch)
                lines.append(
                    "| {branch_id} | {state} | {lineage_id} | {mechanisms} | "
                    "{next_action} | {followup} | {failures} |".format(
                        branch_id=_display(branch.get("branch_id")),
                        state=_display(branch.get("state")),
                        lineage_id=_display(branch.get("lineage_id")),
                        mechanisms=_display(branch.get("mechanism_ids")),
                        next_action=_display(branch.get("next_action")),
                        followup=followup,
                        failures=_display(branch.get("failure_codes")),
                    )
                )
                card_text = branch.get("branch_card_text")
                if card_text:
                    lines.append(
                        f"- `{_display(branch.get('branch_id'))}`: {card_text}"
                    )

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
        measurement = research_focus.get("measurement_opportunity_diagnostics")
        lines.append("- Measurement/opportunity diagnostics:")
        if isinstance(measurement, dict) and measurement:
            for key in (
                "metric",
                "runtime_model",
                "pairing_validity",
                "practical_screen_delta",
                "screening_mde_at_power_80",
                "recommended_min_seeds",
                "summary",
            ):
                value = measurement.get(key)
                if value not in (None, "", [], {}, ()):
                    lines.append(f"  - {key}: {_display(value)}")
            reason_codes = measurement.get("reason_codes")
            if isinstance(reason_codes, list) and reason_codes:
                lines.append(
                    "  - reason_codes: "
                    + ", ".join(_display(item) for item in reason_codes)
                )
        else:
            lines.append("  - None recorded in the prepared manifest.")
        opportunity_classes = research_focus.get("measurable_opportunity_classes")
        lines.append("- Measurable opportunity classes:")
        if isinstance(opportunity_classes, list) and opportunity_classes:
            lines.extend(f"  - {_display(item)}" for item in opportunity_classes)
        else:
            lines.append("  - None recorded in the prepared manifest.")
        for key, label in (
            ("route_merge_exception_rule", "Route-merge exception"),
            ("construction_seed_rule", "Construction-seed rule"),
            ("missing_primary_telemetry_rule", "Missing-primary telemetry rule"),
            ("decision_boundary", "Decision boundary"),
        ):
            value = research_focus.get(key)
            if value:
                lines.append(f"- {label}: {_display(value)}")
        case_protection = research_focus.get("case_protection_requirements")
        if isinstance(case_protection, dict) and case_protection:
            lines.append("- Case-protection requirements:")
            protected_cases = case_protection.get("protected_cases")
            if isinstance(protected_cases, list) and protected_cases:
                lines.append(
                    "  - protected_cases: "
                    + ", ".join(_display(item) for item in protected_cases)
                )
            rules = case_protection.get("rules")
            if isinstance(rules, list) and rules:
                lines.append("  - rules:")
                lines.extend(f"    - {_display(item)}" for item in rules)
            evidence = case_protection.get("required_evidence")
            if isinstance(evidence, list) and evidence:
                lines.append("  - required_evidence:")
                lines.extend(f"    - {_display(item)}" for item in evidence)
        resume_continuity = research_focus.get("resume_continuity_requirements")
        if isinstance(resume_continuity, dict) and resume_continuity:
            lines.append("- Resume-continuity requirements:")
            fallback_sources = resume_continuity.get("fallback_sources")
            if isinstance(fallback_sources, list) and fallback_sources:
                lines.append("  - fallback_sources:")
                lines.extend(f"    - {_display(item)}" for item in fallback_sources)
            rules = resume_continuity.get("rules")
            if isinstance(rules, list) and rules:
                lines.append("  - rules:")
                lines.extend(f"    - {_display(item)}" for item in rules)
            evidence = resume_continuity.get("required_evidence")
            if isinstance(evidence, list) and evidence:
                lines.append("  - required_evidence:")
                lines.extend(f"    - {_display(item)}" for item in evidence)

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
    problem_specific = _phase4_problem_specific_for_markdown(
        inventory.get("phase4_evidence_coverage")
    )
    if problem_specific:
        lines.extend(
            [
                "",
                "### Problem-Specific Phase 4 Evidence Coverage",
                "| Requirement | Available | Count | Source |",
                "|---|---:|---:|---|",
            ]
        )
        for key, item in problem_specific.items():
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


def _prepared_contract_checks_for_markdown(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    checks = value.get("checks")
    if not isinstance(checks, dict):
        return {}
    return {
        str(key): item for key, item in sorted(checks.items()) if isinstance(item, dict)
    }


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


def _phase4_problem_specific_for_markdown(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    requirements = value.get("problem_specific_requirements")
    if not isinstance(requirements, dict):
        return {}
    return {
        str(key): item
        for key, item in sorted(requirements.items())
        if isinstance(item, dict)
    }


def _resume_branch_followup_text(branch: Mapping[str, Any]) -> str:
    recommended = branch.get("followup_recommended")
    required = branch.get("followup_required")
    if recommended is None and required is None:
        return ""
    return f"recommended={_display(recommended)}, required={_display(required)}"


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


if __name__ == "__main__":
    raise SystemExit(main())
