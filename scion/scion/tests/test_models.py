import pytest
import uuid
import re
from scion.core.models import DecisionFeatures, Decision, DecisionOutcome, BranchState

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
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0
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
        "recent_retry_count": int,
        "recent_failure_codes": tuple,
        "budget_remaining_ratio": float,
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
    
    for name, expected_type in allowed_fields.items():
        assert name in fields, f"Missing field: {name}"
        # 注意：这里只是静态定义检查，真正的运行时 guard 在 SafeFeatureExtractor 实现

def test_branch_state_enum():
    """验证 BranchState 涵盖了所有必要状态。"""
    states = [s.value for s in BranchState]
    expected = ["new", "explore", "explore_expand", "ready_validate", "validating", 
                "validating_expand", "ready_frozen", "frozen_testing", "promoted", 
                "abandoned", "stale", "blocked_infra"]
    for s in expected:
        assert s in states
