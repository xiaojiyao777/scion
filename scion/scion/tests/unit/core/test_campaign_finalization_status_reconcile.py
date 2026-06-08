from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.async_weight_opt import AsyncWeightOptCoordinator
from scion.core.campaign import CampaignManager
import scion.core.campaign as campaign_module
from scion.core.campaign_loop import CampaignLoop
from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.step_result import StepResult

from .evidence_recorder_test_support import _champion


def test_stopped_status_clears_incomplete_current_progress(tmp_path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    recorder.current_status_progress = {
        "branch_id": "branch-1",
        "stage": "screening",
        "complete": False,
        "attempted_pairs": 3,
        "total_pairs": 16,
    }
    recorder.in_flight_protocol = {
        "branch_id": "branch-1",
        "phase": "formal_screening",
        "complete": False,
        "attempted_pairs": 3,
        "total_pairs": 16,
    }

    status = recorder.write_status(stopped_reason="max_rounds_exhausted")

    assert status["stopped"] is True
    assert status["stopped_reason"] == "max_rounds_exhausted"
    assert "current_progress" not in status
    assert "in_flight_protocol" not in status
    assert recorder.current_status_progress is None
    assert recorder.in_flight_protocol is None
    source_counts = status["evidence_scope_reconciliation"]["source_counts"]
    assert source_counts["current_progress_count"] == 0
    assert source_counts["in_flight_protocol_count"] == 0


def test_campaign_summary_reconciles_weight_opt_and_stopped_progress(tmp_path) -> None:
    weight_optimization = {
        "pending_threads": 0,
        "active": [],
        "runs": [
            {
                "version": 2,
                "mode": "async",
                "phase": "completed",
                "active": False,
                "improved": False,
            }
        ],
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 1,
            "screened_experiments": 1,
            "branches": [],
            "current_progress": {
                "branch_id": "branch-1",
                "stage": "screening",
                "complete": False,
            },
            "weight_optimization": weight_optimization,
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    assert summary["stopped"] is True
    assert summary["stopped_reason"] == "max_rounds_exhausted"
    assert "current_progress" not in summary
    assert summary["weight_optimization"] == weight_optimization


def test_status_and_summary_state_snapshot_does_not_reconcile_active_slots(
    tmp_path,
    monkeypatch,
) -> None:
    manager = CampaignManager.__new__(CampaignManager)
    recorder = EvidenceRecorder(
        campaign_id="camp-read-only",
        campaign_dir=tmp_path,
        state_provider=manager.get_state_snapshot,
    )
    manager._campaign_id = "camp-read-only"
    manager._campaign_dir = tmp_path
    manager._branch_ctrl = SimpleNamespace(get_reportable_branches=lambda: [])
    manager._scheduler = SimpleNamespace(max_active_branches=1)
    manager._persist_branch_state = lambda _branch_id: (_ for _ in ()).throw(
        AssertionError("status snapshot must not persist branch state")
    )
    manager._step_history = []
    manager._n_experiments = 0
    manager._telemetry_failed_experiments = 0
    manager._round_num = 0
    manager._champion = _champion()
    manager._budget = SimpleNamespace(remaining_ratio=1.0)
    manager._balance_exhausted = False
    manager._circuit_breaker = SimpleNamespace(is_tripped=False)
    manager._frozen_budget_ledger = SimpleNamespace(snapshot=lambda: {})
    manager._evidence_recorder = recorder
    manager._proposal_pipeline = SimpleNamespace(agentic_artifact_dir=None)
    manager._weight_opt_coord = SimpleNamespace(
        status_snapshot=lambda: {"pending_threads": 0, "active": [], "runs": []}
    )
    manager._current_status_progress = None

    def fail_reconcile(*_args, **_kwargs):
        raise AssertionError("status snapshot must not reconcile active slots")

    monkeypatch.setattr(
        campaign_module,
        "reconcile_active_slot_overflow",
        fail_reconcile,
    )

    status = recorder.write_status(stopped_reason="max_rounds_exhausted")
    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    assert status["campaign_id"] == "camp-read-only"
    assert summary["campaign_id"] == "camp-read-only"


def test_async_weight_opt_final_wait_timeout_marks_detached_active_run() -> None:
    manager = _StatusPublishingManager()
    coordinator = AsyncWeightOptCoordinator(manager)  # type: ignore[arg-type]
    coordinator._set_status(1, mode="async", phase="running", active=True)
    coordinator._finish_status(1, phase="completed", improved=False)

    snapshot = coordinator.status_snapshot()
    assert snapshot["active"] == []
    assert snapshot["runs"][0]["phase"] == "completed"
    assert snapshot["runs"][0]["active"] is False

    alive_thread = _AlwaysAliveThread("weight-opt-v2")
    coordinator._pending_threads.append(alive_thread)  # type: ignore[arg-type]
    coordinator._set_status(2, mode="async", phase="running", active=True)

    coordinator.wait_all(timeout=0.01)

    timeout_snapshot = coordinator.status_snapshot()
    active = {run["version"]: run for run in timeout_snapshot["active"]}
    assert timeout_snapshot["pending_threads"] == 1
    assert active[2]["phase"] == "final_wait_timeout"
    assert active[2]["active"] is True
    assert active[2]["detached"] is True
    assert active[2]["final_wait_timeout"] is True
    assert active[2]["final_wait_timeout_sec"] == 0.01
    assert alive_thread.join_timeouts == [0.01]
    assert manager.write_count >= 1


def test_campaign_loop_final_summary_sees_reconciled_stopped_status() -> None:
    status_state: dict[str, Any] = {
        "current_progress": {
            "branch_id": "branch-1",
            "stage": "screening",
            "complete": False,
        }
    }
    last_stop_reason: dict[str, str | None] = {"value": None}
    summaries: list[dict[str, Any]] = []
    stopped_statuses: list[str] = []

    def write_status(**kwargs: Any) -> None:
        stopped_reason = kwargs.get("stopped_reason")
        if stopped_reason is None:
            return
        status_state["stopped"] = True
        status_state["stopped_reason"] = stopped_reason
        status_state.pop("current_progress", None)
        stopped_statuses.append(stopped_reason)

    def write_campaign_summary() -> None:
        summaries.append(
            {
                "summary_stopped_reason": last_stop_reason["value"],
                "status_stopped_reason": status_state.get("stopped_reason"),
                "current_progress": status_state.get("current_progress"),
            }
        )

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: last_stop_reason.__setitem__(
            "value",
            reason,
        ),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=lambda: StepResult(
            action="explore",
            branch_id="branch-1",
            reason="screening complete",
        ),
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=write_campaign_summary,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=1)

    assert stopped_statuses[-1] == "max_rounds_exhausted"
    assert summaries[-1] == {
        "summary_stopped_reason": "max_rounds_exhausted",
        "status_stopped_reason": "max_rounds_exhausted",
        "current_progress": None,
    }


def test_campaign_status_refresh_preserves_final_stop_reason() -> None:
    manager = CampaignManager.__new__(CampaignManager)
    recorder = _RecordingEvidenceRecorder()
    manager._last_stop_reason = "max_rounds_exhausted"
    manager._current_status_progress = {
        "branch_id": "branch-1",
        "complete": False,
    }
    manager._last_status_result = None
    manager._evidence_recorder = recorder

    CampaignManager._write_status(manager)

    assert recorder.calls[-1]["stopped_reason"] == "max_rounds_exhausted"


class _StatusPublishingManager:
    def __init__(self) -> None:
        self.write_count = 0

    def _write_status(self) -> None:
        self.write_count += 1


class _AlwaysAliveThread:
    def __init__(self, name: str) -> None:
        self.name = name
        self.join_timeouts: list[float | None] = []

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)

    def is_alive(self) -> bool:
        return True


class _RecordingEvidenceRecorder:
    def __init__(self) -> None:
        self.current_status_progress = None
        self.last_status_result = None
        self.calls: list[dict[str, Any]] = []

    def write_status(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        self.current_status_progress = None
