"""Leaf capability authority for the dormant hypothesis-generation vertical.

This module owns identities and one-shot state only.  It deliberately imports
no provider, proposal-attempt owner, Registry, trace, SQLite, or durable store.
Semantic owners receive distinct installed handles and remain responsible for
all validation outside the capability graph.
"""

from __future__ import annotations

import contextvars
import enum
import hashlib
import threading
import weakref
from dataclasses import dataclass
from typing import Final


_GENERATION_CONTEXT_PROBE: contextvars.ContextVar[object | None] = (
    contextvars.ContextVar(
        "scion_hypothesis_generation_context",
        default=None,
    )
)


class HypothesisGenerationAuthorityError(RuntimeError):
    """Base error for the dormant generation capability graph."""


class InvalidHypothesisGenerationCapabilityError(
    TypeError,
    HypothesisGenerationAuthorityError,
):
    """A capability or authority handle is forged, malformed, or mismatched."""


class HypothesisGenerationLifecycleError(HypothesisGenerationAuthorityError):
    """A genuine capability crossed its owner/context or was reused."""


class _OpaqueCapability:
    __slots__ = ("__state_anchor", "__weakref__")

    def __new__(cls, *_args: object, **_kwargs: object) -> "_OpaqueCapability":
        raise InvalidHypothesisGenerationCapabilityError(
            f"{cls.__name__} is issued only by its installed semantic owner"
        )

    def __copy__(self) -> "_OpaqueCapability":
        raise InvalidHypothesisGenerationCapabilityError(
            f"{type(self).__name__} cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "_OpaqueCapability":
        raise InvalidHypothesisGenerationCapabilityError(
            f"{type(self).__name__} cannot be copied"
        )

    def __reduce__(self) -> object:
        raise InvalidHypothesisGenerationCapabilityError(
            f"{type(self).__name__} cannot be pickled"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidHypothesisGenerationCapabilityError(
            f"{type(self).__name__} cannot be pickled"
        )


def _sealed_subclass(name: str) -> None:
    raise TypeError(f"{name} is sealed")


class HypothesisCodeSourceRequest(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisCodeSourceRequest")


class HypothesisGenerationView(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisGenerationView")


class HypothesisCodeSource(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisCodeSource")


class HypothesisProblemEvidenceProjection(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisProblemEvidenceProjection")


class HypothesisPromptSource(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisPromptSource")


class BoundHypothesisPrompt(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("BoundHypothesisPrompt")


class StartedHypothesisAttempt(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("StartedHypothesisAttempt")


class ProviderGenerationPermit(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("ProviderGenerationPermit")


class GeneratedHypothesisResult(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("GeneratedHypothesisResult")


class FailedHypothesisGeneration(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("FailedHypothesisGeneration")


class AbortedHypothesisGeneration(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("AbortedHypothesisGeneration")


class TerminalAttemptReceipt(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("TerminalAttemptReceipt")


class _AuthorityHandle(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("_AuthorityHandle")


class _AuthorityRole(enum.Enum):
    REGISTRY = enum.auto()
    CODE_SOURCE_OWNER = enum.auto()
    CONTEXT_MANAGER = enum.auto()
    PROMPT_OWNER = enum.auto()
    PROPOSAL_OWNER = enum.auto()
    PROVIDER = enum.auto()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class _AuthorityHandleState:
    role: _AuthorityRole
    owner: object
    installation: object


@dataclass(frozen=True, slots=True)
class _CheckpointAAuthorities:
    registry: _AuthorityHandle
    code_source_owner: _AuthorityHandle
    context_manager: _AuthorityHandle
    prompt_owner: _AuthorityHandle
    proposal_owner: _AuthorityHandle
    provider: _AuthorityHandle


class _CapabilityStateTable(
    weakref.WeakKeyDictionary[object, weakref.ReferenceType[object]]
):
    """Weak-key/weak-value index; each capability owns its state anchor."""

    def __setitem__(self, key: object, state: object) -> None:
        object.__setattr__(key, "_OpaqueCapability__state_anchor", state)
        super().__setitem__(key, weakref.ref(state))

    def __getitem__(self, key: object) -> object:
        state_ref = super().__getitem__(key)
        state = state_ref()
        try:
            anchor = object.__getattribute__(
                key,
                "_OpaqueCapability__state_anchor",
            )
        except (AttributeError, TypeError) as exc:
            raise KeyError(key) from exc
        if state is None or anchor is not state:
            raise KeyError(key)
        return state

    def get(self, key: object, default: object = None) -> object:
        state_ref = super().get(key)
        state = None if state_ref is None else state_ref()
        try:
            anchor = object.__getattribute__(
                key,
                "_OpaqueCapability__state_anchor",
            )
        except (AttributeError, TypeError):
            return default
        return state if state is not None and anchor is state else default


_AUTHORITY_HANDLE_STATES = _CapabilityStateTable()
_AUTHORITY_HANDLE_LOCK: Final[threading.RLock] = threading.RLock()
_INSTALLED_OWNER_ROLES: Final[set[tuple[int, _AuthorityRole]]] = set()


def _release_installed_owner_role(key: tuple[int, _AuthorityRole]) -> None:
    with _AUTHORITY_HANDLE_LOCK:
        _INSTALLED_OWNER_ROLES.discard(key)


def _install_checkpoint_a_authorities(
    *,
    registry: object,
    code_source_owner: object,
    context_manager: object,
    prompt_owner: object,
    proposal_owner: object,
    provider: object,
) -> _CheckpointAAuthorities:
    """Install one complete real owner graph; no test-only issuer exists."""

    owners = (
        (_AuthorityRole.REGISTRY, registry),
        (_AuthorityRole.CODE_SOURCE_OWNER, code_source_owner),
        (_AuthorityRole.CONTEXT_MANAGER, context_manager),
        (_AuthorityRole.PROMPT_OWNER, prompt_owner),
        (_AuthorityRole.PROPOSAL_OWNER, proposal_owner),
        (_AuthorityRole.PROVIDER, provider),
    )
    if any(owner is None for _, owner in owners):
        raise InvalidHypothesisGenerationCapabilityError(
            "checkpoint-A authority installation requires every semantic owner"
        )
    installation = object()
    handles: dict[_AuthorityRole, _AuthorityHandle] = {}
    with _AUTHORITY_HANDLE_LOCK:
        keys = tuple((id(owner), role) for role, owner in owners)
        if any(key in _INSTALLED_OWNER_ROLES for key in keys):
            raise HypothesisGenerationLifecycleError(
                "checkpoint-A semantic owner is already installed"
            )
        for (role, owner), key in zip(owners, keys, strict=True):
            handle = object.__new__(_AuthorityHandle)
            _AUTHORITY_HANDLE_STATES[handle] = _AuthorityHandleState(
                role=role,
                owner=owner,
                installation=installation,
            )
            _INSTALLED_OWNER_ROLES.add(key)
            weakref.finalize(handle, _release_installed_owner_role, key)
            handles[role] = handle
    return _CheckpointAAuthorities(
        registry=handles[_AuthorityRole.REGISTRY],
        code_source_owner=handles[_AuthorityRole.CODE_SOURCE_OWNER],
        context_manager=handles[_AuthorityRole.CONTEXT_MANAGER],
        prompt_owner=handles[_AuthorityRole.PROMPT_OWNER],
        proposal_owner=handles[_AuthorityRole.PROPOSAL_OWNER],
        provider=handles[_AuthorityRole.PROVIDER],
    )


def _require_authority(
    handle: _AuthorityHandle,
    *,
    role: _AuthorityRole,
    owner: object | None = None,
) -> _AuthorityHandleState:
    if type(handle) is not _AuthorityHandle:
        raise InvalidHypothesisGenerationCapabilityError(
            "operation requires an exact installed authority handle"
        )
    with _AUTHORITY_HANDLE_LOCK:
        state = _AUTHORITY_HANDLE_STATES.get(handle)
    if state is None or state.role is not role:
        raise InvalidHypothesisGenerationCapabilityError(
            f"operation requires the installed {role.name.lower()} authority"
        )
    if owner is not None and state.owner is not owner:
        raise InvalidHypothesisGenerationCapabilityError(
            "authority handle belongs to another semantic owner"
        )
    return state


def _require_same_installation(*handles: _AuthorityHandle) -> None:
    states = tuple(_lookup_handle(handle) for handle in handles)
    if not states or any(
        state.installation is not states[0].installation for state in states[1:]
    ):
        raise InvalidHypothesisGenerationCapabilityError(
            "authority handles belong to different checkpoint-A installations"
        )


def _lookup_handle(handle: object) -> _AuthorityHandleState:
    if type(handle) is not _AuthorityHandle:
        raise InvalidHypothesisGenerationCapabilityError(
            "operation requires an exact installed authority handle"
        )
    with _AUTHORITY_HANDLE_LOCK:
        state = _AUTHORITY_HANDLE_STATES.get(handle)
    if state is None:
        raise InvalidHypothesisGenerationCapabilityError(
            "authority handle was not installed"
        )
    return state


@dataclass(slots=True)
class _ContextBinding:
    thread_id: int
    probe: contextvars.ContextVar[object | None]
    marker: object
    token: contextvars.Token[object | None]
    active: bool = True


def _new_context_binding(label: str) -> _ContextBinding:
    del label
    probe = _GENERATION_CONTEXT_PROBE
    marker = probe.get()
    if marker is None:
        marker = object()
    return _ContextBinding(
        thread_id=threading.get_ident(),
        probe=probe,
        marker=marker,
        token=probe.set(marker),
    )


def _prove_context(binding: _ContextBinding, *, label: str) -> None:
    if not binding.active:
        raise HypothesisGenerationLifecycleError(f"{label} is already settled")
    if binding.thread_id != threading.get_ident():
        raise HypothesisGenerationLifecycleError(f"{label} cannot cross threads")
    if binding.probe.get() is not binding.marker:
        raise HypothesisGenerationLifecycleError(f"{label} cannot cross Contexts")
    try:
        binding.probe.reset(binding.token)
    except (RuntimeError, ValueError) as exc:
        raise HypothesisGenerationLifecycleError(
            f"{label} cannot cross Contexts"
        ) from exc
    binding.token = binding.probe.set(binding.marker)


def _retire_context(binding: _ContextBinding, *, label: str) -> None:
    """Retire one attempt while retaining one bounded context-level proof."""

    _prove_context(binding, label=label)
    binding.active = False


def _required_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires exact {field}"
        )
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field=field)


def _optional_bool(value: object, *, field: str) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires exact bool or null {field}"
        )
    return value


def _required_digest(value: object, *, field: str) -> str:
    text = _required_text(value, field=field)
    if len(text) != 64:
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires SHA-256 {field}"
        )
    try:
        int(text, 16)
    except ValueError as exc:
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires SHA-256 {field}"
        ) from exc
    if text != text.lower():
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires lowercase SHA-256 {field}"
        )
    return text


def _required_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise InvalidHypothesisGenerationCapabilityError(
            f"generation authority requires nonnegative SQLite integer {field}"
        )
    return value


class _CodeRequestPhase(enum.Enum):
    ISSUED = enum.auto()
    SOURCE_IN_FLIGHT = enum.auto()
    SOURCE_BOUND = enum.auto()
    SOURCE_REJECTED = enum.auto()
    SOURCE_UNKNOWN = enum.auto()


class _GenerationViewPhase(enum.Enum):
    CAPTURED = enum.auto()
    CODE_SOURCE_IN_FLIGHT = enum.auto()
    CODE_SOURCE_BOUND = enum.auto()
    PROMPT_SOURCE_ISSUED = enum.auto()
    PROMPT_BOUND = enum.auto()
    START_IN_FLIGHT = enum.auto()
    START_BOUND = enum.auto()
    PERMIT_ISSUED = enum.auto()
    RESULT_BOUND = enum.auto()
    TERMINAL_OUTCOME_BOUND = enum.auto()
    TERMINAL_IN_FLIGHT = enum.auto()
    PRESTART_REJECTED = enum.auto()
    PRESTART_UNKNOWN = enum.auto()
    UNCERTAIN_HOLD = enum.auto()
    SPENT = enum.auto()


class _CodeSourcePhase(enum.Enum):
    ISSUED = enum.auto()
    EVIDENCE_IN_FLIGHT = enum.auto()
    EVIDENCE_BOUND = enum.auto()
    EVIDENCE_REJECTED = enum.auto()
    EVIDENCE_UNKNOWN = enum.auto()
    PROMPT_SOURCE_BOUND = enum.auto()


class _EvidencePhase(enum.Enum):
    ISSUED = enum.auto()
    VIEW_BOUND = enum.auto()
    PROMPT_BOUND = enum.auto()


class _PromptSourcePhase(enum.Enum):
    ISSUED = enum.auto()
    PROMPT_IN_FLIGHT = enum.auto()
    PROMPT_BOUND = enum.auto()
    PROMPT_REJECTED = enum.auto()
    PROMPT_UNKNOWN = enum.auto()


class _BoundPromptPhase(enum.Enum):
    ISSUED = enum.auto()
    START_IN_FLIGHT = enum.auto()
    START_BOUND = enum.auto()
    PROVIDER_BOUND = enum.auto()
    TERMINALIZED = enum.auto()


class _StartedPhase(enum.Enum):
    DURABLE_BOUND = enum.auto()
    PROVIDER_BOUND = enum.auto()
    CREATION_BOUND = enum.auto()
    TERMINALIZED = enum.auto()


class _PermitPhase(enum.Enum):
    ISSUED = enum.auto()
    CLAIMED_BEFORE_TRANSPORT = enum.auto()
    SUCCESS_BOUND = enum.auto()
    FAILURE_BOUND = enum.auto()
    CLAIMED_UNKNOWN = enum.auto()
    CANCELLED = enum.auto()


class _SuccessPhase(enum.Enum):
    ISSUED = enum.auto()


class _TerminalOutcomePhase(enum.Enum):
    ISSUED = enum.auto()
    TERMINALIZED = enum.auto()


class _ReceiptPhase(enum.Enum):
    ISSUED = enum.auto()
    RESERVATION_RESOLVED = enum.auto()


@dataclass(frozen=True, slots=True)
class _GenerationViewProjection:
    root_identity: object
    root_generation: int
    branch_owner: object
    hypothesis_bundle: tuple[object, ...]
    prior_head: object | None
    reservation_id: str
    h_bundle_digest: str
    owner_context_json: bytes


@dataclass(slots=True, weakref_slot=True)
class _GenerationViewState:
    projection: _GenerationViewProjection
    registry: _AuthorityHandle
    binding: _ContextBinding
    phase: _GenerationViewPhase = _GenerationViewPhase.CAPTURED
    code_request: HypothesisCodeSourceRequest | None = None
    code_source: HypothesisCodeSource | None = None
    prompt_source: HypothesisPromptSource | None = None
    bound_prompt: BoundHypothesisPrompt | None = None
    started_attempt: StartedHypothesisAttempt | None = None
    permit: ProviderGenerationPermit | None = None
    outcome: (
        GeneratedHypothesisResult
        | FailedHypothesisGeneration
        | AbortedHypothesisGeneration
        | None
    ) = None
    terminal_receipt: TerminalAttemptReceipt | None = None


@dataclass(frozen=True, slots=True)
class _CodeSourceRequestProjection:
    view_identity: HypothesisGenerationView
    reservation_id: str
    branch_owner: object
    h_bundle_digest: str
    owner_context_json: bytes


@dataclass(slots=True, weakref_slot=True)
class _CodeSourceRequestState:
    projection: _CodeSourceRequestProjection
    registry: _AuthorityHandle
    binding: _ContextBinding
    phase: _CodeRequestPhase = _CodeRequestPhase.ISSUED


@dataclass(frozen=True, slots=True)
class _CodeSourceProjection:
    request: HypothesisCodeSourceRequest
    view_identity: HypothesisGenerationView
    reservation_id: str
    branch_owner: object
    h_bundle_digest: str
    source_kind: str
    selected_manifest_digest: str
    code_hash: str
    snapshot_hash: str
    entries: tuple[tuple[str, bytes, str, bool, bool], ...]
    owner_context_json: bytes


@dataclass(slots=True, weakref_slot=True)
class _CodeSourceState:
    projection: _CodeSourceProjection
    code_source_owner: _AuthorityHandle
    binding: _ContextBinding
    phase: _CodeSourcePhase = _CodeSourcePhase.ISSUED


@dataclass(frozen=True, slots=True)
class _ProblemEvidenceProjection:
    code_source: HypothesisCodeSource
    view_identity: HypothesisGenerationView
    provider_context_json: bytes
    governance_json: bytes
    evidence_digest: str


@dataclass(slots=True, weakref_slot=True)
class _ProblemEvidenceState:
    projection: _ProblemEvidenceProjection
    context_manager: _AuthorityHandle
    binding: _ContextBinding
    phase: _EvidencePhase = _EvidencePhase.ISSUED


@dataclass(frozen=True, slots=True)
class _PromptSourceProjection:
    view_identity: HypothesisGenerationView
    code_source: HypothesisCodeSource
    evidence: HypothesisProblemEvidenceProjection
    reservation_id: str
    branch_owner: object
    h_bundle_digest: str
    source_kind: str
    selected_manifest_digest: str
    owner_context_json: bytes


@dataclass(slots=True, weakref_slot=True)
class _PromptSourceState:
    projection: _PromptSourceProjection
    registry: _AuthorityHandle
    binding: _ContextBinding
    phase: _PromptSourcePhase = _PromptSourcePhase.ISSUED


@dataclass(frozen=True, slots=True)
class _BoundPromptProjection:
    prompt_source: HypothesisPromptSource
    code_source: HypothesisCodeSource
    evidence: HypothesisProblemEvidenceProjection
    view_identity: HypothesisGenerationView
    reservation_id: str
    branch_owner: object
    h_bundle_digest: str
    context_snapshot: object
    provider_context_json: bytes
    provider_snapshot_bytes: bytes
    context_digest: str
    prompt_hash: str
    provider_tool_digest: str
    governance_digest: str
    source_kind: str
    selected_manifest_digest: str
    evidence_digest: str
    owner_context_json: bytes


@dataclass(slots=True, weakref_slot=True)
class _BoundPromptState:
    projection: _BoundPromptProjection
    prompt_owner: _AuthorityHandle
    binding: _ContextBinding
    phase: _BoundPromptPhase = _BoundPromptPhase.ISSUED


@dataclass(frozen=True, slots=True)
class _StartedAttemptProjection:
    stored_event: object
    attempt_id: str
    started_event_id: str
    campaign_id: str
    branch_id: str
    context_digest: str
    prompt_hash: str
    event_storage_sha256: str
    bound_prompt: BoundHypothesisPrompt
    view_identity: HypothesisGenerationView


@dataclass(slots=True, weakref_slot=True)
class _StartedAttemptState:
    projection: _StartedAttemptProjection
    proposal_owner: _AuthorityHandle
    binding: _ContextBinding
    phase: _StartedPhase = _StartedPhase.DURABLE_BOUND
    permit: ProviderGenerationPermit | None = None


@dataclass(frozen=True, slots=True)
class _PermitProjection:
    view_identity: HypothesisGenerationView
    started_attempt: StartedHypothesisAttempt
    bound_prompt: BoundHypothesisPrompt
    provider: _AuthorityHandle


@dataclass(slots=True, weakref_slot=True)
class _PermitState:
    projection: _PermitProjection
    registry: _AuthorityHandle
    binding: _ContextBinding
    phase: _PermitPhase = _PermitPhase.ISSUED
    outcome: GeneratedHypothesisResult | FailedHypothesisGeneration | None = None


@dataclass(frozen=True, slots=True)
class _GeneratedResultProjection:
    permit: ProviderGenerationPermit
    started_attempt: StartedHypothesisAttempt
    bound_prompt: BoundHypothesisPrompt
    receipt: object
    trace_ref: str
    prompt_manifest_ref: str
    raw_response_ref: str
    proposal_canonical_bytes: bytes
    proposal_sha256: str
    provider_ok: bool
    ok: bool
    error_category: None
    error_type: None
    trace_persistence_error: str | None


@dataclass(slots=True, weakref_slot=True)
class _GeneratedResultState:
    projection: _GeneratedResultProjection
    provider: _AuthorityHandle
    binding: _ContextBinding
    phase: _SuccessPhase = _SuccessPhase.ISSUED


@dataclass(frozen=True, slots=True)
class _TerminalOutcomeProjection:
    kind: str
    permit: ProviderGenerationPermit | None
    started_attempt: StartedHypothesisAttempt
    bound_prompt: BoundHypothesisPrompt
    receipt: object | None
    trace_ref: str | None
    prompt_manifest_ref: str | None
    raw_response_ref: str | None
    provider_ok: bool | None
    ok: bool
    failure_category: str
    failure_type: str
    trace_persistence_error: str | None


@dataclass(slots=True, weakref_slot=True)
class _TerminalOutcomeState:
    projection: _TerminalOutcomeProjection
    issuer: _AuthorityHandle
    binding: _ContextBinding
    phase: _TerminalOutcomePhase = _TerminalOutcomePhase.ISSUED
    terminal_receipt: TerminalAttemptReceipt | None = None


@dataclass(frozen=True, slots=True)
class _TerminalReceiptProjection:
    terminal_event: object
    terminal_event_storage_sha256: str
    outcome: FailedHypothesisGeneration | AbortedHypothesisGeneration
    started_attempt: StartedHypothesisAttempt


@dataclass(slots=True, weakref_slot=True)
class _TerminalReceiptState:
    projection: _TerminalReceiptProjection
    proposal_owner: _AuthorityHandle
    binding: _ContextBinding
    phase: _ReceiptPhase = _ReceiptPhase.ISSUED


_GENERATION_VIEW_STATES = _CapabilityStateTable()
_CODE_REQUEST_STATES = _CapabilityStateTable()
_CODE_SOURCE_STATES = _CapabilityStateTable()
_EVIDENCE_STATES = _CapabilityStateTable()
_PROMPT_SOURCE_STATES = _CapabilityStateTable()
_BOUND_PROMPT_STATES = _CapabilityStateTable()
_STARTED_STATES = _CapabilityStateTable()
_PERMIT_STATES = _CapabilityStateTable()
_RESULT_STATES = _CapabilityStateTable()
_FAILURE_STATES = _CapabilityStateTable()
_ABORT_STATES = _CapabilityStateTable()
_RECEIPT_STATES = _CapabilityStateTable()
_CAPABILITY_LOCK: Final[threading.RLock] = threading.RLock()


def _lookup_exact(
    value: object,
    expected_type: type[_OpaqueCapability],
    states: _CapabilityStateTable,
    *,
    label: str,
) -> object:
    if type(value) is not expected_type:
        raise InvalidHypothesisGenerationCapabilityError(
            f"operation requires an exact {label}"
        )
    state = states.get(value)
    if state is None:
        raise InvalidHypothesisGenerationCapabilityError(f"{label} was not issued")
    return state


def _handle_state(handle: object, *, role: _AuthorityRole) -> _AuthorityHandleState:
    state = _lookup_handle(handle)
    if state.role is not role:
        raise InvalidHypothesisGenerationCapabilityError(
            f"operation requires the installed {role.name.lower()} authority"
        )
    return state


def _same_installation(left: _AuthorityHandle, right: _AuthorityHandle) -> None:
    left_state = _lookup_handle(left)
    right_state = _lookup_handle(right)
    if left_state.installation is not right_state.installation:
        raise InvalidHypothesisGenerationCapabilityError(
            "capability owners belong to different checkpoint-A installations"
        )


def _issue_generation_view(
    registry: _AuthorityHandle,
    *,
    root_identity: object,
    root_generation: int,
    branch_owner: object,
    hypothesis_bundle: tuple[object, ...],
    prior_head: object | None,
    reservation_id: str,
    h_bundle_digest: str,
    owner_context_json: bytes,
) -> HypothesisGenerationView:
    """Issue one exact Registry-root generation view and local reservation identity."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    if root_identity is None or branch_owner is None:
        raise InvalidHypothesisGenerationCapabilityError(
            "generation view requires exact root and Branch owner identities"
        )
    if type(hypothesis_bundle) is not tuple or any(
        owner is None for owner in hypothesis_bundle
    ):
        raise InvalidHypothesisGenerationCapabilityError(
            "generation view requires an exact immutable H owner bundle"
        )
    if type(owner_context_json) is not bytes or not owner_context_json:
        raise InvalidHypothesisGenerationCapabilityError(
            "generation view requires canonical owner-context bytes"
        )
    value = object.__new__(HypothesisGenerationView)
    with _CAPABILITY_LOCK:
        _GENERATION_VIEW_STATES[value] = _GenerationViewState(
            projection=_GenerationViewProjection(
                root_identity=root_identity,
                root_generation=_required_nonnegative_int(
                    root_generation,
                    field="root generation",
                ),
                branch_owner=branch_owner,
                hypothesis_bundle=hypothesis_bundle,
                prior_head=prior_head,
                reservation_id=_required_text(
                    reservation_id,
                    field="reservation ID",
                ),
                h_bundle_digest=_required_digest(
                    h_bundle_digest,
                    field="H-bundle digest",
                ),
                owner_context_json=bytes(owner_context_json),
            ),
            registry=registry,
            binding=_new_context_binding("generation_view"),
        )
    return value


def _inspect_generation_view(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> _GenerationViewProjection:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(state, _GenerationViewState)
        if state.registry is not registry:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view belongs to another Registry"
            )
        _prove_context(state.binding, label="HypothesisGenerationView")
        return state.projection


def _issue_code_source_request(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> HypothesisCodeSourceRequest:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        if view_state.registry is not registry:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view belongs to another Registry"
            )
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.phase is not _GenerationViewPhase.CAPTURED
            or view_state.code_request is not None
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view is not available for code-source acquisition"
            )
        projection = _CodeSourceRequestProjection(
            view_identity=view,
            reservation_id=view_state.projection.reservation_id,
            branch_owner=view_state.projection.branch_owner,
            h_bundle_digest=view_state.projection.h_bundle_digest,
            owner_context_json=view_state.projection.owner_context_json,
        )
        value = object.__new__(HypothesisCodeSourceRequest)
        _CODE_REQUEST_STATES[value] = _CodeSourceRequestState(
            projection=projection,
            registry=registry,
            binding=view_state.binding,
        )
        view_state.code_request = value
        view_state.phase = _GenerationViewPhase.CODE_SOURCE_IN_FLIGHT
    return value


def _spend_prestart_generation_view(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
    *,
    rejected: bool,
) -> None:
    """Spend a pre-START view after deterministic rejection or unknown work."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    if type(rejected) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            "pre-START disposition requires exact rejection bool"
        )
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(state, _GenerationViewState)
        _prove_context(state.binding, label="HypothesisGenerationView")
        if state.registry is not registry or state.phase not in {
            _GenerationViewPhase.CODE_SOURCE_IN_FLIGHT,
            _GenerationViewPhase.CODE_SOURCE_BOUND,
            _GenerationViewPhase.PROMPT_SOURCE_ISSUED,
            _GenerationViewPhase.PROMPT_BOUND,
        }:
            raise HypothesisGenerationLifecycleError(
                "generation view is not in a spendable pre-START phase"
            )
        state.phase = (
            _GenerationViewPhase.PRESTART_REJECTED
            if rejected
            else _GenerationViewPhase.PRESTART_UNKNOWN
        )
        state.phase = _GenerationViewPhase.SPENT
        _retire_context(state.binding, label="HypothesisGenerationView")


def _abort_prestart_generation_view(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> None:
    """Spend one stable local view before START without fabricating a failure."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(state, _GenerationViewState)
        _prove_context(state.binding, label="HypothesisGenerationView")
        if state.registry is not registry:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view belongs to another Registry"
            )
        if state.phase is _GenerationViewPhase.CAPTURED:
            pass
        elif state.phase is _GenerationViewPhase.CODE_SOURCE_BOUND:
            source = state.code_source
            if source is None:
                raise InvalidHypothesisGenerationCapabilityError(
                    "generation view lost its bound code source"
                )
            source_state = _lookup_exact(
                source,
                HypothesisCodeSource,
                _CODE_SOURCE_STATES,  # type: ignore[arg-type]
                label="HypothesisCodeSource",
            )
            assert isinstance(source_state, _CodeSourceState)
            if source_state.phase is not _CodeSourcePhase.ISSUED:
                raise HypothesisGenerationLifecycleError(
                    "code source has active or settled evidence work"
                )
        elif state.phase is _GenerationViewPhase.PROMPT_SOURCE_ISSUED:
            prompt_source = state.prompt_source
            if prompt_source is None:
                raise InvalidHypothesisGenerationCapabilityError(
                    "generation view lost its prompt source"
                )
            prompt_state = _lookup_exact(
                prompt_source,
                HypothesisPromptSource,
                _PROMPT_SOURCE_STATES,  # type: ignore[arg-type]
                label="HypothesisPromptSource",
            )
            assert isinstance(prompt_state, _PromptSourceState)
            if prompt_state.phase not in {
                _PromptSourcePhase.ISSUED,
                _PromptSourcePhase.PROMPT_BOUND,
            }:
                raise HypothesisGenerationLifecycleError(
                    "prompt source has active or separately settled work"
                )
        elif state.phase is _GenerationViewPhase.PROMPT_BOUND:
            prompt = state.bound_prompt
            if prompt is None:
                raise InvalidHypothesisGenerationCapabilityError(
                    "generation view lost its bound prompt"
                )
            prompt_state = _lookup_exact(
                prompt,
                BoundHypothesisPrompt,
                _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
                label="BoundHypothesisPrompt",
            )
            assert isinstance(prompt_state, _BoundPromptState)
            if prompt_state.phase is not _BoundPromptPhase.ISSUED:
                raise HypothesisGenerationLifecycleError(
                    "bound prompt has active or settled START work"
                )
        else:
            raise HypothesisGenerationLifecycleError(
                "generation view is not in a stable pre-START abort phase"
            )
        state.phase = _GenerationViewPhase.SPENT
        _retire_context(state.binding, label="HypothesisGenerationView")


def _finish_start_without_authority(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
    *,
    mixed: bool,
) -> None:
    """Settle a non-committed START classification without issuing START authority."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    if type(mixed) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            "START classification requires exact mixed bool"
        )
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(state, _GenerationViewState)
        _prove_context(state.binding, label="HypothesisGenerationView")
        if (
            state.registry is not registry
            or state.phase is not _GenerationViewPhase.START_IN_FLIGHT
            or state.started_attempt is not None
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view has no unsettled START classification"
            )
        state.phase = (
            _GenerationViewPhase.UNCERTAIN_HOLD
            if mixed
            else _GenerationViewPhase.SPENT
        )
        _retire_context(state.binding, label="HypothesisGenerationView")


def _hold_generation_view(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> None:
    """Permanently hold a post-START view after uncertain or mixed settlement."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(state, _GenerationViewState)
        _prove_context(state.binding, label="HypothesisGenerationView")
        if state.registry is not registry or state.phase not in {
            _GenerationViewPhase.START_IN_FLIGHT,
            _GenerationViewPhase.START_BOUND,
            _GenerationViewPhase.PERMIT_ISSUED,
            _GenerationViewPhase.RESULT_BOUND,
            _GenerationViewPhase.TERMINAL_OUTCOME_BOUND,
            _GenerationViewPhase.TERMINAL_IN_FLIGHT,
        }:
            raise HypothesisGenerationLifecycleError(
                "generation view is not in a holdable post-START phase"
            )
        state.phase = _GenerationViewPhase.UNCERTAIN_HOLD
        _retire_context(state.binding, label="HypothesisGenerationView")


def _claim_code_source_request(
    code_source_owner: _AuthorityHandle,
    request: HypothesisCodeSourceRequest,
) -> _CodeSourceRequestProjection:
    _handle_state(code_source_owner, role=_AuthorityRole.CODE_SOURCE_OWNER)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            request,
            HypothesisCodeSourceRequest,
            _CODE_REQUEST_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSourceRequest",
        )
        assert isinstance(state, _CodeSourceRequestState)
        view_state = _lookup_exact(
            state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(code_source_owner, state.registry)
        _prove_context(state.binding, label="HypothesisCodeSourceRequest")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            state.phase is not _CodeRequestPhase.ISSUED
            or view_state.phase is not _GenerationViewPhase.CODE_SOURCE_IN_FLIGHT
            or view_state.code_request is not request
        ):
            raise HypothesisGenerationLifecycleError(
                "HypothesisCodeSourceRequest is already claimed"
            )
        state.phase = _CodeRequestPhase.SOURCE_IN_FLIGHT
        return state.projection


def _finish_code_source_request_failure(
    code_source_owner: _AuthorityHandle,
    request: HypothesisCodeSourceRequest,
    *,
    rejected: bool,
) -> None:
    _handle_state(code_source_owner, role=_AuthorityRole.CODE_SOURCE_OWNER)
    if type(rejected) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            "code-source failure kind must be exact bool"
        )
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            request,
            HypothesisCodeSourceRequest,
            _CODE_REQUEST_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSourceRequest",
        )
        assert isinstance(state, _CodeSourceRequestState)
        _same_installation(code_source_owner, state.registry)
        _prove_context(state.binding, label="HypothesisCodeSourceRequest")
        if state.phase is not _CodeRequestPhase.SOURCE_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "code-source request has no active source claim"
            )
        state.phase = (
            _CodeRequestPhase.SOURCE_REJECTED
            if rejected
            else _CodeRequestPhase.SOURCE_UNKNOWN
        )


def _normalize_source_entries(
    entries: tuple[tuple[str, bytes, str, bool, bool], ...],
) -> tuple[tuple[str, bytes, str, bool, bool], ...]:
    if type(entries) is not tuple:
        raise InvalidHypothesisGenerationCapabilityError(
            "code source requires an exact immutable entry tuple"
        )
    normalized: list[tuple[str, bytes, str, bool, bool]] = []
    prior = ""
    for entry in entries:
        if type(entry) is not tuple or len(entry) != 5:
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source entry has invalid shape"
            )
        path, content, digest, code_identity, snapshot_identity = entry
        path_text = _required_text(path, field="code-source relative path")
        if path_text.startswith("/") or "\\" in path_text or ".." in path_text.split("/"):
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source entry path is not canonical relative POSIX text"
            )
        if prior and path_text <= prior:
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source entries must be unique and sorted"
            )
        if type(content) is not bytes:
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source entry content must be exact bytes"
            )
        digest_text = _required_digest(digest, field="code-source file digest")
        if hashlib.sha256(content).hexdigest() != digest_text:
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source entry digest differs from its bytes"
            )
        if type(code_identity) is not bool or type(snapshot_identity) is not bool:
            raise InvalidHypothesisGenerationCapabilityError(
                "code-source identity flags must be exact bool"
            )
        normalized.append(
            (path_text, bytes(content), digest_text, code_identity, snapshot_identity)
        )
        prior = path_text
    return tuple(normalized)


def _issue_code_source(
    code_source_owner: _AuthorityHandle,
    request: HypothesisCodeSourceRequest,
    *,
    source_kind: str,
    selected_manifest_digest: str,
    code_hash: str,
    snapshot_hash: str,
    entries: tuple[tuple[str, bytes, str, bool, bool], ...],
) -> HypothesisCodeSource:
    _handle_state(code_source_owner, role=_AuthorityRole.CODE_SOURCE_OWNER)
    kind = _required_text(source_kind, field="source kind")
    if kind not in {"base_champion", "verified_branch_workspace"}:
        raise InvalidHypothesisGenerationCapabilityError(
            "code source has unsupported source kind"
        )
    normalized_entries = _normalize_source_entries(entries)
    with _CAPABILITY_LOCK:
        request_state = _lookup_exact(
            request,
            HypothesisCodeSourceRequest,
            _CODE_REQUEST_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSourceRequest",
        )
        assert isinstance(request_state, _CodeSourceRequestState)
        view_state = _lookup_exact(
            request_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(code_source_owner, request_state.registry)
        _prove_context(request_state.binding, label="HypothesisCodeSourceRequest")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if request_state.phase is not _CodeRequestPhase.SOURCE_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "code-source request has no active source claim"
            )
        if (
            view_state.phase is not _GenerationViewPhase.CODE_SOURCE_IN_FLIGHT
            or view_state.code_request is not request
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view no longer owns this code-source request"
            )
        projection = _CodeSourceProjection(
            request=request,
            view_identity=request_state.projection.view_identity,
            reservation_id=request_state.projection.reservation_id,
            branch_owner=request_state.projection.branch_owner,
            h_bundle_digest=request_state.projection.h_bundle_digest,
            source_kind=kind,
            selected_manifest_digest=_required_digest(
                selected_manifest_digest,
                field="selected source manifest digest",
            ),
            code_hash=_required_digest(code_hash, field="source code hash"),
            snapshot_hash=_required_digest(snapshot_hash, field="source snapshot hash"),
            entries=normalized_entries,
            owner_context_json=request_state.projection.owner_context_json,
        )
        value = object.__new__(HypothesisCodeSource)
        _CODE_SOURCE_STATES[value] = _CodeSourceState(
            projection=projection,
            code_source_owner=code_source_owner,
            binding=view_state.binding,
        )
        request_state.phase = _CodeRequestPhase.SOURCE_BOUND
        return value


def _inspect_code_source(
    registry: _AuthorityHandle,
    source: HypothesisCodeSource,
    *,
    view: HypothesisGenerationView,
) -> _CodeSourceProjection:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        assert isinstance(state, _CodeSourceState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, state.code_source_owner)
        _prove_context(state.binding, label="HypothesisCodeSource")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.code_request is not state.projection.request
            or state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "code source belongs to another generation view"
            )
        if view_state.phase is not _GenerationViewPhase.CODE_SOURCE_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "generation view already settled its code source"
            )
        view_state.code_source = source
        view_state.phase = _GenerationViewPhase.CODE_SOURCE_BOUND
        return state.projection


def _claim_code_source_for_evidence(
    context_manager: _AuthorityHandle,
    source: HypothesisCodeSource,
) -> _CodeSourceProjection:
    _handle_state(context_manager, role=_AuthorityRole.CONTEXT_MANAGER)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        assert isinstance(state, _CodeSourceState)
        view_state = _lookup_exact(
            state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(context_manager, state.code_source_owner)
        _prove_context(state.binding, label="HypothesisCodeSource")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            state.phase is not _CodeSourcePhase.ISSUED
            or view_state.phase is not _GenerationViewPhase.CODE_SOURCE_BOUND
            or view_state.code_source is not source
        ):
            raise HypothesisGenerationLifecycleError(
                "HypothesisCodeSource is already evidence-bound"
            )
        state.phase = _CodeSourcePhase.EVIDENCE_IN_FLIGHT
        return state.projection


def _finish_problem_evidence_failure(
    context_manager: _AuthorityHandle,
    source: HypothesisCodeSource,
    *,
    rejected: bool,
) -> None:
    _handle_state(context_manager, role=_AuthorityRole.CONTEXT_MANAGER)
    if type(rejected) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            "problem-evidence failure kind must be exact bool"
        )
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        assert isinstance(state, _CodeSourceState)
        _same_installation(context_manager, state.code_source_owner)
        _prove_context(state.binding, label="HypothesisCodeSource")
        if state.phase is not _CodeSourcePhase.EVIDENCE_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "code source has no active evidence claim"
            )
        state.phase = (
            _CodeSourcePhase.EVIDENCE_REJECTED
            if rejected
            else _CodeSourcePhase.EVIDENCE_UNKNOWN
        )


def _issue_problem_evidence(
    context_manager: _AuthorityHandle,
    source: HypothesisCodeSource,
    *,
    provider_context_json: bytes,
    governance_json: bytes,
) -> HypothesisProblemEvidenceProjection:
    _handle_state(context_manager, role=_AuthorityRole.CONTEXT_MANAGER)
    if type(provider_context_json) is not bytes or not provider_context_json:
        raise InvalidHypothesisGenerationCapabilityError(
            "problem evidence requires canonical provider-context bytes"
        )
    if type(governance_json) is not bytes or not governance_json:
        raise InvalidHypothesisGenerationCapabilityError(
            "problem evidence requires canonical governance bytes"
        )
    digest = hashlib.sha256(
        b"hypothesis-problem-evidence.v1\0"
        + provider_context_json
        + b"\0"
        + governance_json
    ).hexdigest()
    with _CAPABILITY_LOCK:
        source_state = _lookup_exact(
            source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        assert isinstance(source_state, _CodeSourceState)
        view_state = _lookup_exact(
            source_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(context_manager, source_state.code_source_owner)
        _prove_context(source_state.binding, label="HypothesisCodeSource")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if source_state.phase is not _CodeSourcePhase.EVIDENCE_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "code source has no active evidence claim"
            )
        if (
            view_state.phase is not _GenerationViewPhase.CODE_SOURCE_BOUND
            or view_state.code_source is not source
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view no longer owns this evidence claim"
            )
        value = object.__new__(HypothesisProblemEvidenceProjection)
        _EVIDENCE_STATES[value] = _ProblemEvidenceState(
            projection=_ProblemEvidenceProjection(
                code_source=source,
                view_identity=source_state.projection.view_identity,
                provider_context_json=bytes(provider_context_json),
                governance_json=bytes(governance_json),
                evidence_digest=digest,
            ),
            context_manager=context_manager,
            binding=view_state.binding,
        )
        source_state.phase = _CodeSourcePhase.EVIDENCE_BOUND
        return value


def _issue_prompt_source(
    registry: _AuthorityHandle,
    *,
    view: HypothesisGenerationView,
    code_source: HypothesisCodeSource,
    evidence: HypothesisProblemEvidenceProjection,
) -> HypothesisPromptSource:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        source_state = _lookup_exact(
            code_source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        evidence_state = _lookup_exact(
            evidence,
            HypothesisProblemEvidenceProjection,
            _EVIDENCE_STATES,  # type: ignore[arg-type]
            label="HypothesisProblemEvidenceProjection",
        )
        assert isinstance(source_state, _CodeSourceState)
        assert isinstance(evidence_state, _ProblemEvidenceState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, source_state.code_source_owner)
        _same_installation(registry, evidence_state.context_manager)
        _prove_context(source_state.binding, label="HypothesisCodeSource")
        _prove_context(
            evidence_state.binding,
            label="HypothesisProblemEvidenceProjection",
        )
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.code_source is not code_source
            or evidence_state.projection.code_source is not code_source
            or source_state.projection.view_identity is not view
            or evidence_state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "prompt source requires exact source/evidence/view binding"
            )
        if (
            view_state.phase is not _GenerationViewPhase.CODE_SOURCE_BOUND
            or source_state.phase is not _CodeSourcePhase.EVIDENCE_BOUND
            or evidence_state.phase is not _EvidencePhase.ISSUED
        ):
            raise HypothesisGenerationLifecycleError(
                "source/evidence/view binding is already spent"
            )
        value = object.__new__(HypothesisPromptSource)
        _PROMPT_SOURCE_STATES[value] = _PromptSourceState(
            projection=_PromptSourceProjection(
                view_identity=view,
                code_source=code_source,
                evidence=evidence,
                reservation_id=source_state.projection.reservation_id,
                branch_owner=source_state.projection.branch_owner,
                h_bundle_digest=source_state.projection.h_bundle_digest,
                source_kind=source_state.projection.source_kind,
                selected_manifest_digest=(
                    source_state.projection.selected_manifest_digest
                ),
                owner_context_json=source_state.projection.owner_context_json,
            ),
            registry=registry,
            binding=view_state.binding,
        )
        evidence_state.phase = _EvidencePhase.VIEW_BOUND
        source_state.phase = _CodeSourcePhase.PROMPT_SOURCE_BOUND
        view_state.prompt_source = value
        view_state.phase = _GenerationViewPhase.PROMPT_SOURCE_ISSUED
        return value


def _claim_prompt_source(
    prompt_owner: _AuthorityHandle,
    source: HypothesisPromptSource,
) -> tuple[
    _PromptSourceProjection,
    _CodeSourceProjection,
    _ProblemEvidenceProjection,
]:
    _handle_state(prompt_owner, role=_AuthorityRole.PROMPT_OWNER)
    with _CAPABILITY_LOCK:
        source_state = _lookup_exact(
            source,
            HypothesisPromptSource,
            _PROMPT_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisPromptSource",
        )
        assert isinstance(source_state, _PromptSourceState)
        view_state = _lookup_exact(
            source_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(prompt_owner, source_state.registry)
        _prove_context(source_state.binding, label="HypothesisPromptSource")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            source_state.phase is not _PromptSourcePhase.ISSUED
            or view_state.phase is not _GenerationViewPhase.PROMPT_SOURCE_ISSUED
            or view_state.prompt_source is not source
        ):
            raise HypothesisGenerationLifecycleError(
                "HypothesisPromptSource is already claimed"
            )
        evidence_state = _lookup_exact(
            source_state.projection.evidence,
            HypothesisProblemEvidenceProjection,
            _EVIDENCE_STATES,  # type: ignore[arg-type]
            label="HypothesisProblemEvidenceProjection",
        )
        assert isinstance(evidence_state, _ProblemEvidenceState)
        _same_installation(prompt_owner, evidence_state.context_manager)
        _prove_context(
            evidence_state.binding,
            label="HypothesisProblemEvidenceProjection",
        )
        if evidence_state.phase is not _EvidencePhase.VIEW_BOUND:
            raise HypothesisGenerationLifecycleError(
                "problem-evidence projection is not bound to the prompt source"
            )
        source_state.phase = _PromptSourcePhase.PROMPT_IN_FLIGHT
        code_state = _lookup_exact(
            source_state.projection.code_source,
            HypothesisCodeSource,
            _CODE_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisCodeSource",
        )
        assert isinstance(code_state, _CodeSourceState)
        if code_state.phase is not _CodeSourcePhase.PROMPT_SOURCE_BOUND:
            raise HypothesisGenerationLifecycleError(
                "prompt source lost its exact bound code source"
            )
        return (
            source_state.projection,
            code_state.projection,
            evidence_state.projection,
        )


def _finish_prompt_failure(
    prompt_owner: _AuthorityHandle,
    source: HypothesisPromptSource,
    *,
    rejected: bool,
) -> None:
    _handle_state(prompt_owner, role=_AuthorityRole.PROMPT_OWNER)
    if type(rejected) is not bool:
        raise InvalidHypothesisGenerationCapabilityError(
            "prompt failure kind must be exact bool"
        )
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            source,
            HypothesisPromptSource,
            _PROMPT_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisPromptSource",
        )
        assert isinstance(state, _PromptSourceState)
        _same_installation(prompt_owner, state.registry)
        _prove_context(state.binding, label="HypothesisPromptSource")
        if state.phase is not _PromptSourcePhase.PROMPT_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "prompt source has no active prompt claim"
            )
        state.phase = (
            _PromptSourcePhase.PROMPT_REJECTED
            if rejected
            else _PromptSourcePhase.PROMPT_UNKNOWN
        )


def _settle_prompt_failure(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> bool | None:
    """Let Registry discover and spend an externally failed prompt bind.

    ``True`` denotes deterministic rejection, ``False`` denotes an unexpected
    post-claim failure, and ``None`` means the exact prompt source has no
    settled failure.  No caller-authored error or disposition is accepted.
    """

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if view_state.registry is not registry:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view belongs to another Registry"
            )
        if view_state.phase is not _GenerationViewPhase.PROMPT_SOURCE_ISSUED:
            return None
        prompt_source = view_state.prompt_source
        if prompt_source is None:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view lost its exact prompt source"
            )
        prompt_state = _lookup_exact(
            prompt_source,
            HypothesisPromptSource,
            _PROMPT_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisPromptSource",
        )
        assert isinstance(prompt_state, _PromptSourceState)
        if prompt_state.phase is _PromptSourcePhase.PROMPT_REJECTED:
            rejected = True
        elif prompt_state.phase is _PromptSourcePhase.PROMPT_UNKNOWN:
            rejected = False
        else:
            return None
        view_state.phase = _GenerationViewPhase.SPENT
        _retire_context(
            view_state.binding,
            label="HypothesisGenerationView",
        )
        return rejected


def _issue_bound_prompt(
    prompt_owner: _AuthorityHandle,
    source: HypothesisPromptSource,
    *,
    context_snapshot: object,
    provider_context_json: bytes,
    provider_snapshot_bytes: bytes,
    context_digest: str,
    prompt_hash: str,
    provider_tool_digest: str,
    governance_digest: str,
) -> BoundHypothesisPrompt:
    _handle_state(prompt_owner, role=_AuthorityRole.PROMPT_OWNER)
    byte_fields = {
        "provider context": provider_context_json,
        "provider snapshot": provider_snapshot_bytes,
    }
    if context_snapshot is None or any(
        type(value) is not bytes or not value for value in byte_fields.values()
    ):
        raise InvalidHypothesisGenerationCapabilityError(
            "bound prompt requires exact snapshot identity and canonical bytes"
        )
    with _CAPABILITY_LOCK:
        source_state = _lookup_exact(
            source,
            HypothesisPromptSource,
            _PROMPT_SOURCE_STATES,  # type: ignore[arg-type]
            label="HypothesisPromptSource",
        )
        assert isinstance(source_state, _PromptSourceState)
        view_state = _lookup_exact(
            source_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(prompt_owner, source_state.registry)
        _prove_context(source_state.binding, label="HypothesisPromptSource")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if source_state.phase is not _PromptSourcePhase.PROMPT_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "prompt source has no active prompt claim"
            )
        if (
            view_state.phase is not _GenerationViewPhase.PROMPT_SOURCE_ISSUED
            or view_state.prompt_source is not source
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view no longer owns this prompt claim"
            )
        evidence_state = _lookup_exact(
            source_state.projection.evidence,
            HypothesisProblemEvidenceProjection,
            _EVIDENCE_STATES,  # type: ignore[arg-type]
            label="HypothesisProblemEvidenceProjection",
        )
        assert isinstance(evidence_state, _ProblemEvidenceState)
        if evidence_state.phase is not _EvidencePhase.VIEW_BOUND:
            raise HypothesisGenerationLifecycleError(
                "problem evidence is not ready for prompt binding"
            )
        value = object.__new__(BoundHypothesisPrompt)
        _BOUND_PROMPT_STATES[value] = _BoundPromptState(
            projection=_BoundPromptProjection(
                prompt_source=source,
                code_source=source_state.projection.code_source,
                evidence=source_state.projection.evidence,
                view_identity=source_state.projection.view_identity,
                reservation_id=source_state.projection.reservation_id,
                branch_owner=source_state.projection.branch_owner,
                h_bundle_digest=source_state.projection.h_bundle_digest,
                context_snapshot=context_snapshot,
                provider_context_json=bytes(provider_context_json),
                provider_snapshot_bytes=bytes(provider_snapshot_bytes),
                context_digest=_required_digest(
                    context_digest,
                    field="prompt context digest",
                ),
                prompt_hash=_required_digest(prompt_hash, field="prompt hash"),
                provider_tool_digest=_required_digest(
                    provider_tool_digest,
                    field="provider tool digest",
                ),
                governance_digest=_required_digest(
                    governance_digest,
                    field="governance digest",
                ),
                source_kind=source_state.projection.source_kind,
                selected_manifest_digest=(
                    source_state.projection.selected_manifest_digest
                ),
                evidence_digest=evidence_state.projection.evidence_digest,
                owner_context_json=source_state.projection.owner_context_json,
            ),
            prompt_owner=prompt_owner,
            binding=view_state.binding,
        )
        evidence_state.phase = _EvidencePhase.PROMPT_BOUND
        source_state.phase = _PromptSourcePhase.PROMPT_BOUND
        return value


def _inspect_bound_prompt(
    registry: _AuthorityHandle,
    prompt: BoundHypothesisPrompt,
    *,
    view: HypothesisGenerationView,
) -> _BoundPromptProjection:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(state, _BoundPromptState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, state.prompt_owner)
        _prove_context(state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.prompt_source is not state.projection.prompt_source
            or state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "bound prompt belongs to another generation view"
            )
        if (
            view_state.phase is not _GenerationViewPhase.PROMPT_SOURCE_ISSUED
            or state.phase is not _BoundPromptPhase.ISSUED
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view already settled its bound prompt"
            )
        view_state.bound_prompt = prompt
        view_state.phase = _GenerationViewPhase.PROMPT_BOUND
        return state.projection


def _begin_started_attempt(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
    prompt: BoundHypothesisPrompt,
) -> None:
    """Spend the Registry view's pre-START phase before transaction work."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        prompt_state = _lookup_exact(
            prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(view_state, _GenerationViewState)
        assert isinstance(prompt_state, _BoundPromptState)
        _same_installation(registry, prompt_state.prompt_owner)
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        if (
            view_state.registry is not registry
            or view_state.phase is not _GenerationViewPhase.PROMPT_BOUND
            or view_state.bound_prompt is not prompt
            or prompt_state.phase is not _BoundPromptPhase.ISSUED
            or prompt_state.projection.view_identity is not view
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view is not ready for the exact bound prompt START"
            )
        view_state.phase = _GenerationViewPhase.START_IN_FLIGHT


def _claim_bound_prompt_for_start(
    proposal_owner: _AuthorityHandle,
    prompt: BoundHypothesisPrompt,
) -> _BoundPromptProjection:
    """Claim the exact prompt before START transaction work and expose owner facts."""

    _handle_state(proposal_owner, role=_AuthorityRole.PROPOSAL_OWNER)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(state, _BoundPromptState)
        view_state = _lookup_exact(
            state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(proposal_owner, state.prompt_owner)
        _same_installation(proposal_owner, view_state.registry)
        _prove_context(state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            state.phase is not _BoundPromptPhase.ISSUED
            or view_state.phase is not _GenerationViewPhase.START_IN_FLIGHT
            or view_state.bound_prompt is not prompt
        ):
            raise HypothesisGenerationLifecycleError(
                "BoundHypothesisPrompt is already claimed for START"
            )
        state.phase = _BoundPromptPhase.START_IN_FLIGHT
        return state.projection


def _issue_started_attempt(
    proposal_owner: _AuthorityHandle,
    *,
    stored_event: object,
    attempt_id: str,
    started_event_id: str,
    campaign_id: str,
    branch_id: str,
    context_digest: str,
    prompt_hash: str,
    event_storage_sha256: str,
    bound_prompt: BoundHypothesisPrompt,
) -> StartedHypothesisAttempt:
    _handle_state(proposal_owner, role=_AuthorityRole.PROPOSAL_OWNER)
    if stored_event is None:
        raise InvalidHypothesisGenerationCapabilityError(
            "started attempt requires exact durable event and generation view"
        )
    with _CAPABILITY_LOCK:
        prompt_state = _lookup_exact(
            bound_prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(prompt_state, _BoundPromptState)
        view = prompt_state.projection.view_identity
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(proposal_owner, prompt_state.prompt_owner)
        _same_installation(proposal_owner, view_state.registry)
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            prompt_state.phase is not _BoundPromptPhase.START_IN_FLIGHT
            or view_state.phase is not _GenerationViewPhase.START_IN_FLIGHT
            or view_state.bound_prompt is not bound_prompt
            or prompt_state.projection.context_digest != context_digest
            or prompt_state.projection.prompt_hash != prompt_hash
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "started attempt does not match the exact bound prompt/view"
            )
        value = object.__new__(StartedHypothesisAttempt)
        _STARTED_STATES[value] = _StartedAttemptState(
            projection=_StartedAttemptProjection(
                stored_event=stored_event,
                attempt_id=_required_text(attempt_id, field="attempt ID"),
                started_event_id=_required_text(
                    started_event_id,
                    field="START event ID",
                ),
                campaign_id=_required_text(campaign_id, field="campaign ID"),
                branch_id=_required_text(branch_id, field="Branch ID"),
                context_digest=_required_digest(
                    context_digest,
                    field="START context digest",
                ),
                prompt_hash=_required_digest(prompt_hash, field="START prompt hash"),
                event_storage_sha256=_required_digest(
                    event_storage_sha256,
                    field="START event storage digest",
                ),
                bound_prompt=bound_prompt,
                view_identity=view,
            ),
            proposal_owner=proposal_owner,
            binding=view_state.binding,
        )
        prompt_state.phase = _BoundPromptPhase.START_BOUND
        view_state.started_attempt = value
        return value


def _inspect_started_attempt(
    registry: _AuthorityHandle,
    started: StartedHypothesisAttempt,
    *,
    view: HypothesisGenerationView,
) -> _StartedAttemptProjection:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            started,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        assert isinstance(state, _StartedAttemptState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, state.proposal_owner)
        _prove_context(state.binding, label="StartedHypothesisAttempt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.started_attempt is not started
            or state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "started attempt belongs to another generation view"
            )
        if view_state.phase is not _GenerationViewPhase.START_IN_FLIGHT:
            raise HypothesisGenerationLifecycleError(
                "durable START was already classified for this generation view"
            )
        view_state.phase = _GenerationViewPhase.START_BOUND
        return state.projection


def _issue_provider_permit(
    registry: _AuthorityHandle,
    provider: _AuthorityHandle,
    *,
    view: HypothesisGenerationView,
    started_attempt: StartedHypothesisAttempt,
    bound_prompt: BoundHypothesisPrompt,
) -> ProviderGenerationPermit:
    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    _handle_state(provider, role=_AuthorityRole.PROVIDER)
    _same_installation(registry, provider)
    with _CAPABILITY_LOCK:
        started_state = _lookup_exact(
            started_attempt,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        prompt_state = _lookup_exact(
            bound_prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(started_state, _StartedAttemptState)
        assert isinstance(prompt_state, _BoundPromptState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, started_state.proposal_owner)
        _same_installation(registry, prompt_state.prompt_owner)
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.started_attempt is not started_attempt
            or view_state.bound_prompt is not bound_prompt
            or started_state.projection.bound_prompt is not bound_prompt
            or started_state.projection.view_identity is not view
            or prompt_state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "provider permit requires exact durable START/prompt/view binding"
            )
        if (
            view_state.phase is not _GenerationViewPhase.START_BOUND
            or started_state.phase is not _StartedPhase.DURABLE_BOUND
            or started_state.permit is not None
            or prompt_state.phase is not _BoundPromptPhase.START_BOUND
        ):
            raise HypothesisGenerationLifecycleError(
                "durable START/prompt/view binding already issued a permit"
            )
        value = object.__new__(ProviderGenerationPermit)
        _PERMIT_STATES[value] = _PermitState(
            projection=_PermitProjection(
                view_identity=view,
                started_attempt=started_attempt,
                bound_prompt=bound_prompt,
                provider=provider,
            ),
            registry=registry,
            binding=view_state.binding,
        )
        started_state.permit = value
        started_state.phase = _StartedPhase.PROVIDER_BOUND
        prompt_state.phase = _BoundPromptPhase.PROVIDER_BOUND
        view_state.permit = value
        view_state.phase = _GenerationViewPhase.PERMIT_ISSUED
        return value


def _claim_provider_permit(
    provider: _AuthorityHandle,
    permit: ProviderGenerationPermit,
    bound_prompt: BoundHypothesisPrompt,
) -> tuple[_PermitProjection, _BoundPromptProjection, _StartedAttemptProjection]:
    """Irreversibly claim one exact permit before provider transport begins."""

    _handle_state(provider, role=_AuthorityRole.PROVIDER)
    with _CAPABILITY_LOCK:
        permit_state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        prompt_state = _lookup_exact(
            bound_prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(permit_state, _PermitState)
        assert isinstance(prompt_state, _BoundPromptState)
        _same_installation(provider, permit_state.registry)
        _same_installation(provider, prompt_state.prompt_owner)
        _prove_context(permit_state.binding, label="ProviderGenerationPermit")
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        started = permit_state.projection.started_attempt
        started_state = _lookup_exact(
            started,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        assert isinstance(started_state, _StartedAttemptState)
        view_state = _lookup_exact(
            permit_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(provider, started_state.proposal_owner)
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            permit_state.projection.provider is not provider
            or permit_state.projection.bound_prompt is not bound_prompt
            or started_state.permit is not permit
            or started_state.projection.bound_prompt is not bound_prompt
            or view_state.permit is not permit
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "provider permit belongs to another START/prompt binding"
            )
        if (
            permit_state.phase is not _PermitPhase.ISSUED
            or permit_state.outcome is not None
            or prompt_state.phase is not _BoundPromptPhase.PROVIDER_BOUND
            or started_state.phase is not _StartedPhase.PROVIDER_BOUND
            or view_state.phase is not _GenerationViewPhase.PERMIT_ISSUED
        ):
            raise HypothesisGenerationLifecycleError(
                "provider permit's exact START/prompt binding is already spent"
            )
        permit_state.phase = _PermitPhase.CLAIMED_BEFORE_TRANSPORT
        return (
            permit_state.projection,
            prompt_state.projection,
            started_state.projection,
        )


def _mark_provider_claim_unknown(
    provider: _AuthorityHandle,
    permit: ProviderGenerationPermit,
) -> None:
    """Spend a claimed permit when transport may have begun without an outcome."""

    _handle_state(provider, role=_AuthorityRole.PROVIDER)
    with _CAPABILITY_LOCK:
        state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        assert isinstance(state, _PermitState)
        _same_installation(provider, state.registry)
        _prove_context(state.binding, label="ProviderGenerationPermit")
        if (
            state.projection.provider is not provider
            or state.phase is not _PermitPhase.CLAIMED_BEFORE_TRANSPORT
            or state.outcome is not None
        ):
            raise HypothesisGenerationLifecycleError(
                "provider permit has no unresolved claimed transport"
            )
        view_state = _lookup_exact(
            state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(provider, view_state.registry)
        if (
            view_state.phase is not _GenerationViewPhase.PERMIT_ISSUED
            or view_state.permit is not permit
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "claimed-unknown permit belongs to another generation view phase"
            )
        state.phase = _PermitPhase.CLAIMED_UNKNOWN


def _settle_provider_claim_unknown(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
) -> bool:
    """Let Registry exactly discover and hold one claimed-unknown provider call."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if view_state.registry is not registry:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view belongs to another Registry"
            )
        if view_state.phase is not _GenerationViewPhase.PERMIT_ISSUED:
            return False
        permit = view_state.permit
        if permit is None:
            raise InvalidHypothesisGenerationCapabilityError(
                "generation view lost its exact provider permit"
            )
        permit_state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        assert isinstance(permit_state, _PermitState)
        if (
            permit_state.registry is not registry
            or permit_state.projection.view_identity is not view
            or permit_state.phase is not _PermitPhase.CLAIMED_UNKNOWN
            or permit_state.outcome is not None
        ):
            return False
        view_state.phase = _GenerationViewPhase.UNCERTAIN_HOLD
        _retire_context(
            view_state.binding,
            label="HypothesisGenerationView",
        )
        return True


def _issue_generated_result(
    provider: _AuthorityHandle,
    permit: ProviderGenerationPermit,
    *,
    receipt: object,
    trace_ref: str,
    prompt_manifest_ref: str,
    raw_response_ref: str,
    proposal_canonical_bytes: bytes,
    proposal_sha256: str,
    provider_ok: bool,
    ok: bool,
    error_category: None,
    error_type: None,
    trace_persistence_error: str | None,
) -> GeneratedHypothesisResult:
    """Bind validated real provider success facts to one claimed permit."""

    _handle_state(provider, role=_AuthorityRole.PROVIDER)
    if receipt is None or type(proposal_canonical_bytes) is not bytes:
        raise InvalidHypothesisGenerationCapabilityError(
            "generated result requires exact receipt and canonical proposal bytes"
        )
    if provider_ok is not True or ok is not True:
        raise InvalidHypothesisGenerationCapabilityError(
            "generated result requires exact successful provider receipt booleans"
        )
    if error_category is not None or error_type is not None:
        raise InvalidHypothesisGenerationCapabilityError(
            "generated result cannot bind provider error fields"
        )
    persistence_error = _optional_text(
        trace_persistence_error,
        field="trace persistence error",
    )
    digest = _required_digest(proposal_sha256, field="proposal digest")
    if (
        not proposal_canonical_bytes
        or hashlib.sha256(proposal_canonical_bytes).hexdigest() != digest
    ):
        raise InvalidHypothesisGenerationCapabilityError(
            "generated proposal digest differs from canonical bytes"
        )
    refs = tuple(
        _required_text(value, field=label)
        for value, label in (
            (trace_ref, "trace reference"),
            (prompt_manifest_ref, "prompt-manifest reference"),
            (raw_response_ref, "raw-response reference"),
        )
    )
    with _CAPABILITY_LOCK:
        permit_state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        assert isinstance(permit_state, _PermitState)
        _same_installation(provider, permit_state.registry)
        _prove_context(permit_state.binding, label="ProviderGenerationPermit")
        if (
            permit_state.projection.provider is not provider
            or permit_state.phase is not _PermitPhase.CLAIMED_BEFORE_TRANSPORT
            or permit_state.outcome is not None
        ):
            raise HypothesisGenerationLifecycleError(
                "generated result requires one exact active provider claim"
            )
        value = object.__new__(GeneratedHypothesisResult)
        _RESULT_STATES[value] = _GeneratedResultState(
            projection=_GeneratedResultProjection(
                permit=permit,
                started_attempt=permit_state.projection.started_attempt,
                bound_prompt=permit_state.projection.bound_prompt,
                receipt=receipt,
                trace_ref=refs[0],
                prompt_manifest_ref=refs[1],
                raw_response_ref=refs[2],
                proposal_canonical_bytes=bytes(proposal_canonical_bytes),
                proposal_sha256=digest,
                provider_ok=True,
                ok=True,
                error_category=None,
                error_type=None,
                trace_persistence_error=persistence_error,
            ),
            provider=provider,
            binding=permit_state.binding,
        )
        permit_state.outcome = value
        permit_state.phase = _PermitPhase.SUCCESS_BOUND
        return value


def _issue_failed_generation(
    provider: _AuthorityHandle,
    permit: ProviderGenerationPermit,
    *,
    kind: str,
    receipt: object,
    trace_ref: str | None,
    prompt_manifest_ref: str | None,
    raw_response_ref: str | None,
    provider_ok: bool | None,
    ok: bool,
    failure_category: str,
    failure_type: str,
    trace_persistence_error: str | None,
) -> FailedHypothesisGeneration:
    """Bind a truthful provider failure/interruption/parse outcome."""

    _handle_state(provider, role=_AuthorityRole.PROVIDER)
    outcome_kind = _required_text(kind, field="provider failure kind")
    if outcome_kind not in {
        "provider_failure",
        "provider_interruption",
        "invalid_response",
    }:
        raise InvalidHypothesisGenerationCapabilityError(
            "provider failure kind is unsupported"
        )
    if receipt is None:
        raise InvalidHypothesisGenerationCapabilityError(
            "provider failure requires the real call receipt"
        )
    refs = tuple(
        _optional_text(value, field=label)
        for value, label in (
            (trace_ref, "trace reference"),
            (prompt_manifest_ref, "prompt-manifest reference"),
            (raw_response_ref, "raw-response reference"),
        )
    )
    provider_outcome = _optional_bool(provider_ok, field="provider_ok")
    if ok is not False:
        raise InvalidHypothesisGenerationCapabilityError(
            "provider failure receipt requires exact ok=false"
        )
    persistence_error = _optional_text(
        trace_persistence_error,
        field="trace persistence error",
    )
    category = _required_text(failure_category, field="provider failure category")
    error_type = _required_text(failure_type, field="provider failure type")
    with _CAPABILITY_LOCK:
        permit_state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        assert isinstance(permit_state, _PermitState)
        _same_installation(provider, permit_state.registry)
        _prove_context(permit_state.binding, label="ProviderGenerationPermit")
        if (
            permit_state.projection.provider is not provider
            or permit_state.phase is not _PermitPhase.CLAIMED_BEFORE_TRANSPORT
            or permit_state.outcome is not None
        ):
            raise HypothesisGenerationLifecycleError(
                "provider failure requires one exact active provider claim"
            )
        value = object.__new__(FailedHypothesisGeneration)
        _FAILURE_STATES[value] = _TerminalOutcomeState(
            projection=_TerminalOutcomeProjection(
                kind=outcome_kind,
                permit=permit,
                started_attempt=permit_state.projection.started_attempt,
                bound_prompt=permit_state.projection.bound_prompt,
                receipt=receipt,
                trace_ref=refs[0],
                prompt_manifest_ref=refs[1],
                raw_response_ref=refs[2],
                provider_ok=provider_outcome,
                ok=False,
                failure_category=category,
                failure_type=error_type,
                trace_persistence_error=persistence_error,
            ),
            issuer=provider,
            binding=permit_state.binding,
        )
        permit_state.outcome = value
        permit_state.phase = _PermitPhase.FAILURE_BOUND
        return value


def _issue_aborted_generation(
    registry: _AuthorityHandle,
    *,
    started_attempt: StartedHypothesisAttempt,
    bound_prompt: BoundHypothesisPrompt,
    view: HypothesisGenerationView,
    permit: ProviderGenerationPermit | None = None,
) -> AbortedHypothesisGeneration:
    """Issue an exact pre-claim abort, atomically cancelling a permit if present."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        started_state = _lookup_exact(
            started_attempt,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        prompt_state = _lookup_exact(
            bound_prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(started_state, _StartedAttemptState)
        assert isinstance(prompt_state, _BoundPromptState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, started_state.proposal_owner)
        _same_installation(registry, prompt_state.prompt_owner)
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.started_attempt is not started_attempt
            or view_state.bound_prompt is not bound_prompt
            or started_state.projection.view_identity is not view
            or prompt_state.projection.view_identity is not view
            or started_state.projection.bound_prompt is not bound_prompt
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "abort belongs to another START/prompt/view"
            )
        permit_state: _PermitState | None = None
        if permit is None:
            if (
                started_state.phase is not _StartedPhase.DURABLE_BOUND
                or started_state.permit is not None
                or prompt_state.phase is not _BoundPromptPhase.START_BOUND
                or view_state.phase is not _GenerationViewPhase.START_BOUND
            ):
                raise HypothesisGenerationLifecycleError(
                    "pre-permit abort requires an unbound durable START"
                )
        else:
            permit_state = _lookup_exact(
                permit,
                ProviderGenerationPermit,
                _PERMIT_STATES,  # type: ignore[arg-type]
                label="ProviderGenerationPermit",
            )
            assert isinstance(permit_state, _PermitState)
            _same_installation(registry, permit_state.registry)
            _prove_context(permit_state.binding, label="ProviderGenerationPermit")
            if (
                permit_state.registry is not registry
                or permit_state.projection.started_attempt is not started_attempt
                or permit_state.projection.bound_prompt is not bound_prompt
                or started_state.permit is not permit
                or view_state.permit is not permit
            ):
                raise InvalidHypothesisGenerationCapabilityError(
                    "abort permit belongs to another START/prompt/view"
                )
            if (
                permit_state.phase is not _PermitPhase.ISSUED
                or permit_state.outcome is not None
                or started_state.phase is not _StartedPhase.PROVIDER_BOUND
                or prompt_state.phase is not _BoundPromptPhase.PROVIDER_BOUND
                or view_state.phase is not _GenerationViewPhase.PERMIT_ISSUED
            ):
                raise HypothesisGenerationLifecycleError(
                    "exact provider permit is no longer abortable"
                )
        value = object.__new__(AbortedHypothesisGeneration)
        _ABORT_STATES[value] = _TerminalOutcomeState(
            projection=_TerminalOutcomeProjection(
                kind="aborted_before_transport",
                permit=permit,
                started_attempt=started_attempt,
                bound_prompt=bound_prompt,
                receipt=None,
                trace_ref=None,
                prompt_manifest_ref=None,
                raw_response_ref=None,
                provider_ok=None,
                ok=False,
                failure_category="provider_call_cancelled_before_transport",
                failure_type="AbortedHypothesisGeneration",
                trace_persistence_error=None,
            ),
            issuer=registry,
            binding=view_state.binding,
        )
        if permit_state is not None:
            permit_state.phase = _PermitPhase.CANCELLED
        view_state.outcome = value
        view_state.phase = _GenerationViewPhase.TERMINAL_OUTCOME_BOUND
        return value


def _inspect_generation_outcome(
    registry: _AuthorityHandle,
    *,
    permit: ProviderGenerationPermit,
    outcome: GeneratedHypothesisResult | FailedHypothesisGeneration,
    view: HypothesisGenerationView,
) -> _GeneratedResultProjection | _TerminalOutcomeProjection:
    """Non-consumingly prove the exact provider outcome/view identity."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        permit_state = _lookup_exact(
            permit,
            ProviderGenerationPermit,
            _PERMIT_STATES,  # type: ignore[arg-type]
            label="ProviderGenerationPermit",
        )
        assert isinstance(permit_state, _PermitState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _prove_context(permit_state.binding, label="ProviderGenerationPermit")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            permit_state.registry is not registry
            or view_state.registry is not registry
            or view_state.permit is not permit
            or permit_state.projection.view_identity is not view
            or permit_state.outcome is not outcome
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "provider outcome belongs to another permit/view"
            )
        if view_state.phase is not _GenerationViewPhase.PERMIT_ISSUED:
            raise HypothesisGenerationLifecycleError(
                "provider outcome was already observed by its generation view"
            )
        if type(outcome) is GeneratedHypothesisResult:
            outcome_state = _lookup_exact(
                outcome,
                GeneratedHypothesisResult,
                _RESULT_STATES,  # type: ignore[arg-type]
                label="GeneratedHypothesisResult",
            )
            assert isinstance(outcome_state, _GeneratedResultState)
            _same_installation(registry, outcome_state.provider)
            _prove_context(outcome_state.binding, label="GeneratedHypothesisResult")
            if permit_state.phase is not _PermitPhase.SUCCESS_BOUND:
                raise HypothesisGenerationLifecycleError(
                    "generated result is not bound to an exact successful permit"
                )
            view_state.outcome = outcome
            view_state.phase = _GenerationViewPhase.RESULT_BOUND
            return outcome_state.projection
        if type(outcome) is FailedHypothesisGeneration:
            outcome_state = _lookup_exact(
                outcome,
                FailedHypothesisGeneration,
                _FAILURE_STATES,  # type: ignore[arg-type]
                label="FailedHypothesisGeneration",
            )
            assert isinstance(outcome_state, _TerminalOutcomeState)
            _same_installation(registry, outcome_state.issuer)
            _prove_context(outcome_state.binding, label="FailedHypothesisGeneration")
            if permit_state.phase is not _PermitPhase.FAILURE_BOUND:
                raise HypothesisGenerationLifecycleError(
                    "provider failure is not bound to an exact failed permit"
                )
            view_state.outcome = outcome
            view_state.phase = _GenerationViewPhase.TERMINAL_OUTCOME_BOUND
            return outcome_state.projection
        raise InvalidHypothesisGenerationCapabilityError(
            "operation requires an exact provider generation outcome"
        )


def _begin_terminal_persistence(
    registry: _AuthorityHandle,
    view: HypothesisGenerationView,
    outcome: FailedHypothesisGeneration | AbortedHypothesisGeneration,
) -> None:
    """Spend the terminal-outcome view phase before the persistence transaction."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            view_state.registry is not registry
            or view_state.phase is not _GenerationViewPhase.TERMINAL_OUTCOME_BOUND
            or view_state.outcome is not outcome
        ):
            raise HypothesisGenerationLifecycleError(
                "generation view has no exact terminal outcome to persist"
            )
        view_state.phase = _GenerationViewPhase.TERMINAL_IN_FLIGHT


def _claim_terminal_outcome(
    proposal_owner: _AuthorityHandle,
    outcome: FailedHypothesisGeneration | AbortedHypothesisGeneration,
    *,
    started_attempt: StartedHypothesisAttempt,
    bound_prompt: BoundHypothesisPrompt,
) -> _TerminalOutcomeProjection:
    """Irreversibly claim one terminal outcome before durable persistence."""

    _handle_state(proposal_owner, role=_AuthorityRole.PROPOSAL_OWNER)
    with _CAPABILITY_LOCK:
        if type(outcome) is FailedHypothesisGeneration:
            states = _FAILURE_STATES
            label = "FailedHypothesisGeneration"
        elif type(outcome) is AbortedHypothesisGeneration:
            states = _ABORT_STATES
            label = "AbortedHypothesisGeneration"
        else:
            raise InvalidHypothesisGenerationCapabilityError(
                "terminal persistence requires an exact terminal outcome"
            )
        outcome_state = _lookup_exact(
            outcome,
            type(outcome),
            states,  # type: ignore[arg-type]
            label=label,
        )
        started_state = _lookup_exact(
            started_attempt,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        prompt_state = _lookup_exact(
            bound_prompt,
            BoundHypothesisPrompt,
            _BOUND_PROMPT_STATES,  # type: ignore[arg-type]
            label="BoundHypothesisPrompt",
        )
        assert isinstance(outcome_state, _TerminalOutcomeState)
        assert isinstance(started_state, _StartedAttemptState)
        assert isinstance(prompt_state, _BoundPromptState)
        view_state = _lookup_exact(
            started_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(proposal_owner, outcome_state.issuer)
        _same_installation(proposal_owner, started_state.proposal_owner)
        _same_installation(proposal_owner, prompt_state.prompt_owner)
        _prove_context(outcome_state.binding, label=label)
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(prompt_state.binding, label="BoundHypothesisPrompt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        projection = outcome_state.projection
        if (
            started_state.proposal_owner is not proposal_owner
            or projection.started_attempt is not started_attempt
            or projection.bound_prompt is not bound_prompt
            or started_state.projection.bound_prompt is not bound_prompt
            or view_state.outcome is not outcome
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "terminal outcome belongs to another START/prompt/view"
            )
        if (
            outcome_state.phase is not _TerminalOutcomePhase.ISSUED
            or started_state.phase
            not in {_StartedPhase.DURABLE_BOUND, _StartedPhase.PROVIDER_BOUND}
            or prompt_state.phase
            not in {_BoundPromptPhase.START_BOUND, _BoundPromptPhase.PROVIDER_BOUND}
            or view_state.phase is not _GenerationViewPhase.TERMINAL_IN_FLIGHT
        ):
            raise HypothesisGenerationLifecycleError(
                "terminal outcome's exact START/prompt binding is already spent"
            )
        if projection.permit is not None:
            permit_state = _lookup_exact(
                projection.permit,
                ProviderGenerationPermit,
                _PERMIT_STATES,  # type: ignore[arg-type]
                label="ProviderGenerationPermit",
            )
            assert isinstance(permit_state, _PermitState)
            permit_matches = (
                permit_state.phase is _PermitPhase.FAILURE_BOUND
                and permit_state.outcome is outcome
            ) or (
                permit_state.phase is _PermitPhase.CANCELLED
                and type(outcome) is AbortedHypothesisGeneration
                and permit_state.outcome is None
            )
            if started_state.permit is not projection.permit or not permit_matches:
                raise InvalidHypothesisGenerationCapabilityError(
                    "terminal outcome does not match the START permit"
                )
        elif started_state.permit is not None:
            raise InvalidHypothesisGenerationCapabilityError(
                "pre-permit abort cannot terminalize a permit-bound START"
            )
        outcome_state.phase = _TerminalOutcomePhase.TERMINALIZED
        started_state.phase = _StartedPhase.TERMINALIZED
        prompt_state.phase = _BoundPromptPhase.TERMINALIZED
        return projection


def _issue_terminal_receipt(
    proposal_owner: _AuthorityHandle,
    *,
    terminal_event: object,
    terminal_event_storage_sha256: str,
    outcome: FailedHypothesisGeneration | AbortedHypothesisGeneration,
    started_attempt: StartedHypothesisAttempt,
) -> TerminalAttemptReceipt:
    """Issue a receipt only after exact terminal commit classification."""

    _handle_state(proposal_owner, role=_AuthorityRole.PROPOSAL_OWNER)
    if terminal_event is None:
        raise InvalidHypothesisGenerationCapabilityError(
            "terminal receipt requires the exact durable event"
        )
    digest = _required_digest(
        terminal_event_storage_sha256,
        field="terminal event storage digest",
    )
    with _CAPABILITY_LOCK:
        if type(outcome) is FailedHypothesisGeneration:
            states = _FAILURE_STATES
            label = "FailedHypothesisGeneration"
        elif type(outcome) is AbortedHypothesisGeneration:
            states = _ABORT_STATES
            label = "AbortedHypothesisGeneration"
        else:
            raise InvalidHypothesisGenerationCapabilityError(
                "terminal receipt requires an exact terminal outcome"
            )
        outcome_state = _lookup_exact(
            outcome,
            type(outcome),
            states,  # type: ignore[arg-type]
            label=label,
        )
        started_state = _lookup_exact(
            started_attempt,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        assert isinstance(outcome_state, _TerminalOutcomeState)
        assert isinstance(started_state, _StartedAttemptState)
        view_state = _lookup_exact(
            started_state.projection.view_identity,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(proposal_owner, outcome_state.issuer)
        _prove_context(outcome_state.binding, label=label)
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if (
            started_state.proposal_owner is not proposal_owner
            or outcome_state.projection.started_attempt is not started_attempt
            or view_state.outcome is not outcome
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "terminal receipt outcome belongs to another START/view"
            )
        if (
            outcome_state.phase is not _TerminalOutcomePhase.TERMINALIZED
            or outcome_state.terminal_receipt is not None
            or started_state.phase is not _StartedPhase.TERMINALIZED
            or view_state.phase is not _GenerationViewPhase.TERMINAL_IN_FLIGHT
        ):
            raise HypothesisGenerationLifecycleError(
                "exact terminal START/outcome already issued or lost its receipt phase"
            )
        value = object.__new__(TerminalAttemptReceipt)
        _RECEIPT_STATES[value] = _TerminalReceiptState(
            projection=_TerminalReceiptProjection(
                terminal_event=terminal_event,
                terminal_event_storage_sha256=digest,
                outcome=outcome,
                started_attempt=started_attempt,
            ),
            proposal_owner=proposal_owner,
            binding=view_state.binding,
        )
        outcome_state.terminal_receipt = value
        return value


def _resolve_terminal_receipt(
    registry: _AuthorityHandle,
    receipt: TerminalAttemptReceipt,
    *,
    started_attempt: StartedHypothesisAttempt,
    view: HypothesisGenerationView,
) -> _TerminalReceiptProjection:
    """Spend one exact committed receipt while Registry resolves its reservation."""

    _handle_state(registry, role=_AuthorityRole.REGISTRY)
    with _CAPABILITY_LOCK:
        receipt_state = _lookup_exact(
            receipt,
            TerminalAttemptReceipt,
            _RECEIPT_STATES,  # type: ignore[arg-type]
            label="TerminalAttemptReceipt",
        )
        started_state = _lookup_exact(
            started_attempt,
            StartedHypothesisAttempt,
            _STARTED_STATES,  # type: ignore[arg-type]
            label="StartedHypothesisAttempt",
        )
        assert isinstance(receipt_state, _TerminalReceiptState)
        assert isinstance(started_state, _StartedAttemptState)
        view_state = _lookup_exact(
            view,
            HypothesisGenerationView,
            _GENERATION_VIEW_STATES,  # type: ignore[arg-type]
            label="HypothesisGenerationView",
        )
        assert isinstance(view_state, _GenerationViewState)
        _same_installation(registry, receipt_state.proposal_owner)
        _prove_context(receipt_state.binding, label="TerminalAttemptReceipt")
        _prove_context(started_state.binding, label="StartedHypothesisAttempt")
        _prove_context(view_state.binding, label="HypothesisGenerationView")
        if receipt_state.phase is not _ReceiptPhase.ISSUED:
            raise HypothesisGenerationLifecycleError(
                "TerminalAttemptReceipt is already resolved"
            )
        if (
            receipt_state.projection.started_attempt is not started_attempt
            or view_state.registry is not registry
            or view_state.phase is not _GenerationViewPhase.TERMINAL_IN_FLIGHT
            or view_state.started_attempt is not started_attempt
            or view_state.outcome is not receipt_state.projection.outcome
            or started_state.projection.view_identity is not view
        ):
            raise InvalidHypothesisGenerationCapabilityError(
                "terminal receipt belongs to another START/view or is spent"
        )
        receipt_state.phase = _ReceiptPhase.RESERVATION_RESOLVED
        view_state.terminal_receipt = receipt
        view_state.phase = _GenerationViewPhase.SPENT
        _retire_context(
            view_state.binding,
            label="HypothesisGenerationView",
        )
        return receipt_state.projection


__all__ = (
    "AbortedHypothesisGeneration",
    "BoundHypothesisPrompt",
    "FailedHypothesisGeneration",
    "GeneratedHypothesisResult",
    "HypothesisCodeSource",
    "HypothesisCodeSourceRequest",
    "HypothesisGenerationAuthorityError",
    "HypothesisGenerationLifecycleError",
    "HypothesisGenerationView",
    "HypothesisProblemEvidenceProjection",
    "HypothesisPromptSource",
    "InvalidHypothesisGenerationCapabilityError",
    "ProviderGenerationPermit",
    "StartedHypothesisAttempt",
    "TerminalAttemptReceipt",
)
