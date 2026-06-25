"""Generic research telemetry postrun acceptance checks."""

from __future__ import annotations

from typing import Any, Mapping

from scion.postrun.acceptance_checks import (
    PostrunAcceptanceCheck,
    PostrunAcceptanceCheckBundle,
)
from scion.postrun.failure_taxonomy_acceptance import (
    failure_taxonomy_actionability as _failure_taxonomy_actionability,
)


BRANCH_RESEARCH_STATE_SCHEMA = "scion.postrun_branch_research_state_summary.v1"
CHAMPION_PROGRESS_SCHEMA = "scion.postrun_champion_progress_summary.v1"
PROMPT_SIGNAL_DENSITY_SCHEMA = "scion.postrun_prompt_signal_density.v1"
RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA = (
    "scion.postrun_research_context_actionability_summary.v1"
)
FAILURE_TAXONOMY_SCHEMA = "scion.postrun_failure_taxonomy_summary.v1"


class PostrunResearchTelemetryAcceptancePort:
    """Validate generic research telemetry summaries without problem semantics."""

    def summarize(
        self,
        *,
        problem_family: str | None,
        analysis_brief: Mapping[str, Any],
        expected_research_context_actionability: Mapping[str, Any],
        expected_branch_research_state: Mapping[str, Any],
        expected_champion_progress: Mapping[str, Any],
        expected_failure_taxonomy: Mapping[str, Any],
        enabled: bool = True,
    ) -> PostrunAcceptanceCheckBundle:
        if not enabled:
            return PostrunAcceptanceCheckBundle(
                checks=tuple(
                    PostrunAcceptanceCheck(
                        name=name,
                        status="skipped",
                        required=False,
                        detail={
                            "reason": "not_problem_specific_agentic_summary",
                            "problem_family": problem_family,
                        },
                    )
                    for name in (
                        "research_context_actionability",
                        "branch_research_state_actionability",
                        "champion_progress_actionability",
                        "failure_taxonomy_actionability",
                    )
                )
            )

        research_context_status, research_context_detail = (
            _research_context_actionability(
                problem_family=problem_family,
                brief=analysis_brief,
                expected=expected_research_context_actionability,
            )
        )
        branch_state_status, branch_state_detail = _branch_research_state_actionability(
            problem_family=problem_family,
            brief=analysis_brief,
            expected=expected_branch_research_state,
        )
        champion_status, champion_detail = _champion_progress_actionability(
            problem_family=problem_family,
            brief=analysis_brief,
            expected=expected_champion_progress,
        )
        failure_taxonomy_status, failure_taxonomy_detail = (
            _failure_taxonomy_actionability(
                problem_family=problem_family,
                brief=analysis_brief,
                expected=expected_failure_taxonomy,
            )
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="research_context_actionability",
                    status=research_context_status,
                    detail=research_context_detail,
                ),
                PostrunAcceptanceCheck(
                    name="branch_research_state_actionability",
                    status=branch_state_status,
                    detail=branch_state_detail,
                ),
                PostrunAcceptanceCheck(
                    name="champion_progress_actionability",
                    status=champion_status,
                    detail=champion_detail,
                ),
                PostrunAcceptanceCheck(
                    name="failure_taxonomy_actionability",
                    status=failure_taxonomy_status,
                    detail=failure_taxonomy_detail,
                ),
            )
        )


def _research_context_actionability(
    *,
    problem_family: str | None,
    brief: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    prompt_summary = _mapping_or_empty(
        brief.get("prompt_context_visibility_summary")
    )
    continuity_summary = _mapping_or_empty(brief.get("research_continuity_summary"))
    continuity_aggregate = _mapping_or_empty(continuity_summary.get("aggregate"))
    prompt_aggregate = _mapping_or_empty(prompt_summary.get("aggregate"))
    call_kind_counts = _mapping_or_empty(prompt_aggregate.get("call_kind_counts"))
    density = _mapping_or_empty(prompt_aggregate.get("signal_density"))
    hypothesis_density = _mapping_or_empty(
        prompt_aggregate.get("hypothesis_generation_signal_density")
    )
    actionability = _mapping_or_empty(
        brief.get("research_context_actionability_summary")
    )
    indicators = _mapping_or_empty(actionability.get("indicators"))
    expected_actionability = _mapping_or_empty(expected)
    expected_indicators = _mapping_or_empty(expected_actionability.get("indicators"))
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
    projected_hypothesis_trace_count = _int_or_zero(
        prompt_aggregate.get("hypothesis_generation_trace_count")
    )
    hypothesis_block_family_trace_count = _int_or_zero(
        prompt_aggregate.get("hypothesis_generation_block_family_trace_count")
    )
    if hypothesis_trace_count <= 0:
        failures.append("prompt_hypothesis_research_context_trace_missing")
    if projected_hypothesis_trace_count != hypothesis_trace_count:
        failures.append("prompt_hypothesis_generation_trace_count_mismatch")
    if hypothesis_trace_count > 0 and hypothesis_block_family_trace_count <= 0:
        failures.append("prompt_hypothesis_generation_block_family_missing")
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
    if hypothesis_density.get("schema_version") != PROMPT_SIGNAL_DENSITY_SCHEMA:
        failures.append("prompt_hypothesis_generation_signal_density_schema_stale")
    failures.extend(
        _boundary_marker_failures(
            "prompt_hypothesis_generation_signal_density",
            hypothesis_density,
            require_quality=False,
        )
    )
    if (
        hypothesis_trace_count > 0
        and _int_or_zero(hypothesis_density.get("total_token_estimate")) <= 0
    ):
        failures.append(
            "prompt_hypothesis_generation_signal_density_token_accounting_missing"
        )
    continuity_signal_observed = (
        continuity_summary.get("available") is True
        and (
            _int_or_zero(continuity_aggregate.get("max_branch_depth")) > 1
            or _int_or_zero(expected_indicators.get("same_mechanism_observed")) > 0
            or _int_or_zero(expected_indicators.get("branch_lessons_required")) > 0
            or _int_or_zero(expected_indicators.get("weak_positive_observed")) > 0
        )
    )
    hypothesis_research_tokens = _int_or_zero(
        hypothesis_density.get("research_signal_tokens")
    )
    hypothesis_cross_branch_tokens = _int_or_zero(
        hypothesis_density.get("cross_branch_tokens")
    )
    if (
        continuity_signal_observed
        and hypothesis_research_tokens + hypothesis_cross_branch_tokens <= 0
    ):
        failures.append("prompt_hypothesis_generation_research_signal_missing")
    if (
        _int_or_zero(expected_indicators.get("branch_lessons_required")) > 0
        and hypothesis_cross_branch_tokens <= 0
    ):
        failures.append("prompt_hypothesis_generation_cross_branch_signal_missing")
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
            "projected_hypothesis_generation_trace_count": (
                projected_hypothesis_trace_count
            ),
            "hypothesis_generation_block_family_trace_count": (
                hypothesis_block_family_trace_count
            ),
            "signal_density_schema_version": density.get("schema_version"),
            "signal_density_report_only": density.get("report_only"),
            "signal_density_decision_features_excluded": density.get(
                "decision_features_excluded"
            ),
            "signal_density_interpretation": density.get("interpretation"),
            "hypothesis_generation_signal_density_schema_version": (
                hypothesis_density.get("schema_version")
            ),
            "hypothesis_generation_signal_density_report_only": (
                hypothesis_density.get("report_only")
            ),
            "hypothesis_generation_signal_density_decision_features_excluded": (
                hypothesis_density.get("decision_features_excluded")
            ),
            "hypothesis_generation_signal_density_interpretation": (
                hypothesis_density.get("interpretation")
            ),
            "total_token_estimate": density.get("total_token_estimate"),
            "research_signal_tokens": density.get("research_signal_tokens"),
            "source_code_tokens": density.get("source_code_tokens"),
            "cross_branch_tokens": density.get("cross_branch_tokens"),
            "governance_tokens": density.get("governance_tokens"),
            "hypothesis_generation_research_signal_tokens": (
                hypothesis_density.get("research_signal_tokens")
            ),
            "hypothesis_generation_source_code_tokens": (
                hypothesis_density.get("source_code_tokens")
            ),
            "hypothesis_generation_cross_branch_tokens": (
                hypothesis_density.get("cross_branch_tokens")
            ),
            "hypothesis_generation_governance_tokens": (
                hypothesis_density.get("governance_tokens")
            ),
            "research_plus_source_to_governance_ratio": density.get(
                "research_plus_source_to_governance_ratio"
            ),
            "same_mechanism_observed": indicators.get("same_mechanism_observed"),
            "expected_same_mechanism_observed": expected_indicators.get(
                "same_mechanism_observed"
            ),
            "same_mechanism_missed": indicators.get("same_mechanism_missed"),
            "expected_same_mechanism_missed": expected_indicators.get(
                "same_mechanism_missed"
            ),
            "branch_lessons_required": indicators.get("branch_lessons_required"),
            "expected_branch_lessons_required": expected_indicators.get(
                "branch_lessons_required"
            ),
            "branch_lesson_semantic_gap_count": indicators.get(
                "branch_lesson_semantic_gap_count"
            ),
            "expected_branch_lesson_semantic_gap_count": expected_indicators.get(
                "branch_lesson_semantic_gap_count"
            ),
            "weak_positive_observed": indicators.get("weak_positive_observed"),
            "expected_weak_positive_observed": expected_indicators.get(
                "weak_positive_observed"
            ),
            "weak_positive_missed": indicators.get("weak_positive_missed"),
            "expected_weak_positive_missed": expected_indicators.get(
                "weak_positive_missed"
            ),
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
        "research_continuity_max_branch_depth",
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
        "hypothesis_generation_trace_count",
        "hypothesis_generation_block_family_trace_count",
        "hypothesis_generation_research_signal_tokens",
        "hypothesis_generation_source_code_tokens",
        "hypothesis_generation_cross_branch_tokens",
        "hypothesis_generation_governance_tokens",
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

    for field in (
        "research_plus_source_to_governance_ratio",
        "hypothesis_generation_research_plus_source_to_governance_ratio",
    ):
        if not _numeric_or_value_equal(
            indicators.get(field),
            expected_indicators.get(field),
        ):
            failures.append(f"research_context_actionability_{field}_mismatch")

    return failures


_FORMAL_HYPOTHESIS_GENERATION_CALL_KINDS = frozenset(
    {
        "hypothesis",
        "hypothesis_retry",
        "hypothesis_preview_retry",
        "hypothesis_grounding_retry",
        "hypothesis_semantic_retry",
    }
)


def _hypothesis_generation_trace_count(call_kind_counts: Mapping[str, Any]) -> int:
    total = 0
    for key, value in call_kind_counts.items():
        if str(key) in _FORMAL_HYPOTHESIS_GENERATION_CALL_KINDS:
            total += _int_or_zero(value)
    return total


def _branch_research_state_actionability(
    *,
    problem_family: str | None,
    brief: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    summary = _mapping_or_empty(brief.get("branch_research_state_summary"))
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    top_branches = summary.get("top_branches")
    expected = _mapping_or_empty(expected)
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
    *,
    problem_family: str | None,
    brief: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    summary = _mapping_or_empty(brief.get("champion_progress_summary"))
    expected = _mapping_or_empty(expected)
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


def _boundary_marker_failures(
    prefix: str,
    summary: Mapping[str, Any],
    *,
    require_quality: bool = True,
) -> list[str]:
    failures: list[str] = []
    if summary.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if require_quality and summary.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
        failures.append(f"{prefix}_decision_features_not_excluded")
    return failures


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(count) for key, count in sorted(value.items())}


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
