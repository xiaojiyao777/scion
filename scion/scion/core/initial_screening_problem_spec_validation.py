"""Private run-start validation for the frozen problem declaration."""

from __future__ import annotations

import weakref
from dataclasses import dataclass, fields
from types import MethodType
from typing import Any, cast

from scion.config.problem import ProblemSpec
from scion.contract.gate import ContractGate
from scion.contract.surface_access import SurfaceAccess
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.evidence_recording.recorder import EvidenceRecorder
from scion.core.initial_screening_problem_spec import (
    _ERROR,
    _FILENAME,
    _MAX_BYTES,
    _REGISTERED_OWNERS,
    _InitialScreeningProblemSpecError,
    _InitialScreeningProblemSpecInputs,
    _problem_inputs_pristine_key,
    _ProblemSpecPublication,
    _RegisteredProblemSpecBaseline,
    _same_frozen_key,
    _validate_problem_graph_shape,
)
from scion.core.initial_screening_problem_spec_anchors import (
    _CONSUMER_DESCRIPTOR_ANCHORS,
    _CONSUMER_METHOD_ANCHORS,
)
from scion.core.initial_screening_problem_spec_io import (
    _validate_third_control_publication,
)
from scion.core.operator_interface import (
    OperatorExecuteSignature,
    parse_execute_signature,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.research_history import ResearchHistoryWriter
from scion.problem.spec import ProblemSpecV1
from scion.proposal.context_manager import ContextManager
from scion.protocol.experiment import ExperimentProtocol
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.gate import VerificationGate


@dataclass(frozen=True, repr=False)
class _ProblemSpecRunState:
    runtime_inputs: _InitialScreeningProblemSpecInputs
    baseline: _RegisteredProblemSpecBaseline

    def __repr__(self) -> str:
        return "_ProblemSpecRunState(<redacted>)"

    __str__ = __repr__


_SERVICE_SHAPES: dict[str, tuple[type, set[str], tuple[str, ...]]] = {
    "_problem_runtime": (
        ProblemRuntime,
        {
            "_spec",
            "_adapter",
            "_split_manifest",
            "_seed_ledger",
            "_research_input",
            "_research_history",
            "_development_suites",
            "_ctx_manager",
        },
        (
            "build_hypothesis_context",
            "build_code_context",
            "hypothesis_research_public_sources",
            "hypothesis_research_source_prefixes",
        ),
    ),
    "_contract_gate": (
        ContractGate,
        {
            "_spec",
            "_adapter",
            "_operator_signature",
            "_champion_snapshot_path",
            "_champion_snapshot_provider",
            "_source_overrides",
            "_surface_access",
        },
        ("validate_hypothesis", "validate_patch"),
    ),
    "_code_development_evaluator": (
        CodeDevelopmentEvaluator,
        {
            "materializer",
            "problem_spec",
            "suites",
            "workspace_paths",
            "problem_package_paths",
            "limits",
            "operator_execute_signature",
            "sandbox",
        },
        ("evaluate",),
    ),
    "_experiment_protocol": (
        ExperimentProtocol,
        {
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
        },
        ("run_canary", "run_experiment", "resolve_time_limit_sec"),
    ),
    "_vgate": (
        VerificationGate,
        {
            "_spec",
            "_runner",
            "_metrics_dir",
            "_adapter",
            "_strict_runtime_checks",
            "_require_adapter_for_runtime",
            "_operator_execute_signature",
            "_max_runtime_ratio",
            "_runtime_time_limit_sec",
        },
        ("run_preflight", "run"),
    ),
    "_proposal_pipeline": (
        ProposalPipeline,
        {
            "creative",
            "problem_runtime",
            "branch_workspaces",
            "champion_lock",
            "get_champion",
            "step_history",
            "mark_balance_exhausted",
            "code_research_limits",
            "code_development_evaluator",
            "record_hypothesis_candidate_completed",
            "record_hypothesis_candidate_selected",
            "_hypothesis_rejection_counts",
            "_last_hypothesis_rejection_reason",
        },
        ("generate_hypothesis", "generate_code"),
    ),
    "_materializer": (
        WorkspaceMaterializer,
        {
            "_campaign_dir",
            "_workspaces_dir",
            "_candidate_workspaces_dir",
            "_champions_dir",
            "_frozen_patterns",
            "_editable_patterns",
            "_archive_dir",
            "_inflight_branch_workspaces",
            "_inflight_candidate_workspaces",
        },
        ("create_branch_workspace", "create_candidate_workspace", "apply_patch"),
    ),
    "_evidence_recorder": (
        EvidenceRecorder,
        {
            "campaign_id",
            "campaign_dir",
            "status_reporter",
            "registry",
            "model_id",
            "protocol_version",
            "family_taxonomy",
            "final_evidence_refs",
            "_research_history_writer",
        },
        ("record_step",),
    ),
}
_NESTED_METHODS = {
    ContextManager: ("build_hypothesis_context", "build_code_context"),
    SurfaceAccess: (
        "research_surfaces",
        "surface_by_name",
        "surface_for_patch_path",
    ),
    ResearchHistoryWriter: ("append_step",),
}
_PARSE_EXECUTE_SIGNATURE = parse_execute_signature


def _validate_problem_spec_prepublication(
    problem_inputs: Any,
    provisional: Any,
) -> None:
    """Validate every provisional problem consumer before the first leaf."""

    from scion.core.initial_screening_study_controls import (
        _InitialScreeningRuntimeInputs,
    )

    if type(problem_inputs) is not _InitialScreeningProblemSpecInputs:
        raise _InitialScreeningProblemSpecError(_ERROR)
    if type(provisional) is not tuple or len(provisional) != 5:
        raise _InitialScreeningProblemSpecError(_ERROR)
    controls, problem_runtime, contract, protocol, verification = provisional
    try:
        if type(controls) is not _InitialScreeningRuntimeInputs:
            raise TypeError
        _exact_storage(vars(controls), {field.name for field in fields(type(controls))})
        values = {
            "_problem_runtime": problem_runtime,
            "_contract_gate": contract,
            "_experiment_protocol": protocol,
            "_vgate": verification,
        }
        for name, value in values.items():
            expected_type, keys, methods = _SERVICE_SHAPES[name]
            if type(value) is not expected_type:
                raise TypeError
            _exact_storage(vars(value), keys)
            if not _has_exact_methods(value, expected_type, methods):
                raise TypeError
        ctx = vars(problem_runtime)["_ctx_manager"]
        surface = vars(contract)["_surface_access"]
        for value, expected_type, keys, methods in (
            (
                ctx,
                ContextManager,
                {
                    "_adapter",
                    "_research_input",
                    "_prior_research_observations",
                    "_research_history",
                },
                _NESTED_METHODS[ContextManager],
            ),
            (
                surface,
                SurfaceAccess,
                {"_spec"},
                _NESTED_METHODS[SurfaceAccess],
            ),
        ):
            if type(value) is not expected_type:
                raise TypeError
            _exact_storage(vars(value), keys)
            if not _has_exact_methods(value, expected_type, methods):
                raise TypeError
        spec = problem_inputs.problem_spec
        adapter = problem_inputs.adapter
        signature = vars(contract)["_operator_signature"]
        if (
            controls.experiment_protocol is not protocol
            or vars(problem_runtime)["_spec"] is not spec
            or vars(problem_runtime)["_adapter"] is not adapter
            or vars(ctx)["_adapter"] is not adapter
            or vars(contract)["_spec"] is not spec
            or vars(contract)["_adapter"] is not adapter
            or vars(contract)["_surface_access"] is not surface
            or vars(surface)["_spec"] is not spec
            or vars(protocol)["_problem_spec"] is not spec
            or vars(protocol)["_problem_adapter"] is not adapter
            or vars(verification)["_spec"] is not spec
            or vars(verification)["_adapter"] is not adapter
            or not _signature_matches(
                signature, problem_inputs.operator_execute_signature
            )
            or vars(verification)["_operator_execute_signature"]
            != problem_inputs.operator_execute_signature
            or not _same_frozen_key(
                _safe_frozen(vars(protocol)["_metric_specs"]),
                _safe_frozen(problem_inputs.metric_specs),
            )
            or not _same_frozen_key(
                _safe_frozen(vars(protocol)["_objective_policy"]),
                _safe_frozen(problem_inputs.objective_policy),
            )
        ):
            raise ValueError
        _problem_inputs_pristine_key(problem_inputs)
    except Exception:  # noqa: BLE001 - fixed prepublication boundary
        raise _InitialScreeningProblemSpecError(_ERROR) from None


def _prepare_problem_spec_run_validation(
    owner: Any, owner_storage: dict[str, Any]
) -> _ProblemSpecRunState | None:
    """Validate carrier/baseline and consumer shapes without filesystem IO."""

    try:
        return _prepare_problem_spec_run_validation_unchecked(owner, owner_storage)
    except _InitialScreeningProblemSpecError:
        raise
    except Exception:  # noqa: BLE001 - fixed private run boundary
        raise _InitialScreeningProblemSpecError(_ERROR) from None


def _prepare_problem_spec_run_validation_unchecked(
    owner: Any, owner_storage: dict[str, Any]
) -> _ProblemSpecRunState | None:

    from scion.core.campaign import CampaignManager

    _exact_storage(owner_storage, set(owner_storage))
    marker_keys = {
        "_initial_screening_problem_spec_active",
        "_initial_screening_problem_spec",
    }
    present = marker_keys & set(owner_storage)
    if not present:
        if _owner_identity_is_registered(owner):
            raise _InitialScreeningProblemSpecError(_ERROR)
        return None
    if present != marker_keys or type(owner) is not CampaignManager:
        raise _InitialScreeningProblemSpecError(_ERROR)
    runtime_inputs = owner_storage["_initial_screening_problem_spec"]
    if (
        owner_storage["_initial_screening_problem_spec_active"] is not True
        or type(runtime_inputs) is not _InitialScreeningProblemSpecInputs
        or type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary
    ):
        raise _InitialScreeningProblemSpecError(_ERROR)
    _validate_runtime_shape(runtime_inputs)
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
    if type(baseline) is not _RegisteredProblemSpecBaseline:
        raise _InitialScreeningProblemSpecError(_ERROR)
    baseline = cast(_RegisteredProblemSpecBaseline, baseline)
    _validate_baseline_shape(baseline)
    if (
        baseline.runtime_inputs_ref() is not runtime_inputs
        or baseline.spec_v1_ref() is not runtime_inputs.spec_v1
        or baseline.problem_spec_ref() is not runtime_inputs.problem_spec
        or baseline.adapter_ref() is not runtime_inputs.adapter
    ):
        raise _InitialScreeningProblemSpecError(_ERROR)
    services = _service_values(owner_storage)
    _validate_nested_service_shapes(services)
    return _ProblemSpecRunState(runtime_inputs, baseline)


def _validate_problem_spec_publication(
    state: _ProblemSpecRunState,
    controls_inputs: Any,
    provider_state: Any,
) -> None:
    """Freshly rewalk all three exact declaration leaves."""

    try:
        _validate_problem_spec_publication_unchecked(
            state, controls_inputs, provider_state
        )
    except _InitialScreeningProblemSpecError:
        raise
    except Exception:  # noqa: BLE001 - fixed private run boundary
        raise _InitialScreeningProblemSpecError(_ERROR) from None


def _validate_problem_spec_publication_unchecked(
    state: _ProblemSpecRunState,
    controls_inputs: Any,
    provider_state: Any,
) -> None:

    from scion.core.initial_screening_study_controls import (
        _FILENAME as _CONTROLS_FILENAME,
    )
    from scion.core.initial_screening_study_provider_policy import (
        _FILENAME as _PROVIDER_FILENAME,
    )

    baseline = state.baseline
    runtime_inputs = state.runtime_inputs
    publication = runtime_inputs.publication
    controls_publication = controls_inputs.publication
    provider_baseline = provider_state.baseline
    if (
        type(publication) is not _ProblemSpecPublication
        or publication.campaign_dir != baseline.campaign_dir
        or publication.directory_fingerprints != baseline.directory_fingerprints
        or publication.leaf_fingerprint != baseline.leaf_fingerprint
        or controls_publication.campaign_dir != publication.campaign_dir
    ):
        raise _InitialScreeningProblemSpecError(_ERROR)
    _validate_third_control_publication(
        controls_publication,
        first_filename=_CONTROLS_FILENAME,
        first_payload=controls_inputs.payload_bytes,
        second_filename=_PROVIDER_FILENAME,
        second_payload=provider_state.runtime_inputs.payload_bytes,
        second_fingerprint=provider_baseline.leaf_fingerprint,
        filename=_FILENAME,
        payload=baseline.payload_bytes,
        fingerprint=baseline.leaf_fingerprint,
        max_bytes=_MAX_BYTES,
        require_exact_names=False,
    )


def _validate_problem_spec_installed_runtime(
    state: _ProblemSpecRunState, owner: Any
) -> None:
    try:
        _validate_problem_spec_baseline(state)
        _validate_problem_spec_installed_runtime_unchecked(state.runtime_inputs, owner)
    except Exception:  # noqa: BLE001 - fixed private run boundary
        raise _InitialScreeningProblemSpecError(_ERROR) from None


def _validate_problem_spec_installed_runtime_unchecked(
    runtime_inputs: _InitialScreeningProblemSpecInputs, owner: Any
) -> None:
    """Validate all reviewed consumers without evaluating the problem adapter."""

    from scion.core.campaign import CampaignManager

    if type(owner) is not CampaignManager:
        raise TypeError
    _problem_inputs_pristine_key(runtime_inputs)
    owner_storage = vars(owner)
    _exact_storage(owner_storage, set(owner_storage))
    services = _service_values(owner_storage)
    nested = _validate_nested_service_shapes(services)
    spec = runtime_inputs.problem_spec
    spec_v1 = runtime_inputs.spec_v1
    adapter = runtime_inputs.adapter
    problem_runtime = services["_problem_runtime"]
    contract = services["_contract_gate"]
    evaluator = services["_code_development_evaluator"]
    protocol = services["_experiment_protocol"]
    verification = services["_vgate"]
    proposal = services["_proposal_pipeline"]
    materializer = services["_materializer"]
    evidence = services["_evidence_recorder"]
    ctx, surface, writer = nested
    signature = vars(contract)["_operator_signature"]
    if (
        type(spec) is not ProblemSpec
        or type(spec_v1) is not ProblemSpecV1
        or vars(spec).get("spec_v1") is not spec_v1
        or vars(adapter).get("_spec") is not spec_v1
        or vars(problem_runtime)["_spec"] is not spec
        or vars(problem_runtime)["_adapter"] is not adapter
        or vars(problem_runtime)["_ctx_manager"] is not ctx
        or vars(ctx)["_adapter"] is not adapter
        or vars(contract)["_spec"] is not spec
        or vars(contract)["_adapter"] is not adapter
        or vars(contract)["_surface_access"] is not surface
        or vars(surface)["_spec"] is not spec
        or vars(evaluator)["problem_spec"] is not spec
        or vars(evaluator)["materializer"] is not materializer
        or vars(evaluator)["limits"] is not owner_storage.get("_code_research_limits")
        or vars(evaluator)["suites"] is not vars(problem_runtime)["_development_suites"]
        or type(vars(evaluator)["workspace_paths"]) is not tuple
        or any(type(item) is not str for item in vars(evaluator)["workspace_paths"])
        or vars(evaluator)["workspace_paths"] != tuple(spec.development_workspace_paths)
        or type(vars(evaluator)["problem_package_paths"]) is not tuple
        or any(
            type(item) is not str for item in vars(evaluator)["problem_package_paths"]
        )
        or vars(evaluator)["problem_package_paths"]
        != tuple(spec.development_problem_package_paths)
        or vars(protocol)["_problem_spec"] is not spec
        or vars(protocol)["_problem_adapter"] is not adapter
        or vars(verification)["_spec"] is not spec
        or vars(verification)["_adapter"] is not adapter
        or vars(proposal)["problem_runtime"] is not problem_runtime
        or vars(proposal)["code_development_evaluator"] is not evaluator
        or not _signature_matches(signature, runtime_inputs.operator_execute_signature)
        or type(vars(evaluator)["operator_execute_signature"]) is not str
        or vars(evaluator)["operator_execute_signature"]
        != runtime_inputs.operator_execute_signature
        or type(vars(verification)["_operator_execute_signature"]) is not str
        or vars(verification)["_operator_execute_signature"]
        != runtime_inputs.operator_execute_signature
        or not _same_frozen_key(
            _safe_frozen(vars(protocol)["_metric_specs"]),
            _safe_frozen(runtime_inputs.metric_specs),
        )
        or not _same_frozen_key(
            _safe_frozen(vars(protocol)["_objective_policy"]),
            _safe_frozen(runtime_inputs.objective_policy),
        )
        or vars(evidence)["family_taxonomy"] is not spec.family_taxonomy
        or type(vars(writer)["problem_id"]) is not str
        or vars(writer)["problem_id"] != spec.name
    ):
        raise ValueError
    _validate_materializer(materializer, spec)


def _validate_problem_spec_baseline(state: _ProblemSpecRunState) -> None:
    baseline = state.baseline
    current = state.runtime_inputs
    if (
        baseline.payload_bytes != current.payload_bytes
        or baseline.root_dir != current.root_dir
        or not _same_frozen_key(
            current.adapter_class_fingerprint,
            baseline.adapter_class_fingerprint,
        )
        or not _same_frozen_key(current.frozen_value_key, baseline.frozen_value_key)
    ):
        raise ValueError


def _service_values(owner_storage: dict[str, Any]) -> dict[str, Any]:
    if not set(_SERVICE_SHAPES).issubset(owner_storage):
        raise TypeError
    services = {name: owner_storage[name] for name in _SERVICE_SHAPES}
    for name, (expected_type, keys, methods) in _SERVICE_SHAPES.items():
        service = services[name]
        if type(service) is not expected_type:
            raise TypeError
        _exact_storage(vars(service), keys)
        if not _has_exact_methods(service, expected_type, methods):
            raise TypeError
    return services


def _validate_nested_service_shapes(
    services: dict[str, Any],
) -> tuple[ContextManager, SurfaceAccess, ResearchHistoryWriter]:
    problem_runtime = services["_problem_runtime"]
    contract = services["_contract_gate"]
    evidence = services["_evidence_recorder"]
    ctx = vars(problem_runtime)["_ctx_manager"]
    surface = vars(contract)["_surface_access"]
    writer = vars(evidence)["_research_history_writer"]
    nested_shapes = (
        (
            ctx,
            ContextManager,
            {
                "_adapter",
                "_research_input",
                "_prior_research_observations",
                "_research_history",
            },
            ("build_hypothesis_context", "build_code_context"),
        ),
        (
            surface,
            SurfaceAccess,
            {"_spec"},
            ("research_surfaces", "surface_by_name", "surface_for_patch_path"),
        ),
        (
            writer,
            ResearchHistoryWriter,
            {"path", "problem_id", "_lines"},
            ("append_step",),
        ),
    )
    for value, expected_type, keys, methods in nested_shapes:
        if type(value) is not expected_type:
            raise TypeError
        _exact_storage(vars(value), keys)
        if not _has_exact_methods(value, expected_type, methods):
            raise TypeError
    return ctx, surface, writer


def _validate_materializer(materializer: Any, spec: ProblemSpec) -> None:
    storage = vars(materializer)
    frozen = storage["_frozen_patterns"]
    editable = storage["_editable_patterns"]
    expected_frozen = vars(spec.search_space)["frozen"]
    expected_editable = tuple(vars(spec.search_space)["editable"])
    if (
        type(frozen) is not frozenset
        or any(type(item) is not str for item in frozen)
        or frozen != frozenset(expected_frozen)
        or type(editable) is not tuple
        or any(type(item) is not str for item in editable)
        or editable != expected_editable
    ):
        raise ValueError


def _validate_baseline_shape(value: Any) -> None:
    if type(value) is not _RegisteredProblemSpecBaseline:
        raise TypeError
    storage = vars(value)
    _exact_storage(storage, {field.name for field in fields(type(value))})
    references = (
        value.runtime_inputs_ref,
        value.spec_v1_ref,
        value.problem_spec_ref,
        value.adapter_ref,
    )
    if (
        any(type(reference) is not weakref.ReferenceType for reference in references)
        or type(value.payload_bytes) is not bytes
        or type(value.root_dir) is not str
        or type(value.campaign_dir) is not str
        or not _directory_fingerprints(value.directory_fingerprints)
        or not _int_tuple(value.leaf_fingerprint, 4)
        or type(value.adapter_class_fingerprint) is not tuple
        or type(value.frozen_value_key) is not tuple
    ):
        raise TypeError


def _validate_runtime_shape(value: Any) -> None:
    if type(value) is not _InitialScreeningProblemSpecInputs:
        raise TypeError
    _exact_storage(vars(value), {field.name for field in fields(type(value))})
    storage = vars(value)
    _validate_problem_graph_shape(storage["spec_v1"], storage["problem_spec"])
    publication = storage["publication"]
    if type(publication) is not _ProblemSpecPublication:
        raise TypeError
    _exact_storage(
        vars(publication), {field.name for field in fields(type(publication))}
    )
    if (
        type(value.spec_v1) is not ProblemSpecV1
        or type(value.problem_spec) is not ProblemSpec
        or type(value.payload_bytes) is not bytes
        or type(value.root_dir) is not str
        or type(value.adapter_class_fingerprint) is not tuple
        or type(value.frozen_value_key) is not tuple
        or type(publication.campaign_dir) is not str
        or not _directory_fingerprints(publication.directory_fingerprints)
        or not _int_tuple(publication.leaf_fingerprint, 4)
    ):
        raise TypeError


def _owner_identity_is_registered(owner: Any) -> bool:
    if type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary:
        raise TypeError
    references = weakref.WeakKeyDictionary.keyrefs(_REGISTERED_OWNERS)
    if type(references) is not list or any(
        type(reference) is not weakref.ReferenceType for reference in references
    ):
        raise TypeError
    return any(reference() is owner for reference in references)


def _has_exact_methods(value: Any, expected_type: type, names: tuple[str, ...]) -> bool:
    storage = vars(value)
    class_storage = vars(expected_type)
    if type(class_storage).__name__ != "mappingproxy" or any(
        type(key) is not str for key in class_storage
    ):
        return False
    if class_storage.get("__init__") is not _CONSUMER_METHOD_ANCHORS.get(
        (expected_type, "__init__")
    ):
        return False
    if any(
        class_storage.get(name) is not descriptor
        for (owner_type, name), descriptor in _CONSUMER_DESCRIPTOR_ANCHORS.items()
        if owner_type is expected_type
    ):
        return False
    for name in names:
        expected = _CONSUMER_METHOD_ANCHORS.get((expected_type, name))
        if name in storage or class_storage.get(name) is not expected:
            return False
        actual = getattr(value, name, None)
        if (
            type(actual) is not MethodType
            or actual.__self__ is not value
            or actual.__func__ is not expected
        ):
            return False
    return True


def _signature_matches(value: Any, raw: Any) -> bool:
    if type(raw) is not str or parse_execute_signature is not _PARSE_EXECUTE_SIGNATURE:
        return False
    if type(value) is not OperatorExecuteSignature:
        return False
    storage = vars(value)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or set(storage) != {"name", "args", "display"}
        or type(storage["name"]) is not str
        or type(storage["args"]) is not tuple
        or any(type(item) is not str for item in storage["args"])
        or type(storage["display"]) is not str
    ):
        return False
    expected = _PARSE_EXECUTE_SIGNATURE(raw)
    return type(expected) is OperatorExecuteSignature and vars(expected) == storage


def _exact_storage(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != expected:
        raise TypeError


def _directory_fingerprints(value: Any) -> bool:
    return (
        type(value) is tuple
        and bool(value)
        and all(_int_tuple(item, 2) for item in value)
    )


def _int_tuple(value: Any, length: int) -> bool:
    return (
        type(value) is tuple
        and len(value) == length
        and all(type(item) is int for item in value)
    )


def _safe_frozen(value: Any) -> Any:
    from scion.core.initial_screening_problem_spec import _freeze_tree

    return _freeze_tree(value)
