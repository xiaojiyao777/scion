from __future__ import annotations

import inspect
import json

import pytest

from scion.proposal import prompt_projection as subject
from scion.proposal.context_owner_maps import proposal_context_snapshot

from scion.tests.unit.source_ledger_test_support import ledgerize_code_context


def _hypothesis_context() -> dict:
    return {
        "problem_summary": "Synthetic routing control.",
        "research_surfaces": [
            {"name": "local_search", "kind": "operator"},
        ],
        "champion_operators_code": "class Control: pass",
        "champion_stats": {"version": 1},
        "branch_id": "branch-pure-projection",
        "experiment_history": [],
    }


def _code_context() -> dict:
    return ledgerize_code_context(
        {
            "problem_summary": "Synthetic routing control.",
            "branch_id": "branch-pure-projection",
            "target_file": "operators/move.py",
            "target_file_code": "def move(solution):\n    return solution\n",
            "action": "modify",
            "approved_hypothesis": {
                "hypothesis_text": "Improve one local move.",
                "change_locus": "local_search",
                "action": "modify",
                "target_file": "operators/move.py",
                "predicted_direction": "improve",
                "target_weakness": "The current move is weak.",
                "expected_effect": "Improve the objective.",
            },
            "operator_interface_spec": "def move(solution): ...",
            "editable_patterns": ["operators/*.py"],
            "frozen_patterns": ["solver.py"],
        }
    )


@pytest.mark.parametrize(
    ("kind", "context"),
    [
        ("hypothesis", _hypothesis_context()),
        ("code", _code_context()),
    ],
)
def test_project_prompt_is_a_pure_value_projection(
    kind: str,
    context: dict,
) -> None:
    snapshot = proposal_context_snapshot(kind, context)

    projection = subject.project_prompt(kind, snapshot)

    expected = snapshot.inputs.provider_context(include_renderer_inputs=True)
    assert projection.structured_context == expected
    assert projection.system_blocks
    assert projection.user_prompt
    assert json.loads(projection.structured_context_json) == expected


def test_project_prompt_rejects_phase_mismatch_and_unknown_kind() -> None:
    snapshot = proposal_context_snapshot("hypothesis", _hypothesis_context())

    with pytest.raises(ValueError, match="requires a code context snapshot"):
        subject.project_prompt("code", snapshot)
    with pytest.raises(ValueError, match="unsupported prompt kind"):
        subject.project_prompt("repair", snapshot)


def test_hypothesis_prompt_requests_material_evidence_grounded_refinement() -> None:
    snapshot = proposal_context_snapshot("hypothesis", _hypothesis_context())

    projection = subject.project_prompt("hypothesis", snapshot)
    system_text = "\n".join(block["text"] for block in projection.system_blocks)

    assert "algorithmically material hypothesis" in system_text
    assert (
        "one evidence-grounded mechanism-level change or refinement"
        in projection.user_prompt
    )
    assert "materially different mechanism" not in projection.user_prompt


def test_prompt_projection_has_no_authority_or_capability_dependency() -> None:
    source = inspect.getsource(subject)

    for forbidden in (
        "hypothesis_generation_authority",
        "AuthorityHandle",
        "bind_hypothesis_prompt",
        "_claim_",
        "_issue_",
    ):
        assert forbidden not in source
