"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance
from scion.problems.cvrp.solution_checks import (
    check_feasibility as _check_feasibility,
    check_solution_consistency as _check_solution_consistency,
    deserialize_solver_output as _deserialize_solver_output,
    recompute_objective as _recompute_objective,
)
from scion.problems.cvrp.surface_rendering import (
    render_operator_interface as _render_operator_interface,
    render_problem_object as _render_problem_object,
    render_problem_summary as _render_problem_summary,
    render_research_surface_interface as _render_research_surface_interface,
    render_solver_mechanics as _render_solver_mechanics,
)
from scion.problems.cvrp.surface_policy import (
    ACTIVE_RESEARCH_SURFACE_NAMES,
    LEGACY_RESEARCH_SURFACE_NAMES,
    active_research_surfaces as _active_research_surfaces,
    is_active_research_surface as _is_active_research_surface,
    is_legacy_research_surface as _is_legacy_research_surface,
)

__all__ = [
    "CvrpAdapter",
    "CROSS_CAMPAIGN_RESEARCH_PRIOR",
    "CURRENT_RESEARCH_QUESTION",
]


CURRENT_RESEARCH_QUESTION = (
    "What CVRP-owned algorithmic change can improve final total_distance on "
    "the declared evaluation surface while preserving feasibility and route "
    "validity, and what observations support attribution of the final result "
    "to that change?"
)

CROSS_CAMPAIGN_RESEARCH_PRIOR = (
    (
        "Previously evaluated route-segment and cross-route exchanges, "
        "destroy-size schedules, insertion-cost lookahead, construction-seed "
        "selection, route-pair overlap targeting, double-bridge moves, and "
        "adaptive embedded-VNS allocation were neutral or negative on final "
        "total_distance. Broad removal of VNS was also negative. These are "
        "observations, not proposal prohibitions."
    ),
    (
        "Historical screening-level evidence around SWAP* and initial-VNS "
        "budget allocation was mixed and cumulative; it did not isolate a "
        "causal mechanism. This is a neutral lead, not a required direction."
    ),
    (
        "Recent ejection evidence is mixed and implementation-sensitive. An "
        "older deeper route-preserving chain was 0W/4L/4T cases with median "
        "-11.5 and only about 74 ALNS iterations versus 1,631 for B0. In the "
        "open-research R1 partial run, a bounded completion-aware depth-one "
        "repair reproduced a sparse positive direction after expansion at "
        "6W/1L/5T cases, median +3.75 with CI [0,11], but recorded 186 "
        "aggregate repair errors (8.7% of all ALNS iterations) without an "
        "exposed operator-local denominator and did not advance; a cumulative "
        "depth-two variant was negative. These observations neither require "
        "nor forbid ejection research, depth-one refinement, or a different "
        "direction."
    ),
    (
        "Corrected R2's strongest result was elapsed-budget simulated "
        "annealing: its exact 12-case quality screen was 6W/1L/5T cases, "
        "49W/20L/27T pairs, and median final total_distance improvement +2.75 "
        "with CI [0,11]. It did not pass the fixed R2 wins/all-cases rule and "
        "is not a hidden promotion. The implementation removed nearly all "
        "late worsening acceptances and increased best updates, but its "
        "progress denominator omitted construction, initial VNS, and the "
        "tighter outer deadline, while its temperature update lagged one "
        "iteration. These are neutral source-grounded leads, not a required "
        "mechanism or host-mandated fix."
    ),
)


class CvrpAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def solver_design_prompt_provider(self) -> Any:
        from scion.problems.cvrp.solver_design_provider import (
            CvrpSolverDesignProvider,
        )

        return CvrpSolverDesignProvider()

    def research_question_payload(self) -> Mapping[str, Any]:
        """Return ordinary safe research context without a contract graph."""

        return {
            "current_question": CURRENT_RESEARCH_QUESTION,
            "research_prior": list(CROSS_CAMPAIGN_RESEARCH_PRIOR),
        }

    def proposal_mechanism_evidence_provider(self) -> Any:
        from scion.problems.cvrp.proposal_mechanism_evidence import (
            CvrpProposalMechanismEvidenceProvider,
        )

        return CvrpProposalMechanismEvidenceProvider()

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
        """Return current CVRP measurement and attribution guidance.

        The payload is intentionally independent of prior experiment names,
        reviewed mechanism catalogs, and next-target recommendations.
        """

        return {
            "schema_version": "scion.cvrp_measurement_guidance.v3",
            "measurement_context": {
                "metric": "total_distance",
                "objective": "minimize",
                "practical_screen_delta": 2.0,
                "practical_validate_delta": 1.0,
                "screening_mde_at_power_80": None,
                "screening_calibration_status": (
                    "r3_limited_same_seed_null_zero_passes_power_unestablished"
                ),
                "interpretation": (
                    "Interpret paired final total_distance with case-level "
                    "variation and uncertainty. R3's three provider-free "
                    "same-seed A/A diagnostics each had an observed combined "
                    "rule that did not pass and zero of 2,000 independent "
                    "paired-label-swap null samples pass on its fixed 12-case, "
                    "two-seed stage population (Wilson upper 95%=0.001351). "
                    "This is only a limited false-pass/repeatability "
                    "diagnostic; it is not a matched MDE or power estimate. "
                    "Older MDE=9.9 and MDE=9.6 estimates used incompatible "
                    "pair-level designs. Intermediate deltas are not "
                    "substitutes for the final solver result."
                ),
            },
            "feasibility": {
                "required": True,
                "observations": [
                    "capacity constraints",
                    "customer coverage and uniqueness",
                    "depot and route structure",
                    "reported objective consistency",
                    "route count",
                ],
            },
            "typed_attribution": {
                "observations": [
                    "attempted change",
                    "accepted route-state transition",
                    "direct objective change when observable",
                    "downstream search effect",
                    "final total_distance",
                ],
                "interpretation": (
                    "Keep activation, accepted state, direct effect, "
                    "downstream effect, and final outcome distinct."
                ),
            },
        }

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
