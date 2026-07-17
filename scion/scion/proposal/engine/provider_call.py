"""Single owner for traced proposal-provider calls and immutable receipts."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Mapping, NoReturn

from scion.core.models import HypothesisProposal
from scion.core.public_refs import public_artifact_ref
from scion.proposal import hypothesis_generation_authority as _generation
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_manifest import (
    build_api_visible_prompt_manifest,
    stable_digest,
)
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash
from scion.proposal.schemas import bind_hypothesis_tool_to_context

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

ProviderGenerationPermit = _generation.ProviderGenerationPermit
GeneratedHypothesisResult = _generation.GeneratedHypothesisResult
FailedHypothesisGeneration = _generation.FailedHypothesisGeneration
BoundHypothesisPrompt = _generation.BoundHypothesisPrompt


class ProviderCallUnknownError(RuntimeError):
    """A claimed provider permit could not bind a truthful terminal outcome."""


class InvalidBoundProviderSnapshotError(TypeError):
    """Bound prompt bytes are malformed or differ from their exact authority."""


class InvalidProviderOutcomeError(RuntimeError):
    """A real receipt/trace/response cannot support the requested leaf outcome."""


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

    __slots__ = (
        "__generation_authority",
        "_client",
        "_model",
        "_trace_dir",
    )

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
        self.__generation_authority: _generation._AuthorityHandle | None = None

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        """Install this exact provider's leaf handle once during composition."""

        if self.__generation_authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "ProviderCallOwner generation authority is already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROVIDER,
            owner=self,
        )
        self.__generation_authority = authority

    def _require_hypothesis_generation_authority(
        self,
    ) -> _generation._AuthorityHandle:
        authority = self.__generation_authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "ProviderCallOwner generation authority is not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.PROVIDER,
            owner=self,
        )
        return authority

    def call_hypothesis(
        self,
        permit: ProviderGenerationPermit,
        bound_prompt: BoundHypothesisPrompt,
    ) -> GeneratedHypothesisResult | FailedHypothesisGeneration:
        """Consume one leaf permit and bind exactly one real provider outcome."""

        authority = self._require_hypothesis_generation_authority()
        _, prompt, started = _generation._claim_provider_permit(
            authority,
            permit,
            bound_prompt,
        )
        try:
            context, snapshot = _rebuild_bound_hypothesis_turn(prompt)
            attempt_audit = _attempt_audit_from_started_projection(
                started,
                snapshot,
            )
            prompt_manifest_session_id = f"prompt-call-{uuid.uuid4()}"
        except BaseException as exc:
            _mark_claim_unknown(authority, permit, exc)

        try:
            raw, receipt = self.call_with_receipt(
                request_kind="hypothesis",
                tool=dict(snapshot.provider_tool),
                context=context,
                snapshot=snapshot,
                attempt_audit=attempt_audit,
                _prompt_manifest_session_id=prompt_manifest_session_id,
            )
        except KeyboardInterrupt as exc:
            receipt = prompt_call_receipt_from_error(exc)
            return _bind_failed_receipt_or_mark_unknown(
                authority,
                permit,
                receipt,
                kind="provider_interruption",
                prompt=snapshot,
                started=started,
                cause=exc,
            )
        except Exception as exc:
            receipt = prompt_call_receipt_from_error(exc)
            return _bind_failed_receipt_or_mark_unknown(
                authority,
                permit,
                receipt,
                kind="provider_failure",
                prompt=snapshot,
                started=started,
                cause=exc,
            )
        except BaseException as exc:
            _mark_claim_unknown(authority, permit, exc)

        try:
            from .parsing import _parse_hypothesis

            hypothesis = _parse_hypothesis(
                raw,
                allowed_change_loci=snapshot.allowed_change_loci,
            )
            proposal_canonical_bytes = _canonical_hypothesis_bytes(hypothesis)
            proposal_sha256 = hashlib.sha256(proposal_canonical_bytes).hexdigest()
        except Exception as exc:
            failed = replace(
                receipt,
                ok=False,
                error_category="response_parse_failed",
                error_type=type(exc).__name__,
            )
            return _bind_failed_receipt_or_mark_unknown(
                authority,
                permit,
                failed,
                kind="invalid_response",
                prompt=snapshot,
                started=started,
                cause=exc,
            )

        try:
            trace_ref, prompt_manifest_ref, raw_response_ref = (
                _validate_successful_provider_call(
                    owner=self,
                    receipt=receipt,
                    snapshot=snapshot,
                    context=context,
                    attempt_audit=attempt_audit,
                    prompt_manifest_session_id=prompt_manifest_session_id,
                    raw_response=raw,
                )
            )
        except Exception as exc:
            failed = replace(
                receipt,
                ok=False,
                error_category="generated_result_issuance_failed",
                error_type=type(exc).__name__,
            )
            return _bind_failed_receipt_or_mark_unknown(
                authority,
                permit,
                failed,
                kind="provider_failure",
                prompt=snapshot,
                started=started,
                cause=exc,
            )

        try:
            return _generation._issue_generated_result(
                authority,
                permit,
                receipt=receipt,
                trace_ref=trace_ref,
                prompt_manifest_ref=prompt_manifest_ref,
                raw_response_ref=raw_response_ref,
                proposal_canonical_bytes=proposal_canonical_bytes,
                proposal_sha256=proposal_sha256,
                provider_ok=receipt.provider_ok,
                ok=receipt.ok,
                error_category=receipt.error_category,
                error_type=receipt.error_type,
                trace_persistence_error=receipt.trace_persistence_error,
            )
        except BaseException as exc:
            _mark_claim_unknown(authority, permit, exc)

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


_PROVIDER_SNAPSHOT_KEYS = frozenset(
    {
        "schema_version",
        "render_kind",
        "system_blocks",
        "user_prompt",
        "context_digest",
        "provider_tool",
        "allowed_change_loci",
        "authoritative_context_ref",
    }
)


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise InvalidBoundProviderSnapshotError(
            f"{label} cannot be canonically encoded"
        ) from exc


def _duplicate_rejecting_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidBoundProviderSnapshotError(
                "bound provider JSON contains a duplicate object key"
            )
        value[key] = item
    return value


def _reject_nonfinite_json(value: str) -> None:
    raise InvalidBoundProviderSnapshotError(
        f"bound provider JSON contains non-finite constant {value!r}"
    )


def _decode_canonical_json_object(value: object, *, label: str) -> dict[str, Any]:
    if type(value) is not bytes or not value:
        raise InvalidBoundProviderSnapshotError(
            f"{label} must be exact nonempty canonical bytes"
        )
    try:
        decoded = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite_json,
        )
    except InvalidBoundProviderSnapshotError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidBoundProviderSnapshotError(f"{label} is malformed") from exc
    if type(decoded) is not dict:
        raise InvalidBoundProviderSnapshotError(f"{label} must contain an object")
    if _canonical_json_bytes(decoded, label=label) != value:
        raise InvalidBoundProviderSnapshotError(f"{label} bytes are not canonical")
    return decoded


def _rebuild_bound_hypothesis_turn(
    prompt: _generation._BoundPromptProjection,
) -> tuple[dict[str, Any], PromptTurnSnapshot]:
    context_snapshot = prompt.context_snapshot
    if type(context_snapshot) is not ProposalContextSnapshot:
        raise InvalidBoundProviderSnapshotError(
            "bound provider prompt has no exact ProposalContextSnapshot"
        )
    if context_snapshot.phase != "hypothesis":
        raise InvalidBoundProviderSnapshotError(
            "bound provider context is not a hypothesis snapshot"
        )
    provider_context = _decode_canonical_json_object(
        prompt.provider_context_json,
        label="bound provider context",
    )
    expected_context = context_snapshot.inputs.provider_context(
        include_renderer_inputs=True
    )
    if provider_context != expected_context or prompt.provider_context_json != (
        _canonical_json_bytes(
            expected_context,
            label="authoritative provider context",
        )
    ):
        raise InvalidBoundProviderSnapshotError(
            "bound provider context differs from its exact snapshot"
        )

    encoded_snapshot = _decode_canonical_json_object(
        prompt.provider_snapshot_bytes,
        label="bound hypothesis provider snapshot",
    )
    if frozenset(encoded_snapshot) != _PROVIDER_SNAPSHOT_KEYS:
        raise InvalidBoundProviderSnapshotError(
            "bound hypothesis provider snapshot has unexpected fields"
        )
    if (
        encoded_snapshot["schema_version"] != "hypothesis-provider-snapshot.v1"
        or encoded_snapshot["render_kind"] != "hypothesis"
        or encoded_snapshot["authoritative_context_ref"]
        != context_snapshot.snapshot_id
    ):
        raise InvalidBoundProviderSnapshotError(
            "bound hypothesis provider snapshot has another identity"
        )
    system_blocks = encoded_snapshot["system_blocks"]
    provider_tool = encoded_snapshot["provider_tool"]
    allowed_change_loci = encoded_snapshot["allowed_change_loci"]
    user_prompt = encoded_snapshot["user_prompt"]
    context_digest = encoded_snapshot["context_digest"]
    if (
        type(system_blocks) is not list
        or any(type(block) is not dict for block in system_blocks)
        or type(provider_tool) is not dict
        or type(allowed_change_loci) is not list
        or any(type(locus) is not str for locus in allowed_change_loci)
        or type(user_prompt) is not str
        or not user_prompt
        or type(context_digest) is not str
    ):
        raise InvalidBoundProviderSnapshotError(
            "bound hypothesis provider snapshot has invalid field types"
        )
    expected_tool, expected_loci = bind_hypothesis_tool_to_context(provider_context)
    if provider_tool != expected_tool or tuple(allowed_change_loci) != tuple(
        expected_loci
    ):
        raise InvalidBoundProviderSnapshotError(
            "bound hypothesis provider tool differs from its exact context"
        )
    expected_context_digest = stable_digest(provider_context, length=64)
    expected_prompt_hash = _provider_prompt_hash(system_blocks, user_prompt)
    if (
        context_digest != expected_context_digest
        or prompt.context_digest != expected_context_digest
        or prompt.prompt_hash != expected_prompt_hash
        or prompt.provider_tool_digest
        != stable_digest(provider_tool, length=64)
        or prompt.governance_digest != context_snapshot.governance_envelope.digest
    ):
        raise InvalidBoundProviderSnapshotError(
            "bound hypothesis provider digests do not match exact bytes"
        )
    snapshot = PromptTurnSnapshot(
        render_kind="hypothesis",
        system_blocks=tuple(dict(block) for block in system_blocks),
        user_prompt=user_prompt,
        context_digest=context_digest,
        provider_tool=dict(provider_tool),
        allowed_change_loci=tuple(allowed_change_loci),
        authoritative_context_ref=context_snapshot.snapshot_id,
        authoritative_context=context_snapshot,
    )
    _validate_authoritative_provider_context(
        request_kind="hypothesis",
        context=provider_context,
        snapshot=snapshot,
    )
    return provider_context, snapshot


def _attempt_audit_from_started_projection(
    started: _generation._StartedAttemptProjection,
    prompt: PromptTurnSnapshot,
) -> dict[str, Any]:
    if (
        started.context_digest != prompt.context_digest
        or started.prompt_hash
        != _provider_prompt_hash(prompt.system_blocks, prompt.user_prompt)
    ):
        raise InvalidBoundProviderSnapshotError(
            "durable START differs from the exact bound provider prompt"
        )
    audit = {
        "schema_version": "provider-call-attempt-audit.v1",
        "attempt_id": started.attempt_id,
        "phase": "hypothesis",
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "hypothesis_attempt_id": started.attempt_id,
        "started_lineage_event_id": started.started_event_id,
    }
    normalized = _validate_provider_call_attempt_audit(
        audit,
        request_kind="hypothesis",
    )
    if normalized is None:  # pragma: no cover - exact dict cannot normalize to null
        raise InvalidBoundProviderSnapshotError(
            "durable START cannot form provider attempt audit"
        )
    return normalized


def _validate_failure_receipt(
    receipt: object,
    *,
    kind: str,
    prompt: PromptTurnSnapshot,
    started: _generation._StartedAttemptProjection,
) -> PromptCallReceipt:
    if type(receipt) is not PromptCallReceipt:
        raise InvalidProviderOutcomeError(
            "claimed provider failure has no exact call receipt"
        )
    if (
        receipt.request_kind != "hypothesis"
        or receipt.context_digest != prompt.context_digest
        or receipt.prompt_hash
        != _provider_prompt_hash(prompt.system_blocks, prompt.user_prompt)
        or receipt.attempt_id != started.attempt_id
        or receipt.attempt_started_event_id != started.started_event_id
        or receipt.continuation_of_attempt_id is not None
        or receipt.ok is not False
        or type(receipt.error_category) is not str
        or not receipt.error_category
        or type(receipt.error_type) is not str
        or not receipt.error_type
    ):
        raise InvalidProviderOutcomeError(
            "claimed provider failure receipt differs from START/prompt facts"
        )
    if kind == "provider_interruption" and (
        receipt.error_category != "provider_call_interrupted"
    ):
        raise InvalidProviderOutcomeError(
            "provider interruption receipt has another category"
        )
    if kind == "invalid_response" and (
        receipt.provider_ok is not True
        or receipt.error_category != "response_parse_failed"
    ):
        raise InvalidProviderOutcomeError(
            "invalid-response receipt has another provider outcome"
        )
    trace_ref = receipt.trace_ref
    if trace_ref is None:
        if (
            receipt.prompt_manifest_ref is not None
            or receipt.raw_response_ref is not None
        ):
            raise InvalidProviderOutcomeError(
                "provider failure refs have no trace owner"
            )
    else:
        if receipt.prompt_manifest_ref != f"{trace_ref}#/prompt_manifest":
            raise InvalidProviderOutcomeError(
                "provider failure prompt manifest ref differs from its trace"
            )
        if receipt.raw_response_ref not in {None, f"{trace_ref}#/response"}:
            raise InvalidProviderOutcomeError(
                "provider failure raw response ref differs from its trace"
            )
    return receipt


def _bind_failed_receipt_or_mark_unknown(
    authority: _generation._AuthorityHandle,
    permit: ProviderGenerationPermit,
    receipt: PromptCallReceipt | None,
    *,
    kind: str,
    prompt: PromptTurnSnapshot,
    started: _generation._StartedAttemptProjection,
    cause: BaseException,
) -> FailedHypothesisGeneration:
    try:
        exact = _validate_failure_receipt(
            receipt,
            kind=kind,
            prompt=prompt,
            started=started,
        )
        return _generation._issue_failed_generation(
            authority,
            permit,
            kind=kind,
            receipt=exact,
            trace_ref=exact.trace_ref,
            prompt_manifest_ref=exact.prompt_manifest_ref,
            raw_response_ref=exact.raw_response_ref,
            provider_ok=exact.provider_ok,
            ok=exact.ok,
            failure_category=exact.error_category,
            failure_type=exact.error_type,
            trace_persistence_error=exact.trace_persistence_error,
        )
    except BaseException as exc:
        _mark_claim_unknown(authority, permit, exc if exc is not cause else cause)


def _mark_claim_unknown(
    authority: _generation._AuthorityHandle,
    permit: ProviderGenerationPermit,
    cause: BaseException,
) -> NoReturn:
    _generation._mark_provider_claim_unknown(authority, permit)
    if not isinstance(cause, Exception):
        raise cause
    raise ProviderCallUnknownError(
        "claimed provider call could not bind a truthful outcome"
    ) from cause


def _validate_successful_provider_call(
    *,
    owner: ProviderCallOwner,
    receipt: PromptCallReceipt,
    snapshot: PromptTurnSnapshot,
    context: Mapping[str, Any],
    attempt_audit: Mapping[str, Any],
    prompt_manifest_session_id: str,
    raw_response: Mapping[str, Any],
) -> tuple[str, str, str]:
    if type(receipt) is not PromptCallReceipt:
        raise InvalidProviderOutcomeError(
            "generated result requires the exact provider receipt"
        )
    if (
        receipt.request_kind != "hypothesis"
        or receipt.provider_ok is not True
        or receipt.ok is not True
        or receipt.error_category is not None
        or receipt.error_type is not None
        or receipt.trace_persistence_error is not None
        or receipt.attempt_id != attempt_audit["attempt_id"]
        or receipt.attempt_started_event_id
        != attempt_audit["started_lineage_event_id"]
        or receipt.continuation_of_attempt_id is not None
        or receipt.context_digest != snapshot.context_digest
        or receipt.prompt_hash
        != _provider_prompt_hash(snapshot.system_blocks, snapshot.user_prompt)
    ):
        raise InvalidProviderOutcomeError(
            "generated result receipt differs from its exact START/prompt"
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
        raise InvalidProviderOutcomeError(
            "prompt manifest ref is not bound to the trace"
        )
    if raw_response_ref != f"{trace_ref}#/response":
        raise InvalidProviderOutcomeError(
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
    return trace_ref, prompt_manifest_ref, raw_response_ref


def _required_durable_ref(value: str | None, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise InvalidProviderOutcomeError(
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
        raise InvalidProviderOutcomeError(
            "generated result requires persisted trace storage"
        )
    trace_root = Path(trace_dir).resolve()
    candidate = (trace_root.parent / trace_ref).resolve()
    try:
        candidate.relative_to(trace_root)
    except ValueError as exc:
        raise InvalidProviderOutcomeError(
            "generated result trace ref escapes its trace owner"
        ) from exc
    if _public_trace_ref(str(candidate), trace_dir=trace_dir) != trace_ref:
        raise InvalidProviderOutcomeError(
            "generated result trace ref is not canonical"
        )
    try:
        persisted = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidProviderOutcomeError(
            "generated result trace is not durably readable"
        ) from exc
    if type(persisted) is not dict:
        raise InvalidProviderOutcomeError(
            "generated result trace has unsupported shape"
        )
    manifest = persisted.get("prompt_manifest")
    if not isinstance(manifest, Mapping):
        raise InvalidProviderOutcomeError(
            "generated result prompt manifest was not persisted"
        )
    if type(prompt_manifest_session_id) is not str or not prompt_manifest_session_id:
        raise InvalidProviderOutcomeError(
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
        raise InvalidProviderOutcomeError(
            "generated result trace, manifest, or raw response is incomplete"
        )


def _canonical_hypothesis_bytes(hypothesis: HypothesisProposal) -> bytes:
    if type(hypothesis) is not HypothesisProposal:
        raise InvalidProviderOutcomeError(
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
        raise InvalidProviderOutcomeError(
            "HypothesisProposal cannot be canonically encoded"
        ) from exc
    return rendered.encode("utf-8")


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
    "BoundHypothesisPrompt",
    "FailedHypothesisGeneration",
    "GeneratedHypothesisResult",
    "InvalidBoundProviderSnapshotError",
    "InvalidProviderOutcomeError",
    "PromptCallReceipt",
    "PromptTurnSnapshot",
    "ProviderCallOwner",
    "ProviderCallUnknownError",
    "ProviderGenerationPermit",
    "prompt_call_receipt_from_error",
]
