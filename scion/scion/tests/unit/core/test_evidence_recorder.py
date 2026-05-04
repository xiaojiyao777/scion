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
    ProtocolResult,
    StepRecord,
    VerificationResult,
)


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


def test_record_step_and_summary_preserve_current_fields(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step_history: list[StepRecord] = []

    recorder.record_step(_step("/tmp/metrics-round-3.json"), step_history)
    summary = recorder.write_campaign_summary(
        step_history=step_history,
        round_num=3,
        champion=_champion(),
        budget_used=2,
        budget_total=8,
        stopped_reason="max_rounds",
        diagnostics={"note": "ok"},
    )

    assert (tmp_path / "campaign_summary.json").exists()
    from_disk = json.loads((tmp_path / "campaign_summary.json").read_text())
    assert from_disk == summary
    assert summary["campaign_id"] == "camp-1"
    assert summary["total_rounds"] == 3
    assert summary["champion_version"] == 7
    assert summary["champion_weight_revision"] == 2
    assert summary["budget_utilization"] == 0.25
    assert summary["cache_stats"]["total_tokens"] == 100
    assert summary["cache_stats"]["cache_read_tokens"] == 25

    summary_step = summary["steps"][0]
    assert summary_step["round"] == 3
    assert summary_step["branch_id"] == "branch-1"
    assert summary_step["decision"] == "queue_validate"
    assert summary_step["hypothesis"]["text"] == "Improve route insertion with regret scoring."
    assert summary_step["protocol_result"]["raw_metrics_ref"] == "/tmp/metrics-round-3.json"
    assert summary_step["protocol_result"]["reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["runtime_ratio_median"] == 1.18
    assert summary_step["protocol_result"]["runtime_delta_median_ms"] == 24.0
    assert summary_step["protocol_result"]["runtime_regression_rate"] == 0.5
    assert summary_step["protocol_result"]["runtime_pairs"] == 4


def test_protocol_progress_status_preserves_raw_metrics_ref(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {"campaign_id": "camp-1", "round": 4},
    )

    progress = recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        raw_metrics_ref="/tmp/progress-metrics.json",
        completed_cases=2,
    )

    status = json.loads((tmp_path / "status.json").read_text())
    assert progress["raw_metrics_ref"] == "/tmp/progress-metrics.json"
    assert status["current_progress"]["raw_metrics_ref"] == "/tmp/progress-metrics.json"
    assert status["current_progress"]["completed_cases"] == 2
    assert "last_progress_at" in status["current_progress"]


def test_promotion_lineage_payload_includes_decision_reason_champion_and_metrics_ref(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    runtime_check = CheckResult(
        "V9_perf_guard",
        True,
        "heavy",
        "perf ok: case=case-1 candidate=120ms champion=100ms ratio=1.20x timeout=60s",
        7,
        metadata={
            "case_id": "case-1",
            "candidate_ms": 120,
            "champion_ms": 100,
            "ratio": 1.2,
            "candidate_timeout": False,
        },
    )
    event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(
            passed=True,
            checks=(CheckResult("contract", True, "light", "ok", 1),),
        ),
        verification_result=VerificationResult(
            passed=True,
            checks=(CheckResult("syntax", True, "light", "ok", 1), runtime_check),
        ),
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result("/tmp/promotion-metrics.json"),
        decision=Decision.PROMOTE,
        champion=_champion(version=8),
        hypothesis_id="hyp-1",
        decision_reason_codes=("frozen_positive", "runtime_ok"),
    )
    decision_payload = recorder.build_decision_lineage_payload(
        branch=_branch(),
        protocol_result=_protocol_result("/tmp/promotion-metrics.json"),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=(runtime_check,)),
        canary_result=CanaryResult(passed=True),
        decision=Decision.PROMOTE,
        decision_reason_codes=("frozen_positive", "runtime_ok"),
    )

    metadata = json.loads(event["decision_features_json"])
    reason_codes = json.loads(decision_payload["reason"])

    assert event["branch_id"] == "branch-1"
    assert event["decision"] == "promote"
    assert event["raw_metrics_ref"] == "/tmp/promotion-metrics.json"
    assert metadata["current_champion_version"] == 8
    assert metadata["protocol_raw_metrics_ref"] == "/tmp/promotion-metrics.json"
    assert metadata["metrics_refs"]["protocol_raw_metrics_ref"] == "/tmp/promotion-metrics.json"
    assert metadata["decision_reason_codes"] == ["frozen_positive", "runtime_ok"]
    assert metadata["runtime_guard"]["metadata"]["ratio"] == 1.2
    assert metadata["runtime_stats"]["runtime_ratio_median"] == 1.18
    assert metadata["runtime_stats"]["runtime_pairs"] == 4
    assert metadata["verification_checks"][1]["name"] == "V9_perf_guard"
    payload_features = json.loads(decision_payload["features_json"])
    assert payload_features["runtime_guard"]["metadata"]["case_id"] == "case-1"
    assert payload_features["runtime_stats"]["runtime_regression_rate"] == 0.5
    assert reason_codes == ["frozen_positive", "runtime_ok"]


def test_future_final_evidence_refs_do_not_change_step_schema(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    before = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )
    before_step_keys = set(before["steps"][0].keys())

    recorder.attach_final_evidence_refs(
        {"frozen_quality_report": "/tmp/final-quality.json"}
    )
    after = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )

    assert set(after["steps"][0].keys()) == before_step_keys
    assert after["final_evidence_refs"] == {
        "frozen_quality_report": "/tmp/final-quality.json"
    }
