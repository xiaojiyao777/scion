"""Inherited observation reuse and read-receipt matching."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from scion.proposal.agentic_utils import _drop_empty_dict, _sanitize_agentic_value
from scion.proposal.tools import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
)

from scion.proposal.agentic_observation_ledger.digests import (
    current_source_digest,
    normalize_tool_args,
    requested_max_chars,
)
from scion.proposal.agentic_observation_ledger.models import (
    ACTIVE_SOLVER_METADATA_TOOLS,
    REUSABLE_CONTEXT_TOOLS,
)
from scion.proposal.agentic_observation_ledger.payloads import (
    read_receipt_from_entry,
)
from scion.proposal.agentic_observation_ledger.utils import (
    coerce_int,
    inherited_ledger_entries,
    logical_phase,
    normalize_path,
    source_for_receipt,
)


def already_observed_from_inherited_ledger(
    state: Any,
    context: ProposalToolContext,
    *,
    tool_name: str,
    args: Mapping[str, Any],
    tool_call_id: str,
) -> ProposalObservation | None:
    if tool_name not in REUSABLE_CONTEXT_TOOLS:
        return None
    phase = logical_phase(state)
    if phase not in {"code", "repair"}:
        return None
    normalized_args = normalize_tool_args(tool_name, args)
    for entry in reversed(inherited_ledger_entries(state)):
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("tool_name") or "") != tool_name:
            continue
        reusable_by = {
            str(item)
            for item in entry.get("reusable_by_phases", ())
            if str(item).strip()
        }
        if phase not in reusable_by:
            continue
        if not _entry_matches_args(entry, tool_name, normalized_args):
            continue
        current_digest = current_source_digest(context, tool_name, normalized_args)
        if not _entry_digest_matches(entry, current_digest):
            continue
        if not _entry_coverage_satisfies(entry, tool_name, normalized_args):
            continue
        return _already_observed_observation(
            context,
            entry,
            tool_name=tool_name,
            normalized_args=normalized_args,
            tool_call_id=tool_call_id,
            current_digest=current_digest,
        )
    return None


def inherited_ledger_read_budget_paths(state: Any) -> set[str]:
    paths: set[str] = set()
    for entry in inherited_ledger_entries(state):
        if not isinstance(entry, Mapping):
            continue
        if entry.get("tool_name") != "context.read_algorithm_file":
            continue
        path = normalize_path(entry.get("file_path"))
        if path:
            paths.add(path)
    return paths


def _already_observed_observation(
    context: ProposalToolContext,
    entry: Mapping[str, Any],
    *,
    tool_name: str,
    normalized_args: Mapping[str, Any],
    tool_call_id: str,
    current_digest: Any,
) -> ProposalObservation:
    source_observation_id = str(entry.get("observation_id") or "")
    coverage = entry.get("coverage") if isinstance(entry.get("coverage"), Mapping) else {}
    payload = _drop_empty_dict(
        {
            "already_observed": True,
            "source_observation_id": source_observation_id,
            "source_phase": entry.get("phase"),
            "source_proposal_phase": entry.get("proposal_phase"),
            "tool_name": tool_name,
            "normalized_args": dict(normalized_args),
            "file_path": entry.get("file_path") or normalized_args.get("file_path"),
            "symbol": entry.get("symbol") or normalized_args.get("symbol"),
            "digest": entry.get("digest"),
            "source_digest": entry.get("source_digest"),
            "current_source_digest": current_digest,
            "max_chars": coverage.get("max_chars") or entry.get("max_chars"),
            "truncated": coverage.get("truncated") or entry.get("truncated"),
            "coverage": coverage,
            "artifact_ref": entry.get("artifact_ref"),
            "evidence_ref": entry.get("evidence_ref") or source_observation_id,
            "reusable_by_phases": list(entry.get("reusable_by_phases") or ()),
            "read_receipt": read_receipt_from_entry(entry),
            "source": source_for_receipt(entry),
            "readable": True,
            "active": entry.get("active"),
            "role": entry.get("role"),
            "module": entry.get("module"),
            "active_algorithm_facts": entry.get("active_algorithm_facts"),
            "fact_packet_digest": entry.get("fact_packet_digest"),
            "snapshot_digest": entry.get("snapshot_digest"),
        }
    )
    return ProposalObservation(
        observation_id=_receipt_observation_id(source_observation_id, tool_call_id),
        session_id=context.session_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        observation_type="already_observed",
        summary=(
            "Already observed unchanged source in an inherited APS phase ledger; "
            "returning compact read receipt instead of duplicating the payload. "
            "Do not read this same file again for source; call branch-state or "
            "symbol tools only if that different information is needed."
        ),
        structured_payload=_sanitize_agentic_value(payload),
        artifact_ref=str(entry.get("artifact_ref") or "") or None,
        exposure_level=ProposalExposureLevel.CHAMPION_CODE,
    )


def _receipt_observation_id(source_observation_id: str, tool_call_id: str) -> str:
    digest = hashlib.sha256(
        f"{source_observation_id}:{tool_call_id}".encode("utf-8")
    ).hexdigest()[:12]
    return f"obs-reuse-{digest}"


def _entry_matches_args(
    entry: Mapping[str, Any],
    tool_name: str,
    normalized_args: Mapping[str, Any],
) -> bool:
    if tool_name in ACTIVE_SOLVER_METADATA_TOOLS:
        surface = str(normalized_args.get("surface") or "solver_design")
        observed = entry.get("normalized_args")
        observed_surface = (
            str(observed.get("surface") or "solver_design")
            if isinstance(observed, Mapping)
            else "solver_design"
        )
        return surface == observed_surface
    if tool_name == "context.read_algorithm_file":
        return normalize_path(entry.get("file_path")) == normalize_path(
            normalized_args.get("file_path")
        )
    if tool_name == "context.read_algorithm_symbol":
        return (
            normalize_path(entry.get("file_path"))
            == normalize_path(normalized_args.get("file_path"))
            and str(entry.get("symbol") or "").strip()
            == str(normalized_args.get("symbol") or "").strip()
        )
    if tool_name == "context.read_surface":
        observed_args = entry.get("normalized_args")
        observed_args = observed_args if isinstance(observed_args, Mapping) else {}
        return (
            str(observed_args.get("surface") or "").strip()
            == str(normalized_args.get("surface") or "").strip()
            and normalize_path(observed_args.get("target_file"))
            == normalize_path(normalized_args.get("target_file"))
        )
    return False


def _entry_digest_matches(entry: Mapping[str, Any], current_digest: Any) -> bool:
    if not current_digest:
        return False
    candidates = {
        str(entry.get("digest") or ""),
        str(entry.get("snapshot_digest") or ""),
        str(entry.get("source_digest_hash") or ""),
    }
    source_digest = entry.get("source_digest")
    if isinstance(source_digest, Mapping):
        candidates.add(str(source_digest.get("snapshot_digest") or ""))
        files = source_digest.get("files")
        if isinstance(files, Mapping):
            candidates.update(str(value) for value in files.values() if value)
    if isinstance(current_digest, Mapping):
        current_values = {
            str(current_digest.get("digest") or ""),
            str(current_digest.get("sha256") or ""),
            str(current_digest.get("snapshot_digest") or ""),
            str(current_digest.get("source_digest_hash") or ""),
        }
    else:
        current_values = {str(current_digest or "")}
    for candidate in {item for item in candidates if item}:
        for current in {item for item in current_values if item}:
            if candidate == current or candidate == current[:16] or candidate[:16] == current:
                return True
    return False


def _entry_coverage_satisfies(
    entry: Mapping[str, Any],
    tool_name: str,
    normalized_args: Mapping[str, Any],
) -> bool:
    if tool_name in ACTIVE_SOLVER_METADATA_TOOLS:
        return True
    coverage = entry.get("coverage") if isinstance(entry.get("coverage"), Mapping) else {}
    requested = requested_max_chars(tool_name, normalized_args)
    if requested <= 0:
        return True
    observed_max = coerce_int(coverage.get("max_chars") or entry.get("max_chars"))
    preview_chars = coerce_int(coverage.get("content_preview_chars"))
    size_chars = coerce_int(coverage.get("size_chars"))
    truncated = bool(coverage.get("truncated") or entry.get("truncated"))
    if coverage.get("coverage_status") == "metadata_only":
        return False
    if not truncated and size_chars is not None and preview_chars is not None:
        if preview_chars >= min(size_chars, requested):
            return True
        if preview_chars >= size_chars:
            return True
    if observed_max is not None and requested <= observed_max and not truncated:
        return True
    if preview_chars is not None and preview_chars >= requested and not truncated:
        return True
    return False


__all__ = [
    "already_observed_from_inherited_ledger",
    "inherited_ledger_read_budget_paths",
]
