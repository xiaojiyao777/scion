from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.features import BudgetState
from scion.core.models import (
    BranchState,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
)
from scion.failure.router import FailureRouter, RetryConfig


class FakeHypothesisStore:
    def __init__(self) -> None:
        self.records: list[HypothesisRecord] = []

    def save(self, record: HypothesisRecord) -> None:
        self.records.append(record)


class FakeBranchStore:
    def __init__(self) -> None:
        self.saved: list[str] = []

    def save(self, branch) -> None:
        self.saved.append(branch.branch_id)


class FakeRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, event: dict) -> None:
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
    budget: BudgetState | None = None,
    hypotheses: dict | None = None,
    hard_abandons: list[tuple[str, str]] | None = None,
    status_heartbeats: list[tuple[str, str, str | None]] | None = None,
) -> tuple[FailureLifecycleService, BudgetState, FakeHypothesisStore, FakeBranchStore, FakeRegistry, dict[str, int], dict[str, int]]:
    budget = budget or BudgetState(total=100, used=0)
    hyp_store = FakeHypothesisStore()
    branch_store = FakeBranchStore()
    registry = FakeRegistry()
    failure_streak: dict[str, int] = {}
    total_failures: dict[str, int] = {}
    hard_abandons = hard_abandons if hard_abandons is not None else []
    service = FailureLifecycleService(
        failure_router=FailureRouter(RetryConfig(max_llm_retries=3, max_infra_retries=5)),
        budget=budget,
        failure_streak=failure_streak,
        total_failures=total_failures,
        branch_controller=ctrl,
        branch_hypotheses=hypotheses or {},
        branch_patches={},
        hypothesis_store=hyp_store,
        branch_store=branch_store,
        registry=registry,
        campaign_id="campaign-1",
        get_champion=_champion,
        record_hard_abandon=lambda branch_id, reason: hard_abandons.append((branch_id, reason)),
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
    return service, budget, hyp_store, branch_store, registry, failure_streak, total_failures


def test_retry_llm_updates_branch_and_failure_counters() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    service, budget, _, branch_store, _, streak, totals = _service(ctrl)

    service.handle_failure(branch, FailureEvent(category="proposal", detail="bad json"))

    assert branch.pending_retry is True
    assert branch.consecutive_llm_retries == 1
    assert branch.retry_count == 1
    assert branch.failure_codes == ["PROPOSAL"]
    assert budget.used == 0
    assert streak["proposal"] == 1
    assert totals["proposal"] == 1
    assert branch_store.saved == [branch.branch_id]


def test_heavy_failure_blacklists_hypothesis_and_consumes_budget() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    hypotheses = {
        branch.branch_id: HypothesisProposal(
            hypothesis_text="Try a risky operator.",
            change_locus="local_search",
            action="modify",
            target_file="operators/local_search.py",
        )
    }
    service, budget, hyp_store, _, _, _, _ = _service(ctrl, hypotheses=hypotheses)

    service.handle_failure(
        branch,
        FailureEvent(category="verification_heavy", detail="state mutation"),
    )

    assert budget.used == 1
    assert len(hyp_store.records) == 1
    record = hyp_store.records[0]
    assert record.status == "blacklisted"
    assert record.branch_id == branch.branch_id
    assert record.base_champion_version == 1


def test_repeated_infra_failure_records_hard_abandon() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    hard_abandons: list[tuple[str, str]] = []
    service, _, _, _, _, _, _ = _service(ctrl, hard_abandons=hard_abandons)

    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))
    ctrl.unblock_infra(branch.branch_id)
    service.handle_failure(branch, FailureEvent(category="infra", detail="runner down"))

    assert hard_abandons == [(branch.branch_id, "infra_permanent")]


def test_framework_control_timeout_fail_closed_without_budget_or_proposal_streak() -> None:
    ctrl = BranchController()
    branch = ctrl.create_branch(_champion())
    hard_abandons: list[tuple[str, str]] = []
    heartbeats: list[tuple[str, str, str | None]] = []
    service, budget, _, branch_store, registry, streak, totals = _service(
        ctrl,
        hard_abandons=hard_abandons,
        status_heartbeats=heartbeats,
    )

    service.handle_failure(
        branch,
        FailureEvent(
            category="framework_control",
            detail="agentic_proposal:session_timeout: max_wall_time_sec=10",
        ),
    )

    assert branch.state == BranchState.ABANDONED
    assert branch.pending_retry is False
    assert branch.retry_count == 1
    assert branch.failure_codes == ["FRAMEWORK_CONTROL"]
    assert budget.used == 0
    assert streak == {"framework_control": 1}
    assert totals == {"framework_control": 1}
    assert hard_abandons == [(branch.branch_id, "framework_control_fail_closed")]
    assert branch_store.saved == [branch.branch_id]
    assert registry.events[-1]["event_kind"] == "framework_control_fail_closed"
    assert heartbeats == [("failure_handled", branch.branch_id, "framework_control")]
