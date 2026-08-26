"""Private config-subset carrier for an initial-screening-only study root."""

from __future__ import annotations

import json
import math
import os
import weakref
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Any, cast

from pydantic import BaseModel

from scion.config.problem import (
    ProtocolConfig,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.config.protocol_config import (
    MeasurementReadinessConfig,
    RuntimeTimeLimitConfig,
    ScreeningConfig,
    ScreeningGate,
)
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.evidence_recording.common import (
    reduced_measurement_readiness_payload,
)
from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _create_private_child_directory,
    _publish_controls,
)
from scion.core.initial_screening_study_controls_shapes import (
    _validate_dataclass_instance,
    _validate_manifest_and_ledger_shapes,
    _validate_model_instance,
    _validate_objective_shapes,
    _validate_protocol_config_tree,
    _validate_protocol_wrapper_shape,
)
from scion.core.models import ExperimentStage
from scion.core.qualification import QualificationOnlyConfig
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.scheduler import Scheduler
from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec
from scion.protocol.experiment import (
    ExperimentProtocol,
    SeedLedger,
    SplitManager,
)

_SCHEMA_VERSION = "scion.initial_screening_study_controls.config_subset.v1"
_SCOPE = "CONFIG_SUBSET_ONLY"
_FILENAME = "initial_screening_study_controls.json"
_MAX_BYTES = 1 << 20
_ERROR = "INITIAL_SCREENING_STUDY_CONTROLS_UNAVAILABLE"
_LIMITATIONS = (
    "PROBLEM_SPEC_UNVERIFIED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RESEARCH_HISTORY_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_REQUEST_POLICY_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)


class _InitialScreeningStudyControlsError(RuntimeError):
    """Fixed, body-free failure at the private controls boundary."""


@dataclass(frozen=True, repr=False)
class _InitialScreeningStudyControlsRequest:
    """Explicit private opt-in for one config-subset artifact."""

    requested_rounds: int

    def __repr__(self) -> str:
        return "_InitialScreeningStudyControlsRequest(<redacted>)"

    __str__ = __repr__

    def __post_init__(self) -> None:
        if type(self.requested_rounds) is not int or self.requested_rounds <= 0:
            raise _InitialScreeningStudyControlsError(_ERROR)


@dataclass(frozen=True, repr=False)
class _InitialScreeningRuntimeInputs:
    """Detached inputs shared by the artifact and installed runtime services."""

    requested_rounds: int
    qualification: QualificationOnlyConfig
    code_research_limits: CodeResearchLimits
    resource_envelope: ResourceEnvelope
    protocol_config: ProtocolConfig
    split_manifest: SplitManifest
    seed_ledger: SeedLedgerConfig
    experiment_protocol: ExperimentProtocol
    metric_specs: tuple[ObjectiveMetricSpec, ...]
    objective_policy: ObjectivePolicySpec
    scheduler: Scheduler
    payload_bytes: bytes
    publication: _ControlsPublication | None = None
    metrics_directory_fingerprint: tuple[int, int] | None = None

    def __repr__(self) -> str:
        return "_InitialScreeningRuntimeInputs(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _RegisteredControlsBaseline:
    """Independent immutable registration facts not exposed on the owner."""

    runtime_inputs_ref: weakref.ReferenceType[_InitialScreeningRuntimeInputs]
    requested_rounds: int
    payload_bytes: bytes
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]
    metrics_directory_fingerprint: tuple[int, int]
    qualification_ref: weakref.ReferenceType[Any]
    code_research_limits_ref: weakref.ReferenceType[Any]
    resource_envelope_ref: weakref.ReferenceType[Any]
    protocol_config_ref: weakref.ReferenceType[Any]
    split_manifest_ref: weakref.ReferenceType[Any]
    seed_ledger_ref: weakref.ReferenceType[Any]
    experiment_protocol_ref: weakref.ReferenceType[Any]
    metric_specs: tuple[ObjectiveMetricSpec, ...]
    objective_policy_ref: weakref.ReferenceType[Any]
    scheduler_ref: weakref.ReferenceType[Any]

    def __repr__(self) -> str:
        return "_RegisteredControlsBaseline(<redacted>)"

    __str__ = __repr__


_REGISTERED_OWNERS: weakref.WeakKeyDictionary[Any, _RegisteredControlsBaseline]
_REGISTERED_OWNERS = weakref.WeakKeyDictionary()


def _prepare_initial_screening_runtime_inputs(
    *,
    request: _InitialScreeningStudyControlsRequest,
    qualification: QualificationOnlyConfig | None,
    code_research_limits: CodeResearchLimits | None,
    resource_envelope: ResourceEnvelope | None,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    experiment_protocol: Any,
    campaign_dir: str,
) -> _InitialScreeningRuntimeInputs:
    """Normalize one exact private subset without retaining caller aliases."""

    failed = False
    value: _InitialScreeningRuntimeInputs | None = None
    try:
        value = _prepare_unchecked(
            request=request,
            qualification=qualification,
            code_research_limits=code_research_limits,
            resource_envelope=resource_envelope,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            experiment_protocol=experiment_protocol,
            campaign_dir=campaign_dir,
        )
    except Exception:  # noqa: BLE001 - sanitize the private opt-in boundary
        failed = True
    if failed or value is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return value


def _prepare_unchecked(
    *,
    request: _InitialScreeningStudyControlsRequest,
    qualification: QualificationOnlyConfig | None,
    code_research_limits: CodeResearchLimits | None,
    resource_envelope: ResourceEnvelope | None,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    experiment_protocol: Any,
    campaign_dir: str,
) -> _InitialScreeningRuntimeInputs:
    request_storage = (
        vars(request)
        if type(request) is _InitialScreeningStudyControlsRequest
        else None
    )
    if (
        type(request) is not _InitialScreeningStudyControlsRequest
        or type(request_storage) is not dict
        or any(type(key) is not str for key in request_storage)
        or set(request_storage) != {"requested_rounds"}
        or type(request.requested_rounds) is not int
        or request.requested_rounds <= 0
    ):
        raise TypeError
    frozen_qualification = _freeze_qualification(request, qualification)
    frozen_code_limits = _freeze_code_limits(code_research_limits)
    frozen_resource = _freeze_resource_envelope(resource_envelope)
    (
        frozen_config,
        frozen_manifest,
        frozen_ledger,
        frozen_protocol,
        frozen_metrics,
        frozen_objective,
    ) = _freeze_protocol_controls(
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        experiment_protocol=experiment_protocol,
        campaign_dir=campaign_dir,
    )
    scheduler = Scheduler()
    encoded = _runtime_payload_bytes(
        requested_rounds=request.requested_rounds,
        qualification=frozen_qualification,
        code_research_limits=frozen_code_limits,
        resource_envelope=frozen_resource,
        scheduler=scheduler,
        experiment_protocol=frozen_protocol,
    )
    return _InitialScreeningRuntimeInputs(
        requested_rounds=request.requested_rounds,
        qualification=frozen_qualification,
        code_research_limits=frozen_code_limits,
        resource_envelope=frozen_resource,
        protocol_config=frozen_config,
        split_manifest=frozen_manifest,
        seed_ledger=frozen_ledger,
        experiment_protocol=frozen_protocol,
        metric_specs=frozen_metrics,
        objective_policy=frozen_objective,
        scheduler=scheduler,
        payload_bytes=encoded,
    )


def _freeze_qualification(
    request: _InitialScreeningStudyControlsRequest,
    qualification: QualificationOnlyConfig | None,
) -> QualificationOnlyConfig:
    if type(qualification) is not QualificationOnlyConfig:
        raise TypeError
    qualification_value = cast(QualificationOnlyConfig, qualification)
    _validate_dataclass_instance(qualification_value, QualificationOnlyConfig)
    if not qualification_value.initial_screening_only:
        raise ValueError
    limits = _qualification_projection(qualification_value)
    qualification_keys = {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    }
    if set(limits) != qualification_keys:
        raise ValueError
    cap_values = tuple(limits[key] for key in sorted(qualification_keys))
    if (
        len(cap_values) != 3
        or any(type(value) is not int or value <= 0 for value in cap_values)
        or len(set(cap_values)) != 1
        or request.requested_rounds != cap_values[0]
    ):
        raise ValueError
    return replace(
        qualification_value,
        max_proposal_attempts=qualification_value.max_proposal_attempts,
        max_verified_candidate_chains=(
            qualification_value.max_verified_candidate_chains
        ),
        max_formal_screening_stages=(qualification_value.max_formal_screening_stages),
        development_boundary_mode=qualification_value.development_boundary_mode,
    )


def _freeze_code_limits(
    value: CodeResearchLimits | None,
) -> CodeResearchLimits:
    if type(value) is not CodeResearchLimits:
        raise TypeError
    code_limits = cast(CodeResearchLimits, value)
    return replace(code_limits, **_code_limits_projection(code_limits))


def _freeze_resource_envelope(
    value: ResourceEnvelope | None,
) -> ResourceEnvelope:
    if type(value) is not ResourceEnvelope:
        raise TypeError
    resource_value = cast(ResourceEnvelope, value)
    resource = _validated_resource_projection(resource_value)
    return replace(resource_value, **resource)


def _freeze_protocol_controls(
    *,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    experiment_protocol: Any,
    campaign_dir: str,
) -> tuple[
    ProtocolConfig,
    SplitManifest,
    SeedLedgerConfig,
    ExperimentProtocol,
    tuple[ObjectiveMetricSpec, ...],
    ObjectivePolicySpec,
]:
    if type(protocol_config) is not ProtocolConfig:
        raise TypeError
    if type(split_manifest) is not SplitManifest:
        raise TypeError
    if type(seed_ledger) is not SeedLedgerConfig:
        raise TypeError
    if type(experiment_protocol) is not ExperimentProtocol:
        raise TypeError
    _validate_protocol_wrapper_shape(experiment_protocol)
    if type(getattr(experiment_protocol, "_strict_case_paths", None)) is not bool or (
        not experiment_protocol._strict_case_paths
    ):
        raise ValueError
    if (
        type(campaign_dir) is not str
        or not os.path.isabs(campaign_dir)
        or os.path.normpath(campaign_dir) != campaign_dir
        or "\x00" in campaign_dir
    ):
        raise ValueError

    actual_config = experiment_protocol.config
    actual_manifest = getattr(experiment_protocol.split_manager, "_manifest", None)
    actual_ledger = getattr(experiment_protocol.seed_ledger, "_ledger", None)
    _validate_protocol_config_tree(protocol_config)
    _validate_protocol_config_tree(actual_config)
    _validate_manifest_and_ledger_shapes(split_manifest, seed_ledger)
    _validate_manifest_and_ledger_shapes(actual_manifest, actual_ledger)
    if not _same_model(protocol_config, actual_config):
        raise ValueError
    if not _same_model(split_manifest, actual_manifest):
        raise ValueError
    if not _same_model(seed_ledger, actual_ledger):
        raise ValueError

    frozen_config = cast(
        ProtocolConfig,
        _model_validate_exact(
            ProtocolConfig,
            _model_dump_exact(protocol_config, ProtocolConfig, mode="python"),
        ),
    )
    frozen_manifest = cast(
        SplitManifest,
        _model_validate_exact(
            SplitManifest,
            _model_dump_exact(split_manifest, SplitManifest, mode="python"),
        ),
    )
    frozen_ledger = cast(
        SeedLedgerConfig,
        _model_validate_exact(
            SeedLedgerConfig,
            _model_dump_exact(seed_ledger, SeedLedgerConfig, mode="python"),
        ),
    )
    frozen_metrics, frozen_objective = _freeze_objectives(experiment_protocol)
    frozen_protocol = ExperimentProtocol(
        protocol_config=frozen_config,
        split_manager=SplitManager(frozen_manifest),
        seed_ledger=SeedLedger(frozen_ledger),
        runner=experiment_protocol.runner,
        time_limit_sec=_positive_int(experiment_protocol.time_limit_sec),
        metrics_dir=os.path.join(campaign_dir, "metrics"),
        metric_specs=frozen_metrics,
        objective_policy=frozen_objective,
        problem_spec=experiment_protocol.problem_spec,
    )
    frozen_protocol._strict_case_paths = True
    return (
        frozen_config,
        frozen_manifest,
        frozen_ledger,
        frozen_protocol,
        frozen_metrics,
        frozen_objective,
    )


def _runtime_payload_bytes(
    *,
    requested_rounds: int,
    qualification: QualificationOnlyConfig,
    code_research_limits: CodeResearchLimits,
    resource_envelope: ResourceEnvelope,
    scheduler: Scheduler,
    experiment_protocol: ExperimentProtocol,
) -> bytes:
    _validate_runtime_payload_types(
        code_research_limits=code_research_limits,
        scheduler=scheduler,
        experiment_protocol=experiment_protocol,
    )
    limits = _validated_qualification_projection(qualification, requested_rounds)
    resource = _validated_resource_projection(resource_envelope)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "scope": _SCOPE,
        "limitations": list(_LIMITATIONS),
        "campaign": {
            "campaign_mode": "qualification_only",
            "development_boundary_mode": "initial_screening_only_v1",
            "requested_rounds": requested_rounds,
            "qualification_limits": limits,
            "scheduler": {
                "max_active_branches": scheduler.max_active_branches,
            },
        },
        "code_research_limits": _code_limits_projection(code_research_limits),
        "resource_envelope": resource,
        "protocol": _protocol_projection(experiment_protocol),
    }
    return _canonical_json_bytes(payload)


def _validate_runtime_payload_types(
    *,
    code_research_limits: CodeResearchLimits,
    scheduler: Scheduler,
    experiment_protocol: ExperimentProtocol,
) -> None:
    if (
        type(code_research_limits) is not CodeResearchLimits
        or type(scheduler) is not Scheduler
        or type(scheduler.max_active_branches) is not int
        or scheduler.max_active_branches <= 0
        or type(experiment_protocol) is not ExperimentProtocol
    ):
        raise TypeError


def _validated_qualification_projection(
    qualification: QualificationOnlyConfig,
    requested_rounds: int,
) -> dict[str, int]:
    _validate_dataclass_instance(qualification, QualificationOnlyConfig)
    if (
        type(requested_rounds) is not int
        or requested_rounds <= 0
        or qualification.development_boundary_mode != "initial_screening_only_v1"
        or not qualification.initial_screening_only
    ):
        raise ValueError
    limits = _qualification_projection(qualification)
    keys = {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    }
    if set(limits) != keys or any(
        type(limits[key]) is not int or limits[key] != requested_rounds for key in keys
    ):
        raise ValueError
    return limits


def _validated_resource_projection(
    resource_envelope: ResourceEnvelope,
) -> dict[str, int]:
    resource = _resource_projection(resource_envelope)
    if set(resource) != {"provider_call_cap", "outer_hardwall_sec"} or any(
        type(value) is not int or value <= 0 for value in resource.values()
    ):
        raise ValueError
    return resource


def _same_model(expected: Any, actual: Any) -> bool:
    expected_type = type(expected)
    return expected_type is type(actual) and _model_dump_exact(
        expected,
        expected_type,
        mode="json",
    ) == _model_dump_exact(actual, expected_type, mode="json")


def _qualification_projection(value: QualificationOnlyConfig) -> dict[str, int]:
    _validate_dataclass_instance(value, QualificationOnlyConfig)
    return QualificationOnlyConfig.to_projection(value)


def _code_limits_projection(value: CodeResearchLimits) -> dict[str, int]:
    _validate_dataclass_instance(value, CodeResearchLimits)
    return CodeResearchLimits.to_primitive(value)


def _resource_projection(value: ResourceEnvelope) -> dict[str, int]:
    _validate_dataclass_instance(value, ResourceEnvelope)
    return ResourceEnvelope.to_primitive(value)


def _model_dump_exact(
    value: Any,
    expected_type: type[BaseModel],
    *,
    mode: str,
) -> dict[str, Any]:
    _validate_model_instance(value, expected_type)
    result = BaseModel.model_dump(value, mode=mode)
    if type(result) is not dict:
        raise TypeError
    return result


def _model_validate_exact(expected_type: type[Any], value: dict[str, Any]) -> Any:
    return expected_type.model_validate(value)


def _freeze_objectives(
    protocol: ExperimentProtocol,
) -> tuple[tuple[ObjectiveMetricSpec, ...], ObjectivePolicySpec]:
    raw_metrics = getattr(protocol, "_metric_specs", None)
    raw_policy = getattr(protocol, "_objective_policy", None)
    if type(raw_metrics) is not tuple or not raw_metrics:
        raise TypeError
    if any(type(metric) is not ObjectiveMetricSpec for metric in raw_metrics):
        raise TypeError
    if type(raw_policy) is not ObjectivePolicySpec:
        raise TypeError
    policy_value = cast(ObjectivePolicySpec, raw_policy)
    _validate_objective_shapes(raw_metrics, policy_value)
    metrics = tuple(
        ObjectiveMetricSpec.model_validate(
            _model_dump_exact(metric, ObjectiveMetricSpec, mode="python")
        )
        for metric in raw_metrics
    )
    policy = cast(
        ObjectivePolicySpec,
        _model_validate_exact(
            ObjectivePolicySpec,
            _model_dump_exact(policy_value, ObjectivePolicySpec, mode="python"),
        ),
    )
    return metrics, policy


def _protocol_projection(protocol: ExperimentProtocol) -> dict[str, Any]:
    if type(protocol) is not ExperimentProtocol:
        raise TypeError
    _validate_protocol_wrapper_shape(protocol)
    if type(getattr(protocol, "_strict_case_paths", None)) is not bool or (
        not protocol._strict_case_paths
    ):
        raise ValueError
    config = protocol.config
    _validate_protocol_config_tree(config)
    _validate_manifest_and_ledger_shapes(
        protocol.split_manager._manifest,
        protocol.seed_ledger._ledger,
    )
    objective_policy = getattr(protocol, "_objective_policy", None)
    if type(objective_policy) is not ObjectivePolicySpec:
        raise TypeError
    _validate_objective_shapes(
        getattr(protocol, "_metric_specs", None),
        objective_policy,
    )
    modify_cases, create_cases, initial_seeds, canary_cases, canary_seeds = (
        _protocol_rosters(protocol, config)
    )

    screening = config.screening
    gate = config.gates.screening
    time_limits = config.runtime.time_limits
    readiness = config.measurement_readiness
    if (
        type(screening) is not ScreeningConfig
        or type(gate) is not ScreeningGate
        or type(time_limits) is not RuntimeTimeLimitConfig
        or type(readiness) is not MeasurementReadinessConfig
    ):
        raise TypeError
    fallback = _positive_int(protocol.time_limit_sec)
    metrics = _metric_projection(getattr(protocol, "_metric_specs", None))
    objective = _objective_projection(getattr(protocol, "_objective_policy", None))
    projection = {
        "version": _text(config.version, allow_empty=False),
        "strict_case_paths": True,
        "safe_data_roots": _absolute_roots(protocol.split_manager.safe_data_roots()),
        "initial_screening": {
            "cases_by_action": {
                "modify_or_remove": list(modify_cases),
                "create_new": list(create_cases),
            },
            "seeds": list(initial_seeds),
            "selection": _json_value(
                _model_dump_exact(screening, ScreeningConfig, mode="json")
            ),
            "screening_gate": {
                "configured": _json_value(
                    _model_dump_exact(gate, ScreeningGate, mode="json")
                ),
                "resolved_median_delta_min": _finite_float(
                    config.screening_min_practical_delta
                ),
            },
            "effect_policy": {
                "case_aggregation": config.case_aggregation,
                "case_equivalence_band": _finite_float(config.case_equivalence_band),
                "effect_metric": _text(config.effect_metric, allow_empty=True),
                "protected_objectives": _unique_texts(config.protected_objectives),
                "pairing_validity": config.pairing_validity,
                "measurement_governance": config.measurement_governance,
                "runtime_model": config.runtime.runtime_model,
                "max_runtime_ratio": _finite_float(config.runtime.max_runtime_ratio),
                "tie_speedup_ratio": _finite_float(config.runtime.tie_speedup_ratio),
                "tie_min_runtime_pairs": _positive_int(
                    config.runtime.tie_min_runtime_pairs
                ),
                "metric_specs": metrics,
                "objective_policy": objective,
            },
            "measurement_readiness": _json_value(
                reduced_measurement_readiness_payload(
                    _model_dump_exact(
                        readiness,
                        MeasurementReadinessConfig,
                        mode="json",
                    )
                )
            ),
            "runtime_time_limits": _json_value(
                _model_dump_exact(
                    time_limits,
                    RuntimeTimeLimitConfig,
                    mode="json",
                )
            ),
            "resolved_time_limits": _resolved_limits(
                protocol,
                stage=ExperimentStage.SCREENING,
                cases=modify_cases,
            ),
        },
        "canary": {
            "cases": list(canary_cases),
            "seeds": list(canary_seeds),
            "resolved_time_limits": _resolved_limits(
                protocol,
                stage="canary",
                cases=canary_cases,
            ),
        },
        "time_limit_fallback_sec": fallback,
    }
    return _json_value(projection)


def _protocol_rosters(
    protocol: ExperimentProtocol,
    config: ProtocolConfig,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[int, ...],
    tuple[str, ...],
    tuple[int, ...],
]:
    modify_cases = _case_refs(
        protocol._select_cases(ExperimentStage.SCREENING, "modify", 0)
    )
    create_cases = _case_refs(
        protocol._select_cases(ExperimentStage.SCREENING, "create_new", 0)
    )
    initial_seeds = _seeds(
        protocol._select_seeds(ExperimentStage.SCREENING, expanded=False)
    )
    canary_cases = _case_refs(protocol.split_manager.get_canary_cases())
    canary_seeds = _seeds(protocol.seed_ledger.get_canary_seeds())
    basenames = [PurePosixPath(value).name for value in (*modify_cases, *canary_cases)]
    invalid = (
        modify_cases != create_cases,
        tuple(config.canary.cases) != canary_cases,
        tuple(config.canary.seeds) != canary_seeds,
        bool(set(modify_cases) & set(canary_cases)),
        bool(set(initial_seeds) & set(canary_seeds)),
        len(basenames) != len(set(basenames)),
    )
    if any(invalid):
        raise ValueError
    return modify_cases, create_cases, initial_seeds, canary_cases, canary_seeds


def _metric_projection(values: Any) -> list[dict[str, Any]]:
    _validate_objective_shapes(values, None)
    result: list[dict[str, Any]] = []
    for value in values:
        if type(value) is not ObjectiveMetricSpec:
            raise TypeError
        if (
            type(value.name) is not str
            or type(value.direction) is not str
            or type(value.priority) is not int
            or type(value.tie_tolerance) is not float
            or (value.weight is not None and type(value.weight) is not float)
        ):
            raise TypeError
        result.append(
            _json_value(_model_dump_exact(value, ObjectiveMetricSpec, mode="json"))
        )
    return result


def _objective_projection(value: Any) -> dict[str, Any]:
    if type(value) is not ObjectivePolicySpec:
        raise TypeError
    if type(value.mode) is not str or type(value.expose_weights_to_llm) is not bool:
        raise TypeError
    return _json_value(_model_dump_exact(value, ObjectivePolicySpec, mode="json"))


def _absolute_roots(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if type(value) is not str or not value or "\x00" in value:
            raise TypeError
        if not os.path.isabs(value) or os.path.normpath(value) != value:
            raise ValueError
        result.append(value)
    if len(result) != len(set(result)):
        raise ValueError
    return result


def _case_refs(values: Any) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if type(value) is not str or not value or len(value) > 4096:
            raise TypeError
        if "\x00" in value or "\\" in value or value.startswith("/"):
            raise ValueError
        if any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError
        normalized = PurePosixPath(value).as_posix()
        if normalized != value:
            raise ValueError
        result.append(value)
    if not result or len(result) != len(set(result)):
        raise ValueError
    return tuple(result)


def _seeds(values: Any) -> tuple[int, ...]:
    result = tuple(values)
    if (
        not result
        or any(type(value) is not int or value < 0 for value in result)
        or len(result) != len(set(result))
    ):
        raise ValueError
    return result


def _resolved_limits(
    protocol: ExperimentProtocol,
    *,
    stage: ExperimentStage | str,
    cases: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "case_ref": case,
            "time_limit_sec": _positive_int(
                protocol.resolve_time_limit_sec(stage=stage, case_path=case)
            ),
        }
        for case in cases
    ]


def _text(value: Any, *, allow_empty: bool) -> str:
    if type(value) is not str or len(value) > 4096 or "\x00" in value:
        raise TypeError
    if not allow_empty and not value:
        raise ValueError
    return value


def _unique_texts(values: Any) -> list[str]:
    result = [_text(value, allow_empty=False) for value in values]
    if len(result) != len(set(result)):
        raise ValueError
    return result


def _positive_int(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise TypeError
    return value


def _finite_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError
    result = float(value)
    if not math.isfinite(result):
        raise ValueError
    return result


def _json_value(value: Any) -> Any:
    if value is None or type(value) in {str, bool, int}:
        return value
    if isinstance(value, float):
        return _finite_float(value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise TypeError
        return {key: _json_value(item) for key, item in value.items()}
    raise TypeError


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    encoded = (
        json.dumps(
            _json_value(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > _MAX_BYTES:
        raise ValueError
    return encoded


def _write_initial_screening_study_controls(
    campaign_dir: str,
    payload: bytes,
    *,
    protected_roots: tuple[str, ...],
) -> _ControlsPublication:
    """Create the campaign root and publish its first literal leaf safely."""

    failed = False
    publication: _ControlsPublication | None = None
    try:
        publication = _publish_controls(
            campaign_dir,
            payload,
            protected_roots=protected_roots,
            filename=_FILENAME,
            max_bytes=_MAX_BYTES,
        )
    except Exception:  # noqa: BLE001 - sanitize the private publication boundary
        failed = True
    if failed or publication is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return publication


def _bind_controls_publication(
    runtime_inputs: _InitialScreeningRuntimeInputs,
    publication: _ControlsPublication,
) -> _InitialScreeningRuntimeInputs:
    if (
        type(runtime_inputs) is not _InitialScreeningRuntimeInputs
        or type(publication) is not _ControlsPublication
    ):
        raise _InitialScreeningStudyControlsError(_ERROR)
    return replace(runtime_inputs, publication=publication)


def _bind_controls_metrics_directory(
    runtime_inputs: _InitialScreeningRuntimeInputs,
) -> _InitialScreeningRuntimeInputs:
    failed = False
    fingerprint: tuple[int, int] | None = None
    try:
        if (
            type(runtime_inputs) is not _InitialScreeningRuntimeInputs
            or type(runtime_inputs.publication) is not _ControlsPublication
            or runtime_inputs.metrics_directory_fingerprint is not None
        ):
            raise TypeError
        fingerprint = _create_private_child_directory(
            runtime_inputs.publication,
            "metrics",
        )
    except Exception:  # noqa: BLE001 - sanitize the private publication boundary
        failed = True
    if failed or fingerprint is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return replace(runtime_inputs, metrics_directory_fingerprint=fingerprint)


def _register_initial_screening_controls_owner(
    owner: Any,
    runtime_inputs: _InitialScreeningRuntimeInputs,
) -> None:
    publication = runtime_inputs.publication
    metrics_fingerprint = runtime_inputs.metrics_directory_fingerprint
    if (
        type(runtime_inputs) is not _InitialScreeningRuntimeInputs
        or type(publication) is not _ControlsPublication
        or type(metrics_fingerprint) is not tuple
        or len(metrics_fingerprint) != 2
        or any(type(value) is not int for value in metrics_fingerprint)
        or owner in _REGISTERED_OWNERS
    ):
        raise _InitialScreeningStudyControlsError(_ERROR)
    publication_value = cast(_ControlsPublication, publication)
    metrics_value = cast(tuple[int, int], metrics_fingerprint)
    _REGISTERED_OWNERS[owner] = _RegisteredControlsBaseline(
        runtime_inputs_ref=weakref.ref(runtime_inputs),
        requested_rounds=runtime_inputs.requested_rounds,
        payload_bytes=bytes(runtime_inputs.payload_bytes),
        campaign_dir=publication_value.campaign_dir,
        directory_fingerprints=publication_value.directory_fingerprints,
        leaf_fingerprint=publication_value.leaf_fingerprint,
        metrics_directory_fingerprint=metrics_value,
        qualification_ref=weakref.ref(runtime_inputs.qualification),
        code_research_limits_ref=weakref.ref(runtime_inputs.code_research_limits),
        resource_envelope_ref=weakref.ref(runtime_inputs.resource_envelope),
        protocol_config_ref=weakref.ref(runtime_inputs.protocol_config),
        split_manifest_ref=weakref.ref(runtime_inputs.split_manifest),
        seed_ledger_ref=weakref.ref(runtime_inputs.seed_ledger),
        experiment_protocol_ref=weakref.ref(runtime_inputs.experiment_protocol),
        metric_specs=runtime_inputs.metric_specs,
        objective_policy_ref=weakref.ref(runtime_inputs.objective_policy),
        scheduler_ref=weakref.ref(runtime_inputs.scheduler),
    )
