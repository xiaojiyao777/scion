from __future__ import annotations

import ast
import contextvars
import copy
import hashlib
import json
import pickle
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scion.lineage import proposal_attempt_owner as subject
from scion.lineage import sqlite_connection as sqlite_boundary


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


def _started_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "attempt-start-1",
        "campaign_id": "test-campaign",
        "branch_id": "branch-start-1",
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
            "context_digest": "context-start-1",
            "prompt_hash": "prompt-start-1",
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
            "champion_version": 5,
            "champion_weight_revision": 2,
            "champion_code_snapshot_hash": "champion-code-hash",
            "branch_base_champion_id": 5,
            "branch_base_champion_hash": "branch-champion-hash",
        },
        "tainted_artifact_refs": [],
    }
    payload.update(updates)
    return payload


def _harness(
    tmp_path: Path,
    *,
    campaign_id: str = "test-campaign",
) -> tuple[
    Path,
    sqlite_boundary.CampaignDatabaseAuthority,
    subject.ProposalAttemptOwner,
]:
    path = tmp_path / "proposal-attempt-owner.db"
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        _create_schema(connection)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(
        path,
        campaign_id=campaign_id,
    )
    return path, authority, subject.ProposalAttemptOwner(authority)


def _issue(
    tmp_path: Path,
) -> tuple[
    Path,
    sqlite_boundary.CampaignDatabaseAuthority,
    subject.StartedHypothesisAttempt,
]:
    path, authority, owner = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(authority) as transaction:
        started = owner.append_started_hypothesis_attempt_in(
            transaction,
            _started_payload(),
        )
    return path, authority, started


def _bind(
    authority: sqlite_boundary.CampaignDatabaseAuthority,
    started: subject.StartedHypothesisAttempt,
) -> subject._StartedHypothesisProviderBinding:
    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        return subject._bind_started_hypothesis_attempt_to_provider(
            started,
            snapshot,
        )


def test_append_exact_reread_and_provider_binding_derive_frozen_persisted_facts(
    tmp_path: Path,
) -> None:
    path, authority, started = _issue(tmp_path)

    connection = sqlite3.connect(path)
    try:
        row = connection.execute("""
            SELECT event_id,
                   campaign_id,
                   branch_id,
                   hypothesis_id,
                   timestamp,
                   event_kind,
                   stage,
                   audit_payload_json
            FROM experiment_events
            """).fetchone()
    finally:
        connection.close()
    assert row is not None
    payload = _started_payload()
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert row[1:4] == ("test-campaign", "branch-start-1", None)
    assert row[5:7] == ("proposal_attempt_transition", "proposal_hypothesis")
    assert row[7] == canonical.decode("utf-8")

    binding = _bind(authority, started)

    assert binding.attempt_id == payload["attempt_id"]
    assert binding.started_event_id == row[0]
    assert binding.campaign_id == payload["campaign_id"]
    assert binding.branch_id == payload["branch_id"]
    assert binding.context_digest == payload["prompt_call"]["context_digest"]
    assert binding.prompt_hash == payload["prompt_call"]["prompt_hash"]
    assert binding.canonical_payload_json == canonical
    assert binding.payload_sha256 == hashlib.sha256(canonical).hexdigest()
    assert dict(binding.attempt_audit) == {
        "schema_version": "provider-call-attempt-audit.v1",
        "attempt_id": "attempt-start-1",
        "phase": "hypothesis",
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "hypothesis_attempt_id": "attempt-start-1",
        "started_lineage_event_id": row[0],
    }
    with pytest.raises(TypeError):
        binding.attempt_audit["attempt_id"] = "replacement"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        binding.attempt_id = "replacement"  # type: ignore[misc]


def test_start_capability_is_exact_sealed_noncopyable_and_one_shot(
    tmp_path: Path,
) -> None:
    _, authority, started = _issue(tmp_path)

    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        subject.StartedHypothesisAttempt()
    with pytest.raises(TypeError):

        class _Subclass(subject.StartedHypothesisAttempt):
            pass

    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        copy.copy(started)
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        copy.deepcopy(started)
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
        pickle.dumps(started)

    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        forged = object.__new__(subject.StartedHypothesisAttempt)
        with pytest.raises(
            subject.InvalidStartedHypothesisAttemptError,
            match="was not issued",
        ):
            subject._bind_started_hypothesis_attempt_to_provider(forged, snapshot)
        with pytest.raises(subject.InvalidStartedHypothesisAttemptError):
            subject._bind_started_hypothesis_attempt_to_provider(
                object(),  # type: ignore[arg-type]
                snapshot,
            )

        subject._bind_started_hypothesis_attempt_to_provider(started, snapshot)
        with pytest.raises(
            subject.StartedHypothesisAttemptLifecycleError,
            match="already provider-bound",
        ):
            subject._bind_started_hypothesis_attempt_to_provider(started, snapshot)


def test_start_capability_rejects_cross_thread_and_copied_context_before_claim(
    tmp_path: Path,
) -> None:
    _, authority, started = _issue(tmp_path)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            subject._bind_started_hypothesis_attempt_to_provider,
            started,
            object(),
        )
        with pytest.raises(
            subject.StartedHypothesisAttemptLifecycleError,
            match="cross threads",
        ):
            future.result()

    copied = contextvars.copy_context()
    with pytest.raises(
        subject.StartedHypothesisAttemptLifecycleError,
        match="cross Contexts",
    ):
        copied.run(
            subject._bind_started_hypothesis_attempt_to_provider,
            started,
            object(),
        )

    binding = _bind(authority, started)
    assert binding.attempt_id == "attempt-start-1"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"campaign_id": "another-campaign"}, "another campaign"),
        ({"phase": "code"}, "hypothesis phase"),
        ({"status": "generated"}, "started status"),
        ({"attempt_kind": "approved_code_continuation"}, "initial attempt kind"),
        ({"continuation_of_attempt_id": "attempt-old"}, "cannot be a continuation"),
        ({"attempt_id": " attempt-start-1"}, "exact attempt_id"),
    ],
)
def test_owner_rejects_wrong_start_identity_before_insert(
    tmp_path: Path,
    updates: dict[str, object],
    message: str,
) -> None:
    path, authority, owner = _harness(tmp_path)

    with pytest.raises(subject.InvalidStartedHypothesisAttemptError, match=message):
        with sqlite_boundary.immediate_transaction(authority) as transaction:
            owner.append_started_hypothesis_attempt_in(
                transaction,
                _started_payload(**updates),
            )

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM experiment_events"
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_owner_requires_exact_dict_shapes_and_active_matching_transaction(
    tmp_path: Path,
) -> None:
    path, authority, owner = _harness(tmp_path)
    other_path = tmp_path / "other-campaign.db"
    other_connection = sqlite_boundary._connect_sqlite(other_path)
    try:
        _create_schema(other_connection)
        other_connection.commit()
    finally:
        other_connection.close()
    other_authority = sqlite_boundary._issue_test_campaign_database_authority(
        other_path,
    )

    with sqlite_boundary.immediate_transaction(other_authority) as transaction:
        with pytest.raises(sqlite_boundary.InvalidImmediateTransactionError):
            owner.append_started_hypothesis_attempt_in(
                transaction,
                _started_payload(),
            )

    payload = _started_payload()
    payload["prompt_call"] = dict(payload["prompt_call"])
    with sqlite_boundary.immediate_transaction(authority) as transaction:
        started = owner.append_started_hypothesis_attempt_in(transaction, payload)
    with pytest.raises(sqlite_boundary.InactiveImmediateTransactionError):
        owner.append_started_hypothesis_attempt_in(transaction, _started_payload())
    assert type(started) is subject.StartedHypothesisAttempt
    assert path.exists()


def test_strict_reread_rejects_trigger_rewriting_fixed_storage(tmp_path: Path) -> None:
    path, authority, owner = _harness(tmp_path)
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TRIGGER rewrite_started_stage
            AFTER INSERT ON experiment_events
            BEGIN
                UPDATE experiment_events
                SET stage = 'rewritten-stage'
                WHERE event_id = NEW.event_id;
            END;
            """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        subject.InvalidStartedHypothesisAttemptError,
        match="post-write storage differs: stage",
    ):
        with sqlite_boundary.immediate_transaction(authority) as transaction:
            owner.append_started_hypothesis_attempt_in(
                transaction,
                _started_payload(),
            )

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM experiment_events"
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_rolled_back_start_cannot_bind_or_be_retried(tmp_path: Path) -> None:
    path, authority, owner = _harness(tmp_path)
    started: subject.StartedHypothesisAttempt | None = None

    with pytest.raises(RuntimeError, match="force rollback"):
        with sqlite_boundary.immediate_transaction(authority) as transaction:
            started = owner.append_started_hypothesis_attempt_in(
                transaction,
                _started_payload(),
            )
            raise RuntimeError("force rollback")
    assert started is not None
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM experiment_events"
        ).fetchone() == (0,)
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        with pytest.raises(
            subject.InvalidStartedHypothesisAttemptError,
            match="not durably committed",
        ):
            subject._bind_started_hypothesis_attempt_to_provider(started, snapshot)
    with pytest.raises(
        subject.StartedHypothesisAttemptLifecycleError,
        match="already provider-bound",
    ):
        subject._bind_started_hypothesis_attempt_to_provider(
            started,
            object(),  # type: ignore[arg-type]
        )


def test_post_commit_event_replacement_cannot_bind(tmp_path: Path) -> None:
    path, authority, started = _issue(tmp_path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE experiment_events SET stage = ?",
            ("replacement-stage",),
        )
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        with pytest.raises(
            subject.InvalidStartedHypothesisAttemptError,
            match="event differs: stage",
        ):
            subject._bind_started_hypothesis_attempt_to_provider(started, snapshot)


def test_module_has_no_schema_or_transaction_lifecycle_and_one_provider_binder() -> (
    None
):
    source_path = Path(subject.__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "CREATE TABLE" not in source.upper()
    assert "ALTER TABLE" not in source.upper()
    forbidden_calls = {"connect", "commit", "rollback", "close"}
    assert not {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
    }

    package_root = source_path.parents[1]
    production_importers: list[Path] = []
    binding_callers: list[Path] = []
    dormant_entrypoints = {
        "ProposalAttemptOwner",
        "append_started_hypothesis_attempt_in",
        "_issue_provider_generation_permit",
        "_generate_hypothesis_result_with_receipt",
        "_consume_generated_hypothesis_result",
    }
    dormant_callers: dict[str, list[Path]] = {name: [] for name in dormant_entrypoints}
    for candidate in package_root.rglob("*.py"):
        if candidate == source_path or "tests" in candidate.parts:
            continue
        candidate_tree = ast.parse(candidate.read_text(encoding="utf-8"))
        for node in ast.walk(candidate_tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == "scion.lineage.proposal_attempt_owner"
                or (
                    node.module == "scion.lineage"
                    and any(
                        alias.name == "proposal_attempt_owner" for alias in node.names
                    )
                )
            ):
                production_importers.append(candidate)
            if isinstance(node, ast.Import) and any(
                alias.name == "scion.lineage.proposal_attempt_owner"
                for alias in node.names
            ):
                production_importers.append(candidate)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_bind_started_hypothesis_attempt_to_provider"
            ):
                binding_callers.append(candidate)
            if isinstance(node, ast.Call):
                call_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (
                        node.func.attr if isinstance(node.func, ast.Attribute) else None
                    )
                )
                if call_name in dormant_callers:
                    dormant_callers[call_name].append(candidate)
    provider_path = package_root / "proposal" / "engine" / "provider_call.py"
    assert production_importers == [provider_path]
    assert binding_callers == [provider_path]
    assert dormant_callers == {name: [] for name in dormant_entrypoints}
