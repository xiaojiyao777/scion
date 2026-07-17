from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.durable_owner import (
    ActiveEvaluationLeaseConflict,
    DurableOwnerError,
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerNotFound,
    OwnerPayloadConflict,
    OwnerRevisionConflict,
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
    branch_storage_payload,
    hypothesis_storage_payload,
)


class _StringSubclass(str):
    pass


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="a" * 64,
        lineage_id="lineage-1",
        current_code_hash="b" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=1,
        validation_expand_count=2,
        failure_codes=["PRIOR_SAFE_FAILURE"],
        created_at=datetime(2026, 7, 17, 1, 2, 3),
        updated_at=datetime(2026, 7, 17, 1, 2, 4),
        direction="local_search: bounded destroy",
        weight_revision=3,
        branch_code_status="candidate_committed",
        branch_evidence_summary={
            "complete": True,
            "metrics": [1, 2.5, {"nested": "value"}],
            "optional": None,
        },
        infra_block_count=4,
    )


def _hypothesis() -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id="branch-1",
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/local_search.py",
        parent_hypothesis_id="hypothesis-0",
        suggested_weight=-0.0,
        hypothesis_text="Use a bounded destroy neighborhood.",
        created_at=datetime(2026, 7, 17, 1, 2, 5),
        base_champion_version=7,
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        predicted_direction="improve",
        proposal_digest="d" * 64,
    )


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_branch_token_retains_only_immutable_canonical_owner() -> None:
    source = _branch()
    token = RevisionedBranchRecord.from_value(source, owner_revision=11)
    canonical_before = token.canonical_payload_json
    digest_before = token.payload_sha256

    source.state = BranchState.ABANDONED
    source.failure_codes.append("MUTATED")
    source.branch_evidence_summary["metrics"][2]["nested"] = "mutated"

    restored = token.value()
    assert restored.state is BranchState.EXPLORE
    assert restored.failure_codes == ["PRIOR_SAFE_FAILURE"]
    assert restored.branch_evidence_summary["metrics"][2] == {"nested": "value"}
    assert token.canonical_payload_json is canonical_before
    assert token.payload_sha256 == digest_before == _digest(canonical_before)

    second = token.value()
    assert restored is not second
    assert restored.failure_codes is not second.failure_codes
    assert restored.branch_evidence_summary is not second.branch_evidence_summary
    restored.failure_codes.append("DETACHED")
    restored.branch_evidence_summary["metrics"][2]["nested"] = "detached"
    assert token.value().failure_codes == ["PRIOR_SAFE_FAILURE"]
    assert token.value().branch_evidence_summary["metrics"][2] == {
        "nested": "value"
    }

    with pytest.raises(FrozenInstanceError):
        token.owner_revision = 12  # type: ignore[misc]


def test_branch_projection_is_complete_and_excludes_storage_metadata() -> None:
    payload = branch_storage_payload(_branch())
    assert set(payload) == {
        "branch_id",
        "state",
        "base_champion_id",
        "base_champion_hash",
        "lineage_id",
        "current_code_hash",
        "last_clean_code_hash",
        "screening_expand_count",
        "validation_expand_count",
        "failure_codes",
        "created_at",
        "updated_at",
        "direction",
        "weight_revision",
        "branch_code_status",
        "branch_evidence_summary",
        "infra_block_count",
    }
    assert "owner_revision" not in payload
    assert "owner_protocol_generation" not in payload

    token_0 = RevisionedBranchRecord.from_value(_branch(), owner_revision=0)
    token_9 = RevisionedBranchRecord.from_value(_branch(), owner_revision=9)
    assert token_0.canonical_payload_json == token_9.canonical_payload_json
    assert token_0.payload_sha256 == token_9.payload_sha256


def test_hypothesis_token_includes_complete_storage_digest_and_detaches() -> None:
    source = _hypothesis()
    token = RevisionedHypothesisRecord.from_value(source, owner_revision=5)
    canonical_before = token.canonical_storage_payload_json
    digest_before = token.payload_sha256
    payload = json.loads(token.canonical_storage_payload_json)

    assert set(payload) == {
        "hypothesis_id",
        "branch_id",
        "change_locus",
        "action",
        "status",
        "target_file",
        "parent_hypothesis_id",
        "suggested_weight",
        "hypothesis_text",
        "created_at",
        "base_champion_version",
        "family_id",
        "family_source",
        "taxonomy_version",
        "predicted_direction",
        "proposal_digest",
    }
    assert payload["proposal_digest"] == "d" * 64
    assert payload["suggested_weight"] == 0.0
    assert "owner_revision" not in payload
    assert "owner_protocol_generation" not in payload

    source.status = "rejected"
    source.proposal_digest = "e" * 64
    restored = token.value()
    second = token.value()
    assert restored.status == "active"
    assert restored.proposal_digest == "d" * 64
    assert restored is not second
    restored.status = "advanced"
    restored.proposal_digest = None
    assert token.value().status == "active"
    assert token.value().proposal_digest == "d" * 64
    assert token.canonical_storage_payload_json is canonical_before
    assert token.payload_sha256 == digest_before == _digest(canonical_before)

    with pytest.raises(FrozenInstanceError):
        token.owner_revision = 6  # type: ignore[misc]


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda branch: setattr(
                branch,
                "branch_id",
                _StringSubclass("branch-1"),
            ),
            id="id",
        ),
        pytest.param(
            lambda branch: setattr(
                branch,
                "base_champion_hash",
                _StringSubclass("a" * 64),
            ),
            id="required-semantic",
        ),
        pytest.param(
            lambda branch: setattr(
                branch,
                "direction",
                _StringSubclass("local_search: bounded destroy"),
            ),
            id="optional-semantic",
        ),
        pytest.param(
            lambda branch: branch.failure_codes.__setitem__(
                0,
                _StringSubclass("PRIOR_SAFE_FAILURE"),
            ),
            id="list-item",
        ),
        pytest.param(
            lambda branch: setattr(
                branch,
                "branch_evidence_summary",
                {_StringSubclass("complete"): True},
            ),
            id="mapping-key",
        ),
        pytest.param(
            lambda branch: setattr(
                branch,
                "branch_evidence_summary",
                {"detail": _StringSubclass("value")},
            ),
            id="mapping-value",
        ),
    ],
)
def test_branch_projection_requires_exact_builtin_strings(mutate: object) -> None:
    branch = _branch()
    mutate(branch)  # type: ignore[operator]

    with pytest.raises(DurableOwnerIntegrityError):
        RevisionedBranchRecord.from_value(branch, owner_revision=0)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda hypothesis: setattr(
                hypothesis,
                "hypothesis_id",
                _StringSubclass("hypothesis-1"),
            ),
            id="id",
        ),
        pytest.param(
            lambda hypothesis: setattr(
                hypothesis,
                "action",
                _StringSubclass("modify"),
            ),
            id="required-semantic",
        ),
        pytest.param(
            lambda hypothesis: setattr(
                hypothesis,
                "target_file",
                _StringSubclass("operators/local_search.py"),
            ),
            id="optional-semantic",
        ),
        pytest.param(
            lambda hypothesis: setattr(
                hypothesis,
                "proposal_digest",
                _StringSubclass("d" * 64),
            ),
            id="semantic-digest",
        ),
    ],
)
def test_hypothesis_projection_requires_exact_builtin_strings(mutate: object) -> None:
    hypothesis = _hypothesis()
    mutate(hypothesis)  # type: ignore[operator]

    with pytest.raises(DurableOwnerIntegrityError):
        RevisionedHypothesisRecord.from_value(hypothesis, owner_revision=0)


def test_optional_legacy_empty_text_is_preserved_without_normalization() -> None:
    branch = _branch()
    branch.current_code_hash = ""
    branch.last_clean_code_hash = ""
    branch.direction = ""
    branch_token = RevisionedBranchRecord.from_value(branch, owner_revision=0)
    restored_branch = branch_token.value()
    assert restored_branch.current_code_hash == ""
    assert restored_branch.last_clean_code_hash == ""
    assert restored_branch.direction == ""

    hypothesis = _hypothesis()
    hypothesis.target_file = ""
    hypothesis.parent_hypothesis_id = ""
    hypothesis.hypothesis_text = ""
    hypothesis.family_id = ""
    hypothesis.family_source = ""
    hypothesis.taxonomy_version = ""
    hypothesis_token = RevisionedHypothesisRecord.from_value(
        hypothesis,
        owner_revision=0,
    )
    restored_hypothesis = hypothesis_token.value()
    assert restored_hypothesis.target_file == ""
    assert restored_hypothesis.parent_hypothesis_id == ""
    assert restored_hypothesis.hypothesis_text == ""
    assert restored_hypothesis.family_id == ""
    assert restored_hypothesis.family_source == ""
    assert restored_hypothesis.taxonomy_version == ""


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda branch: branch.branch_evidence_summary.update(
                {"invalid": float("nan")}
            ),
            "finite",
        ),
        (
            lambda branch: branch.branch_evidence_summary.update({1: "invalid"}),
            "keys must be strings",
        ),
        (
            lambda branch: branch.branch_evidence_summary.update(
                {"invalid": object()}
            ),
            "JSON primitive",
        ),
        (
            lambda branch: setattr(branch, "screening_expand_count", True),
            "SQLite integer",
        ),
    ],
)
def test_branch_projection_rejects_nonprimitive_or_nonfinite_values(
    mutate: object,
    message: str,
) -> None:
    branch = _branch()
    mutate(branch)  # type: ignore[operator]
    with pytest.raises(DurableOwnerIntegrityError, match=message):
        RevisionedBranchRecord.from_value(branch, owner_revision=0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("suggested_weight", float("inf"), "finite"),
        ("suggested_weight", True, "finite number"),
        ("proposal_digest", "not-a-digest", "lowercase full SHA-256"),
        ("base_champion_version", -1, "SQLite integer"),
        ("action", "rewrite", "action is invalid"),
    ],
)
def test_hypothesis_projection_rejects_invalid_semantic_values(
    field: str,
    value: object,
    message: str,
) -> None:
    hypothesis = _hypothesis()
    setattr(hypothesis, field, value)
    with pytest.raises(DurableOwnerIntegrityError, match=message):
        RevisionedHypothesisRecord.from_value(hypothesis, owner_revision=0)


def test_direct_token_construction_rejects_noncanonical_or_forged_bytes() -> None:
    valid = RevisionedBranchRecord.from_value(_branch(), owner_revision=2)
    payload = json.loads(valid.canonical_payload_json)

    unknown = dict(payload, owner_revision=2)
    unknown_bytes = _canonical(unknown)
    with pytest.raises(DurableOwnerIntegrityError, match="keys are invalid"):
        RevisionedBranchRecord(
            branch_id="branch-1",
            owner_revision=2,
            canonical_payload_json=unknown_bytes,
            payload_sha256=_digest(unknown_bytes),
        )

    noncanonical = json.dumps(payload, sort_keys=False).encode("utf-8")
    with pytest.raises(DurableOwnerIntegrityError, match="not canonical"):
        RevisionedBranchRecord(
            branch_id="branch-1",
            owner_revision=2,
            canonical_payload_json=noncanonical,
            payload_sha256=_digest(noncanonical),
        )

    with pytest.raises(DurableOwnerIntegrityError, match="does not match"):
        RevisionedBranchRecord(
            branch_id="branch-1",
            owner_revision=2,
            canonical_payload_json=valid.canonical_payload_json,
            payload_sha256="0" * 64,
        )

    with pytest.raises(DurableOwnerIntegrityError, match="token ID"):
        RevisionedBranchRecord(
            branch_id="branch-forged",
            owner_revision=2,
            canonical_payload_json=valid.canonical_payload_json,
            payload_sha256=valid.payload_sha256,
        )


def test_direct_token_metadata_requires_exact_builtin_strings() -> None:
    branch = RevisionedBranchRecord.from_value(_branch(), owner_revision=2)
    with pytest.raises(DurableOwnerIntegrityError, match="token ID"):
        RevisionedBranchRecord(
            branch_id=_StringSubclass(branch.branch_id),
            owner_revision=branch.owner_revision,
            canonical_payload_json=branch.canonical_payload_json,
            payload_sha256=branch.payload_sha256,
        )
    with pytest.raises(DurableOwnerIntegrityError, match="digest is invalid"):
        RevisionedBranchRecord(
            branch_id=branch.branch_id,
            owner_revision=branch.owner_revision,
            canonical_payload_json=branch.canonical_payload_json,
            payload_sha256=_StringSubclass(branch.payload_sha256),
        )

    hypothesis = RevisionedHypothesisRecord.from_value(
        _hypothesis(),
        owner_revision=2,
    )
    with pytest.raises(DurableOwnerIntegrityError, match="token ID"):
        RevisionedHypothesisRecord(
            hypothesis_id=_StringSubclass(hypothesis.hypothesis_id),
            owner_revision=hypothesis.owner_revision,
            canonical_storage_payload_json=(
                hypothesis.canonical_storage_payload_json
            ),
            payload_sha256=hypothesis.payload_sha256,
        )
    with pytest.raises(DurableOwnerIntegrityError, match="digest is invalid"):
        RevisionedHypothesisRecord(
            hypothesis_id=hypothesis.hypothesis_id,
            owner_revision=hypothesis.owner_revision,
            canonical_storage_payload_json=(
                hypothesis.canonical_storage_payload_json
            ),
            payload_sha256=_StringSubclass(hypothesis.payload_sha256),
        )


def test_direct_hypothesis_token_rejects_noncanonical_or_forged_bytes() -> None:
    valid = RevisionedHypothesisRecord.from_value(_hypothesis(), owner_revision=2)
    payload = json.loads(valid.canonical_storage_payload_json)

    unknown = dict(payload, owner_revision=2)
    unknown_bytes = _canonical(unknown)
    with pytest.raises(DurableOwnerIntegrityError, match="keys are invalid"):
        RevisionedHypothesisRecord(
            hypothesis_id="hypothesis-1",
            owner_revision=2,
            canonical_storage_payload_json=unknown_bytes,
            payload_sha256=_digest(unknown_bytes),
        )

    noncanonical = json.dumps(payload, sort_keys=False).encode("utf-8")
    with pytest.raises(DurableOwnerIntegrityError, match="not canonical"):
        RevisionedHypothesisRecord(
            hypothesis_id="hypothesis-1",
            owner_revision=2,
            canonical_storage_payload_json=noncanonical,
            payload_sha256=_digest(noncanonical),
        )

    with pytest.raises(DurableOwnerIntegrityError, match="does not match"):
        RevisionedHypothesisRecord(
            hypothesis_id="hypothesis-1",
            owner_revision=2,
            canonical_storage_payload_json=valid.canonical_storage_payload_json,
            payload_sha256="0" * 64,
        )

    with pytest.raises(DurableOwnerIntegrityError, match="token ID"):
        RevisionedHypothesisRecord(
            hypothesis_id="hypothesis-forged",
            owner_revision=2,
            canonical_storage_payload_json=valid.canonical_storage_payload_json,
            payload_sha256=valid.payload_sha256,
        )


def test_direct_hypothesis_token_rejects_noncanonical_storage_number() -> None:
    payload = hypothesis_storage_payload(_hypothesis())
    payload["suggested_weight"] = 1
    canonical = _canonical(payload)
    with pytest.raises(DurableOwnerIntegrityError, match="canonical storage form"):
        RevisionedHypothesisRecord(
            hypothesis_id="hypothesis-1",
            owner_revision=0,
            canonical_storage_payload_json=canonical,
            payload_sha256=_digest(canonical),
        )


def test_recursive_owner_values_raise_typed_integrity_error() -> None:
    branch = _branch()
    recursive: dict[str, object] = {}
    recursive["self"] = recursive
    branch.branch_evidence_summary = recursive

    with pytest.raises(
        DurableOwnerIntegrityError,
        match="recursively nested",
    ) as error:
        RevisionedBranchRecord.from_value(branch, owner_revision=0)
    assert isinstance(error.value.__cause__, RecursionError)

    deeply_nested_json = b"[" * 2048 + b"null" + b"]" * 2048
    with pytest.raises(DurableOwnerIntegrityError, match="canonical payload"):
        RevisionedBranchRecord(
            branch_id="branch-1",
            owner_revision=0,
            canonical_payload_json=deeply_nested_json,
            payload_sha256=_digest(deeply_nested_json),
        )


@pytest.mark.parametrize(
    ("weight", "expected_weight", "sqlite_type"),
    [
        (None, None, "null"),
        (-0.0, 0.0, "real"),
        (1, 1.0, "real"),
        (0.25, 0.25, "real"),
    ],
)
def test_hypothesis_real_and_datetime_are_stable_across_sqlite_roundtrip(
    weight: object,
    expected_weight: float | None,
    sqlite_type: str,
) -> None:
    source = _hypothesis()
    source.suggested_weight = weight  # type: ignore[assignment]
    source.created_at = datetime(
        2026,
        7,
        17,
        1,
        2,
        5,
        123456,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )
    before = RevisionedHypothesisRecord.from_value(source, owner_revision=3)
    payload = json.loads(before.canonical_storage_payload_json)

    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE owner_roundtrip (suggested_weight REAL, created_at TEXT)"
        )
        connection.execute(
            "INSERT INTO owner_roundtrip VALUES (?, ?)",
            (payload["suggested_weight"], payload["created_at"]),
        )
        row = connection.execute(
            "SELECT suggested_weight, typeof(suggested_weight), "
            "created_at, typeof(created_at) FROM owner_roundtrip"
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == expected_weight
    assert row[1] == sqlite_type
    assert type(row[2]) is str
    assert row[3] == "text"

    restored = _hypothesis()
    restored.suggested_weight = row[0]
    restored.created_at = datetime.fromisoformat(row[2])
    after = RevisionedHypothesisRecord.from_value(restored, owner_revision=3)
    assert after.canonical_storage_payload_json == before.canonical_storage_payload_json
    assert after.payload_sha256 == before.payload_sha256


@pytest.mark.parametrize("revision", [-1, True, 1 << 63])
def test_revision_must_be_a_nonnegative_sqlite_integer(revision: object) -> None:
    with pytest.raises(DurableOwnerIntegrityError, match="owner revision"):
        RevisionedBranchRecord.from_value(
            _branch(),
            owner_revision=revision,  # type: ignore[arg-type]
        )


def test_owner_errors_are_distinct_typed_protocol_errors() -> None:
    errors = (
        OwnerNotFound,
        OwnerAlreadyExists,
        OwnerRevisionConflict,
        ActiveEvaluationLeaseConflict,
        OwnerPayloadConflict,
        DurableOwnerIntegrityError,
    )
    assert len(set(errors)) == len(errors)
    assert all(issubclass(error, DurableOwnerError) for error in errors)
