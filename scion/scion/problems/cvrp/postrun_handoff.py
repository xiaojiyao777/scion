"""CVRP-owned prepared postrun handoff validators."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec
from scion.problems.cvrp.prepared_handoff_protection import (
    cvrp_protected_cases_priority_status,
    cvrp_protected_cases_split_status,
)
from scion.problems.cvrp.prompt_bridge import CVRP_PROMPT_BRIDGE_SPEC
from scion.problems.cvrp.research_guidance import (
    PROTECTED_CASES,
    REQUIRED_MECHANISM_ID,
)


CVRP_UNBOUNDED_LARGE_TWOOPT_DEFAULT_AVOID_TOKEN = (
    "unbounded large-instance two-opt fallback"
)
CVRP_REQUIRED_MEASUREMENT_REASON_CODES = frozenset(
    (
        "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
        "TRAJECTORY_DIVERGENT_LOW_SNR",
    )
)
CVRP_REQUIRED_MEASURABLE_OPPORTUNITY_TOKENS = (
    "construction_seed_portfolio",
    "destroy_repair_selection",
    "bounded_local_search_variant",
    REQUIRED_MECHANISM_ID,
    "acceptance_or_adaptive_weighting",
    "post_repair_effect_credit_weighting",
)
CVRP_REQUIRED_DEFAULT_AVOID_TOKENS = (
    "broad vns removal",
    "pure alns",
    "initial-vns",
    CVRP_UNBOUNDED_LARGE_TWOOPT_DEFAULT_AVOID_TOKEN,
    "cadence-2",
    "share70",
    "route-merge",
    "demand-slack",
    "cross-route 2-opt",
    "cluster-biased",
    "route-limit",
)
CVRP_REQUIRED_RESUME_CONTINUITY_TOKENS = (
    "zero branch cards",
    "target-intent",
    "hypothesis",
    "copied",
)
CVRP_REQUIRED_LARGE_TWOOPT_IMPLEMENTATION_TOKENS = (
    "deadline",
    "wall-clock",
    "route",
    "sweep",
    "unbounded",
    "two_opt_intra",
)
CVRP_REQUIRED_LARGE_TWOOPT_EVIDENCE_TOKENS = (
    "total_distance",
    "case",
    "seed",
    "feasibility",
    "route count",
    "wall-clock",
)
CVRP_REQUIRED_LARGE_TWOOPT_REJECT_TOKENS = (
    "unbounded",
    "two_opt_intra",
    "activation",
    "wall-clock",
)
CVRP_REQUIRED_CASE_PROTECTION_RULE_TOKENS = (
    "cmt2",
    "cmt4",
    "target intent",
    "hypothesis",
    "formal coverage",
    "materially different",
    "do not hardcode",
)
CVRP_REQUIRED_CASE_PROTECTION_EVIDENCE_TOKENS = (
    "target-intent",
    "hypothesis",
    "formal screening",
    "case-level",
    "total_distance",
    "cmt2",
    "cmt4",
)
CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS = (
    "cvrp_large_twoopt_seed_handoff",
    "cvrp_large_twoopt_unbounded_default_avoid_handoff",
    "cvrp_large_twoopt_bounded_constraints_handoff",
    "cvrp_cmt_case_protection_handoff",
    "cvrp_resume_continuity_handoff",
    "cvrp_measurement_mde_handoff",
    "cvrp_low_snr_reason_handoff",
    "cvrp_decision_boundary_handoff",
)

CoverageItemFactory = Callable[[int, str], dict[str, Any]]
AddCheck = Callable[[str, bool, Any], None]


class CvrpPreparedHandoffReviewPort:
    """CVRP-owned prepared-handoff checks and coverage."""

    problem_family = "cvrp"

    def prepared_contract_checks(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_run_root: str = "",
        local_run_root: Path | None = None,
        repo_dir: Path,
        scion_project_dir: Path,
    ) -> dict[str, dict[str, Any]]:
        checks: dict[str, dict[str, Any]] = {}

        def add_check(name: str, passed: bool, detail: Any = "") -> None:
            checks[name] = {"passed": bool(passed), "detail": detail}

        add_cvrp_prepared_handoff_checks(
            manifest,
            add_check,
            manifest_run_root=manifest_run_root,
            local_run_root=local_run_root,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        )
        return checks

    def phase4_requirements(
        self,
        manifest: Mapping[str, Any],
        coverage_item: CoverageItemFactory,
    ) -> dict[str, Any]:
        return cvrp_prepared_handoff_phase4_requirements(
            manifest,
            coverage_item,
        )

    def prepared_prompt_context_signals(
        self,
        manifest: Mapping[str, Any],
        research_focus: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return cvrp_prepared_prompt_context_signals(manifest, research_focus)

    def prompt_bridge_spec(self) -> ProblemPromptBridgeSpec:
        return CVRP_PROMPT_BRIDGE_SPEC


def add_cvrp_prepared_handoff_checks(
    manifest: Mapping[str, Any],
    add_check: AddCheck,
    *,
    manifest_run_root: str = "",
    local_run_root: Path | None = None,
    repo_dir: Path,
    scion_project_dir: Path,
) -> None:
    """Append legacy-compatible CVRP prepared handoff checks."""

    if manifest.get("problem_family") != "cvrp":
        return

    research_focus = manifest.get("research_focus")
    focus_is_dict = isinstance(research_focus, dict)
    measurement = (
        research_focus.get("measurement_opportunity_diagnostics")
        if focus_is_dict
        else None
    )
    measurement_is_dict = isinstance(measurement, dict)
    add_check(
        "cvrp_measurement_handoff_present",
        focus_is_dict and measurement_is_dict,
        "research_focus.measurement_opportunity_diagnostics",
    )

    if not isinstance(measurement, dict):
        measurement = {}
    add_check(
        "cvrp_measurement_handoff_report_only",
        measurement.get("proposal_visibility_only") is True
        and measurement.get("decision_features_excluded") is True,
        {
            "proposal_visibility_only": measurement.get("proposal_visibility_only"),
            "decision_features_excluded": measurement.get(
                "decision_features_excluded"
            ),
        },
    )
    add_check(
        "cvrp_measurement_handoff_mde_present",
        _positive_number(measurement.get("screening_mde_at_power_80"))
        and _positive_number(measurement.get("practical_screen_delta")),
        {
            "screening_mde_at_power_80": measurement.get(
                "screening_mde_at_power_80"
            ),
            "practical_screen_delta": measurement.get("practical_screen_delta"),
        },
    )
    readiness = _mapping_or_empty(measurement.get("measurement_readiness"))
    calibration = _mapping_or_empty(measurement.get("calibration"))
    source = str(measurement.get("source") or "")
    add_check(
        "cvrp_measurement_handoff_problem_owned_source",
        source == "problem_v1.measurement.calibration_ref"
        and readiness.get("status") == "ready"
        and readiness.get("reason_code") == "ok"
        and calibration.get("schema") == "scion.aa_noise_floor.v1"
        and calibration.get("decision_features_excluded") is True,
        {
            "source": source,
            "measurement_readiness_status": readiness.get("status"),
            "measurement_readiness_reason_code": readiness.get("reason_code"),
            "calibration_schema": calibration.get("schema"),
            "calibration_ref": calibration.get("ref"),
            "calibration_decision_features_excluded": calibration.get(
                "decision_features_excluded"
            ),
        },
    )

    reason_codes = set(_string_items(measurement.get("reason_codes")))
    missing_reason_codes = sorted(
        CVRP_REQUIRED_MEASUREMENT_REASON_CODES - reason_codes
    )
    add_check(
        "cvrp_measurement_handoff_reason_codes",
        not missing_reason_codes,
        {
            "required": sorted(CVRP_REQUIRED_MEASUREMENT_REASON_CODES),
            "missing": missing_reason_codes,
        },
    )

    opportunity_classes = (
        research_focus.get("measurable_opportunity_classes")
        if focus_is_dict
        else None
    )
    opportunity_items = _string_items(opportunity_classes)
    opportunity_text = "\n".join(opportunity_items)
    missing_opportunity_tokens = [
        token
        for token in CVRP_REQUIRED_MEASURABLE_OPPORTUNITY_TOKENS
        if token not in opportunity_text
    ]
    add_check(
        "cvrp_measurable_opportunity_classes_present",
        len(opportunity_items) >= len(CVRP_REQUIRED_MEASURABLE_OPPORTUNITY_TOKENS)
        and not missing_opportunity_tokens,
        {
            "count": len(opportunity_items),
            "missing": missing_opportunity_tokens,
        },
    )

    focus = research_focus if focus_is_dict else {}
    default_avoid_items = _string_items(focus.get("default_avoid_directions"))
    default_avoid_text = "\n".join(default_avoid_items).lower()
    missing_avoid_tokens = [
        token
        for token in CVRP_REQUIRED_DEFAULT_AVOID_TOKENS
        if token not in default_avoid_text
    ]
    add_check(
        "cvrp_default_avoid_directions_present",
        not missing_avoid_tokens,
        {
            "count": len(default_avoid_items),
            "missing": missing_avoid_tokens,
        },
    )

    route_rule = str(focus.get("route_merge_exception_rule") or "").lower()
    construction_rule = str(focus.get("construction_seed_rule") or "").lower()
    missing_primary_rule = str(
        focus.get("missing_primary_telemetry_rule") or ""
    ).lower()
    add_check(
        "cvrp_direct_effect_rules_present",
        (
            "direct" in route_rule
            and "objective" in route_rule
            and "same-run seed baseline" in construction_rule
            and "same-mechanism" in construction_rule
        ),
        {
            "route_merge_exception_rule": focus.get("route_merge_exception_rule"),
            "construction_seed_rule": focus.get("construction_seed_rule"),
        },
    )
    add_check(
        "cvrp_missing_primary_telemetry_rule_present",
        (
            "missing" in missing_primary_rule
            and "primary mechanism" in missing_primary_rule
            and "not_evaluated/not_triggered" in missing_primary_rule
            and "weak_positive" in missing_primary_rule
            and REQUIRED_MECHANISM_ID in missing_primary_rule
        ),
        {
            "missing_primary_telemetry_rule": focus.get(
                "missing_primary_telemetry_rule"
            ),
        },
    )
    case_protection = _mapping_or_empty(focus.get("case_protection_requirements"))
    case_protection_status = cvrp_case_protection_status(case_protection)
    add_check(
        "cvrp_cmt_case_protection_present",
        case_protection_status["complete"],
        case_protection_status,
    )
    resume_continuity = _mapping_or_empty(
        focus.get("resume_continuity_requirements")
    )
    resume_continuity_status = cvrp_resume_continuity_status(resume_continuity)
    add_check(
        "cvrp_resume_continuity_present",
        resume_continuity_status["complete"],
        resume_continuity_status,
    )
    split_status = cvrp_protected_cases_split_status(
        _mapping_or_empty(manifest.get("config")),
        case_protection,
        manifest_run_root=manifest_run_root,
        local_run_root=local_run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
    )
    add_check(
        "cvrp_protected_cases_in_split",
        split_status["complete"],
        split_status,
    )
    priority_status = cvrp_protected_cases_priority_status(
        _mapping_or_empty(manifest.get("config")),
        case_protection,
        manifest_run_root=manifest_run_root,
        local_run_root=local_run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
    )
    add_check(
        "cvrp_protected_cases_in_priority_selection",
        priority_status["complete"],
        priority_status,
    )
    large_twoopt = _mapping_or_empty(
        focus.get("large_instance_two_opt_constraints")
    )
    large_twoopt_status = cvrp_large_twoopt_constraint_status(large_twoopt)
    add_check(
        "cvrp_large_twoopt_bounded_constraints_present",
        large_twoopt_status["complete"],
        large_twoopt_status,
    )
    boundary = str(focus.get("decision_boundary") or "").lower()
    add_check(
        "cvrp_handoff_decision_boundary_present",
        (
            "decisionfeatures" in boundary
            and "protocol" in boundary
            and "promotion" in boundary
            and "scheduler" in boundary
        ),
        focus.get("decision_boundary"),
    )


def cvrp_prepared_handoff_phase4_requirements(
    manifest: Mapping[str, Any],
    coverage_item: CoverageItemFactory,
) -> dict[str, Any]:
    """Return legacy Phase 4 CVRP handoff coverage payloads."""

    focus = _mapping_or_empty(manifest.get("research_focus"))
    measurement = _mapping_or_empty(focus.get("measurement_opportunity_diagnostics"))
    reason_codes = set(_string_items(measurement.get("reason_codes")))
    opportunity_text = "\n".join(
        _string_items(focus.get("measurable_opportunity_classes"))
    ).lower()
    avoid_text = "\n".join(_string_items(focus.get("default_avoid_directions"))).lower()
    route_rule = str(focus.get("route_merge_exception_rule") or "").lower()
    construction_rule = str(focus.get("construction_seed_rule") or "").lower()
    missing_primary_rule = str(
        focus.get("missing_primary_telemetry_rule") or ""
    ).lower()
    boundary = str(focus.get("decision_boundary") or "").lower()
    case_protection_status = cvrp_case_protection_status(
        _mapping_or_empty(focus.get("case_protection_requirements"))
    )
    resume_continuity_status = cvrp_resume_continuity_status(
        _mapping_or_empty(focus.get("resume_continuity_requirements"))
    )
    large_twoopt_status = cvrp_large_twoopt_constraint_status(
        _mapping_or_empty(focus.get("large_instance_two_opt_constraints"))
    )

    return {
        "cvrp_measurement_mde_handoff": coverage_item(
            int(
                _positive_number(measurement.get("screening_mde_at_power_80"))
                and _positive_number(measurement.get("practical_screen_delta"))
                and measurement.get("source")
                == "problem_v1.measurement.calibration_ref"
            ),
            "prepared_run_manifest cvrp measurement_opportunity_diagnostics problem-owned MDE/practical delta",
        ),
        "cvrp_low_snr_reason_handoff": coverage_item(
            int(not (CVRP_REQUIRED_MEASUREMENT_REASON_CODES - reason_codes)),
            "prepared_run_manifest cvrp measurement_opportunity_diagnostics reason_codes",
        ),
        "cvrp_measurable_opportunity_handoff": coverage_item(
            int(
                all(
                    token.lower() in opportunity_text
                    for token in CVRP_REQUIRED_MEASURABLE_OPPORTUNITY_TOKENS
                )
            ),
            "prepared_run_manifest cvrp research_focus measurable_opportunity_classes",
        ),
        "cvrp_default_avoid_handoff": coverage_item(
            int(
                all(
                    token.lower() in avoid_text
                    for token in CVRP_REQUIRED_DEFAULT_AVOID_TOKENS
                )
            ),
            "prepared_run_manifest cvrp research_focus default_avoid_directions",
        ),
        "cvrp_large_twoopt_seed_handoff": coverage_item(
            int(REQUIRED_MECHANISM_ID in opportunity_text),
            "prepared_run_manifest cvrp research_focus measurable_opportunity_classes large-instance two-opt seed",
        ),
        "cvrp_large_twoopt_unbounded_default_avoid_handoff": coverage_item(
            int(CVRP_UNBOUNDED_LARGE_TWOOPT_DEFAULT_AVOID_TOKEN in avoid_text),
            "prepared_run_manifest cvrp research_focus default_avoid_directions unbounded large-instance two-opt fallback",
        ),
        "cvrp_large_twoopt_bounded_constraints_handoff": coverage_item(
            int(large_twoopt_status["complete"]),
            "prepared_run_manifest cvrp research_focus large_instance_two_opt_constraints",
        ),
        "cvrp_direct_effect_rules_handoff": coverage_item(
            int(
                "direct" in route_rule
                and "objective" in route_rule
                and "same-run seed baseline" in construction_rule
                and "same-mechanism" in construction_rule
            ),
            "prepared_run_manifest cvrp research_focus route/construction direct-effect rules",
        ),
        "cvrp_missing_primary_telemetry_handoff": coverage_item(
            int(
                "missing" in missing_primary_rule
                and "primary mechanism" in missing_primary_rule
                and "not_evaluated/not_triggered" in missing_primary_rule
                and "weak_positive" in missing_primary_rule
                and REQUIRED_MECHANISM_ID in missing_primary_rule
            ),
            "prepared_run_manifest cvrp research_focus missing_primary_telemetry_rule",
        ),
        "cvrp_cmt_case_protection_handoff": coverage_item(
            int(case_protection_status["complete"]),
            "prepared_run_manifest cvrp research_focus case_protection_requirements",
        ),
        "cvrp_resume_continuity_handoff": coverage_item(
            int(resume_continuity_status["complete"]),
            "prepared_run_manifest cvrp research_focus resume_continuity_requirements",
        ),
        "cvrp_decision_boundary_handoff": coverage_item(
            int(
                "decisionfeatures" in boundary
                and "protocol" in boundary
                and "promotion" in boundary
                and "scheduler" in boundary
            ),
            "prepared_run_manifest cvrp research_focus decision_boundary",
        ),
    }


def cvrp_prepared_prompt_context_signals(
    manifest: Mapping[str, Any],
    research_focus: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build CVRP-owned prepared prompt/context readiness signals."""

    if manifest.get("problem_family") != "cvrp":
        return {}

    signals: dict[str, dict[str, Any]] = {}
    measurement = _mapping_or_empty(
        research_focus.get("measurement_opportunity_diagnostics")
    )
    screening_headroom = _mapping_or_empty(measurement.get("screening_headroom"))
    mechanism_rank_count = _sequence_count(
        measurement.get("mechanism_effect_ranking")
    )
    opportunity_diagnostic_count = _sequence_count(
        measurement.get("opportunity_diagnostics")
    )
    measurable_opportunity_count = _sequence_count(
        measurement.get("measurable_opportunity_classes")
    )
    signals["cvrp_measurement_opportunity_handoff"] = _signal(
        available=(
            bool(measurement)
            and measurement.get("proposal_visibility_only") is True
            and measurement.get("decision_features_excluded") is True
            and bool(screening_headroom)
            and measurable_opportunity_count > 0
            and mechanism_rank_count > 0
            and opportunity_diagnostic_count > 0
        ),
        required=True,
        source="prepared_run_manifest.research_focus.measurement_opportunity_diagnostics",
        detail={
            "schema_version": measurement.get("schema_version"),
            "opportunity_projection_source": measurement.get(
                "opportunity_projection_source"
            ),
            "screening_headroom_present": bool(screening_headroom),
            "measurable_opportunity_count": measurable_opportunity_count,
            "mechanism_rank_count": mechanism_rank_count,
            "opportunity_diagnostic_count": opportunity_diagnostic_count,
            "reason_code_count": len(_string_items(measurement.get("reason_codes"))),
        },
    )
    opportunity_items = _string_items(
        research_focus.get("measurable_opportunity_classes")
    )
    avoid_items = _string_items(research_focus.get("default_avoid_directions"))
    signals["cvrp_measurable_opportunity_classes"] = _signal(
        available=bool(opportunity_items),
        required=True,
        source="prepared_run_manifest.research_focus.measurable_opportunity_classes",
        detail={"count": len(opportunity_items)},
    )
    signals["cvrp_default_avoid_directions"] = _signal(
        available=bool(avoid_items),
        required=True,
        source="prepared_run_manifest.research_focus.default_avoid_directions",
        detail={"count": len(avoid_items)},
    )
    direct_rules_present = bool(
        research_focus.get("route_merge_exception_rule")
        and research_focus.get("construction_seed_rule")
    )
    signals["cvrp_direct_effect_rules"] = _signal(
        available=direct_rules_present,
        required=True,
        source=(
            "prepared_run_manifest.research_focus.route_merge_exception_rule "
            "and construction_seed_rule"
        ),
        detail={
            "route_merge_exception_rule_present": bool(
                research_focus.get("route_merge_exception_rule")
            ),
            "construction_seed_rule_present": bool(
                research_focus.get("construction_seed_rule")
            ),
        },
    )
    missing_primary_rule = str(
        research_focus.get("missing_primary_telemetry_rule") or ""
    ).lower()
    signals["cvrp_missing_primary_telemetry_rule"] = _signal(
        available=(
            "missing" in missing_primary_rule
            and "primary mechanism" in missing_primary_rule
            and "not_evaluated/not_triggered" in missing_primary_rule
            and "weak_positive" in missing_primary_rule
            and REQUIRED_MECHANISM_ID in missing_primary_rule
        ),
        required=True,
        source="prepared_run_manifest.research_focus.missing_primary_telemetry_rule",
        detail={
            "missing_primary_telemetry_rule_present": bool(
                research_focus.get("missing_primary_telemetry_rule")
            ),
        },
    )
    large_twoopt = _mapping_or_empty(
        research_focus.get("large_instance_two_opt_constraints")
    )
    implementation_items = _string_items(
        large_twoopt.get("implementation_constraints")
    )
    evidence_items = _string_items(large_twoopt.get("required_pair_evidence"))
    reject_items = _string_items(large_twoopt.get("default_reject_directions"))
    signals["cvrp_large_twoopt_bounded_constraints"] = _signal(
        available=(
            bool(large_twoopt)
            and bool(implementation_items)
            and bool(evidence_items)
            and bool(reject_items)
            and large_twoopt.get("proposal_visibility_only") is True
            and large_twoopt.get("decision_features_excluded") is True
        ),
        required=True,
        source="prepared_run_manifest.research_focus.large_instance_two_opt_constraints",
        detail={
            "schema_version": large_twoopt.get("schema_version"),
            "seed_report": large_twoopt.get("seed_report"),
            "implementation_constraint_count": len(implementation_items),
            "required_pair_evidence_count": len(evidence_items),
            "default_reject_direction_count": len(reject_items),
        },
    )
    case_protection = _mapping_or_empty(
        research_focus.get("case_protection_requirements")
    )
    protected_cases = _string_items(case_protection.get("protected_cases"))
    case_rules = _string_items(case_protection.get("rules"))
    case_evidence = _string_items(case_protection.get("required_evidence"))
    signals["cvrp_case_protection_requirements"] = _signal(
        available=(
            bool(case_protection)
            and bool(protected_cases)
            and bool(case_rules)
            and bool(case_evidence)
            and case_protection.get("proposal_visibility_only") is True
            and case_protection.get("decision_features_excluded") is True
        ),
        required=True,
        source="prepared_run_manifest.research_focus.case_protection_requirements",
        detail={
            "schema_version": case_protection.get("schema_version"),
            "protected_cases": protected_cases,
            "rule_count": len(case_rules),
            "required_evidence_count": len(case_evidence),
        },
    )
    resume_continuity = _mapping_or_empty(
        research_focus.get("resume_continuity_requirements")
    )
    fallback_sources = _string_items(resume_continuity.get("fallback_sources"))
    continuity_rules = _string_items(resume_continuity.get("rules"))
    continuity_evidence = _string_items(resume_continuity.get("required_evidence"))
    signals["cvrp_resume_continuity_requirements"] = _signal(
        available=(
            bool(resume_continuity)
            and bool(fallback_sources)
            and bool(continuity_rules)
            and bool(continuity_evidence)
            and resume_continuity.get("proposal_visibility_only") is True
            and resume_continuity.get("decision_features_excluded") is True
        ),
        required=True,
        source="prepared_run_manifest.research_focus.resume_continuity_requirements",
        detail={
            "schema_version": resume_continuity.get("schema_version"),
            "fallback_source_count": len(fallback_sources),
            "rule_count": len(continuity_rules),
            "required_evidence_count": len(continuity_evidence),
        },
    )
    return signals


def cvrp_case_protection_status(
    requirements: Mapping[str, Any],
) -> dict[str, Any]:
    protected_cases = _string_items(requirements.get("protected_cases"))
    protected_case_upper = {item.upper() for item in protected_cases}
    rules_items = _string_items(requirements.get("rules"))
    evidence_items = _string_items(requirements.get("required_evidence"))
    rules_text = "\n".join(rules_items).lower()
    evidence_text = "\n".join(evidence_items).lower()
    missing_cases = [
        case
        for case in PROTECTED_CASES
        if case.upper() not in protected_case_upper
    ]
    missing_rule_tokens = [
        token
        for token in CVRP_REQUIRED_CASE_PROTECTION_RULE_TOKENS
        if token.lower() not in rules_text
    ]
    missing_evidence_tokens = [
        token
        for token in CVRP_REQUIRED_CASE_PROTECTION_EVIDENCE_TOKENS
        if token.lower() not in evidence_text
    ]
    complete = (
        bool(requirements)
        and requirements.get("proposal_visibility_only") is True
        and requirements.get("decision_features_excluded") is True
        and not missing_cases
        and not missing_rule_tokens
        and not missing_evidence_tokens
    )
    return {
        "complete": complete,
        "schema_version": requirements.get("schema_version"),
        "proposal_visibility_only": requirements.get("proposal_visibility_only"),
        "decision_features_excluded": requirements.get(
            "decision_features_excluded"
        ),
        "protected_cases": protected_cases,
        "rule_count": len(rules_items),
        "required_evidence_count": len(evidence_items),
        "missing_cases": missing_cases,
        "missing_rule_tokens": missing_rule_tokens,
        "missing_evidence_tokens": missing_evidence_tokens,
    }


def cvrp_resume_continuity_status(
    requirements: Mapping[str, Any],
) -> dict[str, Any]:
    fallback_sources = _string_items(requirements.get("fallback_sources"))
    rule_items = _string_items(requirements.get("rules"))
    evidence_items = _string_items(requirements.get("required_evidence"))
    joined_text = "\n".join([*fallback_sources, *rule_items, *evidence_items]).lower()
    missing_tokens = [
        token
        for token in CVRP_REQUIRED_RESUME_CONTINUITY_TOKENS
        if token.lower() not in joined_text
    ]
    complete = (
        bool(requirements)
        and requirements.get("proposal_visibility_only") is True
        and requirements.get("decision_features_excluded") is True
        and bool(fallback_sources)
        and bool(rule_items)
        and bool(evidence_items)
        and not missing_tokens
    )
    return {
        "complete": complete,
        "schema_version": requirements.get("schema_version"),
        "proposal_visibility_only": requirements.get("proposal_visibility_only"),
        "decision_features_excluded": requirements.get(
            "decision_features_excluded"
        ),
        "fallback_source_count": len(fallback_sources),
        "rule_count": len(rule_items),
        "required_evidence_count": len(evidence_items),
        "missing_tokens": missing_tokens,
    }


def cvrp_large_twoopt_constraint_status(
    constraints: Mapping[str, Any],
) -> dict[str, Any]:
    implementation_items = _string_items(constraints.get("implementation_constraints"))
    evidence_items = _string_items(constraints.get("required_pair_evidence"))
    reject_items = _string_items(constraints.get("default_reject_directions"))
    implementation_text = "\n".join(implementation_items).lower()
    evidence_text = "\n".join(evidence_items).lower()
    reject_text = "\n".join(reject_items).lower()
    missing_implementation = [
        token
        for token in CVRP_REQUIRED_LARGE_TWOOPT_IMPLEMENTATION_TOKENS
        if token.lower() not in implementation_text
    ]
    missing_evidence = [
        token
        for token in CVRP_REQUIRED_LARGE_TWOOPT_EVIDENCE_TOKENS
        if token.lower() not in evidence_text
    ]
    missing_reject = [
        token
        for token in CVRP_REQUIRED_LARGE_TWOOPT_REJECT_TOKENS
        if token.lower() not in reject_text
    ]
    complete = (
        bool(constraints)
        and constraints.get("proposal_visibility_only") is True
        and constraints.get("decision_features_excluded") is True
        and bool(str(constraints.get("seed_report") or "").strip())
        and not missing_implementation
        and not missing_evidence
        and not missing_reject
    )
    return {
        "complete": complete,
        "schema_version": constraints.get("schema_version"),
        "seed_report": constraints.get("seed_report"),
        "proposal_visibility_only": constraints.get("proposal_visibility_only"),
        "decision_features_excluded": constraints.get(
            "decision_features_excluded"
        ),
        "implementation_constraint_count": len(implementation_items),
        "required_evidence_count": len(evidence_items),
        "default_reject_count": len(reject_items),
        "missing_implementation_tokens": missing_implementation,
        "missing_evidence_tokens": missing_evidence,
        "missing_reject_tokens": missing_reject,
    }


def _positive_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (float, int)) and value > 0


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _signal(
    *,
    available: bool,
    required: bool,
    source: Any,
    detail: Any,
) -> dict[str, Any]:
    return {
        "available": bool(available),
        "required": bool(required),
        "source": source,
        "detail": detail,
        "runtime_generated_after_launch": False,
    }
