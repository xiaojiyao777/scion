"""Authority-bound construction of approved revision-zero hypothesis targets."""
from __future__ import annotations

import hashlib
import json
import uuid
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from scion.core.models import HypothesisProposal, HypothesisRecord
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.proposal import hypothesis_generation_authority as _generation
from scion.proposal.classifier import HypothesisFamilyClassifier


_TARGET_FACTORY_PROTOCOL_GENERATION = "hypothesis-target-factory.v1"
_PROPOSAL_KEYS = frozenset(
    {
        "hypothesis_text",
        "change_locus",
        "action",
        "target_file",
        "predicted_direction",
        "target_weakness",
        "expected_effect",
        "suggested_weight",
    }
)


class HypothesisTargetFactoryError(RuntimeError):
    """Base target-factory error."""


class HypothesisTargetUnknownError(HypothesisTargetFactoryError):
    """An unexpected fault occurred after an approval was claimed."""


class InvalidTargetAuthorityError(TypeError, HypothesisTargetFactoryError):
    """A clock/UUID authority or its output is invalid."""


class _SealedAuthority:
    __slots__ = ("_sealed",)

    def __init_subclass__(cls, **_kwargs: object) -> None:
        if cls.__module__ != __name__:
            raise TypeError(f"{cls.__name__} is sealed")

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise InvalidTargetAuthorityError(
                f"{type(self).__name__} is immutable after composition"
            )
        object.__setattr__(self, name, value)

    def __copy__(self) -> object:
        raise InvalidTargetAuthorityError(f"{type(self).__name__} cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> object:
        raise InvalidTargetAuthorityError(f"{type(self).__name__} cannot be copied")

    def __reduce__(self) -> object:
        raise InvalidTargetAuthorityError(f"{type(self).__name__} cannot be pickled")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidTargetAuthorityError(f"{type(self).__name__} cannot be pickled")


class ClockAuthority(_SealedAuthority):
    """Sealed identity for the sole target timestamp source."""

    __slots__ = ("__source",)

    def __init__(self, source: Callable[[], datetime]) -> None:
        if not callable(source):
            raise InvalidTargetAuthorityError("ClockAuthority requires a callable")
        object.__setattr__(self, "_ClockAuthority__source", source)
        object.__setattr__(self, "_sealed", True)

    def now_utc_microsecond(self) -> datetime:
        value = self.__source()
        if type(value) is not datetime or value.tzinfo is None:
            raise InvalidTargetAuthorityError(
                "clock must return an exact aware datetime"
            )
        try:
            offset = value.utcoffset()
        except Exception as exc:
            raise InvalidTargetAuthorityError("clock datetime has invalid tzinfo") from exc
        if offset != timedelta(0):
            raise InvalidTargetAuthorityError("clock datetime must be UTC")
        return value.astimezone(timezone.utc)


class UUIDAuthority(_SealedAuthority):
    """Sealed identity for the sole target identifier source."""

    __slots__ = ("__source",)

    def __init__(self, source: Callable[[], uuid.UUID]) -> None:
        if not callable(source):
            raise InvalidTargetAuthorityError("UUIDAuthority requires a callable")
        object.__setattr__(self, "_UUIDAuthority__source", source)
        object.__setattr__(self, "_sealed", True)

    def next_uuid(self) -> uuid.UUID:
        value = self.__source()
        if type(value) is not uuid.UUID:
            raise InvalidTargetAuthorityError(
                "UUID authority must return an exact UUID"
            )
        return value


@dataclass(frozen=True, slots=True)
class _FrozenTaxonomy:
    version: str
    families: tuple[str, ...]
    aliases: tuple[tuple[str, tuple[str, ...]], ...]
    canonical_json: bytes
    digest: str

    def classifier_input(self) -> dict[str, object]:
        return {
            "families": list(self.families),
            "aliases": {key: list(values) for key, values in self.aliases},
        }


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise InvalidTargetAuthorityError(f"{label} is not canonical JSON") from exc


def _freeze_taxonomy(taxonomy: object) -> _FrozenTaxonomy:
    version = _field(taxonomy, "version", "v1")
    families = _field(taxonomy, "families", [])
    aliases = _field(taxonomy, "aliases", {})
    if type(version) is not str or not version or version != version.strip():
        raise InvalidTargetAuthorityError("taxonomy version must be exact text")
    if type(families) not in (list, tuple) or any(
        type(value) is not str or not value or value != value.strip()
        for value in families
    ):
        raise InvalidTargetAuthorityError(
            "taxonomy families must be ordered exact nonempty strings"
        )
    if len(set(families)) != len(families):
        raise InvalidTargetAuthorityError("taxonomy families must be unique")
    if not isinstance(aliases, Mapping) or any(
        type(key) is not str or not key or key != key.strip() for key in aliases
    ):
        raise InvalidTargetAuthorityError("taxonomy aliases must have exact text keys")
    frozen_aliases: list[tuple[str, tuple[str, ...]]] = []
    for key, raw_values in aliases.items():
        if key not in families:
            raise InvalidTargetAuthorityError(
                f"taxonomy alias key {key!r} is not a configured family"
            )
        if type(raw_values) not in (list, tuple) or any(
            type(value) is not str or not value or value != value.strip()
            for value in raw_values
        ):
            raise InvalidTargetAuthorityError(
                f"taxonomy aliases for {key!r} must be ordered exact strings"
            )
        frozen_aliases.append((key, tuple(raw_values)))
    payload = {
        "aliases": {key: list(values) for key, values in frozen_aliases},
        "families": list(families),
        "schema_version": "hypothesis-family-taxonomy.v1",
        "taxonomy_version": version,
    }
    canonical = _canonical_json_bytes(payload, label="family taxonomy")
    return _FrozenTaxonomy(
        version=version,
        families=tuple(families),
        aliases=tuple(frozen_aliases),
        canonical_json=canonical,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def _decode_proposal(value: bytes) -> HypothesisProposal:
    if type(value) is not bytes or not value:
        raise ValueError("generated proposal must be exact canonical bytes")
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("generated proposal is malformed") from exc
    if type(payload) is not dict or frozenset(payload) != _PROPOSAL_KEYS:
        raise ValueError("generated proposal has unexpected fields")
    if _canonical_json_bytes(payload, label="generated proposal") != value:
        raise ValueError("generated proposal bytes are not canonical")
    return HypothesisProposal(**payload)


def _strict_utc(value: datetime, *, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError(f"{label} must be an exact aware UTC datetime")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must use UTC")
    return value.astimezone(timezone.utc)


class HypothesisTargetFactory(_SealedAuthority):
    """Consume one approval and issue one detached revision-zero target."""

    __slots__ = (
        "__authority",
        "__classifier",
        "__clock",
        "__config_digest",
        "__taxonomy",
        "__uuid",
        "__returned_approvals",
    )

    def __init__(
        self,
        *,
        taxonomy: object,
        clock_authority: ClockAuthority,
        uuid_authority: UUIDAuthority,
    ) -> None:
        if type(clock_authority) is not ClockAuthority:
            raise InvalidTargetAuthorityError(
                "target factory requires the exact ClockAuthority"
            )
        if type(uuid_authority) is not UUIDAuthority:
            raise InvalidTargetAuthorityError(
                "target factory requires the exact UUIDAuthority"
            )
        frozen = _freeze_taxonomy(taxonomy)
        classifier = HypothesisFamilyClassifier(
            taxonomy=frozen.classifier_input(),
            taxonomy_version=frozen.version,
        )
        config_payload = {
            "classifier": "HypothesisFamilyClassifier.keyword.v1",
            "clock_authority_identity": id(clock_authority),
            "protocol_generation": _TARGET_FACTORY_PROTOCOL_GENERATION,
            "schema_version": "hypothesis-target-factory-config.v1",
            "target_codec": "RevisionedHypothesisRecord.v1",
            "taxonomy_digest": frozen.digest,
            "uuid_authority_identity": id(uuid_authority),
        }
        config_digest = hashlib.sha256(
            _canonical_json_bytes(config_payload, label="target factory config")
        ).hexdigest()
        object.__setattr__(self, "_HypothesisTargetFactory__authority", None)
        object.__setattr__(self, "_HypothesisTargetFactory__classifier", classifier)
        object.__setattr__(self, "_HypothesisTargetFactory__clock", clock_authority)
        object.__setattr__(
            self,
            "_HypothesisTargetFactory__config_digest",
            config_digest,
        )
        object.__setattr__(self, "_HypothesisTargetFactory__taxonomy", frozen)
        object.__setattr__(self, "_HypothesisTargetFactory__uuid", uuid_authority)
        object.__setattr__(
            self,
            "_HypothesisTargetFactory__returned_approvals",
            weakref.WeakSet(),
        )
        object.__setattr__(self, "_sealed", True)

    @property
    def taxonomy_digest(self) -> str:
        return self.__taxonomy.digest

    @property
    def target_factory_config_digest(self) -> str:
        return self.__config_digest

    @property
    def target_factory_protocol_generation(self) -> str:
        return _TARGET_FACTORY_PROTOCOL_GENERATION

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        if self.__authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "HypothesisTargetFactory generation authority is already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.TARGET_FACTORY,
            owner=self,
        )
        object.__setattr__(
            self,
            "_HypothesisTargetFactory__authority",
            authority,
        )

    def _require_authority(self) -> _generation._AuthorityHandle:
        authority = self.__authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "HypothesisTargetFactory generation authority is not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.TARGET_FACTORY,
            owner=self,
        )
        return authority

    def create_approved_target(
        self,
        approval: _generation.HypothesisContractApproval,
    ) -> _generation.ApprovedHypothesisTarget:
        authority = self._require_authority()
        try:
            claimed = _generation._claim_contract_approval_for_target(
                authority,
                approval,
                target_factory_config_digest=self.__config_digest,
                target_factory_protocol_generation=(
                    _TARGET_FACTORY_PROTOCOL_GENERATION
                ),
                taxonomy_digest=self.__taxonomy.digest,
            )
            proposal = _decode_proposal(
                claimed.result_projection.proposal_canonical_bytes
            )
            branch_owner = claimed.view_projection.branch_owner
            if type(branch_owner) is not RevisionedBranchRecord:
                raise ValueError("target factory requires exact captured Branch owner")
            branch = branch_owner.value()
            prior_owner = claimed.view_projection.prior_head
            if prior_owner is not None and type(prior_owner) is not RevisionedHypothesisRecord:
                raise ValueError("target factory requires exact captured prior H owner")
            created_at = self.__clock.now_utc_microsecond()
            parent_id: str | None = None
            if prior_owner is not None:
                prior = prior_owner.value()
                prior_created_at = _strict_utc(
                    prior.created_at,
                    label="prior hypothesis created_at",
                )
                try:
                    lower_bound = prior_created_at + timedelta(microseconds=1)
                except OverflowError as exc:
                    raise ValueError("prior hypothesis timestamp overflows") from exc
                if created_at < lower_bound:
                    created_at = lower_bound
                parent_id = prior.hypothesis_id
            created_at = _strict_utc(created_at, label="target created_at")
            target_id = str(self.__uuid.next_uuid())
            family = self.__classifier.classify(proposal.hypothesis_text or "")
            record = HypothesisRecord(
                hypothesis_id=target_id,
                branch_id=branch.branch_id,
                change_locus=proposal.change_locus,
                action=proposal.action,
                status="active",
                target_file=proposal.target_file,
                parent_hypothesis_id=parent_id,
                suggested_weight=proposal.suggested_weight,
                hypothesis_text=proposal.hypothesis_text,
                family_id=family.family_id,
                family_source=family.source,
                taxonomy_version=family.taxonomy_version,
                created_at=created_at,
                base_champion_version=branch.base_champion_id,
                predicted_direction=proposal.predicted_direction,
                proposal_digest=claimed.result_projection.proposal_sha256,
            )
            revision_zero = RevisionedHypothesisRecord.from_generated_value(record, 0)
            target = _generation._issue_approved_hypothesis_target(
                authority,
                approval,
                revision_zero_target=revision_zero,
                taxonomy_digest=self.__taxonomy.digest,
                target_factory_config_digest=self.__config_digest,
                target_factory_protocol_generation=(
                    _TARGET_FACTORY_PROTOCOL_GENERATION
                ),
                clock_authority=self.__clock,
                uuid_authority=self.__uuid,
            )
            self.__returned_approvals.add(approval)
            return target
        except BaseException as exc:
            if approval in self.__returned_approvals:
                raise
            postclaim = False
            try:
                postclaim = _generation._finish_hypothesis_target_unknown(
                    authority,
                    approval,
                )
            except BaseException as cleanup:
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        "target claim-fault settlement also failed: "
                        f"{type(cleanup).__name__}: {cleanup}"
                    )
            if not postclaim:
                raise
            if not isinstance(exc, Exception):
                raise
            raise HypothesisTargetUnknownError(
                "hypothesis target construction failed unexpectedly after claim"
            ) from exc


def system_clock_authority() -> ClockAuthority:
    return ClockAuthority(lambda: datetime.now(timezone.utc))


def system_uuid_authority() -> UUIDAuthority:
    return UUIDAuthority(uuid.uuid4)


__all__ = (
    "ClockAuthority",
    "HypothesisTargetFactory",
    "HypothesisTargetFactoryError",
    "HypothesisTargetUnknownError",
    "InvalidTargetAuthorityError",
    "UUIDAuthority",
    "system_clock_authority",
    "system_uuid_authority",
)
