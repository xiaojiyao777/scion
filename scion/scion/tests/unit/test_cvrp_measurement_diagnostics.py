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
    reason_codes = {
        code
        for item in payload["opportunity_diagnostics"]
        for code in item["reason_codes"]
    }
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in reason_codes
    assert "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT" in reason_codes
    assert "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY" in reason_codes
    assert "validation" not in rendered.lower()
    assert "frozen" not in rendered.lower()
    assert "holdout" not in rendered.lower()
    assert "bks" not in rendered.lower()


def test_context_manager_projects_cvrp_adapter_opportunities_top_level() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    adapter = CvrpAdapter(spec_v1)

    payload = _problem_measurement_diagnostics(legacy, adapter=adapter)
    compact = filter_hypothesis_context_for_prompt(
        {
            "problem_summary": "CVRP formal solver-design objective.",
            "research_surfaces": "Research surfaces: solver_design",
            "operator_categories": "solver_design",
            "available_actions": "modify, create_new",
            "targetable_files": "policies/baseline_algorithm.py",
            "champion_operators_code": "def solve():\n    return best\n",
            "champion_stats": "champion_v1",
            "problem_measurement_diagnostics": payload,
        }
    )["problem_measurement_diagnostics"]

    assert payload["decision_features_excluded"] is True
    assert payload["runtime_model"] == "budget_exhausting"
    assert payload["pairing_validity"] == "trajectory_divergent"
    assert "opportunity_diagnostics" in payload
    assert payload["opportunity_diagnostics"][0]["diagnostic_type"] == (
        "measurement_power"
    )
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in compact
    assert "TRAJECTORY_DIVERGENT_LOW_SNR" in compact
    assert "construction seed" in compact.lower()
    assert "excluded_from_decision_features" in compact
    assert "hidden" not in compact.lower()
    assert "raw_pair_rows" not in compact
    assert "validation_case_details" not in compact
    assert "frozen_case_details" not in compact


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
                ]
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
        "prompt_ratios",
        "research_signal_ratio",
        "llm_text",
        "hidden free-form llm text",
        "validation_case_details",
        "frozen_case_details",
    ):
        assert forbidden not in rendered_payload
        assert forbidden not in compact
