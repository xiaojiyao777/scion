"""Route-first comparison guidance for the CVRP research surface."""
from __future__ import annotations

from typing import Any

from scion.research_guidance import EvidenceRequirement, RequiredMechanism

ROUTE_FIRST_COMPARISON_MECHANISM_ID = "route_first_heuristic"
ROUTE_FIRST_COMPARISON_VARIANT_ID = "route_first_heuristic"
ROUTE_FIRST_COMPARISON_TARGET_FILE = "policies/baseline_modules/config.py"
ROUTE_FIRST_COMPARISON_TARGET_FILES = (
    ROUTE_FIRST_COMPARISON_TARGET_FILE,
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/route_first_heuristic.py",
    "policies/baseline_modules/route_first_seeding.py",
    "policies/baseline_modules/route_first_improvement.py",
)
ROUTE_FIRST_COMPARISON_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-comparison-route-first-heuristic-design-20260708.md"
)
ROUTE_FIRST_COMPARISON_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-route-first-comparison-postrun-20260708.md"
)
ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE = (
    "The CVRP route-first comparison object is complete and reviewed negative: "
    f"the implemented `{ROUTE_FIRST_COMPARISON_VARIANT_ID}` variant was enabled "
    f"through `{ROUTE_FIRST_COMPARISON_TARGET_FILE}`, runtime telemetry proved "
    "the route_first_heuristic phase executed, and the short comparison lost "
    "against the current ALNS+VNS champion. Treat unchanged route-first "
    "config-flip candidates as reviewed/default-avoid evidence, not as a live "
    "target-intent slot. Future CVRP solver-design work must use a materially "
    "different CVRP-owned causal path with algorithmic intervention evidence. "
    f"Design: `{ROUTE_FIRST_COMPARISON_DESIGN_PATH}`. Postrun: "
    f"`{ROUTE_FIRST_COMPARISON_POSTRUN_PATH}`."
)


def route_first_comparison_focus() -> dict[str, Any]:
    return {
        "mechanism_id": ROUTE_FIRST_COMPARISON_MECHANISM_ID,
        "variant_id": ROUTE_FIRST_COMPARISON_VARIANT_ID,
        "mechanism_family": "solver_family_comparison",
        "target_file": ROUTE_FIRST_COMPARISON_TARGET_FILE,
        "target_files": list(ROUTE_FIRST_COMPARISON_TARGET_FILES),
        "design_path": ROUTE_FIRST_COMPARISON_DESIGN_PATH,
        "postrun_path": ROUTE_FIRST_COMPARISON_POSTRUN_PATH,
        "status": "reviewed_negative_comparison",
        "required_mechanism_binding": "none",
        "reviewed_result": {
            "case_wlt": "0/16/0",
            "pair_wlt": "0/64/0",
            "median_delta": -24.5,
            "ci": [-116.5, -15.0],
            "runtime_confirmed": True,
            "interpretation": (
                "unchanged route_first_heuristic is worse than ALNS+VNS on "
                "the measured CVRP surface"
            ),
        },
        "material_difference": {
            "changed_dimensions": [
                "complete route-first solver family",
                "default-off variant selection through config",
                "constructive starts from Clarke-Wright and rotated sweeps",
                "deterministic bounded cleanup without ALNS/VNS control",
            ],
            "contrast": (
                "not an ALNS+VNS operator tweak, successor48 route-pool "
                "continuation, repair selector, route skeleton, route memory, "
                "local-search move insertion, acceptance guard, or "
                "runtime-allocation change"
            ),
            "evidence": [
                "SOLVER_VARIANT enables route_first_heuristic",
                "route_first_heuristic phase runtime and iteration counts",
                "attempted and accepted route_first_heuristic moves",
                "route_first_heuristic best-delta and improvement counts",
                "solution progress initial/final distance and route count",
                "final total_distance against the ALNS+VNS champion",
                "feasibility and route-count preservation",
                "CMT2/CMT4 priority-case outcome evidence",
            ],
        },
        "rule": ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE,
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }


def route_first_comparison_required_mechanism(
    protected_cases: tuple[str, ...],
) -> RequiredMechanism:
    return RequiredMechanism(
        mechanism_id=ROUTE_FIRST_COMPARISON_MECHANISM_ID,
        category="solver_family_comparison_reviewed",
        description=ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE,
        required_observations=(
            "enable SOLVER_VARIANT route_first_heuristic",
            "default ALNS+VNS entrypoint remains available",
            "no generic core, protocol, DecisionFeatures, or solver.py edits",
            "route_first_heuristic phase runtime",
            "route_first_heuristic iterations and move counts",
            "route_first_heuristic best-delta and improvement counts",
            "solution progress initial and final total_distance",
            "feasibility and route-count preservation",
            "CMT2/CMT4 priority-case outcome evidence",
        ),
        protected_items=protected_cases,
        hypothesis_mechanism_binding="context_only",
    )


def route_first_comparison_evidence_requirement(
    protected_cases: tuple[str, ...],
) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id="route_first_heuristic_comparison_baseline",
        category="solver_family_comparison_evidence",
        description=ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE,
        mechanism_ids=(
            ROUTE_FIRST_COMPARISON_MECHANISM_ID,
            ROUTE_FIRST_COMPARISON_VARIANT_ID,
            *ROUTE_FIRST_COMPARISON_TARGET_FILES,
        ),
        protected_items=protected_cases,
        required_fields=(
            "route_first comparison design path cited before code",
            "SOLVER_VARIANT route_first_heuristic enabled by candidate",
            "default ALNS+VNS variant remains default outside the candidate",
            "no generic Scion core, protocol, DecisionFeatures, or solver.py edits",
            "route_first_heuristic phase runtime",
            "route_first_heuristic iteration count",
            "route_first_heuristic attempted and accepted move counts",
            "route_first_heuristic best-delta and improvement counts",
            "solution_progress initial/final total_distance and route count",
            "final total_distance against the ALNS+VNS champion",
            "feasibility preservation",
            "route-count preservation or explicit caveat",
            "CMT2/CMT4 priority-case outcome evidence",
        ),
    )


def route_first_comparison_related_ids() -> tuple[str, ...]:
    return (
        ROUTE_FIRST_COMPARISON_MECHANISM_ID,
        ROUTE_FIRST_COMPARISON_VARIANT_ID,
        *ROUTE_FIRST_COMPARISON_TARGET_FILES,
        "solver_family_comparison",
    )
