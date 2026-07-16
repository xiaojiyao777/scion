"""Focused tests for atomic campaign ownership bootstrap."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from scion.core.campaign_open import (
    CAMPAIGN_OPEN_REQUEST_SCHEMA,
    CampaignOpenConflictError,
    CampaignOpenKind,
    CampaignOpenRequest,
    CampaignOpenRequestResolver,
    CampaignOwnershipStore,
    CandidateOwnershipMode,
)


class SimulatedIdentityPublishCrash(RuntimeError):
    pass


def _ownership_rows(db_path: Path) -> tuple[object, object]:
    with sqlite3.connect(db_path) as conn:
        identity = conn.execute(
            "SELECT campaign_id, created_at FROM campaign_identity "
            "WHERE singleton_id = 1"
        ).fetchone()
        mode = conn.execute(
            "SELECT campaign_id, mode, created_at FROM candidate_ownership_mode "
            "WHERE singleton = 1"
        ).fetchone()
    return identity, mode


def _create_event_table(db_path: Path, campaign_ids: tuple[str, ...]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE experiment_events "
            "(event_id TEXT PRIMARY KEY, campaign_id TEXT)"
        )
        conn.executemany(
            "INSERT INTO experiment_events (event_id, campaign_id) VALUES (?, ?)",
            tuple(
                (f"event-{index}", value) for index, value in enumerate(campaign_ids)
            ),
        )


def test_request_is_typed_and_rejects_invalid_identity() -> None:
    request = CampaignOpenRequest("NEW", "campaign-1", "candidate_snapshot_v1")

    assert request.kind is CampaignOpenKind.NEW
    assert request.expected_mode is CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
    with pytest.raises(ValueError, match="campaign identity"):
        CampaignOpenRequest(CampaignOpenKind.NEW, " campaign-1")
    with pytest.raises(ValueError, match="open kind"):
        CampaignOpenRequest("RESUME", "campaign-1")


def test_new_claims_identity_and_snapshot_mode_in_one_transaction(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    store = CampaignOwnershipStore(db_path)
    request = CampaignOpenRequest(CampaignOpenKind.NEW, "campaign-new")

    result = store.open(request)

    assert result.campaign_id == "campaign-new"
    assert result.mode is CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
    assert result.adopted_pre_d2_identity is False
    identity, mode = _ownership_rows(db_path)
    assert identity is not None and mode is not None
    assert identity[0] == mode[0] == "campaign-new"
    assert identity[1] == mode[2]

    reopened = store.open(
        CampaignOpenRequest(
            CampaignOpenKind.REOPEN,
            "campaign-new",
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
        )
    )
    assert reopened == result
    with pytest.raises(CampaignOpenConflictError, match="already has durable state"):
        store.open(request)
    with sqlite3.connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "UPDATE candidate_ownership_mode SET mode = ? WHERE singleton = 1",
                (CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1.value,),
            )


@pytest.mark.parametrize(
    "table",
    ("formal_candidate_index", "events", "future_campaign_owner"),
)
def test_new_rejects_any_existing_durable_row_without_partial_claim(
    tmp_path: Path,
    table: str,
) -> None:
    db_path = tmp_path / "scion.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"CREATE TABLE {table} (owner_id TEXT)")
        conn.execute(f"INSERT INTO {table} VALUES ('owner-1')")
    store = CampaignOwnershipStore(db_path)

    with pytest.raises(CampaignOpenConflictError, match="already has durable state"):
        store.open(CampaignOpenRequest(CampaignOpenKind.NEW, "campaign-new"))

    assert _ownership_rows(db_path) == (None, None)


def test_pre_d2_identity_is_claimed_as_legacy_in_same_reopen_transaction(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    store = CampaignOwnershipStore(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO campaign_identity "
            "(singleton_id, campaign_id, created_at) VALUES (1, ?, 'old')",
            ("campaign-legacy",),
        )

    result = store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-legacy"))

    assert result.mode is CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1
    assert result.adopted_pre_d2_identity is True
    identity, mode = _ownership_rows(db_path)
    assert identity is not None and mode is not None
    assert identity[0] == mode[0] == "campaign-legacy"
    assert mode[1] == CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1.value


def test_pre_d2_identity_rejects_contradictory_event_history(tmp_path: Path) -> None:
    db_path = tmp_path / "scion.db"
    _create_event_table(db_path, ("event-campaign",))
    store = CampaignOwnershipStore(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO campaign_identity "
            "(singleton_id, campaign_id, created_at) VALUES (1, ?, 'old')",
            ("identity-campaign",),
        )

    with pytest.raises(CampaignOpenConflictError, match="event history conflicts"):
        store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "identity-campaign"))

    identity, mode = _ownership_rows(db_path)
    assert identity is not None and identity[0] == "identity-campaign"
    assert mode is None


def test_pre_identity_reopen_requires_positive_legacy_state(
    tmp_path: Path,
) -> None:
    empty_db = tmp_path / "empty.db"
    empty = CampaignOwnershipStore(empty_db)
    with pytest.raises(CampaignOpenConflictError, match="no adoptable"):
        empty.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "caller-empty"))
    assert _ownership_rows(empty_db) == (None, None)

    formal_db = tmp_path / "formal.db"
    with sqlite3.connect(formal_db) as conn:
        conn.execute("CREATE TABLE formal_candidate_index (candidate_id TEXT)")
        conn.execute("INSERT INTO formal_candidate_index VALUES ('candidate-1')")
    formal = CampaignOwnershipStore(formal_db)
    with pytest.raises(CampaignOpenConflictError, match="no adoptable"):
        formal.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "caller-formal"))
    assert _ownership_rows(formal_db) == (None, None)

    branch_db = tmp_path / "branch.db"
    with sqlite3.connect(branch_db) as conn:
        conn.execute("CREATE TABLE branches (branch_id TEXT)")
        conn.execute("INSERT INTO branches VALUES ('branch-1')")
    branch = CampaignOwnershipStore(branch_db).open(
        CampaignOpenRequest(CampaignOpenKind.REOPEN, "caller-branch")
    )
    assert branch.campaign_id == "caller-branch"
    assert branch.mode is CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1


def test_pre_identity_event_history_requires_caller_match_and_rejects_many(
    tmp_path: Path,
) -> None:

    one_db = tmp_path / "one.db"
    _create_event_table(one_db, ("event-owned", "event-owned"))
    one_store = CampaignOwnershipStore(one_db)
    with pytest.raises(CampaignOpenConflictError, match="caller-bound"):
        one_store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "caller-proposed"))
    assert _ownership_rows(one_db) == (None, None)
    one = one_store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "event-owned"))
    assert one.campaign_id == "event-owned"
    assert _ownership_rows(one_db)[0][0] == "event-owned"  # type: ignore[index]

    many_db = tmp_path / "many.db"
    _create_event_table(many_db, ("campaign-a", "campaign-b"))
    many_store = CampaignOwnershipStore(many_db)
    with pytest.raises(CampaignOpenConflictError, match="ambiguous"):
        many_store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "caller-proposed"))
    assert _ownership_rows(many_db) == (None, None)


def test_reopen_rejects_identity_mode_and_expected_mode_conflicts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    store = CampaignOwnershipStore(db_path)
    store.open(CampaignOpenRequest(CampaignOpenKind.NEW, "campaign-1"))

    with pytest.raises(CampaignOpenConflictError, match="contradictory"):
        store.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-2"))
    with pytest.raises(CampaignOpenConflictError, match="does not match"):
        store.open(
            CampaignOpenRequest(
                CampaignOpenKind.REOPEN,
                "campaign-1",
                CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
            )
        )

    broken_db = tmp_path / "broken.db"
    broken = CampaignOwnershipStore(broken_db)
    with sqlite3.connect(broken_db) as conn:
        conn.execute(
            "INSERT INTO candidate_ownership_mode "
            "(singleton, campaign_id, mode, created_at) VALUES (1, ?, ?, 'now')",
            ("campaign-1", CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1.value),
        )
    with pytest.raises(CampaignOpenConflictError, match="has no campaign identity"):
        broken.open(CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-1"))


def test_new_rejects_legacy_expected_mode(tmp_path: Path) -> None:
    store = CampaignOwnershipStore(tmp_path / "scion.db")

    with pytest.raises(CampaignOpenConflictError, match="require snapshot"):
        store.open(
            CampaignOpenRequest(
                CampaignOpenKind.NEW,
                "campaign-1",
                CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
            )
        )

    assert _ownership_rows(tmp_path / "scion.db") == (None, None)


def test_pair_claim_rolls_back_if_second_insert_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "scion.db"
    store = CampaignOwnershipStore(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TRIGGER reject_mode_insert BEFORE INSERT ON "
            "candidate_ownership_mode BEGIN SELECT RAISE(ABORT, 'fault'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="fault"):
        store.open(CampaignOpenRequest(CampaignOpenKind.NEW, "campaign-1"))

    assert _ownership_rows(db_path) == (None, None)


def test_caller_resolver_reuses_identity_across_bootstrap_crash_and_reopen(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    (campaign / "candidate_snapshots").mkdir(parents=True)
    (campaign / "candidate_snapshots" / "not-an-owner.json").write_text("{}")
    resolver = CampaignOpenRequestResolver(campaign)

    first = resolver.resolve()
    before_db = resolver.resolve()

    assert first.kind is CampaignOpenKind.NEW
    assert before_db == first
    identity_payload = json.loads(
        (campaign / "campaign-open-identity.v1.json").read_text()
    )
    assert identity_payload == {
        "campaign_id": first.campaign_id,
        "schema_version": CAMPAIGN_OPEN_REQUEST_SCHEMA,
    }

    CampaignOwnershipStore(campaign / "scion.db").open(first)
    reopened = resolver.resolve(
        expected_mode=CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
    )
    assert reopened == CampaignOpenRequest(
        CampaignOpenKind.REOPEN,
        first.campaign_id,
        CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
    )


def test_resolver_adopts_legacy_event_identity_and_fails_before_rebinding(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    _create_event_table(campaign / "scion.db", ("campaign-legacy",))
    resolver = CampaignOpenRequestResolver(campaign)

    request = resolver.resolve(
        expected_mode=CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1
    )

    assert request == CampaignOpenRequest(
        CampaignOpenKind.REOPEN,
        "campaign-legacy",
        CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
    )
    with pytest.raises(CampaignOpenConflictError, match="contradictory"):
        resolver.resolve(campaign_id="different")
    assert resolver.resolve().campaign_id == "campaign-legacy"


def test_explicit_reopen_event_mismatch_does_not_bind_identity(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    _create_event_table(campaign / "scion.db", ("campaign-legacy",))
    resolver = CampaignOpenRequestResolver(campaign)

    with pytest.raises(CampaignOpenConflictError, match="caller-bound"):
        resolver.resolve(CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-wrong"))

    identity_path = campaign / "campaign-open-identity.v1.json"
    assert not identity_path.exists()
    correct = resolver.resolve(
        CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-legacy")
    )
    assert correct.campaign_id == "campaign-legacy"
    assert json.loads(identity_path.read_text())["campaign_id"] == "campaign-legacy"


@pytest.mark.parametrize(
    "phase",
    ("after_temp_create", "after_temp_write", "after_temp_fsync"),
)
def test_identity_publish_crash_before_link_leaves_no_final_claim(
    tmp_path: Path,
    phase: str,
) -> None:
    campaign = tmp_path / "campaign"

    def crash(current: str) -> None:
        if current == phase:
            raise SimulatedIdentityPublishCrash(current)

    resolver = CampaignOpenRequestResolver(campaign, fault_hook=crash)
    with pytest.raises(SimulatedIdentityPublishCrash, match=phase):
        resolver.resolve(campaign_id="campaign-stable")

    identity_path = campaign / "campaign-open-identity.v1.json"
    assert not identity_path.exists()
    recovered = CampaignOpenRequestResolver(campaign).resolve(
        campaign_id="campaign-stable"
    )
    assert recovered.campaign_id == "campaign-stable"
    assert json.loads(identity_path.read_text())["campaign_id"] == "campaign-stable"


def test_identity_publish_crash_after_link_recovers_complete_claim(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"

    def crash(phase: str) -> None:
        if phase == "after_publish":
            raise SimulatedIdentityPublishCrash(phase)

    resolver = CampaignOpenRequestResolver(campaign, fault_hook=crash)
    with pytest.raises(SimulatedIdentityPublishCrash, match="after_publish"):
        resolver.resolve(campaign_id="campaign-stable")

    identity_path = campaign / "campaign-open-identity.v1.json"
    assert json.loads(identity_path.read_text()) == {
        "campaign_id": "campaign-stable",
        "schema_version": CAMPAIGN_OPEN_REQUEST_SCHEMA,
    }
    recovered = CampaignOpenRequestResolver(campaign).resolve(
        campaign_id="campaign-stable"
    )
    assert recovered.campaign_id == "campaign-stable"


def test_concurrent_identity_claim_publishes_exactly_one_complete_owner(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    barrier = Barrier(2)

    def claim(campaign_id: str) -> tuple[str, object]:
        def synchronize(phase: str) -> None:
            if phase == "after_temp_fsync":
                barrier.wait(timeout=5)

        resolver = CampaignOpenRequestResolver(campaign, fault_hook=synchronize)
        try:
            return "ok", resolver.resolve(campaign_id=campaign_id)
        except CampaignOpenConflictError as exc:
            return "conflict", exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(claim, ("campaign-first", "campaign-second")))

    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    winner = next(value for status, value in results if status == "ok")
    identity_path = campaign / "campaign-open-identity.v1.json"
    payload = json.loads(identity_path.read_text())
    assert payload["campaign_id"] == winner.campaign_id
    assert payload["schema_version"] == CAMPAIGN_OPEN_REQUEST_SCHEMA
    assert not tuple(campaign.glob(".campaign-open-identity.v1.json.*.tmp"))


def test_resolver_does_not_bind_formal_only_state_as_legacy(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    with sqlite3.connect(campaign / "scion.db") as conn:
        conn.execute("CREATE TABLE formal_candidate_index (candidate_id TEXT)")
        conn.execute("INSERT INTO formal_candidate_index VALUES ('candidate-1')")
    resolver = CampaignOpenRequestResolver(campaign)

    with pytest.raises(CampaignOpenConflictError, match="no adoptable"):
        resolver.resolve()

    assert not (campaign / "campaign-open-identity.v1.json").exists()


def test_store_refuses_untyped_open_input(tmp_path: Path) -> None:
    store = CampaignOwnershipStore(tmp_path / "scion.db")

    with pytest.raises(TypeError, match="typed request"):
        store.open(  # type: ignore[arg-type]
            {"kind": "NEW", "campaign_id": "campaign-1"}
        )
