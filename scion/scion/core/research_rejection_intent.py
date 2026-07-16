"""Immutable identity contract for research-rejection completion intents."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping


RESEARCH_REJECTION_COMPLETION_SCHEMA = "research-rejection-completion-intent.v1"
VALID_RESEARCH_REJECTION_STATUSES = frozenset(
    {"prepared", "state_committed", "committed"}
)
VALID_RESEARCH_REJECTION_PHASES = frozenset(
    {"hypothesis_contract", "patch_contract", "verification"}
)


@dataclass(frozen=True)
class ResearchRejectionCompletionIntent:
    completion_id: str
    status: str
    payload: Mapping[str, Any]

    @property
    def campaign_id(self) -> str:
        return str(self.payload["campaign_id"])

    @property
    def provider_attempt_id(self) -> str:
        return str(self.payload["provider_attempt"]["attempt_id"])

    @property
    def branch_id(self) -> str:
        return str(self.payload["branch_id"])

    @property
    def hypothesis_id(self) -> str:
        return str(self.payload["hypothesis_id"])

    @property
    def rejection_phase(self) -> str:
        return str(self.payload["rejection_phase"])

    @property
    def workspace_disposition(self) -> str:
        return str(self.payload["workspace_disposition"])


def intent_from_row(row: sqlite3.Row) -> ResearchRejectionCompletionIntent:
    try:
        payload = json.loads(row["intent_json"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("research rejection intent JSON is invalid") from exc
    core_payload = dict(payload) if isinstance(payload, dict) else {}
    completion_id = str(core_payload.pop("completion_id", ""))
    archive_ref = core_payload.pop("archive_ref", None)
    phase = payload.get("rejection_phase") if isinstance(payload, dict) else None
    rejected_patch_digest = (
        payload.get("rejected_patch_digest") if isinstance(payload, dict) else None
    )
    if (
        row["schema_version"] != RESEARCH_REJECTION_COMPLETION_SCHEMA
        or not isinstance(payload, dict)
        or payload.get("schema_version") != RESEARCH_REJECTION_COMPLETION_SCHEMA
        or row["status"] not in VALID_RESEARCH_REJECTION_STATUSES
        or stable_digest(payload) != row["intent_sha256"]
        or completion_id != row["completion_id"]
        or completion_id_for_payload(core_payload) != completion_id
        or archive_ref
        != (
            f"archive/research-rejection-{completion_id}"
            if payload.get("rejected_candidate") is not None
            else None
        )
        or payload.get("campaign_id") != row["campaign_id"]
        or payload.get("provider_attempt", {}).get("attempt_id")
        != row["provider_attempt_id"]
        or payload.get("branch_id") != row["branch_id"]
        or payload.get("hypothesis_id") != row["hypothesis_id"]
        or payload.get("rejection_phase") != row["rejection_phase"]
        or phase not in VALID_RESEARCH_REJECTION_PHASES
        or not _valid_phase_patch_digest(phase, rejected_patch_digest)
        or not _valid_sha256(payload.get("hypothesis_proposal_digest"))
        or stable_digest(payload.get("source_branch"))
        != payload.get("source_branch_sha256")
        or stable_digest(payload.get("target_branch"))
        != payload.get("target_branch_sha256")
        or stable_digest(payload.get("source_hypothesis"))
        != payload.get("source_hypothesis_sha256")
        or stable_digest(payload.get("target_hypothesis"))
        != payload.get("target_hypothesis_sha256")
    ):
        raise RuntimeError("research rejection completion intent is invalid")
    return ResearchRejectionCompletionIntent(
        completion_id=completion_id,
        status=row["status"],
        payload=payload,
    )


def validated_clean_parent(value: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("clean code parent identity must be a mapping")
    kind = str(value.get("kind") or "")
    if kind not in {"branch_workspace", "champion_snapshot"}:
        raise ValueError("clean code parent kind is invalid")
    return {
        "kind": kind,
        "ref": _validated_relative_ref(
            value.get("ref"),
            prefix=("workspaces/" if kind == "branch_workspace" else "champions/"),
            label="clean code parent",
        ),
        "code_hash": validated_sha256(value.get("code_hash"), "clean code parent"),
        "snapshot_hash": validated_sha256(
            value.get("snapshot_hash"),
            "clean code parent snapshot",
        ),
    }


def validated_rejected_candidate(
    value: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("rejected candidate identity must be a mapping")
    candidate = {
        "workspace_ref": _validated_relative_ref(
            value.get("workspace_ref"),
            prefix="candidate_workspaces/",
            label="rejected candidate",
        ),
        "code_hash": validated_sha256(value.get("code_hash"), "rejected candidate"),
        "snapshot_hash": validated_sha256(
            value.get("snapshot_hash"),
            "rejected candidate snapshot",
        ),
        "patch_digest": validated_sha256(
            value.get("patch_digest"),
            "rejected candidate patch",
        ),
        "hypothesis_id": str(value.get("hypothesis_id") or ""),
    }
    if not candidate["hypothesis_id"]:
        raise ValueError("rejected candidate hypothesis identity is required")
    return candidate


def jsonable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("research rejection diagnostics must be a mapping")
    decoded = json.loads(canonical_json(value))
    if not isinstance(decoded, dict):
        raise TypeError("research rejection diagnostics must be a mapping")
    return decoded


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stable_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def completion_id_for_payload(payload: Mapping[str, Any]) -> str:
    return stable_digest(payload)


def _validated_relative_ref(value: Any, *, prefix: str, label: str) -> str:
    ref = str(value or "")
    path = PurePosixPath(ref)
    if (
        not ref.startswith(prefix)
        or path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != ref
    ):
        raise ValueError(f"{label} ref is invalid")
    return ref


def validated_sha256(value: Any, label: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{label} SHA-256 is invalid")
    return digest


def _valid_sha256(value: Any) -> bool:
    try:
        validated_sha256(value, "research rejection identity")
    except ValueError:
        return False
    return True


def _valid_phase_patch_digest(phase: Any, value: Any) -> bool:
    if phase == "patch_contract":
        return _valid_sha256(value)
    return value is None


__all__ = [
    "RESEARCH_REJECTION_COMPLETION_SCHEMA",
    "VALID_RESEARCH_REJECTION_PHASES",
    "ResearchRejectionCompletionIntent",
    "canonical_json",
    "completion_id_for_payload",
    "intent_from_row",
    "jsonable_mapping",
    "stable_digest",
    "validated_clean_parent",
    "validated_rejected_candidate",
    "validated_sha256",
]
