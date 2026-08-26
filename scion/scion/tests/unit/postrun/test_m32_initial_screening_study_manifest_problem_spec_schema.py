from __future__ import annotations

import ast
import copy
import inspect
import json
import sys
from types import ModuleType
from typing import Any

import pytest

import scion.postrun.research_effectiveness.study_manifest_problem_spec_declaration_schema as declaration_module
from scion.core.initial_screening_problem_spec import _freeze_problem_spec_inputs
from scion.postrun.research_effectiveness.study_manifest_problem_spec_declaration_schema import (
    _ERROR,
    _LIMITATIONS,
    _MAX_BYTES,
    _normalize_declared_problem_spec,
    _StudyManifestProblemSpecDeclarationSchemaError,
)
from scion.postrun.research_effectiveness.study_manifest_problem_spec_schema import (
    _config_provider_problem_spec_join_result,
    _normalize_study_manifest_problem_spec,
    _StudyManifestProblemSpecSchemaError,
)
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import (
    ResearchSurfaceMechanismTelemetrySpec,
    ResearchSurfaceReturnValueSpec,
)
from scion.tests.unit.core.test_initial_screening_problem_spec import _cvrp_inputs
from scion.tests.unit.postrun.test_m32_initial_screening_study_manifest_provider_policy_schema import (
    _manifest as _v2_manifest,
)

_MANIFEST_VERSION = (
    "scion.initial_screening_study_manifest."
    "config_subset_and_requested_provider_policy_and_problem_spec_declaration.v3"
)
_JOIN_VERSION = (
    "scion.initial_screening_study_manifest_join."
    "config_subset_and_requested_provider_policy_and_problem_spec_declaration.v3"
)
_SCOPE = "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_PROBLEM_SPEC_DECLARATION_ONLY"
_STATUS = (
    "CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_PROBLEM_SPEC_DECLARATION_JOINED"
)
_EXPECTED_JOIN_LIMITATIONS = (
    "SCIENTIFIC_ENDPOINTS_NOT_EVALUATED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED",
    "PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED",
    "PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED",
    "LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "MANIFEST_GIT_AND_PREOUTCOME_TIMING_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ACTUAL_ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_EXPECTED_PROBLEM_KEYS = frozenset(
    {
        "spec_version",
        "id",
        "display_name",
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
    }
)


def _problem_leaf() -> dict[str, Any]:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    inputs = _freeze_problem_spec_inputs(
        bridge.problem_spec,
        adapter,
        bridge.operator_execute_signature,
    )
    return json.loads(inputs.payload_bytes)


def _manifest() -> dict[str, Any]:
    value = _v2_manifest()
    value["schema_version"] = _MANIFEST_VERSION
    value["scope"] = _SCOPE
    value["declared_problem_spec"] = _problem_leaf()
    return value


def _fixed_declaration_error(call: Any) -> None:
    with pytest.raises(_StudyManifestProblemSpecDeclarationSchemaError) as raised:
        call()
    error = raised.value
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def _fixed_manifest_error(call: Any) -> None:
    with pytest.raises(_StudyManifestProblemSpecSchemaError) as raised:
        call()
    error = raised.value
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_normalizes_v3_as_detached_v2_and_one_common_problem_declaration() -> None:
    raw = _manifest()
    expected = (
        json.dumps(
            raw["declared_problem_spec"],
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )

    normalized = _normalize_study_manifest_problem_spec(raw)

    assert normalized.base_manifest.base_manifest.problem_id == "cvrp"
    assert len(normalized.base_manifest.base_manifest.blocks) == 5
    assert normalized.declared_problem_spec.problem_id == "cvrp"
    assert normalized.declared_problem_spec.canonical_bytes == expected
    assert repr(normalized) == "_NormalizedStudyManifestProblemSpec(<redacted>)"
    assert (
        repr(normalized.declared_problem_spec)
        == "_NormalizedDeclaredProblemSpec(<redacted>)"
    )
    raw["problem_id"] = "drift"
    raw["declared_problem_spec"]["problem_spec_v1"]["description"] = "secret"
    assert normalized.base_manifest.base_manifest.problem_id == "cvrp"
    assert normalized.declared_problem_spec.canonical_bytes == expected
    assert "secret" not in repr(normalized)


def test_actual_full_freeze_leaf_matches_independent_decoder_and_exact_30() -> None:
    leaf = _problem_leaf()
    problem = leaf["problem_spec_v1"]
    normalized = _normalize_declared_problem_spec(leaf)

    assert set(leaf) == {
        "schema_version",
        "scope",
        "limitations",
        "problem_spec_v1",
    }
    assert tuple(leaf["limitations"]) == _LIMITATIONS
    assert set(problem) == _EXPECTED_PROBLEM_KEYS
    assert len(problem) == 30
    assert "root_dir" not in problem
    assert len(normalized.canonical_bytes) <= _MAX_BYTES
    assert (
        normalized.canonical_bytes
        == json.dumps(
            leaf,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def test_declared_problem_cap_accepts_exact_size_and_rejects_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaf = _problem_leaf()
    size = len(_normalize_declared_problem_spec(leaf).canonical_bytes)
    monkeypatch.setattr(declaration_module, "_MAX_BYTES", size)
    assert _normalize_declared_problem_spec(leaf).problem_id == "cvrp"
    monkeypatch.setattr(declaration_module, "_MAX_BYTES", size - 1)
    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(leaf))


def test_returns_only_the_fixed_v3_validation_result() -> None:
    result = _config_provider_problem_spec_join_result()

    assert result == {
        "schema_version": _JOIN_VERSION,
        "status": _STATUS,
        "validated_scope": _SCOPE,
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_EXPECTED_JOIN_LIMITATIONS),
    }
    assert len(result["limitations"]) == 24
    assert "PROBLEM_SPEC_UNVERIFIED" not in result["limitations"]
    assert "PROBLEM_ADAPTER_UNVERIFIED" in result["limitations"]


@pytest.mark.parametrize(
    "mutation",
    [
        "manifest_extra",
        "manifest_scope",
        "manifest_problem_mismatch",
        "leaf_extra",
        "leaf_limit_order",
        "root_dir",
        "missing_field",
        "wrong_field_type",
    ],
)
def test_rejects_v3_and_declaration_exact_shape_drift(mutation: str) -> None:
    manifest = _manifest()
    leaf = manifest["declared_problem_spec"]
    problem = leaf["problem_spec_v1"]
    if mutation == "manifest_extra":
        manifest["extra"] = None
    elif mutation == "manifest_scope":
        manifest["scope"] = "CONFIG_SUBSET_ONLY"
    elif mutation == "manifest_problem_mismatch":
        manifest["problem_id"] = "other"
    elif mutation == "leaf_extra":
        leaf["api_key"] = "secret"
    elif mutation == "leaf_limit_order":
        leaf["limitations"] = list(reversed(leaf["limitations"]))
    elif mutation == "root_dir":
        problem["root_dir"] = "/secret"
    elif mutation == "missing_field":
        problem.pop("description")
    else:
        problem["description"] = 1
    _fixed_manifest_error(lambda: _normalize_study_manifest_problem_spec(manifest))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("spec_version",), "problem-v2"),
        (("operator_interface", "execute_signature"), ""),
        (("operator_interface", "execute_signature"), "run(self, x)"),
        (("parameter_search", "strategy"), "other"),
        (("objectives",), []),
        (("objectives", 0, "priority"), 2),
        (("measurement", "effect_scale", "practical_delta_screen"), -1.0),
        (("adapter", "import_path"), "foreign.problem:Adapter"),
        (("development_workspace_paths",), ["../escape.py"]),
    ],
)
def test_rejects_nonproducer_problem_semantics(
    path: tuple[Any, ...],
    value: Any,
) -> None:
    leaf = _problem_leaf()
    cursor: Any = leaf["problem_spec_v1"]
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = value
    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(leaf))


def test_signed_zero_is_preserved_in_detached_equality() -> None:
    positive = _problem_leaf()
    positive["problem_spec_v1"]["objectives"][0]["tie_tolerance"] = 0.0
    negative = copy.deepcopy(positive)
    negative["problem_spec_v1"]["objectives"][0]["tie_tolerance"] = -0.0

    positive_normalized = _normalize_declared_problem_spec(positive)
    negative_normalized = _normalize_declared_problem_spec(negative)

    assert positive_normalized.frozen != negative_normalized.frozen
    assert b'"tie_tolerance":-0.0' in negative_normalized.canonical_bytes


def test_normalized_producer_retains_valid_whitespace_mechanism_key() -> None:
    spec, _bridge, _adapter = _cvrp_inputs()
    assert spec.research_surfaces is not None
    evidence = spec.research_surfaces[0].evidence
    assert evidence is not None
    evidence.mechanism_telemetry[" two_opt "] = ResearchSurfaceMechanismTelemetrySpec()
    bridge = bridge_problem_spec_v1(spec)
    adapter = load_problem_adapter(spec)
    inputs = _freeze_problem_spec_inputs(
        bridge.problem_spec,
        adapter,
        bridge.operator_execute_signature,
    )
    leaf = json.loads(inputs.payload_bytes)

    normalized = _normalize_declared_problem_spec(leaf)

    assert b'" two_opt "' in normalized.canonical_bytes


def test_decoder_depth_matches_the_hardened_full_producer_boundary() -> None:
    spec, _bridge, _adapter = _cvrp_inputs()
    assert spec.research_surfaces is not None
    value: Any = 0
    for _index in range(15):
        value = [value]
    spec.research_surfaces[0].interface.return_values["result"] = (
        ResearchSurfaceReturnValueSpec(allowed_literals=[value])
    )
    bridge = bridge_problem_spec_v1(spec)
    adapter = load_problem_adapter(spec)
    inputs = _freeze_problem_spec_inputs(
        bridge.problem_spec,
        adapter,
        bridge.operator_execute_signature,
    )
    leaf = json.loads(inputs.payload_bytes)
    assert _normalize_declared_problem_spec(leaf).problem_id == "cvrp"

    too_deep = copy.deepcopy(leaf)
    too_deep["problem_spec_v1"]["research_surfaces"][0]["interface"]["return_values"][
        "result"
    ]["allowed_literals"] = [[value]]
    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(too_deep))


def test_manifest_embeds_the_maximum_problem_declaration_depth() -> None:
    spec, _bridge, _adapter = _cvrp_inputs()
    assert spec.research_surfaces is not None
    value: Any = 0
    for _index in range(15):
        value = [value]
    spec.research_surfaces[0].interface.return_values["result"] = (
        ResearchSurfaceReturnValueSpec(allowed_literals=[value])
    )
    bridge = bridge_problem_spec_v1(spec)
    adapter = load_problem_adapter(spec)
    inputs = _freeze_problem_spec_inputs(
        bridge.problem_spec,
        adapter,
        bridge.operator_execute_signature,
    )
    leaf = json.loads(inputs.payload_bytes)
    manifest = _manifest()
    manifest["declared_problem_spec"] = leaf

    assert _normalize_study_manifest_problem_spec(manifest).declared_problem_spec == (
        _normalize_declared_problem_spec(leaf)
    )

    too_deep = copy.deepcopy(manifest)
    too_deep["declared_problem_spec"]["problem_spec_v1"]["research_surfaces"][0][
        "interface"
    ]["return_values"]["result"]["allowed_literals"] = [[value]]
    _fixed_manifest_error(lambda: _normalize_study_manifest_problem_spec(too_deep))


def test_rejects_canary_nul_that_mechanical_bridge_cannot_publish() -> None:
    spec, _bridge, _adapter = _cvrp_inputs()
    spec.canary_case_path = "cases/canary\x00.json"
    with pytest.raises(ValueError):
        bridge_problem_spec_v1(spec)

    leaf = _problem_leaf()
    leaf["problem_spec_v1"]["canary_case_path"] = "cases/canary\x00.json"
    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(leaf))


def test_accepts_full_producer_adapter_binding_with_nonidentifier_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec, bridge, adapter = _cvrp_inputs()
    adapter_type = type(adapter)
    module_name = "scion.problems.cvrp.bad-name"
    class_name = "bad-class"
    module = ModuleType(module_name)
    setattr(module, class_name, adapter_type)
    monkeypatch.setitem(sys.modules, module_name, module)
    old_module = adapter_type.__module__
    old_qualname = adapter_type.__qualname__
    try:
        adapter_type.__module__ = module_name
        adapter_type.__qualname__ = class_name
        spec.adapter.import_path = f"{module_name}:{class_name}"
        bridge.problem_spec.spec_v1.adapter.import_path = spec.adapter.import_path
        bridge.problem_spec.adapter_import_path = spec.adapter.import_path
        inputs = _freeze_problem_spec_inputs(
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )
        normalized = _normalize_declared_problem_spec(json.loads(inputs.payload_bytes))
    finally:
        adapter_type.__module__ = old_module
        adapter_type.__qualname__ = old_qualname

    assert normalized.problem_id == "cvrp"


def test_container_subclass_is_rejected_without_running_iteration_hook() -> None:
    hooks = 0

    class HiddenDict(dict[str, Any]):
        def __iter__(self):
            nonlocal hooks
            hooks += 1
            return super().__iter__()

    leaf = _problem_leaf()
    leaf["problem_spec_v1"] = HiddenDict(leaf["problem_spec_v1"])

    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(leaf))
    assert hooks == 0


def test_archived_decoder_has_no_live_problem_schema_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaf = _problem_leaf()

    def bomb(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("live producer helper was called")

    import scion.core.initial_screening_problem_spec as producer_module

    monkeypatch.setattr(producer_module, "_canonical_problem_spec_payload", bomb)
    monkeypatch.setattr(producer_module, "_freeze_tree", bomb)
    assert _normalize_declared_problem_spec(leaf).problem_id == "cvrp"

    source = inspect.getsource(declaration_module)
    imports = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith(
            (
                "scion.core",
                "scion.problem",
                "pydantic",
            )
        )
        for name in imports
    )


def test_fixed_errors_and_repr_do_not_expose_problem_sentinel(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "PRIVATE-PROBLEM-SENTINEL"
    leaf = _problem_leaf()
    leaf["problem_spec_v1"]["description"] = sentinel
    leaf["problem_spec_v1"]["objectives"][0]["priority"] = 99

    _fixed_declaration_error(lambda: _normalize_declared_problem_spec(leaf))

    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert sentinel not in caplog.text
    assert sentinel not in repr(_normalize_declared_problem_spec(_problem_leaf()))
