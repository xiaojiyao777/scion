"""Single owner for traced proposal-provider calls and immutable receipts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from scion.core.public_refs import public_artifact_ref
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_manifest import (
    build_api_visible_prompt_manifest,
    stable_digest,
)
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash

from .trace import _TraceWriter, _client_request_policy


@dataclass(frozen=True)
class PromptTurnSnapshot:
    """One immutable rendering shared by manifest, trace, and provider call."""

    render_kind: str
    system_blocks: tuple[Mapping[str, Any], ...]
    user_prompt: str
    context_digest: str
    provider_tool: Mapping[str, Any]
    allowed_change_loci: tuple[str, ...] = ()
    authoritative_context_ref: str | None = None
    authoritative_context: ProposalContextSnapshot | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class PromptCallReceipt:
    """Mode-neutral audit receipt for one rendered provider call."""

    request_kind: str
    trace_ref: str | None
    prompt_manifest_ref: str | None
    raw_response_ref: str | None
    prompt_hash: str
    context_digest: str
    provider_ok: bool
    ok: bool
    error_category: str | None = None
    error_type: str | None = None
    trace_persistence_error: str | None = None
    attempt_id: str | None = None
    attempt_started_event_id: str | None = None
    continuation_of_attempt_id: str | None = None


_PROMPT_CALL_RECEIPT_ATTR = "_scion_prompt_call_receipt"


def prompt_call_receipt_from_error(error: BaseException) -> PromptCallReceipt | None:
    """Return the call-local receipt attached to an unchanged raised error."""

    receipt = getattr(error, _PROMPT_CALL_RECEIPT_ATTR, None)
    return receipt if isinstance(receipt, PromptCallReceipt) else None


def _attach_prompt_call_receipt(
    error: BaseException,
    receipt: PromptCallReceipt,
) -> None:
    try:
        setattr(error, _PROMPT_CALL_RECEIPT_ATTR, receipt)
    except Exception:
        return


class ProviderCallOwner:
    """Own prompt-manifest, trace, provider, and receipt ordering."""

    def __init__(
        self,
        client: Any,
        model: str,
        *,
        trace_dir: str | None,
    ) -> None:
        self._client = client
        self._model = model
        self._trace_dir = trace_dir

    def call_with_receipt(
        self,
        *,
        request_kind: str,
        tool: Dict[str, Any],
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        attempt_audit: Mapping[str, Any] | None = None,
    ) -> tuple[Dict[str, Any], PromptCallReceipt]:
        """Call the provider with one snapshot and expose its trace identity."""

        _validate_authoritative_provider_context(
            request_kind=request_kind,
            context=context,
            snapshot=snapshot,
        )
        normalized_attempt_audit = _validate_provider_call_attempt_audit(
            attempt_audit,
            request_kind=request_kind,
        )

        rendered_system_blocks = list(snapshot.system_blocks)
        prompt_hash = _provider_prompt_hash(
            snapshot.system_blocks,
            snapshot.user_prompt,
        )
        trace_context = _context_with_embedded_prompt_manifest(
            context,
            snapshot=snapshot,
            request_kind=request_kind,
        )
        trace = _TraceWriter(self._trace_dir)
        request_policy = _client_request_policy(
            self._client,
            request_kind=request_kind,
            tool=tool,
            model=self._model,
        )
        try:
            trace_path = trace.write_start(
                request_kind=request_kind,
                model=self._model,
                tool=tool,
                prompt=snapshot.user_prompt,
                system_blocks=rendered_system_blocks,
                context=trace_context,
                request_policy=request_policy,
                provider_call_attempt=normalized_attempt_audit,
            )
        except KeyboardInterrupt as exc:
            interrupted = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=None,
                prompt_manifest_ref=None,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=False,
                ok=False,
                error_category="provider_call_interrupted",
                error_type=type(exc).__name__,
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, interrupted)
            raise
        except Exception as exc:
            failed = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=None,
                prompt_manifest_ref=None,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=False,
                ok=False,
                error_category="trace_start_failed",
                error_type=type(exc).__name__,
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, failed)
            raise
        trace_ref = _public_trace_ref(trace_path, trace_dir=self._trace_dir)
        prompt_manifest_ref = (
            f"{trace_ref}#/prompt_manifest" if trace_ref else None
        )
        raw_response_ref = f"{trace_ref}#/response" if trace_ref else None
        try:
            raw = self._call_provider(
                request_kind=request_kind,
                prompt=snapshot.user_prompt,
                tool=tool,
                system_blocks=rendered_system_blocks,
            )
        except KeyboardInterrupt as exc:
            try:
                trace.write_finish(
                    trace_path,
                    ok=False,
                    error="provider_call_interrupted",
                    llm_usage=_client_usage_metadata(self._client),
                )
            except Exception:
                pass
            interrupted = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=trace_ref,
                prompt_manifest_ref=prompt_manifest_ref,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=False,
                ok=False,
                error_category="provider_call_interrupted",
                error_type=type(exc).__name__,
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, interrupted)
            raise
        except Exception as exc:
            trace_persistence_error = None
            try:
                trace.write_finish(
                    trace_path,
                    ok=False,
                    error=str(exc),
                    llm_usage=_client_usage_metadata(self._client),
                )
            except Exception as trace_exc:
                trace_persistence_error = (
                    f"trace_finish_failed:{type(trace_exc).__name__}"
                )
            failed = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=trace_ref,
                prompt_manifest_ref=prompt_manifest_ref,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=False,
                ok=False,
                error_category="provider_call_failed",
                error_type=type(exc).__name__,
                trace_persistence_error=trace_persistence_error,
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, failed)
            raise
        try:
            trace.write_finish(
                trace_path,
                ok=True,
                response=raw,
                llm_usage=_client_usage_metadata(self._client),
            )
        except KeyboardInterrupt as exc:
            interrupted = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=trace_ref,
                prompt_manifest_ref=prompt_manifest_ref,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=True,
                ok=False,
                error_category="provider_call_interrupted",
                error_type=type(exc).__name__,
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, interrupted)
            raise
        except Exception as exc:
            failed = PromptCallReceipt(
                request_kind=request_kind,
                trace_ref=trace_ref,
                prompt_manifest_ref=prompt_manifest_ref,
                raw_response_ref=None,
                prompt_hash=prompt_hash,
                context_digest=snapshot.context_digest,
                provider_ok=True,
                ok=False,
                error_category="trace_finish_failed",
                error_type=type(exc).__name__,
                trace_persistence_error=(
                    f"trace_finish_failed:{type(exc).__name__}"
                ),
                **_receipt_attempt_fields(normalized_attempt_audit),
            )
            _attach_prompt_call_receipt(exc, failed)
            raise
        return raw, PromptCallReceipt(
            request_kind=request_kind,
            trace_ref=trace_ref,
            prompt_manifest_ref=prompt_manifest_ref,
            raw_response_ref=raw_response_ref,
            prompt_hash=prompt_hash,
            context_digest=snapshot.context_digest,
            provider_ok=True,
            ok=True,
            **_receipt_attempt_fields(normalized_attempt_audit),
        )

    def _call_provider(
        self,
        *,
        request_kind: str,
        prompt: str,
        tool: Dict[str, Any],
        system_blocks: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._client.call_with_tool(
            prompt,
            tool,
            self._model,
            system_blocks=system_blocks,
            request_kind=request_kind,
        )


def _validate_provider_call_attempt_audit(
    attempt_audit: Mapping[str, Any] | None,
    *,
    request_kind: str,
) -> dict[str, Any] | None:
    if attempt_audit is None:
        return None
    expected_fields = {
        "schema_version",
        "attempt_id",
        "phase",
        "attempt_kind",
        "continuation_of_attempt_id",
        "hypothesis_attempt_id",
        "started_lineage_event_id",
    }
    if set(attempt_audit) != expected_fields:
        raise ValueError("provider call attempt audit has unsupported shape")
    normalized = dict(attempt_audit)
    if normalized.get("schema_version") != "provider-call-attempt-audit.v1":
        raise ValueError("provider call attempt audit has unsupported schema")
    if normalized.get("phase") != request_kind:
        raise ValueError("provider call attempt audit phase mismatch")
    for field in (
        "attempt_id",
        "attempt_kind",
        "hypothesis_attempt_id",
        "started_lineage_event_id",
    ):
        if not str(normalized.get(field) or "").strip():
            raise ValueError(f"provider call attempt audit requires {field}")
    continuation = normalized.get("continuation_of_attempt_id")
    if request_kind == "hypothesis":
        if normalized.get("attempt_kind") != "initial":
            raise ValueError("hypothesis provider call requires initial attempt kind")
        if continuation is not None:
            raise ValueError("hypothesis provider call cannot be a continuation")
        if normalized.get("hypothesis_attempt_id") != normalized.get("attempt_id"):
            raise ValueError("hypothesis provider call attempt identity mismatch")
    else:
        if normalized.get("attempt_kind") != "approved_code_continuation":
            raise ValueError(
                "code provider call requires approved continuation attempt kind"
            )
        if not str(continuation or "").strip():
            raise ValueError("code provider call requires continuation identity")
        if str(continuation) == str(normalized.get("attempt_id")):
            raise ValueError("code provider call cannot continue itself")
    return normalized


def _receipt_attempt_fields(
    attempt_audit: Mapping[str, Any] | None,
) -> dict[str, str | None]:
    if not isinstance(attempt_audit, Mapping):
        return {}
    return {
        "attempt_id": str(attempt_audit.get("attempt_id") or "") or None,
        "attempt_started_event_id": (
            str(attempt_audit.get("started_lineage_event_id") or "") or None
        ),
        "continuation_of_attempt_id": (
            str(attempt_audit.get("continuation_of_attempt_id") or "") or None
        ),
    }


def _validate_authoritative_provider_context(
    *,
    request_kind: str,
    context: Mapping[str, Any],
    snapshot: PromptTurnSnapshot,
) -> None:
    phase = request_kind if request_kind in {"hypothesis", "code"} else None
    if phase is None:
        return
    from scion.proposal.prompt_projection_authority import (
        ProposalPromptProjectionAuthority,
    )

    authoritative = snapshot.authoritative_context
    if not isinstance(authoritative, ProposalContextSnapshot):
        raise ValueError("provider snapshot has no authoritative context owner")
    if authoritative.phase != phase or snapshot.render_kind != request_kind:
        raise ValueError("provider snapshot phase does not match authority")
    if snapshot.authoritative_context_ref != authoritative.snapshot_id:
        raise ValueError("provider snapshot is not bound to authoritative context")
    expected_context = authoritative.inputs.provider_context(
        include_renderer_inputs=True
    )
    incoming_context = dict(context)
    if incoming_context != expected_context:
        raise ValueError("provider context does not match authoritative projection")
    if stable_digest(incoming_context, length=64) != stable_digest(
        expected_context,
        length=64,
    ):
        raise ValueError("provider context digest does not match authority")
    try:
        projected = ProposalPromptProjectionAuthority.project(
            phase,
            authoritative,
        )
    except ValueError as exc:
        raise ValueError(
            "provider snapshot has no authoritative projection mode"
        ) from exc
    if projected.context_digest != snapshot.context_digest:
        raise ValueError("provider snapshot context digest does not match authority")
    if projected.system_blocks != snapshot.system_blocks:
        raise ValueError("provider snapshot system blocks do not match authority")
    if projected.user_prompt != snapshot.user_prompt:
        raise ValueError("provider snapshot user prompt does not match authority")


def _context_with_embedded_prompt_manifest(
    context: Mapping[str, Any],
    *,
    snapshot: PromptTurnSnapshot,
    request_kind: str,
) -> Dict[str, Any]:
    """Attach audit-only manifest data after the provider bytes are frozen."""

    traced = dict(context)
    existing = traced.get("_scion_prompt_manifest")
    current_prompt_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    if (
        isinstance(existing, Mapping)
        and existing
        and str(existing.get("prompt_hash") or "") == current_prompt_hash
    ):
        return traced
    traced["_scion_prompt_manifest"] = build_api_visible_prompt_manifest(
        session_id=f"prompt-call-{uuid.uuid4()}",
        phase=request_kind,
        call_kind=request_kind,
        prompt_context=context,
        observations=(),
        call_index=1,
        system_blocks=snapshot.system_blocks,
        user_prompt=snapshot.user_prompt,
        context_digest_override=snapshot.context_digest,
        authoritative_context_ref=snapshot.authoritative_context_ref,
    )
    return traced


def _public_trace_ref(
    trace_path: str | None,
    *,
    trace_dir: str | None,
) -> str | None:
    if not trace_path:
        return None
    base_dir = Path(trace_dir).resolve().parent if trace_dir else None
    return public_artifact_ref(trace_path, base_dir=base_dir, kind="artifact")


def _client_usage_metadata(client: Any) -> Dict[str, Any] | None:
    getter = getattr(client, "get_last_usage_metadata", None)
    if getter is None:
        return None
    try:
        usage = getter()
    except Exception:
        return None
    return dict(usage) if isinstance(usage, dict) else None


__all__ = [
    "PromptCallReceipt",
    "PromptTurnSnapshot",
    "ProviderCallOwner",
    "prompt_call_receipt_from_error",
]
