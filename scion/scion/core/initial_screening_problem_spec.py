"""Private producer boundary for an initial-screening problem declaration."""

from __future__ import annotations

import json
import math
import sys
import weakref
from dataclasses import dataclass, replace
from types import MappingProxyType, ModuleType
from typing import Any, cast

from pydantic import BaseModel

from scion.config import problem as legacy_problem_schema
from scion.config.problem import ProblemSpec
from scion.core.initial_screening_problem_spec_anchors import (
    _bridge_storage,
    _model_field_names,
    _validate_all_model_surfaces,
    _validate_bridge_class_surface,
    _validate_model_field_surface,
)
from scion.problem import bridge as problem_bridge_module
from scion.problem import spec as problem_spec_schema
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.contracts import ProblemAdapter
from scion.problem.spec import ProblemSpecV1
from scion.protocol.experiment import ExperimentProtocol

_ERROR = "INITIAL_SCREENING_PROBLEM_SPEC_UNAVAILABLE"
_FILENAME = "initial_screening_problem_spec.json"
_MAX_BYTES = 1 << 20
_MAX_JSON_DEPTH = 23
_SCHEMA_VERSION = "scion.initial_screening_problem_spec.declaration.v1"
_SCOPE = "PROBLEM_SPEC_DECLARATION_ONLY"
_LIMITATIONS = (
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_PROBLEM_SPEC_V1_FIELDS = (
    "spec_version",
    "id",
    "display_name",
    "root_dir",
    "description",
    "search_space",
    "solver",
    "parameter_search",
    "operator_interface",
    "research_surfaces",
    "objective_policy",
    "objectives",
    "measurement",
    "llm_hints",
    "family_taxonomy",
    "runtime_dependencies",
    "runtime_failure_guidance",
    "adapter",
    "operators_dir",
    "data_dir",
    "oracle_path",
    "solver_path",
    "canary_case_path",
    "unit_test_path",
    "regression_test_path",
    "development_unit_test_path",
    "development_regression_test_path",
    "development_unit_test_support_paths",
    "development_regression_test_support_paths",
    "development_workspace_paths",
    "development_problem_package_paths",
)
_PROJECTION_KEYS = tuple(name for name in _PROBLEM_SPEC_V1_FIELDS if name != "root_dir")
_PROBLEM_MODEL_TYPES = frozenset(
    value
    for value in vars(problem_spec_schema).values()
    if isinstance(value, type) and issubclass(value, BaseModel)
)
_LEGACY_MODEL_TYPES = frozenset(
    value
    for value in vars(legacy_problem_schema).values()
    if isinstance(value, type) and issubclass(value, BaseModel)
)
_BRIDGE_PROBLEM_SPEC_V1 = bridge_problem_spec_v1
_LEGACY_PROBLEM_SPEC_FROM_V1 = problem_bridge_module.legacy_problem_spec_from_v1
_BRIDGE_DEPENDENCIES = {
    name: vars(problem_bridge_module)[name]
    for name in (
        "ProblemSpecBridge",
        "ProblemSpec",
        "SearchSpace",
        "SolverConfig",
        "ParameterSearchConfig",
        "legacy_problem_spec_from_v1",
        "_parameter_search_from_v1",
        "_resolve_optional_file",
    )
}
_MODEL_VALIDATE = BaseModel.model_validate.__func__
_PROBLEM_SPEC_V1_VALIDATOR = ProblemSpecV1.__pydantic_validator__
_EXPERIMENT_PROTOCOL_INIT = ExperimentProtocol.__init__


class _Redacted:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _InitialScreeningProblemSpecRequest(_Redacted):
    """Zero-value package-private opt-in marker."""


@dataclass(frozen=True, repr=False)
class _ProblemSpecPublication(_Redacted):
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]


@dataclass(frozen=True, repr=False)
class _InitialScreeningProblemSpecInputs(_Redacted):
    spec_v1: ProblemSpecV1
    problem_spec: ProblemSpec
    adapter: Any
    metric_specs: tuple[Any, ...]
    objective_policy: Any
    operator_execute_signature: str
    payload_bytes: bytes
    root_dir: str
    adapter_class_fingerprint: tuple[Any, ...]
    frozen_value_key: tuple[Any, ...]
    publication: _ProblemSpecPublication | None = None


@dataclass(frozen=True, repr=False)
class _RegisteredProblemSpecBaseline(_Redacted):
    runtime_inputs_ref: weakref.ReferenceType[_InitialScreeningProblemSpecInputs]
    spec_v1_ref: weakref.ReferenceType[ProblemSpecV1]
    problem_spec_ref: weakref.ReferenceType[ProblemSpec]
    adapter_ref: weakref.ReferenceType[Any]
    payload_bytes: bytes
    root_dir: str
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]
    adapter_class_fingerprint: tuple[Any, ...]
    frozen_value_key: tuple[Any, ...]


class _InitialScreeningProblemSpecError(RuntimeError):
    """Fixed body-free error at the private declaration boundary."""


_REGISTERED_OWNERS: weakref.WeakKeyDictionary[Any, _RegisteredProblemSpecBaseline] = (
    weakref.WeakKeyDictionary()
)


def _canonical_problem_spec_payload(spec_v1: ProblemSpecV1) -> bytes:
    """Return the exact root-dir-free declaration bytes for a frozen V1 spec."""

    _validate_problem_spec_v1_shape(spec_v1)
    projection = _project_model(spec_v1)
    if _model_field_names(ProblemSpecV1) != _PROBLEM_SPEC_V1_FIELDS:
        raise TypeError
    if set(projection) != set(_PROBLEM_SPEC_V1_FIELDS):
        raise TypeError
    projection.pop("root_dir")
    if set(projection) != set(_PROJECTION_KEYS):
        raise TypeError
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "scope": _SCOPE,
        "limitations": list(_LIMITATIONS),
        "problem_spec_v1": projection,
    }
    _validate_problem_payload_json(payload)
    encoded = (
        json.dumps(
            payload,
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


def _prepare_initial_screening_problem_spec(
    request: Any,
    controls_request: Any,
    provider_request: Any,
    problem_spec: Any,
    adapter: Any,
    operator_execute_signature: Any,
) -> _InitialScreeningProblemSpecInputs | None:
    """Freeze the exact declaration authority before campaign-root IO."""

    if request is None:
        return None
    failed = False
    result: _InitialScreeningProblemSpecInputs | None = None
    try:
        if type(request) is not _InitialScreeningProblemSpecRequest:
            raise TypeError
        request_storage = vars(request)
        if (
            type(request_storage) is not dict
            or any(type(key) is not str for key in request_storage)
            or request_storage
        ):
            raise TypeError
        from scion.core.initial_screening_study_controls import (
            _InitialScreeningStudyControlsRequest,
        )
        from scion.core.initial_screening_study_provider_policy import (
            _InitialScreeningProviderPolicyRequest,
        )

        if (
            type(controls_request) is not _InitialScreeningStudyControlsRequest
            or type(provider_request) is not _InitialScreeningProviderPolicyRequest
        ):
            raise TypeError
        result = _freeze_problem_spec_inputs(
            problem_spec,
            adapter,
            operator_execute_signature,
        )
    except Exception:  # noqa: BLE001 - fixed private preparation boundary
        failed = True
    if failed or result is None:
        raise _InitialScreeningProblemSpecError(_ERROR)
    return result


def _problem_spec_protocol_input(
    source: Any,
    runtime_inputs: _InitialScreeningProblemSpecInputs,
) -> Any:
    """Build a pre-controls protocol carrying the fresh bridge authorities."""

    from scion.core.initial_screening_study_controls_shapes import (
        _validate_protocol_wrapper_shape,
    )

    if type(runtime_inputs) is not _InitialScreeningProblemSpecInputs:
        raise _InitialScreeningProblemSpecError(_ERROR)
    try:
        _validate_protocol_wrapper_shape(source)
        source_storage = _storage(source)
        source_problem_spec = source_storage["_problem_spec"]
        if type(source_problem_spec) is not ProblemSpec or _freeze_tree(
            source_problem_spec
        ) != _freeze_tree(runtime_inputs.problem_spec):
            raise ValueError
        if _freeze_tree(source_storage["_metric_specs"]) != _freeze_tree(
            runtime_inputs.metric_specs
        ) or _freeze_tree(source_storage["_objective_policy"]) != _freeze_tree(
            runtime_inputs.objective_policy
        ):
            raise ValueError
        before = _problem_inputs_pristine_key(runtime_inputs)
        if ExperimentProtocol.__init__ is not _EXPERIMENT_PROTOCOL_INIT:
            raise TypeError
        replacement = ExperimentProtocol(
            protocol_config=source_storage["config"],
            split_manager=source_storage["split_manager"],
            seed_ledger=source_storage["seed_ledger"],
            runner=source_storage["runner"],
            time_limit_sec=source_storage["time_limit_sec"],
            metrics_dir=source_storage["metrics_dir"],
            metric_specs=runtime_inputs.metric_specs,
            objective_policy=runtime_inputs.objective_policy,
            problem_spec=runtime_inputs.problem_spec,
        )
        replacement._strict_case_paths = source_storage["_strict_case_paths"]
        _validate_protocol_wrapper_shape(replacement)
        replacement_storage = _storage(replacement)
        if (
            replacement is source
            or replacement_storage["_problem_spec"] is not runtime_inputs.problem_spec
            or replacement_storage["_objective_policy"]
            is not runtime_inputs.objective_policy
            or _freeze_tree(replacement_storage["_metric_specs"])
            != _freeze_tree(runtime_inputs.metric_specs)
            or not _same_frozen_key(
                _problem_inputs_pristine_key(runtime_inputs), before
            )
        ):
            raise ValueError
        return replacement
    except Exception:  # noqa: BLE001 - fixed private preparation boundary
        raise _InitialScreeningProblemSpecError(_ERROR) from None


def _publish_initial_screening_problem_spec(
    runtime_inputs: _InitialScreeningProblemSpecInputs,
    controls_inputs: Any,
    provider_inputs: Any,
) -> _InitialScreeningProblemSpecInputs:
    """Attach the declaration as the exact third private leaf."""

    failed = False
    result: _InitialScreeningProblemSpecInputs | None = None
    try:
        from scion.core.initial_screening_problem_spec_io import (
            _publish_third_control,
        )
        from scion.core.initial_screening_study_controls import (
            _FILENAME as _CONTROLS_FILENAME,
        )
        from scion.core.initial_screening_study_controls import (
            _InitialScreeningRuntimeInputs,
        )
        from scion.core.initial_screening_study_controls_io import (
            _ControlsPublication,
        )
        from scion.core.initial_screening_study_provider_policy import (
            _FILENAME as _PROVIDER_FILENAME,
        )
        from scion.core.initial_screening_study_provider_policy import (
            _InitialScreeningProviderPolicyInputs,
            _ProviderPolicyPublication,
        )

        if (
            type(runtime_inputs) is not _InitialScreeningProblemSpecInputs
            or runtime_inputs.publication is not None
            or type(controls_inputs) is not _InitialScreeningRuntimeInputs
            or type(controls_inputs.publication) is not _ControlsPublication
            or type(provider_inputs) is not _InitialScreeningProviderPolicyInputs
            or type(provider_inputs.publication) is not _ProviderPolicyPublication
        ):
            raise TypeError
        _problem_inputs_pristine_key(runtime_inputs)
        provider_publication = provider_inputs.publication
        controls_publication = controls_inputs.publication
        if (
            provider_publication.campaign_dir != controls_publication.campaign_dir
            or provider_publication.directory_fingerprints
            != controls_publication.directory_fingerprints
        ):
            raise ValueError
        fingerprint = _publish_third_control(
            controls_publication,
            first_filename=_CONTROLS_FILENAME,
            first_payload=controls_inputs.payload_bytes,
            second_filename=_PROVIDER_FILENAME,
            second_payload=provider_inputs.payload_bytes,
            second_fingerprint=provider_publication.leaf_fingerprint,
            filename=_FILENAME,
            payload=runtime_inputs.payload_bytes,
            max_bytes=_MAX_BYTES,
        )
        result = replace(
            runtime_inputs,
            publication=_ProblemSpecPublication(
                campaign_dir=controls_publication.campaign_dir,
                directory_fingerprints=controls_publication.directory_fingerprints,
                leaf_fingerprint=fingerprint,
            ),
        )
    except Exception:  # noqa: BLE001 - fixed private publication boundary
        failed = True
    if failed or result is None:
        raise _InitialScreeningProblemSpecError(_ERROR)
    return result


def _register_initial_screening_problem_spec_owner(
    owner: Any,
    runtime_inputs: _InitialScreeningProblemSpecInputs,
) -> None:
    """Register an owner-independent baseline after all direct consumers exist."""

    failed = False
    baseline: _RegisteredProblemSpecBaseline | None = None
    try:
        from scion.core.campaign import CampaignManager
        from scion.core.initial_screening_problem_spec_validation import (
            _validate_problem_spec_installed_runtime_unchecked,
        )

        if (
            type(owner) is not CampaignManager
            or type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary
            or weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner) is not None
        ):
            raise TypeError
        _problem_inputs_pristine_key(runtime_inputs)
        publication = runtime_inputs.publication
        if type(publication) is not _ProblemSpecPublication:
            raise TypeError
        _validate_publication_shape(publication)
        owner_storage = _storage(owner)
        if (
            owner_storage.get("_initial_screening_problem_spec_active") is not True
            or owner_storage.get("_initial_screening_problem_spec")
            is not runtime_inputs
        ):
            raise ValueError
        _validate_problem_spec_installed_runtime_unchecked(runtime_inputs, owner)
        baseline = _RegisteredProblemSpecBaseline(
            runtime_inputs_ref=weakref.ref(runtime_inputs),
            spec_v1_ref=weakref.ref(runtime_inputs.spec_v1),
            problem_spec_ref=weakref.ref(runtime_inputs.problem_spec),
            adapter_ref=weakref.ref(runtime_inputs.adapter),
            payload_bytes=runtime_inputs.payload_bytes,
            root_dir=runtime_inputs.root_dir,
            campaign_dir=publication.campaign_dir,
            directory_fingerprints=publication.directory_fingerprints,
            leaf_fingerprint=publication.leaf_fingerprint,
            adapter_class_fingerprint=runtime_inputs.adapter_class_fingerprint,
            frozen_value_key=runtime_inputs.frozen_value_key,
        )
        weakref.WeakKeyDictionary.__setitem__(_REGISTERED_OWNERS, owner, baseline)
    except BaseException:  # noqa: BLE001 - rollback before fixed boundary mapping
        try:
            current = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
            if baseline is not None and current is baseline:
                weakref.WeakKeyDictionary.__delitem__(_REGISTERED_OWNERS, owner)
        except BaseException as ignored_cleanup_error:  # noqa: BLE001 - best effort
            del ignored_cleanup_error
        failed = True
    if failed:
        raise _InitialScreeningProblemSpecError(_ERROR)


def _validate_publication_shape(publication: _ProblemSpecPublication) -> None:
    if type(publication) is not _ProblemSpecPublication:
        raise TypeError
    storage = _storage(publication)
    if set(storage) != {
        "campaign_dir",
        "directory_fingerprints",
        "leaf_fingerprint",
    }:
        raise TypeError
    if (
        type(publication.campaign_dir) is not str
        or type(publication.directory_fingerprints) is not tuple
        or not publication.directory_fingerprints
        or any(
            type(value) is not tuple
            or len(value) != 2
            or any(type(item) is not int for item in value)
            for value in publication.directory_fingerprints
        )
        or type(publication.leaf_fingerprint) is not tuple
        or len(publication.leaf_fingerprint) != 4
        or any(type(item) is not int for item in publication.leaf_fingerprint)
    ):
        raise TypeError


def _freeze_problem_spec_inputs(
    problem_spec: Any,
    adapter: Any,
    operator_execute_signature: Any,
) -> _InitialScreeningProblemSpecInputs:
    """Detach one exact V1, its mechanical bridge, and the loaded adapter type."""

    source_v1 = _validate_source_problem_spec(problem_spec)
    full_projection = _project_model(source_v1)
    if _model_field_names(ProblemSpecV1) != _PROBLEM_SPEC_V1_FIELDS:
        raise TypeError
    _validate_bridge_authority()
    frozen_v1 = cast(
        ProblemSpecV1,
        _MODEL_VALIDATE(ProblemSpecV1, full_projection),
    )
    if frozen_v1 is source_v1:
        raise TypeError
    _validate_problem_spec_v1_shape(frozen_v1)
    frozen_root_dir = _storage(frozen_v1)["root_dir"]
    if type(frozen_root_dir) is not str or not frozen_root_dir:
        raise TypeError
    if _freeze_tree(source_v1) != _freeze_tree(frozen_v1):
        raise ValueError
    payload_bytes = _canonical_problem_spec_payload(frozen_v1)
    fresh_adapter = _freeze_adapter(adapter, source_v1, frozen_v1)
    _validate_all_model_surfaces()
    _validate_bridge_authority()
    bridge = _BRIDGE_PROBLEM_SPEC_V1(frozen_v1)
    bridge_storage = _bridge_storage(bridge)
    bridged_v1 = bridge_storage["spec_v1"]
    bridged_problem = bridge_storage["problem_spec"]
    metric_specs = bridge_storage["metric_specs"]
    objective_policy = bridge_storage["objective_policy"]
    bridged_signature = bridge_storage["operator_execute_signature"]
    if (
        bridged_v1 is not frozen_v1
        or bridged_problem is problem_spec
        or type(bridged_problem) is not ProblemSpec
        or _storage(bridged_problem).get("spec_v1") is not frozen_v1
    ):
        raise TypeError
    if _mutable_identities(source_v1, problem_spec, adapter) & _mutable_identities(
        frozen_v1, bridged_problem, fresh_adapter
    ):
        raise ValueError
    _validate_mechanical_legacy(problem_spec, bridged_problem)
    if (
        type(operator_execute_signature) is not str
        or type(bridged_signature) is not str
        or operator_execute_signature != bridged_signature
    ):
        raise ValueError
    adapter_fingerprint = _adapter_authority_key(fresh_adapter, frozen_v1)
    frozen_key = _authority_value_key(
        spec_v1=frozen_v1,
        problem_spec=bridged_problem,
        adapter=fresh_adapter,
        metric_specs=metric_specs,
        objective_policy=objective_policy,
        operator_execute_signature=bridged_signature,
        payload_bytes=payload_bytes,
        root_dir=frozen_root_dir,
        adapter_class_fingerprint=adapter_fingerprint,
    )
    return _InitialScreeningProblemSpecInputs(
        spec_v1=frozen_v1,
        problem_spec=bridged_problem,
        adapter=fresh_adapter,
        metric_specs=metric_specs,
        objective_policy=objective_policy,
        operator_execute_signature=bridged_signature,
        payload_bytes=payload_bytes,
        root_dir=frozen_root_dir,
        adapter_class_fingerprint=adapter_fingerprint,
        frozen_value_key=frozen_key,
    )


def _problem_inputs_pristine_key(
    runtime_inputs: _InitialScreeningProblemSpecInputs,
) -> tuple[Any, ...]:
    if type(runtime_inputs) is not _InitialScreeningProblemSpecInputs:
        raise TypeError
    storage = _storage(runtime_inputs)
    if set(storage) != {
        "spec_v1",
        "problem_spec",
        "adapter",
        "metric_specs",
        "objective_policy",
        "operator_execute_signature",
        "payload_bytes",
        "root_dir",
        "adapter_class_fingerprint",
        "frozen_value_key",
        "publication",
    }:
        raise TypeError
    if (
        type(storage["adapter_class_fingerprint"]) is not tuple
        or type(storage["frozen_value_key"]) is not tuple
    ):
        raise TypeError
    _validate_problem_graph_shape(storage["spec_v1"], storage["problem_spec"])
    current_adapter_fingerprint = _adapter_authority_key(
        storage["adapter"], storage["spec_v1"]
    )
    if len(current_adapter_fingerprint) != len(
        storage["adapter_class_fingerprint"]
    ) or any(
        current is not frozen
        for current, frozen in zip(
            current_adapter_fingerprint,
            storage["adapter_class_fingerprint"],
        )
    ):
        raise ValueError
    current = _authority_value_key(
        spec_v1=storage["spec_v1"],
        problem_spec=storage["problem_spec"],
        adapter=storage["adapter"],
        metric_specs=storage["metric_specs"],
        objective_policy=storage["objective_policy"],
        operator_execute_signature=storage["operator_execute_signature"],
        payload_bytes=storage["payload_bytes"],
        root_dir=storage["root_dir"],
        adapter_class_fingerprint=current_adapter_fingerprint,
    )
    if not _same_frozen_key(current, storage["frozen_value_key"]):
        raise ValueError
    return current


def _validate_problem_graph_shape(spec_v1: Any, problem_spec: Any) -> None:
    if _validate_source_problem_spec(problem_spec) is not spec_v1:
        raise TypeError


def _validate_bridge_authority() -> None:
    if (
        bridge_problem_spec_v1 is not _BRIDGE_PROBLEM_SPEC_V1
        or _MODEL_VALIDATE is not BaseModel.model_validate.__func__
        or ProblemSpecV1.__pydantic_validator__ is not _PROBLEM_SPEC_V1_VALIDATOR
        or _BRIDGE_PROBLEM_SPEC_V1.__globals__.get("legacy_problem_spec_from_v1")
        is not _LEGACY_PROBLEM_SPEC_FROM_V1
        or any(
            vars(problem_bridge_module).get(name) is not dependency
            for name, dependency in _BRIDGE_DEPENDENCIES.items()
        )
    ):
        raise TypeError
    _validate_bridge_class_surface()


def _validate_source_problem_spec(problem_spec: Any) -> ProblemSpecV1:
    _validate_all_model_surfaces()
    if type(problem_spec) is not ProblemSpec:
        raise TypeError
    storage = _storage(problem_spec)
    required = set(_model_field_names(ProblemSpec)) | {
        "spec_v1",
        "objectives",
        "measurement",
        "runtime_dependencies",
    }
    source_v1 = storage.get("spec_v1")
    if type(source_v1) is not ProblemSpecV1:
        raise TypeError
    _validate_problem_spec_v1_shape(source_v1)
    source_v1_storage = _storage(source_v1)
    if source_v1_storage["family_taxonomy"] is not None:
        required.add("family_taxonomy")
    if set(storage) != required:
        raise TypeError
    _validate_tree(problem_spec)
    if storage["spec_v1"] is not source_v1:
        raise TypeError
    return source_v1


def _validate_problem_spec_v1_shape(value: Any) -> None:
    if type(value) is not ProblemSpecV1:
        raise TypeError
    _validate_tree(value)
    storage = _storage(value)
    if set(storage) != set(_model_field_names(ProblemSpecV1)):
        raise TypeError
    if type(storage["root_dir"]) is not str or not storage["root_dir"]:
        raise TypeError


def _validate_mechanical_legacy(source: ProblemSpec, frozen: ProblemSpec) -> None:
    if type(frozen) is not ProblemSpec:
        raise TypeError
    _validate_tree(frozen)
    if _freeze_tree(source) != _freeze_tree(frozen):
        raise ValueError


def _freeze_adapter(
    source: Any, source_v1: ProblemSpecV1, frozen_v1: ProblemSpecV1
) -> Any:
    adapter_type = type(source)
    import_path = frozen_v1.adapter.import_path
    if type(import_path) is not str or import_path.count(":") != 1:
        raise TypeError
    module_name, class_name = import_path.split(":")
    if (
        type(adapter_type.__module__) is not str
        or type(adapter_type.__qualname__) is not str
        or adapter_type.__module__ != module_name
        or adapter_type.__qualname__ != class_name
    ):
        raise TypeError
    if not module_name.startswith(f"scion.problems.{frozen_v1.id}."):
        raise TypeError
    module = sys.modules.get(module_name)
    if type(module) is not ModuleType:
        raise TypeError
    module_storage = vars(module)
    if (
        type(module_storage) is not dict
        or any(type(key) is not str for key in module_storage)
        or module_storage.get(class_name) is not adapter_type
    ):
        raise TypeError
    source_storage = _storage(source)
    if set(source_storage) != {"_spec"} or source_storage["_spec"] is not source_v1:
        raise TypeError
    descriptor = vars(adapter_type).get("spec")
    if type(descriptor) is not property or descriptor.fget is None:
        raise TypeError
    if source.spec is not source_v1:
        raise ValueError
    before = _freeze_tree(frozen_v1)
    fresh = adapter_type(frozen_v1)
    if type(fresh) is not adapter_type or fresh is source:
        raise TypeError
    fresh_storage = _storage(fresh)
    if (
        set(fresh_storage) != {"_spec"}
        or fresh_storage["_spec"] is not frozen_v1
        or not isinstance(fresh, ProblemAdapter)
        or fresh.spec is not frozen_v1
        or _freeze_tree(frozen_v1) != before
    ):
        raise TypeError
    return fresh


def _adapter_authority_key(adapter: Any, spec_v1: ProblemSpecV1) -> tuple[Any, ...]:
    adapter_type = type(adapter)
    import_path = spec_v1.adapter.import_path
    if type(import_path) is not str or import_path.count(":") != 1:
        raise TypeError
    module_name, class_name = import_path.split(":")
    module = sys.modules.get(module_name)
    if type(module) is not ModuleType:
        raise TypeError
    module_storage = vars(module)
    if (
        type(module_storage) is not dict
        or any(type(key) is not str for key in module_storage)
        or module_storage.get(class_name) is not adapter_type
        or adapter_type.__module__ != module_name
        or adapter_type.__qualname__ != class_name
    ):
        raise TypeError
    adapter_storage = _storage(adapter)
    if set(adapter_storage) != {"_spec"} or adapter_storage["_spec"] is not spec_v1:
        raise TypeError
    class_storage = vars(adapter_type)
    if type(class_storage) is not MappingProxyType or any(
        type(key) is not str for key in class_storage
    ):
        raise TypeError
    descriptor = class_storage.get("spec")
    if type(descriptor) is not property or descriptor.fget is None:
        raise TypeError
    methods = (
        "render_problem_summary",
        "render_operator_interface",
        "load_instance",
        "deserialize_solver_output",
        "check_solution_consistency",
        "check_feasibility",
        "recompute_objective",
        "estimate_lower_bound",
    )
    functions: list[Any] = []
    for name in methods:
        function = class_storage.get(name)
        if not callable(function):
            raise TypeError
        functions.append(function)
    return (adapter_type, module, descriptor, descriptor.fget, *functions)


def _authority_value_key(
    *,
    spec_v1: Any,
    problem_spec: Any,
    adapter: Any,
    metric_specs: Any,
    objective_policy: Any,
    operator_execute_signature: Any,
    payload_bytes: Any,
    root_dir: Any,
    adapter_class_fingerprint: Any,
) -> tuple[Any, ...]:
    _validate_problem_graph_shape(spec_v1, problem_spec)
    spec_value: ProblemSpecV1 = cast(ProblemSpecV1, spec_v1)
    problem_value: ProblemSpec = cast(ProblemSpec, problem_spec)
    _validate_tree(problem_value)
    spec_storage = _storage(spec_value)
    legacy_storage = _storage(problem_value)
    spec_objectives = spec_storage["objectives"]
    if (
        legacy_storage.get("spec_v1") is not spec_value
        or type(metric_specs) is not tuple
        or not metric_specs
        or type(spec_objectives) is not list
        or len(metric_specs) != len(spec_objectives)
        or any(
            metric is not objective
            for metric, objective in zip(metric_specs, spec_objectives)
        )
        or objective_policy is not spec_storage["objective_policy"]
        or type(legacy_storage.get("objectives")) is not tuple
        or len(legacy_storage["objectives"]) != len(metric_specs)
        or any(
            legacy_metric is not metric
            for legacy_metric, metric in zip(legacy_storage["objectives"], metric_specs)
        )
        or legacy_storage.get("measurement") is not spec_storage["measurement"]
        or legacy_storage.get("runtime_dependencies")
        is not spec_storage["runtime_dependencies"]
        or legacy_storage.get("family_taxonomy") is not spec_storage["family_taxonomy"]
        or type(operator_execute_signature) is not str
        or not operator_execute_signature
        or type(payload_bytes) is not bytes
        or type(root_dir) is not str
        or not root_dir
        or root_dir != spec_storage["root_dir"]
        or legacy_storage["root_dir"] != root_dir
        or type(adapter_class_fingerprint) is not tuple
    ):
        raise ValueError
    if _canonical_problem_spec_payload(spec_value) != payload_bytes:
        raise ValueError
    current_adapter_key = _adapter_authority_key(adapter, spec_value)
    if len(current_adapter_key) != len(adapter_class_fingerprint) or any(
        current is not expected
        for current, expected in zip(current_adapter_key, adapter_class_fingerprint)
    ):
        raise ValueError
    return (
        _freeze_tree(spec_value),
        _freeze_tree(problem_value),
        type(adapter),
        adapter_class_fingerprint,
        _freeze_tree(metric_specs),
        _freeze_tree(objective_policy),
        operator_execute_signature,
        payload_bytes,
        root_dir,
    )


def _validate_tree(value: Any, active: set[int] | None = None) -> None:
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return
    stack = set() if active is None else active
    identity = id(value)
    if identity in stack:
        raise ValueError
    stack.add(identity)
    try:
        if type(value) in {list, tuple}:
            for item in value:
                _validate_tree(item, stack)
            return
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise TypeError
            for item in value.values():
                _validate_tree(item, stack)
            return
        if type(value) in (_PROBLEM_MODEL_TYPES | _LEGACY_MODEL_TYPES):
            _validate_model_field_surface(type(value))
            storage = _storage(value)
            expected = set(_model_field_names(type(value)))
            if type(value) is ProblemSpec:
                expected |= set(storage) - set(_model_field_names(ProblemSpec))
            if set(storage) != expected:
                raise TypeError
            for item in storage.values():
                _validate_tree(item, stack)
            return
        raise TypeError
    finally:
        stack.remove(identity)


def _validate_problem_payload_json(
    value: Any,
    depth: int = 0,
    in_allowed_literals: bool = False,
) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return
    if type(value) is list or (type(value) is tuple and not in_allowed_literals):
        for item in value:
            _validate_problem_payload_json(item, depth + 1, in_allowed_literals)
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError
        for key, item in value.items():
            _validate_problem_payload_json(
                item, depth + 1, in_allowed_literals or key == "allowed_literals"
            )
        return
    raise TypeError


def _project_model(value: BaseModel) -> dict[str, Any]:
    _validate_tree(value)
    return {name: _project_value(item) for name, item in _storage(value).items()}


def _project_value(value: Any) -> Any:
    if value is None or type(value) in {str, bool, int, float}:
        return value
    if type(value) is list:
        return [_project_value(item) for item in value]
    if type(value) is tuple:
        return tuple(_project_value(item) for item in value)
    if type(value) is dict:
        return {key: _project_value(item) for key, item in value.items()}
    if type(value) in _PROBLEM_MODEL_TYPES:
        return {name: _project_value(item) for name, item in _storage(value).items()}
    raise TypeError


def _freeze_tree(value: Any) -> Any:
    _validate_tree(value)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        return (float, value.hex())
    if type(value) in {list, tuple}:
        return (type(value), tuple(_freeze_tree(item) for item in value))
    if type(value) is dict:
        return (dict, tuple((key, _freeze_tree(item)) for key, item in value.items()))
    if type(value) in (_PROBLEM_MODEL_TYPES | _LEGACY_MODEL_TYPES):
        return (
            type(value),
            tuple((key, _freeze_tree(item)) for key, item in _storage(value).items()),
        )
    raise TypeError


def _same_frozen_key(current: Any, expected: Any) -> bool:
    """Compare private frozen keys without invoking attacker-defined equality."""

    if type(expected) is tuple:
        return (
            type(current) is tuple
            and len(current) == len(expected)
            and all(
                _same_frozen_key(current_item, expected_item)
                for current_item, expected_item in zip(current, expected)
            )
        )
    if expected is None:
        return current is None
    if type(expected) in {str, bool, int, bytes}:
        return type(current) is type(expected) and current == expected
    return current is expected


def _storage(value: Any) -> dict[str, Any]:
    storage = vars(value)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    return storage


def _mutable_identities(*roots: Any) -> set[int]:
    identities: set[int] = set()
    pending = list(roots)
    while pending:
        value = pending.pop()
        if value is None or type(value) in {str, bool, int, float, tuple}:
            if type(value) is tuple:
                pending.extend(value)
            continue
        identity = id(value)
        if identity in identities:
            continue
        identities.add(identity)
        if type(value) in {list, set, frozenset}:
            pending.extend(value)
        elif type(value) is dict:
            pending.extend(value.values())
        elif type(value) in (_PROBLEM_MODEL_TYPES | _LEGACY_MODEL_TYPES) or type(
            value
        ).__module__.startswith("scion.problems."):
            pending.extend(_storage(value).values())
        else:
            raise TypeError
    return identities
