"""Pure frozen-v1 projections for durable Branch and hypothesis owners.

This module owns only value projection and SQLite row decoding.  It deliberately
contains no persistence, transaction, revision, or lease behavior so every
durable workflow can share the same byte-compatible owner representation.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from scion.core.models import Branch, BranchState, HypothesisRecord

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
STABLE_SOURCE_HYPOTHESIS_SCHEMA = "stable-source-hypothesis.v1"
_HYPOTHESIS_ACTIONS = frozenset({"modify", "create_new", "remove"})

__all__ = (
    "STABLE_SOURCE_HYPOTHESIS_SCHEMA",
    "branch_from_payload",
    "branch_payload_from_row",
    "branch_to_payload",
    "hypothesis_payload_from_row",
    "hypothesis_to_payload",
    "stable_source_hypothesis_payload",
    "stable_source_hypothesis_payload_from_row",
)


def branch_to_payload(branch: Branch) -> dict[str, Any]:
    """Project a Branch to its frozen v1 durable payload."""

    return {
        "branch_id": branch.branch_id,
        "state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "base_champion_hash": branch.base_champion_hash,
        "lineage_id": branch.lineage_id or branch.branch_id,
        "current_code_hash": branch.current_code_hash,
        "last_clean_code_hash": branch.last_clean_code_hash,
        "screening_expand_count": branch.screening_expand_count,
        "validation_expand_count": branch.validation_expand_count,
        "failure_codes": list(branch.failure_codes or ()),
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
        "direction": branch.direction,
        "weight_revision": branch.weight_revision,
        "branch_code_status": branch.branch_code_status,
        "branch_evidence_summary": _jsonable(branch.branch_evidence_summary or {}),
        "infra_block_count": branch.infra_block_count,
    }


def branch_from_payload(payload: Mapping[str, Any]) -> Branch:
    """Reconstruct a Branch using the frozen v1 historical fallbacks."""

    return Branch(
        branch_id=str(payload["branch_id"]),
        state=BranchState(str(payload["state"])),
        base_champion_id=int(payload["base_champion_id"]),
        base_champion_hash=str(payload["base_champion_hash"]),
        lineage_id=str(payload.get("lineage_id") or payload["branch_id"]),
        current_code_hash=payload.get("current_code_hash"),
        last_clean_code_hash=payload.get("last_clean_code_hash"),
        screening_expand_count=int(payload.get("screening_expand_count") or 0),
        validation_expand_count=int(payload.get("validation_expand_count") or 0),
        failure_codes=list(payload.get("failure_codes") or ()),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        direction=payload.get("direction"),
        weight_revision=int(payload.get("weight_revision") or 0),
        branch_code_status=str(payload.get("branch_code_status") or "clean"),
        branch_evidence_summary=dict(payload.get("branch_evidence_summary") or {}),
        infra_block_count=int(payload.get("infra_block_count") or 0),
    )


def hypothesis_to_payload(record: HypothesisRecord) -> dict[str, Any]:
    """Project a hypothesis record to its frozen v1 durable payload."""

    return {
        "hypothesis_id": record.hypothesis_id,
        "branch_id": record.branch_id,
        "change_locus": record.change_locus,
        "action": record.action,
        "status": record.status,
        "target_file": record.target_file,
        "parent_hypothesis_id": record.parent_hypothesis_id,
        "suggested_weight": record.suggested_weight,
        "hypothesis_text": record.hypothesis_text,
        "created_at": record.created_at.isoformat(),
        "base_champion_version": record.base_champion_version,
        "family_id": record.family_id,
        "family_source": record.family_source,
        "taxonomy_version": record.taxonomy_version,
        "predicted_direction": record.predicted_direction,
    }


def stable_source_hypothesis_payload(record: HypothesisRecord) -> dict[str, Any]:
    """Project only the stable scientific identity of a source hypothesis.

    Mutable lifecycle and observational fields such as status, creation time,
    diagnostics, runtime facts, public summaries, and storage revisions are
    intentionally absent.  Pair creation validates those values separately.
    The schema field is the domain separator for canonical-payload hashing.
    """

    return _stable_source_hypothesis_payload(
        hypothesis_id=record.hypothesis_id,
        branch_id=record.branch_id,
        parent_hypothesis_id=record.parent_hypothesis_id,
        proposal_digest=record.proposal_digest,
        base_champion_version=record.base_champion_version,
        change_locus=record.change_locus,
        action=record.action,
        target_file=record.target_file,
        suggested_weight=record.suggested_weight,
        predicted_direction=record.predicted_direction,
        family_id=record.family_id,
        family_source=record.family_source,
        taxonomy_version=record.taxonomy_version,
    )


def stable_source_hypothesis_payload_from_row(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """Strictly project stable source-H identity from its authoritative row.

    Unlike the frozen v1 historical row decoder, this new identity projection
    applies no legacy defaults or string coercions.
    """

    return _stable_source_hypothesis_payload(
        hypothesis_id=row["hypothesis_id"],
        branch_id=row["branch_id"],
        parent_hypothesis_id=row["parent_hypothesis_id"],
        proposal_digest=row["proposal_digest"],
        base_champion_version=row["base_champion_version"],
        change_locus=row["change_locus"],
        action=row["action"],
        target_file=row["target_file"],
        suggested_weight=row["suggested_weight"],
        predicted_direction=row["predicted_direction"],
        family_id=row["family_id"],
        family_source=row["family_source"],
        taxonomy_version=row["taxonomy_version"],
    )


def _stable_source_hypothesis_payload(
    *,
    hypothesis_id: Any,
    branch_id: Any,
    parent_hypothesis_id: Any,
    proposal_digest: Any,
    base_champion_version: Any,
    change_locus: Any,
    action: Any,
    target_file: Any,
    suggested_weight: Any,
    predicted_direction: Any,
    family_id: Any,
    family_source: Any,
    taxonomy_version: Any,
) -> dict[str, Any]:
    hypothesis_id = _required_text(hypothesis_id, "source hypothesis ID")
    branch_id = _required_text(branch_id, "source hypothesis Branch ID")
    change_locus = _required_text(change_locus, "source hypothesis change locus")
    action = _required_text(action, "source hypothesis action")
    if action not in _HYPOTHESIS_ACTIONS:
        raise ValueError("source hypothesis action is invalid")
    parent_hypothesis_id = _optional_text(
        parent_hypothesis_id,
        "source hypothesis parent ID",
    )
    target_file = _optional_text(target_file, "source hypothesis target file")
    family_id = _optional_text(family_id, "source hypothesis family ID")
    family_source = _optional_text(
        family_source,
        "source hypothesis family source",
    )
    taxonomy_version = _optional_text(
        taxonomy_version,
        "source hypothesis taxonomy version",
    )
    if (
        not isinstance(proposal_digest, str)
        or _SHA256_RE.fullmatch(proposal_digest) is None
    ):
        raise ValueError("source hypothesis proposal digest must be a full SHA-256")
    if type(base_champion_version) is not int or base_champion_version < 0:
        raise ValueError("source hypothesis base champion version must be nonnegative")
    if not isinstance(predicted_direction, str) or predicted_direction not in {
        "improve",
        "tradeoff",
        "exploratory",
    }:
        raise ValueError("source hypothesis predicted direction is invalid")
    if suggested_weight is not None and (
        isinstance(suggested_weight, bool)
        or not isinstance(suggested_weight, (int, float))
        or not math.isfinite(suggested_weight)
    ):
        raise ValueError("source hypothesis suggested weight must be finite")
    canonical_suggested_weight = (
        None if suggested_weight is None else float(suggested_weight)
    )
    if canonical_suggested_weight == 0.0:
        # SQLite REAL normalizes IEEE negative zero on durable round-trip.  The
        # in-memory projection must emit the same canonical JSON number.
        canonical_suggested_weight = 0.0
    return {
        "schema_version": STABLE_SOURCE_HYPOTHESIS_SCHEMA,
        "hypothesis_id": hypothesis_id,
        "branch_id": branch_id,
        "parent_hypothesis_id": parent_hypothesis_id,
        "proposal_digest": proposal_digest,
        "base_champion_version": base_champion_version,
        "change_locus": change_locus,
        "action": action,
        "target_file": target_file,
        "suggested_weight": canonical_suggested_weight,
        "predicted_direction": predicted_direction,
        "family_id": family_id,
        "family_source": family_source,
        "taxonomy_version": taxonomy_version,
    }


def branch_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Decode one durable Branch row through the canonical v1 projection."""

    return branch_to_payload(
        Branch(
            branch_id=row["branch_id"],
            state=BranchState(row["state"]),
            base_champion_id=row["base_champion_id"],
            base_champion_hash=row["base_champion_hash"],
            lineage_id=row["lineage_id"] or row["branch_id"],
            current_code_hash=row["current_code_hash"],
            last_clean_code_hash=row["last_clean_code_hash"],
            screening_expand_count=row["screening_expand_count"] or 0,
            validation_expand_count=row["validation_expand_count"] or 0,
            failure_codes=json.loads(row["failure_codes"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            direction=row["direction"],
            weight_revision=row["weight_revision"] or 0,
            branch_code_status=row["branch_code_status"] or "clean",
            branch_evidence_summary=json.loads(
                row["branch_evidence_summary_json"] or "{}"
            ),
            infra_block_count=row["infra_block_count"] or 0,
        )
    )


def hypothesis_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Decode one durable hypothesis row through the canonical v1 projection."""

    return hypothesis_to_payload(
        HypothesisRecord(
            hypothesis_id=row["hypothesis_id"],
            branch_id=row["branch_id"] or "",
            change_locus=row["change_locus"] or "",
            action=row["action"] or "modify",
            status=row["status"] or "active",
            target_file=row["target_file"],
            parent_hypothesis_id=row["parent_hypothesis_id"],
            suggested_weight=row["suggested_weight"],
            hypothesis_text=row["hypothesis_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
            base_champion_version=row["base_champion_version"] or 0,
            family_id=row["family_id"],
            family_source=row["family_source"],
            taxonomy_version=row["taxonomy_version"],
            predicted_direction=row["predicted_direction"] or "exploratory",
        )
    )


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: Any, label: str) -> str | None:
    if value is not None and (
        not isinstance(value, str) or not value or value != value.strip()
    ):
        raise ValueError(f"{label} must be a string or null")
    return value
