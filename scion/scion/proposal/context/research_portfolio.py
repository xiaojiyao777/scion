"""Structured branch portfolio steering artifact for proposal context.

This module projects existing cross-branch summaries into generic signatures
and similarity clusters. The output is tainted proposal guidance only; it is
not a DecisionFeatures input and it does not alter scheduling behavior.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any

from scion.proposal.context.cross_branch_research_support import (
    clean_path as _clean_path,
    clean_token as _clean_token,
    drop_empty as _drop_empty,
    unique as _unique,
)


_SCHEMA_VERSION = "portfolio_steering.v1"
_GRAPH_SCHEMA_VERSION = "branch_similarity_graph.v1"
_SIGNATURE_SCHEMA_VERSION = "branch_research_signature.v1"

_NON_POSITIVE_PATTERNS = {
    "abandoned",
    "blocked",
    "no_effect",
    "parked",
    "pre_protocol_failure",
    "regression",
}
_WEAK_OR_POSITIVE_PATTERNS = {"weak_positive", "positive"}
_CONTRAST_DIMENSIONS = [
    "mechanism_family",
    "target_file",
    "surface",
    "intervention_type",
    "effect_path",
]


def build_portfolio_steering(
    branch_summaries: Sequence[Mapping[str, Any]],
    *,
    opportunity_gaps: Sequence[Mapping[str, Any]] | None = None,
    max_signatures: int = 40,
    max_edges: int = 48,
    max_clusters: int = 16,
    max_lessons: int = 8,
    max_opportunity_gaps: int = 8,
) -> dict[str, Any]:
    """Build a generic proposal-only branch portfolio artifact."""
    signatures = _branch_research_signatures(branch_summaries)[:max_signatures]
    if not signatures:
        return {}

    edges = _similarity_edges(signatures)[:max_edges]
    clusters = _cluster_summary(signatures, edges)[:max_clusters]
    no_effect_lessons = _no_effect_lessons(clusters, max_lessons=max_lessons)
    gaps = _portfolio_opportunity_gaps(
        signatures,
        no_effect_lessons,
        opportunity_gaps=opportunity_gaps,
        max_opportunity_gaps=max_opportunity_gaps,
    )

    return _drop_empty(
        {
            "schema_version": _SCHEMA_VERSION,
            "taint": "proposal_research_feedback",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "signature_schema_version": _SIGNATURE_SCHEMA_VERSION,
            "signatures": signatures,
            "similarity_graph": _drop_empty(
                {
                    "schema_version": _GRAPH_SCHEMA_VERSION,
                    "proposal_visibility_only": True,
                    "decision_features_excluded": True,
                    "node_count": len(signatures),
                    "edge_count": len(edges),
                    "edge_types": dict(
                        sorted(Counter(edge["edge_type"] for edge in edges).items())
                    ),
                    "edges": edges,
                }
            ),
            "clusters": clusters,
            "no_effect_lessons": no_effect_lessons,
            "opportunity_gaps": gaps,
            "summary": _portfolio_summary(signatures, clusters, no_effect_lessons),
        }
    )


def _branch_research_signatures(
    branch_summaries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for summary in branch_summaries:
        branch_id = _clean_token(summary.get("branch_id")) or "unknown"
        descriptors = _summary_descriptors(summary)
        mechanism_ids = _mechanism_ids(summary)
        outcome = _as_mapping(summary.get("outcome_summary"))
        profile = _as_mapping(summary.get("evidence_profile"))
        lifecycle = _as_mapping(summary.get("lifecycle_summary"))
        rollback_reason = (
            _clean_token(lifecycle.get("last_rollback_reason")) or "none"
        )
        for descriptor in descriptors:
            signature = _signature_record(
                branch_id=branch_id,
                descriptor=descriptor,
                mechanism_ids=mechanism_ids,
                outcome=outcome,
                profile=profile,
                rollback_reason=rollback_reason,
            )
            key = (branch_id, signature["signature_digest"])
            if key in seen:
                continue
            seen.add(key)
            signatures.append(signature)
    return sorted(
        signatures,
        key=lambda item: (
            item.get("branch_id", ""),
            item.get("mechanism_family", ""),
            item.get("target_file", ""),
            item.get("action", ""),
            item.get("signature_digest", ""),
        ),
    )


def _summary_descriptors(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_descriptors = summary.get("research_descriptors")
    descriptors: list[dict[str, Any]] = []
    if isinstance(raw_descriptors, Sequence) and not isinstance(
        raw_descriptors,
        (str, bytes),
    ):
        for raw in raw_descriptors:
            if isinstance(raw, Mapping):
                descriptors.append(
                    {
                        "mechanism_family": _clean_token(
                            raw.get("mechanism_family")
                        )
                        or "unknown",
                        "change_locus": _clean_token(raw.get("change_locus"))
                        or "unknown",
                        "target_file": _clean_path(raw.get("target_file"))
                        or "unknown",
                        "action": _clean_token(raw.get("action")) or "unknown",
                        "change_type": _clean_token(raw.get("change_type"))
                        or "unspecified",
                    }
                )
    if descriptors:
        return descriptors

    recent_attempts = summary.get("recent_attempts")
    if isinstance(recent_attempts, Sequence) and not isinstance(
        recent_attempts,
        (str, bytes),
    ):
        for raw in recent_attempts:
            if not isinstance(raw, Mapping):
                continue
            mechanism_ids = raw.get("mechanism_ids")
            mechanism_family = "unknown"
            if isinstance(mechanism_ids, Sequence) and not isinstance(
                mechanism_ids,
                (str, bytes),
            ):
                mechanism_family = _family_from_id(next(iter(mechanism_ids), ""))
            descriptors.append(
                {
                    "mechanism_family": mechanism_family,
                    "change_locus": _clean_token(raw.get("change_locus"))
                    or "unknown",
                    "target_file": _clean_path(raw.get("target_file"))
                    or "unknown",
                    "action": _clean_token(raw.get("action")) or "unknown",
                    "change_type": "unspecified",
                }
            )
    if descriptors:
        return descriptors

    family = next(
        iter(summary.get("mechanism_families", []) or []),
        "unknown",
    )
    target = next(iter(summary.get("touched_files", []) or []), "unknown")
    return [
        {
            "mechanism_family": _clean_token(family) or "unknown",
            "change_locus": "unknown",
            "target_file": _clean_path(target) or "unknown",
            "action": "unknown",
            "change_type": "unspecified",
        }
    ]


def _signature_record(
    *,
    branch_id: str,
    descriptor: Mapping[str, Any],
    mechanism_ids: list[str],
    outcome: Mapping[str, Any],
    profile: Mapping[str, Any],
    rollback_reason: str,
) -> dict[str, Any]:
    surface = _clean_token(descriptor.get("change_locus")) or "unknown"
    target_file = _clean_path(descriptor.get("target_file")) or "unknown"
    action = _clean_token(descriptor.get("action")) or "unknown"
    change_type = _clean_token(descriptor.get("change_type")) or "unspecified"
    mechanism_family = (
        _clean_token(descriptor.get("mechanism_family")) or "unknown"
    )
    outcome_pattern = (
        _clean_token(profile.get("outcome_pattern"))
        or _clean_token(outcome.get("outcome_pattern"))
        or "unknown"
    )
    activation_status = (
        _clean_token(profile.get("activation_status")) or "unknown"
    )
    effect_status = _clean_token(profile.get("effect_status")) or "unknown"
    runtime_evidence_status = (
        _clean_token(profile.get("runtime_evidence_status")) or "unknown"
    )
    stage = _clean_token(outcome.get("stage")) or "unknown"
    reason_codes = _reason_codes(outcome)
    failure_signature = _failure_signature(
        outcome_pattern=outcome_pattern,
        stage=stage,
        reason_codes=reason_codes,
        activation_status=activation_status,
        effect_status=effect_status,
    )
    weak_signal_signature = _weak_signal_signature(
        outcome_pattern=outcome_pattern,
        mechanism_family=mechanism_family,
        surface=surface,
        target_file=target_file,
        action=action,
        activation_status=activation_status,
        effect_status=effect_status,
    )
    record: dict[str, Any] = {
        "schema_version": _SIGNATURE_SCHEMA_VERSION,
        "branch_id": branch_id,
        "surface": surface,
        "change_locus": surface,
        "target_file": target_file,
        "action": action,
        "intervention_type": _intervention_type(action, change_type),
        "mechanism_family": mechanism_family,
        "mechanism_ids": mechanism_ids,
        "outcome_pattern": outcome_pattern,
        "activation_status": activation_status,
        "effect_status": effect_status,
        "runtime_evidence_status": runtime_evidence_status,
        "failure_signature": failure_signature,
        "weak_signal_signature": weak_signal_signature,
        "rollback_reason": rollback_reason or "none",
    }
    record["signature_digest"] = _digest(
        {
            key: value
            for key, value in record.items()
            if key not in {"branch_id", "schema_version", "signature_digest"}
        }
    )
    return record


def _mechanism_ids(summary: Mapping[str, Any]) -> list[str]:
    return _unique(
        _clean_token(item)
        for item in (summary.get("mechanism_ids", []) or [])
    )[:8] or ["unknown"]


def _reason_codes(outcome: Mapping[str, Any]) -> list[str]:
    return sorted(
        _unique(
            _clean_token(item)
            for item in (outcome.get("reason_codes", []) or [])
        )
    )[:8]


def _failure_signature(
    *,
    outcome_pattern: str,
    stage: str,
    reason_codes: list[str],
    activation_status: str,
    effect_status: str,
) -> dict[str, Any]:
    if outcome_pattern not in _NON_POSITIVE_PATTERNS and not reason_codes:
        return {"status": "none"}
    return {
        "status": "present",
        "outcome_pattern": outcome_pattern,
        "stage": stage,
        "reason_codes": reason_codes,
        "activation_status": activation_status,
        "effect_status": effect_status,
    }


def _weak_signal_signature(
    *,
    outcome_pattern: str,
    mechanism_family: str,
    surface: str,
    target_file: str,
    action: str,
    activation_status: str,
    effect_status: str,
) -> dict[str, Any]:
    if (
        outcome_pattern not in _WEAK_OR_POSITIVE_PATTERNS
        and effect_status != "positive_or_weak"
    ):
        return {"status": "none"}
    return {
        "status": "present",
        "outcome_pattern": outcome_pattern,
        "mechanism_family": mechanism_family,
        "surface": surface,
        "target_file": target_file,
        "action": action,
        "activation_status": activation_status,
        "effect_status": effect_status,
    }


def _similarity_edges(signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signature in signatures:
        groups[("exact_signature", signature["signature_digest"])].append(signature)
        groups[
            (
                "same_family_surface",
                "|".join(
                    (
                        signature["mechanism_family"],
                        signature["surface"],
                    )
                ),
            )
        ].append(signature)
        groups[
            (
                "same_target_action",
                "|".join((signature["target_file"], signature["action"])),
            )
        ].append(signature)
        failure_digest = _digest(signature["failure_signature"])
        if signature["failure_signature"].get("status") == "present":
            groups[("same_failure_signature", failure_digest)].append(signature)
        weak_digest = _digest(signature["weak_signal_signature"])
        if signature["weak_signal_signature"].get("status") == "present":
            groups[("weak_signal_sibling", weak_digest)].append(signature)

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for (edge_type, group_key), group in sorted(groups.items()):
        if len(_branch_ids(group)) < 2:
            continue
        for left_index, left in enumerate(group):
            for right in group[left_index + 1 :]:
                if left["branch_id"] == right["branch_id"]:
                    continue
                pair = tuple(sorted((left["signature_digest"], right["signature_digest"])))
                seen_key = (edge_type, pair[0], pair[1], group_key)
                if seen_key in seen:
                    continue
                seen.add(seen_key)
                edges.append(
                    {
                        "edge_type": edge_type,
                        "basis_digest": _digest(
                            {"edge_type": edge_type, "group_key": group_key}
                        ),
                        "left_branch_id": left["branch_id"],
                        "right_branch_id": right["branch_id"],
                        "left_signature_digest": left["signature_digest"],
                        "right_signature_digest": right["signature_digest"],
                    }
                )
    return sorted(
        edges,
        key=lambda item: (
            item["edge_type"],
            item["left_branch_id"],
            item["right_branch_id"],
            item["basis_digest"],
        ),
    )


def _cluster_summary(
    signatures: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signature in signatures:
        groups[
            (
                "family_surface_target_action",
                "|".join(
                    (
                        signature["mechanism_family"],
                        signature["surface"],
                        signature["target_file"],
                        signature["action"],
                    )
                ),
            )
        ].append(signature)
        if signature["failure_signature"].get("status") == "present":
            groups[
                (
                    "failure_signature",
                    _digest(signature["failure_signature"]),
                )
            ].append(signature)
        if signature["weak_signal_signature"].get("status") == "present":
            groups[
                (
                    "weak_signal_signature",
                    _digest(signature["weak_signal_signature"]),
                )
            ].append(signature)

    edge_counts = Counter(edge["edge_type"] for edge in edges)
    clusters: list[dict[str, Any]] = []
    for (cluster_type, group_key), group in groups.items():
        branch_ids = _branch_ids(group)
        if len(branch_ids) < 2:
            continue
        outcome_patterns = Counter(item["outcome_pattern"] for item in group)
        activation_statuses = Counter(item["activation_status"] for item in group)
        effect_statuses = Counter(item["effect_status"] for item in group)
        runtime_statuses = Counter(
            item["runtime_evidence_status"] for item in group
        )
        clusters.append(
            _drop_empty(
                {
                    "cluster_id": _digest(
                        {"cluster_type": cluster_type, "group_key": group_key}
                    ),
                    "cluster_type": cluster_type,
                    "branch_ids": branch_ids,
                    "signature_digests": sorted(
                        _unique(item["signature_digest"] for item in group)
                    ),
                    "branch_count": len(branch_ids),
                    "signature_count": len(group),
                    "shared_signature": _shared_signature(group),
                    "outcome_patterns": dict(sorted(outcome_patterns.items())),
                    "activation_statuses": dict(sorted(activation_statuses.items())),
                    "effect_statuses": dict(sorted(effect_statuses.items())),
                    "runtime_evidence_statuses": dict(
                        sorted(runtime_statuses.items())
                    ),
                    "cluster_signal": _cluster_signal(
                        outcome_patterns,
                        activation_statuses,
                        effect_statuses,
                    ),
                    "recommended_action": _cluster_recommended_action(
                        outcome_patterns,
                        effect_statuses,
                    ),
                    "similarity_edge_types": dict(sorted(edge_counts.items())),
                }
            )
        )
    return sorted(
        clusters,
        key=lambda item: (
            -int(item.get("branch_count", 0)),
            item.get("cluster_type", ""),
            item.get("cluster_id", ""),
        ),
    )


def _no_effect_lessons(
    clusters: list[dict[str, Any]],
    *,
    max_lessons: int,
) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    for cluster in clusters:
        patterns = Counter(cluster.get("outcome_patterns", {}) or {})
        effects = Counter(cluster.get("effect_statuses", {}) or {})
        if patterns.get("no_effect", 0) < 2 and effects.get("zero", 0) < 2:
            continue
        branch_ids = list(cluster.get("branch_ids", []) or [])
        lessons.append(
            {
                "lesson_type": "no_effect_plateau",
                "source_cluster_id": cluster.get("cluster_id", ""),
                "source_signature": cluster.get("shared_signature", {}),
                "branch_ids": branch_ids,
                "evidence_basis": {
                    "branch_count": cluster.get("branch_count", 0),
                    "signature_count": cluster.get("signature_count", 0),
                    "outcome_patterns": cluster.get("outcome_patterns", {}),
                    "activation_statuses": cluster.get("activation_statuses", {}),
                    "effect_statuses": cluster.get("effect_statuses", {}),
                    "runtime_evidence_statuses": cluster.get(
                        "runtime_evidence_statuses",
                        {},
                    ),
                },
                "required_contrast_dimensions": list(_CONTRAST_DIMENSIONS),
                "recommended_action": "diversify",
                "same_branch_refinement_allowed": False,
                "sibling_duplication_allowed": False,
                "reason_codes": ["PORTFOLIO_NO_EFFECT_PLATEAU"],
            }
        )
        if len(lessons) >= max_lessons:
            break
    return lessons


def _portfolio_opportunity_gaps(
    signatures: list[dict[str, Any]],
    no_effect_lessons: list[dict[str, Any]],
    *,
    opportunity_gaps: Sequence[Mapping[str, Any]] | None,
    max_opportunity_gaps: int,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for raw in opportunity_gaps or ():
        if not isinstance(raw, Mapping):
            continue
        gaps.append(
            _drop_empty(
                {
                    "gap_type": _clean_token(raw.get("gap_type"))
                    or _clean_token(raw.get("opportunity_type"))
                    or "unknown",
                    "recommended_action": _clean_token(
                        raw.get("recommended_action")
                    )
                    or "observe",
                    "priority": _clean_token(raw.get("priority")) or "medium",
                    "basis": _bounded_mapping(raw.get("basis")),
                    "reason_codes": _reason_codes(raw),
                    "confidence": raw.get("confidence"),
                }
            )
        )
        if len(gaps) >= max_opportunity_gaps:
            return gaps

    if no_effect_lessons:
        gaps.append(
            {
                "gap_type": "no_effect_contrast_gap",
                "recommended_action": "diversify",
                "priority": "high",
                "basis": {
                    "lesson_count": len(no_effect_lessons),
                    "required_contrast_dimensions": list(_CONTRAST_DIMENSIONS),
                },
                "reason_codes": ["PORTFOLIO_NO_EFFECT_CONTRAST_GAP"],
                "confidence": 0.7,
            }
        )

    action_counts = Counter(signature["action"] for signature in signatures)
    surface_counts = Counter(signature["surface"] for signature in signatures)
    if action_counts and action_counts.most_common(1)[0][1] >= 2:
        gaps.append(
            {
                "gap_type": "action_concentration_gap",
                "recommended_action": "diversify",
                "priority": "medium",
                "basis": {"observed_actions": dict(sorted(action_counts.items()))},
                "reason_codes": ["PORTFOLIO_ACTION_CONCENTRATION"],
                "confidence": 0.52,
            }
        )
    if surface_counts and surface_counts.most_common(1)[0][1] >= 2:
        gaps.append(
            {
                "gap_type": "surface_concentration_gap",
                "recommended_action": "diversify",
                "priority": "medium",
                "basis": {"observed_surfaces": dict(sorted(surface_counts.items()))},
                "reason_codes": ["PORTFOLIO_SURFACE_CONCENTRATION"],
                "confidence": 0.52,
            }
        )
    return gaps[:max_opportunity_gaps]


def _portfolio_summary(
    signatures: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    no_effect_lessons: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "signature_count": len(signatures),
        "branch_count": len(_branch_ids(signatures)),
        "cluster_count": len(clusters),
        "no_effect_lesson_count": len(no_effect_lessons),
        "outcome_patterns": dict(
            sorted(Counter(item["outcome_pattern"] for item in signatures).items())
        ),
    }


def _shared_signature(group: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "mechanism_family",
        "surface",
        "change_locus",
        "target_file",
        "action",
        "intervention_type",
    )
    shared: dict[str, Any] = {}
    for field in fields:
        values = sorted({str(item.get(field, "unknown")) for item in group})
        if len(values) == 1:
            shared[field] = values[0]
    return shared


def _cluster_signal(
    outcome_patterns: Counter[str],
    activation_statuses: Counter[str],
    effect_statuses: Counter[str],
) -> str:
    if outcome_patterns.get("no_effect", 0) >= 2 or effect_statuses.get("zero", 0) >= 2:
        return "no_effect_plateau"
    if any(pattern in _NON_POSITIVE_PATTERNS for pattern in outcome_patterns):
        return "non_positive_cluster"
    if outcome_patterns.get("weak_positive", 0) > 0:
        return "weak_signal_cluster"
    if activation_statuses.get("missing_or_zero", 0) > 0:
        return "activation_gap"
    if outcome_patterns.get("positive", 0) > 0:
        return "positive_cluster"
    return "mixed_or_unknown"


def _cluster_recommended_action(
    outcome_patterns: Counter[str],
    effect_statuses: Counter[str],
) -> str:
    if outcome_patterns.get("no_effect", 0) >= 2 or effect_statuses.get("zero", 0) >= 2:
        return "diversify"
    if outcome_patterns.get("regression", 0) or outcome_patterns.get("abandoned", 0):
        return "avoid"
    if outcome_patterns.get("weak_positive", 0) or outcome_patterns.get("positive", 0):
        return "refine"
    return "observe"


def _branch_ids(items: Sequence[Mapping[str, Any]]) -> list[str]:
    return _unique(_clean_token(item.get("branch_id")) for item in items)


def _intervention_type(action: str, change_type: str) -> str:
    action_token = _clean_token(action) or "unknown"
    change_type_token = _clean_token(change_type) or "unspecified"
    if action_token in {"create_new", "add"} or change_type_token in {"add", "create"}:
        return "create"
    if action_token == "remove" or change_type_token == "remove":
        return "remove"
    if action_token == "modify" and change_type_token in {"modify", "unspecified"}:
        return "modify"
    if change_type_token == "unspecified":
        return action_token
    return f"{action_token}_{change_type_token}"


def _family_from_id(value: Any) -> str:
    tokens = [
        token
        for token in str(value or "").replace("-", "_").split("_")
        if token
    ]
    if len(tokens) >= 2:
        return "_".join(tokens[:2])
    return tokens[0] if tokens else "unknown"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bounded_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected: dict[str, Any] = {}
    for key, child in value.items():
        clean_key = _clean_token(key)
        if not clean_key:
            continue
        if isinstance(child, Mapping):
            projected[clean_key] = _bounded_mapping(child)
        elif isinstance(child, (list, tuple)):
            projected[clean_key] = [
                item
                for item in (
                    _bounded_scalar(grandchild) for grandchild in child[:8]
                )
                if item not in ("", None)
            ]
        else:
            projected[clean_key] = _bounded_scalar(child)
    return _drop_empty(projected)


def _bounded_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:240]


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["build_portfolio_steering"]
