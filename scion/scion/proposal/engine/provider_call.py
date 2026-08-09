"""Provider calls with optional, non-authoritative diagnostics for direct V3."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from scion.core.public_refs import public_artifact_ref
from scion.proposal.context_snapshot import ProposalContextSnapshot
from .trace import _TraceWriter, _client_request_policy


@dataclass(frozen=True)
class PromptTurnSnapshot:
    """One immutable rendering shared by trace and provider call."""

    render_kind: str
    system_blocks: tuple[Mapping[str, Any], ...]
    user_prompt: str
    provider_tool: Mapping[str, Any]
    allowed_change_loci: tuple[str, ...] = ()
    authoritative_context: ProposalContextSnapshot | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class ProviderCallDiagnostics:
    """Best-effort observations about one provider request."""

    request_kind: str
    trace_ref: str | None
    raw_response_ref: str | None
    provider_ok: bool
    ok: bool
    error_category: str | None = None
    error_type: str | None = None
    trace_persistence_error: str | None = None
    provider_response_diagnostics: Mapping[str, Any] | None = None


_PROVIDER_CALL_DIAGNOSTICS_ATTR = "_scion_provider_call_diagnostics"


def provider_call_diagnostics_from_error(
    error: BaseException,
) -> ProviderCallDiagnostics | None:
    diagnostics = getattr(error, _PROVIDER_CALL_DIAGNOSTICS_ATTR, None)
    return diagnostics if isinstance(diagnostics, ProviderCallDiagnostics) else None


def _attach_provider_call_diagnostics(
    error: BaseException,
    diagnostics: ProviderCallDiagnostics,
) -> None:
    try:
        setattr(error, _PROVIDER_CALL_DIAGNOSTICS_ATTR, diagnostics)
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

    def call(
        self,
        *,
        request_kind: str,
        tool: Dict[str, Any],
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[Dict[str, Any], ProviderCallDiagnostics]:
        """Call once; optional call context is opaque trace diagnostics only."""

        _reset_client_call_observations(self._client)
        diagnostic_context = dict(call_context or {})
        _validate_provider_context(
            request_kind=request_kind,
            context=context,
            snapshot=snapshot,
        )

        rendered_system_blocks = [dict(block) for block in snapshot.system_blocks]
        trace = _TraceWriter(self._trace_dir)
        request_policy = _client_request_policy(
            self._client,
            request_kind=request_kind,
            tool=tool,
            model=self._model,
        )
        trace_persistence_error: str | None = None
        try:
            trace_path = trace.write_start(
                request_kind=request_kind,
                model=self._model,
                tool=tool,
                prompt=snapshot.user_prompt,
                system_blocks=rendered_system_blocks,
                context=context,
                request_policy=request_policy,
                provider_call_context=diagnostic_context,
            )
        except Exception as exc:
            trace_path = None
            trace_persistence_error = f"trace_start_failed:{type(exc).__name__}"

        trace_ref = _public_trace_ref(trace_path, trace_dir=self._trace_dir)
        raw_response_ref = f"{trace_ref}#/response" if trace_ref else None
        try:
            raw = self._call_provider(
                request_kind=request_kind,
                prompt=snapshot.user_prompt,
                tool=tool,
                system_blocks=rendered_system_blocks,
            )
        except KeyboardInterrupt as exc:
            response_diagnostics = _client_response_diagnostics(self._client)
            _finish_trace_best_effort(
                trace,
                trace_path,
                client=self._client,
                error="provider_call_interrupted",
                provider_response_diagnostics=response_diagnostics,
            )
            diagnostics = _failed_diagnostics(
                request_kind,
                trace_ref=trace_ref,
                error_category="provider_call_interrupted",
                error=exc,
                trace_persistence_error=trace_persistence_error,
                provider_response_diagnostics=response_diagnostics,
            )
            _attach_provider_call_diagnostics(exc, diagnostics)
            raise
        except Exception as exc:
            response_diagnostics = _client_response_diagnostics(self._client)
            trace_error = _finish_trace_best_effort(
                trace,
                trace_path,
                client=self._client,
                error=str(exc),
                provider_response_diagnostics=response_diagnostics,
            )
            diagnostics = _failed_diagnostics(
                request_kind,
                trace_ref=trace_ref,
                error_category="provider_call_failed",
                error=exc,
                trace_persistence_error=trace_error or trace_persistence_error,
                provider_response_diagnostics=response_diagnostics,
            )
            _attach_provider_call_diagnostics(exc, diagnostics)
            raise

        response_diagnostics = _client_response_diagnostics(self._client)
        try:
            trace.write_finish(
                trace_path,
                ok=True,
                response=raw,
                llm_usage=_client_usage_metadata(self._client),
                provider_response_diagnostics=response_diagnostics,
            )
        except Exception as exc:
            raw_response_ref = None
            trace_persistence_error = f"trace_finish_failed:{type(exc).__name__}"
        return raw, ProviderCallDiagnostics(
            request_kind=request_kind,
            trace_ref=trace_ref,
            raw_response_ref=raw_response_ref,
            provider_ok=True,
            ok=True,
            trace_persistence_error=trace_persistence_error,
            provider_response_diagnostics=response_diagnostics,
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


def _failed_diagnostics(
    request_kind: str,
    *,
    error_category: str,
    error: BaseException,
    trace_ref: str | None = None,
    provider_ok: bool = False,
    trace_persistence_error: str | None = None,
    provider_response_diagnostics: Mapping[str, Any] | None = None,
) -> ProviderCallDiagnostics:
    return ProviderCallDiagnostics(
        request_kind=request_kind,
        trace_ref=trace_ref,
        raw_response_ref=None,
        provider_ok=provider_ok,
        ok=False,
        error_category=error_category,
        error_type=type(error).__name__,
        trace_persistence_error=trace_persistence_error,
        provider_response_diagnostics=provider_response_diagnostics,
    )


def _finish_trace_best_effort(
    trace: _TraceWriter,
    trace_path: str | None,
    *,
    client: Any,
    error: str,
    provider_response_diagnostics: Mapping[str, Any] | None,
) -> str | None:
    try:
        trace.write_finish(
            trace_path,
            ok=False,
            error=error,
            llm_usage=_client_usage_metadata(client),
            provider_response_diagnostics=provider_response_diagnostics,
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
    expected_context = authoritative.inputs.provider_context(
        include_renderer_inputs=True
    )
    incoming_context = dict(context)
    if incoming_context != expected_context:
        raise ValueError("provider context differs from ProposalContextSnapshot")
    from scion.proposal.prompt_projection import project_prompt

    projected = project_prompt(request_kind, authoritative)
    if projected.system_blocks != snapshot.system_blocks:
        raise ValueError("provider snapshot system blocks changed")
    if projected.user_prompt != snapshot.user_prompt:
        raise ValueError("provider snapshot user prompt changed")


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


def _reset_client_call_observations(client: Any) -> None:
    reset = getattr(client, "reset_call_observations", None)
    if not callable(reset):
        return
    try:
        reset()
    except Exception:  # noqa: BLE001 - observations must not affect provider behavior
        return


def _client_response_diagnostics(client: Any) -> dict[str, Any] | None:
    getter = getattr(client, "get_last_response_diagnostics", None)
    if not callable(getter):
        return None
    try:
        diagnostics = getter()
    except Exception:  # noqa: BLE001 - diagnostics must not affect provider behavior
        return None
    return dict(diagnostics) if isinstance(diagnostics, Mapping) else None


__all__ = [
    "ProviderCallDiagnostics",
    "PromptTurnSnapshot",
    "ProviderCaller",
    "provider_call_diagnostics_from_error",
]
