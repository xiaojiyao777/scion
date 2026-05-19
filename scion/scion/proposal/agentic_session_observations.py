
"""Observation and prompt-payload serialization helpers for APS."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from scion.core.models import PatchProposal
from scion.proposal.agentic_artifacts import _proposal_payload
from scion.proposal.agentic_code_context import _observation_prompt_payload
from scion.proposal.agentic_models import (
    AgenticEvidenceRef,
    AgenticProposalPhase,
    AgenticProposalSessionState,
)
from scion.proposal.agentic_session_feedback import _observation_satisfies_compact_requirement
from scion.proposal.agentic_utils import _drop_empty_dict, _enum_value, _sanitize_agentic_value
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.tools import ProposalObservation, ProposalToolContext

_AUTHORITATIVE_PREVIEW_TOOL_NAMES = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)
_AUTHORITATIVE_PREVIEW_SELECTION_SOURCES = frozenset({"fallback_selected"})
_HYPOTHESIS_PROMPT_COMPACT_REQUIREMENT_TOOLS = frozenset(
    {
        "feedback.query_screening",
        "feedback.query_runtime",
    }
)
_PATCH_METADATA_FIELDS = frozenset(
    {"premise_check", "premise_check_reason", "repair_attribution"}
)


def _authoritative_preview_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    state: AgenticProposalSessionState,
) -> tuple[ProposalObservation, ...]:
    """Return deterministic self-check previews, excluding planner exploration."""
    ids = _authoritative_preview_observation_ids(state)
    return tuple(
        observation for observation in observations if observation.observation_id in ids
    )


def _authoritative_preview_observation_ids(
    state: AgenticProposalSessionState,
) -> set[str]:
    ids: set[str] = set()
    for event in state.transcript:
        if str(event.phase or "") != AgenticProposalPhase.SELF_CHECK.value:
            continue
        metadata = dict(event.metadata or {})
        if metadata.get("tool_name") not in _AUTHORITATIVE_PREVIEW_TOOL_NAMES:
            continue
        if (
            str(metadata.get("selection_source") or "")
            not in _AUTHORITATIVE_PREVIEW_SELECTION_SOURCES
        ):
            continue
        observation_id = str(metadata.get("observation_id") or "")
        if observation_id:
            ids.add(observation_id)
    return ids


def _is_authoritative_self_check_preview_call(
    name: str,
    phase: AgenticProposalPhase,
    selection_source: str,
) -> bool:
    return (
        phase == AgenticProposalPhase.SELF_CHECK
        and name in _AUTHORITATIVE_PREVIEW_TOOL_NAMES
        and selection_source in _AUTHORITATIVE_PREVIEW_SELECTION_SOURCES
    )


def _evidence_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[AgenticEvidenceRef]:
    return [
        AgenticEvidenceRef(
            observation_id=observation.observation_id,
            exposure_level=str(_enum_value(observation.exposure_level)),
            summary=observation.summary,
        )
        for observation in observations
    ]


def _hypothesis_prompt_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    context: ProposalToolContext | None,
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    for observation in observations:
        if observation.tool_name in _HYPOTHESIS_PROMPT_COMPACT_REQUIREMENT_TOOLS:
            if _observation_satisfies_compact_requirement(context, observation):
                selected.append(observation)
            continue
        selected.append(observation)
    return selected


def _next_prompt_manifest_index(state: AgenticProposalSessionState) -> int:
    current = int(getattr(state, "_prompt_manifest_index", 0)) + 1
    setattr(state, "_prompt_manifest_index", current)
    return current


def _deduplicate_observation_if_already_read(
    state: AgenticProposalSessionState,
    observation: ProposalObservation,
    *,
    tool_name: str,
    args: Mapping[str, Any],
    phase: AgenticProposalPhase,
    args_hash: str,
) -> ProposalObservation:
    if observation.is_error or not str(tool_name).startswith("context."):
        return observation
    payload_digest = stable_digest(observation.structured_payload, length=16)
    source_hash = _observation_source_hash(observation, payload_digest=payload_digest)
    key = (
        str(tool_name),
        str(args_hash),
        phase.value,
        str(source_hash or payload_digest),
    )
    cache = _already_read_cache(state)
    cached = cache.get(key)
    if cached is not None:
        return replace(
            observation,
            observation_type="already_read_ref",
            summary=(
                "Repeated proposal tool call returned an already-read reference "
                "instead of duplicating the full payload."
            ),
            structured_payload=_already_read_payload(
                observation,
                cached,
                args_hash=args_hash,
                phase=phase.value,
                payload_digest=payload_digest,
                source_hash=source_hash,
            ),
            repair_hint=None,
        )
    cache[key] = {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "tool_call_id": observation.tool_call_id,
        "args_hash": args_hash,
        "args_digest": stable_digest(dict(args), length=16),
        "phase": phase.value,
        "payload_digest": payload_digest,
        "source_hash": source_hash,
    }
    return observation


def _already_read_cache(state: AgenticProposalSessionState) -> dict[tuple[str, ...], Any]:
    cache = getattr(state, "_already_read_observation_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(state, "_already_read_observation_cache", cache)
    return cache


def _already_read_payload(
    observation: ProposalObservation,
    cached: Mapping[str, Any],
    *,
    args_hash: str,
    phase: str,
    payload_digest: str,
    source_hash: str,
) -> dict[str, Any]:
    payload = observation.structured_payload
    return _drop_empty_dict(
        {
            "already_read_ref": {
                "observation_id": cached.get("observation_id"),
                "tool_name": cached.get("tool_name"),
                "tool_call_id": cached.get("tool_call_id"),
                "args_hash": args_hash,
                "phase": phase,
                "payload_digest": payload_digest,
                "source_hash": source_hash,
            },
            "deduplicated": True,
            "tool_name": observation.tool_name,
            "surface": _already_read_surface_payload(payload),
            "detail": payload.get("detail") if isinstance(payload, Mapping) else None,
            "section": payload.get("section") if isinstance(payload, Mapping) else None,
            "target_file": (
                payload.get("target_file") if isinstance(payload, Mapping) else None
            ),
            "file_path": payload.get("file_path") if isinstance(payload, Mapping) else None,
            "symbol": payload.get("symbol") if isinstance(payload, Mapping) else None,
            "readable": payload.get("readable") if isinstance(payload, Mapping) else None,
            "source": payload.get("source") if isinstance(payload, Mapping) else None,
        }
    )


def _already_read_surface_payload(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return None
    surface = value.get("surface")
    if isinstance(surface, Mapping):
        return {
            key: surface.get(key)
            for key in ("name", "id", "kind")
            if surface.get(key) is not None
        }
    return surface


def _observation_source_hash(
    observation: ProposalObservation,
    *,
    payload_digest: str,
) -> str:
    source_payload = _observation_source_payload(observation.structured_payload)
    if source_payload:
        return stable_digest(source_payload, length=16)
    return payload_digest


def _observation_source_payload(value: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                if key_text in {"source_digest", "provenance"} and isinstance(
                    child, Mapping
                ):
                    found.setdefault(key_text, _sanitize_agentic_value(dict(child)))
                elif key_text in {
                    "source",
                    "digest",
                    "sha256",
                    "snapshot_digest",
                    "branch_id",
                    "base_champion_hash",
                    "champion_code_snapshot_hash",
                }:
                    found.setdefault(key_text, _sanitize_agentic_value(child))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found


def _patch_payload_for_preview(patch: PatchProposal) -> dict[str, Any]:
    payload = _proposal_payload(patch)
    for field_name in _PATCH_METADATA_FIELDS:
        payload.pop(field_name, None)
    return payload
