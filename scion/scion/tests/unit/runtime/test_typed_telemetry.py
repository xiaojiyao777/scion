from __future__ import annotations

import pytest

from scion.runtime.telemetry_events import (
    TELEMETRY_EVENT_LANES,
    TypedTelemetryEvent,
    append_typed_telemetry_event,
    normalize_typed_telemetry_event,
    summarize_typed_telemetry_events,
)


def _event(lane: str) -> TypedTelemetryEvent:
    refs = {
        "before_ref": "solution:before" if lane == "direct_effect" else None,
        "after_ref": "solution:after" if lane == "direct_effect" else None,
        "missing_refs": ()
        if lane == "direct_effect"
        else ("before_ref", "after_ref"),
    }
    return TypedTelemetryEvent(
        lane=lane,
        mechanism_id="mechanism_x",
        attribution_scope="mechanism_boundary",
        attribution_confidence=1.0 if lane == "direct_effect" else 0.5,
        **refs,
    )


def test_typed_telemetry_keeps_all_four_lanes_separate() -> None:
    events = [_event(lane) for lane in TELEMETRY_EVENT_LANES]

    summary = summarize_typed_telemetry_events(events)

    assert summary["event_count"] == 4
    assert summary["lane_counts"] == {
        "attempt": 1,
        "state_transition": 1,
        "direct_effect": 1,
        "associated_outcome": 1,
    }
    assert summary["mechanism_lanes"]["mechanism_x"] == summary["lane_counts"]


def test_direct_effect_requires_supported_before_after_boundary() -> None:
    with pytest.raises(ValueError, match="direct_effect requires"):
        TypedTelemetryEvent(
            lane="direct_effect",
            mechanism_id="mechanism_x",
            attribution_scope="mechanism_boundary",
            attribution_confidence=0.0,
            before_ref=None,
            after_ref=None,
            missing_refs=("before_ref", "after_ref"),
        )


def test_every_absent_ref_must_be_explicitly_declared() -> None:
    with pytest.raises(ValueError, match="explicitly missing"):
        normalize_typed_telemetry_event(
            {
                "lane": "attempt",
                "mechanism_id": "mechanism_x",
                "attribution_scope": "mechanism_invocation",
                "attribution_confidence": 1.0,
                "before_ref": None,
                "after_ref": None,
                "missing_refs": [],
            }
        )


def test_typed_event_rejects_legacy_accepted_or_arbitrary_payload_fields() -> None:
    raw = _event("state_transition").as_dict()
    raw["accepted"] = 1

    with pytest.raises(ValueError, match="unknown fields: accepted"):
        normalize_typed_telemetry_event(raw)


def test_append_does_not_invent_legacy_acceptance_and_does_not_drop_events() -> None:
    runtime: dict[str, object] = {"solver_algorithm_accepted_moves": 7}

    for _ in range(257):
        append_typed_telemetry_event(runtime, _event("state_transition"))

    assert runtime["solver_algorithm_accepted_moves"] == 7
    events = runtime["typed_telemetry_events"]
    assert isinstance(events, list)
    assert len(events) == 257
    summary = runtime["typed_telemetry_summary"]
    assert isinstance(summary, dict)
    assert summary["lane_counts"]["state_transition"] == 257
    assert summary["lane_counts"]["direct_effect"] == 0
