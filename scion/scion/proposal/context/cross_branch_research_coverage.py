"""Coverage and gap projection for cross-branch proposal research maps.

The payloads in this module are proposal-only guidance. They summarize generic
branch descriptors and safe screening/pre-protocol feedback, but they do not
read or create DecisionFeatures.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any, Iterable

from scion.proposal.context.cross_branch_research_summary import (
    LOW_RUNTIME_CONFIDENCES as _LOW_RUNTIME_CONFIDENCES,
    LOW_RUNTIME_STATUSES as _LOW_RUNTIME_STATUSES,
)
from scion.proposal.context.cross_branch_research_support import (
    append_unique as _append_unique,
    clean_path as _clean_path,
    clean_token as _clean_token,
    drop_empty as _drop_empty,
    generic_proposal_actions as _generic_proposal_actions,
    non_positive_count as _non_positive_count,
    unique as _unique,
)


COVERAGE_DIMENSIONS = (
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


def portfolio_coverage(
    branch_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    records = coverage_records(branch_summaries)
    if not records:
        return {}
    clusters = [
        _dimension_clusters(records, dimension)
        for dimension in COVERAGE_DIMENSIONS
    ]
    return _drop_empty(
        {
            "policy": "proposal_only",
            "cluster_dimensions": list(COVERAGE_DIMENSIONS),
            "dimension_coverage": {
                dimension: values
                for dimension, values in zip(COVERAGE_DIMENSIONS, clusters)
                if values
            },
            "combined_clusters": _combined_coverage_clusters(records),
            "outcome_mix": dict(
                sorted(Counter(record["outcome_pattern"] for record in records).items())
            ),
            "low_confidence_runtime_clusters": _low_runtime_clusters(records),
        }
    )


def coverage_records(
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


def avoid_bridge_guidance(
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
                        "or family before another unchanged local retry or "
                        "sibling copy."
                    ),
                    "confidence": 0.66,
                }
            ),
        )
    return guidance[:10]


def opportunity_gaps(
    branch_summaries: list[dict[str, Any]],
    portfolio_coverage: dict[str, Any],
    novelty_pressure: dict[str, Any],
    *,
    available_actions: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    records = coverage_records(branch_summaries)
    if not records:
        return []
    gaps: list[dict[str, Any]] = []
    allowed_actions = available_action_set(available_actions)
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


def available_action_set(actions: Iterable[str] | None) -> set[str]:
    values = {
        _clean_token(action)
        for action in (actions or _generic_proposal_actions())
        if _clean_token(action)
    }
    allowed = set(_generic_proposal_actions())
    filtered = values & allowed
    return filtered or allowed


def coverage_signals(portfolio_coverage: dict[str, Any]) -> set[str]:
    signals: set[str] = set()
    for item in portfolio_coverage.get("combined_clusters", []) or []:
        signal = _clean_token(item.get("coverage_signal"))
        if signal:
            signals.add(signal)
    return signals


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


def _branch_ids_with_pattern(
    branch_summaries: list[dict[str, Any]],
    pattern: str,
) -> list[str]:
    branch_ids: list[str] = []
    for summary in branch_summaries:
        outcome = summary.get("outcome_summary", {})
        if outcome.get("outcome_pattern") == pattern:
            _append_unique(branch_ids, summary.get("branch_id", ""))
    return branch_ids


__all__ = [
    "available_action_set",
    "avoid_bridge_guidance",
    "coverage_records",
    "coverage_signals",
    "portfolio_coverage",
    "opportunity_gaps",
]
