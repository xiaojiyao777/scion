from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    StepRecord,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.resource_envelope import ProviderCallBudget, ProviderCallCapExhausted
from scion.proposal.context_manager.history_projection import (
    proposal_pre_protocol_observations,
)
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
)
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchAbstain,
    HypothesisResearchContextError,
    HypothesisResearchFinalized,
    HypothesisResearchSession,
)
from scion.proposal.llm.config import _normalize_request_kind
from scion.verification.development import DevelopmentSuiteManifest

_MAIN_PATH = "operators/main.py"
_HELPER_PATH = "operators/helper.py"
_MAIN_SOURCE = "def improve(value):\n    return value\n"
_HELPER_SOURCE = "def helper(value):\n    return value * 2\n"
_HISTORY_PATCH_SOURCE = "HISTORY_PATCH_BODY_MUST_BE_READ_EXPLICITLY"


def _basis(
    *read_refs: str,
    nearest_prior_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "read_refs": list(read_refs),
        "nearest_prior_refs": list(nearest_prior_refs),
        "material_delta": (
            "This mechanism is materially distinct from the nearest prior."
        ),
        "alternatives_considered": [
            "Retain the current mechanism without this structural change."
        ],
        "observable_prediction": (
            "The public solver metric should change when activated."
        ),
        "falsification_condition": (
            "Reject the mechanism if the declared public metric does not change."
        ),
    }


def _hypothesis() -> dict[str, Any]:
    return {
        "hypothesis_text": "Change one generic mechanism after reading evidence.",
        "change_locus": "generic",
        "action": "modify",
        "target_file": _MAIN_PATH,
        "predicted_direction": "improve",
        "target_weakness": "The current generic operation misses an opportunity.",
        "expected_effect": "Improve the declared solver objective.",
    }


def _source_section(path: str, content: str) -> str:
    return f"### {path}\n```python\n{content}```"


def _context(
    *,
    pre_protocol_observations: list[dict[str, Any]] | None = None,
    include_history: bool = True,
) -> dict[str, Any]:
    context = {
        "problem_summary": "Generic combinatorial optimization subject.",
        "branch_id": "hypothesis-research-branch",
        "champion_version": 987654321,
        "research_surfaces": [{"name": "generic", "kind": "solver_design"}],
        "available_actions": ["modify"],
        "existing_target_files": [_MAIN_PATH, _HELPER_PATH],
        "champion_operators_code": "\n\n".join(
            (
                _source_section(_MAIN_PATH, _MAIN_SOURCE),
                _source_section(_HELPER_PATH, _HELPER_SOURCE),
            )
        ),
        "champion_stats": {},
        "prior_research_history": [
            {
                "hypothesis": {
                    "text": "Earlier exact generic delta.",
                    "change_locus": "generic",
                    "action": "modify",
                    "target_file": _HELPER_PATH,
                },
                "patch": {
                    "changes": [
                        {
                            "file_path": _HELPER_PATH,
                            "action": "modify",
                            "source": _HISTORY_PATCH_SOURCE,
                        }
                    ]
                },
                "outcome": {
                    "outcome": "evaluated",
                    "stage": "screening",
                    "reason_code": "SCREENING_FAIL_CASE_QUALITY",
                },
                "protocol": None,
                "decision": {
                    "value": "continue_explore",
                    "reason_codes": ["SCREENING_FAIL_CASE_QUALITY"],
                },
            }
        ],
        "pre_protocol_observations": pre_protocol_observations
        or [
            {
                "hypothesis": {
                    "hypothesis_text": "An invalid implementation attempt.",
                    "change_locus": "generic",
                    "action": "modify",
                },
                "patch": {"present": False},
                "outcome": {
                    "stage": "proposal_code",
                    "reason_code": "PATCH_PROPOSAL_INVALID",
                    "checks": [],
                },
            }
        ],
        "experiment_history": [
            {
                "proposal_intent": {
                    "hypothesis_text": "A current measured mechanism.",
                    "change_locus": "generic",
                    "action": "modify",
                },
                "experiment_evidence": {
                    "stage": "screening",
                    "protocol_outcome": {
                        "gate_outcome": "fail",
                        "reason_codes": ["SCREENING_FAIL_CASE_QUALITY"],
                    },
                },
            }
        ],
    }
    if not include_history:
        context["prior_research_history"] = []
        context["pre_protocol_observations"] = []
        context["experiment_history"] = []
    return context


def _snapshot(**kwargs: Any):
    return build_prompt_turn_snapshot("hypothesis", _context(**kwargs))


class _SequenceClient:
    model = "fake-hypothesis-research-model"

    def __init__(self, responses: list[Any]) -> None:
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
                "request_kind": request_kind,
                "tool": deepcopy(tool),
                "prompt": prompt,
                "system_text": "\n".join(
                    str(block.get("text") or "") for block in system_blocks
                ),
                "system_blocks": deepcopy(system_blocks),
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def _run(
    responses: list[Any],
    *,
    limits: CodeResearchLimits | None = None,
    budget: ProviderCallBudget | None = None,
    trace_dir: str | None = None,
) -> tuple[HypothesisResearchSession, _SequenceClient]:
    client = _SequenceClient(responses)
    creative = CreativeLayer(
        client,
        provider_call_budget=budget,
        trace_dir=trace_dir,
    )
    return (
        HypothesisResearchSession(creative, limits or CodeResearchLimits()),
        client,
    )


def _tool_action(call: Mapping[str, Any], action: str) -> dict[str, Any]:
    return next(
        branch
        for branch in call["tool"]["input_schema"]["oneOf"]
        if branch["properties"]["action"]["enum"] == [action]
    )


def test_compact_indexes_are_complete_and_bodies_are_read_on_demand() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "search_source", "query": "return value"},
            {"action": "read_history", "ref": "history-0001"},
            {"action": "search_history", "query": "SCREENING_FAIL"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=5),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.target_file == _MAIN_PATH
    assert result.research_basis.read_refs == ("source-0001", "history-0001")
    assert [call["request_kind"] for call in client.calls] == [
        "hypothesis_research_turn"
    ] * 5
    first = client.calls[0]["system_text"]
    assert "source-0001" in first and "source-0002" in first
    assert _HELPER_PATH in first and _MAIN_PATH in first
    assert "history-0001" in first and "history-0003" in first
    assert "Earlier exact generic delta." in first
    assert _MAIN_SOURCE not in first
    assert _HELPER_SOURCE not in first
    assert _HISTORY_PATCH_SOURCE not in first
    assert (
        "def helper(value):\\n    return value * 2\\n" in client.calls[1]["system_text"]
    )
    assert '"line":"    return value"' in client.calls[2]["system_text"]
    assert _HISTORY_PATCH_SOURCE in client.calls[3]["system_text"]
    assert '"field":"$.outcome.reason_code"' in client.calls[4]["system_text"]
    assert session.provider_calls_used == 5


def test_search_over_result_cap_returns_no_partial_top_k() -> None:
    session, client = _run(
        [
            {"action": "search_source", "query": "def"},
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=3, max_search_matches=1),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    second = client.calls[1]["system_text"]
    assert "search_result_cap_exhausted" in second
    assert '"matches"' not in second
    assert "def improve" not in second
    assert "def helper" not in second


def test_search_stops_scanning_at_the_first_unrepresentable_match() -> None:
    class _TripwireSource(str):
        item_calls = 0

        def __getitem__(self, key: int | slice) -> str:
            self.item_calls += 1
            if self.item_calls > 64:
                raise AssertionError("source scan continued past its result capacity")
            return super().__getitem__(key)

    class _TripwireHistory(Mapping[str, str]):
        def __getitem__(self, key: str) -> str:
            return "needle"

        def __iter__(self) -> Iterator[str]:
            yield "one"
            yield "two"

        def __len__(self) -> int:
            return 2

        def items(self) -> Iterator[tuple[str, str]]:
            yield "one", "needle one"
            yield "two", "needle two"
            raise AssertionError("history scan continued past its result capacity")

    source_session = HypothesisResearchSession(
        None, CodeResearchLimits(max_search_matches=1)
    )
    source_result = source_session._search(
        "search_source",
        "needle",
        None,
        [
            {
                "ref": "source-0001",
                "path": "generic.py",
                "body": _TripwireSource(
                    "needle one\nneedle two\nneedle three\n" * 100_000
                ),
            }
        ],
    )
    history_session = HypothesisResearchSession(
        None, CodeResearchLimits(max_search_matches=1)
    )
    history_result = history_session._search(
        "search_history",
        "needle",
        None,
        [
            {
                "ref": "history-0001",
                "kind": "prior_research_history",
                "ordinal": 1,
                "record": _TripwireHistory(),
            }
        ],
    )

    assert source_result["reason"] == "search_result_cap_exhausted"
    assert history_result["reason"] == "search_result_cap_exhausted"


def test_source_index_exposes_adjacency_without_preselecting_a_target() -> None:
    context = _context()
    context["champion_operators_code"] = "\n\n".join(
        (
            _source_section(
                _MAIN_PATH,
                "from operators.helper import helper\n\ndef improve(value):\n"
                "    return helper(value)\n",
            ),
            _source_section(_HELPER_PATH, _HELPER_SOURCE),
        )
    )
    session, client = _run(
        [{"action": "abstain", "reason": "Index inspected."}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(build_prompt_turn_snapshot("hypothesis", context))

    first = client.calls[0]["system_text"]
    assert '"path":"operators/main.py"' in first
    assert '"dependencies":["operators/helper.py"]' in first
    assert '"path":"operators/helper.py"' in first
    assert '"callers":["operators/main.py"]' in first
    assert '"roles":["target"]' not in first
    assert "from operators.helper import helper" not in first


def test_source_index_resolves_relative_and_host_qualified_imports() -> None:
    context = _context()
    relative_path = "policies/relative.py"
    absolute_path = "policies/absolute.py"
    dependency_path = "policies/dependency.py"
    context["existing_target_files"] = [
        relative_path,
        absolute_path,
        dependency_path,
    ]
    context["champion_operators_code"] = "\n\n".join(
        (
            _source_section(
                relative_path,
                "from .dependency import helper\nRELATIVE = helper\n",
            ),
            _source_section(
                absolute_path,
                "from scion.problems.generic.policies.dependency import helper\n"
                "ABSOLUTE = helper\n",
            ),
            _source_section(dependency_path, "def helper():\n    return 1\n"),
        )
    )
    session, client = _run(
        [{"action": "abstain", "reason": "Import graph inspected."}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(
        build_prompt_turn_snapshot("hypothesis", context),
        qualified_prefixes=("scion.problems.generic.",),
    )

    first = client.calls[0]["system_text"]
    assert first.count('"dependencies":["policies/dependency.py"]') == 2
    assert '"callers":["policies/absolute.py","policies/relative.py"]' in first


def test_declared_public_development_test_is_indexed_then_read_losslessly(
    tmp_path: Path,
) -> None:
    public_body = "PUBLIC_DEVELOPMENT_BODY = True\n"
    formal_body = "FORMAL_TEST_MUST_NOT_BE_VISIBLE = True\n"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/public.py").write_text(public_body, encoding="utf-8")
    (tmp_path / "tests/formal.py").write_text(formal_body, encoding="utf-8")
    runtime = ProblemRuntime(
        problem_spec=SimpleNamespace(id="generic"),
        development_suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(tmp_path),
                test_path="tests/public.py",
            ),
        ),
    )
    public_sources = runtime.hypothesis_research_public_sources()
    assert runtime.hypothesis_research_source_prefixes() == ("scion.problems.generic.",)
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0003"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0003"),
            },
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    result = session.run(
        _snapshot(include_history=False), public_sources=public_sources
    )

    assert isinstance(result, HypothesisResearchFinalized)
    first, second = (call["system_text"] for call in client.calls)
    assert '"check_name":"D3_unit_tests"' in first
    assert '"roles":["public_test"]' in first
    assert public_body.strip() not in first
    assert "PUBLIC_DEVELOPMENT_BODY = True\\n" in second
    assert formal_body.strip() not in first + second


def test_held_out_split_file_cannot_become_a_public_h_source(tmp_path: Path) -> None:
    held_out_body = "HELD_OUT_CASE_CONTENT_MUST_NEVER_ENTER_H = True\n"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/held_out.py").write_text(held_out_body, encoding="utf-8")
    suite = DevelopmentSuiteManifest(
        check_name="D3_unit_tests",
        source_root=str(tmp_path),
        test_path="tests/held_out.py",
    )
    runtime = ProblemRuntime(
        problem_spec=SimpleNamespace(id="generic", root_dir=str(tmp_path)),
        split_manifest=SimpleNamespace(
            screening=(),
            validation=(),
            frozen=("tests/held_out.py",),
            canary=(),
            safe_data_roots=(),
        ),
        development_suites=(suite,),
    )

    with pytest.raises(ValueError, match="overlaps Protocol/canary"):
        runtime.hypothesis_research_public_sources()


def test_research_prompt_and_trace_omit_branch_and_champion_identity(
    tmp_path: Path,
) -> None:
    branch_sentinel = "hypothesis-research-branch"
    champion_sentinel = "987654321"
    session, client = _run(
        [{"action": "abstain", "reason": "Identity-free view inspected."}],
        limits=CodeResearchLimits(max_turns=1),
        trace_dir=str(tmp_path),
    )

    session.run(_snapshot())

    wire = client.calls[0]["prompt"] + client.calls[0]["system_text"]
    trace_path = next(tmp_path.glob("*.json"))
    trace_text = trace_path.read_text(encoding="utf-8")
    trace = json.loads(trace_text)
    assert branch_sentinel not in wire + trace_text
    assert champion_sentinel not in wire + trace_text
    assert "branch_id" not in trace
    assert "champion_version" not in trace
    assert "branch_id" not in trace["structured_context"]
    assert "champion_version" not in trace["structured_context"]


def test_abstain_returns_no_hypothesis() -> None:
    session, client = _run(
        [{"action": "abstain", "reason": "Evidence is insufficient."}],
        limits=CodeResearchLimits(max_turns=1),
    )

    result = session.run(_snapshot())

    assert result == HypothesisResearchAbstain(reason="Evidence is insufficient.")
    assert len(client.calls) == 1


def test_complete_index_over_transcript_budget_fails_before_provider() -> None:
    context = _context()
    paths = [f"operators/item_{index:04d}.py" for index in range(200)]
    context["existing_target_files"] = paths
    context["champion_operators_code"] = "\n\n".join(
        _source_section(path, "def item():\n    return 1\n") for path in paths
    )
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    session, client = _run(
        [
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            }
        ],
        limits=CodeResearchLimits(max_turns=1, max_transcript_chars=2_000),
    )

    with pytest.raises(
        ProposalValidationError,
        match="transcript exceeds max_transcript_chars before dispatch",
    ):
        session.run(snapshot)

    assert client.calls == []


@pytest.mark.parametrize(
    ("limits", "include_history", "reason"),
    [
        (
            CodeResearchLimits(max_turns=2, max_read_calls=0),
            False,
            "max_read_calls",
        ),
        (
            CodeResearchLimits(max_turns=3, max_read_calls=1),
            True,
            "max_read_calls",
        ),
    ],
)
def test_unsatisfiable_mandatory_read_limits_fail_before_provider(
    limits: CodeResearchLimits,
    include_history: bool,
    reason: str,
) -> None:
    session, client = _run([], limits=limits)

    with pytest.raises(HypothesisResearchContextError, match=reason):
        session.run(_snapshot(include_history=include_history))

    assert session.provider_calls_used == 0
    assert client.calls == []


def test_unavailable_source_entries_do_not_create_a_mandatory_read_gate() -> None:
    context = _context()
    context["champion_operators_code"] = ""
    session, client = _run(
        [
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "history-0001", nearest_prior_refs=("history-0001",)
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=2, max_read_calls=1),
    )

    result = session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert isinstance(result, HypothesisResearchFinalized)
    assert '"available":false' in client.calls[0]["system_text"]
    assert "contains an available entry" in client.calls[0]["prompt"]
    assert "finalize_hypothesis" not in {
        branch["properties"]["action"]["enum"][0]
        for branch in client.calls[0]["tool"]["input_schema"]["oneOf"]
    }
    assert _tool_action(client.calls[1], "finalize_hypothesis")


def test_history_index_contains_every_record_without_recent_top_k() -> None:
    context = _context()
    context["prior_research_observations"] = [
        {
            "hypothesis": {"hypothesis_text": f"ordinary prior {index:03d}"},
            "outcome": {"reason_code": "ORDINARY_FAILURE"},
        }
        for index in range(50)
    ]
    session, client = _run(
        [{"action": "abstain", "reason": "Complete inventory inspected."}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(build_prompt_turn_snapshot("hypothesis", context))

    first = client.calls[0]["system_text"]
    assert '"ref":"history-0053"' in first
    assert "ordinary prior 000" in first
    assert "ordinary prior 049" in first


def test_proposal_code_rejection_is_safe_and_visible_to_next_h() -> None:
    secret_detail = "FORBIDDEN_PROVIDER_DETAIL_AND_DRAFT_SOURCE"
    secret_target = "private/provider/target.py"
    hypothesis = HypothesisProposal(
        hypothesis_text="Try one bounded implementation.",
        change_locus="generic",
        action="modify",
        target_file=secret_target,
        predicted_direction="exploratory",
        target_weakness="The current mechanism is incomplete.",
    )
    rejected = StepRecord(
        round_num=1,
        branch_id="ordinary-branch",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal_code",
        failure_detail=secret_detail,
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code="PATCH_PROPOSAL_INVALID",
            detail=secret_detail,
            provenance={
                "stage": "proposal_code",
                "provider_response": secret_detail,
            },
        ),
    )
    observations = proposal_pre_protocol_observations([rejected])
    assert observations == [
        {
            "hypothesis": {
                "hypothesis_text": "Try one bounded implementation.",
                "change_locus": "generic",
                "action": "modify",
                "predicted_direction": "exploratory",
                "target_weakness": "The current mechanism is incomplete.",
            },
            "patch": {"present": False},
            "outcome": {
                "stage": "proposal_code",
                "reason_code": "PATCH_PROPOSAL_INVALID",
                "checks": [],
            },
        }
    ]
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0002"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0002",
                    nearest_prior_refs=("history-0002",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=3),
    )

    result = session.run(_snapshot(pre_protocol_observations=observations))

    assert isinstance(result, HypothesisResearchFinalized)
    rendered = "\n".join(call["system_text"] for call in client.calls)
    assert "proposal_code" in rendered
    assert "PATCH_PROPOSAL_INVALID" in rendered
    assert secret_detail not in rendered
    assert secret_target not in rendered


def test_finalize_basis_rejection_can_be_corrected_within_remaining_turns() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0002"),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=3),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert len(client.calls) == 3
    assert (
        '"action":"finalize_hypothesis","ok":false,"reason":"read_refs_not_read"'
    ) in client.calls[2]["system_text"]


def test_m24_unseen_nearest_ref_can_be_grounded_and_revised(
    tmp_path: Path,
) -> None:
    invalid_hypothesis = _hypothesis()
    invalid_hypothesis["hypothesis_text"] = (
        "INVALID_FINALIZE_BODY_MUST_REMAIN_ONLY_IN_ITS_TERMINAL_TRACE"
    )
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": invalid_hypothesis,
                "research_basis": _basis(
                    "source-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=4),
        trace_dir=str(tmp_path),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.hypothesis_text == _hypothesis()["hypothesis_text"]
    assert session.provider_calls_used == 4
    assert len(client.calls) == 4
    assert "nearest_prior_refs_not_read_and_cited" in client.calls[2]["system_text"]
    assert invalid_hypothesis["hypothesis_text"] not in client.calls[2]["system_text"]

    first_actions = {
        branch["properties"]["action"]["enum"][0]
        for branch in client.calls[0]["tool"]["input_schema"]["oneOf"]
    }
    assert "finalize_hypothesis" not in first_actions
    assert _tool_action(client.calls[0], "read_history")["properties"]["ref"][
        "enum"
    ] == ["history-0001", "history-0002", "history-0003"]

    for call in client.calls[:3]:
        actions = {
            branch["properties"]["action"]["enum"][0]
            for branch in call["tool"]["input_schema"]["oneOf"]
        }
        assert "finalize_hypothesis" not in actions
    finalize = _tool_action(client.calls[3], "finalize_hypothesis")
    basis_schema = finalize["properties"]["research_basis"]["properties"]
    assert basis_schema["read_refs"]["items"]["enum"] == [
        "history-0001",
        "source-0001",
    ]
    assert basis_schema["nearest_prior_refs"]["items"]["enum"] == ["history-0001"]
    assert basis_schema["nearest_prior_refs"]["minItems"] == 1
    assert (
        "falsification_condition"
        in finalize["properties"]["research_basis"]["required"]
    )
    assert (
        "must also appear in read_refs"
        in (basis_schema["nearest_prior_refs"]["description"])
    )

    traces = [
        json.loads(path.read_text(encoding="utf-8")) for path in tmp_path.glob("*.json")
    ]
    finalized = [
        trace
        for trace in traces
        if trace.get("response", {}).get("action") == "finalize_hypothesis"
    ]
    assert len(finalized) == 2
    hypotheses = [trace["response"]["hypothesis"] for trace in finalized]
    assert invalid_hypothesis in hypotheses
    assert _hypothesis() in hypotheses


def test_nonempty_source_corpus_also_gates_finalize_and_host_bypass() -> None:
    session, client = _run(
        [
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "history-0001", nearest_prior_refs=("history-0001",)
                ),
            },
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=4),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    for call in client.calls[:3]:
        actions = {
            branch["properties"]["action"]["enum"][0]
            for branch in call["tool"]["input_schema"]["oneOf"]
        }
        assert "finalize_hypothesis" not in actions
    assert (
        '"action":"finalize_hypothesis","ok":false,"reason":"read_refs_not_read"'
        in client.calls[2]["system_text"]
    )
    assert _tool_action(client.calls[3], "finalize_hypothesis")


def test_nonempty_history_requires_nearest_prior_even_after_reads() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001", "history-0001"),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=4),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert (
        '"reason":"nearest_prior_refs_not_read_and_cited"'
        in client.calls[3]["system_text"]
    )


def test_missing_falsification_condition_is_fixed_and_revisable() -> None:
    invalid_basis = _basis(
        "source-0001",
        "history-0001",
        nearest_prior_refs=("history-0001",),
    )
    invalid_basis.pop("falsification_condition")
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": invalid_basis,
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=4),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert '"reason":"research_basis_invalid"' in client.calls[3]["system_text"]
    assert result.research_basis.falsification_condition


def test_visible_nearest_history_must_also_be_cited_and_can_be_revised() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=4),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert "nearest_prior_refs_not_read_and_cited" in client.calls[3]["system_text"]


def test_invalid_hypothesis_can_be_corrected_without_echoing_validator_text() -> None:
    invalid = _hypothesis()
    invalid["change_locus"] = "FORBIDDEN_UNBOUND_LOCUS_MUST_NOT_BE_ECHOED"
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": invalid,
                "research_basis": _basis("source-0001"),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=3),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    correction_context = client.calls[2]["system_text"]
    assert '"reason":"hypothesis_invalid"' in correction_context
    assert invalid["change_locus"] not in correction_context


def test_invalid_finalize_on_last_turn_stops_at_the_local_cap() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0002"),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    with pytest.raises(ProposalValidationError, match="turn cap exhausted"):
        session.run(_snapshot())

    assert session.provider_calls_used == 2
    assert len(client.calls) == 2


def test_last_shared_read_call_is_reserved_for_unread_history() -> None:
    invalid_ref = "HISTORY_REF_SENTINEL_MUST_NOT_BE_ECHOED"
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_source", "ref": "source-0002"},
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_source", "ref": "source-0002"},
            {"action": "read_history", "ref": invalid_ref},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis(
                    "source-0001",
                    "history-0001",
                    nearest_prior_refs=("history-0001",),
                ),
            },
        ],
        limits=CodeResearchLimits(max_turns=7, max_read_calls=4),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert "read_call_reserved_for_history" in client.calls[4]["system_text"]
    assert '"history_read_reserved":true' in client.calls[3]["system_text"]
    assert '"remaining_read_calls":1' in client.calls[4]["system_text"]
    assert "unknown_history_ref" in client.calls[5]["system_text"]
    assert invalid_ref not in client.calls[5]["system_text"]
    assert '"history_read_reserved":true' in client.calls[5]["system_text"]
    assert '"remaining_read_calls":1' in client.calls[5]["system_text"]
    assert (
        "final shared read call is currently reserved"
        in client.calls[3]["tool"]["description"]
    )
    assert _tool_action(client.calls[4], "read_history")["properties"]["ref"][
        "enum"
    ] == ["history-0001", "history-0002", "history-0003"]


def test_invalid_finalize_does_not_bypass_the_global_provider_cap() -> None:
    budget = ProviderCallBudget(2)
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0002"),
            },
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=3),
        budget=budget,
    )

    with pytest.raises(ProviderCallCapExhausted):
        session.run(_snapshot())

    assert budget.used == 2
    assert session.provider_calls_used == 2
    assert len(client.calls) == 2


def test_unknown_action_and_provider_fault_remain_hard_failures() -> None:
    unknown_session, unknown_client = _run(
        [
            {"action": "run_solver"},
            {"action": "abstain", "reason": "must not be reached"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    with pytest.raises(ProposalValidationError, match="action must be"):
        unknown_session.run(_snapshot())

    provider_session, provider_client = _run(
        [RuntimeError("provider transport sentinel")],
        limits=CodeResearchLimits(max_turns=2),
    )
    with pytest.raises(RuntimeError, match="provider transport sentinel"):
        provider_session.run(_snapshot())

    assert len(unknown_client.calls) == 1
    assert unknown_session.provider_calls_used == 1
    assert len(provider_client.calls) == 1
    assert provider_session.provider_calls_used == 1


def test_validated_basis_is_retained_by_terminal_trace_not_hypothesis(
    tmp_path: Path,
) -> None:
    basis = _basis("source-0001")
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": basis,
            },
        ],
        limits=CodeResearchLimits(max_turns=2),
        trace_dir=str(tmp_path),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert not hasattr(result.hypothesis, "research_basis")
    traces = [
        json.loads(path.read_text(encoding="utf-8")) for path in tmp_path.glob("*.json")
    ]
    finalized = next(
        trace
        for trace in traces
        if trace.get("response", {}).get("action") == "finalize_hypothesis"
    )
    assert finalized["response"]["research_basis"] == basis


def test_h_research_turns_share_the_global_provider_budget() -> None:
    budget = ProviderCallBudget(1)
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _hypothesis(),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=2),
        budget=budget,
    )

    with pytest.raises(ProviderCallCapExhausted) as captured:
        session.run(_snapshot())

    assert captured.value.request_kind == "hypothesis_research_turn"
    assert budget.used == 1
    assert len(client.calls) == 1


def test_pipeline_maps_h_research_abstention_to_typed_rejection() -> None:
    client = _SequenceClient(
        [{"action": "abstain", "reason": "No grounded mechanism remains."}]
    )
    branch = Branch(
        branch_id="hypothesis-research-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path="/unused",
    )

    class _Runtime:
        def build_hypothesis_context(self, **_kwargs: Any) -> dict[str, Any]:
            return _context()

        def hypothesis_research_public_sources(self) -> tuple[dict[str, str], ...]:
            return ()

        def hypothesis_research_source_prefixes(self) -> tuple[str, ...]:
            return ()

    pipeline = ProposalPipeline(
        creative=CreativeLayer(client),
        problem_runtime=_Runtime(),
        branch_workspaces={},
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
        step_history=[],
        mark_balance_exhausted=lambda: None,
        code_research_limits=CodeResearchLimits(max_turns=1),
    )

    attempt = pipeline.generate_hypothesis(branch)

    assert attempt.proposal is None
    assert attempt.execution_outcome is not None
    assert attempt.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert attempt.execution_outcome.reason_code == "HYPOTHESIS_RESEARCH_ABSTAINED"


def test_no_limits_pipeline_preserves_the_direct_one_shot_request() -> None:
    context = _context()
    expected = build_prompt_turn_snapshot("hypothesis", context)
    client = _SequenceClient([_hypothesis()])
    loader_called = False

    class _Runtime:
        def build_hypothesis_context(self, **_kwargs: Any) -> dict[str, Any]:
            return deepcopy(context)

        def hypothesis_research_public_sources(self) -> tuple[dict[str, str], ...]:
            nonlocal loader_called
            loader_called = True
            raise AssertionError("direct H must not read development sources")

        def hypothesis_research_source_prefixes(self) -> tuple[str, ...]:
            nonlocal loader_called
            loader_called = True
            raise AssertionError("direct H must not derive research source prefixes")

    pipeline = ProposalPipeline(
        creative=CreativeLayer(client),
        problem_runtime=_Runtime(),
        branch_workspaces={},
        champion_lock=threading.Lock(),
        get_champion=lambda: ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path="/unused",
        ),
        step_history=[],
        mark_balance_exhausted=lambda: None,
        code_research_limits=None,
    )

    attempt = pipeline.generate_hypothesis(
        Branch(
            branch_id="hypothesis-research-branch",
            state=BranchState.EXPLORE,
            base_champion_id=1,
        )
    )

    assert attempt.proposal is not None
    assert loader_called is False
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["request_kind"] == "hypothesis"
    assert call["tool"] == dict(expected.provider_tool)
    assert call["prompt"] == expected.user_prompt
    assert call["system_blocks"] == [dict(block) for block in expected.system_blocks]


def test_research_invalid_source_graph_is_context_failure_before_provider() -> None:
    context = _context()
    context["champion_operators_code"] = _source_section(
        _MAIN_PATH,
        "def broken(:\n",
    )
    client = _SequenceClient([])

    class _Runtime:
        def build_hypothesis_context(self, **_kwargs: Any) -> dict[str, Any]:
            return context

        def hypothesis_research_public_sources(self) -> tuple[dict[str, str], ...]:
            return ()

        def hypothesis_research_source_prefixes(self) -> tuple[str, ...]:
            return ()

    pipeline = ProposalPipeline(
        creative=CreativeLayer(client),
        problem_runtime=_Runtime(),
        branch_workspaces={},
        champion_lock=threading.Lock(),
        get_champion=lambda: ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path="/unused",
        ),
        step_history=[],
        mark_balance_exhausted=lambda: None,
        code_research_limits=CodeResearchLimits(max_turns=1),
    )

    attempt = pipeline.generate_hypothesis(
        Branch(
            branch_id="hypothesis-research-branch",
            state=BranchState.EXPLORE,
            base_champion_id=1,
        )
    )

    assert attempt.proposal is None
    assert attempt.execution_outcome is not None
    assert attempt.execution_outcome.outcome is ExecutionOutcome.NOT_EVALUATED
    assert attempt.execution_outcome.reason_code == "PROPOSAL_CONTEXT_INVALID"
    assert client.calls == []


def test_hypothesis_research_tool_has_an_explicit_transport_kind() -> None:
    assert (
        _normalize_request_kind(tool={"name": "hypothesis_research_turn"})
        == "hypothesis_research_turn"
    )
