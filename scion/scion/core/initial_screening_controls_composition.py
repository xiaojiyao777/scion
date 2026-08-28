"""Construction-time implementation for private initial-screening controls."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from scion.contract.gate import ContractGate
from scion.core.models import ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.core.production_boundary import validate_production_campaign_boundary
from scion.core.verification_factory import CampaignVerificationFactory
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)

_INTEGRATION_MODULE_NAME = "scion.core.initial_screening_research_context_integration"
if type(sys.modules) is not dict or type(sys.modules.get(__name__)) is not ModuleType:
    raise TypeError
_SELF_MODULE = sys.modules[__name__]
_CONTROLS_COMPOSITION_EDGE_NAMES = (
    "_install_research_context_integration_authority",
    "_validated_research_context_runtime_installer",
    "_resolve_active_research_context_installer",
    "_install_active_research_context_capsule",
    "_prepare_initial_screening_controls_setup_impl",
)
_CONTROLS_COMPOSITION_EDGE_HOLDER: list[Any] = [None]


def _make_integration_authority_store() -> tuple[Any, Any]:
    authority: Any = None
    type_fn, tuple_type, len_fn, module_type = type, tuple, len, ModuleType

    def install(module: Any, validator: Any, entries: Any) -> None:
        nonlocal authority
        if (
            authority is not None
            or type_fn(module) is not module_type
            or type_fn(validator) is not tuple_type
            or len_fn(validator) != 2
            or type_fn(entries) is not tuple_type
        ):
            raise TypeError
        authority = (module, validator, entries)

    def read() -> Any:
        return authority

    return install, read


(
    _install_research_context_integration_authority,
    _read_research_context_integration_authority,
) = _make_integration_authority_store()
del _make_integration_authority_store


def _validate_controls_composition_edges(
    edge_names: tuple[str, ...] = _CONTROLS_COMPOSITION_EDGE_NAMES,
    edge_holder: list[Any] = _CONTROLS_COMPOSITION_EDGE_HOLDER,
    self_module: ModuleType = _SELF_MODULE,
    self_name: str = __name__,
) -> None:
    """Lock the active controls caller before it performs any work."""

    if type(self_module) is not ModuleType or type(sys.modules) is not dict:
        raise TypeError
    storage = vars(self_module)
    if (
        type(storage) is not dict
        or any(type(key) is not str for key in storage)
        or any(type(key) is not str for key in sys.modules)
        or storage.get("__name__") != self_name
        or sys.modules.get(self_name) is not self_module
        or storage.get("_SELF_MODULE") is not self_module
        or storage.get("_CONTROLS_COMPOSITION_EDGE_NAMES") is not edge_names
        or storage.get("_CONTROLS_COMPOSITION_EDGE_HOLDER") is not edge_holder
        or type(edge_names) is not tuple
        or type(edge_holder) is not list
        or len(edge_holder) != 1
    ):
        raise TypeError
    bindings = edge_holder[0]
    if (
        type(bindings) is not tuple
        or len(bindings) != len(edge_names)
        or storage.get("_CONTROLS_COMPOSITION_EDGE_BINDINGS") is not bindings
    ):
        raise TypeError
    for expected_name, binding in zip(
        edge_names,
        cast(tuple[Any, ...], bindings),
        strict=True,
    ):
        if (
            type(expected_name) is not str
            or type(binding) is not tuple
            or len(binding) != 2
            or binding[0] != expected_name
            or storage.get(expected_name) is not binding[1]
        ):
            raise TypeError


def _validated_research_context_runtime_installer(
    authority_reader: Any = _read_research_context_integration_authority,
) -> Any:
    """Resolve the opt-in runtime installer after its router validates."""

    authority = authority_reader()
    if authority is None:
        from scion.core import initial_screening_research_context_integration

        del initial_screening_research_context_integration
        authority = authority_reader()
    if type(authority) is not tuple or len(authority) != 3:
        raise TypeError
    integration_module, validator_binding, entry_bindings = authority

    if (
        type(integration_module) is not ModuleType
        or type(sys.modules) is not dict
        or any(type(key) is not str for key in sys.modules)
        or sys.modules.get(_INTEGRATION_MODULE_NAME) is not integration_module
    ):
        raise TypeError
    storage = vars(integration_module)
    if type(storage) is not dict or any(type(key) is not str for key in storage):
        raise TypeError
    current_name = storage.get("__name__")
    if (
        type(current_name) is not str
        or current_name != _INTEGRATION_MODULE_NAME
        or storage.get("_INTEGRATION_VALIDATOR_BINDING") is not validator_binding
        or type(validator_binding) is not tuple
        or len(validator_binding) != 2
        or validator_binding[0] != "_validate_integration_dependencies"
        or storage.get(validator_binding[0]) is not validator_binding[1]
        or not callable(validator_binding[1])
    ):
        raise TypeError
    validator = validator_binding[1]
    validator()
    name = "_install_research_context_runtime_capsule"
    if storage.get("_INTEGRATION_ENTRY_BINDINGS") is not entry_bindings:
        raise TypeError
    entry = storage.get(name)
    if type(entry_bindings) is not tuple:
        raise TypeError
    matches = tuple(
        item
        for item in entry_bindings
        if (
            type(item) is tuple
            and len(item) == 2
            and type(item[0]) is str
            and item[0] == name
        )
    )
    if len(matches) != 1 or matches[0][1] is not entry:
        raise TypeError
    return entry


def _resolve_active_research_context_installer(
    research_context: Any,
    integration_resolver: Any,
    edge_validator: Any,
    self_module: Any,
) -> Any:
    if research_context is None:
        return None
    edge_validator()
    if type(self_module) is not ModuleType:
        raise TypeError
    self_storage = vars(self_module)
    if (
        type(self_storage) is not dict
        or any(type(key) is not str for key in self_storage)
        or self_storage.get("_validated_research_context_runtime_installer")
        is not integration_resolver
    ):
        raise TypeError
    install_research_context = cast(Any, integration_resolver)()
    if not callable(install_research_context):
        raise TypeError
    return install_research_context


def _install_active_research_context_capsule(
    research_context: Any,
    problem_runtime: Any,
    install_research_context: Any,
) -> None:
    if research_context is None:
        return
    install_research_context(research_context, problem_runtime)
    research_storage = vars(research_context)
    runtime_storage = vars(problem_runtime)
    context_manager = runtime_storage.get("_ctx_manager")
    context_storage = vars(context_manager)
    capsule = research_storage.get("capsule")
    capsule_attribute = "_initial_screening_research_context_capsule"
    if (
        type(research_storage) is not dict
        or any(type(key) is not str for key in research_storage)
        or type(runtime_storage) is not dict
        or any(type(key) is not str for key in runtime_storage)
        or type(context_storage) is not dict
        or any(type(key) is not str for key in context_storage)
        or capsule is None
        or runtime_storage.get(capsule_attribute) is not capsule
        or context_storage.get(capsule_attribute) is not capsule
    ):
        raise TypeError


def _initial_screening_protected_roots(
    *,
    problem_spec: Any,
    champion: Any,
    split_manifest: Any,
    development_suites: tuple[Any, ...],
) -> tuple[str, ...]:
    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    candidates = [
        getattr(champion, "code_snapshot_path", None),
        getattr(spec_v1, "root_dir", None),
        *(getattr(split_manifest, "safe_data_roots", ()) or ()),
        *(getattr(suite, "source_root", None) for suite in development_suites),
    ]
    roots: list[str] = []
    for candidate in candidates:
        if candidate is None:
            continue
        if type(candidate) is not str or not candidate or "\x00" in candidate:
            raise TypeError
        root = str(Path(candidate).expanduser().resolve(strict=False))
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _retire_initial_screening_study_chain_impl(
    owner: Any,
    branch_id: str,
    decision: Any,
) -> None:
    runtime = owner._qualification_runtime
    if runtime is None:
        raise RuntimeError("initial screening retirement requires qualification")
    runtime.validate_initial_screening_retirement(branch_id)
    branch = owner._branch_ctrl.get_branch(branch_id)
    owner._branch_ctrl.park_initial_screening_study_branch(branch_id, decision)
    try:
        owner._workspace_service.discard_branch_workspace(branch_id)
    finally:
        owner._branch_workspaces.pop(branch_id, None)
        owner._branch_patches.pop(branch_id, None)
        branch.current_code_hash = None
        branch.hypothesis = None
        branch.direction = None


def _prepare_initial_screening_controls_setup_impl(
    *,
    owner: Any,
    request: Any,
    problem_spec: Any,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    champion: Any,
    campaign_dir: str,
    experiment_protocol: Any,
    adapter: Any,
    verification_gate: Any | None,
    operator_execute_signature: str | None,
    research_input: Any | None,
    research_history: Any,
    resource_envelope: Any | None,
    code_research_limits: Any | None,
    qualification_only: Any | None,
    problem_declaration: Any | None = None,
    research_context: Any | None = None,
    integration_resolver: Any = _validated_research_context_runtime_installer,
    edge_validator: Any = _validate_controls_composition_edges,
    active_installer_resolver: Any = _resolve_active_research_context_installer,
    active_capsule_installer: Any = _install_active_research_context_capsule,
    protected_roots_resolver: Any = _initial_screening_protected_roots,
    self_module: ModuleType = _SELF_MODULE,
) -> Any:
    """Publish and return one fixed-error, config-subset runtime setup."""

    from scion.core.campaign import CampaignManager
    from scion.core.campaign_composition import (
        _InitialScreeningControlsSetup,
    )
    from scion.core.initial_screening_study_controls import (
        _ERROR,
        _bind_controls_publication,
        _InitialScreeningStudyControlsError,
        _prepare_initial_screening_runtime_inputs,
        _write_initial_screening_study_controls,
    )

    failed = False
    result: Any | None = None
    try:
        install_research_context = (
            None
            if research_context is None
            else active_installer_resolver(
                research_context,
                integration_resolver,
                edge_validator,
                self_module,
            )
        )
        if type(owner) is not CampaignManager:
            raise TypeError
        if verification_gate is not None:
            raise ValueError
        runtime_inputs = _prepare_initial_screening_runtime_inputs(
            request=request,
            qualification=qualification_only,
            code_research_limits=code_research_limits,
            resource_envelope=resource_envelope,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            experiment_protocol=experiment_protocol,
            campaign_dir=campaign_dir,
        )
        frozen_config = runtime_inputs.protocol_config
        frozen_manifest = runtime_inputs.split_manifest
        frozen_ledger = runtime_inputs.seed_ledger
        frozen_protocol = runtime_inputs.experiment_protocol
        if type(champion) is not ChampionState:
            raise TypeError
        champion_storage = vars(champion)
        if type(champion_storage) is not dict or any(
            type(key) is not str for key in champion_storage
        ):
            raise TypeError
        champion_snapshot_path = champion_storage.get("code_snapshot_path")
        if (
            type(champion_snapshot_path) is not str
            or not champion_snapshot_path
            or "\x00" in champion_snapshot_path
        ):
            raise TypeError
        development_suites = declared_development_suites(problem_spec)
        development_workspace_paths = declared_development_workspace_paths(problem_spec)
        development_problem_package_paths = declared_development_problem_package_paths(
            problem_spec
        )
        validate_development_closure_boundary(
            problem_spec=problem_spec,
            suites=development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            split_manifest=frozen_manifest,
            champion_root=champion_snapshot_path,
        )
        problem_runtime = ProblemRuntime(
            problem_spec=problem_spec,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            research_input=research_input,
            research_history=research_history,
            development_suites=development_suites,
        )
        contract_gate = ContractGate(
            problem_spec,
            operator_execute_signature=operator_execute_signature,
            adapter=adapter,
            champion_snapshot_provider=lambda: getattr(
                getattr(owner, "_champion", champion),
                "code_snapshot_path",
                None,
            ),
        )
        frozen_protocol.set_problem_adapter(adapter)
        installed_verification_gate = CampaignVerificationFactory.build(
            problem_spec=problem_spec,
            verification_gate=verification_gate,
            experiment_protocol=frozen_protocol,
            campaign_dir=campaign_dir,
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
        )
        validate_production_campaign_boundary(
            problem_spec=problem_spec,
            experiment_protocol=frozen_protocol,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            verification_gate=installed_verification_gate,
        )
        protected_roots = protected_roots_resolver(
            problem_spec=problem_spec,
            champion=champion,
            split_manifest=frozen_manifest,
            development_suites=development_suites,
        )
        if problem_declaration is not None:
            from scion.core.initial_screening_problem_spec_validation import (
                _validate_problem_spec_prepublication,
            )

            _validate_problem_spec_prepublication(
                problem_declaration,
                (
                    runtime_inputs,
                    problem_runtime,
                    contract_gate,
                    frozen_protocol,
                    installed_verification_gate,
                ),
            )
        if research_context is not None:
            active_capsule_installer(
                research_context,
                problem_runtime,
                install_research_context,
            )
        publication = _write_initial_screening_study_controls(
            campaign_dir,
            runtime_inputs.payload_bytes,
            protected_roots=protected_roots,
        )
        runtime_inputs = _bind_controls_publication(runtime_inputs, publication)
        result = _InitialScreeningControlsSetup(
            code_research_limits=runtime_inputs.code_research_limits,
            resource_envelope=runtime_inputs.resource_envelope,
            qualification=runtime_inputs.qualification,
            protocol_config=frozen_config,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            experiment_protocol=frozen_protocol,
            problem_runtime=problem_runtime,
            contract_gate=contract_gate,
            verification_gate=installed_verification_gate,
            development_suites=development_suites,
            development_workspace_paths=development_workspace_paths,
            development_problem_package_paths=development_problem_package_paths,
            runtime_inputs=runtime_inputs,
        )
    except Exception:  # noqa: BLE001 - sanitize the private opt-in boundary
        failed = True
    if failed or result is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return result


_CONTROLS_COMPOSITION_EDGE_BINDINGS = tuple(
    (name, vars(_SELF_MODULE)[name]) for name in _CONTROLS_COMPOSITION_EDGE_NAMES
)
_CONTROLS_COMPOSITION_EDGE_HOLDER[0] = _CONTROLS_COMPOSITION_EDGE_BINDINGS
