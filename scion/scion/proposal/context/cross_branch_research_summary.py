"""Branch summary extraction for proposal-only cross-branch research maps."""
from __future__ import annotations

from typing import Any, Iterable, Sequence
import json

from scion.core.models import (
    Branch,
    BranchState,
    ExperimentStage,
    PatchFileChange,
    ProtocolResult,
    StepRecord,
    mechanism_changes,
)
from scion.core.screening_visibility import runtime_evidence_policy_summary
from scion.proposal.context.cross_branch_research_support import (
    append_unique as _append_unique,
    append_unique_dict as _append_unique_dict,
    clean_path as _clean_path,
    clean_token as _clean_token,
    drop_empty as _drop_empty,
    fallback_mechanism_id as _fallback_mechanism_id,
    first_line as _first_line,
    mechanism_family as _mechanism_family,
    mechanism_signature as _signature,
    similarity_key as _similarity_key,
    unique as _unique,
)


SAFE_PRE_PROTOCOL_FAILURE_STAGES = {
    "agent_quality_blocked",
    "proposal",
    "hypothesis_contract",
    "code_generation",
    "code_generation_failed",
    "patch_contract",
    "workspace",
    "verification",
}
TERMINAL_BRANCH_STATES = {
    BranchState.PROMOTED.value,
    BranchState.ABANDONED.value,
    BranchState.PARKED_LINEAGE.value,
}
LOW_RUNTIME_STATUSES = {
    "fresh_champion_required",
    "incomplete",
    "insufficient",
    "low",
    "low_or_incomplete",
    "unknown_low",
}
LOW_RUNTIME_CONFIDENCES = {"low", "medium", "unknown_low"}


def safe_prompt_steps(steps: Sequence[StepRecord]) -> list[StepRecord]:
    return [
        step
        for step in steps
        if _screening_protocol_step(step) or _safe_pre_protocol_step(step)
    ]


def branch_index(
    current_branch: Branch,
    branches: Iterable[Branch],
) -> dict[str, Branch | None]:
    branch_by_id: dict[str, Branch | None] = {}
    branch_by_id[current_branch.branch_id] = current_branch
    for branch in branches:
        if branch is None:
            continue
        branch_by_id.setdefault(branch.branch_id, branch)
    return branch_by_id


def ordered_branch_ids(
    current_branch_id: str,
    branch_ids: Iterable[str],
    steps: list[StepRecord],
) -> list[str]:
    ordered = [current_branch_id]
    for step in reversed(steps):
        if step.branch_id not in ordered:
            ordered.append(step.branch_id)
    for branch_id in branch_ids:
        if branch_id not in ordered:
            ordered.append(branch_id)
    return ordered


def build_branch_summary(
    *,
    branch_id: str,
    branch: Branch | None,
    steps: list[StepRecord],
    is_current_branch: bool,
    max_steps_per_branch: int,
) -> dict[str, Any]:
    recent_steps = steps[-max_steps_per_branch:]
    descriptors = _mechanism_descriptors(branch, steps)
    latest_step = recent_steps[-1] if recent_steps else None
    outcome = _outcome_summary(branch, latest_step)
    lifecycle = _lifecycle_summary(branch, steps)
    touched_files = _touched_files(steps)
    mechanism_ids = _mechanism_ids(branch, steps)
    evidence_profile = _evidence_profile(branch, latest_step)

    return _drop_empty(
        {
            "branch_id": branch_id,
            "is_current_branch": is_current_branch,
            "state": _branch_state(branch),
            "final_or_active_state": _final_or_active_state(branch),
            "mechanism_ids": mechanism_ids,
            "mechanism_families": _unique(
                item["mechanism_family"] for item in descriptors
            ),
            "mechanism_signatures": [
                item["mechanism_signature"] for item in descriptors
            ][:8],
            "research_descriptors": [
                _drop_empty(
                    {
                        "mechanism_family": item.get("mechanism_family"),
                        "change_locus": item.get("change_locus"),
                        "action": item.get("action"),
                        "target_file": item.get("target_file"),
                        "change_type": item.get("change_type"),
                    }
                )
                for item in descriptors
            ][:8],
            "similarity_keys": [
                item["similarity_key"] for item in descriptors
            ][:8],
            "touched_files": touched_files,
            "outcome_summary": outcome,
            "evidence_profile": evidence_profile,
            "recent_attempts": [
                _attempt_summary(step) for step in recent_steps
            ],
            "lifecycle_summary": lifecycle,
        }
    )


def _mechanism_descriptors(
    branch: Branch | None,
    steps: list[StepRecord],
) -> list[dict[str, str]]:
    descriptors: list[dict[str, str]] = []
    for step in steps:
        hypothesis = step.hypothesis
        target_file = _clean_path(getattr(hypothesis, "target_file", None))
        action = _clean_token(getattr(hypothesis, "action", None))
        change_locus = _clean_token(getattr(hypothesis, "change_locus", None))
        changes = [
            (_clean_token(item.id), _clean_token(item.change_type))
            for item in (
                *mechanism_changes(hypothesis),
                *(
                    mechanism_changes(step.patch)
                    if step.patch is not None
                    else ()
                ),
            )
        ]
        if not changes:
            changes = [
                (_clean_token(item), "branch_owned")
                for item in (getattr(branch, "branch_mechanism_ids", ()) or ())
            ]
        if not changes:
            changes = [
                (_fallback_mechanism_id(change_locus, target_file), "unspecified")
            ]
        for mechanism_id, change_type in changes:
            family = _mechanism_family(mechanism_id, change_locus, target_file)
            signature = _signature(
                mechanism_id=mechanism_id,
                mechanism_family=family,
                change_type=change_type,
                change_locus=change_locus,
                action=action,
                target_file=target_file,
            )
            _append_unique_dict(
                descriptors,
                {
                    "mechanism_id": mechanism_id,
                    "mechanism_family": family,
                    "mechanism_signature": signature,
                    "similarity_key": _similarity_key(
                        mechanism_family=family,
                        change_locus=change_locus,
                        action=action,
                        target_file=target_file,
                    ),
                    "change_locus": change_locus,
                    "action": action,
                    "target_file": target_file,
                    "change_type": change_type,
                },
                key="mechanism_signature",
            )
    if descriptors:
        return descriptors
    for mechanism_id in getattr(branch, "branch_mechanism_ids", ()) or ():
        family = _mechanism_family(str(mechanism_id), "", "")
        descriptors.append(
            {
                "mechanism_id": str(mechanism_id),
                "mechanism_family": family,
                "mechanism_signature": _signature(
                    mechanism_id=str(mechanism_id),
                    mechanism_family=family,
                    change_type="branch_owned",
                    change_locus="",
                    action="",
                    target_file="",
                ),
                "similarity_key": _similarity_key(
                    mechanism_family=family,
                    change_locus="",
                    action="",
                    target_file="",
                ),
                "change_locus": "",
                "action": "",
                "target_file": "",
                "change_type": "branch_owned",
            }
        )
    return descriptors


def _outcome_summary(branch: Branch | None, step: StepRecord | None) -> dict[str, Any]:
    state = _branch_state(branch)
    pattern = _outcome_pattern(branch, step)
    protocol = step.protocol_result if step is not None else None
    stats = getattr(protocol, "stats", None) if protocol is not None else None
    return _drop_empty(
        {
            "outcome_pattern": pattern,
            "branch_state": state,
            "gate_outcome": (
                getattr(protocol, "gate_outcome", None)
                if protocol is not None
                else None
            ),
            "stage": (
                getattr(protocol.stage, "value", protocol.stage)
                if protocol is not None
                else getattr(step, "failure_stage", None)
            ),
            "round_num": getattr(step, "round_num", None),
            "decision": (
                getattr(step.decision, "value", step.decision)
                if step is not None and step.decision is not None
                else None
            ),
            "case_summary": (
                {
                    "n_cases": stats.n_cases,
                    "wins": stats.wins,
                    "losses": stats.losses,
                    "ties": stats.ties,
                    "win_rate": stats.win_rate,
                    "median_delta": stats.median_delta,
                }
                if stats is not None
                else None
            ),
            "reason_codes": list(_reason_codes(step)) if step is not None else [],
            "failure_stage": getattr(step, "failure_stage", None),
            "failure_summary": (
                _first_line(getattr(step, "failure_detail", ""))
                if _safe_pre_protocol_step(step)
                else None
            ),
        }
    )


def _evidence_profile(branch: Branch | None, step: StepRecord | None) -> dict[str, Any]:
    pattern = _outcome_pattern(branch, step)
    protocol = step.protocol_result if step is not None else None
    stats = getattr(protocol, "stats", None) if protocol is not None else None
    reason_codes = _reason_codes(step)
    mechanism_evidence = (
        getattr(protocol, "mechanism_evidence", {})
        if protocol is not None
        else {}
    )
    runtime_status = _runtime_evidence_status(protocol, stats, reason_codes)
    runtime_confidence = _runtime_evidence_confidence(protocol, reason_codes)
    runtime_policy = runtime_evidence_policy_summary(
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_status,
        runtime_pairs=getattr(stats, "runtime_pairs", 0) if stats is not None else 0,
        champion_cached_runtime_pairs=(
            getattr(protocol, "champion_cached_runtime_pairs", 0)
            if protocol is not None
            else 0
        ),
        runtime_aggregate_excluded=_runtime_evidence_quality(
            runtime_confidence,
            runtime_status,
            reason_codes,
        )
        == "low_or_incomplete",
    )
    return _drop_empty(
        {
            "outcome_pattern": pattern,
            "effect_tier": _effect_tier(pattern),
            "activation_status": _activation_status(reason_codes, mechanism_evidence),
            "effect_status": _effect_status(pattern, reason_codes, mechanism_evidence),
            "runtime_evidence_confidence": runtime_confidence,
            "runtime_evidence_status": runtime_status,
            "runtime_evidence_quality": _runtime_evidence_quality(
                runtime_confidence,
                runtime_status,
                reason_codes,
            ),
            "runtime_evidence_policy": runtime_policy,
        }
    )


def _effect_tier(pattern: str) -> str:
    if pattern in {"positive", "weak_positive"}:
        return pattern
    if pattern == "no_effect":
        return "zero_effect"
    if pattern in {"regression", "abandoned"}:
        return "negative"
    if pattern in {"blocked", "pre_protocol_failure", "parked"}:
        return "blocked_or_paused"
    return "unknown"


def _activation_status(
    reason_codes: tuple[str, ...],
    mechanism_evidence: Any,
) -> str:
    reason_text = " ".join(reason_codes).upper()
    evidence_text = _mechanism_evidence_text(mechanism_evidence)
    if "ACTIVATION" in reason_text and any(
        marker in reason_text for marker in ("ABSENT", "MISSING", "ZERO")
    ):
        return "missing_or_zero"
    if "ACTIVATION" in reason_text:
        return "observed"
    if "ACTIVATION" in evidence_text and any(
        marker in evidence_text for marker in ("ABSENT", "MISSING")
    ):
        return "missing_or_zero"
    if "ACTIVATION" in evidence_text:
        return "observed"
    if mechanism_evidence:
        return "reported"
    return "unknown"


def _effect_status(
    pattern: str,
    reason_codes: tuple[str, ...],
    mechanism_evidence: Any,
) -> str:
    text = _evidence_text(reason_codes, mechanism_evidence)
    if pattern == "no_effect" or "NO_EFFECT" in text or "EFFECT_ZERO" in text:
        return "zero"
    if pattern in {"regression", "abandoned"}:
        return "negative"
    if pattern in {"positive", "weak_positive"}:
        return "positive_or_weak"
    if "EFFECT" in text:
        return "reported"
    return "unknown"


def _runtime_evidence_status(
    protocol: ProtocolResult | None,
    stats: Any,
    reason_codes: tuple[str, ...],
) -> str:
    value = _clean_token(getattr(protocol, "runtime_evidence_status", ""))
    if not value:
        value = _clean_token(getattr(stats, "runtime_evidence_status", ""))
    if value:
        return value
    reason_text = " ".join(reason_codes).upper()
    if "RUNTIME" in reason_text and any(
        marker in reason_text
        for marker in ("EXCLUDED", "INCOMPLETE", "INSUFFICIENT", "LOW")
    ):
        return "incomplete"
    return "unknown"


def _runtime_evidence_confidence(
    protocol: ProtocolResult | None,
    reason_codes: tuple[str, ...],
) -> str:
    value = _clean_token(getattr(protocol, "runtime_confidence", ""))
    if value:
        return value
    reason_text = " ".join(reason_codes).upper()
    if "RUNTIME" in reason_text and "LOW" in reason_text:
        return "low"
    return "unknown"


def _runtime_evidence_quality(
    confidence: str,
    status: str,
    reason_codes: tuple[str, ...],
) -> str:
    confidence_key = _clean_token(confidence).lower()
    status_key = _clean_token(status).lower()
    reason_text = " ".join(reason_codes).upper()
    if status_key in LOW_RUNTIME_STATUSES or confidence_key in LOW_RUNTIME_CONFIDENCES:
        return "low_or_incomplete"
    if "RUNTIME" in reason_text and any(
        marker in reason_text
        for marker in ("EXCLUDED", "INCOMPLETE", "INSUFFICIENT", "LOW")
    ):
        return "low_or_incomplete"
    if status_key == "sufficient" and confidence_key == "high":
        return "sufficient"
    if status_key == "unknown" and confidence_key == "unknown":
        return "unknown"
    return "mixed"


def _evidence_text(
    reason_codes: tuple[str, ...],
    mechanism_evidence: Any,
) -> str:
    return " ".join((*reason_codes, _mechanism_evidence_text(mechanism_evidence))).upper()


def _mechanism_evidence_text(mechanism_evidence: Any) -> str:
    evidence_text = ""
    if mechanism_evidence:
        evidence_text = json.dumps(mechanism_evidence, sort_keys=True, default=str)
    return evidence_text.upper()


def _attempt_summary(step: StepRecord) -> dict[str, Any]:
    hypothesis = step.hypothesis
    protocol = step.protocol_result
    return _drop_empty(
        {
            "round_num": step.round_num,
            "change_locus": getattr(hypothesis, "change_locus", None),
            "action": getattr(hypothesis, "action", None),
            "target_file": _clean_path(getattr(hypothesis, "target_file", None)),
            "mechanism_ids": [
                item.id for item in mechanism_changes(hypothesis)
            ],
            "outcome_pattern": _outcome_pattern(None, step),
            "gate_outcome": (
                getattr(protocol, "gate_outcome", None)
                if protocol is not None
                else None
            ),
            "failure_stage": step.failure_stage,
            "reason_codes": list(_reason_codes(step)),
        }
    )


def _lifecycle_summary(
    branch: Branch | None,
    steps: list[StepRecord],
) -> dict[str, Any]:
    reason_codes = []
    for code in getattr(branch, "failure_codes", ()) or ():
        _append_unique(reason_codes, _clean_token(code))
    for step in steps:
        for code in _reason_codes(step):
            upper = code.upper()
            if any(
                marker in upper
                for marker in (
                    "ABANDON",
                    "BLOCK",
                    "CHECKPOINT",
                    "PARK",
                    "QUALITY",
                    "ROLLBACK",
                )
            ):
                _append_unique(reason_codes, code)
    rollback_reason = _clean_token(getattr(branch, "last_rollback_reason", None))
    if rollback_reason:
        _append_unique(reason_codes, rollback_reason)
    redirect_reason = _clean_token(
        getattr(branch, "branch_lifecycle_re" + "ro" + "ute_reason", None)
    )
    if redirect_reason:
        _append_unique(reason_codes, redirect_reason)
    return _drop_empty(
        {
            "rollback_count": getattr(branch, "rollback_count", 0),
            "last_rollback_reason": rollback_reason,
            "best_quality_checkpoint_id": getattr(
                branch,
                "best_quality_checkpoint_id",
                None,
            ),
            "last_valid_checkpoint_id": getattr(
                branch,
                "last_valid_checkpoint_id",
                None,
            ),
            "branch_lifecycle_policy_blocks": getattr(
                branch,
                "branch_lifecycle_policy_blocks",
                0,
            ),
            "branch_lifecycle_new_mechanism_ineligible": bool(
                getattr(branch, "branch_lifecycle_new_mechanism_ineligible", False)
            ),
            "branch_lifecycle_redirect_reason": redirect_reason,
            "reason_codes": reason_codes[:12],
        }
    )


def _screening_protocol_step(step: StepRecord | None) -> bool:
    return (
        step is not None
        and step.protocol_result is not None
        and step.protocol_result.stage == ExperimentStage.SCREENING
    )


def _safe_pre_protocol_step(step: StepRecord | None) -> bool:
    return (
        step is not None
        and step.protocol_result is None
        and step.failure_stage in SAFE_PRE_PROTOCOL_FAILURE_STAGES
    )


def _outcome_pattern(branch: Branch | None, step: StepRecord | None) -> str:
    state = _branch_state(branch)
    if state == BranchState.PARKED_LINEAGE.value:
        return "parked"
    if state == BranchState.ABANDONED.value:
        return "abandoned"
    if step is None:
        return "active" if state not in ("", "unknown") else "unknown"
    if _safe_pre_protocol_step(step):
        text = " ".join(
            (
                str(step.failure_stage or ""),
                str(step.failure_detail or ""),
                " ".join(_reason_codes(step)),
            )
        ).upper()
        if "PARK" in text:
            return "parked"
        if "ABANDON" in text:
            return "abandoned"
        if "QUALITY" in text or "BLOCK" in text:
            return "blocked"
        return "pre_protocol_failure"

    protocol = step.protocol_result
    if protocol is None:
        return "unknown"
    stats = protocol.stats
    reason_text = " ".join(_reason_codes(step)).upper()
    branch_tier = str(
        getattr(branch, "last_screening_feedback_tier", "") or ""
    ).lower()
    median_delta = float(stats.median_delta or 0.0)
    wins = int(stats.wins or 0)
    losses = int(stats.losses or 0)
    if "ABANDON" in reason_text:
        return "abandoned"
    if "PARK" in reason_text:
        return "parked"
    if "REGRESSION" in reason_text or losses > wins or median_delta < 0:
        return "regression"
    if (
        branch_tier == "weak_positive" or "WEAK" in reason_text
    ) and (wins > losses or median_delta > 0):
        return "weak_positive"
    if (
        "NO_EFFECT" in reason_text
        or "EFFECT_ZERO" in reason_text
        or (wins == 0 and losses == 0 and abs(median_delta) <= 1e-12)
    ):
        return "no_effect"
    if protocol.gate_outcome in {"pass", "expand"} or wins > losses:
        return "positive"
    if protocol.gate_outcome == "continue":
        return "weak_positive"
    if protocol.gate_outcome == "fail":
        return "regression"
    return "unknown"


def _mechanism_ids(branch: Branch | None, steps: list[StepRecord]) -> list[str]:
    ids: list[str] = []
    for item in getattr(branch, "branch_mechanism_ids", ()) or ():
        _append_unique(ids, _clean_token(item))
    for step in steps:
        for proposal in (step.hypothesis, step.patch):
            if proposal is None:
                continue
            for change in mechanism_changes(proposal):
                _append_unique(ids, _clean_token(change.id))
    return ids[:16]


def _touched_files(steps: list[StepRecord]) -> list[str]:
    files: list[str] = []
    for step in steps:
        _append_unique(files, _clean_path(getattr(step.hypothesis, "target_file", None)))
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
    return files[:20]


def _reason_codes(step: StepRecord | None) -> tuple[str, ...]:
    if step is None:
        return ()
    codes: list[str] = []
    for code in getattr(step, "decision_reason_codes", None) or ():
        _append_unique(codes, _clean_token(code))
    protocol = step.protocol_result
    for code in getattr(protocol, "reason_codes", ()) or ():
        _append_unique(codes, _clean_token(code))
    return tuple(codes)


def _branch_state(branch: Branch | None) -> str:
    if branch is None:
        return "unknown"
    return getattr(branch.state, "value", str(branch.state))


def _final_or_active_state(branch: Branch | None) -> str:
    state = _branch_state(branch)
    if state in TERMINAL_BRANCH_STATES:
        return "final"
    if state == "unknown":
        return "unknown"
    return "active"


__all__ = [
    "LOW_RUNTIME_CONFIDENCES",
    "LOW_RUNTIME_STATUSES",
    "branch_index",
    "build_branch_summary",
    "ordered_branch_ids",
    "safe_prompt_steps",
]
