"""Production campaign fail-closed boundary checks."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scion.core.problem_identity import problem_id_anchor, stable_identity_hash
from scion.verification.gate import VerificationGate
from scion.verification.requirements import requires_adapter_for_runtime


def is_adapter_backed_production_spec(problem_spec: Any | None) -> bool:
    """Return whether *problem_spec* requires production adapter semantics."""

    return requires_adapter_for_runtime(problem_spec)


def is_adapter_backed_production_campaign(
    *,
    problem_spec: Any | None,
    adapter: Any | None,
    allow_skeleton: bool = False,
) -> bool:
    """Return whether a campaign must use production adapter boundaries."""

    if allow_skeleton:
        return False
    return adapter is not None or is_adapter_backed_production_spec(problem_spec)


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

    if not is_adapter_backed_production_campaign(
        problem_spec=problem_spec,
        adapter=adapter,
        allow_skeleton=allow_skeleton,
    ):
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
    else:
        protocol_metrics = _metric_specs_tuple(
            _attr(experiment_protocol, "_metric_specs", None)
        )
        if protocol_metrics is None:
            errors.append("metric_specs are required")
        else:
            errors.extend(_metric_spec_shape_errors(protocol_metrics))
            errors.extend(_metric_spec_identity_errors(problem_spec, protocol_metrics))
        if _attr(experiment_protocol, "_require_metric_specs", True) is False:
            errors.append("ExperimentProtocol must require metric_specs")
        protocol_problem_spec = _attr(experiment_protocol, "_problem_spec", None)
        errors.extend(
            _problem_spec_match_errors(
                problem_spec,
                protocol_problem_spec,
                label="experiment_protocol.problem_spec",
                require_candidate=True,
            )
        )

    errors.extend(_adapter_spec_errors(problem_spec, adapter))

    errors.extend(_missing_stage_values(split_manifest, "split_manifest"))
    errors.extend(_missing_stage_values(seed_ledger, "seed_ledger"))
    errors.extend(_verification_gate_errors(verification_gate))
    return tuple(errors)


def production_boundary_identity_hashes(
    *,
    problem_spec: Any | None,
    experiment_protocol: Any | None,
    adapter: Any | None,
    split_manifest: Any | None,
    seed_ledger: Any | None,
) -> dict[str, str | None]:
    """Return stable generic identity hashes visible at the production boundary."""

    return {
        "problem_spec_hash": stable_identity_hash(problem_spec),
        "protocol_problem_spec_hash": stable_identity_hash(
            _attr(experiment_protocol, "_problem_spec", None)
            if experiment_protocol is not None
            else None
        ),
        "adapter_spec_hash": stable_identity_hash(_visible_adapter_spec(adapter))
        if adapter is not None
        else None,
        "split_manifest_hash": stable_identity_hash(split_manifest),
        "seed_ledger_hash": stable_identity_hash(seed_ledger),
    }


def _verification_gate_errors(verification_gate: Any | None) -> tuple[str, ...]:
    if verification_gate is None:
        return ()

    errors: list[str] = []
    if not isinstance(verification_gate, VerificationGate):
        errors.append("verification_gate must be a VerificationGate instance")
        return tuple(errors)
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


def _adapter_spec_errors(
    problem_spec: Any | None,
    adapter: Any | None,
) -> tuple[str, ...]:
    if adapter is None:
        return ()
    adapter_spec = _visible_adapter_spec(adapter)
    explicit_hash = _explicit_problem_spec_hash(adapter)
    if explicit_hash is None:
        explicit_hash = _explicit_problem_spec_hash(adapter_spec)
    expected_hash = _canonical_problem_spec_hash(problem_spec)
    errors: list[str] = []
    if (
        explicit_hash is not None
        and expected_hash is not None
        and explicit_hash != expected_hash
    ):
        errors.append(
            "adapter.spec problem_spec_hash must match campaign problem_spec "
            f"{expected_hash!r}; got {explicit_hash!r}"
        )
    if adapter_spec is None:
        if explicit_hash is not None and not errors:
            return ()
        errors.append("adapter.spec is required")
        return tuple(errors)
    errors.extend(_adapter_identity_compatibility_errors(problem_spec, adapter_spec))
    return tuple(errors)


def _problem_spec_match_errors(
    campaign_spec: Any | None,
    candidate_spec: Any | None,
    *,
    label: str,
    require_candidate: bool = False,
) -> tuple[str, ...]:
    if candidate_spec is None:
        if require_candidate:
            return (f"{label} is required",)
        return ()
    campaign_id = _problem_identity(campaign_spec)
    candidate_id = _problem_identity(candidate_spec)
    errors: list[str] = []
    if (
        campaign_id is not None
        and candidate_id is not None
        and campaign_id != candidate_id
    ):
        errors.append(
            f"{label} must match campaign problem_spec identity "
            f"{campaign_id!r}; got {candidate_id!r}"
        )
    campaign_hash = stable_identity_hash(campaign_spec)
    candidate_hash = stable_identity_hash(candidate_spec)
    if (
        campaign_hash is not None
        and candidate_hash is not None
        and campaign_hash != candidate_hash
    ):
        errors.append(
            f"{label} stable identity hash must match campaign problem_spec "
            f"{campaign_hash!r}; got {candidate_hash!r}"
        )
    return tuple(errors)


def _adapter_identity_compatibility_errors(
    campaign_spec: Any | None,
    adapter_spec: Any | None,
) -> tuple[str, ...]:
    """Validate adapter-visible problem identity without requiring full hash parity."""

    campaign_id = _problem_identity(campaign_spec)
    adapter_id = _problem_identity(adapter_spec)
    errors: list[str] = []
    if campaign_id is None:
        errors.append("campaign problem_spec identity is required")
    if adapter_id is None:
        errors.append("adapter.spec identity is required")
    elif campaign_id is not None and adapter_id != campaign_id:
        errors.append(
            "adapter.spec must match campaign problem_spec identity "
            f"{campaign_id!r}; got {adapter_id!r}"
        )

    campaign_objectives = _metric_specs_tuple(_attr(campaign_spec, "objectives", None))
    adapter_objectives = _metric_specs_tuple(_attr(adapter_spec, "objectives", None))
    if campaign_objectives is not None and adapter_objectives is not None:
        expected_names = tuple(
            _attr(metric, "name", None) for metric in campaign_objectives
        )
        actual_names = tuple(_attr(metric, "name", None) for metric in adapter_objectives)
        if actual_names != expected_names:
            errors.append(
                "adapter.spec objectives must match campaign problem_spec names "
                f"{expected_names!r}; got {actual_names!r}"
            )
        expected_semantics = tuple(
            _metric_semantics(metric) for metric in campaign_objectives
        )
        actual_semantics = tuple(_metric_semantics(metric) for metric in adapter_objectives)
        if actual_semantics != expected_semantics:
            errors.append(
                "adapter.spec objectives must match campaign problem_spec semantics "
                f"{expected_semantics!r}; got {actual_semantics!r}"
            )
    return tuple(errors)


def _metric_spec_identity_errors(
    problem_spec: Any | None,
    metric_specs: tuple[Any, ...],
) -> tuple[str, ...]:
    objectives = _metric_specs_tuple(_attr(problem_spec, "objectives", None))
    if objectives is None:
        return ()
    expected_names = tuple(_attr(metric, "name", None) for metric in objectives)
    actual_names = tuple(_attr(metric, "name", None) for metric in metric_specs)
    if actual_names != expected_names:
        return (
            "metric_specs must match problem_spec.objectives names "
            f"{expected_names!r}; got {actual_names!r}",
        )
    expected_semantics = tuple(_metric_semantics(metric) for metric in objectives)
    actual_semantics = tuple(_metric_semantics(metric) for metric in metric_specs)
    if actual_semantics != expected_semantics:
        return (
            "metric_specs must match problem_spec.objectives semantics "
            f"{expected_semantics!r}; got {actual_semantics!r}",
        )
    return ()


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


def _metric_semantics(metric: Any) -> tuple[Any, Any, Any]:
    return (
        _attr(metric, "name", None),
        _attr(metric, "direction", None),
        _attr(metric, "priority", None),
    )


def _visible_adapter_spec(adapter: Any) -> Any | None:
    spec = _attr(adapter, "spec", None)
    if spec is None:
        spec = _attr(adapter, "_spec", None)
    if callable(spec):
        try:
            spec = spec()
        except TypeError:
            return None
    return spec


def _explicit_problem_spec_hash(value: Any | None) -> str | None:
    if value is None:
        return None
    return _clean_text(_attr(value, "problem_spec_hash", None))


def _canonical_problem_spec_hash(problem_spec: Any | None) -> str | None:
    spec_v1 = _attr(problem_spec, "spec_v1", None)
    if spec_v1 is not None:
        return stable_identity_hash(spec_v1)
    return stable_identity_hash(problem_spec)


def _problem_identity(problem_spec: Any | None) -> str | None:
    if problem_spec is None:
        return None
    return problem_id_anchor(problem_spec)


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


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
    "is_adapter_backed_production_campaign",
    "is_adapter_backed_production_spec",
    "production_boundary_errors",
    "production_boundary_identity_hashes",
    "validate_production_campaign_boundary",
]
