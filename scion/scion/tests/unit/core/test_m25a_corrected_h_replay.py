"""Provider- and solver-free M25-A input and corrected-H replay."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

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
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchFinalized,
    HypothesisResearchSession,
)

from .proposal_pipeline_test_support import FakeCreative, _pipeline

_SCION_ROOT = Path(__file__).resolve().parents[4]
_CVRP_ROOT = _SCION_ROOT / "scion" / "problems" / "cvrp"
_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"
_M23_INPUT = _INPUT_ROOT / "v04-cvrp-m24-m23-aggregate-research-input.json"
_M25_INPUT = _INPUT_ROOT / "v04-cvrp-m25-m24-terminal-research-input.json"
_M25_HISTORY_PATHS = tuple(
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
    )
)
_FIXTURE_PATH = (
    _SCION_ROOT / "scion" / "tests" / "fixtures" / "m25a_corrected_h_replay.json"
)
_INPUT_SCHEMA = "scion.cvrp.prior_research_observation.input.v1"
_OUTPUT_SCHEMA = "scion.cvrp.prior_research_observation.v1"


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


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def _diagnostics(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        item["name"]: item["value"]
        for item in observation["terminal"]["failure"]["diagnostics"]
    }


def _real_m25_h_context() -> tuple[dict[str, Any], dict[str, Any]]:
    research_input = _load_research_input(_M25_INPUT)
    history = load_research_histories(
        _M25_HISTORY_PATHS,
        expected_problem_id="cvrp",
    )
    assert len(history) == 33
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    branch = Branch(
        branch_id="m25a-provider-free-context",
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
    return research_input, provider_context


def _fixture_actions(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    hypothesis = fixture["hypothesis"]
    actions: list[dict[str, Any]] = []
    for raw in fixture["actions"]:
        action = deepcopy(raw)
        if action["action"] == "finalize_hypothesis":
            hypothesis_payload = deepcopy(hypothesis)
            override = action.pop("hypothesis_text_override", None)
            if override is not None:
                hypothesis_payload["hypothesis_text"] = override
            action["hypothesis"] = hypothesis_payload
        actions.append(action)
    return actions


class _SequenceClient:
    model = "m25a-provider-free-replay"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

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
                "tool": deepcopy(tool),
                "request_kind": request_kind,
                "system_text": "\n".join(
                    str(block.get("text") or "") for block in system_blocks
                ),
            }
        )
        return deepcopy(self.responses.pop(0))


def _action_names(call: dict[str, Any]) -> set[str]:
    return {
        branch["properties"]["action"]["enum"][0]
        for branch in call["tool"]["input_schema"]["oneOf"]
    }


def _action_schema(call: dict[str, Any], action: str) -> dict[str, Any]:
    return next(
        branch
        for branch in call["tool"]["input_schema"]["oneOf"]
        if branch["properties"]["action"]["enum"] == [action]
    )


class _RepeatedInvalidCreative(FakeCreative):
    def __init__(self, repetitions: int) -> None:
        super().__init__()
        self.repetitions = repetitions
        self.contexts: list[dict[str, Any]] = []

    def generate_direct_hypothesis(self, snapshot):
        self.contexts.append(snapshot.structured_context)
        if len(self.contexts) <= self.repetitions:
            raise ProposalValidationError(
                "M25A_UNTRUSTED_REPEATED_INVALID_DETAIL_AND_IDENTITY"
            )
        return self.hypothesis


def test_m25_input_reaches_real_h_context_without_m24_identity() -> None:
    prior_input = _load_research_input(_M23_INPUT)
    research_input, context = _real_m25_h_context()

    assert research_input["observations"][:3] == prior_input["observations"]
    assert len(research_input["observations"]) == 4
    assert "M24 algorithm evidence 为 0" in research_input["current_question"]
    assert "declared population 未触达" in research_input["current_question"]

    terminal = research_input["observations"][3]
    assert terminal["schema_version"] == _INPUT_SCHEMA
    assert terminal["observation_kind"] == "framework_control_terminal"
    assert terminal["completed_stages"] == []
    assert terminal["terminal"]["stage"] == "proposal_hypothesis"
    assert terminal["terminal"]["terminal_code"] == "PROVIDER_CALL_CAP_EXHAUSTED"
    assert terminal["terminal"]["arm"] == "framework_control"
    assert terminal["terminal"]["case_id"] == "not_reached"
    assert terminal["terminal"]["seed"] == "not_reached"
    assert terminal["terminal"]["stage_metrics_produced"] is False
    assert not any(terminal["observed_outputs"].values())
    assert terminal["claim_context"]["evidence_scope"] == "framework_control_only"
    diagnostics = _diagnostics(terminal)
    assert diagnostics["terminal_reason"] == "PROVIDER_CALL_CAP_EXHAUSTED"
    assert diagnostics["provider_call_cap"] == 34
    assert diagnostics["provider_calls_used"] == 34
    assert diagnostics["valid_hypotheses"] == 0
    assert diagnostics["code_candidates"] == 0
    assert diagnostics["solver_calls"] == 0
    assert diagnostics["formal_stage_count"] == 0
    assert diagnostics["algorithm_evidence_count"] == 0
    assert diagnostics["population_reached"] is False

    normalized_keys = {_normalized_key(key) for key in _iter_keys(terminal)}
    assert not any(
        "raw" in key.split("_") or "heldout" in key.split("_")
        for key in normalized_keys
    )
    assert normalized_keys.isdisjoint(
        {
            "action",
            "change_locus",
            "mechanism",
            "patch",
            "repair",
            "surface",
            "target_file",
        }
    )
    assert all(".vrp" not in text.casefold() for text in _iter_strings(terminal))

    projected = context["prior_research_observations"]
    expected = [
        CvrpPriorResearchObservationProvider().project_prior_research_observation(
            observation=observation
        )
        for observation in research_input["observations"]
    ]
    assert projected == expected
    assert projected[3]["schema_version"] == _OUTPUT_SCHEMA
    assert projected[3]["terminal"]["case_id"] == "not_reached"
    assert projected[3]["terminal"]["seed"] == "not_reached"
    assert not any(projected[3]["observed_outputs"].values())
    assert len(_M25_HISTORY_PATHS) == 12
    assert len(context["prior_research_history"]) == 33
    assert context["research_question"] == {
        "current_question": research_input["current_question"]
    }

    _sources, histories, compact = build_hypothesis_research_corpus(context)
    assert len(histories) == 37
    assert [entry["ref"] for entry in histories] == [
        f"history-{ordinal:04d}" for ordinal in range(1, 38)
    ]
    assert [entry["kind"] for entry in histories[:4]] == [
        "prior_research_observations"
    ] * 4
    assert [entry["ordinal"] for entry in histories[:4]] == [1, 2, 3, 4]
    assert [entry["record"] for entry in histories[:4]] == projected
    assert [entry["kind"] for entry in histories[4:]] == ["prior_research_history"] * 33
    assert [entry["ordinal"] for entry in histories[4:]] == list(range(1, 34))
    assert [entry["record"] for entry in histories[4:]] == context[
        "prior_research_history"
    ]
    assert compact["prior_research_observations"] == {
        "indexed": True,
        "record_count": 4,
    }
    assert compact["prior_research_history"] == {
        "indexed": True,
        "record_count": 33,
    }


def test_corrected_h_replay_gets_enum_feedback_reads_history_and_finalizes() -> None:
    fixture = _fixture()
    input_value = _load_research_input(_M25_INPUT)
    projected_terminal = (
        CvrpPriorResearchObservationProvider().project_prior_research_observation(
            observation=input_value["observations"][3]
        )
    )
    source = fixture["source"]
    context = {
        "problem_summary": "Generic combinatorial optimization subject.",
        "branch_id": "m25a-corrected-h-replay",
        "research_surfaces": [{"name": "generic", "kind": "solver_design"}],
        "available_actions": ["modify"],
        "existing_target_files": [source["path"]],
        "champion_operators_code": (
            f"### {source['path']}\n```python\n{source['content']}```\n"
        ),
        "champion_stats": {},
        "prior_research_observations": [projected_terminal],
    }
    client = _SequenceClient(_fixture_actions(fixture))
    session = HypothesisResearchSession(
        CreativeLayer(client),
        CodeResearchLimits(max_turns=fixture["expected"]["provider_turns"]),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.hypothesis_text == fixture["hypothesis"]["hypothesis_text"]
    assert result.research_basis.read_refs == ("source-0001", "history-0001")
    assert result.research_basis.nearest_prior_refs == ("history-0001",)
    assert (
        result.research_basis.falsification_condition
        == fixture["actions"][3]["research_basis"]["falsification_condition"]
    )
    assert session.provider_calls_used == fixture["expected"]["provider_turns"]
    assert len(client.calls) == fixture["expected"]["provider_turns"]
    assert all(
        call["request_kind"] == "hypothesis_research_turn" for call in client.calls
    )

    assert "finalize_hypothesis" not in _action_names(client.calls[0])
    assert "finalize_hypothesis" not in _action_names(client.calls[1])
    assert "finalize_hypothesis" not in _action_names(client.calls[2])
    assert fixture["expected"]["feedback_reason"] in client.calls[2]["system_text"]
    assert (
        fixture["actions"][1]["hypothesis_text_override"]
        not in client.calls[2]["system_text"]
    )
    assert _action_schema(client.calls[2], "read_history")["properties"]["ref"][
        "enum"
    ] == ["history-0001"]

    final_schema = _action_schema(client.calls[3], "finalize_hypothesis")
    basis_schema = final_schema["properties"]["research_basis"]
    assert "falsification_condition" in basis_schema["required"]
    assert basis_schema["properties"]["nearest_prior_refs"]["minItems"] == 1
    assert basis_schema["properties"]["nearest_prior_refs"]["items"]["enum"] == [
        "history-0001"
    ]


def test_cross_attempt_h_rejection_summary_is_visible_sanitized_and_bounded() -> None:
    fixture = _fixture()
    repetitions = fixture["expected"]["cross_attempt_invalid_repetitions"]
    saturated = fixture["expected"]["saturated_rejection_count"]
    creative = _RepeatedInvalidCreative(repetitions)
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)

    for _ in range(repetitions):
        rejected = pipeline.generate_hypothesis(branch)
        assert rejected.proposal is None
        assert rejected.execution_outcome is not None
        assert rejected.execution_outcome.reason_code == "HYPOTHESIS_PROPOSAL_INVALID"
    accepted = pipeline.generate_hypothesis(branch)

    assert accepted.proposal is creative.hypothesis
    assert "hypothesis_rejection_summary" not in creative.contexts[0]
    assert creative.contexts[1]["hypothesis_rejection_summary"] == {
        "reason_counts": {"HYPOTHESIS_PROPOSAL_INVALID": 1},
        "last_reason": "HYPOTHESIS_PROPOSAL_INVALID",
    }
    final_summary = creative.contexts[-1]["hypothesis_rejection_summary"]
    assert final_summary == {
        "reason_counts": {"HYPOTHESIS_PROPOSAL_INVALID": saturated},
        "last_reason": "HYPOTHESIS_PROPOSAL_INVALID",
    }
    assert set(final_summary) == {"reason_counts", "last_reason"}
    assert "M25A_UNTRUSTED" not in json.dumps(creative.contexts[-1], sort_keys=True)
    saturated_summaries = [
        context["hypothesis_rejection_summary"]
        for context in creative.contexts
        if context.get("hypothesis_rejection_summary", {})
        .get("reason_counts", {})
        .get("HYPOTHESIS_PROPOSAL_INVALID")
        == saturated
    ]
    assert len(saturated_summaries) >= 2
    assert (
        len({len(json.dumps(value, sort_keys=True)) for value in saturated_summaries})
        == 1
    )
