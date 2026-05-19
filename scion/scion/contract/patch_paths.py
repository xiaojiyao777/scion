"""Patch path and action mapping helpers for ContractGate."""
from __future__ import annotations

from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match


def matches_config_pattern(file_rel: str, pattern: str) -> bool:
    try:
        normalized_pattern = normalize_relative_glob_pattern(pattern)
    except ValueError:
        return False
    return segment_glob_match(file_rel, normalized_pattern)


def patch_action_for_hypothesis_action(action: str) -> str | None:
    return {
        "modify": "modify",
        "create_new": "create",
        "remove": "delete",
    }.get(action)


def hypothesis_action_for_patch_action(action: str) -> str | None:
    return {
        "modify": "modify",
        "create": "create_new",
        "delete": "remove",
    }.get(action)
