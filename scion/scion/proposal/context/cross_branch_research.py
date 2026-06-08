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
    StepRecord,
)
from scion.proposal.context.cross_branch_research_coverage import (
    available_action_set as _available_action_set,
    avoid_bridge_guidance as _avoid_bridge_guidance,
    coverage_records as _coverage_records,
    coverage_signals as _coverage_signals,
    opportunity_gaps as _opportunity_gaps,
    portfolio_coverage as _portfolio_coverage,
)
from scion.proposal.context.cross_branch_research_summary import (
    branch_index as _branch_index,
    build_branch_summary as _build_branch_summary,
    ordered_branch_ids as _ordered_branch_ids,
    safe_prompt_steps as _safe_prompt_steps,
)
from scion.proposal.context.cross_branch_research_support import (
    append_unique as _append_unique,
    avoid_signature_set as _avoid_signature_set,
    blocked_signature_pressure as _blocked_signature_pressure,
    branch_lesson_records as _branch_lesson_records,
    branch_lesson_text as _branch_lesson_text,
    clean_token as _clean_token,
    cross_branch_lesson_text as _cross_branch_lesson_text,
    drop_empty as _drop_empty,
    hint_guidance as _hint_guidance,
    lesson_confidence as _lesson_confidence,
    lesson_evidence_strength as _lesson_evidence_strength,
    lesson_failure_mode as _lesson_failure_mode,
    lesson_recommended_action as _lesson_recommended_action,
    lesson_transferability as _lesson_transferability,
    material_difference_audit_records as _material_difference_audit_records,
    material_difference_requirements_for_avoidance as _material_difference_requirements,
    non_positive_count as _non_positive_count,
    parse_similarity_key as _parse_similarity_key,
    same_branch_refinement_allowances as _same_branch_refinement_allowances,
    unique as _unique,
)
from scion.proposal.context.research_portfolio import build_portfolio_steering


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
    max_branch_lesson_records: int = 12,
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
    branch_lesson_records = _branch_lesson_records(
        lesson_cards=lesson_cards,
        branch_summaries=branch_summaries,
        similarity_hints=similarity_hints,
        avoid_bridge_guidance=avoid_bridge_guidance,
        max_records=max_branch_lesson_records,
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
            "branch_lesson_records": branch_lesson_records,
            "portfolio_coverage": portfolio_coverage,
            "avoid_bridge_guidance": avoid_bridge_guidance,
            "opportunity_gaps": opportunity_gaps,
            "novelty_pressure": novelty_pressure,
            "material_difference_audit_records": novelty_pressure.get(
                "material_difference_audit_records",
                [],
            ),
            "cross_branch_research_metadata": (
                _cross_branch_research_metadata(
                    novelty_pressure,
                    branch_lesson_records=branch_lesson_records,
                )
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
    *,
    branch_lesson_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    records = novelty_pressure.get("material_difference_audit_records", []) or []
    lessons = branch_lesson_records or []
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
            "branch_lesson_record_count": len(lessons),
            "branch_lesson_record_ids": [
                item.get("lesson_id")
                for item in lessons
                if isinstance(item, dict) and item.get("lesson_id")
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


__all__ = [
    "build_cross_branch_research_map",
    "render_cross_branch_research_map",
]
