from __future__ import annotations

import json
import signal
import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest
from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignOuterHardwall,
    _completion_from_run_result,
)
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.campaign_loop import CampaignRunResult
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
    ResourceEnvelope,
    normalize_resource_envelope,
    write_resource_envelope,
)
from scion.proposal.engine.provider_call import PromptTurnSnapshot, ProviderCaller
from scion.proposal.mock_client import MockLLMClient

from .campaign_control_boundaries_test_support import (
    _VALID_CODE,
    _AlwaysPassVerification,
    _make_champion,
    _make_spec,
    _MockProtocol,
)
from .proposal_pipeline_test_support import FakeCreative, _pipeline


class _Client:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def call_with_tool(
        self,
        _prompt,
        _tool,
        _model,
        *,
        system_blocks,
        request_kind,
    ):
        self.calls.append(request_kind)
        return {"ok": True}


def _snapshot(kind: str) -> PromptTurnSnapshot:
    return PromptTurnSnapshot(
        render_kind=kind,
        system_blocks=(),
        user_prompt=f"{kind} prompt",
        provider_tool={"name": kind},
        structured_context_json=json.dumps({"phase": kind}),
    )


def test_h_and_c_share_one_provider_call_cap_without_extra_dispatch(
    tmp_path,
) -> None:
    client = _Client()
    budget = ProviderCallBudget(2)
    caller = ProviderCaller(
        client,
        "fake-model",
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
    )

    caller.call(request_kind="hypothesis", tool={}, snapshot=_snapshot("hypothesis"))
    caller.call(request_kind="code", tool={}, snapshot=_snapshot("code"))
    traces_before_exhaustion = tuple((tmp_path / "traces").glob("*.json"))
    with pytest.raises(ProviderCallCapExhausted) as raised:
        caller.call(
            request_kind="hypothesis",
            tool={},
            snapshot=_snapshot("hypothesis"),
        )

    assert client.calls == ["hypothesis", "code"]
    assert budget.used == 2
    assert raised.value.request_kind == "hypothesis"
    assert tuple((tmp_path / "traces").glob("*.json")) == traces_before_exhaustion


def test_none_cap_preserves_unbounded_legacy_dispatch(tmp_path) -> None:
    client = _Client()
    budget = ProviderCallBudget(None)
    caller = ProviderCaller(
        client,
        "fake-model",
        trace_dir=str(tmp_path / "traces"),
        provider_call_budget=budget,
    )

    for _ in range(3):
        caller.call(
            request_kind="hypothesis",
            tool={},
            snapshot=_snapshot("hypothesis"),
        )

    assert client.calls == ["hypothesis"] * 3
    assert budget.used == 3


def test_pipeline_projects_cap_exhaustion_as_typed_resource_terminal() -> None:
    exhausted = ProviderCallCapExhausted(
        cap=1,
        used=1,
        request_kind="code",
    )
    creative = FakeCreative(code_error=exhausted)
    pipeline, branch, _runtime, _balance = _pipeline(creative=creative)
    hypothesis = pipeline.generate_hypothesis(branch).proposal
    assert hypothesis is not None

    attempt = pipeline.generate_code(branch, hypothesis)

    assert attempt.proposal is None
    assert attempt.execution_outcome is not None
    assert attempt.execution_outcome.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert attempt.execution_outcome.reason_code == "PROVIDER_CALL_CAP_EXHAUSTED"
    assert creative.code_calls == 1


@pytest.mark.parametrize(
    "value",
    [
        {"provider_call_cap": 0},
        {"outer_hardwall_sec": 0},
        {"provider_call_cap": True},
        {"outer_hardwall_sec": 1.5},
    ],
)
def test_resource_envelope_rejects_nonpositive_or_noninteger_caps(value) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_resource_envelope(value)


def test_resource_envelope_is_problem_neutral_and_ordinary() -> None:
    envelope = ResourceEnvelope(provider_call_cap=4, outer_hardwall_sec=60)

    assert envelope.to_primitive() == {
        "provider_call_cap": 4,
        "outer_hardwall_sec": 60,
    }


def test_configured_resource_envelope_is_written_once_with_exact_content(
    tmp_path,
) -> None:
    envelope = ResourceEnvelope(provider_call_cap=4, outer_hardwall_sec=60)

    path = write_resource_envelope(str(tmp_path), envelope)

    assert path == tmp_path / "resource_envelope.json"
    assert json.loads(path.read_text(encoding="utf-8")) == envelope.to_primitive()
    with pytest.raises(FileExistsError):
        write_resource_envelope(str(tmp_path), envelope)


def test_absent_resource_limits_write_no_artifact(tmp_path) -> None:
    assert write_resource_envelope(str(tmp_path), ResourceEnvelope()) is None
    assert not (tmp_path / "resource_envelope.json").exists()


def test_campaign_composition_writes_the_declared_envelope_once(tmp_path) -> None:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(
        _VALID_CODE,
        encoding="utf-8",
    )
    spec = _make_spec(str(code_dir))
    protocol = _MockProtocol()
    protocol._problem_spec = spec
    envelope = ResourceEnvelope(provider_call_cap=2, outer_hardwall_sec=30)
    campaign_dir = tmp_path / "campaign"

    CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(),
        split_manifest=SplitManifest(
            screening=["s"],
            validation=["v"],
            frozen=["f"],
            canary=["c"],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[1],
            validation=[2],
            frozen=[3],
            canary=[4],
        ),
        llm_client=MockLLMClient(),
        champion=_make_champion(code_dir),
        campaign_dir=str(campaign_dir),
        experiment_protocol=protocol,
        adapter=SimpleNamespace(spec=spec),
        verification_gate=_AlwaysPassVerification(),
        resource_envelope=envelope,
    )

    artifact = campaign_dir / "resource_envelope.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == envelope.to_primitive()


def test_hardwall_watchdog_marks_expired_then_sends_sigterm() -> None:
    delivered = threading.Event()
    calls: list[tuple[int, int]] = []

    def kill_process(pid: int, signum: int) -> None:
        calls.append((pid, signum))
        delivered.set()

    hardwall = _CampaignOuterHardwall(
        0.01,
        kill_process=kill_process,
        process_id=lambda: 4321,
    )
    with hardwall:
        assert delivered.wait(timeout=1.0)

    assert hardwall.expired.is_set()
    assert calls == [(4321, signal.SIGTERM)]


def test_hardwall_signal_handler_records_distinct_reason_and_exit() -> None:
    class _Manager:
        def __init__(self) -> None:
            self.reasons: list[str] = []

        def request_stop(self, reason: str) -> None:
            self.reasons.append(reason)

        def terminate_active_processes(self) -> None:
            raise AssertionError("signal handler must not acquire runner state")

    manager = _Manager()
    hardwall = _CampaignOuterHardwall(None)
    hardwall.expired.set()

    with _campaign_signal_handlers(manager, hardwall=hardwall):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        with pytest.raises(KeyboardInterrupt) as raised:
            handler(signal.SIGTERM, None)

    assert manager.reasons == ["OUTER_HARDWALL_EXCEEDED"]
    assert raised.value.reason == "OUTER_HARDWALL_EXCEEDED"
    assert raised.value.exit_status == 124


def test_hardwall_finalization_is_a_typed_interruption() -> None:
    terminal = CampaignRunResult.empty(1).terminalized(
        "OUTER_HARDWALL_EXCEEDED",
        interrupted=True,
    )

    assert terminal.stop_reason == "OUTER_HARDWALL_EXCEEDED"
    assert terminal.last_execution_outcome == {
        "outcome": "interrupted",
        "reason_code": "OUTER_HARDWALL_EXCEEDED",
        "stage": "campaign",
    }


def test_hardwall_between_calls_still_finalizes_as_interrupted() -> None:
    manager = object.__new__(CampaignManager)
    manager._external_stop_requested = False
    manager._last_stop_reason = None
    manager._requested_rounds = 1
    manager._weight_opt_coord = SimpleNamespace(wait_all=lambda timeout: None)
    manager._campaign_loop = SimpleNamespace(
        call_in_progress=False,
        current_result=CampaignRunResult.empty(1),
    )
    written: list[CampaignRunResult] = []
    manager._write_terminal_artifacts = written.append

    manager.finalize_requested_stop(
        "OUTER_HARDWALL_EXCEEDED",
        interrupted_override=True,
    )

    assert len(written) == 1
    assert written[0].last_execution_outcome == {
        "outcome": "interrupted",
        "reason_code": "OUTER_HARDWALL_EXCEEDED",
        "stage": "campaign",
    }


def test_resource_exhaustion_has_a_nonzero_cli_completion_status() -> None:
    result = CampaignRunResult.empty(1)
    result = replace(
        result,
        stop_reason="execution_resource_exhausted",
        execution_outcome_counts={
            **result.execution_outcome_counts,
            ExecutionOutcome.RESOURCE_EXHAUSTED.value: 1,
        },
        last_execution_outcome={
            "outcome": "resource_exhausted",
            "reason_code": "PROVIDER_CALL_CAP_EXHAUSTED",
        },
    )

    assert _completion_from_run_result(result) == (
        21,
        "incomplete_resource_stop:resource_exhausted",
    )
