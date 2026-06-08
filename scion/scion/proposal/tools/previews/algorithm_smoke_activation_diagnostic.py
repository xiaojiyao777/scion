"""Proposal-smoke activation diagnostics for algorithm smoke feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.previews.algorithm_smoke_feedback_text import (
    _compact_agent_text_list,
    _first_mapping,
    _mapping_or_none,
)
from scion.proposal.tools.surface import _drop_empty_items

PROPOSAL_ACTIVATION_DIAGNOSTIC_CODE = "proposal_activation_diagnostic"

OBSERVED_ACTIVATION = "observed_activation"
ACTIVATION_UNOBSERVED_CONDITIONAL = "activation_unobserved_conditional"
ACTIVATION_UNOBSERVED_WIRING_SUSPECT = "activation_unobserved_wiring_suspect"
EFFECT_MISSING_OBSERVED_ACTIVATION = "effect_missing_observed_activation"
TELEMETRY_FIELD_MISSING_OR_MISDECLARED = "telemetry_field_missing_or_misdeclared"

VALID_ACTIVE_WEAK_POSITIVE = "valid_active_weak_positive"
ACTIVE_NO_CASE_LEVEL_GATE = "active_no_case_level_gate"
ACTIVE_PAIR_WINS_BUT_CASE_FAIL = "active_pair_wins_but_case_fail"
INACTIVE_OR_WIRING_SUSPECT = "inactive_or_wiring_suspect"

_ACTIVATION_FAILURE_CODES = frozenset(
    {
        "TELEMETRY_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
    }
)
_STATIC_MISMATCH_CODES = frozenset(
    {
        "DECLARED_MECHANISM_ACTIVATION_MISSING",
    }
)
_EFFECT_FIELD_TOKENS = (
    "improvement",
    "best_delta",
    "delta",
    "objective",
    "record_move",
)


def _proposal_smoke_activation_diagnostic(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a compact proposal-smoke activation diagnostic when applicable."""
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    static = _static_activation_mismatch(telemetry_static)
    if static is not None:
        return static
    if telemetry_guard is None or bool(telemetry_guard.get("passed", True)):
        return None
    failure = _first_mapping(telemetry_guard.get("failures"))
    if failure is None:
        return None
    failure_code = str(
        failure.get("code") or telemetry_guard.get("failure_code") or ""
    ).strip()
    if failure_code not in _ACTIVATION_FAILURE_CODES:
        return None

    mechanism = str(
        failure.get("mechanism") or telemetry_guard.get("mechanism") or ""
    ).strip()
    field = str(failure.get("field") or telemetry_guard.get("field") or "").strip()
    diagnostic = _diagnostic_for_mechanism(telemetry_guard, mechanism)
    subtype = _activation_subtype(
        failure=failure,
        field=field,
        mechanism=mechanism,
        diagnostic=diagnostic,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        telemetry_static=telemetry_static,
    )
    return _diagnostic_payload(
        subtype=subtype,
        source="runtime_smoke.telemetry_guard",
        guard_failure_code=failure_code,
        mechanism=mechanism,
        category=str(failure.get("category") or telemetry_guard.get("category") or ""),
        field=field,
        counters=_issue_counters(failure),
        telemetry_guard=telemetry_guard,
        diagnostic=diagnostic,
    )


def _proposal_smoke_telemetry_diagnostics(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
    activation_diagnostic: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return stable proposal-smoke telemetry diagnoses for lifecycle feedback."""
    diagnostics: list[dict[str, Any]] = []
    if activation_diagnostic is None:
        activation_diagnostic = _proposal_smoke_activation_diagnostic(
            raw_payload,
            runtime_smoke=runtime_smoke,
            telemetry_guard=telemetry_guard,
        )
    if isinstance(activation_diagnostic, Mapping):
        diagnostics.append(_telemetry_diagnostic_public_payload(activation_diagnostic))

    guard = telemetry_guard if isinstance(telemetry_guard, Mapping) else {}
    for mechanism_diagnostic in _mechanism_diagnostic_items(guard):
        mechanism = str(mechanism_diagnostic.get("mechanism") or "").strip()
        activation = _status_block(mechanism_diagnostic, "activation")
        effect = _status_block(mechanism_diagnostic, "effect")
        activation_positive = _status_positive(activation)
        effect_status = _status_value(effect)
        if activation_positive:
            effect_issue = _effect_issue_for_mechanism(guard, mechanism)
            if effect_issue is not None or effect_status in {"missing", "zero"}:
                diagnostics.append(
                    _drop_empty_items(
                        {
                            "diagnostic_type": EFFECT_MISSING_OBSERVED_ACTIVATION,
                            "lifecycle_signal": _diagnostic_lifecycle_signal(
                                EFFECT_MISSING_OBSERVED_ACTIVATION
                            ),
                            "mechanism_id": mechanism,
                            "category": "effect",
                            "source": "runtime_smoke.telemetry_guard",
                            "activation_status": _status_value(activation)
                            or mechanism_diagnostic.get("activation_status"),
                            "effect_status": effect_status
                            or mechanism_diagnostic.get("effect_status"),
                            "field": (
                                str((effect_issue or {}).get("field") or "").strip()
                                or _first_field(effect)
                            ),
                            "counters": _counters_from_status_block(effect),
                            "diagnosis": (
                                "Declared mechanism activated in proposal smoke, "
                                "but no positive effect telemetry was observed."
                            ),
                            "screening_policy": (
                                "Allow formal screening when static/runtime checks "
                                "are otherwise clean; treat as weak signal, not a "
                                "plain win-rate failure."
                            ),
                        }
                    )
                )
            else:
                diagnostics.append(
                    _drop_empty_items(
                        {
                            "diagnostic_type": OBSERVED_ACTIVATION,
                            "lifecycle_signal": _diagnostic_lifecycle_signal(
                                OBSERVED_ACTIVATION
                            ),
                            "mechanism_id": mechanism,
                            "category": "activation",
                            "source": "runtime_smoke.telemetry_guard",
                            "activation_status": _status_value(activation)
                            or mechanism_diagnostic.get("activation_status"),
                            "runtime_status": mechanism_diagnostic.get(
                                "runtime_status"
                            ),
                            "effect_status": effect_status
                            or mechanism_diagnostic.get("effect_status"),
                            "counters": _counters_from_status_block(activation),
                            "diagnosis": (
                                "Declared mechanism activation was observed in "
                                "proposal smoke."
                            ),
                        }
                    )
                )

    static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if static is not None and _static_activation_mismatch(static) is not None:
        if not any(
            item.get("diagnostic_type") == TELEMETRY_FIELD_MISSING_OR_MISDECLARED
            for item in diagnostics
        ):
            diagnostics.append(
                _drop_empty_items(
                    {
                        "diagnostic_type": TELEMETRY_FIELD_MISSING_OR_MISDECLARED,
                        "lifecycle_signal": _diagnostic_lifecycle_signal(
                            TELEMETRY_FIELD_MISSING_OR_MISDECLARED
                        ),
                        "category": "activation",
                        "source": "telemetry_static_preview",
                        "issue_codes": list(static.get("issue_codes") or ())[:4],
                        "fields": _compact_agent_text_list(
                            static.get("checked_fields"), limit=4
                        ),
                        "diagnosis": (
                            "Declared expected_telemetry fields do not match the "
                            "runtime telemetry contract."
                        ),
                    }
                )
            )

    return _dedupe_diagnostics(diagnostics)


def _static_activation_mismatch(value: Any) -> dict[str, Any] | None:
    static = _mapping_or_none(value)
    if static is None:
        return None
    issue_codes = tuple(str(code or "").strip() for code in static.get("issue_codes") or ())
    issues = _compact_agent_text_list(static.get("issues"), limit=4)
    joined = "\n".join(issues).lower()
    mismatch = bool(_STATIC_MISMATCH_CODES.intersection(issue_codes)) or any(
        marker in joined
        for marker in (
            "record_move alone",
            "effect telemetry, not activation",
            "expected_telemetry.activation references outcome",
            "expected_telemetry.activation references aggregate effect",
            "expected_telemetry.activation references aggregate runtime",
            "declared mechanism activation",
        )
    )
    if not mismatch:
        return None
    declared = _compact_agent_text_list(static.get("declared_mechanisms"), limit=3)
    checked = _compact_agent_text_list(static.get("checked_fields"), limit=3)
    mechanism = declared[0] if declared else ""
    field = checked[0] if checked else ""
    return _diagnostic_payload(
        subtype="expected_telemetry_mismatch",
        source="telemetry_static_preview",
        guard_failure_code="DECLARED_MECHANISM_ACTIVATION_MISSING",
        mechanism=mechanism,
        category="activation",
        field=field,
        counters={},
        telemetry_guard=None,
        diagnostic=None,
        static_issues=issues,
    )


def _activation_subtype(
    *,
    failure: Mapping[str, Any],
    field: str,
    mechanism: str,
    diagnostic: Mapping[str, Any] | None,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any],
    telemetry_static: Mapping[str, Any] | None,
) -> str:
    activation = _status_block(diagnostic, "activation")
    runtime = _status_block(diagnostic, "runtime")
    effect = _status_block(diagnostic, "effect")
    activation_counters = _counters_from_status_block(activation) or _issue_counters(
        failure
    )
    activation_present = int(activation_counters.get("candidate_present", 0) or 0)
    activation_missing = int(activation_counters.get("candidate_missing", 0) or 0)
    effect_present = int(
        (_counters_from_status_block(effect) or {}).get("candidate_present", 0) or 0
    )
    field_lower = field.lower()
    if _field_looks_like_expected_telemetry_mismatch(field_lower, mechanism):
        return "expected_telemetry_mismatch"
    if effect_present > 0 and _status_value(activation) in {"missing", "zero"}:
        return "expected_telemetry_mismatch"
    if _static_has_activation_helper(telemetry_static, mechanism):
        return "path_not_reached"
    if activation_present > 0:
        return "trigger_not_reached"
    if _status_value(runtime) == "observed" or _runtime_search_effort(runtime_smoke) > 0:
        return "instrumentation_missing"
    case_count = _case_count(runtime_smoke, telemetry_guard)
    if case_count is not None and case_count <= 1:
        return "smoke_budget_or_case_insufficient"
    if activation_missing > 0:
        return "not_connected"
    return "unknown"


def _field_looks_like_expected_telemetry_mismatch(
    field_lower: str,
    mechanism: str,
) -> bool:
    if any(token in field_lower for token in _EFFECT_FIELD_TOKENS):
        return True
    if field_lower.replace(".", "_").endswith("events"):
        return True
    mechanism_lower = mechanism.lower()
    if mechanism_lower and field_lower and mechanism_lower not in field_lower:
        return True
    return False


def _diagnostic_payload(
    *,
    subtype: str,
    source: str,
    guard_failure_code: str,
    mechanism: str,
    category: str,
    field: str,
    counters: Mapping[str, Any],
    telemetry_guard: Mapping[str, Any] | None,
    diagnostic: Mapping[str, Any] | None,
    static_issues: list[str] | None = None,
) -> dict[str, Any]:
    subtype_text = subtype or "unknown"
    repair_guidance = _diagnostic_repair_guidance(subtype_text, mechanism)
    return _drop_empty_items(
        {
            "category": PROPOSAL_ACTIVATION_DIAGNOSTIC_CODE,
            "code": PROPOSAL_ACTIVATION_DIAGNOSTIC_CODE,
            "failure_code": guard_failure_code,
            "mechanism_id": mechanism,
            "activation_diagnostic_kind": subtype_text,
            "diagnostic_type": _public_diagnostic_type(subtype_text),
            "lifecycle_signal": _diagnostic_lifecycle_signal(
                _public_diagnostic_type(subtype_text)
            ),
            "source": source,
            "layer": source,
            "telemetry_failure_code": guard_failure_code,
            "telemetry_failure_mechanism": mechanism,
            "telemetry_failure_category": category,
            "telemetry_failure_field": field,
            "missing_fields": [field] if field else None,
            "counters": dict(counters or {}),
            "candidate_runs": (
                telemetry_guard.get("candidate_runs") if telemetry_guard else None
            ),
            "champion_runs": (
                telemetry_guard.get("champion_runs") if telemetry_guard else None
            ),
            "activation_status": (
                diagnostic.get("activation_status") if diagnostic else None
            ),
            "runtime_status": diagnostic.get("runtime_status") if diagnostic else None,
            "effect_status": diagnostic.get("effect_status") if diagnostic else None,
            "detected_records": _detected_records(diagnostic),
            "static_issues": static_issues or None,
            "diagnosis": _diagnosis_text(subtype_text),
            "proposal_smoke_interpretation": (
                "This diagnostic means the compact proposal smoke did not "
                "exercise positive activation evidence for the declared "
                "mechanism. It is not proof that formal screening cannot "
                "activate the mechanism."
            ),
            "screening_policy": (
                "Treat as smoke coverage or trigger-limitation feedback unless "
                "there is a separate runtime, contract, or formal telemetry "
                "failure."
            ),
            "allowed_repair": repair_guidance[0] if repair_guidance else None,
            "forbidden_repair": (
                "Do not force activation, emit fake activation, use max(..., 1), "
                "or add guarantee-positive fallback behavior only to satisfy telemetry."
            ),
            "repair_guidance": repair_guidance,
        }
    )


def _telemetry_diagnostic_public_payload(
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    kind = str(diagnostic.get("activation_diagnostic_kind") or "").strip()
    diagnostic_type = diagnostic.get("diagnostic_type") or _public_diagnostic_type(kind)
    return _drop_empty_items(
        {
            "diagnostic_type": diagnostic_type,
            "lifecycle_signal": diagnostic.get("lifecycle_signal")
            or _diagnostic_lifecycle_signal(str(diagnostic_type or "")),
            "activation_diagnostic_kind": kind,
            "mechanism_id": diagnostic.get("mechanism_id")
            or diagnostic.get("telemetry_failure_mechanism"),
            "category": diagnostic.get("telemetry_failure_category")
            or diagnostic.get("category"),
            "field": diagnostic.get("telemetry_failure_field"),
            "source": diagnostic.get("source"),
            "failure_code": diagnostic.get("failure_code")
            or diagnostic.get("telemetry_failure_code"),
            "activation_status": diagnostic.get("activation_status"),
            "runtime_status": diagnostic.get("runtime_status"),
            "effect_status": diagnostic.get("effect_status"),
            "counters": diagnostic.get("counters"),
            "diagnosis": diagnostic.get("diagnosis"),
            "proposal_smoke_interpretation": diagnostic.get(
                "proposal_smoke_interpretation"
            ),
            "screening_policy": diagnostic.get("screening_policy"),
            "allowed_repair": diagnostic.get("allowed_repair"),
            "forbidden_repair": diagnostic.get("forbidden_repair"),
        }
    )


def _public_diagnostic_type(subtype: str) -> str:
    if subtype == "expected_telemetry_mismatch":
        return TELEMETRY_FIELD_MISSING_OR_MISDECLARED
    if subtype in {"not_connected", "instrumentation_missing"}:
        return ACTIVATION_UNOBSERVED_WIRING_SUSPECT
    if subtype in {
        "path_not_reached",
        "trigger_not_reached",
        "smoke_budget_or_case_insufficient",
    }:
        return ACTIVATION_UNOBSERVED_CONDITIONAL
    return ACTIVATION_UNOBSERVED_CONDITIONAL


def _diagnostic_lifecycle_signal(diagnostic_type: str) -> str:
    if diagnostic_type in {OBSERVED_ACTIVATION, EFFECT_MISSING_OBSERVED_ACTIVATION}:
        return VALID_ACTIVE_WEAK_POSITIVE
    if diagnostic_type == ACTIVATION_UNOBSERVED_WIRING_SUSPECT:
        return INACTIVE_OR_WIRING_SUSPECT
    if diagnostic_type == ACTIVATION_UNOBSERVED_CONDITIONAL:
        return ACTIVE_NO_CASE_LEVEL_GATE
    return str(diagnostic_type or "").strip()


def _detected_records(diagnostic: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if diagnostic is None:
        return None
    result: dict[str, Any] = {}
    for key in ("activation", "runtime", "effect"):
        block = _status_block(diagnostic, key)
        if block is None:
            continue
        result[key] = _drop_empty_items(
            {
                "status": block.get("status"),
                "candidate_positive": block.get("candidate_positive"),
                "candidate_present": block.get("candidate_present"),
                "candidate_zero": block.get("candidate_zero"),
                "candidate_missing": block.get("candidate_missing"),
            }
        )
    return result or None


def _diagnostic_for_mechanism(
    telemetry_guard: Mapping[str, Any],
    mechanism: str,
) -> Mapping[str, Any] | None:
    diagnostics = telemetry_guard.get("mechanism_diagnostics")
    if not isinstance(diagnostics, (list, tuple)):
        return None
    for item in diagnostics:
        if not isinstance(item, Mapping):
            continue
        if mechanism and str(item.get("mechanism") or "").strip() != mechanism:
            continue
        return item
    return None


def _mechanism_diagnostic_items(
    telemetry_guard: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    diagnostics = telemetry_guard.get("mechanism_diagnostics")
    if not isinstance(diagnostics, (list, tuple)):
        return []
    return [item for item in diagnostics if isinstance(item, Mapping)]


def _effect_issue_for_mechanism(
    telemetry_guard: Mapping[str, Any],
    mechanism: str,
) -> Mapping[str, Any] | None:
    for section in ("failures", "warnings"):
        items = telemetry_guard.get(section)
        if not isinstance(items, (list, tuple)):
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            category = str(item.get("category") or "").strip().lower()
            item_mechanism = str(item.get("mechanism") or "").strip()
            if category != "effect":
                continue
            if mechanism and item_mechanism and item_mechanism != mechanism:
                continue
            return item
    return None


def _status_block(
    diagnostic: Mapping[str, Any] | None,
    name: str,
) -> Mapping[str, Any] | None:
    if diagnostic is None:
        return None
    block = diagnostic.get(name)
    return block if isinstance(block, Mapping) else None


def _status_value(block: Mapping[str, Any] | None) -> str:
    return str((block or {}).get("status") or "").strip().lower()


def _status_positive(block: Mapping[str, Any] | None) -> bool:
    counters = _counters_from_status_block(block)
    if int(counters.get("candidate_positive", 0) or 0) > 0:
        return True
    return _status_value(block) in {"observed", "positive"}


def _first_field(block: Mapping[str, Any] | None) -> str:
    fields = (block or {}).get("fields")
    if isinstance(fields, (list, tuple)) and fields:
        return str(fields[0] or "").strip()
    field = (block or {}).get("field")
    return str(field or "").strip()


def _counters_from_status_block(block: Mapping[str, Any] | None) -> dict[str, int]:
    counters = (block or {}).get("counters")
    if not isinstance(counters, Mapping):
        counters = block or {}
    result: dict[str, int] = {}
    for key in (
        "candidate_positive",
        "candidate_present",
        "candidate_zero",
        "candidate_missing",
    ):
        try:
            result[key] = int(counters.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return result


def _issue_counters(issue: Mapping[str, Any]) -> dict[str, int]:
    counters = issue.get("counters")
    if not isinstance(counters, Mapping):
        counters = issue
    result: dict[str, int] = {}
    for key in (
        "candidate_positive",
        "candidate_present",
        "candidate_zero",
        "candidate_missing",
        "champion_positive",
    ):
        try:
            result[key] = int(counters.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return result


def _runtime_search_effort(runtime_smoke: Mapping[str, Any] | None) -> int:
    runtime = _mapping_or_none((runtime_smoke or {}).get("runtime"))
    if runtime is None:
        return 0
    effort = 0
    for key, value in runtime.items():
        normalized = str(key).replace(".", "_").lower()
        if normalized.endswith("_errors"):
            continue
        if normalized.endswith(("_iterations", "_attempts", "_move_attempts")):
            effort += _nonnegative_int(value)
    return effort


def _case_count(
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any],
) -> int | None:
    for value in (
        (runtime_smoke or {}).get("case_count"),
        telemetry_guard.get("candidate_runs"),
    ):
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _diagnosis_text(subtype: str) -> str:
    if subtype == "not_connected":
        return (
            "Proposal smoke coverage did not show the declared mechanism on the "
            "exercised call path."
        )
    if subtype == "path_not_reached":
        return (
            "Declared activation helper exists in the patch, but proposal smoke "
            "did not exercise that trigger/path."
        )
    if subtype == "trigger_not_reached":
        return (
            "Declared activation telemetry was present, but the short smoke "
            "case did not make the trigger positive."
        )
    if subtype == "instrumentation_missing":
        return (
            "The proposal-smoke run showed generic activity, but it did not "
            "observe mechanism-local activation telemetry."
        )
    if subtype == "expected_telemetry_mismatch":
        return "Declared activation evidence is mismatched with effect/objective telemetry or a non-mechanism-specific field."
    if subtype == "smoke_budget_or_case_insufficient":
        return (
            "The short smoke case or budget did not cover the trigger needed "
            "to observe activation."
        )
    return (
        "Activation telemetry was missing from the compact smoke payload, but "
        "the smoke coverage was insufficient to classify why."
    )


def _diagnostic_repair_guidance(subtype: str, mechanism: str) -> list[str]:
    mech = mechanism or "<declared mechanism>"
    if subtype == "not_connected":
        return [
            (
                f"Check whether proposal smoke exercises {mech}'s natural "
                "trigger; if not, add a smoke-scoped threshold or diagnostic "
                "counter on the real path."
            ),
            (
                f"If the helper is truly inert, wire {mech} into the active "
                "path; otherwise do not add unconditional activation just for "
                "smoke."
            ),
        ]
    if subtype == "path_not_reached":
        return [
            f"Instrument {mech} on its natural trigger/evaluation path; if the trigger is rare, use a canary-scoped threshold for proposal smoke.",
            "Do not unconditionally trigger the mechanism or add another record call inside the same unreachable branch only to satisfy telemetry.",
        ]
    if subtype == "trigger_not_reached":
        return [
            f"Use {mech}'s existing condition: lower only canary/test thresholds or record a diagnostic/budget counter when the condition is evaluated.",
            "Do not force activation, emit fake activation, or change algorithm behavior just to pass telemetry.",
            "Keep the declared mechanism id unchanged.",
        ]
    if subtype == "instrumentation_missing":
        return [
            f"Add context.record_iteration('{mech}', positive_count) on the "
            "active mechanism path; use "
            f"context.record_phase('{mech}', measured_elapsed_ms_delta) only "
            "from a measured duration delta.",
            "Preserve effect telemetry separately with context.record_move "
            "when moves are attempted, and do not fake positive runtime or "
            "activation.",
        ]
    if subtype == "expected_telemetry_mismatch":
        return [
            "Use activation telemetry for activation claims: record_iteration or record_phase with the exact mechanism id.",
            "Do not use objective/effect counters or context.record_move alone as activation evidence.",
        ]
    if subtype == "smoke_budget_or_case_insufficient":
        return [
            f"Treat {mech} as conditional in proposal smoke: add natural condition instrumentation, a canary-targeted threshold, or diagnostic status.",
            "Keep the algorithm valid for full screening; do not add unconditional fallback activation for telemetry.",
        ]
    return [
        "Inspect the active path and expected_telemetry fields; add exact mechanism activation telemetry where the mechanism naturally runs."
    ]


def _static_has_activation_helper(
    telemetry_static: Mapping[str, Any] | None,
    mechanism: str,
) -> bool:
    if telemetry_static is None:
        return False
    helper_evidence = telemetry_static.get("helper_evidence")
    if not isinstance(helper_evidence, Mapping):
        return False
    evidence = helper_evidence.get(mechanism)
    if not isinstance(evidence, Mapping):
        return False
    return bool(evidence.get("record_iteration") or evidence.get("record_phase"))


def _dedupe_diagnostics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("diagnostic_type") or ""),
            str(item.get("mechanism_id") or ""),
            str(item.get("field") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


__all__ = [
    "ACTIVATION_UNOBSERVED_CONDITIONAL",
    "ACTIVATION_UNOBSERVED_WIRING_SUSPECT",
    "ACTIVE_NO_CASE_LEVEL_GATE",
    "ACTIVE_PAIR_WINS_BUT_CASE_FAIL",
    "EFFECT_MISSING_OBSERVED_ACTIVATION",
    "INACTIVE_OR_WIRING_SUSPECT",
    "OBSERVED_ACTIVATION",
    "PROPOSAL_ACTIVATION_DIAGNOSTIC_CODE",
    "TELEMETRY_FIELD_MISSING_OR_MISDECLARED",
    "VALID_ACTIVE_WEAK_POSITIVE",
    "_proposal_smoke_activation_diagnostic",
    "_proposal_smoke_telemetry_diagnostics",
]
