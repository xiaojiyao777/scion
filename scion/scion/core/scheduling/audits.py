"""Scheduler audit metadata builders for resource-policy decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from scion.core.branch_hygiene import branch_lineage_status
from scion.core.models import Branch
from scion.core.scheduling.runtime_pressure import (
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    _runtime_aggregate_excluded,
    _runtime_evidence_low_or_incomplete,
    _runtime_evidence_pressure_count,
    _runtime_evidence_pressure_triggers,
    _summary_nonnegative_int,
    _summary_text,
    branch_runtime_evidence_clean_fork_pressure_summary,
)
from scion.core.scheduling.signals import (
    LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON,
    PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
    PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON,
    SAME_BRANCH_REFINEMENT_SAMPLE_REASON,
    activation_zero_effect_streak,
    branch_plateau_gate,
    branch_plateau_gate_same_branch_candidate,
    branch_runtime_evidence_pressure_preferred,
    branch_same_branch_refinement_sampling_candidate,
    branch_screening_tier,
    branch_state_value,
    gate_nonnegative_int,
    low_value_active_slot_candidate_reason,
    no_effect_followup_count,
    same_branch_refinement_sampling_signal,
    weak_positive_followup_not_selected_reason,
    branch_has_weak_positive_followup_signal,
)


_LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_RELEASE_REASONS = frozenset(
    {
        "repeated_no_effect_zero_effect_slot_release",
        "retained_checkpoint_no_effect_current_head",
    }
)


def clean_fork_selection_audit(
    branches: Iterable[Branch],
    *,
    reason: str,
) -> dict[str, Any]:
    branch_list = list(branches)
    audit = weak_positive_followup_suppression_audit(
        branch_list,
        selected_policy="clean_fork_selected",
        selected_reason=reason,
    )
    pressure_candidates: list[dict[str, Any]] = []
    pressure_count_max = 0
    for branch in branch_list:
        summary = branch_runtime_evidence_clean_fork_pressure_summary(branch)
        if not summary and not branch_runtime_evidence_pressure_preferred(branch):
            continue
        evidence_summary = getattr(branch, "branch_evidence_summary", {}) or {}
        if isinstance(evidence_summary, Mapping):
            pressure_count = _runtime_evidence_pressure_count(evidence_summary)
            pressure_count_max = max(pressure_count_max, pressure_count)
        else:
            pressure_count = 0
        candidate = {
            "branch_id": str(getattr(branch, "branch_id", "") or ""),
            "lineage_status": branch_lineage_status(branch),
            "runtime_evidence_pressure_count": pressure_count,
            "runtime_evidence_pressure_triggers": (
                _runtime_evidence_pressure_triggers(evidence_summary)
                if isinstance(evidence_summary, Mapping)
                else []
            ),
        }
        if summary:
            candidate.update(
                {
                    "case_wins": summary.get("case_wins", 0),
                    "case_losses": summary.get("case_losses", 0),
                    "case_balance": summary.get("case_balance", "unknown"),
                    "runtime_evidence_confidence": summary.get(
                        "runtime_evidence_confidence",
                        "unknown",
                    ),
                    "runtime_evidence_status": summary.get(
                        "runtime_evidence_status",
                        "unknown",
                    ),
                }
            )
        pressure_candidates.append(candidate)
    if pressure_candidates:
        audit.update(
            {
                "runtime_evidence_clean_fork_selected": True,
                "runtime_evidence_clean_fork_reason": reason,
                "runtime_evidence_clean_fork_candidate_count": len(
                    pressure_candidates
                ),
                "runtime_evidence_pressure_count_max": pressure_count_max,
                "runtime_evidence_clean_fork_candidates": pressure_candidates[:8],
            }
        )
    plateau_candidates = plateau_gate_clean_fork_candidates(branch_list)
    if plateau_candidates:
        material_requirement = material_difference_requirement_record(
            reason=PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
            source="plateau_gate",
            required_for="clean_fork_new_branch",
            candidate_count=len(plateau_candidates),
            candidate_branch_ids=[
                str(candidate.get("branch_id") or "")
                for candidate in plateau_candidates
                if str(candidate.get("branch_id") or "").strip()
            ],
        )
        audit.update(
            {
                "plateau_gate_clean_fork_selected": True,
                "plateau_gate_reason": PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
                "material_difference_required": True,
                "material_difference_required_for": "clean_fork_new_branch",
                "material_difference_requirement": material_requirement,
                "material_difference_audit_records": [material_requirement],
                "plateau_gate_clean_fork_candidate_count": len(
                    plateau_candidates
                ),
                "plateau_gate_clean_fork_candidates": plateau_candidates[:8],
            }
        )
    low_value_candidates = low_value_clean_fork_material_difference_candidates(
        branch_list
    )
    if low_value_candidates and not audit.get("material_difference_required"):
        material_requirement = material_difference_requirement_record(
            reason=LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON,
            source="low_value_clean_fork_pressure",
            required_for="clean_fork_new_branch",
            candidate_count=len(low_value_candidates),
            candidate_branch_ids=[
                str(candidate.get("branch_id") or "")
                for candidate in low_value_candidates
                if str(candidate.get("branch_id") or "").strip()
            ],
        )
        audit.update(
            {
                "low_value_clean_fork_material_difference_selected": True,
                "low_value_clean_fork_material_difference_reason": (
                    LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_REASON
                ),
                "material_difference_required": True,
                "material_difference_required_for": "clean_fork_new_branch",
                "material_difference_requirement": material_requirement,
                "material_difference_audit_records": [material_requirement],
                "low_value_clean_fork_material_difference_candidate_count": len(
                    low_value_candidates
                ),
                "low_value_clean_fork_material_difference_candidates": (
                    low_value_candidates[:8]
                ),
            }
        )
    return audit


def material_difference_requirement_record(
    *,
    reason: str,
    source: str,
    required_for: str,
    candidate_count: int,
    candidate_branch_ids: Iterable[str],
) -> dict[str, Any]:
    if source == "plateau_gate":
        reason_codes = [
            "PLATEAU_GATE_THRESHOLD_MET",
            "PLATEAU_GATE_CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE",
        ]
    else:
        reason_codes = [
            "LOW_VALUE_CLEAN_FORK_PRESSURE",
            "CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE",
        ]
    stable_payload = {
        "schema_version": "material_difference_requirement.v1",
        "record_type": "material_difference_requirement",
        "requirement_source": str(source),
        "reason": str(reason),
        "reason_codes": reason_codes,
        "required_for": str(required_for),
        "required_metadata_key": "material_difference_required",
        "candidate_count": max(0, int(candidate_count)),
        "candidate_branch_ids": sorted(
            str(branch_id)
            for branch_id in candidate_branch_ids
            if str(branch_id).strip()
        ),
        "proposal_visibility_only": True,
        "proposal_guidance_only": True,
        "audit_only": True,
        "decision_features_excluded": True,
    }
    digest_input = json.dumps(
        stable_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    stable_payload["record_digest"] = f"sha256:{digest}"
    stable_payload["record_id"] = f"material_difference_requirement:{digest[:16]}"
    return stable_payload


def low_value_active_slot_release_audit(
    branches: Iterable[Branch],
) -> dict[str, Any]:
    candidates = [
        summary
        for branch in branches
        for summary in (low_value_active_slot_release_summary(branch),)
        if summary
    ]
    if not candidates:
        return {}
    return {
        "low_value_active_slot_release": True,
        "low_value_active_slot_release_policy": (
            "audit_low_value_current_head_without_scheduler_lifecycle_change"
        ),
        "low_value_active_slot_release_candidate_count": len(candidates),
        "low_value_active_slot_release_candidates": candidates[:8],
        "proposal_guidance_only": True,
        "decision_features_excluded": True,
    }


def low_value_clean_fork_material_difference_candidates(
    branches: Iterable[Branch],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in branches:
        release_reason = low_value_active_slot_candidate_reason(branch)
        if (
            release_reason
            not in _LOW_VALUE_CLEAN_FORK_MATERIAL_DIFFERENCE_RELEASE_REASONS
        ):
            continue
        if (
            release_reason != "retained_checkpoint_no_effect_current_head"
            and branch_same_branch_refinement_sampling_candidate(branch)
        ):
            continue
        summary = low_value_active_slot_release_summary(branch)
        if summary:
            candidates.append(summary)
    return candidates


def plateau_gate_clean_fork_candidates(
    branches: Iterable[Branch],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in branches:
        gate = branch_plateau_gate(branch)
        if not gate or not bool(gate.get("threshold_met")):
            continue
        if branch_plateau_gate_same_branch_candidate(branch):
            continue
        candidates.append(
            {
                "branch_id": str(getattr(branch, "branch_id", "") or ""),
                "lineage_status": branch_lineage_status(branch),
                "branch_state": branch_state_value(branch),
                "branch_code_status": str(
                    getattr(branch, "branch_code_status", "") or ""
                ),
                "screening_tier": branch_screening_tier(branch)
                or str(gate.get("tier") or "unknown"),
                "effective_screened_no_effect_count": gate_nonnegative_int(
                    gate,
                    "effective_screened_no_effect_count",
                ),
                "runtime_evidence_pressure_count": gate_nonnegative_int(
                    gate,
                    "runtime_evidence_pressure_count",
                ),
                "scheduler_preference": str(
                    gate.get("scheduler_preference") or ""
                ),
                "plateau_gate_reason_codes": [
                    str(code)
                    for code in gate.get("reason_codes", ())
                    if str(code).strip()
                ],
            }
        )
    return candidates


def low_value_active_slot_release_summary(branch: Branch) -> dict[str, Any]:
    reason = low_value_active_slot_candidate_reason(branch)
    if not reason:
        return {}
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    return {
        "branch_id": str(getattr(branch, "branch_id", "") or ""),
        "lineage_status": branch_lineage_status(branch),
        "branch_state": branch_state_value(branch),
        "branch_code_status": str(getattr(branch, "branch_code_status", "") or ""),
        "screening_tier": branch_screening_tier(branch)
        or _summary_text(evidence, "tier", default="unknown"),
        "release_reason": reason,
        "case_wins": _summary_nonnegative_int(evidence, "wins"),
        "case_losses": _summary_nonnegative_int(evidence, "losses"),
        "activation_zero_effect_streak": activation_zero_effect_streak(branch),
        "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(evidence),
    }


def weak_positive_runtime_evidence_suppression_audit(
    branch: Branch,
) -> dict[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return {}
    pressure_count = _runtime_evidence_pressure_count(summary)
    if pressure_count < 2 or not _runtime_evidence_low_or_incomplete(summary):
        return {}
    wins = _summary_nonnegative_int(summary, "wins")
    losses = _summary_nonnegative_int(summary, "losses")
    if wins <= 0 or losses != 0:
        return {}
    return {
        "runtime_evidence_clean_fork_suppression": "weak_positive_exception",
        "runtime_evidence_clean_fork_reason": (
            RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
        ),
        "runtime_evidence_pressure_count": pressure_count,
        "case_wins": wins,
        "case_losses": losses,
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
    }


def same_branch_refinement_sampling_audit(
    branch: Branch,
    *,
    candidate_count: int,
) -> dict[str, Any]:
    reason = same_branch_refinement_sampling_signal(branch)
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    gate = branch_plateau_gate(branch)
    audit = {
        "same_branch_refinement_selected": True,
        "same_branch_refinement_reason": (
            reason or SAME_BRANCH_REFINEMENT_SAMPLE_REASON
        ),
        "same_branch_refinement_sampling": True,
        "same_branch_refinement_sampling_reason": (
            reason or SAME_BRANCH_REFINEMENT_SAMPLE_REASON
        ),
        "same_branch_refinement_sampling_candidate_count": max(
            0,
            int(candidate_count),
        ),
        "clean_fork_suppressed_for_same_branch_sample": True,
        "same_branch_refinement_sampling_candidate": {
            "branch_id": str(getattr(branch, "branch_id", "") or ""),
            "lineage_status": branch_lineage_status(branch),
            "branch_state": branch_state_value(branch),
            "branch_code_status": str(
                getattr(branch, "branch_code_status", "") or ""
            ),
            "screening_tier": branch_screening_tier(branch)
            or _summary_text(evidence, "tier", default="unknown"),
            "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(
                evidence
            ),
            "activation_zero_effect_streak": activation_zero_effect_streak(
                branch
            ),
            "lifecycle_no_effect_diagnostic_followups": no_effect_followup_count(
                branch
            ),
            "runtime_evidence_pressure_triggers": (
                _runtime_evidence_pressure_triggers(evidence)
            ),
        },
    }
    if gate:
        audit.update(
            {
                "plateau_gate_same_branch_refinement_selected": True,
                "plateau_gate_reason": PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON,
                "plateau_gate_reason_codes": [
                    str(code)
                    for code in gate.get("reason_codes", ())
                    if str(code).strip()
                ],
                "plateau_gate": {
                    "schema_version": str(
                        gate.get("schema_version") or "plateau_gate.v1"
                    ),
                    "tier": str(gate.get("tier") or "unknown"),
                    "threshold_met": bool(gate.get("threshold_met")),
                    "effective_screened_no_effect_count": gate_nonnegative_int(
                        gate,
                        "effective_screened_no_effect_count",
                    ),
                    "runtime_evidence_pressure_count": gate_nonnegative_int(
                        gate,
                        "runtime_evidence_pressure_count",
                    ),
                    "scheduler_preference": str(
                        gate.get("scheduler_preference") or ""
                    ),
                    "proposal_guidance_only": True,
                    "audit_only": True,
                    "decision_features_excluded": True,
                },
                "same_branch_refinement_allowed_actions": [
                    str(item)
                    for item in gate.get("allowed_same_branch_actions", ())
                    if str(item).strip()
                ],
            }
        )
    return audit


def weak_positive_followup_suppression_audit(
    branches: Iterable[Branch],
    *,
    selected_policy: str,
    selected_reason: str,
) -> dict[str, Any]:
    suppressed: list[dict[str, Any]] = []
    for branch in branches:
        if not branch_has_weak_positive_followup_signal(branch):
            continue
        suppression_reason = weak_positive_followup_not_selected_reason(branch)
        if not suppression_reason:
            continue
        suppressed.append(
            {
                "branch_id": str(getattr(branch, "branch_id", "") or ""),
                "lineage_status": branch_lineage_status(branch),
                "branch_state": branch_state_value(branch),
                "branch_code_status": str(
                    getattr(branch, "branch_code_status", "") or ""
                ),
                "screening_tier": branch_screening_tier(branch),
                "reason": suppression_reason,
                "runtime_evidence_pressure_count": _runtime_evidence_pressure_count(
                    getattr(branch, "branch_evidence_summary", {}) or {}
                )
                if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
                else 0,
            }
        )
    if not suppressed:
        return {}
    return {
        "weak_positive_followup_suppressed": True,
        "weak_positive_followup_suppression_reason": selected_reason,
        "weak_positive_followup_suppression_selected_policy": selected_policy,
        "weak_positive_followup_suppression_audit": suppressed[:8],
    }
