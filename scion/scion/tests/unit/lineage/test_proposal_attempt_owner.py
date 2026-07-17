from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from scion.lineage import proposal_attempt_owner as subject
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.proposal import hypothesis_generation_authority as generation


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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


def _owner_context(*, campaign_id: str = "test-campaign") -> bytes:
    return _canonical(
        {
            "schema_version": "hypothesis-owner-context-projection.v1",
            "campaign_id": campaign_id,
            "runtime_mode": "direct_v3",
            "root_generation": 3,
            "branch": {
                "branch_id": "branch-a",
                "owner_revision": 7,
                "storage_sha256": _digest("branch-storage"),
                "state": "explore",
                "branch_code_status": "clean",
                "current_code_hash": None,
                "last_clean_code_hash": None,
                "base_champion_id": 5,
                "base_champion_hash": _digest("base-champion"),
                "base_champion_weight_revision": 2,
            },
            "h_bundle": {
                "digest": _digest("empty-h-bundle"),
                "count": 0,
                "items": [],
            },
            "prior_head": None,
            "anchors": {
                "problem_id": "cvrp",
                "problem_spec_hash": _digest("problem-spec"),
                "split_manifest_hash": _digest("split-manifest"),
                "seed_ledger_hash": _digest("seed-ledger"),
                "champion_version": 5,
                "champion_weight_revision": 2,
                "champion_code_snapshot_hash": _digest("champion-snapshot"),
                "branch_base_champion_id": 5,
                "branch_base_champion_hash": _digest("base-champion"),
            },
        }
    )


@dataclass(frozen=True)
class _Path:
    database_path: Path
    database_authority: sqlite_boundary.CampaignDatabaseAuthority
    owner: subject.ProposalAttemptOwner
    authorities: generation._CheckpointAAuthorities
    view: generation.HypothesisGenerationView
    prompt: generation.BoundHypothesisPrompt


_OWNER_KEEPALIVE: list[tuple[object, ...]] = []


def _prompt_path(tmp_path: Path, *, owner_context: bytes | None = None) -> _Path:
    database_path = tmp_path / "proposal-attempt-owner.db"
    connection = sqlite_boundary._connect_sqlite(database_path)
    try:
        _create_schema(connection)
        connection.commit()
    finally:
        connection.close()
    database_authority = sqlite_boundary._issue_test_campaign_database_authority(
        database_path,
        campaign_id="test-campaign",
    )
    owner = subject.ProposalAttemptOwner(database_authority)
    others = tuple(object() for _ in range(5))
    registry, code_owner, context_manager, prompt_owner, provider = others
    _OWNER_KEEPALIVE.append((owner, *others))
    authorities = generation._install_checkpoint_a_authorities(
        registry=registry,
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=owner,
        provider=provider,
    )
    owner._install_hypothesis_generation_authority(authorities.proposal_owner)
    owner_bytes = owner_context or _owner_context()
    view = generation._issue_generation_view(
        authorities.registry,
        root_identity=object(),
        root_generation=3,
        branch_owner=object(),
        hypothesis_bundle=(),
        prior_head=None,
        reservation_id="reservation-a",
        h_bundle_digest=_digest("empty-h-bundle"),
        owner_context_json=owner_bytes,
    )
    request = generation._issue_code_source_request(authorities.registry, view)
    generation._claim_code_source_request(authorities.code_source_owner, request)
    source = generation._issue_code_source(
        authorities.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_digest("selected-manifest"),
        code_hash=_digest("base-champion"),
        snapshot_hash=_digest("source-snapshot"),
        entries=(),
    )
    generation._inspect_code_source(authorities.registry, source, view=view)
    generation._claim_code_source_for_evidence(authorities.context_manager, source)
    evidence = generation._issue_problem_evidence(
        authorities.context_manager,
        source,
        provider_context_json=b'{"problem":"cvrp"}',
        governance_json=b'{"protocol":"direct-v3"}',
    )
    prompt_source = generation._issue_prompt_source(
        authorities.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )
    generation._claim_prompt_source(authorities.prompt_owner, prompt_source)
    prompt = generation._issue_bound_prompt(
        authorities.prompt_owner,
        prompt_source,
        context_snapshot=object(),
        provider_context_json=b'{"problem":"cvrp"}',
        provider_snapshot_bytes=b'{"prompt":"bound"}',
        context_digest=_digest("context"),
        prompt_hash=_digest("prompt"),
        provider_tool_digest=_digest("provider-tool"),
        governance_digest=hashlib.sha256(
            b'{"schema_version":"proposal-governance-envelope.v1","governance":{}}'
        ).hexdigest(),
        c0_governance_json=b"{}",
    )
    generation._inspect_bound_prompt(authorities.registry, prompt, view=view)
    generation._begin_started_attempt(authorities.registry, view, prompt)
    return _Path(
        database_path=database_path,
        database_authority=database_authority,
        owner=owner,
        authorities=authorities,
        view=view,
        prompt=prompt,
    )


def _commit_start(
    path: _Path,
    *,
    inspect_committed: bool = False,
) -> tuple[
    subject.StoredProposalAttemptEvent,
    subject.StartedHypothesisAttempt,
]:
    with sqlite_boundary.immediate_transaction(path.database_authority) as transaction:
        stored = path.owner.append_started_hypothesis_attempt_in(
            transaction,
            path.prompt,
        )
    with sqlite_boundary._independent_authority_read_snapshot(
        path.database_authority
    ) as snapshot:
        classification, started = path.owner._classify_started_attempt_from_snapshot(
            snapshot,
            expected=stored,
        )
    assert classification is subject.ProposalAttemptCommitClassification.COMMITTED
    assert type(started) is subject.StartedHypothesisAttempt
    if inspect_committed:
        generation._inspect_started_attempt(
            path.authorities.registry,
            started,
            view=path.view,
        )
    return stored, started


def test_start_uses_only_leaf_owner_projection_and_issues_after_commit(
    tmp_path: Path,
) -> None:
    path = _prompt_path(tmp_path)
    stored, started = _commit_start(path)

    assert stored.campaign_id == "test-campaign"
    assert stored.branch_id == "branch-a"
    assert stored.status == "started"
    assert len(stored.storage_sha256) == 64
    projection = generation._inspect_started_attempt(
        path.authorities.registry,
        started,
        view=path.view,
    )
    assert projection.stored_event is stored
    assert projection.event_storage_sha256 == stored.storage_sha256


def test_rolled_back_start_classifies_expected_without_start_authority(
    tmp_path: Path,
) -> None:
    path = _prompt_path(tmp_path)
    stored: subject.StoredProposalAttemptEvent | None = None
    with pytest.raises(RuntimeError, match="rollback"):
        with sqlite_boundary.immediate_transaction(path.database_authority) as transaction:
            stored = path.owner.append_started_hypothesis_attempt_in(
                transaction,
                path.prompt,
            )
            raise RuntimeError("rollback")
    assert stored is not None
    with sqlite_boundary._independent_authority_read_snapshot(
        path.database_authority
    ) as snapshot:
        classification, started = path.owner._classify_started_attempt_from_snapshot(
            snapshot,
            expected=stored,
        )
    assert classification is subject.ProposalAttemptCommitClassification.EXPECTED
    assert started is None


def test_owner_context_is_strict_and_caller_mapping_api_is_gone(tmp_path: Path) -> None:
    decoded = json.loads(_owner_context())
    decoded["campaign_id"] = "other-campaign"
    path = _prompt_path(tmp_path, owner_context=_canonical(decoded))
    with pytest.raises(subject.InvalidStartedHypothesisAttemptError, match="another campaign"):
        with sqlite_boundary.immediate_transaction(path.database_authority) as transaction:
            path.owner.append_started_hypothesis_attempt_in(transaction, path.prompt)
    connection = sqlite3.connect(path.database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM experiment_events").fetchone() == (
            0,
        )
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("kind", "category", "provider_ok", "expected_status", "expected_reason"),
    [
        ("provider_failure", "provider_call_failed", False, "failed", "provider_call_failed"),
        (
            "provider_interruption",
            "provider_call_interrupted",
            False,
            "interrupted",
            "provider_call_interrupted",
        ),
        (
            "invalid_response",
            "response_parse_failed",
            True,
            "failed",
            "proposal_response_invalid",
        ),
    ],
)
def test_provider_terminal_rebuild_commit_and_receipt(
    tmp_path: Path,
    kind: str,
    category: str,
    provider_ok: bool,
    expected_status: str,
    expected_reason: str,
) -> None:
    path = _prompt_path(tmp_path)
    _, started = _commit_start(path, inspect_committed=True)
    permit = generation._issue_provider_permit(
        path.authorities.registry,
        path.authorities.provider,
        view=path.view,
        started_attempt=started,
        bound_prompt=path.prompt,
    )
    generation._claim_provider_permit(path.authorities.provider, permit, path.prompt)
    raw_ref = None if kind == "provider_interruption" else "artifact://trace-a#/response"
    failure = generation._issue_failed_generation(
        path.authorities.provider,
        permit,
        kind=kind,
        receipt=object(),
        trace_ref="artifact://trace-a",
        prompt_manifest_ref="artifact://trace-a#/prompt_manifest",
        raw_response_ref=raw_ref,
        provider_ok=provider_ok,
        ok=False,
        failure_category=category,
        failure_type="RuntimeError",
        trace_persistence_error=None,
    )
    generation._inspect_generation_outcome(
        path.authorities.registry,
        permit=permit,
        outcome=failure,
        view=path.view,
    )
    generation._begin_terminal_persistence(
        path.authorities.registry,
        path.view,
        failure,
    )
    with sqlite_boundary.immediate_transaction(path.database_authority) as transaction:
        path.owner.append_terminal_hypothesis_attempt_in(
            transaction,
            started=started,
            bound_prompt=path.prompt,
            outcome=failure,
        )
    with sqlite_boundary._independent_authority_read_snapshot(
        path.database_authority
    ) as snapshot:
        classification, receipt = path.owner._classify_terminal_attempt_from_snapshot(
            snapshot,
            outcome=failure,
        )
    assert classification is subject.ProposalAttemptCommitClassification.COMMITTED
    assert type(receipt) is subject.TerminalAttemptReceipt
    connection = sqlite3.connect(path.database_path)
    try:
        payloads = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT audit_payload_json FROM experiment_events ORDER BY timestamp"
            )
        ]
    finally:
        connection.close()
    assert payloads[-1]["status"] == expected_status
    assert payloads[-1]["transition_reason"] == expected_reason
    assert payloads[-1]["attempt_id"] == payloads[0]["attempt_id"]
    assert payloads[-1]["anchors"] == payloads[0]["anchors"]


def test_explicit_abort_terminal_and_terminal_rollback_classification(
    tmp_path: Path,
) -> None:
    path = _prompt_path(tmp_path)
    _, started = _commit_start(path, inspect_committed=True)
    abort = generation._issue_aborted_generation(
        path.authorities.registry,
        started_attempt=started,
        bound_prompt=path.prompt,
        view=path.view,
    )
    generation._begin_terminal_persistence(path.authorities.registry, path.view, abort)
    with pytest.raises(RuntimeError, match="rollback"):
        with sqlite_boundary.immediate_transaction(path.database_authority) as transaction:
            path.owner.append_terminal_hypothesis_attempt_in(
                transaction,
                started=started,
                bound_prompt=path.prompt,
                outcome=abort,
            )
            raise RuntimeError("rollback")
    with sqlite_boundary._independent_authority_read_snapshot(
        path.database_authority
    ) as snapshot:
        classification, receipt = path.owner._classify_terminal_attempt_from_snapshot(
            snapshot,
            outcome=abort,
        )
    assert classification is subject.ProposalAttemptCommitClassification.EXPECTED
    assert receipt is None


def test_module_keeps_semantic_boundaries_and_has_no_old_provider_binder() -> None:
    source_path = Path(subject.__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "CREATE TABLE" not in source.upper()
    assert "ALTER TABLE" not in source.upper()
    assert "_bind_started_hypothesis_attempt_to_provider" not in source
    assert "provider_call" not in {
        alias.name.rsplit(".", 1)[-1]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"connect", "commit", "rollback", "close"}
    }
