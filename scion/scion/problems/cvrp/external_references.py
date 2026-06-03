"""CVRP-owned external mechanism references for proposal guidance."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


class CvrpExternalMechanismReferenceProvider:
    """Problem-owned mechanism references derived from external CVRP controls.

    These references are tainted proposal guidance. They summarize external
    research-process findings as mechanism-level priors and observability needs;
    they are not Scion Decision input and do not relax protocol gates.
    """

    def entries(self) -> Sequence[Mapping[str, Any]]:
        return (
            {
                "source_ref": "direct-vrp-control:20260603:round08-round10",
                "mechanism_label": "typed_fleet_metadata_soft_preference",
                "surface": "solver_design",
                "target_file": "policies/baseline_modules/construction.py",
                "evidence_scope": "external_control_broad",
                "positive_signals": (
                    "soft parsed fleet metadata survived broad X validation",
                    "round08 improved quick-signal mean without broad safety errors",
                ),
                "negative_boundaries": (
                    "hard parsed fleet metadata failed broad X validation",
                    "explicit user max_routes remains hard; parsed instance-name "
                    "fleet size is advisory unless independently guaranteed",
                ),
                "required_observations": (
                    "problem_metadata.max_routes_source",
                    "problem_metadata.max_routes_confidence",
                    "solution_route_count",
                    "construction_variant_id",
                ),
                "suggested_actions": (
                    "use adapter-owned typed facts for metadata confidence",
                    "treat inferred route-limit metadata as construction preference, not feasibility law",
                    "verify route-count behavior in broad validation before promotion",
                ),
                "confidence": "external_control_broad",
                "note": (
                    "Direct VRP round07 rejected hard parsed metadata; round08 "
                    "accepted the soft-preference interpretation."
                ),
            },
            {
                "source_ref": "direct-vrp-control:20260603:round01-round10",
                "mechanism_label": "size_bucketed_construction_portfolio",
                "surface": "solver_design",
                "target_file": "policies/baseline_modules/construction.py",
                "evidence_scope": "external_control_broad",
                "positive_signals": (
                    "large-instance construction variants improved X411 and X513",
                    "medium construction variant improved X327 and survived "
                    "broad A/B/E/M/P/X/tai validation",
                    "final safe broad comparison improved 33 common rows and "
                    "worsened 3",
                ),
                "negative_boundaries": (
                    "do not add homogeneous construction variants without "
                    "telemetry for selected variant and size bucket",
                    "quick-signal alone is insufficient for accepting "
                    "construction portfolio changes",
                ),
                "required_observations": (
                    "construction_variant_id",
                    "construction_size_bucket",
                    "construction_time_ms",
                    "common_row_improved_count",
                    "common_row_worsened_count",
                ),
                "suggested_actions": (
                    "target bounded construction portfolio variants by declared instance-size bucket",
                    "protect small-instance behavior while probing medium and large buckets",
                    "include common-row improved/worsened evidence in follow-up analysis",
                ),
                "confidence": "external_control_broad",
                "note": (
                    "Direct VRP final safe round10 passed 203/203 broad rows and "
                    "improved 33 of 126 common filtered rows versus prior safe broad."
                ),
            },
            {
                "source_ref": "direct-vrp-control:20260603:round04-round11",
                "mechanism_label": "phase_budgeted_local_improvement",
                "surface": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
                "evidence_scope": "external_control_broad",
                "positive_signals": (
                    "moderate local-search cap reduced runtime without changing "
                    "quick-signal cost",
                    "cap-1 initial polish helped selected large instances when "
                    "broad safety remained clean",
                ),
                "negative_boundaries": (
                    "aggressive local-search cap damaged quality",
                    "extra medium variant added runtime and regressions without wins",
                ),
                "required_observations": (
                    "local_search_phase_time_ms",
                    "vns_cap",
                    "initial_polish_enabled",
                    "initial_polish_time_ms",
                    "local_search_accept_count",
                ),
                "suggested_actions": (
                    "treat phase budget and quality gate as a coupled mechanism",
                    "use bounded caps and no-op guards instead of broad unbounded local search",
                    "separate runtime savings from objective-quality evidence in telemetry",
                ),
                "confidence": "external_control_broad",
                "note": (
                    "Direct VRP round04 kept cap 10; round05 cap 3 regressed; "
                    "round11 extra variant was rejected."
                ),
            },
            {
                "source_ref": "direct-vrp-control:20260603:validation-method",
                "mechanism_label": "common_row_broad_safety_evidence",
                "surface": "solver_design",
                "target_file": "",
                "evidence_scope": "external_control_methodology",
                "positive_signals": (
                    "broad validation caught unsafe hard-metadata interpretation",
                    "common-row improved/worsened counts explained aggregate gains",
                ),
                "negative_boundaries": (
                    "do not rely on mean gap alone for mechanism acceptance",
                    "do not treat quick-signal wins as broad safety evidence",
                ),
                "required_observations": (
                    "common_row_improved_count",
                    "common_row_worsened_count",
                    "broad_validation_status",
                    "timeout_count",
                    "feasible_count",
                ),
                "suggested_actions": (
                    "design hypotheses with telemetry that can support "
                    "common-row comparison",
                    "request broad safety validation before treating a mechanism as promotable",
                    "preserve negative evidence from unsafe variants in branch memory",
                ),
                "confidence": "external_control_methodology",
                "note": (
                    "This is validation-method guidance for proposal reasoning; "
                    "formal promotion remains controlled by Scion protocol."
                ),
            },
        )


__all__ = ["CvrpExternalMechanismReferenceProvider"]
