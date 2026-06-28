"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solution_checks import (
    _as_solution,
    _extract_reported_objective,
    _normalize_route,
    check_feasibility as _check_feasibility,
    check_solution_consistency as _check_solution_consistency,
    deserialize_solver_output as _deserialize_solver_output,
    recompute_objective as _recompute_objective,
)
from scion.problems.cvrp.surface_schema import (
    _POLICY_PREVIEW_EXEC_TIMEOUT_SEC,
    _POLICY_PREVIEW_TIME_LIMIT_SEC,
)
from scion.problems.cvrp.surface_rendering import (
    render_operator_interface as _render_operator_interface,
    render_problem_object as _render_problem_object,
    render_problem_summary as _render_problem_summary,
    render_research_surface_interface as _render_research_surface_interface,
    render_solver_mechanics as _render_solver_mechanics,
)
from scion.problems.cvrp.preview import common as _preview_common
from scion.problems.cvrp.preview import synthetic as _preview_synthetic
from scion.problems.cvrp.preview.dispatch import (
    preview_research_surface_patch as _preview_research_surface_patch,
)
from scion.problems.cvrp.research_guidance import (
    CASE_PROTECTION_REQUIREMENTS,
    LARGE_INSTANCE_TWO_OPT_CONSTRAINTS,
    NEXT_REQUIRED_DIRECTION,
    PROTECTED_CASES,
    REQUIRED_MECHANISM_ID,
    SUCCESSOR_OPPORTUNITY_FAMILIES,
)
from scion.problems.cvrp.surface_policy import (
    ACTIVE_RESEARCH_SURFACE_NAMES,
    LEGACY_RESEARCH_SURFACE_NAMES,
    active_research_surfaces as _active_research_surfaces,
    is_active_research_surface as _is_active_research_surface,
    is_legacy_research_surface as _is_legacy_research_surface,
)


class CvrpAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def mechanism_novelty_provider(self) -> Any:
        from scion.problems.cvrp.mechanism_novelty import (
            CvrpMechanismNoveltyProvider,
        )

        return CvrpMechanismNoveltyProvider()

    def contract_check_provider(self) -> Any:
        from scion.problems.cvrp.contract_checks import CvrpContractCheckProvider

        return CvrpContractCheckProvider()

    def active_subject_policy_provider(self) -> Any:
        from scion.problems.cvrp.contract_checks import CvrpContractCheckProvider

        return CvrpContractCheckProvider()

    def solver_design_prompt_provider(self) -> Any:
        from scion.problems.cvrp.solver_design_provider import (
            CvrpSolverDesignProvider,
        )

        return CvrpSolverDesignProvider()

    def active_solver_design_provider(self) -> Any:
        from scion.problems.cvrp.active_solver_facts import (
            CvrpActiveSolverDesignProvider,
        )

        return CvrpActiveSolverDesignProvider()

    def active_solver_map_provider(self) -> Any:
        from scion.problems.cvrp.active_solver_map_provider import (
            CvrpActiveSolverMapProvider,
        )

        return CvrpActiveSolverMapProvider()

    def solver_design_smoke_provider(self) -> Any:
        from scion.problems.cvrp.solver_design_provider import (
            CvrpSolverDesignProvider,
        )

        return CvrpSolverDesignProvider()

    def active_research_surface_names(self) -> tuple[str, ...]:
        return ACTIVE_RESEARCH_SURFACE_NAMES

    def legacy_research_surface_names(self) -> tuple[str, ...]:
        return LEGACY_RESEARCH_SURFACE_NAMES

    def is_active_research_surface(self, surface_name: str) -> bool:
        return _is_active_research_surface(surface_name)

    def is_legacy_research_surface(self, surface_name: str) -> bool:
        return _is_legacy_research_surface(surface_name)

    def active_research_surfaces(self) -> tuple[Any, ...]:
        return _active_research_surfaces(self._spec.research_surfaces or [])

    def stagnation_object_model_markers(self) -> tuple[str, ...]:
        return (
            "_solution",
            "_route",
            "from_public",
            "from_cvrp_solution",
            "from_routes",
            "to_public",
            "cannot be coerced to cvrpsolution",
            "solver_algorithm_errors=",
            "object model",
        )

    def render_problem_summary(self) -> str:
        return _render_problem_summary()

    def render_problem_object(self) -> str:
        return _render_problem_object()

    def render_solver_mechanics(self) -> str:
        return _render_solver_mechanics()

    def render_research_surface_interface(self, surface_name: str) -> str:
        return _render_research_surface_interface(surface_name)

    def render_operator_interface(self) -> str:
        return _render_operator_interface()

    def render_problem_measurement_diagnostics(self) -> Mapping[str, Any]:
        """Return CVRP proposal-only measurement and opportunity diagnostics."""

        return {
            "schema_version": "cvrp_measurement_opportunity_diagnostic.v1",
            "taint": "problem_owned_proposal_diagnostic",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "measurement_context": {
                "runtime_model": "budget_exhausting",
                "pairing_validity": "trajectory_divergent",
                "metric": "total_distance",
                "practical_screen_delta": 2.0,
                "practical_validate_delta": 1.0,
                "screening_mde_at_power_80": 9.9,
                "recommended_min_seeds": 8,
                "false_pass_rate_at_current_gate": 0.0,
                "interpretation": (
                    "Current formal screening is low-power for small raw "
                    "total_distance deltas; sub-MDE effects need direct "
                    "objective-effect attribution or same-mechanism follow-up."
                ),
            },
            "screening_headroom": {
                "scope": "formal_screening_aggregate",
                "metric": "distance_gap_pct_to_reference",
                "case_count": 16,
                "gap_pct_min": 2.5,
                "gap_pct_max": 10.0,
                "case_count_gap_pct_at_least_3": 12,
                "case_details_omitted": True,
                "planning_use": (
                    "There is aggregate screening headroom, but proposals "
                    "should target mechanisms with direct per-case objective "
                    "effect evidence instead of relying on aggregate win rate."
                ),
            },
            "default_avoid_directions": [
                "broad_vns_removal",
                "pure_alns_no_polish",
                "simple_initial_vns_disablement",
                "raw_cadence_2",
                "recent_best_or_stall_gating",
                "fixed_early_8",
                "tested_share70_cap_or_rescue_variants",
                "unchanged_route_merge_absorption",
                "unchanged_demand_slack_regret_insertion",
                "unchanged_cross_route_2opt_reconnect",
                "unchanged_cluster_biased_worst_removal",
                "unchanged_route_limit_seed_diversification",
            ],
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "construction_seed_portfolio",
                    "required_evidence": (
                        "same-run seed baseline or same-mechanism accepted "
                        "delta showing objective-changing seed effect"
                    ),
                },
                {
                    "mechanism_family": "destroy_repair_selection",
                    "required_evidence": (
                        "per-case total_distance delta tied to the changed "
                        "repair or removal choice"
                    ),
                },
                {
                    "mechanism_family": "bounded_local_search_variant",
                    "required_evidence": (
                        "feasible route-level objective deltas with bounded "
                        "search effort, not only activation counts"
                    ),
                },
                {
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "required_evidence": (
                        "deadline-aware bounded intra-route two-opt on large "
                        "cases with pair-level total_distance, feasibility, "
                        "route-count, and wall-clock evidence; unbounded "
                        "fallback is not accepted"
                    ),
                    "seed_report": (
                        "scion/docs/experiments/v0.4/"
                        "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
                    ),
                },
                {
                    "mechanism_family": "acceptance_or_adaptive_weighting",
                    "required_evidence": (
                        "direct move acceptance and downstream objective "
                        "effect telemetry under the formal budget"
                    ),
                },
            ],
            "top_opportunity_recipe": {
                "schema_version": "scion.cvrp_opportunity_recipe.v1",
                "proposal_visibility_only": True,
                "decision_features_excluded": True,
                "mechanism_family": REQUIRED_MECHANISM_ID,
                "review_status": "reviewed_no_positive_at_mde",
                "successor_opportunity_families": list(SUCCESSOR_OPPORTUNITY_FAMILIES),
                "target_surface": "solver_design",
                "target_files": ["policies/baseline_modules/local_search.py"],
                "next_required_direction": NEXT_REQUIRED_DIRECTION,
                "required_observations": list(
                    LARGE_INSTANCE_TWO_OPT_CONSTRAINTS["required_pair_evidence"]
                ),
                "implementation_constraints": list(
                    LARGE_INSTANCE_TWO_OPT_CONSTRAINTS[
                        "implementation_constraints"
                    ]
                ),
                "protected_cases": list(PROTECTED_CASES),
                "protected_case_required_evidence": list(
                    CASE_PROTECTION_REQUIREMENTS["required_evidence"]
                ),
                "default_reject_directions": list(
                    LARGE_INSTANCE_TWO_OPT_CONSTRAINTS[
                        "default_reject_directions"
                    ]
                ),
            },
            "mechanism_effect_ranking": [
                {
                    "rank": 1,
                    "mechanism_family": "bounded_local_search_variant",
                    "evidence_status": "successor_required_after_reviewed_no_effect",
                    "opportunity_status": "highest_current_successor",
                    "effect_status": "unknown_current_effect",
                    "summary": (
                        "The large-instance intra-route two-opt checklist is "
                        "now complete but measured no positive-at-MDE effect. "
                        "Prefer a bounded local-search successor only if it "
                        "changes a materially different causal path and "
                        "reports direct route-level objective deltas."
                    ),
                    "recommended_action": (
                        "Do not repeat the reviewed seed path; declare the "
                        "bounded trigger, runtime guard, and direct effect "
                        "field for a different local-search mechanism."
                    ),
                    "reason_codes": [
                        "CVRP_LARGE_TWOOPT_REVIEWED_NO_POSITIVE_AT_MDE",
                        "SUCCESSOR_CAUSAL_PATH_REQUIRED",
                    ],
                },
                {
                    "rank": 2,
                    "mechanism_family": "destroy_repair_selection",
                    "evidence_status": "successor_required_after_reviewed_no_effect",
                    "opportunity_status": "eligible_if_materially_different",
                    "effect_status": "unknown_current_effect",
                    "summary": (
                        "Destroy/repair selection is the next plausible "
                        "successor family only when it changes a material "
                        "removal or repair choice and reports per-case "
                        "objective attribution."
                    ),
                    "recommended_action": (
                        "Avoid unchanged demand-slack, route-merge, or "
                        "cluster-biased variants; name the new causal path and "
                        "direct total_distance evidence before screening."
                    ),
                    "reason_codes": [
                        "MATERIAL_DIFFERENCE_REQUIRED",
                        "DIRECT_OBJECTIVE_EFFECT_REQUIRED",
                    ],
                },
                {
                    "rank": 3,
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "evidence_status": "checklist_complete_no_positive_at_mde",
                    "opportunity_status": "reviewed_not_next_required",
                    "effect_status": "measured_no_positive_at_mde",
                    "summary": (
                        "External-control replay seeded this family and the "
                        "current-run checklist is complete, including "
                        "CMT2/CMT4 protection, but the postrun outcome still "
                        "has no positive row at or above MDE."
                    ),
                    "recommended_action": (
                        "Treat additional same-seed refinements as default "
                        "avoid unless a new causal path invalidates the "
                        "reviewed no-effect conclusion."
                    ),
                    "reason_codes": [
                        "CVRP_LARGE_TWOOPT_REVIEWED_NO_POSITIVE_AT_MDE",
                        "ROTATE_TO_SUCCESSOR_OPPORTUNITY",
                    ],
                },
                {
                    "rank": 4,
                    "mechanism_family": "construction_seed_portfolio",
                    "evidence_status": "requires_same_run_seed_baseline",
                    "opportunity_status": "lower_until_seed_effect_is_isolated",
                    "effect_status": "activation_not_objective_effect",
                    "summary": (
                        "Seed or portfolio expansion has not been useful when "
                        "it only increases activation or fallback diversity."
                    ),
                    "recommended_action": (
                        "Use only with a same-run seed baseline or accepted "
                        "same-mechanism delta showing objective-changing seed "
                        "effect."
                    ),
                    "reason_codes": [
                        "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT",
                        "ACTIVATION_IS_NOT_OBJECTIVE_EFFECT",
                    ],
                },
            ],
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "measurement_power",
                    "surface": "solver_design",
                    "mechanism_family": "all",
                    "metric": "total_distance",
                    "summary": (
                        "CVRP formal screening MDE is about 9.9 raw "
                        "total_distance while the practical screen delta is "
                        "2.0, so small deltas are low-SNR."
                    ),
                    "recommended_action": (
                        "Prefer mechanisms with direct per-case objective "
                        "effect evidence or same-mechanism follow-up; do not "
                        "tune gates around win-rate alone."
                    ),
                    "confidence": "high",
                    "reason_codes": [
                        "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                        "TRAJECTORY_DIVERGENT_LOW_SNR",
                    ],
                },
                {
                    "diagnostic_type": "residual_opportunity",
                    "surface": "solver_design",
                    "mechanism_family": "construction_destroy_repair_local_search",
                    "metric": "total_distance",
                    "summary": (
                        "Formal screening cases retain aggregate reference-gap "
                        "headroom, but previous unchanged route-merge, "
                        "demand-slack, cross-route 2-opt, cluster-biased "
                        "removal, and route-limit seed variants did not show "
                        "accepted objective effect."
                    ),
                    "recommended_action": (
                        "Target a materially different causal path or provide "
                        "direct seed/objective-effect attribution before "
                        "revisiting those families."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "CVRP_AGGREGATE_HEADROOM_REMAINS",
                        "DEFAULT_AVOID_PRIOR_WEAK_OR_NEGATIVE",
                    ],
                },
                {
                    "diagnostic_type": "focused_mechanism_seed",
                    "surface": "solver_design",
                    "mechanism_family": "large_instance_intra_route_two_opt_seed",
                    "metric": "total_distance",
                    "summary": (
                        "External-control replay found 8/8 feasible XL wins "
                        "for an intra-route two-opt seed in "
                        "scion/docs/experiments/v0.4/"
                        "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md, "
                        "but only a deadline-aware bounded implementation is in scope."
                    ),
                    "recommended_action": (
                        "If pursuing this seed, derive the local-search "
                        "deadline from the solver time limit, poll remaining "
                        "wall-clock budget before route, sweep, and "
                        "improvement work, and report pair-level objective, "
                        "feasibility, route-count, and wall-clock evidence."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "CVRP_LARGE_INSTANCE_TWO_OPT_SEED",
                        "BOUNDED_DEADLINE_REQUIRED",
                        "UNBOUNDED_TWO_OPT_DEFAULT_REJECT",
                    ],
                },
                {
                    "diagnostic_type": "construction_seed_effect",
                    "surface": "solver_design",
                    "mechanism_family": "construction_seed_portfolio",
                    "metric": "total_distance",
                    "summary": (
                        "Construction seed or portfolio changes are not useful "
                        "unless they show objective-changing seed effect, not "
                        "only fallback activation or larger seed pools."
                    ),
                    "recommended_action": (
                        "Include a same-run seed baseline or accepted "
                        "same-mechanism delta before claiming construction "
                        "seed improvement."
                    ),
                    "confidence": "high",
                    "reason_codes": [
                        "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT",
                        "ACTIVATION_IS_NOT_OBJECTIVE_EFFECT",
                    ],
                },
                {
                    "diagnostic_type": "runtime_semantics",
                    "surface": "solver_design",
                    "mechanism_family": "all",
                    "metric": "elapsed_ms",
                    "summary": (
                        "Budget saturation is expected for this anytime "
                        "ALNS/VNS solver and should be read as budget "
                        "compliance context, not as solver-quality evidence."
                    ),
                    "recommended_action": (
                        "Focus proposal claims on quality-preserving objective "
                        "effects or explicit runtime-improvement evidence that "
                        "does not depend on saturation noise."
                    ),
                    "confidence": "high",
                    "reason_codes": [
                        "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY",
                        "SATURATION_NOT_QUALITY_SIGNAL",
                    ],
                },
            ],
            "policy": (
                "Use these CVRP diagnostics to shape hypothesis planning only. "
                "They are not promotion evidence, not Protocol gate results, "
                "and not DecisionFeatures."
            ),
        }

    def render_problem_opportunity_summary(self) -> Mapping[str, Any]:
        """Return the typed CVRP opportunity summary for proposal context."""

        from scion.problems.cvrp.opportunity import CvrpOpportunityProvider

        return (
            CvrpOpportunityProvider(problem_spec=self._spec, adapter=self)
            .build_opportunity_summary()
            .to_payload()
        )

    def preview_research_surface_patch(
        self,
        *,
        patch: Any,
        surface: Any | None = None,
        base_workspace: str | None = None,
        branch_workspace: str | None = None,
    ) -> Mapping[str, Any]:
        _preview_common._POLICY_PREVIEW_TIME_LIMIT_SEC = (
            _POLICY_PREVIEW_TIME_LIMIT_SEC
        )
        _preview_synthetic._POLICY_PREVIEW_EXEC_TIMEOUT_SEC = (
            _POLICY_PREVIEW_EXEC_TIMEOUT_SEC
        )
        _preview_synthetic._POLICY_PREVIEW_TIME_LIMIT_SEC = (
            _POLICY_PREVIEW_TIME_LIMIT_SEC
        )
        preview_base_workspace = (
            str(branch_workspace or "").strip()
            or str(base_workspace or "").strip()
            or str(getattr(self._spec, "root_dir", "") or "").strip()
            or None
        )
        return _preview_research_surface_patch(
            patch=patch,
            surface=surface,
            base_workspace=preview_base_workspace,
        )

    def load_instance(self, instance_path: str) -> Any:
        suffix = Path(instance_path).suffix.lower()
        if suffix == ".json":
            return CvrpInstance.from_json(instance_path)
        if suffix == ".vrp":
            return load_cvrplib_instance(instance_path)
        raise ValueError(f"unsupported CVRP instance file extension: {suffix or '<none>'}")

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        return _deserialize_solver_output(raw_output, instance)

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        return _check_solution_consistency(artifact, instance)

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        return _check_feasibility(artifact, instance)

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        return _recompute_objective(artifact, instance)

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        return None
