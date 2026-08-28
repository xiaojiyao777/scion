from __future__ import annotations

import builtins
import gc
import importlib
import json
import subprocess
import sys
import weakref
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scion.core import (
    initial_screening_problem_spec as problem_boundary,
)
from scion.core import initial_screening_research_context as research_boundary
from scion.core import (
    initial_screening_research_context_capsule_runtime as capsule_runtime,
)
from scion.core import (
    initial_screening_research_context_integration as integration,
)
from scion.core import (
    initial_screening_research_context_validation as validation,
)
from scion.core import initial_screening_study_controls_run_validation as run_validation
from scion.core import (
    initial_screening_study_controls_validation as controls_validation,
)
from scion.core import (
    initial_screening_study_provider_policy_validation as provider_validation,
)
from scion.core.initial_screening_problem_spec import (
    _ERROR as _PROBLEM_ERROR,
)
from scion.core.initial_screening_problem_spec import (
    _InitialScreeningProblemSpecError,
)
from scion.core.initial_screening_research_context import (
    _ERROR,
    _FILENAME,
    _InitialScreeningResearchContextError,
)
from scion.core.initial_screening_study_controls import (
    _ERROR as _CONTROLS_ERROR,
)
from scion.core.initial_screening_study_controls import (
    _FILENAME as _CONTROLS_FILENAME,
)
from scion.core.initial_screening_study_controls import (
    _InitialScreeningStudyControlsError,
    _InitialScreeningStudyControlsRequest,
)
from scion.core.initial_screening_study_provider_policy import (
    _ERROR as _PROVIDER_ERROR,
)
from scion.core.initial_screening_study_provider_policy import (
    _InitialScreeningProviderPolicyError,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.proposal_pipeline import ProposalPipeline
from scion.proposal.context_manager import ContextManager
from scion.tests.unit.core.test_initial_screening_problem_spec import _problem_manager
from scion.tests.unit.core.test_initial_screening_research_context_integration import (
    _active_manager as _build_active_manager,
)
from scion.tests.unit.core.test_initial_screening_study_controls import _manager
from scion.tests.unit.core.test_initial_screening_study_provider_policy import (
    _provider_manager,
)


def _fixed_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningResearchContextError
    assert error.args == (_ERROR,)
    assert str(error) == _ERROR
    assert error.__cause__ is None
    assert error.__context__ is None


def _forbid_preflight(manager: Any) -> None:
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after research-context drift"
    )


def _active_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    gc.collect()
    return _build_active_manager(tmp_path, monkeypatch)


def test_validation_reimport_rejects_coordinated_integration_replacements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation_name = validation.__name__
    edges_name = "scion.core.initial_screening_research_context_edges"
    calls: list[str] = []
    fake_edges = ModuleType(edges_name)

    def fake_validator() -> None:
        calls.append("validator")

    def fake_installer(_module: ModuleType) -> None:
        calls.append("installer")

    fake_edges._install_validation_authority = fake_installer
    monkeypatch.delitem(sys.modules, validation_name)
    monkeypatch.delattr(
        sys.modules["scion.core"],
        "initial_screening_research_context_validation",
    )
    monkeypatch.setattr(
        integration, "_validate_integration_dependencies", fake_validator
    )
    monkeypatch.setattr(integration, "edges_module", fake_edges)

    with pytest.raises(TypeError):
        importlib.import_module(validation_name)

    assert calls == []


def test_validation_import_missing_capsule_class_does_not_call_module_fallback() -> (
    None
):
    script = """
import importlib

capsule = importlib.import_module(
    "scion.core.initial_screening_research_context_capsule"
)
name = "_InitialScreeningResearchContextCapsule"
original = vars(capsule).pop(name)
calls = []

def fallback(missing):
    calls.append(missing)
    return original

vars(capsule)["__getattr__"] = fallback
try:
    importlib.import_module(
        "scion.core.initial_screening_research_context_validation"
    )
except BaseException as error:
    assert type(error) is TypeError
    assert error.args == ()
else:
    raise AssertionError("validation import unexpectedly succeeded")
assert calls == []
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[4],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_default_off_construction_and_run_do_not_import_or_call_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        validation,
        "_prepare_research_context_run_validation",
        lambda *_args, **_kwargs: pytest.fail("default run called b1 validation"),
    )
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name.startswith("scion.core.initial_screening_research_context"):
            pytest.fail("default-off path imported the b1 boundary")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: (
        "terminal",
        requested_rounds,
    )

    assert manager.run(2) == ("terminal", 2)


def test_full_active_run_validates_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    manager._run_research_environment_preflight = lambda: calls.append("preflight")

    def run_loop(*, requested_rounds: int) -> tuple[None, int]:
        calls.append("loop")
        return None, requested_rounds

    manager._campaign_loop.run = run_loop

    assert manager.run(2) == (None, 2)
    assert calls == ["preflight", "loop"]
    baseline = validation._REGISTERED_OWNERS[manager]
    assert repr(baseline) == "_RegisteredResearchContextBaseline(<redacted>)"
    assert baseline.inputs_ref() is manager._initial_screening_research_context
    assert (
        baseline.capsule_ref()
        is manager._problem_runtime.__dict__[
            "_initial_screening_research_context_capsule"
        ]
    )


def test_research_registration_rejects_rebased_directory_fingerprints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = validation._register_initial_screening_research_context_owner

    def drift_then_register(owner: Any, inputs: Any) -> None:
        object.__setattr__(
            inputs.publication,
            "directory_fingerprints",
            ((101, 103),),
        )
        original(owner, inputs)

    monkeypatch.setattr(
        validation,
        "_register_initial_screening_research_context_owner",
        drift_then_register,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _build_active_manager(tmp_path, monkeypatch)

    _fixed_error(captured.value)


def test_problem_registration_rejects_rebased_directory_fingerprints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = problem_boundary._register_initial_screening_problem_spec_owner

    def drift_then_register(owner: Any, inputs: Any) -> None:
        object.__setattr__(
            inputs.publication,
            "directory_fingerprints",
            ((107, 109),),
        )
        original(owner, inputs)

    monkeypatch.setattr(
        problem_boundary,
        "_register_initial_screening_problem_spec_owner",
        drift_then_register,
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as captured:
        _problem_manager(tmp_path, monkeypatch)

    error = captured.value
    assert error.args == (_PROBLEM_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    "mutation",
    ("clear", "active_only", "inputs_only", "inactive", "carrier_none"),
)
def test_run_gate_rejects_marker_and_carrier_drift_with_context_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    storage = vars(manager)
    active = "_initial_screening_research_context_active"
    inputs = "_initial_screening_research_context"
    if mutation == "clear":
        del storage[active]
        del storage[inputs]
    elif mutation == "active_only":
        del storage[inputs]
    elif mutation == "inputs_only":
        del storage[active]
    elif mutation == "inactive":
        storage[active] = False
    else:
        storage[inputs] = None
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)


def test_run_gate_rejects_exact_outer_carrier_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    manager._initial_screening_research_context = replace(
        manager._initial_screening_research_context
    )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)


@pytest.mark.parametrize(
    "mutation",
    (
        "runtime_capsule",
        "context_capsule",
        "proposal_runtime",
        "runtime_input",
        "runtime_history",
        "context_input",
        "context_observations",
        "context_history",
    ),
)
def test_run_gate_rejects_installed_graph_and_legacy_field_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    runtime = manager._problem_runtime
    context = runtime._ctx_manager
    if mutation == "runtime_capsule":
        runtime._initial_screening_research_context_capsule = object()
    elif mutation == "context_capsule":
        context._initial_screening_research_context_capsule = object()
    elif mutation == "proposal_runtime":
        manager._proposal_pipeline.problem_runtime = object()
    elif mutation == "runtime_input":
        runtime._research_input = {}
    elif mutation == "runtime_history":
        runtime._research_history = ({},)
    elif mutation == "context_input":
        context._research_input = {}
    elif mutation == "context_observations":
        context._prior_research_observations = ({},)
    else:
        context._research_history = ({},)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)


def test_four_leaf_drift_fails_before_installed_runtime_and_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        validation,
        "_validate_research_context_installed_runtime",
        lambda *_args, **_kwargs: calls.append("installed"),
    )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


@pytest.mark.parametrize(
    "mutation",
    (
        "validation_alias",
        "integration_helper",
        "runtime_helper",
        "integration_name",
        "runtime_module_identity",
    ),
)
def test_run_gate_locks_module_and_helper_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    if mutation == "validation_alias":
        monkeypatch.setattr(
            validation,
            "_published_research_context_inputs_key",
            lambda _inputs: (),
        )
    elif mutation == "integration_helper":
        monkeypatch.setattr(
            integration,
            "_materialize_research_context_h_fields",
            lambda _capsule: {},
        )
    elif mutation == "runtime_helper":
        monkeypatch.setattr(
            capsule_runtime,
            "_research_context_capsule_h_fields",
            lambda _capsule: {},
        )
    elif mutation == "integration_name":
        monkeypatch.setattr(integration, "__name__", "private.integration")
    else:
        monkeypatch.setitem(
            __import__("sys").modules,
            "scion.core.initial_screening_research_context_capsule_runtime",
            ModuleType("replacement"),
        )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)


@pytest.mark.parametrize(
    ("class_value", "method"),
    (
        (ProblemRuntime, "build_hypothesis_context"),
        (ContextManager, "build_code_context"),
        (ProposalPipeline, "generate_hypothesis"),
    ),
)
def test_run_gate_rejects_consumer_class_method_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_value: type[Any],
    method: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    monkeypatch.setattr(class_value, method, lambda *_args, **_kwargs: None)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)


@pytest.mark.parametrize(
    ("class_value", "method"),
    (
        (ProblemRuntime, "build_hypothesis_context"),
        (ContextManager, "build_code_context"),
        (ProposalPipeline, "generate_hypothesis"),
    ),
)
def test_descriptor_replacement_is_rejected_without_binding_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_value: type[Any],
    method: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []

    class HookDescriptor:
        def __get__(self, instance: Any, owner: Any = None) -> Any:
            calls.append("bound")
            return lambda *_args, **_kwargs: None

    monkeypatch.setattr(class_value, method, HookDescriptor())
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


def test_publication_entry_replacement_cannot_bypass_bad_fourth_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        validation,
        "_validate_research_context_publication",
        lambda *_args, **_kwargs: calls.append("publication"),
    )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


def test_router_helper_replacement_cannot_bypass_bad_fourth_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def bypass(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("router")
        return None, None, None, None, None

    monkeypatch.setattr(run_validation, "_research_context_run_hooks", bypass)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


def test_router_entry_replacement_is_rejected_at_caller_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def bypass(*_args: Any, **_kwargs: Any) -> None:
        calls.append("entry")

    monkeypatch.setattr(run_validation, "_validate_initial_screening_run", bypass)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


@pytest.mark.parametrize("boundary", (research_boundary, problem_boundary))
def test_run_uses_registered_fixed_error_pair_after_schema_token_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: ModuleType,
) -> None:
    if boundary is research_boundary:
        manager = _active_manager(tmp_path, monkeypatch)
        expected_type = _InitialScreeningResearchContextError
        expected_token = _ERROR
    else:
        manager = _problem_manager(tmp_path, monkeypatch)
        expected_type = _InitialScreeningProblemSpecError
        expected_token = _PROBLEM_ERROR
    monkeypatch.setattr(boundary, "_ERROR", "BODY_SENTINEL")
    _forbid_preflight(manager)

    with pytest.raises(expected_type) as captured:
        manager.run(2)

    error = captured.value
    assert type(error) is expected_type
    assert error.args == (expected_token,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_local_same_key_replacement_cannot_hide_coordinated_canonical_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    inputs = manager._initial_screening_research_context
    capsule = inputs.capsule
    payload = json.loads(inputs.payload_bytes)
    payload["problem_id"] = "alternate-problem"
    replacement_payload = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    object.__setattr__(capsule, "problem_id", "alternate-problem")
    object.__setattr__(inputs, "payload_bytes", replacement_payload)
    calls: list[str] = []

    def bypass(*_args: Any) -> bool:
        calls.append("same-key")
        return True

    monkeypatch.setattr(validation, "_same_key", bypass)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


@pytest.mark.parametrize("mutation", ("replacement", "in_place"))
def test_hidden_baseline_rejects_equal_carrier_and_public_baseline_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    old_inputs = manager._initial_screening_research_context
    new_inputs = replace(old_inputs)
    old_baseline = validation._REGISTERED_OWNERS[manager]
    old_inputs_ref = old_baseline.inputs_ref
    old_inputs_key = old_baseline.inputs_key
    new_inputs_ref = weakref.ref(new_inputs)
    new_inputs_key = validation._published_research_context_inputs_key(new_inputs)
    monkeypatch.setattr(manager, "_initial_screening_research_context", new_inputs)
    if mutation == "replacement":
        validation._REGISTERED_OWNERS[manager] = replace(
            old_baseline,
            inputs_ref=new_inputs_ref,
            inputs_key=new_inputs_key,
        )
    else:
        object.__setattr__(old_baseline, "inputs_ref", new_inputs_ref)
        object.__setattr__(old_baseline, "inputs_key", new_inputs_key)
    _forbid_preflight(manager)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as captured:
            manager.run(2)
    finally:
        validation._REGISTERED_OWNERS[manager] = old_baseline
        object.__setattr__(old_baseline, "inputs_ref", old_inputs_ref)
        object.__setattr__(old_baseline, "inputs_key", old_inputs_key)

    assert new_inputs is not old_inputs
    _fixed_error(captured.value)


@pytest.mark.parametrize("result", (None, "crafted"))
def test_router_identity_authority_replacement_cannot_change_fixed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: str | None,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def replacement(*_args: Any) -> Any:
        calls.append("identity")
        if result is None:
            return None
        return (None, None, None, None, (), (), "Error", type, "BODY_SENTINEL")

    monkeypatch.setattr(run_validation, "_identity_authority", replacement)
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


@pytest.mark.parametrize("name", ("type", "any", "len", "vars", "zip"))
def test_router_builtin_shadow_is_rejected_before_replacement_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    original = getattr(builtins, name)

    def delegate(*args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return original(*args, **kwargs)

    monkeypatch.setattr(run_validation, name, delegate, raising=False)
    with pytest.raises(TypeError):
        run_validation._validate_run_router_dependencies()
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []


def test_router_registration_helper_replacement_fails_without_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = validation._register_initial_screening_research_context_owner
    calls: list[str] = []

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        calls.append("register")

    def replace_then_register(owner: Any, inputs: Any) -> None:
        monkeypatch.setattr(
            run_validation,
            "_register_boundary_authority",
            replacement,
        )
        original(owner, inputs)

    monkeypatch.setattr(
        validation,
        "_register_initial_screening_research_context_owner",
        replace_then_register,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _build_active_manager(tmp_path, monkeypatch)

    _fixed_error(captured.value)
    assert calls == []


def test_public_authority_clear_keeps_hidden_fixed_error_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    authority = run_validation._RESEARCH_CONTEXT_AUTHORITIES[manager]
    run_validation._RESEARCH_CONTEXT_AUTHORITIES.clear()
    _forbid_preflight(manager)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as captured:
            manager.run(2)
    finally:
        run_validation._RESEARCH_CONTEXT_AUTHORITIES[manager] = authority

    _fixed_error(captured.value)


def test_controls_dispatch_replacement_stops_pure_controls_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    (tmp_path / "campaign" / _CONTROLS_FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        controls_validation,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: calls.append("controls"),
    )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningStudyControlsError) as captured:
        manager.run(2)

    assert captured.value.args == (_CONTROLS_ERROR,)
    assert calls == []


def test_provider_dispatch_replacement_stops_provider_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _client, _payload = _provider_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        provider_validation,
        "_prepare_provider_policy_run_validation",
        lambda *_args, **_kwargs: calls.append("provider"),
    )
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningProviderPolicyError) as captured:
        manager.run(2)

    assert captured.value.args == (_PROVIDER_ERROR,)
    assert calls == []


def test_default_off_run_ignores_loaded_research_validation_name_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    monkeypatch.setattr(validation, "__name__", "drifted.research.validation")
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: requested_rounds

    assert manager.run(2) == 2


@pytest.mark.parametrize("name", ("type", "any", "len", "vars", "zip"))
def test_validation_builtin_shadow_is_rejected_before_replacement_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls: list[str] = []
    original = getattr(builtins, name)

    def delegate(*args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return original(*args, **kwargs)

    monkeypatch.setattr(validation, name, delegate, raising=False)
    with pytest.raises(TypeError):
        validation._validate_validation_dependencies()
    _forbid_preflight(manager)

    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager.run(2)

    _fixed_error(captured.value)
    assert calls == []
