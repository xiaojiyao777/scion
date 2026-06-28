"""CVRP successor-family postrun evidence classifiers."""

from __future__ import annotations

import re
from typing import Any, Mapping

from scion.problems.cvrp.research_guidance import (
    CVRP_PROBLEM_FAMILY,
    PROTECTED_CASES,
    SUCCESSOR_OPPORTUNITY_FAMILIES,
)


SCHEMA_VERSION = "scion.postrun_cvrp_successor_summary.v1"
PROOF_SCHEMA_VERSION = "scion.postrun_cvrp_successor_required_evidence_proof.v1"

_FAMILY_ALIASES = {
    "construction_seed_portfolio": (
        "construction_seed_portfolio",
        "construction_seed",
        "seed_portfolio",
        "initial_solution",
        "rotated_sweep_seed_tournament",
        "sweep_seed_tournament",
        "rotated_sweep_seed",
        "sweep_seed",
        "sweep_construction",
        "construction",
    ),
    "bounded_local_search_variant": (
        "bounded_local_search_variant",
        "bounded_local_search",
        "local_search",
        "deadline_aware_local_search",
        "bounded_2node_cross_exchange",
        "two_node_cross_exchange",
        "2node_cross_exchange",
        "cross_exchange",
        "intra_route_or_opt_reinsert",
        "or_opt_reinsert",
        "same_route_or_opt_reinsertion",
        "intra_route_block_reinsert",
        "bounded_same_route_or_opt_reinsertion",
        "alns_vns_intra_route_block_reinsert",
        "segment_swap",
        "route_pair_exchange",
    ),
    "destroy_repair_selection": (
        "destroy_repair_selection",
        "destroy_repair",
        "removal",
        "repair",
        "regret_insertion",
        "insertion",
        "shaw_removal",
        "worst_removal",
    ),
}


def cvrp_successor_summary(
    inventory: Mapping[str, Any],
    *,
    measurement_effect_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize direct evidence for CVRP successor opportunity families."""

    phase4 = _mapping(inventory.get("phase4_evidence_coverage"))
    launcher = _mapping(inventory.get("launcher"))
    contract = _mapping(launcher.get("prepared_run_contract"))
    problem_family = str(contract.get("problem_family") or "")
    current_run_evidence = phase4.get("current_run_evidence") is True
    base = {
        "schema_version": SCHEMA_VERSION,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": problem_family,
        "current_run_evidence": current_run_evidence,
        "available": False,
        "successor_families": list(SUCCESSOR_OPPORTUNITY_FAMILIES),
        "observed_successor_families": [],
        "by_family": {},
        "evidence_gaps": [],
    }
    if problem_family != CVRP_PROBLEM_FAMILY:
        return {**base, "evidence_gaps": ["not_cvrp"]}

    proofs = {
        family: _successor_family_proof(
            family,
            measurement_effect_summary=measurement_effect_summary,
            research_continuity_summary=research_continuity_summary,
        )
        for family in SUCCESSOR_OPPORTUNITY_FAMILIES
    }
    observed = [
        family
        for family, proof in proofs.items()
        if proof.get("mechanism_family_available") is True
    ]
    gaps: list[str] = []
    if not current_run_evidence:
        gaps.append("missing_current_run_evidence")
    if measurement_effect_summary.get("available") is not True:
        gaps.append("missing_measurement_effect_summary")
    if current_run_evidence and measurement_effect_summary.get("available") is True and not observed:
        gaps.append("no_successor_family_protocol_evidence")
    return {
        **base,
        "available": True,
        "observed_successor_families": observed,
        "by_family": proofs,
        "evidence_gaps": gaps,
    }


def cvrp_successor_proofs_by_family(
    successor_summary: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return successor proof payloads keyed by canonical family id."""

    summary = _mapping(successor_summary)
    if summary.get("schema_version") != SCHEMA_VERSION:
        return {}
    return {
        family: proof
        for family, proof in _mapping(summary.get("by_family")).items()
        if isinstance(proof, Mapping)
    }


def _successor_family_proof(
    family: str,
    *,
    measurement_effect_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = _mapping(measurement_effect_summary.get("aggregate"))
    family_effects = _matching_family_effects(
        family,
        _mapping(aggregate.get("mechanism_family_effects")),
    )
    top_rows = _matching_top_rows(family, measurement_effect_summary)
    continuity_families = _matching_continuity_families(
        family,
        research_continuity_summary,
    )
    direct = _direct_evidence(top_rows, family=family)
    protocol_row_count = max(
        sum(_int(_mapping(item).get("protocol_row_count")) for item in family_effects),
        len(top_rows),
    )
    mechanism_family_available = bool(family_effects or top_rows)
    direct["ready"] = _direct_evidence_ready(direct)
    direct["missing"] = _direct_evidence_missing(
        direct,
        mechanism_family_available=mechanism_family_available,
    )
    requirement_statuses = _requirement_statuses(
        direct,
        mechanism_family_available=mechanism_family_available,
        protocol_row_count=protocol_row_count,
    )
    checklist_complete = requirement_statuses["complete"] is True
    if checklist_complete:
        checklist_status = "proven"
    elif mechanism_family_available:
        checklist_status = "unproven"
    else:
        checklist_status = "not_ready"
    return _drop_empty(
        {
            "schema_version": PROOF_SCHEMA_VERSION,
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "problem_family": CVRP_PROBLEM_FAMILY,
            "mechanism_family": family,
            "checklist_status": checklist_status,
            "checklist_complete": checklist_complete,
            "outcome_status": _outcome_status(direct),
            "outcome_direct_evidence_ready": direct["ready"],
            "mechanism_family_available": mechanism_family_available,
            "protocol_row_count": protocol_row_count,
            "top_row_signal_count": len(top_rows),
            "continuity_families": continuity_families,
            "direct_evidence": direct,
            "evidence_requirement_statuses": requirement_statuses,
            "complete_direct_evidence_row_count": direct[
                "complete_direct_evidence_row_count"
            ],
            "positive_effect_row_count": direct["positive_effect_row_count"],
            "activation_observed_count": direct["activation_observed_count"],
            "objective_effect_observed_count": direct[
                "objective_effect_observed_count"
            ],
            "phase_telemetry_observed_count": direct[
                "phase_telemetry_observed_count"
            ],
            "protected_case_complete_row_count": direct[
                "protected_case_complete_row_count"
            ],
            "protected_cases_observed": direct["protected_cases_observed"],
            "missing": requirement_statuses["missing"],
        }
    )


def _direct_evidence(
    rows: list[Mapping[str, Any]],
    *,
    family: str,
) -> dict[str, Any]:
    evidence = {
        "ready": False,
        "missing": [],
        "required_protected_cases": list(PROTECTED_CASES),
        "protected_cases_observed": [],
        "top_rows_checked": 0,
        "complete_direct_evidence_row_count": 0,
        "positive_effect_row_count": 0,
        "activation_observed_count": 0,
        "objective_effect_observed_count": 0,
        "phase_telemetry_observed_count": 0,
        "protected_case_evidence_row_count": 0,
        "protected_case_complete_row_count": 0,
    }
    for row in rows:
        evidence["top_rows_checked"] += 1
        positive_effect = row.get("positive_effect_at_or_above_mde") is True
        activation_observed = _mechanism_activation_observed(row, family=family)
        objective_observed = _mechanism_objective_effect_observed(row, family=family)
        phase_observed = _phase_telemetry_observed(row, family=family)
        protected_cases = _protected_cases_observed(row)
        protected_complete = all(case in protected_cases for case in PROTECTED_CASES)
        if positive_effect:
            evidence["positive_effect_row_count"] += 1
        if activation_observed:
            evidence["activation_observed_count"] += 1
        if objective_observed:
            evidence["objective_effect_observed_count"] += 1
        if phase_observed:
            evidence["phase_telemetry_observed_count"] += 1
        if protected_cases:
            evidence["protected_case_evidence_row_count"] += 1
            evidence["protected_cases_observed"] = sorted(
                set(_strings(evidence.get("protected_cases_observed")))
                | protected_cases
            )
        if protected_complete:
            evidence["protected_case_complete_row_count"] += 1
        if (
            activation_observed
            and objective_observed
            and phase_observed
            and protected_complete
        ):
            evidence["complete_direct_evidence_row_count"] += 1
    return evidence


def _requirement_statuses(
    direct: Mapping[str, Any],
    *,
    mechanism_family_available: bool,
    protocol_row_count: int,
) -> dict[str, Any]:
    objective_missing: list[str] = []
    if not mechanism_family_available:
        objective_missing.append("missing_successor_mechanism_family")
    if _int(direct.get("activation_observed_count")) <= 0:
        objective_missing.append("missing_activation_observed")
    if _int(direct.get("objective_effect_observed_count")) <= 0:
        objective_missing.append("missing_objective_effect_telemetry")
    if _int(direct.get("phase_telemetry_observed_count")) <= 0:
        objective_missing.append("missing_phase_telemetry")

    observed_cases = sorted(set(_strings(direct.get("protected_cases_observed"))))
    missing_cases = [case for case in PROTECTED_CASES if case not in observed_cases]
    protected_missing = (
        ["missing_cmt_case_protection_evidence"] if missing_cases else []
    )
    requirements = {
        "successor_direct_objective_runtime_requirement": _requirement_status(
            missing=objective_missing,
            observed_fields={
                "activation_observed_count": _int(direct.get("activation_observed_count")),
                "objective_effect_observed_count": _int(
                    direct.get("objective_effect_observed_count")
                ),
                "phase_telemetry_observed_count": _int(
                    direct.get("phase_telemetry_observed_count")
                ),
                "protocol_row_count": protocol_row_count,
            },
            outcome_status=_outcome_status(direct),
        ),
        "successor_cmt2_cmt4_case_protection": _requirement_status(
            missing=protected_missing,
            observed_fields={
                "protected_case_complete_row_count": _int(
                    direct.get("protected_case_complete_row_count")
                ),
            },
            protected_cases_observed=observed_cases,
            required_protected_cases=list(PROTECTED_CASES),
            outcome_status="not_outcome_requirement",
        ),
    }
    missing = sorted(
        {
            reason
            for item in requirements.values()
            for reason in _strings(_mapping(item).get("missing_fields"))
        }
    )
    complete = all(
        _mapping(item).get("status") == "observed"
        for item in requirements.values()
    )
    return {
        "schema_version": "scion.postrun_cvrp_successor_evidence_requirement_statuses.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "missing": missing,
        "requirements": requirements,
    }


def _requirement_status(
    *,
    missing: list[str],
    observed_fields: Mapping[str, Any],
    outcome_status: str,
    protected_cases_observed: list[str] | None = None,
    required_protected_cases: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "observed" if not missing else "missing",
        "observed_fields": dict(observed_fields),
        "missing_fields": list(missing),
        "protected_cases_observed": list(protected_cases_observed or []),
        "required_protected_cases": list(required_protected_cases or []),
        "outcome_status": outcome_status,
    }


def _matching_family_effects(
    family: str,
    family_effects: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    return [
        payload
        for raw_family, payload in sorted(family_effects.items())
        if isinstance(payload, Mapping) and _family_matches(raw_family, family)
    ]


def _matching_top_rows(
    family: str,
    measurement_effect_summary: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for entry in _mapping_items(measurement_effect_summary.get("entries")):
        effect = _mapping(entry.get("protocol_effects_vs_mde"))
        for row in _mapping_items(effect.get("top_rows_by_effect_to_mde")):
            if _row_matches_family(row, family):
                rows.append(row)
    return rows


def _matching_continuity_families(
    family: str,
    research_continuity_summary: Mapping[str, Any],
) -> list[str]:
    aggregate = _mapping(research_continuity_summary.get("aggregate"))
    counts = _mapping(aggregate.get("mechanism_family_counts"))
    return sorted(raw for raw in counts if _family_matches(raw, family))


def _row_matches_family(row: Mapping[str, Any], family: str) -> bool:
    if _family_matches(row.get("mechanism_family"), family):
        return True
    evidence = _mapping(row.get("mechanism_evidence"))
    if _family_matches(evidence.get("primary_mechanism"), family):
        return True
    if _family_matches(evidence.get("primary_mechanism_id"), family):
        return True
    for item in _mapping_items(evidence.get("mechanisms")):
        if _family_matches(item.get("mechanism"), family):
            return True
    return False


def _mechanism_activation_observed(row: Mapping[str, Any], *, family: str) -> bool:
    evidence = _mapping(row.get("mechanism_evidence"))
    statuses: list[Any] = []
    if _family_matches(evidence.get("primary_mechanism"), family):
        statuses.extend(
            [
                evidence.get("primary_activation_status"),
                evidence.get("activation_evidence_status"),
            ]
        )
    for item in _mapping_items(evidence.get("mechanisms")):
        if _family_matches(item.get("mechanism"), family):
            statuses.append(item.get("activation_status"))
    return any(_status_observed(status, ("activation_observed",)) for status in statuses)


def _mechanism_objective_effect_observed(
    row: Mapping[str, Any],
    *,
    family: str,
) -> bool:
    evidence = _mapping(row.get("mechanism_evidence"))
    statuses: list[Any] = []
    if _family_matches(evidence.get("primary_mechanism"), family):
        statuses.extend(
            [
                evidence.get("primary_effect_status"),
                evidence.get("objective_effect_status"),
            ]
        )
    for item in _mapping_items(evidence.get("mechanisms")):
        if _family_matches(item.get("mechanism"), family):
            statuses.append(item.get("effect_status"))
    return any(
        _status_observed(
            status,
            (
                "objective_effect_observed",
                "mixed_objective_effect",
                "mixed_positive",
                "positive",
                "zero_objective_effect",
            ),
        )
        for status in statuses
    )


def _phase_telemetry_observed(row: Mapping[str, Any], *, family: str) -> bool:
    summary = _mapping(row.get("candidate_phase_telemetry_summary"))
    buckets = _mapping(summary.get("buckets"))
    for name, payload in buckets.items():
        if not isinstance(payload, Mapping):
            continue
        if not _phase_matches_family(str(name), family):
            continue
        if _float(payload.get("weighted_sum_ms")) not in (None, 0.0):
            return True
        if _float(payload.get("max_ms")) not in (None, 0.0):
            return True
    for key in ("solver_algorithm_phase_improvement_counts", "phase_improvement_counts"):
        if _nested_positive_count_for_phase(_mapping(summary.get(key)), family=family) > 0:
            return True
    return False


def _protected_cases_observed(row: Mapping[str, Any]) -> set[str]:
    observed: set[str] = set()
    for key in (
        "case_protection_evidence",
        "protected_case_evidence",
        "case_level_total_distance_deltas",
        "case_level_deltas",
        "case_metrics",
        "case_results",
        "case_level_results",
        "per_case_results",
        "per_case",
    ):
        observed.update(_protected_cases_from_payload(row.get(key)))
    evidence = _mapping(row.get("mechanism_evidence"))
    for key in (
        "case_protection_evidence",
        "protected_case_evidence",
        "case_level_total_distance_deltas",
        "case_level_deltas",
        "case_results",
    ):
        observed.update(_protected_cases_from_payload(evidence.get(key)))
    return observed


def _protected_cases_from_payload(value: Any) -> set[str]:
    observed: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            case = _protected_case_name(key)
            if case and _payload_has_objective_delta(item):
                observed.add(case)
            if isinstance(item, Mapping):
                embedded = _case_name_from_mapping(item)
                if embedded and _payload_has_objective_delta(item):
                    observed.add(embedded)
                observed.update(_protected_cases_from_payload(item))
            elif isinstance(item, list):
                observed.update(_protected_cases_from_payload(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                embedded = _case_name_from_mapping(item)
                if embedded and _payload_has_objective_delta(item):
                    observed.add(embedded)
                observed.update(_protected_cases_from_payload(item))
            elif isinstance(item, list):
                observed.update(_protected_cases_from_payload(item))
    return observed


def _case_name_from_mapping(value: Mapping[str, Any]) -> str | None:
    for key in (
        "case",
        "case_id",
        "case_name",
        "instance",
        "instance_id",
        "problem_case",
        "protected_case",
        "name",
    ):
        case = _protected_case_name(value.get(key))
        if case:
            return case
    return None


def _payload_has_objective_delta(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return _float(value) is not None
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(
                marker in lowered
                for marker in (
                    "candidate_minus_champion",
                    "champion_minus_candidate",
                    "candidate_minus_baseline",
                    "baseline_minus_candidate",
                    "delta",
                    "distance",
                    "objective",
                    "cost",
                    "improvement",
                )
            ) and _payload_has_numeric(item):
                return True
            if isinstance(item, (Mapping, list)) and _payload_has_objective_delta(item):
                return True
    if isinstance(value, list):
        return any(_payload_has_objective_delta(item) for item in value)
    return False


def _payload_has_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return _float(value) is not None
    if isinstance(value, Mapping):
        return any(_payload_has_numeric(item) for item in value.values())
    if isinstance(value, list):
        return any(_payload_has_numeric(item) for item in value)
    return False


def _direct_evidence_ready(direct: Mapping[str, Any]) -> bool:
    return _int(direct.get("complete_direct_evidence_row_count")) > 0


def _direct_evidence_missing(
    direct: Mapping[str, Any],
    *,
    mechanism_family_available: bool,
) -> list[str]:
    missing = []
    if not mechanism_family_available:
        missing.append("missing_successor_mechanism_family")
    if _int(direct.get("activation_observed_count")) <= 0:
        missing.append("missing_activation_observed")
    if _int(direct.get("objective_effect_observed_count")) <= 0:
        missing.append("missing_objective_effect_telemetry")
    if _int(direct.get("phase_telemetry_observed_count")) <= 0:
        missing.append("missing_phase_telemetry")
    observed = set(_strings(direct.get("protected_cases_observed")))
    if any(case not in observed for case in PROTECTED_CASES):
        missing.append("missing_cmt_case_protection_evidence")
    return missing


def _outcome_status(direct: Mapping[str, Any]) -> str:
    if _int(direct.get("positive_effect_row_count")) > 0:
        return "positive_effect_observed"
    if _int(direct.get("objective_effect_observed_count")) > 0:
        return "measured_no_positive_at_mde"
    return "not_measured"


def _family_matches(value: Any, family: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    aliases = (_normalize(family),) + tuple(
        _normalize(alias) for alias in _FAMILY_ALIASES.get(family, ())
    )
    return any(
        alias and (normalized == alias or alias in normalized or normalized in alias)
        for alias in aliases
    )


def _phase_matches_family(name: str, family: str) -> bool:
    return _family_matches(name, family)


def _nested_positive_count_for_phase(value: Mapping[str, Any], *, family: str) -> int:
    total = 0
    for key, item in value.items():
        if isinstance(item, Mapping):
            total += _nested_positive_count_for_phase(item, family=family)
        elif _phase_matches_family(str(key), family):
            total += max(0, _int(item))
    return total


def _status_observed(status: Any, accepted: tuple[str, ...]) -> bool:
    text = str(status or "").strip().lower()
    return text == "observed" or text in accepted


def _protected_case_name(value: Any) -> str | None:
    text = str(value or "").upper().replace("-", "_")
    for case in PROTECTED_CASES:
        if case in text:
            return case
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            return []
    return sorted(str(item).strip() for item in items if str(item).strip())


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in ("", None, [], {}, ())
    }


__all__ = [
    "PROOF_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "cvrp_successor_proofs_by_family",
    "cvrp_successor_summary",
]
