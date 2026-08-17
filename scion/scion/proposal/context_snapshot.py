"""One validated value boundary for direct V3 proposal contexts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Mapping, TypeAlias, Union

from scion.core.research_input import is_sensitive_research_key
from scion.proposal.solver_design_guidance import RENDERER_INPUTS_KEY

ProposalPhase = Literal["hypothesis", "code"]
SafeScalar: TypeAlias = str | int | float | bool | None
FrozenNode: TypeAlias = Union[SafeScalar, "_FrozenJson"]

_FORBIDDEN_KEYS = frozenset(
    {
        "frozen",
        "private",
        "raw",
        "validation",
    }
)
_FORBIDDEN_PATTERN = re.compile(
    r"(^|_)(bks|decision_features|holdout|llm|raw_metrics|raw_pair)($|_)"
    r"|(^|_)(raw_calibration|calibration_(pair|metrics))($|_)"
    r"|(^|_)frozen_(result|results|case|protocol|metrics)($|_)"
    r"|(^|_)(raw_prompt|prompt_(text|message|messages))($|_)"
    r"|(^|_)validation_(case|result|results|protocol|metrics)($|_)"
)

_HYPOTHESIS_KEYS = frozenset(
    {
        "problem_summary",
        "problem_object",
        "solver_mechanics",
        "champion_version",
        "research_surfaces",
        "available_actions",
        "existing_target_files",
        "create_path_patterns",
        "champion_stats",
        "objective_policy_guidance",
        "problem_measurement_diagnostics",
        "champion_operators_code",
        "branch_current_code",
        "branch_id",
        "research_question",
        "prior_research_observations",
        "seed",
        "experiment_history",
        RENDERER_INPUTS_KEY,
    }
)
_HYPOTHESIS_REQUIRED = frozenset(
    {
        "problem_summary",
        "branch_id",
        "research_surfaces",
        "champion_operators_code",
        "champion_stats",
    }
)
_CODE_KEYS = frozenset(
    {
        "problem_summary",
        "problem_object",
        "solver_mechanics",
        "champion_version",
        "research_surface",
        "operator_interface_spec",
        "import_whitelist",
        "active_subject_code_constraints",
        "problem_id",
        "approved_hypothesis",
        "editable_source_context",
        "branch_id",
        "editable_patterns",
        "frozen_patterns",
        "seed",
        RENDERER_INPUTS_KEY,
    }
)
_CODE_REQUIRED = frozenset(
    {
        "problem_summary",
        "branch_id",
        "approved_hypothesis",
        "editable_source_context",
        "operator_interface_spec",
        "editable_patterns",
        "frozen_patterns",
    }
)


@dataclass(frozen=True)
class _FrozenJson:
    kind: Literal["object", "array"]
    items: tuple[Any, ...]

    def to_primitive(self) -> Any:
        if self.kind == "array":
            return [_to_primitive(item) for item in self.items]
        return {key: _to_primitive(value) for key, value in self.items}


@dataclass(frozen=True, init=False)
class ProposalContextSnapshot:
    """Primitive-only provider context, frozen once before rendering."""

    schema_version: ClassVar[str] = "proposal-context.v1"
    _phase: ProposalPhase
    _context: _FrozenJson

    def __init__(self) -> None:
        raise TypeError("use ProposalContextSnapshot.create")

    @classmethod
    def create(
        cls,
        *,
        phase: ProposalPhase,
        context: Mapping[str, Any],
    ) -> ProposalContextSnapshot:
        if phase == "hypothesis":
            allowed, required = _HYPOTHESIS_KEYS, _HYPOTHESIS_REQUIRED
        elif phase == "code":
            allowed, required = _CODE_KEYS, _CODE_REQUIRED
        else:
            raise ValueError(f"unsupported proposal context phase: {phase}")
        if not isinstance(context, Mapping):
            raise TypeError("proposal context must be a mapping")
        unknown = [key for key in context if key not in allowed]
        missing = [key for key in required if key not in context]
        if unknown or missing:
            key = unknown[0] if unknown else missing[0]
            if unknown:
                _validate_key(key, "$.unknown")
                _freeze_and_validate(
                    context[key], path=f"$.unknown.{key}", active_ids=set()
                )
            raise ValueError(f"unsupported proposal context field: {key}")
        frozen = _freeze_and_validate(context, path="$", active_ids=set())
        if not isinstance(frozen, _FrozenJson) or frozen.kind != "object":
            raise TypeError("proposal context must be a mapping")
        snapshot = object.__new__(cls)
        object.__setattr__(snapshot, "_phase", phase)
        object.__setattr__(snapshot, "_context", frozen)
        return snapshot

    @property
    def phase(self) -> ProposalPhase:
        return self._phase

    def provider_context(
        self, *, include_renderer_inputs: bool = False
    ) -> dict[str, Any]:
        context = self._context.to_primitive()
        if not include_renderer_inputs:
            context.pop(RENDERER_INPUTS_KEY, None)
        return context


def freeze_proposal_context(
    phase: ProposalPhase,
    context: Mapping[str, Any],
) -> ProposalContextSnapshot:
    """Validate and freeze the single context value used for one H or C call."""

    return ProposalContextSnapshot.create(phase=phase, context=context)


def _freeze_and_validate(value: Any, *, path: str, active_ids: set[int]) -> FrozenNode:
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
                if key in seen:
                    raise ValueError(f"duplicate proposal context key at {path}.{key}")
                seen.add(key)
                frozen_items.append(
                    (
                        key,
                        _freeze_and_validate(
                            child, path=f"{path}.{key}", active_ids=active_ids
                        ),
                    )
                )
            return _FrozenJson("object", tuple(frozen_items))
        return _FrozenJson(
            "array",
            tuple(
                _freeze_and_validate(
                    child, path=f"{path}[{index}]", active_ids=active_ids
                )
                for index, child in enumerate(value)
            ),
        )
    finally:
        active_ids.remove(value_id)


def _validate_key(key: Any, path: str) -> None:
    if not isinstance(key, str):
        raise TypeError(f"proposal context key at {path} must be a string")
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    if (
        is_sensitive_research_key(key)
        or normalized in _FORBIDDEN_KEYS
        or _FORBIDDEN_PATTERN.search(normalized)
    ):
        raise ValueError(f"forbidden proposal context field at {path}.{key}: {key}")


def _to_primitive(value: FrozenNode) -> Any:
    return value.to_primitive() if isinstance(value, _FrozenJson) else value


__all__ = [
    "ProposalContextSnapshot",
    "freeze_proposal_context",
]
