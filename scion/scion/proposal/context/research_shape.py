"""Prompt-only research shape diagnostics for proposal planning."""
from __future__ import annotations

import json
from typing import Any, Mapping

_SCHEMA_VERSION = "proposal_research_shape_prompt_summary.v1"
_NON_POSITIVE_OUTCOMES = {
    "abandoned",
    "blocked",
    "no_effect",
    "pre_protocol_failure",
    "regression",
    "unknown",
}


def build_proposal_research_shape_diagnostics(
    cross_branch_research_payload: Mapping[str, Any],
) -> str:
    """Return a compact proposal-only research shape summary.

    The source payload is already tainted proposal feedback.  This projection is
    intentionally generic: it exposes branch depth, repeated mechanism-family
    shape, and outcome distribution, but no problem-specific semantics or raw
    audit records.
    """
    if not isinstance(cross_branch_research_payload, Mapping):
        return ""
    branches = [
        item
        for item in cross_branch_research_payload.get("branches", []) or []
        if isinstance(item, Mapping)
    ]
    if not branches:
        return ""

    current_branch_id = str(
        cross_branch_research_payload.get("current_branch_id") or ""
    ).strip()
    depth_distribution: dict[str, int] = {}
    outcome_pattern_counts: dict[str, int] = {}
    mechanism_family_counts: dict[str, int] = {}
    non_positive_family_counts: dict[str, int] = {}
    active_branch_count = 0
    current_branch_depth = 0
    current_mechanism_families: list[str] = []
    max_observed_branch_depth = 0

    for branch in branches:
        attempts = branch.get("recent_attempts")
        depth = len(attempts) if isinstance(attempts, (list, tuple)) else 0
        max_observed_branch_depth = max(max_observed_branch_depth, depth)
        _increment(depth_distribution, _depth_bucket(depth))

        if str(branch.get("final_or_active_state") or "").strip() == "active":
            active_branch_count += 1

        outcome_pattern = _outcome_pattern(branch)
        if outcome_pattern:
            _increment(outcome_pattern_counts, outcome_pattern)

        families = _mechanism_families(branch)
        for family in families:
            _increment(mechanism_family_counts, family)
            if outcome_pattern in _NON_POSITIVE_OUTCOMES:
                _increment(non_positive_family_counts, family)

        if (
            current_branch_id
            and str(branch.get("branch_id") or "") == current_branch_id
        ):
            current_branch_depth = depth
            current_mechanism_families = families[:6]

    repeated_non_positive_families = _top_counts(
        non_positive_family_counts,
        minimum_count=2,
        limit=5,
    )
    repeated_mechanism_families = _top_counts(
        mechanism_family_counts,
        minimum_count=2,
        limit=5,
    )
    payload = _drop_empty(
        {
            "schema_version": _SCHEMA_VERSION,
            "taint": "proposal_research_feedback",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "current_branch_id": current_branch_id,
            "branch_count": len(branches),
            "active_branch_count": active_branch_count,
            "terminal_branch_count": max(0, len(branches) - active_branch_count),
            "current_branch_depth": current_branch_depth,
            "max_observed_branch_depth": max_observed_branch_depth,
            "branch_depth_distribution": depth_distribution,
            "current_mechanism_families": current_mechanism_families,
            "mechanism_family_counts": _top_counts(mechanism_family_counts, limit=8),
            "outcome_pattern_counts": outcome_pattern_counts,
            "repeated_non_positive_families": repeated_non_positive_families,
            "repeated_mechanism_families": repeated_mechanism_families,
            "shape_label": _shape_label(
                branch_count=len(branches),
                current_depth=current_branch_depth,
                max_depth=max_observed_branch_depth,
                repeated_non_positive_families=repeated_non_positive_families,
            ),
            "proposal_guidance": _proposal_guidance(
                branch_count=len(branches),
                current_depth=current_branch_depth,
                max_depth=max_observed_branch_depth,
                repeated_non_positive_families=repeated_non_positive_families,
            ),
        }
    )
    if len(payload) <= 5:
        return ""
    return json.dumps(payload, sort_keys=True, default=str)


def _mechanism_families(branch: Mapping[str, Any]) -> list[str]:
    families = _string_list(branch.get("mechanism_families"))
    if families:
        return families[:8]
    descriptors = branch.get("research_descriptors")
    if not isinstance(descriptors, (list, tuple)):
        return []
    for descriptor in descriptors:
        if not isinstance(descriptor, Mapping):
            continue
        family = str(descriptor.get("mechanism_family") or "").strip()
        if family and family not in families:
            families.append(family)
    return families[:8]


def _outcome_pattern(branch: Mapping[str, Any]) -> str:
    outcome_summary = branch.get("outcome_summary")
    if isinstance(outcome_summary, Mapping):
        pattern = str(outcome_summary.get("outcome_pattern") or "").strip()
        if pattern:
            return pattern
    evidence_profile = branch.get("evidence_profile")
    if isinstance(evidence_profile, Mapping):
        pattern = str(evidence_profile.get("outcome_pattern") or "").strip()
        if pattern:
            return pattern
    return ""


def _proposal_guidance(
    *,
    branch_count: int,
    current_depth: int,
    max_depth: int,
    repeated_non_positive_families: list[dict[str, Any]],
) -> list[str]:
    guidance: list[str] = []
    if branch_count >= 2 and max_depth <= 1:
        guidance.append(
            "Portfolio is shallow; prefer follow-through on a concrete "
            "mechanism or a materially contrasted new family."
        )
    elif current_depth <= 1 and branch_count >= 2:
        guidance.append(
            "Current branch has low follow-up depth; explicitly choose deepen, "
            "diversify, or repair before proposing the next mechanism."
        )
    if repeated_non_positive_families:
        top_family = str(repeated_non_positive_families[0].get("family") or "")
        guidance.append(
            "Repeated non-positive family history is visible; require a clear "
            f"contrast dimension before reusing {top_family}."
        )
    if current_depth >= 3:
        guidance.append(
            "Current branch has follow-up depth; preserve the lesson thread "
            "and state what evidence changes from the prior attempt."
        )
    if not guidance:
        guidance.append(
            "Use branch depth and outcome distribution to choose deepen, "
            "diversify, or repair; do not treat this as an acceptance signal."
        )
    return guidance[:3]


def _shape_label(
    *,
    branch_count: int,
    current_depth: int,
    max_depth: int,
    repeated_non_positive_families: list[dict[str, Any]],
) -> str:
    if repeated_non_positive_families:
        return "repeated_non_positive_family"
    if branch_count >= 2 and max_depth <= 1:
        return "shallow_scatter"
    if current_depth >= 3:
        return "deep_followup"
    if current_depth <= 1 and branch_count >= 2:
        return "low_followup_depth"
    return "mixed"


def _depth_bucket(depth: int) -> str:
    if depth <= 0:
        return "0"
    if depth <= 2:
        return str(depth)
    return "3+"


def _top_counts(
    counts: Mapping[str, int],
    *,
    minimum_count: int = 1,
    limit: int = 5,
) -> list[dict[str, Any]]:
    items = [
        {"family": key, "count": value}
        for key, value in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if key and value >= minimum_count
    ]
    return items[:limit]


def _increment(counts: dict[str, int], key: str) -> None:
    if not key:
        return
    counts[key] = counts.get(key, 0) + 1


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in ("", None, [], {}, ())
    }


__all__ = ["build_proposal_research_shape_diagnostics"]
