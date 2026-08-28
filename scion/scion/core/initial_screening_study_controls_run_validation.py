"""Thin ordering router for initial-screening run-start validation."""

from __future__ import annotations

import sys
import weakref
from collections.abc import Callable
from types import FunctionType, ModuleType
from typing import Any, cast

from scion.core.initial_screening_study_controls import (
    _ERROR,
    _FILENAME,
    _MAX_BYTES,
    _InitialScreeningRuntimeInputs,
    _InitialScreeningStudyControlsError,
)
from scion.core.initial_screening_study_provider_policy import (
    _ERROR as _PROVIDER_ERROR,
)
from scion.core.initial_screening_study_provider_policy import (
    _REGISTERED_OWNERS as _PROVIDER_REGISTERED_OWNERS,
)
from scion.core.initial_screening_study_provider_policy import (
    _InitialScreeningProviderPolicyError,
)

_RESEARCH_MARKER_KEYS = frozenset(
    {
        "_initial_screening_research_context_active",
        "_initial_screening_research_context",
    }
)
_PROBLEM_MARKER_KEYS = frozenset(
    {
        "_initial_screening_problem_spec_active",
        "_initial_screening_problem_spec",
    }
)
_CONTROLS_MARKER_KEYS = frozenset(
    {
        "_initial_screening_study_controls_active",
        "_initial_screening_study_controls",
    }
)
_RESEARCH_VALIDATION_MODULE_NAME = (
    "scion.core.initial_screening_research_context_validation"
)
_RESEARCH_BOUNDARY_MODULE_NAME = "scion.core.initial_screening_research_context"
_PROBLEM_VALIDATION_MODULE_NAME = "scion.core.initial_screening_problem_spec_validation"
_PROBLEM_BOUNDARY_MODULE_NAME = "scion.core.initial_screening_problem_spec"
_RESEARCH_ERROR_TYPE_NAME = "_InitialScreeningResearchContextError"
_PROBLEM_ERROR_TYPE_NAME = "_InitialScreeningProblemSpecError"
_ENTRY_NAMES = (
    "_prepare_research_context_run_validation",
    "_validate_research_context_publication",
    "_validate_research_context_installed_runtime",
)
_PROBLEM_ENTRY_NAMES = (
    "_prepare_problem_spec_run_validation",
    "_validate_problem_spec_publication",
    "_validate_problem_spec_installed_runtime",
)
_CONTROLS_DISPATCH_NAMES = (
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
_PROVIDER_DISPATCH_NAMES = (
    "_prepare_provider_policy_run_validation",
    "_validate_provider_policy_publication",
    "_validate_provider_policy_installed_runtime",
)
_RESEARCH_CONTEXT_AUTHORITIES: weakref.WeakKeyDictionary[Any, tuple[Any, ...]] = (
    weakref.WeakKeyDictionary()
)
_PROBLEM_AUTHORITIES: weakref.WeakKeyDictionary[Any, tuple[Any, ...]] = (
    weakref.WeakKeyDictionary()
)
_ROUTER_BUILTIN_NAMES = tuple(
    str.split(
        "BaseException TypeError ValueError all any dict getattr int len list "
        "str tuple type vars zip",
        " ",
    )
)


def _make_hidden_authority_store(
    weak_dictionary_type: Any = weakref.WeakKeyDictionary,
    reference_type: Any = weakref.ReferenceType,
    keyrefs: Any = weakref.WeakKeyDictionary.keyrefs,
    items: Any = weakref.WeakKeyDictionary.items,
    setitem: Any = weakref.WeakKeyDictionary.__setitem__,
    type_anchor: Any = type,
    any_anchor: Any = any,
    list_anchor: Any = list,
    error_type: Any = TypeError,
) -> tuple[Callable[[Any, Any], Any], Callable[[Any], Any]]:
    registry = weak_dictionary_type()

    def read(owner: Any) -> Any | None:
        references = keyrefs(registry)
        if type_anchor(references) is not list_anchor or any_anchor(
            type_anchor(reference) is not reference_type for reference in references
        ):
            raise error_type
        if not any_anchor(reference() is owner for reference in references):
            return None
        for key, authority in items(registry):
            if key is owner:
                return authority
        raise error_type

    def write(owner: Any, authority: Any) -> Any:
        current = read(owner)
        if current is None:
            setitem(registry, owner, authority)
            current = read(owner)
        return current

    return write, read


_write_hidden_research_authority, _read_hidden_research_authority = (
    _make_hidden_authority_store()
)
_write_hidden_problem_authority, _read_hidden_problem_authority = (
    _make_hidden_authority_store()
)
del _make_hidden_authority_store


def _make_hidden_owner_checker(
    registry: Any,
    keyrefs: Any = weakref.WeakKeyDictionary.keyrefs,
    reference_type: Any = weakref.ReferenceType,
    type_anchor: Any = type,
    any_anchor: Any = any,
    list_anchor: Any = list,
    error_type: Any = TypeError,
) -> Callable[[Any], bool]:
    def contains(owner: Any) -> bool:
        references = keyrefs(registry)
        if type_anchor(references) is not list_anchor or any_anchor(
            type_anchor(reference) is not reference_type for reference in references
        ):
            raise error_type
        return any_anchor(reference() is owner for reference in references)

    return contains


_provider_owner_is_registered = _make_hidden_owner_checker(_PROVIDER_REGISTERED_OWNERS)
del _make_hidden_owner_checker

if (
    type(sys.modules) is not dict
    or any(type(name) is not str for name in sys.modules)
    or type(__name__) is not str
):
    raise TypeError
_SELF_MODULE = sys.modules.get(__name__)
if type(_SELF_MODULE) is not ModuleType:
    raise TypeError
_SELF_MODULE_STORAGE = vars(_SELF_MODULE)
if (
    type(_SELF_MODULE_STORAGE) is not dict
    or any(type(name) is not str for name in _SELF_MODULE_STORAGE)
    or type(_SELF_MODULE_STORAGE.get("__name__")) is not str
):
    raise TypeError
_SELF_MODULE = cast(ModuleType, _SELF_MODULE)
_SELF_MODULE_NAME = cast(str, _SELF_MODULE_STORAGE["__name__"])


def _validate_router_guard_items(
    items: Any,
    tuple_type: Any,
    str_type: Any,
    type_anchor: Any,
    error_type: Any,
) -> None:
    if type_anchor(items) is not tuple_type:
        raise error_type
    for item in items:
        if (
            type_anchor(item) is not tuple_type
            or item.__len__() != 2
            or type_anchor(item[0]) is not str_type
        ):
            raise error_type


def _validate_router_guard_state(
    self_module: Any,
    self_name: Any,
    sys_module: Any,
    sys_modules: Any,
    builtin_names: Any,
    helpers: Any,
    aliases: Any,
    public_validator: Any,
    module_type: Any,
    dict_type: Any,
    tuple_type: Any,
    str_type: Any,
    type_anchor: Any,
    any_anchor: Any,
    vars_anchor: Any,
    error_type: Any,
) -> None:
    if (
        type_anchor(self_module) is not module_type
        or type_anchor(sys_module) is not module_type
        or type_anchor(self_name) is not str_type
        or type_anchor(sys_modules) is not dict_type
        or type_anchor(builtin_names) is not tuple_type
    ):
        raise error_type
    self_storage = vars_anchor(self_module)
    sys_storage = vars_anchor(sys_module)
    if (
        type_anchor(self_storage) is not dict_type
        or type_anchor(sys_storage) is not dict_type
    ):
        raise error_type
    for storage in (self_storage, sys_storage, sys_modules):
        if any_anchor(type_anchor(name) is not str_type for name in storage):
            raise error_type
    if (
        type_anchor(self_storage.get("__name__")) is not str_type
        or self_storage["__name__"] != self_name
        or sys_storage.get("modules") is not sys_modules
        or sys_modules.get(self_name) is not self_module
        or self_storage.get("_ROUTER_BUILTIN_NAMES") is not builtin_names
        or self_storage.get("_validate_run_router_dependencies") is not public_validator
        or self_storage.get("_ROUTER_HELPER_ITEMS") is not helpers
        or self_storage.get("_ROUTER_ALIAS_ITEMS") is not aliases
    ):
        raise error_type
    for name in builtin_names:
        if type_anchor(name) is not str_type or name in self_storage:
            raise error_type
    for items in (helpers, aliases):
        if type_anchor(items) is not tuple_type or any_anchor(
            type_anchor(item) is not tuple_type
            or item.__len__() != 2
            or type_anchor(item[0]) is not str_type
            or self_storage.get(item[0]) is not item[1]
            for item in items
        ):
            raise error_type


def _make_run_router_dependency_guard(
    self_module: Any = _SELF_MODULE,
    self_name: Any = _SELF_MODULE_NAME,
    sys_module: Any = sys,
    sys_modules: Any = sys.modules,
    builtin_names: Any = _ROUTER_BUILTIN_NAMES,
    module_type: Any = ModuleType,
    dict_type: Any = dict,
    tuple_type: Any = tuple,
    str_type: Any = str,
    type_anchor: Any = type,
    any_anchor: Any = any,
    vars_anchor: Any = vars,
    error_type: Any = TypeError,
    item_validator: Any = _validate_router_guard_items,
    state_validator: Any = _validate_router_guard_state,
) -> tuple[Callable[[Any, Any], None], Callable[[], None]]:
    helpers: Any = None
    aliases: Any = None

    def install(helper_items: Any, alias_items: Any) -> None:
        nonlocal helpers, aliases
        if helpers is not None or aliases is not None:
            raise error_type
        for items in (helper_items, alias_items):
            item_validator(items, tuple_type, str_type, type_anchor, error_type)
        helpers, aliases = helper_items, alias_items

    def validate() -> None:
        state_validator(
            self_module,
            self_name,
            sys_module,
            sys_modules,
            builtin_names,
            helpers,
            aliases,
            validate,
            module_type,
            dict_type,
            tuple_type,
            str_type,
            type_anchor,
            any_anchor,
            vars_anchor,
            error_type,
        )

    return install, validate


_install_run_router_dependencies, _validate_run_router_dependencies = (
    _make_run_router_dependency_guard()
)
del (
    _make_run_router_dependency_guard,
    _validate_router_guard_items,
    _validate_router_guard_state,
)


class _ProblemBoundaryFailure(RuntimeError):
    pass


class _ResearchContextBoundaryFailure(RuntimeError):
    pass


def _module_storage(module: Any, expected_name: str) -> dict[str, Any]:
    if type(expected_name) is not str or type(module) is not ModuleType:
        raise TypeError
    storage = vars(module)
    modules = sys.modules
    if (
        type(storage) is not dict
        or any(type(name) is not str for name in storage)
        or type(storage.get("__name__")) is not str
        or storage["__name__"] != expected_name
        or type(modules) is not dict
        or any(type(name) is not str for name in modules)
        or modules.get(expected_name) is not module
    ):
        raise TypeError
    return cast(dict[str, Any], storage)


def _register_boundary_authority(
    registry: Any,
    owner: Any,
    validation_module: Any,
    validation_name: str,
    boundary_module: Any,
    boundary_name: str,
    entry_names: tuple[str, str, str],
    entries: tuple[Any, Any, Any],
    error_type_name: str,
    error_type: Any,
    error_token: Any,
) -> tuple[Any, ...]:
    if (
        type(registry) is not weakref.WeakKeyDictionary
        or type(entry_names) is not tuple
        or len(entry_names) != 3
        or any(type(name) is not str for name in entry_names)
        or type(entries) is not tuple
        or len(entries) != 3
        or any(type(entry) is not FunctionType for entry in entries)
        or type(error_type_name) is not str
        or type(error_type) is not type
        or type(error_token) is not str
    ):
        raise TypeError
    validation_storage = _module_storage(validation_module, validation_name)
    boundary_storage = _module_storage(boundary_module, boundary_name)
    if (
        any(
            validation_storage.get(name) is not entry
            for name, entry in zip(entry_names, entries)
        )
        or boundary_storage.get(error_type_name) is not error_type
        or boundary_storage.get("_ERROR") is not error_token
    ):
        raise TypeError
    authority = (
        validation_module,
        validation_name,
        boundary_module,
        boundary_name,
        entry_names,
        entries,
        error_type_name,
        error_type,
        error_token,
    )
    current = weakref.WeakKeyDictionary.get(registry, owner)
    if current is None:
        weakref.WeakKeyDictionary.__setitem__(registry, owner, authority)
    elif not _same_authority(current, authority):
        raise ValueError
    return authority


def _same_authority(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _same_authority(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    if type(left) is str:
        return left == right
    return left is right


def _identity_authority(registry: Any, owner: Any) -> Any | None:
    if type(registry) is not weakref.WeakKeyDictionary:
        raise TypeError
    references = weakref.WeakKeyDictionary.keyrefs(registry)
    if type(references) is not list or any(
        type(reference) is not weakref.ReferenceType for reference in references
    ):
        raise TypeError
    if not any(reference() is owner for reference in references):
        return None
    for key, authority in weakref.WeakKeyDictionary.items(registry):
        if key is owner:
            return authority
    raise ValueError


def _validated_run_authority(
    authority: Any,
) -> tuple[Any, Any, Any, type, str]:
    if type(authority) is not tuple or len(authority) != 9:
        raise TypeError
    (
        validation_module,
        validation_name,
        boundary_module,
        boundary_name,
        entry_names,
        entries,
        error_type_name,
        error_type,
        error_token,
    ) = authority
    if (
        type(validation_name) is not str
        or type(boundary_name) is not str
        or type(entry_names) is not tuple
        or len(entry_names) != 3
        or any(type(name) is not str for name in entry_names)
        or type(entries) is not tuple
        or len(entries) != 3
        or any(type(entry) is not FunctionType for entry in entries)
        or type(error_type_name) is not str
        or type(error_type) is not type
        or type(error_token) is not str
    ):
        raise TypeError
    validation_storage = _module_storage(validation_module, validation_name)
    boundary_storage = _module_storage(boundary_module, boundary_name)
    if (
        any(
            validation_storage.get(name) is not entry
            for name, entry in zip(entry_names, entries)
        )
        or boundary_storage.get(error_type_name) is not error_type
        or boundary_storage.get("_ERROR") is not error_token
    ):
        raise TypeError
    return (
        entries[0],
        entries[1],
        entries[2],
        cast(type, error_type),
        cast(str, error_token),
    )


def _register_research_context_run_authority(
    owner: Any,
    validation_module: Any,
    boundary_module: Any,
    prepare: Any,
    publication: Any,
    installed: Any,
    error_type: Any,
    error_token: Any,
    baseline: Any,
    dependency_validator: Callable[[], None] = _validate_run_router_dependencies,
    register: Callable[..., Any] = _register_boundary_authority,
    hidden_write: Callable[[Any, Any], Any] = _write_hidden_research_authority,
    hidden_read: Callable[[Any], Any] = _read_hidden_research_authority,
    public_read: Callable[[Any, Any], Any] = _identity_authority,
    same: Callable[[Any, Any], bool] = _same_authority,
) -> None:
    dependency_validator()
    if baseline is None:
        raise TypeError
    baseline_storage = vars(baseline)
    if type(baseline_storage) is not dict or any(
        type(name) is not str for name in baseline_storage
    ):
        raise TypeError
    baseline_items = tuple(baseline_storage.items())
    authority = register(
        _RESEARCH_CONTEXT_AUTHORITIES,
        owner,
        validation_module,
        _RESEARCH_VALIDATION_MODULE_NAME,
        boundary_module,
        _RESEARCH_BOUNDARY_MODULE_NAME,
        _ENTRY_NAMES,
        (prepare, publication, installed),
        _RESEARCH_ERROR_TYPE_NAME,
        error_type,
        error_token,
    )
    hidden_authority = (authority, baseline, baseline_items)
    hidden_write(owner, hidden_authority)
    hidden = hidden_read(owner)
    public = public_read(_RESEARCH_CONTEXT_AUTHORITIES, owner)
    if not same(hidden, hidden_authority) or not same(public, authority):
        raise TypeError


def _register_problem_run_authority(
    owner: Any,
    validation_module: Any,
    boundary_module: Any,
    prepare: Any,
    publication: Any,
    installed: Any,
    error_type: Any,
    error_token: Any,
    dependency_validator: Callable[[], None] = _validate_run_router_dependencies,
    register: Callable[..., Any] = _register_boundary_authority,
    hidden_write: Callable[[Any, Any], Any] = _write_hidden_problem_authority,
    hidden_read: Callable[[Any], Any] = _read_hidden_problem_authority,
    public_read: Callable[[Any, Any], Any] = _identity_authority,
    same: Callable[[Any, Any], bool] = _same_authority,
) -> None:
    dependency_validator()
    authority = register(
        _PROBLEM_AUTHORITIES,
        owner,
        validation_module,
        _PROBLEM_VALIDATION_MODULE_NAME,
        boundary_module,
        _PROBLEM_BOUNDARY_MODULE_NAME,
        _PROBLEM_ENTRY_NAMES,
        (prepare, publication, installed),
        _PROBLEM_ERROR_TYPE_NAME,
        error_type,
        error_token,
    )
    hidden_write(owner, authority)
    hidden = hidden_read(owner)
    public = public_read(_PROBLEM_AUTHORITIES, owner)
    if not same(hidden, authority) or not same(public, authority):
        raise TypeError


def _validated_dispatch_entries(
    module: Any,
    module_name: Any,
    names: Any,
    entries: Any,
    expected_names: tuple[str, ...],
) -> tuple[Any, ...]:
    if (
        type(module_name) is not str
        or type(names) is not tuple
        or names != expected_names
        or any(type(name) is not str for name in names)
        or type(entries) is not tuple
        or len(entries) != len(names)
        or any(type(entry) is not FunctionType for entry in entries)
    ):
        raise TypeError
    storage = _module_storage(module, module_name)
    if any(storage.get(name) is not entry for name, entry in zip(names, entries)):
        raise TypeError
    return cast(tuple[Any, ...], entries)


def _validate_caller_dispatch(dispatch: Any) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    if type(dispatch) is not tuple or len(dispatch) != 8:
        raise TypeError
    try:
        provider = _validated_dispatch_entries(
            dispatch[4],
            dispatch[5],
            dispatch[6],
            dispatch[7],
            _PROVIDER_DISPATCH_NAMES,
        )
    except BaseException:  # noqa: BLE001 - fixed provider dispatch boundary
        raise _InitialScreeningProviderPolicyError(_PROVIDER_ERROR) from None
    controls = dispatch[3]
    if (
        type(dispatch[2]) is not tuple
        or dispatch[2] != _CONTROLS_DISPATCH_NAMES
        or type(controls) is not tuple
        or len(controls) != len(_CONTROLS_DISPATCH_NAMES)
        or type(controls[0]) is not FunctionType
        or _module_storage(dispatch[0], dispatch[1]).get(dispatch[2][0])
        is not controls[0]
    ):
        raise TypeError
    return controls, provider


def _validate_registered_run(
    requested_rounds: Any,
    owner: Any,
    controls_dispatch: Any,
) -> None:
    controls, provider = _validate_caller_dispatch(controls_dispatch)
    _prepare_provider_policy_run_validation = provider[0]
    provider_state = _prepare_provider_policy_run_validation(owner)
    controls = _validated_dispatch_entries(
        controls_dispatch[0],
        controls_dispatch[1],
        controls_dispatch[2],
        controls_dispatch[3],
        _CONTROLS_DISPATCH_NAMES,
    )
    (
        _campaign_owner_storage,
        _registered_baseline,
        _validate_baseline_shape,
        _validate_carrier_against_baseline,
        _validate_claimed_controls_structural_shape,
        _validate_controls_publication,
        _validate_installed_runtime,
        _validate_private_child_directory,
        _validate_runtime_and_publication_shape,
    ) = controls
    (
        _,
        _validate_provider_policy_publication,
        _validate_provider_policy_installed_runtime,
    ) = provider
    owner_storage = _campaign_owner_storage(owner)
    research = _research_context_run_hooks(owner, owner_storage)
    problem = _problem_run_hooks(owner, owner_storage)
    if not _CONTROLS_MARKER_KEYS.issubset(owner_storage):
        raise TypeError
    active = owner_storage["_initial_screening_study_controls_active"]
    runtime_inputs = owner_storage["_initial_screening_study_controls"]
    baseline = _registered_baseline(owner, active, runtime_inputs)
    if baseline is None:
        if (
            provider_state is not None
            or problem[0] is not None
            or research[0] is not None
        ):
            raise ValueError
        return
    _validate_baseline_shape(baseline)
    if (
        active is not True
        or type(runtime_inputs) is not _InitialScreeningRuntimeInputs
        or runtime_inputs is not baseline.runtime_inputs_ref()
        or type(requested_rounds) is not int
    ):
        raise ValueError
    _validate_runtime_and_publication_shape(runtime_inputs)
    if requested_rounds != baseline.requested_rounds:
        raise ValueError
    publication = _validate_carrier_against_baseline(runtime_inputs, baseline)
    _validate_claimed_controls_structural_shape(runtime_inputs, owner)
    if (
        type(getattr(owner, "_campaign_dir", None)) is not str
        or owner._campaign_dir != baseline.campaign_dir
    ):
        raise ValueError
    _validate_controls_publication(
        publication,
        baseline.payload_bytes,
        filename=_FILENAME,
        max_bytes=_MAX_BYTES,
    )
    if provider_state is not None:
        _validate_provider_policy_publication(provider_state, publication)
    _validate_problem_publication(problem, runtime_inputs, provider_state)
    _validate_research_publication(research, runtime_inputs, provider_state, problem[0])
    _validate_private_child_directory(
        publication,
        "metrics",
        baseline.metrics_directory_fingerprint,
    )
    _validate_installed_runtime(owner, runtime_inputs, baseline)
    if provider_state is not None:
        _validate_provider_policy_installed_runtime(provider_state, owner)
    _validate_problem_installed(problem, owner)
    _validate_research_installed(research, owner)


_RunHooks = tuple[
    Any,
    Callable[..., None] | None,
    Callable[..., None] | None,
    type | None,
    str | None,
]


def _research_context_run_hooks(owner: Any, owner_storage: dict[str, Any]) -> _RunHooks:
    try:
        hidden_authority = _read_hidden_research_authority(owner)
        if not _RESEARCH_MARKER_KEYS.intersection(owner_storage):
            if hidden_authority is not None:
                raise ValueError
            return None, None, None, None, None
        public_authority = _identity_authority(_RESEARCH_CONTEXT_AUTHORITIES, owner)
        if (
            type(hidden_authority) is not tuple
            or len(hidden_authority) != 3
            or public_authority is None
        ):
            raise TypeError
        authority, baseline, baseline_items = hidden_authority
        if not _same_authority(authority, public_authority):
            raise TypeError
        if type(authority) is not tuple or len(authority) != 9:
            raise TypeError
        validation_storage = _module_storage(authority[0], authority[1])
        baseline_registry = validation_storage.get("_REGISTERED_OWNERS")
        baseline_storage = vars(baseline)
        if (
            _identity_authority(baseline_registry, owner) is not baseline
            or type(baseline_storage) is not dict
            or any(type(name) is not str for name in baseline_storage)
            or not _same_authority(tuple(baseline_storage.items()), baseline_items)
        ):
            raise TypeError
        prepare, publication, installed, error_type, error_token = (
            _validated_run_authority(authority)
        )
        state = prepare(owner, owner_storage)
        if state is None:
            raise TypeError
        return state, publication, installed, error_type, error_token
    except BaseException:  # noqa: BLE001 - fixed research-context boundary
        raise _ResearchContextBoundaryFailure from None


def _problem_run_hooks(owner: Any, owner_storage: dict[str, Any]) -> _RunHooks:
    try:
        hidden_authority = _read_hidden_problem_authority(owner)
        if not _PROBLEM_MARKER_KEYS.intersection(owner_storage):
            if hidden_authority is not None:
                raise ValueError
            return None, None, None, None, None
        public_authority = _identity_authority(_PROBLEM_AUTHORITIES, owner)
        if (
            hidden_authority is None
            or public_authority is None
            or not _same_authority(hidden_authority, public_authority)
        ):
            raise TypeError
        prepare, publication, installed, error_type, error_token = (
            _validated_run_authority(hidden_authority)
        )
        state = prepare(owner, owner_storage)
        if state is None:
            raise TypeError
        return state, publication, installed, error_type, error_token
    except BaseException:  # noqa: BLE001 - fixed problem boundary
        raise _ProblemBoundaryFailure from None


def _validate_problem_publication(
    hooks: _RunHooks, controls: Any, provider: Any
) -> None:
    state, validate, _installed, _error_type, _error_token = hooks
    if state is None:
        return
    if provider is None or validate is None:
        raise _ProblemBoundaryFailure from None
    try:
        validate(state, controls, provider)
    except BaseException:  # noqa: BLE001 - fixed problem boundary
        raise _ProblemBoundaryFailure from None


def _validate_research_publication(
    hooks: _RunHooks, controls: Any, provider: Any, problem: Any
) -> None:
    state, validate, _installed, _error_type, _error_token = hooks
    if state is None:
        return
    if provider is None or problem is None or validate is None:
        raise _ResearchContextBoundaryFailure from None
    try:
        validate(state, controls, provider, problem)
    except BaseException:  # noqa: BLE001 - fixed research-context boundary
        raise _ResearchContextBoundaryFailure from None


def _validate_problem_installed(hooks: _RunHooks, owner: Any) -> None:
    state, _publication, validate, _error_type, _error_token = hooks
    if state is None:
        return
    try:
        if validate is None:
            raise TypeError
        validate(state, owner)
    except BaseException:  # noqa: BLE001 - fixed problem boundary
        raise _ProblemBoundaryFailure from None


def _validate_research_installed(hooks: _RunHooks, owner: Any) -> None:
    state, _publication, validate, _error_type, _error_token = hooks
    if state is None:
        return
    try:
        if validate is None:
            raise TypeError
        validate(state, owner)
    except BaseException:  # noqa: BLE001 - fixed research-context boundary
        raise _ResearchContextBoundaryFailure from None


def _make_hidden_error_pair(
    type_anchor: Any = type,
    tuple_type: Any = tuple,
    str_type: Any = str,
    error_type: Any = TypeError,
) -> Callable[[Any], tuple[type, str] | None]:
    def pair(authority: Any) -> tuple[type, str] | None:
        if authority is None:
            return None
        if (
            type_anchor(authority) is tuple_type
            and authority.__len__() == 3
            and type_anchor(authority[0]) is tuple_type
        ):
            authority = authority[0]
        if (
            type_anchor(authority) is not tuple_type
            or authority.__len__() != 9
            or type_anchor(authority[7]) is not type_anchor
            or type_anchor(authority[8]) is not str_type
        ):
            raise error_type
        return authority[7], authority[8]

    return pair


_hidden_error_pair = _make_hidden_error_pair()
del _make_hidden_error_pair


def _failure_name(research: Any, problem: Any, provider: bool) -> str:
    if research is not None:
        return "research_context"
    if problem is not None:
        return "problem"
    return "provider" if provider else "controls"


def _validate_initial_screening_run(
    requested_rounds: Any,
    owner: Any,
    *,
    caller_valid: Any = True,
    controls_dispatch: Any = None,
    dependency_validator: Callable[[], None] = _validate_run_router_dependencies,
    registered_run: Callable[..., None] = _validate_registered_run,
    research_reader: Callable[[Any], Any] = _read_hidden_research_authority,
    problem_reader: Callable[[Any], Any] = _read_hidden_problem_authority,
    error_pair: Callable[[Any], Any] = _hidden_error_pair,
    provider_registered: Callable[[Any], bool] = _provider_owner_is_registered,
    provider_error_type: Any = _InitialScreeningProviderPolicyError,
    provider_error_token: Any = _PROVIDER_ERROR,
    controls_error_type: Any = _InitialScreeningStudyControlsError,
    controls_error_token: Any = _ERROR,
    research_failure: Any = _ResearchContextBoundaryFailure,
    problem_failure: Any = _ProblemBoundaryFailure,
    base_exception: Any = BaseException,
    failure_name: Callable[..., str] = _failure_name,
) -> None:
    research_error: Any = None
    problem_error: Any = None
    provider_active = False
    failure = ""
    try:
        research_error = error_pair(research_reader(owner))
        problem_error = error_pair(problem_reader(owner))
        provider_active = provider_registered(owner)
        if caller_valid is not True and (caller_valid is not None or research_error):
            raise base_exception
        dependency_validator()
    except base_exception:
        failure = failure_name(research_error, problem_error, provider_active)
    if not failure:
        try:
            registered_run(requested_rounds, owner, controls_dispatch)
        except provider_error_type:
            failure = "provider"
        except research_failure:
            failure = "research_context"
        except problem_failure:
            failure = "problem"
        except base_exception:
            failure = failure_name(research_error, problem_error, provider_active)
    if failure == "provider":
        raise provider_error_type(provider_error_token) from None
    if failure == "research_context" and research_error is not None:
        error_type, error_token = research_error
        raise error_type(error_token) from None
    if failure == "problem" and problem_error is not None:
        error_type, error_token = problem_error
        raise error_type(error_token) from None
    if failure:
        raise controls_error_type(controls_error_token) from None


_ROUTER_HELPER_ITEMS = (
    ("_validate_run_router_dependencies", _validate_run_router_dependencies),
    ("_provider_owner_is_registered", _provider_owner_is_registered),
    ("_write_hidden_research_authority", _write_hidden_research_authority),
    ("_read_hidden_research_authority", _read_hidden_research_authority),
    ("_write_hidden_problem_authority", _write_hidden_problem_authority),
    ("_read_hidden_problem_authority", _read_hidden_problem_authority),
    ("_hidden_error_pair", _hidden_error_pair),
    ("_failure_name", _failure_name),
    ("_module_storage", _module_storage),
    ("_register_boundary_authority", _register_boundary_authority),
    (
        "_register_research_context_run_authority",
        _register_research_context_run_authority,
    ),
    ("_register_problem_run_authority", _register_problem_run_authority),
    ("_same_authority", _same_authority),
    ("_identity_authority", _identity_authority),
    ("_validated_run_authority", _validated_run_authority),
    ("_validated_dispatch_entries", _validated_dispatch_entries),
    ("_validate_caller_dispatch", _validate_caller_dispatch),
    ("_validate_registered_run", _validate_registered_run),
    ("_research_context_run_hooks", _research_context_run_hooks),
    ("_problem_run_hooks", _problem_run_hooks),
    ("_validate_problem_publication", _validate_problem_publication),
    ("_validate_research_publication", _validate_research_publication),
    ("_validate_problem_installed", _validate_problem_installed),
    ("_validate_research_installed", _validate_research_installed),
    ("_validate_initial_screening_run", _validate_initial_screening_run),
)
_ROUTER_ALIAS_ITEMS = (
    ("sys", sys),
    ("weakref", weakref),
    ("Callable", Callable),
    ("FunctionType", FunctionType),
    ("ModuleType", ModuleType),
    ("cast", cast),
    ("_ERROR", _ERROR),
    ("_FILENAME", _FILENAME),
    ("_MAX_BYTES", _MAX_BYTES),
    ("_InitialScreeningRuntimeInputs", _InitialScreeningRuntimeInputs),
    ("_InitialScreeningStudyControlsError", _InitialScreeningStudyControlsError),
    ("_PROVIDER_ERROR", _PROVIDER_ERROR),
    ("_PROVIDER_REGISTERED_OWNERS", _PROVIDER_REGISTERED_OWNERS),
    ("_InitialScreeningProviderPolicyError", _InitialScreeningProviderPolicyError),
    ("_RESEARCH_MARKER_KEYS", _RESEARCH_MARKER_KEYS),
    ("_PROBLEM_MARKER_KEYS", _PROBLEM_MARKER_KEYS),
    ("_CONTROLS_MARKER_KEYS", _CONTROLS_MARKER_KEYS),
    ("_RESEARCH_VALIDATION_MODULE_NAME", _RESEARCH_VALIDATION_MODULE_NAME),
    ("_RESEARCH_BOUNDARY_MODULE_NAME", _RESEARCH_BOUNDARY_MODULE_NAME),
    ("_PROBLEM_VALIDATION_MODULE_NAME", _PROBLEM_VALIDATION_MODULE_NAME),
    ("_PROBLEM_BOUNDARY_MODULE_NAME", _PROBLEM_BOUNDARY_MODULE_NAME),
    ("_RESEARCH_ERROR_TYPE_NAME", _RESEARCH_ERROR_TYPE_NAME),
    ("_PROBLEM_ERROR_TYPE_NAME", _PROBLEM_ERROR_TYPE_NAME),
    ("_ENTRY_NAMES", _ENTRY_NAMES),
    ("_PROBLEM_ENTRY_NAMES", _PROBLEM_ENTRY_NAMES),
    ("_CONTROLS_DISPATCH_NAMES", _CONTROLS_DISPATCH_NAMES),
    ("_PROVIDER_DISPATCH_NAMES", _PROVIDER_DISPATCH_NAMES),
    ("_RESEARCH_CONTEXT_AUTHORITIES", _RESEARCH_CONTEXT_AUTHORITIES),
    ("_PROBLEM_AUTHORITIES", _PROBLEM_AUTHORITIES),
    ("_ROUTER_BUILTIN_NAMES", _ROUTER_BUILTIN_NAMES),
    ("_SELF_MODULE", _SELF_MODULE),
    ("_SELF_MODULE_STORAGE", _SELF_MODULE_STORAGE),
    ("_SELF_MODULE_NAME", _SELF_MODULE_NAME),
    ("_ProblemBoundaryFailure", _ProblemBoundaryFailure),
    ("_ResearchContextBoundaryFailure", _ResearchContextBoundaryFailure),
)
_install_run_router_dependencies(_ROUTER_HELPER_ITEMS, _ROUTER_ALIAS_ITEMS)
del _install_run_router_dependencies


__all__ = []
