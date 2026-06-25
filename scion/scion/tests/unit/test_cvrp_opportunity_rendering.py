from __future__ import annotations

import json
from pathlib import Path

from scion.core.models import HypothesisProposal, MechanismChange
from scion.opportunity import opportunity_evidence_commitment_from_summary
from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager.opportunity import (
    problem_opportunity_summary_from_adapter,
)
from scion.proposal.engine.code_prompts import _split_code_context
from scion.proposal.engine.hypothesis_context_profiles import (
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.engine.hypothesis_prompts import _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest


_CVRP_PROBLEM = (
    Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
)


def test_cvrp_adapter_exposes_typed_problem_opportunity_summary() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = adapter.render_problem_opportunity_summary()
    rendered = json.dumps(payload, sort_keys=True, default=str)

    assert payload["schema_version"] == "scion.problem_opportunity_summary.v1"
    assert payload["problem_family"] == "cvrp"
    assert payload["objective"] == "total_distance"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert "large_instance_intra_route_two_opt_seed" in rendered
    assert "large_instance_two_opt_objective_runtime_requirement" in rendered
    assert "elapsed wall-clock" in rendered
    assert "CMT2" in rendered
    assert "CMT4" in rendered
    assert "calibration_ref" not in rendered
    assert "pair_evidence" not in rendered
    assert "validation_case" not in rendered
    assert "frozen_case" not in rendered


def test_cvrp_problem_opportunity_summary_reaches_prompt_and_manifest() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)
    payload = problem_opportunity_summary_from_adapter(adapter)
    context = {
        "problem_summary": "CVRP formal solver-design objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1",
        "problem_opportunity_summary": payload,
    }

    filtered = filter_hypothesis_context_for_prompt(context)
    rendered_summary = filtered["problem_opportunity_summary"]

    assert "scion.problem_opportunity_summary.v1" in rendered_summary
    assert "large_instance_intra_route_two_opt_seed" in rendered_summary
    assert (
        "large_instance_two_opt_objective_runtime_requirement"
        in rendered_summary
    )
    assert "elapsed wall-clock" in rendered_summary
    assert "CVRP_LARGE_INSTANCE_TWO_OPT_SEED" in rendered_summary
    assert "CMT2" in rendered_summary
    assert "CMT4" in rendered_summary
    assert "excluded_from_decision_features" in rendered_summary
    assert "calibration_ref" not in rendered_summary
    assert "pair_evidence" not in rendered_summary
    assert "validation_case" not in rendered_summary
    assert "frozen_case" not in rendered_summary

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(str(block["text"]) for block in system_blocks)
    rendered_prompt += "\n" + user_prompt

    assert "## Problem Opportunity Summary" in rendered_prompt
    assert "large_instance_intra_route_two_opt_seed" in rendered_prompt
    assert "## Problem Measurement Diagnostics" not in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-cvrp-problem-opportunity-summary",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "problem_opportunity_summary" in manifest["section_names"]
    assert manifest["section_statuses"]["problem_opportunity_summary"][
        "block_family"
    ] == "research_signal"
    assert manifest["section_statuses"]["problem_opportunity_summary"][
        "status"
    ] == "included"
    assert manifest["block_family_accounting"]["decision_features_excluded"] is True


def test_cvrp_problem_opportunity_commitment_reaches_code_prompt_manifest() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)
    payload = problem_opportunity_summary_from_adapter(adapter)
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine bounded large-instance intra-route two-opt seed selection."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        mechanism_changes=(
            MechanismChange(
                "large_instance_intra_route_two_opt_seed",
                "modify",
            ),
        ),
    )
    commitment = opportunity_evidence_commitment_from_summary(payload, hypothesis)

    assert commitment["problem_family"] == "cvrp"
    assert commitment["decision_features_excluded"] is True
    rendered_commitment = json.dumps(commitment, sort_keys=True, default=str)
    assert "large_instance_two_opt_objective_runtime_requirement" in (
        rendered_commitment
    )
    assert "cmt2_cmt4_case_protection" in rendered_commitment
    assert "CMT2" in rendered_commitment
    assert "CMT4" in rendered_commitment
    assert "pair_evidence" not in rendered_commitment
    assert "validation_case" not in rendered_commitment
    assert "frozen_case" not in rendered_commitment

    context = {
        "problem_summary": "CVRP formal solver-design objective.",
        "problem_object": "",
        "solver_mechanics": "",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "operator_interface_spec": "def solve(instance, seed, time_limit): ...",
        "import_whitelist": "  - math",
        "hypothesis_implementation_brief": {
            "hypothesis_text": hypothesis.hypothesis_text,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "mechanism_changes": [
                {
                    "id": "large_instance_intra_route_two_opt_seed",
                    "change_type": "modify",
                }
            ],
        },
        "hypothesis_detail": "Approved CVRP large-instance two-opt hypothesis.",
        "target_file": "policies/baseline_modules/local_search.py",
        "target_file_code": "def improve(solution):\n    return solution\n",
        "target_file_exists": True,
        "champion_operators_code": "",
        "reference_operators": "",
        "editable_patterns": "policies/**/*.py",
        "frozen_patterns": "tests/*",
        "opportunity_evidence_commitment": commitment,
    }

    system_blocks, user_prompt = _split_code_context(context)
    prompt_text = "\n".join(str(block["text"]) for block in system_blocks)
    prompt_text += "\n" + user_prompt

    assert "## Opportunity Evidence Commitment" in prompt_text
    assert "large_instance_two_opt_objective_runtime_requirement" in prompt_text
    assert "cmt2_cmt4_case_protection" in prompt_text
    assert "elapsed wall-clock" in prompt_text
    assert "CMT2" in prompt_text
    assert "CMT4" in prompt_text
    assert "excluded_from_decision_features" in prompt_text

    manifest = build_api_visible_prompt_manifest(
        session_id="session-cvrp-opportunity-commitment",
        phase="draft_patch",
        call_kind="code",
        prompt_context=context,
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
