from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import hypothesis_owner_store as subject
from scion.lineage import owner_transaction as owner
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerPayloadConflict,
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
    branch_storage_payload,
    generated_hypothesis_storage_payload,
    hypothesis_storage_payload,
)
from scion.tests.unit.lineage.checkpoint_b_schema_contract import (
    CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL,
    CHECKPOINT_B_MINIMAL_EXPERIMENT_EVENTS_DDL,
    CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL,
)


_CORRECTION = (
    Path(__file__).resolve().parents[4]
    / "docs/planning/v0.4/"
    "v0.4-d2b0b-hypothesis-creation-vertical-correction-20260716.md"
)


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_boundary.CampaignDatabaseAuthority
    store: subject.HypothesisStore
    branch: RevisionedBranchRecord
    prior: RevisionedHypothesisRecord | None
    target: RevisionedHypothesisRecord


def _branch() -> Branch:
    return Branch(
        branch_id="branch-generated",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="a" * 64,
        lineage_id="lineage-generated",
        current_code_hash="b" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=1,
        validation_expand_count=2,
        failure_codes=["SCREENING_FAILED"],
        created_at=datetime(2026, 7, 17, 1, 2, 3),
        updated_at=datetime(2026, 7, 17, 1, 2, 4),
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
    parent_hypothesis_id: str | None,
    created_at: datetime,
    proposal_digest: str,
) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hypothesis_id,
        branch_id="branch-generated",
        change_locus="local_search",
        action="modify",
        status=status,
        target_file="operators/local_search.py",
        parent_hypothesis_id=parent_hypothesis_id,
        suggested_weight=0.5,
        hypothesis_text="Use a bounded neighborhood.",
        created_at=created_at,
        base_champion_version=7,
        family_id="local-search",
        family_source="classifier",
        taxonomy_version="v1",
        predicted_direction="improve",
        proposal_digest=proposal_digest,
    )


def _schema(*, event_superset: bool) -> str:
    event_schema = (
        CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL
        if event_superset
        else CHECKPOINT_B_MINIMAL_EXPERIMENT_EVENTS_DDL
    )
    return """
    CREATE TABLE campaign_identity (campaign_id TEXT PRIMARY KEY);
    CREATE TABLE branches (
        branch_id TEXT PRIMARY KEY, state TEXT NOT NULL,
        base_champion_id INTEGER NOT NULL, base_champion_hash TEXT NOT NULL,
        lineage_id TEXT NOT NULL, current_code_hash TEXT,
        last_clean_code_hash TEXT, screening_expand_count INTEGER NOT NULL,
        validation_expand_count INTEGER NOT NULL, failure_codes TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, direction TEXT,
        weight_revision INTEGER NOT NULL, branch_code_status TEXT NOT NULL,
        branch_evidence_summary_json TEXT NOT NULL,
        infra_block_count INTEGER NOT NULL, owner_revision INTEGER NOT NULL,
        owner_protocol_generation TEXT NOT NULL
    );
    CREATE TABLE hypotheses (
        hypothesis_id TEXT PRIMARY KEY, branch_id TEXT NOT NULL,
        change_locus TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL,
        target_file TEXT, parent_hypothesis_id TEXT, suggested_weight REAL,
        hypothesis_text TEXT, created_at TEXT NOT NULL,
        base_champion_version INTEGER NOT NULL, family_id TEXT,
        family_source TEXT, taxonomy_version TEXT,
        predicted_direction TEXT NOT NULL, proposal_digest TEXT,
        owner_revision INTEGER NOT NULL,
        owner_protocol_generation TEXT NOT NULL
    );
    CREATE TABLE candidate_evaluation_leases (
        state TEXT NOT NULL, branch_id TEXT NOT NULL,
        source_hypothesis_id TEXT NOT NULL
    );
    """ + event_schema + CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _insert_branch(connection: sqlite3.Connection, token: RevisionedBranchRecord) -> None:
    payload = branch_storage_payload(token.value())
    connection.execute(
        """
        INSERT INTO branches VALUES (
            :branch_id, :state, :base_champion_id, :base_champion_hash,
            :lineage_id, :current_code_hash, :last_clean_code_hash,
            :screening_expand_count, :validation_expand_count, :failure_codes,
            :created_at, :updated_at, :direction, :weight_revision,
            :branch_code_status, :branch_evidence_summary_json,
            :infra_block_count, :owner_revision, :owner_protocol_generation
        )
        """,
        {
            **payload,
            "failure_codes": _canonical_json(payload["failure_codes"]),
            "branch_evidence_summary_json": _canonical_json(
                payload["branch_evidence_summary"]
            ),
            "owner_revision": token.owner_revision,
            "owner_protocol_generation": "durable-owner.v1",
        },
    )


def _insert_hypothesis(
    connection: sqlite3.Connection,
    token: RevisionedHypothesisRecord,
    *,
    overrides: dict[str, Any] | None = None,
) -> None:
    payload = generated_hypothesis_storage_payload(token.value())
    payload.update(overrides or {})
    connection.execute(
        subject._HYPOTHESIS_INSERT_SQL,
        {
            **payload,
            "owner_revision": token.owner_revision,
            "owner_protocol_generation": "durable-owner.v1",
        },
    )


def _insert_legacy_hypothesis(
    connection: sqlite3.Connection,
    token: RevisionedHypothesisRecord,
) -> None:
    payload = hypothesis_storage_payload(token.value())
    connection.execute(
        subject._HYPOTHESIS_INSERT_SQL,
        {
            **payload,
            "owner_revision": token.owner_revision,
            "owner_protocol_generation": "durable-owner.v1",
        },
    )


def _harness(
    tmp_path: Path,
    *,
    with_prior: bool = False,
    prior_status: str = "rejected",
    event_superset: bool = False,
) -> _Harness:
    path = tmp_path / "generated-owner.db"
    branch = RevisionedBranchRecord.from_value(_branch(), owner_revision=3)
    exact_second = datetime(2026, 7, 17, 2, 0, 0, tzinfo=timezone.utc)
    prior = (
        RevisionedHypothesisRecord.from_generated_value(
            _hypothesis(
                "hypothesis-prior",
                status=prior_status,
                parent_hypothesis_id=None,
                created_at=exact_second,
                proposal_digest="d" * 64,
            ),
            owner_revision=4,
        )
        if with_prior
        else None
    )
    target = RevisionedHypothesisRecord.from_generated_value(
        _hypothesis(
            "hypothesis-generated",
            status="active",
            parent_hypothesis_id=(None if prior is None else prior.hypothesis_id),
            created_at=exact_second + timedelta(seconds=1),
            proposal_digest="e" * 64,
        ),
        owner_revision=0,
    )
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.executescript(_schema(event_superset=event_superset))
        connection.execute(
            "INSERT INTO campaign_identity VALUES (?)", ("test-campaign",)
        )
        _insert_branch(connection, branch)
        if prior is not None:
            _insert_hypothesis(connection, prior)
        event_insert = """
            INSERT INTO experiment_events (
                event_id, campaign_id, branch_id, hypothesis_id,
                timestamp, event_kind, stage, audit_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        connection.execute(
            event_insert,
            (
                "event-started", "test-campaign", branch.branch_id, None,
                "2026-07-17T02:00:00.000000+00:00",
                "proposal_attempt_transition", "proposal_hypothesis", "{}",
            ),
        )
        connection.execute(
            event_insert,
            (
                "event-generated", "test-campaign", branch.branch_id,
                target.hypothesis_id,
                "2026-07-17T02:00:01.000000+00:00",
                "proposal_attempt_transition", "proposal_hypothesis", "{}",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    return _Harness(
        path=path,
        authority=authority,
        store=subject.HypothesisStore(authority),
        branch=branch,
        prior=prior,
        target=target,
    )


def _insert_binding(
    transaction: sqlite_boundary.ImmediateTransaction,
    harness: _Harness,
    **overrides: Any,
) -> None:
    values: dict[str, Any] = {
        "campaign_id": "test-campaign",
        "provider_attempt_id": "attempt-1",
        "started_event_id": "event-started",
        "generated_event_id": "event-generated",
        "branch_id": harness.branch.branch_id,
        "branch_owner_revision": harness.branch.owner_revision,
        "branch_storage_sha256": harness.branch.payload_sha256,
        "hypothesis_id": harness.target.hypothesis_id,
        "parent_hypothesis_id": (
            None if harness.prior is None else harness.prior.hypothesis_id
        ),
        "parent_owner_revision": (
            None if harness.prior is None else harness.prior.owner_revision
        ),
        "parent_storage_sha256": (
            None if harness.prior is None else harness.prior.payload_sha256
        ),
        "proposal_digest": harness.target.value().proposal_digest,
        "hypothesis_storage_sha256": harness.target.payload_sha256,
        "transition_group_sha256": "f" * 64,
        "binding_protocol_generation": "proposal-h-binding.v1",
        "created_at": "2026-07-17T02:00:01.000000+00:00",
    }
    values.update(overrides)
    sqlite_boundary._execute_participant(
        transaction,
        harness.authority,
        """
        INSERT INTO proposal_hypothesis_attempt_bindings VALUES (
            :campaign_id, :provider_attempt_id, :started_event_id,
            :generated_event_id, :branch_id, :branch_owner_revision,
            :branch_storage_sha256, :hypothesis_id, :parent_hypothesis_id,
            :parent_owner_revision, :parent_storage_sha256, :proposal_digest,
            :hypothesis_storage_sha256, :transition_group_sha256,
            :binding_protocol_generation, :created_at
        )
        """,
        values,
    )


def _authorization(
    transaction: sqlite_boundary.ImmediateTransaction,
    harness: _Harness,
    ledger: owner._OwnerReceiptLedger,
    *,
    owner_id: str | None = None,
    digest: str | None = None,
) -> tuple[
    owner._OwnerCreationAuthorizerAuthority,
    owner._OwnerCreationAuthorization,
]:
    authorizer = owner._issue_hypothesis_creation_authorizer_authority(
        harness.authority
    )
    authorization = owner._register_hypothesis_creation_authorization(
        authorizer,
        transaction,
        ledger,
        harness.target.hypothesis_id if owner_id is None else owner_id,
        harness.target.payload_sha256 if digest is None else digest,
    )
    return authorizer, authorization


def _complete(
    transaction: sqlite_boundary.ImmediateTransaction,
    ledger: owner._OwnerReceiptLedger,
    authorizer: owner._OwnerCreationAuthorizerAuthority,
    authorization: owner._OwnerCreationAuthorization,
    receipt: owner.OwnerCreationReceipt,
) -> owner._OwnerReceiptWitness:
    outcome = owner._issue_hypothesis_semantic_creation_outcome_witness(
        authorizer, transaction, ledger, authorization
    )
    owner._complete_hypothesis_creation_authorization(
        authorizer, transaction, ledger, authorization, receipt, outcome
    )
    witness = owner._consume_hypothesis_creation_receipt(ledger, receipt)
    owner._seal_owner_receipt_ledger(ledger, (receipt,))
    return witness


def _attempt(
    harness: _Harness,
    *,
    binding_overrides: dict[str, Any] | None = None,
    add_binding: bool = True,
) -> None:
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(transaction, harness.authority)
        if add_binding:
            _insert_binding(transaction, harness, **(binding_overrides or {}))
        authorizer, authorization = _authorization(transaction, harness, ledger)
        receipt = harness.store.insert_generated_once_in(
            transaction,
            harness.branch,
            harness.prior,
            harness.target,
            authorization,
        )
        _complete(transaction, ledger, authorizer, authorization, receipt)


def _mutate(path: Path, sql: str, parameters: tuple[object, ...] = ()) -> None:
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute(sql, parameters)
        connection.commit()
    finally:
        connection.close()


def test_generated_insert_sql_is_the_literal_frozen_statement() -> None:
    correction = _CORRECTION.read_text(encoding="utf-8")
    tail = correction.split("`_HYPOTHESIS_GENERATED_INSERT_SQL`", 1)[1]
    expected = tail.split("```sql", 1)[1].split("```", 1)[0]
    normalize = lambda value: re.sub(r"\s+", " ", value).strip()
    assert normalize(subject._HYPOTHESIS_GENERATED_INSERT_SQL) == normalize(expected)


def test_checkpoint_b_test_schema_is_the_literal_frozen_binding_contract() -> None:
    correction = _CORRECTION.read_text(encoding="utf-8")
    tail = correction.split(
        "The explicit test-only DDL is the final binding contract:",
        1,
    )[1]
    expected = tail.split("```sql", 1)[1].split("```", 1)[0]
    normalize = lambda value: re.sub(r"\s+", " ", value).strip()
    assert normalize(CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL) == normalize(expected)


@pytest.mark.parametrize("event_superset", [False, True])
def test_generated_insert_commits_exact_receipt_with_event_schema_variants(
    tmp_path: Path,
    event_superset: bool,
) -> None:
    harness = _harness(tmp_path, event_superset=event_superset)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(transaction, harness.authority)
        _insert_binding(transaction, harness)
        authorizer, authorization = _authorization(transaction, harness, ledger)
        receipt = harness.store.insert_generated_once_in(
            transaction,
            harness.branch,
            None,
            harness.target,
            authorization,
        )
        witness = _complete(
            transaction, ledger, authorizer, authorization, receipt
        )
        assert witness.owner_id == harness.target.hypothesis_id
        assert witness.expected_token is None
        assert witness.committed_token == harness.target
        assert witness.creation_authorization is authorization
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        row = connection.execute(
            "SELECT created_at FROM hypotheses WHERE hypothesis_id = ?",
            (harness.target.hypothesis_id,),
        ).fetchone()
        assert row[0] == "2026-07-17T02:00:01.000000+00:00"
    finally:
        connection.close()


def test_generated_codec_preserves_exact_seconds_without_changing_generic_codec() -> None:
    value = _hypothesis(
        "hypothesis-codec",
        status="active",
        parent_hypothesis_id=None,
        created_at=datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc),
        proposal_digest="a" * 64,
    )
    generated = RevisionedHypothesisRecord.from_generated_value(value, 0)
    generic = RevisionedHypothesisRecord.from_value(value, 0)
    assert b'"created_at":"2026-07-17T02:00:00.000000+00:00"' in (
        generated.canonical_storage_payload_json
    )
    assert b'"created_at":"2026-07-17T02:00:00+00:00"' in (
        generic.canonical_storage_payload_json
    )
    assert generated.value().created_at == value.created_at
    assert generated.payload_sha256 != generic.payload_sha256


@pytest.mark.parametrize(
    "created_at",
    [
        datetime(2026, 7, 17, 2, 0),
        datetime(2026, 7, 17, 2, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_generated_constructor_rejects_non_utc_datetime(created_at: datetime) -> None:
    value = _hypothesis(
        "hypothesis-bad-clock",
        status="active",
        parent_hypothesis_id=None,
        created_at=created_at,
        proposal_digest="a" * 64,
    )
    with pytest.raises(DurableOwnerIntegrityError, match="must use UTC"):
        RevisionedHypothesisRecord.from_generated_value(value, 0)


@pytest.mark.parametrize(
    "stored",
    [
        "2026-07-17T02:00:01Z",
        "2026-07-17T02:00:01+00:00",
        "2026-07-17T02:00:01.0+00:00",
        "2026-07-17T03:00:01.000000+01:00",
        "2026-07-17T02:00:01.0000000+00:00",
    ],
)
def test_generated_read_rejects_timestamp_text_variants(
    tmp_path: Path,
    stored: str,
) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, harness.target, overrides={"created_at": stored})
        connection.commit()
    finally:
        connection.close()
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        with pytest.raises(DurableOwnerIntegrityError, match="UTC microsecond"):
            harness.store._read_generated_required_in(
                transaction, harness.target.hypothesis_id
            )


def test_generated_snapshot_loader_returns_exact_second_target_or_absence(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, harness.target)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store._load_generated_revisioned_hypothesis_from_snapshot(
                snapshot,
                harness.target.hypothesis_id,
            )
            == harness.target
        )
        with pytest.raises(DurableOwnerIntegrityError):
            harness.store._load_revisioned_hypothesis_from_snapshot(
                snapshot,
                harness.target.hypothesis_id,
            )
        assert (
            harness.store._load_generated_revisioned_hypothesis_from_snapshot(
                snapshot,
                "hypothesis-missing",
            )
            is None
        )


def test_generated_snapshot_branch_bundle_preserves_legacy_prior(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    legacy = RevisionedHypothesisRecord.from_value(
        _hypothesis(
            "hypothesis-legacy-prior",
            status="rejected",
            parent_hypothesis_id=None,
            created_at=datetime(2026, 7, 16, 23, 59, 59),
            proposal_digest="c" * 64,
        ),
        owner_revision=5,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_legacy_hypothesis(connection, legacy)
        _insert_hypothesis(connection, harness.target)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store
            ._load_branch_hypotheses_with_generated_target_from_snapshot(
                snapshot,
                harness.branch.branch_id,
                harness.target.hypothesis_id,
            )
            == tuple(
                sorted(
                    (harness.target, legacy),
                    key=lambda token: token.hypothesis_id,
                )
            )
        )


def test_generated_snapshot_branch_bundle_accepts_generated_history(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, with_prior=True)
    assert harness.prior is not None
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, harness.target)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store
            ._load_branch_hypotheses_with_generated_target_from_snapshot(
                snapshot,
                harness.branch.branch_id,
                harness.target.hypothesis_id,
            )
            == tuple(
                sorted(
                    (harness.prior, harness.target),
                    key=lambda token: token.hypothesis_id,
                )
            )
        )


def test_generated_snapshot_branch_bundle_allows_rolled_back_target_absence(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    legacy = RevisionedHypothesisRecord.from_value(
        _hypothesis(
            "hypothesis-legacy-only",
            status="rejected",
            parent_hypothesis_id=None,
            created_at=datetime(2026, 7, 16, 23, 59, 59),
            proposal_digest="c" * 64,
        ),
        owner_revision=5,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_legacy_hypothesis(connection, legacy)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store
            ._load_branch_hypotheses_with_generated_target_from_snapshot(
                snapshot,
                harness.branch.branch_id,
                harness.target.hypothesis_id,
            )
            == (legacy,)
        )


def test_generated_snapshot_complete_inventory_preserves_target_and_legacy_rows(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    legacy = RevisionedHypothesisRecord.from_value(
        _hypothesis(
            "hypothesis-legacy-complete",
            status="rejected",
            parent_hypothesis_id=None,
            created_at=datetime(2026, 7, 16, 23, 59, 59),
            proposal_digest="c" * 64,
        ),
        owner_revision=5,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_legacy_hypothesis(connection, legacy)
        _insert_hypothesis(connection, harness.target)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        loaded = (
            harness.store
            ._load_all_hypotheses_with_generated_targets_from_snapshot(
                snapshot,
                (harness.target.hypothesis_id,),
            )
        )
    assert set(loaded) == {legacy, harness.target}


def test_generated_snapshot_complete_inventory_allows_absent_target_and_rejects_duplicates(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store
            ._load_all_hypotheses_with_generated_targets_from_snapshot(
                snapshot,
                (harness.target.hypothesis_id,),
            )
            == ()
        )
        with pytest.raises(DurableOwnerIntegrityError, match="duplicate"):
            harness.store._load_all_hypotheses_with_generated_targets_from_snapshot(
                snapshot,
                (harness.target.hypothesis_id, harness.target.hypothesis_id),
            )


@pytest.mark.parametrize(
    "stored",
    [
        "2026-07-17T02:00:01Z",
        "2026-07-17T02:00:01+00:00",
        "2026-07-17T02:00:01.0+00:00",
        "2026-07-17T03:00:01.000000+01:00",
    ],
)
def test_generated_snapshot_loaders_reject_target_timestamp_drift(
    tmp_path: Path,
    stored: str,
) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, harness.target, overrides={"created_at": stored})
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        with pytest.raises(DurableOwnerIntegrityError, match="UTC microsecond"):
            harness.store._load_generated_revisioned_hypothesis_from_snapshot(
                snapshot,
                harness.target.hypothesis_id,
            )
        with pytest.raises(DurableOwnerIntegrityError, match="UTC microsecond"):
            harness.store._load_branch_hypotheses_with_generated_target_from_snapshot(
                snapshot,
                harness.branch.branch_id,
                harness.target.hypothesis_id,
            )


def test_generated_snapshot_loaders_reject_nonzero_target_revision(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    nonzero = RevisionedHypothesisRecord.from_generated_value(
        harness.target.value(),
        owner_revision=1,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, nonzero)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        with pytest.raises(DurableOwnerIntegrityError, match="revision-zero"):
            harness.store._load_generated_revisioned_hypothesis_from_snapshot(
                snapshot,
                harness.target.hypothesis_id,
            )
        with pytest.raises(DurableOwnerIntegrityError, match="nonzero target revision"):
            harness.store._load_branch_hypotheses_with_generated_target_from_snapshot(
                snapshot,
                harness.branch.branch_id,
                harness.target.hypothesis_id,
            )


def test_generated_insert_classifies_duplicate_first(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, harness.target)
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(OwnerAlreadyExists, match="already exists"):
        _attempt(harness)


def test_generated_insert_classifies_source_branch_drift(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    _mutate(
        harness.path,
        "UPDATE branches SET state = ? WHERE branch_id = ?",
        ("abandoned", harness.branch.branch_id),
    )
    with pytest.raises(OwnerPayloadConflict, match="source Branch"):
        _attempt(harness)


@pytest.mark.parametrize(
    ("sql", "parameters"),
    [
        (
            "UPDATE hypotheses SET status = ? WHERE hypothesis_id = ?",
            ("validated", "hypothesis-prior"),
        ),
        (
            "UPDATE hypotheses SET created_at = ? WHERE hypothesis_id = ?",
            ("2026-07-17T02:00:02.000000+00:00", "hypothesis-prior"),
        ),
    ],
)
def test_generated_insert_classifies_prior_head_drift(
    tmp_path: Path,
    sql: str,
    parameters: tuple[object, ...],
) -> None:
    harness = _harness(tmp_path, with_prior=True)
    _mutate(harness.path, sql, parameters)
    with pytest.raises(OwnerPayloadConflict, match="prior history head"):
        _attempt(harness)


def test_generated_insert_classifies_later_history_head(tmp_path: Path) -> None:
    harness = _harness(tmp_path, with_prior=True)
    later = RevisionedHypothesisRecord.from_generated_value(
        dataclasses.replace(
            harness.prior.value(),  # type: ignore[union-attr]
            hypothesis_id="hypothesis-later",
            created_at=datetime(2026, 7, 17, 2, 0, 0, 500000, tzinfo=timezone.utc),
            proposal_digest="c" * 64,
        ),
        0,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_hypothesis(connection, later)
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(OwnerPayloadConflict, match="prior history head"):
        _attempt(harness)


def test_generated_insert_classifies_active_h(tmp_path: Path) -> None:
    harness = _harness(tmp_path, with_prior=True, prior_status="active")
    with pytest.raises(OwnerPayloadConflict, match="already has an active H"):
        _attempt(harness)


@pytest.mark.parametrize(
    ("branch_id", "source_hypothesis_id"),
    [
        ("branch-generated", "unrelated-h"),
        ("other-branch", "hypothesis-generated"),
        ("other-branch", "hypothesis-prior"),
    ],
)
def test_generated_insert_classifies_every_active_lease_identity(
    tmp_path: Path,
    branch_id: str,
    source_hypothesis_id: str,
) -> None:
    harness = _harness(tmp_path, with_prior=True)
    _mutate(
        harness.path,
        "INSERT INTO candidate_evaluation_leases VALUES ('active', ?, ?)",
        (branch_id, source_hypothesis_id),
    )
    with pytest.raises(OwnerPayloadConflict, match="active evaluation lease"):
        _attempt(harness)


@pytest.mark.parametrize(
    "overrides",
    [
        None,
        {"branch_storage_sha256": "0" * 64},
        {"proposal_digest": "0" * 64},
        {"hypothesis_storage_sha256": "0" * 64},
    ],
)
def test_generated_insert_classifies_binding_absence_or_drift(
    tmp_path: Path,
    overrides: dict[str, Any] | None,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(OwnerPayloadConflict, match="proposal-attempt binding"):
        _attempt(
            harness,
            add_binding=overrides is not None,
            binding_overrides=overrides,
        )


def test_generated_insert_classifies_unexplained_zero_as_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    monkeypatch.setattr(
        subject,
        "_HYPOTHESIS_GENERATED_INSERT_SQL",
        subject._HYPOTHESIS_GENERATED_INSERT_SQL + "\nAND 0",
    )
    with pytest.raises(DurableOwnerIntegrityError, match="despite exact predicates"):
        _attempt(harness)


def test_generated_zero_row_is_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    execute = subject._execute_generated_owner_insert
    calls = 0

    def counting_execute(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return execute(*args, **kwargs)

    monkeypatch.setattr(subject, "_execute_generated_owner_insert", counting_execute)
    with pytest.raises(OwnerPayloadConflict, match="proposal-attempt binding"):
        _attempt(harness, add_binding=False)
    assert calls == 1


def test_generated_insert_rejects_target_identity_before_sql(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    target = RevisionedHypothesisRecord.from_generated_value(
        dataclasses.replace(harness.target.value(), branch_id="other-branch"),
        0,
    )
    with pytest.raises(OwnerPayloadConflict, match="another Branch"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction, harness.authority
            )
            _, authorization = _authorization(transaction, harness, ledger)
            harness.store.insert_generated_once_in(
                transaction,
                harness.branch,
                None,
                target,
                authorization,
            )


def test_generated_insert_binds_authorization_digest_identity(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(owner.OwnerWriteProtocolError, match="token digest"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction, harness.authority
            )
            _insert_binding(transaction, harness)
            _, authorization = _authorization(
                transaction, harness, ledger, digest="0" * 64
            )
            harness.store.insert_generated_once_in(
                transaction,
                harness.branch,
                None,
                harness.target,
                authorization,
            )


def test_generated_token_rejects_non_protocol_fraction_even_with_valid_digest() -> None:
    value = _hypothesis(
        "hypothesis-manual-token",
        status="active",
        parent_hypothesis_id=None,
        created_at=datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc),
        proposal_digest="a" * 64,
    )
    payload = generated_hypothesis_storage_payload(value)
    payload["created_at"] = "2026-07-17T02:00:00.0+00:00"
    canonical = _canonical_json(payload).encode("utf-8")
    with pytest.raises(DurableOwnerIntegrityError, match="not canonical"):
        RevisionedHypothesisRecord(
            hypothesis_id=value.hypothesis_id,
            owner_revision=0,
            canonical_storage_payload_json=canonical,
            payload_sha256=hashlib.sha256(canonical).hexdigest(),
        )
