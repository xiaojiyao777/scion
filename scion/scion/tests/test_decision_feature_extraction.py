"""Focused tests split from test_decision.py."""

from dataclasses import fields, replace

from .decision_test_support import *  # noqa: F401,F403
from scion.core.features import (
    RUNTIME_EVIDENCE_CONFIDENCE_VALUES,
    RUNTIME_EVIDENCE_STATUS_VALUES,
)
from scion.core.models import DecisionFeatures


def test_decision_features_field_set_preserves_v3_boundary():
    expected_fields = {
        "branch_id",
        "hypothesis_action",
        "stage",
        "contract_passed",
        "verification_passed",
        "canary_passed",
        "n_cases",
        "win_rate",
        "median_delta",
        "ci_low",
        "ci_high",
        "stale",
        "recent_failure_codes",
        "wins",
        "losses",
        "ties",
        "runtime_guard_passed",
        "runtime_guard_ratio",
        "runtime_guard_timeout",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "runtime_pairs",
        "runtime_evidence_confidence",
        "runtime_evidence_status",
        "protocol_gate_outcome",
        "protocol_reason_codes",
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
        "pair_wins",
        "pair_losses",
        "pair_ties",
        "statistical_status",
        "statistical_metric",
        "screening_expand_count",
        "validation_expand_count",
    }
    actual_fields = {field.name for field in fields(DecisionFeatures)}
    forbidden_fragments = (
        "bks",
        "gap",
        "case_hardness",
        "case_gap",
        "case_features",
        "prompt",
        "prompt_ratio",
        "signal_density",
        "calibration",
        "mde",
        "effect_to_mde",
        "llm",
        "hypothesis_text",
        "cross_branch",
        "branch_lesson",
        "mechanism",
        "opportunity",
        "raw",
        "pair_feedback",
    )

    assert actual_fields == expected_fields
    assert not [
        field
        for field in sorted(actual_fields)
        for fragment in forbidden_fragments
        if fragment in field
    ]


def test_extract_basic():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(),
    )
    assert features.contract_passed is True
    assert features.verification_passed is True
    assert features.canary_passed is True
    assert features.win_rate == pytest.approx(0.7)
    assert features.stage == "screening"


def test_extract_no_protocol():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
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
    )
    assert features.runtime_ratio_median == pytest.approx(1.42)
    assert features.runtime_delta_median_ms == pytest.approx(37.5)
    assert features.runtime_regression_rate == pytest.approx(0.75)
    assert features.runtime_pairs == 8
    assert features.runtime_evidence_confidence == "sufficient"
    assert features.protocol_gate_outcome == "pass"
    assert features.total_pairs == 10
    assert features.valid_pairs == 8
    assert features.failed_pairs == 2
    assert features.candidate_failed_pairs == 1
    assert features.champion_failed_pairs == 1
    _validate_no_free_text(features)


def test_extract_ignores_telemetry_free_text_from_exposed_summary():
    branch = _branch()
    protocol = replace(
        _protocol(),
        exposed_summary=(
            "telemetry guard observed stage budget starvation: "
            "solver_algorithm_phase_runtime_ms.alns had no positive runtime evidence"
        ),
    )

    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=protocol,
    )

    _validate_no_free_text(features)
    assert "alns" not in repr(features)
    assert "solver_algorithm_phase_runtime_ms" not in repr(features)


def test_extract_protocol_runtime_confidence_from_cached_champion():
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
            runtime_confidence="low_cached_champion",
        ),
    )

    assert features.runtime_evidence_confidence == "low_cached_champion"
    _validate_no_free_text(features)


def test_extract_protocol_declared_low_runtime_confidence_passes_guard():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(runtime_confidence="low"),
    )

    assert features.runtime_evidence_confidence == "low"
    _validate_no_free_text(features)


def test_extract_protocol_low_sample_runtime_confidence_passes_guard():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=_protocol(
            runtime_ratio_median=1.05,
            runtime_delta_median_ms=10.0,
            runtime_regression_rate=0.25,
            runtime_pairs=2,
        ),
    )

    assert features.runtime_evidence_confidence == "low_sample_diagnostic"
    _validate_no_free_text(features)


def test_extract_protocol_runtime_status_values_pass_guard():
    for status in RUNTIME_EVIDENCE_STATUS_VALUES:
        features = _extractor.extract(
            branch=_branch(),
            hypothesis_action="modify",
            contract=_contract(),
            verification=_verification(),
            canary=_canary(),
            protocol=_protocol(runtime_evidence_status=status),
        )

        assert features.runtime_evidence_status == status
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
    )
    assert features.protocol_gate_outcome == "continue"
    assert features.protocol_reason_codes == ("SCREENING_PASS",)
    _validate_no_free_text(features)


def test_extractor_rejects_unknown_protocol_reason_code():
    protocol = replace(
        _protocol(),
        reason_codes=("free text supplied as a reason",),
    )

    with pytest.raises(DecisionInputGuardError, match="Unknown protocol reason code"):
        _extractor.extract(
            branch=_branch(),
            hypothesis_action="modify",
            contract=_contract(),
            verification=_verification(),
            canary=_canary(),
            protocol=protocol,
        )


def test_validate_no_free_text_valid():
    branch = _branch()
    features = _extractor.extract(
        branch=branch,
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
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
        recent_failure_codes=(),
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
        recent_failure_codes=("FREE_TEXT_FAILURE_REASON",),
    )
    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)


def test_validate_statistical_metric_rejects_free_text_prose():
    from scion.core.models import DecisionFeatures

    features = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="validation",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=4,
        win_rate=0.75,
        median_delta=1.0,
        ci_low=0.1,
        ci_high=2.0,
        stale=False,
        recent_failure_codes=(),
        statistical_metric="total cost improved because candidate looked better",
    )

    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(features)


@pytest.mark.parametrize("confidence", sorted(RUNTIME_EVIDENCE_CONFIDENCE_VALUES))
def test_validate_runtime_evidence_confidence_known_values(confidence):
    features = _extractor.extract(
        branch=_branch(),
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
    )

    _validate_no_free_text(
        replace(features, runtime_evidence_confidence=confidence)
    )


@pytest.mark.parametrize("status", sorted(RUNTIME_EVIDENCE_STATUS_VALUES))
def test_validate_runtime_evidence_status_known_values(status):
    features = _extractor.extract(
        branch=_branch(),
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
    )

    _validate_no_free_text(replace(features, runtime_evidence_status=status))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "runtime_evidence_confidence",
            "runtime evidence looked cached but acceptable",
        ),
        ("runtime_evidence_confidence", "new_runtime_confidence_code"),
        ("runtime_evidence_status", "fresh runtime required by operator note"),
        ("runtime_evidence_status", "fresh_required_v2"),
    ],
)
def test_validate_runtime_evidence_unknown_values_fail_closed(field_name, value):
    features = _extractor.extract(
        branch=_branch(),
        hypothesis_action="modify",
        contract=_contract(),
        verification=_verification(),
        canary=_canary(),
        protocol=None,
    )

    with pytest.raises(DecisionInputGuardError):
        _validate_no_free_text(replace(features, **{field_name: value}))


def test_extractor_rejects_statistical_metric_not_declared_in_metric_stats():
    from dataclasses import replace
    from scion.core.models import MetricEvalStats

    protocol = _protocol(
        statistical_status="positive",
        statistical_metric="undeclared_metric",
    )
    protocol = replace(
        protocol,
        stats=replace(
            protocol.stats,
            metric_stats=(
                MetricEvalStats(
                    metric_name="declared_metric",
                    median_delta=1.0,
                    ci_low=0.1,
                    ci_high=2.0,
                    n_cases=4,
                ),
            ),
        ),
    )

    with pytest.raises(DecisionInputGuardError):
        _extractor.extract(
            branch=_branch(),
            hypothesis_action="modify",
            contract=_contract(),
            verification=_verification(),
            canary=_canary(),
            protocol=protocol,
        )
