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
from scion.problems.cvrp.successor_review import cvrp_successor_proofs_by_family


SCHEMA_VERSION = "scion.postrun_cvrp_opportunity_usage_summary.v2"

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
        "bounded_2node_cross_exchange",
        "two_node_cross_exchange",
        "2node_cross_exchange",
        "cross_exchange",
        "segment_swap",
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
    cvrp_large_twoopt_summary: Mapping[str, Any] | None = None,
    cvrp_successor_summary: Mapping[str, Any] | None = None,
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
        "required_evidence_proofs": {},
        "evidence_gaps": [],
        "entries": [],
    }
    if family != CVRP_PROBLEM_FAMILY:
        return base

    required_evidence_proofs = _required_evidence_proofs(
        cvrp_large_twoopt_summary=cvrp_large_twoopt_summary,
        cvrp_successor_summary=cvrp_successor_summary,
    )
    required_evidence_proof = required_evidence_proofs.get(REQUIRED_MECHANISM_ID, {})
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
            entry = _proposal_usage_entry(
                session,
                report_name=report_name,
                required_evidence_proofs=required_evidence_proofs,
            )
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
        "required_evidence_proof": required_evidence_proof,
        "required_evidence_proofs": required_evidence_proofs,
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
        "required_evidence_proof": _required_evidence_proof_signature(
            payload.get("required_evidence_proof")
        ),
        "required_evidence_proofs": _required_evidence_proofs_signature(
            payload.get("required_evidence_proofs")
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
    required_evidence_proofs: Mapping[str, Any],
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
        checklist_unproven = _required_checklist_unproven(
            opportunity_families,
            session,
            required_evidence_proofs=required_evidence_proofs,
        )
        if checklist_unproven:
            usage_status = "opportunity_evidence_checklist_unproven"
            reason_codes = [
                "matched_opportunity_family",
                "required_evidence_checklist_unproven",
            ]
            reason_codes.extend(
                _required_evidence_missing_reason_codes(
                    opportunity_families,
                    required_evidence_proofs,
                )
            )
        else:
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
            "required_evidence_status": _required_evidence_status(
                opportunity_families,
                required_evidence_proofs,
            ),
            "required_evidence_family": _required_evidence_family(
                opportunity_families,
                required_evidence_proofs,
            ),
            "reason_codes": reason_codes,
        }
    )


def _proposal_terms(proposal: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("selected_surface", "action"):
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


def _required_checklist_unproven(
    opportunity_families: list[str],
    session: Mapping[str, Any],
    *,
    required_evidence_proofs: Mapping[str, Any],
) -> bool:
    for family in opportunity_families:
        proof = _proof_for_family(required_evidence_proofs, family)
        if not proof and family != REQUIRED_MECHANISM_ID:
            continue
        status = str(proof.get("checklist_status") or "").strip()
        if status == "proven":
            continue
        if status in {"unproven", "not_ready", "unavailable"}:
            return True
        if family == REQUIRED_MECHANISM_ID and not _has_structured_contrast(session):
            return True
    return False


def _required_evidence_status(
    opportunity_families: list[str],
    required_evidence_proofs: Mapping[str, Any],
) -> str:
    statuses = [
        str(proof.get("checklist_status") or "")
        for family in opportunity_families
        if (proof := _proof_for_family(required_evidence_proofs, family))
    ]
    statuses = [item for item in statuses if item]
    if not statuses:
        return ""
    if len(set(statuses)) == 1:
        return statuses[0]
    return "mixed"


def _required_evidence_family(
    opportunity_families: list[str],
    required_evidence_proofs: Mapping[str, Any],
) -> str:
    for family in opportunity_families:
        if _proof_for_family(required_evidence_proofs, family):
            return family
    return ""


def _required_evidence_missing_reason_codes(
    opportunity_families: list[str],
    required_evidence_proofs: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for family in opportunity_families:
        proof = _proof_for_family(required_evidence_proofs, family)
        reasons.extend(
            f"required_evidence_{item}"
            for item in _string_list(proof.get("missing"))
            if item
        )
    return reasons[:8]


def _required_evidence_proofs(
    *,
    cvrp_large_twoopt_summary: Mapping[str, Any] | None,
    cvrp_successor_summary: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    proofs: dict[str, dict[str, Any]] = {}
    large_twoopt_proof = _large_twoopt_required_evidence_proof(
        cvrp_large_twoopt_summary
    )
    if large_twoopt_proof:
        proofs[REQUIRED_MECHANISM_ID] = large_twoopt_proof
    proofs.update(cvrp_successor_proofs_by_family(cvrp_successor_summary))
    return proofs


def _proof_for_family(
    required_evidence_proofs: Mapping[str, Any],
    family: str,
) -> dict[str, Any]:
    return _mapping(_mapping(required_evidence_proofs).get(family))


def _large_twoopt_required_evidence_proof(
    cvrp_large_twoopt_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    summary = _mapping(cvrp_large_twoopt_summary)
    if not summary:
        return {}
    if summary.get("schema_version") != "scion.postrun_cvrp_large_twoopt_summary.v1":
        return {}
    evidence = _mapping(summary.get("evidence"))
    mechanism = _mapping(evidence.get("large_twoopt_mechanism"))
    if not mechanism:
        return {}
    requirement_statuses = _mapping(evidence.get("evidence_requirement_statuses"))
    direct = _mapping(mechanism.get("direct_evidence"))
    has_requirement_statuses = bool(requirement_statuses)
    requirement_missing = _string_list(requirement_statuses.get("missing"))
    missing = (
        requirement_missing
        if has_requirement_statuses
        else _string_list(direct.get("missing") or mechanism.get("evidence_gaps"))
    )
    checklist_complete = (
        requirement_statuses.get("complete") is True
        or str(requirement_statuses.get("status") or "") == "complete"
    )
    direct_ready = mechanism.get("direct_evidence_ready") is True
    family_available = mechanism.get("mechanism_family_available") is True
    if checklist_complete:
        checklist_status = "proven"
    elif family_available:
        checklist_status = "unproven"
    else:
        checklist_status = "not_ready"
    return _drop_empty(
        {
            "schema_version": "scion.postrun_cvrp_opportunity_required_evidence_proof.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "problem_family": CVRP_PROBLEM_FAMILY,
            "mechanism_family": REQUIRED_MECHANISM_ID,
            "source_summary_schema_version": str(summary.get("schema_version") or ""),
            "source_interpretation": str(summary.get("interpretation") or ""),
            "checklist_status": checklist_status,
            "checklist_complete": checklist_complete,
            "outcome_direct_evidence_ready": direct_ready,
            "mechanism_family_available": family_available,
            "protocol_row_count": _int(mechanism.get("protocol_row_count")),
            "complete_direct_evidence_row_count": _int(
                direct.get("complete_direct_evidence_row_count")
            ),
            "positive_effect_row_count": _int(direct.get("positive_effect_row_count")),
            "activation_observed_count": _int(direct.get("activation_observed_count")),
            "objective_effect_observed_count": _int(
                direct.get("objective_effect_observed_count")
            ),
            "phase_telemetry_observed_count": _int(
                direct.get("phase_telemetry_observed_count")
            ),
            "protected_case_complete_row_count": _int(
                direct.get("protected_case_complete_row_count")
            ),
            "protected_cases_observed": _string_list(
                direct.get("protected_cases_observed")
            ),
            "missing": missing,
        }
    )


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
    checklist_unproven = _int(
        counts.get("opportunity_evidence_checklist_unproven")
    )
    ignored = _int(counts.get("ignored_or_unproven"))
    default_repeat = _int(counts.get("default_avoid_repeat"))
    if used > 0 and checklist_unproven == 0 and ignored == 0 and default_repeat == 0:
        if _int(counts.get("contrasted_opportunity")) > 0:
            return "contrasted"
        return "used"
    if checklist_unproven > 0 and used == 0 and ignored == 0 and default_repeat == 0:
        return "checklist_unproven"
    if used > 0 or checklist_unproven > 0:
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
    checklist_unproven = _int(
        counts.get("opportunity_evidence_checklist_unproven")
    )
    if current_run_evidence and opportunity_visible and proposal_session_count > 0:
        if used + checklist_unproven <= 0:
            gaps.append("no_structured_proposal_match_to_opportunity_summary")
        if checklist_unproven > 0:
            gaps.append(
                "proposal_selected_opportunity_without_required_evidence_checklist"
            )
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
        "required_evidence_status": str(
            entry.get("required_evidence_status") or ""
        ),
        "required_evidence_family": str(entry.get("required_evidence_family") or ""),
        "reason_codes": _string_list(entry.get("reason_codes")),
    }


def _required_evidence_proof_signature(value: Any) -> dict[str, Any]:
    proof = _mapping(value)
    if not proof:
        return {}
    return {
        "schema_version": str(proof.get("schema_version") or ""),
        "problem_family": str(proof.get("problem_family") or ""),
        "mechanism_family": str(proof.get("mechanism_family") or ""),
        "checklist_status": str(proof.get("checklist_status") or ""),
        "checklist_complete": proof.get("checklist_complete") is True,
        "outcome_direct_evidence_ready": (
            proof.get("outcome_direct_evidence_ready") is True
        ),
        "mechanism_family_available": proof.get("mechanism_family_available") is True,
        "protocol_row_count": _int(proof.get("protocol_row_count")),
        "complete_direct_evidence_row_count": _int(
            proof.get("complete_direct_evidence_row_count")
        ),
        "positive_effect_row_count": _int(proof.get("positive_effect_row_count")),
        "activation_observed_count": _int(proof.get("activation_observed_count")),
        "objective_effect_observed_count": _int(
            proof.get("objective_effect_observed_count")
        ),
        "phase_telemetry_observed_count": _int(
            proof.get("phase_telemetry_observed_count")
        ),
        "protected_case_complete_row_count": _int(
            proof.get("protected_case_complete_row_count")
        ),
        "protected_cases_observed": _string_list(
            proof.get("protected_cases_observed")
        ),
        "missing": _string_list(proof.get("missing")),
    }


def _required_evidence_proofs_signature(value: Any) -> dict[str, Any]:
    proofs = _mapping(value)
    return {
        str(family): _required_evidence_proof_signature(proof)
        for family, proof in sorted(proofs.items())
        if isinstance(proof, Mapping)
    }


def _empty_counts() -> dict[str, int]:
    return {
        "used_opportunity": 0,
        "contrasted_opportunity": 0,
        "opportunity_evidence_checklist_unproven": 0,
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
