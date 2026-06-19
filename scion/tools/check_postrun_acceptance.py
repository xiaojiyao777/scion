#!/usr/bin/env python3
"""Check whether postrun acceptance artifacts are ready for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from postrun_artifact_inventory import build_inventory  # noqa: E402


SCHEMA_VERSION = "scion.postrun_acceptance_readiness.v1"
ANALYSIS_BRIEF_SCHEMA = "scion.postrun_analysis_brief.v1"
REBUILD_SCHEMA = "scion.postrun_acceptance_rebuild.v1"
UNREADY_EXIT = 64
BLOCKING_PROBLEM_SUMMARY_GAPS = {
    "cvrp_large_twoopt_handoff_requirements_incomplete",
    "invalid_infra_only_no_research_conclusion",
    "launch_required_before_bounded_twoopt_conclusion",
    "launch_required_before_plateau_conclusion",
    "missing_measurement_effect_summary",
    "missing_research_continuity_summary",
    "missing_runtime_feedback_summary",
    "no_protocol_evaluated_candidates",
    "warehouse_handoff_requirements_incomplete",
}


def build_readiness(run_root: Path | str) -> dict[str, Any]:
    """Return report-only readiness for delegated postrun analysis."""

    root = Path(run_root).expanduser().resolve()
    checks: dict[str, dict[str, Any]] = {}

    def add_check(
        name: str,
        status: str,
        detail: Any = "",
        *,
        required: bool = True,
    ) -> None:
        checks[name] = {
            "status": status,
            "required": bool(required),
            "detail": detail,
        }

    inventory = build_inventory(root)
    lifecycle = _mapping_or_empty(inventory.get("lifecycle"))
    validity = _mapping_or_empty(inventory.get("validity"))
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    postrun_reports = _mapping_or_empty(inventory.get("postrun_reports"))
    postrun_counts = _mapping_or_empty(postrun_reports.get("counts"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    run_log_markers = _mapping_or_empty(launcher.get("run_log_markers"))

    report_dir = root / "postrun_acceptance"
    rebuild_manifest = _latest_json(report_dir / "rebuild")
    analysis_brief = _latest_json(report_dir / "analysis_brief")

    add_check("inventory_loaded", "ok", str(root))
    add_check(
        "postrun_acceptance_present",
        "ok" if report_dir.exists() else "failed",
        str(report_dir),
    )
    add_check(
        "rebuild_manifest_present",
        "ok" if rebuild_manifest else "failed",
        _artifact_paths(report_dir / "rebuild"),
    )
    add_check(
        "rebuild_manifest_schema",
        "ok"
        if rebuild_manifest.get("schema_version") == REBUILD_SCHEMA
        else "failed",
        rebuild_manifest.get("schema_version"),
    )
    add_check(
        "rebuild_manifest_complete",
        "ok" if rebuild_manifest.get("complete") is True else "failed",
        {
            "complete": rebuild_manifest.get("complete"),
            "families": rebuild_manifest.get("families"),
        },
    )
    add_check(
        "analysis_brief_present",
        "ok" if analysis_brief else "failed",
        _artifact_paths(report_dir / "analysis_brief"),
    )
    add_check(
        "analysis_brief_schema",
        "ok"
        if analysis_brief.get("schema_version") == ANALYSIS_BRIEF_SCHEMA
        else "failed",
        analysis_brief.get("schema_version"),
    )
    add_check(
        "inventory_artifact_present",
        "ok" if _int_or_zero(postrun_counts.get("inventory")) > 0 else "failed",
        postrun_counts,
    )
    add_check(
        "current_run_evidence",
        "ok"
        if lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
        else "failed",
        {
            "lifecycle": lifecycle,
            "phase4": {
                "current_run_evidence": phase4.get("current_run_evidence"),
                "evidence_scope": phase4.get("evidence_scope"),
            },
        },
    )
    add_check(
        "analysis_brief_current_run_evidence",
        "ok"
        if _brief_current_run_evidence(analysis_brief)
        else "failed",
        {
            "lifecycle": _mapping_or_empty(analysis_brief.get("lifecycle")),
            "phase4": _mapping_or_empty(
                analysis_brief.get("phase4_evidence_coverage")
            ),
        },
    )
    add_check(
        "not_invalid_infra_only",
        "ok"
        if validity.get("invalid_infra_only") is not True
        and lifecycle.get("invalid_infra_only") is not True
        else "failed",
        {"lifecycle": lifecycle, "validity": validity},
    )
    add_check(
        "not_prepared_only",
        "ok" if lifecycle.get("prepared_only") is not True else "failed",
        lifecycle,
    )
    add_check(
        "not_pre_campaign_preflight_failed",
        "ok"
        if lifecycle.get("pre_campaign_completion_preflight_failed") is not True
        else "failed",
        lifecycle,
    )
    add_check(
        "current_run_report_families_present",
        "ok"
        if all(
            _int_or_zero(postrun_counts.get(name)) > 0
            for name in ("summaries", "failures", "research_efficiency", "manifests")
        )
        else "failed",
        postrun_counts,
    )
    problem_status, problem_detail = _problem_summary_actionability(
        analysis_brief,
        inventory,
    )
    add_check(
        "problem_summary_actionability",
        problem_status,
        problem_detail,
        required=problem_status != "skipped",
    )
    prompt_status, prompt_detail = _prompt_source_visibility_actionability(
        analysis_brief,
        inventory,
    )
    add_check(
        "prompt_source_visibility_actionability",
        prompt_status,
        prompt_detail,
        required=prompt_status != "skipped",
    )
    add_check(
        "postrun_report_status_marker",
        "ok"
        if _int_or_zero(run_log_markers.get("POSTRUN_REPORTS_EXIT_STATUS")) > 0
        else "missing",
        run_log_markers,
        required=False,
    )

    current_run_analysis_ready = all(
        check["status"] == "ok"
        for check in checks.values()
        if check.get("required") is True
    )
    delegation_ready = (
        checks["analysis_brief_present"]["status"] == "ok"
        and checks["inventory_artifact_present"]["status"] == "ok"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "run_root": str(root),
        "postrun_acceptance_dir": str(report_dir),
        "delegation_ready": delegation_ready,
        "current_run_analysis_ready": current_run_analysis_ready,
        "checks": checks,
    }


def render_markdown(readiness: Mapping[str, Any]) -> str:
    lines = [
        f"# Postrun Acceptance Readiness: {Path(str(readiness['run_root'])).name}",
        "",
        "- Scope: report-only delegated-analysis readiness.",
        "- Boundary: no DecisionFeatures, Protocol gates, promotion, scheduler, "
        "or solver behavior is changed.",
        f"- Delegation ready: `{readiness.get('delegation_ready')}`",
        f"- Current-run analysis ready: `{readiness.get('current_run_analysis_ready')}`",
        "",
        "## Checks",
        "| Check | Required | Status | Detail |",
        "|---|---:|---|---|",
    ]
    checks = readiness.get("checks")
    if isinstance(checks, Mapping):
        for name, check in sorted(checks.items()):
            if not isinstance(check, Mapping):
                continue
            lines.append(
                "| {name} | {required} | {status} | `{detail}` |".format(
                    name=name,
                    required=check.get("required"),
                    status=check.get("status"),
                    detail=_compact_detail(check.get("detail")),
                )
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", help="Run root to inspect.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--require-current-run-ready",
        action="store_true",
        help="Exit 64 unless current-run analysis readiness passes.",
    )
    args = parser.parse_args(argv)

    readiness = build_readiness(args.run_root)
    if args.format == "json":
        print(_stable_json(readiness), end="")
    else:
        print(render_markdown(readiness), end="")
    if args.require_current_run_ready and not readiness["current_run_analysis_ready"]:
        return UNREADY_EXIT
    return 0


def _latest_json(directory: Path) -> dict[str, Any]:
    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    if not paths:
        return {}
    return _read_json_object(paths[-1])


def _artifact_paths(directory: Path) -> list[str]:
    return sorted(str(path) for path in directory.glob("*.json") if path.is_file())


def _brief_current_run_evidence(brief: Mapping[str, Any]) -> bool:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    phase4 = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    return (
        lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
    )


def _problem_summary_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    expected_family, expected_key = _expected_problem_summary(brief, inventory)
    if expected_key:
        summary = _mapping_or_empty(brief.get(expected_key))
        if summary.get("available") is not True:
            return (
                "failed",
                {
                    "reason": "missing_problem_specific_summary",
                    "expected_problem_family": expected_family,
                    "expected_summary": expected_key,
                    "summary_available": summary.get("available"),
                    "summary_problem_family": summary.get("problem_family"),
                },
            )
        summaries = [_summary_actionability_detail(expected_key, summary)]
        return (_summary_actionability_status(summaries), summaries)

    summaries = []
    for key in ("warehouse_followup_summary", "cvrp_large_twoopt_summary"):
        summary = _mapping_or_empty(brief.get(key))
        if summary.get("available") is not True:
            continue
        summaries.append(_summary_actionability_detail(key, summary))
    if not summaries:
        return "skipped", "no problem-specific summary"
    return (_summary_actionability_status(summaries), summaries)


def _expected_problem_summary(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    problem_family = _problem_family(brief, inventory)
    if problem_family == "warehouse_delivery":
        return problem_family, "warehouse_followup_summary"
    if problem_family == "cvrp":
        return problem_family, "cvrp_large_twoopt_summary"
    return problem_family, None


def _problem_family(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> str | None:
    brief_contract = _mapping_or_empty(brief.get("prepared_run_contract"))
    if isinstance(brief_contract.get("problem_family"), str):
        return str(brief_contract["problem_family"])
    launcher = _mapping_or_empty(inventory.get("launcher"))
    inventory_contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    if isinstance(inventory_contract.get("problem_family"), str):
        return str(inventory_contract["problem_family"])
    for key in ("warehouse_followup_summary", "cvrp_large_twoopt_summary"):
        summary = _mapping_or_empty(brief.get(key))
        if summary.get("available") is True and isinstance(
            summary.get("problem_family"),
            str,
        ):
            return str(summary["problem_family"])
    return None


def _summary_actionability_detail(
    key: str,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_gaps = _string_items(summary.get("evidence_gaps"))
    return {
        "summary": key,
        "problem_family": summary.get("problem_family"),
        "current_run_evidence": summary.get("current_run_evidence"),
        "interpretation": summary.get("interpretation"),
        "review_axes_actionability": summary.get("review_axes_actionability"),
        "evidence_gaps": evidence_gaps,
        "blocking_evidence_gaps": _blocking_problem_summary_gaps(evidence_gaps),
    }


def _summary_actionability_status(summaries: list[dict[str, Any]]) -> str:
    ok = all(
        item.get("current_run_evidence") is True
        and item.get("review_axes_actionability")
        == "actionable_current_run_evidence_present"
        and not item.get("blocking_evidence_gaps")
        for item in summaries
    )
    return "ok" if ok else "failed"


def _prompt_source_visibility_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    summary = _mapping_or_empty(brief.get("prompt_context_visibility_summary"))
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    source_visibility = _mapping_or_empty(aggregate.get("source_visibility"))
    failures: list[str] = []
    if summary.get("current_run_evidence") is not True:
        failures.append("prompt_context_not_current_run_evidence")
    if summary.get("available") is not True:
        failures.append("prompt_context_visibility_summary_unavailable")
    if _int_or_zero(aggregate.get("trace_count")) <= 0:
        failures.append("prompt_context_trace_accounting_missing")
    if _int_or_zero(source_visibility.get("trace_count")) <= 0:
        failures.append("prompt_source_visibility_trace_accounting_missing")
    if (
        _int_or_zero(source_visibility.get("hypothesis_target_source_trace_count"))
        <= 0
    ):
        failures.append("hypothesis_target_source_visibility_trace_missing")
    elif (
        _int_or_zero(source_visibility.get("hypothesis_target_source_visible_count"))
        <= 0
    ):
        failures.append("hypothesis_target_source_visibility_not_visible")
    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "current_run_evidence": summary.get("current_run_evidence"),
            "available": summary.get("available"),
            "trace_count": aggregate.get("trace_count"),
            "source_visibility_trace_count": source_visibility.get("trace_count"),
            "code_trace_count": source_visibility.get("code_trace_count"),
            "hypothesis_target_source_trace_count": source_visibility.get(
                "hypothesis_target_source_trace_count"
            ),
            "hypothesis_target_source_visible_count": source_visibility.get(
                "hypothesis_target_source_visible_count"
            ),
            "hypothesis_target_source_not_visible_count": source_visibility.get(
                "hypothesis_target_source_not_visible_count"
            ),
        },
    )


def _blocking_problem_summary_gaps(evidence_gaps: list[str]) -> list[str]:
    return [
        gap
        for gap in evidence_gaps
        if gap in BLOCKING_PROBLEM_SUMMARY_GAPS
    ]


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _compact_detail(value: Any) -> str:
    text = (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (dict, list))
        else str(value)
    )
    return text.replace("\n", " ")[:240]


if __name__ == "__main__":
    raise SystemExit(main())
