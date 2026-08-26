"""Private validation-only M32 ProblemSpec manifest join."""

from __future__ import annotations

from typing import Any, NoReturn

from .models import ResearchEffectivenessInputError
from .study_manifest_controls_schema import _canonical_json_bytes, _freeze_json
from .study_manifest_io import (
    _close_manifest_bundle,
    _load_history_bases,
    _open_manifest_bundle,
    _validate_bundle_paths,
)
from .study_manifest_loader import (
    _build_validation_blocks,
    _JoinedValidationBlock,
    _loaded_history_carrier,
    _ordered_arms,
)
from .study_manifest_problem_spec_declaration_schema import (
    _normalize_declared_problem_spec,
    _NormalizedDeclaredProblemSpec,
)
from .study_manifest_problem_spec_io import (
    _load_problem_spec_root_snapshots,
    _ProblemSpecRootSnapshot,
    _validate_problem_spec_identity_set,
    _verify_problem_spec_study_bundle,
)
from .study_manifest_problem_spec_schema import (
    _MANIFEST_MAX_BYTES,
    _config_provider_problem_spec_join_result,
    _normalize_study_manifest_problem_spec,
)
from .study_manifest_provider_policy_schema import (
    _normalize_declared_provider_policy,
    _NormalizedDeclaredProviderPolicy,
)
from .study_manifest_schema import (
    _normalize_root_controls,
    _NormalizedStudyArm,
    _validate_root_control_join,
)
from .study_root import _decode_study_root

_ERROR = (
    "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_"
    "PROBLEM_SPEC_DECLARATION_JOIN_INVALID"
)


def _validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy_and_problem_spec_declaration(
    *,
    manifest_path: str,
) -> dict[str, Any]:
    """Validate v3 declarations without evaluating scientific endpoints."""

    failed = False
    result: dict[str, Any] | None = None
    try:
        result = _validate_config_provider_problem_spec_unsafe(manifest_path)
    except Exception:  # noqa: BLE001 - collapse every private input detail
        failed = True
    if failed or result is None:
        _fail()
    return result


def _validate_config_provider_problem_spec_unsafe(
    manifest_path: object,
) -> dict[str, Any]:
    bundle = _open_manifest_bundle(manifest_path)
    try:
        if (
            _canonical_json_bytes(bundle.value, max_bytes=_MANIFEST_MAX_BYTES)
            != bundle.manifest.raw
        ):
            raise ValueError
        manifest = _normalize_study_manifest_problem_spec(bundle.value)
        provider_manifest = manifest.base_manifest
        base_manifest = provider_manifest.base_manifest
        arms = _ordered_arms(base_manifest)
        declarations = tuple(
            (block.loaded_history.available, block.loaded_history.files)
            for block in base_manifest.blocks
        )
        root_tokens = tuple(arm.root_path for arm in arms)
        history_tokens = tuple(
            token for _available, files in declarations for token in files
        )
        _validate_bundle_paths(roots=root_tokens, history_files=history_tokens)
        histories = _load_history_bases(
            bundle,
            expected_problem_id=base_manifest.problem_id,
            declarations=declarations,
        )
        loaded_histories = tuple(
            _loaded_history_carrier(basis) for basis in histories.bases
        )
        if len(loaded_histories) != 5:
            raise ValueError
        roots = _load_problem_spec_root_snapshots(
            bundle,
            roots=tuple((arm.root_path, arm.declared_controls.a_cap) for arm in arms),
        )
        _validate_problem_spec_identity_set(bundle, histories, roots)
        _validate_root_declarations(
            roots,
            provider_manifest.declared_provider_policy,
            manifest.declared_problem_spec,
        )
        _validate_problem_control_joins(arms, roots, manifest.declared_problem_spec)
        blocks = _build_validation_blocks(
            base_manifest,
            arms,
            tuple(root.base.base for root in roots),
            loaded_histories,
        )
        _verify_problem_spec_study_bundle(bundle, histories, roots)
        _decode_problem_spec_validation_blocks(blocks)
        return _config_provider_problem_spec_join_result()
    finally:
        _close_manifest_bundle(bundle)


def _validate_root_declarations(
    roots: tuple[_ProblemSpecRootSnapshot, ...],
    declared_provider: _NormalizedDeclaredProviderPolicy,
    declared_problem: _NormalizedDeclaredProblemSpec,
) -> None:
    if (
        type(roots) is not tuple
        or len(roots) != 10
        or any(type(root) is not _ProblemSpecRootSnapshot for root in roots)
        or type(declared_provider) is not _NormalizedDeclaredProviderPolicy
        or type(declared_problem) is not _NormalizedDeclaredProblemSpec
    ):
        raise TypeError
    failed = False
    for root in roots:
        try:
            provider = _normalize_declared_provider_policy(root.base.provider_policy)
            if (
                provider.canonical_bytes != root.base.provider_policy_leaf.raw
                or provider.canonical_bytes != declared_provider.canonical_bytes
                or provider.frozen != declared_provider.frozen
            ):
                raise ValueError
        except Exception:  # noqa: BLE001 - audit every already-loaded arm
            failed = True
        try:
            problem = _normalize_declared_problem_spec(root.problem_spec)
            if (
                problem.canonical_bytes != root.problem_spec_leaf.raw
                or problem.canonical_bytes != declared_problem.canonical_bytes
                or problem.frozen != declared_problem.frozen
            ):
                raise ValueError
        except Exception:  # noqa: BLE001 - audit every already-loaded arm
            failed = True
    if failed:
        raise ValueError


def _validate_problem_control_joins(
    arms: tuple[_NormalizedStudyArm, ...],
    roots: tuple[_ProblemSpecRootSnapshot, ...],
    declared: _NormalizedDeclaredProblemSpec,
) -> None:
    if (
        type(arms) is not tuple
        or len(arms) != 10
        or any(type(arm) is not _NormalizedStudyArm for arm in arms)
        or type(roots) is not tuple
        or len(roots) != 10
        or any(type(root) is not _ProblemSpecRootSnapshot for root in roots)
        or type(declared) is not _NormalizedDeclaredProblemSpec
    ):
        raise TypeError
    failed = False
    for arm, root in zip(arms, roots, strict=True):
        try:
            base = root.base.base
            controls = _normalize_root_controls(base.controls)
            if controls.canonical_bytes != base.controls_leaf.raw:
                raise ValueError
            _validate_root_control_join(
                arm,
                controls,
                base.code_limits,
                base.resource_envelope,
            )
            _validate_problem_control_join(base.controls, declared)
        except Exception:  # noqa: BLE001 - audit every already-loaded arm
            failed = True
    if failed:
        raise ValueError


def _validate_problem_control_join(
    controls: Any,
    problem: _NormalizedDeclaredProblemSpec,
) -> None:
    if type(problem) is not _NormalizedDeclaredProblemSpec:
        raise TypeError
    controls_map = _exact_dict(
        controls,
        {
            "schema_version",
            "scope",
            "limitations",
            "campaign",
            "code_research_limits",
            "resource_envelope",
            "protocol",
        },
    )
    protocol = _exact_dict(
        controls_map["protocol"],
        {
            "version",
            "strict_case_paths",
            "safe_data_roots",
            "initial_screening",
            "canary",
            "time_limit_fallback_sec",
        },
    )
    initial = _exact_dict(
        protocol["initial_screening"],
        {
            "cases_by_action",
            "seeds",
            "selection",
            "screening_gate",
            "effect_policy",
            "measurement_readiness",
            "runtime_time_limits",
            "resolved_time_limits",
        },
    )
    effect = _exact_dict(
        initial["effect_policy"],
        {
            "case_aggregation",
            "case_equivalence_band",
            "effect_metric",
            "protected_objectives",
            "pairing_validity",
            "measurement_governance",
            "runtime_model",
            "max_runtime_ratio",
            "tie_speedup_ratio",
            "tie_min_runtime_pairs",
            "metric_specs",
            "objective_policy",
        },
    )
    if (
        _freeze_json(effect["metric_specs"]) != problem.metric_specs
        or _freeze_json(effect["objective_policy"]) != problem.objective_policy
    ):
        raise ValueError
    if effect["measurement_governance"] == "record_only":
        return
    if (
        effect["measurement_governance"] != "on"
        or type(effect["effect_metric"]) is not str
        or effect["effect_metric"] != problem.effect_metric
        or type(effect["protected_objectives"]) is not list
        or tuple(effect["protected_objectives"]) != problem.protected_objectives
        or type(effect["pairing_validity"]) is not str
        or effect["pairing_validity"] != problem.pairing_validity
        or type(effect["runtime_model"]) is not str
        or effect["runtime_model"] != problem.runtime_model
    ):
        raise ValueError
    gate = _exact_dict(
        initial["screening_gate"],
        {"configured", "resolved_median_delta_min"},
    )
    configured = _exact_dict(
        gate["configured"],
        {
            "min_net_case_score",
            "max_case_loss_rate",
            "win_rate_min",
            "median_delta_min",
            "bootstrap_ci_low_min",
            "initial_quality_expansion",
        },
    )
    median = configured["median_delta_min"]
    if median in {"practical_delta_screen", "practical_delta_validate"}:
        resolved = gate["resolved_median_delta_min"]
        expected = (
            problem.practical_delta_screen
            if median == "practical_delta_screen"
            else problem.practical_delta_validate
        )
        if type(resolved) is not float or resolved.hex() != expected.hex():
            raise ValueError


def _decode_problem_spec_validation_blocks(
    blocks: tuple[_JoinedValidationBlock, ...],
) -> None:
    if type(blocks) is not tuple or len(blocks) != 5:
        raise ValueError
    decoded = 0
    for block in blocks:
        if (
            type(block) is not _JoinedValidationBlock
            or block.arms[0].loaded_history is not block.arms[1].loaded_history
        ):
            raise ValueError
        for arm in block.arms:
            _decode_study_root(arm.artifacts)
            decoded += 1
    if decoded != 10:
        raise ValueError


def _exact_dict(value: Any, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != fields:
        raise ValueError
    return value


def _fail() -> NoReturn:
    raise ResearchEffectivenessInputError(_ERROR)


__all__: tuple[str, ...] = ()
