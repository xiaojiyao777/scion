"""Traced provider calls and diagnostic receipts for direct V3."""
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
    """One immutable rendering shared by trace and provider call."""

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
    """Diagnostic result of one provider request; never an authority token."""

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


_PROMPT_CALL_RECEIPT_ATTR = "_scion_prompt_call_receipt"


def prompt_call_receipt_from_error(error: BaseException) -> PromptCallReceipt | None:
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


class ProviderCaller:
    """Perform one provider request while preserving request/response traces."""

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
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[Dict[str, Any], PromptCallReceipt]:
        """Call once; optional call context is opaque trace diagnostics only."""

        diagnostic_context = dict(call_context or {})
        _validate_provider_context(
            request_kind=request_kind,
            context=context,
            snapshot=snapshot,
        )

        rendered_system_blocks = [dict(block) for block in snapshot.system_blocks]
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
                provider_call_context=diagnostic_context,
            )
        except KeyboardInterrupt as exc:
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                error_category="provider_call_interrupted",
                error=exc,
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise
        except Exception as exc:
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                error_category="trace_start_failed",
                error=exc,
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise

        trace_ref = _public_trace_ref(trace_path, trace_dir=self._trace_dir)
        manifest_ref = f"{trace_ref}#/prompt_manifest" if trace_ref else None
        raw_response_ref = f"{trace_ref}#/response" if trace_ref else None
        try:
            raw = self._call_provider(
                request_kind=request_kind,
                prompt=snapshot.user_prompt,
                tool=tool,
                system_blocks=rendered_system_blocks,
            )
        except KeyboardInterrupt as exc:
            _finish_trace_best_effort(
                trace,
                trace_path,
                client=self._client,
                error="provider_call_interrupted",
            )
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                trace_ref=trace_ref,
                prompt_manifest_ref=manifest_ref,
                error_category="provider_call_interrupted",
                error=exc,
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise
        except Exception as exc:
            trace_error = _finish_trace_best_effort(
                trace,
                trace_path,
                client=self._client,
                error=str(exc),
            )
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                trace_ref=trace_ref,
                prompt_manifest_ref=manifest_ref,
                error_category="provider_call_failed",
                error=exc,
                trace_persistence_error=trace_error,
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise

        try:
            trace.write_finish(
                trace_path,
                ok=True,
                response=raw,
                llm_usage=_client_usage_metadata(self._client),
            )
        except KeyboardInterrupt as exc:
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                trace_ref=trace_ref,
                prompt_manifest_ref=manifest_ref,
                provider_ok=True,
                error_category="provider_call_interrupted",
                error=exc,
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise
        except Exception as exc:
            receipt = _failed_receipt(
                request_kind,
                snapshot,
                prompt_hash,
                trace_ref=trace_ref,
                prompt_manifest_ref=manifest_ref,
                provider_ok=True,
                error_category="trace_finish_failed",
                error=exc,
                trace_persistence_error=f"trace_finish_failed:{type(exc).__name__}",
            )
            _attach_prompt_call_receipt(exc, receipt)
            raise
        return raw, PromptCallReceipt(
            request_kind=request_kind,
            trace_ref=trace_ref,
            prompt_manifest_ref=manifest_ref,
            raw_response_ref=raw_response_ref,
            prompt_hash=prompt_hash,
            context_digest=snapshot.context_digest,
            provider_ok=True,
            ok=True,
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


def _failed_receipt(
    request_kind: str,
    snapshot: PromptTurnSnapshot,
    prompt_hash: str,
    *,
    error_category: str,
    error: BaseException,
    trace_ref: str | None = None,
    prompt_manifest_ref: str | None = None,
    provider_ok: bool = False,
    trace_persistence_error: str | None = None,
) -> PromptCallReceipt:
    return PromptCallReceipt(
        request_kind=request_kind,
        trace_ref=trace_ref,
        prompt_manifest_ref=prompt_manifest_ref,
        raw_response_ref=None,
        prompt_hash=prompt_hash,
        context_digest=snapshot.context_digest,
        provider_ok=provider_ok,
        ok=False,
        error_category=error_category,
        error_type=type(error).__name__,
        trace_persistence_error=trace_persistence_error,
    )


def _finish_trace_best_effort(
    trace: _TraceWriter,
    trace_path: str | None,
    *,
    client: Any,
    error: str,
) -> str | None:
    try:
        trace.write_finish(
            trace_path,
            ok=False,
            error=error,
            llm_usage=_client_usage_metadata(client),
        )
    except Exception as exc:
        return f"trace_finish_failed:{type(exc).__name__}"
    return None


def _validate_provider_context(
    *,
    request_kind: str,
    context: Mapping[str, Any],
    snapshot: PromptTurnSnapshot,
) -> None:
    if request_kind not in {"hypothesis", "code"}:
        return
    authoritative = snapshot.authoritative_context
    if not isinstance(authoritative, ProposalContextSnapshot):
        raise ValueError("provider snapshot has no ProposalContextSnapshot")
    if authoritative.phase != request_kind or snapshot.render_kind != request_kind:
        raise ValueError("provider snapshot phase does not match request")
    if snapshot.authoritative_context_ref != authoritative.snapshot_id:
        raise ValueError("provider snapshot context reference changed")
    expected_context = authoritative.inputs.provider_context(
        include_renderer_inputs=True
    )
    incoming_context = dict(context)
    if incoming_context != expected_context:
        raise ValueError("provider context differs from ProposalContextSnapshot")
    from scion.proposal.prompt_projection import project_prompt

    projected = project_prompt(request_kind, authoritative)
    if stable_digest(projected.structured_context, length=64) != snapshot.context_digest:
        raise ValueError("provider snapshot context digest changed")
    if projected.system_blocks != snapshot.system_blocks:
        raise ValueError("provider snapshot system blocks changed")
    if projected.user_prompt != snapshot.user_prompt:
        raise ValueError("provider snapshot user prompt changed")


def _context_with_embedded_prompt_manifest(
    context: Mapping[str, Any],
    *,
    snapshot: PromptTurnSnapshot,
    request_kind: str,
) -> Dict[str, Any]:
    traced = dict(context)
    traced["_scion_prompt_manifest"] = build_api_visible_prompt_manifest(
        session_id=f"prompt-call-{uuid.uuid4()}",
        phase=request_kind,
        call_kind=request_kind,
        prompt_context=context,
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
    if not callable(getter):
        return None
    try:
        usage = getter()
    except Exception:
        return None
    return dict(usage) if isinstance(usage, dict) else None


__all__ = [
    "PromptCallReceipt",
    "PromptTurnSnapshot",
    "ProviderCaller",
    "prompt_call_receipt_from_error",
]
