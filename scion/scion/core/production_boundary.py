"""Production campaign fail-closed boundary checks."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scion.verification.requirements import requires_adapter_for_runtime


def is_adapter_backed_production_spec(problem_spec: Any | None) -> bool:
    """Return whether *problem_spec* requires production adapter semantics."""

    return requires_adapter_for_runtime(problem_spec)


def validate_production_campaign_boundary(
    *,
    problem_spec: Any | None,
    experiment_protocol: Any | None,
    adapter: Any | None,
    split_manifest: Any | None,
    seed_ledger: Any | None,
    verification_gate: Any | None = None,
    allow_skeleton: bool = False,
) -> None:
    """Fail closed before running adapter-backed production campaigns.

    Legacy skeleton/demo callers can opt into the old fallback path with
    ``allow_skeleton=True``. Without that explicit opt-in, ProblemSpecV1 and
    specs declaring adapter-backed runtime must have the protocol evidence
    needed by the campaign loop.
    """

    if not is_adapter_backed_production_spec(problem_spec) or allow_skeleton:
        return

    errors = production_boundary_errors(
        problem_spec=problem_spec,
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
    problem_spec: Any | None,
    experiment_protocol: Any | None,
    adapter: Any | None,
    split_manifest: Any | None,
    seed_ledger: Any | None,
    verification_gate: Any | None = None,
) -> tuple[str, ...]:
    """Return production boundary violations for a non-skeleton campaign."""

    errors: list[str] = []
    if adapter is None:
        errors.append("problem adapter is required")
    if experiment_protocol is None:
        errors.append("experiment_protocol is required")
    elif not _has_metric_specs(_attr(experiment_protocol, "_metric_specs", None)):
        errors.append("metric_specs are required")
    elif _attr(experiment_protocol, "_require_metric_specs", True) is False:
        errors.append("ExperimentProtocol must require metric_specs")

    errors.extend(_missing_stage_values(split_manifest, "split_manifest"))
    errors.extend(_missing_stage_values(seed_ledger, "seed_ledger"))
    errors.extend(_verification_gate_errors(verification_gate))
    return tuple(errors)


def _verification_gate_errors(verification_gate: Any | None) -> tuple[str, ...]:
    if verification_gate is None:
        return ()

    errors: list[str] = []
    if _attr(verification_gate, "_strict_runtime_checks", None) is not True:
        errors.append("verification_gate must enable strict runtime checks")
    if _attr(verification_gate, "_require_adapter_for_runtime", None) is not True:
        errors.append(
            "verification_gate must require adapter for runtime verification"
        )
    return tuple(errors)


def _missing_stage_values(obj: Any | None, label: str) -> tuple[str, ...]:
    if obj is None:
        return (f"{label} is required",)
    missing = []
    for stage in ("screening", "validation", "frozen", "canary"):
        value = _attr(obj, stage, None)
        if not _non_empty_sequence(value):
            missing.append(f"{label}.{stage} is required")
    return tuple(missing)


def _has_metric_specs(value: Any) -> bool:
    if value is None or isinstance(value, (str, bytes)):
        return False
    if isinstance(value, Sequence):
        return len(value) > 0
    try:
        return any(True for _ in value)
    except TypeError:
        return True


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
    "is_adapter_backed_production_spec",
    "production_boundary_errors",
    "validate_production_campaign_boundary",
]
