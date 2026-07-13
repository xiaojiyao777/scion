"""Typed runtime telemetry events with explicit attribution boundaries.

This module owns only problem-agnostic event semantics.  Problem packages own
the interpretation of their legacy counters and the references used to prove
direct effects.  Typed events are deliberately not projected into legacy
``accepted`` counters or DecisionFeatures.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

TYPED_TELEMETRY_SCHEMA = "scion.typed_telemetry_event.v1"
TYPED_TELEMETRY_EVENTS_KEY = "typed_telemetry_events"
TYPED_TELEMETRY_SUMMARY_KEY = "typed_telemetry_summary"

TELEMETRY_EVENT_LANES = (
    "attempt",
    "state_transition",
    "direct_effect",
    "associated_outcome",
)
_TELEMETRY_EVENT_LANE_SET = frozenset(TELEMETRY_EVENT_LANES)
_REF_FIELDS = ("before_ref", "after_ref")
_EVENT_FIELDS = frozenset(
    {
        "schema",
        "lane",
        "mechanism_id",
        "attribution_scope",
        "attribution_confidence",
        "before_ref",
        "after_ref",
        "missing_refs",
        "occurrences",
        "evidence_ref",
    }
)


@dataclass(frozen=True)
class TypedTelemetryEvent:
    """A single normalized event in one causal-attribution lane.

    Every event must either name each before/after reference or explicitly
    list the absent reference in ``missing_refs``.  A direct effect is
    stronger: both references and positive attribution confidence are
    mandatory.
    """

    lane: str
    mechanism_id: str
    attribution_scope: str
    attribution_confidence: float
    before_ref: str | None
    after_ref: str | None
    missing_refs: tuple[str, ...]
    occurrences: int = 1
    evidence_ref: str | None = None
    schema: str = TYPED_TELEMETRY_SCHEMA

    def __post_init__(self) -> None:
        if str(self.schema or "").strip() != TYPED_TELEMETRY_SCHEMA:
            raise ValueError(f"unsupported typed telemetry schema: {self.schema!r}")
        lane = str(self.lane or "").strip()
        mechanism_id = str(self.mechanism_id or "").strip()
        scope = str(self.attribution_scope or "").strip()
        if lane not in _TELEMETRY_EVENT_LANE_SET:
            raise ValueError(
                "typed telemetry lane must be one of "
                f"{TELEMETRY_EVENT_LANES}, got {self.lane!r}"
            )
        if not mechanism_id:
            raise ValueError("typed telemetry mechanism_id must be non-empty")
        if not scope:
            raise ValueError("typed telemetry attribution_scope must be non-empty")
        if isinstance(self.attribution_confidence, bool):
            raise ValueError("typed telemetry attribution_confidence must be numeric")
        try:
            confidence = float(self.attribution_confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "typed telemetry attribution_confidence must be numeric"
            ) from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "typed telemetry attribution_confidence must be within [0, 1]"
            )
        if (
            isinstance(self.occurrences, bool)
            or not isinstance(self.occurrences, int)
            or self.occurrences <= 0
        ):
            raise ValueError("typed telemetry occurrences must be a positive integer")
        normalized_refs = {
            name: _normalize_ref(getattr(self, name), field_name=name)
            for name in _REF_FIELDS
        }
        missing_refs = tuple(
            dict.fromkeys(str(item).strip() for item in self.missing_refs)
        )
        invalid_missing = sorted(set(missing_refs) - set(_REF_FIELDS))
        if invalid_missing:
            raise ValueError(
                "typed telemetry missing_refs contains unknown fields: "
                + ", ".join(invalid_missing)
            )
        expected_missing = {
            name for name, value in normalized_refs.items() if value is None
        }
        if set(missing_refs) != expected_missing:
            raise ValueError(
                "typed telemetry refs must be present or explicitly missing; "
                f"expected missing_refs={sorted(expected_missing)!r}"
            )
        if lane == "direct_effect" and (
            expected_missing or confidence <= 0.0
        ):
            raise ValueError(
                "direct_effect requires before_ref, after_ref, and positive "
                "attribution_confidence"
            )

        object.__setattr__(self, "lane", lane)
        object.__setattr__(self, "mechanism_id", mechanism_id)
        object.__setattr__(self, "attribution_scope", scope)
        object.__setattr__(self, "attribution_confidence", confidence)
        object.__setattr__(self, "before_ref", normalized_refs["before_ref"])
        object.__setattr__(self, "after_ref", normalized_refs["after_ref"])
        object.__setattr__(self, "missing_refs", missing_refs)
        object.__setattr__(
            self,
            "evidence_ref",
            _normalize_ref(self.evidence_ref, field_name="evidence_ref")
            if self.evidence_ref is not None
            else None,
        )
        object.__setattr__(self, "schema", TYPED_TELEMETRY_SCHEMA)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "lane": self.lane,
            "mechanism_id": self.mechanism_id,
            "attribution_scope": self.attribution_scope,
            "attribution_confidence": self.attribution_confidence,
            "before_ref": self.before_ref,
            "after_ref": self.after_ref,
            "missing_refs": list(self.missing_refs),
            "occurrences": self.occurrences,
            "evidence_ref": self.evidence_ref,
        }


def normalize_typed_telemetry_event(
    event: TypedTelemetryEvent | Mapping[str, Any],
) -> TypedTelemetryEvent:
    """Normalize and validate one typed telemetry event."""

    if isinstance(event, TypedTelemetryEvent):
        return event
    if not isinstance(event, Mapping):
        raise ValueError("typed telemetry event must be a mapping")
    unknown_fields = sorted(str(key) for key in event if key not in _EVENT_FIELDS)
    if unknown_fields:
        raise ValueError(
            "typed telemetry event contains unknown fields: "
            + ", ".join(unknown_fields)
        )
    schema = str(event.get("schema") or TYPED_TELEMETRY_SCHEMA).strip()
    if schema != TYPED_TELEMETRY_SCHEMA:
        raise ValueError(f"unsupported typed telemetry schema: {schema!r}")
    return TypedTelemetryEvent(
        lane=str(event.get("lane") or ""),
        mechanism_id=str(event.get("mechanism_id") or ""),
        attribution_scope=str(event.get("attribution_scope") or ""),
        attribution_confidence=event.get("attribution_confidence", 0.0),
        before_ref=event.get("before_ref"),
        after_ref=event.get("after_ref"),
        missing_refs=_normalize_missing_refs(event.get("missing_refs")),
        occurrences=event.get("occurrences", 1),
        evidence_ref=event.get("evidence_ref"),
    )


def append_typed_telemetry_event(
    runtime: MutableMapping[str, Any],
    event: TypedTelemetryEvent | Mapping[str, Any],
) -> TypedTelemetryEvent:
    """Append a typed event without mutating any legacy telemetry counters."""

    normalized = normalize_typed_telemetry_event(event)
    events = runtime.setdefault(TYPED_TELEMETRY_EVENTS_KEY, [])
    if not isinstance(events, list):
        raise ValueError(f"runtime.{TYPED_TELEMETRY_EVENTS_KEY} must be a list")
    events.append(normalized.as_dict())
    runtime[TYPED_TELEMETRY_SUMMARY_KEY] = summarize_typed_telemetry_events(events)
    return normalized


def summarize_typed_telemetry_events(
    events: Sequence[TypedTelemetryEvent | Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate lanes separately without inventing acceptance or causality."""

    lane_counts = {lane: 0 for lane in TELEMETRY_EVENT_LANES}
    mechanism_lanes: dict[str, dict[str, int]] = {}
    event_count = 0
    for raw_event in events:
        event = normalize_typed_telemetry_event(raw_event)
        event_count += 1
        lane_counts[event.lane] += event.occurrences
        mechanism_summary = mechanism_lanes.setdefault(
            event.mechanism_id,
            {lane: 0 for lane in TELEMETRY_EVENT_LANES},
        )
        mechanism_summary[event.lane] += event.occurrences
    return {
        "schema": "scion.typed_telemetry_summary.v1",
        "event_count": event_count,
        "lane_counts": lane_counts,
        "mechanism_lanes": {
            mechanism: dict(counts)
            for mechanism, counts in sorted(mechanism_lanes.items())
        },
    }


def _normalize_ref(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError(f"typed telemetry {field_name} must be non-empty when present")
    return text


def _normalize_missing_refs(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise ValueError("typed telemetry missing_refs must be a sequence")
    return tuple(str(item) for item in value)


__all__ = [
    "TELEMETRY_EVENT_LANES",
    "TYPED_TELEMETRY_EVENTS_KEY",
    "TYPED_TELEMETRY_SCHEMA",
    "TYPED_TELEMETRY_SUMMARY_KEY",
    "TypedTelemetryEvent",
    "append_typed_telemetry_event",
    "normalize_typed_telemetry_event",
    "summarize_typed_telemetry_events",
]
