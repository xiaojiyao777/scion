from __future__ import annotations

import itertools
import uuid
from dataclasses import FrozenInstanceError, replace

import pytest

import scion.core.candidate_disposition as candidate_disposition_module
from scion.core.candidate_disposition import (
    CandidateDisposition,
    CandidateDispositionError,
    CandidateDispositionMapper,
    CandidateDispositionPlan,
    CandidateDispositionRule,
    CandidateHypothesisStatus,
)
from scion.core.models import Decision, DecisionFeatures, DecisionOutcome

_GATES = ("pass", "fail", "unclear", "expand", "continue", None)


def _features(**overrides: object) -> DecisionFeatures:
    values: dict[str, object] = {
        "branch_id": str(uuid.uuid4()),
        "hypothesis_action": "modify",
        "stage": "screening",
        "contract_passed": True,
        "verification_passed": True,
        "canary_passed": True,
        "n_cases": 8,
        "win_rate": 0.75,
        "median_delta": 2.0,
        "ci_low": 0.0,
        "ci_high": 4.0,
        "stale": False,
        "recent_failure_codes": (),
        "protocol_gate_outcome": "pass",
        "protocol_reason_codes": ("SCREENING_PASS",),
    }
    values.update(overrides)
    return DecisionFeatures(**values)  # type: ignore[arg-type]


def _outcome(
    decision: Decision,
    *,
    reason_codes: tuple[str, ...] = ("FORMAL_DECISION_REASON",),
    **feature_overrides: object,
) -> DecisionOutcome:
    return DecisionOutcome(
        decision=decision,
        reason_codes=reason_codes,
        features_snapshot=_features(**feature_overrides),
    )


@pytest.mark.parametrize(
    (
        "stage",
        "gate",
        "decision",
        "disposition",
        "hypothesis_status",
        "rule",
    ),
    (
        (
            "screening",
            "pass",
            Decision.QUEUE_VALIDATE,
            CandidateDisposition.EXACT_REUSE,
            CandidateHypothesisStatus.ADVANCED,
            CandidateDispositionRule.EXACT_STAGE_REUSE,
        ),
        (
            "screening",
            "expand",
            Decision.EXPAND_SCREENING,
            CandidateDisposition.EXACT_REUSE,
            CandidateHypothesisStatus.ADVANCED,
            CandidateDispositionRule.EXACT_STAGE_REUSE,
        ),
        (
            "screening",
            "fail",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.VERIFIED_SCREENING_CONTINUATION,
        ),
        (
            "screening",
            "unclear",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "screening",
            "continue",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "validation",
            "pass",
            Decision.QUEUE_FROZEN,
            CandidateDisposition.EXACT_REUSE,
            CandidateHypothesisStatus.ADVANCED,
            CandidateDispositionRule.EXACT_STAGE_REUSE,
        ),
        (
            "validation",
            "expand",
            Decision.EXPAND_VALIDATION,
            CandidateDisposition.EXACT_REUSE,
            CandidateHypothesisStatus.ADVANCED,
            CandidateDispositionRule.EXACT_STAGE_REUSE,
        ),
        (
            "validation",
            "fail",
            Decision.ABANDON,
            CandidateDisposition.REJECT_TERMINAL,
            CandidateHypothesisStatus.REJECTED,
            CandidateDispositionRule.TERMINAL_REJECT,
        ),
        (
            "validation",
            "unclear",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "validation",
            "continue",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "frozen",
            "pass",
            Decision.PROMOTE,
            CandidateDisposition.PROMOTE_EXACT,
            CandidateHypothesisStatus.PROMOTED,
            CandidateDispositionRule.FROZEN_PROMOTION,
        ),
        (
            "frozen",
            "fail",
            Decision.ABANDON,
            CandidateDisposition.REJECT_TERMINAL,
            CandidateHypothesisStatus.REJECTED,
            CandidateDispositionRule.TERMINAL_REJECT,
        ),
        (
            "frozen",
            "unclear",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "frozen",
            "continue",
            Decision.CONTINUE_EXPLORE,
            CandidateDisposition.PROVISIONAL_HEAD,
            CandidateHypothesisStatus.PROVISIONAL,
            CandidateDispositionRule.PROTOCOL_PROVISIONAL,
        ),
        (
            "frozen",
            "expand",
            Decision.ABANDON,
            CandidateDisposition.REJECT_TERMINAL,
            CandidateHypothesisStatus.REJECTED,
            CandidateDispositionRule.TERMINAL_REJECT,
        ),
    ),
)
def test_normal_stage_gate_decision_truth_table(
    stage: str,
    gate: str,
    decision: Decision,
    disposition: CandidateDisposition,
    hypothesis_status: CandidateHypothesisStatus,
    rule: CandidateDispositionRule,
) -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(decision, stage=stage, protocol_gate_outcome=gate)
    )

    assert plan.disposition is disposition
    assert plan.hypothesis_status is hypothesis_status
    assert plan.rule is rule
    assert plan.facts.decision is decision
    assert plan.facts.stage.value == stage
    assert plan.facts.gate_outcome is not None
    assert plan.facts.gate_outcome.value == gate


@pytest.mark.parametrize(
    "stage,gate",
    itertools.product(
        ("screening", "validation", "frozen"),
        _GATES,
    ),
)
def test_post_verification_abandon_is_terminal_for_every_gate(
    stage: str,
    gate: str | None,
) -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(
            Decision.ABANDON,
            reason_codes=("CANARY_FAILED",),
            stage=stage,
            protocol_gate_outcome=gate,
            canary_passed=False,
        )
    )

    assert plan.disposition is CandidateDisposition.REJECT_TERMINAL
    assert plan.hypothesis_status is CandidateHypothesisStatus.REJECTED
    assert plan.rule is CandidateDispositionRule.TERMINAL_REJECT


@pytest.mark.parametrize("gate", ("pass", "expand"))
def test_partial_champion_is_the_only_continue_pass_or_expand_exception(
    gate: str,
) -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(
            Decision.CONTINUE_EXPLORE,
            reason_codes=("SCREENING_PARTIAL_CHAMPION_EVIDENCE",),
            stage="screening",
            protocol_gate_outcome=gate,
            candidate_failed_pairs=0,
            champion_failed_pairs=1,
        )
    )

    assert plan.disposition is CandidateDisposition.PROVISIONAL_HEAD
    assert plan.hypothesis_status is CandidateHypothesisStatus.PROVISIONAL
    assert plan.rule is CandidateDispositionRule.PARTIAL_CHAMPION_PROVISIONAL


@pytest.mark.parametrize(
    "overrides",
    (
        {"stage": "validation"},
        {"stage": "frozen"},
        {"candidate_failed_pairs": 1},
        {"champion_failed_pairs": 0},
    ),
)
@pytest.mark.parametrize("gate", ("pass", "expand"))
def test_partial_champion_exception_rejects_fact_drift(
    overrides: dict[str, object],
    gate: str,
) -> None:
    facts: dict[str, object] = {
        "stage": "screening",
        "protocol_gate_outcome": gate,
        "candidate_failed_pairs": 0,
        "champion_failed_pairs": 1,
    }
    facts.update(overrides)

    with pytest.raises(CandidateDispositionError):
        CandidateDispositionMapper.map(
            _outcome(
                Decision.CONTINUE_EXPLORE,
                reason_codes=("SCREENING_PARTIAL_CHAMPION_EVIDENCE",),
                **facts,
            )
        )


@pytest.mark.parametrize(
    "reason_codes",
    (
        ("SCREENING_PASS",),
        (),
        (
            "SCREENING_PARTIAL_CHAMPION_EVIDENCE",
            "SCREENING_PASS",
        ),
    ),
)
@pytest.mark.parametrize("gate", ("pass", "expand"))
def test_partial_champion_exception_requires_exact_decision_reason(
    reason_codes: tuple[str, ...],
    gate: str,
) -> None:
    with pytest.raises(CandidateDispositionError):
        CandidateDispositionMapper.map(
            _outcome(
                Decision.CONTINUE_EXPLORE,
                reason_codes=reason_codes,
                stage="screening",
                protocol_gate_outcome=gate,
                candidate_failed_pairs=0,
                champion_failed_pairs=1,
            )
        )


def test_verified_screening_fail_continues_from_candidate_despite_statistics() -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(
            Decision.CONTINUE_EXPLORE,
            stage="screening",
            protocol_gate_outcome="fail",
            statistical_status="uncertain",
            win_rate=0.99,
            median_delta=1000.0,
            ci_low=999.0,
            ci_high=1001.0,
        )
    )

    assert plan.disposition is CandidateDisposition.PROVISIONAL_HEAD
    assert plan.rule is CandidateDispositionRule.VERIFIED_SCREENING_CONTINUATION


@pytest.mark.parametrize("stage", ("validation", "frozen"))
def test_protocol_fail_continue_is_invalid_after_screening(stage: str) -> None:
    with pytest.raises(CandidateDispositionError):
        CandidateDispositionMapper.map(
            _outcome(
                Decision.CONTINUE_EXPLORE,
                stage=stage,
                protocol_gate_outcome="fail",
            )
        )


def test_unused_safe_features_do_not_influence_the_plan() -> None:
    original = _outcome(
        Decision.CONTINUE_EXPLORE,
        stage="screening",
        protocol_gate_outcome="fail",
    )
    changed_features = replace(
        original.features_snapshot,
        branch_id=str(uuid.uuid4()),
        hypothesis_action="create_new",
        n_cases=999,
        wins=999,
        losses=0,
        ties=0,
        win_rate=1.0,
        median_delta=9999.0,
        ci_low=9998.0,
        ci_high=10000.0,
        statistical_status="positive",
        statistical_metric="totally_different_metric",
        runtime_ratio_median=0.01,
        runtime_delta_median_ms=-9999.0,
        runtime_regression_rate=0.0,
        runtime_pairs=999,
        protocol_reason_codes=("UNRELATED_PROTOCOL_REASON",),
        recent_failure_codes=("INFRA",),
        stale=True,
    )
    changed = replace(original, features_snapshot=changed_features)

    assert CandidateDispositionMapper.map(changed) == (
        CandidateDispositionMapper.map(original)
    )


def test_facts_are_private_frozen_mapper_output() -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(
            Decision.QUEUE_VALIDATE,
            stage="screening",
            protocol_gate_outcome="pass",
        )
    )

    assert "CandidateDispositionFacts" not in candidate_disposition_module.__all__
    assert not hasattr(candidate_disposition_module, "CandidateDispositionFacts")
    with pytest.raises(FrozenInstanceError):
        plan.facts.candidate_failed_pairs = 1  # type: ignore[misc]


def test_plan_is_frozen_and_can_only_be_created_by_mapper() -> None:
    plan = CandidateDispositionMapper.map(
        _outcome(
            Decision.QUEUE_VALIDATE,
            stage="screening",
            protocol_gate_outcome="pass",
        )
    )

    with pytest.raises(TypeError, match="must come from CandidateDispositionMapper"):
        CandidateDispositionPlan(  # type: ignore[call-arg]
            _token=object(),
            facts=plan.facts,
            disposition=plan.disposition,
            hypothesis_status=plan.hypothesis_status,
            rule=plan.rule,
        )
    with pytest.raises(FrozenInstanceError):
        plan.disposition = CandidateDisposition.REJECT_TERMINAL  # type: ignore[misc]


@pytest.mark.parametrize(
    "contract_passed,verification_passed",
    ((False, True), (True, False)),
)
def test_pre_verification_decisions_are_outside_d1(
    contract_passed: bool,
    verification_passed: bool,
) -> None:
    with pytest.raises(CandidateDispositionError, match="post-Verification"):
        CandidateDispositionMapper.map(
            _outcome(
                Decision.ABANDON,
                protocol_gate_outcome=None,
                contract_passed=contract_passed,
                verification_passed=verification_passed,
            )
        )


@pytest.mark.parametrize(
    "stage,gate",
    itertools.product(("screening", "validation", "frozen"), _GATES),
)
def test_validation_repair_required_is_never_a_d1_input(
    stage: str,
    gate: str | None,
) -> None:
    with pytest.raises(CandidateDispositionError, match="legacy-only"):
        CandidateDispositionMapper.map(
            _outcome(
                Decision.VALIDATION_REPAIR_REQUIRED,
                stage=stage,
                protocol_gate_outcome=gate,
            )
        )


def test_every_other_decision_stage_gate_combination_fails_closed() -> None:
    normal = {
        ("screening", "pass", Decision.QUEUE_VALIDATE),
        ("screening", "expand", Decision.EXPAND_SCREENING),
        ("screening", "fail", Decision.CONTINUE_EXPLORE),
        ("screening", "unclear", Decision.CONTINUE_EXPLORE),
        ("screening", "continue", Decision.CONTINUE_EXPLORE),
        ("validation", "pass", Decision.QUEUE_FROZEN),
        ("validation", "expand", Decision.EXPAND_VALIDATION),
        ("validation", "fail", Decision.ABANDON),
        ("validation", "unclear", Decision.CONTINUE_EXPLORE),
        ("validation", "continue", Decision.CONTINUE_EXPLORE),
        ("frozen", "pass", Decision.PROMOTE),
        ("frozen", "fail", Decision.ABANDON),
        ("frozen", "unclear", Decision.CONTINUE_EXPLORE),
        ("frozen", "continue", Decision.CONTINUE_EXPLORE),
        ("frozen", "expand", Decision.ABANDON),
    }
    for stage, gate, decision in itertools.product(
        ("screening", "validation", "frozen"),
        _GATES,
        tuple(Decision),
    ):
        key = (stage, gate, decision)
        # Every post-Verification ABANDON is the explicit hard-safety rule.
        if decision is Decision.ABANDON or key in normal:
            continue
        with pytest.raises(CandidateDispositionError):
            CandidateDispositionMapper.map(
                _outcome(
                    decision,
                    stage=stage,
                    protocol_gate_outcome=gate,
                )
            )
