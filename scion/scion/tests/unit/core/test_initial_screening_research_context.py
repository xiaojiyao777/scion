from __future__ import annotations

import json
from types import ModuleType
from typing import Any

import pytest

from scion.core import initial_screening_research_context as research_context_module
from scion.core.initial_screening_problem_spec import (
    _LIMITATIONS as _PROBLEM_LIMITATIONS,
)
from scion.core.initial_screening_research_context import (
    _ERROR,
    _FILENAME,
    _HISTORY_UNAVAILABLE_REASON,
    _LIMITATIONS,
    _MAX_BYTES,
    _MAX_JSON_DEPTH,
    _MAX_LOADED_HISTORY_RECORDS,
    _SCHEMA_VERSION,
    _SCOPE,
    _canonical_research_context_payload,
    _InitialScreeningLoadedHistoryAvailable,
    _InitialScreeningLoadedHistoryUnavailable,
    _InitialScreeningResearchContextRequest,
)


def _available_input() -> dict[str, Any]:
    return {
        "availability": "available",
        "normalized_input": {
            "current_question": "Which bounded mechanism should be tested next?",
            "observations": [{"ordinal": 1, "score": -0.0}],
        },
        "provider_projection": {
            "research_question": {
                "current_question": "Which bounded mechanism should be tested next?"
            },
            "prior_research_observations": [
                {"finding": "candidate did not activate", "score": -0.0}
            ],
        },
    }


def _large_history_record() -> dict[str, object]:
    return {
        "schema_version": "scion.research_history.step.v1",
        "problem_id": "cvrp",
        "hypothesis": {
            "text": "x" * 900_000,
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
        },
        "protocol": None,
        "decision": None,
    }


def test_research_context_request_and_history_union_are_frozen_and_redacted() -> None:
    available = _InitialScreeningLoadedHistoryAvailable(records=())
    unavailable = _InitialScreeningLoadedHistoryUnavailable()
    request = _InitialScreeningResearchContextRequest(
        research_input=None,
        loaded_history=available,
    )

    assert vars(available) == {"records": ()}
    assert vars(unavailable) == {}
    assert vars(request) == {"research_input": None, "loaded_history": available}
    expected_representations = (
        "_InitialScreeningLoadedHistoryAvailable(<redacted>)",
        "_InitialScreeningLoadedHistoryUnavailable(<redacted>)",
        "_InitialScreeningResearchContextRequest(<redacted>)",
    )
    for value, expected in zip(
        (available, unavailable, request), expected_representations, strict=True
    ):
        assert repr(value) == expected
        assert str(value) == repr(value)
        assert "0x" not in repr(value)
    field_name = "research_input"
    with pytest.raises(AttributeError):
        setattr(request, field_name, {})


def test_redacted_repr_does_not_resolve_schema_builtin_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    unavailable = _InitialScreeningLoadedHistoryUnavailable()

    def replacement_type(_value: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("redacted repr must use its captured type")

    monkeypatch.setattr(
        research_context_module, "type", replacement_type, raising=False
    )
    assert repr(unavailable) == "_InitialScreeningLoadedHistoryUnavailable(<redacted>)"
    assert str(unavailable) == repr(unavailable)
    assert calls == 0


@pytest.mark.parametrize(
    ("carrier_type", "carrier", "expected"),
    (
        (
            _InitialScreeningLoadedHistoryAvailable,
            _InitialScreeningLoadedHistoryAvailable(records=()),
            "_InitialScreeningLoadedHistoryAvailable(<redacted>)",
        ),
        (
            _InitialScreeningLoadedHistoryUnavailable,
            _InitialScreeningLoadedHistoryUnavailable(),
            "_InitialScreeningLoadedHistoryUnavailable(<redacted>)",
        ),
        (
            _InitialScreeningResearchContextRequest,
            _InitialScreeningResearchContextRequest(
                research_input=None,
                loaded_history=_InitialScreeningLoadedHistoryUnavailable(),
            ),
            "_InitialScreeningResearchContextRequest(<redacted>)",
        ),
    ),
)
def test_redacted_repr_does_not_depend_on_mutable_type_names(
    carrier_type: type[Any],
    carrier: Any,
    expected: str,
) -> None:
    original_name = carrier_type.__name__
    original_qualname = carrier_type.__qualname__
    original_module = carrier_type.__module__
    carrier_type.__name__ = "PATH_OR_BODY_0xfeed"
    carrier_type.__qualname__ = "QUALNAME_PATH_OR_BODY_0xfeed"
    carrier_type.__module__ = "module.path_or_body_0xfeed"
    try:
        assert repr(carrier) == expected
        assert str(carrier) == expected
        assert "PATH_OR_BODY" not in repr(carrier)
        assert "0x" not in repr(carrier)
    finally:
        carrier_type.__name__ = original_name
        carrier_type.__qualname__ = original_qualname
        carrier_type.__module__ = original_module


@pytest.mark.parametrize(
    ("research_input", "loaded_history"),
    [
        (
            {"availability": "absent"},
            {"availability": "available", "records": []},
        ),
        (
            _available_input(),
            {"availability": "available", "records": []},
        ),
        (
            _available_input(),
            {
                "availability": "unavailable",
                "reason": _HISTORY_UNAVAILABLE_REASON,
            },
        ),
    ],
)
def test_research_context_payload_is_exact_canonical_schema(
    research_input: dict[str, object],
    loaded_history: dict[str, object],
) -> None:
    raw = _canonical_research_context_payload(
        problem_id="cvrp",
        research_input=research_input,
        loaded_history=loaded_history,
    )
    payload = json.loads(raw)

    assert set(payload) == {
        "schema_version",
        "scope",
        "limitations",
        "problem_id",
        "research_input",
        "loaded_history",
    }
    assert payload["schema_version"] == _SCHEMA_VERSION
    assert payload["scope"] == _SCOPE
    assert tuple(payload["limitations"]) == _LIMITATIONS == _PROBLEM_LIMITATIONS
    assert payload["problem_id"] == "cvrp"
    assert len(raw) <= _MAX_BYTES == 64 << 20
    assert _MAX_JSON_DEPTH == 27
    assert _FILENAME == "initial_screening_research_context.json"
    assert _ERROR == "INITIAL_SCREENING_RESEARCH_CONTEXT_UNAVAILABLE"
    assert raw == (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def test_research_context_unions_and_projection_are_exact() -> None:
    available = _available_input()
    available["extra"] = True
    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input=available,
            loaded_history={"availability": "available", "records": []},
        )

    mismatch = _available_input()
    mismatch["provider_projection"]["research_question"]["current_question"] = (
        "a different question"
    )
    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input=mismatch,
            loaded_history={"availability": "available", "records": []},
        )

    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={
                "availability": "unavailable",
                "reason": "a raw path or exception must not be persisted",
            },
        )


def test_research_context_float_join_preserves_signed_zero() -> None:
    value = _available_input()
    value["provider_projection"]["prior_research_observations"][0]["score"] = 0.0

    raw = _canonical_research_context_payload(
        problem_id="cvrp",
        research_input=value,
        loaded_history={"availability": "available", "records": []},
    )

    assert b'"score":0.0' in raw
    assert b'"score":-0.0' in raw


def test_loaded_history_count_and_exact_container_fail_before_record_decode() -> None:
    calls = 0

    class Record(dict):
        def __iter__(self):
            nonlocal calls
            calls += 1
            raise AssertionError("record must not be inspected")

    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={
                "availability": "available",
                "records": [Record()] * (_MAX_LOADED_HISTORY_RECORDS + 1),
            },
        )
    assert calls == 0

    class Records(list):
        pass

    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": Records()},
        )
    assert calls == 0


@pytest.mark.parametrize(
    "name",
    ["_NORMALIZE_RESEARCH_INPUT", "_NORMALIZE_RESEARCH_HISTORY_RECORD"],
)
def test_research_context_normalizer_dependency_drift_fails_before_use(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    calls = 0

    def identity(value: object, *_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return value

    monkeypatch.setattr(research_context_module, name, identity)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


@pytest.mark.parametrize(
    ("local_name", "module", "source_name"),
    [
        (
            "_NORMALIZE_RESEARCH_INPUT",
            research_context_module.research_input_module,
            "normalize_research_input",
        ),
        (
            "_NORMALIZE_RESEARCH_HISTORY_RECORD",
            research_context_module.research_history_module,
            "normalize_research_history_record",
        ),
    ],
)
def test_coordinated_normalizer_swap_cannot_replace_independent_anchor(
    monkeypatch: pytest.MonkeyPatch,
    local_name: str,
    module: object,
    source_name: str,
) -> None:
    calls = 0

    def identity(value: object, *_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return value

    monkeypatch.setattr(research_context_module, local_name, identity)
    monkeypatch.setattr(module, source_name, identity)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_history_record_cap_subclass_is_rejected_without_equality_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class SideEffectInt(int):
        def __eq__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__eq__(other)

        def __ne__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__ne__(other)

    monkeypatch.setattr(
        research_context_module.research_history_module,
        "MAX_RESEARCH_HISTORY_RECORDS",
        SideEffectInt(_MAX_LOADED_HISTORY_RECORDS),
    )
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


@pytest.mark.parametrize("name", ["_MAX_BYTES", "_MAX_JSON_DEPTH"])
def test_schema_integer_literal_subclass_is_rejected_without_hook(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    calls = 0

    class SideEffectInt(int):
        def __eq__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__eq__(other)

        def __ne__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__ne__(other)

    monkeypatch.setattr(
        research_context_module,
        name,
        SideEffectInt(getattr(research_context_module, name)),
    )
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_schema_limitations_subclass_is_rejected_without_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class EvilTuple(tuple):
        def __iter__(self):
            nonlocal calls
            calls += 1
            raise AssertionError("limitations must not be iterated")

    monkeypatch.setattr(
        research_context_module, "_LIMITATIONS", EvilTuple(_LIMITATIONS)
    )
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (research_context_module.research_input_module, "is_sensitive_research_key"),
        (
            research_context_module.research_history_module,
            "_validate_record_relationships",
        ),
        (
            research_context_module.research_context_anchors.history_projection_module,
            "_canonical_json",
        ),
    ],
)
def test_transitive_schema_dependency_rebind_fails_before_use(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    name: str,
) -> None:
    calls = 0

    def permissive(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(module, name, permissive)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (research_context_module.research_input_module, "len"),
        (research_context_module.research_history_module, "enumerate"),
        (
            research_context_module.research_context_anchors.history_projection_module,
            "isinstance",
        ),
        (research_context_module.research_context_anchors.paths_module, "any"),
    ],
)
def test_dependency_builtin_shadow_is_rejected_before_call(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    name: str,
) -> None:
    calls = 0

    def replacement(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(module, name, replacement, raising=False)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_dynamic_history_projection_module_binding_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchors = research_context_module.research_context_anchors
    name = anchors.history_projection_module.__name__
    replacement = ModuleType(name)
    monkeypatch.setitem(anchors.sys.modules, name, replacement)

    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )


def test_union_discriminants_are_exact_before_equality_hooks() -> None:
    calls = 0

    class EvilStr(str):
        def __eq__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__eq__(other)

        def __ne__(self, other: object) -> bool:
            nonlocal calls
            calls += 1
            return super().__ne__(other)

    cases = (
        (
            {"availability": EvilStr("absent")},
            {"availability": "available", "records": []},
        ),
        (
            {"availability": "absent"},
            {"availability": EvilStr("available"), "records": []},
        ),
        (
            {"availability": "absent"},
            {
                "availability": "unavailable",
                "reason": EvilStr(_HISTORY_UNAVAILABLE_REASON),
            },
        ),
    )
    for research_input, loaded_history in cases:
        with pytest.raises(TypeError):
            _canonical_research_context_payload(
                problem_id="cvrp",
                research_input=research_input,
                loaded_history=loaded_history,
            )
    assert calls == 0


def test_observation_count_fails_before_the_extra_item_is_walked() -> None:
    calls = 0

    class BombTuple(tuple):
        def __iter__(self):
            nonlocal calls
            calls += 1
            raise AssertionError("the sixty-fifth observation must stay unread")

    too_many: list[object] = [{}] * 64 + [BombTuple()]
    raw_input = _available_input()
    raw_input["normalized_input"]["observations"] = too_many
    raw_input["provider_projection"]["prior_research_observations"] = []
    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input=raw_input,
            loaded_history={"availability": "available", "records": []},
        )

    projection = _available_input()
    projection["normalized_input"]["observations"] = []
    projection["provider_projection"]["prior_research_observations"] = too_many
    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input=projection,
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_loaded_history_aggregate_stops_before_later_record_decode() -> None:
    records: list[object] = [_large_history_record()] * 80
    records.append(("this invalid later record must remain unread",))

    with pytest.raises(ValueError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": records},
        )


def test_schema_json_alias_replacement_fails_before_dumps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    replacement = ModuleType("replacement_json")

    def dumps(*_args: object, **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return "{}"

    vars(replacement)["dumps"] = dumps
    monkeypatch.setattr(research_context_module, "json", replacement)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_schema_helper_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: object, **_kwargs: object) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"availability": "absent"}

    monkeypatch.setattr(
        research_context_module,
        "_normalize_research_input_union",
        replacement,
    )
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={
                "availability": "available",
                "normalized_input": {
                    "current_question": "bounded question",
                    "observations": [{"api_key": "must not be accepted"}],
                },
                "provider_projection": {
                    "research_question": {"current_question": "bounded question"},
                    "prior_research_observations": [],
                },
            },
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_anchor_module_vars_replacement_cannot_mask_dependency_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    anchors = research_context_module.research_context_anchors
    original = research_context_module.research_input_module.is_sensitive_research_key

    def permissive(_key: object) -> bool:
        nonlocal calls
        calls += 1
        return False

    def masked_vars(value: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        storage = dict(vars(value))
        if value is research_context_module.research_input_module:
            storage["is_sensitive_research_key"] = original
        return storage

    monkeypatch.setattr(
        research_context_module.research_input_module,
        "is_sensitive_research_key",
        permissive,
    )
    monkeypatch.setattr(anchors, "vars", masked_vars, raising=False)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_schema_builtin_shadow_fails_before_record_count_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement_len(value: Any) -> int:
        nonlocal calls
        calls += 1
        return 0 if type(value) is list and len(value) == 257 else len(value)

    monkeypatch.setattr(research_context_module, "len", replacement_len, raising=False)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": [{}] * 257},
        )
    assert calls == 0


def test_dependency_module_attribute_fallback_is_not_consulted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    anchors = research_context_module.research_context_anchors
    name = "_validate_research_context_schema_dependencies"
    original = vars(anchors)[name]

    def fallback(attribute: str) -> object:
        nonlocal calls
        calls += 1
        if attribute == name:
            return original
        raise AttributeError(attribute)

    monkeypatch.delattr(anchors, name)
    monkeypatch.setattr(anchors, "__getattr__", fallback, raising=False)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


@pytest.mark.parametrize(
    ("target", "name"),
    [
        (research_context_module._JSON_ENCODER, "encode"),
        (research_context_module.json_encoder_module, "_make_iterencode"),
        (research_context_module.json_encoder_module, "sorted"),
    ],
)
def test_json_encoder_surface_replacement_fails_before_call(
    monkeypatch: pytest.MonkeyPatch,
    target: object,
    name: str,
) -> None:
    calls = 0

    def replacement(*_args: object, **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return "{}"

    monkeypatch.setattr(target, name, replacement, raising=False)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_json_encoder_class_binding_replacement_fails_before_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class ReplacementEncoder:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            nonlocal calls
            calls += 1

        def encode(self, _value: object) -> str:
            nonlocal calls
            calls += 1
            return "{}"

    monkeypatch.setattr(research_context_module.json, "JSONEncoder", ReplacementEncoder)
    with pytest.raises(TypeError):
        _canonical_research_context_payload(
            problem_id="cvrp",
            research_input={"availability": "absent"},
            loaded_history={"availability": "available", "records": []},
        )
    assert calls == 0


def test_json_default_encoder_is_not_used_by_canonical_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class DefaultEncoderBomb:
        def encode(self, _value: object) -> str:
            nonlocal calls
            calls += 1
            raise AssertionError("canonical path must construct its captured encoder")

    monkeypatch.setattr(
        research_context_module.json,
        "_default_encoder",
        DefaultEncoderBomb(),
    )
    raw = _canonical_research_context_payload(
        problem_id="cvrp",
        research_input={"availability": "absent"},
        loaded_history={"availability": "available", "records": []},
    )
    assert json.loads(raw)["problem_id"] == "cvrp"
    assert calls == 0
