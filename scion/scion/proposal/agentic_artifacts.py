"""Artifact persistence and replay helpers for agentic proposal sessions."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from scion.core.models import ChampionState, PatchProposal
from scion.core.public_refs import public_artifact_ref
from scion.proposal.agentic_models import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalOutput,
    AgenticProposalRequest,
    AgenticProposalSessionState,
    AgenticReplayValidationResult,
    AgenticSessionIndexEntry,
    AgenticStoredSession,
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
_PROMPT_MANIFEST_REF_MARKER = "api_visible_prompt_manifest"
_PROMPT_MANIFEST_NOT_REQUIRED_REASON = "no_llm_call_recorded_for_session"
_PROMPT_MANIFEST_TOOL_ONLY_REASON = (
    "tool_context_recorded_but_no_model_prompt_call_recorded_for_session"
)


def _dedupe_public_refs(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        candidates = (values,)
    elif isinstance(values, (list, tuple)):
        candidates = tuple(str(value) for value in values if value)
    else:
        try:
            candidates = tuple(str(value) for value in values or () if value)
        except TypeError:
            candidates = (str(values),) if values else ()
    refs: list[str] = []
    for candidate in candidates:
        public_ref = public_artifact_ref(candidate)
        if public_ref and public_ref not in refs:
            refs.append(public_ref)
    return tuple(refs)


def _prompt_manifest_refs_from_output(
    output: AgenticProposalOutput,
) -> tuple[str, ...]:
    return _dedupe_public_refs(
        ref
        for ref in output.tainted_artifact_refs
        if _PROMPT_MANIFEST_REF_MARKER in str(ref)
    )


def _prompt_manifest_refs_from_index_item(item: Mapping[str, Any]) -> tuple[str, ...]:
    refs = list(
        _dedupe_public_refs(
            item.get("prompt_manifest_artifact_refs")
            or item.get("prompt_manifest_refs")
            or ()
        )
    )
    single_ref = str(item.get("prompt_manifest_artifact_ref") or "")
    for ref in _dedupe_public_refs(single_ref):
        if ref not in refs:
            refs.append(ref)
    return tuple(refs)


def _prompt_manifest_not_required_reason_for_output(
    output: AgenticProposalOutput,
) -> str:
    if _output_has_tool_activity(output):
        return _PROMPT_MANIFEST_TOOL_ONLY_REASON
    return _PROMPT_MANIFEST_NOT_REQUIRED_REASON


def _prompt_manifest_not_required_reason_for_index_item(
    item: Mapping[str, Any],
) -> str:
    stored_reason = str(item.get("prompt_manifest_not_required_reason") or "")
    if stored_reason and stored_reason != _PROMPT_MANIFEST_NOT_REQUIRED_REASON:
        return stored_reason
    if _index_item_has_tool_activity(item):
        return _PROMPT_MANIFEST_TOOL_ONLY_REASON
    return stored_reason or _PROMPT_MANIFEST_NOT_REQUIRED_REASON


def _output_has_tool_activity(output: AgenticProposalOutput) -> bool:
    if _tool_budget_has_activity(output.tool_budget_used):
        return True
    for event in output.transcript:
        metadata = getattr(event, "metadata", {}) or {}
        if isinstance(metadata, Mapping) and metadata.get("tool_name"):
            return True
    return False


def _index_item_has_tool_activity(item: Mapping[str, Any]) -> bool:
    return _tool_budget_has_activity(item.get("tool_budget_used") or {})


def _tool_budget_has_activity(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    for key in ("tool_steps", "tool_calls"):
        try:
            if int(value.get(key) or 0) > 0:
                return True
        except Exception:
            continue
    return False


class AgenticSessionStore:
    """File-backed, ops-safe index for persisted APS output artifacts."""

    _INDEX_NAME = "agentic_session_index.json"

    def __init__(self, artifact_dir: str | Path) -> None:
        self._root = Path(artifact_dir).resolve()
        self._index_path = self._root / self._INDEX_NAME

    @property
    def index_path(self) -> Path:
        return self._index_path

    def record_output(
        self,
        output: AgenticProposalOutput,
        artifact_ref: str | Path,
    ) -> AgenticSessionIndexEntry:
        artifact_path = Path(artifact_ref).resolve()
        self._ensure_inside_root(artifact_path)
        public_ref = self._public_artifact_ref(artifact_path)
        now = datetime.now().isoformat()
        entries = self._read_entries()
        existing_created_at = None
        prompt_manifest_refs = _prompt_manifest_refs_from_output(output)
        prompt_manifest_required = bool(prompt_manifest_refs)
        prompt_manifest_not_required_reason = (
            ""
            if prompt_manifest_required
            else _prompt_manifest_not_required_reason_for_output(output)
        )
        kept: list[AgenticSessionIndexEntry] = []
        for entry in entries:
            if entry.session_id == output.session_id:
                existing_created_at = entry.created_at
                continue
            kept.append(entry)
        entry = AgenticSessionIndexEntry(
            schema_version=output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
            session_id=output.session_id,
            request_id=output.request_id or output.session_id,
            idempotency_key=output.idempotency_key,
            artifact_ref=public_ref,
            artifact_path=public_ref,
            transcript_digest=output.transcript_digest,
            termination_reason=str(_enum_value(output.termination_reason)),
            status=str(_enum_value(output.status)),
            created_at=existing_created_at or now,
            updated_at=now,
            tainted=True,
            artifact_ref_scope="artifact_dir_relative",
            artifact_path_internal_only=True,
            tool_loop_config=dict(output.tool_loop_config),
            tool_budget_used=dict(output.tool_budget_used),
            prompt_manifest_required=prompt_manifest_required,
            prompt_manifest_artifact_ref=(
                prompt_manifest_refs[-1] if prompt_manifest_refs else ""
            ),
            prompt_manifest_artifact_refs=prompt_manifest_refs,
            prompt_manifest_ref_scope="artifact_dir_relative",
            raw_prompt_saved=False,
            prompt_manifest_not_required_reason=prompt_manifest_not_required_reason,
        )
        kept.append(entry)
        self._write_entries(kept)
        return entry

    def load_by_session_id(self, session_id: str) -> AgenticStoredSession | None:
        matches = [
            entry for entry in self._read_entries() if entry.session_id == session_id
        ]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def find_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AgenticStoredSession | None:
        matches = [
            entry
            for entry in self._read_entries()
            if entry.idempotency_key == idempotency_key
        ]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def latest_for_request(self, request_id: str) -> AgenticStoredSession | None:
        matches = [
            entry for entry in self._read_entries() if entry.request_id == request_id
        ]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def list_sessions(self) -> list[AgenticStoredSession]:
        return [
            self._load_stored_session(entry)
            for entry in sorted(
                self._read_entries(),
                key=lambda entry: (
                    entry.updated_at,
                    entry.created_at,
                    entry.session_id,
                ),
            )
        ]

    def _load_stored_session(
        self,
        entry: AgenticSessionIndexEntry,
    ) -> AgenticStoredSession:
        artifact: Mapping[str, Any] | None = None
        try:
            artifact_path = self._resolve_artifact_path(entry.artifact_path)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            validation = validate_agentic_session_artifact(artifact)
        except Exception as exc:
            validation = AgenticReplayValidationResult(
                ok=False,
                errors=(f"artifact load failed: {exc}",),
            )
        return AgenticStoredSession(
            entry=entry, artifact=artifact, validation=validation
        )

    def _read_entries(self) -> list[AgenticSessionIndexEntry]:
        if not self._index_path.exists():
            return []
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        entries: list[AgenticSessionIndexEntry] = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            try:
                artifact_path = self._resolve_artifact_path(
                    str(item.get("artifact_path") or item.get("artifact_ref") or "")
                )
                public_ref = self._public_artifact_ref(artifact_path)
                prompt_manifest_refs = _prompt_manifest_refs_from_index_item(item)
                prompt_manifest_required = bool(prompt_manifest_refs)
                prompt_manifest_not_required_reason = (
                    ""
                    if prompt_manifest_required
                    else _prompt_manifest_not_required_reason_for_index_item(item)
                )
                entries.append(
                    AgenticSessionIndexEntry(
                        schema_version=str(item.get("schema_version") or ""),
                        session_id=str(item.get("session_id") or ""),
                        request_id=str(item.get("request_id") or ""),
                        idempotency_key=str(item.get("idempotency_key") or ""),
                        artifact_ref=public_ref,
                        artifact_path=public_ref,
                        transcript_digest=str(item.get("transcript_digest") or ""),
                        termination_reason=str(item.get("termination_reason") or ""),
                        status=str(item.get("status") or ""),
                        created_at=str(item.get("created_at") or ""),
                        updated_at=str(item.get("updated_at") or ""),
                        tainted=bool(item.get("tainted", True)),
                        artifact_ref_scope="artifact_dir_relative",
                        artifact_path_internal_only=bool(
                            item.get("artifact_path_internal_only", True)
                        ),
                        tool_loop_config=dict(item.get("tool_loop_config") or {}),
                        tool_budget_used=dict(item.get("tool_budget_used") or {}),
                        prompt_manifest_required=prompt_manifest_required,
                        prompt_manifest_artifact_ref=(
                            prompt_manifest_refs[-1] if prompt_manifest_refs else ""
                        ),
                        prompt_manifest_artifact_refs=prompt_manifest_refs,
                        prompt_manifest_ref_scope="artifact_dir_relative",
                        raw_prompt_saved=False,
                        prompt_manifest_not_required_reason=(
                            prompt_manifest_not_required_reason
                        ),
                    )
                )
            except Exception:
                continue
        return [
            entry
            for entry in entries
            if entry.session_id and entry.artifact_path and entry.idempotency_key
        ]

    def _write_entries(self, entries: list[AgenticSessionIndexEntry]) -> None:
        payload = [_json_ready(entry) for entry in entries]
        self._root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self._index_path, payload)

    def _ensure_inside_root(self, path: Path) -> None:
        if path != self._root and self._root not in path.parents:
            raise ValueError("agentic session artifact path escapes index root")

    def _resolve_artifact_path(self, value: str) -> Path:
        if not value:
            raise ValueError("missing agentic session artifact path")
        path = Path(value)
        if not path.is_absolute():
            path = self._root / path
        resolved = path.resolve()
        self._ensure_inside_root(resolved)
        return resolved

    def _public_artifact_ref(self, path: Path) -> str:
        ref = public_artifact_ref(path, base_dir=self._root, kind="artifact")
        return ref or path.name

    @staticmethod
    def _latest_entry(
        entries: list[AgenticSessionIndexEntry],
    ) -> AgenticSessionIndexEntry:
        return max(
            entries,
            key=lambda entry: (entry.updated_at, entry.created_at, entry.session_id),
        )


class FileAgenticSessionArtifactStore:
    """Persist tainted session artifacts below one allowed directory."""

    _SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")

    def __init__(self, artifact_dir: str | Path) -> None:
        self._root = Path(artifact_dir).resolve()
        self.session_store = AgenticSessionStore(self._root)

    def write_transcript(self, state: AgenticProposalSessionState) -> str:
        path = self._session_dir(state.session_id) / "transcript.json"
        return self._write_json(path, _agentic_transcript_artifact(state))

    def write_output(self, output: AgenticProposalOutput) -> str:
        path = self._session_dir(output.session_id) / "output.json"
        ref = self._write_json(path, _agentic_output_artifact(output))
        self.session_store.record_output(output, ref)
        return ref

    def write_scratch(
        self,
        session_id: str,
        name: str,
        payload: Mapping[str, Any],
    ) -> str:
        safe_name = self._safe_segment(name)
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"
        path = self._session_dir(session_id) / "scratch" / safe_name
        return self._write_json(path, _json_ready(dict(payload)))

    def _session_dir(self, session_id: str) -> Path:
        safe_id = self._safe_segment(session_id)
        path = (self._root / safe_id).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError("session artifact path escapes allowed artifact dir")
        return path

    def _write_json(self, path: Path, payload: Any) -> str:
        resolved = path.resolve()
        if resolved != self._root and self._root not in resolved.parents:
            raise ValueError("session artifact path escapes allowed artifact dir")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(resolved, payload)
        return str(resolved)

    def _safe_segment(self, value: str) -> str:
        if not value or "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError(f"unsafe session artifact path segment: {value!r}")
        if not self._SAFE_SEGMENT.match(value):
            raise ValueError(f"unsafe session artifact path segment: {value!r}")
        return value

def validate_agentic_session_artifact(
    artifact: str | Path | Mapping[str, Any],
) -> AgenticReplayValidationResult:
    """Lightweight replay/audit validation for a persisted APS artifact.

    This does not execute tools or LLM calls. It only checks that the persisted
    artifact is a supported compact APS envelope with bounded, monotonic tool
    transcript metadata and no raw-reference markers.
    """
    payload = _load_artifact_payload(artifact)
    errors: list[str] = []
    if payload.get("schema_version") != AGENTIC_SESSION_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    for field_name in (
        "schema_version",
        "session_id",
        "request_id",
        "idempotency_key",
        "termination_reason",
        "tool_loop_config",
        "tool_budget_used",
        "transcript_digest",
    ):
        if field_name not in payload:
            errors.append(f"missing required field: {field_name}")

    compact_transcript = payload.get("compact_transcript")
    if compact_transcript is None:
        compact_transcript = payload.get("transcript", [])
    if not isinstance(compact_transcript, list):
        errors.append("transcript must be a list")
        compact_transcript = []

    step_numbers: list[int] = []
    seen_steps: set[str] = set()
    for event in compact_transcript:
        if not isinstance(event, Mapping):
            errors.append("transcript event must be an object")
            continue
        metadata = event.get("metadata", {})
        if not isinstance(metadata, Mapping):
            errors.append("transcript event metadata must be an object")
            continue
        step_id = metadata.get("step_id")
        if step_id is None:
            continue
        step_text = str(step_id)
        if step_text in seen_steps:
            errors.append(f"duplicate step_id: {step_text}")
        seen_steps.add(step_text)
        match = re.fullmatch(r"tool-(\d+)", step_text)
        if match is None:
            errors.append(f"invalid step_id: {step_text}")
            continue
        step_numbers.append(int(match.group(1)))
    if step_numbers != sorted(step_numbers):
        errors.append("transcript step_id values are not monotonic")

    config = payload.get("tool_loop_config", {})
    used = payload.get("tool_budget_used", {})
    if isinstance(config, Mapping) and isinstance(used, Mapping):
        for used_key, config_key in (
            ("tool_steps", "max_steps"),
            ("tool_calls", "max_tool_calls"),
            ("observation_chars", "max_observation_chars"),
        ):
            try:
                used_value = int(used.get(used_key, 0))
                max_value = int(config.get(config_key, 0))
            except Exception:
                errors.append(f"invalid tool budget field: {used_key}")
                continue
            if max_value >= 0 and used_value > max_value:
                errors.append(f"tool budget exceeded: {used_key}")
    else:
        errors.append("tool_loop_config and tool_budget_used must be objects")

    rendered = json.dumps(_json_ready(payload), sort_keys=True, default=str)
    marker = _find_raw_ref_marker(rendered)
    if marker is not None:
        errors.append(f"raw ref marker found: {marker}")

    expected_digest = payload.get("transcript_digest")
    if expected_digest and isinstance(compact_transcript, list):
        actual_digest = _transcript_digest(compact_transcript)
        if expected_digest != actual_digest:
            errors.append("transcript_digest mismatch")

    return AgenticReplayValidationResult(ok=not errors, errors=tuple(errors))


def inspect_agentic_session_artifact(
    artifact: str | Path | Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact ops-safe APS artifact summary."""
    payload = _load_artifact_payload(artifact)
    validation = validate_agentic_session_artifact(payload)
    failure_ledger = (
        payload.get("failure_ledger", {})
        if isinstance(payload.get("failure_ledger"), Mapping)
        else {}
    )
    return {
        "schema_version": payload.get("schema_version"),
        "session_id": payload.get("session_id"),
        "request_id": payload.get("request_id"),
        "termination_reason": payload.get("termination_reason"),
        "status": payload.get("status"),
        "failure_category": payload.get("failure_category"),
        "failure_ledger": {
            "first_root_cause": failure_ledger.get("first_root_cause"),
            "latest_failure": failure_ledger.get("latest_failure"),
            "entry_count": failure_ledger.get("entry_count", 0),
        },
        "tool_loop_config": payload.get("tool_loop_config", {}),
        "tool_budget_used": payload.get("tool_budget_used", {}),
        "transcript_digest": payload.get("transcript_digest"),
        "validation": {
            "ok": validation.ok,
            "errors": list(validation.errors),
        },
    }


def resume_from_artifact(
    artifact: str | Path | Mapping[str, Any],
    *,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """Build sanitized compact APS context for a follow-up session prompt."""
    payload = _load_artifact_payload(artifact)
    validation = validate_agentic_session_artifact(payload)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))
    compact_transcript = payload.get("compact_transcript")
    if compact_transcript is None:
        compact_transcript = payload.get("transcript", [])
    tool_steps = []
    for event in compact_transcript:
        metadata = event.get("metadata", {}) if isinstance(event, Mapping) else {}
        if not isinstance(metadata, Mapping) or not metadata.get("tool_name"):
            continue
        tool_steps.append(
            {
                "tool_name": metadata.get("tool_name"),
                "status": metadata.get("status"),
                "error_code": metadata.get("error_code"),
                "evidence_ref": metadata.get("evidence_ref"),
                "result_summary": _sanitize_agentic_value(
                    metadata.get("result_summary") or ""
                ),
            }
        )
    failure_ledger = (
        payload.get("failure_ledger", {})
        if isinstance(payload.get("failure_ledger"), Mapping)
        else {}
    )
    context = {
        "schema_version": payload.get("schema_version"),
        "session_id": payload.get("session_id"),
        "request_id": payload.get("request_id"),
        "termination_reason": payload.get("termination_reason"),
        "transcript_digest": payload.get("transcript_digest"),
        "tool_budget_used": payload.get("tool_budget_used", {}),
        "tool_steps": tool_steps,
    }
    if payload.get("failure_category"):
        context["failure_category"] = payload.get("failure_category")
    if int(failure_ledger.get("entry_count") or 0) > 0:
        context["failure_ledger"] = failure_ledger
    summary = json.dumps(context, sort_keys=True, default=str)
    if len(summary) > max_chars:
        allowed_steps: list[dict[str, Any]] = []
        for step in tool_steps:
            candidate = dict(context, tool_steps=[*allowed_steps, step])
            if len(json.dumps(candidate, sort_keys=True, default=str)) > max_chars:
                break
            allowed_steps.append(step)
        context["tool_steps"] = allowed_steps
        summary = json.dumps(context, sort_keys=True, default=str)
        if len(summary) > max_chars:
            context["tool_steps"] = []
            summary = json.dumps(context, sort_keys=True, default=str)
            if len(summary) > max_chars:
                summary = summary[: max(0, max_chars - 3)] + "..."
    context["summary"] = summary
    return context


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
