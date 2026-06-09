"""Shared replay-identity contract constants."""

from __future__ import annotations

from typing import Any, Mapping

UNKNOWN_REPLAY_IDENTITY_VALUE = "unknown"
FORMAL_REPLAY_IDENTITY_SCHEMA = "scion.formal_replay_identity.v1"
FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS = (
    "problem_spec_hash",
    "split_manifest_hash",
    "seed_ledger_hash",
    "patch_digest",
    "patch_hash",
    "selected_surface",
    "protocol_version",
    "raw_metrics_ref",
    "code_hash",
)


def formal_replay_identity_missing_keys(
    replay_identity: Mapping[str, Any] | None,
) -> list[str]:
    """Return required replay-identity keys that are absent or placeholder-only."""
    if replay_identity is None:
        return ["replay_identity"]
    explicit = replay_identity.get("missing_identity_keys")
    if explicit is None:
        explicit = replay_identity.get("missing_keys")
    if isinstance(explicit, str):
        missing = [explicit] if explicit else []
    elif isinstance(explicit, (list, tuple, set)):
        missing = [str(item) for item in explicit if str(item)]
    else:
        missing = []
    for key in FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS:
        value = str(replay_identity.get(key) or "").strip()
        if not value or value == UNKNOWN_REPLAY_IDENTITY_VALUE:
            missing.append(key)
    return list(dict.fromkeys(missing))


__all__ = [
    "FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS",
    "FORMAL_REPLAY_IDENTITY_SCHEMA",
    "UNKNOWN_REPLAY_IDENTITY_VALUE",
    "formal_replay_identity_missing_keys",
]
