"""Runtime evidence pressure helpers for scheduler resource policy."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_hygiene import branch_lineage_status
from scion.core.runtime_budget_diagnostics import runtime_model_from_summary


RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON = (
    "runtime_evidence_completeness_clean_fork"
)


def branch_runtime_evidence_clean_fork_pressure_summary(
    branch: Any | None,
) -> dict[str, Any]:
    if branch is None or not _branch_is_weak_positive_lineage(branch):
        return {}
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    pressure_count = _runtime_evidence_pressure_count(summary)
    if pressure_count < 2 or not _runtime_evidence_low_or_incomplete(summary):
        return {}
    wins = _summary_nonnegative_int(summary, "wins")
    losses = _summary_nonnegative_int(summary, "losses")
    if current_weak_positive_without_case_loss(branch):
        return {}
    return {
        "reason": RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
        "policy": "prefer_clean_fork",
        "runtime_evidence_pressure_count": pressure_count,
        "case_wins": wins,
        "case_losses": losses,
        "case_balance": "case_loss" if losses > 0 else "no_case_win",
        "runtime_evidence_confidence": _summary_text(
            summary,
            "runtime_evidence_confidence",
            default="unknown",
        ),
        "runtime_evidence_status": _summary_text(
            summary,
            "runtime_evidence_status",
            default="unknown",
        ),
        "runtime_aggregate_excluded": _runtime_aggregate_excluded(summary),
        "runtime_evidence_pressure_triggers": _runtime_evidence_pressure_triggers(
            summary
        ),
        "tainted_proposal_guidance": True,
        "decision_features_excluded": True,
    }


def _branch_is_weak_positive_lineage(branch: Any) -> bool:
    return branch_lineage_status(branch) in {
        "active_weak_positive",
        "restored_weak_positive",
    }


def current_weak_positive_without_case_loss(branch: Any | None) -> bool:
    if branch is None or not _branch_is_weak_positive_lineage(branch):
        return False
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        summary = {}
    if _summary_nonnegative_int(summary, "losses") > 0:
        return False
    return (
        _summary_nonnegative_int(summary, "wins") > 0
        or _summary_nonnegative_int(summary, "pair_wins") > 0
        or _explicit_current_weak_positive_signal(branch, summary)
    )


def _explicit_current_weak_positive_signal(
    branch: Any,
    summary: Mapping[str, Any],
) -> bool:
    tier = _explicit_current_evidence_tier(branch, summary)
    if tier:
        return tier == "weak_positive"
    return _branch_current_status_is_weak_positive(branch)


def _explicit_current_evidence_tier(
    branch: Any,
    summary: Mapping[str, Any],
) -> str:
    tier = _summary_text(summary, "tier").lower()
    if tier:
        return tier
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "").strip()
    return tier.lower()


def _branch_current_status_is_weak_positive(branch: Any) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "").strip().lower()
    return status in {"active_weak_positive", "restored_weak_positive"}


def _runtime_evidence_pressure_count(summary: Mapping[str, Any]) -> int:
    if not runtime_evidence_pressure_applicable(summary):
        return 0
    try:
        return max(0, int(summary.get("runtime_evidence_pressure_count") or 0))
    except (TypeError, ValueError):
        return 0


def _summary_nonnegative_int(summary: Mapping[str, Any], key: str) -> int:
    try:
        return max(0, int(summary.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _summary_text(
    summary: Mapping[str, Any],
    key: str,
    *,
    default: str = "",
) -> str:
    value = str(summary.get(key) or "").strip()
    return value if value else default


def _runtime_evidence_low_or_incomplete(summary: Mapping[str, Any]) -> bool:
    confidence = _summary_text(summary, "runtime_evidence_confidence").lower()
    status = _summary_text(summary, "runtime_evidence_status").lower()
    return (
        _runtime_aggregate_excluded(summary)
        or confidence.startswith("low")
        or confidence
        in {"incomplete", "insufficient", "missing", "none", "unknown"}
        or status
        in {
            "fresh_required",
            "fresh_champion_required",
            "incomplete",
            "insufficient",
            "missing",
            "none",
            "unknown",
        }
        or "incomplete" in status
        or "insufficient" in status
    )


def _runtime_aggregate_excluded(summary: Mapping[str, Any]) -> bool:
    exclusion = summary.get("runtime_aggregate_exclusion")
    if isinstance(exclusion, Mapping):
        if "excluded" in exclusion:
            return bool(exclusion.get("excluded"))
        return bool(exclusion)
    return bool(exclusion)


def _runtime_evidence_pressure_triggers(summary: Mapping[str, Any]) -> list[str]:
    if not runtime_evidence_pressure_applicable(summary):
        return []
    pressure = summary.get("runtime_evidence_pressure")
    if isinstance(pressure, Mapping):
        triggers = pressure.get("triggers")
        if isinstance(triggers, list):
            return [str(item) for item in triggers if str(item).strip()]
    triggers: list[str] = []
    confidence = _summary_text(summary, "runtime_evidence_confidence").lower()
    status = _summary_text(summary, "runtime_evidence_status").lower()
    if confidence.startswith("low") or "cached" in confidence:
        triggers.append("low_or_cached_runtime_confidence")
    if status in {
        "fresh_required",
        "fresh_champion_required",
        "incomplete",
        "insufficient",
        "missing",
        "unknown",
    }:
        triggers.append(f"runtime_evidence_status:{status}")
    if _runtime_aggregate_excluded(summary):
        triggers.append("runtime_aggregate_excluded")
    return list(dict.fromkeys(triggers))


def runtime_evidence_pressure_applicable(summary: Mapping[str, Any]) -> bool:
    return _runtime_evidence_pressure_runtime_model(summary) != "budget_exhausting"


def _runtime_evidence_pressure_runtime_model(summary: Mapping[str, Any]) -> str:
    runtime_model = runtime_model_from_summary(summary, default="")
    if runtime_model:
        return runtime_model
    policy = summary.get("runtime_evidence_policy")
    if isinstance(policy, Mapping):
        return runtime_model_from_summary(policy, default="")
    return ""
