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
    wins: int = 0,
    losses: int = 0,
    reason_codes: tuple[str, ...] = (),
    scheduler_audit_metadata: dict | None = None,
) -> StepRecord:
    ties = max(0, 4 - wins - losses)
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="Sensitive proposal text must not appear here.",
            change_locus="selection_policy",
            action="modify",
            target_file="components/common.py",
            mechanism_changes=(
                MechanismChange(id=mechanism_id, change_type="modify"),
            ),
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
            "branch_lifecycle_reroute_reason": (
                "repeated_contract_signature_reroute"
            ),
        }
    ]

    payload = build_cross_branch_research_observability(
        steps=steps,
        branch_rows=branch_rows,
    )

    assert payload["schema_version"] == "cross_branch_research_observability.v1"
    assert payload["policy"] == "proposal_observability_only"
    assert payload["decision_input_policy"] == "excluded_from_decision_features"
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
    assert (
        payload["reason_code_counts"]["repeated_contract_signature_reroute"] == 1
    )
    assert "Sensitive proposal text" not in json.dumps(payload)
    assert "compact public result" not in json.dumps(payload)


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
            "branch_lifecycle_reroute_reason": (
                "repeated_contract_signature_reroute"
            ),
            "branch_card": {
                "branch_id": "branch-rerouted",
                "branch_lifecycle_reroute_reason": (
                    "repeated_contract_signature_reroute"
                ),
            },
        }
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
    second = _step("branch-b", round_num=2, mechanism_id="alpha_variant")
    summary = recorder.write_campaign_summary(
        step_history=[first, second],
        round_num=2,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    payload = summary["cross_branch_research_observability"]
    assert payload["near_duplicate_count"] == 1
    assert payload["saturated_signature_count"] == 1
    assert payload["material_difference_requirement_count"] == 2
    assert payload["repeated_contract_reroute_count"] == 1
    assert "cross_branch_research_observability" in json.loads(
        (tmp_path / "campaign_summary.json").read_text()
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
        )
    )

    status_payload = status["cross_branch_research_observability"]
    assert status_payload["observable_step_count"] == 2
    assert status_payload["cross_branch_map_seen_count"] == 2
    assert status_payload["status_scope"] == "loop_accounting_inferred"
    assert status_payload["near_duplicate_count"] == 1
    assert status_payload["saturated_signature_count"] == 1
    assert status_payload["material_difference_requirement_count"] == 2
    assert status_payload["same_branch_refinement_not_selected_count"] == 1
    assert status_payload["repeated_contract_reroute_count"] == 1
    assert "cross_branch_research_observability" in json.loads(
        (tmp_path / "status.json").read_text()
    )
    assert "Sensitive proposal text" not in json.dumps(status_payload)
