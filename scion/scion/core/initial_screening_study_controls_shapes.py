"""Exact detached config shapes for the private initial-screening carrier."""

from __future__ import annotations

import math
import sys
import weakref
from _thread import LockType
from collections.abc import Callable
from dataclasses import fields
from types import MappingProxyType, MethodType, ModuleType
from typing import Any, cast

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.config.protocol_config import (
    CanaryProtocolConfig,
    CaseQualityThresholds,
    EvaluationPipelineConfig,
    EvaluationStageConfig,
    FrozenConfig,
    FrozenGate,
    GatesConfig,
    InitialQualityExpansion,
    MeasurementReadinessConfig,
    RuntimeGovernanceConfig,
    RuntimeTimeLimitConfig,
    RuntimeTimeLimitRule,
    ScreeningConfig,
    ScreeningGate,
    SmokePrescreenConfig,
    ValidationConfig,
    ValidationGate,
)
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.qualification import QualificationOnlyConfig, QualificationRuntime
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager

_SUPPORTED_DATACLASSES = {
    QualificationOnlyConfig,
    CodeResearchLimits,
    ResourceEnvelope,
}
_SUPPORTED_MODELS = {
    ProtocolConfig,
    ScreeningConfig,
    ValidationConfig,
    FrozenConfig,
    CanaryProtocolConfig,
    RuntimeGovernanceConfig,
    RuntimeTimeLimitRule,
    RuntimeTimeLimitConfig,
    EvaluationStageConfig,
    EvaluationPipelineConfig,
    SmokePrescreenConfig,
    CaseQualityThresholds,
    InitialQualityExpansion,
    ScreeningGate,
    ValidationGate,
    FrozenGate,
    GatesConfig,
    MeasurementReadinessConfig,
    SplitManifest,
    SeedLedgerConfig,
    ObjectiveMetricSpec,
    ObjectivePolicySpec,
}


def _weak_registry_contains_owner(registry: Any, owner: Any) -> bool:
    """Scan one exact weak registry by identity without owner hash/equality."""

    if type(registry) is not weakref.WeakKeyDictionary:
        raise TypeError
    references = weakref.WeakKeyDictionary.keyrefs(registry)
    if type(references) is not list or any(
        type(reference) is not weakref.ReferenceType for reference in references
    ):
        raise TypeError
    return any(reference() is owner for reference in references)


def _loaded_problem_boundary_storage() -> dict[str, Any] | None:
    module = sys.modules.get("scion.core.initial_screening_problem_spec")
    if module is None:
        return None
    if type(module) is not ModuleType:
        raise TypeError
    storage = vars(module)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    return storage


def _loaded_problem_error_type() -> Any | None:
    storage = _loaded_problem_boundary_storage()
    return None if storage is None else storage.get("_InitialScreeningProblemSpecError")


def _loaded_problem_owner_is_registered(owner: Any) -> bool:
    storage = _loaded_problem_boundary_storage()
    return storage is not None and _weak_registry_contains_owner(
        storage.get("_REGISTERED_OWNERS"), owner
    )


def _loaded_research_context_boundary_storage() -> dict[str, Any] | None:
    module_name = "scion.core.initial_screening_research_context_validation"
    modules = sys.modules
    if type(modules) is not dict or any(type(key) is not str for key in modules):
        raise TypeError
    module = modules.get(module_name)
    if module is None:
        return None
    if type(module) is not ModuleType:
        raise TypeError
    storage = vars(module)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or type(storage.get("__name__")) is not str
        or storage.get("__name__") != module_name
    ):
        raise TypeError
    return storage


def _loaded_research_context_error_type() -> Any | None:
    storage = _loaded_research_context_boundary_storage()
    return None if storage is None else storage.get("_RESEARCH_CONTEXT_ERROR")


def _loaded_research_context_owner_is_registered(owner: Any) -> bool:
    storage = _loaded_research_context_boundary_storage()
    return storage is not None and _weak_registry_contains_owner(
        storage.get("_REGISTERED_OWNERS"), owner
    )


def _validate_dataclass_instance(value: Any, expected_type: type) -> None:
    if type(value) is not expected_type:
        raise TypeError
    _validate_exact_shape(value)


def _validate_model_instance(value: Any, expected_type: type) -> None:
    if type(value) is not expected_type:
        raise TypeError
    _validate_exact_shape(value)


def _validate_exact_shape(value: Any, active: set[int] | None = None) -> None:
    if _validate_leaf_shape(value):
        return
    stack = set() if active is None else active
    identity = id(value)
    if identity in stack:
        raise ValueError
    stack.add(identity)
    try:
        _validate_composite_shape(value, stack)
    finally:
        stack.remove(identity)


def _validate_leaf_shape(value: Any) -> bool:
    if value is None or type(value) in {str, bool, int}:
        return True
    if type(value) is not float:
        return False
    if not math.isfinite(value):
        raise ValueError
    return True


def _validate_composite_shape(value: Any, stack: set[int]) -> None:
    value_type = type(value)
    if value_type in {list, tuple}:
        for item in value:
            _validate_exact_shape(item, stack)
        return
    if value_type is dict:
        for key, item in value.items():
            _validate_exact_shape(key, stack)
            _validate_exact_shape(item, stack)
        return
    if value_type in _SUPPORTED_DATACLASSES:
        expected = {field.name for field in fields(value_type)}
        _validate_declared_shape(value, expected, stack)
        return
    if value_type in _SUPPORTED_MODELS:
        _validate_declared_shape(value, set(value_type.model_fields), stack)
        return
    raise TypeError


def _validate_declared_shape(
    value: Any,
    expected: set[str],
    stack: set[int],
) -> None:
    _validate_storage_keys(value, expected)
    for name in expected:
        _validate_exact_shape(getattr(value, name), stack)


def _validate_storage_keys(value: Any, expected: set[str]) -> None:
    storage = vars(value)
    if type(storage) is not dict:
        raise TypeError
    if any(type(key) is not str for key in storage):
        raise TypeError
    if set(storage) != expected:
        raise TypeError


def _validate_protocol_config_tree(config: ProtocolConfig) -> None:
    _validate_model_instance(config, ProtocolConfig)
    time_limits = config.runtime.time_limits
    _validate_protocol_config_shapes(config)
    if type(time_limits.rules) is not tuple:
        raise TypeError
    if not _is_bound_method(
        time_limits.resolve,
        time_limits,
        RuntimeTimeLimitConfig.resolve,
    ):
        raise TypeError
    for rule in time_limits.rules:
        _validate_model_instance(rule, RuntimeTimeLimitRule)
        if not _is_bound_method(rule.matches, rule, RuntimeTimeLimitRule.matches):
            raise TypeError


def _validate_manifest_and_ledger_shapes(manifest: Any, ledger: Any) -> None:
    _validate_model_instance(manifest, SplitManifest)
    _validate_model_instance(ledger, SeedLedgerConfig)
    _require_exact(manifest.version, str)
    _require_exact(ledger.version, str)
    for name in ("screening", "validation", "frozen", "canary", "safe_data_roots"):
        _exact_sequence(getattr(manifest, name), list, str)
    for name in ("screening", "validation", "frozen", "canary"):
        _exact_sequence(getattr(ledger, name), list, int)


def _validate_objective_shapes(metrics: Any, policy: Any | None) -> None:
    if type(metrics) is not tuple or not metrics:
        raise TypeError
    for metric in metrics:
        _validate_model_instance(metric, ObjectiveMetricSpec)
        _require_exact(metric.name, str)
        _require_exact(metric.direction, str)
        _require_exact(metric.priority, int)
        _require_finite_float(metric.tie_tolerance)
        if metric.weight is not None:
            _require_finite_float(metric.weight)
    if policy is not None:
        _validate_model_instance(policy, ObjectivePolicySpec)
        _require_exact(policy.mode, str)
        _require_exact(policy.expose_weights_to_llm, bool)


def _validate_protocol_config_shapes(config: ProtocolConfig) -> None:
    screening = config.screening
    canary = config.canary
    runtime = config.runtime
    for name in (
        "n_cases_modify",
        "n_cases_create",
        "n_seeds",
        "expand_to_modify",
        "expand_to_create",
    ):
        _require_exact(getattr(screening, name), int)
    if screening.expand_n_seeds is not None:
        _require_exact(screening.expand_n_seeds, int)
    _require_exact(screening.expose, str)
    _require_exact(screening.require_expanded_for_pass, bool)
    _exact_sequence(screening.priority_case_ids, tuple, str)
    _exact_sequence(canary.cases, list, str)
    _exact_sequence(canary.seeds, list, int)
    _validate_screening_gate_shapes(config.gates.screening)
    _require_exact(runtime.runtime_model, str)
    _require_finite_float(runtime.max_runtime_ratio)
    _require_finite_float(runtime.tie_speedup_ratio)
    _require_exact(runtime.tie_min_runtime_pairs, int)
    _validate_time_limit_shapes(runtime.time_limits)
    _validate_readiness_shapes(config.measurement_readiness)
    _require_exact(config.version, str)
    _require_exact(config.effect_metric, str)
    _exact_sequence(config.protected_objectives, tuple, str)
    _require_exact(config.case_aggregation, str)
    _require_finite_float(config.case_equivalence_band)
    _require_finite_float(config.practical_delta_screen)
    _require_exact(config.pairing_validity, str)
    _require_exact(config.measurement_governance, str)


def _validate_screening_gate_shapes(gate: ScreeningGate) -> None:
    _require_finite_float(gate.win_rate_min)
    if type(gate.median_delta_min) not in {str, float}:
        raise TypeError
    if type(gate.median_delta_min) is float:
        _require_finite_float(gate.median_delta_min)
    for value in (
        gate.bootstrap_ci_low_min,
        gate.min_net_case_score,
        gate.max_case_loss_rate,
    ):
        if value is not None:
            _require_finite_float(value)
    initial = gate.initial_quality_expansion
    if initial is None:
        return
    _validate_model_instance(initial, InitialQualityExpansion)
    _require_finite_float(initial.min_net_case_score)
    _require_finite_float(initial.max_case_loss_rate)
    _require_exact(initial.require_ci_high_at_practical_delta, bool)


def _validate_time_limit_shapes(value: RuntimeTimeLimitConfig) -> None:
    if type(value.stage_defaults) is not dict or any(
        type(key) is not str or type(item) is not int or item <= 0
        for key, item in value.stage_defaults.items()
    ):
        raise TypeError
    _exact_sequence(value.rules, tuple, RuntimeTimeLimitRule)
    for rule in value.rules:
        _require_exact(rule.time_limit_sec, int)
        if rule.time_limit_sec <= 0:
            raise ValueError
        _exact_sequence(rule.stages, tuple, str)
        _exact_sequence(rule.case_globs, tuple, str)
        for bound in (rule.min_dimension, rule.max_dimension):
            if bound is not None:
                _require_exact(bound, int)
                if bound < 0:
                    raise ValueError


def _validate_readiness_shapes(value: MeasurementReadinessConfig) -> None:
    for text_value in (
        value.status,
        value.reason_code,
        value.signal_to_noise_tier,
        value.calibration_evidence_level,
    ):
        _require_exact(text_value, str)
    for count_value in (
        value.calibration_age_days,
        value.calibration_max_age_days,
        value.n_pairs,
    ):
        if count_value is not None:
            _require_exact(count_value, int)
    for float_value in (
        value.mde_at_power_80,
        value.noise_band_p90_abs,
        value.effect_to_mde_ratio,
    ):
        if float_value is not None:
            _require_finite_float(float_value)


def _exact_sequence(value: Any, container_type: type, item_type: type) -> None:
    if type(value) is not container_type:
        raise TypeError
    if any(
        type(item) is not item_type for item in cast(list[Any] | tuple[Any, ...], value)
    ):
        raise TypeError


def _require_exact(value: Any, expected_type: type) -> None:
    if type(value) is not expected_type:
        raise TypeError


def _require_finite_float(value: Any) -> None:
    _require_exact(value, float)
    if not math.isfinite(value):
        raise ValueError


def _is_bound_method(actual: Any, owner: Any, function: Any) -> bool:
    return (
        type(actual) is MethodType
        and getattr(actual, "__self__", None) is owner
        and getattr(actual, "__func__", None) is function
    )


def _validate_protocol_methods(protocol: ExperimentProtocol) -> None:
    surfaces = (
        (
            protocol,
            ExperimentProtocol,
            (
                "run_canary",
                "run_experiment",
                "_select_cases",
                "_select_seeds",
                "resolve_time_limit_sec",
                "time_limit_policy_summary",
                "_emit_progress",
                "_resolve_case_path",
                "_resolve_case_path_status",
                "_compare_objectives",
                "_compute_delta",
            ),
        ),
        (
            protocol.split_manager,
            SplitManager,
            ("get_cases", "get_canary_cases", "safe_data_roots"),
        ),
        (protocol.seed_ledger, SeedLedger, ("get_seeds", "get_canary_seeds")),
    )
    for instance, expected_type, names in surfaces:
        if not _has_exact_methods(instance, expected_type, names):
            raise TypeError


def _validate_protocol_wrapper_shape(protocol: Any) -> None:
    protocol_keys = {
        "config",
        "split_manager",
        "seed_ledger",
        "runner",
        "time_limit_sec",
        "metrics_dir",
        "_metric_specs",
        "_objective_policy",
        "_problem_spec",
        "_problem_adapter",
        "_strict_case_paths",
        "_progress_callback",
    }
    if type(protocol) is not ExperimentProtocol:
        raise TypeError
    _validate_storage_keys(protocol, protocol_keys)
    protocol_storage = vars(protocol)
    split_manager = protocol_storage["split_manager"]
    seed_ledger = protocol_storage["seed_ledger"]
    if type(split_manager) is not SplitManager or type(seed_ledger) is not SeedLedger:
        raise TypeError
    _validate_storage_keys(split_manager, {"_manifest"})
    _validate_storage_keys(seed_ledger, {"_ledger"})
    _validate_protocol_methods(protocol)


def _validate_pristine_storage_shapes(
    owner_storage: dict[str, Any],
    services: dict[str, Any],
) -> None:
    qualification = services["_qualification_runtime"]
    budget = services["_provider_call_budget"]
    proposal = services["_proposal_runtime_telemetry"]
    controller = services["_branch_ctrl"]
    campaign_loop = services["_campaign_loop"]
    proposal_pipeline = services["_proposal_pipeline"]
    explore_pipeline = services["_explore_step_pipeline"]
    _validate_storage_keys(
        qualification,
        {field.name for field in fields(QualificationRuntime)},
    )
    _validate_storage_keys(budget, {"_cap", "_used", "_by_request_kind", "_lock"})
    _validate_storage_keys(
        proposal,
        {
            "_provider_call_budget",
            "_max_hypothesis_candidates",
            "_attempts",
            "_active",
            "_lock",
        },
    )
    _validate_storage_keys(controller, {"_branches"})
    proposal_storage = vars(proposal_pipeline)
    explore_storage = vars(explore_pipeline)
    pipeline_keys = {
        "_hypothesis_rejection_counts",
        "_last_hypothesis_rejection_reason",
    }
    if not pipeline_keys.issubset(proposal_storage) or "_active_candidates" not in (
        explore_storage
    ):
        raise TypeError
    rejection_counts = proposal_storage["_hypothesis_rejection_counts"]
    last_rejection = proposal_storage["_last_hypothesis_rejection_reason"]
    raw_counts = budget._by_request_kind
    counters = (
        qualification.proposal_attempts,
        qualification.formal_screening_stages,
        qualification.initial_screening_stages,
        qualification.expanded_screening_stages,
    )
    if (
        type(qualification.started) is not bool
        or any(type(value) is not int for value in counters)
        or (
            qualification.pending_expansion_branch_id is not None
            and type(qualification.pending_expansion_branch_id) is not str
        )
        or type(qualification.verified_candidate_branch_ids) is not set
        or type(qualification.candidate_screening_stage_counts) is not dict
        or type(budget._cap) is not int
        or type(budget._used) is not int
        or type(raw_counts) is not dict
        or any(type(key) is not str for key in raw_counts)
        or any(type(value) is not int for value in raw_counts.values())
        or type(budget._lock) is not LockType
        or proposal._provider_call_budget is not budget
        or type(proposal._max_hypothesis_candidates) is not int
        or type(proposal._attempts) is not list
        or type(proposal._lock) is not LockType
        or type(controller._branches) is not dict
        or type(rejection_counts) is not dict
        or any(type(key) is not str for key in rejection_counts)
        or any(type(value) is not int for value in rejection_counts.values())
        or (last_rejection is not None and type(last_rejection) is not str)
        or type(explore_storage["_active_candidates"]) is not dict
        or type(owner_storage.get("_branch_workspaces")) is not dict
        or type(owner_storage.get("_branch_patches")) is not dict
        or type(owner_storage.get("_step_history")) is not list
        or type(owner_storage.get("_round_num")) is not int
        or type(owner_storage.get("_n_experiments")) is not int
        or type(owner_storage.get("_balance_exhausted")) is not bool
        or type(owner_storage.get("_external_stop_requested")) is not bool
        or type(owner_storage.get("_research_preflight_checked")) is not bool
        or type(owner_storage.get("_async_stop_deferral_depth")) is not int
        or type(campaign_loop.call_in_progress) is not bool
        or type(campaign_loop._post_return_deferral_active) is not bool
    ):
        raise TypeError


def _has_exact_methods(
    instance: Any,
    expected_type: type,
    names: tuple[str, ...],
) -> bool:
    if type(instance) is not expected_type:
        return False
    storage = vars(instance)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        return False
    return all(
        name not in storage
        and _is_bound_method(
            getattr(instance, name),
            instance,
            getattr(expected_type, name),
        )
        for name in names
    )


def _make_module_builtin_guard(
    module: Any,
    module_name: Any,
    sys_module: Any,
    modules: Any,
    names: Any,
    public_name: Any,
    names_name: Any = None,
    type_anchor: Any = type,
    vars_anchor: Any = vars,
    module_type: Any = ModuleType,
    dict_type: Any = dict,
    tuple_type: Any = tuple,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> Callable[[], None]:
    def validate() -> None:
        if (
            type_anchor(module) is not module_type
            or type_anchor(sys_module) is not module_type
            or type_anchor(module_name) is not str_type
            or type_anchor(modules) is not dict_type
            or type_anchor(names) is not tuple_type
            or type_anchor(public_name) is not str_type
            or (names_name is not None and type_anchor(names_name) is not str_type)
        ):
            raise error_type
        storage, sys_storage = vars_anchor(module), vars_anchor(sys_module)
        for value in (storage, sys_storage, modules):
            if type_anchor(value) is not dict_type:
                raise error_type
            for key in value:
                if type_anchor(key) is not str_type:
                    raise error_type
        if (
            type_anchor(storage.get("__name__")) is not str_type
            or storage["__name__"] != module_name
            or sys_storage.get("modules") is not modules
            or modules.get(module_name) is not module
            or (names_name is not None and storage.get(names_name) is not names)
            or storage.get(public_name) is not validate
        ):
            raise error_type
        for name in names:
            if type_anchor(name) is not str_type or name in storage:
                raise error_type

    return validate


_RESEARCH_VALIDATION_BUILTIN_NAMES = tuple(
    str.split(
        "BaseException TypeError ValueError all any bool bytes dict float int len list "
        "set str tuple type vars zip",
        " ",
    )
)


def _make_research_validation_builtin_guard(
    module: Any,
    sys_module: Any,
    modules: Any,
    names: Any = _RESEARCH_VALIDATION_BUILTIN_NAMES,
    vars_anchor: Any = vars,
) -> Callable[[], None]:
    return _make_module_builtin_guard(
        module,
        vars_anchor(module)["__name__"],
        sys_module,
        modules,
        names,
        "_validate_validation_builtin_guard",
    )


def _research_validation_anchor_items(value: Any) -> tuple[tuple[Any, Any], ...]:
    if type(value) is not dict:
        raise TypeError
    for key in value:
        if (
            type(key) is not tuple
            or len(key) != 2
            or type(key[0]) is not type
            or type(key[1]) is not str
        ):
            raise TypeError
    return tuple(value.items())


def _same_research_validation_anchor_items(value: Any, expected: Any) -> bool:
    if type(value) is not dict or type(expected) is not tuple:
        return False
    current = _research_validation_anchor_items(value)
    if len(current) != len(expected):
        return False
    for current_item, expected_item in zip(current, expected):
        if type(expected_item) is not tuple or len(expected_item) != 2:
            return False
        current_key, current_value = current_item
        expected_key, expected_value = expected_item
        if (
            type(expected_key) is not tuple
            or len(expected_key) != 2
            or current_key[0] is not expected_key[0]
            or current_key[1] != expected_key[1]
            or current_value is not expected_value
        ):
            return False
    return True


def _same_research_validation_key(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _same_research_validation_key(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    if type(left) is float:
        return left.hex() == right.hex()
    if left is None or type(left) in {str, bytes, bool, int}:
        return left == right
    return left is right


def _research_validation_class_surface(value: type[Any]) -> tuple[Any, ...]:
    if type(value) is not type:
        raise TypeError
    storage = vars(value)
    if type(storage) is not MappingProxyType or any(
        type(name) is not str for name in storage
    ):
        raise TypeError
    return (
        value,
        type.__getattribute__(value, "__name__"),
        type.__getattribute__(value, "__qualname__"),
        type.__getattribute__(value, "__module__"),
        type.__getattribute__(value, "__mro__"),
    )


def _research_validation_is_empty_tuple(value: Any) -> bool:
    return type(value) is tuple and len(value) == 0


def _research_validation_int_tuple(value: Any, length: int) -> bool:
    return (
        type(value) is tuple
        and len(value) == length
        and all(type(item) is int for item in value)
    )


def _research_validation_directory_fingerprints(value: Any) -> bool:
    return (
        type(value) is tuple
        and bool(value)
        and all(_research_validation_int_tuple(item, 2) for item in value)
    )
