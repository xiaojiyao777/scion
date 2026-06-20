"""Repair-guidance rendering for telemetry guard mechanism diagnostics."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.summary_signals import (
    NOT_EVALUATED_OR_TRIGGERED,
    RUNTIME_BUDGET_ZERO_OR_SUBMS,
    WIRING_SUSPECT,
)


def _declared_field_issues_for_category(
    issues: Sequence[Any],
    category: str,
) -> list[dict[str, Any]]:
    category_text = str(category or "").strip().lower()
    result: list[dict[str, Any]] = []
    for item in issues:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("category") or "").strip().lower() != category_text:
            continue
        result.append(dict(item))
    return result


def _mechanism_repair_guidance(
    *,
    mechanism: str,
    activation_status: str,
    runtime_status: str,
    effect_status: str,
    diagnostic_kind: str | None = None,
    diagnostic_signals: Sequence[str] = (),
    declared_field_failures: Sequence[Any] = (),
) -> list[str]:
    guidance: list[str] = []
    effect_field_failures = _declared_field_issues_for_category(
        declared_field_failures,
        "effect",
    )
    if effect_field_failures:
        fields = ", ".join(
            dict.fromkeys(
                str(item.get("field") or "").strip()
                for item in effect_field_failures
                if str(item.get("field") or "").strip()
            )
        )
        observed_prefix = ""
        if activation_status == "observed" and runtime_status == "observed":
            observed_prefix = "Activation and runtime telemetry are observed; "
        guidance.append(
            f"{observed_prefix}declared effect field(s) "
            f"{fields or 'unknown'} for mechanism {mechanism} are not positive. "
            "This is not activation missing; repair effect telemetry attribution "
            "or make the mechanism produce true positive evidence for the "
            "declared effect field(s)."
        )
    if diagnostic_kind == NOT_EVALUATED_OR_TRIGGERED:
        guidance.append(
            f"Mechanism {mechanism} was not evaluated or its trigger did not "
            "fire in this short run. Do not fake activation or force "
            "unconditional execution; instrument the natural decision/evaluation "
            "branch and, for rare triggers, use a canary-scoped threshold or "
            "declare a more appropriate conditional telemetry expectation."
        )
    if WIRING_SUSPECT in diagnostic_signals or diagnostic_kind == WIRING_SUSPECT:
        guidance.append(
            f"No mechanism-local context/evaluation evidence was observed for "
            f"{mechanism}. Check that the declared mechanism is wired into the "
            "active solve/search path and that the exact mechanism id is used "
            "by telemetry helpers."
        )
    if activation_status == "inactive":
        guidance.append(
            "Declared activation telemetry for mechanism "
            f"{mechanism} was present but explicitly inactive. Do not flip the "
            "flag only to satisfy telemetry; inspect the natural trigger, "
            "canary threshold, and mechanism-id wiring, or revise expected "
            "telemetry when the mechanism is intentionally conditional."
        )
    if RUNTIME_BUDGET_ZERO_OR_SUBMS in diagnostic_signals:
        guidance.append(
            f"Runtime/budget telemetry for {mechanism} is zero-valued while "
            "non-time activation or evaluation evidence exists. Treat this as "
            "zero/sub-ms timer granularity unless other evidence is missing; "
            "do not repair it by adding sleeps, max(..., 1), or fake positive "
            "runtime. Keep context/evaluation instrumentation on the natural "
            "path and record phase duration only from the measured delta."
        )
    if activation_status in {"missing", "zero"}:
        guidance.append(
            "Add direct activation telemetry for declared mechanism "
            f"{mechanism}: record a context/iteration/evaluation counter on "
            "the natural mechanism path, for example "
            f"context.record_iteration('{mechanism}', positive_count). Use "
            "phase runtime as supporting budget evidence, not as the only proof "
            "of activation. Do not unconditionally trigger the mechanism only "
            "to satisfy telemetry; instrument its natural trigger/evaluation "
            "path, use a canary-scoped threshold, or revise expected telemetry "
            "for a conditional mechanism."
        )
    if runtime_status in {"missing", "zero"}:
        detail = "missing" if runtime_status == "missing" else "zero-valued"
        guidance.append(
            "Runtime/budget telemetry for declared mechanism "
            f"{mechanism} is {detail}. Prefer non-time activation/evaluation "
            "evidence to prove the mechanism ran; use "
            f"context.record_phase('{mechanism}', elapsed_ms_delta) only with a "
            "measured phase-duration delta on the natural path. Do not add "
            "unconditional execution, sleeps, or fake positive elapsed time only "
            "to make runtime telemetry positive."
        )
    if (
        effect_status == "zero"
        and activation_status == "observed"
        and not effect_field_failures
    ):
        guidance.append(
            "Mechanism executed but declared effect stayed zero. Treat this as "
            "a no-effect performance outcome, not missing activation; use a "
            "different trigger, schedule, threshold, composition, or mechanism "
            "instead of repeating the unchanged change."
        )
    if effect_status == "missing":
        prefix = (
            "Activation was observed but effect attribution is missing. "
            if activation_status == "observed" or runtime_status == "observed"
            else ""
        )
        guidance.append(
            prefix
            + "Add effect telemetry for declared mechanism "
            f"{mechanism}: context.record_move('{mechanism}', attempted=1, "
            "accepted=accepted_flag, delta=objective_delta, "
            "best_improved=best_improved_flag)."
        )
    return guidance
