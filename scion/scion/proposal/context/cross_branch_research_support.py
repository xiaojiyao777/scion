"""Support utilities for generic cross-branch proposal feedback."""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Iterable


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
        token
        for token in re.split(r"[^a-zA-Z0-9]+", str(value or "").lower())
        if token
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
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


__all__ = [
    "append_unique",
    "append_unique_dict",
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
    "mechanism_family",
    "mechanism_signature",
    "non_positive_count",
    "parse_similarity_key",
    "similarity_key",
    "unique",
]
