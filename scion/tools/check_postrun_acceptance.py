#!/usr/bin/env python3
"""Check whether postrun acceptance artifacts are ready for delegated review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
SCION_ROOT = TOOLS_DIR.parent
if str(SCION_ROOT) not in sys.path:
    sys.path.insert(0, str(SCION_ROOT))

from postrun_artifact_inventory import build_inventory  # noqa: E402
from postrun_analysis_brief import (  # noqa: E402
    _branch_research_state_summary,
    _champion_progress_summary,
    _failure_taxonomy_summary,
    _measurement_effect_summary,
    _prompt_context_visibility_summary,
    _proposal_trajectory_manifests,
    _protocol_accounting_summary,
    _research_continuity_summary,
    _research_context_actionability_summary,
    _runtime_feedback_summary,
)
from scion.postrun import (  # noqa: E402
    MappingPostrunInventoryPort,
    PostrunReadinessOrchestrator,
    PostrunArtifactAcceptancePort,
    PostrunEvidenceConsistencyAcceptancePort,
    PostrunLifecycleAcceptancePort,
    PostrunPromptVisibilityAcceptancePort,
    PostrunReviewInputAcceptancePort,
    PostrunResearchTelemetryAcceptancePort,
    ProblemReviewRegistry,
    problem_summary_actionability_detail,
    problem_summary_actionability_status,
)
from scion.problems.cvrp.opportunity_review import (  # noqa: E402
    SCHEMA_VERSION as CVRP_OPPORTUNITY_USAGE_SCHEMA,
    build_cvrp_opportunity_usage_summary,
    cvrp_opportunity_usage_signature,
)
from scion.problems.cvrp.postrun_review import (  # noqa: E402
    CVRP_LARGE_TWOOPT_ACTIONABILITY_SPEC,
    CvrpLargeTwoOptReviewPort,
    cvrp_large_twoopt_input_consistency,
)
from scion.problems.warehouse_delivery.postrun_review import (  # noqa: E402
    WAREHOUSE_FOLLOWUP_ACTIONABILITY_SPEC,
    WarehouseFollowupReviewPort,
    warehouse_followup_input_consistency,
)


SCHEMA_VERSION = "scion.postrun_acceptance_readiness.v1"
UNREADY_EXIT = 64
PROBLEM_SUMMARY_ACTIONABILITY_SPECS = {
    WAREHOUSE_FOLLOWUP_ACTIONABILITY_SPEC.summary_key: WAREHOUSE_FOLLOWUP_ACTIONABILITY_SPEC,
    CVRP_LARGE_TWOOPT_ACTIONABILITY_SPEC.summary_key: CVRP_LARGE_TWOOPT_ACTIONABILITY_SPEC,
}
PROBLEM_SUMMARY_SCHEMAS = {
    key: spec.schema_version
    for key, spec in PROBLEM_SUMMARY_ACTIONABILITY_SPECS.items()
}

def build_readiness(
    run_root: Path | str,
    *,
    include_typed_summary: bool = False,
) -> dict[str, Any]:
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

    artifact_port = PostrunArtifactAcceptancePort()
    report_dir = root / "postrun_acceptance"
    rebuild_manifest = artifact_port.read_rebuild_manifest(report_dir)
    inventory_path = artifact_port.artifact_json_path_from_manifest(
        rebuild_manifest,
        report_dir,
        "inventory",
    )
    stored_inventory = (
        artifact_port.read_json_object(inventory_path)
        if inventory_path is not None
        else {}
    )
    if stored_inventory:
        inventory = stored_inventory
        inventory_source = "stored_postrun_inventory"
    else:
        inventory = build_inventory(root)
        inventory_source = "live_inventory_rebuild"
    postrun_reports = _mapping_or_empty(inventory.get("postrun_reports"))
    postrun_counts = _mapping_or_empty(postrun_reports.get("counts"))

    analysis_brief_path = artifact_port.analysis_brief_path_from_manifest(
        rebuild_manifest,
        report_dir,
    )
    analysis_brief = (
        artifact_port.read_json_object(analysis_brief_path)
        if analysis_brief_path
        else {}
    )

    checks.update(
        artifact_port.summarize(
            root=root,
            report_dir=report_dir,
            rebuild_manifest=rebuild_manifest,
            inventory_source=inventory_source,
            inventory_path=inventory_path,
            analysis_brief_path=analysis_brief_path,
            analysis_brief=analysis_brief,
            postrun_counts=postrun_counts,
        ).to_payloads()
    )
    checks.update(
        PostrunLifecycleAcceptancePort()
        .summarize(inventory, analysis_brief)
        .to_payloads()
    )
    checks.update(
        PostrunEvidenceConsistencyAcceptancePort()
        .summarize(analysis_brief=analysis_brief, inventory=inventory)
        .to_payloads()
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
            root,
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
        root,
        analysis_brief,
        inventory,
    )
    add_check(
        "prompt_source_visibility_actionability",
        prompt_status,
        prompt_detail,
        required=prompt_status != "skipped",
    )
    cvrp_usage_status, cvrp_usage_detail = _cvrp_opportunity_usage_actionability(
        root,
        analysis_brief,
        inventory,
    )
    add_check(
        "cvrp_opportunity_usage_actionability",
        cvrp_usage_status,
        cvrp_usage_detail,
        required=False,
    )
    checks.update(
        _research_telemetry_acceptance_checks(
            root,
            analysis_brief,
            inventory,
        ).to_payloads()
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
    typed_readiness = _typed_postrun_readiness_payload(
        root,
        inventory,
        analysis_brief=analysis_brief,
    )
    payload = {
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
    if include_typed_summary:
        payload["typed_readiness_summary"] = typed_readiness
    return payload


def _research_telemetry_acceptance_checks(
    root: Path,
    analysis_brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
):
    problem_family = _problem_family(analysis_brief, inventory)
    enabled = problem_family in {"warehouse_delivery", "cvrp"}
    expected_research_context_actionability: Mapping[str, Any] = {}
    expected_branch_research_state: Mapping[str, Any] = {}
    expected_champion_progress: Mapping[str, Any] = {}
    expected_failure_taxonomy: Mapping[str, Any] = {}
    if enabled:
        prompt_summary = _mapping_or_empty(
            analysis_brief.get("prompt_context_visibility_summary")
        )
        continuity_summary = _mapping_or_empty(
            analysis_brief.get("research_continuity_summary")
        )
        expected_research_context_actionability = (
            _research_context_actionability_summary(
                prompt_context_visibility_summary=prompt_summary,
                research_continuity_summary=continuity_summary,
            )
        )
        expected_branch_research_state = _branch_research_state_summary(inventory)
        expected_champion_progress = _champion_progress_summary(inventory)
        expected_failure_taxonomy = _failure_taxonomy_summary(root, inventory)
    return PostrunResearchTelemetryAcceptancePort().summarize(
        problem_family=problem_family,
        analysis_brief=analysis_brief,
        expected_research_context_actionability=(
            expected_research_context_actionability
        ),
        expected_branch_research_state=expected_branch_research_state,
        expected_champion_progress=expected_champion_progress,
        expected_failure_taxonomy=expected_failure_taxonomy,
        enabled=enabled,
    )


def _typed_postrun_readiness_payload(
    root: Path,
    inventory: Mapping[str, Any],
    *,
    analysis_brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the Design N typed-port summary without changing legacy output."""

    typed_inventory = dict(inventory)
    if analysis_brief:
        typed_inventory["analysis_brief"] = analysis_brief
    return (
        PostrunReadinessOrchestrator(
            MappingPostrunInventoryPort(typed_inventory),
            problem_reviews=ProblemReviewRegistry(
                {
                    "cvrp": CvrpLargeTwoOptReviewPort(),
                    "warehouse_delivery": WarehouseFollowupReviewPort(),
                }
            ),
        )
        .build(root)
        .to_payload()
    )


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
    expected_current_run_evidence = _brief_current_run_evidence(brief)
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
                expected_current_run_evidence=expected_current_run_evidence,
            )
        ]
        return (_summary_actionability_status(summaries), summaries)

    summaries = []
    for key in ("warehouse_followup_summary", "cvrp_large_twoopt_summary"):
        summary = _mapping_or_empty(brief.get(key))
        if summary.get("available") is not True:
            continue
        summaries.append(
            _summary_actionability_detail(
                key,
                summary,
                expected_current_run_evidence=expected_current_run_evidence,
            )
        )
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
    expected_current_run_evidence: bool | None = None,
) -> dict[str, Any]:
    spec = PROBLEM_SUMMARY_ACTIONABILITY_SPECS[key]
    return problem_summary_actionability_detail(
        spec,
        summary,
        expected_family=expected_family,
        expected_current_run_evidence=expected_current_run_evidence,
    )


def _summary_actionability_status(summaries: list[dict[str, Any]]) -> str:
    return problem_summary_actionability_status(summaries)


def _review_input_summaries_actionability(
    run_root: Path,
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
    expected_summaries = {
        "protocol_accounting_summary": _protocol_accounting_summary(
            run_root,
            inventory,
        ),
        "measurement_effect_summary": _measurement_effect_summary(
            run_root,
            inventory,
        ),
        "runtime_feedback_summary": _runtime_feedback_summary(
            run_root,
            inventory,
        ),
        "research_continuity_summary": _research_continuity_summary(
            run_root,
            inventory,
        ),
    }
    check = PostrunReviewInputAcceptancePort().summarize(
        problem_family=problem_family,
        interpretation=interpretation,
        analysis_brief=brief,
        expected_summaries=expected_summaries,
        required_summary_keys=required_summaries,
    ).checks[0]
    return (
        check.status,
        check.detail,
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

    kwargs = {
        "summary": summary,
        "protocol_accounting_summary": _mapping_or_empty(
            brief.get("protocol_accounting_summary")
        ),
        "measurement_effect_summary": _mapping_or_empty(
            brief.get("measurement_effect_summary")
        ),
        "runtime_feedback_summary": _mapping_or_empty(
            brief.get("runtime_feedback_summary")
        ),
        "failure_taxonomy_summary": _mapping_or_empty(
            brief.get("failure_taxonomy_summary")
        ),
        "research_continuity_summary": _mapping_or_empty(
            brief.get("research_continuity_summary")
        ),
    }
    if expected_key == "warehouse_followup_summary":
        return warehouse_followup_input_consistency(inventory, **kwargs)
    if expected_key == "cvrp_large_twoopt_summary":
        return cvrp_large_twoopt_input_consistency(inventory, **kwargs)
    return "skipped", {
        "reason": "unsupported_problem_specific_summary",
        "problem_family": problem_family,
        "summary": expected_key,
    }


def _is_quality_blocked_interpretation(interpretation: str) -> bool:
    return interpretation.startswith("quality_blocked_")


def _required_review_input_summaries_for_interpretation(
    interpretation: str,
) -> set[str]:
    if _is_quality_blocked_interpretation(interpretation):
        return {"protocol_accounting_summary"}
    return PostrunReviewInputAcceptancePort.summary_keys()


def _prompt_source_visibility_actionability(
    run_root: Path,
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family not in {"warehouse_delivery", "cvrp"}:
        return "skipped", {
            "reason": "not_problem_specific_agentic_summary",
            "problem_family": problem_family,
        }

    expected = _prompt_context_visibility_summary(run_root, inventory)
    failure_prefix = "cvrp" if problem_family == "cvrp" else "warehouse"
    check = PostrunPromptVisibilityAcceptancePort().summarize(
        problem_family=problem_family,
        summary=_mapping_or_empty(brief.get("prompt_context_visibility_summary")),
        expected=expected,
        active_subject_failure_prefix=failure_prefix,
    ).checks[0]
    return check.status, check.detail

def _cvrp_opportunity_usage_actionability(
    run_root: Path,
    brief: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> tuple[str, Any]:
    problem_family = _problem_family(brief, inventory)
    if problem_family != "cvrp":
        return "skipped", {
            "reason": "not_cvrp",
            "problem_family": problem_family,
        }
    if not _brief_current_run_evidence(brief):
        return "skipped", {
            "reason": "not_current_run_evidence",
            "problem_family": problem_family,
        }

    summary = _mapping_or_empty(brief.get("cvrp_opportunity_usage_summary"))
    prompt_context = _mapping_or_empty(
        brief.get("prompt_context_visibility_summary")
    )
    expected = build_cvrp_opportunity_usage_summary(
        problem_family=problem_family,
        current_run_evidence=_brief_current_run_evidence(brief),
        prompt_context_visibility_summary=_prompt_context_visibility_summary(
            run_root,
            inventory,
        ),
        proposal_trajectory_manifests=_proposal_trajectory_manifests(
            run_root,
            inventory,
        ),
        cvrp_large_twoopt_summary=(
            _mapping_or_empty(brief.get("cvrp_large_twoopt_summary"))
            if summary.get("required_evidence_proof")
            else None
        ),
    )

    failures: list[str] = []
    if not summary:
        failures.append("cvrp_opportunity_usage_summary_missing")
    if summary.get("schema_version") != CVRP_OPPORTUNITY_USAGE_SCHEMA:
        failures.append("cvrp_opportunity_usage_schema_stale")
    failures.extend(
        _boundary_marker_failures("cvrp_opportunity_usage", summary)
    )
    for excluded_field in (
        "proposal_visibility_only",
        "raw_prompt_excluded",
        "raw_response_excluded",
        "patch_body_excluded",
    ):
        if summary.get(excluded_field) is not True:
            failures.append(f"cvrp_opportunity_usage_{excluded_field}_not_true")
    if summary.get("problem_family") != problem_family:
        failures.append("cvrp_opportunity_usage_problem_family_mismatch")
    if (
        summary.get("current_run_evidence")
        is not _brief_current_run_evidence(brief)
    ):
        failures.append("cvrp_opportunity_usage_current_run_evidence_mismatch")
    if (
        summary.get("opportunity_summary_visible")
        is not _brief_problem_opportunity_summary_visible(prompt_context)
    ):
        failures.append("cvrp_opportunity_usage_visibility_mismatch")
    summary_signature = cvrp_opportunity_usage_signature(summary)
    expected_signature = cvrp_opportunity_usage_signature(expected)
    if summary_signature != expected_signature:
        failures.append("cvrp_opportunity_usage_signature_mismatch")

    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "schema_version": summary.get("schema_version"),
            "expected_schema_version": CVRP_OPPORTUNITY_USAGE_SCHEMA,
            "summary_signature": summary_signature,
            "expected_signature": expected_signature,
        },
    )


def _brief_problem_opportunity_summary_visible(
    brief_prompt_context: Mapping[str, Any],
) -> bool:
    aggregate = _mapping_or_empty(brief_prompt_context.get("aggregate"))
    visibility = _mapping_or_empty(aggregate.get("problem_opportunity_visibility"))
    return (
        _int_or_zero(visibility.get("section_visible_trace_count")) > 0
        or _int_or_zero(
            visibility.get("hypothesis_generation_section_visible_trace_count")
        )
        > 0
    )


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


def _json_comparison_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError):
        return str(value)


def _summary_without_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                _path_tail_signature(item)
                if str(key) == "path"
                else _summary_without_paths(item)
            )
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_summary_without_paths(item) for item in value]
    return _json_comparison_value(value)


def _path_tail_signature(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return _json_comparison_value(value)
    normalized = value.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in {"", "/"}]
    return {"path_tail": parts[-4:]}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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
