from __future__ import annotations

import json

from scion.opportunity import compact_problem_opportunity_summary
from scion.proposal.context_manager.opportunity import (
    problem_opportunity_summary_from_adapter,
)
from scion.proposal.engine.hypothesis_context_profiles import (
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.engine.hypothesis_prompts import _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest


def test_problem_opportunity_summary_projection_is_tainted_and_bounded() -> None:
    payload = {
        "schema_version": "scion.problem_opportunity_summary.v1",
        "problem_family": "demo",
        "objective": "score",
        "residual_opportunity": [
            {
                "axis_id": "residual_headroom",
                "metric": "score",
                "status": "available",
                "summary": "bounded improvement remains plausible",
                "reason_codes": ["HEADROOM"],
                "raw_pair_rows": [{"case": "hidden-raw-pair"}],
            }
        ],
        "mechanism_evidence": [
            {
                "mechanism_family": "bounded_operator",
                "evidence_status": "needs_direct_effect",
                "opportunity_status": "eligible",
                "effect_status": "unknown",
                "summary": "requires direct objective effect evidence",
                "recommended_action": "measure the bounded causal path",
                "reason_codes": ["DIRECT_EFFECT_REQUIRED"],
                "pair_evidence": [{"case": "hidden-pair-evidence"}],
            }
        ],
        "protected_cases": [
            {
                "case_id": "protected-a",
                "reason": "regression sentinel",
                "required_evidence": ["objective_delta"],
                "validation_case_details": "hidden-validation-case",
            }
        ],
        "measurement": {
            "schema_version": "scion.measurement_consumer_view.v1",
            "problem_family": "demo",
            "readiness_status": "ready",
            "readiness_reason_code": "calibration_fresh",
            "runtime_model": "comparative",
            "pairing_validity": "trajectory_stable",
            "effect_metric": "score",
            "effect_unit": "relative_pct",
            "mde_at_power_80": 1.2,
            "calibration_ref": "hidden/calibration.json",
        },
        "default_avoid": [
            {
                "mechanism_family": "repeated_operator",
                "reason": "prior no-effect evidence",
            }
        ],
        "bks_gap_details": "hidden-bks-gap",
        "prompt_ratios": {"research_signal_ratio": 0.9},
        "llm_text": "hidden llm prose",
    }

    rendered = compact_problem_opportunity_summary(payload)

    assert "scion.problem_opportunity_summary.v1" in rendered
    assert "bounded_operator" in rendered
    assert "protected-a" in rendered
    assert "excluded_from_decision_features" in rendered
    for forbidden in (
        "hidden-raw-pair",
        "hidden-pair-evidence",
        "hidden-validation-case",
        "hidden/calibration.json",
        "hidden-bks-gap",
        "research_signal_ratio",
        "hidden llm prose",
    ):
        assert forbidden not in rendered


def test_problem_opportunity_adapter_summary_reaches_prompt_and_manifest() -> None:
    class _Adapter:
        def render_problem_opportunity_summary(self) -> dict[str, object]:
            return {
                "problem_family": "demo",
                "objective": "score",
                "residual_opportunity": [
                    {
                        "axis_id": "residual_headroom",
                        "metric": "score",
                        "status": "available",
                        "summary": "bounded improvement remains plausible",
                    }
                ],
                "mechanism_evidence": [
                    {
                        "mechanism_family": "bounded_operator",
                        "evidence_status": "needs_direct_effect",
                        "opportunity_status": "eligible",
                        "recommended_action": "measure the bounded causal path",
                    }
                ],
                "protected_cases": [{"case_id": "protected-a"}],
                "raw_pair_rows": [{"case": "hidden"}],
            }

    payload = problem_opportunity_summary_from_adapter(_Adapter())
    serialized = json.dumps(payload, sort_keys=True, default=str)
    context = {
        "problem_summary": "demo combinatorial optimization objective",
        "research_surfaces": "Research surfaces: operator_design",
        "operator_categories": "operator_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1",
        "problem_opportunity_summary": payload,
    }

    filtered = filter_hypothesis_context_for_prompt(context)
    rendered_summary = filtered["problem_opportunity_summary"]

    assert payload["schema_version"] == "scion.problem_opportunity_summary.v1"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert "hidden" not in serialized
    assert "bounded_operator" in rendered_summary
    assert "protected-a" in rendered_summary
    assert "excluded_from_decision_features" in rendered_summary
    assert (
        filtered["context_profile_metadata"][
            "problem_opportunity_summary_visibility"
        ]
        == "full"
    )

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(str(block["text"]) for block in system_blocks)
    rendered_prompt += "\n" + user_prompt

    assert "## Problem Opportunity Summary" in rendered_prompt
    assert "bounded_operator" in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-problem-opportunity-summary",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert manifest["section_statuses"]["problem_opportunity_summary"][
        "block_family"
    ] == "research_signal"
    assert manifest["section_statuses"]["problem_opportunity_summary"][
        "status"
    ] == "included"
    assert manifest["block_family_accounting"]["decision_features_excluded"] is True


def test_record_only_measurement_governance_suppresses_opportunity_summary() -> None:
    filtered = filter_hypothesis_context_for_prompt(
        {
            "measurement_governance": "record_only",
            "problem_summary": "demo",
            "research_surfaces": "Research surfaces: operator_design",
            "champion_operators_code": "def solve():\n    return best\n",
            "champion_stats": "champion_v1",
            "problem_opportunity_summary": {
                "problem_family": "demo",
                "objective": "score",
                "mechanism_evidence": [
                    {
                        "mechanism_family": "hidden_operator",
                        "opportunity_status": "eligible",
                    }
                ],
            },
        }
    )

    assert "problem_opportunity_summary" not in filtered
    assert (
        filtered["context_profile_metadata"][
            "problem_opportunity_summary_visibility"
        ]
        == "suppressed"
    )
