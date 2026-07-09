"""CVRP solver-design hypothesis quality contract."""
from __future__ import annotations

from typing import Any, Mapping

CVRP_SOLVER_DESIGN_STATIC_QUALITY_FAILURE = (
    "agent_quality_blocked:cvrp_solver_design_static_quality"
)
CVRP_CONSTRUCTION_SEED_DIRECT_EFFECT_FAILURE = (
    "agent_quality_blocked:cvrp_construction_seed_direct_effect_missing"
)
CVRP_REVIEWED_DEFAULT_AVOID_FAILURE = (
    "agent_quality_blocked:cvrp_reviewed_default_avoid"
)
CVRP_SOLVER_DESIGN_CAUSAL_PATH_FAILURE = (
    "agent_quality_blocked:cvrp_solver_design_causal_path_contract"
)
CVRP_REVIEWED_DEFAULT_AVOID_MECHANISMS = (
    (
        "route_angle_aware_2opt_star",
        (
            "successor37 valid screening abandoned this route-angle local-search "
            "order-bias path with median delta -4.25, CI [-8.0, 0.0], and "
            "CMT2/CMT4 losses"
        ),
    ),
    (
        "edge_frequency_penalty_repair",
        (
            "successor37 valid screening found only weak-positive below-MDE "
            "evidence while direct mechanism effect was zero and CMT2/CMT4 "
            "lost all seeds"
        ),
    ),
    (
        "radial_2opt_star_relink",
        (
            "successor38 valid screening found active runtime but zero accepted "
            "radial relink moves, zero direct mechanism effect, and all case "
            "gates tied"
        ),
    ),
    (
        "bounded_dual_repair_selector",
        (
            "successor39 valid screening activated the repair selector but "
            "stayed weak-positive below MDE with CMT4/B/P losses"
        ),
    ),
    (
        "bounded_two_for_one_exchange",
        (
            "successor40 valid screening activated the two-route set exchange "
            "but both rows stayed below MDE; the guarded follow-up reduced "
            "losses mostly by becoming no-op while B/CMT2/P losses remained"
        ),
    ),
    (
        "route_skeleton_regret_repair",
        (
            "successor41 and successor41b valid screenings activated "
            "route-skeleton repair but stayed below MDE; successor41b remained "
            "P/B/E loss-prone and did not force CMT2 coverage"
        ),
    ),
    (
        "elite_route_memory_repair",
        (
            "successor42b valid screening activated complete-route memory "
            "repair with direct telemetry but stayed marginal below MDE and "
            "failed CMT2/CMT4 protected-case evidence"
        ),
    ),
    (
        "bounded_destroy_operator_shadow_selector",
        (
            "successor43 valid screening activated the raw destroy-choice "
            "shadow selector and stayed marginal below MDE, but failed CMT2 "
            "and B/P protection; the generated implementation also did not "
            "isolate shadow RNG or attribute selected alternate destroy "
            "operators back to scheduler weights and traces"
        ),
    ),
    (
        "bounded_destroy_operator_shadow_selector_protected_followup",
        (
            "successor43b valid screening repaired much of the RNG and "
            "selected-operator attribution contract, but still stayed below "
            "MDE, remained unsafe on CMT2/CMT4/B, and showed local pre-VNS "
            "selector gains did not reliably preserve final trajectory quality"
        ),
    ),
    (
        "post_vns_best_anchor_acceptance_guard",
        (
            "successor44d repaired policy-effect warning hygiene and observed "
            "policy outcome evidence, but the expanded screen stayed "
            "weak-positive below MDE and B-family losses remained; unchanged "
            "successor44 acceptance-guard repeats are not long-run candidates"
        ),
    ),
    (
        "bounded_repair_placement_tournament",
        (
            "successor45 valid screening observed local repair-placement "
            "effect, but final objective evidence stayed quality-regression "
            "below MDE, CMT2/CMT4 protection failed, and the alternate repair "
            "tournament can overstate pre-VNS gains that do not preserve final "
            "trajectory quality"
        ),
    ),
    (
        "bounded_route_pool_set_partition_recombination",
        (
            "successor48 and successor49 activated bounded whole-route "
            "route-pool set-partition recombination, but the measured effect "
            "stayed zero or below MDE; same-mechanism repeats keep returning "
            "to a conservative no-op whole-route pool rather than a materially "
            "different CVRP causal path"
        ),
    ),
    (
        "route_first_heuristic",
        (
            "the route-first comparison activated normally but both screened "
            "candidates were duplicate config flips and the aggregate evidence "
            "lost to the current ALNS+VNS champion"
        ),
    ),
    (
        "material_difference_contract_repair",
        (
            "successor50 showed that a scheduler-level material-difference "
            "contract hook is repair-or-infra work, not a CVRP solver "
            "mechanism: it left the champion route search unchanged, produced "
            "zero direct objective effect, and should not consume solver-design "
            "optimization slots"
        ),
    ),
)
CVRP_SUCCESSOR37_DEFAULT_AVOID_FAILURE = CVRP_REVIEWED_DEFAULT_AVOID_FAILURE
CVRP_SUCCESSOR37_DEFAULT_AVOID_MECHANISMS = CVRP_REVIEWED_DEFAULT_AVOID_MECHANISMS

_CAUSAL_PATH_GATE = "cvrp_solver_design_causal_path_contract"
_MATERIAL_DIFFERENCE_DIMENSION_KEYS = (
    "changed_dimensions",
    "changed_dimension",
    "difference_dimensions",
    "difference_dimension",
    "contrast_dimensions",
    "contrast_dimension",
)
_MATERIAL_DIFFERENCE_CONTRAST_KEYS = (
    "contrast",
    "mechanism_contrast",
    "nearest_reviewed_mechanisms",
    "nearest_reviewed_mechanism",
    "distinct_from",
    "baseline_contrast",
    "signature_digest",
)
_MATERIAL_DIFFERENCE_EVIDENCE_KEYS = (
    "evidence",
    "evidence_basis",
    "evidence_status_delta",
    "evidence_status",
    "source_evidence",
    "review_evidence",
    "supporting_evidence",
    "signature_digest",
)
_EFFECT_TELEMETRY_KEYS = (
    "effect",
    "direct_effect",
    "objective_effect",
    "mechanism_effect",
    "direct_objective_effect",
)
_POLICY_TELEMETRY_KEYS = (
    "activity",
    "activation",
    "budget",
)
_SUCCESSOR44_MECHANISM_ID = "post_vns_best_anchor_acceptance_guard"
_PROTECTION_ROOT_KEYS = (
    "clean_fork_diversity_claim",
    "cvrp_clean_fork_diversity_claim",
    "lesson_usage",
    "applied_lesson",
)
_PROTECTION_FIELD_KEYS = (
    "protected_cases",
    "protected_case_plan",
    "case_protection",
    "case_protection_plan",
    "case_protection_evidence",
    "protection_plan",
    "protection_evidence",
)
_PROTECTED_CASES = ("CMT2", "CMT4")
_ALGORITHMIC_TRAJECTORY_TERMS = (
    "solve_trajectory",
    "search_trajectory",
    "search_state",
    "candidate_state",
    "route_state",
    "current_state",
    "downstream_trajectory",
)
_ALGORITHMIC_CANDIDATE_TERMS = (
    "new_candidate",
    "alternate_candidate",
    "candidate_route",
    "route_candidate",
    "candidate_solution",
    "route_pool",
    "recombination",
    "generate",
    "generation",
    "selection",
    "selector",
)
_ALGORITHMIC_FINAL_EFFECT_TERMS = (
    "final_total_distance",
    "post_downstream",
    "post_vns",
    "final_objective",
    "total_distance",
    "accepted_current_best",
    "best_solution",
)
_ALGORITHMIC_ATTEMPT_TERMS = (
    "attempted",
    "attempt",
    "attempts",
    "move_attempts",
)
_ALGORITHMIC_ACCEPT_TERMS = (
    "accepted",
    "acceptance",
    "accepted_moves",
)
_ALGORITHMIC_REJECT_OR_BUDGET_TERMS = (
    "rejected",
    "reject",
    "rejects",
    "rejection",
    "budget",
    "budget_stopped",
    "budget_exhausted",
)
_REPAIR_OR_INFRA_MECHANISM_TERMS = (
    "contract_repair",
    "material_difference_contract",
    "proposal_contract",
    "context_contract",
)
_REPAIR_OR_INFRA_TEXT_TERMS = (
    "contract_gate",
    "metadata_gate",
    "metadata_preflight",
    "telemetry_only",
    "hook_gate",
    "hook_wrapper",
    "no_op_hook",
    "solver_design_context_contract",
    "scheduler_level_material_difference_contract",
)
_REPAIR_OR_INFRA_EVIDENCE_REASON = (
    "successor50 showed that contract repair, scheduler-level metadata gates, "
    "telemetry-only wrappers, and no-op hook validation are repair-or-infra "
    "work rather than CVRP solver mechanisms; retry must rewrite the solver "
    "hypothesis, not replace it with contract governance"
)


def validate_cvrp_hypothesis_quality(hypothesis: Any) -> Mapping[str, Any]:
    """Reject weak CVRP solver-design hypotheses before code generation."""

    change_locus = _string(_value(hypothesis, "change_locus"))
    target_file = _string(_value(hypothesis, "target_file"))
    if change_locus != "solver_design":
        return {"allowed": True, "gate_name": _CAUSAL_PATH_GATE}

    mechanism_ids = _mechanism_ids(hypothesis)
    default_avoid = _reviewed_default_avoid_rejection(
        mechanism_ids=mechanism_ids,
        target_file=target_file,
    )
    if default_avoid is not None:
        return default_avoid
    repair_or_infra = _repair_or_infra_rejection(
        hypothesis=hypothesis,
        mechanism_ids=mechanism_ids,
        target_file=target_file,
    )
    if repair_or_infra is not None:
        return repair_or_infra

    missing = _causal_path_missing_fields(hypothesis, mechanism_ids=mechanism_ids)
    if missing:
        return _causal_path_rejection(
            missing_fields=missing,
            mechanism_ids=mechanism_ids,
            target_file=target_file,
        )
    return {"allowed": True, "gate_name": _CAUSAL_PATH_GATE}


def _reviewed_default_avoid_rejection(
    *, mechanism_ids: list[str], target_file: str
) -> Mapping[str, Any] | None:
    for blocked_mechanism_id, evidence_reason in (
        CVRP_REVIEWED_DEFAULT_AVOID_MECHANISMS
    ):
        if blocked_mechanism_id not in mechanism_ids:
            continue
        return {
            "allowed": False,
            "detail": (
                f"{CVRP_REVIEWED_DEFAULT_AVOID_FAILURE}: "
                f"{blocked_mechanism_id} is reviewed "
                "default-avoid evidence; selected_mechanisms="
                + ",".join(mechanism_ids or ["none"])
            ),
            "gate_name": "cvrp_reviewed_default_avoid",
            "structured_rejection": {
                "source": "cvrp_problem_adapter",
                "gate_name": "cvrp_reviewed_default_avoid",
                "failure_code": CVRP_REVIEWED_DEFAULT_AVOID_FAILURE,
                "agent_block_reason": "agent_quality_blocked",
                "blocked_mechanism_id": blocked_mechanism_id,
                "selected_mechanism_ids": mechanism_ids,
                "target_file": target_file,
                "evidence_reason": evidence_reason,
                "retry_constraint": (
                    "Redraft the CVRP solver-design hypothesis before code "
                    "generation: do not repeat unchanged reviewed "
                    f"`{blocked_mechanism_id}`. Name a materially different "
                    "CVRP-owned causal path, state direct mechanism "
                    "objective-effect evidence, and include CMT2/CMT4 "
                    "protection plan with protected-case protection evidence."
                ),
                "repair_template": {
                    "repair_type": "cvrp_reviewed_default_avoid",
                    "blocked_mechanism_id": blocked_mechanism_id,
                    "required_causal_path": (
                        "materially different CVRP-owned causal path with "
                        "direct mechanism effect and protected-case plan"
                    ),
                },
                "decision_features_excluded": True,
            },
        }
    return None


def _repair_or_infra_rejection(
    *, hypothesis: Any, mechanism_ids: list[str], target_file: str
) -> Mapping[str, Any] | None:
    mechanism_text = _normalized_text(" ".join(mechanism_ids))
    proposal_text = _normalized_text(
        " ".join(
            [
                target_file,
                mechanism_text,
                _proposal_text(hypothesis, include_material_fields=True),
                " ".join(_flatten_strings(_value(hypothesis, "expected_telemetry"))),
                " ".join(_flatten_strings(_value(hypothesis, "branch_lesson_usage"))),
                _string(_value(hypothesis, "no_op_condition")),
            ]
        )
    )
    blocks_by_mechanism = any(
        term in mechanism_text for term in _REPAIR_OR_INFRA_MECHANISM_TERMS
    )
    blocks_by_scheduler_contract = target_file.endswith(
        "policies/baseline_modules/scheduler.py"
    ) and any(term in proposal_text for term in _REPAIR_OR_INFRA_TEXT_TERMS)
    if not blocks_by_mechanism and not blocks_by_scheduler_contract:
        return None

    blocked_mechanism_id = mechanism_ids[0] if mechanism_ids else "repair_or_infra"
    return {
        "allowed": False,
        "detail": (
            f"{CVRP_REVIEWED_DEFAULT_AVOID_FAILURE}: "
            f"{blocked_mechanism_id} is repair-or-infra work, not a CVRP "
            "solver mechanism; selected_mechanisms="
            + ",".join(mechanism_ids or ["none"])
        ),
        "gate_name": "cvrp_reviewed_default_avoid",
        "structured_rejection": {
            "source": "cvrp_problem_adapter",
            "gate_name": "cvrp_reviewed_default_avoid",
            "failure_code": CVRP_REVIEWED_DEFAULT_AVOID_FAILURE,
            "agent_block_reason": "agent_quality_blocked",
            "blocked_mechanism_id": blocked_mechanism_id,
            "selected_mechanism_ids": mechanism_ids,
            "target_file": target_file,
            "evidence_reason": _REPAIR_OR_INFRA_EVIDENCE_REASON,
            "retry_constraint": (
                "Redraft the CVRP solver-design hypothesis before code "
                "generation: keep the solver mechanism as the target, and "
                "repair its material_difference, CMT2/CMT4 protection, "
                "candidate-state generation or selection, attempted/accepted/"
                "rejected/budget observations, and final total_distance "
                "attribution. Do not switch the retry to scheduler-level "
                "contract repair, metadata preflight, telemetry-only wrapper, "
                "hook gate, or no-op hook validation."
            ),
            "repair_template": {
                "repair_type": "cvrp_repair_or_infra_not_solver_slot",
                "required_causal_path": (
                    "materially different CVRP-owned solver mechanism that "
                    "changes route search state and reports final objective "
                    "attribution"
                ),
            },
            "decision_features_excluded": True,
        },
    }


def _causal_path_missing_fields(
    hypothesis: Any, *, mechanism_ids: list[str]
) -> list[str]:
    missing: list[str] = []
    if not mechanism_ids:
        missing.append("mechanism_changes.id")
    if not _material_difference_satisfied(_value(hypothesis, "material_difference")):
        missing.append("material_difference")
    expected_telemetry = _value(hypothesis, "expected_telemetry")
    if _successor44_policy_telemetry_contract(mechanism_ids):
        if not _successor44_policy_telemetry_satisfied(
            expected_telemetry,
            mechanism_ids=mechanism_ids,
        ):
            missing.append("expected_telemetry.activation_or_activity")
    elif not _effect_telemetry_satisfied(
        expected_telemetry,
        mechanism_ids=mechanism_ids,
    ):
        missing.append("expected_telemetry.effect")
    if not _cmt_protection_satisfied(_value(hypothesis, "branch_lesson_usage")):
        missing.append("branch_lesson_usage.clean_fork_diversity_claim")
    if not _algorithmic_intervention_satisfied(hypothesis):
        missing.append("algorithmic_intervention_sufficiency")
    return missing


def _causal_path_rejection(
    *, missing_fields: list[str], mechanism_ids: list[str], target_file: str
) -> Mapping[str, Any]:
    successor44_policy = _successor44_policy_telemetry_contract(mechanism_ids)
    telemetry_retry_constraint = (
        (
            "For post_vns_best_anchor_acceptance_guard, do not fabricate "
            "broad-loop best_delta/improvement_counts effect telemetry. Use "
            "expected_telemetry activation/activity/budget under the declared "
            "mechanism id, record guard allow/reject trajectory evidence, and "
            "tie objective evidence to formal per-case total_distance outcomes. "
        )
        if successor44_policy
        else (
            "include direct objective-effect telemetry whose effect path or "
            "text contains the declared mechanism id, "
        )
    )
    telemetry_required_field = (
        "expected_telemetry.activation_or_activity"
        if successor44_policy
        else "expected_telemetry.effect"
    )
    required_causal_path = (
        "materially different CVRP-owned post-VNS acceptance policy with "
        "mechanism activation/activity telemetry, guard decision evidence, "
        "formal per-case total_distance evidence, and CMT2/CMT4 protection"
        if successor44_policy
        else (
            "materially different CVRP-owned causal path with direct "
            "objective-effect telemetry and CMT2/CMT4 protection"
        )
    )
    return {
        "allowed": False,
        "detail": (
            f"{CVRP_SOLVER_DESIGN_CAUSAL_PATH_FAILURE}: CVRP solver_design "
            "hypothesis must declare a materially different causal path before "
            "code generation; missing="
            + ",".join(missing_fields)
            + "; selected_mechanisms="
            + ",".join(mechanism_ids or ["none"])
        ),
        "gate_name": _CAUSAL_PATH_GATE,
        "structured_rejection": {
            "source": "cvrp_problem_adapter",
            "gate_name": _CAUSAL_PATH_GATE,
            "failure_code": CVRP_SOLVER_DESIGN_CAUSAL_PATH_FAILURE,
            "agent_block_reason": "agent_quality_blocked",
            "selected_mechanism_ids": mechanism_ids,
            "target_file": target_file,
            "missing_fields": list(missing_fields),
            "retry_constraint": (
                "Redraft the CVRP solver-design hypothesis before code "
                "generation: name a materially different CVRP-owned causal "
                f"path, {telemetry_retry_constraint}and provide "
                "structured CMT2/CMT4 protected-case protection evidence. "
                "Use this exact material_difference shape: "
                "changed_dimensions=['route_state_update'], "
                "contrast={'nearest_reviewed_mechanisms':['reviewed_id'], "
                "'difference':'specific structural contrast'}, "
                "evidence=['direct telemetry to collect']; "
                "do not use aliases such as new_dimensions, old_signature, "
                "selection_gate, module_boundary, or protected_loss_plan. "
                "Use this exact shape in branch_lesson_usage: "
                "clean_fork_diversity_claim.protected_cases=['CMT2','CMT4'] "
                "and clean_fork_diversity_claim.protection_plan with separate "
                "CMT2 and CMT4 entries. Do not put CMT2/CMT4 only in prose, "
                "material_difference, or contrast_dimensions. For selector, "
                "shadow, or filter mechanisms, separate pre_vns_local_delta "
                "diagnostics from post_downstream_or_final_total_distance_delta "
                "before claiming final objective effect. Use an explicit "
                "algorithmic_intervention record with "
                "solve_trajectory_change, "
                "candidate_state_generation_or_selection, "
                "attempted_accepted_rejected_budget_evidence, and "
                "final_total_distance_attribution. The evidence text must "
                "include attempt/accept/reject or budget-stop observations and "
                "post-downstream or final total_distance attribution. A "
                "config-only activation, default-off variant flip, or "
                "telemetry-only wrapper is not sufficient."
            ),
            "repair_template": {
                "repair_type": _CAUSAL_PATH_GATE,
                "required_fields": [
                    "mechanism_changes[].id",
                    "material_difference.changed_dimensions",
                    "material_difference.contrast",
                    "material_difference.evidence",
                    telemetry_required_field,
                    (
                        "branch_lesson_usage.clean_fork_diversity_claim."
                        "protected_cases"
                    ),
                    (
                        "branch_lesson_usage.clean_fork_diversity_claim."
                        "protection_plan"
                    ),
                    "algorithmic_intervention.solve_trajectory_change",
                    "algorithmic_intervention.candidate_state_generation_or_selection",
                    "algorithmic_intervention.attempted_accepted_rejected_budget_evidence",
                    "algorithmic_intervention.final_total_distance_attribution",
                ],
                "example_branch_lesson_usage": {
                    "clean_fork_diversity_claim": {
                        "protected_cases": ["CMT2", "CMT4"],
                        "protection_plan": {
                            "CMT2": "case-specific protection or caveat token",
                            "CMT4": "case-specific protection or caveat token",
                        },
                    }
                },
                "example_material_difference": {
                    "changed_dimensions": ["mechanism_family", "effect_path"],
                    "contrast": {
                        "nearest_reviewed_mechanism": "reviewed mechanism id",
                        "difference": "specific structural difference",
                    },
                    "evidence": [
                        "direct mechanism telemetry to collect before objective claims"
                    ],
                },
                "required_causal_path": required_causal_path,
            },
            "decision_features_excluded": True,
        },
    }


def _mechanism_ids(hypothesis: Any) -> list[str]:
    mechanism_ids: list[str] = []
    for change in _value(hypothesis, "mechanism_changes") or ():
        raw_id = change.get("id") if isinstance(change, Mapping) else getattr(change, "id", "")
        mechanism_id = _string(raw_id)
        if mechanism_id:
            mechanism_ids.append(mechanism_id)
    return mechanism_ids


def _material_difference_satisfied(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    has_difference_axis = _has_nonempty_key(
        value,
        _MATERIAL_DIFFERENCE_DIMENSION_KEYS + _MATERIAL_DIFFERENCE_CONTRAST_KEYS,
    )
    has_evidence_axis = _has_nonempty_key(
        value,
        _MATERIAL_DIFFERENCE_EVIDENCE_KEYS,
    )
    return has_difference_axis and has_evidence_axis


def _effect_telemetry_satisfied(value: Any, *, mechanism_ids: list[str]) -> bool:
    if not isinstance(value, Mapping) or not mechanism_ids:
        return False
    effect_payloads = [value[key] for key in _EFFECT_TELEMETRY_KEYS if key in value]
    if not effect_payloads or not any(_nonempty(payload) for payload in effect_payloads):
        return False
    effect_text = _normalized_text(" ".join(_flatten_strings(effect_payloads)))
    return any(_normalized_text(mechanism_id) in effect_text for mechanism_id in mechanism_ids)


def _successor44_policy_telemetry_contract(mechanism_ids: list[str]) -> bool:
    return _SUCCESSOR44_MECHANISM_ID in mechanism_ids


def _successor44_policy_telemetry_satisfied(
    value: Any, *, mechanism_ids: list[str]
) -> bool:
    if not isinstance(value, Mapping) or not mechanism_ids:
        return False
    payloads = [value[key] for key in _POLICY_TELEMETRY_KEYS if key in value]
    if not payloads or not any(_nonempty(payload) for payload in payloads):
        return False
    telemetry_text = _normalized_text(" ".join(_flatten_strings(payloads)))
    return any(_normalized_text(mechanism_id) in telemetry_text for mechanism_id in mechanism_ids)


def _cmt_protection_satisfied(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    candidates: list[Any] = [value]
    candidates.extend(value[key] for key in _PROTECTION_ROOT_KEYS if key in value)
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        protection_payloads = [
            candidate[key] for key in _PROTECTION_FIELD_KEYS if key in candidate
        ]
        if protection_payloads and _contains_all_protected_cases(protection_payloads):
            return True
    return False


def _algorithmic_intervention_satisfied(hypothesis: Any) -> bool:
    text = _normalized_text(
        " ".join(
            [
                _proposal_text(hypothesis, include_material_fields=True),
                " ".join(_flatten_strings(_value(hypothesis, "expected_telemetry"))),
                " ".join(_flatten_strings(_value(hypothesis, "branch_lesson_usage"))),
            ]
        )
    )
    if not text:
        return False
    has_trajectory_change = any(
        term in text for term in _ALGORITHMIC_TRAJECTORY_TERMS
    )
    has_candidate_state = any(term in text for term in _ALGORITHMIC_CANDIDATE_TERMS)
    has_outcome_observation = (
        any(term in text for term in _ALGORITHMIC_ATTEMPT_TERMS)
        and (
            any(term in text for term in _ALGORITHMIC_ACCEPT_TERMS)
            or "best_improved" in text
        )
        and any(term in text for term in _ALGORITHMIC_REJECT_OR_BUDGET_TERMS)
    )
    has_final_attribution = any(
        term in text for term in _ALGORITHMIC_FINAL_EFFECT_TERMS
    )
    return (
        has_trajectory_change
        and has_candidate_state
        and has_outcome_observation
        and has_final_attribution
    )


def _contains_all_protected_cases(value: Any) -> bool:
    protected_text = _case_text(value)
    return all(case.lower() in protected_text for case in _PROTECTED_CASES)


def _case_text(value: Any) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.extend(_flatten_strings(item))
        return " ".join(parts).lower()
    if isinstance(value, (list, tuple, set)):
        return " ".join(_case_text(item) for item in value).lower()
    return str(value or "").lower()


def _has_nonempty_key(value: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(_nonempty(value.get(key)) for key in keys)


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_nonempty(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_nonempty(item) for item in value)
    return value is not None


def _proposal_text(hypothesis: Any, *, include_material_fields: bool) -> str:
    fields = [
        "hypothesis_text",
        "target_weakness",
        "expected_effect",
        "target_runtime_effect",
        "complexity_claim",
        "runtime_budget_strategy",
    ]
    parts = [_string(_value(hypothesis, field)) for field in fields]
    novelty = _value(hypothesis, "novelty_signature") or {}
    if isinstance(novelty, Mapping):
        parts.extend(str(item or "") for item in novelty.values())
    if include_material_fields:
        parts.extend(_flatten_strings(_value(hypothesis, "material_difference")))
    return " ".join(parts)


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.extend(_flatten_strings(item))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_flatten_strings(item))
        return parts
    if value is None:
        return []
    return [str(value)]


def _normalized_text(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _value(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)
