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
from postrun_analysis_brief import (  # noqa: E402
    _branch_research_state_summary,
    _champion_progress_summary,
    _cvrp_large_twoopt_mechanism_signal,
    _research_context_actionability_summary,
    _warehouse_followup_continuity_signal,
    _warehouse_followup_measurement_signal,
)


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
NONBLOCKING_PROBLEM_SUMMARY_GAPS_BY_INTERPRETATION = {
    "quality_blocked_no_protocol_plateau_conclusion": {
        "missing_measurement_effect_summary",
        "missing_research_continuity_summary",
        "missing_runtime_feedback_summary",
    },
    "quality_blocked_no_protocol_twoopt_conclusion": {
        "missing_measurement_effect_summary",
        "missing_research_continuity_summary",
        "missing_runtime_feedback_summary",
    },
}
PROBLEM_SUMMARY_SCHEMAS = {
    "warehouse_followup_summary": "scion.postrun_warehouse_followup_summary.v1",
    "cvrp_large_twoopt_summary": "scion.postrun_cvrp_large_twoopt_summary.v1",
}
BRANCH_RESEARCH_STATE_SCHEMA = "scion.postrun_branch_research_state_summary.v1"
CHAMPION_PROGRESS_SCHEMA = "scion.postrun_champion_progress_summary.v1"
PROMPT_CONTEXT_VISIBILITY_SCHEMA = (
    "scion.postrun_prompt_context_visibility_summary.v1"
)
PROMPT_SOURCE_VISIBILITY_SCHEMA = "scion.postrun_prompt_source_visibility_summary.v1"
PROMPT_SIGNAL_DENSITY_SCHEMA = "scion.postrun_prompt_signal_density.v1"
RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA = (
    "scion.postrun_research_context_actionability_summary.v1"
)
FAILURE_TAXONOMY_SCHEMA = "scion.postrun_failure_taxonomy_summary.v1"
PROBLEM_SUMMARY_DELEGATED_INTERPRETATIONS = {
    "warehouse_followup_summary": {
        "quality_blocked_no_protocol_plateau_conclusion",
        "protocol_evaluated_measurement_effect_inconclusive",
        "protocol_evaluated_plateau_review_ready",
        "protocol_evaluated_positive_effect_review_ready",
        "protocol_evaluated_research_continuity_too_shallow",
    },
    "cvrp_large_twoopt_summary": {
        "bounded_twoopt_review_ready",
        "quality_blocked_no_protocol_twoopt_conclusion",
        "protocol_evaluated_without_large_twoopt_direct_evidence",
        "protocol_evaluated_without_large_twoopt_signal",
    },
}
REVIEW_INPUT_SUMMARIES = {
    "protocol_accounting_summary": (
        "scion.postrun_protocol_accounting_summary.v1",
        "accounting_report_count",
    ),
    "measurement_effect_summary": (
        "scion.postrun_measurement_effect_summary.v1",
        "effect_report_count",
    ),
    "runtime_feedback_summary": (
        "scion.postrun_runtime_feedback_summary.v1",
        "runtime_report_count",
    ),
    "research_continuity_summary": (
        "scion.postrun_research_continuity_summary.v1",
        "continuity_report_count",
    ),
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
    rebuild_manifest = _read_rebuild_manifest(report_dir)
    analysis_brief_path = _analysis_brief_path_from_rebuild_manifest(
        rebuild_manifest,
        report_dir,
    )
    analysis_brief = (
        _read_json_object(analysis_brief_path)
        if analysis_brief_path
        else {}
    )

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
        "rebuild_manifest_run_identity",
        "ok"
        if _payload_path_matches(rebuild_manifest.get("run_root"), root)
        else "failed",
        {
            "expected_run_root": str(root),
            "manifest_run_root": rebuild_manifest.get("run_root"),
        },
    )
    identity_status, identity_detail = _rebuild_manifest_identity_boundary(
        root,
        report_dir,
        rebuild_manifest,
    )
    add_check(
        "rebuild_manifest_identity_boundary",
        identity_status,
        identity_detail,
    )
    add_check(
        "rebuild_manifest_complete",
        "ok" if rebuild_manifest.get("complete") is True else "failed",
        {
            "complete": rebuild_manifest.get("complete"),
            "families": rebuild_manifest.get("families"),
        },
    )
    manifest_outputs_status, manifest_outputs_detail = (
        _rebuild_manifest_declared_outputs_present(rebuild_manifest, report_dir)
    )
    add_check(
        "rebuild_manifest_declared_outputs_present",
        manifest_outputs_status,
        manifest_outputs_detail,
    )
    add_check(
        "analysis_brief_present",
        "ok" if analysis_brief else "failed",
        {
            "selected_from_rebuild_manifest": str(analysis_brief_path)
            if analysis_brief_path
            else "",
            "available_artifacts": _artifact_paths(report_dir / "analysis_brief"),
        },
    )
    add_check(
        "analysis_brief_schema",
        "ok"
        if analysis_brief.get("schema_version") == ANALYSIS_BRIEF_SCHEMA
        else "failed",
        analysis_brief.get("schema_version"),
    )
    add_check(
        "analysis_brief_run_identity",
        "ok"
        if _payload_path_matches(analysis_brief.get("run_root"), root)
        else "failed",
        {
            "expected_run_root": str(root),
            "analysis_brief_run_root": analysis_brief.get("run_root"),
            "analysis_brief_path": str(analysis_brief_path)
            if analysis_brief_path
            else "",
        },
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
    contract_status, contract_detail = _prepared_contract_consistency(
        analysis_brief,
        inventory,
    )
    add_check(
        "analysis_brief_prepared_contract_consistency",
        contract_status,
        contract_detail,
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
    review_input_status, review_input_detail = (
        _review_input_summaries_actionability(
            analysis_brief,
            inventory,
        )
    )
    add_check(
        "review_input_summaries_actionability",
        review_input_status,
        review_input_detail,
        required=review_input_status != "skipped",
    )
    consistency_status, consistency_detail = _problem_summary_input_consistency(
        analysis_brief,
        inventory,
    )
    add_check(
        "problem_summary_input_consistency",
        consistency_status,
        consistency_detail,
        required=consistency_status != "skipped",
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
    research_context_status, research_context_detail = (
        _research_context_actionability(
            analysis_brief,
            inventory,
        )
    )
    add_check(
        "research_context_actionability",
        research_context_status,
        research_context_detail,
        required=research_context_status != "skipped",
    )
    branch_state_status, branch_state_detail = _branch_research_state_actionability(
        analysis_brief,
        inventory,
    )
    add_check(
        "branch_research_state_actionability",
        branch_state_status,
        branch_state_detail,
        required=branch_state_status != "skipped",
    )
    champion_status, champion_detail = _champion_progress_actionability(
        analysis_brief,
        inventory,
    )
    add_check(
        "champion_progress_actionability",
        champion_status,
        champion_detail,
        required=champion_status != "skipped",
    )
    failure_taxonomy_status, failure_taxonomy_detail = (
        _failure_taxonomy_actionability(
            analysis_brief,
            inventory,
        )
    )
    add_check(
        "failure_taxonomy_actionability",
        failure_taxonomy_status,
        failure_taxonomy_detail,
        required=failure_taxonomy_status != "skipped",
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
    failed_required_checks = _failed_check_names(checks, required=True)
    failed_optional_checks = _failed_check_names(checks, required=False)
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
        "failed_required_checks": failed_required_checks,
        "failed_optional_checks": failed_optional_checks,
        "checks": checks,
    }


def _failed_check_names(
    checks: Mapping[str, Mapping[str, Any]],
    *,
    required: bool,
) -> list[str]:
    return [
        name
        for name, check in sorted(checks.items())
        if check.get("required") is required
        and check.get("status") not in {"ok", "skipped"}
    ]


def render_markdown(readiness: Mapping[str, Any]) -> str:
    lines = [
        f"# Postrun Acceptance Readiness: {Path(str(readiness['run_root'])).name}",
        "",
        "- Scope: report-only delegated-analysis readiness.",
        "- Boundary: no DecisionFeatures, Protocol gates, promotion, scheduler, "
        "or solver behavior is changed.",
        f"- Delegation ready: `{readiness.get('delegation_ready')}`",
        f"- Current-run analysis ready: `{readiness.get('current_run_analysis_ready')}`",
        f"- Failed required checks: `{_compact_detail(readiness.get('failed_required_checks'))}`",
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


def _read_rebuild_manifest(report_dir: Path) -> dict[str, Any]:
    return _read_json_object(report_dir / "rebuild" / "rebuild_manifest.v1.json")


def _analysis_brief_path_from_rebuild_manifest(
    rebuild_manifest: Mapping[str, Any],
    report_dir: Path,
) -> Path | None:
    families = _mapping_or_empty(rebuild_manifest.get("families"))
    analysis_brief = _mapping_or_empty(families.get("analysis_brief"))
    outputs = analysis_brief.get("outputs")
    if not isinstance(outputs, list):
        return None
    for item in outputs:
        output = str(item)
        path = _manifest_output_path(output, report_dir)
        if (
            path.suffix == ".json"
            and path.is_file()
            and _manifest_output_in_family(path, report_dir, "analysis_brief")
        ):
            return path
    return None


def _rebuild_manifest_identity_boundary(
    root: Path,
    report_dir: Path,
    rebuild_manifest: Mapping[str, Any],
) -> tuple[str, Any]:
    if not rebuild_manifest:
        return "failed", {"reason": "missing_rebuild_manifest", "failures": []}

    failures: list[dict[str, Any]] = []
    expected_identity = {
        "artifact_kind": "postrun_acceptance_rebuild",
        "run_root": str(root),
        "campaign_dir": str(root / "campaign"),
        "report_dir": str(report_dir),
    }
    for field, expected in expected_identity.items():
        actual = rebuild_manifest.get(field)
        matches = (
            _payload_path_matches(actual, Path(expected))
            if field in {"run_root", "campaign_dir", "report_dir"}
            else actual == expected
        )
        if not matches:
            failures.append(
                {
                    "reason": "manifest_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                }
            )

    boundary_expectations = {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
    }
    for field, expected in boundary_expectations.items():
        if rebuild_manifest.get(field) is not expected:
            failures.append(
                {
                    "reason": "manifest_boundary_flag_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": rebuild_manifest.get(field),
                }
            )

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "expected_identity": expected_identity,
            "boundary_expectations": boundary_expectations,
        },
    )


def _rebuild_manifest_declared_outputs_present(
    rebuild_manifest: Mapping[str, Any],
    report_dir: Path,
) -> tuple[str, Any]:
    if not rebuild_manifest:
        return "failed", {"reason": "missing_rebuild_manifest"}
    families = _mapping_or_empty(rebuild_manifest.get("families"))
    if not families:
        return "failed", {"reason": "missing_rebuild_manifest_families"}

    ok_families: list[str] = []
    skipped_families: list[str] = []
    missing_outputs: list[dict[str, Any]] = []
    inconsistent_outputs: list[dict[str, Any]] = []
    unexpected_outputs: list[dict[str, Any]] = []
    out_of_scope_outputs: list[dict[str, Any]] = []
    family_failures: list[dict[str, Any]] = []
    for family_name, raw_family in sorted(families.items()):
        family = _mapping_or_empty(raw_family)
        family_status = family.get("status")
        outputs = _string_items(family.get("outputs"))
        outputs_present = _mapping_or_empty(family.get("outputs_present"))
        if family_status == "skipped":
            skipped_families.append(str(family_name))
            continue
        if family_status != "ok":
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "family_status_not_ok",
                }
            )
            continue
        ok_families.append(str(family_name))
        if not outputs:
            family_failures.append(
                {
                    "family": str(family_name),
                    "status": family_status,
                    "reason": "ok_family_without_outputs",
                }
                )
            continue
        declared_paths: set[Path] = set()
        for output in outputs:
            path = _manifest_output_path(output, report_dir)
            in_scope = _manifest_output_in_family(path, report_dir, str(family_name))
            if not in_scope:
                out_of_scope_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "expected_directory": str(report_dir / str(family_name)),
                        "reason": "manifest_output_outside_family_directory",
                    }
                )
            else:
                declared_paths.add(path.resolve())
            actual_present = path.is_file()
            manifest_present = outputs_present.get(output)
            if actual_present is False:
                missing_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                    }
                )
            if isinstance(manifest_present, bool):
                if manifest_present is not actual_present:
                    inconsistent_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "manifest_output": output,
                            "manifest_outputs_present": manifest_present,
                            "actual_present": actual_present,
                        }
                    )
            else:
                inconsistent_outputs.append(
                    {
                        "family": str(family_name),
                        "path": str(path),
                        "manifest_output": output,
                        "manifest_outputs_present": manifest_present,
                        "actual_present": actual_present,
                        "reason": "missing_outputs_present_entry",
                    }
                )
        family_dir = report_dir / str(family_name)
        if family_dir.is_dir():
            for path in sorted(family_dir.iterdir()):
                if not path.is_file() or path.suffix not in {".json", ".md"}:
                    continue
                if path.resolve() not in declared_paths:
                    unexpected_outputs.append(
                        {
                            "family": str(family_name),
                            "path": str(path),
                            "reason": "undeclared_generated_output",
                        }
                    )

    failures_present = bool(
        missing_outputs
        or inconsistent_outputs
        or unexpected_outputs
        or out_of_scope_outputs
        or family_failures
    )
    return (
        "failed" if failures_present else "ok",
        {
            "ok_families": ok_families,
            "skipped_families": skipped_families,
            "missing_outputs": missing_outputs,
            "inconsistent_outputs": inconsistent_outputs,
            "unexpected_outputs": unexpected_outputs,
            "out_of_scope_outputs": out_of_scope_outputs,
            "family_failures": family_failures,
        },
    )


def _manifest_output_path(value: str, report_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (report_dir / path).resolve()


def _manifest_output_in_family(path: Path, report_dir: Path, family_name: str) -> bool:
    try:
        return path.resolve().parent == (report_dir / family_name).resolve()
    except OSError:
        return False


def _artifact_paths(directory: Path) -> list[str]:
    return sorted(str(path) for path in directory.glob("*.json") if path.is_file())


def _payload_path_matches(value: Any, expected: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return Path(value).expanduser().resolve() == expected
    except OSError:
        return False


def _brief_current_run_evidence(brief: Mapping[str, Any]) -> bool:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    phase4 = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    return (
        lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
    )


def _prepared_contract_consistency(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    brief_contract = _mapping_or_empty(brief.get("prepared_run_contract"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    inventory_contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    failures: list[str] = []
    if not brief_contract:
        failures.append("analysis_brief_prepared_contract_missing")
    if not inventory_contract:
        failures.append("inventory_prepared_contract_missing")
    for field in (
        "schema_version",
        "report_only",
        "quality_judgment",
        "decision_features_excluded",
        "manifest_present",
        "contract_complete",
        "problem_family",
        "model",
        "resume_from_campaign",
        "control_pair_key",
        "completion_preflight",
        "postrun_reports",
    ):
        if brief_contract.get(field) != inventory_contract.get(field):
            failures.append(f"prepared_contract_{field}_mismatch")
    if _mapping_or_empty(brief_contract.get("execution")) != _mapping_or_empty(
        inventory_contract.get("execution")
    ):
        failures.append("prepared_contract_execution_mismatch")
    if _mapping_or_empty(brief_contract.get("git")) != _mapping_or_empty(
        inventory_contract.get("git")
    ):
        failures.append("prepared_contract_git_mismatch")
    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "brief_problem_family": brief_contract.get("problem_family"),
            "inventory_problem_family": inventory_contract.get("problem_family"),
            "brief_model": brief_contract.get("model"),
            "inventory_model": inventory_contract.get("model"),
            "brief_control_pair_key": brief_contract.get("control_pair_key"),
            "inventory_control_pair_key": inventory_contract.get("control_pair_key"),
            "brief_resume_from_campaign": brief_contract.get("resume_from_campaign"),
            "inventory_resume_from_campaign": inventory_contract.get(
                "resume_from_campaign"
            ),
        },
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
        summaries = [
            _summary_actionability_detail(
                expected_key,
                summary,
                expected_family=expected_family,
            )
        ]
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
    launcher = _mapping_or_empty(inventory.get("launcher"))
    inventory_contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    if isinstance(inventory_contract.get("problem_family"), str):
        return str(inventory_contract["problem_family"])
    brief_contract = _mapping_or_empty(brief.get("prepared_run_contract"))
    if isinstance(brief_contract.get("problem_family"), str):
        return str(brief_contract["problem_family"])
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
    *,
    expected_family: str | None = None,
) -> dict[str, Any]:
    evidence_gaps = _string_items(summary.get("evidence_gaps"))
    expected_schema = PROBLEM_SUMMARY_SCHEMAS.get(key)
    schema_version = summary.get("schema_version")
    interpretation = summary.get("interpretation")
    delegated_interpretations = PROBLEM_SUMMARY_DELEGATED_INTERPRETATIONS.get(
        key,
        set(),
    )
    summary_failures: list[str] = []
    if expected_schema and schema_version != expected_schema:
        summary_failures.append("stale_problem_summary_schema")
    if summary.get("report_only") is not True:
        summary_failures.append("problem_summary_not_report_only")
    if summary.get("quality_judgment") is not False:
        summary_failures.append("problem_summary_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
        summary_failures.append("problem_summary_decision_features_not_excluded")
    if delegated_interpretations and interpretation not in delegated_interpretations:
        summary_failures.append("unsupported_problem_summary_interpretation")
    problem_family = summary.get("problem_family")
    if expected_family is not None and problem_family != expected_family:
        summary_failures.append("problem_summary_family_mismatch")
    if (
        summary.get("current_run_evidence") is True
        and not _mapping_or_empty(summary.get("evidence"))
    ):
        summary_failures.append("problem_summary_evidence_missing")
    launch_required_field = {
        "warehouse_followup_summary": "launch_required_before_plateau_conclusion",
        "cvrp_large_twoopt_summary": "launch_required_before_twoopt_conclusion",
    }.get(key)
    if (
        launch_required_field is not None
        and summary.get("current_run_evidence") is True
        and summary.get(launch_required_field) is not False
    ):
        summary_failures.append("problem_summary_launch_required_flag_stale")
    return {
        "summary": key,
        "problem_family": problem_family,
        "expected_problem_family": expected_family,
        "problem_family_matches_expected": (
            True if expected_family is None else problem_family == expected_family
        ),
        "schema_version": schema_version,
        "expected_schema_version": expected_schema,
        "schema_current": schema_version == expected_schema,
        "current_run_evidence": summary.get("current_run_evidence"),
        "launch_required_field": launch_required_field,
        "launch_required_before_conclusion": (
            summary.get(launch_required_field)
            if launch_required_field is not None
            else None
        ),
        "report_only": summary.get("report_only"),
        "quality_judgment": summary.get("quality_judgment"),
        "decision_features_excluded": summary.get("decision_features_excluded"),
        "interpretation": interpretation,
        "interpretation_supported": interpretation in delegated_interpretations,
        "review_axes_actionability": summary.get("review_axes_actionability"),
        "evidence_gaps": evidence_gaps,
        "blocking_evidence_gaps": _blocking_problem_summary_gaps(
            evidence_gaps,
            interpretation=str(interpretation or ""),
        ),
        "summary_failures": summary_failures,
    }


def _summary_actionability_status(summaries: list[dict[str, Any]]) -> str:
    ok = all(
        item.get("current_run_evidence") is True
        and item.get("schema_current") is True
        and item.get("interpretation_supported") is True
        and item.get("review_axes_actionability")
        == "actionable_current_run_evidence_present"
        and not item.get("summary_failures")
        and not item.get("blocking_evidence_gaps")
        for item in summaries
    )
    return "ok" if ok else "failed"


def _review_input_summaries_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    _, expected_key = _expected_problem_summary(brief, inventory)
    problem_summary = _mapping_or_empty(brief.get(expected_key))
    interpretation = str(problem_summary.get("interpretation") or "")
    required_summaries = _required_review_input_summaries_for_interpretation(
        interpretation,
    )
    details = []
    for key, (schema, count_field) in REVIEW_INPUT_SUMMARIES.items():
        required_for_interpretation = key in required_summaries
        summary = _mapping_or_empty(brief.get(key))
        count_value = _int_or_zero(summary.get(count_field))
        summary_present = (
            summary.get("available") is True
            or _int_or_zero(summary.get("report_count")) > 0
            or summary.get("schema_version") is not None
        )
        failures: list[str] = []
        if (required_for_interpretation or summary_present) and (
            summary.get("schema_version") != schema
        ):
            failures.append(f"{key}_schema_stale")
        if (required_for_interpretation or summary_present) and (
            summary.get("report_only") is not True
        ):
            failures.append(f"{key}_not_report_only")
        if (required_for_interpretation or summary_present) and (
            summary.get("quality_judgment") is not False
        ):
            failures.append(f"{key}_quality_judgment_not_false")
        if (required_for_interpretation or summary_present) and (
            summary.get("decision_features_excluded") is not True
        ):
            failures.append(f"{key}_decision_features_not_excluded")
        if (
            required_for_interpretation
            and summary.get("current_run_evidence") is not True
        ):
            failures.append(f"{key}_not_current_run_evidence")
        if required_for_interpretation and summary.get("available") is not True:
            failures.append(f"{key}_unavailable")
        if (
            required_for_interpretation
            and _int_or_zero(summary.get("report_count")) <= 0
        ):
            failures.append(f"{key}_report_count_missing")
        if required_for_interpretation and count_value <= 0:
            failures.append(f"{key}_{count_field}_missing")
        if key == "runtime_feedback_summary" and required_for_interpretation:
            if summary.get("drain_status_complete") is not True:
                failures.append("runtime_feedback_summary_drain_status_incomplete")
            if summary.get("review_ready") is not True:
                failures.append("runtime_feedback_summary_not_review_ready")
        details.append(
            {
                "summary": key,
                "required_for_interpretation": required_for_interpretation,
                "failures": failures,
                "schema_version": summary.get("schema_version"),
                "expected_schema_version": schema,
                "report_only": summary.get("report_only"),
                "quality_judgment": summary.get("quality_judgment"),
                "decision_features_excluded": summary.get(
                    "decision_features_excluded"
                ),
                "current_run_evidence": summary.get("current_run_evidence"),
                "available": summary.get("available"),
                "report_count": summary.get("report_count"),
                count_field: summary.get(count_field),
                "drain_status_complete": summary.get("drain_status_complete"),
                "review_ready": summary.get("review_ready"),
            }
        )
    return (
        "ok"
        if all(not item["failures"] for item in details)
        else "failed",
        {
            "problem_family": problem_family,
            "interpretation": interpretation,
            "summaries": details,
        },
    )


def _problem_summary_input_consistency(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family, expected_key = _expected_problem_summary(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"} or expected_key is None:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    summary = _mapping_or_empty(brief.get(expected_key))
    if summary.get("available") is not True:
        return "skipped", {
            "reason": "missing_problem_specific_summary",
            "problem_family": problem_family,
            "summary": expected_key,
        }

    evidence = _mapping_or_empty(summary.get("evidence"))
    protocol_evidence = _mapping_or_empty(evidence.get("protocol"))
    measurement_evidence = _mapping_or_empty(evidence.get("measurement_effect"))
    large_twoopt_evidence = _mapping_or_empty(evidence.get("large_twoopt_mechanism"))
    runtime_evidence = _mapping_or_empty(evidence.get("runtime"))
    continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
    quality_evidence = _mapping_or_empty(evidence.get("quality_blocks"))

    protocol_summary = _mapping_or_empty(brief.get("protocol_accounting_summary"))
    protocol_aggregate = _mapping_or_empty(protocol_summary.get("aggregate"))
    protocol_rows = _mapping_or_empty(protocol_aggregate.get("protocol_rows"))
    input_protocol_evaluated = max(
        _int_or_zero(protocol_rows.get("protocol_evaluated_candidates")),
        _int_or_zero(protocol_aggregate.get("formal_protocol_evaluated_candidates")),
    )
    summary_protocol_evaluated = _int_or_zero(
        protocol_evidence.get("protocol_evaluated_candidates")
    )

    measurement_summary = _mapping_or_empty(brief.get("measurement_effect_summary"))
    measurement_aggregate = _mapping_or_empty(measurement_summary.get("aggregate"))
    runtime_summary = _mapping_or_empty(brief.get("runtime_feedback_summary"))
    continuity_summary = _mapping_or_empty(brief.get("research_continuity_summary"))
    failure_summary = _mapping_or_empty(brief.get("failure_taxonomy_summary"))
    failure_aggregate = _mapping_or_empty(failure_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure_aggregate.get("proposal_quality"))
    input_quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    summary_quality_block_signal = max(
        _int_or_zero(quality_evidence.get("proposal_quality_blocks")),
        _int_or_zero(quality_evidence.get("quality_blocks")),
        _int_or_zero(quality_evidence.get("quality_block_ledger_count")),
    )

    failures: list[str] = []
    interpretation = str(summary.get("interpretation") or "")
    if not evidence:
        failures.append("problem_summary_evidence_missing")
    if summary_protocol_evaluated != input_protocol_evaluated:
        failures.append("problem_summary_protocol_evaluated_mismatch")
    if _is_protocol_evaluated_interpretation(interpretation):
        if summary_protocol_evaluated <= 0:
            failures.append("problem_summary_protocol_evaluated_missing")
        if input_protocol_evaluated <= 0:
            failures.append("review_input_protocol_evaluated_missing")
    if _is_quality_blocked_interpretation(interpretation):
        if summary_protocol_evaluated > 0 or input_protocol_evaluated > 0:
            failures.append(
                "quality_blocked_no_protocol_has_protocol_evaluated_candidates"
            )
        if summary_quality_block_signal <= 0:
            failures.append("problem_summary_quality_block_signal_missing")
        if input_quality_block_signal <= 0:
            failures.append("failure_taxonomy_quality_block_signal_missing")
    if (
        measurement_evidence.get("available")
        is not measurement_summary.get("available")
    ):
        failures.append("problem_summary_measurement_available_mismatch")
    if _int_or_zero(measurement_evidence.get("protocol_row_count")) != _int_or_zero(
        measurement_aggregate.get("protocol_row_count")
    ):
        failures.append("problem_summary_measurement_protocol_rows_mismatch")
    for field in ("rows_at_or_above_mde", "rows_with_ci_high_below_mde"):
        if _int_or_zero(measurement_evidence.get(field)) != _int_or_zero(
            measurement_aggregate.get(field)
        ):
            failures.append(f"problem_summary_measurement_{field}_mismatch")
    runtime_ready = runtime_summary.get("review_ready") is True
    runtime_evidence_ready = (
        runtime_evidence.get("review_ready")
        if "review_ready" in runtime_evidence
        else runtime_evidence.get("available")
    )
    runtime_raw_available = runtime_summary.get("available") is True
    runtime_evidence_raw_available = (
        runtime_evidence.get("raw_available")
        if "raw_available" in runtime_evidence
        else runtime_evidence.get("available")
    )
    runtime_aggregate = _mapping_or_empty(runtime_summary.get("aggregate"))
    runtime_budget = _mapping_or_empty(
        runtime_aggregate.get("runtime_budget_diagnostics")
    )
    if runtime_evidence_ready is not runtime_ready:
        failures.append("problem_summary_runtime_review_ready_mismatch")
    if runtime_evidence_raw_available is not runtime_raw_available:
        failures.append("problem_summary_runtime_raw_available_mismatch")
    if (
        runtime_evidence.get("drain_status_complete")
        is not runtime_summary.get("drain_status_complete")
    ):
        failures.append("problem_summary_runtime_drain_status_mismatch")
    if _int_mapping(runtime_evidence.get("runtime_model_counts")) != _int_mapping(
        runtime_budget.get("runtime_model_counts")
    ):
        failures.append("problem_summary_runtime_model_counts_mismatch")
    if _int_or_zero(
        runtime_evidence.get("runtime_budget_diagnostic_count")
    ) != _int_or_zero(runtime_budget.get("diagnostic_count")):
        failures.append("problem_summary_runtime_budget_diagnostic_count_mismatch")
    if (
        continuity_evidence.get("available")
        is not continuity_summary.get("available")
    ):
        failures.append("problem_summary_continuity_available_mismatch")
    if _int_or_zero(
        continuity_evidence.get("continuity_report_count")
    ) != _int_or_zero(continuity_summary.get("continuity_report_count")):
        failures.append("problem_summary_continuity_report_count_mismatch")
    if (
        interpretation == "protocol_evaluated_plateau_review_ready"
        and continuity_evidence.get("substantive") is not True
    ):
        failures.append("warehouse_plateau_continuity_not_substantive")
    input_large_twoopt_signal: dict[str, Any] = {}
    input_warehouse_measurement_signal: dict[str, Any] = {}
    input_warehouse_continuity_signal: dict[str, Any] = {}
    if problem_family == "warehouse_delivery":
        input_warehouse_measurement_signal = _warehouse_followup_measurement_signal(
            measurement_summary
        )
        for field in (
            "effect_signal",
            "positive_effect_at_or_above_mde",
            "plateau_consistent",
            "all_ci_high_below_mde",
        ):
            if not _is_protocol_evaluated_interpretation(interpretation):
                continue
            summary_value = measurement_evidence.get(field)
            input_value = input_warehouse_measurement_signal.get(field)
            if isinstance(input_value, bool):
                if summary_value is not input_value:
                    failures.append(
                        f"problem_summary_warehouse_measurement_{field}_mismatch"
                    )
            elif str(summary_value or "") != str(input_value or ""):
                failures.append(
                    f"problem_summary_warehouse_measurement_{field}_mismatch"
                )
        input_warehouse_continuity_signal = _warehouse_followup_continuity_signal(
            continuity_summary
        )
        for field in (
            "substantive",
            "max_branch_depth",
            "same_mechanism_selected",
            "same_mechanism_observed",
            "branch_lessons_satisfied",
            "branch_lessons_required",
            "weak_positive_accepted",
            "weak_positive_observed",
        ):
            summary_value = continuity_evidence.get(field)
            input_value = input_warehouse_continuity_signal.get(field)
            if isinstance(input_value, bool):
                if summary_value is not input_value:
                    failures.append(
                        f"problem_summary_warehouse_continuity_{field}_mismatch"
                    )
            elif _int_or_zero(summary_value) != _int_or_zero(input_value):
                failures.append(
                    f"problem_summary_warehouse_continuity_{field}_mismatch"
                )
        if interpretation == "protocol_evaluated_plateau_review_ready":
            if (
                input_warehouse_measurement_signal.get("plateau_consistent")
                is not True
            ):
                failures.append(
                    "review_input_warehouse_measurement_not_plateau_consistent"
                )
            if (
                input_warehouse_measurement_signal.get(
                    "positive_effect_at_or_above_mde"
                )
                is True
            ):
                failures.append("review_input_warehouse_positive_effect_not_plateau")
            if input_warehouse_continuity_signal.get("substantive") is not True:
                failures.append("review_input_warehouse_continuity_not_substantive")
        if interpretation == "protocol_evaluated_positive_effect_review_ready":
            if (
                input_warehouse_measurement_signal.get(
                    "positive_effect_at_or_above_mde"
                )
                is not True
            ):
                failures.append("review_input_warehouse_positive_effect_missing")
        if interpretation == "protocol_evaluated_measurement_effect_inconclusive":
            if input_warehouse_measurement_signal.get("plateau_consistent") is True:
                failures.append(
                    "review_input_warehouse_measurement_inconclusive_has_plateau_signal"
                )
            if (
                input_warehouse_measurement_signal.get(
                    "positive_effect_at_or_above_mde"
                )
                is True
            ):
                failures.append(
                    "review_input_warehouse_measurement_inconclusive_has_positive_effect"
                )
    if problem_family == "cvrp":
        input_large_twoopt_signal = _cvrp_large_twoopt_mechanism_signal(
            measurement_effect_summary=measurement_summary,
            research_continuity_summary=continuity_summary,
        )
        if large_twoopt_evidence:
            for field in (
                "available",
                "mechanism_family_available",
                "direct_evidence_ready",
            ):
                if large_twoopt_evidence.get(field) is not input_large_twoopt_signal.get(
                    field
                ):
                    failures.append(f"problem_summary_large_twoopt_{field}_mismatch")
            if _int_or_zero(large_twoopt_evidence.get("protocol_row_count")) != (
                _int_or_zero(input_large_twoopt_signal.get("protocol_row_count"))
            ):
                failures.append("problem_summary_large_twoopt_protocol_rows_mismatch")
        if interpretation == "bounded_twoopt_review_ready":
            if large_twoopt_evidence.get("available") is not True:
                failures.append("problem_summary_large_twoopt_available_missing")
            if input_large_twoopt_signal.get("available") is not True:
                failures.append("review_input_large_twoopt_direct_evidence_missing")

    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "summary": expected_key,
            "interpretation": interpretation,
            "failures": failures,
            "summary_protocol_evaluated_candidates": summary_protocol_evaluated,
            "input_protocol_evaluated_candidates": input_protocol_evaluated,
            "summary_quality_block_signal": summary_quality_block_signal,
            "input_quality_block_signal": input_quality_block_signal,
            "summary_measurement_available": measurement_evidence.get("available"),
            "input_measurement_available": measurement_summary.get("available"),
            "summary_measurement_protocol_row_count": measurement_evidence.get(
                "protocol_row_count"
            ),
            "input_measurement_protocol_row_count": measurement_aggregate.get(
                "protocol_row_count"
            ),
            "summary_measurement_rows_at_or_above_mde": measurement_evidence.get(
                "rows_at_or_above_mde"
            ),
            "input_measurement_rows_at_or_above_mde": measurement_aggregate.get(
                "rows_at_or_above_mde"
            ),
            "summary_measurement_rows_with_ci_high_below_mde": measurement_evidence.get(
                "rows_with_ci_high_below_mde"
            ),
            "input_measurement_rows_with_ci_high_below_mde": measurement_aggregate.get(
                "rows_with_ci_high_below_mde"
            ),
            "summary_measurement_effect_signal": measurement_evidence.get(
                "effect_signal"
            ),
            "input_measurement_effect_signal": input_warehouse_measurement_signal.get(
                "effect_signal"
            ),
            "summary_measurement_plateau_consistent": measurement_evidence.get(
                "plateau_consistent"
            ),
            "input_measurement_plateau_consistent": input_warehouse_measurement_signal.get(
                "plateau_consistent"
            ),
            "summary_measurement_positive_effect_at_or_above_mde": (
                measurement_evidence.get("positive_effect_at_or_above_mde")
            ),
            "input_measurement_positive_effect_at_or_above_mde": (
                input_warehouse_measurement_signal.get(
                    "positive_effect_at_or_above_mde"
                )
            ),
            "summary_runtime_review_ready": runtime_evidence_ready,
            "input_runtime_review_ready": runtime_summary.get("review_ready"),
            "summary_runtime_raw_available": runtime_evidence_raw_available,
            "input_runtime_raw_available": runtime_summary.get("available"),
            "summary_runtime_drain_status_complete": runtime_evidence.get(
                "drain_status_complete"
            ),
            "input_runtime_drain_status_complete": runtime_summary.get(
                "drain_status_complete"
            ),
            "summary_runtime_model_counts": _int_mapping(
                runtime_evidence.get("runtime_model_counts")
            ),
            "input_runtime_model_counts": _int_mapping(
                runtime_budget.get("runtime_model_counts")
            ),
            "summary_runtime_budget_diagnostic_count": _int_or_zero(
                runtime_evidence.get("runtime_budget_diagnostic_count")
            ),
            "input_runtime_budget_diagnostic_count": _int_or_zero(
                runtime_budget.get("diagnostic_count")
            ),
            "summary_continuity_available": continuity_evidence.get("available"),
            "input_continuity_available": continuity_summary.get("available"),
            "summary_continuity_report_count": continuity_evidence.get(
                "continuity_report_count"
            ),
            "input_continuity_report_count": continuity_summary.get(
                "continuity_report_count"
            ),
            "summary_continuity_substantive": continuity_evidence.get(
                "substantive"
            ),
            "input_continuity_substantive": input_warehouse_continuity_signal.get(
                "substantive"
            ),
            "summary_continuity_max_branch_depth": continuity_evidence.get(
                "max_branch_depth"
            ),
            "input_continuity_max_branch_depth": input_warehouse_continuity_signal.get(
                "max_branch_depth"
            ),
            "summary_continuity_same_mechanism_selected": continuity_evidence.get(
                "same_mechanism_selected"
            ),
            "input_continuity_same_mechanism_selected": (
                input_warehouse_continuity_signal.get("same_mechanism_selected")
            ),
            "summary_continuity_branch_lessons_satisfied": continuity_evidence.get(
                "branch_lessons_satisfied"
            ),
            "input_continuity_branch_lessons_satisfied": (
                input_warehouse_continuity_signal.get("branch_lessons_satisfied")
            ),
            "summary_continuity_weak_positive_accepted": continuity_evidence.get(
                "weak_positive_accepted"
            ),
            "input_continuity_weak_positive_accepted": (
                input_warehouse_continuity_signal.get("weak_positive_accepted")
            ),
            "summary_large_twoopt_available": large_twoopt_evidence.get("available"),
            "input_large_twoopt_available": input_large_twoopt_signal.get(
                "available"
            ),
            "summary_large_twoopt_mechanism_family_available": (
                large_twoopt_evidence.get("mechanism_family_available")
            ),
            "input_large_twoopt_mechanism_family_available": (
                input_large_twoopt_signal.get("mechanism_family_available")
            ),
            "summary_large_twoopt_direct_evidence_ready": (
                large_twoopt_evidence.get("direct_evidence_ready")
            ),
            "input_large_twoopt_direct_evidence_ready": (
                input_large_twoopt_signal.get("direct_evidence_ready")
            ),
            "summary_large_twoopt_protocol_row_count": (
                large_twoopt_evidence.get("protocol_row_count")
            ),
            "input_large_twoopt_protocol_row_count": (
                input_large_twoopt_signal.get("protocol_row_count")
            ),
        },
    )


def _is_protocol_evaluated_interpretation(interpretation: str) -> bool:
    return (
        interpretation.startswith("protocol_evaluated_")
        or interpretation == "bounded_twoopt_review_ready"
    )


def _is_quality_blocked_interpretation(interpretation: str) -> bool:
    return interpretation.startswith("quality_blocked_")


def _required_review_input_summaries_for_interpretation(
    interpretation: str,
) -> set[str]:
    if _is_quality_blocked_interpretation(interpretation):
        return {"protocol_accounting_summary"}
    return set(REVIEW_INPUT_SUMMARIES)


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
    if summary.get("schema_version") != PROMPT_CONTEXT_VISIBILITY_SCHEMA:
        failures.append("prompt_context_visibility_schema_stale")
    failures.extend(
        _boundary_marker_failures("prompt_context_visibility", summary)
    )
    for excluded_field in (
        "raw_prompt_excluded",
        "raw_response_excluded",
        "patch_body_excluded",
    ):
        if summary.get(excluded_field) is not True:
            failures.append(f"prompt_context_visibility_{excluded_field}_not_true")
    if source_visibility.get("schema_version") != PROMPT_SOURCE_VISIBILITY_SCHEMA:
        failures.append("prompt_source_visibility_schema_stale")
    failures.extend(
        _boundary_marker_failures(
            "prompt_source_visibility",
            source_visibility,
            require_quality=False,
        )
    )
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
    hypothesis_required_count = _int_or_zero(
        source_visibility.get("hypothesis_target_source_required_count")
    )
    hypothesis_visible_count = _int_or_zero(
        source_visibility.get("hypothesis_target_source_visible_count")
    )
    if (
        hypothesis_required_count > 0
        and hypothesis_visible_count < hypothesis_required_count
    ):
        failures.append("hypothesis_target_required_source_not_fully_visible")
    code_trace_count = _int_or_zero(source_visibility.get("code_trace_count"))
    code_protected_source_visible_count = _int_or_zero(
        source_visibility.get("code_protected_source_visible_count")
    )
    code_missing_required_source_trace_count = _int_or_zero(
        source_visibility.get("code_missing_required_source_trace_count")
    )
    if code_trace_count > 0:
        if code_protected_source_visible_count < code_trace_count:
            failures.append("code_protected_source_visibility_not_full")
        if code_missing_required_source_trace_count > 0:
            failures.append("code_missing_required_source_visibility")
    active_constraints_trace_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_trace_count")
    )
    active_constraints_required_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_required_count")
    )
    active_constraints_full_visible_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_full_visible_count")
    )
    if problem_family in {"cvrp", "warehouse_delivery"} and code_trace_count > 0:
        failure_prefix = (
            "cvrp"
            if problem_family == "cvrp"
            else "warehouse"
        )
        if active_constraints_trace_count <= 0:
            failures.append(
                f"{failure_prefix}_active_subject_code_constraints_trace_missing"
            )
        if active_constraints_required_count < code_trace_count:
            failures.append(
                f"{failure_prefix}_active_subject_code_constraints_not_required"
            )
        if active_constraints_full_visible_count < code_trace_count:
            failures.append(
                f"{failure_prefix}_active_subject_code_constraints_not_full_visible"
            )
    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "current_run_evidence": summary.get("current_run_evidence"),
            "schema_version": summary.get("schema_version"),
            "expected_schema_version": PROMPT_CONTEXT_VISIBILITY_SCHEMA,
            "report_only": summary.get("report_only"),
            "quality_judgment": summary.get("quality_judgment"),
            "decision_features_excluded": summary.get("decision_features_excluded"),
            "raw_prompt_excluded": summary.get("raw_prompt_excluded"),
            "raw_response_excluded": summary.get("raw_response_excluded"),
            "patch_body_excluded": summary.get("patch_body_excluded"),
            "available": summary.get("available"),
            "trace_count": aggregate.get("trace_count"),
            "source_visibility_schema_version": source_visibility.get(
                "schema_version"
            ),
            "source_visibility_report_only": source_visibility.get("report_only"),
            "source_visibility_decision_features_excluded": source_visibility.get(
                "decision_features_excluded"
            ),
            "source_visibility_trace_count": source_visibility.get("trace_count"),
            "code_trace_count": source_visibility.get("code_trace_count"),
            "code_protected_source_visible_count": source_visibility.get(
                "code_protected_source_visible_count"
            ),
            "code_protected_source_missing_count": source_visibility.get(
                "code_protected_source_missing_count"
            ),
            "code_missing_required_source_trace_count": source_visibility.get(
                "code_missing_required_source_trace_count"
            ),
            "code_missing_required_source_path_counts": source_visibility.get(
                "code_missing_required_source_path_counts"
            ),
            "active_subject_code_constraints_trace_count": source_visibility.get(
                "active_subject_code_constraints_trace_count"
            ),
            "active_subject_code_constraints_required_count": source_visibility.get(
                "active_subject_code_constraints_required_count"
            ),
            "active_subject_code_constraints_full_visible_count": (
                source_visibility.get(
                    "active_subject_code_constraints_full_visible_count"
                )
            ),
            "active_subject_code_constraints_not_full_visible_count": (
                source_visibility.get(
                    "active_subject_code_constraints_not_full_visible_count"
                )
            ),
            "active_subject_code_constraints_status_counts": source_visibility.get(
                "active_subject_code_constraints_status_counts"
            ),
            "hypothesis_target_source_trace_count": source_visibility.get(
                "hypothesis_target_source_trace_count"
            ),
            "hypothesis_target_source_required_count": source_visibility.get(
                "hypothesis_target_source_required_count"
            ),
            "hypothesis_target_source_visible_count": source_visibility.get(
                "hypothesis_target_source_visible_count"
            ),
            "hypothesis_target_source_not_visible_count": source_visibility.get(
                "hypothesis_target_source_not_visible_count"
            ),
        },
    )


def _research_context_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    prompt_summary = _mapping_or_empty(
        brief.get("prompt_context_visibility_summary")
    )
    continuity_summary = _mapping_or_empty(brief.get("research_continuity_summary"))
    prompt_aggregate = _mapping_or_empty(prompt_summary.get("aggregate"))
    call_kind_counts = _mapping_or_empty(prompt_aggregate.get("call_kind_counts"))
    density = _mapping_or_empty(prompt_aggregate.get("signal_density"))
    actionability = _mapping_or_empty(
        brief.get("research_context_actionability_summary")
    )
    indicators = _mapping_or_empty(actionability.get("indicators"))
    expected_actionability = _research_context_actionability_summary(
        prompt_context_visibility_summary=prompt_summary,
        research_continuity_summary=continuity_summary,
    )
    failures: list[str] = []
    if actionability.get("schema_version") != RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA:
        failures.append("research_context_actionability_schema_stale")
    failures.extend(
        _boundary_marker_failures("research_context_actionability", actionability)
    )
    if actionability.get("current_run_evidence") is not True:
        failures.append("research_context_actionability_not_current_run_evidence")
    if actionability.get("available") is not True:
        failures.append("research_context_actionability_unavailable")
    if _int_or_zero(prompt_aggregate.get("block_family_trace_count")) <= 0:
        failures.append("prompt_block_family_trace_accounting_missing")
    hypothesis_trace_count = _hypothesis_generation_trace_count(call_kind_counts)
    if hypothesis_trace_count <= 0:
        failures.append("prompt_hypothesis_research_context_trace_missing")
    if density.get("schema_version") != PROMPT_SIGNAL_DENSITY_SCHEMA:
        failures.append("prompt_signal_density_schema_stale")
    failures.extend(
        _boundary_marker_failures(
            "prompt_signal_density",
            density,
            require_quality=False,
        )
    )
    if _int_or_zero(density.get("total_token_estimate")) <= 0:
        failures.append("prompt_signal_density_token_accounting_missing")
    if (
        actionability.get("guidance_status")
        == "no_prompt_or_continuity_actionability_evidence"
    ):
        failures.append("research_context_actionability_no_evidence")
    consistency_failures = _research_context_actionability_consistency_failures(
        actionability=actionability,
        expected=expected_actionability,
    )
    failures.extend(consistency_failures)
    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "consistency_failures": consistency_failures,
            "schema_version": actionability.get("schema_version"),
            "expected_schema_version": RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA,
            "current_run_evidence": actionability.get("current_run_evidence"),
            "expected_current_run_evidence": expected_actionability.get(
                "current_run_evidence"
            ),
            "report_only": actionability.get("report_only"),
            "quality_judgment": actionability.get("quality_judgment"),
            "decision_features_excluded": actionability.get(
                "decision_features_excluded"
            ),
            "available": actionability.get("available"),
            "expected_available": expected_actionability.get("available"),
            "guidance_status": actionability.get("guidance_status"),
            "expected_guidance_status": expected_actionability.get(
                "guidance_status"
            ),
            "actionability_gaps": actionability.get("actionability_gaps"),
            "expected_actionability_gaps": expected_actionability.get(
                "actionability_gaps"
            ),
            "block_family_trace_count": prompt_aggregate.get(
                "block_family_trace_count"
            ),
            "call_kind_counts": call_kind_counts,
            "hypothesis_generation_trace_count": hypothesis_trace_count,
            "signal_density_schema_version": density.get("schema_version"),
            "signal_density_report_only": density.get("report_only"),
            "signal_density_decision_features_excluded": density.get(
                "decision_features_excluded"
            ),
            "signal_density_interpretation": density.get("interpretation"),
            "total_token_estimate": density.get("total_token_estimate"),
            "research_signal_tokens": density.get("research_signal_tokens"),
            "source_code_tokens": density.get("source_code_tokens"),
            "cross_branch_tokens": density.get("cross_branch_tokens"),
            "governance_tokens": density.get("governance_tokens"),
            "research_plus_source_to_governance_ratio": density.get(
                "research_plus_source_to_governance_ratio"
            ),
            "same_mechanism_observed": indicators.get("same_mechanism_observed"),
            "expected_same_mechanism_observed": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("same_mechanism_observed"),
            "same_mechanism_missed": indicators.get("same_mechanism_missed"),
            "expected_same_mechanism_missed": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("same_mechanism_missed"),
            "branch_lessons_required": indicators.get("branch_lessons_required"),
            "expected_branch_lessons_required": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("branch_lessons_required"),
            "branch_lesson_semantic_gap_count": indicators.get(
                "branch_lesson_semantic_gap_count"
            ),
            "expected_branch_lesson_semantic_gap_count": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("branch_lesson_semantic_gap_count"),
            "weak_positive_observed": indicators.get("weak_positive_observed"),
            "expected_weak_positive_observed": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("weak_positive_observed"),
            "weak_positive_missed": indicators.get("weak_positive_missed"),
            "expected_weak_positive_missed": _mapping_or_empty(
                expected_actionability.get("indicators")
            ).get("weak_positive_missed"),
        },
    )


def _research_context_actionability_consistency_failures(
    *,
    actionability: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in (
        "current_run_evidence",
        "available",
        "prompt_context_available",
        "research_continuity_available",
        "guidance_status",
    ):
        if actionability.get(field) != expected.get(field):
            failures.append(f"research_context_actionability_{field}_mismatch")

    if _string_list(actionability.get("actionability_gaps")) != _string_list(
        expected.get("actionability_gaps")
    ):
        failures.append("research_context_actionability_gaps_mismatch")
    if _string_list(actionability.get("recommendations")) != _string_list(
        expected.get("recommendations")
    ):
        failures.append("research_context_actionability_recommendations_mismatch")

    indicators = _mapping_or_empty(actionability.get("indicators"))
    expected_indicators = _mapping_or_empty(expected.get("indicators"))
    if indicators.get("schema_version") != expected_indicators.get("schema_version"):
        failures.append("research_context_actionability_indicators_schema_mismatch")

    for field in (
        "same_mechanism_selected",
        "same_mechanism_observed",
        "same_mechanism_missed",
        "branch_lessons_satisfied",
        "branch_lessons_required",
        "branch_lesson_semantic_gap_count",
        "branch_lesson_semantic_failure_count",
        "branch_lesson_semantic_block_count",
        "weak_positive_accepted",
        "weak_positive_observed",
        "weak_positive_missed",
        "research_signal_tokens",
        "source_code_tokens",
        "cross_branch_tokens",
        "governance_tokens",
        "omitted_section_trace_count",
        "truncated_section_trace_count",
    ):
        if _int_or_zero(indicators.get(field)) != _int_or_zero(
            expected_indicators.get(field)
        ):
            failures.append(f"research_context_actionability_{field}_mismatch")

    for field in (
        "branch_lesson_semantic_failure_counts",
        "branch_lesson_semantic_block_counts",
    ):
        if _int_mapping(indicators.get(field)) != _int_mapping(
            expected_indicators.get(field)
        ):
            failures.append(f"research_context_actionability_{field}_mismatch")

    field = "research_plus_source_to_governance_ratio"
    if not _numeric_or_value_equal(
        indicators.get(field),
        expected_indicators.get(field),
    ):
        failures.append(f"research_context_actionability_{field}_mismatch")

    return failures


def _hypothesis_generation_trace_count(call_kind_counts: Mapping[str, Any]) -> int:
    total = 0
    for key, value in call_kind_counts.items():
        text = str(key)
        if text == "hypothesis" or (
            text.startswith("hypothesis_")
            and text != "hypothesis_target_intent"
        ):
            total += _int_or_zero(value)
    return total


def _branch_research_state_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    summary = _mapping_or_empty(brief.get("branch_research_state_summary"))
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    top_branches = summary.get("top_branches")
    expected = _branch_research_state_summary(inventory)
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    expected_top_branches = expected.get("top_branches")
    failures: list[str] = []
    if summary.get("schema_version") != BRANCH_RESEARCH_STATE_SCHEMA:
        failures.append("branch_research_state_schema_stale")
    if summary.get("report_only") is not True:
        failures.append("branch_research_state_not_report_only")
    if summary.get("quality_judgment") is not False:
        failures.append("branch_research_state_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
        failures.append("branch_research_state_decision_features_not_excluded")
    for mutation_field in (
        "campaign_state_mutated",
        "scheduler_state_mutated",
        "promotion_state_mutated",
    ):
        if summary.get(mutation_field) is not False:
            failures.append(f"branch_research_state_{mutation_field}_not_false")
    for excluded_field in (
        "raw_prompts_excluded",
        "raw_responses_excluded",
        "patch_body_excluded",
    ):
        if summary.get(excluded_field) is not True:
            failures.append(f"branch_research_state_{excluded_field}_not_true")
    if summary.get("current_run_evidence") is not True:
        failures.append("branch_research_state_not_current_run_evidence")
    if not isinstance(summary.get("available"), bool):
        failures.append("branch_research_state_available_not_bool")
    if not aggregate:
        failures.append("branch_research_state_aggregate_missing")
    if not isinstance(top_branches, list):
        failures.append("branch_research_state_top_branches_not_list")
    consistency_failures = _branch_research_state_consistency_failures(
        summary=summary,
        expected=expected,
    )
    failures.extend(consistency_failures)

    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "consistency_failures": consistency_failures,
            "current_run_evidence": summary.get("current_run_evidence"),
            "expected_current_run_evidence": expected.get("current_run_evidence"),
            "available": summary.get("available"),
            "expected_available": expected.get("available"),
            "branch_count": aggregate.get("branch_count"),
            "expected_branch_count": expected_aggregate.get("branch_count"),
            "lineage_count": aggregate.get("lineage_count"),
            "expected_lineage_count": expected_aggregate.get("lineage_count"),
            "branch_state_counts": aggregate.get("branch_state_counts"),
            "expected_branch_state_counts": expected_aggregate.get(
                "branch_state_counts"
            ),
            "branches_with_hypotheses": aggregate.get("branches_with_hypotheses"),
            "expected_branches_with_hypotheses": expected_aggregate.get(
                "branches_with_hypotheses"
            ),
            "branches_with_events": aggregate.get("branches_with_events"),
            "expected_branches_with_events": expected_aggregate.get(
                "branches_with_events"
            ),
            "branches_with_sessions": aggregate.get("branches_with_sessions"),
            "expected_branches_with_sessions": expected_aggregate.get(
                "branches_with_sessions"
            ),
            "branches_with_traces": aggregate.get("branches_with_traces"),
            "expected_branches_with_traces": expected_aggregate.get(
                "branches_with_traces"
            ),
            "hypothesis_count": aggregate.get("hypothesis_count"),
            "expected_hypothesis_count": expected_aggregate.get("hypothesis_count"),
            "events_by_kind": aggregate.get("events_by_kind"),
            "expected_events_by_kind": expected_aggregate.get("events_by_kind"),
            "events_by_decision": aggregate.get("events_by_decision"),
            "expected_events_by_decision": expected_aggregate.get(
                "events_by_decision"
            ),
            "events_by_stage": aggregate.get("events_by_stage"),
            "expected_events_by_stage": expected_aggregate.get("events_by_stage"),
            "top_branch_count": (
                len(top_branches) if isinstance(top_branches, list) else None
            ),
            "expected_top_branch_count": (
                len(expected_top_branches)
                if isinstance(expected_top_branches, list)
                else None
            ),
        },
    )


def _branch_research_state_consistency_failures(
    *,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if summary.get("current_run_evidence") is not expected.get(
        "current_run_evidence"
    ):
        failures.append("branch_research_state_current_run_evidence_mismatch")
    if summary.get("available") is not expected.get("available"):
        failures.append("branch_research_state_available_mismatch")

    aggregate = _mapping_or_empty(summary.get("aggregate"))
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    for field in (
        "branch_count",
        "lineage_count",
        "branches_with_hypotheses",
        "branches_with_events",
        "branches_with_sessions",
        "branches_with_traces",
        "rollback_count_total",
        "branches_with_rollback",
        "hypothesis_count",
    ):
        if _int_or_zero(aggregate.get(field)) != _int_or_zero(
            expected_aggregate.get(field)
        ):
            failures.append(f"branch_research_state_{field}_mismatch")
    for field in (
        "branch_state_counts",
        "failure_code_counts",
        "hypotheses_by_status",
        "hypotheses_by_action",
        "hypotheses_by_change_locus",
        "events_by_kind",
        "events_by_decision",
        "events_by_stage",
    ):
        if _int_mapping(aggregate.get(field)) != _int_mapping(
            expected_aggregate.get(field)
        ):
            failures.append(f"branch_research_state_{field}_mismatch")

    top_branches = summary.get("top_branches")
    expected_top_branches = expected.get("top_branches")
    if isinstance(top_branches, list) and isinstance(expected_top_branches, list):
        if top_branches != expected_top_branches:
            failures.append("branch_research_state_top_branches_mismatch")
    return failures


def _champion_progress_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
        "reason": "not_problem_specific_agentic_summary",
        "problem_family": problem_family,
    }
    summary = _mapping_or_empty(brief.get("champion_progress_summary"))
    expected = _champion_progress_summary(inventory)
    failures: list[str] = []
    if summary.get("schema_version") != CHAMPION_PROGRESS_SCHEMA:
        failures.append("champion_progress_schema_stale")
    if summary.get("current_run_evidence") is not True:
        failures.append("champion_progress_not_current_run_evidence")
    if summary.get("report_only") is not True:
        failures.append("champion_progress_not_report_only")
    if summary.get("quality_judgment") is not False:
        failures.append("champion_progress_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
        failures.append("champion_progress_decision_features_not_excluded")
    for mutation_field in (
        "campaign_state_mutated",
        "scheduler_state_mutated",
        "promotion_state_mutated",
    ):
        if summary.get(mutation_field) is not False:
            failures.append(f"champion_progress_{mutation_field}_not_false")
    if not str(summary.get("interpretation") or ""):
        failures.append("champion_progress_interpretation_missing")
    consistency_failures = _champion_progress_consistency_failures(
        summary=summary,
        expected=expected,
    )
    failures.extend(consistency_failures)

    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "consistency_failures": consistency_failures,
            "current_run_evidence": summary.get("current_run_evidence"),
            "expected_current_run_evidence": expected.get("current_run_evidence"),
            "available": summary.get("available"),
            "expected_available": expected.get("available"),
            "interpretation": summary.get("interpretation"),
            "expected_interpretation": expected.get("interpretation"),
            "starting_champion_version": summary.get("starting_champion_version"),
            "expected_starting_champion_version": expected.get(
                "starting_champion_version"
            ),
            "current_champion_version": summary.get("current_champion_version"),
            "expected_current_champion_version": expected.get(
                "current_champion_version"
            ),
            "champion_version_gain": summary.get("champion_version_gain"),
            "expected_champion_version_gain": expected.get("champion_version_gain"),
            "champion_count": summary.get("champion_count"),
            "expected_champion_count": expected.get("champion_count"),
            "champion_versions": summary.get("champion_versions"),
            "expected_champion_versions": expected.get("champion_versions"),
            "promoted_hypothesis_count": summary.get("promoted_hypothesis_count"),
            "expected_promoted_hypothesis_count": expected.get(
                "promoted_hypothesis_count"
            ),
            "promotion_decision_count": summary.get("promotion_decision_count"),
            "expected_promotion_decision_count": expected.get(
                "promotion_decision_count"
            ),
        },
    )


def _champion_progress_consistency_failures(
    *,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in (
        "current_run_evidence",
        "available",
        "interpretation",
        "champion_table_present",
        "latest_promotion_experiment_id",
        "latest_promotion_dossier_ref",
    ):
        if summary.get(field) != expected.get(field):
            failures.append(f"champion_progress_{field}_mismatch")
    for field in (
        "starting_champion_version",
        "current_champion_version",
        "champion_version_gain",
        "champion_count",
        "max_weight_revision",
        "promotion_experiment_count",
        "promotion_dossier_count",
        "promoted_at_count",
        "promoted_hypothesis_count",
        "promotion_decision_count",
    ):
        if _int_or_none(summary.get(field)) != _int_or_none(expected.get(field)):
            failures.append(f"champion_progress_{field}_mismatch")
    if _int_list(summary.get("champion_versions")) != _int_list(
        expected.get("champion_versions")
    ):
        failures.append("champion_progress_champion_versions_mismatch")
    return failures


def _failure_taxonomy_actionability(
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }
    summary = _mapping_or_empty(brief.get("failure_taxonomy_summary"))
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(aggregate.get("proposal_quality"))
    entries = summary.get("entries")
    entry_count = len(entries) if isinstance(entries, list) else 0
    report_evidence_count = max(
        _int_or_zero(summary.get("failure_report_count")),
        entry_count,
    )
    run_validity_counts = _mapping_or_empty(
        aggregate.get("run_validity_status_counts")
    )
    failure_observation_counts = _mapping_or_empty(
        aggregate.get("failure_observation_counts")
    )
    proposal_attempts = _int_or_zero(
        proposal_quality.get("proposal_attempts_total")
    )
    report_evidence_available = (
        bool(run_validity_counts)
        or bool(failure_observation_counts)
        or proposal_attempts > 0
    )
    failures: list[str] = []
    if summary.get("schema_version") != FAILURE_TAXONOMY_SCHEMA:
        failures.append("failure_taxonomy_schema_stale")
    failures.extend(_boundary_marker_failures("failure_taxonomy", summary))
    if summary.get("raw_logs_excluded") is not True:
        failures.append("failure_taxonomy_raw_logs_excluded_not_true")
    if summary.get("current_run_evidence") is not True:
        failures.append("failure_taxonomy_not_current_run_evidence")
    if summary.get("available") is not True:
        failures.append("failure_taxonomy_unavailable")
    if _int_or_zero(summary.get("report_count")) <= 0:
        failures.append("failure_taxonomy_report_count_missing")
    if report_evidence_count <= 0:
        failures.append("failure_taxonomy_entry_missing")
    if not report_evidence_available:
        failures.append("failure_taxonomy_report_evidence_missing")
    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "schema_version": summary.get("schema_version"),
            "expected_schema_version": FAILURE_TAXONOMY_SCHEMA,
            "current_run_evidence": summary.get("current_run_evidence"),
            "report_only": summary.get("report_only"),
            "quality_judgment": summary.get("quality_judgment"),
            "decision_features_excluded": summary.get("decision_features_excluded"),
            "raw_logs_excluded": summary.get("raw_logs_excluded"),
            "available": summary.get("available"),
            "report_count": summary.get("report_count"),
            "failure_report_count": summary.get("failure_report_count"),
            "entry_count": entry_count,
            "run_validity_status_counts": run_validity_counts,
            "failure_observation_counts": failure_observation_counts,
            "proposal_attempts_total": proposal_quality.get(
                "proposal_attempts_total"
            ),
            "proposal_quality_blocks": proposal_quality.get(
                "proposal_quality_blocks"
            ),
            "quality_blocks": proposal_quality.get("quality_blocks"),
            "quality_block_ledger_count": proposal_quality.get(
                "quality_block_ledger_count"
            ),
        },
    )


def _blocking_problem_summary_gaps(
    evidence_gaps: list[str],
    *,
    interpretation: str,
) -> list[str]:
    nonblocking_for_interpretation = (
        NONBLOCKING_PROBLEM_SUMMARY_GAPS_BY_INTERPRETATION.get(
            interpretation,
            set(),
        )
    )
    return [
        gap
        for gap in evidence_gaps
        if gap in BLOCKING_PROBLEM_SUMMARY_GAPS
        and gap not in nonblocking_for_interpretation
    ]


def _boundary_marker_failures(
    prefix: str,
    payload: Mapping[str, Any],
    *,
    require_quality: bool = True,
) -> list[str]:
    failures: list[str] = []
    if payload.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if require_quality and payload.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if payload.get("decision_features_excluded") is not True:
        failures.append(f"{prefix}_decision_features_not_excluded")
    return failures


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


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(count) for key, count in value.items()}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _numeric_or_value_equal(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    try:
        return abs(float(actual) - float(expected)) <= 1e-9
    except (TypeError, ValueError):
        return False


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    items: list[int] = []
    for item in value:
        parsed = _int_or_none(item)
        if parsed is not None:
            items.append(parsed)
    return items


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
