"""Dormant focused persistence for revisioned durable Branch owners.

The store owns the complete Branch SQL and row codec.  Transaction lifecycle,
owner-table permits, write facts, and sealed receipts remain in their focused
boundaries.  No production module imports this dormant store before the
offline durable-owner cutover.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Final

from scion.core.models import Branch, BranchState
from scion.lineage import owner_transaction as _owner
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerNotFound,
    OwnerPayloadConflict,
    OwnerRevisionConflict,
    RevisionedBranchRecord,
)

__all__ = ("BranchStore",)

_OWNER_PROTOCOL_GENERATION: Final[str] = "durable-owner.v1"
_BRANCH_COLUMNS: Final[tuple[str, ...]] = (
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
    "branch_evidence_summary_json",
    "infra_block_count",
    "owner_revision",
    "owner_protocol_generation",
)

_BRANCH_SELECT_SQL: Final[str] = """
SELECT branch_id,
       state,
       base_champion_id,
       base_champion_hash,
       lineage_id,
       current_code_hash,
       last_clean_code_hash,
       screening_expand_count,
       validation_expand_count,
       failure_codes,
       created_at,
       updated_at,
       direction,
       weight_revision,
       branch_code_status,
       branch_evidence_summary_json,
       infra_block_count,
       owner_revision,
       owner_protocol_generation
FROM branches
WHERE branch_id = ?
"""

_BRANCH_SELECT_ALL_SQL: Final[str] = """
SELECT branch_id,
       state,
       base_champion_id,
       base_champion_hash,
       lineage_id,
       current_code_hash,
       last_clean_code_hash,
       screening_expand_count,
       validation_expand_count,
       failure_codes,
       created_at,
       updated_at,
       direction,
       weight_revision,
       branch_code_status,
       branch_evidence_summary_json,
       infra_block_count,
       owner_revision,
       owner_protocol_generation
FROM branches
ORDER BY branch_id ASC
"""

_BRANCH_INSERT_SQL: Final[str] = """
INSERT INTO branches (
    branch_id,
    state,
    base_champion_id,
    base_champion_hash,
    lineage_id,
    current_code_hash,
    last_clean_code_hash,
    screening_expand_count,
    validation_expand_count,
    failure_codes,
    created_at,
    updated_at,
    direction,
    weight_revision,
    branch_code_status,
    branch_evidence_summary_json,
    infra_block_count,
    owner_revision,
    owner_protocol_generation
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_BRANCH_CAS_SQL: Final[str] = """
UPDATE branches
SET state = ?,
    base_champion_id = ?,
    base_champion_hash = ?,
    lineage_id = ?,
    current_code_hash = ?,
    last_clean_code_hash = ?,
    screening_expand_count = ?,
    validation_expand_count = ?,
    failure_codes = ?,
    created_at = ?,
    updated_at = ?,
    direction = ?,
    weight_revision = ?,
    branch_code_status = ?,
    branch_evidence_summary_json = ?,
    infra_block_count = ?,
    owner_revision = owner_revision + 1
WHERE branch_id = ?
  AND owner_revision = ?
  AND owner_protocol_generation = ?
"""


def _required_branch_id(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(
            "Branch owner ID must be a non-empty exact string"
        )
    return value


def _canonical_datetime(value: object, *, field: str) -> datetime:
    if type(value) is not str:
        raise DurableOwnerIntegrityError(f"{field} must be a canonical string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(f"{field} is invalid") from exc
    if parsed.isoformat() != value:
        raise DurableOwnerIntegrityError(f"{field} is not canonical")
    return parsed


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DurableOwnerIntegrityError(
                "Branch JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _decode_json(value: object, *, field: str) -> Any:
    if type(value) is not str:
        raise DurableOwnerIntegrityError(f"{field} must be JSON text")
    try:
        return json.loads(value, object_pairs_hook=_json_object)
    except DurableOwnerIntegrityError:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(f"{field} is malformed JSON") from exc


def _decode_branch_row(
    row: object,
    *,
    require_canonical_storage: bool = False,
) -> RevisionedBranchRecord:
    try:
        values = tuple(row)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise DurableOwnerIntegrityError("Branch owner row is not materialized") from exc
    if len(values) != len(_BRANCH_COLUMNS):
        raise DurableOwnerIntegrityError(
            "Branch owner row does not contain the complete final schema"
        )

    (
        branch_id,
        state,
        base_champion_id,
        base_champion_hash,
        lineage_id,
        current_code_hash,
        last_clean_code_hash,
        screening_expand_count,
        validation_expand_count,
        failure_codes_json,
        created_at,
        updated_at,
        direction,
        weight_revision,
        branch_code_status,
        evidence_summary_json,
        infra_block_count,
        owner_revision,
        protocol_generation,
    ) = values

    owner_id = _required_branch_id(branch_id)
    if type(state) is not str:
        raise DurableOwnerIntegrityError("Branch state must be exact text")
    try:
        branch_state = BranchState(state)
    except ValueError as exc:
        raise DurableOwnerIntegrityError("Branch state is invalid") from exc
    if type(lineage_id) is not str or not lineage_id:
        raise DurableOwnerIntegrityError("Branch lineage ID must be non-empty text")
    if protocol_generation != _OWNER_PROTOCOL_GENERATION:
        raise DurableOwnerIntegrityError("Branch owner protocol generation is invalid")

    branch = Branch(
        branch_id=owner_id,
        state=branch_state,
        base_champion_id=base_champion_id,
        base_champion_hash=base_champion_hash,
        lineage_id=lineage_id,
        current_code_hash=current_code_hash,
        last_clean_code_hash=last_clean_code_hash,
        screening_expand_count=screening_expand_count,
        validation_expand_count=validation_expand_count,
        failure_codes=_decode_json(
            failure_codes_json,
            field="Branch failure codes",
        ),
        created_at=_canonical_datetime(created_at, field="Branch creation time"),
        updated_at=_canonical_datetime(updated_at, field="Branch update time"),
        direction=direction,
        weight_revision=weight_revision,
        branch_code_status=branch_code_status,
        branch_evidence_summary=_decode_json(
            evidence_summary_json,
            field="Branch evidence summary",
        ),
        infra_block_count=infra_block_count,
    )
    try:
        token = RevisionedBranchRecord.from_value(branch, owner_revision)
    except DurableOwnerIntegrityError:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise DurableOwnerIntegrityError("Branch owner row is malformed") from exc
    if require_canonical_storage:
        canonical_values = (
            *_branch_storage_values(token),
            token.owner_revision,
            _OWNER_PROTOCOL_GENERATION,
        )
        for column, stored, canonical in zip(
            _BRANCH_COLUMNS,
            values,
            canonical_values,
            strict=True,
        ):
            if type(stored) is not type(canonical) or stored != canonical:
                raise DurableOwnerIntegrityError(
                    f"Branch post-write storage is not canonical: {column}"
                )
    return token


def _result_columns(result: _sqlite.ImmediateResult) -> tuple[str, ...]:
    description = result.description
    if description is None:
        raise DurableOwnerIntegrityError("Branch owner SELECT has no row description")
    try:
        return tuple(column[0] for column in description)
    except (IndexError, TypeError) as exc:
        raise DurableOwnerIntegrityError(
            "Branch owner SELECT description is malformed"
        ) from exc


def _read_branch_in(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    branch_id: str,
    *,
    require_canonical_storage: bool = False,
) -> RevisionedBranchRecord | None:
    owner_id = _required_branch_id(branch_id)
    result = _sqlite._execute_participant(
        transaction,
        database_authority,
        _BRANCH_SELECT_SQL,
        (owner_id,),
    )
    if _result_columns(result) != _BRANCH_COLUMNS:
        raise DurableOwnerIntegrityError(
            "Branch owner SELECT did not return the exact final columns"
        )
    rows = result.fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise DurableOwnerIntegrityError(
            "Branch owner SELECT returned duplicate durable owners"
        )
    return _decode_branch_row(
        rows[0],
        require_canonical_storage=require_canonical_storage,
    )


def _decode_branch_snapshot_rows(
    rows: tuple[object, ...],
) -> tuple[RevisionedBranchRecord, ...]:
    decoded: list[RevisionedBranchRecord] = []
    owner_ids: set[str] = set()
    for row in rows:
        try:
            columns = tuple(row.keys())  # type: ignore[attr-defined]
        except (AttributeError, TypeError) as exc:
            raise DurableOwnerIntegrityError(
                "Branch snapshot row is not a named SQLite row"
            ) from exc
        if columns != _BRANCH_COLUMNS:
            raise DurableOwnerIntegrityError(
                "Branch snapshot row has incomplete or unexpected columns"
            )
        token = _decode_branch_row(row)
        if token.branch_id in owner_ids:
            raise DurableOwnerIntegrityError(
                "Branch snapshot returned duplicate durable owners"
            )
        owner_ids.add(token.branch_id)
        decoded.append(token)
    return tuple(decoded)


def _json_text(value: object, *, field: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(f"{field} is not canonical JSON") from exc


def _branch_storage_values(token: RevisionedBranchRecord) -> tuple[object, ...]:
    branch = token.value()
    return (
        branch.branch_id,
        branch.state.value,
        branch.base_champion_id,
        branch.base_champion_hash,
        branch.lineage_id,
        branch.current_code_hash,
        branch.last_clean_code_hash,
        branch.screening_expand_count,
        branch.validation_expand_count,
        _json_text(branch.failure_codes, field="Branch failure codes"),
        branch.created_at.isoformat(),
        branch.updated_at.isoformat(),
        branch.direction,
        branch.weight_revision,
        branch.branch_code_status,
        _json_text(
            branch.branch_evidence_summary,
            field="Branch evidence summary",
        ),
        branch.infra_block_count,
    )


def _require_expected_owner(
    actual: RevisionedBranchRecord | None,
    expected: RevisionedBranchRecord,
) -> None:
    if actual is None:
        raise OwnerNotFound(f"Branch owner {expected.branch_id!r} does not exist")
    if actual.owner_revision != expected.owner_revision:
        raise OwnerRevisionConflict(
            f"Branch owner {expected.branch_id!r} revision changed"
        )
    if actual != expected:
        raise OwnerPayloadConflict(
            f"Branch owner {expected.branch_id!r} payload changed at the same revision"
        )


def _raise_cas_failure(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    expected: RevisionedBranchRecord,
) -> None:
    current = _read_branch_in(
        transaction,
        database_authority,
        expected.branch_id,
    )
    _require_expected_owner(current, expected)
    raise DurableOwnerIntegrityError(
        "Branch CAS changed zero rows despite an exact current owner"
    )


def _raise_insert_failure(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    branch_id: str,
) -> None:
    if _read_branch_in(transaction, database_authority, branch_id) is not None:
        raise OwnerAlreadyExists(f"Branch owner {branch_id!r} already exists")
    raise DurableOwnerIntegrityError(
        "Branch insert changed zero rows without creating its owner"
    )


class BranchStore:
    """Focused, connection-scoped durable Branch owner participant."""

    __slots__ = ("__database_authority", "__store_authority")

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        self.__database_authority = database_authority
        self.__store_authority = _owner._issue_branch_store_authority(
            database_authority
        )

    def load_revisioned_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        branch_id: str,
    ) -> RevisionedBranchRecord | None:
        _sqlite.require_active_immediate_transaction(
            transaction,
            self.__database_authority,
        )
        return _read_branch_in(
            transaction,
            self.__database_authority,
            branch_id,
        )

    def _load_revisioned_branch_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        branch_id: str,
    ) -> RevisionedBranchRecord | None:
        """Strictly decode one Branch for Registry-owned outcome classification."""

        owner_id = _required_branch_id(branch_id)
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _BRANCH_SELECT_SQL,
            (owner_id,),
        )
        decoded = _decode_branch_snapshot_rows(rows)
        if not decoded:
            return None
        if len(decoded) != 1 or decoded[0].branch_id != owner_id:
            raise DurableOwnerIntegrityError(
                "Branch snapshot did not return the exact requested owner"
            )
        return decoded[0]

    def _load_all_revisioned_branches_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
    ) -> tuple[RevisionedBranchRecord, ...]:
        """Return the complete stable Branch inventory from the caller's snapshot."""

        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _BRANCH_SELECT_ALL_SQL,
        )
        return _decode_branch_snapshot_rows(rows)

    def compare_and_swap_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        expected: RevisionedBranchRecord,
        target: Branch,
    ) -> _owner.OwnerMutationReceipt:
        if type(expected) is not RevisionedBranchRecord:
            raise DurableOwnerIntegrityError(
                "Branch CAS expected owner must be a revisioned Branch token"
            )
        if type(target) is not Branch:
            raise DurableOwnerIntegrityError("Branch CAS target must be a Branch")
        ledger = _owner._require_branch_store_ledger(
            transaction,
            self.__store_authority,
        )
        actual = _read_branch_in(
            transaction,
            self.__database_authority,
            expected.branch_id,
        )
        _require_expected_owner(actual, expected)

        target_token = RevisionedBranchRecord.from_value(
            target,
            expected.owner_revision + 1,
        )
        if target_token.branch_id != expected.branch_id:
            raise OwnerPayloadConflict("Branch CAS target changed owner identity")
        if target_token.payload_sha256 == expected.payload_sha256:
            raise OwnerPayloadConflict("Branch CAS target has no semantic change")
        target_values = _branch_storage_values(target_token)

        result, write_fact = _owner._execute_branch_owner_update(
            self.__store_authority,
            ledger,
            expected,
            _BRANCH_CAS_SQL,
            (
                *target_values[1:],
                expected.branch_id,
                expected.owner_revision,
                _OWNER_PROTOCOL_GENERATION,
            ),
        )
        if result.rowcount != 1:
            _raise_cas_failure(
                transaction,
                self.__database_authority,
                expected,
            )

        committed = _read_branch_in(
            transaction,
            self.__database_authority,
            expected.branch_id,
            require_canonical_storage=True,
        )
        if committed != target_token:
            raise OwnerPayloadConflict(
                "Branch CAS durable post-state differs from its exact target token"
            )
        return _owner._issue_branch_mutation_receipt(
            self.__store_authority,
            ledger,
            write_fact,
            committed,
        )

    def insert_once_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        target: Branch,
    ) -> _owner.OwnerCreationReceipt:
        if type(target) is not Branch:
            raise DurableOwnerIntegrityError("Branch creation target must be a Branch")
        target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)
        ledger = _owner._require_branch_store_ledger(
            transaction,
            self.__store_authority,
        )
        if (
            _read_branch_in(
                transaction,
                self.__database_authority,
                target_token.branch_id,
            )
            is not None
        ):
            raise OwnerAlreadyExists(
                f"Branch owner {target_token.branch_id!r} already exists"
            )
        target_values = _branch_storage_values(target_token)

        result, write_fact = _owner._execute_branch_owner_insert(
            self.__store_authority,
            ledger,
            target_token.branch_id,
            _BRANCH_INSERT_SQL,
            (*target_values, 0, _OWNER_PROTOCOL_GENERATION),
        )
        if result.rowcount != 1:
            _raise_insert_failure(
                transaction,
                self.__database_authority,
                target_token.branch_id,
            )

        committed = _read_branch_in(
            transaction,
            self.__database_authority,
            target_token.branch_id,
            require_canonical_storage=True,
        )
        if committed != target_token:
            raise OwnerPayloadConflict(
                "Branch creation durable post-state differs from its exact target token"
            )
        return _owner._issue_branch_creation_receipt(
            self.__store_authority,
            ledger,
            write_fact,
            committed,
        )
