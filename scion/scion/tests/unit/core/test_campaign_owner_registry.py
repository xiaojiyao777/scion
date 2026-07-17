from __future__ import annotations

import contextvars
import copy
import dataclasses
import pickle
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from scion.core import campaign_owner_registry as subject
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import branch_owner_store
from scion.lineage import hypothesis_owner_store
from scion.lineage import owner_transaction
from scion.lineage import sqlite_connection
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_connection.CampaignDatabaseAuthority
    branch_store: branch_owner_store.BranchStore
    hypothesis_store: hypothesis_owner_store.HypothesisStore
    registry: subject.CampaignOwnerRegistry
    branch: RevisionedBranchRecord
    active_hypothesis: RevisionedHypothesisRecord
    alternate_hypothesis: RevisionedHypothesisRecord


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="a" * 64,
        lineage_id="lineage-branch-1",
        current_code_hash="b" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=1,
        validation_expand_count=2,
        failure_codes=["SCREENING_FAILED"],
        created_at=datetime(2026, 7, 16, 1, 2, 3),
        updated_at=datetime(2026, 7, 16, 1, 2, 4),
        direction="local-search",
        weight_revision=3,
        branch_code_status="candidate_committed",
        branch_evidence_summary={"complete": True, "score": 1.25},
        infra_block_count=0,
    )


def _hypothesis(
    hypothesis_id: str,
    *,
    status: str,
    created_second: int,
) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hypothesis_id,
        branch_id="branch-1",
        change_locus="local_search",
        action="modify",
        status=status,
        target_file="operators/local_search.py",
        parent_hypothesis_id=None,
        suggested_weight=0.5,
        hypothesis_text=f"Bounded neighborhood for {hypothesis_id}.",
        created_at=datetime(2026, 7, 16, 1, 2, created_second),
        base_champion_version=7,
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        predicted_direction="improve",
        proposal_digest=("d" if status == "active" else "e") * 64,
    )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE branches (
            branch_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            base_champion_id INTEGER NOT NULL,
            base_champion_hash TEXT NOT NULL,
            lineage_id TEXT NOT NULL,
            current_code_hash TEXT,
            last_clean_code_hash TEXT,
            screening_expand_count INTEGER NOT NULL,
            validation_expand_count INTEGER NOT NULL,
            failure_codes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            direction TEXT,
            weight_revision INTEGER NOT NULL,
            branch_code_status TEXT NOT NULL,
            branch_evidence_summary_json TEXT NOT NULL,
            infra_block_count INTEGER NOT NULL,
            owner_revision INTEGER NOT NULL,
            owner_protocol_generation TEXT NOT NULL
        );

        CREATE TABLE hypotheses (
            hypothesis_id TEXT PRIMARY KEY,
            branch_id TEXT NOT NULL,
            change_locus TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            target_file TEXT,
            parent_hypothesis_id TEXT,
            suggested_weight REAL,
            hypothesis_text TEXT,
            created_at TEXT NOT NULL,
            base_champion_version INTEGER NOT NULL,
            family_id TEXT,
            family_source TEXT,
            taxonomy_version TEXT,
            predicted_direction TEXT NOT NULL,
            proposal_digest TEXT,
            owner_revision INTEGER NOT NULL,
            owner_protocol_generation TEXT NOT NULL
        );
        """
    )


def _seed_branch(
    connection: sqlite3.Connection,
    token: RevisionedBranchRecord,
) -> None:
    connection.execute(
        branch_owner_store._BRANCH_INSERT_SQL,
        (
            *branch_owner_store._branch_storage_values(token),
            token.owner_revision,
            branch_owner_store._OWNER_PROTOCOL_GENERATION,
        ),
    )


def _seed_hypothesis(
    connection: sqlite3.Connection,
    token: RevisionedHypothesisRecord,
) -> None:
    connection.execute(
        hypothesis_owner_store._HYPOTHESIS_INSERT_SQL,
        hypothesis_owner_store._write_parameters(token),
    )


def _harness(tmp_path: Path, *, live: bool = True) -> _Harness:
    path = tmp_path / "campaign-owner-registry.db"
    branch = RevisionedBranchRecord.from_value(_branch(), owner_revision=0)
    active = RevisionedHypothesisRecord.from_value(
        _hypothesis("hypothesis-active", status="active", created_second=5),
        owner_revision=0,
    )
    alternate = RevisionedHypothesisRecord.from_value(
        _hypothesis("hypothesis-alternate", status="validated", created_second=6),
        owner_revision=0,
    )
    connection = sqlite_connection._connect_sqlite(path)
    try:
        _create_schema(connection)
        _seed_branch(connection, branch)
        _seed_hypothesis(connection, active)
        _seed_hypothesis(connection, alternate)
        connection.commit()
    finally:
        connection.close()

    authority = sqlite_connection._issue_test_campaign_database_authority(path)
    registry = subject.CampaignOwnerRegistry(authority)
    if live:
        restore = registry.begin_restore()
        registry.seal_live(restore)
    return _Harness(
        path=path,
        authority=authority,
        branch_store=branch_owner_store.BranchStore(authority),
        hypothesis_store=hypothesis_owner_store.HypothesisStore(authority),
        registry=registry,
        branch=branch,
        active_hypothesis=active,
        alternate_hypothesis=alternate,
    )


def _branch_target(expected: RevisionedBranchRecord) -> Branch:
    target = expected.value()
    target.state = BranchState.READY_VALIDATE
    target.updated_at = datetime(2026, 7, 16, 2, 3, 4)
    target.failure_codes.append("TARGET_READY")
    target.branch_evidence_summary["target"] = "ready_validate"
    return target


def _load_branch(harness: _Harness) -> RevisionedBranchRecord:
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        token = harness.branch_store._load_revisioned_branch_from_snapshot(
            snapshot,
            harness.branch.branch_id,
        )
    assert token is not None
    return token


def _load_hypothesis(
    harness: _Harness,
    hypothesis_id: str,
) -> RevisionedHypothesisRecord:
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        token = harness.hypothesis_store._load_revisioned_hypothesis_from_snapshot(
            snapshot,
            hypothesis_id,
        )
    assert token is not None
    return token


def _external_branch_mutation(
    harness: _Harness,
    expected: RevisionedBranchRecord,
    target: Branch,
) -> RevisionedBranchRecord:
    with sqlite_connection.immediate_transaction(harness.authority) as transaction:
        ledger = owner_transaction._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt = harness.branch_store.compare_and_swap_in(
            transaction,
            expected,
            target,
        )
        witness = owner_transaction._consume_branch_mutation_receipt(ledger, receipt)
        owner_transaction._seal_owner_receipt_ledger(ledger, (receipt,))
    committed = witness.committed_token
    assert type(committed) is RevisionedBranchRecord
    return committed


def _external_hypothesis_switch(
    harness: _Harness,
) -> tuple[RevisionedHypothesisRecord, RevisionedHypothesisRecord]:
    active_target = dataclasses.replace(
        harness.active_hypothesis.value(),
        status="validated",
    )
    alternate_target = dataclasses.replace(
        harness.alternate_hypothesis.value(),
        status="active",
    )
    with sqlite_connection.immediate_transaction(harness.authority) as transaction:
        ledger = owner_transaction._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        active_receipt = harness.hypothesis_store.compare_and_swap_in(
            transaction,
            harness.active_hypothesis,
            active_target,
        )
        active_witness = owner_transaction._consume_hypothesis_mutation_receipt(
            ledger,
            active_receipt,
        )
        alternate_receipt = harness.hypothesis_store.compare_and_swap_in(
            transaction,
            harness.alternate_hypothesis,
            alternate_target,
        )
        alternate_witness = owner_transaction._consume_hypothesis_mutation_receipt(
            ledger,
            alternate_receipt,
        )
        owner_transaction._seal_owner_receipt_ledger(
            ledger,
            (active_receipt, alternate_receipt),
        )
    active = active_witness.committed_token
    alternate = alternate_witness.committed_token
    assert type(active) is RevisionedHypothesisRecord
    assert type(alternate) is RevisionedHypothesisRecord
    return active, alternate


def _assert_registry_lock_is_released(registry: subject.CampaignOwnerRegistry) -> None:
    assert registry._owner_lock.acquire(blocking=False)
    registry._owner_lock.release()


def _execute_raw(
    harness: _Harness,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> None:
    connection = sqlite_connection._connect_sqlite(harness.path)
    try:
        connection.execute(sql, parameters)
        connection.commit()
    finally:
        connection.close()


def test_restore_is_context_bound_detached_and_one_registry_per_authority(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, live=False)
    registry = harness.registry
    restore = registry.begin_restore()

    with pytest.raises(subject.CampaignOwnerLifecycleError, match="Contexts"):
        contextvars.copy_context().run(registry.seal_live, restore)
    with pytest.raises(subject.InvalidCampaignOwnerCapabilityError, match="copied"):
        copy.copy(restore)

    registry.seal_live(restore)
    assert registry._owner_state.publication_generation == 0
    assert registry.branch_snapshots()[0] == harness.branch.value()
    assert [record.hypothesis_id for record in registry.hypothesis_snapshots()] == [
        "hypothesis-active",
        "hypothesis-alternate",
    ]
    assert (
        registry.current_hypothesis_snapshot("branch-1").hypothesis_id
        == "hypothesis-active"
    )

    detached = registry.branch_snapshot("branch-1")
    detached.failure_codes.append("CALLER_ONLY")
    detached.branch_evidence_summary["caller"] = True
    fresh = registry.branch_snapshot("branch-1")
    assert "CALLER_ONLY" not in fresh.failure_codes
    assert "caller" not in fresh.branch_evidence_summary

    with pytest.raises(subject.CampaignOwnerLifecycleError, match="already"):
        subject.CampaignOwnerRegistry(harness.authority)
    for operation in (
        copy.copy,
        copy.deepcopy,
        pickle.dumps,
    ):
        with pytest.raises(subject.InvalidCampaignOwnerCapabilityError):
            operation(registry)


def test_mixed_branch_and_current_hypothesis_switch_publishes_one_root(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    old_root = registry._owner_state
    branch_view = registry.acquire_branch_mutation("branch-1")
    active_view = registry.acquire_hypothesis_mutation("hypothesis-active")
    alternate_view = registry.acquire_hypothesis_mutation("hypothesis-alternate")
    branch_target = branch_view.target
    branch_target.state = BranchState.READY_VALIDATE
    branch_target.updated_at = datetime(2026, 7, 16, 2, 3, 4)
    active_target = active_view.target
    active_target.status = "validated"
    alternate_target = alternate_view.target
    alternate_target.status = "active"

    with registry.owner_transaction(
        branch_views=(branch_view,),
        hypothesis_views=(active_view, alternate_view),
    ) as scope:
        scope.compare_and_stage_branch(branch_view)
        scope.compare_and_stage_hypothesis(active_view)
        scope.compare_and_stage_hypothesis(alternate_view)

    assert registry._owner_state is not old_root
    assert registry._owner_state.publication_generation == 1
    assert registry.branch_snapshot("branch-1").state is BranchState.READY_VALIDATE
    assert registry.hypothesis_snapshot("hypothesis-active").status == "validated"
    assert registry.hypothesis_snapshot("hypothesis-alternate").status == "active"
    assert (
        registry.current_hypothesis_snapshot("branch-1").hypothesis_id
        == "hypothesis-alternate"
    )
    assert _load_branch(harness).owner_revision == 1
    assert _load_hypothesis(harness, "hypothesis-active").owner_revision == 1
    assert _load_hypothesis(harness, "hypothesis-alternate").owner_revision == 1

    branch_target.state = BranchState.ABANDONED
    active_target.status = "caller-mutated"
    assert registry.branch_snapshot("branch-1").state is BranchState.READY_VALIDATE
    assert registry.hypothesis_snapshot("hypothesis-active").status == "validated"
    _assert_registry_lock_is_released(registry)


def test_body_failure_rolls_back_spends_view_and_retains_root(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    old_root = registry._owner_state
    view = registry.acquire_branch_mutation("branch-1")
    view.target.state = BranchState.READY_VALIDATE

    with pytest.raises(RuntimeError, match="body rollback"):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)
            raise RuntimeError("body rollback")

    assert registry._owner_state is old_root
    assert registry._owner_state.publication_generation == 0
    assert registry.branch_snapshot("branch-1") == harness.branch.value()
    assert _load_branch(harness) == harness.branch
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="spent"):
        _ = view.target
    _assert_registry_lock_is_released(registry)


def test_commit_then_raise_is_classified_and_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    view = registry.acquire_branch_mutation("branch-1")
    target = _branch_target(view.owner)
    view.target.state = target.state
    view.target.updated_at = target.updated_at
    view.target.failure_codes = target.failure_codes
    view.target.branch_evidence_summary = target.branch_evidence_summary
    original_commit = subject._sqlite._commit_coordinated_transaction

    def _commit_then_raise(session: object, authority: object) -> None:
        original_commit(session, authority)  # type: ignore[arg-type]
        raise KeyboardInterrupt("after durable commit")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        _commit_then_raise,
    )
    with pytest.raises(KeyboardInterrupt, match="after durable commit"):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)

    assert registry._owner_state.publication_generation == 1
    assert registry.branch_snapshot("branch-1").state is BranchState.READY_VALIDATE
    assert _load_branch(harness).owner_revision == 1
    _assert_registry_lock_is_released(registry)


def test_recovered_deactivation_fault_publishes_then_reports_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    view = registry.acquire_branch_mutation("branch-1")
    view.target.state = BranchState.READY_VALIDATE
    original_deactivate = subject._sqlite._deactivate_coordinated_transaction
    calls = 0

    def _deactivate_then_raise_once(session: object, authority: object) -> None:
        nonlocal calls
        calls += 1
        original_deactivate(session, authority)  # type: ignore[arg-type]
        if calls == 1:
            raise RuntimeError("after deactivation")

    monkeypatch.setattr(
        subject._sqlite,
        "_deactivate_coordinated_transaction",
        _deactivate_then_raise_once,
    )
    with pytest.raises(subject.CampaignOwnerCleanupError):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)

    assert calls == 2
    assert registry._owner_state.publication_generation == 1
    assert registry.branch_snapshot("branch-1").state is BranchState.READY_VALIDATE
    assert _load_branch(harness).owner_revision == 1
    _assert_registry_lock_is_released(registry)


def test_view_context_forgery_and_copy_fail_without_consuming_original(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    view = registry.acquire_branch_mutation("branch-1")

    with pytest.raises(subject.InvalidCampaignOwnerCapabilityError):
        subject.BranchMutationView()
    with pytest.raises(TypeError, match="sealed"):

        class _ForbiddenView(subject.BranchMutationView):
            pass

    forged = object.__new__(subject.BranchMutationView)
    with pytest.raises(subject.InvalidCampaignOwnerCapabilityError, match="not issued"):
        _ = forged.target
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(subject.InvalidCampaignOwnerCapabilityError):
            operation(view)

    def _consume_in_copied_context() -> None:
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)

    with pytest.raises(subject.CampaignOwnerLifecycleError, match="Contexts"):
        contextvars.copy_context().run(_consume_in_copied_context)

    view.target.state = BranchState.READY_VALIDATE
    with pytest.raises(RuntimeError, match="original context rollback"):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)
            raise RuntimeError("original context rollback")
    assert registry._owner_state.publication_generation == 0


@pytest.mark.parametrize("wrong_collection", ["branch", "hypothesis"])
def test_view_kind_must_match_its_claim_collection_before_begin(
    tmp_path: Path,
    wrong_collection: str,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    branch_view = registry.acquire_branch_mutation("branch-1")
    hypothesis_view = registry.acquire_hypothesis_mutation("hypothesis-active")

    with pytest.raises(subject.InvalidCampaignOwnerCapabilityError, match="kind"):
        if wrong_collection == "branch":
            with registry.owner_transaction(branch_views=(hypothesis_view,)) as scope:
                scope.compare_and_stage_hypothesis(hypothesis_view)
        else:
            with registry.owner_transaction(hypothesis_views=(branch_view,)) as scope:
                scope.compare_and_stage_branch(branch_view)

    assert registry._owner_state.publication_generation == 0
    assert _load_branch(harness).owner_revision == 0
    assert _load_hypothesis(harness, "hypothesis-active").owner_revision == 0


def test_branch_and_hypothesis_bundle_refresh_advance_once_and_purge_views(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    assert registry.refresh_branch_from_durable("branch-1") == harness.branch.value()
    assert registry._owner_state.publication_generation == 0

    stale_view = registry.acquire_branch_mutation("branch-1")
    branch_target = _branch_target(harness.branch)
    committed_branch = _external_branch_mutation(
        harness,
        harness.branch,
        branch_target,
    )
    refreshed = registry.refresh_branch_from_durable("branch-1")
    assert refreshed == committed_branch.value()
    assert registry._owner_state.publication_generation == 1
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="spent"):
        _ = stale_view.target

    committed_active, committed_alternate = _external_hypothesis_switch(harness)
    refreshed_hypothesis = registry.refresh_hypothesis_from_durable(
        "hypothesis-alternate"
    )
    assert refreshed_hypothesis == committed_alternate.value()
    assert registry._owner_state.publication_generation == 2
    assert registry.hypothesis_snapshot("hypothesis-active") == committed_active.value()
    assert (
        registry.current_hypothesis_snapshot("branch-1").hypothesis_id
        == "hypothesis-alternate"
    )


def test_refresh_fault_after_root_assignment_uses_identity_without_double_advance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    committed = _external_branch_mutation(
        harness,
        harness.branch,
        _branch_target(harness.branch),
    )
    original_spend = subject.CampaignOwnerRegistry._spend_stale_issued_views_locked

    def _spend_then_raise(
        self: subject.CampaignOwnerRegistry,
        old_root: object,
    ) -> None:
        original_spend(self, old_root)  # type: ignore[arg-type]
        raise RuntimeError("after refresh root assignment")

    monkeypatch.setattr(
        subject.CampaignOwnerRegistry,
        "_spend_stale_issued_views_locked",
        _spend_then_raise,
    )
    with pytest.raises(subject.CampaignOwnerCleanupError):
        registry.refresh_branch_from_durable("branch-1")

    assert registry._owner_state.publication_generation == 1
    assert registry.branch_snapshot("branch-1") == committed.value()
    monkeypatch.setattr(
        subject.CampaignOwnerRegistry,
        "_spend_stale_issued_views_locked",
        original_spend,
    )
    assert registry.refresh_branch_from_durable("branch-1") == committed.value()
    assert registry._owner_state.publication_generation == 1
    _assert_registry_lock_is_released(registry)


def test_same_database_inode_cannot_issue_a_second_registry(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    second_authority = sqlite_connection._issue_test_campaign_database_authority(
        harness.path,
        campaign_id="second-authority-same-database",
    )

    with pytest.raises(subject.CampaignOwnerLifecycleError, match="already"):
        subject.CampaignOwnerRegistry(second_authority)


def test_open_then_raise_recovers_the_unassigned_session_before_clearing_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    view = registry.acquire_branch_mutation("branch-1")
    original_open = subject._sqlite._open_coordinated_transaction_session

    def _open_then_raise(authority: object) -> object:
        original_open(authority)  # type: ignore[arg-type]
        raise KeyboardInterrupt("after coordinated open")

    monkeypatch.setattr(
        subject._sqlite,
        "_open_coordinated_transaction_session",
        _open_then_raise,
    )
    with pytest.raises(KeyboardInterrupt, match="after coordinated open"):
        with registry.owner_transaction(branch_views=(view,)):
            pass

    assert registry.branch_snapshot("branch-1") == harness.branch.value()
    assert subject._sqlite._thread_owner() is None
    assert subject._sqlite._thread_session_owner() is None
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="spent"):
        _ = view.target
    _assert_registry_lock_is_released(registry)


def test_preexisting_same_authority_session_is_rejected_without_hijack(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    view = registry.acquire_branch_mutation("branch-1")
    session = subject._sqlite._open_coordinated_transaction_session(
        harness.authority
    )

    with pytest.raises(subject.CampaignOwnerReentrancyError, match="nest"):
        with registry.owner_transaction(branch_views=(view,)):
            pass

    session_state = subject._sqlite._lookup_session_state(session)
    assert session_state.phase is subject._sqlite._SessionPhase.ACTIVE
    assert subject._sqlite._thread_session_owner() is session
    subject._sqlite._deactivate_coordinated_transaction(session, harness.authority)
    assert (
        subject._sqlite._settle_deactivated_original_connection(
            session,
            harness.authority,
        )
        is subject._sqlite._OriginalConnectionSettlement.ROLLED_BACK
    )

    view.target.state = BranchState.READY_VALIDATE
    with pytest.raises(RuntimeError, match="view remains issued"):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)
            raise RuntimeError("view remains issued")
    assert registry.branch_snapshot("branch-1") == harness.branch.value()


@pytest.mark.parametrize("interrupt_before_discard", [True, False])
def test_standalone_release_single_fault_cannot_strand_drain(
    tmp_path: Path,
    interrupt_before_discard: bool,
) -> None:
    harness = _harness(tmp_path, live=False)
    registry = harness.registry
    lease = subject._acquire_standalone_lease(registry)

    class _InterruptingSet(set[object]):
        calls = 0

        def discard(self, value: object) -> None:
            self.calls += 1
            if self.calls == 1 and interrupt_before_discard:
                raise KeyboardInterrupt("before standalone discard")
            super().discard(value)
            if self.calls == 1:
                raise KeyboardInterrupt("after standalone discard")

    registry._standalone_leases = _InterruptingSet(registry._standalone_leases)
    with pytest.raises(KeyboardInterrupt, match="standalone discard"):
        subject._release_standalone_lease(lease)

    assert not registry._standalone_leases
    restore = registry.begin_restore()
    registry.seal_live(restore)
    assert registry.branch_snapshot("branch-1") == harness.branch.value()


def test_standalone_drain_waits_for_release_and_permanently_denies_new_leases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, live=False)
    registry = harness.registry
    lease = subject._acquire_standalone_lease(registry)
    drain_waiting = threading.Event()
    live = threading.Event()
    errors: list[BaseException] = []
    original_wait_for = threading.Condition.wait_for

    def _observe_drain(
        condition: threading.Condition,
        predicate: object,
        timeout: float | None = None,
    ) -> bool:
        if condition is registry._condition:
            drain_waiting.set()
        return original_wait_for(condition, predicate, timeout)  # type: ignore[arg-type]

    monkeypatch.setattr(threading.Condition, "wait_for", _observe_drain)

    def _restore_and_seal() -> None:
        try:
            authority = registry.begin_restore()
            registry.seal_live(authority)
            live.set()
        except BaseException as error:
            errors.append(error)
            live.set()

    thread = threading.Thread(target=_restore_and_seal)
    thread.start()
    drain_waiting.wait()
    assert not live.is_set()
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="revoked"):
        subject._acquire_standalone_lease(registry)

    subject._release_standalone_lease(lease)
    thread.join()
    assert errors == []
    assert live.is_set()
    assert registry.branch_snapshot("branch-1") == harness.branch.value()
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="revoked"):
        subject._acquire_standalone_lease(registry)


@pytest.mark.parametrize("corruption", ["missing_branch", "two_active"])
def test_malformed_complete_restore_publishes_nothing_and_holds(
    tmp_path: Path,
    corruption: str,
) -> None:
    harness = _harness(tmp_path, live=False)
    if corruption == "missing_branch":
        _execute_raw(harness, "DELETE FROM branches WHERE branch_id = ?", ("branch-1",))
    else:
        _execute_raw(
            harness,
            "UPDATE hypotheses SET status = 'active' WHERE hypothesis_id = ?",
            ("hypothesis-alternate",),
        )

    with pytest.raises(subject.CampaignOwnerIntegrityHoldError, match="restore"):
        harness.registry.begin_restore()

    assert dict(harness.registry._owner_state.branch_slots) == {}
    assert dict(harness.registry._owner_state.hypothesis_slots.by_id) == {}
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError, match="hold"):
        harness.registry.branch_snapshot("branch-1")
    _assert_registry_lock_is_released(harness.registry)


def test_commit_classification_snapshot_failure_enters_permanent_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    old_root = registry._owner_state
    view = registry.acquire_branch_mutation("branch-1")
    view.target.state = BranchState.READY_VALIDATE
    original_snapshot = subject._sqlite._independent_authority_read_snapshot

    def _commit_interruption(_session: object, _authority: object) -> None:
        raise RuntimeError("commit interrupted before SQLite commit")

    def _snapshot_failure(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("classification snapshot unavailable")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        _commit_interruption,
    )
    monkeypatch.setattr(
        subject._sqlite,
        "_independent_authority_read_snapshot",
        _snapshot_failure,
    )
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError, match="uncertain"):
        with registry.owner_transaction(branch_views=(view,)) as scope:
            scope.compare_and_stage_branch(view)

    assert registry._owner_state is old_root
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError, match="hold"):
        registry.branch_snapshot("branch-1")
    monkeypatch.setattr(
        subject._sqlite,
        "_independent_authority_read_snapshot",
        original_snapshot,
    )
    assert _load_branch(harness) == harness.branch
    _assert_registry_lock_is_released(registry)


@pytest.mark.parametrize("corruption", ["moved", "missing_member", "two_active"])
def test_hypothesis_bundle_refresh_rejects_incoherent_durable_inventory(
    tmp_path: Path,
    corruption: str,
) -> None:
    harness = _harness(tmp_path)
    registry = harness.registry
    old_root = registry._owner_state
    if corruption == "moved":
        _execute_raw(
            harness,
            """
            UPDATE hypotheses
            SET branch_id = 'branch-2', owner_revision = owner_revision + 1
            WHERE hypothesis_id = ?
            """,
            ("hypothesis-alternate",),
        )
    elif corruption == "missing_member":
        _execute_raw(
            harness,
            "DELETE FROM hypotheses WHERE hypothesis_id = ?",
            ("hypothesis-active",),
        )
    else:
        _execute_raw(
            harness,
            """
            UPDATE hypotheses
            SET status = 'active', owner_revision = owner_revision + 1
            WHERE hypothesis_id = ?
            """,
            ("hypothesis-alternate",),
        )

    with pytest.raises(subject.CampaignOwnerIntegrityHoldError):
        registry.refresh_hypothesis_from_durable("hypothesis-alternate")

    assert registry._owner_state is old_root
    assert registry._owner_state.publication_generation == 0
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError, match="hold"):
        registry.hypothesis_snapshot("hypothesis-active")
    _assert_registry_lock_is_released(registry)
