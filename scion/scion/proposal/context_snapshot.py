"""Typed safety shell for authoritative proposal contexts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Mapping, TypeAlias, Union


ProposalPhase = Literal["hypothesis", "code"]
ProposalInputOwner = Literal[
    "static.approved_hypothesis",
    "static.problem",
    "static.source_index",
    "static.task_constraints",
    "evidence.continuation",
    "evidence.safe_pre_protocol",
    "evidence.screening",
    "renderer_inputs",
    "governance",
    "audit",
]
SafeScalar: TypeAlias = str | int | float | bool | None
FrozenNode: TypeAlias = Union[SafeScalar, "_FrozenJson"]

_FORBIDDEN_KEYS = frozenset({"frozen", "prompt", "validation"})
_SAFE_METADATA_KEYS = frozenset(
    {"decision_features_excluded", "llm_trace_excluded"}
)
_FORBIDDEN_PATTERN = re.compile(
    r"(^|_)(bks|decision_features|holdout|llm|raw_metrics|raw_pair)($|_)"
    r"|(^|_)(raw_calibration|calibration_(pair|metrics))($|_)"
    r"|(^|_)frozen_(result|results|case|protocol|metrics)($|_)"
    r"|(^|_)(raw_prompt|prompt_(text|message|messages))($|_)"
    r"|(^|_)validation_(case|result|results|protocol|metrics)($|_)"
)
_STATIC_SECTIONS = frozenset(
    {"approved_hypothesis", "problem", "source_index", "task_constraints"}
)
_EVIDENCE_SECTIONS = frozenset({"continuation", "safe_pre_protocol", "screening"})


@dataclass(frozen=True)
class _FrozenJson:
    kind: Literal["object", "array"]
    items: tuple[Any, ...]

    def to_primitive(self) -> Any:
        if self.kind == "array":
            return [_to_primitive(item) for item in self.items]
        return {key: _to_primitive(value) for key, value in self.items}


@dataclass(frozen=True, init=False)
class SafetyManifest:
    """Read-only proof facts derived from the sole safe-input constructor."""

    schema_version: ClassVar[str] = "proposal-context-safety.v1"
    constructor_validated: ClassVar[bool] = True
    production_route_ready: ClassVar[bool] = True
    forbidden_field_names: ClassVar[tuple[str, ...]] = tuple(sorted(_FORBIDDEN_KEYS))
    forbidden_type_names: ClassVar[tuple[str, ...]] = ("opaque_object",)
    _checked_node_count: int

    def __init__(self) -> None:
        raise TypeError("SafetyManifest is derived and cannot be constructed")

    @classmethod
    def _from_validated_count(cls, count: int) -> SafetyManifest:
        manifest = object.__new__(cls)
        object.__setattr__(manifest, "_checked_node_count", count)
        return manifest

    @property
    def checked_node_count(self) -> int:
        return self._checked_node_count


@dataclass(frozen=True, init=False)
class GovernanceEnvelope:
    """Frozen host-owned facts that never enter provider-visible context."""

    schema_version: ClassVar[str] = "proposal-governance-envelope.v1"
    _payload: _FrozenJson
    _digest: str

    def __init__(self) -> None:
        raise TypeError("GovernanceEnvelope is derived from SafeProposalInputs.create")

    @classmethod
    def _from_mapping(
        cls,
        governance: Mapping[str, Any],
    ) -> tuple[GovernanceEnvelope, int]:
        if not isinstance(governance, Mapping):
            raise TypeError("proposal governance envelope must be a mapping")
        frozen, checked_node_count = _freeze_and_validate(
            governance,
            path="$.governance",
            active_ids=set(),
        )
        if not isinstance(frozen, _FrozenJson) or frozen.kind != "object":
            raise TypeError("proposal governance envelope must be a mapping")
        envelope = object.__new__(cls)
        object.__setattr__(envelope, "_payload", frozen)
        object.__setattr__(
            envelope,
            "_digest",
            _stable_hash(
                {
                    "schema_version": cls.schema_version,
                    "governance": frozen.to_primitive(),
                }
            ),
        )
        return envelope, checked_node_count

    def to_primitive(self) -> dict[str, Any]:
        primitive = self._payload.to_primitive()
        if not isinstance(primitive, dict):
            raise TypeError("frozen governance envelope is not a mapping")
        return primitive

    @property
    def digest(self) -> str:
        return self._digest


@dataclass(frozen=True, init=False)
class SafeProposalInputs:
    """Primitive-only proposal facts grouped under explicit safe sections."""

    schema_version: ClassVar[str] = "safe-proposal-inputs.v1"
    _phase: ProposalPhase
    _static_sections: _FrozenJson
    _evidence_sections: _FrozenJson
    _renderer_inputs: _FrozenJson
    _governance_envelope: GovernanceEnvelope
    _field_order: tuple[str, ...]
    _identity: str
    _checked_node_count: int

    def __init__(self) -> None:
        raise TypeError("use SafeProposalInputs.create")

    @classmethod
    def create(
        cls,
        *,
        phase: ProposalPhase,
        static_sections: Mapping[str, Any],
        evidence_sections: Mapping[str, Any],
        renderer_inputs: Mapping[str, Any] | None = None,
        governance: Mapping[str, Any] | None = None,
        field_order: tuple[str, ...] | None = None,
    ) -> SafeProposalInputs:
        if phase not in {"hypothesis", "code"}:
            raise ValueError(f"unsupported proposal context phase: {phase}")
        _validate_top_sections(static_sections, _STATIC_SECTIONS, "$.static")
        _validate_top_sections(evidence_sections, _EVIDENCE_SECTIONS, "$.evidence")
        static, static_count = _freeze_and_validate(
            static_sections, path="$.static", active_ids=set()
        )
        evidence, evidence_count = _freeze_and_validate(
            evidence_sections, path="$.evidence", active_ids=set()
        )
        renderer, renderer_count = _freeze_and_validate(
            renderer_inputs or {}, path="$.renderer_inputs", active_ids=set()
        )
        governance_envelope, governance_count = GovernanceEnvelope._from_mapping(
            {} if governance is None else governance
        )
        if not isinstance(static, _FrozenJson) or static.kind != "object":
            raise TypeError("static proposal sections must be a mapping")
        if not isinstance(evidence, _FrozenJson) or evidence.kind != "object":
            raise TypeError("evidence proposal sections must be a mapping")
        if not isinstance(renderer, _FrozenJson) or renderer.kind != "object":
            raise TypeError("proposal renderer inputs must be a mapping")
        resolved_order: tuple[str, ...] = ()
        if field_order is not None:
            owned = _flatten_owned_context(static, evidence, renderer)
            resolved_order = field_order
            if (
                len(resolved_order) != len(set(resolved_order))
                or set(resolved_order) != set(owned)
            ):
                raise ValueError(
                    "proposal context field order does not match owned fields"
                )
        identity = _stable_hash(
            {
                "schema_version": cls.schema_version,
                "phase": phase,
                "static_sections": static.to_primitive(),
                "evidence_sections": evidence.to_primitive(),
                "renderer_inputs": renderer.to_primitive(),
                "governance_envelope_digest": governance_envelope.digest,
                "field_order": list(resolved_order),
            }
        )
        inputs = object.__new__(cls)
        object.__setattr__(inputs, "_phase", phase)
        object.__setattr__(inputs, "_static_sections", static)
        object.__setattr__(inputs, "_evidence_sections", evidence)
        object.__setattr__(inputs, "_renderer_inputs", renderer)
        object.__setattr__(inputs, "_governance_envelope", governance_envelope)
        object.__setattr__(inputs, "_field_order", resolved_order)
        object.__setattr__(inputs, "_identity", identity)
        object.__setattr__(
            inputs,
            "_checked_node_count",
            static_count + evidence_count + renderer_count + governance_count,
        )
        return inputs

    @property
    def phase(self) -> ProposalPhase:
        return self._phase

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def static_sections(self) -> _FrozenJson:
        return self._static_sections

    @property
    def evidence_sections(self) -> _FrozenJson:
        return self._evidence_sections

    @property
    def renderer_inputs(self) -> _FrozenJson:
        return self._renderer_inputs

    @property
    def governance_envelope(self) -> GovernanceEnvelope:
        return self._governance_envelope

    @property
    def field_order(self) -> tuple[str, ...]:
        return self._field_order

    def provider_context(self, *, include_renderer_inputs: bool = False) -> dict[str, Any]:
        if not self.field_order:
            raise ValueError("safe proposal inputs have no reconstructable field order")
        owned = _flatten_owned_context(
            self.static_sections,
            self.evidence_sections,
            self.renderer_inputs,
        )
        renderer_keys = set(self.renderer_inputs.to_primitive())
        return {
            key: owned[key]
            for key in self.field_order
            if include_renderer_inputs or key not in renderer_keys
        }

    @property
    def safety_manifest(self) -> SafetyManifest:
        return SafetyManifest._from_validated_count(self._checked_node_count)


@dataclass(frozen=True, init=False)
class ProposalContextSnapshot:
    """Authoritative identity routed to direct or legacy provider projection."""

    schema_version: ClassVar[str] = "proposal-context-snapshot.v1"
    _inputs: SafeProposalInputs
    _snapshot_id: str

    def __init__(self) -> None:
        raise TypeError("use ProposalContextSnapshot.from_safe_inputs")

    @classmethod
    def from_safe_inputs(cls, inputs: SafeProposalInputs) -> ProposalContextSnapshot:
        if not isinstance(inputs, SafeProposalInputs):
            raise TypeError("snapshot inputs must be SafeProposalInputs")
        snapshot = object.__new__(cls)
        object.__setattr__(snapshot, "_inputs", inputs)
        object.__setattr__(
            snapshot,
            "_snapshot_id",
            f"proposal-context:{inputs.phase}:"
            + _stable_hash(
                {
                    "schema_version": cls.schema_version,
                    "phase": inputs.phase,
                    "safe_inputs_identity": inputs.identity,
                }
            ),
        )
        return snapshot

    @property
    def inputs(self) -> SafeProposalInputs:
        return self._inputs

    @property
    def snapshot_id(self) -> str:
        return self._snapshot_id

    @property
    def phase(self) -> ProposalPhase:
        return self.inputs.phase

    @property
    def safety_manifest(self) -> SafetyManifest:
        return self.inputs.safety_manifest

    @property
    def governance_envelope(self) -> GovernanceEnvelope:
        return self.inputs.governance_envelope


@dataclass(frozen=True, init=False)
class SafeProposalInputExtractor:
    """Explicitly assign primitive context keys to safe owners or a sidecar."""

    _owner_map: tuple[tuple[str, ProposalInputOwner], ...]
    _required_keys: frozenset[str]

    def __init__(self) -> None:
        raise TypeError("use SafeProposalInputExtractor.with_owner_map")

    @classmethod
    def with_owner_map(
        cls,
        owner_map: Mapping[str, ProposalInputOwner],
        *,
        required_keys: frozenset[str] | None = None,
    ) -> SafeProposalInputExtractor:
        allowed = {
            "static.approved_hypothesis",
            "static.problem",
            "static.source_index",
            "static.task_constraints",
            "evidence.continuation",
            "evidence.safe_pre_protocol",
            "evidence.screening",
            "renderer_inputs",
            "governance",
            "audit",
        }
        if not owner_map or any(
            not isinstance(key, str) or owner not in allowed
            for key, owner in owner_map.items()
        ):
            raise ValueError("extractor owner map must name explicit safe owners")
        extractor = object.__new__(cls)
        object.__setattr__(extractor, "_owner_map", tuple(owner_map.items()))
        required = frozenset(owner_map) if required_keys is None else required_keys
        if not required.issubset(owner_map):
            raise ValueError("extractor required key has no declared owner")
        object.__setattr__(extractor, "_required_keys", required)
        return extractor

    def extract(
        self,
        *,
        phase: ProposalPhase,
        context: Mapping[str, Any],
    ) -> SafeProposalInputs:
        owners = dict(self._owner_map)
        unknown = [key for key in context if key not in owners]
        missing = [key for key in self._required_keys if key not in context]
        if unknown or missing:
            key = unknown[0] if unknown else missing[0]
            if unknown:
                _validate_key(key, "$.unknown")
                _freeze_and_validate(
                    context[key],
                    path=f"$.unknown.{key}",
                    active_ids=set(),
                )
            raise ValueError(f"proposal context key has no exact extractor owner: {key}")
        static: dict[str, dict[str, Any]] = {}
        evidence: dict[str, dict[str, Any]] = {}
        renderer: dict[str, Any] = {}
        governance: dict[str, Any] = {}
        field_order: list[str] = []
        for key, value in context.items():
            owner = owners[key]
            if owner == "audit":
                continue
            if owner == "governance":
                governance[key] = value
                continue
            field_order.append(key)
            if owner == "renderer_inputs":
                renderer[key] = value
                continue
            family, section = owner.split(".", 1)
            target = static if family == "static" else evidence
            target.setdefault(section, {})[key] = value
        provider_task_constraint_keys = tuple(
            key
            for key in ("forced_surface", "forced_action", "forced_target_file")
            if key in context and owners.get(key) != "governance"
        )
        if provider_task_constraint_keys:
            governance["provider_task_constraint_authority"] = {
                "provider_keys": list(provider_task_constraint_keys),
                "provider_values_digest": _stable_hash(
                    {key: context[key] for key in provider_task_constraint_keys}
                ),
                "authority_ref": "provider_visible_task_constraints",
            }
        if phase == "code":
            hard_binding_keys = tuple(
                key
                for key in (
                    "approved_hypothesis",
                    "proposal_source_ledger",
                )
                if key in context and owners.get(key) != "governance"
            )
            if hard_binding_keys:
                governance["provider_hard_binding_authority"] = {
                    "provider_keys": list(hard_binding_keys),
                    "provider_values_digest": _stable_hash(
                        {key: context[key] for key in hard_binding_keys}
                    ),
                    "authority_ref": "approved_hypothesis_target_source_binding",
                }
        return SafeProposalInputs.create(
            phase=phase,
            static_sections=static,
            evidence_sections=evidence,
            renderer_inputs=renderer,
            governance=governance,
            field_order=tuple(field_order),
        )


def _flatten_owned_context(
    static: _FrozenJson,
    evidence: _FrozenJson,
    renderer: _FrozenJson,
) -> dict[str, Any]:
    owned: dict[str, Any] = {}
    for family in (static, evidence):
        for section in family.to_primitive().values():
            for key, value in section.items():
                if key in owned:
                    raise ValueError(f"duplicate proposal context owner: {key}")
                owned[key] = value
    for key, value in renderer.to_primitive().items():
        if key in owned:
            raise ValueError(f"duplicate proposal context owner: {key}")
        owned[key] = value
    return owned


def _freeze_and_validate(
    value: Any, *, path: str, active_ids: set[int]
) -> tuple[FrozenNode, int]:
    if value is None or isinstance(value, (str, bool, int)):
        return value, 1
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite proposal context number at {path}")
        return value, 1
    if not isinstance(value, (Mapping, list, tuple)):
        raise TypeError(
            f"unsupported opaque proposal context value at {path}: "
            f"{type(value).__name__}"
        )
    value_id = id(value)
    if value_id in active_ids:
        raise ValueError(f"cyclic proposal context value at {path}")
    active_ids.add(value_id)
    count = 1
    try:
        if isinstance(value, Mapping):
            frozen_items: list[tuple[str, FrozenNode]] = []
            seen: set[str] = set()
            for key, child in value.items():
                _validate_key(key, path)
                if key in _SAFE_METADATA_KEYS and child is not True:
                    raise ValueError(
                        f"safe exclusion metadata must be true at {path}.{key}"
                    )
                if key in seen:
                    raise ValueError(f"duplicate proposal context key at {path}.{key}")
                seen.add(key)
                frozen, child_count = _freeze_and_validate(
                    child, path=f"{path}.{key}", active_ids=active_ids
                )
                frozen_items.append((key, frozen))
                count += child_count
            return _FrozenJson("object", tuple(frozen_items)), count
        frozen_values: list[FrozenNode] = []
        for index, child in enumerate(value):
            frozen, child_count = _freeze_and_validate(
                child, path=f"{path}[{index}]", active_ids=active_ids
            )
            frozen_values.append(frozen)
            count += child_count
        return _FrozenJson("array", tuple(frozen_values)), count
    finally:
        active_ids.remove(value_id)


def _validate_top_sections(
    sections: Mapping[str, Any], allowed: frozenset[str], path: str
) -> None:
    if not isinstance(sections, Mapping):
        raise TypeError(f"proposal context sections at {path} must be a mapping")
    for name in sections:
        if name not in allowed:
            raise ValueError(f"unsupported proposal context section at {path}: {name}")


def _validate_key(key: Any, path: str) -> None:
    if not isinstance(key, str):
        raise TypeError(f"proposal context key at {path} must be a string")
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    if normalized not in _SAFE_METADATA_KEYS and (
        normalized in _FORBIDDEN_KEYS or _FORBIDDEN_PATTERN.search(normalized)
    ):
        raise ValueError(f"forbidden proposal context field at {path}.{key}: {key}")


def _to_primitive(value: FrozenNode) -> Any:
    return value.to_primitive() if isinstance(value, _FrozenJson) else value


def _stable_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "GovernanceEnvelope",
    "ProposalContextSnapshot",
    "SafeProposalInputExtractor",
    "SafeProposalInputs",
    "SafetyManifest",
]
