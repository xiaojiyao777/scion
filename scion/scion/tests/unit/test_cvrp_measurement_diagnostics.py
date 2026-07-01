from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager.manager import _problem_measurement_diagnostics
from scion.proposal.engine.hypothesis_context_profiles import (
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.engine.hypothesis_prompts import _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest


_CVRP_PROBLEM = (
    Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
)


def test_cvrp_adapter_renders_proposal_only_measurement_opportunities() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec_v1)

    payload = adapter.render_problem_measurement_diagnostics()
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "cvrp_measurement_opportunity_diagnostic.v1"
    assert payload["decision_features_excluded"] is True
    assert payload["measurement_context"]["screening_mde_at_power_80"] == 9.9
    assert payload["measurement_context"]["practical_screen_delta"] == 2.0
    assert payload["screening_headroom"]["gap_pct_min"] == 2.5
    assert "broad_vns_removal" in payload["default_avoid_directions"]
    assert "unchanged_demand_slack_regret_insertion" in (
        payload["default_avoid_directions"]
    )
    ranking = payload["mechanism_effect_ranking"]
    assert ranking[0]["mechanism_family"] == "bounded_local_search_variant"
    assert ranking[0]["opportunity_status"] == "eligible_same_family_repair"
    assert ranking[0]["evidence_status"] == (
        "successor34_ready_after_successor33_frozen_unsafe"
    )
    assert "frozen_safe_neighbor_list_vns_filter" in ranking[0]["summary"]
    assert "candidate timeouts" in ranking[0]["summary"]
    assert ranking[1]["mechanism_family"] == "acceptance_or_adaptive_weighting"
    assert ranking[1]["opportunity_status"] == "reviewed_default_avoid"
    assert ranking[1]["evidence_status"] == "successor32_reviewed_zero_effect"
    assert ranking[2]["mechanism_family"] == "construction_seed_portfolio"
    assert ranking[2]["opportunity_status"] == "reviewed_default_avoid"
    assert ranking[2]["evidence_status"] == "successor26b_seed_trajectory_below_mde"
    assert "short_horizon_seed_trajectory_selector_v2" in ranking[2]["summary"]
    assert ranking[3]["mechanism_family"] == "scheduler_destroy_size_policy"
    assert ranking[3]["opportunity_status"] == (
        "eligible_only_if_materially_different_or_telemetry_audit"
    )
    assert ranking[3]["evidence_status"] == "successor23_reviewed_solver_negative"
    assert "baseline_q/adapted_q/q_delta" in ranking[3]["summary"]
    assert ranking[4]["mechanism_family"] == "large_instance_intra_route_two_opt_seed"
    assert ranking[4]["opportunity_status"] == "reviewed_not_next_required"
    assert "bks" not in json.dumps(ranking, sort_keys=True).lower()
    reason_codes = {
        code
        for item in payload["opportunity_diagnostics"]
        for code in item["reason_codes"]
    }
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in reason_codes
    assert "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT" in reason_codes
    assert "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY" in reason_codes
    assert "SUCCESSOR34_FROZEN_SAFE_NEIGHBOR_LIST_READY" in rendered
    assert "SUCCESSOR33_VALIDATION_POSITIVE_FROZEN_UNSAFE" in rendered
    assert "holdout" not in rendered.lower()
    assert "bks" not in rendered.lower()


def test_context_manager_projects_cvrp_adapter_opportunities_top_level() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    adapter = CvrpAdapter(spec_v1)

    payload = _problem_measurement_diagnostics(legacy, adapter=adapter)
    context = {
        "problem_summary": "CVRP formal solver-design objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/baseline_algorithm.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1",
        "problem_measurement_diagnostics": payload,
    }
    filtered = filter_hypothesis_context_for_prompt(context)
    compact = filtered["problem_measurement_diagnostics"]

    assert payload["decision_features_excluded"] is True
    assert payload["runtime_model"] == "budget_exhausting"
    assert payload["pairing_validity"] == "trajectory_divergent"
    assert "opportunity_diagnostics" in payload
    assert payload["opportunity_diagnostics"][0]["diagnostic_type"] == (
        "measurement_power"
    )
    assert payload["screening_headroom"]["case_count"] == 16
    assert payload["measurable_opportunity_classes"][0]["mechanism_family"] == (
        "acceptance_or_adaptive_weighting"
    )
    assert payload["mechanism_effect_ranking"][0]["mechanism_family"] == (
        "bounded_local_search_variant"
    )
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in compact
    assert "TRAJECTORY_DIVERGENT_LOW_SNR" in compact
    assert "mechanism_effect_ranking" in compact
    assert "eligible_same_family_repair" in compact
    assert "SUCCESSOR34_FROZEN_SAFE_NEIGHBOR_LIST_READY" in compact
    assert "SUCCESSOR33_VALIDATION_POSITIVE_FROZEN_UNSAFE" in compact
    assert "ROUTE_PAIR_OVERLAP_LINE_PARKED" in compact
    assert "eligible_only_if_materially_different_or_telemetry_audit" in compact
    assert "SUCCESSOR23_REVIEWED_BELOW_MDE" in compact
    assert "reviewed_not_next_required" in compact
    assert "measurable_opportunity_classes" in compact
    assert "case_count_gap_pct_at_least_3" in compact
    assert "construction seed" in compact.lower()
    assert "excluded_from_decision_features" in compact
    assert "hidden" not in compact.lower()
    assert "raw_pair_rows" not in compact
    assert "validation_case_details" not in compact
    assert "frozen_case_details" not in compact

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(str(block["text"]) for block in system_blocks)
    rendered_prompt += "\n" + user_prompt
    rendered_lower = rendered_prompt.lower()

    assert "## Problem Measurement Diagnostics" in rendered_prompt
    assert "cvrp_measurement_opportunity_diagnostic.v1" in rendered_prompt
    assert "screening_headroom" in rendered_prompt
    assert "large_instance_intra_route_two_opt_seed" in rendered_prompt
    assert "CVRP_LARGE_INSTANCE_TWO_OPT_SEED" in rendered_prompt
    assert "excluded from DecisionFeatures" in rendered_prompt
    assert "bks_gap_details" not in rendered_lower
    assert "hidden-bks" not in rendered_lower
    assert "validation_case_details" not in rendered_prompt
    assert "frozen_case_details" not in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-cvrp-adapter-measurement-diagnostics",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    assert manifest["section_statuses"]["problem_measurement_diagnostics"][
        "block_family"
    ] == "research_signal"
    assert manifest["section_statuses"]["problem_measurement_diagnostics"][
        "status"
    ] == "included"
    assert manifest["block_family_accounting"]["decision_features_excluded"] is True


def test_adapter_opportunity_projection_drops_unapproved_fields() -> None:
    class _Spec:
        measurement = None

    class _Adapter:
        def render_problem_measurement_diagnostics(self) -> dict[str, object]:
            return {
                "adapter_summary": "safe proposal planning summary",
                "nested": {
                    "safe_note": "keep this adapter note",
                    "raw_pair_rows": [{"case": "hidden-nested-row"}],
                    "pair_evidence": [{"case": "hidden-pair-evidence"}],
                    "bks_gap_details": "hidden-bks-gap",
                    "prompt_ratios": {"research_signal_ratio": 0.9},
                    "llm_text": "hidden free-form llm text",
                },
                "opportunity_diagnostics": [
                    {
                        "diagnostic_type": "measurement_power",
                        "surface": "solver_design",
                        "summary": "proposal-only low-SNR guidance",
                        "recommended_action": "use direct objective-effect evidence",
                        "reason_codes": ["LOW_SNR"],
                        "raw_pair_rows": [{"case": "hidden"}],
                        "validation_case_details": "hidden",
                        "frozen_case_details": "hidden",
                    }
                ],
                "mechanism_effect_ranking": [
                    {
                        "rank": 1,
                        "mechanism_family": "safe_family",
                        "effect_status": "positive_seed",
                        "summary": "safe ranking summary",
                        "recommended_action": "safe ranking action",
                        "reason_codes": ["SAFE_RANKING"],
                        "raw_pair_rows": [{"case": "hidden-ranking-row"}],
                        "bks_gap_details": "hidden-ranking-bks-gap",
                        "validation_case_details": "hidden-ranking-validation",
                    }
                ],
            }

    payload = _problem_measurement_diagnostics(
        _Spec(), adapter=_Adapter()  # type: ignore[arg-type]
    )
    projected = payload["opportunity_diagnostics"][0]
    rendered_payload = json.dumps(payload, sort_keys=True, default=str)
    compact = filter_hypothesis_context_for_prompt(
        {
            "problem_summary": "CVRP formal solver-design objective.",
            "research_surfaces": "Research surfaces: solver_design",
            "operator_categories": "solver_design",
            "available_actions": "modify",
            "targetable_files": "policies/baseline_algorithm.py",
            "champion_operators_code": "def solve():\n    return best\n",
            "champion_stats": "champion_v1",
            "problem_measurement_diagnostics": payload,
        }
    )["problem_measurement_diagnostics"]

    assert projected == {
        "diagnostic_type": "measurement_power",
        "surface": "solver_design",
        "summary": "proposal-only low-SNR guidance",
        "recommended_action": "use direct objective-effect evidence",
        "reason_codes": ["LOW_SNR"],
    }
    assert payload["mechanism_effect_ranking"][0]["mechanism_family"] == "safe_family"
    assert "SAFE_RANKING" in compact
    assert "safe proposal planning summary" in rendered_payload
    assert "keep this adapter note" in rendered_payload
    assert "LOW_SNR" in compact
    for forbidden in (
        "raw_pair_rows",
        "hidden-nested-row",
        "pair_evidence",
        "hidden-pair-evidence",
        "bks_gap_details",
        "hidden-bks-gap",
        "hidden-ranking-row",
        "hidden-ranking-bks-gap",
        "hidden-ranking-validation",
        "prompt_ratios",
        "research_signal_ratio",
        "llm_text",
        "hidden free-form llm text",
        "validation_case_details",
        "frozen_case_details",
    ):
        assert forbidden not in rendered_payload
        assert forbidden not in compact
