"""Small shared helpers for APS observation ledgers."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_utils import _drop_empty_dict, _limit_string
from scion.proposal.agentic_observation_ledger.models import REUSABLE_CONTEXT_TOOLS


def normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def coerce_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


def logical_phase(state: Any) -> str:
    return str(getattr(state, "_agentic_logical_phase", "") or "hypothesis")


def resume_ledger_entries(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    candidates: list[Any] = []
    for container in (value, value.get("resume")):
        if not isinstance(container, Mapping):
            continue
        ledger = container.get("observation_ledger")
        if isinstance(ledger, Mapping):
            candidates.append(ledger.get("observations"))
        inherited = container.get("inherited_observation_ledger")
        if isinstance(inherited, Mapping):
            candidates.append(inherited.get("observations"))
    entries: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, (list, tuple)):
            continue
        for item in candidate:
            if isinstance(item, Mapping):
                entries.append(dict(item))
    return entries


def inherited_ledger_entries(state: Any) -> list[Mapping[str, Any]]:
    entries = getattr(state, "_inherited_observation_ledger", None)
    return entries if isinstance(entries, list) else []


def reusable_by_phases(observation: Any, *, phase: str) -> list[str]:
    if observation.is_error or observation.tool_name not in REUSABLE_CONTEXT_TOOLS:
        return []
    if phase == "hypothesis":
        return ["code", "repair"]
    if phase == "code":
        return ["repair"]
    return []


def file_path_from_observation(
    payload: Mapping[str, Any],
    normalized_args: Mapping[str, Any],
) -> str:
    return normalize_path(
        payload.get("file_path")
        or normalized_args.get("file_path")
        or payload.get("target_file")
        or normalized_args.get("target_file")
    )


def symbol_from_observation(
    payload: Mapping[str, Any],
    normalized_args: Mapping[str, Any],
) -> str:
    return str(payload.get("symbol") or normalized_args.get("symbol") or "").strip()


def compact_string_list(value: Any, limit: int, max_chars: int) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in list(value)[:limit]:
        text = _limit_string(item, max_chars)
        if text:
            result.append(text)
    return result


def compact_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty_dict(
        {
            "source": value.get("source"),
            "branch_id": value.get("branch_id"),
            "base_champion_hash": value.get("base_champion_hash"),
            "champion_version": value.get("champion_version"),
            "champion_code_snapshot_hash": value.get("champion_code_snapshot_hash"),
        }
    )


def source_for_receipt(entry: Mapping[str, Any]) -> str:
    source_digest = entry.get("source_digest")
    if isinstance(source_digest, Mapping) and source_digest.get("source"):
        return str(source_digest.get("source"))
    provenance = entry.get("provenance")
    if isinstance(provenance, Mapping) and provenance.get("source"):
        return str(provenance.get("source"))
    return ""


def latest_context_policy_id(entries: list[Mapping[str, Any]]) -> str:
    for entry in reversed(entries):
        stale_if = entry.get("stale_if")
        if isinstance(stale_if, Mapping) and stale_if.get("context_policy_id"):
            return str(stale_if.get("context_policy_id"))
    return ""


__all__ = [
    "coerce_int",
    "compact_provenance",
    "compact_string_list",
    "file_path_from_observation",
    "inherited_ledger_entries",
    "latest_context_policy_id",
    "logical_phase",
    "normalize_path",
    "resume_ledger_entries",
    "reusable_by_phases",
    "source_for_receipt",
    "symbol_from_observation",
]
