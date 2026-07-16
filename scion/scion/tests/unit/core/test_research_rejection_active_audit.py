from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from scion.core.decision_completion_transaction import DecisionCompletionStore
from scion.core.execution_outcome import branch_has_execution_hold
from scion.core.models import Branch, BranchState, Decision, HypothesisRecord
from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.core.research_rejection_active_audit import audit_unowned_active_attempts
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry


def _owners(tmp_path: Path) -> tuple[LineageRegistry, BranchStore, HypothesisStore]:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    registry.claim_campaign_id("campaign-1")
    return registry, BranchStore(registry), HypothesisStore(registry)


def _branch(*, state: BranchState = BranchState.EXPLORE) -> Branch:
    return Branch(
        branch_id="branch-1",
        state=state,
        base_champion_id=1,
        base_champion_hash="base-hash",
        lineage_id="branch-1",
    )


def _hypothesis() -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id="branch-1",
        change_locus="operator",
        action="modify",
        status="active",
        target_file="operators/op.py",
        hypothesis_text="change operator",
        base_champion_version=1,
        proposal_digest="a" * 64,
    )


def _prompt(phase: str, attempt_id: str, *, generated: bool) -> dict[str, object]:
    return {
        "request_kind": phase,
        "context_digest": "context",
        "prompt_hash": "prompt",
        "trace_ref": f"traces/{attempt_id}" if generated else None,
        "prompt_manifest_ref": f"prompts/{attempt_id}" if generated else None,
        "raw_response_ref": f"responses/{attempt_id}" if generated else None,
        "provider_ok": True if generated else None,
        "ok": True if generated else None,
        "error_category": None,
        "error_type": None,
    }


def _record_group(
    registry: LineageRegistry,
    *,
    phase: str,
    attempt_id: str,
    terminal: bool = True,
    continuation: str | None = None,
) -> None:
    recorder = ProposalAttemptRecorder(registry)
    hypothesis_id = None if phase == "hypothesis" else "hypothesis-1"
    hypothesis_digest = None if phase == "hypothesis" else "a" * 64
    common = {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": attempt_id,
        "campaign_id": "campaign-1",
        "branch_id": "branch-1",
        "runtime_mode": "direct_v3",
        "phase": phase,
        "failure_lane": None,
        "attempt_kind": (
            "initial" if phase == "hypothesis" else "approved_code_continuation"
        ),
        "continuation_of_attempt_id": continuation,
        "anchors": {
            "problem_id": "test",
            "problem_spec_hash": "problem",
            "split_manifest_hash": "split",
            "seed_ledger_hash": "seed",
            "champion_version": 1,
            "champion_weight_revision": 0,
            "champion_code_snapshot_hash": "snapshot",
            "branch_base_champion_id": 1,
            "branch_base_champion_hash": "base-hash",
        },
        "tainted_artifact_refs": [],
    }
    recorder.record_transition(
        {
            **common,
            "status": "started",
            "transition_reason": "provider_call_started",
            "hypothesis_id": hypothesis_id,
            "hypothesis_digest": hypothesis_digest,
            "patch_digest": None,
            "prompt_call": _prompt(phase, attempt_id, generated=False),
        }
    )
    if terminal:
        recorder.record_transition(
            {
                **common,
                "status": "generated",
                "transition_reason": "provider_call_completed",
                "hypothesis_id": "hypothesis-1",
                "hypothesis_digest": "a" * 64,
                "patch_digest": "b" * 64 if phase == "code" else None,
                "prompt_call": _prompt(phase, attempt_id, generated=True),
            }
        )


def _audit(
    registry: LineageRegistry,
    branch_store: BranchStore,
    branch: Branch,
    hypotheses: tuple[HypothesisRecord, ...],
    *,
    prevalidated_candidate_owners: dict[str, str] | None = None,
):
    return audit_unowned_active_attempts(
        db_path=registry.db_path,
        campaign_id="campaign-1",
        branches=(branch,),
        active_hypotheses=hypotheses,
        branch_store=branch_store,
        registry=registry,
        prevalidated_candidate_owners=prevalidated_candidate_owners,
    )


def test_generated_hypothesis_without_h_row_installs_one_hold(tmp_path: Path) -> None:
    registry, branch_store, _ = _owners(tmp_path)
    branch = _branch()
    branch_store.save(branch)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")

    holds = _audit(registry, branch_store, branch, ())
    second = _audit(registry, branch_store, branch, ())

    assert len(holds) == 1
    assert holds[0].reason == "generated hypothesis has no durable H row owner"
    assert second == ()
    assert branch_has_execution_hold(branch)


def test_generated_code_without_completion_or_candidate_owner_holds(tmp_path: Path) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    hypothesis = _hypothesis()
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")
    _record_group(
        registry,
        phase="code",
        attempt_id="attempt-c",
        continuation="attempt-h",
    )

    holds = _audit(registry, branch_store, branch, (hypothesis,))

    assert len(holds) == 1
    assert holds[0].attempt_id == "attempt-c"
    assert "no rejection or verified-candidate owner" in holds[0].reason


def test_transition_row_payload_hypothesis_misbind_holds(tmp_path: Path) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    hypothesis = _hypothesis()
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")
    with sqlite3.connect(registry.db_path) as conn:
        conn.execute(
            "UPDATE experiment_events SET hypothesis_id = 'wrong-h' "
            "WHERE event_kind = 'proposal_attempt_transition' "
            "AND hypothesis_id = 'hypothesis-1'"
        )

    holds = _audit(registry, branch_store, branch, (hypothesis,))

    assert len(holds) == 1
    assert holds[0].reason == "proposal transition evidence is malformed or misbound"


def test_active_hypothesis_proposal_digest_mismatch_holds(tmp_path: Path) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    hypothesis = _hypothesis()
    hypothesis.proposal_digest = "c" * 64
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")

    holds = _audit(registry, branch_store, branch, (hypothesis,))

    assert len(holds) == 1
    assert "proposal digest conflicts" in holds[0].reason


def test_legacy_active_h_without_digest_and_without_strong_owner_holds(
    tmp_path: Path,
) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    hypothesis = _hypothesis()
    hypothesis.proposal_digest = None
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")

    holds = _audit(registry, branch_store, branch, (hypothesis,))

    assert len(holds) == 1
    assert "proposal digest conflicts" in holds[0].reason


@pytest.mark.parametrize(
    "state",
    [
        BranchState.READY_VALIDATE,
        BranchState.VALIDATING,
        BranchState.READY_FROZEN,
        BranchState.FROZEN_TESTING,
    ],
)
def test_validation_and_frozen_graph_with_durable_verified_owner_is_excluded(
    tmp_path: Path,
    state: BranchState,
) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch(state=state)
    hypothesis = _hypothesis()
    branch.current_code_hash = "c" * 64
    branch.last_clean_code_hash = "c" * 64
    branch.branch_evidence_summary = {
        "verified_candidate_commit": {
            "schema_version": "verified-candidate-commit-ref.v1",
            "artifact_schema": "verified-candidate-commit.v1",
            "artifact_ref": "artifacts/verified_candidate_commits/commit.json",
            "artifact_sha256": "d" * 64,
            "hypothesis_id": hypothesis.hypothesis_id,
            "verified_code_hash": "c" * 64,
            "executable_snapshot_hash": "e" * 64,
            "patch_digest": "b" * 64,
            "promotion_status": "committed",
            "evaluation_status": "pending",
            "commit_kind": "reconcile" if state is BranchState.VALIDATING else "explore",
        }
    }
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")
    _record_group(
        registry,
        phase="code",
        attempt_id="attempt-c",
        continuation="attempt-h",
    )

    assert _audit(registry, branch_store, branch, (hypothesis,)) == ()


def test_legacy_null_digest_pending_reconcile_owner_is_excluded(tmp_path: Path) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch(state=BranchState.VALIDATING)
    hypothesis = _hypothesis()
    hypothesis.proposal_digest = None
    branch.current_code_hash = "c" * 64
    branch.last_clean_code_hash = "c" * 64
    branch.branch_evidence_summary = {
        "verified_candidate_commit": {
            "schema_version": "verified-candidate-commit-ref.v1",
            "artifact_schema": "verified-candidate-commit.v1",
            "artifact_ref": "artifacts/verified_candidate_commits/commit.json",
            "artifact_sha256": "d" * 64,
            "hypothesis_id": hypothesis.hypothesis_id,
            "verified_code_hash": "c" * 64,
            "executable_snapshot_hash": "e" * 64,
            "patch_digest": "b" * 64,
            "promotion_status": "committed",
            "evaluation_status": "pending",
            "commit_kind": "reconcile",
        }
    }
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")

    assert _audit(registry, branch_store, branch, (hypothesis,)) == ()


def test_prevalidated_legacy_candidate_owner_requires_exact_hypothesis(
    tmp_path: Path,
) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch(state=BranchState.READY_VALIDATE)
    hypothesis = _hypothesis()
    hypothesis.proposal_digest = None
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")

    exact = _audit(
        registry,
        branch_store,
        branch,
        (hypothesis,),
        prevalidated_candidate_owners={branch.branch_id: hypothesis.hypothesis_id},
    )
    mismatched = _audit(
        registry,
        branch_store,
        branch,
        (hypothesis,),
        prevalidated_candidate_owners={branch.branch_id: "other-hypothesis"},
    )

    assert exact == ()
    assert len(mismatched) == 1


def test_current_committed_decision_is_a_durable_active_h_owner(tmp_path: Path) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    branch.current_code_hash = "c" * 64
    branch.last_clean_code_hash = "c" * 64
    hypothesis = _hypothesis()
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")
    _record_group(
        registry,
        phase="code",
        attempt_id="attempt-c",
        continuation="attempt-h",
    )
    target = copy.deepcopy(branch)
    target.state = BranchState.READY_VALIDATE
    decisions = DecisionCompletionStore(registry.db_path)
    intent = decisions.prepare(
        source_branch=branch,
        target_branch=target,
        hypothesis_record=hypothesis,
        target_hypothesis_status=None,
        decision=Decision.QUEUE_VALIDATE,
        reason_codes=("QUEUE",),
        protocol_result=None,
    )
    decisions.commit_state(intent)
    decisions.mark_committed(intent)
    persisted = branch_store.load(branch.branch_id)
    assert persisted is not None

    assert _audit(registry, branch_store, persisted, (hypothesis,)) == ()


def test_malformed_transition_rows_do_not_override_exact_decision_owner(
    tmp_path: Path,
) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    branch.current_code_hash = "c" * 64
    branch.last_clean_code_hash = "c" * 64
    hypothesis = _hypothesis()
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    _record_group(registry, phase="hypothesis", attempt_id="attempt-h")
    _record_group(
        registry,
        phase="code",
        attempt_id="attempt-c",
        continuation="attempt-h",
    )
    target = copy.deepcopy(branch)
    target.state = BranchState.READY_VALIDATE
    decisions = DecisionCompletionStore(registry.db_path)
    intent = decisions.prepare(
        source_branch=branch,
        target_branch=target,
        hypothesis_record=hypothesis,
        target_hypothesis_status=None,
        decision=Decision.QUEUE_VALIDATE,
        reason_codes=("QUEUE",),
        protocol_result=None,
    )
    decisions.commit_state(intent)
    decisions.mark_committed(intent)
    registry.record_event(
        {
            "event_id": "malformed-historical-transition",
            "campaign_id": "campaign-1",
            "branch_id": branch.branch_id,
            "hypothesis_id": "historical-hypothesis",
            "event_kind": "proposal_attempt_transition",
            "stage": "proposal_code",
            "audit_payload_json": "{not-json",
        }
    )
    registry.record_event(
        {
            "event_id": "malformed-current-h-transition",
            "campaign_id": "campaign-1",
            "branch_id": branch.branch_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "event_kind": "proposal_attempt_transition",
            "stage": "proposal_code",
            "audit_payload_json": json.dumps(
                {
                    "attempt_id": "malformed-current",
                    "hypothesis_id": hypothesis.hypothesis_id,
                }
            ),
        }
    )
    persisted = branch_store.load(branch.branch_id)
    assert persisted is not None

    assert _audit(registry, branch_store, persisted, (hypothesis,)) == ()


def test_legacy_decision_v1_verifies_after_proposal_digest_column_migration(
    tmp_path: Path,
) -> None:
    registry, branch_store, hypothesis_store = _owners(tmp_path)
    branch = _branch()
    branch.current_code_hash = "c" * 64
    branch.last_clean_code_hash = "c" * 64
    hypothesis = _hypothesis()
    branch_store.save(branch)
    hypothesis_store.save(hypothesis)
    target = copy.deepcopy(branch)
    target.state = BranchState.READY_VALIDATE
    decisions = DecisionCompletionStore(registry.db_path)
    intent = decisions.prepare(
        source_branch=branch,
        target_branch=target,
        hypothesis_record=hypothesis,
        target_hypothesis_status=None,
        decision=Decision.QUEUE_VALIDATE,
        reason_codes=("QUEUE",),
        protocol_result=None,
    )
    decisions.commit_state(intent)
    decisions.mark_committed(intent)
    with sqlite3.connect(registry.db_path) as conn:
        conn.execute(
            "UPDATE hypotheses SET proposal_digest = NULL WHERE hypothesis_id = ?",
            (hypothesis.hypothesis_id,),
        )

    assert DecisionCompletionStore(registry.db_path).verify_committed(
        intent.transaction_id
    )
