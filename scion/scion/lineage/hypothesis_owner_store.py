"""Dormant, focused persistence for revisioned hypothesis owners.

This module owns the complete hypothesis row projection and the only SQL used
by the focused store.  Transaction authorization, one-shot write permits, and
receipt accounting remain in :mod:`scion.lineage.owner_transaction`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from scion.core.models import HypothesisRecord
from scion.lineage import owner_transaction as _owner
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerNotFound,
    OwnerPayloadConflict,
    OwnerRevisionConflict,
    RevisionedHypothesisRecord,
    hypothesis_storage_payload,
)

__all__ = ("HypothesisStore",)

_OWNER_PROTOCOL_GENERATION: Final[str] = "durable-owner.v1"

_HYPOTHESIS_COLUMNS: Final[tuple[str, ...]] = (
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
    "owner_revision",
    "owner_protocol_generation",
)

_HYPOTHESIS_SELECT_SQL: Final[str] = """
SELECT hypothesis_id,
       branch_id,
       change_locus,
       action,
       status,
       target_file,
       parent_hypothesis_id,
       suggested_weight,
       hypothesis_text,
       created_at,
       base_champion_version,
       family_id,
       family_source,
       taxonomy_version,
       predicted_direction,
       proposal_digest,
       owner_revision,
       owner_protocol_generation
FROM hypotheses
WHERE hypothesis_id = :hypothesis_id
"""

_HYPOTHESIS_INSERT_SQL: Final[str] = """
INSERT INTO hypotheses (
    hypothesis_id,
    branch_id,
    change_locus,
    action,
    status,
    target_file,
    parent_hypothesis_id,
    suggested_weight,
    hypothesis_text,
    created_at,
    base_champion_version,
    family_id,
    family_source,
    taxonomy_version,
    predicted_direction,
    proposal_digest,
    owner_revision,
    owner_protocol_generation
) VALUES (
    :hypothesis_id,
    :branch_id,
    :change_locus,
    :action,
    :status,
    :target_file,
    :parent_hypothesis_id,
    :suggested_weight,
    :hypothesis_text,
    :created_at,
    :base_champion_version,
    :family_id,
    :family_source,
    :taxonomy_version,
    :predicted_direction,
    :proposal_digest,
    :owner_revision,
    :owner_protocol_generation
)
"""

_HYPOTHESIS_CAS_SQL: Final[str] = """
UPDATE hypotheses
SET change_locus = :change_locus,
    action = :action,
    status = :status,
    target_file = :target_file,
    parent_hypothesis_id = :parent_hypothesis_id,
    suggested_weight = :suggested_weight,
    hypothesis_text = :hypothesis_text,
    created_at = :created_at,
    base_champion_version = :base_champion_version,
    family_id = :family_id,
    family_source = :family_source,
    taxonomy_version = :taxonomy_version,
    predicted_direction = :predicted_direction,
    proposal_digest = :proposal_digest,
    owner_revision = :target_revision
WHERE hypothesis_id = :hypothesis_id
  AND branch_id = :branch_id
  AND owner_revision = :expected_revision
  AND owner_protocol_generation = :owner_protocol_generation
"""


class HypothesisStore:
    """Connection-scoped participant for one Campaign's hypothesis owners."""

    __slots__ = ("__database_authority", "__store_authority")

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        self.__store_authority = _owner._issue_hypothesis_store_authority(
            database_authority
        )
        self.__database_authority = database_authority

    def load_revisioned_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord | None:
        """Read and strictly decode one owner inside an active transaction."""

        _sqlite.require_active_immediate_transaction(
            transaction,
            self.__database_authority,
        )
        owner_id = _validate_hypothesis_id(hypothesis_id)
        return self._read_optional_in(transaction, owner_id)

    def compare_and_swap_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        expected: RevisionedHypothesisRecord,
        target: HypothesisRecord,
    ) -> _owner.OwnerMutationReceipt:
        """Replace one exact expected owner and return its sealed write receipt."""

        if type(expected) is not RevisionedHypothesisRecord:
            raise DurableOwnerIntegrityError(
                "expected must be an exact RevisionedHypothesisRecord"
            )
        if type(target) is not HypothesisRecord:
            raise DurableOwnerIntegrityError(
                "target must be an exact HypothesisRecord"
            )
        ledger = _owner._require_hypothesis_store_ledger(
            transaction,
            self.__store_authority,
        )
        if target.hypothesis_id != expected.hypothesis_id:
            raise OwnerPayloadConflict("hypothesis owner identity cannot change")
        expected_value = expected.value()
        if target.branch_id != expected_value.branch_id:
            raise OwnerPayloadConflict(
                "a hypothesis owner cannot move between Branches"
            )
        target_token = RevisionedHypothesisRecord.from_value(
            target,
            owner_revision=expected.owner_revision + 1,
        )
        current = self._read_required_in(transaction, expected.hypothesis_id)
        _require_exact_expected(current, expected)
        if (
            target_token.canonical_storage_payload_json
            == expected.canonical_storage_payload_json
        ):
            raise OwnerPayloadConflict(
                "hypothesis mutation must change its semantic payload"
            )

        parameters = _write_parameters(target_token)
        parameters["expected_revision"] = expected.owner_revision
        parameters["target_revision"] = target_token.owner_revision
        result, write_fact = _owner._execute_hypothesis_owner_update(
            self.__store_authority,
            ledger,
            expected,
            _HYPOTHESIS_CAS_SQL,
            parameters,
        )
        if result.rowcount != 1:
            self._raise_cas_failure(transaction, expected)

        committed = self._read_required_in(transaction, expected.hypothesis_id)
        _require_exact_committed(committed, target_token)
        return _owner._issue_hypothesis_mutation_receipt(
            self.__store_authority,
            ledger,
            write_fact,
            committed,
        )

    def insert_once_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis: HypothesisRecord,
    ) -> _owner.OwnerCreationReceipt:
        """Create one revision-zero owner without replacement semantics."""

        if type(hypothesis) is not HypothesisRecord:
            raise DurableOwnerIntegrityError(
                "hypothesis must be an exact HypothesisRecord"
            )
        ledger = _owner._require_hypothesis_store_ledger(
            transaction,
            self.__store_authority,
        )
        target_token = RevisionedHypothesisRecord.from_value(
            hypothesis,
            owner_revision=0,
        )
        if (
            self._read_optional_in(transaction, target_token.hypothesis_id)
            is not None
        ):
            raise OwnerAlreadyExists(
                f"hypothesis owner already exists: {target_token.hypothesis_id}"
            )

        result, write_fact = _owner._execute_hypothesis_owner_insert(
            self.__store_authority,
            ledger,
            target_token.hypothesis_id,
            _HYPOTHESIS_INSERT_SQL,
            _write_parameters(target_token),
        )
        if result.rowcount != 1:
            self._raise_insert_failure(transaction, target_token.hypothesis_id)

        committed = self._read_required_in(transaction, target_token.hypothesis_id)
        _require_exact_committed(committed, target_token)
        return _owner._issue_hypothesis_creation_receipt(
            self.__store_authority,
            ledger,
            write_fact,
            committed,
        )

    def _read_optional_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord | None:
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _HYPOTHESIS_SELECT_SQL,
            {"hypothesis_id": hypothesis_id},
        )
        rows = result.fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise DurableOwnerIntegrityError(
                "hypothesis owner query returned duplicate rows"
            )
        token = _decode_hypothesis_row(rows[0])
        if token.hypothesis_id != hypothesis_id:
            raise DurableOwnerIntegrityError(
                "hypothesis owner query returned another owner identity"
            )
        return token

    def _read_required_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord:
        token = self._read_optional_in(transaction, hypothesis_id)
        if token is None:
            raise OwnerNotFound(f"hypothesis owner does not exist: {hypothesis_id}")
        return token

    def _raise_cas_failure(
        self,
        transaction: _sqlite.ImmediateTransaction,
        expected: RevisionedHypothesisRecord,
    ) -> None:
        current = self._read_optional_in(transaction, expected.hypothesis_id)
        if current is None:
            raise OwnerNotFound(
                f"hypothesis owner does not exist: {expected.hypothesis_id}"
            )
        _require_exact_expected(current, expected)
        raise DurableOwnerIntegrityError(
            "hypothesis CAS changed zero rows despite an exact current owner"
        )

    def _raise_insert_failure(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis_id: str,
    ) -> None:
        if self._read_optional_in(transaction, hypothesis_id) is not None:
            raise OwnerAlreadyExists(
                f"hypothesis owner already exists: {hypothesis_id}"
            )
        raise DurableOwnerIntegrityError(
            "hypothesis insert changed zero rows without creating its owner"
        )


def _validate_hypothesis_id(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(
            "hypothesis ID must be a non-empty exact string"
        )
    return value


def _decode_hypothesis_row(row: Any) -> RevisionedHypothesisRecord:
    try:
        keys = tuple(row.keys())
    except (AttributeError, TypeError) as exc:
        raise DurableOwnerIntegrityError(
            "hypothesis owner row is not a named SQLite row"
        ) from exc
    if keys != _HYPOTHESIS_COLUMNS:
        raise DurableOwnerIntegrityError(
            "hypothesis owner row has incomplete or unexpected columns"
        )
    raw = {column: row[column] for column in _HYPOTHESIS_COLUMNS}
    if raw["owner_protocol_generation"] != _OWNER_PROTOCOL_GENERATION:
        raise DurableOwnerIntegrityError(
            "hypothesis owner protocol generation is invalid"
        )
    revision = raw["owner_revision"]
    if type(revision) is not int:
        raise DurableOwnerIntegrityError(
            "hypothesis owner revision must be an exact SQLite integer"
        )
    created_at = raw["created_at"]
    if type(created_at) is not str:
        raise DurableOwnerIntegrityError(
            "hypothesis creation time must be a string"
        )
    try:
        decoded_created_at = datetime.fromisoformat(created_at)
        value = HypothesisRecord(
            hypothesis_id=raw["hypothesis_id"],
            branch_id=raw["branch_id"],
            change_locus=raw["change_locus"],
            action=raw["action"],
            status=raw["status"],
            target_file=raw["target_file"],
            parent_hypothesis_id=raw["parent_hypothesis_id"],
            suggested_weight=raw["suggested_weight"],
            hypothesis_text=raw["hypothesis_text"],
            created_at=decoded_created_at,
            base_champion_version=raw["base_champion_version"],
            family_id=raw["family_id"],
            family_source=raw["family_source"],
            taxonomy_version=raw["taxonomy_version"],
            predicted_direction=raw["predicted_direction"],
            proposal_digest=raw["proposal_digest"],
        )
        canonical_payload = hypothesis_storage_payload(value)
        token = RevisionedHypothesisRecord.from_value(value, revision)
    except (TypeError, ValueError, OverflowError, DurableOwnerIntegrityError) as exc:
        raise DurableOwnerIntegrityError(
            "hypothesis owner row has malformed semantic data"
        ) from exc
    for column, canonical_value in canonical_payload.items():
        stored_value = raw[column]
        if (
            type(stored_value) is not type(canonical_value)
            or stored_value != canonical_value
        ):
            raise DurableOwnerIntegrityError(
                f"hypothesis owner column is not canonical: {column}"
            )
    return token


def _write_parameters(token: RevisionedHypothesisRecord) -> dict[str, Any]:
    parameters = hypothesis_storage_payload(token.value())
    parameters["owner_revision"] = token.owner_revision
    parameters["owner_protocol_generation"] = _OWNER_PROTOCOL_GENERATION
    return parameters


def _require_exact_expected(
    current: RevisionedHypothesisRecord,
    expected: RevisionedHypothesisRecord,
) -> None:
    if current.owner_revision != expected.owner_revision:
        raise OwnerRevisionConflict(
            "hypothesis owner revision differs from the expected revision"
        )
    if current != expected:
        raise OwnerPayloadConflict(
            "hypothesis owner payload differs at the expected revision"
        )


def _require_exact_committed(
    committed: RevisionedHypothesisRecord,
    target: RevisionedHypothesisRecord,
) -> None:
    if committed != target:
        raise DurableOwnerIntegrityError(
            "hypothesis owner post-write token differs from the requested target"
        )
