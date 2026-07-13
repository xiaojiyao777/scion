"""Artifact reference and protocol snapshot helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from scion.core.models import ProtocolResult, VerificationResult
from scion.core.public_refs import redact_public_refs

from .common import _drop_none, _optional_int, _stage_value


def _read_partial_metrics_snapshot(raw_ref: Any) -> dict[str, Any]:
    if raw_ref is None:
        return {}
    try:
        path = Path(str(raw_ref))
    except TypeError:
        return {}
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, Mapping):
        return {}
    snapshot = {
        key: data[key]
        for key in (
            "stage",
            "complete",
            "total_pairs",
            "attempted_pairs",
            "valid_pairs",
            "failed_pairs",
            "candidate_failed_pairs",
            "champion_failed_pairs",
            "runtime_confidence",
            "runtime_evidence_status",
            "runtime_evidence_policy",
            "runtime_gate_visibility",
            "champion_cached_runtime_pairs",
        )
        if key in data
    }
    surface_summary = data.get("candidate_surface_runtime_summary")
    if isinstance(surface_summary, Mapping):
        diagnostic = surface_summary.get("runtime_budget_diagnostic")
        if isinstance(diagnostic, Mapping):
            snapshot["runtime_budget_diagnostic"] = dict(diagnostic)
            code = str(diagnostic.get("code") or "").strip()
            if code:
                snapshot["runtime_budget_diagnostic_code"] = code
    return snapshot


def _in_flight_protocol_snapshot(progress: Mapping[str, Any]) -> dict[str, Any]:
    stage = str(progress.get("stage") or "").strip()
    phase = str(progress.get("phase") or "").strip()
    raw_metrics_ref = progress.get("raw_metrics_ref")
    target_file = progress.get("target_file")
    hypothesis_action = progress.get("hypothesis_action")
    complete = bool(progress.get("complete", False))
    snapshot = {
        "phase": phase or (f"formal_{stage}" if stage else "formal_protocol"),
        "protocol_state": progress.get(
            "protocol_state",
            "complete" if complete else "running",
        ),
        "stage": stage or None,
        "branch_id": progress.get("branch_id"),
        "candidate": _drop_none(
            {
                "branch_id": progress.get("branch_id"),
                "target_file": target_file,
                "hypothesis_action": hypothesis_action,
            }
        ),
        "hypothesis": _drop_none(
            {
                "text": progress.get("hypothesis_text"),
                "action": hypothesis_action,
                "target_file": target_file,
            }
        ),
        "partial_metrics_ref": raw_metrics_ref,
        "partial_metrics_ref_scope": progress.get("raw_metrics_ref_scope"),
        "partial_metrics_internal_only": progress.get("raw_metrics_internal_only"),
        "attempted_pairs": _optional_int(progress.get("attempted_pairs")),
        "total_pairs": _optional_int(progress.get("total_pairs")),
        "valid_pairs": _optional_int(
            progress.get("valid_pairs", progress.get("completed_pairs"))
        ),
        "failed_pairs": _optional_int(progress.get("failed_pairs")),
        "candidate_failed_pairs": _optional_int(
            progress.get("candidate_failed_pairs")
        ),
        "champion_failed_pairs": _optional_int(progress.get("champion_failed_pairs")),
        "complete": complete,
        "decision_formed": False,
        "counts_toward_n_experiments": False,
        "child_pid": _optional_int(progress.get("child_pid")),
        "child_exit_code": _optional_int(progress.get("child_exit_code")),
        "child_elapsed_ms": _optional_int(progress.get("child_elapsed_ms")),
        "child_phase": progress.get("child_phase"),
        "runtime_budget_diagnostic": (
            dict(progress["runtime_budget_diagnostic"])
            if isinstance(progress.get("runtime_budget_diagnostic"), Mapping)
            else None
        ),
        "runtime_budget_diagnostic_code": progress.get(
            "runtime_budget_diagnostic_code"
        ),
        "last_case": progress.get("last_case", progress.get("case")),
        "last_seed": progress.get("last_seed", progress.get("seed")),
        "step_started_at": progress.get("step_started_at"),
        "last_progress_at": progress.get("last_progress_at"),
    }
    return _drop_none(snapshot)



def _audit_check_detail(detail: Any, *, base_dir: str | Path | None = None) -> str:
    text = str(detail or "")
    redacted = redact_public_refs(text, base_dir=base_dir)
    return str(redacted)


def _serialize_verification_checks(
    verification_result: VerificationResult,
    *,
    base_dir: str | Path | None = None,
) -> list[Dict[str, Any]]:
    return [
        {
            "name": check.name,
            "passed": check.passed,
            "severity": check.severity,
            "detail": _audit_check_detail(check.detail, base_dir=base_dir),
            "elapsed_ms": check.elapsed_ms,
            "metadata": dict(check.metadata or {}),
        }
        for check in verification_result.checks
    ]


def _extract_runtime_guard_evidence(
    verification_result: VerificationResult,
) -> Dict[str, Any]:
    for check in verification_result.checks:
        if check.name == "V9_perf_guard":
            return {
                "passed": check.passed,
                "detail": check.detail,
                "elapsed_ms": check.elapsed_ms,
                "metadata": dict(check.metadata or {}),
            }
    return {}


def _extract_protocol_runtime_stats(
    protocol_result: ProtocolResult | None,
) -> Dict[str, Any]:
    if protocol_result is None:
        return {
            "runtime_ratio_median": None,
            "runtime_delta_median_ms": None,
            "runtime_regression_rate": None,
            "runtime_pairs": 0,
        }
    stats = protocol_result.stats
    return {
        "runtime_ratio_median": stats.runtime_ratio_median,
        "runtime_delta_median_ms": stats.runtime_delta_median_ms,
        "runtime_regression_rate": stats.runtime_regression_rate,
        "runtime_pairs": stats.runtime_pairs,
        "total_pairs": stats.total_pairs,
        "attempted_pairs": stats.attempted_pairs,
        "valid_pairs": stats.valid_pairs,
        "failed_pairs": stats.failed_pairs,
        "candidate_failed_pairs": stats.candidate_failed_pairs,
        "champion_failed_pairs": stats.champion_failed_pairs,
    }



def _screening_pair_counts(protocol_result: ProtocolResult | None) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    wins = losses = ties = 0
    for feedback in protocol_result.pair_feedback or ():
        comparison = str(getattr(feedback, "comparison", "") or "")
        if comparison == "win":
            wins += 1
        elif comparison == "loss":
            losses += 1
        else:
            ties += 1
    total = wins + losses + ties
    return {
        "screening_pair_wins": wins,
        "screening_pair_losses": losses,
        "screening_pair_ties": ties,
        "screening_pair_total": total,
        "screening_pair_win_rate": wins / total if total else 0.0,
    }


def _screening_rate_fields(
    protocol_result: ProtocolResult | None,
) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    stats = protocol_result.stats
    wins = stats.wins
    losses = stats.losses
    ties = stats.ties
    total = wins + losses + ties
    win_rate = stats.win_rate
    return {
        "screening_case_wins": wins,
        "screening_case_losses": losses,
        "screening_case_ties": ties,
        "screening_case_total": total,
        "screening_case_win_rate": win_rate,
        "screening_case_level_gate_wins": wins,
        "screening_case_level_gate_losses": losses,
        "screening_case_level_gate_ties": ties,
        "screening_case_level_gate_total": total,
        "screening_case_level_gate_win_rate": win_rate,
        "screening_gate_win_rate": win_rate,
        "screening_win_rate": win_rate,
        "screening_win_rate_scope": "case_level_gate",
        **_screening_pair_counts(protocol_result),
    }
