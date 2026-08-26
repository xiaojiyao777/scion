"""Import-time anchors for the private ProblemSpec declaration boundary."""

from __future__ import annotations

from dataclasses import fields
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel

from scion.config import problem as legacy_problem_schema
from scion.contract.gate import ContractGate
from scion.contract.surface_access import SurfaceAccess
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.evidence_recording.recorder import EvidenceRecorder
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.research_history import ResearchHistoryWriter
from scion.problem import spec as problem_spec_schema
from scion.problem.bridge import ProblemSpecBridge
from scion.problem.spec import OperatorInterfaceSpec
from scion.proposal.context_manager import ContextManager
from scion.protocol.experiment import ExperimentProtocol
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.gate import VerificationGate

_MISSING = object()
_LEGACY_PROBLEM_SPEC_EXTRA_FIELDS = (
    "spec_v1",
    "objectives",
    "measurement",
    "runtime_dependencies",
    "family_taxonomy",
)
_MODEL_TYPES: frozenset[type[BaseModel]] = frozenset(
    cast(type[BaseModel], value)
    for module in (problem_spec_schema, legacy_problem_schema)
    for value in vars(module).values()
    if isinstance(value, type) and issubclass(value, BaseModel)
)
_MODEL_FIELD_SURFACES = {
    model_type: (
        model_type.__mro__,
        tuple(model_type.model_fields),
        tuple(
            (
                owner_type,
                tuple(
                    (
                        name,
                        vars(owner_type).get(name, _MISSING),
                    )
                    for name in (
                        tuple(model_type.model_fields)
                        + (
                            _LEGACY_PROBLEM_SPEC_EXTRA_FIELDS
                            if model_type is legacy_problem_schema.ProblemSpec
                            else ()
                        )
                    )
                ),
            )
            for owner_type in model_type.__mro__
        ),
        tuple(
            (name, getattr(model_type, name, _MISSING))
            for name in ("__init__", "__getattribute__", "__getattr__")
        ),
        model_type.__pydantic_validator__,
        getattr(model_type, "model_dump", _MISSING),
        tuple(model_type.model_fields.items()),
    )
    for model_type in _MODEL_TYPES
}
_MODEL_DUMP = BaseModel.model_dump
_CATEGORY_NAMES = vars(OperatorInterfaceSpec)["category_names"]
_PROBLEM_SPEC_BRIDGE_FIELDS = (
    "spec_v1",
    "problem_spec",
    "metric_specs",
    "objective_policy",
    "operator_execute_signature",
)
_PROBLEM_SPEC_BRIDGE_MRO = ProblemSpecBridge.__mro__
_PROBLEM_SPEC_BRIDGE_DATACLASS_FIELDS = vars(ProblemSpecBridge)["__dataclass_fields__"]
_PROBLEM_SPEC_BRIDGE_DATACLASS_PARAMS = vars(ProblemSpecBridge)["__dataclass_params__"]
_PROBLEM_SPEC_BRIDGE_FIELD_SURFACES = tuple(
    (
        owner_type,
        tuple(
            (name, vars(owner_type).get(name, _MISSING))
            for name in _PROBLEM_SPEC_BRIDGE_FIELDS
        ),
    )
    for owner_type in ProblemSpecBridge.__mro__
)
_PROBLEM_SPEC_BRIDGE_METHODS = tuple(
    (name, getattr(ProblemSpecBridge, name, _MISSING))
    for name in ("__init__", "__getattribute__", "__getattr__")
)


def _capture_consumer_method_anchors() -> dict[tuple[type, str], Any]:
    surfaces = {
        ProblemRuntime: (
            "build_hypothesis_context",
            "build_code_context",
            "hypothesis_research_public_sources",
            "hypothesis_research_source_prefixes",
        ),
        ContextManager: ("build_hypothesis_context", "build_code_context"),
        ContractGate: ("validate_hypothesis", "validate_patch"),
        SurfaceAccess: (
            "research_surfaces",
            "surface_by_name",
            "surface_for_patch_path",
        ),
        CodeDevelopmentEvaluator: ("evaluate",),
        ExperimentProtocol: ("run_canary", "run_experiment", "resolve_time_limit_sec"),
        VerificationGate: ("run_preflight", "run"),
        ProposalPipeline: ("generate_hypothesis", "generate_code"),
        WorkspaceMaterializer: (
            "create_branch_workspace",
            "create_candidate_workspace",
            "apply_patch",
        ),
        EvidenceRecorder: ("record_step",),
        ResearchHistoryWriter: ("append_step",),
    }
    return {
        (expected_type, name): vars(expected_type)[name]
        for expected_type, names in surfaces.items()
        for name in ("__init__", *names)
    }


_CONSUMER_METHOD_ANCHORS = _capture_consumer_method_anchors()
_CONSUMER_DESCRIPTOR_ANCHORS = {
    (expected_type, name): vars(expected_type)[name]
    for expected_type, names in {
        ProblemRuntime: (
            "spec",
            "adapter",
            "split_manifest",
            "seed_ledger",
            "research_input",
            "research_history",
            "development_suites",
            "ctx_manager",
        ),
        ExperimentProtocol: ("objective_semantics", "problem_spec"),
    }.items()
    for name in names
}


def _validate_model_field_surface(model_type: type[BaseModel]) -> None:
    expected = _MODEL_FIELD_SURFACES.get(model_type)
    model_fields = model_type.model_fields
    if (
        expected is None
        or model_type.__mro__ != expected[0]
        or type(model_fields) is not dict
        or any(type(name) is not str for name in model_fields)
        or tuple(model_fields) != expected[1]
        or model_type.__pydantic_validator__ is not expected[4]
        or getattr(model_type, "model_dump", _MISSING) is not expected[5]
        or len(model_fields) != len(expected[6])
        or any(
            name != expected_name or field_info is not expected_field_info
            for (name, field_info), (expected_name, expected_field_info) in zip(
                model_fields.items(), expected[6]
            )
        )
    ):
        raise TypeError
    for owner_type, field_surfaces in expected[2]:
        storage = vars(owner_type)
        if type(storage) is not MappingProxyType or any(
            type(key) is not str for key in storage
        ):
            raise TypeError
        if any(
            storage.get(name, _MISSING) is not descriptor
            for name, descriptor in field_surfaces
        ):
            raise TypeError
    if any(
        getattr(model_type, name, _MISSING) is not descriptor
        for name, descriptor in expected[3]
    ):
        raise TypeError
    if BaseModel.model_dump is not _MODEL_DUMP:
        raise TypeError
    if vars(OperatorInterfaceSpec).get("category_names") is not _CATEGORY_NAMES:
        raise TypeError


def _model_field_names(model_type: type[BaseModel]) -> tuple[str, ...]:
    _validate_model_field_surface(model_type)
    value = _MODEL_FIELD_SURFACES[model_type][1]
    if type(value) is not tuple or any(type(name) is not str for name in value):
        raise TypeError
    return value


def _validate_all_model_surfaces() -> None:
    for model_type in _MODEL_TYPES:
        _validate_model_field_surface(model_type)


def _validate_bridge_class_surface() -> None:
    class_storage = vars(ProblemSpecBridge)
    if (
        type(class_storage) is not MappingProxyType
        or any(type(key) is not str for key in class_storage)
        or class_storage.get("__dataclass_fields__")
        is not _PROBLEM_SPEC_BRIDGE_DATACLASS_FIELDS
        or class_storage.get("__dataclass_params__")
        is not _PROBLEM_SPEC_BRIDGE_DATACLASS_PARAMS
        or ProblemSpecBridge.__mro__ != _PROBLEM_SPEC_BRIDGE_MRO
        or tuple(field.name for field in fields(ProblemSpecBridge))
        != _PROBLEM_SPEC_BRIDGE_FIELDS
        or any(
            getattr(ProblemSpecBridge, name, _MISSING) is not expected
            for name, expected in _PROBLEM_SPEC_BRIDGE_METHODS
        )
    ):
        raise TypeError
    for owner_type, expected_fields in _PROBLEM_SPEC_BRIDGE_FIELD_SURFACES:
        owner_storage = vars(owner_type)
        if type(owner_storage) is not MappingProxyType or any(
            type(key) is not str for key in owner_storage
        ):
            raise TypeError
        if any(
            owner_storage.get(name, _MISSING) is not expected
            for name, expected in expected_fields
        ):
            raise TypeError


def _bridge_storage(value: Any) -> dict[str, Any]:
    _validate_bridge_class_surface()
    if type(value) is not ProblemSpecBridge:
        raise TypeError
    storage = vars(value)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage) != set(_PROBLEM_SPEC_BRIDGE_FIELDS)
    ):
        raise TypeError
    return storage
