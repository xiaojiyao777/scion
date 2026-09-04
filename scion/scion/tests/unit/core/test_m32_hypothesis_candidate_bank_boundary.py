from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scion.core.campaign_composition import _normalize_campaign_boundaries
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import ContractResult, Decision, ExperimentStage
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.selected_hypothesis_basis import (
    canonical_selected_hypothesis_research_basis_json,
)
from scion.proposal.llm_client import LLMAuthError
from scion.tests.campaign_test_support import (
    _VALID_HYPOTHESIS,
    _VALID_PATCH,
    MockExperimentProtocol,
    _campaign,
    _make_protocol_result,
)

_K2_MODE = "bounded_hypothesis_candidates_v1"


class _NoCallClient:
    model = "k2-no-call-model"

    def call_with_tool(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("K2 composition unexpectedly dispatched a provider")


def _limits() -> CodeResearchLimits:
    return CodeResearchLimits(
        max_turns=4,
        max_hypothesis_candidates=2,
    )


def _complete_envelope() -> ResourceEnvelope:
    return ResourceEnvelope(provider_call_cap=12, outer_hardwall_sec=60)


def _research_history_record() -> dict[str, Any]:
    return {
        "schema_version": "scion.research_history.step.v1",
        "problem_id": "test_vrp",
        "hypothesis": {
            "text": "A prior ordinary local-search hypothesis.",
            "change_locus": "local_search",
            "action": "modify",
            "target_file": "operators/local_search.py",
            "predicted_direction": "improve",
            "target_weakness": "A prior local-search weakness.",
            "expected_effect": "A prior local-search effect.",
            "suggested_weight": None,
        },
        "patch": None,
        "outcome": {
            "outcome": "research_rejected",
            "stage": "proposal_code",
            "reason_code": "DEVELOPMENT_REGRESSION_REJECTED",
        },
        "protocol": None,
        "decision": None,
    }


def _selected_basis(
    *,
    history: bool,
    material_delta: str,
) -> dict[str, Any]:
    refs = ["source-0001"]
    nearest: list[str] = []
    if history:
        refs.append("history-0001")
        nearest.append("history-0001")
    return {
        "read_refs": refs,
        "nearest_prior_refs": nearest,
        "material_delta": material_delta,
        "alternatives_considered": ["Retain the current local search."],
        "observable_prediction": "The public development metric will change.",
        "falsification_condition": "Reject if that metric does not change.",
    }


@pytest.mark.parametrize(
    "envelope",
    (
        None,
        ResourceEnvelope(),
        ResourceEnvelope(outer_hardwall_sec=60),
        ResourceEnvelope(provider_call_cap=12),
        _complete_envelope(),
    ),
)
def test_k2_composition_keeps_global_resource_boundaries_optional(
    envelope: ResourceEnvelope | None,
) -> None:
    limits, normalized_envelope = _normalize_campaign_boundaries(
        code_research_limits=_limits(),
        resource_envelope=envelope,
    )

    assert limits == _limits()
    assert normalized_envelope == (envelope or ResourceEnvelope())


def test_k2_valid_composition_persists_config_and_projects_frozen_mode(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        llm_client=_NoCallClient(),
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )
    configured = json.loads(
        (tmp_path / "campaign" / "code_research_limits.json").read_text(
            encoding="utf-8"
        )
    )

    cm.finalize_requested_stop("operator_requested_stop")

    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert configured["max_hypothesis_candidates"] == 2
    assert cm.get_state()["proposal_runtime_mode"] == _K2_MODE
    assert status["proposal_runtime_mode"] == _K2_MODE
    assert summary["proposal_runtime_mode"] == _K2_MODE


class _K2ThenCodeAuthFailureClient:
    model = "k2-artifact-boundary-model"

    def __init__(self, *, loser: str, selected: str) -> None:
        loser_hypothesis = deepcopy(_VALID_HYPOTHESIS)
        loser_hypothesis["hypothesis_text"] = loser
        selected_hypothesis = deepcopy(_VALID_HYPOTHESIS)
        selected_hypothesis["hypothesis_text"] = selected
        basis = {
            "read_refs": ["source-0001"],
            "nearest_prior_refs": [],
            "material_delta": "This mechanism is distinct from current history.",
            "alternatives_considered": ["Retain the current local search."],
            "observable_prediction": "The public development metric will change.",
            "falsification_condition": "Reject if that metric does not change.",
        }
        self._hypothesis_responses = [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "stage_hypothesis_candidate",
                "slot": 1,
                "hypothesis": loser_hypothesis,
                "research_basis": deepcopy(basis),
            },
            {
                "action": "stage_hypothesis_candidate",
                "slot": 2,
                "hypothesis": selected_hypothesis,
                "research_basis": deepcopy(basis),
            },
            {"action": "select_hypothesis_candidate", "slot": 2},
        ]

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks
        if request_kind == "hypothesis_research_turn":
            return deepcopy(self._hypothesis_responses.pop(0))
        raise LLMAuthError("synthetic code auth stop")


def test_k2_loser_is_trace_only_and_never_authoritative(tmp_path: Path) -> None:
    loser = "K2_CAMPAIGN_TRACE_ONLY_LOSER_SENTINEL"
    selected = "K2_CAMPAIGN_SELECTED_SENTINEL"
    cm = _campaign(
        tmp_path,
        llm_client=_K2ThenCodeAuthFailureClient(loser=loser, selected=selected),
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )

    terminal = cm.run(requested_rounds=1)

    assert terminal.stop_reason == "execution_blocked_infra"
    assert len(cm._step_history) == 1
    step = cm._step_history[0]
    assert step.hypothesis is not None
    assert step.hypothesis.hypothesis_text == selected
    assert loser not in repr(cm._step_history)
    trace_text = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "campaign" / "llm_traces").glob("*.json")
    )
    assert loser in trace_text

    authoritative_files = [
        path
        for path in (tmp_path / "campaign").rglob("*")
        if path.is_file()
        and "llm_traces" not in path.relative_to(tmp_path / "campaign").parts
    ]
    assert authoritative_files
    for path in authoritative_files:
        assert loser.encode() not in path.read_bytes(), path
    status_text = (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    summary_text = (tmp_path / "campaign" / "campaign_summary.json").read_text(
        encoding="utf-8"
    )
    assert selected in summary_text
    assert json.loads(status_text)["proposal_runtime_mode"] == _K2_MODE
    assert json.loads(summary_text)["proposal_runtime_mode"] == _K2_MODE


class _K2SelectedBasisThenCodeAuthFailureClient:
    model = "k2-selected-basis-model"

    def __init__(self) -> None:
        unselected = deepcopy(_VALID_HYPOTHESIS)
        unselected["hypothesis_text"] = "Unselected history-informed candidate."
        selected = deepcopy(_VALID_HYPOTHESIS)
        selected["hypothesis_text"] = "Selected source-only candidate."
        self.unselected_basis = _selected_basis(
            history=True,
            material_delta="UNSELECTED_HISTORY_BASIS_SENTINEL",
        )
        self.selected_basis = _selected_basis(
            history=False,
            material_delta="SELECTED_SOURCE_ONLY_BASIS_SENTINEL",
        )
        self._hypothesis_responses = [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "stage_hypothesis_candidate",
                "slot": 1,
                "hypothesis": unselected,
                "research_basis": deepcopy(self.unselected_basis),
            },
            {
                "action": "stage_hypothesis_candidate",
                "slot": 2,
                "hypothesis": selected,
                "research_basis": deepcopy(self.selected_basis),
            },
            {"action": "select_hypothesis_candidate", "slot": 2},
        ]

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks
        if request_kind == "hypothesis_research_turn":
            return deepcopy(self._hypothesis_responses.pop(0))
        raise LLMAuthError("synthetic code auth stop")


class _K1SelectedBasisClient:
    model = "k1-selected-basis-model"

    def __init__(self) -> None:
        self.selected_basis = _selected_basis(
            history=True,
            material_delta="K1_SELECTED_HISTORY_BASIS_SENTINEL",
        )
        self._hypothesis_responses = [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "read_history", "ref": "history-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": deepcopy(_VALID_HYPOTHESIS),
                "research_basis": deepcopy(self.selected_basis),
            },
        ]

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks
        if request_kind == "hypothesis_research_turn":
            return deepcopy(self._hypothesis_responses.pop(0))
        raise LLMAuthError("synthetic code auth stop")


def _summary_steps(tmp_path: Path) -> list[dict[str, Any]]:
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(
            encoding="utf-8"
        )
    )
    return summary["steps"]


def test_k2_summary_uses_only_the_selected_slot_research_basis(
    tmp_path: Path,
) -> None:
    client = _K2SelectedBasisThenCodeAuthFailureClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        research_history=[_research_history_record()],
        resource_envelope=_complete_envelope(),
        code_research_limits=CodeResearchLimits(
            max_turns=5,
            max_read_calls=2,
            max_hypothesis_candidates=2,
        ),
    )

    terminal = cm.run(requested_rounds=1)

    assert terminal.stop_reason == "execution_blocked_infra"
    assert len(cm._step_history) == 1
    assert (
        cm._step_history[0].selected_hypothesis_research_basis
        == client.selected_basis
    )
    assert (
        _summary_steps(tmp_path)[0]["selected_hypothesis_research_basis"]
        == client.selected_basis
    )
    summary_basis = _summary_steps(tmp_path)[0][
        "selected_hypothesis_research_basis"
    ]
    assert summary_basis == client.selected_basis
    assert summary_basis["read_refs"] == ["source-0001"]
    assert summary_basis["nearest_prior_refs"] == []
    assert client.unselected_basis["material_delta"] not in json.dumps(
        _summary_steps(tmp_path),
        sort_keys=True,
    )


def test_k1_summary_preserves_the_selected_history_basis(tmp_path: Path) -> None:
    client = _K1SelectedBasisClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        research_history=[_research_history_record()],
        resource_envelope=ResourceEnvelope(provider_call_cap=6),
        code_research_limits=CodeResearchLimits(
            max_turns=3,
            max_read_calls=2,
        ),
    )

    terminal = cm.run(requested_rounds=1)

    assert terminal.stop_reason == "execution_blocked_infra"
    basis = _summary_steps(tmp_path)[0]["selected_hypothesis_research_basis"]
    assert basis == client.selected_basis
    assert basis["read_refs"] == ["source-0001", "history-0001"]
    assert basis["nearest_prior_refs"] == ["history-0001"]


def test_selected_basis_persists_on_post_h_workspace_outcome(
    tmp_path: Path,
) -> None:
    client = _K2PromotionClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )
    cm._proposal_pipeline.code_development_evaluator = _PassingDevelopmentEvaluator()
    cm._explore_step_pipeline.setup_workspace = lambda _branch: None

    result = cm.run_one_step()

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == "WORKSPACE_SETUP_FAILED"
    row = next(
        row
        for row in cm._registry.query_by_branch(result.branch_id)
        if row["event_kind"] == "workspace_execution_outcome"
    )
    assert row["selected_hypothesis_research_basis_json"] == (
        canonical_selected_hypothesis_research_basis_json(client.selected_basis)
    )
    assert json.loads(row["execution_outcome_provenance_json"]) == {
        "stage": "workspace_setup"
    }
    assert cm._step_history[-1].selected_hypothesis_research_basis == (
        client.selected_basis
    )


def test_selected_basis_survives_early_hypothesis_contract_rejection(
    tmp_path: Path,
) -> None:
    client = _K1SelectedBasisClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        research_history=[_research_history_record()],
        resource_envelope=ResourceEnvelope(provider_call_cap=4),
        code_research_limits=CodeResearchLimits(
            max_turns=3,
            max_read_calls=2,
        ),
    )
    cm._explore_step_pipeline.contract_gate.validate_hypothesis = (
        lambda *_args, **_kwargs: ContractResult(
            passed=False,
            checks=(),
            failure_reason="synthetic early H rejection",
        )
    )

    result = cm.run_one_step()
    cm._write_campaign_summary()

    assert result.failure_stage == "hypothesis_contract"
    assert len(cm._step_history) == 1
    assert (
        cm._step_history[0].selected_hypothesis_research_basis
        == client.selected_basis
    )
    rejection_rows = [
        row
        for row in cm._registry.query_by_branch(result.branch_id)
        if row["event_kind"] == "research_rejection"
    ]
    assert len(rejection_rows) == 1
    assert json.loads(
        rejection_rows[0]["selected_hypothesis_research_basis_json"]
    ) == client.selected_basis


def test_direct_h_summary_has_no_selected_research_basis(tmp_path: Path) -> None:
    cm = _campaign(tmp_path)

    terminal = cm.run(requested_rounds=1)

    assert terminal.completed
    assert len(cm._step_history) == 1
    assert cm._step_history[0].selected_hypothesis_research_basis is None
    assert (
        _summary_steps(tmp_path)[0]["selected_hypothesis_research_basis"] is None
    )
    experiment = next(
        row
        for row in cm._registry.query_by_branch(cm._step_history[0].branch_id)
        if row["event_kind"] == "experiment"
    )
    assert experiment["selected_hypothesis_research_basis_json"] is None
    history = json.loads(
        (tmp_path / "campaign" / "research_history.jsonl").read_text(
            encoding="utf-8"
        )
    )
    assert history["selected_hypothesis_research_basis"] is None


class _K2PromotionClient:
    model = "k2-normal-promotion-model"

    def __init__(self) -> None:
        first = deepcopy(_VALID_HYPOTHESIS)
        first["hypothesis_text"] = "Try the first bounded research candidate."
        second = deepcopy(_VALID_HYPOTHESIS)
        second["hypothesis_text"] = "Select the second bounded research candidate."
        basis = {
            "read_refs": ["source-0001"],
            "nearest_prior_refs": [],
            "material_delta": "This changes the local-search mechanism.",
            "alternatives_considered": ["Keep the current local search."],
            "observable_prediction": "The development metric will improve.",
            "falsification_condition": "Reject if the metric does not improve.",
        }
        self.selected_basis = deepcopy(basis)
        self._hypothesis = [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "stage_hypothesis_candidate",
                "slot": 1,
                "hypothesis": first,
                "research_basis": deepcopy(basis),
            },
            {
                "action": "stage_hypothesis_candidate",
                "slot": 2,
                "hypothesis": second,
                "research_basis": deepcopy(basis),
            },
            {"action": "select_hypothesis_candidate", "slot": 2},
        ]
        self._code = [
            {"action": "revise", "patch": deepcopy(_VALID_PATCH)},
            {"action": "test_patch"},
            {"action": "ready"},
        ]

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks
        if request_kind == "hypothesis_research_turn":
            return deepcopy(self._hypothesis.pop(0))
        if request_kind == "code_research_turn":
            return deepcopy(self._code.pop(0))
        if request_kind == "code_research_finalize":
            return {"outcome": "finalize_patch"}
        raise AssertionError(f"unexpected request kind: {request_kind}")


class _PassingDevelopmentEvaluator:
    def evaluate(self, **_kwargs: Any) -> Any:
        return SimpleNamespace(
            provider_projection=lambda: {
                "outcome": "passed",
                "checks": [{"name": "D3_unit_tests", "outcome": "passed"}],
                "counts": {"total": 1, "passed": 1, "failed": 0},
            }
        )


def test_k2_normal_campaign_reaches_promotion_through_all_protocol_stages(
    tmp_path: Path,
) -> None:
    protocol = MockExperimentProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, "pass"),
            _make_protocol_result(ExperimentStage.FROZEN, "pass"),
        ]
    )
    client = _K2PromotionClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        experiment_protocol=protocol,
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )
    cm._proposal_pipeline.code_development_evaluator = _PassingDevelopmentEvaluator()

    terminal = cm.run(requested_rounds=3)

    assert terminal.completed
    assert terminal.protocol_stage_counts == {
        "screening": 1,
        "validation": 1,
        "frozen": 1,
    }
    assert [step.decision for step in cm._step_history] == [
        Decision.QUEUE_VALIDATE,
        Decision.QUEUE_FROZEN,
        Decision.PROMOTE,
    ]
    assert [
        step.selected_hypothesis_research_basis for step in cm._step_history
    ] == [client.selected_basis] * 3
    assert [
        step["selected_hypothesis_research_basis"]
        for step in _summary_steps(tmp_path)
    ] == [client.selected_basis] * 3
    with (tmp_path / "campaign" / "research_history.jsonl").open(
        encoding="utf-8"
    ) as source:
        visible_history = [json.loads(line) for line in source]
    assert len(visible_history) == 1
    assert visible_history[0]["selected_hypothesis_research_basis"] == (
        client.selected_basis
    )
    lineage = cm._registry.query_by_branch(cm._step_history[0].branch_id)
    evaluated = [row for row in lineage if row["event_kind"] == "experiment"]
    assert len(evaluated) == 3
    for row, step in zip(reversed(evaluated), cm._step_history, strict=True):
        assert json.loads(row["selected_hypothesis_research_basis_json"]) == (
            step.selected_hypothesis_research_basis
        )
        assert row["execution_outcome"] == "evaluated"
        assert row["execution_outcome_reason_code"] == "EVALUATION_COMPLETED"
        assert json.loads(row["execution_outcome_provenance_json"]) == {
            "stage": step.protocol_result.stage.value
        }
    assert cm.get_state()["champion_version"] == 2
    assert all(branch.state.value != "parked_lineage" for branch in cm._branch_ctrl._branches.values())


def test_selected_basis_persists_on_promotion_infrastructure_outcome(
    tmp_path: Path,
) -> None:
    protocol = MockExperimentProtocol(
        results=[
            _make_protocol_result(ExperimentStage.SCREENING, "pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, "pass"),
            _make_protocol_result(ExperimentStage.FROZEN, "pass"),
        ]
    )
    client = _K2PromotionClient()
    cm = _campaign(
        tmp_path,
        llm_client=client,
        experiment_protocol=protocol,
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )
    cm._proposal_pipeline.code_development_evaluator = _PassingDevelopmentEvaluator()

    first = cm.run_one_step()
    assert first.decision is Decision.QUEUE_VALIDATE
    second = cm.run_one_step()
    assert second.decision is Decision.QUEUE_FROZEN

    def fail_promotion(_branch: Any) -> None:
        raise OSError("synthetic promotion storage failure")

    cm._decision_finalizer.promote_branch = fail_promotion
    result = cm.run_one_step()

    assert result.execution_outcome is not None
    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == "PROMOTION_FAILED"
    row = next(
        row
        for row in cm._registry.query_by_branch(result.branch_id)
        if row["event_kind"] == "promotion_execution_outcome"
    )
    assert row["selected_hypothesis_research_basis_json"] == (
        canonical_selected_hypothesis_research_basis_json(client.selected_basis)
    )
