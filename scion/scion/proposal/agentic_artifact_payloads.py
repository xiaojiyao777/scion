"""Payload and digest helpers for agentic session artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from scion.core.models import ChampionState, PatchProposal
from scion.proposal.agentic_models import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalOutput,
    AgenticProposalRequest,
    AgenticProposalSessionState,
    AgenticTranscriptEvent,
    AgenticToolLoopConfig,
)
from scion.proposal.agentic_utils import (
    _enum_value,
    _json_ready,
    _sanitize_agentic_value,
)

_RAW_REF_MARKERS = (
    "raw_metrics_ref",
    "raw metrics",
    "raw_ref",
    "raw ref",
    "SECRET_RAW",
    "SECRET_VALIDATION",
    "SECRET_FROZEN",
    "SECRET_HOLDOUT",
)


def ensure_agentic_output_audit_metadata(
    output: AgenticProposalOutput,
) -> AgenticProposalOutput:
    compact_transcript = _compact_transcript(tuple(output.transcript))
    return replace(
        output,
        schema_version=output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
        request_id=output.request_id or output.session_id,
        idempotency_key=output.idempotency_key,
        transcript_digest=output.transcript_digest
        or _transcript_digest(compact_transcript),
    )

def _champion_version(champion: ChampionState | None) -> int | None:
    return champion.version if champion is not None else None

def _champion_weight_revision(champion: ChampionState | None) -> int | None:
    return getattr(champion, "weight_revision", None) if champion is not None else None

def _tool_loop_config_payload(config: AgenticToolLoopConfig) -> dict[str, Any]:
    return {
        "max_steps": int(config.max_steps),
        "max_tool_calls": int(config.max_tool_calls),
        "max_observation_chars": int(config.max_observation_chars),
        "max_wall_time_sec": float(config.max_wall_time_sec),
        "max_repeated_tool_calls": int(config.max_repeated_tool_calls),
        "max_code_tool_calls": int(config.max_code_tool_calls),
        "max_code_repair_attempts": int(config.max_code_repair_attempts),
        "max_code_generation_timeout_retries": int(
            config.max_code_generation_timeout_retries
        ),
    }

def _tool_budget_used_payload(state: AgenticProposalSessionState) -> dict[str, int]:
    return {
        "tool_steps": int(state.tool_step_count),
        "tool_calls": int(state.tool_call_count),
        "preview_tool_steps": int(state.preview_tool_step_count),
        "preview_tool_calls": int(state.preview_tool_call_count),
        "observation_chars": int(state.observation_chars_used),
    }

def _compact_transcript(
    transcript: tuple[AgenticTranscriptEvent, ...] | list[AgenticTranscriptEvent],
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    allowed_metadata = {
        "step_id",
        "tool_name",
        "status",
        "error_code",
        "evidence_ref",
        "result_summary",
        "selection_source",
        "fallback",
        "skip_reason",
        "stop_reason",
        "tool_steps",
        "tool_calls",
        "observation_chars_used",
    }
    for event in transcript:
        metadata = {
            key: _sanitize_agentic_value(value)
            for key, value in dict(event.metadata).items()
            if key in allowed_metadata
        }
        compact.append(
            {
                "phase": event.phase,
                "created_at": event.created_at,
                "message": _sanitize_agentic_value(event.message),
                "metadata": metadata,
            }
        )
    return compact

def _transcript_digest(compact_transcript: Any) -> str:
    rendered = json.dumps(
        _json_ready(compact_transcript),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

def _agentic_transcript_artifact(
    state: AgenticProposalSessionState,
) -> dict[str, Any]:
    compact_transcript = _compact_transcript(tuple(state.transcript))
    return {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "artifact_kind": "agentic_proposal_transcript",
        "session_id": state.session_id,
        "request_id": state.request_id or state.session_id,
        "idempotency_key": state.idempotency_key,
        "campaign_id": state.campaign_id,
        "branch_id": state.branch_id,
        "phase": state.phase.value,
        "status": _enum_value(state.status),
        "termination_reason": state.loop_stop_reason,
        "tool_loop_config": dict(state.tool_loop_config),
        "tool_budget_used": _tool_budget_used_payload(state),
        "failure_ledger": _json_ready(
            _sanitize_agentic_value(
                {
                    "schema_version": "agentic-retry-error-ledger.v1",
                    "entries": list(state.failure_ledger),
                    "entry_count": len(state.failure_ledger),
                    "first_root_cause": (
                        state.failure_ledger[0].get("root_cause")
                        if state.failure_ledger
                        else None
                    ),
                    "latest_failure": (
                        state.failure_ledger[-1].get("category")
                        if state.failure_ledger
                        else None
                    ),
                }
            )
        ),
        "transcript_digest": _transcript_digest(compact_transcript),
        "compact_transcript": compact_transcript,
        "tainted": True,
    }

def _agentic_output_artifact(output: AgenticProposalOutput) -> dict[str, Any]:
    compact_transcript = _compact_transcript(tuple(output.transcript))
    transcript_digest = output.transcript_digest or _transcript_digest(
        compact_transcript
    )
    artifact = {
        "schema_version": output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
        "artifact_kind": "agentic_proposal_output",
        "session_id": output.session_id,
        "request_id": output.request_id or output.session_id,
        "idempotency_key": output.idempotency_key,
        "campaign_id": output.campaign_id,
        "branch_id": output.branch_id,
        "status": _enum_value(output.status),
        "termination_reason": _enum_value(output.termination_reason),
        "tool_loop_config": dict(output.tool_loop_config),
        "tool_budget_used": dict(output.tool_budget_used),
        "transcript_digest": transcript_digest,
        "selected_surface": output.selected_surface,
        "action": output.action,
        "problem_id": output.problem_id,
        "problem_spec_hash": output.problem_spec_hash,
        "champion_version": output.champion_version,
        "champion_weight_revision": output.champion_weight_revision,
        "hypothesis": (
            _proposal_payload(output.hypothesis)
            if output.hypothesis is not None
            else None
        ),
        "patch": (
            _patch_artifact_payload(output.patch) if output.patch is not None else None
        ),
        "evidence_used": [
            {
                "observation_id": evidence.observation_id,
                "exposure_level": evidence.exposure_level,
                "summary": _sanitize_agentic_value(evidence.summary),
            }
            for evidence in output.evidence_used
        ],
        "self_check": _json_ready(output.self_check),
        "compact_transcript": compact_transcript,
        "failure_detail": _sanitize_agentic_value(output.failure_detail),
        "failure_category": _enum_value(output.failure_category),
        "structured_rejection": _sanitize_agentic_value(output.structured_rejection),
        "failure_ledger": _json_ready(
            _sanitize_agentic_value(output.failure_ledger)
        ),
        "tainted": True,
    }
    return _json_ready(_sanitize_agentic_value(artifact))

def _patch_artifact_payload(patch: PatchProposal) -> dict[str, Any]:
    payload = _proposal_payload(patch)
    code_content = payload.pop("code_content", None)
    if code_content is not None:
        payload["patch_body_omitted"] = True
        payload["patch_body_chars"] = len(str(code_content))
    additional = []
    for change in payload.get("additional_changes") or []:
        if not isinstance(change, Mapping):
            continue
        compact = dict(change)
        change_code = compact.pop("code_content", None)
        if change_code is not None:
            compact["patch_body_omitted"] = True
            compact["patch_body_chars"] = len(str(change_code))
        additional.append(compact)
    if additional:
        payload["additional_changes"] = additional
        payload["additional_change_count"] = len(additional)
    return payload

def _load_artifact_payload(artifact: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(artifact, Mapping):
        return dict(artifact)
    path = Path(artifact)
    return json.loads(path.read_text(encoding="utf-8"))

def _atomic_write_json(path: Path, payload: Any) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(rendered, encoding="utf-8")
    os.replace(tmp_path, path)

def _find_raw_ref_marker(rendered: str) -> str | None:
    lowered = rendered.lower()
    for marker in _RAW_REF_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None

def compute_agentic_idempotency_key(
    request: AgenticProposalRequest,
    tool_loop_config: AgenticToolLoopConfig,
) -> str:
    """Stable replay/audit key for duplicate APS requests.

    The key is derived from durable campaign/request anchors and policy/config,
    never from the random session_id.
    """
    policy_payload: Any = None
    if request.tool_context is not None:
        policy_payload = _json_ready(request.tool_context.policy)
    champion = request.champion
    branch = request.branch
    anchor_payload = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "campaign_id": request.campaign_id,
        "branch": {
            "branch_id": branch.branch_id,
            "base_champion_id": branch.base_champion_id,
            "base_champion_hash": branch.base_champion_hash,
            "current_code_hash": branch.current_code_hash,
            "weight_revision": getattr(branch, "weight_revision", None),
        },
        "champion": {
            "version": _champion_version(champion),
            "code_snapshot_hash": (
                getattr(champion, "code_snapshot_hash", None)
                if champion is not None
                else None
            ),
            "solver_config_hash": (
                getattr(champion, "solver_config_hash", None)
                if champion is not None
                else None
            ),
            "weight_revision": _champion_weight_revision(champion),
        },
        "problem": {
            "problem_id": request.problem_id,
            "problem_spec_hash": request.problem_spec_hash,
        },
        "request": {
            "kind": "code" if request.approved_hypothesis is not None else "hypothesis",
            "approved_hypothesis": (
                _proposal_payload(request.approved_hypothesis)
                if request.approved_hypothesis is not None
                else None
            ),
            "prior_failure": _sanitize_agentic_value(request.prior_failure),
        },
        "policy": policy_payload,
        "tool_loop_config": _tool_loop_config_payload(tool_loop_config),
    }
    rendered = json.dumps(
        _json_ready(_sanitize_agentic_value(anchor_payload)),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "aps:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()

def _tool_call_fingerprint(name: str, args: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        _json_ready(_sanitize_agentic_value({"tool_name": name, "args": dict(args)})),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

def _proposal_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return dict(_sanitize_agentic_value(asdict(value)))
    if isinstance(value, Mapping):
        return dict(_sanitize_agentic_value(value))
    return dict(_sanitize_agentic_value(getattr(value, "__dict__", {})))
