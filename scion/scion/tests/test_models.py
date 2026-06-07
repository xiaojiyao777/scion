import pytest
import uuid
import re
import dataclasses

from scion.core.explore_step.material_difference import (
    material_difference_pre_code_block_reason,
)
from scion.core.explore_step.pipeline import (
    material_difference_pre_code_block_reason as pipeline_md_block_reason,
)
from scion.core.models import (
    Branch,
    Decision,
    DecisionFeatures,
    DecisionOutcome,
    BranchState,
    HypothesisProposal,
)
from scion.proposal.engine import _parse_hypothesis

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
    assert "material_difference" not in fields
    
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


def test_hypothesis_material_difference_round_trips_and_filters_raw_text():
    proposal = _parse_hypothesis(
        {
            "hypothesis_text": "Change the generic search surface in a bounded way.",
            "change_locus": "search_surface",
            "action": "modify",
            "target_file": "surfaces/search.py",
            "material_difference": {
                "changed_dimensions": ["target_file", "effect_path"],
                "signature_digest": "abc123",
                "evidence_status_delta": ["activation_changed"],
                "raw_cross_branch_text": "do not persist raw context",
                "rationale": "do not persist rationale",
                "trace": {"tool": "do not persist trace"},
                "hypothesis_text": "do not duplicate hypothesis prose",
                "long_claim": "x" * 121,
                "nested": {
                    "status": "different",
                    "trace_id": "drop-me",
                },
            },
        }
    )

    assert proposal.material_difference == {
        "changed_dimensions": ["target_file", "effect_path"],
        "signature_digest": "abc123",
        "evidence_status_delta": ["activation_changed"],
        "nested": {"status": "different"},
    }
    round_tripped = HypothesisProposal(**dataclasses.asdict(proposal))
    assert round_tripped.material_difference == proposal.material_difference


def test_material_difference_required_blocks_empty_record_before_code():
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={
            "material_difference_required": True,
            "material_difference_required_for": "sibling_nearby_attempt",
        },
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
    )

    reason = material_difference_pre_code_block_reason(hypothesis, branch)

    assert reason is not None
    assert "material_difference_required_missing" in reason
    assert "before code generation" in reason

    minimal_metadata_branch = Branch(
        branch_id="b1-minimal",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={"material_difference_required": True},
    )
    assert (
        material_difference_pre_code_block_reason(
            hypothesis,
            minimal_metadata_branch,
        )
        is not None
    )


def test_material_difference_pipeline_import_stays_compatible():
    assert pipeline_md_block_reason is material_difference_pre_code_block_reason


def test_material_difference_requirement_record_in_branch_metadata_blocks_before_code():
    requirement = {
        "schema_version": "material_difference_requirement.v1",
        "record_type": "material_difference_requirement",
        "record_id": "material_difference_requirement:test",
        "record_digest": "sha256:test",
        "required_for": "clean_fork_new_branch",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }
    branch = Branch(
        branch_id="b1-record",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={
            "material_difference_required": True,
            "material_difference_requirement": requirement,
        },
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
    )

    reason = material_difference_pre_code_block_reason(hypothesis, branch)

    assert reason is not None
    assert "source=branch.branch_evidence_summary" in reason
    assert "required_for=clean_fork_new_branch" in reason
    hypothesis.material_difference = {"signature_digest": "abc123"}
    assert material_difference_pre_code_block_reason(hypothesis, branch) is None


def test_material_difference_requirement_rejects_boilerplate_record_before_code():
    branch = Branch(
        branch_id="b1-boilerplate",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={
            "material_difference_required": True,
            "material_difference_required_for": "clean_fork_new_branch",
        },
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
    )

    hypothesis.material_difference = {"summary": "different approach"}
    reason = material_difference_pre_code_block_reason(hypothesis, branch)
    assert reason is not None
    assert "material_difference_required_missing" in reason

    hypothesis.material_difference = {
        "differs_from": "nearby sibling attempt",
        "effect_path": "different descriptive effect path",
    }
    reason = material_difference_pre_code_block_reason(hypothesis, branch)
    assert reason is not None
    assert "material_difference_required_missing" in reason

    hypothesis.material_difference = {
        "changed_dimensions": ["search_budget_allocation"]
    }
    assert material_difference_pre_code_block_reason(hypothesis, branch) is None


@pytest.mark.parametrize(
    "material_difference",
    [
        {"schema_version": "material_difference.v1"},
        {"required_for": "clean_fork_new_branch"},
        {"decision_features_excluded": "true"},
        {
            "schema_version": "material_difference.v1",
            "record_type": "material_difference",
            "record_id": "material_difference:test",
            "required_for": "clean_fork_new_branch",
            "decision_features_excluded": True,
            "proposal_visibility_only": True,
        },
    ],
)
def test_material_difference_requirement_rejects_metadata_only_record_before_code(
    material_difference,
):
    branch = Branch(
        branch_id="b1-metadata-only",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={
            "material_difference_required": True,
            "material_difference_required_for": "clean_fork_new_branch",
        },
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
        material_difference=material_difference,
    )

    reason = material_difference_pre_code_block_reason(hypothesis, branch)

    assert reason is not None
    assert "material_difference_required_missing" in reason


@pytest.mark.parametrize(
    "material_difference",
    [
        {"changed_dimension": "surface_selection"},
        {"changed_dimensions": ["search_budget_allocation"]},
        {"signature_digest": "abc123"},
        {"signature": {"surface": "search_surface"}},
        {"evidence_status_delta": ["activation_status_changed"]},
        {"evidence_deltas": [{"status": "screening_effect_changed"}]},
        {"mechanism_family_delta": "family_changed"},
        {"intervention_type_delta": "intervention_changed"},
        {"surface_delta": "search_surface_changed"},
        {"failure_signature_delta": "failure_mode_changed"},
        {"weak_signal_delta": "weak_activation_signal_changed"},
    ],
)
def test_material_difference_requirement_accepts_whitelisted_signal_fields(
    material_difference,
):
    branch = Branch(
        branch_id="b1-whitelist",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_evidence_summary={
            "material_difference_required": True,
            "material_difference_required_for": "clean_fork_new_branch",
        },
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
        material_difference=material_difference,
    )

    assert material_difference_pre_code_block_reason(hypothesis, branch) is None


def test_material_difference_not_required_or_present_does_not_block_code():
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a generic alternate surface behavior.",
        change_locus="search_surface",
        action="modify",
        target_file="surfaces/search.py",
    )

    assert material_difference_pre_code_block_reason(hypothesis, branch) is None

    required_branch = Branch(
        branch_id="b2",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
    )
    hypothesis.material_difference = {
        "changed_dimensions": ["effect_path"],
        "signature_digest": "abc123",
    }
    session_ref = {
        "metadata": {
            "material_difference_requirements": {
                "required_for": "another_nearby_attempt",
                "signature": {"change_locus": "search_surface"},
            }
        }
    }

    assert (
        material_difference_pre_code_block_reason(
            hypothesis,
            required_branch,
            session_ref=session_ref,
        )
        is None
    )
