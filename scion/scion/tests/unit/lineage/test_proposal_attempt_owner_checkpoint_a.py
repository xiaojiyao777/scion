from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scion.lineage import proposal_attempt_owner as subject
from scion.lineage import sqlite_connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE experiment_events (
            event_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            hypothesis_id TEXT,
            timestamp TEXT NOT NULL,
            event_kind TEXT NOT NULL,
            stage TEXT NOT NULL,
            audit_payload_json TEXT NOT NULL
        )
        """)


def _started_payload(
    *,
    attempt_id: str = "attempt-1",
    branch_id: str = "branch-1",
) -> dict[str, object]:
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": attempt_id,
        "campaign_id": "test-campaign",
        "branch_id": branch_id,
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
            "problem_spec_hash": "spec-hash",
            "split_manifest_hash": "split-hash",
            "seed_ledger_hash": "seed-hash",
            "champion_version": 7,
            "champion_weight_revision": 3,
            "champion_code_snapshot_hash": "a" * 64,
            "branch_base_champion_id": 7,
            "branch_base_champion_hash": "a" * 64,
        },
        "tainted_artifact_refs": [],
    }


def _terminal_payload(
    started: dict[str, object],
    *,
    status: str,
) -> dict[str, object]:
    payload = json.loads(json.dumps(started))
    prompt_call = payload["prompt_call"]
    assert isinstance(prompt_call, dict)
    if status == "generated":
        payload.update(
            status="generated",
            transition_reason="generated",
            hypothesis_id="hypothesis-1",
            hypothesis_digest="b" * 64,
        )
        prompt_call.update(
            trace_ref="traces/attempt-1.json",
            prompt_manifest_ref="traces/attempt-1.json#/prompt_manifest",
            raw_response_ref="traces/attempt-1.json#/response",
            provider_ok=True,
            ok=True,
        )
    elif status == "failed":
        payload.update(
            status="failed",
            transition_reason="provider_call_failed",
            failure_lane="infra",
        )
        prompt_call.update(
            provider_ok=False,
            ok=False,
            error_category="provider_call_failed",
            error_type="RuntimeError",
        )
    elif status == "interrupted":
        payload.update(
            status="interrupted",
            transition_reason="provider_call_interrupted",
            non_resumable=True,
        )
        prompt_call.update(
            provider_ok=False,
            ok=False,
            error_category="provider_call_interrupted",
            error_type="KeyboardInterrupt",
        )
    else:  # pragma: no cover - test helper contract
        raise AssertionError(status)
    return payload


def _canonical_payload(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _insert(
    path: Path,
    payload: dict[str, object],
    *,
    event_id: str,
    timestamp: str,
    raw_payload: str | None = None,
    branch_id: str | None = None,
    hypothesis_id: str | None | object = ...,
) -> None:
    if hypothesis_id is ...:
        hypothesis_id = payload.get("hypothesis_id")
    with sqlite3.connect(path) as connection:
        connection.execute(
            subject._STARTED_EVENT_INSERT_SQL,
            (
                event_id,
                payload["campaign_id"],
                branch_id if branch_id is not None else payload["branch_id"],
                hypothesis_id,
                timestamp,
                "proposal_attempt_transition",
                "proposal_hypothesis",
                raw_payload if raw_payload is not None else _canonical_payload(payload),
            ),
        )


def _harness(
    tmp_path: Path,
) -> tuple[Path, sqlite_connection.CampaignDatabaseAuthority, subject.ProposalAttemptOwner]:
    path = tmp_path / "checkpoint-a-attempt-owner.db"
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
    return path, authority, subject.ProposalAttemptOwner(authority)


def _inventory(
    authority: sqlite_connection.CampaignDatabaseAuthority,
    owner: subject.ProposalAttemptOwner,
) -> subject._HypothesisAttemptInventory:
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        return owner._load_hypothesis_attempt_inventory_from_snapshot(snapshot)


def test_strict_stored_event_codec_binds_all_eight_raw_values(tmp_path: Path) -> None:
    path, authority, owner = _harness(tmp_path)
    payload = _started_payload()
    raw_payload = _canonical_payload(payload)
    timestamp = "2026-07-17T01:02:03.000004+00:00"
    _insert(
        path,
        payload,
        event_id="event-start",
        timestamp=timestamp,
        raw_payload=raw_payload,
    )

    inventory = _inventory(authority, owner)
    event = inventory.groups[0].events[0]
    expected_storage = {
        "schema_version": "proposal-attempt-event-storage.v1",
        "event_id": "event-start",
        "campaign_id": "test-campaign",
        "branch_id": "branch-1",
        "hypothesis_id": None,
        "timestamp": timestamp,
        "event_kind": "proposal_attempt_transition",
        "stage": "proposal_hypothesis",
        "audit_payload_json": raw_payload,
    }
    expected_bytes = json.dumps(
        expected_storage,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert event.storage_sha256 == hashlib.sha256(expected_bytes).hexdigest()
    assert event.canonical_payload_json == raw_payload.encode("utf-8")
    assert inventory.groups[0].disposition is subject._AttemptGroupDisposition.UNRESOLVED


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-07-17T01:02:03Z",
        "2026-07-17T01:02:03+00:00",
        "2026-07-17T01:02:03.000004+01:00",
        "2026-07-17T01:02:03.00004+00:00",
    ),
)
def test_restore_inventory_holds_noncanonical_timestamp(
    tmp_path: Path,
    timestamp: str,
) -> None:
    path, authority, owner = _harness(tmp_path)
    _insert(path, _started_payload(), event_id="bad-time", timestamp=timestamp)

    inventory = _inventory(authority, owner)
    assert inventory.groups == ()
    assert inventory.malformed_branch_ids == ("branch-1",)
    assert inventory.branch_is_clear("branch-1") is False


@pytest.mark.parametrize("raw_kind", ("pretty", "duplicate", "nonfinite"))
def test_restore_inventory_holds_noncanonical_or_malformed_raw_json(
    tmp_path: Path,
    raw_kind: str,
) -> None:
    path, authority, owner = _harness(tmp_path)
    payload = _started_payload()
    canonical = _canonical_payload(payload)
    if raw_kind == "pretty":
        raw = json.dumps(payload, indent=2)
    elif raw_kind == "duplicate":
        raw = canonical[:-1] + ',"status":"started"}'
    else:
        raw = canonical.replace('"champion_version":7', '"champion_version":NaN')
    _insert(
        path,
        payload,
        event_id=f"bad-{raw_kind}",
        timestamp="2026-07-17T01:02:03.000004+00:00",
        raw_payload=raw,
    )

    inventory = _inventory(authority, owner)
    assert inventory.groups == ()
    assert inventory.malformed_branch_ids == ("branch-1",)


@pytest.mark.parametrize("status", ("generated", "failed", "interrupted"))
def test_complete_strict_terminal_group_is_resolved(
    tmp_path: Path,
    status: str,
) -> None:
    path, authority, owner = _harness(tmp_path)
    started = _started_payload()
    terminal = _terminal_payload(started, status=status)
    _insert(
        path,
        started,
        event_id="event-start",
        timestamp="2026-07-17T01:02:03.000004+00:00",
    )
    _insert(
        path,
        terminal,
        event_id=f"event-{status}",
        timestamp="2026-07-17T01:02:04.000004+00:00",
    )

    inventory = _inventory(authority, owner)
    assert len(inventory.groups) == 1
    assert inventory.groups[0].disposition is subject._AttemptGroupDisposition.RESOLVED
    assert inventory.branch_is_clear("branch-1") is True


def test_transaction_preflight_rejects_open_branch_and_reused_natural_key(
    tmp_path: Path,
) -> None:
    path, authority, owner = _harness(tmp_path)
    started = _started_payload()
    _insert(
        path,
        started,
        event_id="event-start",
        timestamp="2026-07-17T01:02:03.000004+00:00",
    )

    with sqlite_connection.immediate_transaction(authority) as transaction:
        with pytest.raises(subject.InvalidStartedHypothesisAttemptError, match="Branch"):
            owner._require_branch_clear_for_start_in(
                transaction,
                branch_id="branch-1",
                attempt_id="attempt-2",
            )
        with pytest.raises(subject.InvalidStartedHypothesisAttemptError, match="natural"):
            owner._require_branch_clear_for_start_in(
                transaction,
                branch_id="branch-2",
                attempt_id="attempt-1",
            )


def test_start_and_terminal_classifiers_cover_expected_committed_and_mixed(
    tmp_path: Path,
) -> None:
    path, authority, owner = _harness(tmp_path)
    started_payload = _started_payload()
    _insert(
        path,
        started_payload,
        event_id="event-start",
        timestamp="2026-07-17T01:02:03.000004+00:00",
    )
    committed_inventory = _inventory(authority, owner)
    started = committed_inventory.groups[0].events[0]
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        assert owner._classify_started_event_from_snapshot(
            snapshot,
            expected=started,
        ) is subject.ProposalAttemptCommitClassification.COMMITTED

    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM experiment_events")
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        assert owner._classify_started_event_from_snapshot(
            snapshot,
            expected=started,
        ) is subject.ProposalAttemptCommitClassification.EXPECTED

    _insert(
        path,
        started_payload,
        event_id="event-start",
        timestamp="2026-07-17T01:02:03.000004+00:00",
    )
    terminal_payload = _terminal_payload(started_payload, status="failed")
    _insert(
        path,
        terminal_payload,
        event_id="event-failed",
        timestamp="2026-07-17T01:02:04.000004+00:00",
    )
    terminal = _inventory(authority, owner).groups[0].events[1]
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        assert owner._classify_started_event_from_snapshot(
            snapshot,
            expected=started,
        ) is subject.ProposalAttemptCommitClassification.MIXED
        assert owner._classify_terminal_event_from_snapshot(
            snapshot,
            started=started,
            expected_terminal=terminal,
        ) is subject.ProposalAttemptCommitClassification.COMMITTED

    with sqlite3.connect(path) as connection:
        connection.execute(
            "DELETE FROM experiment_events WHERE event_id = 'event-failed'"
        )
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        assert owner._classify_terminal_event_from_snapshot(
            snapshot,
            started=started,
            expected_terminal=terminal,
        ) is subject.ProposalAttemptCommitClassification.EXPECTED

    other_started = _started_payload(attempt_id="attempt-2")
    _insert(
        path,
        other_started,
        event_id="event-other-start",
        timestamp="2026-07-17T01:02:05.000004+00:00",
    )
    with sqlite_connection._independent_authority_read_snapshot(authority) as snapshot:
        assert owner._classify_terminal_event_from_snapshot(
            snapshot,
            started=started,
            expected_terminal=terminal,
        ) is subject.ProposalAttemptCommitClassification.MIXED
