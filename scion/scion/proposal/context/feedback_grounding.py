"""Concise hypothesis-grounding summaries from screening feedback."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Optional

from scion.core.models import ExperimentStage, StepRecord
from scion.proposal.mechanism_labels import extract_mechanism_label


def _build_feedback_grounding_summary(
    branch_steps: list[StepRecord],
    taxonomy: Optional[list] = None,
) -> str:
    """Render next-hypothesis guidance from screening-visible aggregates."""

    screening_steps = [
        step
        for step in branch_steps
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ][-6:]
    if not screening_steps:
        return ""

    lines: list[str] = ["## Feedback Grounding Summary (screening only)"]
    if bottleneck := _active_bottleneck_line(screening_steps):
        lines.append(f"- Active bottleneck: {bottleneck}")
    if objective_lines := _objective_opportunity_lines(screening_steps):
        lines.append("- Objective opportunities:")
        lines.extend(f"  - {line}" for line in objective_lines[:4])
    if mechanism_lines := _recent_no_effect_mechanism_lines(
        screening_steps,
        taxonomy=taxonomy,
    ):
        lines.append("- Low-value/no-effect mechanisms:")
        lines.extend(f"  - {line}" for line in mechanism_lines[:4])
    if len(lines) == 1:
        return ""
    lines.append(
        "- Next hypothesis must target the active bottleneck, preserve "
        "stable/protected objectives, and repeat avoid-tagged mechanisms only "
        "with new evidence or a materially different mechanism."
    )
    return "\n".join(lines)


def _active_bottleneck_line(screening_steps: list[StepRecord]) -> str:
    latest = next(
        (
            step
            for step in reversed(screening_steps)
            if step.protocol_result is not None
            and step.protocol_result.gate_outcome in {"fail", "continue", "unclear"}
        ),
        screening_steps[-1],
    )
    protocol = latest.protocol_result
    if protocol is None:
        return ""
    primary = _primary_screening_reason(latest)
    stats = protocol.stats
    if primary and "WIN_RATE" in primary.upper():
        return (
            "case win-rate/objective movement is insufficient "
            f"(primary_reason={primary}, case_win_rate={stats.win_rate:.2f}, "
            f"median_delta={stats.median_delta:.4f})."
        )
    if primary and (
        stats.candidate_failed_pairs
        or stats.failed_pairs
        or protocol.candidate_runtime_failure_categories
    ):
        return (
            "runtime/evaluation completion is the limiting signal "
            f"(primary_reason={primary}, failed_pairs={stats.failed_pairs}, "
            f"candidate_failed_pairs={stats.candidate_failed_pairs})."
        )
    if primary:
        return (
            f"screening gate did not pass (primary_reason={primary}, "
            f"case_win_rate={stats.win_rate:.2f}, "
            f"median_delta={stats.median_delta:.4f})."
        )
    return ""


def _objective_opportunity_lines(screening_steps: list[StepRecord]) -> list[str]:
    keys = (
        "n",
        "positive",
        "negative",
        "tie",
        "targeted_recently",
        "protected_recently",
        "recent_no_effect_targets",
    )
    stats_by_objective: dict[str, dict[str, int]] = defaultdict(
        lambda: {key: 0 for key in keys}
    )

    for step in screening_steps:
        protocol = step.protocol_result
        if protocol is None:
            continue
        targets = _objective_set(getattr(step.hypothesis, "target_objectives", ()))
        protected = _objective_set(
            getattr(step.hypothesis, "protected_objectives", ())
        )
        for name in targets:
            stats_by_objective[name]["targeted_recently"] += 1
        for name in protected:
            stats_by_objective[name]["protected_recently"] += 1
        for cf in protocol.case_feedback or ():
            for name, val in (getattr(cf, "median_deltas", {}) or {}).items():
                objective = str(name).strip()
                if not objective:
                    continue
                objective_stats = stats_by_objective[objective]
                objective_stats["n"] += 1
                numeric = _safe_float(val)
                if numeric > 1e-12:
                    objective_stats["positive"] += 1
                elif numeric < -1e-12:
                    objective_stats["negative"] += 1
                else:
                    objective_stats["tie"] += 1
        if _screening_step_has_no_objective_effect(step):
            for name in targets:
                stats_by_objective[name]["recent_no_effect_targets"] += 1

    lines: list[str] = []
    for objective, stats in sorted(stats_by_objective.items()):
        n = stats["n"]
        positive = stats["positive"]
        negative = stats["negative"]
        tie = stats["tie"]
        targeted = stats["targeted_recently"]
        protected = stats["protected_recently"]
        no_effect_targets = stats["recent_no_effect_targets"]
        if n <= 0 and not (targeted or protected):
            continue
        tags = _objective_tags(n, positive, negative, tie, protected, no_effect_targets)
        if not tags:
            continue
        guidance = ""
        if "stable/tie-dominated" in tags or protected or no_effect_targets:
            guidance = "; avoid unless new evidence, and treat as a preserve/no-op condition"
        lines.append(
            f"{objective}: {', '.join(tags)} "
            f"(positive={positive}, negative={negative}, tied={tie}, "
            f"targeted={targeted}, protected={protected}){guidance}."
        )
    return lines


def _objective_tags(
    n: int,
    positive: int,
    negative: int,
    tie: int,
    protected: int,
    no_effect_targets: int,
) -> list[str]:
    tags: list[str] = []
    tie_ratio = (tie / n) if n else 0.0
    if n and tie_ratio >= 0.8 and positive == 0 and negative == 0:
        tags.append("stable/tie-dominated")
    elif n and tie_ratio >= 0.8:
        tags.append("mostly tied")
    if protected:
        tags.append("protected_by_recent_hypotheses")
    if no_effect_targets:
        tags.append(f"recent_no_effect_targets={no_effect_targets}")
    return tags


def _recent_no_effect_mechanism_lines(
    screening_steps: list[StepRecord],
    taxonomy: Optional[list] = None,
) -> list[str]:
    lines: list[str] = []
    for step in reversed(screening_steps):
        if not _screening_step_has_no_objective_effect(step):
            continue
        protocol = step.protocol_result
        if protocol is None:
            continue
        pieces = [
            f"{_mechanism_label_for_feedback(step, taxonomy=taxonomy)} "
            f"(round {step.round_num})",
            "no observed objective effect",
            f"case_win_rate={protocol.stats.win_rate:.2f}",
        ]
        if targets := _objective_text(getattr(step.hypothesis, "target_objectives", ())):
            pieces.append(f"targets={targets}")
        if protected := _objective_text(
            getattr(step.hypothesis, "protected_objectives", ())
        ):
            pieces.append(f"protects={protected}")
        if reason := _primary_screening_reason(step):
            pieces.append(f"primary_reason={reason}")
        pieces.append(
            "repeat only with new evidence or a materially different mechanism"
        )
        lines.append("; ".join(pieces) + ".")
    return lines


def _screening_step_has_no_objective_effect(step: StepRecord) -> bool:
    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        return False
    stats = protocol.stats
    if (
        _safe_float(stats.win_rate) <= 0.0
        and abs(_safe_float(stats.median_delta)) <= 1e-12
    ):
        return True
    if stats.n_cases and stats.ties >= stats.n_cases:
        return abs(_safe_float(stats.median_delta)) <= 1e-12
    if any("tie" in str(code).lower() for code in protocol.reason_codes or ()):
        return abs(_safe_float(stats.median_delta)) <= 1e-12
    case_feedback = tuple(protocol.case_feedback or ())
    if not case_feedback:
        return False
    if not all(getattr(cf, "dominant_result", "") == "tie" for cf in case_feedback):
        return False
    deltas = [
        _safe_float(value)
        for cf in case_feedback
        for value in (getattr(cf, "median_deltas", {}) or {}).values()
    ]
    return not deltas or all(abs(value) <= 1e-12 for value in deltas)


def _primary_screening_reason(step: StepRecord) -> str:
    protocol = step.protocol_result
    if protocol is None:
        return ""
    primary = _choose_primary_reason(
        tuple(getattr(step, "decision_reason_codes", None) or ())
    )
    return primary or _choose_primary_reason(tuple(protocol.reason_codes or ()))


def _choose_primary_reason(reason_codes: tuple[str, ...]) -> str:
    cleaned = [str(code).strip() for code in reason_codes if str(code).strip()]
    if not cleaned:
        return ""
    for code in cleaned:
        upper = code.upper()
        if upper.startswith("SCREENING_FAIL") or "WIN_RATE" in upper:
            return code
    for code in cleaned:
        upper = code.upper()
        if (
            "RUNTIME" not in upper
            and "TELEMETRY" not in upper
            and "WARNING" not in upper
        ):
            return code
    return cleaned[0]


def _auxiliary_screening_reasons(
    step: StepRecord,
    primary_reason: str,
) -> list[str]:
    protocol = step.protocol_result
    if protocol is None:
        return []
    seen: set[str] = set()
    reasons: list[str] = []
    for code in protocol.reason_codes or ():
        text = str(code).strip()
        if not text or text == primary_reason or text in seen:
            continue
        seen.add(text)
        reasons.append(text)
    return reasons


def _mechanism_label_for_feedback(
    step: StepRecord,
    taxonomy: Optional[list] = None,
) -> str:
    changes = []
    for change in getattr(step.hypothesis, "mechanism_changes", ()) or ():
        value = change.get("id") if isinstance(change, Mapping) else getattr(change, "id", None)
        if text := str(value or "").strip():
            changes.append(text)
    if changes:
        return ", ".join(dict.fromkeys(changes))
    return extract_mechanism_label(
        step.hypothesis.hypothesis_text or "",
        taxonomy=taxonomy,
        preferred_label=step.hypothesis.change_locus,
    )


def _objective_set(values: Any) -> set[str]:
    return {str(item).strip() for item in values or () if str(item).strip()}


def _objective_text(values: Any) -> str:
    return ", ".join(sorted(_objective_set(values)))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
