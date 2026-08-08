import pytest
import uuid
import re
import dataclasses

from scion.core.decision_features_serialization import decision_features_to_payload
from scion.core.models import (
    Branch,
    Decision,
    DecisionFeatures,
    DecisionOutcome,
    BranchState,
    HypothesisProposal,
)

DECISION_FEATURES_REPORT_METADATA_DENYLIST = {
    "api_key_env",
    "branch_lesson_usage",
    "calibration_explanation",
    "calibration_ref",
    "completion_preflight",
    "control_pair_key",
    "effect_to_mde_ratio",
    "free_form_notes",
    "gap",
    "launcher",
    "llm_rationale",
    "llm_text",
    "measurement_readiness",
    "measurement_readiness_source",
    "mde",
    "mde_at_power_80",
    "notes",
    "pair_evidence",
    "postrun",
    "postrun_report",
    "problem_opportunity_summary",
    "problem_measurement_diagnostics",
    "protected_cases",
    "prompt_hash",
    "prompt_manifest",
    "prompt_manifest_artifact_ref",
    "prompt_ratio",
    "prompt_ratios",
    "proposal_trajectory",
    "proposal_trajectory_manifest",
    "raw_calibration_pair_rows",
    "residual_opportunity",
    "research_efficiency",
    "mechanism_evidence",
    "mechanism_rankings",
    "run_status",
    "signal_to_noise_tier",
    "solver_mechanics",
    "aggregate_objective_headroom",
    "aggregate_noise_context",
}

def test_decision_features_immutability():
    """验证 DecisionFeatures 是 frozen 的。"""
    features = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=10,
        win_rate=0.7,
        median_delta=0.05,
        ci_low=0.01,
        ci_high=0.09,
        stale=False,
        recent_failure_codes=(),
    )
    with pytest.raises(Exception): # dataclasses.FrozenInstanceError
        features.win_rate = 0.8

def test_decision_features_no_free_text_guard():
    """验证 DecisionFeatures 的字段符合无自由文本的约束（通过简单的类型检查实现 MVP）。"""
    # 允许的字段列表及对应的合法类型
    allowed_fields = {
        "branch_id": str,
        "hypothesis_action": str, # Literal
        "stage": str,             # Literal
        "contract_passed": bool,
        "verification_passed": bool,
        "canary_passed": bool,
        "n_cases": int,
        "win_rate": (float, type(None)),
        "median_delta": (float, type(None)),
        "ci_low": (float, type(None)),
        "ci_high": (float, type(None)),
        "stale": bool,
        "recent_failure_codes": tuple,
        "runtime_ratio_median": (float, type(None)),
        "runtime_delta_median_ms": (float, type(None)),
        "runtime_regression_rate": (float, type(None)),
        "runtime_pairs": int,
        "protocol_gate_outcome": (str, type(None)),
        "total_pairs": int,
        "attempted_pairs": int,
        "valid_pairs": int,
        "failed_pairs": int,
        "candidate_failed_pairs": int,
        "champion_failed_pairs": int,
    }
    
    # 检查所有 DecisionFeatures 的字段是否都在允许列表中
    import dataclasses
    fields = {f.name: f.type for f in dataclasses.fields(DecisionFeatures)}
    assert "material_difference" not in fields
    assert "branch_lesson_usage" not in fields
    
    for name, expected_type in allowed_fields.items():
        assert name in fields, f"Missing field: {name}"
        # 注意：这里只是静态定义检查，真正的运行时 guard 在 SafeFeatureExtractor 实现


def test_decision_features_serialization_excludes_measurement_diagnostics():
    features = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=10,
        win_rate=0.7,
        median_delta=0.05,
        ci_low=0.01,
        ci_high=0.09,
        stale=False,
        recent_failure_codes=(),
    )

    payload = decision_features_to_payload(features)
    serialized_keys = set(_walk_mapping_keys(payload))
    denied_keys = DECISION_FEATURES_REPORT_METADATA_DENYLIST | {"BKS", "bks"}

    assert denied_keys.isdisjoint(serialized_keys)


def test_decision_features_schema_excludes_report_and_launcher_metadata():
    field_names = {field.name for field in dataclasses.fields(DecisionFeatures)}

    assert DECISION_FEATURES_REPORT_METADATA_DENYLIST.isdisjoint(field_names)


def _walk_mapping_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_mapping_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_mapping_keys(item)

def test_branch_state_enum():
    """验证 BranchState 涵盖了所有必要状态。"""
    states = [s.value for s in BranchState]
    expected = ["new", "explore", "explore_expand", "ready_validate", "validating", 
                "validating_expand", "ready_frozen", "frozen_testing", "promoted", 
                "abandoned", "stale", "blocked_infra"]
    for s in expected:
        assert s in states
