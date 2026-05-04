from __future__ import annotations

import json
import threading

from scion.core.async_weight_opt import WeightOptCompletionEvent
from scion.core.branch import BranchController
from scion.core.models import Branch, BranchState, ChampionState, OperatorConfig
from scion.core.weight_opt_committer import WeightOptCommitter


class FakeEventSource:
    def __init__(self, events: list[WeightOptCompletionEvent]) -> None:
        self._events = list(events)
        self.latest_result = None

    def drain_completed_events(self) -> list[WeightOptCompletionEvent]:
        events = list(self._events)
        self._events.clear()
        return events


class FakeChampionStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.promoted: list[ChampionState] = []

    def promote(self, champion: ChampionState) -> None:
        if self.fail:
            raise OSError("store unavailable")
        self.promoted.append(champion)


class FakeRegistry:
    def __init__(self) -> None:
        self.weight_rows: list[tuple[str, int, object]] = []
        self.events: list[dict] = []

    def record_weight_optimization(
        self,
        campaign_id: str,
        champion_version: int,
        result: object,
    ) -> None:
        self.weight_rows.append((campaign_id, champion_version, result))

    def record_event(self, event: dict) -> None:
        self.events.append(event)


def _operator(weight: float = 1.0) -> OperatorConfig:
    return OperatorConfig(
        name="ls",
        file_path="operators/ls.py",
        category="local_search",
        weight=weight,
        class_name="LocalSearch",
    )


def _champion(*, version: int = 2, revision: int = 0) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={"ls": _operator()},
        solver_config_hash="solver-hash",
        code_snapshot_path=f"/tmp/champion_v{version}",
        code_snapshot_hash=f"hash-{version}",
        promoted_at="2026-05-01T00:00:00",
        weight_revision=revision,
    )


def _committer(
    *,
    champion: ChampionState,
    events: list[WeightOptCompletionEvent],
    branch_controller: BranchController | None = None,
    store: FakeChampionStore | None = None,
) -> tuple[WeightOptCommitter, FakeEventSource, FakeChampionStore, FakeRegistry, list[int], list[ChampionState]]:
    state = [champion]
    persisted_branch_counts: list[int] = []
    event_source = FakeEventSource(events)
    store = store or FakeChampionStore()
    registry = FakeRegistry()
    ctrl = branch_controller or BranchController()
    committer = WeightOptCommitter(
        event_source=event_source,
        champion_lock=threading.Lock(),
        get_champion=lambda: state[0],
        set_champion=lambda next_champion: state.__setitem__(0, next_champion),
        champion_store=store,
        branch_controller=ctrl,
        persist_branch_states=lambda: persisted_branch_counts.append(1),
        registry=registry,
        campaign_id="campaign-1",
        clock=lambda: "2026-05-04T00:00:00",
    )
    return committer, event_source, store, registry, persisted_branch_counts, state


def test_drain_commits_improved_weight_event_and_marks_branches_stale() -> None:
    ctrl = BranchController()
    ctrl._branches["ready"] = Branch(
        branch_id="ready",
        state=BranchState.READY_VALIDATE,
        base_champion_id=2,
        base_champion_hash="hash-2",
    )
    ctrl._branches["frozen"] = Branch(
        branch_id="frozen",
        state=BranchState.FROZEN_TESTING,
        base_champion_id=2,
        base_champion_hash="hash-2",
    )
    event = WeightOptCompletionEvent(
        version=2,
        base_weight_revision=0,
        result={"best_score": 1.0},
        elapsed_minutes=0.1,
        improved=True,
        new_revision=1,
        snapshot_path="/tmp/champion_v2_r1",
        snapshot_hash="hash-2-r1",
        operator_pool={"ls": _operator(weight=2.0)},
    )
    committer, source, store, registry, persisted, state = _committer(
        champion=_champion(),
        events=[event],
        branch_controller=ctrl,
    )

    committer.drain()

    assert source.latest_result == {"best_score": 1.0}
    assert state[0].weight_revision == 1
    assert state[0].code_snapshot_path == "/tmp/champion_v2_r1"
    assert state[0].operator_pool["ls"].weight == 2.0
    assert store.promoted == [state[0]]
    assert ctrl._branches["ready"].state == BranchState.STALE_WEIGHT_UPDATE
    assert ctrl._branches["frozen"].state == BranchState.FROZEN_TESTING
    assert persisted == [1]
    assert registry.weight_rows == [("campaign-1", 2, {"best_score": 1.0})]
    assert registry.events[0]["event_kind"] == "weight_update_invalidation"
    payload = json.loads(registry.events[0]["decision_features_json"])
    assert payload["stale_branch_ids"] == ["ready"]


def test_stale_weight_event_is_recorded_but_not_committed() -> None:
    event = WeightOptCompletionEvent(
        version=2,
        base_weight_revision=0,
        result={"best_score": 1.0},
        elapsed_minutes=0.1,
        improved=True,
        new_revision=1,
        snapshot_path="/tmp/champion_v2_r1",
        snapshot_hash="hash-2-r1",
        operator_pool={"ls": _operator(weight=2.0)},
    )
    committer, source, store, registry, persisted, state = _committer(
        champion=_champion(version=3, revision=0),
        events=[event],
    )

    committer.drain()

    assert source.latest_result == {"best_score": 1.0}
    assert state[0].version == 3
    assert state[0].weight_revision == 0
    assert store.promoted == []
    assert persisted == []
    assert registry.weight_rows == [("campaign-1", 2, {"best_score": 1.0})]
    assert registry.events == []


def test_unimproved_weight_event_updates_feedback_only() -> None:
    event = WeightOptCompletionEvent(
        version=2,
        base_weight_revision=0,
        result={"best_score": 0.0},
        elapsed_minutes=0.1,
        improved=False,
    )
    committer, source, store, registry, persisted, state = _committer(
        champion=_champion(),
        events=[event],
    )

    committer.drain()

    assert source.latest_result == {"best_score": 0.0}
    assert state[0].weight_revision == 0
    assert store.promoted == []
    assert persisted == []
    assert registry.weight_rows == [("campaign-1", 2, {"best_score": 0.0})]
    assert registry.events == []


def test_weight_opt_store_failure_does_not_replace_champion_or_stale_branches() -> None:
    ctrl = BranchController()
    ctrl._branches["ready"] = Branch(
        branch_id="ready",
        state=BranchState.READY_VALIDATE,
        base_champion_id=2,
        base_champion_hash="hash-2",
    )
    event = WeightOptCompletionEvent(
        version=2,
        base_weight_revision=0,
        result={"best_score": 1.0},
        elapsed_minutes=0.1,
        improved=True,
        new_revision=1,
        snapshot_path="/tmp/champion_v2_r1",
        snapshot_hash="hash-2-r1",
        operator_pool={"ls": _operator(weight=2.0)},
    )
    original = _champion()
    committer, source, store, registry, persisted, state = _committer(
        champion=original,
        events=[event],
        branch_controller=ctrl,
        store=FakeChampionStore(fail=True),
    )

    committer.drain()

    assert source.latest_result == {"best_score": 1.0}
    assert state[0] is original
    assert state[0].weight_revision == 0
    assert state[0].code_snapshot_path == "/tmp/champion_v2"
    assert store.promoted == []
    assert ctrl._branches["ready"].state == BranchState.READY_VALIDATE
    assert persisted == []
    assert registry.weight_rows == [("campaign-1", 2, {"best_score": 1.0})]
    assert registry.events == []
