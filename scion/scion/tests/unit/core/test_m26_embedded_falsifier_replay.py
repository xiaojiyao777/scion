"""Provider- and solver-free M26 context and embedded-falsifier replay."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scion.cli.commands.init_run import _load_research_input
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.research_history import load_research_histories
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)
from scion.proposal.code_research_session import CodeResearchSession
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
)
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
)

_SCION_ROOT = Path(__file__).resolve().parents[4]
_CVRP_ROOT = _SCION_ROOT / "scion" / "problems" / "cvrp"
_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"
_M25_INPUT = _INPUT_ROOT / "v04-cvrp-m25-m24-terminal-research-input.json"
_M26_INPUT = _INPUT_ROOT / "v04-cvrp-m26-m25-terminal-research-input.json"
_M26_HISTORY_PATHS = tuple(
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
    )
)
_FIXTURE_PATH = (
    _SCION_ROOT / "scion" / "tests" / "fixtures" / "m26_embedded_falsifier_replay.json"
)


def _fixture() -> dict[str, Any]:
    value = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


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


class _SequenceClient:
    model = "m26-provider-free-replay"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def call_with_tool(
        self,
        prompt: str,
        tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "prompt": prompt,
                "request_kind": request_kind,
                "system_text": "\n".join(
                    str(block.get("text") or "") for block in system_blocks
                ),
            }
        )
        return deepcopy(self.responses.pop(0))


def test_m26_real_context_keeps_native_audit_and_filters_provider_history() -> None:
    fixture = _fixture()
    prior_input = _load_research_input(_M25_INPUT)
    research_input = _load_research_input(_M26_INPUT)
    history = load_research_histories(
        _M26_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )

    assert research_input["observations"][:4] == prior_input["observations"]
    assert all(
        campaign in research_input["current_question"]
        for campaign in ("M7", "M18", "M23", "M24", "M25")
    )
    assert (
        len(research_input["observations"]) == fixture["expected"]["prior_observations"]
    )
    assert len(_M26_HISTORY_PATHS) == 13
    assert len(history) == fixture["expected"]["native_history"]
    assert [
        record["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"]
        for record in history[-2:]
    ] == [
        "expand",
        "fail",
    ]
    assert history[-1]["decision"]["value"] == "abandon"

    terminal = research_input["observations"][4]
    assert terminal["observation_kind"] == "autonomous_candidate_evaluation_terminal"
    assert (
        terminal["claim_context"][
            "population_selection_outcome_blind_relative_to_exact_estimand"
        ]
        is False
    )
    assert terminal["claim_context"]["incremental_effect_isolated"] is False
    assert terminal["claim_context"]["globally_case_unseen"] is False
    serialized_public_context = json.dumps(
        {
            "current_question": research_input["current_question"],
            "m25_terminal": terminal,
        },
        sort_keys=True,
    ).casefold()
    forbidden = {
        "raw",
        "provider_response",
        "trace",
        "research_basis",
        "falsifier_source",
        "editable_source",
    }
    assert {key.casefold() for key in _iter_keys(terminal)}.isdisjoint(forbidden)
    assert all(marker not in serialized_public_context for marker in forbidden)
    assert all(
        case_id.casefold() not in serialized_public_context
        for case_id in (
            "P-n55-k7",
            "X-n308-k13",
            "X-n548-k50",
            "X-n275-k28",
            "X-n480-k70",
            "X-n876-k59",
        )
    )
    assert {5405, 4354, 2959, 6748}.isdisjoint(set(_iter_scalars(terminal)))

    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    branch = Branch(
        branch_id="m26-provider-free-context",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(_CVRP_ROOT),
    )
    context = ContextManager(
        adapter=adapter,
        research_input=research_input,
        research_history=history,
    ).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy_problem_spec_from_v1(spec),
    )
    provider_context = freeze_proposal_context("hypothesis", context).provider_context()
    _, histories, compact = build_hypothesis_research_corpus(provider_context)

    assert len(histories) == fixture["expected"]["provider_history_entries"]
    assert [entry["kind"] for entry in histories[:5]] == [
        "prior_research_observations"
    ] * 5
    assert [entry["kind"] for entry in histories[5:]] == [
        "prior_research_history"
    ] * fixture["expected"]["provider_scientific_history"]
    assert compact["prior_research_observations"]["record_count"] == 5
    assert compact["prior_research_history"]["record_count"] == fixture["expected"][
        "provider_scientific_history"
    ]
    assert histories[4]["record"] == (
        CvrpPriorResearchObservationProvider().project_prior_research_observation(
            observation=terminal
        )
    )


def test_m26_h1_h2_history_indexes_remain_complete_without_host_ranking() -> None:
    fixture = _fixture()
    research_input = _load_research_input(_M26_INPUT)
    history = load_research_histories(
        _M26_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    context = ContextManager(
        adapter=CvrpAdapter(spec),
        research_input=research_input,
        research_history=history,
    ).build_hypothesis_context(
        branch=Branch(
            branch_id="m26-nearest-history-replay",
            state=BranchState.EXPLORE,
            base_champion_id=1,
        ),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(_CVRP_ROOT),
        ),
        problem_spec=legacy_problem_spec_from_v1(spec),
    )
    provider_context = freeze_proposal_context("hypothesis", context).provider_context()
    expected_refs = fixture["expected"]["nearest_history_refs"]

    _, h1_histories, _ = build_hypothesis_research_corpus(provider_context)
    h1_by_ref = {entry["ref"]: entry for entry in h1_histories}
    assert h1_by_ref["history-0021"]["index"]["hypothesis"] == h1_by_ref[
        expected_refs[0]
    ]["index"]["hypothesis"]
    assert expected_refs[0] == "history-0022"
    assert expected_refs[0] in {entry["ref"] for entry in h1_histories}

    h2_context = deepcopy(provider_context)
    h2_context["experiment_history"] = [
        {
            "latest_round": 1,
            "relation": "current",
            "proposal_intent": fixture["nearest_history_candidates"][0],
        }
    ]
    _, h2_histories, _ = build_hypothesis_research_corpus(h2_context)
    assert len(h2_histories) == fixture["expected"]["provider_history_entries"] + 1
    assert expected_refs[1] == "history-0023"
    assert expected_refs[1] in {entry["ref"] for entry in h2_histories}


def test_m26_failed_falsifier_is_fail_closed_and_source_is_not_replayed() -> None:
    fixture = _fixture()
    source = fixture["source"]
    probe = fixture["falsifier"]
    client = _SequenceClient(fixture["actions"])
    session = CodeResearchSession(
        CreativeLayer(client),
        CodeResearchLimits(max_turns=3),
    )
    observed_probe_sources: list[str | None] = []

    def _test_patch(_patch, _remaining, _corpus, falsifier_source):
        observed_probe_sources.append(falsifier_source)
        return {
            "outcome": "passed",
            "falsifier_outcome": probe["reported_outcome"],
            "checks": [{"name": "D3_unit_tests", "outcome": "passed"}],
            "counts": {"total": 1, "passed": 1, "failed": 0},
        }

    session._test_patch = _test_patch
    snapshot = build_prompt_turn_snapshot(
        "code",
        {
            "problem_summary": "Generic bounded optimization subject.",
            "branch_id": "m26-provider-free-code-replay",
            "approved_hypothesis": fixture["hypothesis"],
            "editable_source_context": {
                "approved_target": source["path"],
                "sources": [
                    {
                        "path": source["path"],
                        "content": source["content"],
                        "roles": ["target"],
                        "visible": True,
                    }
                ],
                "public_tests": [],
                "target_api_guidance": "Preserve the public callable.",
            },
            "operator_interface_spec": "",
            "editable_patterns": "operators/*.py",
            "frozen_patterns": "",
        },
    )

    with pytest.raises(
        ProposalValidationError,
        match="falsifier-rejected draft",
    ):
        session.run(snapshot)

    assert observed_probe_sources == [probe["source"]]
    assert len(client.calls) == fixture["expected"]["code_research_provider_calls"]
    for call in client.calls[2:]:
        assert probe["source"] not in call["system_text"]
        assert "M26_PRIVATE_FALSIFIER_SENTINEL" not in call["system_text"]
        assert "falsifier_source" not in call["system_text"]
    assert '"falsifier_outcome":"failed"' in client.calls[2]["system_text"]
