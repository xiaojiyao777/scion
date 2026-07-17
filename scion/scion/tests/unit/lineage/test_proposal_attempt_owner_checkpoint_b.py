from __future__ import annotations

import gc
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import hypothesis_owner_store
from scion.lineage import owner_transaction
from scion.lineage import proposal_attempt_owner as subject
from scion.lineage import sqlite_connection
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.proposal import hypothesis_generation_authority as generation
from scion.tests.unit.lineage.checkpoint_b_schema_contract import (
    CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL,
    CHECKPOINT_B_DROP_IMMUTABILITY_TRIGGERS_FOR_CORRUPTION_DDL,
    CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL,
)


_D = "d" * 64


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_connection.CampaignDatabaseAuthority
    owner: subject.ProposalAttemptOwner
    store: hypothesis_owner_store.HypothesisStore
    started_capability: generation.StartedHypothesisAttempt
    result_projection: generation._GeneratedResultProjection
    source_branch: RevisionedBranchRecord
    target: RevisionedHypothesisRecord


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _start_payload() -> dict[str, object]:
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "provider-attempt-1",
        "campaign_id": "test-campaign",
        "branch_id": "branch-1",
        "runtime_mode": "direct_v3",
        "phase": "hypothesis",
        "status": "started",
        "transition_reason": "provider_call_started",
        "failure_lane": None,
        "hypothesis_id": None,
        "hypothesis_digest": None,
        "patch_digest": None,
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": "context-digest",
            "prompt_hash": "prompt-hash",
            "trace_ref": None,
            "prompt_manifest_ref": None,
            "raw_response_ref": None,
            "provider_ok": None,
            "ok": None,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "cvrp",
            "problem_spec_hash": _D,
            "split_manifest_hash": _D,
            "seed_ledger_hash": _D,
            "champion_version": 7,
            "champion_weight_revision": 3,
            "champion_code_snapshot_hash": _D,
            "branch_base_champion_id": 7,
            "branch_base_champion_hash": _D,
        },
        "tainted_artifact_refs": [],
    }


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE campaign_identity (campaign_id TEXT PRIMARY KEY);
        CREATE TABLE branches (branch_id TEXT PRIMARY KEY);
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
        CREATE TABLE candidate_evaluation_leases (
            lease_id TEXT PRIMARY KEY,
            branch_id TEXT NOT NULL,
            source_hypothesis_id TEXT,
            state TEXT NOT NULL
        );
        """
        + CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL
        + CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL
    )
    connection.execute("INSERT INTO campaign_identity VALUES ('test-campaign')")
    connection.execute("INSERT INTO branches VALUES ('branch-1')")
    payload = _start_payload()
    connection.execute(
        subject._STARTED_EVENT_INSERT_SQL,
        (
            "event-start",
            "test-campaign",
            "branch-1",
            None,
            "2026-07-17T01:02:03.000004+00:00",
            "proposal_attempt_transition",
            "proposal_hypothesis",
            _canonical(payload).decode("utf-8"),
        ),
    )


def _harness(tmp_path: Path, *, text: str = "Use 路径-aware bounded moves.") -> _Harness:
    path = tmp_path / "proposal-checkpoint-b.db"
    connection = sqlite_connection._connect_sqlite(path)
    try:
        _create_schema(connection)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_connection._issue_test_campaign_database_authority(
        path,
        campaign_id="test-campaign",
    )
    owner = subject.ProposalAttemptOwner(authority)
    store = hypothesis_owner_store.HypothesisStore(authority)
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        inventory = owner._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
    started = inventory.groups[0].events[0]
    started_capability = object.__new__(generation.StartedHypothesisAttempt)
    owner._ProposalAttemptOwner__started_events[started_capability] = started

    proposal = {
        "hypothesis_text": text,
        "change_locus": "local_search",
        "action": "modify",
        "target_file": "operators/local_search.py",
        "predicted_direction": "improve",
        "target_weakness": "Current move set is too narrow.",
        "expected_effect": "Improve dense-instance quality.",
        "suggested_weight": 0.5,
    }
    proposal_bytes = _canonical(proposal)
    proposal_digest = hashlib.sha256(proposal_bytes).hexdigest()
    source_branch = RevisionedBranchRecord.from_value(
        Branch(
            branch_id="branch-1",
            state=BranchState.EXPLORE,
            base_champion_id=7,
            base_champion_hash=_D,
            current_code_hash=_D,
            last_clean_code_hash=_D,
            created_at=datetime(2026, 7, 17, 1, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 17, 1, 1, tzinfo=timezone.utc),
            weight_revision=3,
        ),
        owner_revision=4,
    )
    target = RevisionedHypothesisRecord.from_generated_value(
        HypothesisRecord(
            hypothesis_id="hypothesis-1",
            branch_id="branch-1",
            change_locus=proposal["change_locus"],
            action=proposal["action"],
            status="proposed",
            target_file=proposal["target_file"],
            suggested_weight=proposal["suggested_weight"],
            hypothesis_text=proposal["hypothesis_text"],
            created_at=datetime(
                2026, 7, 17, 1, 2, 5, 123456, tzinfo=timezone.utc
            ),
            base_champion_version=7,
            family_id="local-search",
            family_source="classifier",
            taxonomy_version="v1",
            predicted_direction=proposal["predicted_direction"],
            proposal_digest=proposal_digest,
        ),
        owner_revision=0,
    )
    result = generation._GeneratedResultProjection(
        permit=object(),
        started_attempt=started_capability,
        bound_prompt=object(),
        receipt=object(),
        trace_ref="artifact://trace",
        prompt_manifest_ref="artifact://trace#/prompt_manifest",
        raw_response_ref="artifact://trace#/response",
        proposal_canonical_bytes=proposal_bytes,
        proposal_sha256=proposal_digest,
        provider_ok=True,
        ok=True,
        error_category=None,
        error_type=None,
        trace_persistence_error=None,
    )
    return _Harness(
        path=path,
        authority=authority,
        owner=owner,
        store=store,
        started_capability=started_capability,
        result_projection=result,
        source_branch=source_branch,
        target=target,
    )


def _stage(
    harness: _Harness,
    *,
    commit: bool,
) -> tuple[
    owner_transaction._OwnerCreationAuthorization,
    owner_transaction.SemanticCreationOutcomeWitness,
]:
    authorization: owner_transaction._OwnerCreationAuthorization
    witness: owner_transaction.SemanticCreationOutcomeWitness
    class _Rollback(Exception):
        pass

    try:
        with sqlite_connection.immediate_transaction(harness.authority) as transaction:
            ledger = owner_transaction._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            authorization = harness.owner._register_generated_hypothesis_projection_in(
                transaction,
                ledger,
                result_projection=harness.result_projection,
                source_branch=harness.source_branch,
                prior_head=None,
                target=harness.target,
            )
            harness.owner.append_generated_hypothesis_creation_in(
                transaction,
                authorization,
            )
            receipt = harness.store.insert_once_in(
                transaction,
                harness.target.value(),
                authorization,
            )
            witness = harness.owner.complete_generated_hypothesis_creation_in(
                transaction,
                ledger,
                authorization,
                receipt,
            )
            harness.owner._require(witness, authorization)
            if not commit:
                raise _Rollback
            owner_transaction._consume_hypothesis_creation_receipt(ledger, receipt)
            owner_transaction._seal_owner_receipt_ledger(ledger, (receipt,))
    except _Rollback:
        pass
    return authorization, witness


def _classify(
    harness: _Harness,
    authorization: owner_transaction._OwnerCreationAuthorization,
    witness: owner_transaction.SemanticCreationOutcomeWitness,
) -> subject.ProposalAttemptCommitClassification:
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        return harness.owner._classify(snapshot, witness, authorization)


def test_generated_creation_round_trip_unicode_and_gc_safe_strong_projection(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    authorization, witness = _stage(harness, commit=True)
    state = harness.owner._ProposalAttemptOwner__creation_states[authorization]
    assert state.committed.generated is not None
    assert b"\\u8def\\u5f84" in harness.result_projection.proposal_canonical_bytes
    del state
    gc.collect()

    assert _classify(harness, authorization, witness) is (
        subject.ProposalAttemptCommitClassification.COMMITTED
    )
    harness.owner._settle(witness, authorization)
    harness.owner._settle(witness, authorization)
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        harness.owner._discard(authorization)


def test_normal_commit_settlement_needs_no_classification_snapshot(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    authorization, witness = _stage(harness, commit=True)
    harness.owner._settle(witness, authorization)
    harness.owner._settle(witness, authorization)
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        harness.owner._require(witness, authorization)


def test_rolled_back_semantic_group_is_expected_and_discard_is_exactly_idempotent(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    authorization, witness = _stage(harness, commit=False)
    assert _classify(harness, authorization, witness) is (
        subject.ProposalAttemptCommitClassification.EXPECTED
    )
    harness.owner._discard(authorization)
    harness.owner._discard(authorization)
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        harness.owner._settle(witness, authorization)


def test_frozen_binding_contract_rejects_update_and_delete(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    _stage(harness, commit=True)

    with sqlite3.connect(harness.path) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="proposal hypothesis binding is immutable",
        ):
            connection.execute(
                "UPDATE proposal_hypothesis_attempt_bindings "
                "SET created_at = created_at"
            )
        connection.rollback()
        with pytest.raises(
            sqlite3.IntegrityError,
            match="proposal hypothesis binding is immutable",
        ):
            connection.execute("DELETE FROM proposal_hypothesis_attempt_bindings")
        connection.rollback()
        assert connection.execute(
            "SELECT COUNT(*) FROM proposal_hypothesis_attempt_bindings"
        ).fetchone() == (1,)


def test_ordinary_event_cannot_be_updated_into_protected_attempt_storage(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            """
            INSERT INTO experiment_events (
                event_id, campaign_id, branch_id, hypothesis_id,
                timestamp, event_kind, stage, audit_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-ordinary",
                "test-campaign",
                "branch-1",
                None,
                "2026-07-17T01:02:03.000005+00:00",
                "experiment",
                "screening",
                "{}",
            ),
        )
        connection.commit()
        with pytest.raises(
            sqlite3.IntegrityError,
            match="proposal attempt event is append-only",
        ):
            connection.execute(
                "UPDATE experiment_events "
                "SET event_kind = 'proposal_attempt_transition', "
                "stage = 'proposal_hypothesis' "
                "WHERE event_id = 'event-ordinary'"
            )
        connection.rollback()
        assert connection.execute(
            "SELECT event_kind, stage FROM experiment_events "
            "WHERE event_id = 'event-ordinary'"
        ).fetchone() == ("experiment", "screening")


@pytest.mark.parametrize(
    "mutation",
    (
        "event_only",
        "binding_only",
        "raw_json",
        "binding_digest",
        "binding_parent",
        "binding_id",
    ),
)
def test_partial_or_drifted_semantic_groups_classify_mixed(
    tmp_path: Path,
    mutation: str,
) -> None:
    harness = _harness(tmp_path)
    authorization, witness = _stage(harness, commit=True)
    with sqlite3.connect(harness.path) as connection:
        connection.executescript(
            CHECKPOINT_B_DROP_IMMUTABILITY_TRIGGERS_FOR_CORRUPTION_DDL
        )
        if mutation == "event_only":
            connection.execute("DELETE FROM proposal_hypothesis_attempt_bindings")
        elif mutation == "binding_only":
            connection.execute(
                "DELETE FROM experiment_events WHERE event_id <> 'event-start'"
            )
        elif mutation == "raw_json":
            raw = connection.execute(
                "SELECT audit_payload_json FROM experiment_events "
                "WHERE event_id <> 'event-start'"
            ).fetchone()[0]
            connection.execute(
                "UPDATE experiment_events SET audit_payload_json = ? "
                "WHERE event_id <> 'event-start'",
                (json.dumps(json.loads(raw), indent=2),),
            )
        elif mutation == "binding_digest":
            connection.execute(
                "UPDATE proposal_hypothesis_attempt_bindings "
                "SET proposal_digest = ?",
                ("c" * 64,),
            )
        elif mutation == "binding_parent":
            connection.execute(
                "UPDATE proposal_hypothesis_attempt_bindings "
                "SET parent_hypothesis_id = 'parent-drift', "
                "parent_owner_revision = 3, parent_storage_sha256 = ?",
                ("b" * 64,),
            )
        else:
            connection.execute(
                "UPDATE proposal_hypothesis_attempt_bindings "
                "SET hypothesis_id = 'hypothesis-drift'"
            )
    assert _classify(harness, authorization, witness) is (
        subject.ProposalAttemptCommitClassification.MIXED
    )
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        harness.owner._discard(authorization)


def test_extra_terminal_is_mixed_and_event_only_generated_does_not_clear_restore(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    authorization, witness = _stage(harness, commit=True)
    start = _start_payload()
    failed = json.loads(json.dumps(start))
    failed.update(
        status="failed",
        transition_reason="provider_call_failed",
        failure_lane="infra",
    )
    failed["prompt_call"].update(
        provider_ok=False,
        ok=False,
        error_category="provider_call_failed",
        error_type="RuntimeError",
    )
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            subject._STARTED_EVENT_INSERT_SQL,
            (
                "event-extra",
                "test-campaign",
                "branch-1",
                None,
                "2026-07-17T01:02:06.000004+00:00",
                "proposal_attempt_transition",
                "proposal_hypothesis",
                _canonical(failed).decode("utf-8"),
            ),
        )
    assert _classify(harness, authorization, witness) is (
        subject.ProposalAttemptCommitClassification.MIXED
    )
    with sqlite3.connect(harness.path) as connection:
        connection.executescript(
            CHECKPOINT_B_DROP_IMMUTABILITY_TRIGGERS_FOR_CORRUPTION_DDL
        )
        connection.execute("DELETE FROM proposal_hypothesis_attempt_bindings")
        connection.execute("DELETE FROM experiment_events WHERE event_id = 'event-extra'")
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        inventory = harness.owner._load_hypothesis_attempt_inventory_from_snapshot(
            snapshot
        )
    assert inventory.branch_is_clear("branch-1") is False


def test_schema_valid_forged_terminal_mapping_cannot_clear_restore_hold(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    forged = _start_payload()
    forged.update(
        status="failed",
        transition_reason="bogus_reason",
        failure_lane="infra",
    )
    prompt = forged["prompt_call"]
    assert isinstance(prompt, dict)
    prompt.update(
        provider_ok=False,
        ok=False,
        error_category="bogus_category",
        error_type="RuntimeError",
    )
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            subject._STARTED_EVENT_INSERT_SQL,
            (
                "event-forged-terminal",
                "test-campaign",
                "branch-1",
                None,
                "2026-07-17T01:02:06.000004+00:00",
                "proposal_attempt_transition",
                "proposal_hypothesis",
                _canonical(forged).decode("utf-8"),
            ),
        )
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        inventory = harness.owner._load_hypothesis_attempt_inventory_from_snapshot(
            snapshot
        )

    assert inventory.groups[0].disposition is subject._AttemptGroupDisposition.MALFORMED
    assert inventory.branch_is_clear("branch-1") is False


@pytest.mark.parametrize(
    ("reason", "status", "lane", "provider_ok", "category", "error_type", "refs", "extra"),
    (
        (
            "provider_call_interrupted",
            "interrupted",
            None,
            False,
            "provider_call_interrupted",
            "RuntimeError",
            ("trace", "manifest", None),
            {"non_resumable": True},
        ),
        (
            "provider_call_failed",
            "failed",
            "infra",
            False,
            "transport_error",
            "RuntimeError",
            ("trace", "manifest", None),
            {},
        ),
        (
            "proposal_response_invalid",
            "failed",
            "invalid_response",
            True,
            "parse_error",
            "ValueError",
            ("trace", "manifest", "response"),
            {},
        ),
        (
            "hypothesis_contract_rejected",
            "failed",
            "invalid_response",
            True,
            "hypothesis_contract_rejected",
            "HypothesisContractRejection",
            ("trace", "manifest", "response"),
            {},
        ),
        (
            "provider_call_cancelled_before_transport",
            "failed",
            "infra",
            None,
            "provider_call_cancelled_before_transport",
            "AbortedHypothesisGeneration",
            (None, None, None),
            {},
        ),
    ),
)
def test_frozen_terminal_mapping_rejects_reason_specific_semantic_drift(
    reason: str,
    status: str,
    lane: str | None,
    provider_ok: bool | None,
    category: str,
    error_type: str,
    refs: tuple[str | None, str | None, str | None],
    extra: dict[str, object],
) -> None:
    tainted: list[str] = []
    for value in refs:
        if value is not None and value not in tainted:
            tainted.append(value)
    payload = _start_payload()
    payload.update(
        status=status,
        transition_reason=reason,
        failure_lane=lane,
        tainted_artifact_refs=tainted,
        **extra,
    )
    prompt = payload["prompt_call"]
    assert isinstance(prompt, dict)
    prompt.update(
        trace_ref=refs[0],
        prompt_manifest_ref=refs[1],
        raw_response_ref=refs[2],
        provider_ok=provider_ok,
        ok=False,
        error_category=category,
        error_type=error_type,
    )
    terminal = subject.StoredProposalAttemptEvent(
        event_id="terminal",
        campaign_id="test-campaign",
        branch_id="branch-1",
        hypothesis_id=None,
        timestamp="2026-07-17T01:02:06.000004+00:00",
        event_kind="proposal_attempt_transition",
        stage="proposal_hypothesis",
        audit_payload_json="{}",
        storage_sha256=_D,
        attempt_id="provider-attempt-1",
        status=status,
        context_digest="context-digest",
        prompt_hash="prompt-hash",
    )
    assert subject._terminal_has_frozen_mapping(terminal, payload) is True

    drifted = json.loads(json.dumps(payload))
    drifted["failure_lane"] = "invalid_response" if lane != "invalid_response" else "infra"
    assert subject._terminal_has_frozen_mapping(terminal, drifted) is False


@pytest.mark.parametrize("fault_point", ("registered", "event", "binding"))
def test_caller_retains_authorization_across_semantic_dml_faults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_point: str,
) -> None:
    harness = _harness(tmp_path)
    authorization: owner_transaction._OwnerCreationAuthorization

    class _Fault(Exception):
        pass

    real_event_append = subject._append_stored_proposal_attempt_event_in
    real_binding_append = subject._append_proposal_hypothesis_binding_in

    if fault_point == "event":
        def _fault_after_event(*args: object, **kwargs: object) -> object:
            real_event_append(*args, **kwargs)
            raise _Fault

        monkeypatch.setattr(
            subject,
            "_append_stored_proposal_attempt_event_in",
            _fault_after_event,
        )
    elif fault_point == "binding":
        def _fault_after_binding(*args: object, **kwargs: object) -> object:
            real_binding_append(*args, **kwargs)
            raise _Fault

        monkeypatch.setattr(
            subject,
            "_append_proposal_hypothesis_binding_in",
            _fault_after_binding,
        )

    with pytest.raises(_Fault):
        with sqlite_connection.immediate_transaction(harness.authority) as transaction:
            ledger = owner_transaction._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            authorization = harness.owner._register_generated_hypothesis_projection_in(
                transaction,
                ledger,
                result_projection=harness.result_projection,
                source_branch=harness.source_branch,
                prior_head=None,
                target=harness.target,
            )
            if fault_point == "registered":
                raise _Fault
            harness.owner.append_generated_hypothesis_creation_in(
                transaction,
                authorization,
            )

    harness.owner._discard(authorization)
    harness.owner._discard(authorization)
    assert authorization not in harness.owner._ProposalAttemptOwner__creation_states
    with sqlite3.connect(harness.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM experiment_events"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM proposal_hypothesis_attempt_bindings"
        ).fetchone() == (0,)


def test_active_lease_fails_before_authorization_registration(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            "INSERT INTO candidate_evaluation_leases VALUES (?, ?, ?, ?)",
            ("lease-1", "branch-1", None, "active"),
        )
    class _Rollback(Exception):
        pass

    with pytest.raises(_Rollback):
        with sqlite_connection.immediate_transaction(harness.authority) as transaction:
            ledger = owner_transaction._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(
                subject.InvalidStartedHypothesisAttemptError,
                match="active evaluation lease",
            ):
                harness.owner._register_generated_hypothesis_projection_in(
                    transaction,
                    ledger,
                    result_projection=harness.result_projection,
                    source_branch=harness.source_branch,
                    prior_head=None,
                    target=harness.target,
                )
            raise _Rollback


def test_contract_rejection_rebuilds_exact_terminal_failure_payload(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    started = harness.owner._ProposalAttemptOwner__started_events[
        harness.started_capability
    ]
    projection = generation._TerminalOutcomeProjection(
        kind="hypothesis_contract_rejected",
        permit=object(),
        started_attempt=harness.started_capability,
        bound_prompt=object(),
        receipt=object(),
        trace_ref="artifact://trace",
        prompt_manifest_ref="artifact://trace#/prompt_manifest",
        raw_response_ref="artifact://trace#/response",
        provider_ok=True,
        ok=False,
        failure_category="hypothesis_contract_rejected",
        failure_type="HypothesisContractRejection",
        trace_persistence_error=None,
        contract_result=object(),
    )
    payload = subject._terminal_payload_from_start(started, projection)
    assert payload["status"] == "failed"
    assert payload["transition_reason"] == "hypothesis_contract_rejected"
    assert payload["failure_lane"] == "invalid_response"
    prompt = payload["prompt_call"]
    assert isinstance(prompt, dict)
    assert prompt["provider_ok"] is True
    assert prompt["ok"] is False
    assert prompt["error_category"] == "hypothesis_contract_rejected"
