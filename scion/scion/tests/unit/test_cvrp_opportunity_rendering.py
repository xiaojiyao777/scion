from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager.opportunity import (
    problem_opportunity_summary_from_adapter,
)
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
