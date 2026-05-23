"""Payload envelope and resume compaction helpers for observation ledgers."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_utils import _drop_empty_dict, _limit_string

from scion.proposal.agentic_observation_ledger.models import (
    LEDGER_SCHEMA_VERSION,
    AgenticObservationLedger,
)
from scion.proposal.agentic_observation_ledger.utils import (
    compact_string_list,
    latest_context_policy_id,
)


def agentic_observation_ledger_payload(
    state: Any,
    output: Any,
) -> dict[str, Any]:
    ledger = AgenticObservationLedger(
        session_id=getattr(output, "session_id", "") or getattr(state, "session_id", ""),
        campaign_id=getattr(output, "campaign_id", "")
        or getattr(state, "campaign_id", ""),
        branch_id=getattr(output, "branch_id", "") or getattr(state, "branch_id", ""),
        champion_version=getattr(output, "champion_version", None),
        problem_spec_hash=getattr(output, "problem_spec_hash", None),
        context_policy_id=latest_context_policy_id(state.observation_ledger),
        observations=tuple(state.observation_ledger),
    )
    return ledger.to_payload()


def compact_observation_ledger_for_resume(
    value: Any,
    *,
    max_entries: int = 24,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    raw_entries = value.get("observations")
    if not isinstance(raw_entries, (list, tuple)):
        raw_entries = ()
    entries = [
        compact_resume_entry(entry)
        for entry in raw_entries
        if isinstance(entry, Mapping)
    ][:max_entries]
    if not entries:
        return {}
    return _drop_empty_dict(
        {
            "schema_version": value.get("schema_version") or LEDGER_SCHEMA_VERSION,
            "session_id": value.get("session_id"),
            "campaign_id": value.get("campaign_id"),
            "branch_id": value.get("branch_id"),
            "champion_version": value.get("champion_version"),
            "problem_spec_hash": value.get("problem_spec_hash"),
            "context_policy_id": value.get("context_policy_id"),
            "observation_count": value.get("observation_count") or len(entries),
            "observations": entries,
            "read_receipts": [read_receipt_from_entry(entry) for entry in entries],
            "active_fact_anchor": (
                value.get("active_fact_anchor")
                if isinstance(value.get("active_fact_anchor"), Mapping)
                else active_fact_anchor_from_entries(entries)
            ),
            "reuse_rule": (
                "Code phase may reuse an observation only when the source digest "
                "still matches and the recorded coverage satisfies the requested "
                "file/symbol read."
            ),
        }
    )


def read_receipt_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    coverage = entry.get("coverage") if isinstance(entry.get("coverage"), Mapping) else {}
    return _drop_empty_dict(
        {
            "observation_id": entry.get("observation_id"),
            "tool_name": entry.get("tool_name"),
            "file_path": entry.get("file_path"),
            "symbol": entry.get("symbol"),
            "digest": entry.get("digest"),
            "source_digest_hash": entry.get("source_digest_hash"),
            "fact_packet_digest": entry.get("fact_packet_digest"),
            "snapshot_digest": entry.get("snapshot_digest"),
            "phase": entry.get("phase"),
            "reusable_by_phases": list(entry.get("reusable_by_phases") or ()),
            "max_chars": coverage.get("max_chars") or entry.get("max_chars"),
            "truncated": coverage.get("truncated") or entry.get("truncated"),
            "coverage_status": coverage.get("coverage_status"),
            "artifact_ref": entry.get("artifact_ref"),
            "evidence_ref": entry.get("evidence_ref"),
        }
    )


def compact_resume_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "observation_id": entry.get("observation_id"),
            "tool_name": entry.get("tool_name"),
            "normalized_args": entry.get("normalized_args"),
            "args_hash": entry.get("args_hash"),
            "file_path": entry.get("file_path"),
            "symbol": entry.get("symbol"),
            "digest": entry.get("digest"),
            "source_digest": entry.get("source_digest"),
            "source_digest_hash": entry.get("source_digest_hash"),
            "fact_packet_digest": entry.get("fact_packet_digest"),
            "fact_ids": entry.get("fact_ids"),
            "snapshot_digest": entry.get("snapshot_digest"),
            "coverage": entry.get("coverage"),
            "max_chars": entry.get("max_chars"),
            "truncated": entry.get("truncated"),
            "artifact_ref": entry.get("artifact_ref"),
            "evidence_ref": entry.get("evidence_ref"),
            "phase": entry.get("phase"),
            "proposal_phase": entry.get("proposal_phase"),
            "reusable_by_phases": list(entry.get("reusable_by_phases") or ()),
            "summary": _limit_string(entry.get("summary"), 240),
            "active_algorithm_facts": entry.get("active_algorithm_facts"),
            "stale_if": entry.get("stale_if"),
        }
    )


def active_fact_anchor_from_entries(
    entries: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> dict[str, Any]:
    for entry in reversed(tuple(entries)):
        if entry.get("tool_name") != "context.read_active_solver_design":
            continue
        fact_packet_digest = entry.get("fact_packet_digest")
        if not fact_packet_digest:
            continue
        return _drop_empty_dict(
            {
                "source_observation_id": entry.get("observation_id"),
                "snapshot_digest": entry.get("snapshot_digest"),
                "fact_packet_digest": fact_packet_digest,
                "fact_ids": entry.get("fact_ids"),
                "source_digest_hash": entry.get("source_digest_hash"),
            }
        )
    return {}


def compact_active_algorithm_facts(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    facts_value = value.get("facts")
    compact_facts: list[dict[str, Any]] = []
    if isinstance(facts_value, (list, tuple)):
        for item in facts_value[:20]:
            if not isinstance(item, Mapping):
                continue
            compact_facts.append(
                _drop_empty_dict(
                    {
                        "fact_id": item.get("fact_id"),
                        "claim": _limit_string(item.get("claim"), 420),
                        "evidence": compact_string_list(item.get("evidence"), 8, 160),
                        "source_paths_or_symbols": compact_string_list(
                            item.get("source_paths_or_symbols"),
                            10,
                            160,
                        ),
                        "importance": item.get("importance"),
                        "used_by_prompt": item.get("used_by_prompt"),
                        "used_by_gate": item.get("used_by_gate"),
                    }
                )
            )
    return _drop_empty_dict(
        {
            "packet_id": value.get("packet_id"),
            "snapshot_digest": value.get("snapshot_digest"),
            "fact_packet_digest": value.get("fact_packet_digest"),
            "fact_ids": [
                str(item.get("fact_id"))
                for item in compact_facts
                if item.get("fact_id")
            ],
            "facts": compact_facts,
        }
    )


__all__ = [
    "active_fact_anchor_from_entries",
    "agentic_observation_ledger_payload",
    "compact_active_algorithm_facts",
    "compact_observation_ledger_for_resume",
    "compact_resume_entry",
    "read_receipt_from_entry",
]
