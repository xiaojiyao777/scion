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
    NEXT_REQUIRED_DIRECTION,
    PROTECTED_CASES,
    SUCCESSOR32_MECHANISM_ID,
    SUCCESSOR32_TARGET_FILE,
    SUCCESSOR34_DESIGN_PATH,
    SUCCESSOR34_MECHANISM_ID,
    SUCCESSOR34_TARGET_FILE,
    SUCCESSOR_OPPORTUNITY_FAMILIES,
)
from scion.problems.cvrp.surface_policy import (
    ACTIVE_RESEARCH_SURFACE_NAMES,
    LEGACY_RESEARCH_SURFACE_NAMES,
    active_research_surfaces as _active_research_surfaces,
    is_active_research_surface as _is_active_research_surface,
    is_legacy_research_surface as _is_legacy_research_surface,
)


CVRP_SOLVER_DESIGN_STATIC_QUALITY_FAILURE = (
    "agent_quality_blocked:cvrp_solver_design_static_quality"
)
CVRP_CONSTRUCTION_SEED_DIRECT_EFFECT_FAILURE = (
    "agent_quality_blocked:cvrp_construction_seed_direct_effect_missing"
)
CVRP_SUCCESSOR32_FOCUS_FAILURE = (
    "agent_quality_blocked:cvrp_successor32_focus_mismatch"
)
CVRP_SUCCESSOR34_FOCUS_FAILURE = (
    "agent_quality_blocked:cvrp_successor34_focus_mismatch"
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

    def validate_hypothesis_quality(
        self,
        *,
        branch: Any | None,
        hypothesis: Any,
        step_history: Sequence[Any] | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned current successor proposal quality check for CVRP."""

        del branch, step_history
        change_locus = str(getattr(hypothesis, "change_locus", "") or "").strip()
        target_file = str(getattr(hypothesis, "target_file", "") or "").strip()
        if change_locus != "solver_design":
            return {"allowed": True, "gate_name": "cvrp_successor34_focus"}
        if target_file == SUCCESSOR34_TARGET_FILE:
            gate_name = "cvrp_successor34_focus"
            failure_code = CVRP_SUCCESSOR34_FOCUS_FAILURE
            required_mechanism_id = SUCCESSOR34_MECHANISM_ID
            required_target_file = SUCCESSOR34_TARGET_FILE
            successor_label = "successor34 frozen-safe neighbor-list VNS filter"
            required_causal_path = (
                "frozen-safe customer-adjacency filtering/order for existing "
                "VNS neighborhood candidate enumeration with deadline guards "
                "and bounded fallback"
            )
            retry_constraint = (
                "Redraft the CVRP solver-design hypothesis as the "
                "successor34 frozen-safe neighbor-list VNS filter: declare "
                f"mechanism `{SUCCESSOR34_MECHANISM_ID}`, keep the target "
                f"file at `{SUCCESSOR34_TARGET_FILE}`, and describe "
                "customer-adjacency candidate filtering/order inside existing "
                "VNS neighborhoods plus large-instance deadline guards, "
                "bounded fallback, and budget-stop telemetry. "
                "Do not switch to destroy/repair selection, q scheduling, seed "
                "selection, acceptance probability, operator-credit weighting, "
                "embedded-VNS runtime allocation, or a new local-search move family."
            )
        elif target_file == SUCCESSOR32_TARGET_FILE:
            gate_name = "cvrp_successor32_focus"
            failure_code = CVRP_SUCCESSOR32_FOCUS_FAILURE
            required_mechanism_id = SUCCESSOR32_MECHANISM_ID
            required_target_file = SUCCESSOR32_TARGET_FILE
            successor_label = "successor32 operator-credit mechanism"
            required_causal_path = (
                "post-repair pre-polish objective-effect credit for ALNS "
                "destroy/repair adaptive weights"
            )
            retry_constraint = (
                "Redraft the CVRP solver-design hypothesis as the "
                "successor32 operator-credit mechanism: declare mechanism "
                f"`{SUCCESSOR32_MECHANISM_ID}`, keep the target file at "
                f"`{SUCCESSOR32_TARGET_FILE}`, and describe post-repair "
                "pre-polish objective-effect credit for ALNS "
                "destroy/repair weights. Do not switch to destroy/repair "
                "selection, q scheduling, local search, seed selection, "
                "acceptance probability, or embedded-VNS runtime allocation."
            )
        else:
            return {"allowed": True, "gate_name": "cvrp_successor34_focus"}

        mechanism_ids: list[str] = []
        for change in getattr(hypothesis, "mechanism_changes", ()) or ():
            if isinstance(change, Mapping):
                raw_id = change.get("id")
            else:
                raw_id = getattr(change, "id", "")
            mechanism_id = str(raw_id or "").strip()
            if mechanism_id:
                mechanism_ids.append(mechanism_id)
        text = " ".join(
            str(part or "")
            for part in (
                getattr(hypothesis, "hypothesis_text", ""),
                getattr(hypothesis, "target_weakness", ""),
                getattr(hypothesis, "expected_effect", ""),
                getattr(hypothesis, "target_runtime_effect", ""),
                getattr(hypothesis, "complexity_claim", ""),
                getattr(hypothesis, "runtime_budget_strategy", ""),
            )
        )
        novelty = getattr(hypothesis, "novelty_signature", {}) or {}
        if isinstance(novelty, Mapping):
            text += " " + " ".join(str(item or "") for item in novelty.values())
        normalized_text = text.lower().replace("-", "_").replace(" ", "_")
        if required_mechanism_id in mechanism_ids or (
            required_mechanism_id in normalized_text
        ):
            return {"allowed": True, "gate_name": gate_name}

        return {
            "allowed": False,
            "detail": (
                f"{failure_code}: {successor_label} proposal must test "
                f"{required_mechanism_id} before code generation; "
                "selected_mechanisms="
                + ",".join(mechanism_ids or ["none"])
            ),
            "gate_name": gate_name,
            "structured_rejection": {
                "source": "cvrp_problem_adapter",
                "gate_name": gate_name,
                "failure_code": failure_code,
                "agent_block_reason": "agent_quality_blocked",
                "required_mechanism_id": required_mechanism_id,
                "selected_mechanism_ids": mechanism_ids,
                "target_file": target_file,
                "retry_constraint": retry_constraint,
                "repair_template": {
                    "repair_type": gate_name,
                    "required_mechanism_id": required_mechanism_id,
                    "required_target_file": required_target_file,
                    "required_causal_path": required_causal_path,
                },
                "decision_features_excluded": True,
            },
        }

    def validate_patch_quality(
        self,
        *,
        branch: Any | None,
        hypothesis: Any,
        patch: Any,
        step_history: Sequence[Any] | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned solver-design patch quality checks for CVRP."""

        del branch, step_history
        from scion.problems.cvrp.solver_design.static_quality import static_smoke_issue

        issue = static_smoke_issue(patch=patch, hypothesis=hypothesis)
        if issue is None:
            return {"allowed": True, "gate_name": "cvrp_solver_design_static_quality"}
        construction_seed_issue = "construction seed" in issue.lower()
        failure_code = (
            CVRP_CONSTRUCTION_SEED_DIRECT_EFFECT_FAILURE
            if construction_seed_issue
            else CVRP_SOLVER_DESIGN_STATIC_QUALITY_FAILURE
        )
        missing_code_elements = (
            ["construction_seed_direct_effect_record_move"]
            if construction_seed_issue
            else ["solver_design_static_quality"]
        )
        retry_constraint = (
            "Revise the CVRP solver-design patch before protocol: construction "
            "seed/portfolio mechanisms must record same-run seed/trajectory-"
            "vs-baseline objective effect with context.record_move under the "
            "declared mechanism id. Activation, phase timing, seed-pool size, "
            "or fallback use is not objective-effect evidence."
            if construction_seed_issue
            else "Revise the CVRP solver-design patch to satisfy problem-owned "
            "static quality constraints before protocol."
        )
        return {
            "allowed": False,
            "detail": f"{failure_code}: {issue}",
            "gate_name": "cvrp_solver_design_static_quality",
            "structured_rejection": {
                "source": "cvrp_problem_adapter",
                "gate_name": "cvrp_solver_design_static_quality",
                "failure_code": failure_code,
                "agent_block_reason": "agent_quality_blocked",
                "retry_constraint": retry_constraint,
                "repair_template": {
                    "repair_type": "cvrp_solver_design_static_quality",
                    "required_code_signals": {
                        "activation": [
                            "context.record_iteration('<mechanism>', count)",
                            "context.record_phase('<mechanism>', elapsed_ms)",
                        ],
                        "direct_effect": [
                            "context.record_move('<mechanism>', attempted=1, "
                            "accepted=..., delta=..., best_improved=...)"
                        ],
                    },
                    "missing_items": missing_code_elements,
                },
                "missing_code_elements": missing_code_elements,
                "decision_features_excluded": True,
            },
        }

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
                "unchanged_bounded_2node_cross_exchange",
                "unchanged_intra_route_or_opt_reinsert",
                "unchanged_bounded_intra_route_3opt",
                "unchanged_bounded_ejection_chain_relocate",
                "unchanged_bounded_route_segment_exchange",
                "unchanged_angular_sector_removal",
                "unchanged_radial_string_removal",
                "unchanged_farthest_noise_related_removal",
                "unchanged_polar_sweep_destroy_repair",
                "unchanged_route_fragment_recombination_repair",
                "unchanged_adjacency_pair_removal_repair",
                "unchanged_load_compatible_ruin_recreate",
                "unchanged_lookahead_insertion_cost_repair",
                "unchanged_lookahead_insertion_cost_repair_v2",
                "unchanged_savings_seed_selection_probe",
                "unchanged_cw_sweep_seed_baseline_selector",
                "unchanged_short_horizon_seed_trajectory_selector",
                "unchanged_short_horizon_seed_trajectory_selector_v2",
                "unchanged_route_pair_overlap_removal",
                "unchanged_route_pair_overlap_removal_protected_followup",
                "unchanged_boundary_spoke_outlier_removal",
                "unchanged_edge_conflict_endpoint_removal",
                "unchanged_bounded_cross_route_double_bridge_polish",
                "unchanged_adaptive_embedded_vns_runtime_allocation",
            ],
            "measurable_opportunity_classes": [
                {
                    "mechanism_family": "acceptance_or_adaptive_weighting",
                    "required_evidence": (
                        "successor32 post-repair operator-credit weighting is "
                        "reviewed zero-effect; repeat only with a materially "
                        "new adaptive-weighting causal path and direct "
                        "per-case total_distance evidence"
                    ),
                },
                {
                    "mechanism_family": "construction_seed_portfolio",
                    "required_evidence": (
                        "same-run seed baseline or same-mechanism accepted "
                        "delta showing objective-changing seed effect"
                    ),
                },
                {
                    "mechanism_family": "scheduler_destroy_size_policy",
                    "required_evidence": (
                        "activation telemetry and q-distribution or trace "
                        "evidence showing destroy magnitude changed before "
                        "existing destroy/repair operators ran"
                    ),
                },
                {
                    "mechanism_family": "destroy_repair_selection",
                    "required_evidence": (
                        "per-case total_distance delta tied to the changed "
                        "repair or removal choice; successor29 parked the "
                        "route-pair-overlap line for v0.4, so do not continue "
                        "unchanged route-pair overlap variants"
                    ),
                },
                {
                    "mechanism_family": "bounded_local_search_variant",
                    "required_evidence": (
                        "successor34 frozen-safe neighbor-list VNS filtering/"
                        "order: feasible route-level objective deltas, "
                        "attempted/accepted move counts, record_move delta, "
                        "phase runtime, iteration count, bounded candidate "
                        "enumeration, and budget/fallback/timeout evidence"
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
                    "mechanism_family": "scheduler_runtime_allocation",
                    "required_evidence": (
                        "successor31 stayed exact zero-effect despite runtime "
                        "movement; unchanged embedded-VNS runtime allocation "
                        "is default-avoid"
                    ),
                },
            ],
            "top_opportunity_recipe": {
                "schema_version": "scion.cvrp_opportunity_recipe.v1",
                "proposal_visibility_only": True,
                "decision_features_excluded": True,
                "mechanism_family": "bounded_local_search_variant",
                "mechanism_id": SUCCESSOR34_MECHANISM_ID,
                "review_status": "successor34_ready_after_successor33_frozen_unsafe",
                "successor_opportunity_families": list(SUCCESSOR_OPPORTUNITY_FAMILIES),
                "target_surface": "solver_design",
                "target_files": [SUCCESSOR34_TARGET_FILE],
                "design_path": SUCCESSOR34_DESIGN_PATH,
                "next_required_direction": NEXT_REQUIRED_DIRECTION,
                "required_observations": [
                    (
                        "exact mechanism id "
                        f"{SUCCESSOR34_MECHANISM_ID} before code work starts"
                    ),
                    (
                        "existing VNS neighborhood name plus attempted and "
                        "accepted move counts"
                    ),
                    (
                        "customer-adjacency candidate filtering scope, "
                        "deadline guard, and bounded fallback behavior"
                    ),
                    "record_move direct effect and best-improved status under the mechanism id",
                    "phase runtime and iteration count for the filtered VNS path",
                    "feasibility, route-count, runtime budget, and timeout evidence",
                    "CMT2/CMT4 case-level evidence or an explicit caveat",
                    "effect-vs-MDE interpretation",
                ],
                "implementation_constraints": [
                    (
                        "do not continue unchanged successor23-style "
                        "stagnation_adaptive_destroy_size_schedule scheduling"
                    ),
                    (
                        "use scheduler_destroy_size_policy only for a "
                        "telemetry-only q-audit repair or a materially different "
                        "scheduler causal path"
                    ),
                    (
                        "do not continue unchanged successor24-style "
                        "lookahead insertion-cost repair"
                    ),
                    (
                        "do not continue unchanged successor25-style raw "
                        "cw_sweep_seed_baseline_selector selection"
                    ),
                    (
                        "do not continue unchanged successor26-style "
                        "short_horizon_seed_trajectory_selector selection"
                    ),
                    (
                        "do not continue unchanged successor27-style "
                        "route_pair_overlap_removal or successor29 protected "
                        "route-pair-overlap follow-up"
                    ),
                    (
                        "do not continue unchanged successor30-style bounded "
                        "cross-route double-bridge polish"
                    ),
                    (
                        "do not continue unchanged successor31-style adaptive "
                        "embedded-VNS runtime allocation"
                    ),
                    (
                        "do not continue unchanged successor32-style post-repair "
                        "effect credit weighting"
                    ),
                    (
                        "do not add a new local-search move family for "
                        "successor34; the causal path is frozen-safe candidate "
                        "filtering inside existing VNS neighborhoods"
                    ),
                    (
                        "do not hardcode case ids, reference objective values, "
                        "seeds, or split membership when designing the "
                        "candidate filter"
                    ),
                    (
                        "keep the local_search.py change narrow; if the "
                        "candidate-index structure grows beyond local scope, "
                        "keep it as a coherent problem-owned module rather "
                        "than adding helper sprawl to an oversized file"
                    ),
                    (
                        "keep CVRP semantics in problem-owned solver files and "
                        "generic core unchanged"
                    ),
                ],
                "protected_cases": list(PROTECTED_CASES),
                "protected_case_required_evidence": list(
                    CASE_PROTECTION_REQUIREMENTS["required_evidence"]
                ),
                "default_reject_directions": [
                    "unchanged stagnation_adaptive_destroy_size_schedule",
                    "unchanged operator_pair_destroy_size_bands",
                    "unchanged bounded_route_segment_exchange",
                    "unchanged lookahead_insertion_cost_repair",
                    "unchanged lookahead_insertion_cost_repair_v2",
                    "unchanged cw_sweep_seed_baseline_selector",
                    "unchanged short_horizon_seed_trajectory_selector",
                    "unchanged short_horizon_seed_trajectory_selector_v2",
                    "unchanged route_pair_overlap_removal",
                    "unchanged route_pair_overlap_removal_protected_followup",
                    "unchanged bounded_cross_route_double_bridge_polish",
                    "unchanged neighbor_list_vns_filter without frozen-safe guards",
                    "unchanged adaptive_embedded_vns_runtime_allocation",
                    "unchanged post_repair_effect_credit_weighting",
                    "same-family scheduler q changes without explicit q-audit fields",
                ],
            },
            "mechanism_effect_ranking": [
                {
                    "rank": 1,
                    "mechanism_family": "bounded_local_search_variant",
                    "evidence_status": "successor34_ready_after_successor33_frozen_unsafe",
                    "opportunity_status": "eligible_same_family_repair",
                    "effect_status": "validation_positive_frozen_unsafe",
                    "summary": (
                        "Successor28/29 parked route-pair-overlap follow-ups, "
                        "successor30 parked bounded cross-route double-bridge "
                        "polish, and successor31 parked adaptive embedded-VNS "
                        "runtime allocation. Successor32 showed internal "
                        "operator-credit movement but zero objective effect. "
                        "Successor33 neighbor_list_vns_filter then passed "
                        "screening/validation but failed frozen on candidate "
                        "timeouts. The next slot should repair that line with "
                        "frozen_safe_neighbor_list_vns_filter."
                    ),
                    "recommended_action": (
                        "Target policies/baseline_modules/local_search.py and "
                        "record neighborhood name, attempted/accepted counts, "
                        "record_move delta, best-improved status, phase runtime, "
                        "iterations, budget/fallback/timeout counters, and "
                        "per-case total_distance evidence."
                    ),
                    "reason_codes": [
                        "SUCCESSOR34_FROZEN_SAFE_NEIGHBOR_LIST_READY",
                        "SUCCESSOR33_VALIDATION_POSITIVE_FROZEN_UNSAFE",
                        "SUCCESSOR31_ZERO_EFFECT_DEFAULT_AVOID",
                        "ROUTE_PAIR_OVERLAP_LINE_PARKED",
                        "DIRECT_OBJECTIVE_EFFECT_REQUIRED",
                    ],
                },
                {
                    "rank": 2,
                    "mechanism_family": "acceptance_or_adaptive_weighting",
                    "evidence_status": "successor32_reviewed_zero_effect",
                    "opportunity_status": "reviewed_default_avoid",
                    "effect_status": "measured_no_positive_at_mde",
                    "summary": (
                        "Successor32 post_repair_effect_credit_weighting "
                        "showed internal operator-credit movement, but valid "
                        "screening measured zero objective effect."
                    ),
                    "recommended_action": (
                        "Do not repeat unchanged post-repair effect credit "
                        "weighting; revisit adaptive weighting only with a "
                        "materially new causal path and direct objective effect."
                    ),
                    "reason_codes": [
                        "SUCCESSOR32_ZERO_EFFECT_DEFAULT_AVOID",
                        "ADAPTIVE_WEIGHTING_REVIEWED_NO_OBJECTIVE_EFFECT",
                    ],
                },
                {
                    "rank": 3,
                    "mechanism_family": "construction_seed_portfolio",
                    "evidence_status": "successor26b_seed_trajectory_below_mde",
                    "opportunity_status": "reviewed_default_avoid",
                    "effect_status": "measured_no_positive_at_mde",
                    "summary": (
                        "Successor25 showed raw construction seed deltas were "
                        "not preserved downstream; successor26b validly "
                        "screened short_horizon_seed_trajectory_selector and "
                        "short_horizon_seed_trajectory_selector_v2, but both "
                        "stayed below MDE and v2 lost on CMT2/CMT4."
                    ),
                    "recommended_action": (
                        "Do not continue unchanged construction seed-baseline "
                        "or seed-trajectory selection. Any construction revisit "
                        "must name a new causal path and explain why successor25/"
                        "successor26b evidence no longer applies."
                    ),
                    "reason_codes": [
                        "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT",
                        "SUCCESSOR25_REVIEWED_SEED_DELTA_NOT_PRESERVED",
                        "SUCCESSOR26B_REVIEWED_BELOW_MDE",
                        "ACTIVATION_IS_NOT_OBJECTIVE_EFFECT",
                    ],
                },
                {
                    "rank": 4,
                    "mechanism_family": "scheduler_destroy_size_policy",
                    "evidence_status": "successor23_reviewed_solver_negative",
                    "opportunity_status": "eligible_only_if_materially_different_or_telemetry_audit",
                    "effect_status": "below_mde_quality_regression",
                    "summary": (
                        "Successor23 repaired observable q deltas for "
                        "stagnation_adaptive_destroy_size_schedule, but stayed "
                        "below MDE, parked as quality regression, and missed "
                        "explicit baseline_q/adapted_q/q_delta runtime fields."
                    ),
                    "recommended_action": (
                        "Do not continue the unchanged scheduler policy; use "
                        "this family only for telemetry-only q-audit repair or "
                        "a materially different scheduler causal path."
                    ),
                    "reason_codes": [
                        "SUCCESSOR23_REVIEWED_BELOW_MDE",
                        "QUALITY_REGRESSION_PARKED",
                        "EXPLICIT_Q_AUDIT_FIELDS_MISSING",
                    ],
                },
                {
                    "rank": 5,
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
                    "mechanism_family": (
                        "scheduler_policy_construction_destroy_repair_local_search"
                    ),
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
                    "diagnostic_type": "reviewed_scheduler_policy",
                    "surface": "solver_design",
                    "mechanism_family": "scheduler_destroy_size_policy",
                    "metric": "total_distance",
                    "summary": (
                        "The latest scheduler destroy-size successor repaired "
                        "observable q trajectory but remained below MDE, parked "
                        "as quality regression, and missed explicit q-audit "
                        "fields."
                    ),
                    "recommended_action": (
                        "Clean-fork to a materially different CVRP-owned causal "
                        "path, or explicitly scope a telemetry-only repair that "
                        "records baseline_q, adapted_q, and q_delta."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "SUCCESSOR23_REVIEWED_BELOW_MDE",
                        "QUALITY_REGRESSION_PARKED",
                        "EXPLICIT_Q_AUDIT_FIELDS_MISSING",
                    ],
                },
                {
                    "diagnostic_type": "route_pair_overlap_line_parked",
                    "surface": "solver_design",
                    "mechanism_family": "destroy_repair_selection",
                    "metric": "total_distance",
                    "summary": (
                        "Successor27 route_pair_overlap_removal was weak "
                        "positive below MDE, but successor29's true protected "
                        "follow-up stayed negative with CMT4/P-family losses. "
                        "The route-pair-overlap line is parked for v0.4."
                    ),
                    "recommended_action": (
                        "Do not continue unchanged route_pair_overlap_removal "
                        "or route_pair_overlap_removal_protected_followup in "
                        "the next slot."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "SUCCESSOR29_PROTECTED_FOLLOWUP_NEGATIVE",
                        "ROUTE_PAIR_OVERLAP_LINE_PARKED",
                    ],
                },
                {
                    "diagnostic_type": "successor34_frozen_safe_neighbor_list_vns_filter",
                    "surface": "solver_design",
                    "mechanism_family": "bounded_local_search_variant",
                    "metric": "total_distance",
                    "summary": (
                        "Successor33 proved customer-adjacency VNS filtering "
                        "can pass screening and validation, but frozen failed "
                        "on candidate-side timeouts. Successor34 should repair "
                        "that path with deadline guards, bounded fallback, and "
                        "budget-stop telemetry."
                    ),
                    "recommended_action": (
                        "Target frozen_safe_neighbor_list_vns_filter in "
                        "policies/baseline_modules/local_search.py and record "
                        "neighborhood name, attempted/accepted counts, "
                        "record_move delta, best-improved status, phase runtime, "
                        "iterations, fallback/skipped/budget-stop counters, "
                        "and formal per-case objective deltas."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "SUCCESSOR34_FROZEN_SAFE_NEIGHBOR_LIST_READY",
                        "SUCCESSOR33_VALIDATION_POSITIVE_FROZEN_UNSAFE",
                        "BOUNDED_LOCAL_SEARCH_DIRECT_EFFECT_REQUIRED",
                    ],
                },
                {
                    "diagnostic_type": "successor32_operator_credit_reviewed",
                    "surface": "solver_design",
                    "mechanism_family": "acceptance_or_adaptive_weighting",
                    "metric": "total_distance",
                    "summary": (
                        "Successor32 post_repair_effect_credit_weighting "
                        "recorded internal operator-credit movement but stayed "
                        "at zero objective effect in valid screening."
                    ),
                    "recommended_action": (
                        "Do not repeat unchanged post-repair effect credit "
                        "weighting; only revisit adaptive weighting with a "
                        "materially new causal path and direct objective effect."
                    ),
                    "confidence": "medium",
                    "reason_codes": [
                        "SUCCESSOR32_ZERO_EFFECT_DEFAULT_AVOID",
                        "ADAPTIVE_WEIGHTING_REVIEWED_NO_OBJECTIVE_EFFECT",
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
