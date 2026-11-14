"""Production campaign fail-closed boundary checks."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any


def validate_fresh_campaign_output(
    campaign_dir: str | Path,
) -> None:
    """Reject any output value from a prior campaign invocation."""

    path = Path(campaign_dir)
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f"campaign output is not a directory: {path}")
    unexpected = sorted(entry.name for entry in path.iterdir())
    if not unexpected:
        return
    names = ", ".join(unexpected[:8])
    if len(unexpected) > 8:
        names += f", ... ({len(unexpected)} entries)"
    raise ValueError(
        "campaign output must be fresh; choose a new directory "
        f"(found: {names})"
    )


def validate_production_campaign_boundary(
    *,
    experiment_protocol: Any | None,
    adapter: Any | None,
    split_manifest: Any | None,
    seed_ledger: Any | None,
    verification_gate: Any | None = None,
) -> None:
    """Fail closed unless the complete direct-V3 campaign boundary exists."""

    errors = production_boundary_errors(
        experiment_protocol=experiment_protocol,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        verification_gate=verification_gate,
    )
    if errors:
        raise ValueError(
            "adapter-backed production campaign is not runnable; "
            + "; ".join(errors)
        )


def production_boundary_errors(
    *,
    experiment_protocol: Any | None,
    adapter: Any | None,
    split_manifest: Any | None,
    seed_ledger: Any | None,
    verification_gate: Any | None = None,
) -> tuple[str, ...]:
    """Return production boundary violations for a non-skeleton campaign."""

    errors: list[str] = []
    problem_spec = _visible_adapter_spec(adapter) if adapter is not None else None
    parameter_search = _attr(problem_spec, "parameter_search", None)
    if _attr(parameter_search, "enabled", False) is True:
        errors.append(
            "parameter_search.enabled must be false for direct-v3 production "
            "campaigns"
        )
    if adapter is None:
        errors.append("problem adapter is required")
    elif problem_spec is None:
        errors.append("adapter.spec is required")
    if experiment_protocol is None:
        errors.append("experiment_protocol is required")
    else:
        protocol_metrics = _metric_specs_tuple(
            _attr(experiment_protocol, "_metric_specs", None)
        )
        if protocol_metrics is None:
            errors.append("metric_specs are required")
        else:
            errors.extend(_metric_spec_shape_errors(protocol_metrics))
    errors.extend(_missing_stage_values(split_manifest, "split_manifest"))
    errors.extend(_missing_stage_values(seed_ledger, "seed_ledger"))
    errors.extend(_verification_gate_errors(verification_gate))
    return tuple(errors)


def _verification_gate_errors(verification_gate: Any | None) -> tuple[str, ...]:
    if verification_gate is None:
        return ()
    if not callable(_attr(verification_gate, "run", None)):
        return ("verification_gate.run is required",)
    return ()


def _missing_stage_values(obj: Any | None, label: str) -> tuple[str, ...]:
    if obj is None:
        return (f"{label} is required",)
    missing = []
    for stage in ("screening", "validation", "frozen", "canary"):
        value = _attr(obj, stage, None)
        if not _non_empty_sequence(value):
            missing.append(f"{label}.{stage} is required")
    return tuple(missing)


def _metric_spec_shape_errors(metric_specs: tuple[Any, ...]) -> tuple[str, ...]:
    errors: list[str] = []
    seen_priorities: set[int] = set()
    seen_names: set[str] = set()
    for index, metric in enumerate(metric_specs):
        name = _attr(metric, "name", None)
        direction = _attr(metric, "direction", None)
        priority = _attr(metric, "priority", None)
        label = f"metric_specs[{index}]"
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}.name is required")
        elif name in seen_names:
            errors.append(f"{label}.name duplicates {name!r}")
        else:
            seen_names.add(name)
        if direction not in {"minimize", "maximize"}:
            errors.append(f"{label}.direction must be 'minimize' or 'maximize'")
        if (
            not isinstance(priority, int)
            or isinstance(priority, bool)
            or priority <= 0
        ):
            errors.append(f"{label}.priority must be a positive integer")
        elif priority in seen_priorities:
            errors.append(f"{label}.priority duplicates {priority}")
        else:
            seen_priorities.add(priority)
    return tuple(errors)


def _metric_specs_tuple(value: Any) -> tuple[Any, ...] | None:
    if value is None or isinstance(value, (str, bytes)):
        return None
    if isinstance(value, Sequence):
        return tuple(value) or None
    try:
        values = tuple(value)
    except TypeError:
        return None
    return values or None


def _visible_adapter_spec(adapter: Any) -> Any | None:
    return _attr(adapter, "spec", None)


def _non_empty_sequence(value: Any) -> bool:
    if value is None or isinstance(value, (str, bytes)):
        return False
    try:
        return len(value) > 0
    except TypeError:
        return False


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


__all__ = [
    "production_boundary_errors",
    "validate_production_campaign_boundary",
]
