"""Dormant one-root Campaign coordination for durable Branch/H mutations.

The Registry is the sole Campaign-local owner of immutable revision tokens,
detached projections, mutation views, receipt staging, and post-commit local
publication.  Focused stores continue to own every Branch/H statement and row
decoder; ``owner_transaction`` owns permits and receipts; ``sqlite_connection``
owns connection and transaction lifecycle.

This module is deliberately not imported by production Campaign composition.
It implements existing-owner mutation only.  Creation views and creation
receipt consumption remain unavailable until champion and proposal-attempt
participants can bind their durable authorization into the write receipt.
"""

from __future__ import annotations

import contextvars
import enum
import hashlib
import json
import re
import threading
import uuid
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final, Mapping

from scion.core.models import Branch, HypothesisRecord
from scion.lineage import owner_transaction as _owner
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage.branch_owner_store import BranchStore
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerNotFound,
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.lineage.hypothesis_owner_store import HypothesisStore
from scion.lineage.proposal_attempt_owner import (
    ProposalAttemptCommitClassification,
    ProposalAttemptOwner,
    StoredProposalAttemptEvent,
    _AttemptGroupDisposition,
    _HypothesisAttemptInventory,
)
from scion.proposal import hypothesis_generation_authority as _generation
from scion.proposal.context_manager.manager import (
    ContextManager,
    HypothesisProblemEvidenceRejectedError,
    HypothesisProblemEvidenceUnknownError,
)
from scion.proposal.engine.provider_call import ProviderCallOwner
from scion.proposal.hypothesis_code_source_owner import (
    HypothesisCodeSourceOwner,
    HypothesisCodeSourceRejectedError,
    HypothesisCodeSourceUnknownError,
)
from scion.proposal.prompt_projection_authority import (
    ProposalPromptProjectionAuthority,
)

__all__ = (
    "BranchMutationView",
    "CampaignOwnerCleanupError",
    "CampaignOwnerIntegrityHoldError",
    "CampaignOwnerLifecycleError",
    "CampaignOwnerReentrancyError",
    "CampaignOwnerRegistry",
    "CampaignOwnerRegistryError",
    "CampaignOwnerTransactionScope",
    "HypothesisMutationView",
    "HypothesisGenerationReservationHoldError",
    "InvalidCampaignOwnerCapabilityError",
    "LoadedRestoreAuthority",
)


class CampaignOwnerRegistryError(RuntimeError):
    """Base error for dormant Campaign owner coordination."""


class InvalidCampaignOwnerCapabilityError(TypeError, CampaignOwnerRegistryError):
    """A restore authority, view, scope, or standalone lease was not issued."""


class CampaignOwnerLifecycleError(CampaignOwnerRegistryError):
    """A Registry phase, capability lifecycle, or exact-view rule was violated."""


class CampaignOwnerReentrancyError(CampaignOwnerLifecycleError):
    """A public Registry operation re-entered an active owner scope."""


class CampaignOwnerIntegrityHoldError(CampaignOwnerRegistryError):
    """The Campaign owner root is permanently non-schedulable in this process."""


class CampaignOwnerCleanupError(CampaignOwnerRegistryError):
    """Cleanup failed after a proven durable/local owner result."""


class HypothesisGenerationReservationHoldError(CampaignOwnerRegistryError):
    """One Branch remains unavailable after uncertain generation persistence."""


class _StartupPhase(enum.Enum):
    OFFLINE_STANDALONE = enum.auto()
    DRAINING_STANDALONE = enum.auto()
    RESTORING = enum.auto()
    LIVE_REGISTRY = enum.auto()


class _Availability(enum.Enum):
    CLEAR = enum.auto()
    TRANSITION = enum.auto()
    PERMANENT_HOLD = enum.auto()


class _CapabilityPhase(enum.Enum):
    ISSUED = enum.auto()
    CLAIMED = enum.auto()
    SPENT = enum.auto()


class _RestorePhase(enum.Enum):
    LOADED = enum.auto()
    SPENT = enum.auto()


class _CommitOutcome(enum.Enum):
    PROVEN_COMMITTED = enum.auto()
    PROVEN_ROLLED_BACK = enum.auto()
    UNCERTAIN_OR_MIXED = enum.auto()


class _GenerationReservationPhase(enum.Enum):
    LOCAL = enum.auto()
    DURABLE_OPEN = enum.auto()
    OUTCOME_BOUND = enum.auto()
    RESOLVED = enum.auto()
    UNCERTAIN_HOLD = enum.auto()
    RELEASED = enum.auto()


@dataclass(frozen=True, slots=True)
class _BranchSlot:
    owner: RevisionedBranchRecord
    projection: Branch


@dataclass(frozen=True, slots=True)
class _HypothesisSlot:
    owner: RevisionedHypothesisRecord
    projection: HypothesisRecord


@dataclass(frozen=True, slots=True)
class _HypothesisSlotIndex:
    by_id: Mapping[str, _HypothesisSlot]
    current_by_branch: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _CampaignOwnerState:
    branch_slots: Mapping[str, _BranchSlot]
    hypothesis_slots: _HypothesisSlotIndex
    publication_generation: int


@dataclass(frozen=True, slots=True)
class _HypothesisGenerationComponents:
    code_source_owner: HypothesisCodeSourceOwner
    context_manager: ContextManager
    prompt_owner: ProposalPromptProjectionAuthority
    proposal_owner: ProposalAttemptOwner
    provider_owner: ProviderCallOwner
    registry_authority: _generation._AuthorityHandle
    provider_authority: _generation._AuthorityHandle
    campaign_id: str
    runtime_mode: str
    problem_id: str
    problem_spec_hash: str
    split_manifest_hash: str
    seed_ledger_hash: str


@dataclass(slots=True)
class _HypothesisGenerationReservation:
    branch_id: str
    reservation_id: str
    phase: _GenerationReservationPhase
    view: _generation.HypothesisGenerationView | None


@dataclass(slots=True)
class _HypothesisGenerationState:
    view: _generation.HypothesisGenerationView
    reservation: _HypothesisGenerationReservation
    root: _CampaignOwnerState
    branch_owner: RevisionedBranchRecord
    hypothesis_bundle: tuple[RevisionedHypothesisRecord, ...]
    prior_head: RevisionedHypothesisRecord | None
    code_source: _generation.HypothesisCodeSource | None = None
    prompt_source: _generation.HypothesisPromptSource | None = None
    bound_prompt: _generation.BoundHypothesisPrompt | None = None
    pending_start: StoredProposalAttemptEvent | None = None
    started_attempt: _generation.StartedHypothesisAttempt | None = None
    permit: _generation.ProviderGenerationPermit | None = None
    outcome: (
        _generation.GeneratedHypothesisResult
        | _generation.FailedHypothesisGeneration
        | _generation.AbortedHypothesisGeneration
        | None
    ) = None


class LoadedRestoreAuthority:
    """Sealed authority for one complete, validated, unpublished restore root."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "LoadedRestoreAuthority":
        raise InvalidCampaignOwnerCapabilityError(
            "LoadedRestoreAuthority is issued only by begin_restore()"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("LoadedRestoreAuthority is sealed")

    def __copy__(self) -> "LoadedRestoreAuthority":
        raise InvalidCampaignOwnerCapabilityError(
            "LoadedRestoreAuthority cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "LoadedRestoreAuthority":
        raise InvalidCampaignOwnerCapabilityError(
            "LoadedRestoreAuthority cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidCampaignOwnerCapabilityError(
            "LoadedRestoreAuthority cannot be pickled"
        )


class BranchMutationView:
    """Sealed one-shot mutation view over one captured Branch owner root."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "BranchMutationView":
        raise InvalidCampaignOwnerCapabilityError(
            "BranchMutationView is issued only by CampaignOwnerRegistry"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("BranchMutationView is sealed")

    @property
    def owner(self) -> RevisionedBranchRecord:
        state = _lookup_view_state(self, expected_kind=_ViewKind.BRANCH)
        _prove_view_context(state)
        if type(state.owner) is not RevisionedBranchRecord:
            raise InvalidCampaignOwnerCapabilityError("Branch view owner is malformed")
        return state.owner

    @property
    def target(self) -> Branch:
        state = _lookup_view_state(self, expected_kind=_ViewKind.BRANCH)
        _prove_view_context(state)
        if type(state.target) is not Branch:
            raise InvalidCampaignOwnerCapabilityError("Branch view target is malformed")
        return state.target

    def __copy__(self) -> "BranchMutationView":
        raise InvalidCampaignOwnerCapabilityError("BranchMutationView cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> "BranchMutationView":
        raise InvalidCampaignOwnerCapabilityError("BranchMutationView cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidCampaignOwnerCapabilityError("BranchMutationView cannot be pickled")


class HypothesisMutationView:
    """Sealed one-shot mutation view over one captured hypothesis owner root."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "HypothesisMutationView":
        raise InvalidCampaignOwnerCapabilityError(
            "HypothesisMutationView is issued only by CampaignOwnerRegistry"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("HypothesisMutationView is sealed")

    @property
    def owner(self) -> RevisionedHypothesisRecord:
        state = _lookup_view_state(self, expected_kind=_ViewKind.HYPOTHESIS)
        _prove_view_context(state)
        if type(state.owner) is not RevisionedHypothesisRecord:
            raise InvalidCampaignOwnerCapabilityError(
                "hypothesis view owner is malformed"
            )
        return state.owner

    @property
    def target(self) -> HypothesisRecord:
        state = _lookup_view_state(self, expected_kind=_ViewKind.HYPOTHESIS)
        _prove_view_context(state)
        if type(state.target) is not HypothesisRecord:
            raise InvalidCampaignOwnerCapabilityError(
                "hypothesis view target is malformed"
            )
        return state.target

    def __copy__(self) -> "HypothesisMutationView":
        raise InvalidCampaignOwnerCapabilityError(
            "HypothesisMutationView cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "HypothesisMutationView":
        raise InvalidCampaignOwnerCapabilityError(
            "HypothesisMutationView cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidCampaignOwnerCapabilityError(
            "HypothesisMutationView cannot be pickled"
        )


class CampaignOwnerTransactionScope:
    """Sealed active scope for one complete Registry-owned owner commit."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "CampaignOwnerTransactionScope":
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerTransactionScope is issued only by owner_transaction()"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("CampaignOwnerTransactionScope is sealed")

    @property
    def transaction(self) -> _sqlite.ImmediateTransaction:
        return _require_active_scope(self).transaction

    def compare_and_stage_branch(self, view: BranchMutationView) -> None:
        state = _require_active_scope(self)
        _compare_and_stage_branch(state, view)

    def compare_and_stage_hypothesis(self, view: HypothesisMutationView) -> None:
        state = _require_active_scope(self)
        _compare_and_stage_hypothesis(state, view)

    def __copy__(self) -> "CampaignOwnerTransactionScope":
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerTransactionScope cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "CampaignOwnerTransactionScope":
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerTransactionScope cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerTransactionScope cannot be pickled"
        )


class _StandaloneLease:
    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "_StandaloneLease":
        raise InvalidCampaignOwnerCapabilityError(
            "standalone leases are issued only by the Registry startup boundary"
        )


class _ViewKind(enum.Enum):
    BRANCH = enum.auto()
    HYPOTHESIS = enum.auto()


_OwnerToken = RevisionedBranchRecord | RevisionedHypothesisRecord
_MutationView = BranchMutationView | HypothesisMutationView


@dataclass(slots=True)
class _RestoreState:
    registry_ref: weakref.ReferenceType[CampaignOwnerRegistry]
    prepared_root: _CampaignOwnerState
    thread_id: int
    context_probe: contextvars.ContextVar[object | None]
    context_token: contextvars.Token[object | None]
    phase: _RestorePhase = _RestorePhase.LOADED


@dataclass(slots=True)
class _ViewState:
    registry_ref: weakref.ReferenceType[CampaignOwnerRegistry]
    kind: _ViewKind
    owner: _OwnerToken
    target: Branch | HypothesisRecord
    generation: int
    thread_id: int
    context_probe: contextvars.ContextVar[object | None]
    context_token: contextvars.Token[object | None]
    phase: _CapabilityPhase = _CapabilityPhase.ISSUED


@dataclass(slots=True)
class _StandaloneLeaseState:
    registry_ref: weakref.ReferenceType[CampaignOwnerRegistry]
    thread_id: int
    active: bool = True


@dataclass(slots=True)
class _ScopeState:
    registry: CampaignOwnerRegistry
    scope: CampaignOwnerTransactionScope
    session: _sqlite._CoordinatedTransactionSession
    transaction: _sqlite.ImmediateTransaction
    ledger: _owner._OwnerReceiptLedger
    requested_views: tuple[_MutationView, ...]
    requested_view_states: tuple[_ViewState, ...]
    old_root: _CampaignOwnerState
    thread_id: int
    context_token: contextvars.Token[CampaignOwnerTransactionScope | None]
    context_probe: contextvars.ContextVar[object | None]
    context_proof_token: contextvars.Token[object | None]
    staged_tokens: dict[_MutationView, _OwnerToken]
    staged_receipts: dict[_MutationView, _owner.OwnerMutationReceipt]
    staged_witnesses: dict[_MutationView, object]
    prepared_root: _CampaignOwnerState | None = None
    witnesses: tuple[object, ...] = ()
    commit_latched: bool = False
    active: bool = True


_RESTORE_STATES: weakref.WeakKeyDictionary[
    LoadedRestoreAuthority, _RestoreState
] = weakref.WeakKeyDictionary()
_VIEW_STATES: weakref.WeakKeyDictionary[_MutationView, _ViewState] = (
    weakref.WeakKeyDictionary()
)
_STANDALONE_LEASE_STATES: weakref.WeakKeyDictionary[
    _StandaloneLease, _StandaloneLeaseState
] = weakref.WeakKeyDictionary()
_SCOPE_STATES: weakref.WeakKeyDictionary[
    CampaignOwnerTransactionScope, _ScopeState
] = weakref.WeakKeyDictionary()
_CAPABILITY_STATES_LOCK = threading.RLock()
_ACTIVE_SCOPE: contextvars.ContextVar[CampaignOwnerTransactionScope | None] = (
    contextvars.ContextVar("scion_campaign_owner_scope", default=None)
)
_CONTEXT_PROOF: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "scion_campaign_owner_context_proof",
    default=None,
)
_THREAD_SCOPE = threading.local()

_DATABASE_REGISTRIES: dict[
    tuple[int, int],
    weakref.ReferenceType[CampaignOwnerRegistry],
] = {}
_AUTHORITY_REGISTRIES_LOCK = threading.Lock()
_CANONICAL_UTC_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"\.[0-9]{6}\+00:00$"
)
_OWNER_CONTEXT_SCHEMA: Final[str] = "hypothesis-owner-context-projection.v1"
_H_BUNDLE_SCHEMA: Final[str] = "hypothesis-generation-source-bundle.v1"


def _database_registry_key(
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> tuple[int, int]:
    state = _sqlite._lookup_authority_state(database_authority)
    return state.device, state.inode


def _empty_owner_state() -> _CampaignOwnerState:
    return _CampaignOwnerState(
        branch_slots=MappingProxyType({}),
        hypothesis_slots=_HypothesisSlotIndex(
            by_id=MappingProxyType({}),
            current_by_branch=MappingProxyType({}),
        ),
        publication_generation=0,
    )


def _required_owner_id(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(
            f"{label} must be a non-empty exact string without edge whitespace"
        )
    return value


def _required_digest(value: object, *, label: str) -> str:
    text = _required_owner_id(value, label=label)
    if len(text) != 64:
        raise DurableOwnerIntegrityError(f"{label} must be a SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(f"{label} must be a SHA-256 digest") from exc
    if text != text.lower():
        raise DurableOwnerIntegrityError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return text


def _required_sqlite_integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0 or value > (1 << 63) - 1:
        raise DurableOwnerIntegrityError(
            f"{label} must be a nonnegative SQLite INTEGER"
        )
    return value


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise DurableOwnerIntegrityError(f"{label} is not canonical JSON") from exc


def _canonical_hypothesis_created_at(
    token: RevisionedHypothesisRecord,
) -> str:
    try:
        payload = json.loads(token.canonical_storage_payload_json)
        raw = payload["created_at"]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise DurableOwnerIntegrityError(
            "hypothesis owner has no canonical created_at"
        ) from exc
    if type(raw) is not str or _CANONICAL_UTC_RE.fullmatch(raw) is None:
        raise DurableOwnerIntegrityError(
            "hypothesis created_at is not canonical UTC microsecond text"
        )
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DurableOwnerIntegrityError(
            "hypothesis created_at is invalid"
        ) from exc
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="microseconds") != raw
    ):
        raise DurableOwnerIntegrityError(
            "hypothesis created_at is not canonical UTC microsecond text"
        )
    return raw


def _hypothesis_owner_item(
    token: RevisionedHypothesisRecord,
) -> dict[str, object]:
    return {
        "hypothesis_id": _required_owner_id(
            token.hypothesis_id,
            label="hypothesis ID",
        ),
        "owner_revision": _required_sqlite_integer(
            token.owner_revision,
            label="hypothesis owner revision",
        ),
        "storage_sha256": _required_digest(
            token.payload_sha256,
            label="hypothesis storage digest",
        ),
    }


def _hypothesis_bundle_projection(
    branch_id: str,
    bundle: tuple[RevisionedHypothesisRecord, ...],
) -> tuple[str, tuple[dict[str, object], ...]]:
    items = tuple(
        _hypothesis_owner_item(token)
        for token in sorted(bundle, key=lambda item: item.hypothesis_id)
    )
    digest_payload = {
        "schema_version": _H_BUNDLE_SCHEMA,
        "branch_id": branch_id,
        "count": len(items),
        "items": items,
    }
    digest = hashlib.sha256(
        _canonical_json_bytes(digest_payload, label="hypothesis owner bundle")
    ).hexdigest()
    return digest, items


def _prior_hypothesis_head(
    bundle: tuple[RevisionedHypothesisRecord, ...],
) -> RevisionedHypothesisRecord | None:
    if not bundle:
        return None
    return max(
        bundle,
        key=lambda token: (
            _canonical_hypothesis_created_at(token),
            token.hypothesis_id,
        ),
    )


def _owner_context_json(
    components: _HypothesisGenerationComponents,
    *,
    root: _CampaignOwnerState,
    branch_owner: RevisionedBranchRecord,
    bundle: tuple[RevisionedHypothesisRecord, ...],
    prior_head: RevisionedHypothesisRecord | None,
    h_bundle_digest: str,
    h_bundle_items: tuple[dict[str, object], ...],
) -> bytes:
    branch = branch_owner.value()
    branch_id = _required_owner_id(branch.branch_id, label="Branch ID")
    branch_revision = _required_sqlite_integer(
        branch_owner.owner_revision,
        label="Branch owner revision",
    )
    branch_storage_digest = _required_digest(
        branch_owner.payload_sha256,
        label="Branch storage digest",
    )
    base_champion_id = _required_sqlite_integer(
        branch.base_champion_id,
        label="base champion ID",
    )
    base_weight_revision = _required_sqlite_integer(
        branch.weight_revision,
        label="base champion weight revision",
    )
    current_code_hash = (
        None
        if branch.current_code_hash is None
        else _required_digest(
            branch.current_code_hash,
            label="Branch current code hash",
        )
    )
    last_clean_code_hash = (
        None
        if branch.last_clean_code_hash is None
        else _required_digest(
            branch.last_clean_code_hash,
            label="Branch last-clean code hash",
        )
    )
    base_hash = _required_digest(
        branch.base_champion_hash,
        label="Branch base champion hash",
    )
    anchors = {
        "problem_id": components.problem_id,
        "problem_spec_hash": components.problem_spec_hash,
        "split_manifest_hash": components.split_manifest_hash,
        "seed_ledger_hash": components.seed_ledger_hash,
        "champion_version": base_champion_id,
        "champion_weight_revision": base_weight_revision,
        "champion_code_snapshot_hash": base_hash,
        "branch_base_champion_id": base_champion_id,
        "branch_base_champion_hash": base_hash,
    }
    payload = {
        "schema_version": _OWNER_CONTEXT_SCHEMA,
        "campaign_id": components.campaign_id,
        "runtime_mode": components.runtime_mode,
        "root_generation": _required_sqlite_integer(
            root.publication_generation,
            label="owner root generation",
        ),
        "branch": {
            "branch_id": branch_id,
            "owner_revision": branch_revision,
            "storage_sha256": branch_storage_digest,
            "state": branch.state.value,
            "branch_code_status": branch.branch_code_status,
            "current_code_hash": current_code_hash,
            "last_clean_code_hash": last_clean_code_hash,
            "base_champion_id": base_champion_id,
            "base_champion_hash": base_hash,
            "base_champion_weight_revision": base_weight_revision,
        },
        "h_bundle": {
            "digest": h_bundle_digest,
            "count": len(h_bundle_items),
            "items": h_bundle_items,
        },
        "prior_head": (
            None if prior_head is None else _hypothesis_owner_item(prior_head)
        ),
        "anchors": anchors,
    }
    return _canonical_json_bytes(payload, label="hypothesis owner context")


def _restore_generation_holds(
    inventory: _HypothesisAttemptInventory,
    prepared_root: _CampaignOwnerState,
) -> dict[str, _HypothesisGenerationReservation]:
    if type(inventory) is not _HypothesisAttemptInventory:
        raise DurableOwnerIntegrityError(
            "proposal-attempt restore returned another inventory kind"
        )
    if inventory.unattributed_malformed:
        raise DurableOwnerIntegrityError(
            "proposal-attempt restore contains unattributed malformed storage"
        )
    held_branches = set(inventory.malformed_branch_ids)
    for group in inventory.groups:
        if group.disposition in {
            _AttemptGroupDisposition.UNRESOLVED,
            _AttemptGroupDisposition.MALFORMED,
        }:
            held_branches.add(
                _required_owner_id(
                    group.branch_id,
                    label="restored proposal-attempt Branch ID",
                )
            )
        elif group.disposition is not _AttemptGroupDisposition.RESOLVED:
            raise DurableOwnerIntegrityError(
                "proposal-attempt restore has an unknown group disposition"
            )
    holds: dict[str, _HypothesisGenerationReservation] = {}
    for branch_id in sorted(held_branches):
        if branch_id not in prepared_root.branch_slots:
            raise DurableOwnerIntegrityError(
                "proposal-attempt hold references a missing Branch owner"
            )
        holds[branch_id] = _HypothesisGenerationReservation(
            branch_id=branch_id,
            reservation_id=f"restored-hold:{branch_id}",
            phase=_GenerationReservationPhase.UNCERTAIN_HOLD,
            view=None,
        )
    return holds


def _validate_generation(value: object) -> int:
    if type(value) is not int or value < 0:
        raise DurableOwnerIntegrityError(
            "Campaign owner publication generation must be a nonnegative integer"
        )
    return value


def _build_owner_state(
    branch_tokens: Mapping[str, RevisionedBranchRecord],
    hypothesis_tokens: Mapping[str, RevisionedHypothesisRecord],
    *,
    generation: int,
) -> _CampaignOwnerState:
    next_generation = _validate_generation(generation)
    branch_slots: dict[str, _BranchSlot] = {}
    for owner_id, token in branch_tokens.items():
        if type(token) is not RevisionedBranchRecord:
            raise DurableOwnerIntegrityError("Branch root contains a forged token")
        if owner_id != token.branch_id:
            raise DurableOwnerIntegrityError("Branch root key differs from its token")
        if owner_id in branch_slots:
            raise DurableOwnerIntegrityError("Branch root contains duplicate owners")
        projection = token.value()
        if type(projection) is not Branch or projection.branch_id != owner_id:
            raise DurableOwnerIntegrityError("Branch token rebuilt another owner")
        branch_slots[owner_id] = _BranchSlot(token, projection)

    hypothesis_slots: dict[str, _HypothesisSlot] = {}
    current_by_branch: dict[str, str] = {}
    for owner_id, token in hypothesis_tokens.items():
        if type(token) is not RevisionedHypothesisRecord:
            raise DurableOwnerIntegrityError("hypothesis root contains a forged token")
        if owner_id != token.hypothesis_id:
            raise DurableOwnerIntegrityError(
                "hypothesis root key differs from its token"
            )
        if owner_id in hypothesis_slots:
            raise DurableOwnerIntegrityError(
                "hypothesis root contains duplicate owners"
            )
        projection = token.value()
        if (
            type(projection) is not HypothesisRecord
            or projection.hypothesis_id != owner_id
        ):
            raise DurableOwnerIntegrityError("hypothesis token rebuilt another owner")
        if projection.branch_id not in branch_slots:
            raise DurableOwnerIntegrityError(
                "hypothesis root references a missing Branch owner"
            )
        hypothesis_slots[owner_id] = _HypothesisSlot(token, projection)
        if projection.status == "active":
            prior = current_by_branch.get(projection.branch_id)
            if prior is not None:
                raise DurableOwnerIntegrityError(
                    "a Branch has more than one active hypothesis owner"
                )
            current_by_branch[projection.branch_id] = owner_id

    for branch_id, hypothesis_id in current_by_branch.items():
        slot = hypothesis_slots.get(hypothesis_id)
        if (
            slot is None
            or slot.projection.branch_id != branch_id
            or slot.projection.status != "active"
        ):
            raise DurableOwnerIntegrityError(
                "current hypothesis index differs from its owner slots"
            )

    return _CampaignOwnerState(
        branch_slots=MappingProxyType(branch_slots),
        hypothesis_slots=_HypothesisSlotIndex(
            by_id=MappingProxyType(hypothesis_slots),
            current_by_branch=MappingProxyType(current_by_branch),
        ),
        publication_generation=next_generation,
    )


def _root_branch_tokens(
    root: _CampaignOwnerState,
) -> dict[str, RevisionedBranchRecord]:
    return {owner_id: slot.owner for owner_id, slot in root.branch_slots.items()}


def _root_hypothesis_tokens(
    root: _CampaignOwnerState,
) -> dict[str, RevisionedHypothesisRecord]:
    return {
        owner_id: slot.owner
        for owner_id, slot in root.hypothesis_slots.by_id.items()
    }


def _prepare_successor_root(
    old_root: _CampaignOwnerState,
    staged_tokens: Mapping[_MutationView, _OwnerToken],
) -> _CampaignOwnerState:
    branch_tokens = _root_branch_tokens(old_root)
    hypothesis_tokens = _root_hypothesis_tokens(old_root)
    for view, token in staged_tokens.items():
        if type(view) is BranchMutationView:
            if type(token) is not RevisionedBranchRecord:
                raise DurableOwnerIntegrityError(
                    "Branch staging produced another owner kind"
                )
            if token.branch_id not in branch_tokens:
                raise DurableOwnerIntegrityError(
                    "Branch mutation cannot create an absent local owner"
                )
            branch_tokens[token.branch_id] = token
        elif type(view) is HypothesisMutationView:
            if type(token) is not RevisionedHypothesisRecord:
                raise DurableOwnerIntegrityError(
                    "hypothesis staging produced another owner kind"
                )
            if token.hypothesis_id not in hypothesis_tokens:
                raise DurableOwnerIntegrityError(
                    "hypothesis mutation cannot create an absent local owner"
                )
            hypothesis_tokens[token.hypothesis_id] = token
        else:
            raise InvalidCampaignOwnerCapabilityError(
                "prepared root contains a forged mutation view"
            )
    return _build_owner_state(
        branch_tokens,
        hypothesis_tokens,
        generation=old_root.publication_generation + 1,
    )


def _lookup_restore_state(value: object) -> _RestoreState:
    if type(value) is not LoadedRestoreAuthority:
        raise InvalidCampaignOwnerCapabilityError(
            "operation requires an issued LoadedRestoreAuthority"
        )
    with _CAPABILITY_STATES_LOCK:
        state = _RESTORE_STATES.get(value)
    if state is None:
        raise InvalidCampaignOwnerCapabilityError(
            "LoadedRestoreAuthority was not issued"
        )
    return state


def _lookup_view_state(
    value: object,
    *,
    expected_kind: _ViewKind | None = None,
    allow_spent: bool = False,
) -> _ViewState:
    if type(value) not in {BranchMutationView, HypothesisMutationView}:
        raise InvalidCampaignOwnerCapabilityError(
            "operation requires an issued mutation view"
        )
    with _CAPABILITY_STATES_LOCK:
        state = _VIEW_STATES.get(value)  # type: ignore[arg-type]
    if state is None:
        raise InvalidCampaignOwnerCapabilityError("mutation view was not issued")
    if expected_kind is not None and state.kind is not expected_kind:
        raise InvalidCampaignOwnerCapabilityError("mutation view has another kind")
    if state.phase is _CapabilityPhase.SPENT and not allow_spent:
        raise CampaignOwnerLifecycleError("mutation view is spent")
    return state


def _lookup_scope_state(value: object) -> _ScopeState:
    if type(value) is not CampaignOwnerTransactionScope:
        raise InvalidCampaignOwnerCapabilityError(
            "operation requires an issued Campaign owner scope"
        )
    with _CAPABILITY_STATES_LOCK:
        state = _SCOPE_STATES.get(value)
    if state is None:
        raise InvalidCampaignOwnerCapabilityError("Campaign owner scope was not issued")
    return state


def _require_active_scope(scope: CampaignOwnerTransactionScope) -> _ScopeState:
    state = _lookup_scope_state(scope)
    if not state.active:
        raise CampaignOwnerLifecycleError("Campaign owner scope is no longer active")
    if state.thread_id != threading.get_ident():
        raise CampaignOwnerLifecycleError("Campaign owner scope cannot cross threads")
    if _ACTIVE_SCOPE.get() is not scope or getattr(_THREAD_SCOPE, "scope", None) is not scope:
        raise CampaignOwnerLifecycleError("Campaign owner scope cannot cross Contexts")
    _prove_scope_context(state)
    _sqlite.require_active_immediate_transaction(
        state.transaction,
        state.registry._database_authority,
    )
    return state


def _new_context_proof() -> tuple[
    contextvars.ContextVar[object | None],
    contextvars.Token[object | None],
]:
    probe = _CONTEXT_PROOF
    return probe, probe.set(object())


def _prove_context(
    *,
    probe: contextvars.ContextVar[object | None],
    token: contextvars.Token[object | None],
    label: str,
) -> contextvars.Token[object | None]:
    current = probe.get()
    try:
        probe.reset(token)
    except (RuntimeError, ValueError) as exc:
        raise CampaignOwnerLifecycleError(f"{label} cannot cross Contexts") from exc
    return probe.set(current)


def _prove_view_context(state: _ViewState) -> None:
    if state.thread_id != threading.get_ident():
        raise CampaignOwnerLifecycleError("mutation view cannot cross threads")
    state.context_token = _prove_context(
        probe=state.context_probe,
        token=state.context_token,
        label="mutation view",
    )


def _prove_scope_context(state: _ScopeState) -> None:
    state.context_proof_token = _prove_context(
        probe=state.context_probe,
        token=state.context_proof_token,
        label="Campaign owner scope",
    )


def _assert_no_active_scope() -> None:
    if _ACTIVE_SCOPE.get() is not None or getattr(_THREAD_SCOPE, "scope", None) is not None:
        raise CampaignOwnerReentrancyError(
            "public Campaign owner operation cannot run inside an owner scope"
        )


def _append_cleanup_context(primary: BaseException, cleanup: BaseException) -> None:
    tail = primary
    seen: set[int] = set()
    while tail.__cause__ is not None and id(tail) not in seen:
        seen.add(id(tail))
        tail = tail.__cause__
    if tail is cleanup:
        return
    try:
        tail.__cause__ = cleanup
    except BaseException:
        pass


def _raise_primary(
    primary: BaseException,
    traceback: Any,
    cleanup_errors: list[BaseException],
) -> None:
    for cleanup in cleanup_errors:
        if cleanup is not primary:
            _append_cleanup_context(primary, cleanup)
    raise primary.with_traceback(traceback)


class CampaignOwnerRegistry:
    """One immutable Campaign-local owner root bound to one database authority."""

    __slots__ = (
        "__weakref__",
        "_availability",
        "_branch_store",
        "_condition",
        "_database_authority",
        "_hypothesis_store",
        "_hypothesis_generation_components",
        "_hypothesis_generation_reservations",
        "_hypothesis_generation_states",
        "_initialized",
        "_owner_lock",
        "_owner_state",
        "_pending_restore_root",
        "_pending_restore_generation_holds",
        "_standalone_leases",
        "_startup_phase",
    )

    def __new__(
        cls,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> "CampaignOwnerRegistry":
        if type(database_authority) is not _sqlite.CampaignDatabaseAuthority:
            raise InvalidCampaignOwnerCapabilityError(
                "Registry requires an issued CampaignDatabaseAuthority"
            )
        database_key = _database_registry_key(database_authority)
        with _AUTHORITY_REGISTRIES_LOCK:
            prior_ref = _DATABASE_REGISTRIES.get(database_key)
            prior = None if prior_ref is None else prior_ref()
            if prior is not None:
                raise CampaignOwnerLifecycleError(
                    "Campaign database authority already has an owner Registry"
                )
            instance = object.__new__(cls)
            _DATABASE_REGISTRIES[database_key] = weakref.ref(instance)
            return instance

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        if getattr(self, "_initialized", False):
            raise CampaignOwnerLifecycleError(
                "CampaignOwnerRegistry cannot be initialized twice"
            )
        database_key = _database_registry_key(database_authority)
        with _AUTHORITY_REGISTRIES_LOCK:
            issued_ref = _DATABASE_REGISTRIES.get(database_key)
            if issued_ref is None or issued_ref() is not self:
                raise InvalidCampaignOwnerCapabilityError(
                    "CampaignOwnerRegistry was not issued for this authority"
                )
        self._initialized = True
        self._database_authority = database_authority
        self._branch_store = BranchStore(database_authority)
        self._hypothesis_store = HypothesisStore(database_authority)
        self._owner_lock = threading.Lock()
        self._condition = threading.Condition(self._owner_lock)
        self._startup_phase = _StartupPhase.OFFLINE_STANDALONE
        self._availability = _Availability.CLEAR
        self._standalone_leases: set[_StandaloneLease] = set()
        self._owner_state = _empty_owner_state()
        self._pending_restore_root: _CampaignOwnerState | None = None
        self._hypothesis_generation_components: (
            _HypothesisGenerationComponents | None
        ) = None
        self._hypothesis_generation_reservations: dict[
            str,
            _HypothesisGenerationReservation,
        ] = {}
        self._hypothesis_generation_states: dict[
            _generation.HypothesisGenerationView,
            _HypothesisGenerationState,
        ] = {}
        self._pending_restore_generation_holds: dict[
            str,
            _HypothesisGenerationReservation,
        ] | None = None

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("CampaignOwnerRegistry is sealed")

    def __copy__(self) -> "CampaignOwnerRegistry":
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerRegistry cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "CampaignOwnerRegistry":
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerRegistry cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidCampaignOwnerCapabilityError(
            "CampaignOwnerRegistry cannot be pickled"
        )

    def _install_hypothesis_generation_components(
        self,
        *,
        code_source_owner: HypothesisCodeSourceOwner,
        context_manager: ContextManager,
        prompt_owner: ProposalPromptProjectionAuthority,
        proposal_owner: ProposalAttemptOwner,
        provider_owner: ProviderCallOwner,
        registry_authority: _generation._AuthorityHandle,
        provider_authority: _generation._AuthorityHandle,
        runtime_mode: str,
        problem_id: str,
        problem_spec_hash: str,
        split_manifest_hash: str,
        seed_ledger_hash: str,
    ) -> None:
        """Install one immutable dormant checkpoint-A composition exactly once."""

        _assert_no_active_scope()
        if type(code_source_owner) is not HypothesisCodeSourceOwner:
            raise InvalidCampaignOwnerCapabilityError(
                "generation install requires the exact code-source owner"
            )
        if type(context_manager) is not ContextManager:
            raise InvalidCampaignOwnerCapabilityError(
                "generation install requires the exact ContextManager"
            )
        if type(prompt_owner) is not ProposalPromptProjectionAuthority:
            raise InvalidCampaignOwnerCapabilityError(
                "generation install requires the exact prompt owner"
            )
        if type(proposal_owner) is not ProposalAttemptOwner:
            raise InvalidCampaignOwnerCapabilityError(
                "generation install requires the exact proposal-attempt owner"
            )
        if type(provider_owner) is not ProviderCallOwner:
            raise InvalidCampaignOwnerCapabilityError(
                "generation install requires the exact provider owner"
            )
        registry_handle_state = _generation._require_authority(
            registry_authority,
            role=_generation._AuthorityRole.REGISTRY,
            owner=self,
        )
        provider_handle_state = _generation._require_authority(
            provider_authority,
            role=_generation._AuthorityRole.PROVIDER,
            owner=provider_owner,
        )
        del registry_handle_state, provider_handle_state
        component_handles = (
            code_source_owner._require_hypothesis_generation_authority(),
            context_manager._require_hypothesis_generation_authority(),
            prompt_owner._require_hypothesis_generation_authority(),
            proposal_owner._require_hypothesis_generation_authority(),
            provider_owner._require_hypothesis_generation_authority(),
        )
        if component_handles[-1] is not provider_authority:
            raise InvalidCampaignOwnerCapabilityError(
                "installed provider handle differs from Registry composition"
            )
        _generation._require_same_installation(
            registry_authority,
            provider_authority,
            *component_handles,
        )
        authority_state = _sqlite._lookup_authority_state(self._database_authority)
        mode = _required_owner_id(runtime_mode, label="runtime mode")
        if mode != "direct_v3":
            raise DurableOwnerIntegrityError(
                "hypothesis generation requires direct_v3 runtime mode"
            )
        components = _HypothesisGenerationComponents(
            code_source_owner=code_source_owner,
            context_manager=context_manager,
            prompt_owner=prompt_owner,
            proposal_owner=proposal_owner,
            provider_owner=provider_owner,
            registry_authority=registry_authority,
            provider_authority=provider_authority,
            campaign_id=_required_owner_id(
                authority_state.campaign_id,
                label="Campaign ID",
            ),
            runtime_mode=mode,
            problem_id=_required_owner_id(problem_id, label="problem ID"),
            problem_spec_hash=_required_digest(
                problem_spec_hash,
                label="problem-spec hash",
            ),
            split_manifest_hash=_required_digest(
                split_manifest_hash,
                label="split-manifest hash",
            ),
            seed_ledger_hash=_required_digest(
                seed_ledger_hash,
                label="seed-ledger hash",
            ),
        )
        with self._owner_lock:
            self._require_not_held_locked()
            if self._startup_phase is not _StartupPhase.OFFLINE_STANDALONE:
                raise CampaignOwnerLifecycleError(
                    "generation components must install before restore"
                )
            if self._hypothesis_generation_components is not None:
                raise CampaignOwnerLifecycleError(
                    "hypothesis generation components are already installed"
                )
            self._hypothesis_generation_components = components

    def begin_restore(self) -> LoadedRestoreAuthority:
        """Drain dormant standalone owners and load one complete invisible root."""

        _assert_no_active_scope()
        self._condition.acquire()
        transition_started = False
        try:
            self._require_not_held_locked()
            if self._startup_phase is not _StartupPhase.OFFLINE_STANDALONE:
                raise CampaignOwnerLifecycleError("restore has already begun")
            transition_started = True
            self._startup_phase = _StartupPhase.DRAINING_STANDALONE
            self._condition.wait_for(lambda: not self._standalone_leases)
            self._startup_phase = _StartupPhase.RESTORING
            attempt_inventory: _HypothesisAttemptInventory | None = None
            with _sqlite._independent_authority_read_snapshot(
                self._database_authority
            ) as snapshot:
                branches = (
                    self._branch_store._load_all_revisioned_branches_from_snapshot(
                        snapshot
                    )
                )
                hypotheses = (
                    self._hypothesis_store._load_all_revisioned_hypotheses_from_snapshot(
                        snapshot
                    )
                )
                components = self._hypothesis_generation_components
                if components is not None:
                    attempt_inventory = (
                        components.proposal_owner
                        ._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
                    )
            branch_tokens = {token.branch_id: token for token in branches}
            hypothesis_tokens = {token.hypothesis_id: token for token in hypotheses}
            if len(branch_tokens) != len(branches):
                raise DurableOwnerIntegrityError(
                    "complete Branch inventory contains duplicate owner IDs"
                )
            if len(hypothesis_tokens) != len(hypotheses):
                raise DurableOwnerIntegrityError(
                    "complete hypothesis inventory contains duplicate owner IDs"
                )
            prepared = _build_owner_state(
                branch_tokens,
                hypothesis_tokens,
                generation=0,
            )
            restore_holds = (
                {}
                if attempt_inventory is None
                else _restore_generation_holds(attempt_inventory, prepared)
            )
            self._pending_restore_root = prepared
            self._pending_restore_generation_holds = restore_holds
            authority = object.__new__(LoadedRestoreAuthority)
            probe, context_token = _new_context_proof()
            with _CAPABILITY_STATES_LOCK:
                _RESTORE_STATES[authority] = _RestoreState(
                    registry_ref=weakref.ref(self),
                    prepared_root=prepared,
                    thread_id=threading.get_ident(),
                    context_probe=probe,
                    context_token=context_token,
                )
            return authority
        except BaseException as exc:
            if transition_started:
                self._availability = _Availability.PERMANENT_HOLD
                self._pending_restore_root = None
                self._pending_restore_generation_holds = None
                if type(exc) is CampaignOwnerIntegrityHoldError:
                    raise
                raise CampaignOwnerIntegrityHoldError(
                    "complete Campaign owner restore failed"
                ) from exc
            raise
        finally:
            self._condition.release()

    def seal_live(self, authority: LoadedRestoreAuthority) -> None:
        """Publish the exact loaded restore root and permanently enable Registry use."""

        _assert_no_active_scope()
        self._owner_lock.acquire()
        restore_state: _RestoreState | None = None
        spent = False
        generation_holds_installed = False
        try:
            self._require_not_held_locked()
            if self._startup_phase is not _StartupPhase.RESTORING:
                raise CampaignOwnerLifecycleError("Registry is not restoring")
            restore_state = _lookup_restore_state(authority)
            if restore_state.registry_ref() is not self:
                raise InvalidCampaignOwnerCapabilityError(
                    "restore authority belongs to another Registry"
                )
            if restore_state.phase is not _RestorePhase.LOADED:
                raise CampaignOwnerLifecycleError("restore authority is spent")
            if restore_state.thread_id != threading.get_ident():
                raise CampaignOwnerLifecycleError(
                    "restore authority cannot cross threads"
                )
            restore_state.context_token = _prove_context(
                probe=restore_state.context_probe,
                token=restore_state.context_token,
                label="restore authority",
            )
            if self._pending_restore_root is not restore_state.prepared_root:
                self._availability = _Availability.PERMANENT_HOLD
                raise CampaignOwnerIntegrityHoldError(
                    "loaded restore root identity is no longer authoritative"
                )
            pending_generation_holds = self._pending_restore_generation_holds
            if pending_generation_holds is None:
                self._availability = _Availability.PERMANENT_HOLD
                raise CampaignOwnerIntegrityHoldError(
                    "loaded restore lost its generation-hold inventory"
                )

            # Arm fail-closed cleanup before the irreversible spend latch.
            spent = True
            restore_state.phase = _RestorePhase.SPENT
            self._owner_state = restore_state.prepared_root
            self._hypothesis_generation_reservations = dict(
                pending_generation_holds
            )
            generation_holds_installed = True
        finally:
            try:
                if spent and restore_state is not None:
                    if (
                        self._owner_state is restore_state.prepared_root
                        and generation_holds_installed
                    ):
                        self._pending_restore_root = None
                        self._pending_restore_generation_holds = None
                        self._availability = _Availability.CLEAR
                        self._startup_phase = _StartupPhase.LIVE_REGISTRY
                    else:
                        self._availability = _Availability.PERMANENT_HOLD
            finally:
                self._owner_lock.release()

    def branch_snapshot(self, branch_id: str) -> Branch:
        _assert_no_active_scope()
        owner_id = _required_owner_id(branch_id, label="Branch ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            slot = root.branch_slots.get(owner_id)
            if slot is None:
                raise OwnerNotFound(f"Branch owner does not exist: {owner_id}")
            return slot.owner.value()

    def branch_snapshots(self) -> tuple[Branch, ...]:
        _assert_no_active_scope()
        with self._owner_lock:
            root = self._capture_live_root_locked()
            return tuple(
                root.branch_slots[owner_id].owner.value()
                for owner_id in sorted(root.branch_slots)
            )

    def hypothesis_snapshot(self, hypothesis_id: str) -> HypothesisRecord:
        _assert_no_active_scope()
        owner_id = _required_owner_id(hypothesis_id, label="hypothesis ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            slot = root.hypothesis_slots.by_id.get(owner_id)
            if slot is None:
                raise OwnerNotFound(f"hypothesis owner does not exist: {owner_id}")
            return slot.owner.value()

    def hypothesis_snapshots(self) -> tuple[HypothesisRecord, ...]:
        _assert_no_active_scope()
        with self._owner_lock:
            root = self._capture_live_root_locked()
            return tuple(
                root.hypothesis_slots.by_id[owner_id].owner.value()
                for owner_id in sorted(root.hypothesis_slots.by_id)
            )

    def current_hypothesis_snapshot(
        self,
        branch_id: str,
    ) -> HypothesisRecord | None:
        _assert_no_active_scope()
        owner_id = _required_owner_id(branch_id, label="Branch ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            hypothesis_id = root.hypothesis_slots.current_by_branch.get(owner_id)
            if hypothesis_id is None:
                return None
            slot = root.hypothesis_slots.by_id.get(hypothesis_id)
            if slot is None:
                self._availability = _Availability.PERMANENT_HOLD
                raise CampaignOwnerIntegrityHoldError(
                    "current hypothesis index lost its owner slot"
                )
            return slot.owner.value()

    def _require_hypothesis_generation_components(
        self,
    ) -> _HypothesisGenerationComponents:
        components = self._hypothesis_generation_components
        if components is None:
            raise CampaignOwnerLifecycleError(
                "hypothesis generation components are not installed"
            )
        return components

    def _lookup_hypothesis_generation_state_locked(
        self,
        view: _generation.HypothesisGenerationView,
    ) -> _HypothesisGenerationState:
        if type(view) is not _generation.HypothesisGenerationView:
            raise InvalidCampaignOwnerCapabilityError(
                "operation requires an exact HypothesisGenerationView"
            )
        state = self._hypothesis_generation_states.get(view)
        if state is None or state.view is not view:
            raise InvalidCampaignOwnerCapabilityError(
                "hypothesis generation view was not issued by this Registry"
            )
        reservation = self._hypothesis_generation_reservations.get(
            state.branch_owner.branch_id
        )
        if reservation is not state.reservation:
            raise CampaignOwnerIntegrityHoldError(
                "hypothesis generation view lost its Branch reservation"
            )
        return state

    def _require_generation_root_current_locked(
        self,
        state: _HypothesisGenerationState,
    ) -> None:
        root = self._capture_live_root_locked()
        slot = root.branch_slots.get(state.branch_owner.branch_id)
        if (
            root is not state.root
            or root.publication_generation != state.root.publication_generation
            or slot is None
            or slot.owner != state.branch_owner
        ):
            raise CampaignOwnerLifecycleError(
                "hypothesis generation view belongs to a stale owner root"
            )

    def _require_generation_owners_current_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        state: _HypothesisGenerationState,
    ) -> None:
        durable_branch = self._branch_store.load_revisioned_in(
            transaction,
            state.branch_owner.branch_id,
        )
        if durable_branch != state.branch_owner:
            raise DurableOwnerIntegrityError(
                "generation START Branch differs from its captured owner"
            )
        durable_bundle = self._hypothesis_store._load_branch_hypotheses_in(
            transaction,
            state.branch_owner.branch_id,
        )
        expected_bundle = tuple(
            sorted(
                state.hypothesis_bundle,
                key=lambda token: token.hypothesis_id,
            )
        )
        if durable_bundle != expected_bundle:
            raise DurableOwnerIntegrityError(
                "generation START H bundle differs from its complete capture"
            )

    def _release_local_generation_locked(
        self,
        state: _HypothesisGenerationState,
    ) -> None:
        reservation = state.reservation
        if reservation.phase is not _GenerationReservationPhase.LOCAL:
            raise CampaignOwnerLifecycleError(
                "only a local generation reservation can be released"
            )
        current = self._hypothesis_generation_reservations.get(
            reservation.branch_id
        )
        if current is not reservation:
            self._availability = _Availability.PERMANENT_HOLD
            raise CampaignOwnerIntegrityHoldError(
                "local generation release lost its exact Branch reservation"
            )
        reservation.phase = _GenerationReservationPhase.RELEASED
        del self._hypothesis_generation_reservations[reservation.branch_id]
        self._hypothesis_generation_states.pop(state.view, None)

    def _hold_generation_reservation_locked(
        self,
        state: _HypothesisGenerationState,
    ) -> None:
        reservation = state.reservation
        current = self._hypothesis_generation_reservations.get(
            reservation.branch_id
        )
        if current is not reservation:
            self._availability = _Availability.PERMANENT_HOLD
            raise CampaignOwnerIntegrityHoldError(
                "generation hold lost its exact Branch reservation"
            )
        reservation.phase = _GenerationReservationPhase.UNCERTAIN_HOLD

    def _resolve_generation_reservation_locked(
        self,
        state: _HypothesisGenerationState,
    ) -> None:
        reservation = state.reservation
        current = self._hypothesis_generation_reservations.get(
            reservation.branch_id
        )
        if current is not reservation:
            self._availability = _Availability.PERMANENT_HOLD
            raise CampaignOwnerIntegrityHoldError(
                "terminal receipt lost its exact Branch reservation"
            )
        reservation.phase = _GenerationReservationPhase.RESOLVED
        del self._hypothesis_generation_reservations[reservation.branch_id]
        self._hypothesis_generation_states.pop(state.view, None)

    def _require_branch_generation_clear_locked(self, branch_id: str) -> None:
        reservation = self._hypothesis_generation_reservations.get(branch_id)
        if reservation is not None and reservation.phase not in {
            _GenerationReservationPhase.RELEASED,
            _GenerationReservationPhase.RESOLVED,
        }:
            if reservation.phase is _GenerationReservationPhase.UNCERTAIN_HOLD:
                raise HypothesisGenerationReservationHoldError(
                    "Branch has an unresolved hypothesis generation hold"
                )
            raise CampaignOwnerLifecycleError(
                "Branch has an active hypothesis generation reservation"
            )

    def _settle_provider_claim_unknown_locked(
        self,
        components: _HypothesisGenerationComponents,
        state: _HypothesisGenerationState,
    ) -> bool:
        if (
            state.reservation.phase
            is not _GenerationReservationPhase.DURABLE_OPEN
        ):
            return False
        if not _generation._settle_provider_claim_unknown(
            components.registry_authority,
            state.view,
        ):
            return False
        self._hold_generation_reservation_locked(state)
        return True

    def _settle_failed_start_claim_locked(
        self,
        components: _HypothesisGenerationComponents,
        state: _HypothesisGenerationState,
        cause: BaseException,
    ) -> None:
        cleanup_errors: list[BaseException] = []
        try:
            _generation._finish_start_without_authority(
                components.registry_authority,
                state.view,
                mixed=False,
            )
            self._release_local_generation_locked(state)
            return
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            _generation._spend_prestart_generation_view(
                components.registry_authority,
                state.view,
                rejected=False,
            )
            self._release_local_generation_locked(state)
            return
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            _generation._hold_generation_view(
                components.registry_authority,
                state.view,
            )
        except BaseException as error:
            cleanup_errors.append(error)
        self._hold_generation_reservation_locked(state)
        for error in cleanup_errors:
            _append_cleanup_context(cause, error)
        raise HypothesisGenerationReservationHoldError(
            "failed START claim could not prove a local release"
        ) from cause

    def settle_hypothesis_prompt_failure(
        self,
        view: _generation.HypothesisGenerationView,
    ) -> bool | None:
        """Release a LOCAL reservation only from the leaf's exact prompt state."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if state.reservation.phase is not _GenerationReservationPhase.LOCAL:
                return None
            disposition = _generation._settle_prompt_failure(
                components.registry_authority,
                view,
            )
            if disposition is not None:
                self._release_local_generation_locked(state)
            return disposition

    def acquire_hypothesis_generation(
        self,
        branch_id: str,
    ) -> _generation.HypothesisGenerationView:
        """Capture one exact immutable root and reserve its Branch locally."""

        _assert_no_active_scope()
        owner_id = _required_owner_id(branch_id, label="Branch ID")
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            root = self._capture_live_root_locked()
            existing = self._hypothesis_generation_reservations.get(owner_id)
            if (
                existing is not None
                and existing.phase is _GenerationReservationPhase.LOCAL
                and existing.view is not None
            ):
                disposition = _generation._settle_prompt_failure(
                    components.registry_authority,
                    existing.view,
                )
                if disposition is not None:
                    existing_state = self._hypothesis_generation_states.get(
                        existing.view
                    )
                    if existing_state is None:
                        raise CampaignOwnerIntegrityHoldError(
                            "local generation reservation lost its view state"
                        )
                    self._release_local_generation_locked(existing_state)
                    existing = None
            if (
                existing is not None
                and existing.phase is _GenerationReservationPhase.DURABLE_OPEN
                and existing.view is not None
            ):
                existing_state = self._hypothesis_generation_states.get(
                    existing.view
                )
                if existing_state is None:
                    raise CampaignOwnerIntegrityHoldError(
                        "durable generation reservation lost its view state"
                    )
                self._settle_provider_claim_unknown_locked(
                    components,
                    existing_state,
                )
            if existing is not None:
                if (
                    existing.phase
                    is _GenerationReservationPhase.UNCERTAIN_HOLD
                ):
                    raise HypothesisGenerationReservationHoldError(
                        "Branch has an unresolved hypothesis generation hold"
                    )
                raise CampaignOwnerLifecycleError(
                    "Branch already has a hypothesis generation reservation"
                )
            branch_slot = root.branch_slots.get(owner_id)
            if branch_slot is None:
                raise OwnerNotFound(f"Branch owner does not exist: {owner_id}")
            if owner_id in root.hypothesis_slots.current_by_branch:
                raise CampaignOwnerLifecycleError(
                    "Branch already has an active hypothesis owner"
                )
            bundle = tuple(
                slot.owner
                for slot in root.hypothesis_slots.by_id.values()
                if slot.projection.branch_id == owner_id
            )
            bundle = tuple(sorted(bundle, key=lambda token: token.hypothesis_id))
            prior_head = _prior_hypothesis_head(bundle)
            h_bundle_digest, h_bundle_items = _hypothesis_bundle_projection(
                owner_id,
                bundle,
            )
            reservation_id = str(uuid.uuid4())
            owner_context_json = _owner_context_json(
                components,
                root=root,
                branch_owner=branch_slot.owner,
                bundle=bundle,
                prior_head=prior_head,
                h_bundle_digest=h_bundle_digest,
                h_bundle_items=h_bundle_items,
            )
            view = _generation._issue_generation_view(
                components.registry_authority,
                root_identity=root,
                root_generation=root.publication_generation,
                branch_owner=branch_slot.owner,
                hypothesis_bundle=bundle,
                prior_head=prior_head,
                reservation_id=reservation_id,
                h_bundle_digest=h_bundle_digest,
                owner_context_json=owner_context_json,
            )
            reservation = _HypothesisGenerationReservation(
                branch_id=owner_id,
                reservation_id=reservation_id,
                phase=_GenerationReservationPhase.LOCAL,
                view=view,
            )
            state = _HypothesisGenerationState(
                view=view,
                reservation=reservation,
                root=root,
                branch_owner=branch_slot.owner,
                hypothesis_bundle=bundle,
                prior_head=prior_head,
            )
            self._hypothesis_generation_reservations[owner_id] = reservation
            self._hypothesis_generation_states[view] = state
            return view

    def _spend_prestart_generation(
        self,
        view: _generation.HypothesisGenerationView,
        *,
        rejected: bool,
    ) -> None:
        components = self._require_hypothesis_generation_components()
        _generation._spend_prestart_generation_view(
            components.registry_authority,
            view,
            rejected=rejected,
        )
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            self._release_local_generation_locked(state)

    def bind_hypothesis_code_source(
        self,
        view: _generation.HypothesisGenerationView,
    ) -> _generation.HypothesisCodeSource:
        """Invoke the exact configured code-source owner without caller inputs."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if state.reservation.phase is not _GenerationReservationPhase.LOCAL:
                raise CampaignOwnerLifecycleError(
                    "generation view has no local reservation"
                )
            request = _generation._issue_code_source_request(
                components.registry_authority,
                view,
            )
            try:
                self._require_generation_root_current_locked(state)
            except BaseException:
                _generation._spend_prestart_generation_view(
                    components.registry_authority,
                    view,
                    rejected=False,
                )
                self._release_local_generation_locked(state)
                raise
        try:
            with _sqlite._independent_authority_read_snapshot(
                self._database_authority
            ) as snapshot:
                source = (
                    components.code_source_owner
                    ._bind_hypothesis_code_source_from_snapshot(
                        snapshot,
                        request,
                    )
                )
        except HypothesisCodeSourceRejectedError:
            self._spend_prestart_generation(view, rejected=True)
            raise
        except HypothesisCodeSourceUnknownError:
            self._spend_prestart_generation(view, rejected=False)
            raise
        except BaseException:
            self._spend_prestart_generation(view, rejected=False)
            raise
        try:
            with self._owner_lock:
                state = self._lookup_hypothesis_generation_state_locked(view)
                self._require_generation_root_current_locked(state)
                _generation._inspect_code_source(
                    components.registry_authority,
                    source,
                    view=view,
                )
                state.code_source = source
        except BaseException:
            self._spend_prestart_generation(view, rejected=False)
            raise
        return source

    def issue_hypothesis_prompt_source(
        self,
        view: _generation.HypothesisGenerationView,
    ) -> _generation.HypothesisPromptSource:
        """Issue evidence and prompt source through the exact configured owners."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if state.reservation.phase is not _GenerationReservationPhase.LOCAL:
                raise CampaignOwnerLifecycleError(
                    "generation view has no local reservation"
                )
            source = state.code_source
            if source is None:
                raise CampaignOwnerLifecycleError(
                    "generation view has no bound code source"
                )
            try:
                self._require_generation_root_current_locked(state)
            except BaseException:
                _generation._spend_prestart_generation_view(
                    components.registry_authority,
                    view,
                    rejected=False,
                )
                self._release_local_generation_locked(state)
                raise
        try:
            evidence = components.context_manager._project_hypothesis_problem_evidence(
                source
            )
        except HypothesisProblemEvidenceRejectedError:
            self._spend_prestart_generation(view, rejected=True)
            raise
        except HypothesisProblemEvidenceUnknownError:
            self._spend_prestart_generation(view, rejected=False)
            raise
        except BaseException:
            self._spend_prestart_generation(view, rejected=False)
            raise
        try:
            with self._owner_lock:
                state = self._lookup_hypothesis_generation_state_locked(view)
                self._require_generation_root_current_locked(state)
                prompt_source = _generation._issue_prompt_source(
                    components.registry_authority,
                    view=view,
                    code_source=source,
                    evidence=evidence,
                )
                state.prompt_source = prompt_source
        except BaseException:
            self._spend_prestart_generation(view, rejected=False)
            raise
        return prompt_source

    def start_hypothesis_generation(
        self,
        view: _generation.HypothesisGenerationView,
        bound_prompt: _generation.BoundHypothesisPrompt,
        audit_metadata: Mapping[str, Any] | None = None,
    ) -> _generation.ProviderGenerationPermit:
        """Persist and independently classify START before issuing a permit."""

        _assert_no_active_scope()
        if audit_metadata is not None:
            if type(audit_metadata) is not dict:
                raise TypeError("START audit_metadata must be an exact dict or None")
            _canonical_json_bytes(audit_metadata, label="START audit metadata")
        components = self._require_hypothesis_generation_components()
        transaction_error: BaseException | None = None
        transaction_traceback: Any = None
        classification_error: BaseException | None = None
        stored: StoredProposalAttemptEvent | None = None
        classification = ProposalAttemptCommitClassification.MIXED
        started: _generation.StartedHypothesisAttempt | None = None

        self._owner_lock.acquire()
        transition_started = False
        try:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if state.reservation.phase is not _GenerationReservationPhase.LOCAL:
                raise CampaignOwnerLifecycleError(
                    "generation START requires a local Branch reservation"
                )
            try:
                self._require_generation_root_current_locked(state)
            except BaseException:
                _generation._spend_prestart_generation_view(
                    components.registry_authority,
                    view,
                    rejected=False,
                )
                self._release_local_generation_locked(state)
                raise
            try:
                _generation._inspect_bound_prompt(
                    components.registry_authority,
                    bound_prompt,
                    view=view,
                )
                state.bound_prompt = bound_prompt
                _generation._begin_started_attempt(
                    components.registry_authority,
                    view,
                    bound_prompt,
                )
            except BaseException as error:
                self._settle_failed_start_claim_locked(
                    components,
                    state,
                    error,
                )
                raise

            self._availability = _Availability.TRANSITION
            transition_started = True
            try:
                with _sqlite.immediate_transaction(
                    self._database_authority
                ) as transaction:
                    self._require_generation_owners_current_in(
                        transaction,
                        state,
                    )
                    stored = (
                        components.proposal_owner
                        .append_started_hypothesis_attempt_in(
                            transaction,
                            bound_prompt,
                        )
                    )
                    state.pending_start = stored
            except BaseException as error:
                transaction_error = error
                transaction_traceback = error.__traceback__

            try:
                with _sqlite._independent_authority_read_snapshot(
                    self._database_authority
                ) as snapshot:
                    if stored is not None:
                        classification, started = (
                            components.proposal_owner
                            ._classify_started_attempt_from_snapshot(
                                snapshot,
                                expected=stored,
                            )
                        )
                    else:
                        inventory = (
                            components.proposal_owner
                            ._load_hypothesis_attempt_inventory_from_snapshot(
                                snapshot
                            )
                        )
                        classification = (
                            ProposalAttemptCommitClassification.EXPECTED
                            if inventory.branch_is_clear(
                                state.branch_owner.branch_id
                            )
                            else ProposalAttemptCommitClassification.MIXED
                        )
            except BaseException as error:
                classification_error = error
                classification = ProposalAttemptCommitClassification.MIXED

            if classification is ProposalAttemptCommitClassification.EXPECTED:
                try:
                    _generation._finish_start_without_authority(
                        components.registry_authority,
                        view,
                        mixed=False,
                    )
                    self._release_local_generation_locked(state)
                except BaseException as error:
                    classification_error = classification_error or error
                    self._hold_generation_reservation_locked(state)
                    raise HypothesisGenerationReservationHoldError(
                        "rolled-back START could not release its Branch reservation"
                    ) from classification_error
                if transaction_error is not None:
                    raise transaction_error.with_traceback(transaction_traceback)
                raise CampaignOwnerLifecycleError(
                    "hypothesis START was not durably committed"
                )

            if (
                classification is ProposalAttemptCommitClassification.COMMITTED
                and started is not None
            ):
                try:
                    _generation._inspect_started_attempt(
                        components.registry_authority,
                        started,
                        view=view,
                    )
                    permit = _generation._issue_provider_permit(
                        components.registry_authority,
                        components.provider_authority,
                        view=view,
                        started_attempt=started,
                        bound_prompt=bound_prompt,
                    )
                    state.started_attempt = started
                    state.permit = permit
                    state.reservation.phase = (
                        _GenerationReservationPhase.DURABLE_OPEN
                    )
                    return permit
                except BaseException as error:
                    classification_error = classification_error or error

            try:
                if started is None:
                    try:
                        _generation._finish_start_without_authority(
                            components.registry_authority,
                            view,
                            mixed=True,
                        )
                    except BaseException:
                        _generation._hold_generation_view(
                            components.registry_authority,
                            view,
                        )
                else:
                    _generation._hold_generation_view(
                        components.registry_authority,
                        view,
                    )
            except BaseException as error:
                classification_error = classification_error or error
            self._hold_generation_reservation_locked(state)
            hold_error = HypothesisGenerationReservationHoldError(
                "hypothesis START classification is uncertain or mixed"
            )
            cause = classification_error or transaction_error
            if cause is not None:
                raise hold_error from cause
            raise hold_error
        finally:
            if transition_started and self._availability is _Availability.TRANSITION:
                self._availability = _Availability.CLEAR
            self._owner_lock.release()

    def observe_hypothesis_generation_outcome(
        self,
        view: _generation.HypothesisGenerationView,
        outcome: _generation.GeneratedHypothesisResult
        | _generation.FailedHypothesisGeneration,
    ) -> None:
        """Bind one exact externally produced provider outcome to its view."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if (
                state.reservation.phase
                is not _GenerationReservationPhase.DURABLE_OPEN
                or state.permit is None
            ):
                raise CampaignOwnerLifecycleError(
                    "generation view has no open durable provider permit"
                )
            if self._settle_provider_claim_unknown_locked(components, state):
                raise HypothesisGenerationReservationHoldError(
                    "provider claim outcome is unknown for this Branch"
                )
            _generation._inspect_generation_outcome(
                components.registry_authority,
                permit=state.permit,
                outcome=outcome,
                view=view,
            )
            state.outcome = outcome
            if type(outcome) is _generation.FailedHypothesisGeneration:
                state.reservation.phase = (
                    _GenerationReservationPhase.OUTCOME_BOUND
                )

    def abort_hypothesis_generation(
        self,
        view: _generation.HypothesisGenerationView,
    ) -> _generation.AbortedHypothesisGeneration | None:
        """Release pre-START work or bind one exact durable pre-claim abort."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        with self._owner_lock:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if state.reservation.phase is _GenerationReservationPhase.LOCAL:
                _generation._abort_prestart_generation_view(
                    components.registry_authority,
                    view,
                )
                self._release_local_generation_locked(state)
                return None
            if (
                state.reservation.phase
                is not _GenerationReservationPhase.DURABLE_OPEN
                or state.started_attempt is None
                or state.bound_prompt is None
            ):
                raise CampaignOwnerLifecycleError(
                    "generation view is not abortable after durable START"
                )
            if self._settle_provider_claim_unknown_locked(components, state):
                raise HypothesisGenerationReservationHoldError(
                    "provider claim outcome is unknown for this Branch"
                )
            outcome = _generation._issue_aborted_generation(
                components.registry_authority,
                started_attempt=state.started_attempt,
                bound_prompt=state.bound_prompt,
                view=view,
                permit=state.permit,
            )
            state.outcome = outcome
            state.reservation.phase = _GenerationReservationPhase.OUTCOME_BOUND
            return outcome

    def terminalize_hypothesis_generation(
        self,
        view: _generation.HypothesisGenerationView,
        outcome: _generation.FailedHypothesisGeneration
        | _generation.AbortedHypothesisGeneration,
    ) -> _generation.TerminalAttemptReceipt:
        """Persist one exact terminal outcome and resolve only a committed receipt."""

        _assert_no_active_scope()
        components = self._require_hypothesis_generation_components()
        transaction_error: BaseException | None = None
        classification_error: BaseException | None = None
        classification = ProposalAttemptCommitClassification.MIXED
        receipt: _generation.TerminalAttemptReceipt | None = None

        self._owner_lock.acquire()
        transition_started = False
        try:
            state = self._lookup_hypothesis_generation_state_locked(view)
            if (
                state.reservation.phase
                is not _GenerationReservationPhase.OUTCOME_BOUND
                or state.outcome is not outcome
                or state.started_attempt is None
                or state.bound_prompt is None
            ):
                raise CampaignOwnerLifecycleError(
                    "generation view has no exact terminal outcome to persist"
                )
            try:
                _generation._begin_terminal_persistence(
                    components.registry_authority,
                    view,
                    outcome,
                )
            except BaseException as error:
                try:
                    _generation._hold_generation_view(
                        components.registry_authority,
                        view,
                    )
                except BaseException as cleanup:
                    _append_cleanup_context(error, cleanup)
                self._hold_generation_reservation_locked(state)
                raise HypothesisGenerationReservationHoldError(
                    "terminal claim failed after its durable outcome was bound"
                ) from error
            self._availability = _Availability.TRANSITION
            transition_started = True
            try:
                with _sqlite.immediate_transaction(
                    self._database_authority
                ) as transaction:
                    components.proposal_owner.append_terminal_hypothesis_attempt_in(
                        transaction,
                        started=state.started_attempt,
                        bound_prompt=state.bound_prompt,
                        outcome=outcome,
                    )
            except BaseException as error:
                transaction_error = error

            try:
                with _sqlite._independent_authority_read_snapshot(
                    self._database_authority
                ) as snapshot:
                    classification, receipt = (
                        components.proposal_owner
                        ._classify_terminal_attempt_from_snapshot(
                            snapshot,
                            outcome=outcome,
                        )
                    )
            except BaseException as error:
                classification_error = error
                classification = ProposalAttemptCommitClassification.MIXED

            if (
                classification is ProposalAttemptCommitClassification.COMMITTED
                and receipt is not None
            ):
                try:
                    _generation._resolve_terminal_receipt(
                        components.registry_authority,
                        receipt,
                        started_attempt=state.started_attempt,
                        view=view,
                    )
                    self._resolve_generation_reservation_locked(state)
                    return receipt
                except BaseException as error:
                    classification_error = classification_error or error

            try:
                _generation._hold_generation_view(
                    components.registry_authority,
                    view,
                )
            except BaseException as error:
                classification_error = classification_error or error
            self._hold_generation_reservation_locked(state)
            hold_error = HypothesisGenerationReservationHoldError(
                "hypothesis terminal classification is not strictly committed"
            )
            cause = classification_error or transaction_error
            if cause is not None:
                raise hold_error from cause
            raise hold_error
        finally:
            if transition_started and self._availability is _Availability.TRANSITION:
                self._availability = _Availability.CLEAR
            self._owner_lock.release()

    def acquire_branch_mutation(self, branch_id: str) -> BranchMutationView:
        _assert_no_active_scope()
        owner_id = _required_owner_id(branch_id, label="Branch ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            self._require_branch_generation_clear_locked(owner_id)
            slot = root.branch_slots.get(owner_id)
            if slot is None:
                raise OwnerNotFound(f"Branch owner does not exist: {owner_id}")
            view = object.__new__(BranchMutationView)
            probe, context_token = _new_context_proof()
            with _CAPABILITY_STATES_LOCK:
                _VIEW_STATES[view] = _ViewState(
                    registry_ref=weakref.ref(self),
                    kind=_ViewKind.BRANCH,
                    owner=slot.owner,
                    target=slot.owner.value(),
                    generation=root.publication_generation,
                    thread_id=threading.get_ident(),
                    context_probe=probe,
                    context_token=context_token,
                )
            return view

    def acquire_hypothesis_mutation(
        self,
        hypothesis_id: str,
    ) -> HypothesisMutationView:
        _assert_no_active_scope()
        owner_id = _required_owner_id(hypothesis_id, label="hypothesis ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            slot = root.hypothesis_slots.by_id.get(owner_id)
            if slot is None:
                raise OwnerNotFound(f"hypothesis owner does not exist: {owner_id}")
            self._require_branch_generation_clear_locked(
                slot.projection.branch_id
            )
            view = object.__new__(HypothesisMutationView)
            probe, context_token = _new_context_proof()
            with _CAPABILITY_STATES_LOCK:
                _VIEW_STATES[view] = _ViewState(
                    registry_ref=weakref.ref(self),
                    kind=_ViewKind.HYPOTHESIS,
                    owner=slot.owner,
                    target=slot.owner.value(),
                    generation=root.publication_generation,
                    thread_id=threading.get_ident(),
                    context_probe=probe,
                    context_token=context_token,
                )
            return view

    def owner_transaction(
        self,
        *,
        branch_views: tuple[BranchMutationView, ...] = (),
        hypothesis_views: tuple[HypothesisMutationView, ...] = (),
    ) -> _OwnerTransactionContext:
        if type(branch_views) is not tuple or type(hypothesis_views) is not tuple:
            raise TypeError("owner transaction view collections must be exact tuples")
        if any(type(view) is not BranchMutationView for view in branch_views):
            raise InvalidCampaignOwnerCapabilityError(
                "branch_views contains another capability kind"
            )
        if any(
            type(view) is not HypothesisMutationView
            for view in hypothesis_views
        ):
            raise InvalidCampaignOwnerCapabilityError(
                "hypothesis_views contains another capability kind"
            )
        requested: tuple[_MutationView, ...] = (*branch_views, *hypothesis_views)
        if not requested:
            raise CampaignOwnerLifecycleError(
                "owner transaction requires at least one mutation view"
            )
        return _OwnerTransactionContext(self, requested)

    def refresh_branch_from_durable(self, branch_id: str) -> Branch:
        _assert_no_active_scope()
        owner_id = _required_owner_id(branch_id, label="Branch ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            self._require_branch_generation_clear_locked(owner_id)
            self._availability = _Availability.TRANSITION
            prepared: _CampaignOwnerState | None = None
            try:
                local = root.branch_slots.get(owner_id)
                with _sqlite._independent_authority_read_snapshot(
                    self._database_authority
                ) as snapshot:
                    durable = self._branch_store._load_revisioned_branch_from_snapshot(
                        snapshot,
                        owner_id,
                    )
                if local is None or durable is None:
                    raise DurableOwnerIntegrityError(
                        "Branch durable refresh found incomplete owner inventory"
                    )
                if not self._compare_refresh_token(local.owner, durable):
                    self._availability = _Availability.CLEAR
                    return local.owner.value()
                branch_tokens = _root_branch_tokens(root)
                branch_tokens[owner_id] = durable
                prepared = _build_owner_state(
                    branch_tokens,
                    _root_hypothesis_tokens(root),
                    generation=root.publication_generation + 1,
                )
                self._owner_state = prepared
                self._spend_stale_issued_views_locked(root)
            except BaseException as exc:
                if prepared is not None and self._owner_state is prepared:
                    self._availability = _Availability.CLEAR
                    raise CampaignOwnerCleanupError(
                        "Branch durable refresh published but cleanup failed"
                    ) from exc
                self._availability = _Availability.PERMANENT_HOLD
                if type(exc) is CampaignOwnerIntegrityHoldError:
                    raise
                raise CampaignOwnerIntegrityHoldError(
                    "Branch durable refresh failed before publication"
                ) from exc
            finally:
                if prepared is not None and self._owner_state is prepared:
                    self._availability = _Availability.CLEAR
            return durable.value()

    def refresh_hypothesis_from_durable(
        self,
        hypothesis_id: str,
    ) -> HypothesisRecord:
        _assert_no_active_scope()
        owner_id = _required_owner_id(hypothesis_id, label="hypothesis ID")
        with self._owner_lock:
            root = self._capture_live_root_locked()
            local = root.hypothesis_slots.by_id.get(owner_id)
            if local is None:
                raise DurableOwnerIntegrityError(
                    "hypothesis durable refresh found an absent local owner"
                )
            affected_branch = local.projection.branch_id
            self._require_branch_generation_clear_locked(affected_branch)
            self._availability = _Availability.TRANSITION
            prepared: _CampaignOwnerState | None = None
            try:
                with _sqlite._independent_authority_read_snapshot(
                    self._database_authority
                ) as snapshot:
                    durable_owner = (
                        self._hypothesis_store._load_revisioned_hypothesis_from_snapshot(
                            snapshot,
                            owner_id,
                        )
                    )
                    durable_bundle = (
                        self._hypothesis_store._load_branch_hypotheses_from_snapshot(
                            snapshot,
                            affected_branch,
                        )
                    )
                if (
                    durable_owner is None
                    or durable_owner.value().branch_id != affected_branch
                ):
                    raise DurableOwnerIntegrityError(
                        "hypothesis durable refresh moved or lost its owner"
                    )
                bundle = {token.hypothesis_id: token for token in durable_bundle}
                if len(bundle) != len(durable_bundle):
                    raise DurableOwnerIntegrityError(
                        "hypothesis durable bundle contains duplicate owner IDs"
                    )
                local_bundle = {
                    existing_id: slot
                    for existing_id, slot in root.hypothesis_slots.by_id.items()
                    if slot.projection.branch_id == affected_branch
                }
                if set(local_bundle) - set(bundle):
                    raise DurableOwnerIntegrityError(
                        "hypothesis durable bundle is missing a local owner"
                    )
                hypothesis_tokens = _root_hypothesis_tokens(root)
                changed = False
                for existing_id, durable in bundle.items():
                    if durable.value().branch_id != affected_branch:
                        raise DurableOwnerIntegrityError(
                            "hypothesis durable bundle contains another Branch"
                        )
                    local_slot = root.hypothesis_slots.by_id.get(existing_id)
                    if local_slot is None:
                        raise DurableOwnerIntegrityError(
                            "hypothesis durable bundle contains an absent local owner"
                        )
                    if self._compare_refresh_token(local_slot.owner, durable):
                        hypothesis_tokens[existing_id] = durable
                        changed = True
                if not changed:
                    self._availability = _Availability.CLEAR
                    return local.owner.value()
                prepared = _build_owner_state(
                    _root_branch_tokens(root),
                    hypothesis_tokens,
                    generation=root.publication_generation + 1,
                )
                self._owner_state = prepared
                self._spend_stale_issued_views_locked(root)
            except BaseException as exc:
                if prepared is not None and self._owner_state is prepared:
                    self._availability = _Availability.CLEAR
                    raise CampaignOwnerCleanupError(
                        "hypothesis durable refresh published but cleanup failed"
                    ) from exc
                self._availability = _Availability.PERMANENT_HOLD
                if type(exc) is CampaignOwnerIntegrityHoldError:
                    raise
                raise CampaignOwnerIntegrityHoldError(
                    "hypothesis durable refresh failed before publication"
                ) from exc
            finally:
                if prepared is not None and self._owner_state is prepared:
                    self._availability = _Availability.CLEAR
            refreshed = prepared.hypothesis_slots.by_id[owner_id].owner
            return refreshed.value()

    def _capture_live_root_locked(self) -> _CampaignOwnerState:
        self._require_not_held_locked()
        if self._startup_phase is not _StartupPhase.LIVE_REGISTRY:
            raise CampaignOwnerLifecycleError("Campaign owner Registry is not live")
        if self._availability is not _Availability.CLEAR:
            raise CampaignOwnerLifecycleError("Campaign owner Registry is transitioning")
        return self._owner_state

    def _require_not_held_locked(self) -> None:
        if self._availability is _Availability.PERMANENT_HOLD:
            raise CampaignOwnerIntegrityHoldError(
                "Campaign owner Registry is in a permanent integrity hold"
            )

    def _compare_refresh_token(
        self,
        local: _OwnerToken,
        durable: _OwnerToken,
    ) -> bool:
        if type(local) is not type(durable):
            self._availability = _Availability.PERMANENT_HOLD
            raise CampaignOwnerIntegrityHoldError(
                "durable refresh changed the owner kind"
            )
        if local.owner_revision > durable.owner_revision:
            return False
        if local.owner_revision == durable.owner_revision:
            if local != durable:
                self._availability = _Availability.PERMANENT_HOLD
                raise CampaignOwnerIntegrityHoldError(
                    "durable owner bytes drifted at an equal revision"
                )
            return False
        return True

    def _spend_stale_issued_views_locked(self, old_root: _CampaignOwnerState) -> None:
        with _CAPABILITY_STATES_LOCK:
            for state in tuple(_VIEW_STATES.values()):
                if (
                    state.registry_ref() is self
                    and state.phase is _CapabilityPhase.ISSUED
                    and state.generation <= old_root.publication_generation
                ):
                    state.phase = _CapabilityPhase.SPENT


def _acquire_standalone_lease(
    registry: CampaignOwnerRegistry,
) -> _StandaloneLease:
    """Private future-wrapper seam; currently has zero production importers."""

    if type(registry) is not CampaignOwnerRegistry:
        raise InvalidCampaignOwnerCapabilityError(
            "standalone lease requires an exact CampaignOwnerRegistry"
        )
    _assert_no_active_scope()
    with registry._condition:
        registry._require_not_held_locked()
        if registry._startup_phase is not _StartupPhase.OFFLINE_STANDALONE:
            raise CampaignOwnerLifecycleError(
                "standalone owner authority has been permanently revoked"
            )
        lease = object.__new__(_StandaloneLease)
        state = _StandaloneLeaseState(
            registry_ref=weakref.ref(registry),
            thread_id=threading.get_ident(),
        )
        registered = False
        try:
            with _CAPABILITY_STATES_LOCK:
                _STANDALONE_LEASE_STATES[lease] = state
            registered = True
            registry._standalone_leases.add(lease)
            return lease
        except BaseException:
            state.active = False
            registry._standalone_leases.discard(lease)
            if registered:
                with _CAPABILITY_STATES_LOCK:
                    _STANDALONE_LEASE_STATES.pop(lease, None)
            registry._condition.notify_all()
            raise


def _release_standalone_lease(lease: _StandaloneLease) -> None:
    """Release one lease only after its future transaction connection closes."""

    if type(lease) is not _StandaloneLease:
        raise InvalidCampaignOwnerCapabilityError(
            "operation requires an issued standalone lease"
        )
    with _CAPABILITY_STATES_LOCK:
        state = _STANDALONE_LEASE_STATES.get(lease)
    if state is None:
        raise InvalidCampaignOwnerCapabilityError("standalone lease was not issued")
    registry = state.registry_ref()
    if registry is None:
        raise CampaignOwnerLifecycleError("standalone lease Registry disappeared")
    if state.thread_id != threading.get_ident():
        raise CampaignOwnerLifecycleError("standalone lease cannot cross threads")
    with registry._condition:
        if not state.active:
            raise CampaignOwnerLifecycleError("standalone lease is already released")
        try:
            registry._standalone_leases.discard(lease)
        finally:
            try:
                registry._standalone_leases.discard(lease)
            finally:
                try:
                    state.active = False
                finally:
                    registry._condition.notify_all()


class _OwnerTransactionContext:
    __slots__ = ("_entered", "_registry", "_requested", "_scope")

    def __init__(
        self,
        registry: CampaignOwnerRegistry,
        requested: tuple[_MutationView, ...],
    ) -> None:
        self._registry = registry
        self._requested = requested
        self._scope: CampaignOwnerTransactionScope | None = None
        self._entered = False

    def __enter__(self) -> CampaignOwnerTransactionScope:
        if self._entered:
            raise CampaignOwnerLifecycleError(
                "Campaign owner transaction context cannot be re-entered"
            )
        scope = _enter_owner_scope(self._registry, self._requested)
        self._scope = scope
        self._entered = True
        return scope

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None:
        scope = self._scope
        if not self._entered or scope is None:
            raise CampaignOwnerLifecycleError(
                "Campaign owner transaction context is not active"
            )
        state = _require_active_scope(scope)
        try:
            if (exc_type is None) != (exc_value is None):
                protocol_error = CampaignOwnerLifecycleError(
                    "owner transaction exit received inconsistent exception state"
                )
                _exit_owner_scope(
                    state,
                    protocol_error,
                    protocol_error.__traceback__,
                )
            _exit_owner_scope(state, exc_value, traceback)
        finally:
            self._entered = False
        return None


def _validate_requested_views_locked(
    registry: CampaignOwnerRegistry,
    root: _CampaignOwnerState,
    requested: tuple[_MutationView, ...],
) -> tuple[_ViewState, ...]:
    if any(
        type(view) not in {BranchMutationView, HypothesisMutationView}
        for view in requested
    ):
        raise InvalidCampaignOwnerCapabilityError(
            "owner transaction contains a forged mutation view"
        )
    if len({id(view) for view in requested}) != len(requested):
        raise CampaignOwnerLifecycleError("owner transaction contains duplicate views")
    seen: set[tuple[_ViewKind, str]] = set()
    states: list[_ViewState] = []
    for view in requested:
        state = _lookup_view_state(view)
        if state.registry_ref() is not registry:
            raise InvalidCampaignOwnerCapabilityError(
                "mutation view belongs to another Registry"
            )
        if state.phase is not _CapabilityPhase.ISSUED:
            raise CampaignOwnerLifecycleError("mutation view is not issued")
        _prove_view_context(state)
        if state.generation != root.publication_generation:
            raise CampaignOwnerLifecycleError("mutation view belongs to a stale root")
        if state.kind is _ViewKind.BRANCH:
            if type(state.owner) is not RevisionedBranchRecord:
                raise InvalidCampaignOwnerCapabilityError(
                    "Branch mutation view contains another owner kind"
                )
            slot = root.branch_slots.get(state.owner.branch_id)
            owner_id = state.owner.branch_id
            affected_branch_id = owner_id
        else:
            if type(state.owner) is not RevisionedHypothesisRecord:
                raise InvalidCampaignOwnerCapabilityError(
                    "hypothesis mutation view contains another owner kind"
                )
            slot = root.hypothesis_slots.by_id.get(state.owner.hypothesis_id)
            owner_id = state.owner.hypothesis_id
            affected_branch_id = state.owner.value().branch_id
        if slot is None or slot.owner != state.owner:
            raise CampaignOwnerLifecycleError("mutation view owner is no longer current")
        registry._require_branch_generation_clear_locked(affected_branch_id)
        identity = (state.kind, owner_id)
        if identity in seen:
            raise CampaignOwnerLifecycleError(
                "owner transaction contains duplicate owner identities"
            )
        seen.add(identity)
        states.append(state)
    return tuple(states)


def _enter_owner_scope(
    registry: CampaignOwnerRegistry,
    requested: tuple[_MutationView, ...],
) -> CampaignOwnerTransactionScope:
    _assert_no_active_scope()
    registry._owner_lock.acquire()
    guard_raised = False
    open_attempted = False
    view_states: tuple[_ViewState, ...] = ()
    session: _sqlite._CoordinatedTransactionSession | None = None
    ledger: _owner._OwnerReceiptLedger | None = None
    scope: CampaignOwnerTransactionScope | None = None
    context_token: contextvars.Token[CampaignOwnerTransactionScope | None] | None = None
    proof_probe: contextvars.ContextVar[object | None] | None = None
    proof_token: contextvars.Token[object | None] | None = None
    try:
        if _sqlite._thread_session_owner() is not None:
            raise CampaignOwnerReentrancyError(
                "owner transaction cannot nest another SQLite transaction"
            )
        root = registry._capture_live_root_locked()
        # The exact cleanup set exists before the claim latch.
        view_states = _validate_requested_views_locked(registry, root, requested)
        registry._availability = _Availability.TRANSITION
        guard_raised = True
        for state in view_states:
            state.phase = _CapabilityPhase.CLAIMED

        open_attempted = True
        session = _sqlite._open_coordinated_transaction_session(
            registry._database_authority
        )
        transaction = _sqlite._coordinated_transaction(
            session,
            registry._database_authority,
        )
        ledger = _owner._attach_owner_receipt_ledger(
            transaction,
            registry._database_authority,
        )
        scope = object.__new__(CampaignOwnerTransactionScope)
        proof_probe, proof_token = _new_context_proof()
        context_token = _ACTIVE_SCOPE.set(scope)
        _THREAD_SCOPE.scope = scope
        state = _ScopeState(
            registry=registry,
            scope=scope,
            session=session,
            transaction=transaction,
            ledger=ledger,
            requested_views=requested,
            requested_view_states=view_states,
            old_root=root,
            thread_id=threading.get_ident(),
            context_token=context_token,
            context_probe=proof_probe,
            context_proof_token=proof_token,
            staged_tokens={},
            staged_receipts={},
            staged_witnesses={},
        )
        with _CAPABILITY_STATES_LOCK:
            _SCOPE_STATES[scope] = state
        return scope
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_errors: list[BaseException] = []
        if session is None and open_attempted:
            try:
                recovered_session = _sqlite._thread_session_owner()
                if type(recovered_session) is _sqlite._CoordinatedTransactionSession:
                    recovered_state = _sqlite._lookup_session_state(recovered_session)
                    if recovered_state.authority is registry._database_authority:
                        session = recovered_session
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
        safe_old_root = session is None and _sqlite._thread_session_owner() is None
        views_spent_complete = False
        try:
            if ledger is not None:
                try:
                    _owner._close_owner_receipt_ledger(
                        ledger,
                        registry._database_authority,
                    )
                except BaseException as cleanup:
                    cleanup_errors.append(cleanup)
            if session is not None:
                for _attempt in range(2):
                    try:
                        _sqlite._deactivate_coordinated_transaction(
                            session,
                            registry._database_authority,
                        )
                        break
                    except BaseException as cleanup:
                        cleanup_errors.append(cleanup)
                try:
                    session_state = _sqlite._lookup_session_state(session)
                    deactivation_complete = _sqlite._session_deactivation_complete(
                        session_state
                    )
                except BaseException as cleanup:
                    cleanup_errors.append(cleanup)
                    deactivation_complete = False
                if deactivation_complete:
                    try:
                        settlement = (
                            _sqlite._settle_deactivated_original_connection(
                                session,
                                registry._database_authority,
                            )
                        )
                        safe_old_root = (
                            settlement
                            is _sqlite._OriginalConnectionSettlement.ROLLED_BACK
                        )
                    except BaseException as cleanup:
                        cleanup_errors.append(cleanup)
        except BaseException as cleanup:
            cleanup_errors.append(cleanup)
        finally:
            try:
                try:
                    for view_state in view_states:
                        view_state.phase = _CapabilityPhase.SPENT
                    views_spent_complete = True
                except BaseException as cleanup:
                    cleanup_errors.append(cleanup)
                if guard_raised:
                    registry._availability = (
                        _Availability.CLEAR
                        if safe_old_root and views_spent_complete
                        else _Availability.PERMANENT_HOLD
                    )
                if context_token is not None and scope is not None:
                    try:
                        if _ACTIVE_SCOPE.get() is scope:
                            _ACTIVE_SCOPE.reset(context_token)
                    except BaseException as cleanup:
                        cleanup_errors.append(cleanup)
                if proof_probe is not None and proof_token is not None:
                    try:
                        proof_probe.reset(proof_token)
                    except BaseException as cleanup:
                        cleanup_errors.append(cleanup)
                if getattr(_THREAD_SCOPE, "scope", None) is scope:
                    _THREAD_SCOPE.scope = None
            finally:
                registry._owner_lock.release()
        _raise_primary(primary, traceback, cleanup_errors)


def _compare_and_stage_branch(
    state: _ScopeState,
    view: BranchMutationView,
) -> None:
    view_state = _lookup_view_state(view, expected_kind=_ViewKind.BRANCH)
    _require_claimed_scope_view(state, view, view_state)
    if (
        type(view_state.owner) is not RevisionedBranchRecord
        or type(view_state.target) is not Branch
    ):
        raise InvalidCampaignOwnerCapabilityError(
            "Branch mutation view contains malformed staged values"
        )
    receipt = state.registry._branch_store.compare_and_swap_in(
        state.transaction,
        view_state.owner,
        view_state.target,
    )
    witness = _owner._consume_branch_mutation_receipt(state.ledger, receipt)
    committed = witness.committed_token
    if (
        witness.expected_token is not view_state.owner
        or type(committed) is not RevisionedBranchRecord
        or committed.branch_id != view_state.owner.branch_id
        or committed.owner_revision != view_state.owner.owner_revision + 1
        or committed
        != RevisionedBranchRecord.from_value(
            view_state.target,
            committed.owner_revision,
        )
    ):
        raise DurableOwnerIntegrityError(
            "Branch receipt does not match its exact claimed mutation view"
        )
    state.staged_tokens[view] = committed
    state.staged_receipts[view] = receipt
    state.staged_witnesses[view] = witness


def _compare_and_stage_hypothesis(
    state: _ScopeState,
    view: HypothesisMutationView,
) -> None:
    view_state = _lookup_view_state(view, expected_kind=_ViewKind.HYPOTHESIS)
    _require_claimed_scope_view(state, view, view_state)
    if (
        type(view_state.owner) is not RevisionedHypothesisRecord
        or type(view_state.target) is not HypothesisRecord
    ):
        raise InvalidCampaignOwnerCapabilityError(
            "hypothesis mutation view contains malformed staged values"
        )
    receipt = state.registry._hypothesis_store.compare_and_swap_in(
        state.transaction,
        view_state.owner,
        view_state.target,
    )
    witness = _owner._consume_hypothesis_mutation_receipt(state.ledger, receipt)
    committed = witness.committed_token
    if (
        witness.expected_token is not view_state.owner
        or type(committed) is not RevisionedHypothesisRecord
        or committed.hypothesis_id != view_state.owner.hypothesis_id
        or committed.owner_revision != view_state.owner.owner_revision + 1
        or committed
        != RevisionedHypothesisRecord.from_value(
            view_state.target,
            committed.owner_revision,
        )
    ):
        raise DurableOwnerIntegrityError(
            "hypothesis receipt does not match its exact claimed mutation view"
        )
    state.staged_tokens[view] = committed
    state.staged_receipts[view] = receipt
    state.staged_witnesses[view] = witness


def _require_claimed_scope_view(
    state: _ScopeState,
    view: _MutationView,
    view_state: _ViewState,
) -> None:
    if view not in state.requested_views:
        raise InvalidCampaignOwnerCapabilityError(
            "mutation view was not claimed by this scope"
        )
    if view_state.registry_ref() is not state.registry:
        raise InvalidCampaignOwnerCapabilityError(
            "mutation view belongs to another Registry"
        )
    if view_state.phase is not _CapabilityPhase.CLAIMED:
        raise CampaignOwnerLifecycleError("mutation view is not claimed")
    if view in state.staged_tokens:
        raise CampaignOwnerLifecycleError("mutation view was already staged")


def _prepare_and_seal_scope(state: _ScopeState) -> None:
    if set(state.staged_tokens) != set(state.requested_views):
        raise _owner.OwnerReceiptClosureError(
            "every claimed mutation view must complete fused CAS/staging"
        )
    receipts = tuple(state.staged_receipts[view] for view in state.requested_views)
    witnesses = tuple(state.staged_witnesses[view] for view in state.requested_views)
    prepared = _prepare_successor_root(state.old_root, state.staged_tokens)
    sealed_witnesses = _owner._seal_owner_receipt_ledger(state.ledger, receipts)
    if len(sealed_witnesses) != len(witnesses) or any(
        sealed is not staged
        for sealed, staged in zip(sealed_witnesses, witnesses, strict=True)
    ):
        raise _owner.OwnerReceiptClosureError(
            "sealed owner witnesses differ from staged receipt identities"
        )
    state.prepared_root = prepared
    state.witnesses = tuple(sealed_witnesses)


def _deactivate_session(state: _ScopeState) -> tuple[list[BaseException], bool]:
    errors: list[BaseException] = []
    for _attempt in range(2):
        try:
            _sqlite._deactivate_coordinated_transaction(
                state.session,
                state.registry._database_authority,
            )
            break
        except BaseException as error:
            errors.append(error)
    complete = False
    try:
        session_state = _sqlite._lookup_session_state(state.session)
        complete = _sqlite._session_deactivation_complete(session_state)
    except BaseException as error:
        errors.append(error)
    return errors, complete


def _classify_latched_scope(state: _ScopeState) -> _CommitOutcome:
    committed = True
    expected = True
    with _sqlite._independent_authority_read_snapshot(
        state.registry._database_authority
    ) as snapshot:
        for witness in state.witnesses:
            expected_token = witness.expected_token
            committed_token = witness.committed_token
            if (
                type(expected_token) is RevisionedBranchRecord
                and type(committed_token) is RevisionedBranchRecord
            ):
                actual = state.registry._branch_store._load_revisioned_branch_from_snapshot(
                    snapshot,
                    committed_token.branch_id,
                )
            elif (
                type(expected_token) is RevisionedHypothesisRecord
                and type(committed_token) is RevisionedHypothesisRecord
            ):
                actual = state.registry._hypothesis_store._load_revisioned_hypothesis_from_snapshot(
                    snapshot,
                    committed_token.hypothesis_id,
                )
            else:
                raise DurableOwnerIntegrityError(
                    "mutation classification encountered a creation or mixed-kind witness"
                )
            committed = committed and actual == committed_token
            expected = expected and actual == expected_token
    if committed and not expected:
        return _CommitOutcome.PROVEN_COMMITTED
    if expected and not committed:
        return _CommitOutcome.PROVEN_ROLLED_BACK
    return _CommitOutcome.UNCERTAIN_OR_MIXED


def _publish_prepared_root(state: _ScopeState) -> None:
    prepared = state.prepared_root
    if prepared is None:
        raise CampaignOwnerIntegrityHoldError(
            "committed owner transaction has no prepared local root"
        )
    registry = state.registry
    if registry._owner_state is prepared:
        registry._availability = _Availability.CLEAR
        return
    if registry._owner_state is not state.old_root:
        registry._availability = _Availability.PERMANENT_HOLD
        raise CampaignOwnerIntegrityHoldError(
            "Campaign owner root changed outside its held publication scope"
        )
    try:
        registry._owner_state = prepared
    finally:
        registry._availability = (
            _Availability.CLEAR
            if registry._owner_state is prepared
            else _Availability.PERMANENT_HOLD
        )


def _clear_scope_binding(state: _ScopeState) -> list[BaseException]:
    errors: list[BaseException] = []
    state.active = False
    try:
        state.context_probe.reset(state.context_proof_token)
    except BaseException as error:
        errors.append(error)
    try:
        if _ACTIVE_SCOPE.get() is state.scope:
            _ACTIVE_SCOPE.reset(state.context_token)
    except BaseException as error:
        errors.append(error)
        try:
            if _ACTIVE_SCOPE.get() is state.scope:
                _ACTIVE_SCOPE.set(None)
        except BaseException as fallback:
            errors.append(fallback)
    try:
        if getattr(_THREAD_SCOPE, "scope", None) is state.scope:
            _THREAD_SCOPE.scope = None
    except BaseException as error:
        errors.append(error)
    return errors


def _exit_owner_scope(
    state: _ScopeState,
    body_error: BaseException | None,
    body_traceback: Any,
) -> None:
    registry = state.registry
    primary = body_error
    traceback = body_traceback
    cleanup_errors: list[BaseException] = []
    commit_returned = False
    settlement: _sqlite._OriginalConnectionSettlement | None = None
    outcome: _CommitOutcome | None = None
    try:
        # This preallocated transition runs before cleanup calls.  The outer
        # finally still owns the guard, scope bindings, and owner-lock release.
        for view_state in state.requested_view_states:
            view_state.phase = _CapabilityPhase.SPENT

        if primary is None:
            try:
                _prepare_and_seal_scope(state)
            except BaseException as error:
                primary = error
                traceback = error.__traceback__

        if primary is None:
            state.commit_latched = True
            try:
                _sqlite._commit_coordinated_transaction(
                    state.session,
                    registry._database_authority,
                )
                commit_returned = True
                outcome = _CommitOutcome.PROVEN_COMMITTED
            except BaseException as error:
                primary = error
                traceback = error.__traceback__

        try:
            _owner._close_owner_receipt_ledger(
                state.ledger,
                registry._database_authority,
            )
        except BaseException as error:
            cleanup_errors.append(error)

        deactivation_errors, deactivation_complete = _deactivate_session(state)
        cleanup_errors.extend(deactivation_errors)

        if commit_returned:
            if deactivation_complete:
                try:
                    _publish_prepared_root(state)
                except BaseException as error:
                    if registry._owner_state is not state.prepared_root:
                        registry._availability = _Availability.PERMANENT_HOLD
                        primary = CampaignOwnerIntegrityHoldError(
                            "committed durable owners could not publish locally"
                        )
                        traceback = primary.__traceback__
                    cleanup_errors.append(error)
            else:
                registry._availability = _Availability.PERMANENT_HOLD
                primary = CampaignOwnerIntegrityHoldError(
                    "committed owner transaction authority did not deactivate"
                )
                traceback = primary.__traceback__
            try:
                _sqlite._close_coordinated_transaction(
                    state.session,
                    registry._database_authority,
                )
            except BaseException as error:
                cleanup_errors.append(error)
        else:
            if deactivation_complete:
                try:
                    settlement = _sqlite._settle_deactivated_original_connection(
                        state.session,
                        registry._database_authority,
                    )
                except BaseException as error:
                    cleanup_errors.append(error)
            else:
                cleanup_errors.append(
                    CampaignOwnerIntegrityHoldError(
                        "owner transaction authority did not deactivate"
                    )
                )

            if state.commit_latched:
                if settlement is not None:
                    try:
                        outcome = _classify_latched_scope(state)
                    except BaseException as error:
                        cleanup_errors.append(error)
                        outcome = _CommitOutcome.UNCERTAIN_OR_MIXED
                else:
                    outcome = _CommitOutcome.UNCERTAIN_OR_MIXED

                if outcome is _CommitOutcome.PROVEN_COMMITTED:
                    try:
                        _publish_prepared_root(state)
                    except BaseException as error:
                        cleanup_errors.append(error)
                        if registry._owner_state is not state.prepared_root:
                            outcome = _CommitOutcome.UNCERTAIN_OR_MIXED
                elif (
                    outcome is _CommitOutcome.PROVEN_ROLLED_BACK
                    and settlement is _sqlite._OriginalConnectionSettlement.ROLLED_BACK
                ):
                    registry._availability = _Availability.CLEAR
                else:
                    outcome = _CommitOutcome.UNCERTAIN_OR_MIXED
            elif settlement is _sqlite._OriginalConnectionSettlement.ROLLED_BACK:
                registry._availability = _Availability.CLEAR
            else:
                registry._availability = _Availability.PERMANENT_HOLD
                cleanup_errors.append(
                    CampaignOwnerIntegrityHoldError(
                        "pre-commit owner rollback and close were not proven"
                    )
                )

        if state.commit_latched and outcome is _CommitOutcome.UNCERTAIN_OR_MIXED:
            registry._availability = _Availability.PERMANENT_HOLD
            hold_error = CampaignOwnerIntegrityHoldError(
                "durable owner commit outcome is uncertain or mixed"
            )
            if primary is not None:
                _append_cleanup_context(hold_error, primary)
            primary = hold_error
            traceback = hold_error.__traceback__
    except BaseException as unexpected:
        if primary is None:
            primary = unexpected
            traceback = unexpected.__traceback__
        else:
            cleanup_errors.append(unexpected)
    finally:
        try:
            # Exact root identity is the no-double-publish recovery proof.
            if (
                state.prepared_root is not None
                and registry._owner_state is state.prepared_root
            ):
                registry._availability = _Availability.CLEAR
            elif registry._availability is _Availability.TRANSITION:
                registry._availability = _Availability.PERMANENT_HOLD
                cleanup_errors.append(
                    CampaignOwnerIntegrityHoldError(
                        "owner transaction exited without a proven local outcome"
                    )
                )
            cleanup_errors.extend(_clear_scope_binding(state))
        finally:
            registry._owner_lock.release()

    if primary is not None:
        _raise_primary(primary, traceback, cleanup_errors)
    if cleanup_errors:
        cleanup_error = CampaignOwnerCleanupError(
            "Campaign owner cleanup failed after a proven result"
        )
        for error in cleanup_errors:
            _append_cleanup_context(cleanup_error, error)
        raise cleanup_error
