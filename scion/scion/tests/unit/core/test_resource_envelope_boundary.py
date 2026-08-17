from __future__ import annotations

import inspect
import json
import signal
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignOuterHardwall,
    _CampaignSignalStop,
)
from scion.core.campaign_loop import CampaignLoop, CampaignRunResult
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
    ResourceEnvelope,
    normalize_resource_envelope,
    write_resource_envelope,
)
from scion.core.step_result import StepResult
from scion.proposal.engine import CreativeLayer, build_prompt_turn_snapshot
from scion.runtime import subprocess_runner
from scion.runtime.subprocess_runner import LocalSubprocessRunner

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]

_HYPOTHESIS_RESPONSE = {
    "hypothesis_text": "Try one bounded generic improvement.",
    "change_locus": "generic_search",
    "action": "modify",
    "target_file": "operators/generic.py",
    "predicted_direction": "improve",
    "target_weakness": "The current generic operation is weak.",
    "expected_effect": "Improve the declared objective.",
}
_PATCH_RESPONSE = {
    "file_path": "operators/generic.py",
    "action": "modify",
    "edit_intent": "full_file",
    "content_after": "def improve(value):\n    return value + 1\n",
    "full_file_reason": "Replace the complete small declared target.",
    "evidence_refs": [],
}


class _KindClient:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        assert system_blocks
        self.calls.append(request_kind)
        if request_kind == "hypothesis":
            return dict(_HYPOTHESIS_RESPONSE)
        if request_kind == "code":
            return dict(_PATCH_RESPONSE)
        raise AssertionError(f"unexpected request kind: {request_kind}")


class _InterruptedProc:
    pid = 12345
    returncode: int | None = None
    stdout = None
    stderr = None

    def communicate(self, *, timeout: int) -> tuple[bytes, bytes]:
        assert timeout > 0
        raise KeyboardInterrupt("operator interrupt")

    def poll(self) -> int | None:
        return self.returncode


class _SignalInterruptedProc(_InterruptedProc):
    def communicate(self, *, timeout: int) -> tuple[bytes, bytes]:
        assert timeout > 0
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        handler(signal.SIGTERM, None)
        raise AssertionError("hardwall signal handler must interrupt communicate")


class _StopManager:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    def request_stop(self, reason: str) -> None:
        self.reasons.append(reason)


class _PipelineRuntime:
    spec = SimpleNamespace()

    def build_hypothesis_context(self, **_kwargs: Any) -> dict[str, Any]:
        return _hypothesis_snapshot().structured_context

    def build_code_context(self, **_kwargs: Any) -> dict[str, Any]:
        return _code_snapshot().structured_context


def _hypothesis_snapshot():
    return build_prompt_turn_snapshot(
        "hypothesis",
        {
            "problem_summary": "Generic optimization subject.",
            "branch_id": "resource-envelope-branch",
            "research_surfaces": [
                {"name": "generic_search", "kind": "operator"},
            ],
            "available_actions": ["modify"],
            "existing_target_files": ["operators/generic.py"],
            "champion_operators_code": (
                "### operators/generic.py\ndef improve(value):\n    return value\n"
            ),
            "champion_stats": {},
        },
    )


def _code_snapshot():
    return build_prompt_turn_snapshot(
        "code",
        {
            "problem_summary": "Generic optimization subject.",
            "branch_id": "resource-envelope-branch",
            "approved_hypothesis": dict(_HYPOTHESIS_RESPONSE),
            "editable_source_context": {
                "approved_target": "operators/generic.py",
                "sources": [
                    {
                        "path": "operators/generic.py",
                        "content": "def improve(value):\n    return value\n",
                    }
                ],
                "target_api_guidance": "",
            },
            "operator_interface_spec": "def improve(value): ...",
            "editable_patterns": ["operators/*.py"],
            "frozen_patterns": ["solver.py"],
        },
    )


def test_one_budget_is_shared_by_h_and_c_and_blocks_before_extra_dispatch() -> None:
    budget = ProviderCallBudget(2)
    client = _KindClient()
    creative = CreativeLayer(client, provider_call_budget=budget)

    creative.generate_direct_hypothesis(_hypothesis_snapshot())
    creative.generate_direct_code(_code_snapshot())

    with pytest.raises(ProviderCallCapExhausted) as raised:
        creative.generate_direct_hypothesis(_hypothesis_snapshot())
    assert raised.value.request_kind == "hypothesis"
    assert raised.value.cap == 2
    assert raised.value.used == 2
    assert budget.used == 2
    assert client.calls == ["hypothesis", "code"]


def test_cap_one_allows_h_then_blocks_c_without_a_client_call() -> None:
    budget = ProviderCallBudget(1)
    client = _KindClient()
    creative = CreativeLayer(client, provider_call_budget=budget)

    creative.generate_direct_hypothesis(_hypothesis_snapshot())

    with pytest.raises(ProviderCallCapExhausted) as raised:
        creative.generate_direct_code(_code_snapshot())
    assert raised.value.request_kind == "code"
    assert budget.used == 1
    assert client.calls == ["hypothesis"]


def test_cap_exhaustion_becomes_one_typed_campaign_stop() -> None:
    budget = ProviderCallBudget(1)
    client = _KindClient()
    creative = CreativeLayer(client, provider_call_budget=budget)
    branch = Branch(
        branch_id="resource-envelope-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path="/unused-by-fake-runtime",
    )
    pipeline = ProposalPipeline(
        creative=creative,
        problem_runtime=_PipelineRuntime(),
        branch_workspaces={},
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
        step_history=[],
        mark_balance_exhausted=lambda: None,
    )

    hypothesis_attempt = pipeline.generate_hypothesis(branch)
    assert hypothesis_attempt.proposal is not None
    code_attempt = pipeline.generate_code(branch, hypothesis_attempt.proposal)
    assert code_attempt.proposal is None
    assert code_attempt.execution_outcome is not None
    assert code_attempt.execution_outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert code_attempt.execution_outcome.reason_code == "PROVIDER_CALL_CAP_EXHAUSTED"

    step_calls = 0

    def run_one_step() -> StepResult:
        nonlocal step_calls
        step_calls += 1
        return StepResult(
            action="explore",
            execution_outcome=code_attempt.execution_outcome,
        )

    loop = CampaignLoop(
        write_status=lambda **_kwargs: None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda _reason: None,
        run_one_step=run_one_step,
        write_terminal_artifacts=lambda _result: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda _timeout: None,
    )
    result = loop.run(requested_rounds=1)

    assert result.stop_reason == "execution_resource_exhausted"
    assert result.evaluated_rounds == 0
    assert result.scheduled_calls == 1
    assert result.execution_outcome_counts["resource_exhausted"] == 1
    assert step_calls == 1
    assert budget.used == 1
    assert client.calls == ["hypothesis"]


def test_absent_limits_preserve_unbounded_legacy_provider_behavior() -> None:
    envelope = normalize_resource_envelope(None)
    budget = ProviderCallBudget(envelope.provider_call_cap)
    client = _KindClient()
    creative = CreativeLayer(client, provider_call_budget=budget)

    for _index in range(3):
        creative.generate_direct_hypothesis(_hypothesis_snapshot())
        creative.generate_direct_code(_code_snapshot())

    assert envelope == ResourceEnvelope()
    assert envelope.to_primitive() == {}
    assert budget.cap is None
    assert budget.used == 6
    assert client.calls == ["hypothesis", "code"] * 3


@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        ({"provider_call_cap": 0}, ValueError),
        ({"provider_call_cap": -1}, ValueError),
        ({"provider_call_cap": True}, TypeError),
        ({"outer_hardwall_sec": 0}, ValueError),
        ({"outer_hardwall_sec": 1.5}, TypeError),
        ({"unknown": 1}, ValueError),
    ],
)
def test_resource_limits_fail_closed_without_aliases(
    value: dict[str, Any],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        normalize_resource_envelope(value)


def test_keyboard_interrupt_kills_and_unregisters_active_fake_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _InterruptedProc()
    killed: list[_InterruptedProc] = []

    def kill(active: _InterruptedProc) -> None:
        killed.append(active)
        active.returncode = -9

    monkeypatch.setattr(subprocess_runner.subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess_runner, "_kill_proc", kill)
    runner = LocalSubprocessRunner()

    with pytest.raises(KeyboardInterrupt, match="operator interrupt"):
        runner.run_solver(
            workdir=str(tmp_path),
            instance_path=str(tmp_path / "instance.json"),
            seed=7,
            time_limit_sec=5,
            registry_path=str(tmp_path / "registry.json"),
        )

    assert killed == [proc]
    assert runner._active_procs == set()


def test_hardwall_watchdog_requests_one_sigterm_without_domain_work() -> None:
    delivered = threading.Event()
    calls: list[tuple[int, int]] = []

    def deliver(pid: int, signum: int) -> None:
        calls.append((pid, signum))
        delivered.set()

    hardwall = _CampaignOuterHardwall(
        0.01,
        kill_process=deliver,
        process_id=lambda: 2468,
    )
    with hardwall:
        assert delivered.wait(timeout=0.5)

    assert hardwall.expired.is_set()
    assert calls == [(2468, signal.SIGTERM)]


def test_hardwall_signal_kills_active_fake_child_and_has_typed_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _SignalInterruptedProc()
    killed: list[_SignalInterruptedProc] = []

    def kill(active: _SignalInterruptedProc) -> None:
        killed.append(active)
        active.returncode = -9

    monkeypatch.setattr(subprocess_runner.subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess_runner, "_kill_proc", kill)
    runner = LocalSubprocessRunner()
    manager = _StopManager()
    hardwall = _CampaignOuterHardwall(None)
    hardwall.expired.set()

    with (
        _campaign_signal_handlers(manager, hardwall=hardwall),
        pytest.raises(_CampaignSignalStop) as raised,
    ):
        runner.run_solver(
            workdir=str(tmp_path),
            instance_path=str(tmp_path / "instance.json"),
            seed=9,
            time_limit_sec=5,
            registry_path=str(tmp_path / "registry.json"),
        )

    assert raised.value.reason == "OUTER_HARDWALL_EXCEEDED"
    assert raised.value.exit_status == 124
    assert manager.reasons == ["OUTER_HARDWALL_EXCEEDED"]
    assert killed == [proc]
    assert runner._active_procs == set()
    terminal = CampaignRunResult.empty(1).terminalized(
        raised.value.reason,
        interrupted=True,
    )
    assert terminal.stop_reason == "OUTER_HARDWALL_EXCEEDED"
    assert terminal.execution_outcome_counts["interrupted"] == 1
    assert terminal.last_execution_outcome == {
        "outcome": "interrupted",
        "reason_code": "OUTER_HARDWALL_EXCEEDED",
        "stage": "campaign",
    }


def test_absent_hardwall_starts_no_thread_and_delivers_no_signal() -> None:
    calls: list[tuple[int, int]] = []
    hardwall = _CampaignOuterHardwall(
        None,
        kill_process=lambda pid, signum: calls.append((pid, signum)),
        process_id=lambda: 2468,
    )

    with hardwall:
        assert hardwall._thread is None
        assert not hardwall.expired.is_set()

    assert calls == []


def test_configured_envelope_is_one_ordinary_file_without_sidecars(
    tmp_path: Path,
) -> None:
    envelope = ResourceEnvelope(provider_call_cap=2, outer_hardwall_sec=30)

    path = write_resource_envelope(str(tmp_path), envelope)

    assert path == tmp_path / "resource_envelope.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "provider_call_cap": 2,
        "outer_hardwall_sec": 30,
    }
    assert [item.name for item in tmp_path.iterdir()] == ["resource_envelope.json"]
    with pytest.raises(FileExistsError):
        write_resource_envelope(str(tmp_path), envelope)


def test_absent_envelope_writes_no_artifact(tmp_path: Path) -> None:
    assert write_resource_envelope(str(tmp_path), ResourceEnvelope()) is None
    assert list(tmp_path.iterdir()) == []


def test_resource_envelope_has_no_domain_or_self_proof_lifecycle() -> None:
    source = inspect.getsource(
        __import__(
            "scion.core.resource_envelope",
            fromlist=["resource_envelope"],
        )
    ).casefold()
    forbidden = {
        "authorization",
        "cvrp",
        "hash",
        "identity",
        "lease",
        "m7",
        "receipt",
        "register",
        "signature",
        "warehouse",
    }
    for token in forbidden:
        assert token not in source
