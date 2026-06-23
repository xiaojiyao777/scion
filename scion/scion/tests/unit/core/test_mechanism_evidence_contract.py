from __future__ import annotations

from types import SimpleNamespace

from scion.core.branch_hygiene import branch_has_actionable_diagnostic
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary,
)
from scion.core.mechanism_evidence_contract import (
    mechanism_evidence_contract_for_protocol,
)
from scion.core.models import (
    Branch,
    BranchState,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
)
from scion.core.scheduler import Scheduler, branch_scheduling_status
from scion.core.scheduling.status import INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON
from scion.runtime.telemetry_guard.summary_signals import (
    EVALUATED_NO_EFFECT,
    NOT_EVALUATED_OR_TRIGGERED,
)


def test_missing_declared_mechanism_contract_requires_followup() -> None:
    protocol = _protocol_with_guard(
        {
            "declared_mechanisms": ["mechanism_alpha"],
            "mechanism_diagnostics": [
                {
                    "mechanism": "mechanism_alpha",
                    "activation_status": "missing",
                    "runtime_status": "missing",
                    "effect_status": "missing",
                    "diagnostic_kind": NOT_EVALUATED_OR_TRIGGERED,
                }
            ],
        }
    )

    contract = mechanism_evidence_contract_for_protocol(protocol)

    assert contract["schema_version"] == "scion.mechanism_evidence_contract.v1"
    assert contract["declared_mechanism_ids"] == ["mechanism_alpha"]
    assert contract["primary_mechanism_id"] == "mechanism_alpha"
    assert contract["primary_status"] == "declared_not_triggered"
    assert contract["followup_required"] is True
    assert contract["repairable"] is True
    assert contract["repair_mechanism_ids"] == ["mechanism_alpha"]
    assert contract["decision_features_excluded"] is True
    assert contract["proposal_visibility_only"] is True
    assert "MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REQUIRED" in (
        contract["reason_codes"]
    )


def test_evaluated_no_effect_contract_is_not_repair_followup() -> None:
    protocol = _protocol_with_guard(
        {
            "declared_mechanisms": ["mechanism_beta"],
            "mechanism_diagnostics": [
                {
                    "mechanism": "mechanism_beta",
                    "activation_status": "observed",
                    "runtime_status": "observed",
                    "effect_status": "zero",
                    "diagnostic_kind": EVALUATED_NO_EFFECT,
                }
            ],
        }
    )

    contract = mechanism_evidence_contract_for_protocol(protocol)

    assert contract["primary_status"] == "observed_no_effect"
    assert contract["followup_required"] is False
    assert contract["repairable"] is False
    assert contract["repair_mechanism_ids"] == []
    assert contract["reason_codes"] == [
        "MECHANISM_CONTRACT_EVALUATED_NO_EFFECT",
        "MECHANISM_CONTRACT_NO_REPAIR_FOLLOWUP",
    ]


def test_inactive_branch_with_mechanism_contract_followup_is_schedulable() -> None:
    branch = Branch(
        branch_id="inactive-mechanism-followup",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="clean",
        last_screening_feedback_tier="inactive",
    )
    protocol = _protocol_with_guard(
        {
            "declared_mechanisms": ["mechanism_gamma"],
            "mechanism_diagnostics": [
                {
                    "mechanism": "mechanism_gamma",
                    "activation_status": "missing",
                    "runtime_status": "missing",
                    "effect_status": "missing",
                    "diagnostic_kind": NOT_EVALUATED_OR_TRIGGERED,
                }
            ],
        }
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=_screening_feedback("inactive"),
    )

    status = branch_scheduling_status(branch)
    action = Scheduler(max_active_branches=1).select_next([branch])
    summary = branch.branch_evidence_summary

    assert summary["mechanism_evidence_contract"]["followup_required"] is True
    assert summary["mechanism_evidence_contract"]["repair_mechanism_ids"] == [
        "mechanism_gamma"
    ]
    assert summary["phase_activation_summary"]["mechanism_contract_status"] == (
        "declared_not_triggered"
    )
    assert summary["phase_activation_summary"]["mechanism_followup_required"] is True
    assert branch_has_actionable_diagnostic(branch) is True
    assert status.lane == "diagnostic_followup"
    assert status.release_reason == ""
    assert status.consumes_active_slot is True
    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"


def test_inactive_branch_without_contract_followup_releases_slot() -> None:
    branch = Branch(
        branch_id="inactive-no-followup",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="clean",
        last_screening_feedback_tier="inactive",
        branch_evidence_summary={
            "stage": "screening",
            "tier": "inactive",
            "mechanism_evidence_contract": {
                "schema_version": "scion.mechanism_evidence_contract.v1",
                "primary_status": "observed_no_effect",
                "followup_required": False,
                "decision_features_excluded": True,
            },
        },
    )

    status = branch_scheduling_status(branch)
    action = Scheduler(max_active_branches=1).select_next([branch])

    assert branch_has_actionable_diagnostic(branch) is False
    assert status.lane == "not_schedulable"
    assert status.release_reason == INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON
    assert status.consumes_active_slot is False
    assert action.action == "create_new"
    assert action.reason == "new_exploration_slot_available"


def _protocol_with_guard(guard: dict) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=1,
            wins=0,
            losses=0,
            ties=1,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="continue",
        reason_codes=(),
        exposed_summary="screening dummy mechanism evidence",
        raw_metrics_ref="/tmp/metrics.json",
        candidate_surface_runtime_summary={"telemetry_guard": guard},
    )


def _screening_feedback(tier: str) -> SimpleNamespace:
    return SimpleNamespace(
        tier=tier,
        pair_wins=0,
        pair_losses=0,
        pair_ties=1,
        activation_status="missing",
        effect_status="missing",
        opportunity_status="unknown",
    )
