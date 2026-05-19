"""Runtime feedback and runtime-failure guidance helpers."""
from __future__ import annotations

import re
from typing import Any, List

from scion.core.models import ExperimentStage, StepRecord
from scion.proposal.context.feedback import (
    _filter_hypothesis_prompt_steps,
    _first_line,
)
from scion.proposal.context.surfaces import _coerce_text_list, _get_research_surfaces

def _build_runtime_feedback(
    steps: List[StepRecord],
    max_items: int = 4,
    *,
    slow_case_threshold: float = 2.0,
) -> str:
    """Render bounded runtime-guard feedback for proposal context.

    This is proposal guidance only. It is intentionally derived from bounded
    verification and screening aggregates. Validation/frozen per-case data is
    never rendered here.
    """
    items: list[str] = []
    summaries: list[str] = []
    slow_cases: list[str] = []
    failure_cases: list[str] = []
    failure_causes: list[str] = []
    contract_failures: list[str] = []
    for step in reversed(steps):
        detail = step.verification_detail or step.failure_detail or ""
        target = (
            step.patch.file_path
            if step.patch is not None
            else step.hypothesis.target_file
            or step.hypothesis.change_locus
        )
        if (
            step.protocol_result is None
            and step.failure_stage in {"hypothesis_contract", "patch_contract"}
            and len(contract_failures) < max_items
        ):
            contract_failures.append(
                f"- R{step.round_num} target={target}: "
                f"stage={step.failure_stage} detail={_first_line(detail)}"
            )
        if "V9_perf_guard" in detail and len(items) < max_items:
            check_line = _extract_runtime_guard_line(detail)
            items.append(f"- R{step.round_num} target={target}: {check_line}")
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        ):
            if step.protocol_result.stats.runtime_pairs > 0 and len(summaries) < max_items:
                st = step.protocol_result.stats
                summaries.append(
                    f"- R{step.round_num} target={target}: "
                    f"median_ratio={_fmt_runtime(st.runtime_ratio_median)}x "
                    f"median_delta_ms={_fmt_runtime(st.runtime_delta_median_ms)} "
                    f"regression_rate={_fmt_runtime(st.runtime_regression_rate)} "
                    f"pairs={st.runtime_pairs}"
                )
            (
                raw_failures,
                raw_slow_cases,
                raw_failure_causes,
            ) = _extract_screening_runtime_structured_feedback(
                step,
                target=target,
                max_items=max_items,
                slow_case_threshold=slow_case_threshold,
            )
            for line in raw_failure_causes:
                if len(failure_causes) < max_items:
                    failure_causes.append(line)
            for line in raw_failures:
                if len(failure_cases) < max_items:
                    failure_cases.append(line)
            for line in raw_slow_cases:
                if len(slow_cases) < max_items:
                    slow_cases.append(line)
        if (
            len(items) >= max_items
            and len(summaries) >= max_items
            and len(failure_causes) >= max_items
            and len(contract_failures) >= max_items
            and len(slow_cases) >= max_items
            and len(failure_cases) >= max_items
        ):
            break
    if (
        not items
        and not summaries
        and not failure_cases
        and not slow_cases
        and not failure_causes
        and not contract_failures
    ):
        return ""
    sections: list[str] = []
    if failure_causes:
        sections.append(
            "Recent screening failure causes:\n"
            + "\n".join(reversed(failure_causes))
        )
    if contract_failures:
        sections.append(
            "Recent contract failures:\n" + "\n".join(reversed(contract_failures))
        )
    if summaries:
        sections.append(
            "Recent screening runtime summary:\n" + "\n".join(reversed(summaries))
        )
    if failure_cases:
        sections.append(
            "Recent screening runtime failure categories:\n"
            + "\n".join(reversed(failure_cases))
        )
    if slow_cases:
        sections.append(
            "Recent slow screening cases:\n" + "\n".join(reversed(slow_cases))
        )
    if items:
        sections.append("Recent runtime guard failures:\n" + "\n".join(reversed(items)))
    sections.append(
        "Prefer bounded neighborhoods, top-k candidate filters, and early no-op exits."
    )
    return "\n".join(sections)

def _build_runtime_failure_guidance(
    steps: List[StepRecord],
    *,
    problem_spec: Any,
    adapter_spec: Any = None,
    max_items: int = 4,
    forced_surface: str | None = None,
) -> str:
    """Render problem-declared steering for structured runtime failure categories."""
    guidance_specs = _get_runtime_failure_guidance_specs(problem_spec, adapter_spec)
    if not guidance_specs:
        return ""

    safe_steps = [
        step
        for step in _filter_hypothesis_prompt_steps(steps)
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ][-12:]
    if not safe_steps:
        return ""

    surfaces = _get_research_surfaces(problem_spec, adapter_spec)
    kind_by_surface = {
        str(getattr(surface, "name", "")): str(getattr(surface, "kind", ""))
        for surface in surfaces
    }
    rendered: list[str] = []
    for spec in guidance_specs:
        categories = _coerce_text_list(getattr(spec, "failure_categories", None))
        if not categories:
            continue
        profile = _runtime_guidance_profile(
            safe_steps,
            categories=categories,
            applies_to_surfaces=_coerce_text_list(
                getattr(spec, "applies_to_surfaces", None)
            ),
            applies_to_surface_kinds=_coerce_text_list(
                getattr(spec, "applies_to_surface_kinds", None)
            ),
            kind_by_surface=kind_by_surface,
        )
        matched = profile["matched_count"]
        total = profile["total_count"]
        if total <= 0 or matched <= 0:
            continue
        min_count = max(1, _as_int(getattr(spec, "min_count", 1)))
        try:
            min_fraction = float(getattr(spec, "min_category_fraction", 0.5))
        except (TypeError, ValueError):
            min_fraction = 0.5
        fraction = matched / total
        if matched < min_count or fraction < min_fraction:
            continue

        lines = [
            (
                f"- Runtime categories {', '.join(categories)} dominate recent "
                f"matching screening evidence ({matched}/{total}, "
                f"fraction={fraction:.2f})."
            )
        ]
        surfaces_seen = sorted(profile["surfaces"])[:max_items]
        if surfaces_seen:
            lines.append(f"  observed_surfaces: {', '.join(surfaces_seen)}")
        recommended = _coerce_text_list(getattr(spec, "recommended_surfaces", None))
        discouraged = _coerce_text_list(getattr(spec, "discouraged_surfaces", None))
        forced_conflict = bool(
            forced_surface
            and (
                (recommended and forced_surface not in recommended)
                or forced_surface in discouraged
            )
        )
        if recommended and not forced_conflict:
            lines.append(f"  recommended_surfaces: {', '.join(recommended)}")
        safe_discouraged = [
            surface for surface in discouraged if surface != forced_surface
        ]
        if safe_discouraged and not forced_conflict:
            lines.append(f"  discouraged_surfaces: {', '.join(safe_discouraged)}")
        if forced_surface:
            lines.append(
                f"  forced_surface_constraint: keep surface {forced_surface}"
            )
        guidance = str(getattr(spec, "guidance", "") or "").strip()
        if guidance and not forced_conflict:
            lines.append(f"  guidance: {guidance}")
        rendered.append("\n".join(lines))

    if not rendered:
        return ""
    return (
        "Problem-declared runtime-failure steering (screening only):\n"
        + "\n".join(rendered[:max_items])
    )

def _get_runtime_failure_guidance_specs(
    problem_spec: Any,
    adapter_spec: Any = None,
) -> list[Any]:
    for spec in (problem_spec, adapter_spec):
        hints = getattr(spec, "runtime_failure_guidance", None)
        if hints:
            return list(hints)
        hints = getattr(spec, "failure_response_hints", None)
        if hints:
            return list(hints)
    return []

def _runtime_guidance_profile(
    steps: list[StepRecord],
    *,
    categories: list[str],
    applies_to_surfaces: list[str],
    applies_to_surface_kinds: list[str],
    kind_by_surface: dict[str, str],
) -> dict[str, Any]:
    category_set = set(categories)
    surface_set = set(applies_to_surfaces)
    kind_set = set(applies_to_surface_kinds)
    matched_count = 0
    total_count = 0
    surfaces_seen: set[str] = set()
    for step in steps:
        surface = str(step.hypothesis.change_locus or "")
        kind = kind_by_surface.get(surface, "")
        if surface_set and surface not in surface_set:
            continue
        if kind_set and kind not in kind_set:
            continue
        counts = {
            category: count
            for category, count in _runtime_failure_categories(step).items()
            if count > 0
        }
        if not counts:
            continue
        step_total = sum(counts.values())
        total_count += step_total
        matched_count += sum(
            count for category, count in counts.items() if category in category_set
        )
        if surface:
            surfaces_seen.add(surface)
    return {
        "matched_count": matched_count,
        "total_count": total_count,
        "surfaces": surfaces_seen,
    }

def _extract_screening_runtime_structured_feedback(
    step: StepRecord,
    *,
    target: str,
    max_items: int,
    slow_case_threshold: float = 2.0,
) -> tuple[list[str], list[str], list[str]]:
    """Extract bounded screening-only runtime feedback from structured summaries."""
    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        return [], [], []

    failure_cause = _build_screening_failure_cause_line(step, target, {})
    failure_causes = [failure_cause] if failure_cause else []
    failure_lines: list[str] = []
    categories = _runtime_failure_categories(step)
    first = _first_runtime_failure(step)
    for category, count in sorted(categories.items()):
        if count <= 0:
            continue
        detail = ""
        if first and first.get("category") == category:
            code = first.get("code") or "unknown"
            component = first.get("component") or "unknown"
            summary = first.get("detail_summary") or ""
            detail = f" first_code={code} component={component} detail={_first_line(str(summary))}"
        failure_lines.append(
            f"- R{step.round_num} target={target}: "
            f"candidate_failure_category={category} count={count}{detail}"
        )
        if len(failure_lines) >= max_items:
            break

    return failure_lines, [], failure_causes

def _build_screening_failure_cause_line(
    step: StepRecord,
    target: str,
    payload: dict[str, Any],
) -> str:
    protocol = step.protocol_result
    if protocol is None:
        return ""
    stats = protocol.stats
    operator_attempts = _structured_runtime_count(
        step,
        "candidate_operator_attempts",
        payload,
        "candidate_runtime",
        "operator_attempts",
    )
    operator_accepted = _structured_runtime_count(
        step,
        "candidate_operator_accepted",
        payload,
        "candidate_runtime",
        "operator_accepted",
    )
    operator_errors = _structured_runtime_count(
        step,
        "candidate_operator_errors",
        payload,
        "candidate_runtime",
        "operator_errors",
    )
    invalid_outputs = _structured_runtime_count(
        step,
        "candidate_operator_invalid_outputs",
        payload,
        "candidate_runtime",
        "operator_invalid_outputs",
    )
    stop_reasons = _runtime_stop_reasons(step) or _operator_stop_reason_counts(payload)
    failed_pairs = _count_field(stats.failed_pairs, payload, "failed_pairs")
    candidate_failed = _count_field(
        stats.candidate_failed_pairs,
        payload,
        "candidate_failed_pairs",
    )
    champion_failed = _count_field(
        stats.champion_failed_pairs,
        payload,
        "champion_failed_pairs",
    )
    gate_failed = protocol.gate_outcome in {"fail", "unclear", "continue"}
    has_runtime_or_operator_signal = any(
        value > 0
        for value in (
            failed_pairs,
            candidate_failed,
            champion_failed,
            operator_attempts,
            operator_accepted,
            operator_errors,
            invalid_outputs,
        )
    )
    if not gate_failed and not has_runtime_or_operator_signal:
        return ""

    reason_codes = ",".join(protocol.reason_codes) if protocol.reason_codes else "none"
    total_pairs = _count_field(stats.total_pairs, payload, "total_pairs")
    valid_pairs = _count_field(stats.valid_pairs, payload, "valid_pairs")
    runtime_ratio = (
        stats.runtime_ratio_median
        if stats.runtime_ratio_median is not None
        else _runtime_stat(payload, "runtime_ratio_median")
    )
    quality_notes: list[str] = []
    if operator_attempts > 0 and operator_accepted == 0:
        quality_notes.append("no accepted operator moves despite attempted moves")
    if stats.ties > max(stats.wins, stats.losses) and stats.ties > 0:
        quality_notes.append("tie-dominated screening evidence")
    if stop_reasons:
        reason_text = ",".join(
            f"{reason}:{count}" for reason, count in sorted(stop_reasons.items())
        )
        quality_notes.append(f"operator_stop_reason={reason_text}")
        if "no_improvement_round" in stop_reasons:
            quality_notes.append(
                "no_improvement_round indicates weak/no-op search behavior, not schema/runtime failure"
            )
    surface_runtime_note = _surface_runtime_summary_note(protocol)
    if surface_runtime_note:
        quality_notes.append(surface_runtime_note)
    if (
        quality_notes
        and failed_pairs == 0
        and candidate_failed == 0
        and champion_failed == 0
        and operator_errors == 0
        and invalid_outputs == 0
    ):
        quality_notes.append("no schema/runtime failure detected")

    quality_suffix = ""
    if quality_notes:
        quality_suffix = " quality_notes=" + "; ".join(quality_notes)

    return (
        f"- R{step.round_num} target={target}: gate={protocol.gate_outcome} "
        f"reasons={reason_codes} total_pairs={total_pairs} valid_pairs={valid_pairs} "
        f"wins={stats.wins} losses={stats.losses} ties={stats.ties} "
        f"failed_pairs={failed_pairs} candidate_failed_pairs={candidate_failed} "
        f"champion_failed_pairs={champion_failed} "
        f"runtime_ratio_median={_fmt_runtime(runtime_ratio)}x "
        f"operator_attempts={operator_attempts} operator_accepted={operator_accepted} "
        f"operator_errors={operator_errors} invalid_outputs={invalid_outputs}"
        f"{quality_suffix}"
    )

def _surface_runtime_summary_note(protocol: Any) -> str:
    summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(summary, dict):
        return ""
    surface = str(summary.get("selected_surface") or "").strip()
    fields = summary.get("fields")
    if not surface or not isinstance(fields, dict):
        return ""

    candidates: list[tuple[tuple[int, int, str], str]] = []
    guard_note = _telemetry_guard_summary_note(summary)
    if guard_note:
        candidates.append(((0, -1, "telemetry_guard"), guard_note))
    for field, field_summary in fields.items():
        if not isinstance(field_summary, dict):
            continue
        field_name = str(field)
        if not _surface_runtime_field_interesting(field_name, field_summary):
            continue
        values = field_summary.get("values")
        value_text = ""
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, dict):
                raw_value = str(first.get("value", ""))[:120]
                count = _as_int(first.get("count", 0))
                value_text = f" value={raw_value} count={count}"
        numeric_text = _surface_runtime_numeric_note(field_summary)
        failed = _as_int(field_summary.get("failed", 0))
        missing = _as_int(field_summary.get("missing", 0))
        suffix = value_text + numeric_text
        if failed or missing:
            suffix += f" failed={failed} missing={missing}"
        candidates.append(
            (
                _surface_runtime_sort_key(field_name, field_summary),
                f"{field_name}:{suffix.strip()}",
            )
        )
    candidates.sort(key=lambda item: item[0])
    interesting = [text for _sort_key, text in candidates[:8]]
    if not interesting:
        return ""
    return f"selected_surface_runtime[{surface}]=" + "; ".join(interesting)

def _telemetry_guard_summary_note(summary: dict[str, Any]) -> str:
    guard = summary.get("telemetry_guard")
    if not isinstance(guard, dict):
        return ""
    failures = guard.get("failures")
    warnings = guard.get("warnings")
    parts: list[str] = []
    if isinstance(failures, list) and failures:
        codes = [
            str(item.get("code"))
            for item in failures
            if isinstance(item, dict) and item.get("code")
        ]
        if codes:
            parts.append("fail=" + ",".join(codes[:4]))
    if isinstance(warnings, list) and warnings:
        codes = [
            str(item.get("code"))
            for item in warnings
            if isinstance(item, dict) and item.get("code")
        ]
        if codes:
            parts.append("warn=" + ",".join(codes[:4]))
    if not parts:
        return ""
    return "telemetry_guard(" + ";".join(parts) + ")"

_SURFACE_RUNTIME_PRIORITY_SUFFIXES = (
    "_objective_trace",
    "_delta_by_phase",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_accepted_moves",
    "_move_attempts",
    "_search_iterations",
    "_elapsed_ms",
    "_phase_runtime_ms",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_accepted",
    "_attempts",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_coverage_status",
    "_stop_reason",
    "_errors",
    "_active",
    "_loaded",
)

def _surface_runtime_sort_key(
    field_name: str,
    field_summary: dict[str, Any],
) -> tuple[int, int, str]:
    has_issue = any(
        _as_int(field_summary.get(key, 0)) > 0
        for key in ("failed", "missing", "empty")
    )
    priority = len(_SURFACE_RUNTIME_PRIORITY_SUFFIXES)
    for index, suffix in enumerate(_SURFACE_RUNTIME_PRIORITY_SUFFIXES):
        if field_name.endswith(suffix):
            priority = index
            break
    return (0 if has_issue else 1, priority, field_name)

def _surface_runtime_numeric_note(field_summary: dict[str, Any]) -> str:
    numeric = field_summary.get("numeric_summary")
    if not isinstance(numeric, dict):
        return ""
    parts: list[str] = []
    scalar = numeric.get("scalar")
    if isinstance(scalar, dict):
        parts.append(_surface_runtime_numeric_stats_text("scalar", scalar))
    mapping = numeric.get("mapping")
    if isinstance(mapping, dict):
        for key, stats in list(mapping.items())[:3]:
            if isinstance(stats, dict):
                parts.append(_surface_runtime_numeric_stats_text(str(key), stats))
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return " numeric=" + "|".join(parts)

def _surface_runtime_numeric_stats_text(label: str, stats: dict[str, Any]) -> str:
    selected = []
    for key in (
        "observed_count",
        "weighted_sum",
        "nonzero_count",
        "positive_count",
        "zero_count",
    ):
        if key in stats:
            selected.append(f"{key}={stats[key]}")
    if not selected:
        return ""
    return f"{label}(" + ",".join(selected) + ")"

def _surface_runtime_field_interesting(
    field_name: str,
    field_summary: dict[str, Any],
) -> bool:
    if any(
        _as_int(field_summary.get(key, 0)) > 0
        for key in ("failed", "missing", "empty")
    ):
        return True
    return any(
        field_name.endswith(suffix)
        for suffix in _SURFACE_RUNTIME_PRIORITY_SUFFIXES
    )

def _runtime_failure_categories(step: StepRecord) -> dict[str, int]:
    categories = dict(getattr(step, "candidate_runtime_failure_categories", {}) or {})
    protocol = step.protocol_result
    if protocol is not None:
        categories.update(
            dict(getattr(protocol, "candidate_runtime_failure_categories", {}) or {})
        )
    return {str(key): _as_int(value) for key, value in categories.items()}

def _first_runtime_failure(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    first = getattr(protocol, "candidate_first_runtime_failure", None) if protocol else None
    if first is None:
        first = getattr(step, "candidate_first_runtime_failure", None)
    return dict(first or {})

def _runtime_stop_reasons(step: StepRecord) -> dict[str, int]:
    reasons = dict(getattr(step, "candidate_runtime_stop_reasons", {}) or {})
    protocol = step.protocol_result
    if protocol is not None:
        reasons.update(dict(getattr(protocol, "candidate_runtime_stop_reasons", {}) or {}))
    return {str(key): _as_int(value) for key, value in reasons.items()}

def _structured_runtime_count(
    step: StepRecord,
    attr_name: str,
    payload: dict[str, Any],
    runtime_key: str,
    field: str,
) -> int:
    protocol = step.protocol_result
    value = getattr(protocol, attr_name, 0) if protocol is not None else 0
    if _as_int(value) > 0:
        return _as_int(value)
    step_value = getattr(step, attr_name, 0)
    if _as_int(step_value) > 0:
        return _as_int(step_value)
    return _sum_runtime_field(payload, runtime_key, field)

def _sum_runtime_field(payload: dict[str, Any], runtime_key: str, field: str) -> int:
    total = 0
    for pair in payload.get("pairs", []) or []:
        if not isinstance(pair, dict):
            continue
        counted_pair_runtime = False
        runtime = pair.get(runtime_key)
        if isinstance(runtime, dict):
            total += _as_int(runtime.get(field))
            counted_pair_runtime = True
        failure = pair.get("failure")
        if isinstance(failure, dict):
            audit = failure.get("runtime_audit")
            if (
                isinstance(audit, dict)
                and runtime_key.startswith("candidate")
                and not counted_pair_runtime
            ):
                total += _as_int(audit.get(field))
    return total

def _operator_stop_reason_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pair in payload.get("pairs", []) or []:
        if not isinstance(pair, dict):
            continue
        runtime = pair.get("candidate_runtime")
        if not isinstance(runtime, dict):
            continue
        reason = str(runtime.get("operator_stop_reason") or "").strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts

def _count_field(stats_value: int, payload: dict[str, Any], field: str) -> int:
    return stats_value if stats_value > 0 else _as_int(payload.get(field))

def _runtime_stat(payload: dict[str, Any], field: str) -> float | None:
    runtime_stats = payload.get("runtime_stats")
    if not isinstance(runtime_stats, dict):
        return None
    value = runtime_stats.get(field)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0

def _fmt_runtime(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.2f}"

def _extract_runtime_guard_line(detail: str) -> str:
    for line in detail.splitlines():
        if "[V9_perf_guard]" in line:
            cleaned = re.sub(r"^\s*\[V9_perf_guard\]\s*\(heavy\)\s*", "", line)
            return cleaned.strip()
    for line in detail.splitlines():
        if "V9_perf_guard" in line:
            return line.replace("V9_perf_guard", "runtime guard").strip()
    return "runtime guard failed"
