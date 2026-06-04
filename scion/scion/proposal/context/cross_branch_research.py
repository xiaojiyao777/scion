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
    StepRecord,
    mechanism_changes,
)
from scion.proposal.context.cross_branch_research_support import (
    append_unique as _append_unique,
    append_unique_dict as _append_unique_dict,
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
    mechanism_family as _mechanism_family,
    mechanism_signature as _signature,
    non_positive_count as _non_positive_count,
    parse_similarity_key as _parse_similarity_key,
    similarity_key as _similarity_key,
    unique as _unique,
)


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
    novelty_pressure = _novelty_pressure(
        branch_summaries,
        similarity_hints,
        available_actions=available_actions,
    )
    portfolio_guidance = _portfolio_guidance(
        branch_summaries,
        lesson_cards,
        novelty_pressure,
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
            "novelty_pressure": novelty_pressure,
            "portfolio_guidance": portfolio_guidance,
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
            "similarity_keys": [
                item["similarity_key"] for item in descriptors
            ][:8],
            "touched_files": touched_files,
            "outcome_summary": outcome,
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


def _novelty_pressure(
    branch_summaries: list[dict[str, Any]],
    similarity_hints: list[dict[str, Any]],
    *,
    available_actions: Iterable[str] | None = None,
) -> dict[str, Any]:
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
    return _drop_empty(
        {
            "policy": "proposal_only",
            "allowed_actions": sorted(allowed_actions),
            "near_duplicates": near_duplicates,
            "saturated_signatures": saturated_signatures,
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


def _portfolio_guidance(
    branch_summaries: list[dict[str, Any]],
    lesson_cards: list[dict[str, Any]],
    novelty_pressure: dict[str, Any],
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
