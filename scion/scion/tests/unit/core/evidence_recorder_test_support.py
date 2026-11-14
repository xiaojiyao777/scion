from __future__ import annotations

import json
from pathlib import Path

from scion.core.campaign_loop import CampaignRunResult
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    CaseAggregateFeedback,
    ChampionState,
    CheckResult,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    OperatorConfig,
    PairwiseCaseFeedback,
    PatchProposal,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)
from scion.core.public_refs import contains_absolute_path
from scion.lineage.registry import LineageRegistry
from scion.problem.spec import FamilyTaxonomySpec


def _hypothesis(text: str = "Improve route insertion.") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="class LocalSearch:\n    pass\n",
    )


def _protocol_result(raw_metrics_ref: str = "/tmp/raw_metrics.json") -> ProtocolResult:
    stats = EvalStats(
        n_cases=6,
        wins=4,
        losses=1,
        ties=1,
        win_rate=0.67,
        median_delta=0.12,
        ci_low=0.03,
        ci_high=0.21,
        runtime_ratio_median=1.18,
        runtime_delta_median_ms=24.0,
        runtime_regression_rate=0.5,
        runtime_pairs=4,
    )
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome="pass",
        reason_codes=("screening_positive", "runtime_ok"),
        exposed_summary="candidate wins",
        raw_metrics_ref=raw_metrics_ref,
        case_ids=("case-1", "case-2"),
        seed_set=(11, 13),
        case_feedback=(
            CaseAggregateFeedback(
                case_id="case-1",
                n_pairs=2,
                wins=2,
                losses=0,
                ties=0,
                win_rate=1.0,
                dominant_result="win",
                decisive_metric="total_distance",
                median_deltas={"total_distance": 0.12},
            ),
        ),
    )


def _step(raw_metrics_ref: str = "/tmp/raw_metrics.json") -> StepRecord:
    return StepRecord(
        round_num=3,
        branch_id="branch-1",
        hypothesis=_hypothesis("Improve route insertion with regret scoring."),
        patch=_patch(),
        contract_passed=True,
        verification_passed=True,
        protocol_result=_protocol_result(raw_metrics_ref),
        decision=Decision.QUEUE_VALIDATE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("screening_positive",),
        base_champion_version=6,
        base_source_ref="branch:branch-1:accepted-head:1",
        changed_files=("operators/local_search.py",),
        execution_outcome=ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.EVALUATED,
            reason_code="PROTOCOL_EVALUATED",
            provenance={
                "owner": "fixture_evaluation",
                "stage": "screening",
            },
        ),
    )


def _champion(version: int = 7) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={
            "local_search": OperatorConfig(
                name="local_search",
                file_path="operators/local_search.py",
                category="local_search",
                weight=1.0,
                class_name="LocalSearch",
            )
        },
        code_snapshot_path="/tmp/champion",
        weight_revision=2,
    )


def _operator_state(*, n_steps: int = 0) -> dict[str, object]:
    return {
        "campaign_id": "camp-1",
        "proposal_runtime_mode": "direct_v3",
        "n_experiments": 0,
        "screened_experiments": 0,
        "n_steps": n_steps,
        "champion_version": 7,
        "branches": [],
    }


def _run_projection(requested_rounds: int = 1) -> dict[str, object]:
    return CampaignRunResult.empty(requested_rounds).to_projection()


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=6,
        current_code_hash="candidate-hash",
        failure_codes=["prior_timeout"],
        weight_revision=2,
    )


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
