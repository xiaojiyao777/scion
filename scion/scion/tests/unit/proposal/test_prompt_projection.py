from __future__ import annotations

import inspect
import json

import pytest

from scion.proposal import prompt_projection as subject
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.tests.unit.editable_source_context_test_support import editable_code_context


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
    return editable_code_context(
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
    snapshot = freeze_proposal_context(kind, context)

    projection = subject.project_prompt(kind, snapshot)

    expected = snapshot.provider_context(include_renderer_inputs=True)
    assert projection.structured_context == expected
    assert projection.system_blocks
    assert projection.user_prompt
    assert json.loads(projection.structured_context_json) == expected


def test_direct_v3_canonical_blocks_are_lossless_compact_and_deterministic() -> None:
    splitter = _split_hypothesis_context
    context = {
        "problem_summary": "Caf\u00e9\nrouting control.",
        "champion_stats": {"coordinates": (1, 2)},
        "branch_id": "branch-canonical-json",
        "experiment_history": [
            {
                "labels": {"beta", "alpha"},
                "payload": b"\x00\xff",
            }
        ],
    }

    first_blocks, first_user_prompt = splitter(context)
    second_blocks, second_user_prompt = splitter(context)

    assert first_blocks == second_blocks
    assert first_user_prompt == second_user_prompt
    decoded_context = {}
    rendered_bodies = []
    for index in (1, 2):
        body = first_blocks[index]["text"].split("\n", 1)[1]
        decoded = json.loads(body)
        assert "\n" not in body
        assert body == json.dumps(
            decoded,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        decoded_context.update(decoded)
        rendered_bodies.append(body)

    assert "\\u00e9" in "".join(rendered_bodies)
    assert decoded_context["problem_summary"] == "Caf\u00e9\nrouting control."
    assert decoded_context["champion_stats"]["coordinates"] == {
        "__scion_tuple__": [1, 2]
    }
    assert decoded_context["experiment_history"][0]["labels"] == {
        "__scion_set__": ["alpha", "beta"]
    }
    assert decoded_context["experiment_history"][0]["payload"] == {
        "__scion_bytes_hex__": "00ff"
    }

    with pytest.raises(TypeError, match="non-finite float"):
        splitter({"problem_summary": float("nan")})


def test_code_canonical_block_contains_only_research_core() -> None:
    context = _code_context()
    context["editable_source_context"]["target_api_guidance"] = "Café API"
    context["host_only_marker"] = "must-not-reach-provider"

    first_blocks, first_prompt = _split_code_context(context)
    second_blocks, second_prompt = _split_code_context(context)

    assert first_blocks == second_blocks
    assert first_prompt == second_prompt
    body = first_blocks[1]["text"].split("\n", 1)[1]
    provider_context = json.loads(body)
    assert body == json.dumps(
        provider_context,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    assert "\\u00e9" in body
    assert set(provider_context) == {
        "approved_hypothesis",
        "editable_source_context",
    }
    assert "must-not-reach-provider" not in body


def test_project_prompt_rejects_phase_mismatch_and_unknown_kind() -> None:
    snapshot = freeze_proposal_context("hypothesis", _hypothesis_context())

    with pytest.raises(ValueError, match="requires a code context snapshot"):
        subject.project_prompt("code", snapshot)
    with pytest.raises(ValueError, match="unsupported prompt kind"):
        subject.project_prompt("repair", snapshot)


def test_hypothesis_prompt_keeps_history_optional_and_non_directive() -> None:
    snapshot = freeze_proposal_context("hypothesis", _hypothesis_context())

    projection = subject.project_prompt("hypothesis", snapshot)
    system_text = "\n".join(block["text"] for block in projection.system_blocks)

    assert "algorithmically material hypothesis" in system_text
    assert "History is optional research evidence" in projection.user_prompt
    assert "cite records you actually read, or ignore it" in projection.user_prompt
    assert "does not prescribe a mechanism, action, target" in projection.user_prompt
    assert "mechanisms already evaluated in experiment_history" not in (
        projection.user_prompt
    )
    assert "current research frontier" not in projection.user_prompt
    assert "Otherwise pivot" not in projection.user_prompt


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
