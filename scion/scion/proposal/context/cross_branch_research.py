"""Generic cross-branch research map for proposal-time feedback.

This module only builds tainted proposal guidance from generic branch,
mechanism, target, and screening/pre-protocol feedback fields. It deliberately
does not read or create DecisionFeatures.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any, Iterable, Sequence

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
    avoid_signature_set as _avoid_signature_set,
    blocked_signature_pressure as _blocked_signature_pressure,
    branch_lesson_text as _branch_lesson_text,
    clean_path as _clean_path,
    clean_token as _clean_token,
    cross_branch_lesson_text as _cross_branch_lesson_text,
    drop_empty as _drop_empty,
    fallback_mechanism_id as _fallback_mechanism_id,
    first_line as _first_line,
    generic_proposal_actions as _generic_proposal_actions,
    hint_guidance as _hint_guidance,
    lesson_confidence as _lesson_confidence,
    lesson_evidence_strength as _lesson_evidence_strength,
    lesson_failure_mode as _lesson_failure_mode,
    lesson_recommended_action as _lesson_recommended_action,
    lesson_transferability as _lesson_transferability,
    material_difference_audit_records as _material_difference_audit_records,
    material_difference_requirements_for_avoidance as _material_difference_requirements,
    mechanism_family as _mechanism_family,
    mechanism_signature as _signature,
    non_positive_count as _non_positive_count,
    parse_similarity_key as _parse_similarity_key,
    same_branch_refinement_allowances as _same_branch_refinement_allowances,
    similarity_key as _similarity_key,
    unique as _unique,
)
from scion.proposal.context.research_portfolio import build_portfolio_steering


_SAFE_PRE_PROTOCOL_FAILURE_STAGES = {
    "agent_quality_blocked",
    "proposal",
    "hypothesis_contract",
    "code_generation",
    "code_generation_failed",
    "patch_contract",
    "workspace",
    "verification",
}
_TERMINAL_BRANCH_STATES = {
    BranchState.PROMOTED.value,
    BranchState.ABANDONED.value,
    BranchState.PARKED_LINEAGE.value,
}
_SIMILARITY_BASIS = (
    "mechanism_family",
    "target_file",
    "change_locus",
    "action",
)
_COVERAGE_DIMENSIONS = (
    "mechanism_family",
    "target_file",
    "action",
    "outcome_pattern",
    "effect_tier",
    "activation_status",
    "effect_status",
    "runtime_evidence_confidence",
    "runtime_evidence_status",
)
_NON_POSITIVE_PATTERNS = {
    "abandoned",
    "blocked",
    "no_effect",
    "parked",
    "pre_protocol_failure",
    "regression",
}
_LOW_RUNTIME_STATUSES = {
    "fresh_champion_required",
    "incomplete",
    "insufficient",
    "low",
    "low_or_incomplete",
    "unknown_low",
}
_LOW_RUNTIME_CONFIDENCES = {"low", "medium", "unknown_low"}


def build_cross_branch_research_map(
    current_branch: Branch,
    branches: Sequence[Branch] | None,
    steps: Sequence[StepRecord] | None,
    *,
    available_actions: Iterable[str] | None = None,
    max_branches: int = 10,
    max_steps_per_branch: int = 4,
    max_similarity_hints: int = 8,
    max_lessons: int = 12,
) -> dict[str, Any]:
    """Build tainted cross-branch research feedback for hypothesis prompts.

    The returned payload is proposal-only context. It filters away validation
    and frozen protocol records, emits no raw metrics refs, and carries an
    explicit decision-input exclusion policy.
    """

    safe_steps = _safe_prompt_steps(steps or ())
    branch_by_id = _branch_index(current_branch, branches or ())
    for step in safe_steps:
        branch_by_id.setdefault(step.branch_id, None)

    ordered_branch_ids = _ordered_branch_ids(
        current_branch.branch_id,
        branch_by_id.keys(),
        safe_steps,
    )[:max_branches]
    branch_summaries = [
        _build_branch_summary(
            branch_id=branch_id,
            branch=branch_by_id.get(branch_id),
            steps=[step for step in safe_steps if step.branch_id == branch_id],
            is_current_branch=branch_id == current_branch.branch_id,
            max_steps_per_branch=max_steps_per_branch,
        )
        for branch_id in ordered_branch_ids
    ]
    branch_summaries = [item for item in branch_summaries if item]
    similarity_hints = _similarity_hints(
        branch_summaries,
        max_similarity_hints=max_similarity_hints,
    )
    lesson_cards = _lesson_cards(
        branch_summaries,
        similarity_hints,
        max_lessons=max_lessons,
    )
    lessons = _lessons_from_cards(lesson_cards, max_lessons=max_lessons)
    portfolio_coverage = _portfolio_coverage(branch_summaries)
    avoid_bridge_guidance = _avoid_bridge_guidance(
        branch_summaries,
        similarity_hints,
        portfolio_coverage,
    )
    novelty_pressure = _novelty_pressure(
        branch_summaries,
        similarity_hints,
        available_actions=available_actions,
    )
    opportunity_gaps = _opportunity_gaps(
        branch_summaries,
        portfolio_coverage,
        novelty_pressure,
        available_actions=available_actions,
    )
    portfolio_guidance = _portfolio_guidance(
        branch_summaries,
        lesson_cards,
        novelty_pressure,
        portfolio_coverage,
        avoid_bridge_guidance,
        opportunity_gaps,
    )
    portfolio_steering = build_portfolio_steering(
        branch_summaries,
        opportunity_gaps=opportunity_gaps,
    )

    return _drop_empty(
        {
            "schema_version": "cross_branch_research.v1",
            "taint": "proposal_research_feedback",
            "decision_input_policy": "excluded_from_decision_features",
            "current_branch_id": current_branch.branch_id,
            "exposure_policy": "screening_and_safe_pre_protocol_only",
            "branches": branch_summaries,
            "similarity_hints": similarity_hints,
            "lesson_cards": lesson_cards,
            "lessons": lessons,
            "portfolio_coverage": portfolio_coverage,
            "avoid_bridge_guidance": avoid_bridge_guidance,
            "opportunity_gaps": opportunity_gaps,
            "novelty_pressure": novelty_pressure,
            "material_difference_audit_records": novelty_pressure.get(
                "material_difference_audit_records",
                [],
            ),
            "cross_branch_research_metadata": (
                _cross_branch_research_metadata(novelty_pressure)
            ),
            "portfolio_guidance": portfolio_guidance,
            "portfolio_steering": portfolio_steering,
        }
    )


def render_cross_branch_research_map(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    return (
        "This cross-branch research map is tainted proposal feedback for "
        "hypothesis planning only. It is excluded from DecisionFeatures and "
        "must not be used as a deterministic decision input.\n"
        f"{json.dumps(payload, indent=2, sort_keys=True, default=str)}"
    )


def _build_branch_summary(
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
    if status_key in _LOW_RUNTIME_STATUSES or confidence_key in _LOW_RUNTIME_CONFIDENCES:
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


def _similarity_hints(
    branch_summaries: list[dict[str, Any]],
    *,
    max_similarity_hints: int,
) -> list[dict[str, Any]]:
    by_similarity_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in branch_summaries:
        for key in summary.get("similarity_keys", ()) or ():
            by_similarity_key[key].append(summary)

    hints: list[dict[str, Any]] = []
    for key, summaries in sorted(
        by_similarity_key.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        branch_ids = _unique(summary["branch_id"] for summary in summaries)
        if len(branch_ids) < 2:
            continue
        patterns = Counter(
            summary.get("outcome_summary", {}).get("outcome_pattern", "unknown")
            for summary in summaries
        )
        hint_type = (
            "saturated_family"
            if _non_positive_count(patterns) >= 2
            else "near_duplicate"
        )
        hints.append(
            _drop_empty(
                {
                    "hint_type": hint_type,
                    "basis": list(_SIMILARITY_BASIS),
                    "shared_signature": _parse_similarity_key(key),
                    "branch_ids": branch_ids,
                    "outcome_patterns": dict(sorted(patterns.items())),
                    "proposal_guidance": _hint_guidance(hint_type),
                }
            )
        )
        if len(hints) >= max_similarity_hints:
            break
    return hints


def _lesson_cards(
    branch_summaries: list[dict[str, Any]],
    similarity_hints: list[dict[str, Any]],
    *,
    max_lessons: int,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for summary in branch_summaries:
        outcome = summary.get("outcome_summary", {})
        lesson_type = outcome.get("outcome_pattern") or "unknown"
        cards.append(_branch_lesson_card(summary, lesson_type))

    for hint in similarity_hints:
        hint_type = hint.get("hint_type", "near_duplicate")
        cards.append(_hint_lesson_card(hint, hint_type))

    pattern_counts = Counter(
        summary.get("outcome_summary", {}).get("outcome_pattern", "unknown")
        for summary in branch_summaries
    )
    for lesson_type in (
        "weak_positive",
        "regression",
        "no_effect",
        "abandoned",
        "parked",
    ):
        if pattern_counts.get(lesson_type, 0) < 2:
            continue
        branch_ids = [
            summary.get("branch_id")
            for summary in branch_summaries
            if summary.get("outcome_summary", {}).get("outcome_pattern") == lesson_type
        ]
        cards.append(
            _drop_empty(
                {
                    "scope": "cross_branch",
                    "lesson_type": lesson_type,
                    "failure_mode": _lesson_failure_mode(lesson_type),
                    "evidence_strength": _lesson_evidence_strength(lesson_type),
                    "transferability": _lesson_transferability(
                        "cross_branch",
                        lesson_type,
                    ),
                    "recommended_action": _lesson_recommended_action(lesson_type),
                    "affected_stage": "screening",
                    "confidence": _lesson_confidence(
                        lesson_type,
                        branch_count=pattern_counts[lesson_type],
                    ),
                    "branch_count": pattern_counts[lesson_type],
                    "branch_ids": [item for item in branch_ids if item],
                    "shared_signature": {
                        "basis": "outcome_pattern",
                        "outcome_pattern": lesson_type,
                    },
                    "reason_codes": [f"CROSS_BRANCH_{lesson_type.upper()}"],
                    "summary": _cross_branch_lesson_text(lesson_type),
                }
            )
        )
    return cards[:max_lessons]


def _branch_lesson_card(
    summary: dict[str, Any],
    lesson_type: str,
) -> dict[str, Any]:
    outcome = summary.get("outcome_summary", {})
    reason_codes = list(outcome.get("reason_codes", []))
    _append_unique(reason_codes, f"LESSON_{lesson_type.upper()}")
    return _drop_empty(
        {
            "scope": "branch_local",
            "branch_id": summary.get("branch_id"),
            "lesson_type": lesson_type,
            "failure_mode": _lesson_failure_mode(lesson_type),
            "evidence_strength": _lesson_evidence_strength(lesson_type),
            "transferability": _lesson_transferability(
                "branch_local",
                lesson_type,
            ),
            "recommended_action": _lesson_recommended_action(lesson_type),
            "affected_stage": outcome.get("stage") or "screening",
            "confidence": _lesson_confidence(lesson_type),
            "mechanism_signature": next(
                iter(summary.get("mechanism_signatures", ())),
                None,
            ),
            "reason_codes": reason_codes[:12],
            "mechanism_ids": summary.get("mechanism_ids", [])[:8],
            "target_files": summary.get("touched_files", [])[:8],
            "case_summary": outcome.get("case_summary", {}),
            "summary": _branch_lesson_text(lesson_type),
        }
    )


def _hint_lesson_card(
    hint: dict[str, Any],
    hint_type: str,
) -> dict[str, Any]:
    branch_ids = list(hint.get("branch_ids", []) or [])
    reason_codes = [f"CROSS_BRANCH_{hint_type.upper()}"]
    patterns = Counter(hint.get("outcome_patterns", {}) or {})
    if _non_positive_count(patterns) > 0:
        _append_unique(reason_codes, "CROSS_BRANCH_NON_POSITIVE_CLUSTER")
    return _drop_empty(
        {
            "scope": "cross_branch",
            "lesson_type": hint_type,
            "failure_mode": _lesson_failure_mode(hint_type),
            "evidence_strength": _lesson_evidence_strength(hint_type),
            "transferability": _lesson_transferability(
                "cross_branch",
                hint_type,
            ),
            "recommended_action": _lesson_recommended_action(hint_type),
            "affected_stage": "screening",
            "confidence": _lesson_confidence(
                hint_type,
                branch_count=len(branch_ids),
            ),
            "branch_ids": branch_ids,
            "shared_signature": hint.get("shared_signature", {}),
            "reason_codes": reason_codes,
            "summary": _cross_branch_lesson_text(hint_type),
        }
    )


def _lessons_from_cards(
    lesson_cards: list[dict[str, Any]],
    *,
    max_lessons: int,
) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    for card in lesson_cards[:max_lessons]:
        lessons.append(
            _drop_empty(
                {
                    "scope": card.get("scope"),
                    "branch_id": card.get("branch_id"),
                    "branch_ids": card.get("branch_ids"),
                    "lesson_type": card.get("lesson_type"),
                    "failure_mode": card.get("failure_mode"),
                    "evidence_strength": card.get("evidence_strength"),
                    "transferability": card.get("transferability"),
                    "recommended_action": card.get("recommended_action"),
                    "affected_stage": card.get("affected_stage"),
                    "confidence": card.get("confidence"),
                    "mechanism_signature": card.get("mechanism_signature"),
                    "shared_signature": card.get("shared_signature"),
                    "mechanism_ids": card.get("mechanism_ids"),
                    "target_files": card.get("target_files"),
                    "case_summary": card.get("case_summary"),
                    "reason_codes": card.get("reason_codes", []),
                    "summary": card.get("summary"),
                }
            )
        )
    return lessons


def _portfolio_coverage(
    branch_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    records = _coverage_records(branch_summaries)
    if not records:
        return {}
    clusters = [
        _dimension_clusters(records, dimension)
        for dimension in _COVERAGE_DIMENSIONS
    ]
    return _drop_empty(
        {
            "policy": "proposal_only",
            "cluster_dimensions": list(_COVERAGE_DIMENSIONS),
            "dimension_coverage": {
                dimension: values
                for dimension, values in zip(_COVERAGE_DIMENSIONS, clusters)
                if values
            },
            "combined_clusters": _combined_coverage_clusters(records),
            "outcome_mix": dict(
                sorted(Counter(record["outcome_pattern"] for record in records).items())
            ),
            "low_confidence_runtime_clusters": _low_runtime_clusters(records),
        }
    )


def _coverage_records(
    branch_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for summary in branch_summaries:
        profile = summary.get("evidence_profile", {}) or {}
        outcome = summary.get("outcome_summary", {}) or {}
        branch_id = _clean_token(summary.get("branch_id"))
        descriptors = summary.get("research_descriptors") or [
            {
                "mechanism_family": next(
                    iter(summary.get("mechanism_families", ()) or ()),
                    "unknown",
                ),
                "target_file": next(
                    iter(summary.get("touched_files", ()) or ()),
                    "unknown",
                ),
                "action": next(
                    (
                        attempt.get("action")
                        for attempt in summary.get("recent_attempts", ()) or ()
                        if attempt.get("action")
                    ),
                    "unknown",
                ),
                "change_locus": next(
                    (
                        attempt.get("change_locus")
                        for attempt in summary.get("recent_attempts", ()) or ()
                        if attempt.get("change_locus")
                    ),
                    "unknown",
                ),
            }
        ]
        for descriptor in descriptors:
            mechanism_family = _clean_token(
                descriptor.get("mechanism_family")
            ) or "unknown"
            target_file = _clean_path(descriptor.get("target_file")) or "unknown"
            action = _clean_token(descriptor.get("action")) or "unknown"
            change_locus = _clean_token(descriptor.get("change_locus")) or "unknown"
            key = (branch_id, mechanism_family, target_file, action, change_locus)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "branch_id": branch_id,
                    "is_current_branch": bool(summary.get("is_current_branch")),
                    "final_or_active_state": summary.get("final_or_active_state", ""),
                    "mechanism_family": mechanism_family,
                    "target_file": target_file,
                    "action": action,
                    "change_locus": change_locus,
                    "outcome_pattern": (
                        _clean_token(profile.get("outcome_pattern"))
                        or _clean_token(outcome.get("outcome_pattern"))
                        or "unknown"
                    ),
                    "effect_tier": _clean_token(profile.get("effect_tier"))
                    or "unknown",
                    "activation_status": _clean_token(
                        profile.get("activation_status")
                    )
                    or "unknown",
                    "effect_status": _clean_token(profile.get("effect_status"))
                    or "unknown",
                    "runtime_evidence_confidence": _clean_token(
                        profile.get("runtime_evidence_confidence")
                    )
                    or "unknown",
                    "runtime_evidence_status": _clean_token(
                        profile.get("runtime_evidence_status")
                    )
                    or "unknown",
                    "runtime_evidence_quality": _clean_token(
                        profile.get("runtime_evidence_quality")
                    )
                    or "unknown",
                }
            )
    return records


def _dimension_clusters(
    records: list[dict[str, Any]],
    dimension: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_clean_token(record.get(dimension)) or "unknown"].append(record)
    items = [
        _coverage_cluster(dimension, value, group)
        for value, group in grouped.items()
    ]
    return sorted(
        items,
        key=lambda item: (
            -int(item.get("branch_count", 0)),
            str(item.get("value", "")),
        ),
    )[:10]


def _combined_coverage_clusters(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[
            (
                record["mechanism_family"],
                record["target_file"],
                record["action"],
            )
        ].append(record)
    items: list[dict[str, Any]] = []
    for (family, target_file, action), group in grouped.items():
        cluster = _coverage_cluster("family_target_action", "", group)
        cluster["signature"] = {
            "mechanism_family": family,
            "target_file": target_file,
            "action": action,
        }
        cluster.pop("value", None)
        items.append(cluster)
    return sorted(
        items,
        key=lambda item: (
            -int(item.get("branch_count", 0)),
            item.get("signature", {}).get("mechanism_family", ""),
            item.get("signature", {}).get("target_file", ""),
            item.get("signature", {}).get("action", ""),
        ),
    )[:12]


def _coverage_cluster(
    dimension: str,
    value: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    branch_ids = _unique(record.get("branch_id", "") for record in records)
    outcome_patterns = Counter(record["outcome_pattern"] for record in records)
    runtime_quality = Counter(record["runtime_evidence_quality"] for record in records)
    activation_statuses = Counter(record["activation_status"] for record in records)
    effect_statuses = Counter(record["effect_status"] for record in records)
    return _drop_empty(
        {
            "dimension": dimension,
            "value": value,
            "branch_count": len(branch_ids),
            "attempt_count": len(records),
            "branch_ids": branch_ids,
            "outcome_patterns": dict(sorted(outcome_patterns.items())),
            "effect_tiers": dict(
                sorted(Counter(record["effect_tier"] for record in records).items())
            ),
            "activation_statuses": dict(sorted(activation_statuses.items())),
            "effect_statuses": dict(sorted(effect_statuses.items())),
            "runtime_evidence_confidences": dict(
                sorted(
                    Counter(
                        record["runtime_evidence_confidence"] for record in records
                    ).items()
                )
            ),
            "runtime_evidence_statuses": dict(
                sorted(
                    Counter(record["runtime_evidence_status"] for record in records).items()
                )
            ),
            "runtime_evidence_quality": dict(sorted(runtime_quality.items())),
            "coverage_signal": _coverage_signal(
                outcome_patterns=outcome_patterns,
                activation_statuses=activation_statuses,
                effect_statuses=effect_statuses,
                runtime_quality=runtime_quality,
            ),
            "recommended_action": _coverage_recommended_action(
                outcome_patterns=outcome_patterns,
                activation_statuses=activation_statuses,
                effect_statuses=effect_statuses,
                runtime_quality=runtime_quality,
            ),
            "reason_codes": _coverage_reason_codes(
                dimension=dimension,
                outcome_patterns=outcome_patterns,
                runtime_quality=runtime_quality,
            ),
        }
    )


def _coverage_signal(
    *,
    outcome_patterns: Counter[str],
    activation_statuses: Counter[str],
    effect_statuses: Counter[str],
    runtime_quality: Counter[str],
) -> str:
    if runtime_quality.get("low_or_incomplete", 0) > 0:
        return "low_runtime_evidence"
    if _non_positive_count(outcome_patterns) >= 2:
        return "non_positive_cluster"
    if outcome_patterns.get("weak_positive", 0) > 0:
        return "weak_positive_cluster"
    if (
        activation_statuses.get("missing_or_zero", 0) > 0
        or effect_statuses.get("zero", 0) > 0
    ):
        return "observability_gap"
    if outcome_patterns.get("positive", 0) > 0:
        return "positive_cluster"
    return "mixed_or_unknown"


def _coverage_recommended_action(
    *,
    outcome_patterns: Counter[str],
    activation_statuses: Counter[str],
    effect_statuses: Counter[str],
    runtime_quality: Counter[str],
) -> str:
    if runtime_quality.get("low_or_incomplete", 0) > 0:
        return "bridge"
    if outcome_patterns.get("regression", 0) or outcome_patterns.get("abandoned", 0):
        return "avoid"
    if _non_positive_count(outcome_patterns) >= 2:
        return "diversify"
    if (
        activation_statuses.get("missing_or_zero", 0) > 0
        or effect_statuses.get("zero", 0) > 0
    ):
        return "observe"
    if outcome_patterns.get("weak_positive", 0) or outcome_patterns.get("positive", 0):
        return "refine"
    return "observe"


def _coverage_reason_codes(
    *,
    dimension: str,
    outcome_patterns: Counter[str],
    runtime_quality: Counter[str],
) -> list[str]:
    reason_codes = [f"COVERAGE_CLUSTER_{dimension.upper()}"]
    if _non_positive_count(outcome_patterns) >= 2:
        _append_unique(reason_codes, "COVERAGE_NON_POSITIVE_CLUSTER")
    if runtime_quality.get("low_or_incomplete", 0) > 0:
        _append_unique(reason_codes, "COVERAGE_LOW_RUNTIME_EVIDENCE")
    return reason_codes


def _low_runtime_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    low_records = [
        record
        for record in records
        if record.get("runtime_evidence_quality") == "low_or_incomplete"
    ]
    if not low_records:
        return []
    return [
        cluster
        for cluster in _dimension_clusters(low_records, "target_file")
        if cluster.get("branch_count", 0) >= 1
    ][:6]


def _avoid_bridge_guidance(
    branch_summaries: list[dict[str, Any]],
    similarity_hints: list[dict[str, Any]],
    portfolio_coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []
    combined = portfolio_coverage.get("combined_clusters", []) or []
    for cluster in combined:
        patterns = Counter(cluster.get("outcome_patterns", {}) or {})
        if int(cluster.get("branch_count", 0)) >= 2 and _non_positive_count(patterns) >= 2:
            _append_guidance_once(
                guidance,
                _coverage_guidance_item(
                    guidance_type="avoid_repeated_non_positive_cluster",
                    recommended_action="diversify",
                    priority="high",
                    cluster=cluster,
                    reason_codes=["GUIDANCE_AVOID_NON_POSITIVE_CLUSTER"],
                    proposal_guidance=(
                        "Avoid another proposal in this same generic family, "
                        "target, and action cluster unless at least one "
                        "dimension changes materially."
                    ),
                    confidence=0.76,
                ),
            )
        if _cluster_has_low_runtime_evidence(cluster):
            _append_guidance_once(
                guidance,
                _coverage_guidance_item(
                    guidance_type="bridge_low_confidence_runtime_evidence",
                    recommended_action="bridge",
                    priority="high",
                    cluster=cluster,
                    reason_codes=["GUIDANCE_BRIDGE_LOW_RUNTIME_EVIDENCE"],
                    proposal_guidance=(
                        "Treat low, cached, excluded, or fresh-required runtime "
                        "evidence as planning uncertainty. Do not use it as a "
                        "standalone optimization signal; bridge with fresh "
                        "measurement, objective, activation, or effect evidence "
                        "before planning from this runtime signal."
                    ),
                    confidence=0.7,
                ),
            )

    for hint in similarity_hints:
        if hint.get("hint_type") != "saturated_family":
            continue
        _append_guidance_once(
            guidance,
            _drop_empty(
                {
                    "guidance_type": "avoid_saturated_similarity_signature",
                    "source": "proposal_only",
                    "recommended_action": "diversify",
                    "priority": "high",
                    "shared_signature": hint.get("shared_signature", {}),
                    "branch_ids": hint.get("branch_ids", []),
                    "outcome_patterns": hint.get("outcome_patterns", {}),
                    "reason_codes": ["GUIDANCE_AVOID_SATURATED_SIGNATURE"],
                    "proposal_guidance": (
                        "A near signature is already saturated by non-positive "
                        "evidence; choose a different family, target, action, "
                        "or observability path."
                    ),
                    "confidence": 0.74,
                }
            ),
        )

    no_effect_branches = _branch_ids_with_pattern(branch_summaries, "no_effect")
    if len(no_effect_branches) >= 2:
        _append_guidance_once(
            guidance,
            _drop_empty(
                {
                    "guidance_type": "bridge_repeated_zero_effect",
                    "source": "proposal_only",
                    "recommended_action": "bridge",
                    "priority": "medium",
                    "branch_ids": no_effect_branches,
                    "reason_codes": ["GUIDANCE_BRIDGE_REPEATED_ZERO_EFFECT"],
                    "proposal_guidance": (
                        "Repeated zero-effect outcomes need a bridge proposal "
                        "that changes activation, effect observability, target, "
                        "or family before more local refinement."
                    ),
                    "confidence": 0.66,
                }
            ),
        )
    return guidance[:10]


def _coverage_guidance_item(
    *,
    guidance_type: str,
    recommended_action: str,
    priority: str,
    cluster: dict[str, Any],
    reason_codes: list[str],
    proposal_guidance: str,
    confidence: float,
) -> dict[str, Any]:
    runtime_guidance = "runtime" in guidance_type
    return _drop_empty(
        {
            "guidance_type": guidance_type,
            "source": "proposal_only",
            "recommended_action": recommended_action,
            "priority": priority,
            "signature": cluster.get("signature"),
            "branch_ids": cluster.get("branch_ids", []),
            "outcome_patterns": cluster.get("outcome_patterns", {}),
            "activation_statuses": cluster.get("activation_statuses", {}),
            "effect_statuses": cluster.get("effect_statuses", {}),
            "runtime_evidence_quality": cluster.get("runtime_evidence_quality", {}),
            "runtime_signal_role": (
                "audit_or_proposal_guidance_only" if runtime_guidance else None
            ),
            "standalone_optimization_signal": False if runtime_guidance else None,
            "reason_codes": reason_codes,
            "proposal_guidance": proposal_guidance,
            "confidence": confidence,
        }
    )


def _append_guidance_once(
    guidance: list[dict[str, Any]],
    item: dict[str, Any],
) -> None:
    key = (
        item.get("guidance_type"),
        json.dumps(item.get("signature", item.get("shared_signature", {})), sort_keys=True),
        tuple(item.get("branch_ids", []) or ()),
    )
    for existing in guidance:
        existing_key = (
            existing.get("guidance_type"),
            json.dumps(
                existing.get("signature", existing.get("shared_signature", {})),
                sort_keys=True,
            ),
            tuple(existing.get("branch_ids", []) or ()),
        )
        if existing_key == key:
            return
    guidance.append(item)


def _cluster_has_low_runtime_evidence(cluster: dict[str, Any]) -> bool:
    quality = Counter(cluster.get("runtime_evidence_quality", {}) or {})
    statuses = Counter(cluster.get("runtime_evidence_statuses", {}) or {})
    confidences = Counter(cluster.get("runtime_evidence_confidences", {}) or {})
    return (
        quality.get("low_or_incomplete", 0) > 0
        or any(status in _LOW_RUNTIME_STATUSES for status in statuses)
        or any(confidence in _LOW_RUNTIME_CONFIDENCES for confidence in confidences)
    )


def _opportunity_gaps(
    branch_summaries: list[dict[str, Any]],
    portfolio_coverage: dict[str, Any],
    novelty_pressure: dict[str, Any],
    *,
    available_actions: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    records = _coverage_records(branch_summaries)
    if not records:
        return []
    gaps: list[dict[str, Any]] = []
    allowed_actions = _available_action_set(available_actions)
    action_counts = Counter(record["action"] for record in records)
    target_counts = Counter(record["target_file"] for record in records)
    family_counts = Counter(record["mechanism_family"] for record in records)
    outcome_counts = Counter(record["outcome_pattern"] for record in records)
    runtime_quality = Counter(record["runtime_evidence_quality"] for record in records)
    effect_statuses = Counter(record["effect_status"] for record in records)
    activation_statuses = Counter(record["activation_status"] for record in records)

    unexplored_actions = sorted(
        action for action in allowed_actions if action not in action_counts
    )
    if unexplored_actions:
        gaps.append(
            _gap_item(
                gap_type="action_diversity_gap",
                recommended_action="diversify",
                priority="medium",
                basis={
                    "observed_actions": sorted(action_counts),
                    "unexplored_actions": unexplored_actions,
                },
                reason_codes=["GAP_UNEXPLORED_ACTION"],
                proposal_guidance=(
                    "Consider an allowed action that has not yet been tried, "
                    "or explain why the same action changes a different "
                    "family, target, or observability path."
                ),
                confidence=0.5,
            )
        )

    for dimension, counts, gap_type in (
        ("mechanism_family", family_counts, "family_diversity_gap"),
        ("target_file", target_counts, "target_diversity_gap"),
    ):
        value, count = counts.most_common(1)[0]
        if count >= 2 and _non_positive_count(outcome_counts) > 0:
            gaps.append(
                _gap_item(
                    gap_type=gap_type,
                    recommended_action="diversify",
                    priority="high" if count >= 3 else "medium",
                    basis={
                        "dominant_dimension": dimension,
                        "dominant_value": value,
                        "dominant_count": count,
                        "distinct_values": sorted(counts),
                    },
                    reason_codes=[f"GAP_OVERUSED_{dimension.upper()}"],
                    proposal_guidance=(
                        "The current map is concentrated on one generic "
                        "dimension with weak or non-positive evidence; change "
                        "that dimension before another nearby attempt."
                    ),
                    confidence=min(0.78, 0.48 + count * 0.06),
                )
            )

    if (
        outcome_counts.get("no_effect", 0) >= 2
        or effect_statuses.get("zero", 0) >= 2
        or activation_statuses.get("missing_or_zero", 0) > 0
    ):
        gaps.append(
            _gap_item(
                gap_type="observability_path_gap",
                recommended_action="bridge",
                priority="high",
                basis={
                    "outcome_patterns": dict(sorted(outcome_counts.items())),
                    "activation_statuses": dict(sorted(activation_statuses.items())),
                    "effect_statuses": dict(sorted(effect_statuses.items())),
                },
                reason_codes=["GAP_OBSERVABILITY_PATH"],
                proposal_guidance=(
                    "Before another same-neighborhood refinement, propose a "
                    "generic bridge that makes activation and effect evidence "
                    "clearer or changes where that evidence is collected."
                ),
                confidence=0.68,
            )
        )

    if runtime_quality.get("low_or_incomplete", 0) > 0:
        gaps.append(
            _gap_item(
                gap_type="runtime_evidence_confidence_gap",
                recommended_action="bridge",
                priority="high",
                basis={
                    "runtime_evidence_quality": dict(sorted(runtime_quality.items())),
                    "low_confidence_clusters": portfolio_coverage.get(
                        "low_confidence_runtime_clusters",
                        [],
                    )[:3],
                },
                reason_codes=["GAP_RUNTIME_EVIDENCE_CONFIDENCE"],
                proposal_guidance=(
                    "Do not treat low, cached, excluded, or fresh-required "
                    "runtime evidence as a standalone optimization signal; "
                    "first bridge through fresh measurement, clearer evidence, "
                    "or a different non-runtime signal."
                ),
                confidence=0.72,
            )
        )

    saturated = novelty_pressure.get("saturated_signatures", []) or []
    if saturated:
        gaps.append(
            _gap_item(
                gap_type="signature_bridge_gap",
                recommended_action="bridge",
                priority="high",
                basis={"saturated_signatures": saturated[:4]},
                reason_codes=["GAP_SIGNATURE_BRIDGE"],
                proposal_guidance=(
                    "A saturated signature should not receive another local "
                    "variant; bridge by changing one or more generic dimensions."
                ),
                confidence=0.7,
            )
        )
    return gaps[:8]


def _gap_item(
    *,
    gap_type: str,
    recommended_action: str,
    priority: str,
    basis: dict[str, Any],
    reason_codes: list[str],
    proposal_guidance: str,
    confidence: float,
) -> dict[str, Any]:
    runtime_gap = "runtime" in gap_type
    return _drop_empty(
        {
            "gap_type": gap_type,
            "source": "proposal_only",
            "recommended_action": recommended_action,
            "priority": priority,
            "basis": basis,
            "runtime_signal_role": (
                "audit_or_proposal_guidance_only" if runtime_gap else None
            ),
            "standalone_optimization_signal": False if runtime_gap else None,
            "reason_codes": reason_codes,
            "proposal_guidance": proposal_guidance,
            "confidence": confidence,
        }
    )


def _novelty_pressure(
    branch_summaries: list[dict[str, Any]],
    similarity_hints: list[dict[str, Any]],
    *,
    available_actions: Iterable[str] | None = None,
) -> dict[str, Any]:
    records = _coverage_records(branch_summaries)
    near_duplicates: list[dict[str, Any]] = []
    saturated_signatures: list[dict[str, Any]] = []
    for hint in similarity_hints:
        hint_type = hint.get("hint_type", "near_duplicate")
        target = saturated_signatures if hint_type == "saturated_family" else near_duplicates
        target.append(
            _drop_empty(
                {
                    "shared_signature": hint.get("shared_signature", {}),
                    "branch_ids": hint.get("branch_ids", []),
                    "outcome_patterns": hint.get("outcome_patterns", {}),
                    "recommended_action": _lesson_recommended_action(hint_type),
                    "confidence": _lesson_confidence(
                        hint_type,
                        branch_count=len(hint.get("branch_ids", []) or []),
                    ),
                    "reason_codes": [f"NOVELTY_{hint_type.upper()}"],
                }
            )
        )

    action_counts: Counter[str] = Counter()
    locus_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    outcome_by_dimension: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for summary in branch_summaries:
        pattern = summary.get("outcome_summary", {}).get("outcome_pattern", "unknown")
        for attempt in summary.get("recent_attempts", ()) or ():
            action = _clean_token(attempt.get("action"))
            locus = _clean_token(attempt.get("change_locus"))
            if action:
                action_counts[action] += 1
                outcome_by_dimension[("action", action)][pattern] += 1
            if locus:
                locus_counts[locus] += 1
                outcome_by_dimension[("change_locus", locus)][pattern] += 1
        for family in summary.get("mechanism_families", ()) or ():
            family = _clean_token(family)
            if family:
                family_counts[family] += 1
                outcome_by_dimension[("mechanism_family", family)][pattern] += 1

    allowed_actions = _available_action_set(available_actions)
    observed_actions = sorted(action for action in action_counts if action in allowed_actions)
    unexplored_actions = [
        action
        for action in allowed_actions
        if action not in action_counts
    ]
    avoid_signature_set = _avoid_signature_set(records)
    material_difference_audit_records = _material_difference_audit_records(
        avoid_signature_set,
        saturated_signatures=saturated_signatures,
        near_duplicates=near_duplicates,
    )
    return _drop_empty(
        {
            "policy": "proposal_only",
            "allowed_actions": sorted(allowed_actions),
            "near_duplicates": near_duplicates,
            "saturated_signatures": saturated_signatures,
            "avoid_signature_set": avoid_signature_set,
            "blocked_signature_pressure": _blocked_signature_pressure(
                avoid_signature_set
            ),
            "material_difference_requirements": (
                _material_difference_requirements(avoid_signature_set)
            ),
            "material_difference_audit_records": material_difference_audit_records,
            "same_branch_refinement_allowances": (
                _same_branch_refinement_allowances(branch_summaries)
            ),
            "overused_dimensions": _overused_dimensions(
                action_counts=action_counts,
                locus_counts=locus_counts,
                family_counts=family_counts,
                outcome_by_dimension=outcome_by_dimension,
            ),
            "unexplored_action_pressure": (
                {
                    "observed_actions": observed_actions,
                    "unexplored_actions": unexplored_actions,
                    "recommended_action": "diversify",
                    "confidence": 0.42,
                    "reason_codes": ["UNEXPLORED_ACTION_PRESSURE"],
                    "actionability": (
                        "choose_only_from_allowed_actions_or_diversify_target_family"
                    ),
                }
                if unexplored_actions
                else None
            ),
            "in_action_diversity_pressure": _in_action_diversity_pressure(
                action_counts=action_counts,
                locus_counts=locus_counts,
                family_counts=family_counts,
                allowed_actions=allowed_actions,
                outcome_by_dimension=outcome_by_dimension,
            ),
        }
    )


def _available_action_set(actions: Iterable[str] | None) -> set[str]:
    values = {
        _clean_token(action)
        for action in (actions or _generic_proposal_actions())
        if _clean_token(action)
    }
    allowed = set(_generic_proposal_actions())
    filtered = values & allowed
    return filtered or allowed


def _overused_dimensions(
    *,
    action_counts: Counter[str],
    locus_counts: Counter[str],
    family_counts: Counter[str],
    outcome_by_dimension: dict[tuple[str, str], Counter[str]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for dimension, counts in (
        ("action", action_counts),
        ("change_locus", locus_counts),
        ("mechanism_family", family_counts),
    ):
        for value, count in counts.most_common():
            if count < 2:
                continue
            patterns = outcome_by_dimension[(dimension, value)]
            recommended_action = (
                "diversify"
                if _non_positive_count(patterns) > 0
                else "refine"
            )
            items.append(
                _drop_empty(
                    {
                        "dimension": dimension,
                        "value": value,
                        "count": count,
                        "outcome_patterns": dict(sorted(patterns.items())),
                        "pressure": f"overused_{dimension}",
                        "recommended_action": recommended_action,
                        "confidence": min(0.85, 0.45 + count * 0.05),
                        "reason_codes": [f"OVERUSED_{dimension.upper()}"],
                    }
                )
            )
    return items[:8]


def _in_action_diversity_pressure(
    *,
    action_counts: Counter[str],
    locus_counts: Counter[str],
    family_counts: Counter[str],
    allowed_actions: set[str],
    outcome_by_dimension: dict[tuple[str, str], Counter[str]],
) -> dict[str, Any]:
    if not action_counts:
        return {}
    dominant_action, dominant_count = action_counts.most_common(1)[0]
    if dominant_count < 2:
        return {}
    action_patterns = outcome_by_dimension[("action", dominant_action)]
    if _non_positive_count(action_patterns) <= 0:
        return {}
    all_observed_actions = set(action_counts)
    alternate_actions = sorted(allowed_actions - all_observed_actions)
    dominant_loci = [
        value
        for value, count in locus_counts.most_common(3)
        if count >= 2
        and _non_positive_count(outcome_by_dimension[("change_locus", value)]) > 0
    ]
    dominant_families = [
        value
        for value, count in family_counts.most_common(4)
        if count >= 2
        and _non_positive_count(outcome_by_dimension[("mechanism_family", value)]) > 0
    ]
    return _drop_empty(
        {
            "dominant_action": dominant_action,
            "dominant_action_count": dominant_count,
            "allowed_alternate_actions": alternate_actions,
            "overused_change_loci": dominant_loci,
            "overused_mechanism_families": dominant_families,
            "recommended_action": "diversify",
            "confidence": min(0.82, 0.5 + dominant_count * 0.05),
            "reason_codes": ["IN_ACTION_DIVERSITY_PRESSURE"],
            "proposal_guidance": (
                "If the next proposal keeps the dominant legal action, it must "
                "change at least one of target, generic mechanism family, "
                "effect pathway, or runtime budget strategy."
            ),
        }
    )


def _cross_branch_research_metadata(
    novelty_pressure: dict[str, Any],
) -> dict[str, Any]:
    records = novelty_pressure.get("material_difference_audit_records", []) or []
    return _drop_empty(
        {
            "schema_version": "cross_branch_research_context_metadata.v1",
            "policy": "proposal_only",
            "decision_input_policy": "excluded_from_decision_features",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "material_difference_requirement_count": len(records),
            "material_difference_record_ids": [
                item.get("record_id")
                for item in records
                if isinstance(item, dict) and item.get("record_id")
            ],
            "material_difference_record_digests": [
                item.get("record_digest")
                for item in records
                if isinstance(item, dict) and item.get("record_digest")
            ],
        }
    )


def _portfolio_guidance(
    branch_summaries: list[dict[str, Any]],
    lesson_cards: list[dict[str, Any]],
    novelty_pressure: dict[str, Any],
    portfolio_coverage: dict[str, Any],
    avoid_bridge_guidance: list[dict[str, Any]],
    opportunity_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []
    active_weak = _branch_ids_with_pattern(
        branch_summaries,
        "weak_positive",
        active_only=True,
    )
    if active_weak:
        guidance.append(
            _guidance_item(
                guidance_type="refine_active_weak_positive",
                recommended_action="refine",
                branch_ids=active_weak,
                priority="high",
                reason_codes=["PORTFOLIO_REFINE_WEAK_POSITIVE"],
                proposal_guidance=(
                    "Prefer focused refinement of active weak-positive "
                    "signals before duplicating nearby signatures."
                ),
                confidence=0.68,
            )
        )

    no_effect = _branch_ids_with_pattern(branch_summaries, "no_effect")
    if no_effect:
        guidance.append(
            _guidance_item(
                guidance_type="avoid_no_effect_checkpoint",
                recommended_action="observe",
                branch_ids=no_effect,
                priority="medium",
                reason_codes=["PORTFOLIO_NO_EFFECT_OBSERVE"],
                proposal_guidance=(
                    "Avoid repeating a no-effect checkpoint until the "
                    "activation, target, or observability path changes."
                ),
                confidence=0.62,
            )
        )

    abandoned = _branch_ids_with_pattern(branch_summaries, "abandoned")
    if abandoned:
        guidance.append(
            _guidance_item(
                guidance_type="avoid_closed_lineage",
                recommended_action="avoid",
                branch_ids=abandoned,
                priority="medium",
                reason_codes=["PORTFOLIO_AVOID_CLOSED_LINEAGE"],
                proposal_guidance=(
                    "Do not reopen closed lineage patterns without new "
                    "structured evidence."
                ),
                confidence=0.72,
            )
        )

    saturated = novelty_pressure.get("saturated_signatures", []) or []
    near_duplicates = novelty_pressure.get("near_duplicates", []) or []
    in_action_pressure = novelty_pressure.get("in_action_diversity_pressure", {})
    overused_dimensions = novelty_pressure.get("overused_dimensions", []) or []
    if saturated or len(near_duplicates) >= 2:
        guidance.append(
            _guidance_item(
                guidance_type="diversify_when_recent_signatures_saturated",
                recommended_action="diversify",
                branch_ids=_unique(
                    branch_id
                    for item in (*saturated, *near_duplicates)
                    for branch_id in item.get("branch_ids", [])
                ),
                priority="high" if saturated else "medium",
                reason_codes=["PORTFOLIO_DIVERSIFY_SATURATED_SIGNATURES"],
                proposal_guidance=(
                    "Recent branch signatures are saturated or near-duplicate; "
                    "change action, locus, family, or target before retrying."
                ),
                confidence=0.7 if saturated else 0.58,
            )
        )

    if in_action_pressure or overused_dimensions:
        guidance.append(
            _guidance_item(
                guidance_type="diversify_within_executable_action",
                recommended_action="diversify",
                branch_ids=_unique(
                    branch_id
                    for summary in branch_summaries
                    for branch_id in (summary.get("branch_id"),)
                    if branch_id
                ),
                priority="high",
                reason_codes=["PORTFOLIO_DIVERSIFY_EXECUTABLE_ACTION"],
                proposal_guidance=(
                    "Recent proposal attempts overuse an executable action or "
                    "locus. If action switching is not selected by the host, "
                    "the next hypothesis must diversify target, generic "
                    "mechanism family, effect pathway, or runtime budget "
                    "strategy."
                ),
                confidence=0.66,
            )
        )

    coverage_signals = _coverage_signals(portfolio_coverage)
    if "non_positive_cluster" in coverage_signals:
        guidance.append(
            _guidance_item(
                guidance_type="use_coverage_clusters_for_layout",
                recommended_action="diversify",
                branch_ids=_unique(
                    branch_id
                    for item in portfolio_coverage.get("combined_clusters", []) or []
                    if item.get("coverage_signal") == "non_positive_cluster"
                    for branch_id in item.get("branch_ids", [])
                ),
                priority="high",
                reason_codes=["PORTFOLIO_USE_COVERAGE_CLUSTERS"],
                proposal_guidance=(
                    "Use the coverage clusters as a global layout map: avoid "
                    "adding another candidate to a non-positive cluster unless "
                    "family, target, action, or observability changes."
                ),
                confidence=0.7,
            )
        )

    if avoid_bridge_guidance:
        guidance.append(
            _guidance_item(
                guidance_type="apply_avoid_bridge_guidance",
                recommended_action="bridge",
                branch_ids=_unique(
                    branch_id
                    for item in avoid_bridge_guidance
                    for branch_id in item.get("branch_ids", [])
                ),
                priority="high",
                reason_codes=["PORTFOLIO_APPLY_AVOID_BRIDGE_GUIDANCE"],
                proposal_guidance=(
                    "Before another local follow-up, apply the avoid/bridge "
                    "guidance from repeated non-positive or low-confidence "
                    "evidence clusters."
                ),
                confidence=0.69,
            )
        )

    if opportunity_gaps:
        guidance.append(
            _guidance_item(
                guidance_type="close_opportunity_gaps",
                recommended_action="diversify",
                branch_ids=_unique(
                    branch_id
                    for summary in branch_summaries
                    for branch_id in (summary.get("branch_id"),)
                    if branch_id
                ),
                priority="medium",
                reason_codes=["PORTFOLIO_CLOSE_OPPORTUNITY_GAPS"],
                proposal_guidance=(
                    "Use opportunity gaps to select a generic missing "
                    "dimension: action, target, family, observability path, "
                    "or evidence-confidence path."
                ),
                confidence=0.6,
            )
        )

    if not guidance and lesson_cards:
        guidance.append(
            _guidance_item(
                guidance_type="observe_until_clear_signal",
                recommended_action="observe",
                branch_ids=_unique(
                    card.get("branch_id")
                    for card in lesson_cards
                    if card.get("branch_id")
                ),
                priority="low",
                reason_codes=["PORTFOLIO_OBSERVE_WEAK_CONTEXT"],
                proposal_guidance=(
                    "Use the map as weak proposal context until a clearer "
                    "branch-local or shared-signature signal appears."
                ),
                confidence=0.4,
            )
        )
    return guidance[:6]


def _coverage_signals(portfolio_coverage: dict[str, Any]) -> set[str]:
    signals: set[str] = set()
    for item in portfolio_coverage.get("combined_clusters", []) or []:
        signal = _clean_token(item.get("coverage_signal"))
        if signal:
            signals.add(signal)
    return signals


def _branch_ids_with_pattern(
    branch_summaries: list[dict[str, Any]],
    pattern: str,
    *,
    active_only: bool = False,
) -> list[str]:
    branch_ids: list[str] = []
    for summary in branch_summaries:
        if active_only and summary.get("final_or_active_state") != "active":
            continue
        outcome = summary.get("outcome_summary", {})
        if outcome.get("outcome_pattern") == pattern:
            _append_unique(branch_ids, summary.get("branch_id", ""))
    return branch_ids


def _guidance_item(
    *,
    guidance_type: str,
    recommended_action: str,
    branch_ids: list[str],
    priority: str,
    reason_codes: list[str],
    proposal_guidance: str,
    confidence: float,
) -> dict[str, Any]:
    return _drop_empty(
        {
            "guidance_type": guidance_type,
            "source": "proposal_only",
            "recommended_action": recommended_action,
            "branch_ids": branch_ids,
            "priority": priority,
            "reason_codes": reason_codes,
            "proposal_guidance": proposal_guidance,
            "confidence": confidence,
        }
    )


def _safe_prompt_steps(steps: Sequence[StepRecord]) -> list[StepRecord]:
    return [
        step
        for step in steps
        if _screening_protocol_step(step) or _safe_pre_protocol_step(step)
    ]


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
        and step.failure_stage in _SAFE_PRE_PROTOCOL_FAILURE_STAGES
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


def _branch_index(
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


def _ordered_branch_ids(
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


def _branch_state(branch: Branch | None) -> str:
    if branch is None:
        return "unknown"
    return getattr(branch.state, "value", str(branch.state))


def _final_or_active_state(branch: Branch | None) -> str:
    state = _branch_state(branch)
    if state in _TERMINAL_BRANCH_STATES:
        return "final"
    if state == "unknown":
        return "unknown"
    return "active"


__all__ = [
    "build_cross_branch_research_map",
    "render_cross_branch_research_map",
]
