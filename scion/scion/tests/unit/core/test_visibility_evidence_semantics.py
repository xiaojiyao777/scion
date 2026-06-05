from __future__ import annotations

import json
from pathlib import Path

from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.models import (
    ChampionState,
    Decision,
    DecisionFeatures,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    OperatorConfig,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)


def test_observability_no_effect_is_reported_as_diagnostic_not_quality_failure(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-generic", campaign_dir=tmp_path)
    step = _generic_step(
        protocol=_generic_protocol(
            stats=EvalStats(
                n_cases=2,
                wins=0,
                losses=0,
                ties=2,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=-0.01,
                ci_high=0.01,
            ),
            gate_outcome="fail",
            reason_codes=(
                "TELEMETRY_OBSERVABILITY_BRIDGE",
                "SCREENING_NO_EFFECT",
            ),
            mechanism_evidence={
                "primary_mechanism": "telemetry_bridge",
                "primary_activation_status": "observed",
                "primary_effect_status": "zero",
                "primary_diagnostic_kind": "observability_bridge",
                "telemetry_outcome": "observed",
            },
        ),
        expected_telemetry={"intent": "observability_bridge"},
        mechanism_changes=(
            MechanismChange(id="telemetry_bridge", change_type="add"),
        ),
        decision=Decision.ABANDON,
        decision_reason_codes=("SCREENING_NO_EFFECT",),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_generic_champion(),
        stopped_reason="max_rounds",
    )

    assert summary["candidate_intent_counts"] == {
        "quality_candidate": 0,
        "observability_candidate": 1,
        "diagnostic_candidate": 0,
        "unknown": 0,
    }
    summary_step = summary["steps"][0]
    protocol = summary_step["protocol_result"]
    assert summary_step["decision"] == "abandon"
    assert protocol["decision_reason_codes"] == ["SCREENING_NO_EFFECT"]
    assert protocol["candidate_intent"] == "observability_candidate"
    assert protocol["quality_search_interpretation"] == (
        "diagnostic_not_quality_failure"
    )
    assert protocol["candidate_intent_visibility"]["formal_decision_unchanged"] is True
    assert (
        protocol["candidate_intent_visibility"]["decision_features_excluded"] is True
    )
    assert "candidate_intent" not in DecisionFeatures.__dataclass_fields__
    assert "quality_search_interpretation" not in DecisionFeatures.__dataclass_fields__


def test_cached_runtime_policy_counts_and_status_payload_are_audit_only(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-generic", campaign_dir=tmp_path)
    step = _generic_step(
        protocol=_generic_protocol(
            stats=EvalStats(
                n_cases=3,
                wins=0,
                losses=0,
                ties=3,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=-0.02,
                ci_high=0.02,
                runtime_pairs=0,
            ),
            gate_outcome="fail",
            reason_codes=("RUNTIME_EVIDENCE_REQUIRES_FRESH_BASELINE",),
            champion_cached_runtime_pairs=5,
            runtime_confidence="low_cached_champion",
            runtime_evidence_status="fresh_champion_required",
            candidate_surface_runtime_summary={
                "fields": {
                    "candidate_elapsed_ms": {
                        "present": 3,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                    }
                }
            },
        )
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_generic_champion(),
        stopped_reason="max_rounds",
    )

    assert summary["candidate_intent_counts"]["diagnostic_candidate"] == 1
    counts = summary["runtime_evidence_policy_counts"]
    assert summary["fresh_champion_required_count"] == 1
    assert summary["runtime_aggregate_excluded_count"] == 1
    assert counts["fresh_champion_required_count"] == 1
    assert counts["runtime_aggregate_excluded_count"] == 1
    assert counts["low_cached_champion_count"] == 1
    assert counts["standalone_optimization_signal_false_count"] == 1
    assert counts["decision_features_excluded_count"] == 1
    assert counts["runtime_signal_role_counts"] == {
        "audit_or_proposal_guidance_only": 1
    }
    protocol_policy = summary["steps"][0]["protocol_result"][
        "runtime_evidence_policy"
    ]
    assert summary["steps"][0]["protocol_result"]["candidate_intent"] == (
        "diagnostic_candidate"
    )
    assert protocol_policy["standalone_optimization_signal"] is False
    assert protocol_policy["runtime_signal_role"] == (
        "audit_or_proposal_guidance_only"
    )
    assert protocol_policy["decision_features_excluded"] is True
    assert "runtime_evidence_policy" not in DecisionFeatures.__dataclass_fields__
    assert "runtime_signal_role" not in DecisionFeatures.__dataclass_fields__
    assert "standalone_optimization_signal" not in DecisionFeatures.__dataclass_fields__
    assert "decision_features_excluded" not in DecisionFeatures.__dataclass_fields__

    progress = recorder.record_protocol_progress(
        branch_id="branch-beta",
        stage="screening",
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="fresh_champion_required",
        runtime_pairs=0,
        champion_cached_runtime_pairs=5,
        runtime_aggregate_excluded=True,
    )
    status = json.loads((tmp_path / "status.json").read_text())
    assert progress["runtime_evidence_policy"]["standalone_optimization_signal"] is (
        False
    )
    assert progress["runtime_evidence_policy"]["runtime_signal_role"] == (
        "audit_or_proposal_guidance_only"
    )
    assert progress["runtime_evidence_policy"]["decision_features_excluded"] is True
    assert status["current_progress"]["runtime_evidence_policy"] == (
        progress["runtime_evidence_policy"]
    )


def _generic_step(
    *,
    protocol: ProtocolResult,
    decision: Decision = Decision.CONTINUE_EXPLORE,
    decision_reason_codes: tuple[str, ...] = (),
    expected_telemetry: dict | None = None,
    mechanism_changes: tuple[MechanismChange, ...] = (),
) -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id="branch-alpha",
        hypothesis=HypothesisProposal(
            hypothesis_text="Structured candidate for generic evidence visibility.",
            change_locus="component_alpha",
            action="modify",
            target_file="components/component_alpha.py",
            predicted_direction="exploratory",
            expected_telemetry=expected_telemetry or {},
            mechanism_changes=mechanism_changes,
        ),
        patch=PatchProposal(
            file_path="components/component_alpha.py",
            action="modify",
            code_content="class ComponentAlpha:\n    pass\n",
        ),
        contract_passed=True,
        verification_passed=True,
        protocol_result=protocol,
        decision=decision,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=decision_reason_codes,
    )


def _generic_protocol(
    *,
    stats: EvalStats,
    gate_outcome: str,
    reason_codes: tuple[str, ...],
    mechanism_evidence: dict | None = None,
    champion_cached_runtime_pairs: int = 0,
    runtime_confidence: str = "high",
    runtime_evidence_status: str = "sufficient",
    candidate_surface_runtime_summary: dict | None = None,
) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome=gate_outcome,  # type: ignore[arg-type]
        reason_codes=reason_codes,
        exposed_summary="generic evidence summary",
        raw_metrics_ref="/tmp/generic-metrics.json",
        case_ids=("case-alpha", "case-beta"),
        seed_set=(1, 2),
        mechanism_evidence=mechanism_evidence or {},
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
        candidate_surface_runtime_summary=candidate_surface_runtime_summary or {},
    )


def _generic_champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={
            "component_alpha": OperatorConfig(
                name="component_alpha",
                file_path="components/component_alpha.py",
                category="component",
                weight=1.0,
                class_name="ComponentAlpha",
            )
        },
        solver_config_hash="config-hash",
        code_snapshot_path="/tmp/generic-champion",
        code_snapshot_hash="code-hash",
    )
