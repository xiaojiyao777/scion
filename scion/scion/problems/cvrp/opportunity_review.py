"""CVRP-owned postrun review of opportunity-summary uptake."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Mapping

from scion.problems.cvrp.research_guidance import (
    CVRP_PROBLEM_FAMILY,
    DEFAULT_AVOID_DIRECTIONS,
    MEASURABLE_OPPORTUNITY_CLASSES,
    REQUIRED_MECHANISM_ID,
)


SCHEMA_VERSION = "scion.postrun_cvrp_opportunity_usage_summary.v1"

_CONTRAST_FIELD_NAMES = frozenset(
    {
        "contrasted_lessons",
        "rejected_lessons",
        "rejected_weak_positive_lessons",
    }
)

_OPPORTUNITY_FAMILY_ALIASES = {
    REQUIRED_MECHANISM_ID: (
        REQUIRED_MECHANISM_ID,
        "large_instance_two_opt",
        "large_two_opt",
        "intra_route_two_opt",
        "two_opt_seed",
        "2opt_seed",
    ),
    "bounded_local_search_variant": (
        "bounded_local_search_variant",
        "bounded_local_search",
        "deadline_aware_local_search",
        "local_search",
        "two_opt_intra_bounded",
    ),
    "destroy_repair_selection": (
        "destroy_repair_selection",
        "destroy_repair",
        "removal",
        "repair",
        "regret_insertion",
        "insertion",
    ),
    "construction_seed_portfolio": (
        "construction_seed_portfolio",
        "construction_seed",
        "seed_portfolio",
        "initial_solution",
    ),
    "acceptance_or_adaptive_weighting": (
        "acceptance_or_adaptive_weighting",
        "adaptive_weighting",
        "adaptive_weights",
        "acceptance",
        "rank_gap",
        "route_pressure",
    ),
}


def build_cvrp_opportunity_usage_summary(
    *,
    problem_family: str | None,
    current_run_evidence: bool | None = None,
    prompt_context_visibility_summary: Mapping[str, Any] | None = None,
    proposal_trajectory_manifests: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Summarize whether proposal fingerprints used visible CVRP opportunities."""

    family = str(problem_family or "")
    prompt_summary = _mapping(prompt_context_visibility_summary)
    current_run = (
        prompt_summary.get("current_run_evidence") is True
        if current_run_evidence is None
        else bool(current_run_evidence)
    )
    visibility = _opportunity_visibility(prompt_summary)
    manifests = [
        item
        for item in proposal_trajectory_manifests
        if isinstance(item, Mapping)
    ]
    base = {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "proposal_visibility_only": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "problem_family": family,
        "current_run_evidence": current_run,
        "available": False,
        "opportunity_summary_visible": visibility["visible"],
        "opportunity_visibility": visibility,
        "manifest_report_count": len(manifests),
        "proposal_session_count": 0,
        "interpretable_proposal_count": 0,
        "usage_status": "not_cvrp",
        "counts": _empty_counts(),
        "recommended_opportunity_families": _recommended_opportunity_families(),
        "default_avoid_families": _default_avoid_family_ids(),
        "evidence_gaps": [],
        "entries": [],
    }
    if family != CVRP_PROBLEM_FAMILY:
        return base

    entries: list[dict[str, Any]] = []
    counts = _empty_counts()
    session_count = 0
    interpretable_count = 0
    for manifest in manifests:
        report_name = str(manifest.get("artifact_ref") or manifest.get("path") or "")
        if not report_name:
            report_name = str(manifest.get("report") or "")
        for session in _mapping_items(manifest.get("sessions")):
            session_count += 1
            entry = _proposal_usage_entry(session, report_name=report_name)
            if entry["usage_status"] != "uninterpretable":
                interpretable_count += 1
            _increment_count(counts, entry["usage_status"])
            if len(entries) < 25:
                entries.append(entry)

    usage_status = _aggregate_usage_status(
        current_run_evidence=current_run,
        opportunity_visible=visibility["visible"],
        proposal_session_count=session_count,
        counts=counts,
    )
    evidence_gaps = _evidence_gaps(
        current_run_evidence=current_run,
        opportunity_visible=visibility["visible"],
        proposal_session_count=session_count,
        counts=counts,
    )
    return {
        **base,
        "available": True,
        "proposal_session_count": session_count,
        "interpretable_proposal_count": interpretable_count,
        "usage_status": usage_status,
        "counts": counts,
        "evidence_gaps": evidence_gaps,
        "entries": entries,
    }


def cvrp_opportunity_usage_signature(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable fields used for checker-side consistency."""

    payload = _mapping(value)
    return {
        "schema_version": str(payload.get("schema_version") or ""),
        "problem_family": str(payload.get("problem_family") or ""),
        "current_run_evidence": payload.get("current_run_evidence") is True,
        "available": payload.get("available") is True,
        "opportunity_summary_visible": (
            payload.get("opportunity_summary_visible") is True
        ),
        "usage_status": str(payload.get("usage_status") or ""),
        "manifest_report_count": _int(payload.get("manifest_report_count")),
        "proposal_session_count": _int(payload.get("proposal_session_count")),
        "interpretable_proposal_count": _int(
            payload.get("interpretable_proposal_count")
        ),
        "counts": _int_mapping(payload.get("counts")),
        "evidence_gaps": _string_list(payload.get("evidence_gaps")),
        "recommended_opportunity_families": _string_list(
            payload.get("recommended_opportunity_families")
        ),
        "default_avoid_families": _string_list(
            payload.get("default_avoid_families")
        ),
        "entries": [
            _entry_signature(item)
            for item in _mapping_items(payload.get("entries"))
        ],
    }


def _proposal_usage_entry(
    session: Mapping[str, Any],
    *,
    report_name: str,
) -> dict[str, Any]:
    proposal = _mapping(session.get("proposal_fingerprint"))
    if not proposal:
        return {
            "report": report_name,
            "session_id": str(session.get("session_id") or ""),
            "branch_id": str(session.get("branch_id") or ""),
            "usage_status": "uninterpretable",
            "opportunity_families": [],
            "default_avoid_families": [],
            "reason_codes": ["missing_proposal_fingerprint"],
        }

    terms = _proposal_terms(proposal)
    opportunity_families = _matched_opportunity_families(terms)
    default_avoid_families = _matched_default_avoid_families(terms)
    has_contrast = _has_structured_contrast(session)
    if opportunity_families:
        usage_status = (
            "contrasted_opportunity" if has_contrast else "used_opportunity"
        )
        reason_codes = ["matched_opportunity_family"]
        if has_contrast:
            reason_codes.append("structured_lesson_contrast_present")
    elif default_avoid_families:
        usage_status = "default_avoid_repeat"
        reason_codes = ["matched_default_avoid_family_without_opportunity_family"]
    else:
        usage_status = "ignored_or_unproven"
        reason_codes = ["no_structured_match_to_opportunity_summary"]

    return _drop_empty(
        {
            "report": report_name,
            "session_id": str(session.get("session_id") or ""),
            "branch_id": str(session.get("branch_id") or ""),
            "selected_surface": str(proposal.get("selected_surface") or ""),
            "action": str(proposal.get("action") or ""),
            "target_file": str(proposal.get("target_file") or ""),
            "mechanism_ids": _string_list(proposal.get("mechanism_ids")),
            "usage_status": usage_status,
            "opportunity_families": opportunity_families,
            "default_avoid_families": default_avoid_families,
            "reason_codes": reason_codes,
        }
    )


def _proposal_terms(proposal: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("selected_surface", "action", "target_file"):
        value = str(proposal.get(key) or "").strip()
        if value:
            values.append(value)
    values.extend(_string_list(proposal.get("mechanism_ids")))
    normalized = [_normalize(value) for value in values]
    return tuple(item for item in normalized if item)


def _matched_opportunity_families(terms: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for family, aliases in _OPPORTUNITY_FAMILY_ALIASES.items():
        normalized_aliases = tuple(_normalize(alias) for alias in aliases)
        if _terms_match_any(terms, normalized_aliases):
            matches.append(family)
    return sorted(matches)


def _matched_default_avoid_families(terms: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for raw in DEFAULT_AVOID_DIRECTIONS:
        family_id = _default_avoid_family_id(str(raw))
        aliases = (family_id, _normalize(str(raw)))
        if _terms_match_any(terms, aliases):
            matches.append(family_id)
    return sorted(set(matches))


def _terms_match_any(terms: tuple[str, ...], aliases: tuple[str, ...]) -> bool:
    for term in terms:
        if len(term) < 5:
            continue
        for alias in aliases:
            if len(alias) < 5:
                continue
            if term == alias or term in alias or alias in term:
                return True
    return False


def _has_structured_contrast(session: Mapping[str, Any]) -> bool:
    usage = _mapping(session.get("branch_lesson_usage_fingerprint"))
    fields = _int_mapping(usage.get("field_counts"))
    return any(fields.get(field, 0) > 0 for field in _CONTRAST_FIELD_NAMES)


def _opportunity_visibility(prompt_summary: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = _mapping(prompt_summary.get("aggregate"))
    visibility = _mapping(aggregate.get("problem_opportunity_visibility"))
    section_visible = _int(visibility.get("section_visible_trace_count"))
    hypothesis_visible = _int(
        visibility.get("hypothesis_generation_section_visible_trace_count")
    )
    return {
        "schema_version": str(visibility.get("schema_version") or ""),
        "trace_count": _int(visibility.get("trace_count")),
        "section_visible_trace_count": section_visible,
        "hypothesis_generation_section_visible_trace_count": hypothesis_visible,
        "visible": section_visible > 0 or hypothesis_visible > 0,
    }


def _aggregate_usage_status(
    *,
    current_run_evidence: bool,
    opportunity_visible: bool,
    proposal_session_count: int,
    counts: Mapping[str, int],
) -> str:
    if not current_run_evidence:
        return "not_applicable_no_current_run_evidence"
    if not opportunity_visible:
        return "not_applicable_no_visible_summary"
    if proposal_session_count <= 0:
        return "unavailable_no_proposals"
    used = _int(counts.get("used_opportunity")) + _int(
        counts.get("contrasted_opportunity")
    )
    ignored = _int(counts.get("ignored_or_unproven"))
    default_repeat = _int(counts.get("default_avoid_repeat"))
    if used > 0 and ignored == 0 and default_repeat == 0:
        if _int(counts.get("contrasted_opportunity")) > 0:
            return "contrasted"
        return "used"
    if used > 0:
        return "mixed"
    if default_repeat > 0 and ignored == 0:
        return "default_avoid_repeat"
    return "ignored_or_unproven"


def _evidence_gaps(
    *,
    current_run_evidence: bool,
    opportunity_visible: bool,
    proposal_session_count: int,
    counts: Mapping[str, int],
) -> list[str]:
    gaps: list[str] = []
    if not current_run_evidence:
        gaps.append("missing_current_run_evidence")
    if current_run_evidence and not opportunity_visible:
        gaps.append("problem_opportunity_summary_not_visible")
    if current_run_evidence and opportunity_visible and proposal_session_count <= 0:
        gaps.append("proposal_trajectory_sessions_missing")
    used = _int(counts.get("used_opportunity")) + _int(
        counts.get("contrasted_opportunity")
    )
    if current_run_evidence and opportunity_visible and proposal_session_count > 0:
        if used <= 0:
            gaps.append("no_structured_proposal_match_to_opportunity_summary")
        if _int(counts.get("default_avoid_repeat")) > 0:
            gaps.append("proposal_repeats_default_avoid_family")
    return gaps


def _recommended_opportunity_families() -> list[str]:
    families = {_normalize(REQUIRED_MECHANISM_ID): REQUIRED_MECHANISM_ID}
    for item in MEASURABLE_OPPORTUNITY_CLASSES:
        family = str(item).split(":", 1)[0].strip()
        if family:
            families[_normalize(family)] = family
    return sorted(families.values())


def _default_avoid_family_ids() -> list[str]:
    return sorted(
        _default_avoid_family_id(str(item))
        for item in DEFAULT_AVOID_DIRECTIONS
    )


def _default_avoid_family_id(value: str) -> str:
    return _normalize(value)[:96]


def _entry_signature(value: Mapping[str, Any]) -> dict[str, Any]:
    entry = _mapping(value)
    return {
        "report": str(entry.get("report") or ""),
        "session_id": str(entry.get("session_id") or ""),
        "branch_id": str(entry.get("branch_id") or ""),
        "selected_surface": str(entry.get("selected_surface") or ""),
        "action": str(entry.get("action") or ""),
        "target_file": str(entry.get("target_file") or ""),
        "mechanism_ids": _string_list(entry.get("mechanism_ids")),
        "usage_status": str(entry.get("usage_status") or ""),
        "opportunity_families": _string_list(entry.get("opportunity_families")),
        "default_avoid_families": _string_list(entry.get("default_avoid_families")),
        "reason_codes": _string_list(entry.get("reason_codes")),
    }


def _empty_counts() -> dict[str, int]:
    return {
        "used_opportunity": 0,
        "contrasted_opportunity": 0,
        "ignored_or_unproven": 0,
        "default_avoid_repeat": 0,
        "uninterpretable": 0,
    }


def _increment_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            return []
    return sorted(str(item).strip() for item in items if str(item).strip())


def _int_mapping(value: Any) -> dict[str, int]:
    mapping = _mapping(value)
    return {str(key): _int(count) for key, count in sorted(mapping.items())}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in ("", None, [], {}, ())
    }


__all__ = [
    "SCHEMA_VERSION",
    "build_cvrp_opportunity_usage_summary",
    "cvrp_opportunity_usage_signature",
]
