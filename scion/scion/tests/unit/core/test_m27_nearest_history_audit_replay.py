"""Provider- and solver-free M27 context and nearest-history audit replay."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from scion.cli.commands.init_run import _load_research_input
from scion.core.code_research_limits import load_code_research_limits
from scion.core.research_history import (
    load_research_histories,
    provider_research_history,
)
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.engine import build_prompt_turn_snapshot
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
)
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchFinalized,
    HypothesisResearchSession,
)

_SCION_ROOT = Path(__file__).resolve().parents[4]
_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"
_M26_INPUT = _INPUT_ROOT / "v04-cvrp-m26-m25-terminal-research-input.json"
_M27_INPUT = _INPUT_ROOT / "v04-cvrp-m27-m26-terminal-research-input.json"
_M27_HISTORY_COPY = _INPUT_ROOT / "v04-cvrp-m27-m26-research-history.jsonl"
_M27_HISTORY_PATHS = tuple(
    _INPUT_ROOT / filename
    for filename in (
        "v04-cvrp-m10-m9-research-history.jsonl",
        "v04-cvrp-m11-m10-research-history.jsonl",
        "v04-cvrp-m12-m11-research-history.jsonl",
        "v04-cvrp-m13-m12-research-history.jsonl",
        "v04-cvrp-m14-m13-research-history.jsonl",
        "v04-cvrp-m15-m14-research-history.jsonl",
        "v04-cvrp-m16-m15-research-history.jsonl",
        "v04-cvrp-m19-m16-research-history.jsonl",
        "v04-cvrp-m20-m19-research-history.jsonl",
        "v04-cvrp-m21-m20-research-history.jsonl",
        "v04-cvrp-m22-m21-research-history.jsonl",
        "v04-cvrp-m24-m22-research-history.jsonl",
        "v04-cvrp-m26-m25-research-history.jsonl",
        "v04-cvrp-m27-m26-research-history.jsonl",
    )
)
_LIMITS_PATH = _INPUT_ROOT / "v04-cvrp-m11-code-research-limits.json"
_FIXTURE_PATH = (
    _SCION_ROOT
    / "scion"
    / "tests"
    / "fixtures"
    / "m27_nearest_history_audit_replay.json"
)


def _fixture() -> dict[str, Any]:
    value = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_keys(child)


def _iter_scalars(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_scalars(child)
    else:
        yield value


def _diagnostics(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        item["name"]: item["value"]
        for item in observation["terminal"]["failure"]["diagnostics"]
    }


def _provider_context(
    fixture: dict[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], dict[str, Any]]:
    research_input = _load_research_input(_M27_INPUT)
    history = load_research_histories(
        _M27_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )
    projector = CvrpPriorResearchObservationProvider()
    observations = [
        projector.project_prior_research_observation(observation=observation)
        for observation in research_input["observations"]
    ]
    source = fixture["source"]
    context = {
        "problem_summary": "Generic bounded optimization subject.",
        "branch_id": "m27-provider-free-nearest-history-audit",
        "research_surfaces": [{"name": "solver_design", "kind": "generic_algorithm"}],
        "available_actions": ["modify"],
        "existing_target_files": [source["path"]],
        "champion_operators_code": (
            f"### {source['path']}\n```python\n{source['content']}```\n"
        ),
        "champion_stats": {},
        "prior_research_observations": observations,
        "prior_research_history": provider_research_history(history),
        "research_question": {"current_question": research_input["current_question"]},
    }
    return research_input, history, context


def _basis(
    fixture: dict[str, Any],
    *,
    read_refs: list[str],
    nearest_prior_refs: list[str],
) -> dict[str, Any]:
    return {
        "read_refs": read_refs,
        "nearest_prior_refs": nearest_prior_refs,
        **deepcopy(fixture["research_basis"]),
    }


def _action_names(snapshot) -> set[str]:
    return {
        branch["properties"]["action"]["enum"][0]
        for branch in snapshot.provider_tool["input_schema"]["oneOf"]
    }


class _SequenceCreative:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.contexts: list[dict[str, Any]] = []
        self.snapshots = []

    def call_hypothesis_research_turn(self, snapshot):
        self.snapshots.append(snapshot)
        self.contexts.append(deepcopy(snapshot.structured_context))
        return deepcopy(self.responses.pop(0))


def test_m27_real_context_keeps_native_audit_and_filters_provider_history() -> None:
    fixture = _fixture()
    prior_input = _load_research_input(_M26_INPUT)
    research_input, history, context = _provider_context(fixture)
    expected = fixture["expected"]

    assert research_input["observations"][:5] == prior_input["observations"]
    assert len(research_input["observations"]) == expected["prior_observations"]
    assert len(_M27_HISTORY_PATHS) == expected["history_files"]
    assert len(history) == expected["native_history"]

    copied_bytes = _M27_HISTORY_COPY.read_bytes()
    assert len(copied_bytes) == expected["m26_history_bytes"]
    assert copied_bytes.count(b"\n") == expected["m26_history_lines"]
    canonical_m26 = load_research_histories(
        (_M27_HISTORY_COPY,),
        expected_problem_id="cvrp",
    )
    assert history[-2:] == canonical_m26
    assert [
        record["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"]
        for record in canonical_m26
    ] == ["fail", "fail"]
    assert [record["decision"]["value"] for record in canonical_m26] == [
        "continue_explore",
        "continue_explore",
    ]

    _sources, indexed_history, compact = build_hypothesis_research_corpus(context)
    assert len(indexed_history) == expected["provider_history_entries"]
    assert [entry["ref"] for entry in indexed_history] == [
        f"history-{ordinal:04d}"
        for ordinal in range(1, expected["provider_history_entries"] + 1)
    ]
    assert [entry["ref"] for entry in indexed_history[:6]] == expected[
        "provider_observation_refs"
    ]
    assert [entry["kind"] for entry in indexed_history[:6]] == [
        "prior_research_observations"
    ] * 6
    assert [entry["kind"] for entry in indexed_history[6:]] == [
        "prior_research_history"
    ] * expected["provider_scientific_history"]
    assert [entry["ref"] for entry in indexed_history[-2:]] == expected[
        "m26_history_provider_refs"
    ]
    assert [entry["record"] for entry in indexed_history[-2:]] == (
        context["prior_research_history"][-2:]
    )
    assert compact["prior_research_observations"]["record_count"] == 6
    assert compact["prior_research_history"]["record_count"] == expected[
        "provider_scientific_history"
    ]
    eligible_fields = (
        "text",
        "hypothesis_text",
        "target_file",
        "change_locus",
        "action",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
    )
    eligible = [
        entry
        for entry in indexed_history
        if isinstance(entry["index"].get("hypothesis"), dict)
        and any(
            isinstance(entry["index"]["hypothesis"].get(field), str)
            and bool(entry["index"]["hypothesis"][field].strip())
            for field in eligible_fields
        )
    ]
    assert len(eligible) == expected["eligible_headline_entries"]
    assert [entry["ref"] for entry in eligible] == [
        f"history-{ordinal:04d}"
        for ordinal in range(7, expected["provider_history_entries"] + 1)
    ]


def test_m27_terminal_observation_is_strict_aggregate_public_context() -> None:
    fixture = _fixture()
    research_input, _history, context = _provider_context(fixture)
    terminal = research_input["observations"][5]
    projected = context["prior_research_observations"][5]

    assert terminal["observation_kind"] == "autonomous_candidate_evaluation_terminal"
    assert [stage["block"] for stage in terminal["completed_stages"]] == [
        "initial",
        "initial",
    ]
    assert [stage["valid_pairs"] for stage in terminal["completed_stages"]] == [6, 6]
    assert [
        stage["case_outcomes"]["ci_low"] for stage in terminal["completed_stages"]
    ] == [
        -61.5,
        -90.5,
    ]
    diagnostics = _diagnostics(terminal)
    assert diagnostics["provider_calls_used"] == 15
    assert diagnostics["hypothesis_research_calls"] == 7
    assert diagnostics["code_research_calls"] == 6
    assert diagnostics["code_final_decision_calls"] == 2
    assert diagnostics["solver_calls"] == 32
    assert diagnostics["formal_stage_count"] == 2
    assert diagnostics["initial_screen_valid_pairs"] == 12
    assert diagnostics["validation_reached"] is False
    assert diagnostics["frozen_reached"] is False
    assert projected["observed_outputs"] == {
        "terminal_stage_metrics": True,
        "terminal_safe_features": True,
        "terminal_decision": True,
        "later_stage_metrics": False,
        "promotion": False,
        "retained_baseline_comparison": False,
    }
    claim = terminal["claim_context"]
    assert (
        claim["population_selection_outcome_blind_relative_to_exact_estimand"] is False
    )
    assert claim["incremental_effect_isolated"] is False
    assert claim["globally_case_unseen"] is False
    # This is one prior exact-candidate outcome overlap, not population/case overlap.
    assert claim["exact_candidate_outcome_overlap_count"] == 1

    normalized_keys = {_normalized_key(key) for key in _iter_keys(terminal)}
    assert normalized_keys.isdisjoint(
        {
            "action",
            "change_locus",
            "editable_source",
            "falsifier_source",
            "mechanism",
            "patch",
            "provider_response",
            "provider_trace",
            "repair",
            "research_basis",
            "surface",
            "target_file",
        }
    )
    strings = [value for value in _iter_scalars(terminal) if isinstance(value, str)]
    assert all(".vrp" not in value.casefold() for value in strings)
    assert all("policies/" not in value.casefold() for value in strings)
    assert {5405, 4354, 2959, 6748}.isdisjoint(set(_iter_scalars(terminal)))
    question = research_input["current_question"]
    prior_targets = {
        record["hypothesis"].get("target_file")
        for record in context["prior_research_history"]
        if isinstance(record.get("hypothesis"), dict)
    }
    assert all(target not in question for target in prior_targets if target)


def test_m27_actual_context_allows_finalize_without_host_routed_history() -> None:
    fixture = _fixture()
    _research_input, _history, context = _provider_context(fixture)
    first_basis = _basis(
        fixture,
        read_refs=["source-0001"],
        nearest_prior_refs=[],
    )
    creative = _SequenceCreative(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": fixture["hypothesis"],
                "research_basis": first_basis,
            },
        ]
    )
    session = HypothesisResearchSession(
        creative,
        load_code_research_limits(_LIMITS_PATH),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.research_basis.read_refs == ("source-0001",)
    assert result.research_basis.nearest_prior_refs == ()
    assert session.provider_calls_used == 2
    assert len(creative.contexts) == 2
    assert "finalize_hypothesis" not in _action_names(creative.snapshots[0])
    assert "finalize_hypothesis" in _action_names(creative.snapshots[1])
    assert "required_history_ref" not in json.dumps(creative.contexts, sort_keys=True)


def test_m27_actual_context_accepts_an_agent_selected_history_read() -> (
    None
):
    fixture = _fixture()
    _research_input, _history, context = _provider_context(fixture)
    _sources, indexed_history, _compact = build_hypothesis_research_corpus(context)
    required_ref = fixture["expected"]["generic_fake_h_required_ref"]
    assert required_ref in {entry["ref"] for entry in indexed_history}
    accepted_basis = _basis(
        fixture,
        read_refs=["source-0001", required_ref],
        nearest_prior_refs=[required_ref],
    )
    creative = _SequenceCreative(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": required_ref},
            {
                "action": "finalize_hypothesis",
                "hypothesis": fixture["hypothesis"],
                "research_basis": accepted_basis,
            },
        ]
    )
    session = HypothesisResearchSession(
        creative,
        load_code_research_limits(_LIMITS_PATH),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.research_basis.nearest_prior_refs == (required_ref,)
    assert session.provider_calls_used == 3
    tool_results = creative.contexts[-1]["hypothesis_research"]["tool_results"]
    assert [result["action"] for result in tool_results] == [
        "read_source",
        "read_history",
    ]
    assert all(
        result.get("reason") != fixture["expected"]["feedback_reason"]
        for result in tool_results
    )
