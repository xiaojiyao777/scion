from __future__ import annotations

import json

from scion.core.models import HypothesisProposal, MechanismChange
from scion.opportunity import compact_problem_opportunity_summary
from scion.opportunity.commitment import (
    compact_opportunity_evidence_commitment,
    opportunity_evidence_commitment_from_summary,
)
from scion.proposal.context_manager.opportunity import (
    problem_opportunity_summary_from_adapter,
)
from scion.proposal.engine.code_prompts import _split_code_context
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


def test_problem_opportunity_commitment_reaches_code_prompt_and_manifest() -> None:
    summary = {
        "schema_version": "scion.problem_opportunity_summary.v1",
        "problem_family": "demo",
        "objective": "score",
        "evidence_requirements": [
            {
                "requirement_id": "bounded_operator_required_evidence",
                "mechanism_family": "bounded_operator",
                "status": "current_run_required",
                "summary": "Measure the bounded operator before claiming progress.",
                "recommended_action": "implement a bounded causal path",
                "required_observations": [
                    "paired objective delta",
                    "feasibility status",
                ],
                "protected_cases": ["protected-a"],
                "reason_codes": ["DIRECT_EFFECT_REQUIRED"],
                "raw_pair_rows": [{"hidden": True}],
            },
            {
                "requirement_id": "unselected_required_evidence",
                "mechanism_family": "other_operator",
                "summary": "Should not be selected by this hypothesis.",
            },
        ],
        "pair_evidence": [{"hidden": True}],
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded operator.",
        change_locus="operator_design",
        action="modify",
        target_file="policies/baseline.py",
        mechanism_changes=(MechanismChange("bounded_operator", "modify"),),
    )

    commitment = opportunity_evidence_commitment_from_summary(summary, hypothesis)
    rendered = compact_opportunity_evidence_commitment(commitment)

    assert commitment["schema_version"] == (
        "scion.problem_opportunity_evidence_commitment.v1"
    )
    assert commitment["selected_mechanism_ids"] == ["bounded_operator"]
    assert commitment["requirements"][0]["requirement_id"] == (
        "bounded_operator_required_evidence"
    )
    assert "other_operator" not in json.dumps(commitment, sort_keys=True)
    assert "hidden" not in json.dumps(commitment, sort_keys=True)
    assert "paired objective delta" in rendered
    assert "excluded_from_decision_features" in rendered

    system_blocks, user_prompt = _split_code_context(
        _minimal_code_context(commitment)
    )
    prompt_text = "\n".join(str(block["text"]) for block in system_blocks)
    prompt_text += "\n" + user_prompt

    assert "## Opportunity Evidence Commitment" in prompt_text
    assert "bounded_operator_required_evidence" in prompt_text
    assert "paired objective delta" in prompt_text
    assert "hidden" not in prompt_text

    manifest = build_api_visible_prompt_manifest(
        session_id="session-demo-opportunity-commitment",
        phase="draft_patch",
        call_kind="code",
        prompt_context=_minimal_code_context(commitment),
        observations=[],
        call_index=2,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "opportunity_evidence_commitment" in manifest["section_names"]
    assert manifest["section_statuses"]["opportunity_evidence_commitment"][
        "block_family"
    ] == "research_signal"
    assert manifest["section_statuses"]["opportunity_evidence_commitment"][
        "status"
    ] == "included"


def _minimal_code_context(commitment: dict[str, object]) -> dict[str, object]:
    return {
        "problem_summary": "Demo combinatorial optimization objective.",
        "problem_object": "",
        "solver_mechanics": "",
        "research_surface_name": "operator_design",
        "research_surface_kind": "operator",
        "change_locus": "operator_design",
        "operator_interface_spec": "def apply(solution, rng): ...",
        "import_whitelist": "  - math",
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Try a bounded operator.",
            "change_locus": "operator_design",
            "action": "modify",
            "target_file": "policies/baseline.py",
            "mechanism_changes": [
                {"id": "bounded_operator", "change_type": "modify"}
            ],
        },
        "hypothesis_detail": "Approved generic bounded-operator hypothesis.",
        "target_file": "policies/baseline.py",
        "target_file_code": "def apply(solution, rng):\n    return solution\n",
        "target_file_exists": True,
        "champion_operators_code": "",
        "reference_operators": "",
        "editable_patterns": "policies/*.py",
        "frozen_patterns": "tests/*",
        "opportunity_evidence_commitment": commitment,
    }


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
