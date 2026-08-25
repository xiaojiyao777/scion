from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import ContractResult
from scion.core.qualification import (
    QualificationOnlyConfig,
    QualificationProposalBudgetExhausted,
)
from scion.core.resource_envelope import ResourceEnvelope
from scion.proposal.llm_client import LLMProviderError
from scion.tests.campaign_test_support import (
    _VALID_HYPOTHESIS,
    _VALID_PATCH,
    _campaign,
)


def _basis() -> dict[str, Any]:
    return {
        "read_refs": ["source-0001"],
        "nearest_prior_refs": [],
        "material_delta": "This changes one mechanism from the current source.",
        "alternatives_considered": ["Retain the current mechanism."],
        "observable_prediction": "The public development result will change.",
        "falsification_condition": "Reject if that result does not change.",
    }


def _stage(slot: int, hypothesis: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "stage_hypothesis_candidate",
        "slot": slot,
        "hypothesis": hypothesis,
        "research_basis": _basis(),
    }


def _runtime_artifacts(cm: Any, tmp_path: Path) -> tuple[dict[str, Any], ...]:
    state = cm.get_state()
    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert state["proposal_runtime"] == status["proposal_runtime"]
    assert status["proposal_runtime"] == summary["proposal_runtime"]
    return (
        state["proposal_runtime"],
        status["proposal_runtime"],
        summary["proposal_runtime"],
    )


class _K1CodeFailureClient:
    model = "m32-d1-k1-code-failure"

    def __init__(self) -> None:
        self._hypothesis = [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": deepcopy(_VALID_HYPOTHESIS),
                "research_basis": _basis(),
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
            return deepcopy(self._hypothesis.pop(0))
        raise LLMProviderError("synthetic code stop")


def test_k1_completed_selected_exported_and_provider_failure_are_one_closed_row(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        llm_client=_K1CodeFailureClient(),
        code_research_limits=CodeResearchLimits(max_turns=3),
        resource_envelope=ResourceEnvelope(provider_call_cap=8),
    )

    terminal = cm.run(1)
    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    row = runtime["attempts"][0]

    assert terminal.stop_reason == "execution_blocked_infra"
    assert row == {
        "round_num": 1,
        "accounting_state": "closed",
        "provider_calls": {
            "budget_admitted": 3,
            "by_request_kind": {
                "hypothesis": 0,
                "hypothesis_research_turn": 2,
                "code": 0,
                "code_research_turn": 1,
                "code_research_finalize": 0,
                "other": 0,
            },
        },
        "hypothesis_candidates_completed": 1,
        "hypothesis_candidates_selected": 1,
        "hypotheses_exported": 1,
        "patches_completed": 0,
        "code_candidates_ready": 0,
    }


class _K2CodeFailureClient:
    model = "m32-d1-k2-code-failure"

    def __init__(self, *, loser: str, selected: str) -> None:
        first = deepcopy(_VALID_HYPOTHESIS)
        first["hypothesis_text"] = loser
        second = deepcopy(_VALID_HYPOTHESIS)
        second["hypothesis_text"] = selected
        duplicate = deepcopy(first)
        duplicate_basis = _basis()
        duplicate_basis["material_delta"] = "DUPLICATE_BASIS_PRIVATE_SENTINEL"
        self._hypothesis = [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, first),
            {
                **_stage(2, duplicate),
                "research_basis": duplicate_basis,
            },
            _stage(2, second),
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
            return deepcopy(self._hypothesis.pop(0))
        raise LLMProviderError("synthetic K2 code stop")


def test_k2_counts_only_accepted_slots_and_loser_stays_trace_only(
    tmp_path: Path,
) -> None:
    loser = "D1_K2_UNSELECTED_PRIVATE_BODY"
    selected = "D1_K2_SELECTED_BODY"
    cm = _campaign(
        tmp_path,
        llm_client=_K2CodeFailureClient(loser=loser, selected=selected),
        qualification_only=QualificationOnlyConfig(max_proposal_attempts=1),
        resource_envelope=ResourceEnvelope(
            provider_call_cap=10,
            outer_hardwall_sec=60,
        ),
        code_research_limits=CodeResearchLimits(
            max_turns=5,
            max_hypothesis_candidates=2,
        ),
    )

    terminal = cm.run(1)
    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    row = runtime["attempts"][0]

    assert terminal.stop_reason == "execution_blocked_infra"
    assert row["accounting_state"] == "closed"
    assert row["provider_calls"]["budget_admitted"] == 6
    assert row["hypothesis_candidates_completed"] == 2
    assert row["hypothesis_candidates_selected"] == 1
    assert row["hypotheses_exported"] == 1
    assert row["patches_completed"] == 0
    assert row["code_candidates_ready"] == 0
    assert loser in "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "campaign" / "llm_traces").glob("*.json")
    )
    for path in (tmp_path / "campaign").rglob("*"):
        if (
            path.is_file()
            and "llm_traces" not in path.relative_to(tmp_path / "campaign").parts
        ):
            assert loser.encode() not in path.read_bytes(), path


class _K1ReadyPatchClient:
    model = "m32-d1-k1-ready-patch"

    def __init__(self) -> None:
        self._hypothesis = [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": deepcopy(_VALID_HYPOTHESIS),
                "research_basis": _basis(),
            },
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


@pytest.mark.parametrize(
    ("boundary", "expected_ready"),
    (("patch_contract", 0), ("materialization", 0), ("success", 1)),
)
def test_patch_completion_and_code_ready_use_distinct_physical_boundaries(
    tmp_path: Path,
    boundary: str,
    expected_ready: int,
) -> None:
    cm = _campaign(
        tmp_path,
        llm_client=_K1ReadyPatchClient(),
        code_research_limits=CodeResearchLimits(max_turns=3),
        resource_envelope=ResourceEnvelope(provider_call_cap=10),
    )
    cm._proposal_pipeline.code_development_evaluator = _PassingDevelopmentEvaluator()
    if boundary == "patch_contract":
        cm._explore_step_pipeline.contract_gate.validate_patch = (
            lambda *_args, **_kwargs: ContractResult(
                passed=False,
                checks=(),
                failure_reason="synthetic patch contract rejection",
            )
        )
    elif boundary == "materialization":
        cm._explore_step_pipeline.apply_patch = lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("synthetic materialization failure"))

    cm.run(1)
    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    row = runtime["attempts"][0]

    assert row["hypothesis_candidates_completed"] == 1
    assert row["hypothesis_candidates_selected"] == 1
    assert row["hypotheses_exported"] == 1
    assert row["patches_completed"] == 1
    assert row["code_candidates_ready"] == expected_ready


class _InterruptClient:
    model = "m32-d1-interrupt"

    def call_with_tool(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise KeyboardInterrupt("synthetic admitted interrupt")


def test_provider_interrupt_is_counted_and_scope_closes_interrupted(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        llm_client=_InterruptClient(),
        code_research_limits=CodeResearchLimits(max_turns=1),
        resource_envelope=ResourceEnvelope(provider_call_cap=2),
    )

    with pytest.raises(KeyboardInterrupt, match="admitted interrupt"):
        cm.run(1)

    active = cm.get_state()["proposal_runtime"]
    assert active["attempts"][0]["accounting_state"] == "interrupted"
    assert active["attempts"][0]["provider_calls"]["budget_admitted"] == 1
    cm.finalize_requested_stop("operator_requested_stop")
    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    assert runtime["attempts"][0]["accounting_state"] == "interrupted"
    assert runtime["provider_calls"]["budget_admitted"] == 1


def test_order_is_heartbeat_then_reserve_then_begin_and_exception_is_unresolved(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        code_research_limits=CodeResearchLimits(max_turns=1),
        resource_envelope=ResourceEnvelope(provider_call_cap=2),
    )
    pipeline = cm._explore_step_pipeline
    events: list[str] = []
    original_status = pipeline.update_status_progress
    original_reserve = pipeline.reserve_proposal_attempt
    original_scope = pipeline.proposal_attempt_scope

    def status(payload: dict[str, Any] | None) -> None:
        if payload is not None and payload.get("phase") == "proposal_hypothesis":
            events.append("heartbeat")
        original_status(payload)

    def reserve() -> None:
        events.append("reserve")
        original_reserve()

    @contextmanager
    def scope(round_num: int) -> Iterator[None]:
        events.append("begin")
        with original_scope(round_num):
            yield

    pipeline.update_status_progress = status
    pipeline.reserve_proposal_attempt = reserve
    pipeline.proposal_attempt_scope = scope
    pipeline.generate_hypothesis = lambda _branch: (_ for _ in ()).throw(
        RuntimeError("synthetic unhandled explore failure")
    )

    with pytest.raises(RuntimeError, match="unhandled explore failure"):
        cm.run(1)

    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    assert events[:3] == ["heartbeat", "reserve", "begin"]
    assert runtime["attempts"][0]["accounting_state"] == "unresolved"
    assert runtime["attempts"][0]["provider_calls"]["budget_admitted"] == 0


def test_qualification_reserve_failure_creates_no_attempt_row(tmp_path: Path) -> None:
    cm = _campaign(
        tmp_path,
        qualification_only=QualificationOnlyConfig(max_proposal_attempts=1),
        code_research_limits=CodeResearchLimits(max_turns=1),
        resource_envelope=ResourceEnvelope(
            provider_call_cap=2,
            outer_hardwall_sec=30,
        ),
    )
    cm._explore_step_pipeline.reserve_proposal_attempt = lambda: (_ for _ in ()).throw(
        QualificationProposalBudgetExhausted("synthetic reserve rejection")
    )

    cm.run(1)
    runtime, _status, _summary = _runtime_artifacts(cm, tmp_path)
    assert runtime["attempts"] == []
    assert runtime["provider_calls"]["budget_admitted"] == 0
