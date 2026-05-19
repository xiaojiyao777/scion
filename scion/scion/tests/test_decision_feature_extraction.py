"""Focused tests split from test_decision.py."""

from .decision_test_support import *  # noqa: F401,F403

def test_extract_basic():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(),
        budget=BudgetState(total=100, used=10),
    )
    assert features.contract_passed is True
    assert features.verification_passed is True
    assert features.canary_passed is True
    assert features.win_rate == pytest.approx(0.7)
    assert features.stage == "screening"
    assert features.budget_remaining_ratio == pytest.approx(0.9)


def test_extract_no_protocol():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.win_rate is None
    assert features.n_cases == 0


def test_extract_stale_flag():
    branch = _branch(state=BranchState.STALE)
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.stale is True


def test_extract_validation_stage():
    branch = _branch(state=BranchState.VALIDATING)
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(stage=ExperimentStage.VALIDATION),
        budget=BudgetState(total=100, used=0),
    )
    assert features.stage == "validation"


def test_extract_expand_counters_propagate():
    """T3: SafeFeatureExtractor must copy stage-aware expand counters from
    Branch to DecisionFeatures so decision rules can use them."""
    branch = _branch()
    branch.screening_expand_count = 2
    branch.validation_expand_count = 1
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.screening_expand_count == 2
    assert features.validation_expand_count == 1


def test_extract_runtime_guard_facts_without_free_text():
    branch = _branch()
    verification = VerificationResult(
        passed=True,
        checks=(
            CheckResult(
                "V9_perf_guard",
                True,
                "heavy",
                "perf ok",
                3,
                metadata={
                    "ratio": 1.25,
                    "candidate_timeout": False,
                    "case_id": "case-a",
                },
            ),
        ),
    )
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=verification,
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    assert features.runtime_guard_passed is True
    assert features.runtime_guard_ratio == pytest.approx(1.25)
    assert features.runtime_guard_timeout is False
    _validate_no_free_text(features)


def test_extract_protocol_runtime_facts_without_free_text():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(
            runtime_ratio_median=1.42,
            runtime_delta_median_ms=37.5,
            runtime_regression_rate=0.75,
            runtime_pairs=8,
            total_pairs=10,
            attempted_pairs=10,
            valid_pairs=8,
            failed_pairs=2,
            candidate_failed_pairs=1,
            champion_failed_pairs=1,
        ),
        budget=BudgetState(total=100, used=0),
    )
    assert features.runtime_ratio_median == pytest.approx(1.42)
    assert features.runtime_delta_median_ms == pytest.approx(37.5)
    assert features.runtime_regression_rate == pytest.approx(0.75)
    assert features.runtime_pairs == 8
    assert features.protocol_gate_outcome == "pass"
    assert features.total_pairs == 10
    assert features.valid_pairs == 8
    assert features.failed_pairs == 2
    assert features.candidate_failed_pairs == 1
    assert features.champion_failed_pairs == 1
    _validate_no_free_text(features)


def test_extract_legacy_continue_protocol_gate_outcome():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(win_rate=0.3, gate_outcome="continue"),
        budget=BudgetState(total=100, used=0),
    )
    assert features.protocol_gate_outcome == "continue"
    _validate_no_free_text(features)


def test_validate_no_free_text_valid():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
        budget=BudgetState(total=100, used=0),
    )
    # Should not raise
    _validate_no_free_text(features)


def test_validate_invalid_uuid_raises():
    from scion.core.models import DecisionFeatures
    import dataclasses
    features = DecisionFeatures(
        branch_id="not-a-uuid",
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=0,
        win_rate=None,
        median_delta=None,
        ci_low=None,
        ci_high=None,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
    )
    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)


def test_validate_unknown_failure_code_raises():
    from scion.core.models import DecisionFeatures
    features = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=0,
        win_rate=None,
        median_delta=None,
        ci_low=None,
        ci_high=None,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=("FREE_TEXT_FAILURE_REASON",),
        budget_remaining_ratio=1.0,
    )
    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)
