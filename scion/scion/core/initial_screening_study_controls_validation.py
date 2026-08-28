from __future__ import annotations

import os
import sys
import weakref
from _thread import LockType
from collections.abc import Callable
from dataclasses import fields
from types import FunctionType, GetSetDescriptorType, MethodType, ModuleType
from typing import Any, cast

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core import (
    initial_screening_study_controls_run_validation as run_validation_module,
)
from scion.core import (
    initial_screening_study_provider_policy_validation as provider_validation_module,
)
from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.campaign_loop import CampaignLoop
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.initial_screening_study_controls import (
    _REGISTERED_OWNERS,
    _InitialScreeningRuntimeInputs,
    _RegisteredControlsBaseline,
    _runtime_payload_bytes,
)
from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _validate_controls_publication,
    _validate_private_child_directory,
)
from scion.core.initial_screening_study_controls_shapes import (
    _validate_dataclass_instance,
    _validate_model_instance,
    _validate_objective_shapes,
    _validate_pristine_storage_shapes,
    _validate_protocol_wrapper_shape,
    _weak_registry_contains_owner,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.proposal_runtime_telemetry import (
    ProposalRuntimeSnapshot,
    ProposalRuntimeTelemetry,
)
from scion.core.qualification import QualificationOnlyConfig, QualificationRuntime
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallBudgetSnapshot,
    ResourceEnvelope,
)
from scion.core.scheduler import Scheduler
from scion.core.workspace_service import WorkspaceService
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.engine import CreativeLayer
from scion.proposal.engine.provider_call import ProviderCaller
from scion.protocol.experiment import ExperimentProtocol
from scion.verification.gate import VerificationGate

_RUN_VALIDATION_MODULE_NAME = (
    "scion.core.initial_screening_study_controls_run_validation"
)
if type(run_validation_module) is not ModuleType:
    raise TypeError
_RUN_VALIDATION_STORAGE = vars(run_validation_module)
if (
    type(_RUN_VALIDATION_STORAGE) is not dict
    or any(type(name) is not str for name in _RUN_VALIDATION_STORAGE)
    or type(_RUN_VALIDATION_STORAGE.get("__name__")) is not str
    or _RUN_VALIDATION_STORAGE["__name__"] != _RUN_VALIDATION_MODULE_NAME
):
    raise TypeError
_RUN_VALIDATION_ENTRY = _RUN_VALIDATION_STORAGE.get("_validate_initial_screening_run")
if type(_RUN_VALIDATION_ENTRY) is not FunctionType:
    raise TypeError
_RUN_PUBLICATION_HOOKS = (
    _validate_controls_publication,
    _validate_private_child_directory,
)


def _make_run_dispatch_store(
    error_type: Any = TypeError,
) -> tuple[Callable[[Any], None], Callable[[], Any]]:
    authority: Any = None

    def install(value: Any) -> None:
        nonlocal authority
        if authority is not None:
            raise error_type
        authority = value

    def read() -> Any:
        if authority is None:
            raise error_type
        return authority

    return install, read


_install_run_dispatch_authority, _read_run_dispatch_authority = (
    _make_run_dispatch_store()
)
del _make_run_dispatch_store
_DIRECT_SERVICE_TYPES = {
    "_initial_screening_study_controls": _InitialScreeningRuntimeInputs,
    "_protocol_config": ProtocolConfig,
    "_split_manifest": SplitManifest,
    "_seed_ledger": SeedLedgerConfig,
    "_experiment_protocol": ExperimentProtocol,
    "_scheduler": Scheduler,
    "_code_research_limits": CodeResearchLimits,
    "_resource_envelope": ResourceEnvelope,
    "_qualification_only_config": QualificationOnlyConfig,
    "_problem_runtime": ProblemRuntime,
    "_qualification_runtime": QualificationRuntime,
    "_provider_call_budget": ProviderCallBudget,
    "_proposal_runtime_telemetry": ProposalRuntimeTelemetry,
    "_code_development_evaluator": CodeDevelopmentEvaluator,
    "_proposal_pipeline": ProposalPipeline,
    "_creative": CreativeLayer,
    "_branch_step_runner": BranchStepRunner,
    "_campaign_loop": CampaignLoop,
    "_explore_step_pipeline": ExploreStepPipeline,
    "_decision_finalizer": DecisionFinalizer,
    "_evaluation_orchestrator": EvaluationOrchestrator,
    "_workspace_service": WorkspaceService,
    "_research_rejection_finalizer": ResearchRejectionFinalizer,
    "_vgate": VerificationGate,
    "_branch_ctrl": BranchController,
}


def _validate_initial_screening_requested_rounds(
    requested_rounds: Any,
    owner: Any,
    caller_binding_valid: Any = True,
    run_module: ModuleType = run_validation_module,
    run_name: str = _RUN_VALIDATION_MODULE_NAME,
    run_entry: Any = _RUN_VALIDATION_ENTRY,
    sys_module: ModuleType = sys,
    sys_modules: dict[str, Any] = sys.modules,
    dispatch_reader: Callable[[], Any] = _read_run_dispatch_authority,
    safe_ops: Any = (type, vars, any, ModuleType, FunctionType, dict, str),
) -> None:
    type_fn, vars_fn, any_fn, module_type, function_type, dict_type, str_type = safe_ops
    modules_shaped = type_fn(run_module) is module_type is type_fn(sys_module)
    run_storage = vars_fn(run_module) if modules_shaped else {}
    sys_storage = vars_fn(sys_module) if modules_shaped else {}
    if not (
        (caller_binding_valid is True or caller_binding_valid is None)
        and modules_shaped
        and not (
            type_fn(run_storage) is not dict_type
            or any_fn(type_fn(name) is not str_type for name in run_storage)
            or type_fn(sys_storage) is not dict_type
            or any_fn(type_fn(name) is not str_type for name in sys_storage)
            or type_fn(run_name) is not str_type
            or type_fn(run_storage.get("__name__")) is not str_type
            or run_storage["__name__"] != run_name
            or type_fn(sys_modules) is not dict_type
            or any_fn(type_fn(name) is not str_type for name in sys_modules)
            or sys_storage.get("modules") is not sys_modules
            or sys_modules.get(run_name) is not run_module
            or type_fn(run_entry) is not function_type
            or run_storage.get("_validate_initial_screening_run") is not run_entry
        )
    ):
        caller_binding_valid = False
    valid, dispatch = caller_binding_valid, dispatch_reader()
    run_entry(requested_rounds, owner, caller_valid=valid, controls_dispatch=dispatch)


_REQUESTED_ROUNDS_CALLER_AUTHORITY = (
    "_validate_initial_screening_requested_rounds",
    _validate_initial_screening_requested_rounds,
)


def _registered_baseline(
    owner: Any,
    active: Any,
    runtime_inputs: Any,
) -> _RegisteredControlsBaseline | None:
    from scion.core.campaign import CampaignManager

    if type(owner) is not CampaignManager:
        if (
            _weak_registry_contains_owner(_REGISTERED_OWNERS, owner)
            or active is not False
            or runtime_inputs is not None
        ):
            raise TypeError
        return None
    if type(_REGISTERED_OWNERS) is not weakref.WeakKeyDictionary:
        raise TypeError
    baseline = weakref.WeakKeyDictionary.get(_REGISTERED_OWNERS, owner)
    if baseline is None and active is False and runtime_inputs is None:
        return None
    if type(baseline) is not _RegisteredControlsBaseline:
        raise TypeError
    return baseline


def _campaign_owner_storage(owner: Any) -> dict[str, Any]:
    from scion.core.campaign import CampaignManager

    descriptor = CampaignManager.__dict__.get("__dict__")
    if type(descriptor) is not GetSetDescriptorType:
        raise TypeError
    storage = GetSetDescriptorType.__get__(descriptor, owner, CampaignManager)
    _validate_exact_string_keys(storage)
    return cast(dict[str, Any], storage)


def _validate_claimed_controls_structural_shape(
    runtime_inputs: _InitialScreeningRuntimeInputs,
    owner: Any,
) -> None:
    _validate_dataclass_instance(
        runtime_inputs.qualification,
        QualificationOnlyConfig,
    )
    _validate_dataclass_instance(
        runtime_inputs.code_research_limits,
        CodeResearchLimits,
    )
    _validate_dataclass_instance(
        runtime_inputs.resource_envelope,
        ResourceEnvelope,
    )
    _validate_model_instance(runtime_inputs.protocol_config, ProtocolConfig)
    _validate_model_instance(runtime_inputs.split_manifest, SplitManifest)
    _validate_model_instance(runtime_inputs.seed_ledger, SeedLedgerConfig)
    _validate_objective_shapes(
        runtime_inputs.metric_specs,
        runtime_inputs.objective_policy,
    )
    protocol = runtime_inputs.experiment_protocol
    _validate_protocol_wrapper_shape(protocol)
    if (
        protocol.config is not runtime_inputs.protocol_config
        or protocol.split_manager._manifest is not runtime_inputs.split_manifest
        or protocol.seed_ledger._ledger is not runtime_inputs.seed_ledger
        or protocol._metric_specs is not runtime_inputs.metric_specs
        or protocol._objective_policy is not runtime_inputs.objective_policy
        or type(protocol.time_limit_sec) is not int
        or type(protocol.metrics_dir) is not str
        or type(protocol._strict_case_paths) is not bool
        or type(protocol._progress_callback) is not MethodType
    ):
        raise TypeError
    _validate_direct_service_shapes(owner, runtime_inputs)


def _validate_direct_service_shapes(
    owner: Any,
    runtime_inputs: _InitialScreeningRuntimeInputs,
) -> None:
    from scion.core.campaign import CampaignManager

    storage, services = _owner_service_values(owner)
    scheduler = runtime_inputs.scheduler
    creative = services["_creative"]
    creative_storage = vars(creative)
    if "_provider_calls" not in creative_storage:
        raise TypeError
    provider_calls = creative_storage["_provider_calls"]
    qualification_runtime = services["_qualification_runtime"]
    proposal_runtime = services["_proposal_runtime_telemetry"]
    campaign_loop = services["_campaign_loop"]
    explore_pipeline = services["_explore_step_pipeline"]
    evaluation = services["_evaluation_orchestrator"]
    branch_runner = services["_branch_step_runner"]
    verification_gate = services["_vgate"]
    if (
        type(storage.get("_campaign_dir")) is not str
        or services["_initial_screening_study_controls"] is not runtime_inputs
        or services["_protocol_config"] is not runtime_inputs.protocol_config
        or services["_split_manifest"] is not runtime_inputs.split_manifest
        or services["_seed_ledger"] is not runtime_inputs.seed_ledger
        or services["_experiment_protocol"] is not runtime_inputs.experiment_protocol
        or services["_scheduler"] is not runtime_inputs.scheduler
        or services["_code_research_limits"] is not runtime_inputs.code_research_limits
        or services["_resource_envelope"] is not runtime_inputs.resource_envelope
        or services["_qualification_only_config"] is not runtime_inputs.qualification
        or type(scheduler._max_active_branches) is not int
        or type(verification_gate._metrics_dir) is not str
        or type(branch_runner.qualification_only) is not bool
        or type(explore_pipeline.initial_screening_only) is not bool
        or type(services["_decision_finalizer"].initial_screening_only) is not bool
        or type(provider_calls) is not ProviderCaller
        or not _has_exact_methods(scheduler, Scheduler, ("select_next",))
        or not _has_exact_methods(
            creative,
            CreativeLayer,
            (
                "generate_direct_hypothesis",
                "generate_direct_code",
                "call_code_research_turn",
                "call_hypothesis_research_turn",
                "call_code_research_finalize",
            ),
        )
        or not _has_exact_methods(provider_calls, ProviderCaller, ("call",))
        or not _has_exact_methods(
            services["_provider_call_budget"],
            ProviderCallBudget,
            ("snapshot", "consume"),
        )
        or not _has_exact_methods(
            proposal_runtime,
            ProposalRuntimeTelemetry,
            ("snapshot", "attempt_scope"),
        )
        or not _has_exact_methods(
            qualification_runtime,
            QualificationRuntime,
            ("reserve_proposal_attempt",),
        )
        or not _is_bound_method(
            campaign_loop.retire_initial_screening_study_chain,
            owner,
            CampaignManager._retire_initial_screening_study_chain,
        )
        or not _is_bound_method(
            campaign_loop.park_qualification_chain,
            owner,
            CampaignManager._park_qualification_chain,
        )
        or not _is_bound_method(
            explore_pipeline.reserve_proposal_attempt,
            qualification_runtime,
            QualificationRuntime.reserve_proposal_attempt,
        )
        or not _is_bound_method(
            explore_pipeline.proposal_attempt_scope,
            proposal_runtime,
            ProposalRuntimeTelemetry.attempt_scope,
        )
        or not _is_bound_method(
            evaluation.experiment_protocol_provider,
            owner,
            CampaignManager._provide_experiment_protocol,
        )
        or not _is_bound_method(
            branch_runner.experiment_protocol_provider,
            owner,
            CampaignManager._provide_experiment_protocol,
        )
        or not _is_bound_method(
            runtime_inputs.experiment_protocol._progress_callback,
            owner,
            CampaignManager._on_protocol_progress,
        )
    ):
        raise TypeError
    _validate_pristine_storage_shapes(storage, services)


def _owner_service_values(owner: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    storage = _campaign_owner_storage(owner)
    if not set(_DIRECT_SERVICE_TYPES).issubset(storage):
        raise TypeError
    services = {name: storage[name] for name in _DIRECT_SERVICE_TYPES}
    if any(
        type(value) is not _DIRECT_SERVICE_TYPES[name]
        for name, value in services.items()
    ):
        raise TypeError
    for service in services.values():
        _validate_exact_string_keys(vars(service))
    return storage, services


def _validate_carrier_against_baseline(
    runtime_inputs: _InitialScreeningRuntimeInputs,
    baseline: _RegisteredControlsBaseline,
) -> _ControlsPublication:
    _validate_carrier_shapes(runtime_inputs, baseline)
    publication = cast(_ControlsPublication, runtime_inputs.publication)
    if (
        runtime_inputs.requested_rounds != baseline.requested_rounds
        or runtime_inputs.payload_bytes != baseline.payload_bytes
        or publication.campaign_dir != baseline.campaign_dir
        or publication.directory_fingerprints != baseline.directory_fingerprints
        or publication.leaf_fingerprint != baseline.leaf_fingerprint
        or runtime_inputs.metrics_directory_fingerprint
        != baseline.metrics_directory_fingerprint
        or not _baseline_components_match(runtime_inputs, baseline)
    ):
        raise ValueError
    return _ControlsPublication(
        campaign_dir=baseline.campaign_dir,
        directory_fingerprints=baseline.directory_fingerprints,
        leaf_fingerprint=baseline.leaf_fingerprint,
    )


def _validate_carrier_shapes(
    runtime_inputs: Any,
    baseline: _RegisteredControlsBaseline,
) -> None:
    _validate_baseline_shape(baseline)
    _validate_runtime_and_publication_shape(runtime_inputs)


def _validate_baseline_shape(baseline: _RegisteredControlsBaseline) -> None:
    _validate_exact_dataclass_storage(baseline, _RegisteredControlsBaseline)
    references = (
        baseline.runtime_inputs_ref,
        baseline.qualification_ref,
        baseline.code_research_limits_ref,
        baseline.resource_envelope_ref,
        baseline.protocol_config_ref,
        baseline.split_manifest_ref,
        baseline.seed_ledger_ref,
        baseline.experiment_protocol_ref,
        baseline.objective_policy_ref,
        baseline.scheduler_ref,
    )
    if (
        any(type(reference) is not weakref.ReferenceType for reference in references)
        or type(baseline.requested_rounds) is not int
        or type(baseline.payload_bytes) is not bytes
        or type(baseline.campaign_dir) is not str
        or not _is_exact_directory_fingerprints(baseline.directory_fingerprints)
        or not _is_exact_int_tuple(baseline.leaf_fingerprint, 4)
        or not _is_exact_int_tuple(baseline.metrics_directory_fingerprint, 2)
        or type(baseline.metric_specs) is not tuple
        or any(
            type(metric) is not ObjectiveMetricSpec for metric in baseline.metric_specs
        )
    ):
        raise TypeError


def _validate_runtime_and_publication_shape(runtime_inputs: Any) -> None:
    if type(runtime_inputs) is not _InitialScreeningRuntimeInputs:
        raise TypeError
    _validate_exact_dataclass_storage(
        runtime_inputs,
        _InitialScreeningRuntimeInputs,
    )
    publication = runtime_inputs.publication
    if type(publication) is not _ControlsPublication:
        raise TypeError
    _validate_exact_dataclass_storage(publication, _ControlsPublication)
    if (
        type(runtime_inputs.requested_rounds) is not int
        or type(runtime_inputs.payload_bytes) is not bytes
        or type(runtime_inputs.metric_specs) is not tuple
        or any(
            type(metric) is not ObjectiveMetricSpec
            for metric in runtime_inputs.metric_specs
        )
        or not _is_exact_int_tuple(runtime_inputs.metrics_directory_fingerprint, 2)
        or type(publication.campaign_dir) is not str
        or not _is_exact_directory_fingerprints(publication.directory_fingerprints)
        or not _is_exact_int_tuple(publication.leaf_fingerprint, 4)
    ):
        raise TypeError


def _validate_exact_dataclass_storage(value: Any, expected_type: type) -> None:
    storage = vars(value)
    _validate_exact_string_keys(storage)
    expected = {field.name for field in fields(expected_type)}
    if set(storage) != expected:
        raise TypeError


def _validate_exact_string_keys(value: Any) -> None:
    if type(value) is not dict:
        raise TypeError
    if any(type(key) is not str for key in value):
        raise TypeError


def _has_exact_storage_keys(value: Any, expected: set[str]) -> bool:
    storage = vars(value)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        return False
    return set(storage) == expected


def _is_exact_directory_fingerprints(value: Any) -> bool:
    if type(value) is not tuple:
        return False
    return all(_is_exact_int_tuple(item, 2) for item in value)


def _is_exact_int_tuple(value: Any, length: int) -> bool:
    if type(value) is not tuple:
        return False
    return len(value) == length and all(type(item) is int for item in value)


def _baseline_components_match(
    runtime_inputs: _InitialScreeningRuntimeInputs,
    baseline: _RegisteredControlsBaseline,
) -> bool:
    pairs = (
        (baseline.qualification_ref, runtime_inputs.qualification),
        (baseline.code_research_limits_ref, runtime_inputs.code_research_limits),
        (baseline.resource_envelope_ref, runtime_inputs.resource_envelope),
        (baseline.protocol_config_ref, runtime_inputs.protocol_config),
        (baseline.split_manifest_ref, runtime_inputs.split_manifest),
        (baseline.seed_ledger_ref, runtime_inputs.seed_ledger),
        (baseline.experiment_protocol_ref, runtime_inputs.experiment_protocol),
        (baseline.objective_policy_ref, runtime_inputs.objective_policy),
        (baseline.scheduler_ref, runtime_inputs.scheduler),
    )
    return (
        baseline.metric_specs is runtime_inputs.metric_specs
        and all(type(reference) is weakref.ReferenceType for reference, _ in pairs)
        and all(reference() is value for reference, value in pairs)
    )


def _validate_installed_runtime(
    owner: Any,
    runtime_inputs: _InitialScreeningRuntimeInputs,
    baseline: _RegisteredControlsBaseline,
) -> None:
    from scion.core.campaign import CampaignManager

    if type(owner) is not CampaignManager:
        raise ValueError
    owner_storage, services = _owner_service_values(owner)
    protocol = runtime_inputs.experiment_protocol
    if any(
        (
            services["_initial_screening_study_controls"] is not runtime_inputs,
            services["_protocol_config"] is not runtime_inputs.protocol_config,
            services["_split_manifest"] is not runtime_inputs.split_manifest,
            services["_seed_ledger"] is not runtime_inputs.seed_ledger,
            services["_experiment_protocol"] is not protocol,
            services["_scheduler"] is not runtime_inputs.scheduler,
            services["_code_research_limits"]
            is not runtime_inputs.code_research_limits,
            services["_resource_envelope"] is not runtime_inputs.resource_envelope,
            services["_qualification_only_config"] is not runtime_inputs.qualification,
        )
    ):
        raise ValueError
    _validate_protocol_objects(runtime_inputs)
    problem_runtime = services["_problem_runtime"]
    if (
        problem_runtime is None
        or problem_runtime.split_manifest is not runtime_inputs.split_manifest
        or problem_runtime.seed_ledger is not runtime_inputs.seed_ledger
    ):
        raise ValueError

    qualification_runtime = services["_qualification_runtime"]
    provider_budget = services["_provider_call_budget"]
    proposal_runtime = services["_proposal_runtime_telemetry"]
    code_evaluator = services["_code_development_evaluator"]
    proposal_pipeline = services["_proposal_pipeline"]
    creative = services["_creative"]
    provider_calls = vars(creative)["_provider_calls"]
    branch_runner = services["_branch_step_runner"]
    campaign_loop = services["_campaign_loop"]
    explore_pipeline = services["_explore_step_pipeline"]
    decision_finalizer = services["_decision_finalizer"]
    evaluation_orchestrator = services["_evaluation_orchestrator"]
    workspace_service = services["_workspace_service"]
    rejection_finalizer = services["_research_rejection_finalizer"]
    verification_gate = services["_vgate"]
    metrics_dir = os.path.join(baseline.campaign_dir, "metrics")
    protocol_metrics_dir = getattr(protocol, "metrics_dir", None)
    verification_metrics_dir = verification_gate._metrics_dir
    candidate_cap = proposal_runtime._max_hypothesis_candidates
    if type(provider_calls) is not ProviderCaller:
        raise ValueError
    qualification_value = cast(QualificationRuntime, qualification_runtime)
    budget_value = cast(ProviderCallBudget, provider_budget)
    proposal_value = cast(ProposalRuntimeTelemetry, proposal_runtime)
    if (
        qualification_value.config is not runtime_inputs.qualification
        or type(budget_value.cap) is not int
        or budget_value.cap != runtime_inputs.resource_envelope.provider_call_cap
        or proposal_value._provider_call_budget is not budget_value
        or type(candidate_cap) is not int
        or candidate_cap
        != runtime_inputs.code_research_limits.max_hypothesis_candidates
        or code_evaluator is None
        or code_evaluator.limits is not runtime_inputs.code_research_limits
        or proposal_pipeline is None
        or proposal_pipeline.code_research_limits
        is not runtime_inputs.code_research_limits
        or proposal_pipeline.code_development_evaluator is not code_evaluator
        or proposal_pipeline.creative is not creative
        or not _has_exact_methods(
            creative,
            CreativeLayer,
            (
                "generate_direct_hypothesis",
                "generate_direct_code",
                "call_code_research_turn",
                "call_hypothesis_research_turn",
                "call_code_research_finalize",
            ),
        )
        or not _has_exact_methods(provider_calls, ProviderCaller, ("call",))
        or provider_calls._provider_call_budget is not provider_budget
        or branch_runner is None
        or not _has_exact_methods(
            runtime_inputs.scheduler,
            Scheduler,
            ("select_next",),
        )
        or branch_runner.scheduler is not runtime_inputs.scheduler
        or branch_runner.verification_gate is not verification_gate
        or branch_runner.qualification_runtime is not qualification_runtime
        or branch_runner.qualification_only is not True
        or campaign_loop is None
        or campaign_loop.qualification_runtime is not qualification_runtime
        or not _is_bound_method(
            campaign_loop.retire_initial_screening_study_chain,
            owner,
            CampaignManager._retire_initial_screening_study_chain,
        )
        or not _is_bound_method(
            campaign_loop.park_qualification_chain,
            owner,
            CampaignManager._park_qualification_chain,
        )
        or explore_pipeline is None
        or explore_pipeline.verification_gate is not verification_gate
        or explore_pipeline.initial_screening_only is not True
        or not _is_bound_method(
            explore_pipeline.reserve_proposal_attempt,
            qualification_value,
            QualificationRuntime.reserve_proposal_attempt,
        )
        or not _is_bound_method(
            explore_pipeline.proposal_attempt_scope,
            proposal_value,
            ProposalRuntimeTelemetry.attempt_scope,
        )
        or decision_finalizer is None
        or decision_finalizer.initial_screening_only is not True
        or evaluation_orchestrator is None
        or type(protocol_metrics_dir) is not str
        or protocol_metrics_dir != metrics_dir
        or not _is_bound_method(
            protocol._progress_callback,
            owner,
            CampaignManager._on_protocol_progress,
        )
        or type(verification_metrics_dir) is not str
        or verification_metrics_dir != metrics_dir
        or not _is_bound_method(
            evaluation_orchestrator.experiment_protocol_provider,
            owner,
            CampaignManager._provide_experiment_protocol,
        )
        or not _is_bound_method(
            branch_runner.experiment_protocol_provider,
            owner,
            CampaignManager._provide_experiment_protocol,
        )
    ):
        raise ValueError
    _validate_shared_branch_state(
        owner_storage=owner_storage,
        workspace_service=workspace_service,
        proposal_pipeline=proposal_pipeline,
        evaluation_orchestrator=evaluation_orchestrator,
        explore_pipeline=explore_pipeline,
        branch_runner=branch_runner,
        decision_finalizer=decision_finalizer,
        rejection_finalizer=rejection_finalizer,
    )
    if (
        proposal_pipeline._hypothesis_rejection_counts
        or proposal_pipeline._last_hypothesis_rejection_reason is not None
        or explore_pipeline._active_candidates
    ):
        raise ValueError
    _validate_owner_pristine(owner, campaign_loop)
    _validate_pristine_runtime(
        qualification_runtime=qualification_runtime,
        provider_budget=budget_value,
        proposal_runtime=proposal_value,
        resource_envelope=runtime_inputs.resource_envelope,
    )
    current_payload = _runtime_payload_bytes(
        requested_rounds=runtime_inputs.requested_rounds,
        qualification=runtime_inputs.qualification,
        code_research_limits=runtime_inputs.code_research_limits,
        resource_envelope=runtime_inputs.resource_envelope,
        scheduler=runtime_inputs.scheduler,
        experiment_protocol=protocol,
    )
    if current_payload != baseline.payload_bytes:
        raise ValueError


def _validate_shared_branch_state(
    *,
    owner_storage: dict[str, Any],
    workspace_service: Any,
    proposal_pipeline: Any,
    evaluation_orchestrator: Any,
    explore_pipeline: Any,
    branch_runner: Any,
    decision_finalizer: Any,
    rejection_finalizer: Any,
) -> None:
    required_owner_keys = {
        "_branch_ctrl",
        "_branch_workspaces",
        "_branch_patches",
        "_step_history",
    }
    if not required_owner_keys.issubset(owner_storage):
        raise ValueError
    controller = owner_storage["_branch_ctrl"]
    workspaces = owner_storage["_branch_workspaces"]
    patches = owner_storage["_branch_patches"]
    history = owner_storage["_step_history"]
    if (
        type(controller) is not BranchController
        or not _has_exact_storage_keys(controller, {"_branches"})
        or type(workspace_service) is not WorkspaceService
        or type(proposal_pipeline) is not ProposalPipeline
        or type(evaluation_orchestrator) is not EvaluationOrchestrator
        or type(explore_pipeline) is not ExploreStepPipeline
        or type(branch_runner) is not BranchStepRunner
        or type(decision_finalizer) is not DecisionFinalizer
        or type(rejection_finalizer) is not ResearchRejectionFinalizer
        or workspace_service.branch_controller is not controller
        or decision_finalizer.branch_controller is not controller
        or evaluation_orchestrator.branch_controller is not controller
        or explore_pipeline.branch_controller is not controller
        or branch_runner.branch_controller is not controller
        or workspace_service.branch_workspaces is not workspaces
        or proposal_pipeline.branch_workspaces is not workspaces
        or evaluation_orchestrator.branch_workspaces is not workspaces
        or explore_pipeline.branch_workspaces is not workspaces
        or branch_runner.branch_workspaces is not workspaces
        or rejection_finalizer.branch_patches is not patches
        or decision_finalizer.branch_patches is not patches
        or evaluation_orchestrator.branch_patches is not patches
        or explore_pipeline.branch_patches is not patches
        or branch_runner.branch_patches is not patches
        or proposal_pipeline.step_history is not history
        or explore_pipeline.step_history is not history
    ):
        raise ValueError


def _validate_protocol_objects(runtime_inputs: _InitialScreeningRuntimeInputs) -> None:
    protocol = runtime_inputs.experiment_protocol
    _validate_protocol_wrapper_shape(protocol)
    if (
        protocol.config is not runtime_inputs.protocol_config
        or protocol.split_manager._manifest is not runtime_inputs.split_manifest
        or protocol.seed_ledger._ledger is not runtime_inputs.seed_ledger
        or protocol._metric_specs is not runtime_inputs.metric_specs
        or protocol._objective_policy is not runtime_inputs.objective_policy
    ):
        raise ValueError


def _validate_owner_pristine(owner: Any, campaign_loop: Any) -> None:
    if (
        type(getattr(getattr(owner, "_branch_ctrl", None), "_branches", None))
        is not dict
        or owner._branch_ctrl._branches
        or type(getattr(owner, "_branch_workspaces", None)) is not dict
        or owner._branch_workspaces
        or type(getattr(owner, "_branch_patches", None)) is not dict
        or owner._branch_patches
        or type(getattr(owner, "_step_history", None)) is not list
        or owner._step_history
        or type(getattr(owner, "_round_num", None)) is not int
        or owner._round_num != 0
        or type(getattr(owner, "_n_experiments", None)) is not int
        or owner._n_experiments != 0
        or getattr(owner, "_current_status_progress", None) is not None
        or getattr(owner, "_balance_exhausted", None) is not False
        or getattr(owner, "_external_stop_requested", None) is not False
        or getattr(owner, "_research_preflight_checked", None) is not False
        or getattr(owner, "_last_stop_reason", None) is not None
        or getattr(owner, "_last_status_result", None) is not None
        or type(getattr(owner, "_async_stop_deferral_depth", None)) is not int
        or owner._async_stop_deferral_depth != 0
        or campaign_loop.current_result is not None
        or campaign_loop.call_in_progress is not False
        or getattr(campaign_loop, "_post_return_deferral_active", None) is not False
    ):
        raise ValueError


def _validate_pristine_runtime(
    *,
    qualification_runtime: Any,
    provider_budget: Any,
    proposal_runtime: Any,
    resource_envelope: ResourceEnvelope,
) -> None:
    qualification_fields = {field.name for field in fields(QualificationRuntime)}
    expected_kinds = (
        "hypothesis",
        "hypothesis_research_turn",
        "code",
        "code_research_turn",
        "code_research_finalize",
        "other",
    )
    raw_counts = getattr(provider_budget, "_by_request_kind", None)
    budget_lock = getattr(provider_budget, "_lock", None)
    proposal_lock = getattr(proposal_runtime, "_lock", None)
    if (
        type(qualification_runtime) is not QualificationRuntime
        or not _has_exact_storage_keys(qualification_runtime, qualification_fields)
        or type(provider_budget) is not ProviderCallBudget
        or not _has_exact_storage_keys(
            provider_budget,
            {"_cap", "_used", "_by_request_kind", "_lock"},
        )
        or type(provider_budget._cap) is not int
        or provider_budget._cap != resource_envelope.provider_call_cap
        or type(provider_budget._used) is not int
        or provider_budget._used != 0
        or type(raw_counts) is not dict
        or any(type(key) is not str for key in raw_counts)
        or tuple(raw_counts) != expected_kinds
        or any(
            type(raw_counts[key]) is not int or raw_counts[key] != 0
            for key in expected_kinds
        )
        or type(budget_lock) is not LockType
        or budget_lock.locked()
        or type(proposal_runtime) is not ProposalRuntimeTelemetry
        or not _has_exact_storage_keys(
            proposal_runtime,
            {
                "_provider_call_budget",
                "_max_hypothesis_candidates",
                "_attempts",
                "_active",
                "_lock",
            },
        )
        or proposal_runtime._provider_call_budget is not provider_budget
        or type(proposal_runtime._max_hypothesis_candidates) is not int
        or not _is_bound_method(
            provider_budget.snapshot,
            provider_budget,
            ProviderCallBudget.snapshot,
        )
        or not _is_bound_method(
            provider_budget.consume,
            provider_budget,
            ProviderCallBudget.consume,
        )
        or not _is_bound_method(
            proposal_runtime.snapshot,
            proposal_runtime,
            ProposalRuntimeTelemetry.snapshot,
        )
        or type(getattr(proposal_runtime, "_attempts", None)) is not list
        or proposal_runtime._attempts
        or getattr(proposal_runtime, "_active", None) is not None
        or type(proposal_lock) is not LockType
        or proposal_lock.locked()
    ):
        raise ValueError
    counters = (
        qualification_runtime.proposal_attempts,
        qualification_runtime.formal_screening_stages,
        qualification_runtime.initial_screening_stages,
        qualification_runtime.expanded_screening_stages,
    )
    if (
        qualification_runtime.started is not False
        or any(type(value) is not int or value != 0 for value in counters)
        or qualification_runtime.pending_expansion_branch_id is not None
        or type(qualification_runtime.verified_candidate_branch_ids) is not set
        or qualification_runtime.verified_candidate_branch_ids
        or type(qualification_runtime.candidate_screening_stage_counts) is not dict
        or qualification_runtime.candidate_screening_stage_counts
    ):
        raise ValueError
    budget = provider_budget.snapshot()
    cap = resource_envelope.provider_call_cap
    if (
        type(budget) is not ProviderCallBudgetSnapshot
        or type(provider_budget.cap) is not int
        or type(cap) is not int
        or type(budget.cap) is not int
        or budget.cap != cap
        or type(budget.budget_admitted) is not int
        or budget.budget_admitted != 0
        or type(budget.remaining) is not int
        or budget.remaining != cap
        or type(budget.by_request_kind) is not tuple
    ):
        raise ValueError
    if len(budget.by_request_kind) != len(expected_kinds):
        raise ValueError
    for item, expected_kind in zip(budget.by_request_kind, expected_kinds):
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not int
            or item[0] != expected_kind
            or item[1] != 0
        ):
            raise ValueError
    proposal = proposal_runtime.snapshot(budget, terminal=False)
    if (
        type(proposal) is not ProposalRuntimeSnapshot
        or proposal.provider_calls is not budget
        or type(proposal.attempts) is not tuple
        or proposal.attempts
    ):
        raise ValueError


def _is_bound_method(actual: Any, owner: Any, function: Any) -> bool:
    return (
        type(actual) is MethodType
        and getattr(actual, "__self__", None) is owner
        and getattr(actual, "__func__", None) is function
    )


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
            getattr(instance, name, None),
            instance,
            getattr(expected_type, name),
        )
        for name in names
    )


_CONTROLS_RUN_DISPATCH_NAMES = (
    "_campaign_owner_storage",
    "_registered_baseline",
    "_validate_baseline_shape",
    "_validate_carrier_against_baseline",
    "_validate_claimed_controls_structural_shape",
    "_validate_controls_publication",
    "_validate_installed_runtime",
    "_validate_private_child_directory",
    "_validate_runtime_and_publication_shape",
)
_PROVIDER_RUN_DISPATCH_NAMES = (
    "_prepare_provider_policy_run_validation",
    "_validate_provider_policy_publication",
    "_validate_provider_policy_installed_runtime",
)
_CONTROLS_SELF_MODULE = sys.modules[__name__]
_CONTROLS_SELF_NAME = vars(_CONTROLS_SELF_MODULE)["__name__"]
_PROVIDER_VALIDATION_NAME = vars(provider_validation_module)["__name__"]
_install_run_dispatch_authority(
    (
        _CONTROLS_SELF_MODULE,
        _CONTROLS_SELF_NAME,
        _CONTROLS_RUN_DISPATCH_NAMES,
        tuple(
            vars(_CONTROLS_SELF_MODULE)[name] for name in _CONTROLS_RUN_DISPATCH_NAMES
        ),
        provider_validation_module,
        _PROVIDER_VALIDATION_NAME,
        _PROVIDER_RUN_DISPATCH_NAMES,
        tuple(
            vars(provider_validation_module)[name]
            for name in _PROVIDER_RUN_DISPATCH_NAMES
        ),
    )
)
del _install_run_dispatch_authority
