"""Single owner for traced proposal-provider calls and immutable receipts."""

from __future__ import annotations

import contextvars
import enum
import hashlib
import json
import threading
import uuid
import weakref
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping

from scion.core.models import HypothesisProposal
from scion.core.public_refs import public_artifact_ref
from scion.lineage import proposal_attempt_owner as _proposal_attempt_owner
from scion.lineage import sqlite_connection as _sqlite
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


class GeneratedHypothesisResultError(RuntimeError):
    """Base error for the dormant provider-issued hypothesis proof."""


class InvalidGeneratedHypothesisResultError(
    TypeError,
    GeneratedHypothesisResultError,
):
    """A value is not an exact proof issued by the provider boundary."""


class GeneratedHypothesisResultLifecycleError(GeneratedHypothesisResultError):
    """A genuine result crossed its bound execution context or was reused."""


class ProviderGenerationPermit:
    """Sealed one-shot authority for one started hypothesis provider call."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls,
        *_args: object,
        **_kwargs: object,
    ) -> "ProviderGenerationPermit":
        raise InvalidGeneratedHypothesisResultError(
            "ProviderGenerationPermit is issued only for a bound started attempt"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("ProviderGenerationPermit is sealed")

    def __copy__(self) -> "ProviderGenerationPermit":
        raise InvalidGeneratedHypothesisResultError(
            "ProviderGenerationPermit cannot be copied"
        )

    def __deepcopy__(
        self,
        _memo: dict[int, object],
    ) -> "ProviderGenerationPermit":
        raise InvalidGeneratedHypothesisResultError(
            "ProviderGenerationPermit cannot be copied"
        )

    def __reduce__(self) -> object:
        raise InvalidGeneratedHypothesisResultError(
            "ProviderGenerationPermit cannot be pickled"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidGeneratedHypothesisResultError(
            "ProviderGenerationPermit cannot be pickled"
        )


class _ProviderGenerationPermitPhase(enum.Enum):
    ISSUED = enum.auto()
    START_BOUND = enum.auto()
    RESULT_BOUND = enum.auto()


@dataclass(slots=True)
class _ProviderGenerationPermitState:
    started_attempt: _proposal_attempt_owner.StartedHypothesisAttempt
    attempt_audit: Mapping[str, Any]
    expected_context_digest: str
    expected_prompt_hash: str
    thread_id: int
    context_probe: contextvars.ContextVar[object | None]
    context_token: contextvars.Token[object | None]
    phase: _ProviderGenerationPermitPhase = _ProviderGenerationPermitPhase.ISSUED
    result_ref: weakref.ReferenceType[GeneratedHypothesisResult] | None = None


class GeneratedHypothesisResult:
    """Sealed one-shot proof of one persisted, parsed hypothesis response."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls,
        *_args: object,
        **_kwargs: object,
    ) -> "GeneratedHypothesisResult":
        raise InvalidGeneratedHypothesisResultError(
            "GeneratedHypothesisResult is issued only by the provider boundary"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("GeneratedHypothesisResult is sealed")

    def __copy__(self) -> "GeneratedHypothesisResult":
        raise InvalidGeneratedHypothesisResultError(
            "GeneratedHypothesisResult cannot be copied"
        )

    def __deepcopy__(
        self,
        _memo: dict[int, object],
    ) -> "GeneratedHypothesisResult":
        raise InvalidGeneratedHypothesisResultError(
            "GeneratedHypothesisResult cannot be copied"
        )

    def __reduce__(self) -> object:
        raise InvalidGeneratedHypothesisResultError(
            "GeneratedHypothesisResult cannot be pickled"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidGeneratedHypothesisResultError(
            "GeneratedHypothesisResult cannot be pickled"
        )


@dataclass(slots=True)
class _GeneratedHypothesisResultState:
    permit: ProviderGenerationPermit
    started_attempt: object
    attempt_id: str
    started_event_id: str
    context_digest: str
    prompt_hash: str
    receipt: PromptCallReceipt
    trace_ref: str
    prompt_manifest_ref: str
    raw_response_ref: str
    proposal_canonical_bytes: bytes
    proposal_sha256: str
    thread_id: int
    context_probe: contextvars.ContextVar[object | None]
    context_token: contextvars.Token[object | None]
    consumed: bool = False


@dataclass(frozen=True, slots=True)
class _ConsumedGeneratedHypothesisResult:
    """Immutable facts returned after exact proof consumption."""

    attempt_id: str
    started_event_id: str
    context_digest: str
    prompt_hash: str
    receipt: PromptCallReceipt
    trace_ref: str
    prompt_manifest_ref: str
    raw_response_ref: str
    proposal_canonical_bytes: bytes
    proposal_sha256: str

    def detached_hypothesis(self) -> HypothesisProposal:
        """Return a fresh value copy; this value is data, never authority."""

        return _hypothesis_from_canonical_bytes(self.proposal_canonical_bytes)


_GENERATED_HYPOTHESIS_RESULT_STATES: weakref.WeakKeyDictionary[
    GeneratedHypothesisResult,
    _GeneratedHypothesisResultState,
] = weakref.WeakKeyDictionary()
_GENERATED_HYPOTHESIS_RESULT_STATES_LOCK = threading.RLock()
_PROVIDER_GENERATION_PERMIT_STATES: weakref.WeakKeyDictionary[
    ProviderGenerationPermit,
    _ProviderGenerationPermitState,
] = weakref.WeakKeyDictionary()
_PROVIDER_GENERATION_PERMIT_STATES_LOCK = threading.RLock()
_GENERATED_HYPOTHESIS_CONTEXT_PROOF: contextvars.ContextVar[object | None] = (
    contextvars.ContextVar(
        "scion_generated_hypothesis_result_context_proof",
        default=None,
    )
)
_PROVIDER_GENERATION_PERMIT_CONTEXT_PROOF: contextvars.ContextVar[object | None] = (
    contextvars.ContextVar(
        "scion_provider_generation_permit_context_proof",
        default=None,
    )
)


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
        _prompt_manifest_session_id: str | None = None,
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
            session_id=_prompt_manifest_session_id,
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
        prompt_manifest_ref = f"{trace_ref}#/prompt_manifest" if trace_ref else None
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
                trace_persistence_error=(f"trace_finish_failed:{type(exc).__name__}"),
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


def _issue_provider_generation_permit(
    *,
    started_attempt: _proposal_attempt_owner.StartedHypothesisAttempt,
    committed_snapshot: _sqlite._IndependentReadSnapshot,
) -> ProviderGenerationPermit:
    """Consume one persisted START authority and issue its exact call permit."""

    binding = _proposal_attempt_owner._bind_started_hypothesis_attempt_to_provider(
        started_attempt,
        committed_snapshot,
    )
    normalized_attempt_audit = _validate_provider_call_attempt_audit(
        binding.attempt_audit,
        request_kind="hypothesis",
    )
    if normalized_attempt_audit is None:
        raise InvalidGeneratedHypothesisResultError(
            "provider generation permit requires attempt audit identity"
        )
    context_probe = _PROVIDER_GENERATION_PERMIT_CONTEXT_PROOF
    context_token = context_probe.set(object())
    permit = object.__new__(ProviderGenerationPermit)
    state = _ProviderGenerationPermitState(
        started_attempt=started_attempt,
        attempt_audit=MappingProxyType(dict(normalized_attempt_audit)),
        expected_context_digest=binding.context_digest,
        expected_prompt_hash=binding.prompt_hash,
        thread_id=threading.get_ident(),
        context_probe=context_probe,
        context_token=context_token,
    )
    with _PROVIDER_GENERATION_PERMIT_STATES_LOCK:
        _PROVIDER_GENERATION_PERMIT_STATES[permit] = state
    return permit


def _claim_provider_generation_permit(
    permit: ProviderGenerationPermit,
) -> _ProviderGenerationPermitState:
    """Irreversibly bind one permit before any provider transport is invoked."""

    if type(permit) is not ProviderGenerationPermit:
        raise InvalidGeneratedHypothesisResultError(
            "operation requires an exact ProviderGenerationPermit"
        )
    with _PROVIDER_GENERATION_PERMIT_STATES_LOCK:
        state = _PROVIDER_GENERATION_PERMIT_STATES.get(permit)
        if state is None:
            raise InvalidGeneratedHypothesisResultError(
                "ProviderGenerationPermit was not issued"
            )
        if state.phase is not _ProviderGenerationPermitPhase.ISSUED:
            raise GeneratedHypothesisResultLifecycleError(
                "ProviderGenerationPermit is already bound"
            )
        if state.thread_id != threading.get_ident():
            raise GeneratedHypothesisResultLifecycleError(
                "ProviderGenerationPermit cannot cross threads"
            )
        _prove_provider_generation_permit_context(state)
        state.phase = _ProviderGenerationPermitPhase.START_BOUND
        return state


def _generate_hypothesis_result_with_receipt(
    owner: ProviderCallOwner,
    *,
    context: Dict[str, Any],
    snapshot: PromptTurnSnapshot,
    permit: ProviderGenerationPermit,
) -> tuple[
    HypothesisProposal,
    PromptCallReceipt,
    GeneratedHypothesisResult,
]:
    """Dormant real-call seam that privately issues one generated-H proof.

    The existing production facade intentionally does not call this seam.  A
    later Registry cutover can do so only after it owns the sealed started
    attempt supplied here.  Keeping provider call, successful trace finish,
    parse, canonicalization, and issuance in one frame prevents a caller from
    combining an audit receipt with a substituted proposal.
    """

    if type(owner) is not ProviderCallOwner:
        raise InvalidGeneratedHypothesisResultError(
            "generated hypothesis call requires an exact ProviderCallOwner"
        )
    permit_state = _claim_provider_generation_permit(permit)
    normalized_attempt_audit = dict(permit_state.attempt_audit)
    if (
        snapshot.context_digest != permit_state.expected_context_digest
        or _provider_prompt_hash(snapshot.system_blocks, snapshot.user_prompt)
        != permit_state.expected_prompt_hash
    ):
        raise InvalidGeneratedHypothesisResultError(
            "provider generation input does not match the persisted START"
        )
    prompt_manifest_session_id = f"prompt-call-{uuid.uuid4()}"

    raw, receipt = owner.call_with_receipt(
        request_kind="hypothesis",
        tool=dict(snapshot.provider_tool),
        context=context,
        snapshot=snapshot,
        attempt_audit=normalized_attempt_audit,
        _prompt_manifest_session_id=prompt_manifest_session_id,
    )
    try:
        from .parsing import _parse_hypothesis

        hypothesis = _parse_hypothesis(
            raw,
            allowed_change_loci=snapshot.allowed_change_loci,
        )
    except Exception as exc:
        failed = replace(
            receipt,
            ok=False,
            error_category="response_parse_failed",
            error_type=type(exc).__name__,
        )
        _attach_prompt_call_receipt(exc, failed)
        raise

    try:
        result_state = _validated_generated_hypothesis_result_state(
            owner=owner,
            permit=permit,
            started_attempt=permit_state.started_attempt,
            attempt_audit=normalized_attempt_audit,
            prompt_manifest_session_id=prompt_manifest_session_id,
            context=context,
            snapshot=snapshot,
            receipt=receipt,
            raw_response=raw,
            hypothesis=hypothesis,
        )
        result = object.__new__(GeneratedHypothesisResult)
        _bind_provider_generation_result(
            permit,
            result=result,
            result_state=result_state,
        )
    except Exception as exc:
        failed = replace(
            receipt,
            ok=False,
            error_category="generated_result_issuance_failed",
            error_type=type(exc).__name__,
        )
        _attach_prompt_call_receipt(exc, failed)
        raise
    return hypothesis, receipt, result


def _validated_generated_hypothesis_result_state(
    *,
    owner: ProviderCallOwner,
    permit: ProviderGenerationPermit,
    started_attempt: object,
    attempt_audit: Mapping[str, Any],
    prompt_manifest_session_id: str,
    context: Mapping[str, Any],
    snapshot: PromptTurnSnapshot,
    receipt: PromptCallReceipt,
    raw_response: Mapping[str, Any],
    hypothesis: HypothesisProposal,
) -> _GeneratedHypothesisResultState:
    """Validate bound facts without exposing an object-issuance operation."""

    if type(receipt) is not PromptCallReceipt:
        raise InvalidGeneratedHypothesisResultError(
            "generated result requires the exact provider receipt type"
        )
    attempt_id = str(attempt_audit.get("attempt_id") or "")
    started_event_id = str(attempt_audit.get("started_lineage_event_id") or "")
    if not attempt_id or not started_event_id:
        raise InvalidGeneratedHypothesisResultError(
            "generated result requires complete started-attempt identity"
        )
    if (
        receipt.request_kind != "hypothesis"
        or receipt.provider_ok is not True
        or receipt.ok is not True
        or receipt.error_category is not None
        or receipt.error_type is not None
        or receipt.trace_persistence_error is not None
    ):
        raise InvalidGeneratedHypothesisResultError(
            "generated result requires a successful persisted provider call"
        )
    if (
        receipt.attempt_id != attempt_id
        or receipt.attempt_started_event_id != started_event_id
        or receipt.continuation_of_attempt_id is not None
    ):
        raise InvalidGeneratedHypothesisResultError(
            "provider receipt does not match the exact started attempt"
        )
    expected_prompt_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    if (
        receipt.context_digest != snapshot.context_digest
        or receipt.prompt_hash != expected_prompt_hash
    ):
        raise InvalidGeneratedHypothesisResultError(
            "provider receipt does not match the exact context and prompt"
        )
    trace_ref = _required_durable_ref(receipt.trace_ref, label="trace")
    prompt_manifest_ref = _required_durable_ref(
        receipt.prompt_manifest_ref,
        label="prompt manifest",
    )
    raw_response_ref = _required_durable_ref(
        receipt.raw_response_ref,
        label="raw response",
    )
    if prompt_manifest_ref != f"{trace_ref}#/prompt_manifest":
        raise InvalidGeneratedHypothesisResultError(
            "prompt manifest ref is not bound to the trace"
        )
    if raw_response_ref != f"{trace_ref}#/response":
        raise InvalidGeneratedHypothesisResultError(
            "raw response ref is not bound to the trace"
        )
    _validate_persisted_generated_hypothesis_trace(
        owner=owner,
        trace_ref=trace_ref,
        receipt=receipt,
        snapshot=snapshot,
        context=context,
        prompt_manifest_session_id=prompt_manifest_session_id,
        attempt_audit=attempt_audit,
        raw_response=raw_response,
    )

    proposal_canonical_bytes = _canonical_hypothesis_bytes(hypothesis)
    proposal_sha256 = hashlib.sha256(proposal_canonical_bytes).hexdigest()
    context_probe = _GENERATED_HYPOTHESIS_CONTEXT_PROOF
    context_token = context_probe.set(object())
    return _GeneratedHypothesisResultState(
        permit=permit,
        started_attempt=started_attempt,
        attempt_id=attempt_id,
        started_event_id=started_event_id,
        context_digest=receipt.context_digest,
        prompt_hash=receipt.prompt_hash,
        receipt=receipt,
        trace_ref=trace_ref,
        prompt_manifest_ref=prompt_manifest_ref,
        raw_response_ref=raw_response_ref,
        proposal_canonical_bytes=proposal_canonical_bytes,
        proposal_sha256=proposal_sha256,
        thread_id=threading.get_ident(),
        context_probe=context_probe,
        context_token=context_token,
    )


def _consume_generated_hypothesis_result(
    result: GeneratedHypothesisResult,
    *,
    permit: ProviderGenerationPermit,
    started_attempt: object,
    receipt: PromptCallReceipt,
) -> _ConsumedGeneratedHypothesisResult:
    """Consume one exact provider proof and return its immutable bound facts."""

    if type(result) is not GeneratedHypothesisResult:
        raise InvalidGeneratedHypothesisResultError(
            "operation requires an exact GeneratedHypothesisResult"
        )
    if type(permit) is not ProviderGenerationPermit:
        raise InvalidGeneratedHypothesisResultError(
            "operation requires an exact ProviderGenerationPermit"
        )
    with _PROVIDER_GENERATION_PERMIT_STATES_LOCK:
        permit_state = _PROVIDER_GENERATION_PERMIT_STATES.get(permit)
        if permit_state is None:
            raise InvalidGeneratedHypothesisResultError(
                "ProviderGenerationPermit was not issued"
            )
        if (
            permit_state.phase is not _ProviderGenerationPermitPhase.RESULT_BOUND
            or permit_state.result_ref is None
            or permit_state.result_ref() is not result
        ):
            raise InvalidGeneratedHypothesisResultError(
                "ProviderGenerationPermit is not bound to the exact result"
            )
        if permit_state.thread_id != threading.get_ident():
            raise GeneratedHypothesisResultLifecycleError(
                "ProviderGenerationPermit cannot cross threads"
            )
        _prove_provider_generation_permit_context(permit_state)
    with _GENERATED_HYPOTHESIS_RESULT_STATES_LOCK:
        state = _GENERATED_HYPOTHESIS_RESULT_STATES.get(result)
        if state is None:
            raise InvalidGeneratedHypothesisResultError(
                "GeneratedHypothesisResult was not issued"
            )
        if state.consumed:
            raise GeneratedHypothesisResultLifecycleError(
                "GeneratedHypothesisResult is already consumed"
            )
        if state.thread_id != threading.get_ident():
            raise GeneratedHypothesisResultLifecycleError(
                "GeneratedHypothesisResult cannot cross threads"
            )
        if state.permit is not permit:
            raise InvalidGeneratedHypothesisResultError(
                "GeneratedHypothesisResult requires the exact provider permit"
            )
        if state.started_attempt is not started_attempt:
            raise InvalidGeneratedHypothesisResultError(
                "GeneratedHypothesisResult has another started attempt"
            )
        if state.receipt is not receipt:
            raise InvalidGeneratedHypothesisResultError(
                "GeneratedHypothesisResult requires the exact provider receipt"
            )
        _prove_generated_hypothesis_result_context(state)
        consumed = _ConsumedGeneratedHypothesisResult(
            attempt_id=state.attempt_id,
            started_event_id=state.started_event_id,
            context_digest=state.context_digest,
            prompt_hash=state.prompt_hash,
            receipt=state.receipt,
            trace_ref=state.trace_ref,
            prompt_manifest_ref=state.prompt_manifest_ref,
            raw_response_ref=state.raw_response_ref,
            proposal_canonical_bytes=state.proposal_canonical_bytes,
            proposal_sha256=state.proposal_sha256,
        )
        state.consumed = True
        return consumed


def _bind_provider_generation_result(
    permit: ProviderGenerationPermit,
    *,
    result: GeneratedHypothesisResult,
    result_state: _GeneratedHypothesisResultState,
) -> None:
    """Atomically register one result and advance its exact permit."""

    with _PROVIDER_GENERATION_PERMIT_STATES_LOCK:
        permit_state = _PROVIDER_GENERATION_PERMIT_STATES.get(permit)
        if permit_state is None:
            raise InvalidGeneratedHypothesisResultError(
                "ProviderGenerationPermit was not issued"
            )
        if permit_state.phase is not _ProviderGenerationPermitPhase.START_BOUND:
            raise GeneratedHypothesisResultLifecycleError(
                "ProviderGenerationPermit has no active started call"
            )
        if permit_state.thread_id != threading.get_ident():
            raise GeneratedHypothesisResultLifecycleError(
                "ProviderGenerationPermit cannot cross threads"
            )
        _prove_provider_generation_permit_context(permit_state)
        if (
            result_state.permit is not permit
            or result_state.started_attempt is not permit_state.started_attempt
        ):
            raise InvalidGeneratedHypothesisResultError(
                "generated result does not match its exact provider permit"
            )
        with _GENERATED_HYPOTHESIS_RESULT_STATES_LOCK:
            _GENERATED_HYPOTHESIS_RESULT_STATES[result] = result_state
        permit_state.result_ref = weakref.ref(result)
        permit_state.phase = _ProviderGenerationPermitPhase.RESULT_BOUND


def _prove_provider_generation_permit_context(
    state: _ProviderGenerationPermitState,
) -> None:
    current = state.context_probe.get()
    try:
        state.context_probe.reset(state.context_token)
    except (RuntimeError, ValueError) as exc:
        raise GeneratedHypothesisResultLifecycleError(
            "ProviderGenerationPermit cannot cross Contexts"
        ) from exc
    state.context_token = state.context_probe.set(current)


def _prove_generated_hypothesis_result_context(
    state: _GeneratedHypothesisResultState,
) -> None:
    current = state.context_probe.get()
    try:
        state.context_probe.reset(state.context_token)
    except (RuntimeError, ValueError) as exc:
        raise GeneratedHypothesisResultLifecycleError(
            "GeneratedHypothesisResult cannot cross Contexts"
        ) from exc
    state.context_token = state.context_probe.set(current)


def _required_durable_ref(value: str | None, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise InvalidGeneratedHypothesisResultError(
            f"generated result requires a durable {label} ref"
        )
    return normalized


def _validate_persisted_generated_hypothesis_trace(
    *,
    owner: ProviderCallOwner,
    trace_ref: str,
    receipt: PromptCallReceipt,
    snapshot: PromptTurnSnapshot,
    context: Mapping[str, Any],
    prompt_manifest_session_id: str,
    attempt_audit: Mapping[str, Any],
    raw_response: Mapping[str, Any],
) -> None:
    trace_dir = str(owner._trace_dir or "").strip()
    if not trace_dir:
        raise InvalidGeneratedHypothesisResultError(
            "generated result requires persisted trace storage"
        )
    trace_root = Path(trace_dir).resolve()
    candidate = (trace_root.parent / trace_ref).resolve()
    try:
        candidate.relative_to(trace_root)
    except ValueError as exc:
        raise InvalidGeneratedHypothesisResultError(
            "generated result trace ref escapes its trace owner"
        ) from exc
    if _public_trace_ref(str(candidate), trace_dir=trace_dir) != trace_ref:
        raise InvalidGeneratedHypothesisResultError(
            "generated result trace ref is not canonical"
        )
    try:
        persisted = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidGeneratedHypothesisResultError(
            "generated result trace is not durably readable"
        ) from exc
    if type(persisted) is not dict:
        raise InvalidGeneratedHypothesisResultError(
            "generated result trace has unsupported shape"
        )
    manifest = persisted.get("prompt_manifest")
    if not isinstance(manifest, Mapping):
        raise InvalidGeneratedHypothesisResultError(
            "generated result prompt manifest was not persisted"
        )
    if type(prompt_manifest_session_id) is not str or not prompt_manifest_session_id:
        raise InvalidGeneratedHypothesisResultError(
            "generated result has no prebound prompt manifest session identity"
        )
    expected_manifest = build_api_visible_prompt_manifest(
        session_id=prompt_manifest_session_id,
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=context,
        observations=(),
        call_index=1,
        system_blocks=snapshot.system_blocks,
        user_prompt=snapshot.user_prompt,
        context_digest_override=snapshot.context_digest,
        authoritative_context_ref=snapshot.authoritative_context_ref,
    )
    if (
        persisted.get("ok") is not True
        or persisted.get("request_kind") != "hypothesis"
        or persisted.get("prompt_hash") != receipt.prompt_hash
        or persisted.get("response") != dict(raw_response)
        or persisted.get("provider_call_attempt") != dict(attempt_audit)
        or dict(manifest) != expected_manifest
    ):
        raise InvalidGeneratedHypothesisResultError(
            "generated result trace, manifest, or raw response is incomplete"
        )


def _canonical_hypothesis_bytes(hypothesis: HypothesisProposal) -> bytes:
    if type(hypothesis) is not HypothesisProposal:
        raise InvalidGeneratedHypothesisResultError(
            "generated result requires an exact HypothesisProposal"
        )
    payload = {
        "hypothesis_text": hypothesis.hypothesis_text,
        "change_locus": hypothesis.change_locus,
        "action": hypothesis.action,
        "target_file": hypothesis.target_file,
        "predicted_direction": hypothesis.predicted_direction,
        "target_weakness": hypothesis.target_weakness,
        "expected_effect": hypothesis.expected_effect,
        "suggested_weight": hypothesis.suggested_weight,
    }
    try:
        rendered = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidGeneratedHypothesisResultError(
            "HypothesisProposal cannot be canonically encoded"
        ) from exc
    return rendered.encode("utf-8")


def _hypothesis_from_canonical_bytes(value: bytes) -> HypothesisProposal:
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidGeneratedHypothesisResultError(
            "generated hypothesis canonical bytes are malformed"
        ) from exc
    if type(payload) is not dict:
        raise InvalidGeneratedHypothesisResultError(
            "generated hypothesis canonical payload is malformed"
        )
    return HypothesisProposal(**payload)


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
    session_id: str | None = None,
) -> Dict[str, Any]:
    """Attach audit-only manifest data after the provider bytes are frozen."""

    traced = dict(context)
    existing = traced.get("_scion_prompt_manifest")
    current_prompt_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    if (
        session_id is None
        and isinstance(existing, Mapping)
        and existing
        and str(existing.get("prompt_hash") or "") == current_prompt_hash
    ):
        return traced
    traced["_scion_prompt_manifest"] = build_api_visible_prompt_manifest(
        session_id=session_id or f"prompt-call-{uuid.uuid4()}",
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
    "GeneratedHypothesisResult",
    "GeneratedHypothesisResultError",
    "GeneratedHypothesisResultLifecycleError",
    "InvalidGeneratedHypothesisResultError",
    "PromptCallReceipt",
    "PromptTurnSnapshot",
    "ProviderGenerationPermit",
    "ProviderCallOwner",
    "prompt_call_receipt_from_error",
]
