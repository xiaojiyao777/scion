from __future__ import annotations

import json
from typing import Any

from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.engine.hypothesis_prompts import _direct_v3_canonical_json
from scion.proposal.prompt_projection import project_prompt


def _mapping_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_mapping_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_mapping_keys(child) for child in value))
    return set()


def test_h_provider_receives_research_core_while_snapshot_remains_complete() -> None:
    context = {
        "problem_summary": "Minimise distance while preserving feasibility.",
        "problem_object": {
            "invariants": ["capacity", "fleet"],
            "schema_version": "problem.v2",
        },
        "solver_mechanics": {"algorithm": "ALNS+VNS"},
        "objective_policy_guidance": {"direction": "minimize"},
        "research_surfaces": [
            {
                "name": "solver_design",
                "target_files": ["policies/scheduler.py"],
                "allowed_actions": ["modify"],
            }
        ],
        "available_actions": ["modify"],
        "existing_target_files": ["policies/scheduler.py"],
        "create_path_patterns": [],
        "champion_operators_code": "def solve(): return 'champion'\n",
        "branch_current_code": "def solve(): return 'current'\n",
        "champion_stats": {"version": 7, "algorithm": "ALNS+VNS"},
        "problem_measurement_diagnostics": {
            "screening_signal": "phase starvation",
        },
        "experiment_history": [
            {
                "case": "P-n65-k10",
                "candidate_distance": 111.0,
                "control_distance": 113.0,
            },
            {
                "case": "X-n120-k6",
                "candidate_distance": 222.0,
                "control_distance": 225.0,
            },
        ],
        "research_question": {
            "current_question": "How should useful search time be allocated?",
        },
        "prior_research_observations": [
            {"finding": "Inspect current source and paired evidence."}
        ],
        "proposal_renderer_inputs": {
            "solver_design_prompt_guidance": {
                "hypothesis_guidance": ["Choose one causal algorithm path."],
                "schema_version": "guidance.v1",
            }
        },
        "branch_id": "branch-host-only",
        "champion_version": 7,
    }
    snapshot = freeze_proposal_context("hypothesis", context)
    projection = project_prompt("hypothesis", snapshot)
    raw = projection.structured_context
    assert raw["branch_id"] == "branch-host-only"
    assert raw["champion_version"] == 7
    assert raw["research_question"]["current_question"] == (
        "How should useful search time be allocated?"
    )
    assert raw["champion_stats"]["version"] == 7

    provider: dict[str, Any] = {}
    for block in projection.system_blocks[1:]:
        provider.update(json.loads(block["text"].split("\n", 1)[1]))

    assert not _mapping_keys(provider).intersection(
        {
            "branch_id",
            "champion_version",
            "schema_version",
            "problem_family",
        }
    )
    assert provider["problem_object"]["invariants"] == ["capacity", "fleet"]
    assert provider["solver_mechanics"] == {"algorithm": "ALNS+VNS"}
    assert provider["objective_policy_guidance"] == {"direction": "minimize"}
    assert provider["research_surfaces"][0]["target_files"] == ["policies/scheduler.py"]
    assert provider["available_actions"] == ["modify"]
    assert provider["champion_operators_code"].endswith("'champion'\n")
    assert provider["branch_current_code"].endswith("'current'\n")
    assert provider["champion_stats"] == {"algorithm": "ALNS+VNS"}
    assert [item["case"] for item in provider["experiment_history"]] == [
        "P-n65-k10",
        "X-n120-k6",
    ]
    assert provider["experiment_history"][1]["control_distance"] == 225.0
    assert provider["research_question"] == {
        "current_question": "How should useful search time be allocated?",
    }
    assert provider["prior_research_observations"] == [
        {"finding": "Inspect current source and paired evidence."}
    ]
    assert "last_research_rejection" not in provider


def test_shared_canonical_json_does_not_strip_code_metadata() -> None:
    assert json.loads(
        _direct_v3_canonical_json(
            {
                "editable_source_context": {
                    "schema_version": "source.v1",
                    "source_role": "editable",
                }
            }
        )
    )["editable_source_context"] == {
        "schema_version": "source.v1",
        "source_role": "editable",
    }
