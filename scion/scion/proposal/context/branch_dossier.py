"""Generic branch research dossier for proposal-time feedback.

The dossier is tainted research feedback. It summarizes branch-local evidence
for the next proposal, but it is not a Decision input.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any

from scion.core.models import (
    Branch,
    ExperimentStage,
    PatchFileChange,
    StepRecord,
    mechanism_changes,
)


def build_branch_dossier(
    branch: Branch,
    steps: list[StepRecord] | tuple[StepRecord, ...],
    *,
    max_timeline_items: int = 6,
) -> dict[str, Any]:
    branch_steps = [step for step in steps if step.branch_id == branch.branch_id]
    recent_steps = branch_steps[-max_timeline_items:]
    mechanisms = _mechanism_ids(branch, branch_steps)
    touched_files = _touched_files(branch_steps)
    runtime_diagnostics = _diagnostics(branch_steps, keywords=("RUNTIME", "BUDGET"))
    telemetry_diagnostics = _diagnostics(
        branch_steps,
        keywords=("TELEMETRY", "ACTIVATION", "EFFECT"),
    )
    return _drop_empty(
        {
            "schema_version": "branch_dossier.v1",
            "taint": "proposal_research_feedback",
            "decision_input_policy": "excluded_from_decision_features",
            "branch_id": branch.branch_id,
            "state": getattr(branch.state, "value", str(branch.state)),
            "direction": getattr(branch, "direction", None),
            "mechanisms": mechanisms,
            "touched_files": touched_files,
            "outcome_timeline": [
                _timeline_item(step) for step in recent_steps
            ],
            "best_screening_signal": _best_screening_signal(branch_steps),
            "zero_effect_streak": _zero_effect_streak(branch_steps),
            "runtime_budget_diagnostics": runtime_diagnostics,
            "telemetry_diagnostics": telemetry_diagnostics,
            "active_status": _active_status(branch),
            "suggested_next_research_questions": (
                _suggested_next_research_questions(
                    branch=branch,
                    runtime_diagnostics=runtime_diagnostics,
                    telemetry_diagnostics=telemetry_diagnostics,
                )
            ),
        }
    )


def render_branch_dossier(dossier: dict[str, Any]) -> str:
    if not dossier:
        return ""
    return (
        "This branch dossier is tainted proposal feedback for research "
        "planning only. It must not be treated as Decision input.\n"
        f"{json.dumps(dossier, indent=2, sort_keys=True, default=str)}"
    )


def _mechanism_ids(branch: Branch, steps: list[StepRecord]) -> list[str]:
    ids: list[str] = []
    for item in getattr(branch, "branch_mechanism_ids", ()) or ():
        _append_unique(ids, str(item).strip())
    for step in steps:
        for proposal in (step.hypothesis, step.patch):
            if proposal is None:
                continue
            for change in mechanism_changes(proposal):
                _append_unique(ids, str(change.id).strip())
    return ids[:12]


def _touched_files(steps: list[StepRecord]) -> list[str]:
    files: list[str] = []
    for step in steps:
        target = getattr(step.hypothesis, "target_file", None)
        _append_unique(files, _clean_path(target))
        patch = step.patch
        if patch is None:
            continue
        _append_unique(files, _clean_path(patch.file_path))
        for change in patch.additional_changes or ():
            if isinstance(change, PatchFileChange):
                _append_unique(files, _clean_path(change.file_path))
            elif isinstance(change, dict):
                _append_unique(files, _clean_path(change.get("file_path")))
            else:
                _append_unique(files, _clean_path(getattr(change, "file_path", "")))
    return files[:16]


def _timeline_item(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    stats = getattr(protocol, "stats", None) if protocol is not None else None
    return _drop_empty(
        {
            "round_num": step.round_num,
            "stage": (
                getattr(protocol.stage, "value", protocol.stage)
                if protocol is not None
                else step.failure_stage
            ),
            "target_file": getattr(step.hypothesis, "target_file", None),
            "action": getattr(step.hypothesis, "action", None),
            "decision": (
                getattr(step.decision, "value", step.decision)
                if step.decision is not None
                else None
            ),
            "gate_outcome": getattr(protocol, "gate_outcome", None),
            "reason_codes": list(_reason_codes(step)),
            "case_summary": (
                {
                    "wins": stats.wins,
                    "losses": stats.losses,
                    "ties": stats.ties,
                    "win_rate": stats.win_rate,
                    "median_delta": stats.median_delta,
                }
                if stats is not None
                else None
            ),
            "pair_summary": _pair_summary(protocol),
            "runtime_summary": _runtime_summary(stats),
        }
    )


def _best_screening_signal(steps: list[StepRecord]) -> dict[str, Any]:
    best: tuple[tuple[float, float, float, int], StepRecord] | None = None
    for step in steps:
        protocol = step.protocol_result
        if protocol is None or protocol.stage != ExperimentStage.SCREENING:
            continue
        stats = protocol.stats
        pair_summary = _pair_summary(protocol)
        rank = (
            float(stats.win_rate or 0.0),
            float(pair_summary.get("wins", 0)) / max(1, pair_summary.get("total", 0)),
            float(stats.median_delta or 0.0),
            step.round_num,
        )
        if best is None or rank > best[0]:
            best = (rank, step)
    if best is None:
        return {}
    step = best[1]
    protocol = step.protocol_result
    stats = protocol.stats
    return _drop_empty(
        {
            "round_num": step.round_num,
            "gate_outcome": protocol.gate_outcome,
            "reason_codes": list(_reason_codes(step)),
            "case_summary": {
                "wins": stats.wins,
                "losses": stats.losses,
                "ties": stats.ties,
                "win_rate": stats.win_rate,
                "median_delta": stats.median_delta,
            },
            "pair_summary": _pair_summary(protocol),
            "runtime_summary": _runtime_summary(stats),
        }
    )


def _zero_effect_streak(steps: list[StepRecord]) -> int:
    streak = 0
    for step in reversed(steps):
        protocol = step.protocol_result
        if protocol is None or protocol.stage != ExperimentStage.SCREENING:
            continue
        stats = protocol.stats
        pair_summary = _pair_summary(protocol)
        median_delta = float(stats.median_delta or 0.0)
        if (
            int(stats.wins or 0) == 0
            and int(stats.losses or 0) == 0
            and int(pair_summary.get("wins", 0)) == 0
            and int(pair_summary.get("losses", 0)) == 0
            and abs(median_delta) <= 1e-12
        ):
            streak += 1
            continue
        break
    return streak


def _diagnostics(
    steps: list[StepRecord],
    *,
    keywords: tuple[str, ...],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for step in steps:
        codes = [
            code
            for code in _reason_codes(step)
            if any(keyword in code.upper() for keyword in keywords)
        ]
        if not codes:
            continue
        items.append(
            {
                "round_num": step.round_num,
                "reason_codes": codes,
                "stage": (
                    getattr(step.protocol_result.stage, "value", step.protocol_result.stage)
                    if step.protocol_result is not None
                    else step.failure_stage
                ),
            }
        )
    return items[-8:]


def _active_status(branch: Branch) -> dict[str, Any]:
    return _drop_empty(
        {
            "branch_code_status": getattr(branch, "branch_code_status", None),
            "last_screening_feedback_tier": getattr(
                branch,
                "last_screening_feedback_tier",
                None,
            ),
            "last_telemetry_outcome": getattr(branch, "last_telemetry_outcome", None),
            "pending_retry": bool(getattr(branch, "pending_retry", False)),
            "branch_lifecycle_policy_blocks": getattr(
                branch,
                "branch_lifecycle_policy_blocks",
                0,
            ),
        }
    )


def _suggested_next_research_questions(
    *,
    branch: Branch,
    runtime_diagnostics: list[dict[str, Any]],
    telemetry_diagnostics: list[dict[str, Any]],
) -> list[str]:
    questions = [
        "Which observed signal should this follow-up preserve?",
        (
            "Which diagnostic suggests the mechanism is inactive, too late, "
            "too expensive, or too conservative?"
        ),
        "What minimal refinement should test the branch-local explanation?",
    ]
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if tier == "weak_positive":
        questions.append(
            "Which narrow change can preserve the weak positive signal while "
            "reducing neutral or losing cases?"
        )
    if runtime_diagnostics:
        questions.append(
            "Can the next hypothesis change the trigger, budget allocation, "
            "or observability before adding more expensive work?"
        )
    if telemetry_diagnostics:
        questions.append(
            "Is the mechanism absent from the active path, activated too late, "
            "or measured with insufficient effect telemetry?"
        )
    return questions


def _runtime_summary(stats: Any) -> dict[str, Any]:
    if stats is None:
        return {}
    return _drop_empty(
        {
            "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
            "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
            "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
            "runtime_pairs": getattr(stats, "runtime_pairs", 0),
        }
    )


def _pair_summary(protocol: Any) -> dict[str, int]:
    if protocol is None:
        return {}
    counts: Counter[str] = Counter()
    for item in getattr(protocol, "pair_feedback", ()) or ():
        comparison = str(getattr(item, "comparison", "tie") or "tie")
        if comparison not in {"win", "loss", "tie"}:
            comparison = "tie"
        counts[comparison] += 1
    if not counts:
        return {}
    return {
        "wins": counts["win"],
        "losses": counts["loss"],
        "ties": counts["tie"],
        "total": sum(counts.values()),
    }


def _reason_codes(step: StepRecord) -> tuple[str, ...]:
    codes: list[str] = []
    for code in getattr(step, "decision_reason_codes", None) or ():
        _append_unique(codes, str(code).strip())
    protocol = step.protocol_result
    for code in getattr(protocol, "reason_codes", ()) or ():
        _append_unique(codes, str(code).strip())
    return tuple(codes)


def _clean_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/")


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


__all__ = ["build_branch_dossier", "render_branch_dossier"]
