"""Typed safety shell for authoritative proposal contexts."""

from __future__ import annotations

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
class SafeProposalInputs:
    """Primitive-only proposal facts grouped under explicit safe sections."""

    schema_version: ClassVar[str] = "safe-proposal-inputs.v1"
    _phase: ProposalPhase
    _static_sections: _FrozenJson
    _evidence_sections: _FrozenJson
    _renderer_inputs: _FrozenJson
    _field_order: tuple[str, ...]

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
        field_order: tuple[str, ...] | None = None,
    ) -> SafeProposalInputs:
        if phase not in {"hypothesis", "code"}:
            raise ValueError(f"unsupported proposal context phase: {phase}")
        _validate_top_sections(static_sections, _STATIC_SECTIONS, "$.static")
        _validate_top_sections(evidence_sections, _EVIDENCE_SECTIONS, "$.evidence")
        static = _freeze_and_validate(
            static_sections, path="$.static", active_ids=set()
        )
        evidence = _freeze_and_validate(
            evidence_sections, path="$.evidence", active_ids=set()
        )
        renderer = _freeze_and_validate(
            renderer_inputs or {}, path="$.renderer_inputs", active_ids=set()
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
        inputs = object.__new__(cls)
        object.__setattr__(inputs, "_phase", phase)
        object.__setattr__(inputs, "_static_sections", static)
        object.__setattr__(inputs, "_evidence_sections", evidence)
        object.__setattr__(inputs, "_renderer_inputs", renderer)
        object.__setattr__(inputs, "_field_order", resolved_order)
        return inputs

    @property
    def phase(self) -> ProposalPhase:
        return self._phase

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

@dataclass(frozen=True, init=False)
class ProposalContextSnapshot:
    """Frozen, validated value routed to the provider projection."""

    schema_version: ClassVar[str] = "proposal-context-snapshot.v1"
    _inputs: SafeProposalInputs

    def __init__(self) -> None:
        raise TypeError("use ProposalContextSnapshot.from_safe_inputs")

    @classmethod
    def from_safe_inputs(cls, inputs: SafeProposalInputs) -> ProposalContextSnapshot:
        if not isinstance(inputs, SafeProposalInputs):
            raise TypeError("snapshot inputs must be SafeProposalInputs")
        snapshot = object.__new__(cls)
        object.__setattr__(snapshot, "_inputs", inputs)
        return snapshot

    @property
    def inputs(self) -> SafeProposalInputs:
        return self._inputs

    @property
    def phase(self) -> ProposalPhase:
        return self.inputs.phase


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
        field_order: list[str] = []
        for key, value in context.items():
            owner = owners[key]
            field_order.append(key)
            if owner == "renderer_inputs":
                renderer[key] = value
                continue
            family, section = owner.split(".", 1)
            target = static if family == "static" else evidence
            target.setdefault(section, {})[key] = value
        return SafeProposalInputs.create(
            phase=phase,
            static_sections=static,
            evidence_sections=evidence,
            renderer_inputs=renderer,
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
) -> FrozenNode:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite proposal context number at {path}")
        return value
    if not isinstance(value, (Mapping, list, tuple)):
        raise TypeError(
            f"unsupported opaque proposal context value at {path}: "
            f"{type(value).__name__}"
        )
    value_id = id(value)
    if value_id in active_ids:
        raise ValueError(f"cyclic proposal context value at {path}")
    active_ids.add(value_id)
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
                frozen = _freeze_and_validate(
                    child, path=f"{path}.{key}", active_ids=active_ids
                )
                frozen_items.append((key, frozen))
            return _FrozenJson("object", tuple(frozen_items))
        frozen_values: list[FrozenNode] = []
        for index, child in enumerate(value):
            frozen = _freeze_and_validate(
                child, path=f"{path}[{index}]", active_ids=active_ids
            )
            frozen_values.append(frozen)
        return _FrozenJson("array", tuple(frozen_values))
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


__all__ = [
    "ProposalContextSnapshot",
    "SafeProposalInputExtractor",
    "SafeProposalInputs",
]
