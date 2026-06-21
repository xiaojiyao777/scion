"""Support utilities for generic cross-branch proposal feedback."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

FAMILY_SUFFIXES = {
    "attempt",
    "candidate",
    "experimental",
    "followup",
    "probe",
    "refine",
    "refined",
    "refinement",
    "retry",
    "test",
    "tuned",
    "variant",
}

BRANCH_LESSON_TEXT = {
    "weak_positive": (
        "Preserve the branch-local signal and refine the same generic "
        "mechanism before changing direction."
    ),
    "regression": (
        "Do not repeat this generic signature without a stronger guard, "
        "narrower trigger, or different target."
    ),
    "no_effect": (
        "The mechanism needs a materially different activation, target, "
        "or observability path before another attempt."
    ),
    "abandoned": "Treat this branch as closed unless new structured evidence appears.",
    "parked": "Treat this branch as parked; prefer other active signals first.",
    "blocked": (
        "Repair the proposal-quality issue before interpreting this as "
        "solver-quality evidence."
    ),
}

CROSS_BRANCH_LESSON_TEXT = {
    "saturated_family": (
        "Multiple branches share this generic signature with non-positive "
        "outcomes; change family, target, or action before retrying."
    ),
    "near_duplicate": (
        "A sibling branch already explored a similar generic signature; "
        "make novelty explicit or choose a different signature."
    ),
    "weak_positive": (
        "Several branches show weak positive evidence; prefer focused "
        "refinement over broad duplication."
    ),
    "regression": (
        "Regressions cluster across branches; require stronger guards and "
        "bounded activation before revisiting the pattern."
    ),
    "no_effect": (
        "No-effect results cluster across branches; prioritize activation "
        "and effect observability changes."
    ),
    "abandoned": "Several branches were abandoned; avoid their shared signatures.",
    "parked": "Several branches are parked; use active signals first.",
}

HINT_GUIDANCE = {
    "saturated_family": (
        "Avoid another near-identical proposal unless the mechanism family, "
        "target file, locus, or action changes materially."
    ),
    "near_duplicate": (
        "Check sibling evidence before proposing this signature; explain the "
        "material difference if continuing nearby."
    ),
}

LESSON_FAILURE_MODES = {
    "weak_positive": "weak_positive_signal",
    "positive": "positive_signal",
    "regression": "negative_signal",
    "no_effect": "zero_effect",
    "abandoned": "closed_lineage",
    "parked": "paused_lineage",
    "blocked": "proposal_quality_block",
    "pre_protocol_failure": "pre_protocol_failure",
    "saturated_family": "saturated_signature",
    "near_duplicate": "near_duplicate_signature",
}

LESSON_RECOMMENDED_ACTIONS = {
    "weak_positive": "refine",
    "positive": "refine",
    "regression": "avoid",
    "no_effect": "observe",
    "abandoned": "avoid",
    "parked": "park",
    "blocked": "retry",
    "pre_protocol_failure": "retry",
    "saturated_family": "diversify",
    "near_duplicate": "diversify",
}

LESSON_EVIDENCE_STRENGTH = {
    "weak_positive": "weak",
    "positive": "moderate",
    "regression": "moderate",
    "no_effect": "moderate",
    "abandoned": "strong",
    "parked": "moderate",
    "blocked": "weak",
    "pre_protocol_failure": "weak",
    "saturated_family": "strong",
    "near_duplicate": "moderate",
}

LESSON_CONFIDENCE = {
    "weak_positive": 0.58,
    "positive": 0.62,
    "regression": 0.68,
    "no_effect": 0.64,
    "abandoned": 0.78,
    "parked": 0.62,
    "blocked": 0.48,
    "pre_protocol_failure": 0.44,
    "saturated_family": 0.76,
    "near_duplicate": 0.66,
}

GENERIC_PROPOSAL_ACTIONS = ("modify", "create_new", "remove")
MATERIAL_DIFFERENCE_DIMENSIONS = (
    "mechanism_family",
    "target_file",
    "action",
    "change_locus",
    "effect_path",
)
BRANCH_LESSON_RECORD_SCHEMA = "branch_lesson.v1"
BRANCH_LESSON_REQUIRED_CONTRAST_DIMENSIONS = (
    "mechanism_family",
    "target_file",
    "action",
    "change_locus",
    "effect_path",
    "activation_path",
    "runtime_budget_strategy",
)
BRANCH_LESSON_WEAK_POSITIVE_PATH_FIELDS = (
    "activation_path",
    "effect_path",
)
BRANCH_LESSON_WEAK_POSITIVE_RISK_OR_CONTRAST_FIELDS = (
    "risk_to_avoid",
    "contrast_dimensions",
)
MATERIAL_DIFFERENCE_EVIDENCE_STATUSES = (
    "activation_status",
    "effect_status",
    "runtime_evidence_confidence",
    "runtime_evidence_status",
)
MATERIAL_DIFFERENCE_RECORD_SCHEMA = "material_difference_requirement.v1"
_MATERIAL_DIFFERENCE_RECORD_PREFIX = "mdr"
_BRANCH_LESSON_RECORD_PREFIX = "lesson"


def branch_lesson_text(lesson_type: str) -> str:
    return BRANCH_LESSON_TEXT.get(
        lesson_type,
        "Use this branch only as weak planning context.",
    )


def cross_branch_lesson_text(lesson_type: str) -> str:
    return CROSS_BRANCH_LESSON_TEXT.get(
        lesson_type,
        "Use cross-branch patterns as tainted planning context only.",
    )


def hint_guidance(hint_type: str) -> str:
    return HINT_GUIDANCE.get(hint_type, HINT_GUIDANCE["near_duplicate"])


def lesson_failure_mode(lesson_type: str) -> str:
    return LESSON_FAILURE_MODES.get(lesson_type, "unknown_signal")


def lesson_recommended_action(lesson_type: str) -> str:
    return LESSON_RECOMMENDED_ACTIONS.get(lesson_type, "observe")


def lesson_evidence_strength(lesson_type: str) -> str:
    return LESSON_EVIDENCE_STRENGTH.get(lesson_type, "weak")


def lesson_confidence(lesson_type: str, *, branch_count: int = 1) -> float:
    base = LESSON_CONFIDENCE.get(lesson_type, 0.4)
    if branch_count <= 1:
        return base
    return min(0.9, base + min(branch_count - 1, 4) * 0.04)


def lesson_transferability(scope: str, lesson_type: str) -> str:
    if scope == "branch_local":
        return "same_branch"
    if lesson_type in {"near_duplicate", "saturated_family"}:
        return "shared_signature"
    return "cross_branch_pattern"


def generic_proposal_actions() -> tuple[str, ...]:
    return GENERIC_PROPOSAL_ACTIONS


def avoid_signature_set(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[
            (
                record["mechanism_family"],
                record["target_file"],
                record["action"],
                record["change_locus"],
            )
        ].append(record)

    items: list[dict[str, Any]] = []
    for (family, target_file, action, change_locus), group in grouped.items():
        branch_ids = unique(record.get("branch_id", "") for record in group)
        if len(branch_ids) < 2:
            continue
        outcome_patterns = Counter(record["outcome_pattern"] for record in group)
        effect_statuses = Counter(record["effect_status"] for record in group)
        repeated_zero = (
            outcome_patterns.get("no_effect", 0) >= 2
            or effect_statuses.get("zero", 0) >= 2
        )
        non_positive = non_positive_count(outcome_patterns)
        if non_positive < 2 and not repeated_zero:
            continue
        activation_statuses = Counter(record["activation_status"] for record in group)
        runtime_confidences = Counter(
            record["runtime_evidence_confidence"] for record in group
        )
        runtime_statuses = Counter(
            record["runtime_evidence_status"] for record in group
        )
        active_weak_positive = unique(
            record.get("branch_id", "")
            for record in group
            if record.get("final_or_active_state") == "active"
            and record.get("outcome_pattern") == "weak_positive"
        )
        current_active_no_effect = unique(
            record.get("branch_id", "")
            for record in group
            if record.get("is_current_branch")
            and record.get("final_or_active_state") == "active"
            and record.get("outcome_pattern") == "no_effect"
        )
        same_branch_refinement_branch_ids = unique(
            (*active_weak_positive, *current_active_no_effect)
        )
        current_branch_ids = unique(
            record.get("branch_id", "")
            for record in group
            if record.get("is_current_branch")
        )
        sibling_branch_ids = [
            branch_id for branch_id in branch_ids if branch_id not in current_branch_ids
        ]
        pressure_type = (
            "repeated_zero_effect_signature"
            if repeated_zero
            else "non_positive_signature"
        )
        signature = {
            "mechanism_family": family,
            "target_file": target_file,
            "action": action,
            "change_locus": change_locus,
        }
        requirements = material_difference_requirement(
            signature,
            required_for=(
                "sibling_nearby_attempt"
                if same_branch_refinement_branch_ids
                else "another_nearby_attempt"
            ),
            same_branch_refinement_allowed=bool(same_branch_refinement_branch_ids),
        )
        items.append(
            drop_empty(
                {
                    "pressure_type": pressure_type,
                    "source": "proposal_only",
                    "decision_input_policy": "excluded_from_decision_features",
                    "priority": "high",
                    "shared_signature": signature,
                    "branch_ids": branch_ids,
                    "current_branch_ids": current_branch_ids,
                    "sibling_branch_ids": sibling_branch_ids,
                    "active_weak_positive_branch_ids": active_weak_positive,
                    "current_active_no_effect_branch_ids": current_active_no_effect,
                    "same_branch_refinement_allowed": bool(
                        same_branch_refinement_branch_ids
                    ),
                    "same_branch_refinement_allowed_branch_ids": (
                        same_branch_refinement_branch_ids
                    ),
                    "sibling_duplication_allowed": False,
                    "material_difference_required_for": requirements.get(
                        "required_for"
                    ),
                    "material_difference_requirements": requirements,
                    "outcome_patterns": dict(sorted(outcome_patterns.items())),
                    "activation_statuses": dict(sorted(activation_statuses.items())),
                    "effect_statuses": dict(sorted(effect_statuses.items())),
                    "runtime_evidence_confidences": dict(
                        sorted(runtime_confidences.items())
                    ),
                    "runtime_evidence_statuses": dict(sorted(runtime_statuses.items())),
                    "reason_codes": avoid_signature_reason_codes(
                        repeated_zero=repeated_zero,
                        non_positive=non_positive,
                    ),
                    "proposal_guidance": (
                        "Avoid another sibling or nearby proposal with this "
                        "generic signature unless it changes family, target, "
                        "action, locus, or effect path. Same-branch "
                        "weak-positive or current no-effect diagnostic "
                        "refinement remains allowed only for listed active "
                        "branches."
                    ),
                    "confidence": min(0.88, 0.68 + len(branch_ids) * 0.04),
                }
            )
        )
    return sorted(
        items,
        key=lambda item: (
            str(item.get("priority", "")) != "high",
            -len(item.get("branch_ids", []) or []),
            item.get("shared_signature", {}).get("mechanism_family", ""),
            item.get("shared_signature", {}).get("target_file", ""),
            item.get("shared_signature", {}).get("action", ""),
            item.get("shared_signature", {}).get("change_locus", ""),
        ),
    )[:8]


def avoid_signature_reason_codes(
    *,
    repeated_zero: bool,
    non_positive: int,
) -> list[str]:
    reason_codes = ["NOVELTY_AVOID_SIGNATURE_PRESSURE"]
    if non_positive >= 2:
        append_unique(reason_codes, "NOVELTY_REPEATED_NON_POSITIVE_SIGNATURE")
    if repeated_zero:
        append_unique(reason_codes, "NOVELTY_REPEATED_ZERO_EFFECT_SIGNATURE")
    return reason_codes


def blocked_signature_pressure(
    avoid_signatures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        drop_empty(
            {
                "pressure_type": "blocked_signature_pressure",
                "source": "proposal_only",
                "decision_input_policy": "excluded_from_decision_features",
                "deterministic_screening_block": False,
                "priority": item.get("priority", "high"),
                "shared_signature": item.get("shared_signature", {}),
                "branch_ids": item.get("branch_ids", []),
                "sibling_branch_ids": item.get("sibling_branch_ids", []),
                "same_branch_refinement_allowed_branch_ids": item.get(
                    "same_branch_refinement_allowed_branch_ids",
                    [],
                ),
                "recommended_action": "diversify",
                "counted_screening_pressure": (
                    "avoid_nearby_counted_screening_without_material_difference"
                ),
                "material_difference_required_for": item.get(
                    "material_difference_required_for"
                ),
                "material_difference_requirements": item.get(
                    "material_difference_requirements",
                    {},
                ),
                "reason_codes": item.get("reason_codes", []),
            }
        )
        for item in avoid_signatures
    ]


def branch_lesson_records(
    *,
    lesson_cards: Iterable[Mapping[str, Any]],
    branch_summaries: Iterable[Mapping[str, Any]],
    similarity_hints: Iterable[Mapping[str, Any]],
    avoid_bridge_guidance: Iterable[Mapping[str, Any]],
    max_records: int = 12,
) -> list[dict[str, Any]]:
    """Build stable compact lesson records for proposal-time propagation."""

    records: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    summaries_by_branch = {
        str(summary.get("branch_id")): summary
        for summary in branch_summaries
        if isinstance(summary, Mapping) and summary.get("branch_id")
    }

    for card in lesson_cards:
        if not isinstance(card, Mapping):
            continue
        scope = str(card.get("scope") or "branch_local")
        raw_lesson_type = str(card.get("lesson_type") or "unknown")
        lesson_type = _branch_lesson_type(raw_lesson_type)
        source_branch_ids = _lesson_source_branch_ids(card)
        evidence_basis = _evidence_basis_for_lesson(
            card,
            summaries_by_branch=summaries_by_branch,
            source_branch_ids=source_branch_ids,
        )
        shared_signature = _lesson_shared_signature(card, summaries_by_branch)
        record_scope = _lesson_record_scope(
            scope=scope,
            lesson_type=lesson_type,
            source_branch_ids=source_branch_ids,
            summaries_by_branch=summaries_by_branch,
        )
        lesson_role = _lesson_role(
            scope=record_scope,
            lesson_type=lesson_type,
            evidence_basis=evidence_basis,
        )
        maturity = _lesson_maturity(
            scope=record_scope,
            lesson_type=lesson_type,
            source_branch_count=len(source_branch_ids),
            evidence_basis=evidence_basis,
        )
        record = _branch_lesson_record(
            scope=record_scope,
            lesson_role=lesson_role,
            lesson_type=lesson_type,
            maturity=maturity,
            source_branch_ids=source_branch_ids,
            shared_signature=shared_signature,
            evidence_basis=evidence_basis,
            required_for=(
                "same_branch_refinement"
                if _same_branch_refinement_allowed(
                    scope=scope,
                    lesson_type=lesson_type,
                    source_branch_ids=source_branch_ids,
                    summaries_by_branch=summaries_by_branch,
                )
                else (
                    "clean_fork_new_branch"
                    if lesson_role == "borrow"
                    else "sibling_nearby_attempt"
                )
            ),
            same_branch_refinement_allowed=_same_branch_refinement_allowed(
                scope=record_scope,
                lesson_type=lesson_type,
                source_branch_ids=source_branch_ids,
                summaries_by_branch=summaries_by_branch,
            ),
            reason_codes=card.get("reason_codes", []) or [],
        )
        _append_lesson_record(records, seen_keys, record)

    for hint in similarity_hints:
        if not isinstance(hint, Mapping):
            continue
        hint_type = _branch_lesson_type(str(hint.get("hint_type") or "near_duplicate"))
        record = _branch_lesson_record(
            scope="cross_branch",
            lesson_role="contrast",
            lesson_type=hint_type,
            maturity=(
                "saturated" if hint_type == "saturated_signature" else "repeated"
            ),
            source_branch_ids=unique(
                str(item) for item in hint.get("branch_ids", []) or []
            ),
            shared_signature=_clean_material_signature(
                hint.get("shared_signature", {}) if isinstance(hint, Mapping) else {}
            ),
            evidence_basis={
                "outcome_patterns": _counter_dict(hint.get("outcome_patterns", {})),
            },
            required_for="sibling_nearby_attempt",
            same_branch_refinement_allowed=False,
            reason_codes=[
                *[str(code) for code in hint.get("reason_codes", []) or []],
                "BRANCH_LESSON_CONTRAST_REQUIRED",
            ],
        )
        _append_lesson_record(records, seen_keys, record)

    for guidance in avoid_bridge_guidance:
        if not isinstance(guidance, Mapping):
            continue
        if not _bridge_guidance(guidance):
            continue
        source_branch_ids = unique(
            str(item) for item in guidance.get("branch_ids", []) or []
        )
        same_branch_no_effect_allowed = any(
            _low_signal_source_is_current(branch_id, summaries_by_branch)
            for branch_id in source_branch_ids
        )
        record = _branch_lesson_record(
            scope="cross_branch",
            lesson_role="bridge",
            lesson_type="no_effect",
            maturity="repeated",
            source_branch_ids=source_branch_ids,
            shared_signature=_clean_material_signature(
                guidance.get("shared_signature", {})
                or guidance.get("signature", {})
                or {}
            ),
            evidence_basis={
                "outcome_patterns": _counter_dict(guidance.get("outcome_patterns", {})),
                "runtime_evidence_statuses": _counter_dict(
                    guidance.get("runtime_evidence_statuses", {})
                ),
            },
            required_for=(
                "same_branch_refinement"
                if same_branch_no_effect_allowed
                else "clean_fork_new_branch"
            ),
            same_branch_refinement_allowed=same_branch_no_effect_allowed,
            reason_codes=[
                *[str(code) for code in guidance.get("reason_codes", []) or []],
                "BRANCH_LESSON_BRIDGE_REQUIRED",
            ],
        )
        _append_lesson_record(records, seen_keys, record)

    return sorted(records, key=lambda item: item["lesson_id"])[:max_records]


def material_difference_requirements_for_avoidance(
    avoid_signatures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in avoid_signatures:
        requirement = item.get("material_difference_requirements", {})
        if not requirement:
            continue
        key = json.dumps(requirement.get("signature", {}), sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        requirements.append(requirement)
    return requirements


def material_difference_audit_records(
    avoid_signatures: list[dict[str, Any]],
    *,
    saturated_signatures: Iterable[Mapping[str, Any]] = (),
    near_duplicates: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def add_pressure(
        *,
        signature: Mapping[str, Any],
        pressure_type: str,
        pressure_source: str,
        branch_ids: Iterable[Any],
        reason_codes: Iterable[Any],
        outcome_patterns: Mapping[str, Any] | None = None,
        required_for: str = "another_nearby_attempt",
        same_branch_refinement_allowed: bool = False,
    ) -> None:
        clean_signature = _clean_material_signature(signature)
        if not clean_signature:
            return
        key = json.dumps(clean_signature, sort_keys=True, separators=(",", ":"))
        item = grouped.setdefault(
            key,
            {
                "signature": clean_signature,
                "pressure_types": set(),
                "pressure_sources": set(),
                "branch_ids": set(),
                "reason_codes": set(),
                "outcome_patterns": Counter(),
                "required_for": required_for,
                "same_branch_refinement_allowed": same_branch_refinement_allowed,
            },
        )
        item["pressure_types"].add(str(pressure_type))
        item["pressure_sources"].add(str(pressure_source))
        item["branch_ids"].update(
            str(branch_id) for branch_id in branch_ids if branch_id
        )
        item["reason_codes"].update(str(code) for code in reason_codes if code)
        if outcome_patterns:
            for pattern, count in outcome_patterns.items():
                try:
                    item["outcome_patterns"][str(pattern)] += int(count)
                except (TypeError, ValueError):
                    item["outcome_patterns"][str(pattern)] += 1
        if same_branch_refinement_allowed:
            item["same_branch_refinement_allowed"] = True
            item["required_for"] = "sibling_nearby_attempt"

    for item in avoid_signatures:
        requirement = item.get("material_difference_requirements", {})
        signature = (
            requirement.get("signature") if isinstance(requirement, Mapping) else None
        ) or item.get("shared_signature", {})
        add_pressure(
            signature=signature,
            pressure_type=str(item.get("pressure_type") or "avoid_signature_pressure"),
            pressure_source="avoid_signature_set",
            branch_ids=item.get("branch_ids", []) or [],
            reason_codes=item.get("reason_codes", []) or [],
            outcome_patterns=item.get("outcome_patterns", {}) or {},
            required_for=str(
                item.get("material_difference_required_for") or "another_nearby_attempt"
            ),
            same_branch_refinement_allowed=bool(
                item.get("same_branch_refinement_allowed")
            ),
        )

    for item in saturated_signatures:
        add_pressure(
            signature=(
                item.get("shared_signature", {}) if isinstance(item, Mapping) else {}
            ),
            pressure_type="saturated_signature",
            pressure_source="saturated_signatures",
            branch_ids=item.get("branch_ids", []) if isinstance(item, Mapping) else [],
            reason_codes=(
                item.get("reason_codes", []) if isinstance(item, Mapping) else []
            ),
            outcome_patterns=(
                item.get("outcome_patterns", {}) if isinstance(item, Mapping) else {}
            ),
        )

    for item in near_duplicates:
        add_pressure(
            signature=(
                item.get("shared_signature", {}) if isinstance(item, Mapping) else {}
            ),
            pressure_type="near_duplicate_signature",
            pressure_source="near_duplicates",
            branch_ids=item.get("branch_ids", []) if isinstance(item, Mapping) else [],
            reason_codes=(
                item.get("reason_codes", []) if isinstance(item, Mapping) else []
            ),
            outcome_patterns=(
                item.get("outcome_patterns", {}) if isinstance(item, Mapping) else {}
            ),
        )

    records = [
        _material_difference_audit_record(
            signature=item["signature"],
            pressure_types=sorted(item["pressure_types"]),
            pressure_sources=sorted(item["pressure_sources"]),
            branch_ids=sorted(item["branch_ids"]),
            reason_codes=sorted(item["reason_codes"]),
            outcome_patterns=dict(sorted(item["outcome_patterns"].items())),
            required_for=item["required_for"],
            same_branch_refinement_allowed=item["same_branch_refinement_allowed"],
        )
        for item in grouped.values()
    ]
    return sorted(records, key=lambda item: item["record_id"])[:12]


def material_difference_requirement(
    signature: dict[str, str],
    *,
    required_for: str,
    same_branch_refinement_allowed: bool,
) -> dict[str, Any]:
    payload = drop_empty(
        {
            "schema_version": MATERIAL_DIFFERENCE_RECORD_SCHEMA,
            "signature": _clean_material_signature(signature),
            "required_for": required_for,
            "minimum_requirement": "change_one_or_more_generic_dimensions",
            "required_change_dimensions": list(MATERIAL_DIFFERENCE_DIMENSIONS),
            "evidence_status_dimensions": list(MATERIAL_DIFFERENCE_EVIDENCE_STATUSES),
            "same_branch_refinement_allowed": same_branch_refinement_allowed,
            "sibling_duplication_allowed": False,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "proposal_guidance": (
                "A nearby sibling attempt needs at least one changed generic "
                "dimension: mechanism family, target file, action, change "
                "locus, or effect path. Evidence-status fields may justify "
                "the material difference but remain proposal guidance only."
            ),
        }
    )
    digest = _stable_digest(payload)
    return {
        "requirement_id": f"{_MATERIAL_DIFFERENCE_RECORD_PREFIX}:requirement:{digest[:16]}",
        "requirement_digest": digest,
        **payload,
    }


def _material_difference_audit_record(
    *,
    signature: dict[str, str],
    pressure_types: list[str],
    pressure_sources: list[str],
    branch_ids: list[str],
    reason_codes: list[str],
    outcome_patterns: dict[str, int],
    required_for: str,
    same_branch_refinement_allowed: bool,
) -> dict[str, Any]:
    requirement = material_difference_requirement(
        signature,
        required_for=required_for,
        same_branch_refinement_allowed=same_branch_refinement_allowed,
    )
    body = drop_empty(
        {
            "record_type": "material_difference_requirement",
            "schema_version": MATERIAL_DIFFERENCE_RECORD_SCHEMA,
            "requirement": requirement,
            "generic_signature": requirement["signature"],
            "family_pressure": {
                "mechanism_family": requirement["signature"].get(
                    "mechanism_family",
                    "unknown",
                ),
                "pressure_types": pressure_types,
                "pressure_sources": pressure_sources,
                "branch_count": len(branch_ids),
                "outcome_patterns": outcome_patterns,
            },
            "branch_ids": branch_ids,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        "MATERIAL_DIFFERENCE_REQUIREMENT",
                        *reason_codes,
                    ]
                )
            ),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "raw_branch_text_excluded": True,
            "raw_hypothesis_excluded": True,
            "llm_trace_excluded": True,
        }
    )
    digest = _stable_digest(body)
    return {
        "record_id": f"{_MATERIAL_DIFFERENCE_RECORD_PREFIX}:{digest[:16]}",
        "record_digest": digest,
        **body,
    }


def _clean_material_signature(signature: Mapping[str, Any]) -> dict[str, str]:
    cleaned = drop_empty(
        {
            "mechanism_family": clean_token(signature.get("mechanism_family")),
            "target_file": clean_path(signature.get("target_file")),
            "action": clean_token(signature.get("action")),
            "change_locus": clean_token(signature.get("change_locus")),
        }
    )
    return cleaned if any(cleaned.values()) else {}


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _branch_lesson_record(
    *,
    scope: str,
    lesson_role: str,
    lesson_type: str,
    maturity: str,
    source_branch_ids: list[str],
    shared_signature: Mapping[str, Any],
    evidence_basis: Mapping[str, Any],
    required_for: str,
    same_branch_refinement_allowed: bool,
    reason_codes: Iterable[Any],
) -> dict[str, Any]:
    normalized_scope = _allowed_value(
        scope,
        {"branch_local", "cross_branch", "cluster"},
        fallback="cross_branch",
    )
    normalized_role = _allowed_value(
        lesson_role,
        {"preserve", "borrow", "avoid", "contrast", "bridge"},
        fallback="contrast",
    )
    normalized_type = _allowed_value(
        lesson_type,
        {
            "weak_positive",
            "no_effect",
            "regression",
            "abandoned",
            "parked",
            "near_duplicate",
            "saturated_signature",
        },
        fallback="no_effect",
    )
    normalized_maturity = _allowed_value(
        maturity,
        {"fresh", "repeated", "saturated", "closed"},
        fallback="fresh",
    )
    body = {
        "schema_version": BRANCH_LESSON_RECORD_SCHEMA,
        "source": "proposal_only",
        "decision_input_policy": "excluded_from_decision_features",
        "scope": normalized_scope,
        "lesson_role": normalized_role,
        "lesson_type": normalized_type,
        "maturity": normalized_maturity,
        "source_branch_ids": sorted(dict.fromkeys(source_branch_ids))[:8],
        "shared_signature": _clean_material_signature(shared_signature),
        "evidence_basis": _clean_evidence_basis(evidence_basis),
        "transfer_contract": _weak_positive_transfer_contract(
            lesson_role=normalized_role,
            lesson_type=normalized_type,
            shared_signature=shared_signature,
            evidence_basis=evidence_basis,
        ),
        "required_response": _branch_lesson_required_response(
            required_for=required_for,
            lesson_role=normalized_role,
            lesson_type=normalized_type,
            same_branch_refinement_allowed=same_branch_refinement_allowed,
        ),
        "reason_codes": _branch_lesson_reason_codes(reason_codes),
    }
    digest = _stable_digest(body)
    return {"lesson_id": f"{_BRANCH_LESSON_RECORD_PREFIX}:{digest[:16]}", **body}


def _branch_lesson_required_response(
    *,
    required_for: str,
    lesson_role: str,
    lesson_type: str,
    same_branch_refinement_allowed: bool,
) -> dict[str, Any]:
    response = {
        "required_for": _allowed_value(
            required_for,
            {
                "clean_fork_new_branch",
                "sibling_nearby_attempt",
                "same_branch_refinement",
            },
            fallback="sibling_nearby_attempt",
        ),
        "required_output_field": "branch_lesson_usage",
        "minimum_requirement": (
            "name_borrowed_or_avoided_lesson_and_contrast_dimension"
        ),
        "required_contrast_dimensions": list(
            BRANCH_LESSON_REQUIRED_CONTRAST_DIMENSIONS
        ),
        "same_branch_refinement_allowed": bool(same_branch_refinement_allowed),
        "sibling_duplication_allowed": False,
    }
    if lesson_type == "weak_positive" and lesson_role in {"borrow", "preserve"}:
        response.update(
            {
                "minimum_requirement": (
                    "borrow_or_preserve_or_machine_reject_with_activation_effect_linkage"
                ),
                "required_path_fields": list(BRANCH_LESSON_WEAK_POSITIVE_PATH_FIELDS),
                "required_linkage_fields": [
                    "target_file",
                    "action",
                    "mechanism_or_mechanism_change_id",
                ],
                "one_of_required_fields": list(
                    BRANCH_LESSON_WEAK_POSITIVE_RISK_OR_CONTRAST_FIELDS
                ),
                "machine_reject_fields": [
                    "rejected_weak_positive_lessons.lesson_id",
                    "rejected_weak_positive_lessons.reject_reason_code",
                    "rejected_weak_positive_lessons.target_file",
                    "rejected_weak_positive_lessons.action",
                    "rejected_weak_positive_lessons.mechanism_or_mechanism_change_id",
                ],
                "reuse_or_reject_required": True,
                "proposal_guidance": (
                    "Borrow or preserve the weak-positive lesson with "
                    "activation path, effect path, target/action/mechanism "
                    "linkage using a specific mechanism id, and at least one risk-to-avoid or contrast "
                    "dimension. If rejecting reuse, emit a machine-readable "
                    "reject reason with the same linkage. This is proposal "
                    "guidance only and does not enter DecisionFeatures."
                ),
            }
        )
    return response


def _weak_positive_transfer_contract(
    *,
    lesson_role: str,
    lesson_type: str,
    shared_signature: Mapping[str, Any],
    evidence_basis: Mapping[str, Any],
) -> dict[str, Any]:
    if lesson_type != "weak_positive" or lesson_role not in {"borrow", "preserve"}:
        return {}
    signature = _clean_material_signature(shared_signature)
    mechanism = (
        signature.get("mechanism_family")
        or signature.get("change_locus")
        or "unspecified_generic_mechanism"
    )
    return drop_empty(
        {
            "trigger_mechanism": mechanism,
            "activation_path": (
                signature.get("change_locus")
                or signature.get("mechanism_family")
                or "unspecified_activation_path"
            ),
            "effect_path": (
                signature.get("mechanism_family")
                or signature.get("change_locus")
                or "unspecified_effect_path"
            ),
            "entry_file": signature.get("target_file"),
            "entry_function": "unspecified_generic_entry",
            "risk_boundary": {
                "risk_to_avoid": "do_not_duplicate_without_target_action_mechanism_linkage",
                "evidence_basis": _clean_evidence_basis(evidence_basis),
            },
            "reuse_requirements": {
                "required_output_field": "branch_lesson_usage",
                "required_usage": "borrowed_lessons_or_preserved_same_branch_lesson",
                "required_fields": [
                    "lesson_id",
                    "lesson_type",
                    "activation_path",
                    "effect_path",
                    "target_file",
                    "action",
                    "mechanism_or_mechanism_change_id",
                ],
            },
            "reject_requirements": {
                "required_usage": "rejected_weak_positive_lessons",
                "required_fields": [
                    "lesson_id",
                    "reject_reason_code",
                    "target_file",
                    "action",
                    "mechanism_or_mechanism_change_id",
                ],
            },
        }
    )


def _branch_lesson_reason_codes(reason_codes: Iterable[Any]) -> list[str]:
    codes = ["BRANCH_LESSON_REQUIRED"]
    for code in reason_codes:
        append_unique(codes, clean_token(code))
    return codes[:12]


def _append_lesson_record(
    records: list[dict[str, Any]],
    seen_keys: set[str],
    record: dict[str, Any],
) -> None:
    if not record:
        return
    key = record["lesson_id"]
    if key in seen_keys:
        return
    seen_keys.add(key)
    records.append(record)


def _lesson_source_branch_ids(card: Mapping[str, Any]) -> list[str]:
    raw_ids = card.get("branch_ids")
    if not raw_ids:
        raw_ids = [card.get("branch_id")]
    return unique(str(item) for item in raw_ids or [] if item)


def _lesson_shared_signature(
    card: Mapping[str, Any],
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    raw_signature = card.get("shared_signature")
    if not raw_signature:
        raw_signature = _signature_from_mechanism_signature(
            card.get("mechanism_signature")
        )
    if not raw_signature:
        for branch_id in _lesson_source_branch_ids(card):
            summary = summaries_by_branch.get(branch_id, {})
            descriptors = summary.get("research_descriptors", []) or []
            if descriptors:
                raw_signature = descriptors[0]
                break
    return _clean_material_signature(
        raw_signature if isinstance(raw_signature, Mapping) else {}
    )


def _signature_from_mechanism_signature(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    parsed: dict[str, str] = {}
    aliases = {
        "family": "mechanism_family",
        "target": "target_file",
        "action": "action",
        "locus": "change_locus",
    }
    for part in value.split("|"):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        if key in aliases:
            parsed[aliases[key]] = raw
    return parsed


def _evidence_basis_for_lesson(
    card: Mapping[str, Any],
    *,
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
    source_branch_ids: list[str],
) -> dict[str, Any]:
    outcome_patterns: Counter[str] = Counter()
    activation_statuses: Counter[str] = Counter()
    effect_statuses: Counter[str] = Counter()
    runtime_statuses: Counter[str] = Counter()

    for branch_id in source_branch_ids:
        summary = summaries_by_branch.get(branch_id, {})
        outcome = summary.get("outcome_summary", {}) or {}
        evidence = summary.get("evidence_profile", {}) or {}
        outcome_patterns.update(
            [
                str(
                    outcome.get("outcome_pattern")
                    or card.get("lesson_type")
                    or "unknown"
                )
            ]
        )
        activation_statuses.update(
            [str(evidence.get("activation_status") or "unknown")]
        )
        effect_statuses.update([str(evidence.get("effect_status") or "unknown")])
        runtime_statuses.update(
            [str(evidence.get("runtime_evidence_status") or "unknown")]
        )

    if not outcome_patterns:
        outcome_patterns.update([str(card.get("lesson_type") or "unknown")])

    return drop_empty(
        {
            "outcome_patterns": dict(sorted(outcome_patterns.items())),
            "activation_statuses": dict(sorted(activation_statuses.items())),
            "effect_statuses": dict(sorted(effect_statuses.items())),
            "runtime_evidence_statuses": dict(sorted(runtime_statuses.items())),
        }
    )


def _clean_evidence_basis(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "outcome_patterns",
        "activation_statuses",
        "effect_statuses",
        "runtime_evidence_statuses",
    )
    return drop_empty(
        {
            key: _counter_dict(value.get(key, {}))
            for key in allowed
            if isinstance(value.get(key, {}), Mapping)
        }
    )


def _counter_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, raw_count in sorted(value.items(), key=lambda item: str(item[0])):
        clean_key = clean_token(key)
        if not clean_key:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 1
        if count > 0:
            result[clean_key] = count
    return result


def _branch_lesson_type(value: str) -> str:
    normalized = clean_token(value)
    if normalized == "saturated_family":
        return "saturated_signature"
    if normalized in {
        "weak_positive",
        "no_effect",
        "regression",
        "abandoned",
        "parked",
        "near_duplicate",
        "saturated_signature",
    }:
        return normalized
    if normalized in {"blocked", "pre_protocol_failure"}:
        return "no_effect"
    return "no_effect"


def _lesson_role(
    *,
    scope: str,
    lesson_type: str,
    evidence_basis: Mapping[str, Any],
) -> str:
    if _bridge_evidence(evidence_basis):
        return "bridge"
    if lesson_type == "weak_positive":
        return "preserve" if scope == "branch_local" else "borrow"
    if lesson_type in {"near_duplicate", "saturated_signature"}:
        return "contrast"
    return "avoid"


def _lesson_record_scope(
    *,
    scope: str,
    lesson_type: str,
    source_branch_ids: list[str],
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> str:
    if lesson_type != "weak_positive" or scope != "branch_local":
        return scope
    if any(
        _weak_positive_source_is_current(branch_id, summaries_by_branch)
        for branch_id in source_branch_ids
    ):
        return "branch_local"
    if any(
        _weak_positive_source_is_transferable(branch_id, summaries_by_branch)
        for branch_id in source_branch_ids
    ):
        return "cross_branch"
    return scope


def _lesson_maturity(
    *,
    scope: str,
    lesson_type: str,
    source_branch_count: int,
    evidence_basis: Mapping[str, Any],
) -> str:
    if lesson_type in {"abandoned", "parked"}:
        return "closed"
    if lesson_type == "saturated_signature" or source_branch_count >= 3:
        return "saturated"
    if scope == "cross_branch" or source_branch_count >= 2:
        return "repeated"
    if _bridge_evidence(evidence_basis):
        return "repeated"
    return "fresh"


def _same_branch_refinement_allowed(
    *,
    scope: str,
    lesson_type: str,
    source_branch_ids: list[str],
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> bool:
    if scope != "branch_local":
        return False
    if lesson_type == "weak_positive":
        return any(
            _weak_positive_source_is_current(branch_id, summaries_by_branch)
            for branch_id in source_branch_ids
        )
    if lesson_type == "no_effect":
        return any(
            _low_signal_source_is_current(branch_id, summaries_by_branch)
            for branch_id in source_branch_ids
        )
    return False


def _low_signal_source_is_current(
    branch_id: str,
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> bool:
    summary = summaries_by_branch.get(branch_id, {})
    outcome = summary.get("outcome_summary", {}) or {}
    return (
        bool(summary.get("is_current_branch"))
        and summary.get("final_or_active_state") == "active"
        and outcome.get("outcome_pattern") == "no_effect"
    )


def _weak_positive_source_is_current(
    branch_id: str,
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> bool:
    summary = summaries_by_branch.get(branch_id, {})
    return bool(summary.get("is_current_branch")) and (
        _weak_positive_source_is_transferable(branch_id, summaries_by_branch)
    )


def _weak_positive_source_is_transferable(
    branch_id: str,
    summaries_by_branch: Mapping[str, Mapping[str, Any]],
) -> bool:
    summary = summaries_by_branch.get(branch_id, {})
    outcome = summary.get("outcome_summary", {}) or {}
    if outcome.get("outcome_pattern") != "weak_positive":
        return False
    return summary.get("final_or_active_state") in {"active", "final"}


def _bridge_guidance(value: Mapping[str, Any]) -> bool:
    guidance_type = str(value.get("guidance_type") or value.get("hint_type") or "")
    if "bridge" in guidance_type:
        return True
    return _bridge_evidence(
        {
            "runtime_evidence_statuses": value.get(
                "runtime_evidence_statuses",
                {},
            )
        }
    )


def _bridge_evidence(value: Mapping[str, Any]) -> bool:
    statuses = value.get("runtime_evidence_statuses", {})
    if not isinstance(statuses, Mapping):
        return False
    return any(
        key in statuses
        for key in (
            "fresh_champion_required",
            "insufficient",
            "low",
            "low_or_incomplete",
        )
    )


def _allowed_value(value: str, allowed: set[str], *, fallback: str) -> str:
    normalized = clean_token(value)
    return normalized if normalized in allowed else fallback


def same_branch_refinement_allowances(
    branch_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowances: list[dict[str, Any]] = []
    for summary in branch_summaries:
        outcome = summary.get("outcome_summary", {}) or {}
        outcome_pattern = str(outcome.get("outcome_pattern") or "")
        if outcome_pattern not in {"weak_positive", "no_effect"}:
            continue
        if summary.get("final_or_active_state") != "active":
            continue
        if outcome_pattern == "no_effect" and not summary.get("is_current_branch"):
            continue
        descriptors = summary.get("research_descriptors", []) or []
        signatures = [
            drop_empty(
                {
                    "mechanism_family": descriptor.get("mechanism_family"),
                    "target_file": descriptor.get("target_file"),
                    "action": descriptor.get("action"),
                    "change_locus": descriptor.get("change_locus"),
                }
            )
            for descriptor in descriptors
        ]
        no_effect = outcome_pattern == "no_effect"
        allowances.append(
            drop_empty(
                {
                    "branch_id": summary.get("branch_id"),
                    "is_current_branch": bool(summary.get("is_current_branch")),
                    "source": "proposal_only",
                    "decision_input_policy": "excluded_from_decision_features",
                    "same_branch_refinement_allowed": True,
                    "sibling_duplication_allowed": False,
                    "recommended_action": "diagnose" if no_effect else "refine",
                    "priority": "high",
                    "signatures": signatures[:4],
                    "evidence_profile": summary.get("evidence_profile", {}),
                    "reason_codes": [
                        (
                            "NOVELTY_SAME_BRANCH_NO_EFFECT_DIAGNOSTIC_ALLOWED"
                            if no_effect
                            else "NOVELTY_SAME_BRANCH_WEAK_POSITIVE_REFINEMENT_ALLOWED"
                        )
                    ],
                    "proposal_guidance": (
                        (
                            "Continue the current no-effect branch only through "
                            "same-branch diagnostic refinement that changes "
                            "trigger, effect-path, or observability evidence. "
                            "Do not copy this as a sibling duplicate without a "
                            "material signature change."
                        )
                        if no_effect
                        else (
                            "Continue the active weak-positive branch through "
                            "same-branch refinement when the proposal explains "
                            "the follow-up. Do not copy this as a sibling "
                            "duplicate without a material signature or "
                            "effect-path change."
                        )
                    ),
                    "confidence": 0.68,
                }
            )
        )
    return allowances[:6]


def non_positive_count(patterns: Counter[str]) -> int:
    return sum(
        patterns.get(item, 0)
        for item in (
            "abandoned",
            "blocked",
            "no_effect",
            "parked",
            "pre_protocol_failure",
            "regression",
        )
    )


def mechanism_family(
    mechanism_id: str,
    change_locus: str,
    target_file: str,
) -> str:
    tokens = tokenize(mechanism_id)
    while tokens and (
        tokens[-1] in FAMILY_SUFFIXES or re.fullmatch(r"v\d+", tokens[-1])
    ):
        tokens.pop()
    if len(tokens) >= 2:
        return "_".join(tokens[:2])
    if tokens:
        return tokens[0]
    if change_locus:
        return change_locus
    stem = path_stem(target_file)
    return stem or "unknown"


def fallback_mechanism_id(change_locus: str, target_file: str) -> str:
    if change_locus and target_file:
        return f"{change_locus}:{path_stem(target_file)}"
    return change_locus or path_stem(target_file) or "unknown"


def mechanism_signature(
    *,
    mechanism_id: str,
    mechanism_family: str,
    change_type: str,
    change_locus: str,
    action: str,
    target_file: str,
) -> str:
    return "|".join(
        (
            f"family={mechanism_family or 'unknown'}",
            f"id={mechanism_id or 'unknown'}",
            f"type={change_type or 'unknown'}",
            f"locus={change_locus or 'unknown'}",
            f"action={action or 'unknown'}",
            f"target={target_file or 'unknown'}",
        )
    )


def similarity_key(
    *,
    mechanism_family: str,
    change_locus: str,
    action: str,
    target_file: str,
) -> str:
    return "|".join(
        (
            mechanism_family or "unknown",
            change_locus or "unknown",
            action or "unknown",
            target_file or "unknown",
        )
    )


def parse_similarity_key(key: str) -> dict[str, str]:
    parts = key.split("|")
    values = list(parts) + ["unknown"] * max(0, 4 - len(parts))
    return {
        "mechanism_family": values[0],
        "change_locus": values[1],
        "action": values[2],
        "target_file": values[3],
    }


def tokenize(value: str) -> list[str]:
    return [
        token for token in re.split(r"[^a-zA-Z0-9]+", str(value or "").lower()) if token
    ]


def path_stem(path: str) -> str:
    value = clean_path(path)
    if not value:
        return ""
    name = value.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def clean_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/")


def clean_token(value: Any) -> str:
    return str(value or "").strip()


def first_line(value: Any, *, max_chars: int = 240) -> str:
    text = str(value or "").strip().splitlines()[0] if str(value or "").strip() else ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        append_unique(result, clean_token(value))
    return result


def append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def append_unique_dict(
    items: list[dict[str, str]],
    value: dict[str, str],
    *,
    key: str,
) -> None:
    if all(item.get(key) != value.get(key) for item in items):
        items.append(value)


def drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item for key, item in value.items() if item not in (None, "", [], {}, ())
    }


__all__ = [
    "append_unique",
    "append_unique_dict",
    "avoid_signature_set",
    "blocked_signature_pressure",
    "branch_lesson_text",
    "clean_path",
    "clean_token",
    "cross_branch_lesson_text",
    "drop_empty",
    "fallback_mechanism_id",
    "first_line",
    "generic_proposal_actions",
    "hint_guidance",
    "lesson_confidence",
    "lesson_evidence_strength",
    "lesson_failure_mode",
    "lesson_recommended_action",
    "lesson_transferability",
    "material_difference_audit_records",
    "material_difference_requirements_for_avoidance",
    "mechanism_family",
    "mechanism_signature",
    "non_positive_count",
    "parse_similarity_key",
    "same_branch_refinement_allowances",
    "similarity_key",
    "unique",
]
