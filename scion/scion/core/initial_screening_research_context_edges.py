from __future__ import annotations

import sys
import weakref
from types import MappingProxyType, ModuleType
from typing import Any, cast

import scion.core as core_module
import scion.core.features as features_module
import scion.core.initial_screening_problem_spec as problem_spec_module
import scion.core.initial_screening_problem_spec_validation as problem_validation_module
import scion.core.initial_screening_study_controls as controls_module
import scion.core.initial_screening_study_provider_policy as provider_policy_module
from scion.core import campaign as campaign_module
from scion.core import campaign_composition as campaign_composition_module
from scion.core import (
    initial_screening_controls_composition as controls_composition_module,
)
from scion.core import (
    initial_screening_declaration_composition as declaration_composition_module,
)
from scion.core import (
    initial_screening_research_context as research_context_module,
)
from scion.proposal.context_manager import manager as context_manager_module

_MODULE_NAMES = (
    "scion.core",
    "scion.core.campaign",
    "scion.core.campaign_composition",
    "scion.core.features",
    "scion.core.initial_screening_controls_composition",
    "scion.core.initial_screening_declaration_composition",
    "scion.core.initial_screening_problem_spec",
    "scion.core.initial_screening_problem_spec_validation",
    "scion.core.initial_screening_research_context",
    "scion.core.initial_screening_study_controls",
    "scion.core.initial_screening_study_provider_policy",
    "scion.proposal.context_manager.manager",
)
_SOURCE_MODULES = (
    core_module,
    campaign_module,
    campaign_composition_module,
    features_module,
    controls_composition_module,
    declaration_composition_module,
    problem_spec_module,
    problem_validation_module,
    research_context_module,
    controls_module,
    provider_policy_module,
    context_manager_module,
)
if type(sys.modules) is not dict or any(type(name) is not str for name in sys.modules):
    raise TypeError
if any(type(module) is not ModuleType for module in _SOURCE_MODULES):
    raise TypeError
_SOURCE_STORAGES = tuple(vars(module) for module in _SOURCE_MODULES)
if any(
    type(storage) is not dict or any(type(key) is not str for key in storage)
    for storage in _SOURCE_STORAGES
):
    raise TypeError
for _module_name, _module, _storage in zip(
    _MODULE_NAMES,
    _SOURCE_MODULES,
    _SOURCE_STORAGES,
    strict=True,
):
    _current_name = _storage.get("__name__")
    if (
        type(_current_name) is not str
        or _current_name != _module_name
        or sys.modules.get(_module_name) is not _module
    ):
        raise TypeError

(
    _core_storage,
    _campaign_storage,
    _campaign_composition_storage,
    _features_storage,
    _controls_composition_storage,
    _declaration_composition_storage,
    _problem_spec_storage,
    _problem_validation_storage,
    _research_context_storage,
    _controls_storage,
    _provider_policy_storage,
    _context_manager_storage,
) = _SOURCE_STORAGES

_ERROR = _research_context_storage["_ERROR"]
_RESEARCH_CONTEXT_ERROR = _research_context_storage[
    "_InitialScreeningResearchContextError"
]
_COMPOSE_CAMPAIGN_SERVICES = _campaign_composition_storage["compose_campaign_services"]
_CAMPAIGN_COMPOSITION_BINDINGS = _campaign_composition_storage[
    "_CAMPAIGN_COMPOSITION_ACTIVE_EDGE_BINDINGS"
]
_CONTROLS_COMPOSITION_BINDINGS = _controls_composition_storage[
    "_CONTROLS_COMPOSITION_EDGE_BINDINGS"
]
_CONTROLS_COMPOSITION_VALIDATOR = _controls_composition_storage[
    "_validate_controls_composition_edges"
]
_DECLARATION_BINDINGS = _declaration_composition_storage["_DECLARATION_EDGE_BINDINGS"]
_DECLARATION_VALIDATOR_BINDING = _declaration_composition_storage[
    "_DECLARATION_VALIDATOR_BINDING"
]
_DECLARATION_INTEGRATION_AUTHORITY_INSTALLER = _declaration_composition_storage[
    "_install_research_context_integration_authority"
]
_CONTROLS_INTEGRATION_AUTHORITY_INSTALLER = _controls_composition_storage[
    "_install_research_context_integration_authority"
]
_CAMPAIGN_EDGE_AUTHORITY_HOLDER = _campaign_storage[
    "_RESEARCH_CONTEXT_EDGE_AUTHORITY_HOLDER"
]
_CAMPAIGN_EDGE_AUTHORITY_INSTALLER = _campaign_storage[
    "_install_research_context_edge_authority"
]
_CAMPAIGN_EDGE_AUTHORITY_READER = _campaign_storage[
    "_read_research_context_edge_authority"
]
_CONTEXT_EDGE_AUTHORITY_HOLDER = _context_manager_storage[
    "_RESEARCH_CONTEXT_EDGE_AUTHORITY_HOLDER"
]
_CONTEXT_EDGE_AUTHORITY_INSTALLER = _context_manager_storage[
    "_install_research_context_edge_authority"
]
_CONTEXT_EDGE_AUTHORITY_READER = _context_manager_storage[
    "_read_research_context_edge_authority"
]
_CONTROLS_INTEGRATION_MODULE_NAME = _controls_composition_storage[
    "_INTEGRATION_MODULE_NAME"
]
_DECLARATION_INTEGRATION_MODULE_NAME = _declaration_composition_storage[
    "_INTEGRATION_MODULE_NAME"
]
if (
    type(_CONTROLS_INTEGRATION_MODULE_NAME) is not str
    or _CONTROLS_INTEGRATION_MODULE_NAME
    != "scion.core.initial_screening_research_context_integration"
    or type(_DECLARATION_INTEGRATION_MODULE_NAME) is not str
    or _DECLARATION_INTEGRATION_MODULE_NAME
    != "scion.core.initial_screening_research_context_integration"
):
    raise TypeError


def _captured_bindings(
    module: ModuleType,
    storage: dict[str, Any],
) -> tuple[Any, ...]:
    return tuple(
        (module, name, value)
        for name, value in storage.items()
        if name != "__warningregistry__"
    )


_SOURCE_BINDINGS = tuple(
    binding
    for module, storage in zip(_SOURCE_MODULES, _SOURCE_STORAGES, strict=True)
    for binding in _captured_bindings(module, storage)
)
_SOURCE_NAMESETS = tuple(
    (module, frozenset(name for name in storage if name != "__warningregistry__"))
    for module, storage in zip(_SOURCE_MODULES[1:], _SOURCE_STORAGES[1:], strict=True)
)
_composition_os = _campaign_composition_storage["os"]
_composition_datetime = _campaign_composition_storage["datetime"]
_composition_threading = _campaign_composition_storage["threading"]
_verification_factory = _campaign_composition_storage["CampaignVerificationFactory"]
if (
    type(_composition_os) is not ModuleType
    or type(vars(_composition_os).get("path")) is not ModuleType
    or type(_composition_datetime) is not type
    or type(_composition_threading) is not ModuleType
    or type(_verification_factory) is not type
):
    raise TypeError
_composition_path = vars(_composition_os)["path"]
_NESTED_BINDINGS = tuple(
    (owner, name, vars(owner)[name])
    for owner, name in (
        (_composition_os, "makedirs"),
        (_composition_os, "path"),
        (_composition_path, "join"),
        (_composition_datetime, "now"),
        (_composition_threading, "Lock"),
        (_verification_factory, "build"),
    )
)
del _composition_datetime, _composition_os, _composition_path
del _composition_threading, _verification_factory
del _captured_bindings
_MODULE_BINDINGS = tuple(zip(_MODULE_NAMES, _SOURCE_MODULES, strict=True))
_SELF_MODULE = sys.modules[__name__]
if type(_SELF_MODULE) is not ModuleType:
    raise TypeError
_SELF_NAME = "scion.core.initial_screening_research_context_edges"
_ENTRY_NAMES = (
    "_compose_initial_screening_research_context_campaign",
    "_validated_research_context_materializer_edge",
)
_ENTRY_HOLDER: list[Any] = [None]
_BUILTIN_NAMES = tuple(
    (  # noqa: SIM905 - immutable finite builtin-name surface
        "BaseException TypeError ValueError any callable dict len list set str "
        "frozenset tuple type vars zip"
    ).split()
)
_SOURCE_BUILTIN_NAMES = tuple(
    (  # noqa: SIM905 - immutable finite builtin-name surface
        "BaseException Exception FileNotFoundError OverflowError RuntimeError "
        "TypeError UnicodeEncodeError ValueError all any bool bytes callable dict "
        "enumerate float frozenset getattr hasattr id int isinstance issubclass "
        "iter len list map max min next object ord property range repr reversed "
        "set setattr sorted str sum super "
        "tuple type vars zip"
    ).split()
)
_SELF_BINDING_NAMES = (
    "sys",
    "weakref",
    "cast",
    "ModuleType",
    "MappingProxyType",
    "core_module",
    "campaign_module",
    "campaign_composition_module",
    "controls_composition_module",
    "declaration_composition_module",
    "problem_spec_module",
    "problem_validation_module",
    "research_context_module",
    "controls_module",
    "provider_policy_module",
    "context_manager_module",
    "_MODULE_BINDINGS",
    "_SOURCE_BINDINGS",
    "_SOURCE_NAMESETS",
    "_SOURCE_BUILTIN_NAMES",
    "_NESTED_BINDINGS",
    "_DECLARATION_VALIDATOR_BINDING",
    "_CONTROLS_COMPOSITION_VALIDATOR",
    "_read_edge_entry_authority",
    "_install_research_context_integration_authorities",
    "_read_research_context_integration_authority",
    "_install_validation_authority",
    "_read_validation_authority",
    "_read_self_binding_authority",
    "_fixed_error",
    "_validated_module_storages",
    "_validate_named_bindings",
    "_validate_source_storages",
    "_validate_nested_bindings",
    "_validate_late_validation_authority",
    "_validate_caller_authorities",
    "_validate_self_edges",
    "_validate_edge_dependencies",
    "_validate_registered_owner",
    "_compose_initial_screening_research_context_campaign",
    "_one_alias",
    "_resolve_materializer_authority",
    "_resolve_validation_materializer",
    "_validated_research_context_materializer_edge",
)


def _make_edge_entry_authority_store() -> tuple[Any, Any]:
    authority: Any = None
    type_fn, tuple_type, error_type = type, tuple, TypeError

    def install(value: Any) -> None:
        nonlocal authority
        if authority is not None or type_fn(value) is not tuple_type:
            raise error_type
        authority = value

    def read() -> Any:
        if type_fn(authority) is not tuple_type:
            raise error_type
        return authority

    return install, read


_install_edge_entry_authority, _read_edge_entry_authority = (
    _make_edge_entry_authority_store()
)
del _make_edge_entry_authority_store
_EDGE_AUTHORITY_READER_BINDING = (
    "_read_edge_entry_authority",
    _read_edge_entry_authority,
)


def _make_integration_authority_store() -> tuple[Any, Any]:
    authority: Any = None
    type_fn, tuple_type, len_fn, module_type = type, tuple, len, ModuleType
    dict_type, str_type, vars_fn, any_fn = dict, str, vars, any
    declaration_installer = _DECLARATION_INTEGRATION_AUTHORITY_INSTALLER
    controls_installer = _CONTROLS_INTEGRATION_AUTHORITY_INSTALLER

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
        storage = vars_fn(module)
        if type_fn(storage) is not dict_type or any_fn(
            type_fn(key) is not str_type for key in storage
        ):
            raise TypeError
        bindings = tuple_type(
            (name, value)
            for name, value in storage.items()
            if name != "__warningregistry__"
        )
        names = frozenset(name for name, _value in bindings)
        declaration_installer(module, validator, entries)
        controls_installer(module, validator, entries)
        authority = (module, validator, entries, bindings, names)

    def read() -> Any:
        return authority

    return install, read


(
    _install_research_context_integration_authorities,
    _read_research_context_integration_authority,
) = _make_integration_authority_store()
del _make_integration_authority_store


def _make_self_binding_store() -> tuple[Any, Any]:
    bindings: Any = None
    type_fn, tuple_type, error_type = type, tuple, TypeError

    def install(value: Any) -> None:
        nonlocal bindings
        if bindings is not None or type_fn(value) is not tuple_type:
            raise error_type
        bindings = value

    def read() -> Any:
        if type_fn(bindings) is not tuple_type:
            raise error_type
        return bindings

    return install, read


_install_self_binding_authority, _read_self_binding_authority = (
    _make_self_binding_store()
)
del _make_self_binding_store


def _validated_integration_authority(
    authority_reader: Any = _read_research_context_integration_authority,
    modules: dict[str, Any] = sys.modules,
    operations: Any = (type, vars, any, len, tuple, ModuleType, dict, str, TypeError),
    frozenset_type: Any = frozenset,
) -> tuple[Any, Any]:
    type_fn, vars_fn, any_fn, len_fn, tuple_type, *exact_types = operations
    module_type, dict_type, str_type, error_type = exact_types
    name = "scion.core.initial_screening_research_context_integration"
    authority = authority_reader()
    if (
        type_fn(modules) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in modules)
        or type_fn(authority) is not tuple_type
        or len_fn(authority) != 5
    ):
        raise error_type
    module, validator, entries, bindings, names = authority
    if type_fn(module) is not module_type or modules.get(name) is not module:
        raise error_type
    storage = vars_fn(module)
    current_name = storage.get("__name__") if type_fn(storage) is dict_type else None
    if (
        type_fn(storage) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in storage)
        or type_fn(current_name) is not str_type
        or current_name != name
        or type_fn(validator) is not tuple_type
        or len_fn(validator) != 2
        or type_fn(validator[0]) is not str_type
        or validator[0] != "_validate_integration_dependencies"
        or type_fn(bindings) is not tuple_type
        or type_fn(names) is not frozenset_type
        or any_fn(type_fn(item) is not str_type for item in names)
        or frozenset_type(key for key in storage if key != "__warningregistry__")
        != names
        or any_fn(
            type_fn(binding) is not tuple_type
            or len_fn(binding) != 2
            or type_fn(binding[0]) is not str_type
            or storage.get(binding[0]) is not binding[1]
            for binding in bindings
        )
        or storage.get("_INTEGRATION_VALIDATOR_BINDING") is not validator
        or storage.get("_INTEGRATION_ENTRY_BINDINGS") is not entries
        or storage.get(validator[0]) is not validator[1]
    ):
        raise error_type
    validator[1]()
    return module, storage


def _make_validation_authority_store() -> tuple[Any, Any]:
    authority: Any = None
    type_fn, module_type, dict_type, str_type = type, ModuleType, dict, str
    tuple_type, vars_fn, any_fn = tuple, vars, any
    integration_validator = _validated_integration_authority
    error_type = TypeError

    def install(module: Any) -> None:
        nonlocal authority
        if authority is not None or type_fn(module) is not module_type:
            raise error_type
        integration_validator()
        storage = vars_fn(module)
        if type_fn(storage) is not dict_type or any_fn(
            type_fn(key) is not str_type for key in storage
        ):
            raise error_type
        bindings = tuple_type(
            (name, value)
            for name, value in storage.items()
            if name != "__warningregistry__"
        )
        names = frozenset(name for name, _value in bindings)
        authority = (module, bindings, names)

    def read() -> Any:
        return authority

    return install, read


_install_validation_authority, _read_validation_authority = (
    _make_validation_authority_store()
)
del _make_validation_authority_store


def _fixed_error(
    error_class: Any = _RESEARCH_CONTEXT_ERROR,
    error_token: str = _ERROR,
) -> BaseException:
    return error_class(error_token)


def _validated_module_storages(
    module_bindings: Any = _MODULE_BINDINGS,
    sys_module: ModuleType = sys,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    module_type: Any = ModuleType,
    dict_type: Any = dict,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> dict[ModuleType, dict[str, Any]]:
    if type_fn(sys_module) is not module_type:
        raise error_type
    modules = vars_fn(sys_module).get("modules")
    if type_fn(modules) is not dict_type or any_fn(
        type_fn(key) is not str_type for key in modules
    ):
        raise error_type
    result: dict[ModuleType, dict[str, Any]] = {}
    for name, module in module_bindings:
        if (
            type_fn(name) is not str_type
            or type_fn(module) is not module_type
            or modules.get(name) is not module
        ):
            raise error_type
        storage = vars_fn(module)
        if (
            type_fn(storage) is not dict_type
            or any_fn(type_fn(key) is not str_type for key in storage)
            or type_fn(storage.get("__name__")) is not str_type
            or storage.get("__name__") != name
        ):
            raise error_type
        result[module] = storage
    return result


def _validate_named_bindings(
    storage: dict[str, Any],
    bindings: Any,
    expected_names: tuple[str, ...],
    type_fn: Any = type,
    len_fn: Any = len,
    zip_fn: Any = zip,
) -> None:
    if type_fn(bindings) is not tuple or len_fn(bindings) != len_fn(expected_names):
        raise TypeError
    for expected_name, binding in zip_fn(expected_names, bindings, strict=True):
        if (
            type_fn(expected_name) is not str
            or type_fn(binding) is not tuple
            or len_fn(binding) != 2
            or binding[0] != expected_name
            or storage.get(expected_name) is not binding[1]
        ):
            raise TypeError


def _validate_source_storages(
    storages: dict[ModuleType, dict[str, Any]],
    namesets: Any = _SOURCE_NAMESETS,
    builtin_names: Any = _SOURCE_BUILTIN_NAMES,
    type_fn: Any = type,
    len_fn: Any = len,
    any_fn: Any = any,
    set_fn: Any = set,
    frozenset_fn: Any = frozenset,
) -> None:
    if (
        type_fn(builtin_names) is not tuple
        or not builtin_names
        or any_fn(type_fn(name) is not str for name in builtin_names)
        or len_fn(set_fn(builtin_names)) != len_fn(builtin_names)
        or type_fn(namesets) is not tuple
        or any_fn(
            type_fn(item) is not tuple
            or len_fn(item) != 2
            or type_fn(item[0]) is not ModuleType
            or type_fn(item[1]) is not frozenset
            or any_fn(type_fn(name) is not str for name in item[1])
            for item in namesets
        )
    ):
        raise TypeError
    for storage in storages.values():
        if any_fn(name in storage for name in builtin_names):
            raise TypeError
    for module, names in namesets:
        if (
            frozenset_fn(
                name for name in storages[module] if name != "__warningregistry__"
            )
            != names
        ):
            raise TypeError


def _validate_nested_bindings(
    bindings: Any = _NESTED_BINDINGS,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
) -> None:
    if type_fn(bindings) is not tuple:
        raise TypeError
    for binding in bindings:
        if type_fn(binding) is not tuple or len_fn(binding) != 3:
            raise TypeError
        owner, name, expected = binding
        if type_fn(name) is not str or type_fn(owner) not in (ModuleType, type):
            raise TypeError
        storage = vars_fn(owner)
        if (
            type_fn(storage) not in (dict, MappingProxyType)
            or any_fn(type_fn(key) is not str for key in storage)
            or storage.get(name) is not expected
        ):
            raise TypeError


def _validate_late_validation_authority(
    require_present: bool,
    authority_reader: Any = _read_validation_authority,
    validation_name: str = ("scion.core.initial_screening_research_context_validation"),
    builtin_names: Any = _SOURCE_BUILTIN_NAMES,
    core: ModuleType = core_module,
    sys_module: ModuleType = sys,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
) -> None:
    authority = authority_reader()
    modules = vars_fn(sys_module).get("modules")
    core_storage = vars_fn(core)
    if authority is None:
        if (
            require_present is not False
            or type_fn(modules) is not dict
            or any_fn(type_fn(key) is not str for key in modules)
            or type_fn(core_storage) is not dict
            or any_fn(type_fn(key) is not str for key in core_storage)
            or validation_name in modules
            or "initial_screening_research_context_validation" in core_storage
        ):
            raise TypeError
        return
    if type_fn(authority) is not tuple or len_fn(authority) != 3:
        raise TypeError
    module, bindings, names = authority
    storage: Any = vars_fn(module) if type_fn(module) is ModuleType else None
    if type_fn(storage) is not dict:
        raise TypeError
    current_name = storage.get("__name__")
    if (
        type_fn(modules) is not dict
        or any_fn(type_fn(key) is not str for key in modules)
        or any_fn(type_fn(key) is not str for key in storage)
        or type_fn(core_storage) is not dict
        or any_fn(type_fn(key) is not str for key in core_storage)
        or type_fn(validation_name) is not str
        or type_fn(current_name) is not type_fn(validation_name)
        or current_name != validation_name
        or modules.get(validation_name) is not module
        or core_storage.get("initial_screening_research_context_validation")
        is not module
        or type_fn(bindings) is not tuple
        or type_fn(names) is not frozenset
        or any_fn(type_fn(name) is not str for name in names)
        or frozenset(name for name in storage if name != "__warningregistry__") != names
        or any_fn(
            type_fn(binding) is not tuple
            or len_fn(binding) != 2
            or type_fn(binding[0]) is not str
            or storage.get(binding[0]) is not binding[1]
            for binding in bindings
        )
        or any_fn(name in storage for name in builtin_names)
    ):
        raise TypeError


def _validate_caller_authorities(
    storages: dict[ModuleType, dict[str, Any]],
    named_bindings_validator: Any = _validate_named_bindings,
    campaign_bindings: Any = _CAMPAIGN_COMPOSITION_BINDINGS,
    controls_bindings: Any = _CONTROLS_COMPOSITION_BINDINGS,
    declaration_bindings: Any = _DECLARATION_BINDINGS,
    declaration_validator: Any = _DECLARATION_VALIDATOR_BINDING,
) -> None:
    campaign_composition_storage = storages[campaign_composition_module]
    controls_storage = storages[controls_composition_module]
    declaration_storage = storages[declaration_composition_module]
    named_bindings_validator(
        campaign_composition_storage,
        campaign_bindings,
        (
            "compose_campaign_services",
            "_prepare_initial_screening_controls_setup",
        ),
    )
    named_bindings_validator(
        controls_storage,
        controls_bindings,
        (
            "_install_research_context_integration_authority",
            "_validated_research_context_runtime_installer",
            "_resolve_active_research_context_installer",
            "_install_active_research_context_capsule",
            "_prepare_initial_screening_controls_setup_impl",
        ),
    )
    named_bindings_validator(
        declaration_storage,
        declaration_bindings,
        (
            "_install_research_context_integration_authority",
            "_validated_research_context_integration_entry",
            "_prepare_initial_screening_declarations",
            "_publish_initial_screening_declarations",
            "_install_initial_screening_declaration_carriers",
            "_install_initial_screening_research_context_owner",
            "_finalize_initial_screening_declarations",
        ),
    )
    if (
        type(declaration_validator) is not tuple
        or len(declaration_validator) != 2
        or declaration_validator[0] != "_validate_research_context_declaration_edges"
        or declaration_storage.get(declaration_validator[0])
        is not declaration_validator[1]
    ):
        raise TypeError


def _validate_self_edges(
    expected_holder: list[Any] = _ENTRY_HOLDER,
    authority_reader: Any = _read_edge_entry_authority,
    expected_reader: Any = _read_edge_entry_authority,
    reader_binding: tuple[str, Any] = _EDGE_AUTHORITY_READER_BINDING,
    integration_installer: Any = _install_research_context_integration_authorities,
    self_binding_reader: Any = _read_self_binding_authority,
    expected_self_binding_reader: Any = _read_self_binding_authority,
    self_binding_names: tuple[str, ...] = _SELF_BINDING_NAMES,
    builtin_names: tuple[str, ...] = _BUILTIN_NAMES,
    named_bindings_validator: Any = _validate_named_bindings,
    entry_names: tuple[str, ...] = _ENTRY_NAMES,
    self_module: ModuleType = _SELF_MODULE,
    self_name: str = _SELF_NAME,
    sys_module: ModuleType = sys,
    type_fn: Any = type,
    vars_fn: Any = vars,
    any_fn: Any = any,
    len_fn: Any = len,
    cast_fn: Any = cast,
    module_type: Any = ModuleType,
    dict_type: Any = dict,
    str_type: Any = str,
    tuple_type: Any = tuple,
    list_type: Any = list,
    error_type: Any = TypeError,
) -> None:
    entries = authority_reader()
    self_bindings = self_binding_reader()
    if (
        type_fn(self_module) is not module_type
        or type_fn(sys_module) is not module_type
    ):
        raise error_type
    storage = vars_fn(self_module)
    modules = vars_fn(sys_module).get("modules")
    current_name = storage.get("__name__") if type_fn(storage) is dict_type else None
    if (
        type_fn(storage) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in storage)
        or type_fn(modules) is not dict_type
        or any_fn(type_fn(key) is not str_type for key in modules)
        or type_fn(current_name) is not type_fn(self_name)
        or current_name != self_name
        or modules.get(self_name) is not self_module
        or storage.get("_SELF_BINDING_NAMES") is not self_binding_names
        or storage.get("_BUILTIN_NAMES") is not builtin_names
        or any_fn(name in storage for name in builtin_names)
        or storage.get("_ENTRY_NAMES") is not entry_names
        or storage.get("_ENTRY_HOLDER") is not expected_holder
        or storage.get("_read_edge_entry_authority") is not expected_reader
        or storage.get("_read_self_binding_authority")
        is not expected_self_binding_reader
        or storage.get("_install_research_context_integration_authorities")
        is not integration_installer
        or type_fn(expected_holder) is not list_type
        or len_fn(expected_holder) != 1
        or expected_holder[0] is not entries
    ):
        raise error_type
    if (
        type_fn(entries) is not tuple_type
        or len_fn(entries) != len_fn(entry_names)
        or type_fn(self_bindings) is not tuple_type
        or len_fn(self_bindings) != len_fn(self_binding_names)
        or storage.get("_SELF_BINDINGS") is not self_bindings
        or storage.get("_EDGE_ENTRY_BINDINGS") is not entries
    ):
        raise error_type
    exact_entries = cast_fn(tuple[Any, ...], entries)
    if (
        storage.get("_CAMPAIGN_CONSTRUCTION_EDGE_BINDING") is not exact_entries[0]
        or storage.get("_MATERIALIZER_RESOLUTION_EDGE_BINDING") is not exact_entries[1]
        or storage.get("_EDGE_AUTHORITY_READER_BINDING") is not reader_binding
        or reader_binding != ("_read_edge_entry_authority", expected_reader)
    ):
        raise TypeError
    named_bindings_validator(storage, self_bindings, self_binding_names)
    named_bindings_validator(storage, exact_entries, entry_names)


def _validate_edge_dependencies(
    require_validation: bool,
    self_validator: Any = _validate_self_edges,
    storage_validator: Any = _validated_module_storages,
    source_storage_validator: Any = _validate_source_storages,
    nested_binding_validator: Any = _validate_nested_bindings,
    validation_authority_validator: Any = _validate_late_validation_authority,
    caller_validator: Any = _validate_caller_authorities,
    source_bindings: Any = _SOURCE_BINDINGS,
    declaration_validator: Any = _DECLARATION_VALIDATOR_BINDING,
    controls_validator: Any = _CONTROLS_COMPOSITION_VALIDATOR,
) -> None:
    storages = storage_validator()
    self_validator()
    source_storage_validator(storages)
    nested_binding_validator()
    validation_authority_validator(require_validation)
    for module, name, expected in source_bindings:
        if storages[module].get(name) is not expected:
            raise TypeError
    caller_validator(storages)
    declaration_validator[1]()
    controls_validator()


def _validate_registered_owner(owner: Any) -> None:
    validation_name = "scion.core.initial_screening_research_context_validation"
    validation_module = sys.modules.get(validation_name)
    if type(validation_module) is not ModuleType:
        raise TypeError
    validation_storage = vars(validation_module)
    owner_storage = vars(owner)
    if (
        type(validation_storage) is not dict
        or any(type(key) is not str for key in validation_storage)
        or type(validation_storage.get("__name__")) is not str
        or validation_storage.get("__name__") != validation_name
        or type(owner_storage) is not dict
        or any(type(key) is not str for key in owner_storage)
    ):
        raise TypeError
    registry = validation_storage.get("_REGISTERED_OWNERS")
    baseline_type = validation_storage.get("_RegisteredResearchContextBaseline")
    if (
        type(registry) is not weakref.WeakKeyDictionary
        or type(baseline_type) is not type
    ):
        raise TypeError
    baseline = weakref.WeakKeyDictionary.get(registry, owner)
    inputs = owner_storage.get("_initial_screening_research_context")
    if type(baseline) is not baseline_type or inputs is None:
        raise TypeError
    baseline_storage = vars(baseline)
    inputs_ref = baseline_storage.get("inputs_ref")
    if (
        owner_storage.get("_initial_screening_research_context_active") is not True
        or type(baseline_storage) is not dict
        or any(type(key) is not str for key in baseline_storage)
        or type(inputs_ref) is not weakref.ReferenceType
        or inputs_ref() is not inputs
    ):
        raise ValueError


def _compose_initial_screening_research_context_campaign(
    owner: Any,
    composition_arguments: dict[str, Any],
    dependency_validator: Any = _validate_edge_dependencies,
    owner_validator: Any = _validate_registered_owner,
    compose_authority: Any = _COMPOSE_CAMPAIGN_SERVICES,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> None:
    failed = False
    try:
        dependency_validator(False)
        if (
            type(composition_arguments) is not dict
            or any(type(key) is not str for key in composition_arguments)
            or composition_arguments.get("_initial_screening_research_context") is None
        ):
            raise TypeError
        compose_authority(owner, **composition_arguments)
        dependency_validator(True)
        owner_validator(owner)
    except base_exception:
        failed = True
    if failed:
        raise fixed_error() from None


def _one_alias(aliases: Any, name: str) -> Any:
    if type(aliases) is not tuple or type(name) is not str:
        raise TypeError
    matches = tuple(
        item
        for item in aliases
        if (
            type(item) is tuple
            and len(item) == 2
            and type(item[0]) is str
            and item[0] == name
        )
    )
    if len(matches) != 1:
        raise TypeError
    return matches[0][1]


def _resolve_materializer_authority(
    integration_validator: Any = _validated_integration_authority,
) -> Any:
    validation_name = "scion.core.initial_screening_research_context_validation"
    integration_module, integration_storage = integration_validator()
    validation_module = sys.modules.get(validation_name)
    if type(validation_module) is not ModuleType:
        raise TypeError
    validation_storage = vars(validation_module)
    if type(validation_storage) is not dict or any(
        type(key) is not str for key in validation_storage
    ):
        raise TypeError
    validation_current_name = validation_storage.get("__name__")
    if (
        type(validation_current_name) is not type(validation_name)
        or validation_current_name != validation_name
    ):
        raise TypeError
    return _resolve_validation_materializer(
        integration_module,
        integration_storage,
        validation_storage,
    )


def _resolve_validation_materializer(
    integration_module: ModuleType,
    integration_storage: dict[str, Any],
    validation_storage: dict[str, Any],
) -> Any:
    validation_aliases = validation_storage.get("_VALIDATION_ALIASES")
    validation_guard = _one_alias(
        validation_aliases,
        "_validate_local_helper_anchors",
    )
    validation_error = _one_alias(validation_aliases, "_RESEARCH_CONTEXT_ERROR")
    materializer = _one_alias(validation_aliases, "_MATERIALIZE_H_FIELDS")
    validator = validation_storage.get("_validate_validation_dependencies")
    if (
        validation_error is not _RESEARCH_CONTEXT_ERROR
        or validation_storage.get("_RESEARCH_CONTEXT_ERROR")
        is not _RESEARCH_CONTEXT_ERROR
        or validation_storage.get("_validate_local_helper_anchors")
        is not validation_guard
        or validation_storage.get("integration_module") is not integration_module
    ):
        raise TypeError
    if not callable(validation_guard):
        raise TypeError
    validation_guard(validation_storage)
    if not callable(validator):
        raise TypeError
    validator()
    entry_bindings = integration_storage.get("_INTEGRATION_ENTRY_BINDINGS")
    expected = _one_alias(
        entry_bindings,
        "_materialize_research_context_h_fields",
    )
    if (
        materializer is not expected
        or integration_storage.get("_materialize_research_context_h_fields")
        is not expected
    ):
        raise TypeError
    return expected


def _validated_research_context_materializer_edge(
    dependency_validator: Any = _validate_edge_dependencies,
    authority_resolver: Any = _resolve_materializer_authority,
    fixed_error: Any = _fixed_error,
    base_exception: Any = BaseException,
) -> Any:
    failed = False
    result: Any = None
    try:
        dependency_validator(True)
        result = authority_resolver()
    except base_exception:
        failed = True
    if failed or result is None:
        raise fixed_error() from None
    return result


_SELF_BINDINGS = tuple((name, vars(_SELF_MODULE)[name]) for name in _SELF_BINDING_NAMES)
_install_self_binding_authority(_SELF_BINDINGS)
del _install_self_binding_authority
_EDGE_ENTRY_BINDINGS = tuple((name, vars(_SELF_MODULE)[name]) for name in _ENTRY_NAMES)
_ENTRY_HOLDER[0] = _EDGE_ENTRY_BINDINGS
_install_edge_entry_authority(_EDGE_ENTRY_BINDINGS)
del _install_edge_entry_authority
_CAMPAIGN_EDGE_AUTHORITY_INSTALLER(
    _read_edge_entry_authority,
    _EDGE_ENTRY_BINDINGS,
)
_CONTEXT_EDGE_AUTHORITY_INSTALLER(
    _read_edge_entry_authority,
    _EDGE_ENTRY_BINDINGS,
)
_CAMPAIGN_CONSTRUCTION_EDGE_BINDING = _EDGE_ENTRY_BINDINGS[0]
_MATERIALIZER_RESOLUTION_EDGE_BINDING = _EDGE_ENTRY_BINDINGS[1]

__all__ = []
