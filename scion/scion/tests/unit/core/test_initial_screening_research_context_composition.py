from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scion.core import (
    initial_screening_research_context_capsule as capsule_module,
)
from scion.core import (
    initial_screening_research_context_capsule_runtime as capsule_runtime_module,
)
from scion.core import (
    initial_screening_research_context_composition as composition_module,
)
from scion.core.initial_screening_problem_spec import (
    _freeze_problem_spec_inputs,
    _InitialScreeningProblemSpecRequest,
)
from scion.core.initial_screening_research_context import (
    _ERROR,
    _InitialScreeningLoadedHistoryAvailable,
    _InitialScreeningLoadedHistoryUnavailable,
    _InitialScreeningResearchContextError,
    _InitialScreeningResearchContextRequest,
)
from scion.core.initial_screening_research_context_capsule import (
    _InitialScreeningResearchContextPublication,
    _validate_capsule_dependencies,
)
from scion.core.initial_screening_research_context_capsule_runtime import (
    _bind_research_context_publication,
    _published_research_context_inputs_key,
    _research_context_capsule_h_fields,
    _research_context_capsule_pristine_key,
)
from scion.core.initial_screening_research_context_composition import (
    _InitialScreeningFrozenLoadedHistoryAvailable,
    _InitialScreeningFrozenLoadedHistoryUnavailable,
    _prepare_initial_screening_research_context,
    _research_context_inputs_pristine_key,
    _thaw_frozen_history,
    _thaw_frozen_json,
)
from scion.core.initial_screening_study_controls import (
    _InitialScreeningStudyControlsRequest,
)
from scion.core.initial_screening_study_provider_policy import (
    _InitialScreeningProviderPolicyRequest,
)
from scion.problem.bridge import (
    bridge_problem_spec_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.prior_research_observation import (
    CvrpPriorResearchObservationProvider,
)

_SCION_ROOT = Path(__file__).resolve().parents[4]
_CVRP_SPEC = _SCION_ROOT / "scion" / "problems" / "cvrp" / "problem-v1.yaml"
_CVRP_RESEARCH_INPUT = (
    _SCION_ROOT
    / "docs"
    / "experiments"
    / "v0.4"
    / "inputs"
    / "v04-cvrp-m9-m7-fc1-research-input.json"
)


def _problem_inputs() -> Any:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_SPEC)
    bridge = bridge_problem_spec_v1(spec_v1)
    return _freeze_problem_spec_inputs(
        bridge.problem_spec,
        load_problem_adapter(spec_v1),
        bridge.operator_execute_signature,
    )


def _markers() -> tuple[Any, Any, Any]:
    return (
        _InitialScreeningStudyControlsRequest(requested_rounds=2),
        _InitialScreeningProviderPolicyRequest(),
        _InitialScreeningProblemSpecRequest(),
    )


def _prepare(
    request: _InitialScreeningResearchContextRequest,
    *,
    problem_inputs: Any | None = None,
) -> Any:
    return _prepare_initial_screening_research_context(
        request,
        *_markers(),
        _problem_inputs() if problem_inputs is None else problem_inputs,
        research_input=None,
        research_history=(),
    )


def _research_input() -> dict[str, Any]:
    value = json.loads(_CVRP_RESEARCH_INPUT.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _history_record() -> dict[str, Any]:
    return {
        "schema_version": "scion.research_history.step.v1",
        "problem_id": "cvrp",
        "hypothesis": {
            "text": "Test one bounded local-search change.",
            "change_locus": "local_search",
            "action": "modify",
            "target_file": None,
            "predicted_direction": "improve",
            "target_weakness": "weak moves",
            "expected_effect": "better solutions",
            "suggested_weight": None,
        },
        "patch": None,
        "outcome": {
            "outcome": "research_rejected",
            "stage": "proposal_code",
            "reason_code": "PROPOSAL_REJECTED",
            "checks": [
                {"name": "proposal_shape", "passed": False, "severity": "light"}
            ],
        },
        "protocol": None,
        "decision": None,
    }


def _fixed_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningResearchContextError
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_real_cvrp_projection_is_single_ordered_detached_capture() -> None:
    research_input = _research_input()
    first = research_input["observations"][0]
    first_kind = first["observation_kind"]
    second = deepcopy(first)
    second["observation_kind"] = "second"
    third = deepcopy(first)
    third["observation_kind"] = "third"
    research_input["observations"] = [first, second, third]
    factory_calls = 0
    projection_calls: list[str] = []
    returned_values: list[dict[str, Any]] = []
    original_factory = CvrpAdapter.prior_research_observation_provider
    original_project = (
        CvrpPriorResearchObservationProvider.project_prior_research_observation
    )

    factory_code = original_factory.__code__
    project_code = original_project.__code__

    def profile(frame: Any, event: str, argument: Any) -> None:
        nonlocal factory_calls
        if frame.f_code is factory_code and event == "call":
            factory_calls += 1
        elif frame.f_code is project_code and event == "call":
            projection_calls.append(frame.f_locals["observation"]["observation_kind"])
        elif frame.f_code is project_code and event == "return":
            assert type(argument) is dict
            returned_values.append(argument)

    inputs = _problem_inputs()
    request = _InitialScreeningResearchContextRequest(
        research_input=research_input,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )

    sys.setprofile(profile)
    try:
        prepared = _prepare(request, problem_inputs=inputs)
    finally:
        sys.setprofile(None)
    payload = json.loads(prepared.payload_bytes)
    projection = payload["research_input"]["provider_projection"]

    assert factory_calls == 1
    assert projection_calls == [
        first_kind,
        "second",
        "third",
    ]
    assert [
        value["observation_kind"] for value in projection["prior_research_observations"]
    ] == [first_kind, "second", "third"]
    assert prepared.capsule.generation == 1
    assert prepared.capsule.problem_id == "cvrp"
    assert (
        prepared.request_snapshot.research_input is not prepared.capsule.research_input
    )
    assert repr(prepared) == "_InitialScreeningResearchContextInputs(<redacted>)"
    assert repr(prepared.capsule) == (
        "_InitialScreeningResearchContextCapsule(<redacted>)"
    )

    research_input["observations"][0]["observation_kind"] = "caller_mutated"
    returned_values[0]["observation_kind"] = "provider_mutated"
    detached = _thaw_frozen_json(prepared.capsule.provider_projection)
    detached["prior_research_observations"][0]["observation_kind"] = "copy_mutated"
    again = _thaw_frozen_json(prepared.capsule.provider_projection)
    assert again["prior_research_observations"][0]["observation_kind"] == first_kind
    assert _research_context_inputs_pristine_key(prepared)


@pytest.mark.parametrize("mode", ["absent", "available_empty"])
def test_absent_or_empty_input_never_resolves_projection_provider(
    mode: str,
) -> None:
    calls = {"factory": 0, "project": 0}
    factory_code = CvrpAdapter.prior_research_observation_provider.__code__
    project_code = (
        CvrpPriorResearchObservationProvider.project_prior_research_observation.__code__
    )

    def profile(frame: Any, event: str, _argument: Any) -> None:
        if event == "call" and frame.f_code is factory_code:
            calls["factory"] += 1
        elif event == "call" and frame.f_code is project_code:
            calls["project"] += 1

    research_input = (
        None
        if mode == "absent"
        else {"current_question": "What should be tested next?", "observations": []}
    )
    sys.setprofile(profile)
    try:
        prepared = _prepare(
            _InitialScreeningResearchContextRequest(
                research_input=research_input,
                loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
            )
        )
    finally:
        sys.setprofile(None)

    assert calls == {"factory": 0, "project": 0}
    if mode == "absent":
        assert prepared.capsule.research_input is None
        assert prepared.capsule.provider_projection is None
    else:
        assert prepared.capsule.research_input is not None
        projection = _thaw_frozen_json(prepared.capsule.provider_projection)
        assert projection == {
            "research_question": {"current_question": "What should be tested next?"},
            "prior_research_observations": [],
        }


def test_available_empty_and_unavailable_history_remain_distinct() -> None:
    available = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
        )
    )
    unavailable = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryUnavailable(),
        )
    )

    assert type(available.capsule.loaded_history) is (
        _InitialScreeningFrozenLoadedHistoryAvailable
    )
    assert type(unavailable.capsule.loaded_history) is (
        _InitialScreeningFrozenLoadedHistoryUnavailable
    )
    assert _thaw_frozen_history(available.capsule.loaded_history) == {
        "availability": "available",
        "records": [],
    }
    assert _thaw_frozen_history(unavailable.capsule.loaded_history) == {
        "availability": "unavailable",
        "reason": "HISTORY_REPLAY_BASIS_UNAVAILABLE",
    }
    assert available.payload_bytes != unavailable.payload_bytes


def test_loaded_history_is_normalized_and_nested_aliases_do_not_cross_capsule() -> None:
    record = _history_record()
    prepared = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryAvailable(records=(record,)),
        )
    )
    record["outcome"]["checks"][0]["name"] = "caller_mutated"

    first = _thaw_frozen_history(prepared.capsule.loaded_history)
    first["records"][0]["outcome"]["checks"][0]["name"] = "copy_mutated"
    second = _thaw_frozen_history(prepared.capsule.loaded_history)

    assert second["records"][0]["outcome"]["checks"][0]["name"] == ("proposal_shape")
    assert (
        json.loads(prepared.payload_bytes)["loaded_history"]["records"]
        == second["records"]
    )
    assert (
        prepared.request_snapshot.loaded_history is not prepared.capsule.loaded_history
    )


def test_capsule_runtime_materialization_and_publication_binding_are_fresh() -> None:
    prepared = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=_research_input(),
            loaded_history=_InitialScreeningLoadedHistoryAvailable(
                records=(_history_record(),)
            ),
        )
    )
    before = _research_context_capsule_pristine_key(prepared.capsule)
    fields = _research_context_capsule_h_fields(prepared.capsule)

    assert set(fields) == {
        "research_question",
        "prior_research_observations",
        "prior_research_history",
    }
    history = fields["prior_research_history"]
    assert "schema_version" not in history[0]
    assert "problem_id" not in history[0]
    fields["research_question"]["current_question"] = "mutated copy"
    fields["prior_research_observations"].clear()
    history[0]["outcome"]["checks"][0]["name"] = "mutated copy"
    assert _research_context_capsule_pristine_key(prepared.capsule) == before

    publication = _InitialScreeningResearchContextPublication(
        campaign_dir="/tmp/scion-private-campaign",
        directory_fingerprints=((1, 2),),
        leaf_fingerprint=(1, 2, 3, 4),
    )
    published = _bind_research_context_publication(prepared, publication)
    assert published is not prepared
    assert published.request_snapshot is prepared.request_snapshot
    assert published.capsule is prepared.capsule
    assert published.payload_bytes is prepared.payload_bytes
    assert published.publication is publication
    assert _published_research_context_inputs_key(published)


def test_capsule_h_fields_omit_absent_and_non_replayable_values() -> None:
    unavailable = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryUnavailable(),
        )
    )
    empty = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
        )
    )

    assert _research_context_capsule_h_fields(unavailable.capsule) == {}
    assert _research_context_capsule_h_fields(empty.capsule) == {}


def test_every_capsule_repr_is_fixed_under_class_name_mutation() -> None:
    prepared = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
        )
    )
    publication = _InitialScreeningResearchContextPublication(
        campaign_dir="/tmp/scion-private-campaign",
        directory_fingerprints=((1, 2),),
        leaf_fingerprint=(1, 2, 3, 4),
    )
    values = (
        (capsule_module._Redacted(), "_Redacted(<redacted>)"),
        (
            prepared.capsule.loaded_history,
            "_InitialScreeningFrozenLoadedHistoryAvailable(<redacted>)",
        ),
        (
            _InitialScreeningFrozenLoadedHistoryUnavailable(),
            "_InitialScreeningFrozenLoadedHistoryUnavailable(<redacted>)",
        ),
        (
            prepared.request_snapshot,
            "_InitialScreeningResearchContextRequestSnapshot(<redacted>)",
        ),
        (
            prepared.capsule,
            "_InitialScreeningResearchContextCapsule(<redacted>)",
        ),
        (publication, "_InitialScreeningResearchContextPublication(<redacted>)"),
        (prepared, "_InitialScreeningResearchContextInputs(<redacted>)"),
    )
    token = "PATH_OR_BODY_0xDEADBEEF"
    for value, expected in values:
        class_value = type(value)
        original_name = class_value.__name__
        class_value.__name__ = token
        try:
            assert repr(value) == expected
            assert str(value) == expected
            assert token not in repr(value)
            with pytest.raises(TypeError):
                _validate_capsule_dependencies()
        finally:
            class_value.__name__ = original_name


@pytest.mark.parametrize(
    ("marker_index", "replacement"),
    [
        (0, None),
        (1, object()),
        (2, _InitialScreeningProviderPolicyRequest()),
    ],
)
def test_opt_in_requires_all_three_exact_markers(
    marker_index: int,
    replacement: Any,
) -> None:
    markers = list(_markers())
    markers[marker_index] = replacement
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare_initial_screening_research_context(
            request,
            *markers,
            _problem_inputs(),
            research_input=None,
            research_history=(),
        )
    _fixed_error(caught.value)


@pytest.mark.parametrize(
    ("legacy_input", "legacy_history"),
    [
        ({"current_question": "legacy", "observations": []}, ()),
        (None, []),
        (None, ({},)),
    ],
)
def test_opt_in_rejects_dual_legacy_research_authority(
    legacy_input: Any,
    legacy_history: Any,
) -> None:
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare_initial_screening_research_context(
            request,
            *_markers(),
            _problem_inputs(),
            research_input=legacy_input,
            research_history=legacy_history,
        )
    _fixed_error(caught.value)


def test_phase_a_rejects_primitive_subclass_without_equality_hook() -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("phase A must reject before equality")

        def __ne__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("phase A must reject before equality")

    request = _InitialScreeningResearchContextRequest(
        research_input={
            "current_question": EvilStr("unsafe subclass"),
            "observations": [],
        },
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_phase_a_rejects_nested_tuple_before_provider_factory_call() -> None:
    research_input = _research_input()
    research_input["observations"][0]["claim_context"]["unsafe"] = ()
    factory_calls = 0
    factory_code = CvrpAdapter.prior_research_observation_provider.__code__

    def profile(frame: Any, event: str, _argument: Any) -> None:
        nonlocal factory_calls
        if event == "call" and frame.f_code is factory_code:
            factory_calls += 1

    sys.setprofile(profile)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as caught:
            _prepare(
                _InitialScreeningResearchContextRequest(
                    research_input=research_input,
                    loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
                )
            )
    finally:
        sys.setprofile(None)
    _fixed_error(caught.value)
    assert factory_calls == 0


def test_phase_a_rejects_observation_65_without_touching_it() -> None:
    calls = 0

    class Bomb:
        def __iter__(self) -> Any:
            nonlocal calls
            calls += 1
            raise AssertionError("observation 65 must not be traversed")

        def __eq__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("observation 65 must not be compared")

    research_input = _research_input()
    observation = research_input["observations"][0]
    research_input["observations"] = [deepcopy(observation) for _ in range(64)] + [
        Bomb()
    ]

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(
            _InitialScreeningResearchContextRequest(
                research_input=research_input,
                loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
            )
        )
    _fixed_error(caught.value)
    assert calls == 0


def test_phase_a_stops_oversized_history_before_any_normalizer_call() -> None:
    normalizer_calls = 0
    normalizer_code = composition_module._NORMALIZE_RESEARCH_HISTORY_RECORD.__code__
    large_record = {"blob": "x" * 900_000}
    records = (large_record,) * 80

    def profile(frame: Any, event: str, _argument: Any) -> None:
        nonlocal normalizer_calls
        if event == "call" and frame.f_code is normalizer_code:
            normalizer_calls += 1

    sys.setprofile(profile)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as caught:
            _prepare(
                _InitialScreeningResearchContextRequest(
                    research_input=None,
                    loaded_history=_InitialScreeningLoadedHistoryAvailable(
                        records=records
                    ),
                )
            )
    finally:
        sys.setprofile(None)
    _fixed_error(caught.value)
    assert normalizer_calls == 0


def test_fresh_import_never_calls_rebound_schema_dependency_validator() -> None:
    script = """
from scion.core import initial_screening_research_context as schema

calls = 0
def bomb():
    global calls
    calls += 1
    raise AssertionError("pre-import replacement must not run")

schema._validate_dependency_anchors = bomb
from scion.core.initial_screening_research_context_composition_anchors import (
    _validate_composition_external_dependencies,
)
try:
    _validate_composition_external_dependencies()
except TypeError:
    pass
else:
    raise AssertionError("replacement must be rejected")
assert calls == 0
"""
    subprocess.run([sys.executable, "-c", script], check=True)


@pytest.mark.parametrize(
    ("local_name", "module_name"),
    [
        (
            "_RESOLVE_PRIOR_RESEARCH_PROVIDER",
            "resolve_prior_research_observation_provider",
        ),
        (
            "_PROJECT_PRIOR_RESEARCH_OBSERVATION",
            "project_prior_research_observation",
        ),
    ],
)
def test_projection_helper_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
    local_name: str,
    module_name: str,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("replacement must never run")

    monkeypatch.setattr(composition_module, local_name, replacement)
    monkeypatch.setattr(
        composition_module.anchors_module.problem_providers_module,
        module_name,
        replacement,
    )
    request = _InitialScreeningResearchContextRequest(
        research_input=_research_input(),
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


@pytest.mark.parametrize("local_name", ["_phase_a_request_key", "type"])
def test_local_helper_or_builtin_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
    local_name: str,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("replacement must not run")

    monkeypatch.setattr(composition_module, local_name, replacement, raising=False)
    request = _InitialScreeningResearchContextRequest(
        research_input=_research_input(),
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_cvrp_projector_helper_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("replacement must not run")

    monkeypatch.setattr(
        composition_module.anchors_module.cvrp_projection_module,
        "_project_observation",
        replacement,
    )
    request = _InitialScreeningResearchContextRequest(
        research_input=_research_input(),
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_missing_local_alias_does_not_trigger_module_attr_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fallback(_name: str) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("module fallback must not run")

    monkeypatch.setattr(composition_module, "__getattr__", fallback, raising=False)
    monkeypatch.delattr(composition_module, "_REQUEST_TYPE")
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_error_alias_replacement_uses_fixed_import_time_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("mutant error token must not be compared")

    class ReplacementError(RuntimeError):
        def __init__(self, *_args: Any) -> None:
            nonlocal calls
            calls += 1
            raise AssertionError("mutant error class must not be constructed")

    monkeypatch.setattr(composition_module, "_ERROR", EvilStr("PATH_BODY_0xBAD"))
    monkeypatch.setattr(composition_module, "_RESEARCH_CONTEXT_ERROR", ReplacementError)
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_composition_anchor_module_name_is_shape_checked_before_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("module name must be shape-checked first")

        def __ne__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("module name must be shape-checked first")

    monkeypatch.setattr(
        composition_module.anchors_module,
        "__name__",
        EvilStr("scion.mutant.PATH_BODY_0xBAD"),
    )
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_capsule_runtime_module_name_is_shape_checked_before_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("module name must be shape-checked first")

        def __ne__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("module name must be shape-checked first")

    prepared = _prepare(
        _InitialScreeningResearchContextRequest(
            research_input=None,
            loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
        )
    )
    monkeypatch.setattr(
        capsule_runtime_module.capsule_module,
        "__name__",
        EvilStr("scion.mutant.PATH_BODY_0xBAD"),
    )
    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _research_context_capsule_h_fields(prepared.capsule)
    _fixed_error(caught.value)
    assert calls == 0


@pytest.mark.parametrize(
    "class_value",
    [CvrpAdapter, CvrpPriorResearchObservationProvider],
)
def test_cvrp_class_metadata_subclass_is_rejected_before_equality(
    class_value: type[Any],
) -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("class metadata must be shape-checked first")

        def __ne__(self, _other: object) -> bool:
            nonlocal calls
            calls += 1
            raise AssertionError("class metadata must be shape-checked first")

    inputs = _problem_inputs()
    original_name = class_value.__name__
    class_value.__name__ = EvilStr("PATH_BODY_0xBAD")
    request = _InitialScreeningResearchContextRequest(
        research_input=_research_input(),
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as caught:
            _prepare(request, problem_inputs=inputs)
    finally:
        class_value.__name__ = original_name
    _fixed_error(caught.value)
    assert calls == 0


def test_adapter_projection_descriptor_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _InitialScreeningResearchContextRequest(
        research_input=_research_input(),
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    calls = 0

    def replacement(_self: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("replacement factory must not run")

    monkeypatch.setattr(
        CvrpAdapter,
        "prior_research_observation_provider",
        replacement,
    )

    with pytest.raises(_InitialScreeningResearchContextError) as caught:
        _prepare(request)
    _fixed_error(caught.value)
    assert calls == 0


def test_caller_request_mutation_during_projection_is_detected() -> None:
    research_input = _research_input()
    request = _InitialScreeningResearchContextRequest(
        research_input=research_input,
        loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
    )
    project_code = (
        CvrpPriorResearchObservationProvider.project_prior_research_observation.__code__
    )
    mutated = False

    def profile(frame: Any, event: str, _argument: Any) -> None:
        nonlocal mutated
        if not mutated and frame.f_code is project_code and event == "return":
            research_input["current_question"] = "mutated during projection"
            mutated = True

    sys.setprofile(profile)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as caught:
            _prepare(request)
    finally:
        sys.setprofile(None)
    _fixed_error(caught.value)
    assert mutated is True


def test_none_request_is_default_off_without_touching_other_arguments() -> None:
    bomb = object()
    assert (
        _prepare_initial_screening_research_context(
            None,
            bomb,
            bomb,
            bomb,
            bomb,
            research_input=bomb,
            research_history=bomb,
        )
        is None
    )


def test_fresh_import_rejects_unshaped_aliases_without_running_hooks() -> None:
    prefix = """
calls = 0
class Bomb:
    @property
    def __dict__(self):
        global calls
        calls += 1
        raise AssertionError("hook must not run")
def fallback(_name):
    global calls
    calls += 1
    raise AssertionError("fallback must not run")
"""
    cases = (
        (
            "from scion.core import initial_screening_research_context as source\nsource.__getattr__=fallback\ndel source._MAX_JSON_DEPTH",
            "scion.core.initial_screening_research_context_capsule",
        ),
        (
            "from scion.core import initial_screening_research_context as source\nsource.json=Bomb()",
            "scion.core.initial_screening_research_context_composition_anchors",
        ),
        (
            "from scion.problems.cvrp import prior_research_observation as source\nsource.math=Bomb()",
            "scion.core.initial_screening_research_context_composition_anchors",
        ),
        (
            "from scion.problems.cvrp import adapter as source\nsource.CvrpAdapter=Bomb()",
            "scion.core.initial_screening_research_context_composition_anchors",
        ),
        (
            "from scion.problems.cvrp import prior_research_observation as source\nsource.CvrpPriorResearchObservationProvider=Bomb()",
            "scion.core.initial_screening_research_context_composition_anchors",
        ),
    )
    suffix = """
try:
    __import__(target)
except (KeyError, TypeError):
    pass
else:
    raise AssertionError("unshaped alias accepted")
assert calls == 0
"""
    for setup, target in cases:
        subprocess.run(
            [sys.executable, "-c", prefix + setup + f"\ntarget={target!r}\n" + suffix],
            check=True,
        )


@pytest.mark.parametrize("mode", ["input", "history"])
def test_phase_a_progressively_stops_before_copying_oversized_tree(mode: str) -> None:
    research_input: Any = None
    records: tuple[dict[str, Any], ...] = ()
    upper_bound = 550_000
    if mode == "input":
        research_input = {
            "current_question": "bounded",
            "observations": [{"blob": [0] * 200_000}],
        }
        upper_bound = 150_000
    else:
        records = ({"blob": [0] * 700_000},)
    freeze_calls = normalizer_calls = 0
    freeze_code = composition_module._phase_a_freeze_json.__code__
    normalizer_codes = {
        composition_module._NORMALIZE_RESEARCH_INPUT.__code__,
        composition_module._NORMALIZE_RESEARCH_HISTORY_RECORD.__code__,
    }

    def profile(frame: Any, event: str, _argument: Any) -> None:
        nonlocal freeze_calls, normalizer_calls
        if event == "call" and frame.f_code is freeze_code:
            freeze_calls += 1
        elif event == "call" and frame.f_code in normalizer_codes:
            normalizer_calls += 1

    sys.setprofile(profile)
    try:
        with pytest.raises(_InitialScreeningResearchContextError) as caught:
            _prepare(
                _InitialScreeningResearchContextRequest(
                    research_input=research_input,
                    loaded_history=_InitialScreeningLoadedHistoryAvailable(
                        records=records
                    ),
                )
            )
    finally:
        sys.setprofile(None)
    _fixed_error(caught.value)
    assert freeze_calls < upper_bound
    assert normalizer_calls == 0
