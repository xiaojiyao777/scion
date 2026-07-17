"""Dormant, focused persistence for revisioned hypothesis owners.

This module owns the complete hypothesis row projection and the only SQL used
by the focused store.  Transaction authorization, one-shot write permits, and
receipt accounting remain in :mod:`scion.lineage.owner_transaction`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
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
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
    branch_storage_payload,
    generated_hypothesis_storage_payload,
    hypothesis_storage_payload,
)

__all__ = ("HypothesisStore",)

_OWNER_PROTOCOL_GENERATION: Final[str] = "durable-owner.v1"
_execute_generated_owner_insert = _owner._execute_hypothesis_owner_insert
_CANONICAL_UTC_MICROSECOND_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"\.[0-9]{6}\+00:00$"
)

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

_HYPOTHESIS_SELECT_ALL_SQL: Final[str] = """
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
ORDER BY hypothesis_id ASC
"""

_HYPOTHESIS_SELECT_BRANCH_SQL: Final[str] = """
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
WHERE branch_id = :branch_id
ORDER BY hypothesis_id ASC
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

# Frozen by the accepted Checkpoint-B correction.  Cross-owner tables appear
# only as non-returning authorization predicates; this store owns neither
# their codecs nor their mutation lifecycle.
_HYPOTHESIS_GENERATED_INSERT_SQL: Final[str] = """
INSERT INTO hypotheses (
    hypothesis_id, branch_id, change_locus, action, status, target_file,
    parent_hypothesis_id, suggested_weight, hypothesis_text, created_at,
    base_champion_version, family_id, family_source, taxonomy_version,
    predicted_direction, proposal_digest, owner_revision,
    owner_protocol_generation
)
SELECT
    :hypothesis_id, :branch_id, :change_locus, :action, :status, :target_file,
    :parent_hypothesis_id, :suggested_weight, :hypothesis_text, :created_at,
    :base_champion_version, :family_id, :family_source, :taxonomy_version,
    :predicted_direction, :proposal_digest, :owner_revision,
    :owner_protocol_generation
WHERE NOT EXISTS (
    SELECT 1 FROM hypotheses AS duplicate_h
    WHERE duplicate_h.hypothesis_id = :hypothesis_id
)
AND :branch_id = :source_branch_id
AND EXISTS (
    SELECT 1 FROM branches AS source_b
    WHERE source_b.branch_id = :source_branch_id
      AND source_b.state IS :source_branch_state
      AND source_b.base_champion_id IS :source_branch_base_champion_id
      AND source_b.base_champion_hash IS :source_branch_base_champion_hash
      AND source_b.lineage_id IS :source_branch_lineage_id
      AND source_b.current_code_hash IS :source_branch_current_code_hash
      AND source_b.last_clean_code_hash IS :source_branch_last_clean_code_hash
      AND source_b.screening_expand_count IS :source_branch_screening_expand_count
      AND source_b.validation_expand_count IS :source_branch_validation_expand_count
      AND source_b.failure_codes IS :source_branch_failure_codes
      AND source_b.created_at IS :source_branch_created_at
      AND source_b.updated_at IS :source_branch_updated_at
      AND source_b.direction IS :source_branch_direction
      AND source_b.weight_revision IS :source_branch_weight_revision
      AND source_b.branch_code_status IS :source_branch_code_status
      AND source_b.branch_evidence_summary_json IS :source_branch_evidence_summary_json
      AND source_b.infra_block_count IS :source_branch_infra_block_count
      AND source_b.owner_revision IS :source_branch_owner_revision
      AND source_b.owner_protocol_generation IS :source_branch_owner_protocol_generation
)
AND EXISTS (
    SELECT 1 FROM proposal_hypothesis_attempt_bindings AS binding
    WHERE binding.campaign_id = :authority_campaign_id
      AND binding.branch_id = :branch_id
      AND binding.branch_owner_revision = :source_branch_owner_revision
      AND binding.branch_storage_sha256 = :source_branch_storage_sha256
      AND binding.hypothesis_id = :hypothesis_id
      AND binding.parent_hypothesis_id IS :parent_hypothesis_id
      AND binding.parent_owner_revision IS :parent_owner_revision
      AND binding.parent_storage_sha256 IS :parent_storage_sha256
      AND binding.proposal_digest = :proposal_digest
      AND binding.hypothesis_storage_sha256 = :hypothesis_storage_sha256
      AND binding.binding_protocol_generation = 'proposal-h-binding.v1'
)
AND (
    (
        :parent_hypothesis_id IS NULL
        AND NOT EXISTS (
            SELECT 1 FROM hypotheses AS empty_history
            WHERE empty_history.branch_id = :branch_id
        )
    )
    OR
    (
        :parent_hypothesis_id IS NOT NULL
        AND (
            :created_at > :parent_created_at
            OR (
                :created_at = :parent_created_at
                AND :hypothesis_id > :parent_hypothesis_id
            )
        )
        AND EXISTS (
            SELECT 1 FROM hypotheses AS parent_h
            WHERE parent_h.hypothesis_id = :parent_hypothesis_id
              AND parent_h.branch_id IS :parent_branch_id
              AND parent_h.change_locus IS :parent_change_locus
              AND parent_h.action IS :parent_action
              AND parent_h.status IS :parent_status
              AND parent_h.target_file IS :parent_target_file
              AND parent_h.parent_hypothesis_id IS :parent_parent_hypothesis_id
              AND parent_h.suggested_weight IS :parent_suggested_weight
              AND parent_h.hypothesis_text IS :parent_hypothesis_text
              AND parent_h.created_at IS :parent_created_at
              AND parent_h.base_champion_version IS :parent_base_champion_version
              AND parent_h.family_id IS :parent_family_id
              AND parent_h.family_source IS :parent_family_source
              AND parent_h.taxonomy_version IS :parent_taxonomy_version
              AND parent_h.predicted_direction IS :parent_predicted_direction
              AND parent_h.proposal_digest IS :parent_proposal_digest
              AND parent_h.owner_revision IS :parent_owner_revision
              AND parent_h.owner_protocol_generation IS :parent_owner_protocol_generation
        )
        AND NOT EXISTS (
            SELECT 1 FROM hypotheses AS later_h
            WHERE later_h.branch_id = :branch_id
              AND (
                  later_h.created_at > :parent_created_at
                  OR (
                      later_h.created_at = :parent_created_at
                      AND later_h.hypothesis_id > :parent_hypothesis_id
                  )
              )
        )
    )
)
AND NOT EXISTS (
    SELECT 1 FROM hypotheses AS active_h
    WHERE active_h.branch_id = :branch_id
      AND active_h.status = 'active'
)
AND NOT EXISTS (
    SELECT 1 FROM candidate_evaluation_leases AS active_lease
    WHERE active_lease.state = 'active'
      AND (
          active_lease.branch_id = :branch_id
          OR active_lease.source_hypothesis_id = :hypothesis_id
          OR active_lease.source_hypothesis_id IN (
              SELECT source_h.hypothesis_id
              FROM hypotheses AS source_h
              WHERE source_h.branch_id = :branch_id
          )
      )
)
"""

_AUTHORITY_CAMPAIGN_ID_SQL: Final[str] = """
SELECT campaign_id
FROM campaign_identity
"""

_GENERATED_INSERT_CLASSIFICATION_COLUMNS: Final[tuple[str, ...]] = (
    "duplicate_owner",
    "source_matches",
    "parent_matches",
    "active_h_conflict",
    "lease_conflict",
    "binding_matches",
)

_GENERATED_INSERT_CLASSIFICATION_SQL: Final[str] = """
SELECT
    EXISTS (
        SELECT 1 FROM hypotheses AS duplicate_h
        WHERE duplicate_h.hypothesis_id = :hypothesis_id
    ) AS duplicate_owner,
    EXISTS (
        SELECT 1 FROM branches AS source_b
        WHERE source_b.branch_id = :source_branch_id
          AND source_b.state IS :source_branch_state
          AND source_b.base_champion_id IS :source_branch_base_champion_id
          AND source_b.base_champion_hash IS :source_branch_base_champion_hash
          AND source_b.lineage_id IS :source_branch_lineage_id
          AND source_b.current_code_hash IS :source_branch_current_code_hash
          AND source_b.last_clean_code_hash IS :source_branch_last_clean_code_hash
          AND source_b.screening_expand_count IS :source_branch_screening_expand_count
          AND source_b.validation_expand_count IS :source_branch_validation_expand_count
          AND source_b.failure_codes IS :source_branch_failure_codes
          AND source_b.created_at IS :source_branch_created_at
          AND source_b.updated_at IS :source_branch_updated_at
          AND source_b.direction IS :source_branch_direction
          AND source_b.weight_revision IS :source_branch_weight_revision
          AND source_b.branch_code_status IS :source_branch_code_status
          AND source_b.branch_evidence_summary_json IS :source_branch_evidence_summary_json
          AND source_b.infra_block_count IS :source_branch_infra_block_count
          AND source_b.owner_revision IS :source_branch_owner_revision
          AND source_b.owner_protocol_generation IS :source_branch_owner_protocol_generation
    ) AS source_matches,
    CASE
        WHEN :parent_hypothesis_id IS NULL THEN NOT EXISTS (
            SELECT 1 FROM hypotheses AS empty_history
            WHERE empty_history.branch_id = :branch_id
        )
        ELSE (
            (
                :created_at > :parent_created_at
                OR (
                    :created_at = :parent_created_at
                    AND :hypothesis_id > :parent_hypothesis_id
                )
            )
            AND EXISTS (
                SELECT 1 FROM hypotheses AS parent_h
                WHERE parent_h.hypothesis_id = :parent_hypothesis_id
                  AND parent_h.branch_id IS :parent_branch_id
                  AND parent_h.change_locus IS :parent_change_locus
                  AND parent_h.action IS :parent_action
                  AND parent_h.status IS :parent_status
                  AND parent_h.target_file IS :parent_target_file
                  AND parent_h.parent_hypothesis_id IS :parent_parent_hypothesis_id
                  AND parent_h.suggested_weight IS :parent_suggested_weight
                  AND parent_h.hypothesis_text IS :parent_hypothesis_text
                  AND parent_h.created_at IS :parent_created_at
                  AND parent_h.base_champion_version IS :parent_base_champion_version
                  AND parent_h.family_id IS :parent_family_id
                  AND parent_h.family_source IS :parent_family_source
                  AND parent_h.taxonomy_version IS :parent_taxonomy_version
                  AND parent_h.predicted_direction IS :parent_predicted_direction
                  AND parent_h.proposal_digest IS :parent_proposal_digest
                  AND parent_h.owner_revision IS :parent_owner_revision
                  AND parent_h.owner_protocol_generation IS :parent_owner_protocol_generation
            )
            AND NOT EXISTS (
                SELECT 1 FROM hypotheses AS later_h
                WHERE later_h.branch_id = :branch_id
                  AND (
                      later_h.created_at > :parent_created_at
                      OR (
                          later_h.created_at = :parent_created_at
                          AND later_h.hypothesis_id > :parent_hypothesis_id
                      )
                  )
            )
        )
    END AS parent_matches,
    EXISTS (
        SELECT 1 FROM hypotheses AS active_h
        WHERE active_h.branch_id = :branch_id
          AND active_h.status = 'active'
    ) AS active_h_conflict,
    EXISTS (
        SELECT 1 FROM candidate_evaluation_leases AS active_lease
        WHERE active_lease.state = 'active'
          AND (
              active_lease.branch_id = :branch_id
              OR active_lease.source_hypothesis_id = :hypothesis_id
              OR active_lease.source_hypothesis_id IN (
                  SELECT source_h.hypothesis_id
                  FROM hypotheses AS source_h
                  WHERE source_h.branch_id = :branch_id
              )
          )
    ) AS lease_conflict,
    EXISTS (
        SELECT 1 FROM proposal_hypothesis_attempt_bindings AS binding
        WHERE binding.campaign_id = :authority_campaign_id
          AND binding.branch_id = :branch_id
          AND binding.branch_owner_revision = :source_branch_owner_revision
          AND binding.branch_storage_sha256 = :source_branch_storage_sha256
          AND binding.hypothesis_id = :hypothesis_id
          AND binding.parent_hypothesis_id IS :parent_hypothesis_id
          AND binding.parent_owner_revision IS :parent_owner_revision
          AND binding.parent_storage_sha256 IS :parent_storage_sha256
          AND binding.proposal_digest = :proposal_digest
          AND binding.hypothesis_storage_sha256 = :hypothesis_storage_sha256
          AND binding.binding_protocol_generation = 'proposal-h-binding.v1'
    ) AS binding_matches
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

    def _load_branch_hypotheses_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        branch_id: str,
    ) -> tuple[RevisionedHypothesisRecord, ...]:
        """Return one Branch's complete H bundle inside an active transaction."""

        _sqlite.require_active_immediate_transaction(
            transaction,
            self.__database_authority,
        )
        owner_branch_id = _validate_branch_id(branch_id)
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _HYPOTHESIS_SELECT_BRANCH_SQL,
            {"branch_id": owner_branch_id},
        )
        return _decode_branch_hypotheses(
            tuple(result.fetchall()),
            owner_branch_id,
        )

    def _load_revisioned_hypothesis_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord | None:
        """Strictly decode one H for Registry-owned outcome classification."""

        owner_id = _validate_hypothesis_id(hypothesis_id)
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_SQL,
            {"hypothesis_id": owner_id},
        )
        decoded = _decode_hypothesis_snapshot_rows(rows)
        if not decoded:
            return None
        if len(decoded) != 1 or decoded[0].hypothesis_id != owner_id:
            raise DurableOwnerIntegrityError(
                "hypothesis snapshot did not return the exact requested owner"
            )
        return decoded[0]

    def _load_all_revisioned_hypotheses_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
    ) -> tuple[RevisionedHypothesisRecord, ...]:
        """Return the complete stable H inventory from the caller's snapshot."""

        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_ALL_SQL,
        )
        return _decode_hypothesis_snapshot_rows(rows)

    def _load_all_hypotheses_with_generated_targets_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        generated_hypothesis_ids: tuple[str, ...],
    ) -> tuple[RevisionedHypothesisRecord, ...]:
        """Load the complete inventory with strict named checkpoint-B targets.

        Named targets are decoded by the generated-H codec when present and
        must be revision zero.  Other canonical UTC-microsecond rows use that
        codec as generated history; all remaining historical rows retain the
        legacy decoder.  Missing named targets remain representable so the
        Registry can install a Branch-local partial-group hold.
        """

        if type(generated_hypothesis_ids) is not tuple:
            raise TypeError("generated_hypothesis_ids must be an exact tuple")
        target_ids = tuple(
            _validate_hypothesis_id(value) for value in generated_hypothesis_ids
        )
        if len(set(target_ids)) != len(target_ids):
            raise DurableOwnerIntegrityError(
                "generated target inventory contains duplicate owner IDs"
            )
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_ALL_SQL,
        )
        named = frozenset(target_ids)
        decoded: list[RevisionedHypothesisRecord] = []
        owner_ids: set[str] = set()
        for row in rows:
            try:
                stored_id = row["hypothesis_id"]
            except (IndexError, KeyError, TypeError) as exc:
                raise DurableOwnerIntegrityError(
                    "generated-target inventory row has no hypothesis identity"
                ) from exc
            token = (
                _decode_generated_hypothesis_row(row)
                if stored_id in named or _row_uses_generated_timestamp_protocol(row)
                else _decode_hypothesis_row(row)
            )
            if token.hypothesis_id in owner_ids:
                raise DurableOwnerIntegrityError(
                    "generated-target inventory returned duplicate owners"
                )
            if token.hypothesis_id in named and token.owner_revision != 0:
                raise DurableOwnerIntegrityError(
                    "generated-target inventory returned a nonzero target revision"
                )
            owner_ids.add(token.hypothesis_id)
            decoded.append(token)
        return tuple(decoded)

    def _load_branch_hypotheses_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        branch_id: str,
    ) -> tuple[RevisionedHypothesisRecord, ...]:
        """Return one affected Branch's complete H bundle in the same snapshot."""

        owner_branch_id = _validate_branch_id(branch_id)
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_BRANCH_SQL,
            {"branch_id": owner_branch_id},
        )
        return _decode_branch_hypotheses(rows, owner_branch_id)

    def _load_generated_revisioned_hypothesis_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord | None:
        """Strictly read one generated revision-zero H from a stable snapshot."""

        owner_id = _validate_hypothesis_id(hypothesis_id)
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_SQL,
            {"hypothesis_id": owner_id},
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise DurableOwnerIntegrityError(
                "generated hypothesis snapshot returned multiple owners"
            )
        token = _decode_generated_hypothesis_row(rows[0])
        if token.hypothesis_id != owner_id or token.owner_revision != 0:
            raise DurableOwnerIntegrityError(
                "generated hypothesis snapshot did not return its exact revision-zero owner"
            )
        return token

    def _load_branch_hypotheses_with_generated_target_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        branch_id: str,
        generated_hypothesis_id: str,
    ) -> tuple[RevisionedHypothesisRecord, ...]:
        """Read a Branch bundle with one optional strict generated target.

        The named target is always strict.  Other fixed-UTC-microsecond rows
        use the generated decoder, while historical rows retain the legacy
        decoder.  This avoids reinterpreting old H storage in global commit
        classification.
        """

        owner_branch_id = _validate_branch_id(branch_id)
        target_id = _validate_hypothesis_id(generated_hypothesis_id)
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _HYPOTHESIS_SELECT_BRANCH_SQL,
            {"branch_id": owner_branch_id},
        )
        decoded: list[RevisionedHypothesisRecord] = []
        owner_ids: set[str] = set()
        for row in rows:
            try:
                stored_id = row["hypothesis_id"]
            except (IndexError, KeyError, TypeError) as exc:
                raise DurableOwnerIntegrityError(
                    "generated-target Branch snapshot row has no hypothesis identity"
                ) from exc
            token = (
                _decode_generated_hypothesis_row(row)
                if (
                    stored_id == target_id
                    or _row_uses_generated_timestamp_protocol(row)
                )
                else _decode_hypothesis_row(row)
            )
            if token.hypothesis_id in owner_ids:
                raise DurableOwnerIntegrityError(
                    "generated-target Branch snapshot returned duplicate owners"
                )
            if token.value().branch_id != owner_branch_id:
                raise DurableOwnerIntegrityError(
                    "generated-target Branch snapshot returned another Branch"
                )
            if token.hypothesis_id == target_id and token.owner_revision != 0:
                raise DurableOwnerIntegrityError(
                    "generated-target Branch snapshot returned a nonzero target revision"
                )
            owner_ids.add(token.hypothesis_id)
            decoded.append(token)
        return tuple(sorted(decoded, key=lambda token: token.hypothesis_id))

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
            raise DurableOwnerIntegrityError("target must be an exact HypothesisRecord")
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
        creation_authorization: _owner._OwnerCreationAuthorization,
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
        if self._read_optional_in(transaction, target_token.hypothesis_id) is not None:
            raise OwnerAlreadyExists(
                f"hypothesis owner already exists: {target_token.hypothesis_id}"
            )

        result, write_fact = _owner._execute_hypothesis_owner_insert(
            self.__store_authority,
            ledger,
            creation_authorization,
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

    def insert_generated_once_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        source_branch: RevisionedBranchRecord,
        prior_head: RevisionedHypothesisRecord | None,
        target: RevisionedHypothesisRecord,
        creation_authorization: _owner._OwnerCreationAuthorization,
    ) -> _owner.OwnerCreationReceipt:
        """Create one guarded revision-zero H from exact captured owner facts.

        Branch, proposal-binding, history-head, active-H, and evaluation-lease
        facts are authorization predicates only.  This method never returns or
        adopts a cross-owner row and never repeats a failed statement.
        """

        if type(source_branch) is not RevisionedBranchRecord:
            raise DurableOwnerIntegrityError(
                "generated hypothesis requires an exact captured Branch owner"
            )
        if prior_head is not None and type(prior_head) is not RevisionedHypothesisRecord:
            raise DurableOwnerIntegrityError(
                "generated hypothesis prior head must be exact or absent"
            )
        if type(target) is not RevisionedHypothesisRecord or target.owner_revision != 0:
            raise DurableOwnerIntegrityError(
                "generated hypothesis target must be exact revision zero"
            )
        ledger = _owner._require_hypothesis_store_ledger(
            transaction,
            self.__store_authority,
        )
        parameters = _generated_insert_parameters(
            transaction,
            self.__database_authority,
            source_branch=source_branch,
            prior_head=prior_head,
            target=target,
        )
        result, write_fact = _execute_generated_owner_insert(
            self.__store_authority,
            ledger,
            creation_authorization,
            target.hypothesis_id,
            _HYPOTHESIS_GENERATED_INSERT_SQL,
            parameters,
        )
        if result.rowcount != 1:
            self._raise_generated_insert_failure(
                transaction,
                parameters=parameters,
            )

        committed = self._read_generated_required_in(
            transaction,
            target.hypothesis_id,
        )
        _require_exact_committed(committed, target)
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

    def _read_generated_required_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        hypothesis_id: str,
    ) -> RevisionedHypothesisRecord:
        owner_id = _validate_hypothesis_id(hypothesis_id)
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _HYPOTHESIS_SELECT_SQL,
            {"hypothesis_id": owner_id},
        )
        rows = result.fetchall()
        if len(rows) != 1:
            raise DurableOwnerIntegrityError(
                "generated hypothesis reread did not return one exact owner"
            )
        token = _decode_generated_hypothesis_row(rows[0])
        if token.hypothesis_id != owner_id or token.owner_revision != 0:
            raise DurableOwnerIntegrityError(
                "generated hypothesis reread returned another revision-zero owner"
            )
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

    def _raise_generated_insert_failure(
        self,
        transaction: _sqlite.ImmediateTransaction,
        *,
        parameters: dict[str, Any],
    ) -> None:
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _GENERATED_INSERT_CLASSIFICATION_SQL,
            parameters,
        )
        description = result.description
        columns = (
            () if description is None else tuple(column[0] for column in description)
        )
        rows = result.fetchall()
        if columns != _GENERATED_INSERT_CLASSIFICATION_COLUMNS or len(rows) != 1:
            raise DurableOwnerIntegrityError(
                "generated hypothesis zero-row classification is malformed"
            )
        values = tuple(rows[0])
        if any(type(value) is not int or value not in {0, 1} for value in values):
            raise DurableOwnerIntegrityError(
                "generated hypothesis zero-row classification is noncanonical"
            )
        classified = dict(zip(columns, values, strict=True))
        hypothesis_id = parameters["hypothesis_id"]
        if classified["duplicate_owner"]:
            raise OwnerAlreadyExists(
                f"generated hypothesis owner already exists: {hypothesis_id}"
            )
        if not classified["source_matches"]:
            raise OwnerPayloadConflict(
                "generated hypothesis source Branch differs from its capture"
            )
        if not classified["parent_matches"]:
            raise OwnerPayloadConflict(
                "generated hypothesis prior history head differs from its capture"
            )
        if classified["active_h_conflict"]:
            raise OwnerPayloadConflict(
                "generated hypothesis Branch already has an active H"
            )
        if classified["lease_conflict"]:
            raise OwnerPayloadConflict(
                "generated hypothesis conflicts with an active evaluation lease"
            )
        if not classified["binding_matches"]:
            raise OwnerPayloadConflict(
                "generated hypothesis has no exact proposal-attempt binding"
            )
        raise DurableOwnerIntegrityError(
            "generated hypothesis INSERT changed zero rows despite exact predicates"
        )


def _canonical_generated_created_at(
    token: RevisionedHypothesisRecord,
    *,
    label: str,
) -> str:
    try:
        payload = json.loads(token.canonical_storage_payload_json.decode("utf-8"))
        raw = payload["created_at"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DurableOwnerIntegrityError(
            f"{label} has no exact generated-H creation timestamp"
        ) from exc
    if type(raw) is not str or _CANONICAL_UTC_MICROSECOND_RE.fullmatch(raw) is None:
        raise DurableOwnerIntegrityError(
            f"{label} must use canonical UTC microsecond text"
        )
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(
            f"{label} has an invalid generated-H creation timestamp"
        ) from exc
    if parsed.tzinfo != timezone.utc or parsed.isoformat(timespec="microseconds") != raw:
        raise DurableOwnerIntegrityError(
            f"{label} must use canonical UTC microsecond text"
        )
    return raw


def _canonical_sql_json(value: object, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(f"{label} is not canonical JSON") from exc


def _generated_insert_parameters(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    *,
    source_branch: RevisionedBranchRecord,
    prior_head: RevisionedHypothesisRecord | None,
    target: RevisionedHypothesisRecord,
) -> dict[str, Any]:
    authority_campaign_id = _read_authority_campaign_id(
        transaction,
        database_authority,
    )
    source_value = source_branch.value()
    source_payload = branch_storage_payload(source_value)
    target_value = target.value()
    target_payload = generated_hypothesis_storage_payload(target_value)
    target_created_at = _canonical_generated_created_at(
        target,
        label="generated hypothesis target",
    )
    if target_payload["created_at"] != target_created_at:
        raise DurableOwnerIntegrityError(
            "generated hypothesis target storage timestamp is not exact"
        )
    if target_value.branch_id != source_branch.branch_id:
        raise OwnerPayloadConflict(
            "generated hypothesis target belongs to another Branch"
        )
    if target_value.status != "active":
        raise OwnerPayloadConflict(
            "generated hypothesis target status must be active"
        )

    if prior_head is None:
        if target_value.parent_hypothesis_id is not None:
            raise OwnerPayloadConflict(
                "generated hypothesis target has a parent for empty history"
            )
        parent_parameters: dict[str, Any] = {
            "parent_hypothesis_id": None,
            "parent_owner_revision": None,
            "parent_storage_sha256": None,
            "parent_branch_id": None,
            "parent_change_locus": None,
            "parent_action": None,
            "parent_status": None,
            "parent_target_file": None,
            "parent_parent_hypothesis_id": None,
            "parent_suggested_weight": None,
            "parent_hypothesis_text": None,
            "parent_created_at": None,
            "parent_base_champion_version": None,
            "parent_family_id": None,
            "parent_family_source": None,
            "parent_taxonomy_version": None,
            "parent_predicted_direction": None,
            "parent_proposal_digest": None,
            "parent_owner_protocol_generation": None,
        }
    else:
        parent_value = prior_head.value()
        parent_payload = generated_hypothesis_storage_payload(parent_value)
        parent_created_at = _canonical_generated_created_at(
            prior_head,
            label="generated hypothesis prior head",
        )
        if parent_payload["created_at"] != parent_created_at:
            raise DurableOwnerIntegrityError(
                "generated hypothesis prior-head storage timestamp is not exact"
            )
        if parent_value.branch_id != source_branch.branch_id:
            raise OwnerPayloadConflict(
                "generated hypothesis prior head belongs to another Branch"
            )
        if target_value.parent_hypothesis_id != prior_head.hypothesis_id:
            raise OwnerPayloadConflict(
                "generated hypothesis target does not name the captured prior head"
            )
        parent_parameters = {
            "parent_hypothesis_id": prior_head.hypothesis_id,
            "parent_owner_revision": prior_head.owner_revision,
            "parent_storage_sha256": prior_head.payload_sha256,
            "parent_branch_id": parent_payload["branch_id"],
            "parent_change_locus": parent_payload["change_locus"],
            "parent_action": parent_payload["action"],
            "parent_status": parent_payload["status"],
            "parent_target_file": parent_payload["target_file"],
            "parent_parent_hypothesis_id": parent_payload["parent_hypothesis_id"],
            "parent_suggested_weight": parent_payload["suggested_weight"],
            "parent_hypothesis_text": parent_payload["hypothesis_text"],
            "parent_created_at": parent_created_at,
            "parent_base_champion_version": parent_payload[
                "base_champion_version"
            ],
            "parent_family_id": parent_payload["family_id"],
            "parent_family_source": parent_payload["family_source"],
            "parent_taxonomy_version": parent_payload["taxonomy_version"],
            "parent_predicted_direction": parent_payload["predicted_direction"],
            "parent_proposal_digest": parent_payload["proposal_digest"],
            "parent_owner_protocol_generation": _OWNER_PROTOCOL_GENERATION,
        }

    parameters = dict(target_payload)
    parameters.update(
        {
            "created_at": target_created_at,
            "owner_revision": target.owner_revision,
            "owner_protocol_generation": _OWNER_PROTOCOL_GENERATION,
            "authority_campaign_id": authority_campaign_id,
            "hypothesis_storage_sha256": target.payload_sha256,
            "source_branch_id": source_branch.branch_id,
            "source_branch_state": source_payload["state"],
            "source_branch_base_champion_id": source_payload[
                "base_champion_id"
            ],
            "source_branch_base_champion_hash": source_payload[
                "base_champion_hash"
            ],
            "source_branch_lineage_id": source_payload["lineage_id"],
            "source_branch_current_code_hash": source_payload[
                "current_code_hash"
            ],
            "source_branch_last_clean_code_hash": source_payload[
                "last_clean_code_hash"
            ],
            "source_branch_screening_expand_count": source_payload[
                "screening_expand_count"
            ],
            "source_branch_validation_expand_count": source_payload[
                "validation_expand_count"
            ],
            "source_branch_failure_codes": _canonical_sql_json(
                source_payload["failure_codes"],
                label="Branch failure codes",
            ),
            "source_branch_created_at": source_payload["created_at"],
            "source_branch_updated_at": source_payload["updated_at"],
            "source_branch_direction": source_payload["direction"],
            "source_branch_weight_revision": source_payload["weight_revision"],
            "source_branch_code_status": source_payload["branch_code_status"],
            "source_branch_evidence_summary_json": _canonical_sql_json(
                source_payload["branch_evidence_summary"],
                label="Branch evidence summary",
            ),
            "source_branch_infra_block_count": source_payload[
                "infra_block_count"
            ],
            "source_branch_owner_revision": source_branch.owner_revision,
            "source_branch_owner_protocol_generation": (
                _OWNER_PROTOCOL_GENERATION
            ),
            "source_branch_storage_sha256": source_branch.payload_sha256,
        }
    )
    parameters.update(parent_parameters)
    return parameters


def _read_authority_campaign_id(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> str:
    result = _sqlite._execute_participant(
        transaction,
        database_authority,
        _AUTHORITY_CAMPAIGN_ID_SQL,
    )
    description = result.description
    columns = () if description is None else tuple(item[0] for item in description)
    rows = result.fetchall()
    if columns != ("campaign_id",) or len(rows) != 1:
        raise DurableOwnerIntegrityError(
            "generated hypothesis requires one authority Campaign identity"
        )
    campaign_id = rows[0][0]
    if (
        type(campaign_id) is not str
        or not campaign_id
        or campaign_id != campaign_id.strip()
    ):
        raise DurableOwnerIntegrityError(
            "generated hypothesis authority Campaign identity is malformed"
        )
    return campaign_id


def _decode_generated_hypothesis_row(row: Any) -> RevisionedHypothesisRecord:
    try:
        keys = tuple(row.keys())
    except (AttributeError, TypeError) as exc:
        raise DurableOwnerIntegrityError(
            "generated hypothesis row is not a named SQLite row"
        ) from exc
    if keys != _HYPOTHESIS_COLUMNS:
        raise DurableOwnerIntegrityError(
            "generated hypothesis row has incomplete or unexpected columns"
        )
    raw_created_at = row["created_at"]
    if (
        type(raw_created_at) is not str
        or _CANONICAL_UTC_MICROSECOND_RE.fullmatch(raw_created_at) is None
    ):
        raise DurableOwnerIntegrityError(
            "generated hypothesis created_at is not canonical UTC microsecond text"
        )
    try:
        parsed = datetime.fromisoformat(raw_created_at)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(
            "generated hypothesis created_at is invalid"
        ) from exc
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="microseconds") != raw_created_at
    ):
        raise DurableOwnerIntegrityError(
            "generated hypothesis created_at is not canonical UTC microsecond text"
        )
    raw = {column: row[column] for column in _HYPOTHESIS_COLUMNS}
    if raw["owner_protocol_generation"] != _OWNER_PROTOCOL_GENERATION:
        raise DurableOwnerIntegrityError(
            "generated hypothesis owner protocol generation is invalid"
        )
    revision = raw["owner_revision"]
    if type(revision) is not int:
        raise DurableOwnerIntegrityError(
            "generated hypothesis owner revision must be an exact SQLite integer"
        )
    try:
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
            created_at=parsed,
            base_champion_version=raw["base_champion_version"],
            family_id=raw["family_id"],
            family_source=raw["family_source"],
            taxonomy_version=raw["taxonomy_version"],
            predicted_direction=raw["predicted_direction"],
            proposal_digest=raw["proposal_digest"],
        )
        canonical_payload = generated_hypothesis_storage_payload(value)
        token = RevisionedHypothesisRecord.from_generated_value(value, revision)
    except (TypeError, ValueError, OverflowError, DurableOwnerIntegrityError) as exc:
        raise DurableOwnerIntegrityError(
            "generated hypothesis owner row has malformed semantic data"
        ) from exc
    for column, canonical_value in canonical_payload.items():
        stored_value = raw[column]
        if (
            type(stored_value) is not type(canonical_value)
            or stored_value != canonical_value
        ):
            raise DurableOwnerIntegrityError(
                f"generated hypothesis owner column is not canonical: {column}"
            )
    return token


def _row_uses_generated_timestamp_protocol(row: Any) -> bool:
    try:
        raw_created_at = row["created_at"]
    except (IndexError, KeyError, TypeError) as exc:
        raise DurableOwnerIntegrityError(
            "generated-aware hypothesis row has no creation timestamp"
        ) from exc
    return (
        type(raw_created_at) is str
        and _CANONICAL_UTC_MICROSECOND_RE.fullmatch(raw_created_at) is not None
    )


def _validate_hypothesis_id(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(
            "hypothesis ID must be a non-empty exact string"
        )
    return value


def _validate_branch_id(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(
            "hypothesis Branch ID must be a non-empty exact string"
        )
    return value


def _decode_hypothesis_snapshot_rows(
    rows: tuple[object, ...],
) -> tuple[RevisionedHypothesisRecord, ...]:
    decoded: list[RevisionedHypothesisRecord] = []
    owner_ids: set[str] = set()
    for row in rows:
        token = _decode_hypothesis_row(row)
        if token.hypothesis_id in owner_ids:
            raise DurableOwnerIntegrityError(
                "hypothesis snapshot returned duplicate durable owners"
            )
        owner_ids.add(token.hypothesis_id)
        decoded.append(token)
    return tuple(decoded)


def _decode_branch_hypotheses(
    rows: tuple[object, ...],
    branch_id: str,
) -> tuple[RevisionedHypothesisRecord, ...]:
    decoded = _decode_hypothesis_snapshot_rows(rows)
    if any(token.value().branch_id != branch_id for token in decoded):
        raise DurableOwnerIntegrityError(
            "hypothesis Branch query returned another Branch's owner"
        )
    return tuple(sorted(decoded, key=lambda token: token.hypothesis_id))


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
        raise DurableOwnerIntegrityError("hypothesis creation time must be a string")
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
