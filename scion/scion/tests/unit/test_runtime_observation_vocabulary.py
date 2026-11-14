from types import SimpleNamespace

from scion.protocol.experiment.runtime_observation import (
    _candidate_runtime_counter_template,
    _candidate_runtime_observation,
    _format_runtime_counter_summary,
    _merge_runtime_observation,
    _runtime_audit_summary,
)


def _result(runtime):
    return SimpleNamespace(output=SimpleNamespace(runtime=runtime))


def _spec():
    return {
        "research_surfaces": [{
            "name": "search",
            "evidence": {
                "runtime_field_roles": {
                    "activity": ["search.visits"],
                    "diagnostic": ["search.errors", "search.stop_reason"],
                    "protected_outcome": ["answer"],
                },
            },
        }],
    }


def test_no_implicit_algorithm_taxonomy_or_no_move_failure():
    assert _candidate_runtime_counter_template() == {}
    observation = _candidate_runtime_observation(_result({
        "operator_attempts": 5,
        "operator_accepted": 0,
        "operator_stop_reason": "done",
    }))
    assert observation == {
        "categories": {}, "counters": {}, "stop_reasons": {}, "first_failure": None,
    }


def test_declared_nested_counters_are_aggregated_without_objective_fields():
    kwargs = {"problem_spec": _spec(), "selected_surface": "search"}
    counters = _candidate_runtime_counter_template(**kwargs)
    categories, stops = {}, {}
    for visits in (2, 3):
        observation = _candidate_runtime_observation(_result({
            "search": {"visits": visits, "errors": 1, "stop_reason": "done"},
            "answer": 42,
            "operator_attempts": 99,
        }), **kwargs)
        _merge_runtime_observation(
            observation, categories=categories, counters=counters, stop_reasons=stops,
        )
    assert counters["search.visits"] == 5
    assert counters["search.errors"] == 2
    assert "answer" not in counters
    assert "operator_attempts" not in counters
    assert categories == {"search_error": 2}
    assert stops == {"done": 2}
    assert "search.visits:5" in _format_runtime_counter_summary(counters)
    assert "operator" not in _format_runtime_counter_summary(counters)


def test_raw_scalar_and_event_observations_have_no_namespace_allowlist():
    runtime = {
        "custom_fact": "full-tail",
        "operator_attempts": 0,
        "custom_events": [{"component": "custom", "detail": "x" * 3000}],
        "search": {"visits": 7},
    }
    summary = _runtime_audit_summary(
        _result(runtime), problem_spec=_spec(), selected_surface="search",
    )
    assert summary["custom_fact"] == "full-tail"
    assert summary["operator_attempts"] == 0
    assert summary["custom_events"] == runtime["custom_events"]
    assert summary["search.visits"] == 7


def test_counter_summary_preserves_declared_zero_values():
    assert _format_runtime_counter_summary({"search.visits": 0}) == (
        " candidate_runtime_counters=search.visits:0"
    )
