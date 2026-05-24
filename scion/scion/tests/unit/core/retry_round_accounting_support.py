from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
)


def hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Try a bounded local search variant.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )


def hypothesis_record(branch_id: str) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hyp-1",
        branch_id=branch_id,
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/local_search.py",
        hypothesis_text="Try a bounded local search variant.",
    )


class ContractGate:
    def validate_hypothesis(self, *args: Any, **kwargs: Any) -> ContractResult:
        return ContractResult(
            passed=True,
            checks=(CheckResult("C", True, "light", "ok", 0),),
        )

    def validate_patch(self, *args: Any, **kwargs: Any) -> ContractResult:
        return ContractResult(
            passed=True,
            checks=(CheckResult("P", True, "light", "ok", 0),),
        )


class HypothesisStore:
    def __init__(self) -> None:
        self.saved: list[HypothesisRecord] = []
        self.statuses: list[tuple[str, str]] = []

    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        return []

    def save(self, record: HypothesisRecord) -> None:
        self.saved.append(record)

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        self.statuses.append((hypothesis_id, status))


def pipeline(
    *,
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] | None = None,
    increment_round,
    increment_rounds_since_last_promote,
    get_current_round=lambda: 0,
    generate_hypothesis,
    generate_code,
    record_step,
    branch_controller=SimpleNamespace(),
    verification_gate=None,
    setup_workspace=lambda branch: None,
    apply_patch=lambda *args, **kwargs: None,
    record_verification_pass=lambda branch, code_hash: None,
    evaluate=lambda branch, workspace, hypothesis: None,
    apply_decision_and_finalize=lambda **kwargs: None,
    persist_branch_state=lambda branch_id: None,
    update_status_progress=lambda payload: None,
) -> ExploreStepPipeline:
    store = HypothesisStore()
    step_pipeline = ExploreStepPipeline(
        branch_controller=branch_controller,
        contract_gate=ContractGate(),
        verification_gate=verification_gate,
        hypothesis_store=store,
        registry=SimpleNamespace(),
        campaign_id="campaign",
        get_champion=lambda: None,
        pending_hypotheses=pending if pending is not None else {},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=increment_round,
        increment_rounds_since_last_promote=increment_rounds_since_last_promote,
        generate_hypothesis=generate_hypothesis,
        generate_code=generate_code,
        attempt_fix=lambda branch, patch, vresult: None,
        handle_failure=lambda *args, **kwargs: None,
        record_step=record_step,
        setup_workspace=setup_workspace,
        apply_patch=apply_patch,
        record_verification_pass=record_verification_pass,
        archive_failed_workspace=lambda workspace, branch_id, round_num: None,
        evaluate=evaluate,
        apply_decision_and_finalize=apply_decision_and_finalize,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        proposal_failure_detail_for=lambda branch_id: "forced code failure",
        proposal_session_ref_for=lambda branch_id: {"session_id": "s1"},
        get_current_round=get_current_round,
        persist_branch_state=persist_branch_state,
        update_status_progress=update_status_progress,
    )
    step_pipeline._test_store = store
    return step_pipeline


__all__ = ["hypothesis", "hypothesis_record", "pipeline"]
