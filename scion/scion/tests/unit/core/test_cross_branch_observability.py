from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scion.core.evidence_recording.cross_branch_observability import (
    build_cross_branch_research_observability,
)
from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.models import (
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
from scion.core.step_result import StepResult


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver-hash",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="code-hash",
    )


def _step(
    branch_id: str,
    *,
    round_num: int,
    mechanism_id: str,
    target_file: str = "components/common.py",
    change_locus: str = "selection_policy",
    action: str = "modify",
    novelty_signature: dict | None = None,
    wins: int = 0,
    losses: int = 0,
    reason_codes: tuple[str, ...] = (),
    scheduler_audit_metadata: dict | None = None,
    proposal_session_ref: dict | None = None,
) -> StepRecord:
    ties = max(0, 4 - wins - losses)
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="Sensitive proposal text must not appear here.",
            change_locus=change_locus,
            action=action,
            target_file=target_file,
            novelty_signature=novelty_signature or {},
            mechanism_changes=(MechanismChange(id=mechanism_id, change_type="modify"),),
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=4,
                wins=wins,
                losses=losses,
                ties=ties,
                win_rate=wins / 4,
                median_delta=0.02 if wins else (-0.02 if losses else 0.0),
                ci_low=-0.05,
                ci_high=0.08,
            ),
            gate_outcome="continue",
            reason_codes=reason_codes,
            exposed_summary="compact public result",
            raw_metrics_ref="/tmp/internal-metrics.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=reason_codes,
        scheduler_audit_metadata=scheduler_audit_metadata or {},
        proposal_session_ref=proposal_session_ref,
    )


def _material_difference_record(record_id: str) -> dict:
    return {
        "record_type": "material_difference_requirement",
        "schema_version": "material_difference_requirement.v1",
        "record_id": record_id,
        "record_digest": f"{record_id}:digest",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }


def _branch_lesson_record(lesson_id: str) -> dict:
    return {
        "schema_version": "branch_lesson.v1",
        "lesson_id": lesson_id,
        "source": "proposal_only",
        "decision_input_policy": "excluded_from_decision_features",
        "scope": "cross_branch",
        "lesson_role": "contrast",
        "lesson_type": "near_duplicate",
        "maturity": "repeated",
        "source_branch_ids": ["branch-a"],
        "shared_signature": {
            "mechanism_family": "family_a",
            "target_file": "components/common.py",
            "action": "modify",
            "change_locus": "selection_policy",
        },
        "evidence_basis": {"outcome_patterns": {"no_effect": 1}},
        "required_response": {
            "required_for": "clean_fork_new_branch",
            "required_output_field": "branch_lesson_usage",
            "required_contrast_dimensions": ["target_file"],
            "sibling_duplication_allowed": False,
        },
    }


def _branch_lesson_requirement(record_id: str) -> dict:
    return {
        "schema_version": "branch_lesson_usage_requirement.v1",
        "record_type": "branch_lesson_usage_requirement",
        "record_id": record_id,
        "record_digest": f"{record_id}:digest",
        "required": True,
        "required_for": "clean_fork_new_branch",
        "required_fors": ["clean_fork_new_branch"],
        "required_output_field": "branch_lesson_usage",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }


def _cross_branch_record(record_id: str) -> dict:
    return {
        "record_type": "cross_branch_research_audit",
        "schema_version": "cross_branch_research_audit.v1",
        "record_id": record_id,
        "record_digest": f"{record_id}:digest",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }


def test_cross_branch_observability_counts_generic_proposal_context() -> None:
    steps = [
        _step(
            "branch-a",
            round_num=1,
            mechanism_id="alpha_probe",
            reason_codes=("NOVELTY_AVOID_SIGNATURE_PRESSURE",),
            scheduler_audit_metadata={
                "cross_branch_research_audit_records": [
                    _material_difference_record("mdr:alpha")
                ]
            },
        ),
        _step(
            "branch-b",
            round_num=2,
            mechanism_id="alpha_variant",
            reason_codes=("CROSS_BRANCH_NEAR_DUPLICATE",),
            scheduler_audit_metadata={
                "clean_fork_selected": True,
                "same_branch_refinement_not_selected_reason": (
                    "scheduler_selected_clean_exploration_branch"
                ),
            },
        ),
        _step(
            "branch-c",
            round_num=3,
            mechanism_id="beta_refine",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            scheduler_audit_metadata={
                "same_branch_refinement_selected": True,
                "post_finalizer_actual_branch_action": "continue_same_branch",
            },
        ),
    ]
    branch_rows = [
        {
            "id": "branch-a",
            "state": "explore",
            "branch_mechanism_ids": ["alpha_probe"],
            "branch_card": {
                "branch_id": "branch-a",
                "direction": "modify/selection_policy",
                "mechanism_ids": ["alpha_probe"],
                "target_files": ["components/common.py"],
                "generic_evidence_summary": {"tier": "no_effect"},
            },
        },
        {
            "id": "branch-b",
            "state": "explore",
            "branch_mechanism_ids": ["alpha_variant"],
            "branch_card": {
                "branch_id": "branch-b",
                "direction": "modify/selection_policy",
                "mechanism_ids": ["alpha_variant"],
                "target_files": ["components/common.py"],
                "generic_evidence_summary": {"tier": "no_effect"},
            },
        },
        {
            "id": "branch-rerouted",
            "branch_lifecycle_reroute_reason": ("repeated_contract_signature_reroute"),
        },
    ]

    payload = build_cross_branch_research_observability(
        steps=steps,
        branch_rows=branch_rows,
    )

    assert payload["schema_version"] == "cross_branch_research_observability.v1"
    assert payload["policy"] == "proposal_observability_only"
    assert payload["decision_input_policy"] == "excluded_from_decision_features"
    assert payload["step_history_scope"] == (
        "screening_and_counted_pre_protocol_failures"
    )
    assert payload["branch_state_scope"] == "branch_rows_snapshot"
    assert payload["source_counts"]["step_history_total"] == 3
    assert payload["source_counts"]["branch_row_count"] == 3
    assert payload["observable_step_count"] == 3
    assert payload["near_duplicate_count"] == 1
    assert payload["saturated_signature_count"] == 1
    assert payload["avoid_signature_count"] == 1
    assert payload["material_difference_requirement_count"] == 1
    assert payload["same_branch_refinement_allowance_count"] == 1
    assert payload["same_branch_refinement_not_selected_count"] == 1
    assert payload["repeated_contract_reroute_count"] == 1
    assert payload["novelty_pressure_seen_count"] == 6
    assert payload["cross_branch_map_seen_count"] == 3
    assert payload["reason_code_counts"]["CROSS_BRANCH_NEAR_DUPLICATE"] == 1
    assert payload["reason_code_counts"]["repeated_contract_signature_reroute"] == 1
    assert "Sensitive proposal text" not in json.dumps(payload)
    assert "compact public result" not in json.dumps(payload)


def test_cross_branch_observability_excludes_non_counted_pre_protocol_steps() -> None:
    counted_failure = replace(
        _step("branch-counted", round_num=1, mechanism_id="alpha_probe"),
        protocol_result=None,
        decision=None,
        contract_passed=False,
        verification_passed=False,
        failure_stage="proposal",
        failure_detail="proposal_quality_blocked",
        counts_toward_max_rounds=True,
    )
    non_counted_failure = replace(
        _step("branch-non-counted", round_num=2, mechanism_id="beta_probe"),
        protocol_result=None,
        decision=None,
        contract_passed=False,
        verification_passed=False,
        failure_stage="proposal",
        failure_detail="branch_lifecycle_policy_violation",
        counts_toward_max_rounds=False,
    )

    payload = build_cross_branch_research_observability(
        steps=[counted_failure, non_counted_failure],
    )

    assert payload["observable_step_count"] == 1
    assert payload["includes_failed_pre_protocol_steps"] is True
    assert payload["includes_non_counted_steps"] is False
    assert payload["excludes_non_counted_steps"] is True
    assert payload["source_counts"]["safe_pre_protocol_failure_steps"] == 2
    assert payload["source_counts"]["counted_pre_protocol_failure_steps"] == 1
    assert payload["source_counts"]["non_counted_pre_protocol_failure_steps"] == 1


def test_cross_branch_observability_counts_material_requirements_from_records() -> None:
    payload = build_cross_branch_research_observability(
        steps=[
            _step("branch-a", round_num=1, mechanism_id="alpha_probe"),
            _step("branch-b", round_num=2, mechanism_id="alpha_variant"),
        ],
        scheduler_records=[
            {
                "cross_branch_research_audit_records": [
                    _material_difference_record("mdr:alpha"),
                    _material_difference_record("mdr:beta"),
                ]
            }
        ],
    )

    assert payload["avoid_signature_count"] == 1
    assert payload["saturated_signature_count"] == 1
    assert payload["material_difference_requirement_count"] == 2


def test_cross_branch_observability_flags_generic_near_duplicate_diagnostics() -> None:
    payload = build_cross_branch_research_observability(
        steps=[
            _step(
                "branch-seed-a",
                round_num=1,
                mechanism_id="construction_seed_selector",
            ),
            _step(
                "branch-seed-b",
                round_num=2,
                mechanism_id="regret_seed_select_variant",
            ),
        ],
    )

    assert payload["near_duplicate_count"] == 1
    assert payload["saturated_signature_count"] == 1
    near = payload["near_duplicate_diagnostics"][0]
    saturated = payload["saturated_signature_diagnostics"][0]
    assert near["advisory_only"] is True
    assert near["decision_features_excluded"] is True
    assert near["signature"]["mechanism_family"] == "construction_seed_selector"
    assert near["signature_observation_count"] == 2
    assert saturated["diagnostic_kind"] == "saturated_signature"
    assert saturated["non_positive_outcome_count"] == 2
    assert "Sensitive proposal text" not in json.dumps(payload)


def test_cross_branch_observability_counts_broad_family_saturation() -> None:
    payload = build_cross_branch_research_observability(
        steps=[
            _step(
                "branch-local-a",
                round_num=1,
                mechanism_id="local_search_alpha",
                target_file="components/a.py",
                novelty_signature={"mechanism_family": "local_search"},
            ),
            _step(
                "branch-local-b",
                round_num=2,
                mechanism_id="local_search_beta",
                target_file="components/b.py",
                novelty_signature={"mechanism_family": "local_search"},
            ),
            _step(
                "branch-local-c",
                round_num=3,
                mechanism_id="local_search_gamma",
                target_file="components/c.py",
                novelty_signature={"mechanism_family": "local_search"},
                wins=1,
                reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            ),
        ],
    )

    assert payload["near_duplicate_count"] == 0
    summary = payload["family_saturation_summary"]
    assert summary["schema_version"] == "cross_branch_family_saturation_summary.v1"
    assert summary["visibility_marker"] == (
        "advisory proposal-only excluded_from_DecisionFeatures"
    )
    assert summary["proposal_visibility_only"] is True
    assert summary["advisory_only"] is True
    assert summary["decision_input_policy"] == "excluded_from_decision_features"
    assert summary["grouping_keys"] == [
        "mechanism_family",
        "intervention_type",
        "surface",
        "outcome_tier",
    ]
    assert summary["saturated_family_count"] == 1
    item = summary["summaries"][0]
    assert item["mechanism_family"] == "local_search"
    assert item["intervention_type"] == "modify"
    assert item["surface"] == "selection_policy"
    assert item["attempt_count"] == 3
    assert item["branch_count"] == 3
    assert item["outcome_tier_counts"] == {
        "no_effect": 2,
        "weak_positive": 1,
    }
    assert item["case_level_counts"] == {
        "wins": 1,
        "losses": 0,
        "no_effect": 11,
    }
    assert item["lifecycle_counts"]["weak_positive"] == 1
    assert "consider diversifying" in item["proposal_advisory"]
    assert "must switch" not in json.dumps(summary).lower()
    assert "forbidden" not in json.dumps(summary).lower()
    assert "Sensitive proposal text" not in json.dumps(payload)


def test_cross_branch_observability_counts_direct_material_requirement_record() -> None:
    payload = build_cross_branch_research_observability(
        steps=[
            _step("branch-a", round_num=1, mechanism_id="alpha_probe"),
        ],
        branch_rows=[
            {
                "id": "branch-new",
                "material_difference_requirement": _material_difference_record(
                    "mdr:clean-fork"
                ),
            }
        ],
    )

    assert payload["material_difference_requirement_count"] == 1


def test_cross_branch_observability_counts_map_coverage_without_pressure() -> None:
    payload = build_cross_branch_research_observability(
        steps=[
            _step("branch-a", round_num=1, mechanism_id="alpha_probe"),
            _step("branch-b", round_num=2, mechanism_id="beta_probe"),
        ],
        branch_rows=[],
    )

    assert payload["observable_step_count"] == 2
    assert payload["cross_branch_map_seen_count"] == 2
    assert payload["near_duplicate_count"] == 0
    assert payload["avoid_signature_count"] == 0
    assert payload["material_difference_requirement_count"] == 0
    assert payload["novelty_pressure_seen_count"] == 0


def test_cross_branch_observability_counts_branch_lesson_usage_quality() -> None:
    borrowed = _step("branch-borrow", round_num=1, mechanism_id="alpha_probe")
    borrowed.hypothesis.branch_lesson_usage = {
        "borrowed_lessons": [
            {
                "lesson_id": "lesson:borrow",
                "lesson_type": "weak_positive",
                "source_branch_ids": ["branch-a"],
                "activation_path": "observed_activation",
                "effect_path": "weak_effect",
                "borrowed_signal": "weak_positive_signal",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "alpha_probe",
            }
        ],
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:borrow",
                "contrast_dimensions": ["target_file"],
                "new_path": "generic_path",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "alpha_probe",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["target_file"],
            "sibling_duplication_allowed": False,
        },
    }
    borrowed.scheduler_audit_metadata = {
        "branch_lesson_usage_requirement": _branch_lesson_requirement("blur:borrow")
    }
    avoided = _step("branch-avoid", round_num=2, mechanism_id="beta_probe")
    avoided.hypothesis.branch_lesson_usage = {
        "avoided_lessons": [
            {
                "lesson_id": "lesson:avoid",
                "avoid_reason": "no_effect_cluster",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "beta_probe",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["mechanism_family"],
            "sibling_duplication_allowed": False,
        },
    }
    preserved = _step("branch-preserve", round_num=3, mechanism_id="gamma_probe")
    preserved.hypothesis.branch_lesson_usage = {
        "preserved_same_branch_lesson": {
            "lesson_id": "lesson:local",
            "preserved_signal": "weak_signal",
            "risk_to_avoid": "known_gap",
            "target_file": "components/common.py",
            "action": "modify",
            "mechanism": "gamma_probe",
        }
    }
    missing = replace(
        _step("branch-missing", round_num=4, mechanism_id="delta_probe"),
        protocol_result=None,
        decision=None,
        contract_passed=True,
        verification_passed=False,
        failure_stage="proposal",
        failure_detail=(
            "agent_quality_blocked:branch_lesson_usage_required_missing: "
            "structured branch_lesson_usage is required"
        ),
        counts_toward_max_rounds=False,
        attempt_kind="proposal_block",
    )

    payload = build_cross_branch_research_observability(
        steps=[borrowed, avoided, preserved, missing],
        context_records=[
            _branch_lesson_requirement("blur:context"),
            {
                "cross_branch_research_payload": {
                    "branch_lesson_records": [
                        _branch_lesson_record("lesson:borrow"),
                        _branch_lesson_record("lesson:avoid"),
                    ]
                }
            },
        ],
    )

    assert payload["branch_lesson_record_count"] == 2
    assert payload["branch_lesson_usage_requirement_count"] == 3
    assert payload["branch_lesson_usage_present_count"] == 3
    assert payload["branch_lesson_usage_satisfied_count"] == 1
    assert payload["branch_lesson_usage_present_not_semantic_count"] == 2
    assert payload["branch_lesson_usage_missing_block_count"] == 1
    assert payload["borrowed_lesson_count"] == 1
    assert payload["avoided_lesson_count"] == 1
    assert payload["contrasted_lesson_count"] == 1
    assert payload["preserved_same_branch_lesson_count"] == 1
    assert payload["clean_fork_contrast_satisfied_count"] == 1
    assert payload["weak_positive_transfer_count"] == 1
    assert payload["weak_positive_transfer_reject_count"] == 0
    assert payload["policy"] == "proposal_observability_only"
    assert payload["decision_input_policy"] == "excluded_from_decision_features"
    assert "Sensitive proposal text" not in json.dumps(payload)


def test_branch_lesson_usage_satisfied_requires_attached_requirement() -> None:
    voluntary = _step("branch-voluntary", round_num=1, mechanism_id="alpha_probe")
    voluntary.hypothesis.branch_lesson_usage = {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:voluntary",
                "contrast_dimensions": ["target_file"],
                "new_path": "generic_path",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["target_file"],
        },
    }
    required = _step(
        "branch-required",
        round_num=2,
        mechanism_id="beta_probe",
        proposal_session_ref={
            "schema_version": "proposal-context-ref.v1",
            "branch_lesson_usage_requirement": _branch_lesson_requirement(
                "blur:required"
            ),
        },
    )
    required.hypothesis.branch_lesson_usage = {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:required",
                "contrast_dimensions": ["target_file"],
                "new_path": "generic_path",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "beta_probe",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["target_file"],
        },
    }

    voluntary_payload = build_cross_branch_research_observability(
        steps=[voluntary],
    )
    required_payload = build_cross_branch_research_observability(
        steps=[required],
    )

    assert voluntary_payload["branch_lesson_usage_present_count"] == 1
    assert voluntary_payload["branch_lesson_usage_satisfied_count"] == 0
    assert required_payload["branch_lesson_usage_present_count"] == 1
    assert required_payload["branch_lesson_usage_satisfied_count"] == 1


def test_branch_lesson_usage_observability_distinguishes_linkage_unrecognized() -> None:
    step = _step("branch-linkage", round_num=1, mechanism_id="alpha_probe")
    step.hypothesis.branch_lesson_usage = {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:linkage",
                "contrast_dimensions": ["mechanism"],
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism_story": "alpha_probe",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["mechanism"],
            "sibling_duplication_allowed": False,
        },
    }
    step.scheduler_audit_metadata = {
        "branch_lesson_usage_requirement": _branch_lesson_requirement("lesson:linkage")
    }

    blocked = replace(
        _step("branch-blocked", round_num=2, mechanism_id="alpha_probe"),
        protocol_result=None,
        decision=None,
        contract_passed=True,
        verification_passed=False,
        failure_stage="proposal",
        failure_detail=(
            "agent_quality_blocked:branch_lesson_usage_linkage_unrecognized: "
            "target/action/mechanism linkage is unrecognized"
        ),
        counts_toward_max_rounds=False,
        attempt_kind="proposal_block",
    )

    payload = build_cross_branch_research_observability(steps=[step, blocked])

    assert payload["branch_lesson_usage_present_count"] == 1
    assert payload["branch_lesson_usage_present_not_semantic_count"] == 1
    assert payload["branch_lesson_usage_missing_block_count"] == 0
    assert payload["branch_lesson_usage_linkage_unrecognized_count"] == 1
    assert payload["branch_lesson_usage_linkage_unrecognized_block_count"] == 1


def test_weak_positive_reject_satisfies_without_counting_transfer() -> None:
    rejected = _step("branch-reject", round_num=1, mechanism_id="reject_probe")
    rejected.hypothesis.branch_lesson_usage = {
        "rejected_weak_positive_lessons": [
            {
                "lesson_id": "lesson:weak-reject",
                "lesson_type": "weak_positive",
                "reject_reason_code": "target_action_mismatch",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "reject_probe",
            }
        ],
    }
    rejected.scheduler_audit_metadata = {
        "branch_lesson_usage_requirement": {
            **_branch_lesson_requirement("blur:weak-reject"),
            "requirement_source": "weak_positive_transfer",
            "candidate_lesson_ids": ["lesson:weak-reject"],
            "candidate_lesson_types": ["weak_positive"],
            "candidate_lesson_roles": ["borrow"],
        }
    }

    payload = build_cross_branch_research_observability(steps=[rejected])

    assert payload["branch_lesson_usage_present_count"] == 1
    assert payload["branch_lesson_usage_satisfied_count"] == 1
    assert payload["weak_positive_transfer_count"] == 0
    assert payload["weak_positive_transfer_reject_count"] == 1


def test_step_visibility_audit_sees_proposal_session_branch_lessons(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-visibility", campaign_dir=tmp_path)
    step = _step(
        "branch-visible",
        round_num=1,
        mechanism_id="alpha_probe",
        proposal_session_ref={
            "schema_version": "proposal-context-ref.v1",
            "branch_lesson_records": [_branch_lesson_record("lesson:visible")],
            "branch_lesson_usage_requirement": _branch_lesson_requirement(
                "blur:visible"
            ),
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    visibility = summary["steps"][0]["step_visibility_audit"][
        "cross_branch_research_visibility"
    ]
    assert visibility["status"] == "available"
    assert visibility["record_count"] > 0
    assert (
        summary["cross_branch_research_observability"]["branch_lesson_record_count"]
        == 1
    )
    assert (
        summary["cross_branch_research_observability"][
            "branch_lesson_usage_requirement_count"
        ]
        == 1
    )


def test_campaign_summary_and_status_write_observability_payload(
    tmp_path: Path,
) -> None:
    branch_rows = [
        {
            "id": "branch-a",
            "state": "explore",
            "branch_mechanism_ids": ["alpha_probe"],
            "branch_card": {
                "branch_id": "branch-a",
                "direction": "modify/selection_policy",
                "mechanism_ids": ["alpha_probe"],
                "target_files": ["components/common.py"],
                "generic_evidence_summary": {"tier": "no_effect"},
            },
            "cross_branch_research_audit_records": [
                _material_difference_record("mdr:summary-alpha"),
            ],
        },
        {
            "id": "branch-b",
            "state": "explore",
            "branch_mechanism_ids": ["alpha_variant"],
            "branch_card": {
                "branch_id": "branch-b",
                "direction": "modify/selection_policy",
                "mechanism_ids": ["alpha_variant"],
                "target_files": ["components/common.py"],
                "generic_evidence_summary": {"tier": "no_effect"},
            },
            "cross_branch_research_audit_records": [
                _material_difference_record("mdr:summary-beta"),
            ],
        },
        {
            "id": "branch-rerouted",
            "branch_lifecycle_reroute_reason": ("repeated_contract_signature_reroute"),
            "branch_card": {
                "branch_id": "branch-rerouted",
                "branch_lifecycle_reroute_reason": (
                    "repeated_contract_signature_reroute"
                ),
            },
        },
    ]
    recorder = EvidenceRecorder(
        campaign_id="camp-compact",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 2,
            "proposal_attempts": 2,
            "screened_experiments": 2,
            "branches": branch_rows,
        },
    )
    first = _step("branch-a", round_num=1, mechanism_id="alpha_probe")
    first.scheduler_audit_metadata = {
        "cross_branch_research_audit_records": [
            _cross_branch_record("cbr:summary-alpha"),
        ],
        "material_difference_requirement": _material_difference_record(
            "mdr:step-alpha"
        ),
    }
    first.proposal_session_ref = {
        "schema_version": "proposal-context-ref.v1",
        "branch_lesson_records": [_branch_lesson_record("lesson:summary")],
        "branch_lesson_usage_requirement": _branch_lesson_requirement("blur:summary"),
    }
    second = _step("branch-b", round_num=2, mechanism_id="alpha_variant")
    summary = recorder.write_campaign_summary(
        step_history=[first, second],
        round_num=2,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    payload = summary["cross_branch_research_observability"]
    assert summary["evidence_scope_reconciliation"]["step_history_scope"] == (
        "full_step_history"
    )
    assert summary["evidence_scope_reconciliation"]["branch_state_scope"] == (
        "branch_rows_snapshot"
    )
    assert (
        summary["evidence_scope_reconciliation"]["source_counts"]["step_history_total"]
        == 2
    )
    assert (
        summary["evidence_scope_reconciliation"]["source_counts"][
            "cross_branch_observable_step_count"
        ]
        == 2
    )
    assert payload["near_duplicate_count"] == 1
    assert payload["saturated_signature_count"] == 1
    assert payload["material_difference_requirement_count"] == 3
    assert payload["branch_lesson_record_count"] == 1
    assert payload["branch_lesson_usage_requirement_count"] == 1
    assert payload["repeated_contract_reroute_count"] == 1
    assert "cross_branch_research_observability" in json.loads(
        (tmp_path / "campaign_summary.json").read_text()
    )
    step_audit = summary["steps"][0]["step_visibility_audit"]
    assert step_audit["candidate_intent_visibility"]["status"] == "derived"
    assert step_audit["observability_value_visibility"]["status"] == "derived"
    assert step_audit["cross_branch_research_visibility"]["status"] == "available"
    assert step_audit["material_difference_requirement_visibility"]["status"] == (
        "available"
    )
    assert (
        step_audit["cross_branch_research_visibility"]["records"][0]["record_id"]
        == "cbr:summary-alpha"
    )
    assert (
        step_audit["material_difference_requirement_visibility"]["records"][0][
            "record_id"
        ]
        == "mdr:step-alpha"
    )

    status = recorder.write_status(
        last_result=StepResult(
            action="create_branch",
            branch_id="branch-clean",
            decision=Decision.CONTINUE_EXPLORE,
            reason="clean exploration selected",
            scheduler_audit_metadata={
                "clean_fork_selected": True,
                "same_branch_refinement_not_selected_reason": (
                    "scheduler_selected_clean_exploration_branch"
                ),
            },
            proposal_session_ref={
                "schema_version": "proposal-context-ref.v1",
                "branch_lesson_records": [_branch_lesson_record("lesson:status")],
                "branch_lesson_usage_requirement": _branch_lesson_requirement(
                    "blur:status"
                ),
            },
        )
    )

    status_payload = status["cross_branch_research_observability"]
    assert status["evidence_scope_reconciliation"]["step_history_scope"] == (
        "not_available"
    )
    assert status["evidence_scope_reconciliation"]["branch_state_scope"] == (
        "branch_rows_snapshot"
    )
    assert status["evidence_scope_reconciliation"]["last_result_scope"] == (
        "last_completed_result_only"
    )
    assert status_payload["observable_step_count"] == 2
    assert status_payload["cross_branch_map_seen_count"] == 2
    assert status_payload["status_scope"] == "loop_accounting_inferred"
    assert status_payload["near_duplicate_count"] == 1
    assert status_payload["saturated_signature_count"] == 1
    assert status_payload["material_difference_requirement_count"] == 2
    assert status_payload["branch_lesson_record_count"] == 1
    assert status_payload["branch_lesson_usage_requirement_count"] == 1
    assert status_payload["same_branch_refinement_not_selected_count"] == 1
    assert status_payload["repeated_contract_reroute_count"] == 1
    assert "cross_branch_research_observability" in json.loads(
        (tmp_path / "status.json").read_text()
    )
    assert "Sensitive proposal text" not in json.dumps(status_payload)


def test_terminal_status_uses_summary_grade_branch_lesson_usage_counters(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-terminal-branch-lessons",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 1,
            "proposal_attempts": 1,
            "screened_experiments": 1,
            "effective_rounds_completed": 1,
            "requested_rounds": 1,
            "stopped": True,
            "branches": [],
        },
    )
    proposal_session_ref = {
        "schema_version": "proposal-context-ref.v1",
        "branch_lesson_records": [_branch_lesson_record("lesson:terminal")],
        "branch_lesson_usage_requirement": _branch_lesson_requirement("blur:terminal"),
    }
    step = _step(
        "branch-terminal",
        round_num=1,
        mechanism_id="terminal_probe",
        proposal_session_ref=proposal_session_ref,
    )
    step.hypothesis.branch_lesson_usage = {
        "contrasted_lessons": [
            {
                "lesson_id": "lesson:terminal",
                "contrast_dimensions": ["target_file"],
                "new_path": "generic_path",
                "target_file": "components/common.py",
                "action": "modify",
                "mechanism": "terminal_probe",
            }
        ],
        "clean_fork_diversity_claim": {
            "changed_dimensions": ["target_file"],
        },
    }

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )
    summary_observability = summary["cross_branch_research_observability"]
    assert summary_observability["branch_lesson_usage_present_count"] == 1
    assert summary_observability["branch_lesson_usage_satisfied_count"] == 1

    status = recorder.write_status(
        last_result=StepResult(
            action="explore",
            branch_id="branch-terminal",
            decision=Decision.CONTINUE_EXPLORE,
            reason="terminal status refresh",
            protocol_stage="screening",
            formal_protocol_evaluated=True,
            screened_experiment_effective=True,
            proposal_session_ref=proposal_session_ref,
        ),
        stopped_reason="max_rounds_exhausted",
    )

    status_observability = status["cross_branch_research_observability"]
    assert status["evidence_scope_reconciliation"]["step_history_scope"] == (
        "not_available"
    )
    assert status_observability["step_history_scope"] == "none"
    assert status_observability["branch_lesson_usage_counter_scope"] == (
        "summary_step_history"
    )
    assert status_observability["branch_lesson_usage_counter_reason"] == (
        "status_step_history_not_available; copied_summary_grade_step_history_counters"
    )
    assert status_observability["branch_lesson_usage_present_count"] == 1
    assert status_observability["branch_lesson_usage_satisfied_count"] == 1
