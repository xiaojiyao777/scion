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


def test_record_step_and_summary_preserve_current_fields(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_active_branches": 0,
            "branches": [],
        },
    )
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
    assert summary["n_active_branches"] == 0
    assert summary["budget_utilization"] == 0.25
    assert summary["cache_stats"]["total_tokens"] == 100
    assert summary["cache_stats"]["cache_read_tokens"] == 25

    summary_step = summary["steps"][0]
    assert summary_step["round"] == 3
    assert summary_step["branch_id"] == "branch-1"
    assert summary_step["decision"] == "queue_validate"
    assert summary_step["hypothesis"]["text"] == "Improve route insertion with regret scoring."
    assert not summary_step["protocol_result"]["raw_metrics_ref"].startswith("/")
    assert "metrics-round-3.json" in summary_step["protocol_result"]["raw_metrics_ref"]
    assert summary_step["protocol_result"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert summary_step["protocol_result"]["raw_metrics_internal_only"] is True
    assert summary_step["protocol_result"]["win_rate_scope"] == "case_level_gate"
    assert summary_step["protocol_result"]["screening_case_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_gate_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_win_rate_scope"] == (
        "case_level_gate"
    )
    assert summary_step["protocol_result"]["reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["protocol_reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["decision_reason_codes"] == [
        "screening_positive",
    ]
    assert summary_step["protocol_result"]["effective_reason_codes"] == [
        "screening_positive",
    ]
    assert summary_step["protocol_result"]["effective_reason_source"] == (
        "decision_engine"
    )
    assert summary_step["protocol_result"]["runtime_ratio_median"] == 1.18
    assert summary_step["protocol_result"]["runtime_delta_median_ms"] == 24.0
    assert summary_step["protocol_result"]["runtime_regression_rate"] == 0.5
    assert summary_step["protocol_result"]["runtime_pairs"] == 4


def test_campaign_summary_exposes_runtime_veto_decision_reason_codes(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/runtime-timeout.json",
    )
    step.decision = Decision.ABANDON
    step.decision_reason_codes = ("CANDIDATE_RUNTIME_FAILURE",)

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["protocol_reason_codes"] == ["SCREENING_FAIL_WIN_RATE"]
    assert protocol["decision_reason_codes"] == ["CANDIDATE_RUNTIME_FAILURE"]
    assert protocol["effective_reason_codes"] == ["CANDIDATE_RUNTIME_FAILURE"]
    assert protocol["effective_reason_source"] == "decision_engine"


def test_campaign_summary_distinguishes_pair_and_case_screening_rates(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    pair_results = (
        ["win"] * 2
        + ["tie"] * 12
        + ["loss"] * 2
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=-0.01,
            ci_high=0.01,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="case-level gate failed",
        raw_metrics_ref="/tmp/r2-like-screening.json",
        pair_feedback=tuple(
            PairwiseCaseFeedback(
                case_id=f"case-{idx // 4}",
                seed=idx,
                comparison=result,
                delta=1.0 if result == "win" else -1.0 if result == "loss" else 0.0,
            )
            for idx, result in enumerate(pair_results)
        ),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["screening_win_rate"] == 0.0
    assert protocol["screening_win_rate_scope"] == "case_level_gate"
    assert protocol["screening_case_win_rate"] == 0.0
    assert protocol["screening_gate_win_rate"] == 0.0
    assert protocol["screening_pair_wins"] == 2
    assert protocol["screening_pair_losses"] == 2
    assert protocol["screening_pair_ties"] == 12
    assert protocol["screening_pair_total"] == 16
    assert protocol["screening_pair_win_rate"] == 0.125


def test_campaign_summary_exposes_bounded_runtime_failure_summary(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/private-runtime.json",
        candidate_runtime_failure_categories={
            "operator_error": 2,
            "invalid_output": 1,
        },
        candidate_first_runtime_failure={
            "category": "operator_error",
            "code": "operator_errors",
            "surface": "local_search",
            "component": "operator",
            "detail_summary": "solver runtime reported operator_errors=2",
        },
        candidate_operator_attempts=8,
        candidate_operator_accepted=0,
        candidate_operator_errors=2,
        candidate_operator_invalid_outputs=1,
        candidate_policy_errors=3,
        candidate_construction_errors=4,
        candidate_portfolio_errors=5,
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["candidate_runtime_failure_categories"] == {
        "operator_error": 2,
        "invalid_output": 1,
    }
    assert protocol["candidate_first_runtime_failure"]["category"] == "operator_error"
    assert protocol["candidate_operator_attempts"] == 8
    assert protocol["candidate_operator_accepted"] == 0
    assert protocol["candidate_operator_errors"] == 2
    assert protocol["candidate_operator_invalid_outputs"] == 1
    assert protocol["candidate_policy_errors"] == 3
    assert protocol["candidate_construction_errors"] == 4
    assert protocol["candidate_portfolio_errors"] == 5


def test_campaign_summary_exposes_selected_surface_runtime_summary(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/algorithm-blueprint-runtime.json",
        selected_surface="algorithm_blueprint",
        candidate_surface_runtime_summary={
            "selected_surface": "algorithm_blueprint",
            "required_runtime_fields": [
                "algorithm_blueprint_loaded",
                "algorithm_plan",
            ],
            "candidate_pairs": 4,
            "runtime_observed_pairs": 4,
            "runtime_missing_pairs": 0,
            "fields": {
                "algorithm_blueprint_loaded": {
                    "present": 4,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                    "values": [{"value": "true", "count": 4}],
                },
                "algorithm_plan": {
                    "present": 4,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                    "values": [
                        {
                            "value": "{\"baseline_time_fraction\":0.75,\"enabled\":true}",
                            "count": 4,
                        }
                    ],
                },
            },
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["selected_surface"] == "algorithm_blueprint"
    surface_summary = protocol["candidate_surface_runtime_summary"]
    assert surface_summary["candidate_pairs"] == 4
    assert "algorithm_plan" in surface_summary["required_runtime_fields"]
    assert surface_summary["fields"]["algorithm_plan"]["present"] == 4


def test_campaign_summary_family_coverage_uses_step_locus_for_ambiguous_text(
    tmp_path: Path,
) -> None:
    taxonomy = FamilyTaxonomySpec(
        families=["alpha", "beta"],
        aliases={
            "alpha": ["alpha move", "previous alpha"],
            "beta": ["beta move", "cross move"],
        },
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        family_taxonomy=taxonomy,
    )
    alpha = _step()
    alpha.hypothesis.hypothesis_text = "Implement alpha move."
    alpha.hypothesis.change_locus = "alpha"
    beta = _step()
    beta.hypothesis.hypothesis_text = (
        "Implement cross move. Unlike the previous alpha move, this changes "
        "the active mechanism."
    )
    beta.hypothesis.change_locus = "beta"

    summary = recorder.write_campaign_summary(
        step_history=[alpha, beta],
        round_num=2,
        champion=_champion(),
    )

    assert summary["family_coverage"] == {"alpha": 1, "beta": 1}


def test_protocol_progress_status_uses_public_raw_metrics_ref(tmp_path: Path) -> None:
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
    assert progress["raw_metrics_ref"] != "/tmp/progress-metrics.json"
    assert not progress["raw_metrics_ref"].startswith("/")
    assert "progress-metrics.json" in progress["raw_metrics_ref"]
    assert progress["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert progress["raw_metrics_internal_only"] is True
    assert status["current_progress"]["raw_metrics_ref"] == progress["raw_metrics_ref"]
    assert not status["current_progress"]["raw_metrics_ref"].startswith("/")
    assert status["current_progress"]["completed_cases"] == 2
    assert "last_progress_at" in status["current_progress"]


def test_public_summary_and_status_redact_nested_diagnostics_and_branches(
    tmp_path: Path,
) -> None:
    branch_workspace = tmp_path / "workspaces" / "branch-1"
    branch_trace = tmp_path / "traces" / "branch-1.json"
    diagnostic_log = tmp_path / "diagnostics" / "branch-1.log"
    branch_summary = f"retry workspace {branch_workspace} before promotion"
    trace_note = f"trace captured at {branch_trace}, retryable"
    diagnostic_message = (
        f"runtime log stored at {diagnostic_log}; workspace={branch_workspace}"
    )
    colon_note = f"log:{diagnostic_log}; workspace:{branch_workspace}"
    local_uri_note = (
        f"log uri file://{diagnostic_log.as_posix()}, "
        f"workspace file://localhost{branch_workspace.as_posix()}"
    )
    trace_uri_note = f"trace uri file://{branch_trace.as_posix()}"
    branch_colon_summary = f"retry workspace:{branch_workspace} before promotion"
    external_note = "external diagnostic copied from /var/tmp/scion-internal.log"
    assert contains_absolute_path(trace_note)
    assert contains_absolute_path(diagnostic_message)
    assert contains_absolute_path(colon_note)
    assert contains_absolute_path(local_uri_note)
    assert contains_absolute_path(trace_uri_note)
    assert contains_absolute_path(branch_colon_summary)
    assert contains_absolute_path(external_note)
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_active_branches": 1,
            "branches": [
                {
                    "branch_id": "branch-1",
                    "workspace_path": str(branch_workspace),
                    "branch_summary": branch_summary,
                    "branch_colon_summary": branch_colon_summary,
                    "diagnostics": {
                        "trace_path": str(branch_trace),
                        "trace_note": trace_note,
                        "trace_uri_note": trace_uri_note,
                    },
                }
            ],
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
        diagnostics=[
            {
                "kind": "runtime",
                "payload": {
                    "log_path": str(diagnostic_log),
                    "message": diagnostic_message,
                    "colon_note": colon_note,
                    "local_uri_note": local_uri_note,
                    "external_note": external_note,
                    "raw_metrics_ref": f"metrics captured in {diagnostic_log}",
                    "branches": [
                        {
                            "workspace": str(branch_workspace),
                            "note": f"branch workspace:{branch_workspace}",
                        }
                    ],
                },
            }
        ],
    )
    status = recorder.write_status()

    assert not contains_absolute_path(summary)
    assert not contains_absolute_path(status)
    assert not contains_absolute_path(
        json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    )
    assert summary["diagnostics"][0]["payload"]["log_path"] == (
        "diagnostics/branch-1.log"
    )
    assert summary["diagnostics"][0]["payload"]["message"] == (
        "runtime log stored at diagnostics/branch-1.log; "
        "workspace=workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["colon_note"] == (
        "log:diagnostics/branch-1.log; workspace:workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["local_uri_note"] == (
        "log uri diagnostics/branch-1.log, workspace workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["external_note"].startswith(
        "external diagnostic copied from artifact:scion-internal.log#"
    )
    assert summary["diagnostics"][0]["payload"]["raw_metrics_ref"] == (
        "metrics captured in diagnostics/branch-1.log"
    )
    assert summary["diagnostics"][0]["payload"]["branches"][0]["note"] == (
        "branch workspace:workspaces/branch-1"
    )
    assert summary["branches"][0]["workspace_path"] == "workspaces/branch-1"
    assert summary["branches"][0]["branch_summary"] == (
        "retry workspace workspaces/branch-1 before promotion"
    )
    assert summary["branches"][0]["branch_colon_summary"] == (
        "retry workspace:workspaces/branch-1 before promotion"
    )
    assert status["branches"][0]["diagnostics"]["trace_path"] == "traces/branch-1.json"
    assert status["branches"][0]["diagnostics"]["trace_note"] == (
        "trace captured at traces/branch-1.json, retryable"
    )
    assert status["branches"][0]["diagnostics"]["trace_uri_note"] == (
        "trace uri traces/branch-1.json"
    )


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
    v8_check = CheckResult(
        "V8_nondeterminism",
        True,
        "heavy",
        "adapter_canonical_signature identical across two runs",
        5,
        metadata={
            "comparison_mode": "adapter_canonical_signature",
            "selected_surface": "search_policy",
            "adapter_backed": True,
            "comparison_equal": True,
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
            checks=(
                CheckResult("syntax", True, "light", "ok", 1),
                v8_check,
                runtime_check,
            ),
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
    assert not event["raw_metrics_ref"].startswith("/")
    assert "promotion-metrics.json" in event["raw_metrics_ref"]
    assert metadata["current_champion_version"] == 8
    assert metadata["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["raw_metrics_internal_only"] is True
    assert metadata["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["metrics_refs"]["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["metrics_refs"]["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert metadata["metrics_refs"]["raw_metrics_internal_only"] is True
    assert metadata["metrics_refs"]["audit_payload_stored_in"] == (
        "experiment_events.audit_payload_json"
    )
    audit_payload = json.loads(event["audit_payload_json"])
    assert audit_payload["internal_only"] is True
    assert audit_payload["raw_metrics_internal_only"] is True
    assert audit_payload["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["metrics_refs"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref"] == (
        event["raw_metrics_ref"]
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert not contains_absolute_path(audit_payload)
    assert metadata["decision_reason_codes"] == ["frozen_positive", "runtime_ok"]
    assert metadata["runtime_guard"]["metadata"]["ratio"] == 1.2
    assert metadata["runtime_stats"]["runtime_ratio_median"] == 1.18
    assert metadata["runtime_stats"]["runtime_pairs"] == 4
    assert metadata["verification_checks"][1]["name"] == "V8_nondeterminism"
    assert metadata["verification_checks"][1]["metadata"]["comparison_mode"] == (
        "adapter_canonical_signature"
    )
    assert metadata["verification_checks"][1]["metadata"]["adapter_backed"] is True
    assert metadata["verification_checks"][2]["name"] == "V9_perf_guard"
    payload_features = json.loads(decision_payload["features_json"])
    assert payload_features["runtime_guard"]["metadata"]["case_id"] == "case-1"
    assert payload_features["runtime_stats"]["runtime_regression_rate"] == 0.5
    assert reason_codes == ["frozen_positive", "runtime_ok"]


def test_db_audit_payload_uses_public_raw_metrics_refs(tmp_path: Path) -> None:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=registry,
    )
    metrics_path = tmp_path / "metrics" / "screening-metrics.json"

    recorder.record_step_lineage(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(
            passed=True,
            checks=(CheckResult("contract", True, "light", "ok", 1),),
        ),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result(str(metrics_path)),
        decision=Decision.ABANDON,
        champion=_champion(),
        hypothesis_id="hyp-1",
    )

    rows = registry.query_by_branch("branch-1")
    event = next(row for row in rows if row["event_kind"] == "experiment")
    audit_payload = json.loads(event["audit_payload_json"])

    assert event["raw_metrics_ref"] == "metrics/screening-metrics.json"
    assert not contains_absolute_path(event["raw_metrics_ref"])
    assert not contains_absolute_path(audit_payload)
    assert audit_payload["internal_only"] is True
    assert audit_payload["raw_metrics_internal_only"] is True
    assert audit_payload["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["metrics_refs"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref"] == (
        event["raw_metrics_ref"]
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )


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
    assert not contains_absolute_path(after["final_evidence_refs"])
    assert "final-quality.json" in after["final_evidence_refs"]["frozen_quality_report"]
