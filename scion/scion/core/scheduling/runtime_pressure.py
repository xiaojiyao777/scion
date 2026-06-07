"""Runtime evidence pressure helpers for scheduler resource policy."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_hygiene import branch_lineage_status


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
    if wins > 0 and losses == 0:
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


def _runtime_evidence_pressure_count(summary: Mapping[str, Any]) -> int:
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

