"""Thin composition hooks for private initial-screening declarations."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any

_INTEGRATION_MODULE_NAME = "scion.core.initial_screening_research_context_integration"
if type(sys.modules) is not dict or type(sys.modules.get(__name__)) is not ModuleType:
    raise TypeError
_SELF_MODULE = sys.modules[__name__]
_DECLARATION_EDGE_NAMES = (
    "_install_research_context_integration_authority",
    "_validated_research_context_integration_entry",
    "_prepare_initial_screening_declarations",
    "_publish_initial_screening_declarations",
    "_install_initial_screening_declaration_carriers",
    "_install_initial_screening_research_context_owner",
    "_finalize_initial_screening_declarations",
)
_DECLARATION_EDGE_HOLDER: list[Any] = [None]
_DECLARATION_VALIDATOR_HOLDER: list[Any] = [None]


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


def _validated_research_context_integration_entry(
    name: str,
    authority_reader: Any = _read_research_context_integration_authority,
) -> Any:
    """Resolve one opt-in integration edge only after its router validates."""

    authority = authority_reader()
    if authority is None:
        from scion.core import initial_screening_research_context_integration

        del initial_screening_research_context_integration
        authority = authority_reader()
    if type(authority) is not tuple or len(authority) != 3:
        raise TypeError
    integration_module, validator_binding, entry_bindings = authority

    if (
        type(name) is not str
        or type(integration_module) is not ModuleType
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


def _validate_research_context_declaration_edges(
    edge_names: tuple[str, ...] = _DECLARATION_EDGE_NAMES,
    edge_holder: list[Any] = _DECLARATION_EDGE_HOLDER,
    validator_holder: list[Any] = _DECLARATION_VALIDATOR_HOLDER,
    self_module: ModuleType = _SELF_MODULE,
    self_name: str = __name__,
    sys_modules: dict[str, Any] = sys.modules,
    module_type: Any = ModuleType,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    zip_fn: Any = zip,
    tuple_type: Any = tuple,
    list_type: Any = list,
    dict_type: Any = dict,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> None:
    """Lock every active declaration edge before the first active action."""

    if type_fn(self_module) is not module_type or type_fn(sys_modules) is not dict_type:
        raise error_type
    storage = vars_fn(self_module)
    if (
        type_fn(storage) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in storage)
        or any_fn(type_fn(key) is not str_type for key in sys_modules)
        or sys_modules.get(self_name) is not self_module
        or storage.get("__name__") != self_name
        or storage.get("_SELF_MODULE") is not self_module
        or storage.get("_DECLARATION_EDGE_NAMES") is not edge_names
        or storage.get("_DECLARATION_EDGE_HOLDER") is not edge_holder
        or storage.get("_DECLARATION_VALIDATOR_HOLDER") is not validator_holder
        or type_fn(edge_names) is not tuple_type
        or any_fn(type_fn(name) is not str_type for name in edge_names)
        or any_fn(
            type_fn(holder) is not list_type or len_fn(holder) != 1
            for holder in (edge_holder, validator_holder)
        )
    ):
        raise error_type
    edges = edge_holder[0]
    validator_binding = validator_holder[0]
    if (
        type_fn(edges) is not tuple_type
        or len_fn(edges) != len_fn(edge_names)
        or storage.get("_DECLARATION_EDGE_BINDINGS") is not edges
        or type_fn(validator_binding) is not tuple_type
        or len_fn(validator_binding) != 2
        or validator_binding[0] != "_validate_research_context_declaration_edges"
        or storage.get("_DECLARATION_VALIDATOR_BINDING") is not validator_binding
        or storage.get(validator_binding[0]) is not validator_binding[1]
    ):
        raise error_type
    for expected_name, binding in zip_fn(edge_names, edges):
        if (
            type_fn(binding) is not tuple_type
            or len_fn(binding) != 2
            or binding[0] != expected_name
            or storage.get(expected_name) is not binding[1]
        ):
            raise error_type


@dataclass(frozen=True, repr=False)
class _PreparedInitialScreeningDeclarations:
    provider_policy: Any | None
    problem_spec: Any | None
    research_context: Any | None
    runtime_problem_spec: Any
    runtime_adapter: Any
    runtime_operator_execute_signature: str | None
    runtime_experiment_protocol: Any

    def __repr__(self) -> str:
        return "_PreparedInitialScreeningDeclarations(<redacted>)"

    __str__ = __repr__


def _prepare_initial_screening_declarations(
    *,
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
    llm_client: Any,
    problem_spec: Any,
    adapter: Any,
    operator_execute_signature: str | None,
    experiment_protocol: Any,
    research_request: Any | None = None,
    research_input: Any | None = None,
    research_history: Any = (),
    integration_resolver: Any = _validated_research_context_integration_entry,
    edge_validator: Any = _validate_research_context_declaration_edges,
    self_module: ModuleType = _SELF_MODULE,
) -> _PreparedInitialScreeningDeclarations:
    """Freeze every requested declaration before the controls root is created."""

    if research_request is not None:
        edge_validator()
        if type(self_module) is not ModuleType:
            raise TypeError
        self_storage = vars(self_module)
        if (
            type(self_storage) is not dict
            or any(type(key) is not str for key in self_storage)
            or self_storage.get("_validated_research_context_integration_entry")
            is not integration_resolver
        ):
            raise TypeError

    from scion.core.initial_screening_study_provider_policy import (
        _ERROR as _PROVIDER_POLICY_ERROR,
    )
    from scion.core.initial_screening_study_provider_policy import (
        _InitialScreeningProviderPolicyError,
        _prepare_initial_screening_provider_policy,
        _reject_reused_provider_client_without_marker,
    )

    _reject_reused_provider_client_without_marker(provider_request, llm_client)
    provider_inputs = None
    if provider_request is not None:
        if controls_request is None:
            raise _InitialScreeningProviderPolicyError(_PROVIDER_POLICY_ERROR)
        provider_inputs = _prepare_initial_screening_provider_policy(
            provider_request, llm_client
        )
    problem_inputs = None
    runtime_protocol = experiment_protocol
    if problem_request is not None:
        from scion.core.initial_screening_problem_spec import (
            _prepare_initial_screening_problem_spec,
            _problem_spec_protocol_input,
        )

        problem_inputs = _prepare_initial_screening_problem_spec(
            problem_request,
            controls_request,
            provider_request,
            problem_spec,
            adapter,
            operator_execute_signature,
        )
        runtime_protocol = _problem_spec_protocol_input(
            experiment_protocol, problem_inputs
        )
        problem_spec = problem_inputs.problem_spec
        adapter = problem_inputs.adapter
        operator_execute_signature = problem_inputs.operator_execute_signature
    research_context = None
    if research_request is not None:
        edge_validator()
        if (
            vars(self_module).get("_validated_research_context_integration_entry")
            is not integration_resolver
        ):
            raise TypeError
        if not callable(integration_resolver):
            raise TypeError
        prepare_research_context = integration_resolver(
            "_prepare_research_context_integration"
        )
        if not callable(prepare_research_context):
            raise TypeError

        research_context = prepare_research_context(
            research_request,
            controls_request,
            provider_request,
            problem_request,
            problem_inputs,
            research_input=research_input,
            research_history=research_history,
        )
        if research_context is None:
            raise TypeError
    return _PreparedInitialScreeningDeclarations(
        provider_policy=provider_inputs,
        problem_spec=problem_inputs,
        research_context=research_context,
        runtime_problem_spec=problem_spec,
        runtime_adapter=adapter,
        runtime_operator_execute_signature=operator_execute_signature,
        runtime_experiment_protocol=runtime_protocol,
    )


def _publish_initial_screening_declarations(
    prepared: _PreparedInitialScreeningDeclarations,
    controls_setup: Any,
    integration_resolver: Any = _validated_research_context_integration_entry,
    edge_validator: Any = _validate_research_context_declaration_edges,
    self_module: ModuleType = _SELF_MODULE,
) -> _PreparedInitialScreeningDeclarations:
    """Publish provider second, problem third, and research context fourth."""

    provider_inputs = prepared.provider_policy
    problem_inputs = prepared.problem_spec
    research_context = prepared.research_context
    if research_context is not None:
        edge_validator()
        if type(self_module) is not ModuleType:
            raise TypeError
        self_storage = vars(self_module)
        if (
            type(self_storage) is not dict
            or any(type(key) is not str for key in self_storage)
            or self_storage.get("_validated_research_context_integration_entry")
            is not integration_resolver
        ):
            raise TypeError
    if provider_inputs is not None:
        from scion.core.initial_screening_study_provider_policy import (
            _publish_initial_screening_provider_policy,
        )

        provider_inputs = _publish_initial_screening_provider_policy(
            provider_inputs, controls_setup.runtime_inputs.publication
        )
    if problem_inputs is not None:
        from scion.core.initial_screening_problem_spec import (
            _publish_initial_screening_problem_spec,
        )

        problem_inputs = _publish_initial_screening_problem_spec(
            problem_inputs,
            controls_setup.runtime_inputs,
            provider_inputs,
        )
    if research_context is not None:
        edge_validator()
        if (
            vars(self_module).get("_validated_research_context_integration_entry")
            is not integration_resolver
        ):
            raise TypeError
        if not callable(integration_resolver):
            raise TypeError
        publish_research_context = integration_resolver(
            "_publish_research_context_integration"
        )
        if not callable(publish_research_context):
            raise TypeError

        research_context = publish_research_context(
            research_context,
            controls_setup,
            provider_inputs,
            problem_inputs,
        )
        if research_context is None:
            raise TypeError
    return _PreparedInitialScreeningDeclarations(
        provider_policy=provider_inputs,
        problem_spec=problem_inputs,
        research_context=research_context,
        runtime_problem_spec=prepared.runtime_problem_spec,
        runtime_adapter=prepared.runtime_adapter,
        runtime_operator_execute_signature=(
            prepared.runtime_operator_execute_signature
        ),
        runtime_experiment_protocol=prepared.runtime_experiment_protocol,
    )


def _install_initial_screening_declaration_carriers(
    owner: Any,
    prepared: _PreparedInitialScreeningDeclarations,
    edge_validator: Any = _validate_research_context_declaration_edges,
) -> None:
    """Install only carriers that were explicitly requested and published."""

    if prepared.research_context is not None:
        edge_validator()

    if prepared.provider_policy is not None:
        owner._initial_screening_provider_policy_active = True
        owner._initial_screening_provider_policy = prepared.provider_policy
    if prepared.problem_spec is not None:
        owner._initial_screening_problem_spec_active = True
        owner._initial_screening_problem_spec = prepared.problem_spec


def _install_initial_screening_research_context_owner(
    owner: Any,
    prepared: _PreparedInitialScreeningDeclarations,
    integration_resolver: Any = _validated_research_context_integration_entry,
    edge_validator: Any = _validate_research_context_declaration_edges,
    self_module: ModuleType = _SELF_MODULE,
) -> None:
    """Install research context after the owner has its ProblemRuntime."""

    if prepared.research_context is None:
        return
    edge_validator()
    if type(self_module) is not ModuleType:
        raise TypeError
    self_storage = vars(self_module)
    if (
        type(self_storage) is not dict
        or any(type(key) is not str for key in self_storage)
        or self_storage.get("_validated_research_context_integration_entry")
        is not integration_resolver
    ):
        raise TypeError
    if not callable(integration_resolver):
        raise TypeError
    install_research_context = integration_resolver(
        "_install_published_research_context_owner"
    )
    if not callable(install_research_context):
        raise TypeError

    install_research_context(owner, prepared.research_context)


def _finalize_initial_screening_declarations(
    owner: Any,
    controls_setup: Any,
    prepared: _PreparedInitialScreeningDeclarations,
    edge_validator: Any = _validate_research_context_declaration_edges,
) -> None:
    """Register existing declarations first and research context last."""

    if prepared.research_context is not None:
        edge_validator()

    if controls_setup is not None:
        from scion.core.initial_screening_study_controls import (
            _register_initial_screening_controls_owner,
        )

        _register_initial_screening_controls_owner(
            owner,
            owner._initial_screening_study_controls,
        )
    if prepared.problem_spec is not None:
        from scion.core.initial_screening_problem_spec import (
            _register_initial_screening_problem_spec_owner,
        )

        _register_initial_screening_problem_spec_owner(owner, prepared.problem_spec)
    if prepared.provider_policy is not None:
        from scion.core.initial_screening_study_provider_policy import (
            _finalize_initial_screening_provider_policy,
        )

        _finalize_initial_screening_provider_policy(owner, prepared.provider_policy)
    if prepared.research_context is not None:
        from scion.core.initial_screening_research_context_validation import (
            _register_initial_screening_research_context_owner,
        )

        _register_initial_screening_research_context_owner(
            owner,
            prepared.research_context,
        )


_DECLARATION_EDGE_BINDINGS = tuple(
    (name, vars(_SELF_MODULE)[name]) for name in _DECLARATION_EDGE_NAMES
)
_DECLARATION_EDGE_HOLDER[0] = _DECLARATION_EDGE_BINDINGS
_DECLARATION_VALIDATOR_BINDING = (
    "_validate_research_context_declaration_edges",
    _validate_research_context_declaration_edges,
)
_DECLARATION_VALIDATOR_HOLDER[0] = _DECLARATION_VALIDATOR_BINDING
