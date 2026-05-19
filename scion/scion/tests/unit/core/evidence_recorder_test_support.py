from __future__ import annotations

import json
from pathlib import Path

from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    CheckResult,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    OperatorConfig,
    PatchProposal,
    PairwiseCaseFeedback,
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
        cache_stats={"total": 100, "cache_read": 25, "cache_create": 75},
        hypothesis_id="hyp-1",
        decision_reason_codes=("screening_positive",),
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
        solver_config_hash="solver-hash",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="code-hash",
        weight_revision=2,
    )


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=6,
        base_champion_hash="base-hash",
        current_code_hash="candidate-hash",
        retry_count=1,
        failure_codes=["prior_timeout"],
        weight_revision=2,
    )


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
