"""Append-only, mode-neutral proposal-attempt transition recording."""
from __future__ import annotations

import json
import math
import uuid
from typing import Any, Mapping, Protocol

from scion.core.public_refs import contains_absolute_path


PROPOSAL_ATTEMPT_TRANSITION_SCHEMA = "proposal-attempt-transition.v1"

_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "attempt_id",
        "campaign_id",
        "branch_id",
        "runtime_mode",
        "phase",
        "status",
        "transition_reason",
        "failure_lane",
        "hypothesis_id",
        "hypothesis_digest",
        "patch_digest",
        "prompt_call",
        "anchors",
        "tainted_artifact_refs",
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "attempt_kind",
        "continuation_of_attempt_id",
        "non_resumable",
        "trace_persistence_error",
    }
)
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_REQUIRED_ANCHORS = frozenset(
    {
        "problem_id",
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "champion_version",
        "champion_weight_revision",
        "champion_code_snapshot_hash",
        "branch_base_champion_id",
        "branch_base_champion_hash",
    }
)
_PROMPT_CALL_FIELDS = frozenset(
    {
        "request_kind",
        "context_digest",
        "prompt_hash",
        "trace_ref",
        "prompt_manifest_ref",
        "raw_response_ref",
        "provider_ok",
        "ok",
        "error_category",
        "error_type",
    }
)
_TRACE_PERSISTENCE_ERROR_FIELDS = frozenset({"stage", "error_type"})
_FORBIDDEN_FIELDS = frozenset(
    {
        "code_content",
        "hypothesis",
        "hypothesis_text",
        "patch",
        "prompt",
        "raw_response",
        "system_blocks",
        "user_prompt",
    }
)


class _LineageRegistryLike(Protocol):
    def record_event(self, event: dict[str, Any]) -> str: ...


class ProposalAttemptRecorder:
    """Validate one compact transition and delegate its single durable write."""

    def __init__(self, lineage_registry: _LineageRegistryLike) -> None:
        self._lineage_registry = lineage_registry

    def record_transition(self, payload: Mapping[str, Any]) -> str:
        normalized = dict(payload)
        self._validate(normalized)
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "campaign_id": normalized["campaign_id"],
            "branch_id": normalized["branch_id"],
            "hypothesis_id": normalized.get("hypothesis_id"),
            "event_kind": "proposal_attempt_transition",
            "stage": f"proposal_{normalized['phase']}",
            "audit_payload_json": json.dumps(
                normalized,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
        recorded_id = self._lineage_registry.record_event(event)
        return str(recorded_id or event_id)

    @staticmethod
    def _validate(payload: Mapping[str, Any]) -> None:
        missing = sorted(_REQUIRED_FIELDS - payload.keys())
        if missing:
            raise ValueError(
                "proposal attempt transition missing fields: " + ", ".join(missing)
            )
        forbidden = sorted(_FORBIDDEN_FIELDS & payload.keys())
        if forbidden:
            raise ValueError(
                "proposal attempt transition forbidden payload field: "
                + ", ".join(forbidden)
            )
        unknown = sorted(payload.keys() - _ALLOWED_FIELDS)
        if unknown:
            raise ValueError(
                "proposal attempt transition contains unsupported fields: "
                + ", ".join(unknown)
            )
        if payload.get("schema_version") != PROPOSAL_ATTEMPT_TRANSITION_SCHEMA:
            raise ValueError("unsupported proposal attempt transition schema")
        if not str(payload.get("attempt_id") or "").strip():
            raise ValueError("proposal attempt transition requires attempt_id")
        if not str(payload.get("campaign_id") or "").strip():
            raise ValueError("proposal attempt transition requires campaign_id")
        if not str(payload.get("branch_id") or "").strip():
            raise ValueError("proposal attempt transition requires branch_id")
        if payload.get("runtime_mode") != "direct_v3":
            raise ValueError("invalid proposal attempt runtime_mode")
        if payload.get("phase") not in {"hypothesis", "code"}:
            raise ValueError("invalid proposal attempt phase")
        ProposalAttemptRecorder._validate_continuation(payload)
        if payload.get("status") not in {
            "started",
            "generated",
            "failed",
            "interrupted",
        }:
            raise ValueError("invalid proposal attempt status")
        lane = payload.get("failure_lane")
        if lane not in {None, "infra", "invalid_response"}:
            raise ValueError("invalid proposal attempt failure_lane")
        if payload.get("status") in {
            "started",
            "generated",
            "interrupted",
        } and lane is not None:
            raise ValueError(
                "started/generated/interrupted proposal attempt cannot have "
                "failure_lane"
            )
        if payload.get("status") == "failed" and lane is None:
            raise ValueError("failed proposal attempt requires failure_lane")
        if payload.get("status") == "interrupted":
            if payload.get("non_resumable") is not True:
                raise ValueError(
                    "interrupted proposal attempt must be non_resumable"
                )
        elif "non_resumable" in payload:
            raise ValueError(
                "non_resumable is only valid for interrupted proposal attempts"
            )
        if not str(payload.get("transition_reason") or "").strip():
            raise ValueError("proposal attempt transition requires transition_reason")
        anchors = payload.get("anchors")
        if not isinstance(anchors, Mapping):
            raise ValueError("proposal attempt transition requires anchors mapping")
        missing_anchors = sorted(_REQUIRED_ANCHORS - anchors.keys())
        unknown_anchors = sorted(anchors.keys() - _REQUIRED_ANCHORS)
        if missing_anchors:
            raise ValueError(
                "proposal attempt transition missing anchors: "
                + ", ".join(missing_anchors)
            )
        if unknown_anchors:
            raise ValueError(
                "proposal attempt transition anchors contain unsupported fields: "
                + ", ".join(unknown_anchors)
            )
        invalid_anchor_values = sorted(
            str(key)
            for key, value in anchors.items()
            if not _is_json_scalar(value)
        )
        if invalid_anchor_values:
            raise ValueError(
                "proposal attempt transition anchors must be JSON scalars: "
                + ", ".join(invalid_anchor_values)
            )
        prompt_call = payload.get("prompt_call")
        if not isinstance(prompt_call, Mapping):
            raise ValueError("proposal attempt transition requires prompt_call mapping")
        missing_prompt_fields = sorted(_PROMPT_CALL_FIELDS - prompt_call.keys())
        unknown_prompt_fields = sorted(prompt_call.keys() - _PROMPT_CALL_FIELDS)
        if missing_prompt_fields:
            raise ValueError(
                "proposal attempt prompt_call missing fields: "
                + ", ".join(missing_prompt_fields)
            )
        if unknown_prompt_fields:
            raise ValueError(
                "proposal attempt prompt_call contains unsupported fields: "
                + ", ".join(unknown_prompt_fields)
            )
        if prompt_call.get("request_kind") != payload.get("phase"):
            raise ValueError("proposal attempt prompt request_kind must match phase")
        if not str(prompt_call.get("prompt_hash") or "").strip():
            raise ValueError("proposal attempt prompt_call requires prompt_hash")
        if not str(prompt_call.get("context_digest") or "").strip():
            raise ValueError("proposal attempt prompt_call requires context_digest")
        if (
            payload.get("phase") == "hypothesis"
            and payload.get("patch_digest") is not None
        ):
            raise ValueError("hypothesis transition cannot contain patch_digest")
        if payload.get("status") == "generated":
            if (
                prompt_call.get("provider_ok") is not True
                or prompt_call.get("ok") is not True
            ):
                raise ValueError(
                    "generated proposal transition requires successful prompt_call"
                )
            missing_refs = sorted(
                field
                for field in ("trace_ref", "prompt_manifest_ref", "raw_response_ref")
                if not str(prompt_call.get(field) or "").strip()
            )
            if missing_refs:
                raise ValueError(
                    "generated proposal transition missing durable prompt refs: "
                    + ", ".join(missing_refs)
                )
            if not str(payload.get("hypothesis_id") or "").strip():
                raise ValueError("generated proposal transition requires hypothesis_id")
            if not str(payload.get("hypothesis_digest") or "").strip():
                raise ValueError("generated proposal transition requires hypothesis_digest")
            if payload.get("phase") == "code" and not str(
                payload.get("patch_digest") or ""
            ).strip():
                raise ValueError("generated code transition requires patch_digest")
        elif payload.get("status") == "started":
            if payload.get("transition_reason") != "provider_call_started":
                raise ValueError(
                    "started proposal transition requires provider_call_started reason"
                )
            if prompt_call.get("provider_ok") is not None or prompt_call.get(
                "ok"
            ) is not None:
                raise ValueError(
                    "started proposal transition cannot claim provider outcome"
                )
            if prompt_call.get("error_category") is not None or prompt_call.get(
                "error_type"
            ) is not None:
                raise ValueError(
                    "started proposal transition cannot contain provider error"
                )
            if any(
                prompt_call.get(field) not in (None, "")
                for field in ("trace_ref", "prompt_manifest_ref", "raw_response_ref")
            ):
                raise ValueError(
                    "started proposal transition cannot contain completed prompt refs"
                )
            if payload.get("patch_digest") is not None:
                raise ValueError("started proposal transition cannot contain patch_digest")
            if payload.get("tainted_artifact_refs") not in ([], ()):
                raise ValueError(
                    "started proposal transition cannot contain artifact refs"
                )
            if payload.get("phase") == "hypothesis" and (
                payload.get("hypothesis_id") is not None
                or payload.get("hypothesis_digest") is not None
            ):
                raise ValueError(
                    "started hypothesis transition cannot claim model output identity"
                )
            if payload.get("phase") == "code" and (
                not str(payload.get("hypothesis_id") or "").strip()
                or not str(payload.get("hypothesis_digest") or "").strip()
            ):
                raise ValueError(
                    "started code transition requires approved hypothesis identity"
                )
        elif payload.get("status") == "interrupted":
            if payload.get("transition_reason") != "provider_call_interrupted":
                raise ValueError(
                    "interrupted proposal transition requires "
                    "provider_call_interrupted reason"
                )
            if prompt_call.get("provider_ok") not in {False, True} or prompt_call.get(
                "ok"
            ) is not False:
                raise ValueError(
                    "interrupted proposal transition requires an interrupted "
                    "prompt_call"
                )
            if prompt_call.get("error_category") != "provider_call_interrupted":
                raise ValueError(
                    "interrupted proposal transition requires interruption category"
                )
            if not str(prompt_call.get("error_type") or "").strip():
                raise ValueError(
                    "interrupted proposal transition requires error_type"
                )
            if prompt_call.get("raw_response_ref") not in (None, ""):
                raise ValueError(
                    "interrupted proposal transition cannot claim a raw response"
                )
            if payload.get("patch_digest") is not None:
                raise ValueError(
                    "interrupted proposal transition cannot contain patch_digest"
                )
        for field in ("trace_ref", "prompt_manifest_ref", "raw_response_ref"):
            ref = prompt_call.get(field)
            if ref not in (None, ""):
                _validate_public_ref(ref, field=field)
        refs = payload.get("tainted_artifact_refs")
        if not isinstance(refs, (list, tuple)):
            raise ValueError("proposal attempt tainted_artifact_refs must be a sequence")
        if any(not isinstance(ref, str) for ref in refs):
            raise ValueError("proposal attempt tainted artifact refs must be strings")
        for ref in refs:
            _validate_public_ref(ref, field="tainted_artifact_refs")
        ProposalAttemptRecorder._validate_trace_persistence_error(payload)
        try:
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("proposal attempt transition must be JSON serializable") from exc

    @staticmethod
    def _validate_continuation(payload: Mapping[str, Any]) -> None:
        attempt_kind = payload.get("attempt_kind")
        continuation_id = payload.get("continuation_of_attempt_id")
        if attempt_kind is not None and attempt_kind not in {
            "initial",
            "approved_code_continuation",
        }:
            raise ValueError("invalid proposal attempt_kind")
        if continuation_id is not None and not str(continuation_id).strip():
            raise ValueError("continuation_of_attempt_id must be non-empty")
        if continuation_id is not None and payload.get("phase") != "code":
            raise ValueError("proposal continuation is only valid for code phase")
        if continuation_id is not None and attempt_kind != "approved_code_continuation":
            raise ValueError(
                "continuation_of_attempt_id requires approved_code_continuation"
            )
        if attempt_kind == "approved_code_continuation" and continuation_id is None:
            raise ValueError(
                "approved_code_continuation requires continuation_of_attempt_id"
            )
        if continuation_id is not None and str(continuation_id) == str(
            payload.get("attempt_id")
        ):
            raise ValueError("proposal continuation cannot reference its own attempt_id")

    @staticmethod
    def _validate_trace_persistence_error(payload: Mapping[str, Any]) -> None:
        error = payload.get("trace_persistence_error")
        if error is None:
            return
        if payload.get("status") != "failed":
            raise ValueError(
                "trace_persistence_error is only valid for failed transitions"
            )
        if not isinstance(error, Mapping):
            raise ValueError("trace_persistence_error must be a mapping")
        missing = sorted(_TRACE_PERSISTENCE_ERROR_FIELDS - error.keys())
        unknown = sorted(error.keys() - _TRACE_PERSISTENCE_ERROR_FIELDS)
        if missing:
            raise ValueError(
                "trace_persistence_error missing fields: " + ", ".join(missing)
            )
        if unknown:
            raise ValueError(
                "trace_persistence_error contains unsupported fields: "
                + ", ".join(unknown)
            )
        if error.get("stage") not in {"start", "finish"}:
            raise ValueError("invalid trace_persistence_error stage")
        if not str(error.get("error_type") or "").strip():
            raise ValueError("trace_persistence_error requires error_type")


def _is_json_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _validate_public_ref(value: Any, *, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"proposal attempt {field} must contain non-empty refs")
    ref = value.strip()
    normalized = ref.replace("\\", "/")
    if ref.lower().startswith("file:"):
        raise ValueError(f"proposal attempt {field} cannot contain file URI refs")
    windows_drive_path = (
        len(normalized) >= 3
        and normalized[0].isalpha()
        and normalized[1:3] == ":/"
    )
    if normalized.startswith("//") or windows_drive_path or contains_absolute_path(ref):
        raise ValueError(f"proposal attempt {field} cannot contain absolute paths")
    path_part = normalized.split("#", 1)[0].split("?", 1)[0]
    if any(part == ".." for part in path_part.split("/")):
        raise ValueError(f"proposal attempt {field} cannot contain parent traversal")


__all__ = [
    "PROPOSAL_ATTEMPT_TRANSITION_SCHEMA",
    "ProposalAttemptRecorder",
]
