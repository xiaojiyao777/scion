from __future__ import annotations

import json
from pathlib import Path

import pytest
from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
    hypothesis_prompts,
    provider_call,
)
from scion.proposal.llm_client import (
    LLMClient,
    LLMFormatError,
    LLMProviderError,
)
from scion.proposal.schemas import HYPOTHESIS_TOOL, PATCH_TOOL
from scion.protocol.experiment.proposal_evidence import (
    problem_proposal_mechanism_evidence,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT

from .editable_source_context_test_support import editable_code_context

_M7_RESEARCH_INPUT = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "experiments"
    / "v0.4"
    / "inputs"
    / "v04-cvrp-m9-m7-fc1-research-input.json"
)

_HYPOTHESIS_RESPONSE = {
    "hypothesis_text": "Try one bounded local improvement move.",
    "change_locus": "local_search",
    "action": "create_new",
    "target_file": "operators/bounded_receipt.py",
    "predicted_direction": "improve",
    "target_weakness": "The control lacks this bounded move.",
    "expected_effect": "Improve the primary objective when the move applies.",
}

_PATCH_RESPONSE = {
    "file_path": "operators/bounded_receipt.py",
    "action": "create",
    "edit_intent": "full_file",
    "content_after": "def bounded_receipt(solution):\n    return solution\n",
    "full_file_reason": "Create the approved new research-surface file.",
    "evidence_refs": [],
}

_PROVIDER_HOST_CONTROL_KEYS = frozenset(
    {
        "branch_id",
        "champion_version",
        "schema_version",
    }
)


def _without_provider_host_control(value):
    if isinstance(value, dict):
        return {
            key: _without_provider_host_control(child)
            for key, child in value.items()
            if key not in _PROVIDER_HOST_CONTROL_KEYS
        }
    if isinstance(value, list):
        return [_without_provider_host_control(child) for child in value]
    return value


def _nested_keys(value) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_nested_keys(child))
        return keys
    if isinstance(value, list):
        keys = set()
        for child in value:
            keys.update(_nested_keys(child))
        return keys
    return set()


def test_patch_tool_keeps_each_file_in_one_typed_edit() -> None:
    schema_guidance = " ".join(
        (
            PATCH_TOOL["input_schema"]["properties"]["edit_intent"]["description"],
            PATCH_TOOL["input_schema"]["properties"]["additional_changes"][
                "description"
            ],
        )
    )
    assert "additional_changes" in PATCH_TOOL["description"]
    assert "Each file_path may appear exactly once" in PATCH_TOOL["description"]
    assert "Each file_path may appear exactly once" in schema_guidance
    code_snapshot = build_prompt_turn_snapshot("code", _code_context())
    code_guidance = code_snapshot.user_prompt
    for expected in (
        "Choose exact_replace",
        "exact source block",
        "whose indentation is part of the selector",
        "Choose exact_line_replace",
        "identical complete logical-line body repeats",
        "Choose full_file for creates, broad rewrites",
        "no stable exact selector",
    ):
        assert expected in PATCH_TOOL["description"]
        assert expected in schema_guidance
        assert expected not in code_guidance
    assert "follow the tool schema's edit protocol" in code_guidance


class _CaptureClient:
    model = "test-model"

    def __init__(
        self,
        *,
        error: Exception | None = None,
        response: dict | None = None,
        response_diagnostics: dict | None = None,
        usage: dict | None = None,
        expected_tool: str = "generate_hypothesis",
    ) -> None:
        self.error = error
        self.response = dict(response or _HYPOTHESIS_RESPONSE)
        self.response_diagnostics = (
            dict(response_diagnostics) if response_diagnostics is not None else None
        )
        self.usage = dict(usage) if usage is not None else None
        self.expected_tool = expected_tool
        self.calls: list[tuple[str, list[dict], str]] = []
        self.tools: list[dict] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        del model
        self.calls.append((str(prompt), list(system_blocks or []), str(request_kind)))
        self.tools.append(json.loads(json.dumps(tool)))
        if self.error is not None:
            raise self.error
        assert tool["name"] == self.expected_tool
        return dict(self.response)

    def get_last_response_diagnostics(self):
        if self.response_diagnostics is None:
            return None
        return dict(self.response_diagnostics)

    def get_last_usage_metadata(self):
        if self.usage is None:
            return None
        return dict(self.usage)


class _DirectOpenAIClient(LLMClient):
    def __init__(
        self,
        *,
        length_response: bool = False,
        omit_predicted_direction: bool = False,
    ) -> None:
        super().__init__(model="gpt-5.6-sol")
        self.length_response = length_response
        self.omit_predicted_direction = omit_predicted_direction
        self.calls_seen: list[str] = []

    def _tool_call_once(
        self,
        prompt,
        tool,
        model,
        system_blocks,
        timeout_sec,
    ):
        del prompt, model, system_blocks, timeout_sec
        self.calls_seen.append(str(tool["name"]))
        if self.length_response:
            return {}
        if tool["name"] == "generate_hypothesis":
            response = dict(_HYPOTHESIS_RESPONSE)
            if self.omit_predicted_direction:
                del response["predicted_direction"]
            return response
        return dict(_PATCH_RESPONSE)


def _hypothesis_context() -> dict:
    return {
        "problem_summary": "Synthetic routing control.",
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "target_files": ["operators/*.py"],
            }
        ],
        "objective_policy_guidance": "Minimize cost while preserving feasibility.",
        "solver_mechanics": "",
        "champion_operators_code": "class Control: pass",
        "champion_stats": {"version": 1, "operators": []},
        "available_actions": ["create_new"],
        "existing_target_files": [],
        "create_path_patterns": ["operators/*.py"],
        "experiment_history": [],
        "branch_id": "branch-receipt",
        "champion_version": 1,
    }


def _code_context() -> dict:
    return editable_code_context(
        {
            "problem_summary": "Synthetic routing control.",
            "target_file": "operators/bounded_receipt.py",
            "target_file_code": "",
            "action": "create_new",
            "approved_hypothesis": {
                "hypothesis_text": "Try one local improvement move.",
                "change_locus": "local_search",
                "action": "create_new",
                "target_file": "operators/bounded_receipt.py",
                "predicted_direction": "improve",
                "target_weakness": "The current solver lacks this move.",
                "expected_effect": "Improve screening outcomes.",
            },
            "operator_interface_spec": "",
            "research_surface": {"name": "local_search", "kind": "operator"},
            "editable_patterns": ["operators/*.py"],
            "frozen_patterns": ["solver.py"],
            "branch_id": "branch-receipt",
            "champion_version": 1,
        }
    )


def _trace_payloads(root: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "traces").glob("*.json"))
    ]


def _single_trace(root: Path) -> dict:
    traces = _trace_payloads(root)
    assert len(traces) == 1
    return traces[0]


def test_provider_call_uses_one_snapshot_for_trace_and_provider(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis = creative.generate_direct_hypothesis(
        snapshot,
    )

    trace = _single_trace(tmp_path)
    assert hypothesis.hypothesis_text == _HYPOTHESIS_RESPONSE["hypothesis_text"]
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "hypothesis")
    ]
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert "prompt_hash" not in trace
    assert "prompt_manifest" not in trace
    assert client.tools[0]["input_schema"]["properties"]["change_locus"]["enum"] == [
        "local_search"
    ]
    assert "enum" not in HYPOTHESIS_TOOL["input_schema"]["properties"]["change_locus"]
    assert trace["tool_schema"]["properties"]["change_locus"]["enum"] == [
        "local_search"
    ]


def test_missing_predicted_direction_defaults_after_one_provider_call(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient(omit_predicted_direction=True)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis = creative.generate_direct_hypothesis(
        snapshot,
    )

    trace = _single_trace(tmp_path)
    schema = trace["tool_schema"]
    assert hypothesis.predicted_direction == "exploratory"
    assert client.calls_seen == ["generate_hypothesis"]
    assert "predicted_direction" not in schema["required"]
    assert schema["properties"]["predicted_direction"]["enum"] == [
        "improve",
        "tradeoff",
        "exploratory",
    ]


def test_provider_response_cannot_append_description_to_change_locus(
    tmp_path: Path,
) -> None:
    response = {
        **_HYPOTHESIS_RESPONSE,
        "change_locus": "local_search neighborhood family",
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(
        ProposalValidationError,
        match="must exactly match one provider-visible research surface",
    ):
        creative.generate_direct_hypothesis(snapshot)

    assert len(client.calls) == 1
    assert client.tools[0]["input_schema"]["properties"]["change_locus"]["enum"] == [
        "local_search"
    ]
    trace = _single_trace(tmp_path)
    assert trace["ok"] is True
    assert trace["response"] == response


def test_hypothesis_tool_enum_is_generic_across_visible_surfaces(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = {
        **_hypothesis_context(),
        "research_surfaces": [
            {"name": "local_search", "kind": "operator"},
            {"name": "construction", "kind": "solver_design"},
        ],
    }
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    creative.generate_direct_hypothesis(snapshot)

    assert client.tools[0]["input_schema"]["properties"]["change_locus"]["enum"] == [
        "local_search",
        "construction",
    ]


@pytest.mark.parametrize(
    "research_surfaces",
    [
        "local_search",
        [],
        [{"kind": "operator"}],
        [{"name": "local_search"}, {"name": "local_search"}],
        [{"name": " local_search"}],
        [{"name": "local_search "}],
    ],
)
def test_hypothesis_tool_rejects_invalid_visible_surface_contract_before_call(
    research_surfaces: object,
) -> None:
    context = {
        **_hypothesis_context(),
        "research_surfaces": research_surfaces,
    }

    with pytest.raises(ValueError, match="research"):
        build_prompt_turn_snapshot("hypothesis", context)


def test_provider_call_uses_single_frozen_context_value(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = _hypothesis_context()
    turn = build_prompt_turn_snapshot("hypothesis", raw_context)
    frozen_context = turn.structured_context
    creative.generate_direct_hypothesis(
        turn,
    )

    assert turn.structured_context == frozen_context == raw_context
    trace = _single_trace(tmp_path)
    assert trace["structured_context"] == frozen_context
    assert "unexpected_host_sidecar" not in trace["structured_context"]

    with pytest.raises(ValueError, match="unsupported proposal context field"):
        build_prompt_turn_snapshot(
            "hypothesis",
            {**raw_context, "_scion_trace_context": {"host_only": True}},
        )


def test_direct_context_preserves_complete_authoritative_inputs(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    sentinels = {
        "problem_summary": "SENTINEL_STATIC_PROBLEM_SUMMARY",
        "problem_object": "SENTINEL_STATIC_PROBLEM_OBJECT",
        "solver_mechanics": "SENTINEL_STATIC_SOLVER_MECHANICS",
        "research_surfaces": "SENTINEL_STATIC_RESEARCH_SURFACES",
        "objective_policy": "SENTINEL_STATIC_OBJECTIVE_POLICY",
        "champion_code": "SENTINEL_STATIC_CHAMPION_CODE",
        "champion_stats": "SENTINEL_STATIC_CHAMPION_STATS",
        "item_9": "SENTINEL_ITEM_AFTER_8",
        "sequence_7": "SENTINEL_SEQUENCE_AFTER_6",
        "text_221": "SENTINEL_TEXT_AFTER_220",
        "line_7": "SENTINEL_LINE_AFTER_6",
        "char_361": "SENTINEL_CHAR_AFTER_360",
        "branch_code": "SENTINEL_BRANCH_CURRENT_CODE",
        "measurement": "SENTINEL_MEASUREMENT_CONTEXT",
        "research_question": "SENTINEL_RESEARCH_QUESTION",
    }

    context = {
        **_hypothesis_context(),
        "problem_summary": sentinels["problem_summary"],
        "problem_object": sentinels["problem_object"],
        "solver_mechanics": sentinels["solver_mechanics"],
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "marker": sentinels["research_surfaces"],
            }
        ],
        "objective_policy_guidance": sentinels["objective_policy"],
        "champion_operators_code": sentinels["champion_code"],
        "champion_stats": {"marker": sentinels["champion_stats"]},
        "branch_current_code": sentinels["branch_code"],
        "experiment_history": [
            {"round_num": index, "marker": f"round-{index}"} for index in range(8)
        ]
        + [
            {
                "round_num": 9,
                "marker": sentinels["item_9"],
                "long_text": "x" * 220 + sentinels["text_221"],
                "lines": [f"line-{index}" for index in range(6)]
                + [sentinels["line_7"]],
                "sequence": [f"value-{index}" for index in range(6)]
                + [sentinels["sequence_7"]],
                "long_line": "y" * 360 + sentinels["char_361"],
            }
        ],
        "problem_measurement_diagnostics": {
            "measurement_context": sentinels["measurement"],
            "schema_version": "host-schema-control",
        },
        "research_question": {
            "current_question": sentinels["research_question"],
        },
        "proposal_renderer_inputs": {
            "solver_design_prompt_guidance": {
                "hypothesis_guidance": ["Use the complete source and evidence once."]
            }
        },
    }
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    assert client.calls == []
    assert snapshot.structured_context == context

    creative.generate_direct_hypothesis(snapshot)

    provider_prompt, provider_system_blocks, request_kind = client.calls[0]
    provider_bytes = json.dumps(
        {
            "system_blocks": provider_system_blocks,
            "user_prompt": provider_prompt,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    for sentinel in sentinels.values():
        assert sentinel in provider_bytes

    static_block = provider_system_blocks[1]["text"]
    evidence_block = provider_system_blocks[2]["text"]
    static_payload = json.loads(static_block.split("\n", 1)[1])
    evidence_payload = json.loads(evidence_block.split("\n", 1)[1])
    assert hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS == frozenset(
        {
            "problem_summary",
            "problem_object",
            "solver_mechanics",
            "research_surfaces",
            "objective_policy_guidance",
            "problem_measurement_diagnostics",
            "available_actions",
            "existing_target_files",
            "create_path_patterns",
            "champion_operators_code",
            "champion_stats",
        }
    )
    assert set(static_payload) == (
        hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS & set(context)
    )
    assert set(evidence_payload) == (
        set(context)
        - hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS
        - {"branch_id", "champion_version"}
    )
    provider_payload = {**static_payload, **evidence_payload}
    assert not (_nested_keys(provider_payload) & _PROVIDER_HOST_CONTROL_KEYS)
    assert evidence_payload["branch_current_code"] == sentinels["branch_code"]
    for forbidden_marker in (
        "compact_research_signals.v1",
        "compact_cross_branch_learning.v1",
        "omitted_item_count",
        "omitted_runtime_feedback",
        "text_digest",
        "truncated",
    ):
        assert forbidden_marker not in provider_bytes.lower()

    trace = _single_trace(tmp_path)
    assert request_kind == "hypothesis"
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "hypothesis")
    ]
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert trace["structured_context"] == context
    assert trace["branch_id"] == context["branch_id"]
    assert trace["champion_version"] == context["champion_version"]
    assert "prompt_hash" not in trace
    assert "prompt_manifest" not in trace

    distinct_branch_code = "SENTINEL_DISTINCT_BRANCH_CODE"
    distinct_snapshot = build_prompt_turn_snapshot(
        "hypothesis",
        {**context, "branch_current_code": distinct_branch_code},
    )
    distinct_provider_bytes = json.dumps(
        {
            "system_blocks": list(distinct_snapshot.system_blocks),
            "user_prompt": distinct_snapshot.user_prompt,
        },
        sort_keys=True,
    )
    assert distinct_provider_bytes.count(sentinels["champion_code"]) == 1
    assert distinct_provider_bytes.count(distinct_branch_code) == 1


def test_external_cvrp_research_input_reaches_actual_hypothesis_provider_request(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(_CVRP_ROOT),
    )
    branch = Branch(
        branch_id="cvrp-research-prior-request",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    research_input = json.loads(_M7_RESEARCH_INPUT.read_text(encoding="utf-8"))
    context = ContextManager(
        adapter=CvrpAdapter(spec),
        research_input=research_input,
    ).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
    )
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    response = {
        **_HYPOTHESIS_RESPONSE,
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_modules/local_search.py",
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))

    creative.generate_direct_hypothesis(snapshot)

    assert len(client.calls) == 1
    provider_prompt, provider_system_blocks, request_kind = client.calls[0]
    provider_bytes = json.dumps(
        {
            "system_blocks": provider_system_blocks,
            "user_prompt": provider_prompt,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    assert request_kind == "hypothesis"
    question = research_input["current_question"]
    assert context["research_question"] == {"current_question": question}
    provider_evidence_text = provider_system_blocks[2]["text"].split("\n", 1)[1]
    provider_evidence = json.loads(provider_evidence_text)
    assert provider_evidence["research_question"] == {"current_question": question}
    escaped_question = json.dumps(question, ensure_ascii=True)[1:-1]
    assert provider_evidence_text.count(escaped_question) == 1
    projected = context["prior_research_observations"]
    assert len(projected) == 1
    assert projected[0]["terminal"]["terminal_code"] == ("CANDIDATE_SUBJECT_VETO")
    assert projected[0]["terminal"]["case_id"] == "X-n200-k36"
    for hidden_detail in (
        "tai150a",
        "expanded validation",
        "frozen run",
        "8W/2L/2T",
        "5W/1L/2T",
        "-22, -210, -90, -21",
    ):
        assert hidden_detail not in provider_bytes
    assert "algorithmically material hypothesis" in provider_bytes
    assert (
        "one evidence-grounded mechanism-level change or refinement" in provider_prompt
    )
    assert "materially different mechanism" not in provider_bytes
    trace = _single_trace(tmp_path)
    traced_provider_bytes = json.dumps(
        {
            "system_blocks": trace["system_blocks"],
            "user_prompt": trace["user_prompt"],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    traced_evidence_text = trace["system_blocks"][2]["text"].split("\n", 1)[1]
    assert json.loads(traced_evidence_text)["research_question"] == {
        "current_question": question
    }
    assert traced_evidence_text.count(escaped_question) == 1
    assert traced_provider_bytes.count("CANDIDATE_SUBJECT_VETO") == 1
    assert traced_provider_bytes.count("X-n200-k36") == 1


def test_actual_h_provider_gets_latest_cvrp_evidence_once(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec)
    adapter = CvrpAdapter(spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(_CVRP_ROOT),
    )
    branch = Branch(
        branch_id="cvrp-latest-evidence-request",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    mechanism = problem_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        {
                            "iteration": 1,
                            "repair_operator": "ejection_regret",
                            "accepted": True,
                            "best_improved": True,
                            "acceptance_reason": "new_best",
                            "elapsed_ms_before": 10,
                            "elapsed_ms_after": 25,
                        }
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        {
                            "iteration": 1,
                            "repair_operator": "regret2",
                            "accepted": False,
                            "best_improved": False,
                            "acceptance_reason": "rejected",
                            "elapsed_ms_before": 5,
                            "elapsed_ms_after": 15,
                        }
                    ]
                },
                "champion_result_source": "fresh",
            }
        ],
        problem_spec=legacy,
        adapter=adapter,
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Measure one completion-aware ejection repair.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
    )
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=3.75,
                ci_low=0.0,
                ci_high=11.0,
                total_pairs=1,
                valid_pairs=1,
                pair_wins=1,
                pair_losses=0,
                pair_ties=0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="latest evidence",
            raw_metrics_ref="private/latest.json",
            case_ids=("private-case",),
            seed_set=(11,),
            pair_feedback=(
                PairwiseCaseFeedback(
                    case_id="private-case",
                    seed=11,
                    comparison="win",
                    delta=3.75,
                ),
            ),
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="private-case",
                    n_pairs=1,
                    wins=1,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    dominant_result="win",
                    decisive_metric="total_distance",
                    median_deltas={"total_distance": 3.75},
                    seed_consistency=1.0,
                    case_features={"dimension": 64, "size_bucket": "medium"},
                ),
            ),
            mechanism_evidence=mechanism,
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )
    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )
    raw_mechanism = context["experiment_history"][0]["experiment_evidence"][
        "mechanism_evidence"
    ]
    assert raw_mechanism == mechanism
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    snapshot_context = snapshot.structured_context
    assert (
        snapshot_context["experiment_history"][0]["experiment_evidence"][
            "mechanism_evidence"
        ]
        == mechanism
    )
    response = {
        **_HYPOTHESIS_RESPONSE,
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_modules/destroy_repair.py",
    }
    client = _CaptureClient(response=response)
    CreativeLayer(
        client, trace_dir=str(tmp_path / "traces")
    ).generate_direct_hypothesis(
        snapshot,
    )

    _prompt, blocks, request_kind = client.calls[0]
    assert request_kind == "hypothesis"
    provider_evidence = json.loads(blocks[2]["text"].split("\n", 1)[1])
    history = provider_evidence["experiment_history"]
    assert len(history) == 1
    assert "screening_trajectory" not in history[0]
    latest = history[0]["experiment_evidence"]
    assert latest["case_outcomes"]["case_feedback"] == [
        {
            "n_pairs": 1,
            "wins": 1,
            "losses": 0,
            "ties": 0,
            "win_rate": 1.0,
            "dominant_result": "win",
            "seed_pattern": "uniform",
            "median_deltas": {"total_distance": 3.75},
            "decisive_metric": "total_distance",
            "seed_consistency": 1.0,
            "case_features": {"dimension": 64, "size_bucket": "medium"},
        }
    ]
    assert latest["mechanism_evidence"] == _without_provider_host_control(mechanism)
    provider_bytes = json.dumps(blocks, sort_keys=True)
    assert "prior_research_observations" not in provider_bytes


def test_direct_v3_context_fails_closed_for_unsupported_non_json_value() -> None:
    with pytest.raises(TypeError, match="unsupported opaque proposal context"):
        build_prompt_turn_snapshot(
            "hypothesis",
            {**_hypothesis_context(), "unsupported_runtime_handle": object()},
        )


def test_code_provider_call_preserves_prompt_value(tmp_path: Path) -> None:
    response = dict(_PATCH_RESPONSE)
    client = _CaptureClient(response=response, expected_tool="generate_patch")
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _code_context()
    snapshot = build_prompt_turn_snapshot("code", context)

    patch = creative.generate_direct_code(snapshot)

    trace = _single_trace(tmp_path)
    assert patch.file_path == response["file_path"]
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "code")
    ]
    assert client.tools == [snapshot.provider_tool]
    assert client.tools[0] is not snapshot.provider_tool
    assert snapshot.provider_tool == PATCH_TOOL
    assert snapshot.provider_tool is not PATCH_TOOL
    assert snapshot.provider_tool["input_schema"] is not PATCH_TOOL["input_schema"]
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert trace["tool_schema"] == snapshot.provider_tool["input_schema"]
    assert "prompt_hash" not in trace
    assert "prompt_manifest" not in trace


def test_code_prompt_trace_and_parser_share_one_frozen_source_value(
    tmp_path: Path,
) -> None:
    source_before = "FROZEN_SOURCE_MARKER = 'before'\n"
    source_after = "FROZEN_SOURCE_MARKER = 'after'\n"
    caller_mutation = "MUTATED_CALLER_MARKER = True\n"
    response = {
        "file_path": "operators/bounded_receipt.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": source_before,
        "new_string": source_after,
        "replace_all": False,
        "evidence_refs": [],
    }
    client = _CaptureClient(response=response, expected_tool="generate_patch")
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = _code_context()
    raw_context["approved_hypothesis"].update(
        {
            "action": "modify",
            "target_file": "operators/bounded_receipt.py",
        }
    )
    raw_context["editable_source_context"] = {
        "approved_target": "operators/bounded_receipt.py",
        "sources": [
            {
                "path": "operators/bounded_receipt.py",
                "content": source_before,
            }
        ],
        "target_api_guidance": "Keep bounded_receipt callable.",
    }
    turn = build_prompt_turn_snapshot("code", raw_context)

    raw_context["editable_source_context"]["sources"][0]["content"] = caller_mutation
    frozen_context = turn.structured_context
    patch = creative.generate_direct_code(turn)

    trace = _single_trace(tmp_path)
    provider_context = json.loads(client.calls[0][1][1]["text"].split("\n", 1)[1])
    provider_source = provider_context["editable_source_context"]["sources"][0]
    trace_source = trace["structured_context"]["editable_source_context"]["sources"][0]
    assert set(provider_context) == {
        "approved_hypothesis",
        "editable_source_context",
    }
    assert provider_source["content"] == source_before
    assert trace_source["content"] == source_before
    assert patch.code_content == source_after
    assert trace["structured_context"] == frozen_context
    assert trace["structured_context"]["problem_summary"] == (
        "Synthetic routing control."
    )
    provider_and_trace = json.dumps(
        {
            "system_blocks": client.calls[0][1],
            "structured_context": trace["structured_context"],
        },
        sort_keys=True,
    )
    assert caller_mutation not in provider_and_trace


def test_direct_hypothesis_and_code_use_provider_managed_output_without_cap(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    hypothesis_context = _hypothesis_context()
    hypothesis_snapshot = build_prompt_turn_snapshot(
        "hypothesis",
        hypothesis_context,
    )
    creative.generate_direct_hypothesis(
        hypothesis_snapshot,
    )
    code_context = _code_context()
    code_snapshot = build_prompt_turn_snapshot("code", code_context)
    creative.generate_direct_code(
        code_snapshot,
    )

    assert client.calls_seen == ["generate_hypothesis", "generate_patch"]
    traces = _trace_payloads(tmp_path)
    assert len(traces) == 2
    for trace in traces:
        assert trace["request_policy"]["output_token_policy"] == ("provider_managed")
        assert trace["request_policy"]["output_token_parameter"] == "omitted"
        assert "max_tokens" not in trace["request_policy"]
        assert "truncation_retries" not in trace["request_policy"]


def test_direct_provider_response_rejects_removed_governance_fields(
    tmp_path: Path,
) -> None:
    long_a = "shared-prefix-" + ("x" * 140) + "-TAIL-A"
    long_b = "shared-prefix-" + ("x" * 140) + "-TAIL-B"
    structured = {
        "claim_a": long_a,
        "claim_b": long_b,
        "items": [f"item-{index}" for index in range(15)],
        "mapping": {f"key-{index}": index for index in range(26)},
        "deep": {"d1": {"d2": {"d3": {"d4": {"d5": "DEEP_TAIL"}}}}},
    }
    response = {
        **_HYPOTHESIS_RESPONSE,
        "novelty_signature": structured,
        "material_difference": structured,
        "branch_lesson_usage": structured,
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError, match="extra_forbidden"):
        creative.generate_direct_hypothesis(snapshot)


def test_direct_hypothesis_and_code_traces_use_provider_managed_output(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    creative.generate_direct_hypothesis(
        snapshot,
    )
    code_context = _code_context()
    code_snapshot = build_prompt_turn_snapshot("code", code_context)
    creative.generate_direct_code(
        code_snapshot,
    )

    assert client.calls_seen == ["generate_hypothesis", "generate_patch"]
    traces = _trace_payloads(tmp_path)
    assert len(traces) == 2
    for trace in traces:
        assert trace["request_policy"]["output_token_policy"] == "provider_managed"
        assert trace["request_policy"]["output_token_parameter"] == "omitted"
        assert "max_tokens" not in trace["request_policy"]
        assert "truncation_retries" not in trace["request_policy"]


def test_provider_length_response_typed_failure_has_no_truncation_retry(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient(length_response=True)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(LLMFormatError):
        creative.generate_direct_hypothesis(snapshot)

    assert client.calls_seen == ["generate_hypothesis"]
    trace = _single_trace(tmp_path)
    assert trace["ok"] is False
    assert trace["error_type"] == "LLMFormatError"
    assert trace["request_policy"]["output_token_policy"] == "provider_managed"
    assert "max_tokens" not in trace["request_policy"]
    assert "truncation_retries" not in trace["request_policy"]
    assert "llm_retry_events" not in trace
    assert "llm_retry_summary" not in trace


def test_consecutive_calls_write_current_terminal_trace_without_shared_state(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    first_context = _hypothesis_context()
    first_snapshot = build_prompt_turn_snapshot("hypothesis", first_context)
    creative.generate_direct_hypothesis(
        first_snapshot,
    )

    client.error = LLMProviderError("synthetic provider interruption")
    second_context = {**first_context, "branch_id": "branch-receipt-second"}
    second_snapshot = build_prompt_turn_snapshot("hypothesis", second_context)

    with pytest.raises(LLMProviderError):
        creative.generate_direct_hypothesis(
            second_snapshot,
        )

    traces = _trace_payloads(tmp_path)
    assert len(traces) == 2
    trace = next(item for item in traces if item["ok"] is False)
    assert trace["request_kind"] == "hypothesis"
    assert trace["ok"] is False
    assert trace["branch_id"] == second_context["branch_id"]
    assert trace["error"] == "synthetic provider interruption"
    assert trace["error_type"] == "LLMProviderError"


def test_provider_response_mechanical_diagnostics_reach_trace(
    tmp_path: Path,
) -> None:
    response_diagnostics = {
        "provider": "openai_compatible",
        "finish_reason": "length",
        "choice_count": 1,
        "choice_count_scope": "response.choices",
        "tool_call_count": 2,
        "tool_call_count_scope": "response.choices[0].message.tool_calls",
        "selected_choice_index": 0,
        "selected_choice_index_scope": "response.choices",
        "selected_tool_call_index": 0,
        "selected_tool_call_index_scope": ("response.choices[0].message.tool_calls"),
        "selected_tool_name": "generate_hypothesis",
        "selected_arguments_bytes": 321,
        "selected_arguments_json_valid": True,
        "arguments_representation": "sdk_argument_string_utf8",
        "arguments_value_type": "str",
    }
    usage = {"input_tokens": 123, "output_tokens": 45}
    client = _CaptureClient(
        response_diagnostics=response_diagnostics,
        usage=usage,
    )
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis = creative.generate_direct_hypothesis(
        snapshot,
    )

    assert hypothesis.hypothesis_text == _HYPOTHESIS_RESPONSE["hypothesis_text"]
    trace = _single_trace(tmp_path)
    assert trace["provider_response_diagnostics"] == response_diagnostics
    assert trace["llm_usage"] == usage


def test_provider_caller_resets_observations_before_policy_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _DirectOpenAIClient()
    client._last_usage_metadata = {"input_tokens": 123}
    client._last_response_diagnostics = {"finish_reason": "stale"}

    def fail_policy(**_kwargs):
        raise ValueError("synthetic provider policy failure")

    monkeypatch.setattr(client, "resolve_request_policy", fail_policy)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ValueError, match="synthetic provider policy failure"):
        creative.generate_direct_hypothesis(snapshot)

    assert client.get_last_usage_metadata() is None
    assert client.get_last_response_diagnostics() is None
    assert client.calls_seen == []


def test_provider_format_failure_keeps_mechanical_response_trace(
    tmp_path: Path,
) -> None:
    response_diagnostics = {
        "provider": "openai_compatible",
        "finish_reason": "length",
        "choice_count": 1,
        "choice_count_scope": "response.choices",
        "tool_call_count": 1,
        "tool_call_count_scope": "response.choices[0].message.tool_calls",
        "selected_choice_index": 0,
        "selected_choice_index_scope": "response.choices",
        "selected_tool_call_index": 0,
        "selected_tool_call_index_scope": ("response.choices[0].message.tool_calls"),
        "selected_tool_name": "generate_hypothesis",
        "selected_arguments_bytes": 17,
        "selected_arguments_json_valid": False,
        "arguments_representation": "sdk_argument_string_utf8",
        "arguments_value_type": "str",
    }
    client = _CaptureClient(
        error=LLMFormatError("synthetic invalid JSON"),
        response_diagnostics=response_diagnostics,
    )
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(LLMFormatError):
        creative.generate_direct_hypothesis(snapshot)

    trace = _single_trace(tmp_path)
    assert trace["ok"] is False
    assert trace["provider_response_diagnostics"] == response_diagnostics


def test_keyboard_interrupt_is_diagnosed_without_a_second_provider_call(
    tmp_path: Path,
) -> None:
    interruption = KeyboardInterrupt("operator interrupt")
    client = _CaptureClient(error=interruption)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", raw_context)

    with pytest.raises(KeyboardInterrupt) as caught:
        creative.generate_direct_hypothesis(snapshot)

    assert caught.value is interruption
    assert len(client.calls) == 1
    trace = _single_trace(tmp_path)
    assert trace["ok"] is False
    assert trace["error"] == "provider_call_interrupted"
    assert trace["error_type"] == "KeyboardInterrupt"


def test_parse_failure_keeps_successful_provider_terminal_trace(
    tmp_path: Path,
) -> None:
    client = _CaptureClient(response={"hypothesis_text": "missing required fields"})
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError):
        creative.generate_direct_hypothesis(snapshot)

    trace = _single_trace(tmp_path)
    assert trace["ok"] is True
    assert trace["response"] == {"hypothesis_text": "missing required fields"}


def test_direct_strict_parse_failure_is_terminal(
    tmp_path: Path,
) -> None:
    response = {
        **_HYPOTHESIS_RESPONSE,
        "material_difference": {"raw_trace": "provider-private reasoning"},
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError, match="forbidden"):
        creative.generate_direct_hypothesis(snapshot)

    assert len(client.calls) == 1
    trace = _single_trace(tmp_path)
    assert trace["ok"] is True
    assert trace["response"] == response


def test_unknown_context_sidecar_is_rejected_before_provider(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    context = {
        **_hypothesis_context(),
        "_scion_prompt_manifest": {
            "artifact_kind": "stale-sidecar",
        },
    }
    with pytest.raises(ValueError, match="unsupported proposal context field"):
        build_prompt_turn_snapshot("hypothesis", context)

    assert client.calls == []


def test_provider_trace_is_published_only_after_provider_returns(
    tmp_path: Path,
) -> None:
    trace_dir = tmp_path / "traces"

    class _InspectingClient(_CaptureClient):
        def call_with_tool(self, *args, **kwargs):
            assert not trace_dir.exists() or not list(trace_dir.iterdir())
            return super().call_with_tool(*args, **kwargs)

    client = _InspectingClient()
    creative = CreativeLayer(client, trace_dir=str(trace_dir))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis = creative.generate_direct_hypothesis(snapshot)

    assert hypothesis.hypothesis_text == _HYPOTHESIS_RESPONSE["hypothesis_text"]
    assert len(client.calls) == 1
    trace = _single_trace(tmp_path)
    assert trace["ok"] is True
    assert trace["response"] == _HYPOTHESIS_RESPONSE
    assert len(list(trace_dir.glob("*.json"))) == 1
    assert not list(trace_dir.glob("*.tmp"))


def test_provider_failure_is_not_masked_when_terminal_trace_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_error = LLMProviderError("synthetic provider failure")
    trace_error = PermissionError("synthetic terminal trace failure")

    def fail_terminal(*_args, **_kwargs):
        raise trace_error

    monkeypatch.setattr(provider_call._TraceWriter, "write_terminal", fail_terminal)
    client = _CaptureClient(error=provider_error)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(LLMProviderError) as caught:
        creative.generate_direct_hypothesis(snapshot)

    assert caught.value is provider_error
    assert len(client.calls) == 1
    assert not list((tmp_path / "traces").glob("*"))


def test_provider_success_terminal_trace_failure_keeps_valid_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_error = OSError("synthetic terminal trace failure")

    def fail_terminal(*_args, **_kwargs):
        raise trace_error

    monkeypatch.setattr(provider_call._TraceWriter, "write_terminal", fail_terminal)
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis = creative.generate_direct_hypothesis(snapshot)

    assert hypothesis.hypothesis_text == _HYPOTHESIS_RESPONSE["hypothesis_text"]
    assert len(client.calls) == 1
    assert not list((tmp_path / "traces").glob("*"))
