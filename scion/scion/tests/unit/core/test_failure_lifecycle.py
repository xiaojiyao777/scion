from __future__ import annotations

import json

import pytest

from scion.core.branch import BranchController
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.models import BranchState, ChampionState, FailureEvent
from scion.failure.router import FailureRouter
from scion.lineage.branch_store import BranchStore
from scion.lineage.registry import LineageRegistry


class FakeBranchStore:
    def __init__(self) -> None:
        self.saved: list[str] = []
        self.fail_next = False

    def save(self, branch) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("branch store unavailable")
        self.saved.append(branch.branch_id)


class FakeRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.fail_next = False
        self.on_record = None

    def record_event(self, event: dict) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("registry unavailable")
        if self.on_record is not None:
            self.on_record(event)
        self.events.append(event)


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="hash",
    )


def _service(
    ctrl: BranchController,
    *,
    status_heartbeats: list[tuple[str, str, str | None]] | None = None,
) -> tuple[
    FailureLifecycleService,
    FakeBranchStore,
    FakeRegistry,
    dict[str, int],
    dict[str, int],
]:
    branch_store = FakeBranchStore()
    registry = FakeRegistry()
    failure_streak: dict[str, int] = {}
    total_failures: dict[str, int] = {}
    service = FailureLifecycleService(
        failure_router=FailureRouter(),
        failure_streak=failure_streak,
        total_failures=total_failures,
        branch_controller=ctrl,
        branch_hypotheses={},
        branch_patches={},
        branch_store=branch_store,
        registry=registry,
        campaign_id="campaign-1",
        status_heartbeat=(
            None
            if status_heartbeats is None
            else lambda event_kind, branch, failure: status_heartbeats.append(
                (
                    event_kind,
                    branch.branch_id,
                    failure.category if failure is not None else None,
                )
            )
        ),
    )
    return service, branch_store, registry, failure_streak, total_failures


def test_response_rejection_is_terminal_for_current_candidate() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, branch_store, _, streak, totals = _service(ctrl)
    service.branch_hypotheses[branch.branch_id] = object()
    service.branch_patches[branch.branch_id] = object()

    service.handle_failure(branch, FailureEvent(category="proposal", detail="bad json"))

    assert branch.state is BranchState.EXPLORE
    assert branch.failure_codes == ["PROPOSAL"]
    assert branch.branch_id not in service.branch_hypotheses
    assert branch.branch_id not in service.branch_patches
    assert not hasattr(branch, "pending_retry")
    assert streak == {"proposal": 1}
    assert totals == {"proposal": 1}
    assert branch_store.saved == [branch.branch_id]


def test_repeated_response_rejections_never_escalate_to_infra_or_abandon() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, _, _, streak, totals = _service(ctrl)

    for _ in range(20):
        service.handle_failure(
            branch,
            FailureEvent(category="contract", detail="candidate rejected"),
        )

    assert branch.state is BranchState.EXPLORE
    assert streak == {"contract": 20}
    assert totals == {"contract": 20}


def test_failure_state_write_failure_is_not_silenced() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, branch_store, _, _, _ = _service(ctrl)
    branch_store.fail_next = True

    with pytest.raises(RuntimeError, match="branch store unavailable"):
        service.handle_failure(
            branch,
            FailureEvent(category="contract", detail="candidate rejected"),
        )


def test_infra_failure_stays_blocked_without_research_side_effects() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, _, _, _, _ = _service(ctrl)
    hypothesis = object()
    patch = object()
    service.branch_hypotheses[branch.branch_id] = hypothesis
    service.branch_patches[branch.branch_id] = patch

    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    assert branch.state is BranchState.BLOCKED_INFRA
    assert branch.infra_block_count == 2
    assert service.branch_hypotheses[branch.branch_id] is hypothesis
    assert service.branch_patches[branch.branch_id] is patch


def test_operator_resume_persists_event_before_unblocking() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    heartbeats: list[tuple[str, str, str | None]] = []
    service, branch_store, registry, _, _ = _service(
        ctrl,
        status_heartbeats=heartbeats,
    )
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))
    state_when_event_persisted: list[BranchState] = []
    registry.on_record = lambda _event: state_when_event_persisted.append(branch.state)

    assert service.operator_resume_infra(
        branch.branch_id,
        operator_reason="runner connectivity restored",
        operator_ack="operator-ack-7",
        failed_attempt_id="attempt-7",
    )

    assert branch.state is BranchState.EXPLORE
    assert state_when_event_persisted == [BranchState.BLOCKED_INFRA]
    resume_events = [
        e for e in registry.events if e["event_kind"] == "operator_resume_infra"
    ]
    assert len(resume_events) == 1
    payload = json.loads(resume_events[0]["audit_payload_json"])
    assert payload["operator_ack"] == "operator-ack-7"
    assert payload["state_before"] == "blocked_infra"
    assert branch_store.saved == [branch.branch_id, branch.branch_id]
    assert heartbeats[-1] == ("operator_resume_infra", branch.branch_id, None)


def test_operator_resume_requires_ack_and_keeps_hold() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, _, _, _, _ = _service(ctrl)
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    with pytest.raises(ValueError, match="operator_ack"):
        service.operator_resume_infra(
            branch.branch_id,
            operator_reason="runner restored",
            operator_ack="  ",
        )

    assert branch.state is BranchState.BLOCKED_INFRA


def test_operator_resume_registry_failure_keeps_branch_blocked() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, _, registry, _, _ = _service(ctrl)
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))
    registry.fail_next = True

    with pytest.raises(RuntimeError, match="registry unavailable"):
        service.operator_resume_infra(
            branch.branch_id,
            operator_reason="runner restored",
            operator_ack="operator-ack",
        )

    assert branch.state is BranchState.BLOCKED_INFRA


def test_operator_resume_branch_write_failure_restores_hold() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, branch_store, registry, _, _ = _service(ctrl)
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))
    branch_store.fail_next = True

    with pytest.raises(RuntimeError, match="branch store unavailable"):
        service.operator_resume_infra(
            branch.branch_id,
            operator_reason="runner restored",
            operator_ack="operator-ack",
        )

    assert branch.state is BranchState.BLOCKED_INFRA
    assert (
        len([e for e in registry.events if e["event_kind"] == "operator_resume_infra"])
        == 1
    )


def test_operator_resume_is_durable_in_sqlite(tmp_path) -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, _, _, _, _ = _service(ctrl)
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    branch_store = BranchStore(registry)
    service.registry = registry
    service.branch_store = branch_store
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    service.operator_resume_infra(
        branch.branch_id,
        operator_reason="filesystem repaired",
        operator_ack="operator-ack-sqlite",
    )

    persisted = branch_store.load(branch.branch_id)
    assert persisted is not None
    assert persisted.state is BranchState.EXPLORE
    rows = registry.query_by_branch(branch.branch_id)
    assert (
        len([row for row in rows if row["event_kind"] == "operator_resume_infra"]) == 1
    )


def test_operator_resume_restores_persisted_frozen_state_after_reopen(tmp_path) -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    branch.state = BranchState.FROZEN_TESTING
    service, _, _, _, _ = _service(ctrl)
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    branch_store = BranchStore(registry)
    service.registry = registry
    service.branch_store = branch_store

    service.handle_failure(
        branch,
        FailureEvent(category="infra", detail="champion evidence timeout"),
    )

    persisted = branch_store.load(branch.branch_id)
    assert persisted is not None
    assert persisted.state is BranchState.BLOCKED_INFRA
    assert persisted.branch_evidence_summary["infra_resume_state"] == {
        "schema_version": "infra-resume-state.v1",
        "state": "frozen_testing",
    }

    reopened_ctrl = BranchController()
    reopened_ctrl.restore_branch(persisted)
    reopened_service, _, _, _, _ = _service(reopened_ctrl)
    reopened_service.registry = registry
    reopened_service.branch_store = branch_store

    assert reopened_service.operator_resume_infra(
        persisted.branch_id,
        operator_reason="evidence runner repaired",
        operator_ack="operator-ack-frozen",
    )

    restored = branch_store.load(persisted.branch_id)
    assert restored is not None
    assert restored.state is BranchState.FROZEN_TESTING
    assert "infra_resume_state" not in restored.branch_evidence_summary
