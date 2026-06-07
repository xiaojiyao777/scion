"""Recording helpers for APS observation ledgers."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _enum_value,
    _limit_string,
    _sanitize_agentic_value,
)
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.tools import ProposalObservation, ProposalToolContext

from scion.proposal.agentic_observation_ledger.digests import (
    coverage_payload,
    normalize_tool_args,
    primary_digest,
    snapshot_digest_from_source,
    source_digest_payload,
)
from scion.proposal.agentic_observation_ledger.models import REUSABLE_CONTEXT_TOOLS
from scion.proposal.agentic_observation_ledger.payloads import (
    compact_active_algorithm_facts,
)
from scion.proposal.agentic_observation_ledger.utils import (
    compact_provenance,
    file_path_from_observation,
    logical_phase,
    resume_ledger_entries,
    reusable_by_phases,
    symbol_from_observation,
)


def initialize_agentic_observation_ledger_state(
    state: Any,
    request: Any,
) -> None:
    """Attach inherited ledger state to a fresh session state object."""

    phase = "code" if getattr(request, "approved_hypothesis", None) else "hypothesis"
    setattr(state, "_agentic_logical_phase", phase)
    inherited = resume_ledger_entries(getattr(request, "resume_context", None))
    setattr(state, "_inherited_observation_ledger", inherited)
    if inherited:
        state.note(
            state.phase,
            "Loaded inherited APS observation ledger.",
            metadata={
                "observation_ledger_entries": len(inherited),
                "reusable_phase": phase,
            },
        )


def record_agentic_ledger_observation(
    state: Any,
    context: ProposalToolContext,
    observation: ProposalObservation,
    *,
    args: Mapping[str, Any],
    proposal_phase: str,
    prompt_visible_chars: int | None = None,
    selection_source: str | None = None,
) -> None:
    """Record one compact observation ledger entry on session state."""

    if observation.tool_name not in REUSABLE_CONTEXT_TOOLS:
        return
    entry = build_agentic_ledger_observation(
        context,
        observation,
        args=args,
        logical_phase=logical_phase(state),
        proposal_phase=proposal_phase,
        prompt_visible_chars=prompt_visible_chars,
        selection_source=selection_source,
    )
    if entry:
        state.observation_ledger.append(entry)


def build_agentic_ledger_observation(
    context: ProposalToolContext,
    observation: ProposalObservation,
    *,
    args: Mapping[str, Any],
    logical_phase: str,
    proposal_phase: str,
    prompt_visible_chars: int | None = None,
    selection_source: str | None = None,
) -> dict[str, Any]:
    payload = (
        observation.structured_payload
        if isinstance(observation.structured_payload, Mapping)
        else {}
    )
    normalized_args = normalize_tool_args(observation.tool_name, args)
    coverage = coverage_payload(observation.tool_name, payload, normalized_args)
    source_digest = source_digest_payload(observation.tool_name, payload)
    digest = primary_digest(payload, source_digest)
    payload_hash = stable_digest(payload, length=16)
    novelty = _observation_novelty(
        observation=observation,
        payload=payload,
        digest=digest,
    )
    prompt_payload_hash = stable_digest(
        {
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "tool_call_id": observation.tool_call_id,
            "structured_payload": payload,
        },
        length=16,
    )
    active_facts = compact_active_algorithm_facts(
        payload.get("active_algorithm_facts")
    )
    read_receipt = (
        payload.get("read_receipt")
        if isinstance(payload.get("read_receipt"), Mapping)
        else {}
    )
    entry = _drop_empty_dict(
        {
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "normalized_args": normalized_args,
            "args_hash": stable_digest(normalized_args, length=16),
            "target_id": read_receipt.get("target_id")
            or normalized_args.get("registry_id")
            or normalized_args.get("slice_id"),
            "registry_id": payload.get("registry_id")
            or normalized_args.get("registry_id"),
            "slice_id": payload.get("slice_id")
            or normalized_args.get("slice_id"),
            "file_path": file_path_from_observation(payload, normalized_args),
            "symbol": symbol_from_observation(payload, normalized_args),
            "digest": digest,
            "result_digest": digest,
            "tool_result_novelty": novelty,
            "result_novelty": novelty,
            "payload_hash": payload_hash,
            "source_digest": source_digest,
            "source_digest_hash": stable_digest(source_digest or digest, length=16),
            "fact_packet_digest": active_facts.get("fact_packet_digest"),
            "fact_ids": active_facts.get("fact_ids"),
            "snapshot_digest": snapshot_digest_from_source(source_digest),
            "max_chars": coverage.get("max_chars"),
            "truncated": coverage.get("truncated"),
            "coverage": coverage,
            "artifact_ref": observation.artifact_ref,
            "evidence_ref": observation.observation_id,
            "phase": logical_phase,
            "proposal_phase": proposal_phase,
            "selection_source": selection_source,
            "reusable_by_phases": reusable_by_phases(
                observation,
                phase=logical_phase,
            ),
            "summary": _limit_string(observation.summary, 300),
            "observation_type": observation.observation_type,
            "exposure_level": _enum_value(observation.exposure_level),
            "taint": _enum_value(observation.taint),
            "is_error": observation.is_error,
            "failure_code": _enum_value(observation.failure_code),
            "prompt_visible_chars": prompt_visible_chars,
            "visible_text_chars": prompt_visible_chars,
            "visible_text_hash": (
                prompt_payload_hash
                if prompt_visible_chars is not None and prompt_visible_chars > 0
                else None
            ),
            "rendered_visibility_flag": (
                None if prompt_visible_chars is None else prompt_visible_chars > 0
            ),
            "omitted": None if prompt_visible_chars is None else prompt_visible_chars <= 0,
            "active_algorithm_facts": active_facts,
            "provenance": compact_provenance(payload.get("provenance")),
            "stale_if": _drop_empty_dict(
                {
                    "champion_version": getattr(context.champion, "version", None),
                    "champion_code_snapshot_hash": getattr(
                        context.champion,
                        "code_snapshot_hash",
                        None,
                    ),
                    "problem_spec_hash": context.problem_spec_hash,
                    "context_policy_id": getattr(context.policy, "context_policy_id", ""),
                }
            ),
        }
    )
    return _sanitize_agentic_value(entry)


def _observation_novelty(
    *,
    observation: ProposalObservation,
    payload: Mapping[str, Any],
    digest: Mapping[str, Any] | str,
) -> str:
    del digest
    if _ledger_payload_empty(observation, payload):
        return "empty"
    if str(observation.observation_type or "") in {
        "already_read_ref",
        "already_observed",
    }:
        return "duplicate_same_digest"
    if _ledger_payload_summary_only(observation, payload):
        return "summary_only"
    return "new"


def _ledger_payload_empty(
    observation: ProposalObservation,
    payload: Mapping[str, Any],
) -> bool:
    if observation.tool_name == "feedback.query_screening":
        status = payload.get("screening_observation_status")
        if isinstance(status, Mapping):
            return not bool(status.get("usable"))
        return int(payload.get("matched_screening_step_count") or 0) <= 0
    if observation.tool_name == "feedback.query_runtime":
        status = payload.get("runtime_observation_status")
        if isinstance(status, Mapping):
            return not bool(status.get("usable"))
    if payload:
        return False
    return not str(observation.summary or "").strip()


def _ledger_payload_summary_only(
    observation: ProposalObservation,
    payload: Mapping[str, Any],
) -> bool:
    if str(observation.observation_type or "") == "tool_skipped":
        return True
    if not payload and str(observation.summary or "").strip():
        return True
    return set(payload).issubset({"summary", "status", "message", "note"})


__all__ = [
    "build_agentic_ledger_observation",
    "initialize_agentic_observation_ledger_state",
    "record_agentic_ledger_observation",
]
