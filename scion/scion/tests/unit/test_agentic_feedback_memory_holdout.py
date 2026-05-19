from __future__ import annotations

from scion.tests.unit.agentic_feedback_test_support import *

def test_default_holdout_summary_exposes_no_validation_or_frozen_rows(
    tmp_path: Path,
) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        _context(tmp_path),
    )

    assert observation.structured_payload["holdout_steps"] == []
    assert observation.structured_payload["validation_exposure"] == "none"
    assert observation.structured_payload["frozen_exposure"] == "none"


def test_memory_query_hides_promotion_and_holdout_signals(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query",
        {},
        _context(tmp_path),
    )

    text = observation.structured_payload["text"].lower()
    assert "safe screening idea" in text
    assert "champion_evolution" not in text
    assert "promoted" not in text
    assert "promotion" not in text
    assert "validation" not in text
    assert "frozen" not in text
    assert "holdout" not in text


def test_memory_query_rejects_default_render_without_safe_view(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=UnsafeDefaultOnlyMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query", {}, context
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered
    assert "promotion path" not in rendered


def test_memory_query_rejects_non_callable_render(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query", {}, context
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED


def test_champion_summary_hides_version_and_promotion_fields(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "context.read_champion_summary",
        {},
        _context(tmp_path),
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert "version" not in rendered
    assert "promotion" not in rendered
    assert "promoted_at" not in rendered
    assert "promotion-secret" not in rendered


def test_holdout_aggregate_does_not_expose_malicious_raw_refs_or_case_ids(
    tmp_path: Path,
) -> None:
    context = _context(
        tmp_path,
        policy=ContextExposurePolicy(
            validation_exposure=HoldoutExposure.AGGREGATE,
            frozen_exposure=HoldoutExposure.AGGREGATE,
        ),
    )
    malicious_step = StepRecord(
        round_num=4,
        branch_id="branch-1",
        hypothesis=_hyp(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.VALIDATION,
            stats=_stats(),
            gate_outcome="fail",
            reason_codes=("VALIDATION_REASON",),
            exposed_summary="validation safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            case_ids=("SECRET_CASE_ID",),
            seed_set=(999,),
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="SECRET_CASE_ID",
                    n_pairs=2,
                    wins=2,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    dominant_result="win",
                    decisive_metric="distance",
                    median_deltas={"distance": -5.0},
                ),
            ),
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=(malicious_step,),
        search_memory=context.search_memory,
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        context,
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is False
    assert "SECRET_RAW_REF" not in rendered
    assert "SECRET_CASE_ID" not in rendered
    assert "case_feedback" not in rendered
    assert "raw_metrics_ref" not in rendered
