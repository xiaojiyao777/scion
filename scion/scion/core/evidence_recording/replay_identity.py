"""Replay identity builders shared by formal evidence artifacts."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable

from scion.core.replay_identity_contract import (
    FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS,
    FORMAL_REPLAY_IDENTITY_SCHEMA,
    UNKNOWN_REPLAY_IDENTITY_VALUE,
    formal_replay_identity_missing_keys as _contract_missing_keys,
)


def stable_patch_digest(changes: Iterable[Any]) -> str:
    """Return the canonical full-file patch digest used for replay identity."""
    payload = []
    for change in changes:
        payload.append(
            {
                "file_path": str(getattr(change, "file_path", "") or ""),
                "action": str(getattr(change, "action", "") or ""),
                "code_sha256": hashlib.sha256(
                    (getattr(change, "code_content", None) or "").encode("utf-8")
                ).hexdigest(),
            }
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def formal_replay_identity_payload(
    *,
    problem_spec_hash: Any,
    split_manifest_hash: Any,
    seed_ledger_hash: Any,
    patch_digest: str,
    selected_surface: Any,
    protocol_version: Any,
    raw_metrics_ref: Any,
    code_hash: Any,
) -> Dict[str, Any]:
    """Build the generic replay identity for formal candidate audit payloads."""
    normalized_patch_digest = str(patch_digest or "").strip()
    raw_values = {
        "problem_spec_hash": _clean_value(problem_spec_hash),
        "split_manifest_hash": _clean_value(split_manifest_hash),
        "seed_ledger_hash": _clean_value(seed_ledger_hash),
        "patch_digest": normalized_patch_digest,
        "patch_hash": normalized_patch_digest,
        "selected_surface": _clean_value(selected_surface),
        "protocol_version": _clean_value(protocol_version),
        "raw_metrics_ref": _clean_value(raw_metrics_ref),
        "code_hash": _clean_value(code_hash),
    }
    missing_keys = [
        key for key in FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS if not raw_values.get(key)
    ]
    status = "degraded" if missing_keys else "complete"
    identity = {
        key: _replay_identity_value(raw_values.get(key))
        for key in FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS
    }
    return {
        "schema": FORMAL_REPLAY_IDENTITY_SCHEMA,
        **identity,
        "missing_identity_keys": missing_keys,
        "missing_keys": missing_keys,
        "identity_status": status,
        "status": status,
        "identity_degraded": bool(missing_keys),
        "degraded_markers": ["missing_replay_identity"] if missing_keys else [],
    }


def formal_replay_identity_missing_keys(
    replay_identity: Dict[str, Any] | None,
) -> list[str]:
    """Return required replay-identity keys that are absent or placeholder-only."""
    return _contract_missing_keys(replay_identity)


def formal_replay_identity_complete(replay_identity: Dict[str, Any] | None) -> bool:
    """Return whether a formal replay identity can be used for materialization."""
    return not formal_replay_identity_missing_keys(replay_identity)


def _clean_value(value: Any) -> str:
    return str(value or "").strip()


def _replay_identity_value(value: Any) -> str:
    normalized = _clean_value(value)
    return normalized or UNKNOWN_REPLAY_IDENTITY_VALUE
