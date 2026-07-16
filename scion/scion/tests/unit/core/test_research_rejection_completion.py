from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.evidence_recording.replay_identity import stable_patch_digest
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.core.proposal_pipeline.direct_attempt_lifecycle import (
    DirectAttemptLifecycle,
)
from scion.core.research_rejection_completion import (
    ResearchRejectionCompletionStore,
)
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry
from scion.runtime.workspace import WorkspaceMaterializer


@dataclass
class Harness:
    campaign: Path
    campaign_id: str
    registry: LineageRegistry
    branch_store: BranchStore
    hypothesis_store: HypothesisStore
    materializer: WorkspaceMaterializer
    controller: BranchController
    lifecycle: WorkspaceLifecycleService
    branch: Branch
    hypothesis: HypothesisRecord
    finalizer: ResearchRejectionFinalizer
    store: ResearchRejectionCompletionStore
    champion: ChampionState


def _harness(tmp_path: Path, *, durable_workspace: bool = False) -> Harness:
    campaign = tmp_path / "campaign"
    source = tmp_path / "source"
    (source / "operators").mkdir(parents=True)
    (source / "operators" / "op.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "registry.yaml").write_text("operators: []\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(
        str(campaign),
        editable_patterns=("operators/**",),
    )
    initial = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=str(source),
        code_snapshot_hash=materializer.compute_snapshot_hash(str(source)),
    )
    snapshot = materializer.create_champion_snapshot(
        initial,
        str(campaign / "champions"),
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path=snapshot,
        code_snapshot_hash=materializer.compute_snapshot_hash(snapshot),
    )
    registry = LineageRegistry(str(campaign / "scion.db"))
    campaign_id = registry.claim_campaign_id("campaign-1")
    branch_store = BranchStore(registry)
    hypothesis_store = HypothesisStore(registry)
    branch = Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash=champion.code_snapshot_hash,
        lineage_id="branch-1",
    )
    controller = BranchController()
    controller.restore_branch(branch)
    branch_workspaces: dict[str, str] = {}
    if durable_workspace:
        workspace = materializer.create_branch_workspace(
            branch.branch_id,
            champion.code_snapshot_path,
        )
        branch_workspaces[branch.branch_id] = workspace
        code_hash = materializer.compute_code_hash(workspace)
        branch.current_code_hash = code_hash
        branch.last_clean_code_hash = code_hash
    branch_store.save(branch)
    proposal = HypothesisProposal(
        hypothesis_text="change operator",
        change_locus="operator",
        action="modify",
        target_file="operators/op.py",
        target_weakness="operator is static",
        expected_effect="operator adapts",
    )
    hypothesis = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus=proposal.change_locus,
        action=proposal.action,
        status="active",
        target_file=proposal.target_file,
        hypothesis_text=proposal.hypothesis_text,
        base_champion_version=1,
        proposal_digest=DirectAttemptLifecycle.hypothesis_digest(proposal),
    )
    hypothesis_store.save(hypothesis)
    lifecycle = WorkspaceLifecycleService(
        materializer=materializer,
        branch_controller=controller,
        branch_workspaces=branch_workspaces,
        branch_patches={},
        champion_lock=_NullLock(),
        get_champion=lambda: champion,
    )
    store = ResearchRejectionCompletionStore(registry.db_path)
    approved: set[str] = {branch.branch_id}
    finalizer = ResearchRejectionFinalizer(
        campaign_id=campaign_id,
        campaign_dir=str(campaign),
        store=store,
        branch_store=branch_store,
        materializer=materializer,
        workspace_lifecycle=lifecycle,
        branch_hypotheses={branch.branch_id: object()},
        branch_patches={},
        branch_current_hypothesis={branch.branch_id: hypothesis},
        discard_approved_hypothesis_binding=lambda bid: approved.discard(bid),
    )
    finalizer._test_approved = approved  # type: ignore[attr-defined]
    return Harness(
        campaign=campaign,
        campaign_id=campaign_id,
        registry=registry,
        branch_store=branch_store,
        hypothesis_store=hypothesis_store,
        materializer=materializer,
        controller=controller,
        lifecycle=lifecycle,
        branch=branch,
        hypothesis=hypothesis,
        finalizer=finalizer,
        store=store,
        champion=champion,
    )


class _NullLock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


class _Crash(RuntimeError):
    pass


def _crash_at(target: str):
    def hook(phase: str, _intent: object) -> None:
        if phase == target:
            raise _Crash(target)

    return hook


def _record_attempt(
    harness: Harness,
    *,
    phase: str,
    attempt_id: str,
    hypothesis_attempt_id: str | None = None,
    patch: PatchProposal | None = None,
) -> dict[str, str]:
    anchors = {
        "problem_id": "test",
        "problem_spec_hash": "problem",
        "split_manifest_hash": "split",
        "seed_ledger_hash": "seed",
        "champion_version": 1,
        "champion_weight_revision": 0,
        "champion_code_snapshot_hash": harness.champion.code_snapshot_hash,
        "branch_base_champion_id": harness.branch.base_champion_id,
        "branch_base_champion_hash": harness.branch.base_champion_hash,
    }
    hypothesis_digest = str(harness.hypothesis.proposal_digest)
    patch_digest = stable_patch_digest(patch.iter_file_changes()) if patch else None
    common = {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": attempt_id,
        "campaign_id": harness.campaign_id,
        "branch_id": harness.branch.branch_id,
        "runtime_mode": "direct_v3",
        "phase": phase,
        "attempt_kind": (
            "initial" if phase == "hypothesis" else "approved_code_continuation"
        ),
        "continuation_of_attempt_id": hypothesis_attempt_id,
        "anchors": anchors,
        "failure_lane": None,
        "tainted_artifact_refs": [],
    }
    started = {
        **common,
        "status": "started",
        "transition_reason": "provider_call_started",
        "hypothesis_id": (
            None if phase == "hypothesis" else harness.hypothesis.hypothesis_id
        ),
        "hypothesis_digest": None if phase == "hypothesis" else hypothesis_digest,
        "patch_digest": None,
        "prompt_call": {
            "request_kind": phase,
            "context_digest": "context",
            "prompt_hash": "prompt",
            "trace_ref": None,
            "prompt_manifest_ref": None,
            "raw_response_ref": None,
            "provider_ok": None,
            "ok": None,
            "error_category": None,
            "error_type": None,
        },
    }
    generated = {
        **common,
        "status": "generated",
        "transition_reason": "provider_call_completed",
        "hypothesis_id": harness.hypothesis.hypothesis_id,
        "hypothesis_digest": hypothesis_digest,
        "patch_digest": patch_digest,
        "prompt_call": {
            "request_kind": phase,
            "context_digest": "context",
            "prompt_hash": "prompt",
            "trace_ref": f"traces/{attempt_id}.json",
            "prompt_manifest_ref": f"prompts/{attempt_id}.json",
            "raw_response_ref": f"responses/{attempt_id}.json",
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
        },
    }
    started_event = f"event-{attempt_id}-started"
    generated_event = f"event-{attempt_id}-generated"
    for event_id, payload in (
        (started_event, started),
        (generated_event, generated),
    ):
        harness.registry.record_event(
            {
                "event_id": event_id,
                "campaign_id": harness.campaign_id,
                "branch_id": harness.branch.branch_id,
                "hypothesis_id": payload["hypothesis_id"],
                "event_kind": "proposal_attempt_transition",
                "stage": f"proposal_{phase}",
                "audit_payload_json": json.dumps(payload, sort_keys=True),
            }
        )
    ref = {
        "attempt_id": attempt_id,
        "lineage_event_id": generated_event,
        "started_lineage_event_id": started_event,
        "phase": phase,
        "status": "generated",
    }
    if hypothesis_attempt_id:
        ref["hypothesis_attempt_id"] = hypothesis_attempt_id
    return ref


def _record_raw_transition(
    harness: Harness,
    *,
    event_id: str,
    hypothesis_id: str | None,
    stage: str,
    audit_payload_json: str,
) -> None:
    harness.registry.record_event(
        {
            "event_id": event_id,
            "campaign_id": harness.campaign_id,
            "branch_id": harness.branch.branch_id,
            "hypothesis_id": hypothesis_id,
            "event_kind": "proposal_attempt_transition",
            "stage": stage,
            "audit_payload_json": audit_payload_json,
        }
    )


def _outcome(phase: str) -> ExecutionOutcomeRecord:
    return ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code=(
            "VERIFICATION_LIGHT_REJECTED"
            if phase == "verification"
            else "HYPOTHESIS_CONTRACT_REJECTED"
        ),
        detail="check failed",
        provenance={"owner": "test", "stage": phase},
    )


def _check(name: str) -> tuple[dict[str, object], ...]:
    return (
        {
            "name": name,
            "passed": False,
            "severity": "light",
            "detail": "failed",
            "elapsed_ms": 0,
            "metadata": {},
        },
    )


def test_hypothesis_contract_rejection_commits_one_owner_and_compatible_event(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")

    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="hypothesis_contract",
        outcome=_outcome("hypothesis_contract"),
        checks=_check("H1_schema"),
    )

    assert harness.store.verify_committed(
        result.marker,
        ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
            dict(intent.payload), require_cleanup_receipt=require
        ),
    )
    assert harness.hypothesis_store.get_one(harness.hypothesis.hypothesis_id).status == (
        "research_rejected"
    )
    with sqlite3.connect(harness.registry.db_path) as conn:
        row = conn.execute(
            """
            SELECT event_kind, contract_result, verification_result,
                   canary_result, audit_payload_json
            FROM experiment_events
            WHERE event_id = ?
            """,
            (f"research-rejection-completion:{result.marker.completion_id}",),
        ).fetchone()
    assert row[:4] == ("contract_fail", "failed", "skipped", "skipped")
    audit = json.loads(row[4])
    assert audit["schema"] == "execution-outcome-event.v1"
    assert audit["execution_outcome"]["outcome"] == "research_rejected"
    assert result.archive_ref is None


def test_patch_contract_requires_code_child_and_commits_without_workspace(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )

    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="patch_contract",
        outcome=_outcome("patch_contract"),
        checks=_check("P1_path"),
        patch=patch,
    )

    assert result.marker.provider_attempt_id == "attempt-c"
    assert result.archive_ref is None
    assert harness.store.durable_counts(
        harness.campaign_id,
        archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
            dict(intent.payload)
        ),
    )["by_phase"] == {"patch_contract": 1}


def test_prepare_binds_durable_h_to_canonical_provider_hypothesis_digest(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    with sqlite3.connect(harness.registry.db_path) as conn:
        conn.execute(
            "UPDATE hypotheses SET proposal_digest = ? WHERE hypothesis_id = ?",
            ("b" * 64, harness.hypothesis.hypothesis_id),
        )

    with pytest.raises(RuntimeError, match="hypothesis proposal identity conflict"):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="hypothesis_contract",
            outcome=_outcome("hypothesis_contract"),
            checks=_check("H1_schema"),
        )

    assert harness.store.pending() == []


def test_patch_contract_binds_passed_rejected_patch_to_code_transition(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    generated_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    different_rejected_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 3\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=generated_patch,
    )

    with pytest.raises(RuntimeError, match="rejected patch identity conflict"):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="patch_contract",
            outcome=_outcome("patch_contract"),
            checks=_check("P1_path"),
            patch=different_rejected_patch,
        )

    assert harness.store.pending() == []


def test_unrelated_historical_malformed_transition_does_not_block_rejection(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _record_raw_transition(
        harness,
        event_id="historical-malformed",
        hypothesis_id="historical-hypothesis",
        stage="proposal_hypothesis",
        audit_payload_json="{not-json",
    )
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )

    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="patch_contract",
        outcome=_outcome("patch_contract"),
        checks=_check("P1_path"),
        patch=patch,
    )

    assert result.marker.provider_attempt_id == "attempt-c"


@pytest.mark.parametrize(
    ("claimed_attempt_id", "stage", "audit_payload_json", "error_match"),
    [
        (
            "attempt-c",
            "proposal_code",
            "{not-json",
            "research rejection proposal transition is invalid",
        ),
        (
            "attempt-h",
            "proposal_hypothesis",
            json.dumps({"attempt_id": "attempt-h"}),
            "hypothesis parent transition is invalid",
        ),
    ],
)
def test_malformed_row_claiming_current_attempt_or_parent_fails_closed(
    tmp_path: Path,
    claimed_attempt_id: str,
    stage: str,
    audit_payload_json: str,
    error_match: str,
) -> None:
    harness = _harness(tmp_path)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )
    _record_raw_transition(
        harness,
        event_id=f"malformed-{claimed_attempt_id}",
        hypothesis_id=harness.hypothesis.hypothesis_id,
        stage=stage,
        audit_payload_json=audit_payload_json,
    )

    with pytest.raises(RuntimeError, match=error_match):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="patch_contract",
            outcome=_outcome("patch_contract"),
            checks=_check("P1_path"),
            patch=patch,
        )

    assert harness.store.pending() == []


def test_verification_rejection_archives_exact_candidate_and_cleans_binding(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, durable_workspace=True)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )
    base = harness.lifecycle.branch_workspaces[harness.branch.branch_id]
    applied = harness.lifecycle.apply_candidate_patch(
        harness.branch,
        base,
        patch,
        remember_patch=True,
    )

    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="verification",
        outcome=_outcome("verification"),
        checks=_check("V1b_undefined_names"),
        rejected_candidate_workspace=applied.workspace,
        patch=patch,
    )

    assert not Path(applied.workspace).exists()
    assert harness.lifecycle.pending_candidates == {}
    assert result.archive_ref is not None
    assert (harness.campaign / result.archive_ref).is_dir()
    receipt = harness.campaign / "archive" / (
        f".research-rejection-{result.marker.completion_id}.receipt.json"
    )
    assert receipt.is_file()
    assert harness.branch.current_code_hash == harness.branch.last_clean_code_hash


def test_verification_then_patch_contract_preserves_exact_durable_branch_target(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, durable_workspace=True)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h1")
    first_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    first_ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c1",
        hypothesis_attempt_id="attempt-h1",
        patch=first_patch,
    )
    base = harness.lifecycle.branch_workspaces[harness.branch.branch_id]
    applied = harness.lifecycle.apply_candidate_patch(
        harness.branch,
        base,
        first_patch,
    )
    harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=first_ref,
        rejection_phase="verification",
        outcome=_outcome("verification"),
        checks=_check("V1"),
        rejected_candidate_workspace=applied.workspace,
        patch=first_patch,
    )
    persisted_after_verification = harness.branch_store.load(harness.branch.branch_id)
    assert persisted_after_verification is not None
    assert harness.branch.updated_at == persisted_after_verification.updated_at

    second_proposal = HypothesisProposal(
        hypothesis_text="change operator again",
        change_locus="operator",
        action="modify",
        target_file="operators/op.py",
        target_weakness="operator is still static",
        expected_effect="operator adapts more",
    )
    second_hypothesis = HypothesisRecord(
        hypothesis_id="hypothesis-2",
        branch_id=harness.branch.branch_id,
        change_locus=second_proposal.change_locus,
        action=second_proposal.action,
        status="active",
        target_file=second_proposal.target_file,
        hypothesis_text=second_proposal.hypothesis_text,
        base_champion_version=1,
        proposal_digest=DirectAttemptLifecycle.hypothesis_digest(second_proposal),
    )
    harness.hypothesis_store.save(second_hypothesis)
    harness.hypothesis = second_hypothesis
    second_patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 3\n",
    )
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h2")
    second_ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c2",
        hypothesis_attempt_id="attempt-h2",
        patch=second_patch,
    )

    harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=second_hypothesis,
        proposal_attempt_ref=second_ref,
        rejection_phase="patch_contract",
        outcome=_outcome("patch_contract"),
        checks=_check("P1"),
        patch=second_patch,
    )

    assert harness.store.durable_counts(
        harness.campaign_id,
        archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
            dict(intent.payload)
        ),
    )["by_phase"] == {"verification": 1, "patch_contract": 1}


def test_existing_archive_without_receipt_recovers_exactly_once(tmp_path: Path) -> None:
    harness = _harness(tmp_path, durable_workspace=True)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )
    base = harness.lifecycle.branch_workspaces[harness.branch.branch_id]
    applied = harness.lifecycle.apply_candidate_patch(harness.branch, base, patch)
    source = harness.branch_store.load(harness.branch.branch_id)
    clean = harness.finalizer._clean_parent_identity(source)
    candidate = harness.finalizer._candidate_identity(
        branch_id=harness.branch.branch_id,
        hypothesis_id=harness.hypothesis.hypothesis_id,
        workspace=applied.workspace,
        patch=patch,
    )
    intent = harness.store.prepare(
        campaign_id=harness.campaign_id,
        proposal_attempt_ref=ref,
        branch_id=harness.branch.branch_id,
        hypothesis_id=harness.hypothesis.hypothesis_id,
        rejection_phase="verification",
        reason_code="VERIFICATION_LIGHT_REJECTED",
        failed_check="V1",
        diagnostic_metadata={"proposal": {}},
        clean_code_parent=clean,
        rejected_candidate=candidate,
        rejected_patch_digest=None,
        execution_outcome=_outcome("verification"),
        identity_validator=lambda clean, rejected: harness.materializer.validate_research_rejection_sources(
            branch_id=harness.branch.branch_id,
            clean_parent=dict(clean),
            candidate=dict(rejected) if rejected else None,
        ),
    )
    archive = harness.campaign / str(intent.payload["archive_ref"])
    shutil.copytree(applied.workspace, archive)

    harness.materializer.archive_research_rejection_candidate(dict(intent.payload))
    harness.materializer.archive_research_rejection_candidate(dict(intent.payload))

    receipt = harness.campaign / "archive" / (
        f".research-rejection-{intent.completion_id}.receipt.json"
    )
    assert receipt.is_file()
    assert archive.is_dir()
    assert not Path(applied.workspace).exists()


def test_verification_live_stale_drift_conflicts_without_cleanup(tmp_path: Path) -> None:
    harness = _harness(tmp_path, durable_workspace=True)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )
    base = harness.lifecycle.branch_workspaces[harness.branch.branch_id]
    applied = harness.lifecycle.apply_candidate_patch(harness.branch, base, patch)
    harness.branch.state = BranchState.STALE

    with pytest.raises(RuntimeError, match="owner changed"):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="verification",
            outcome=_outcome("verification"),
            checks=_check("V1"),
            rejected_candidate_workspace=applied.workspace,
            patch=patch,
        )

    assert Path(applied.workspace).is_dir()
    assert harness.store.pending() == []


@pytest.mark.parametrize(
    "fault_phase",
    [
        "after_prepare",
        "before_hypothesis_update",
        "after_hypothesis_update",
        "after_branch_upsert",
        "after_typed_event",
        "before_state_commit",
    ],
)
def test_transaction_fault_reopen_converges_exactly_once(
    tmp_path: Path,
    fault_phase: str,
) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    harness.store.fault_hook = _crash_at(fault_phase)

    with pytest.raises(_Crash, match=fault_phase):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="hypothesis_contract",
            outcome=_outcome("hypothesis_contract"),
            checks=_check("H1_schema"),
        )

    reopened = ResearchRejectionCompletionStore(harness.registry.db_path)
    recovered = reopened.recover_pending(
        cleanup=lambda intent: harness.materializer.archive_research_rejection_candidate(
            dict(intent.payload)
        ),
        ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
            dict(intent.payload), require_cleanup_receipt=require
        ),
    )

    assert len(recovered) == 1
    assert reopened.pending() == []
    counts = reopened.durable_counts(
        harness.campaign_id,
        archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
            dict(intent.payload)
        ),
    )
    assert counts["total"] == 1
    with sqlite3.connect(harness.registry.db_path) as conn:
        event_count = conn.execute(
            "SELECT COUNT(*) FROM experiment_events "
            "WHERE event_kind = 'contract_fail'"
        ).fetchone()[0]
    assert event_count == 1


@pytest.mark.parametrize(
    "fault_phase",
    ["before_cleanup", "after_cleanup", "before_final_mark", "after_final_mark"],
)
def test_cleanup_and_final_mark_faults_reopen_without_provider_replay(
    tmp_path: Path,
    fault_phase: str,
) -> None:
    harness = _harness(tmp_path, durable_workspace=True)
    _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
    )
    ref = _record_attempt(
        harness,
        phase="code",
        attempt_id="attempt-c",
        hypothesis_attempt_id="attempt-h",
        patch=patch,
    )
    base = harness.lifecycle.branch_workspaces[harness.branch.branch_id]
    applied = harness.lifecycle.apply_candidate_patch(harness.branch, base, patch)
    harness.store.fault_hook = _crash_at(fault_phase)

    with pytest.raises(_Crash, match=fault_phase):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="verification",
            outcome=_outcome("verification"),
            checks=_check("V1"),
            rejected_candidate_workspace=applied.workspace,
            patch=patch,
        )

    provider_calls = 0
    reopened = ResearchRejectionCompletionStore(harness.registry.db_path)
    recovered = reopened.recover_pending(
        cleanup=lambda intent: harness.materializer.archive_research_rejection_candidate(
            dict(intent.payload)
        ),
        ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
            dict(intent.payload), require_cleanup_receipt=require
        ),
    )

    assert provider_calls == 0
    assert len(recovered) == (0 if fault_phase == "after_final_mark" else 1)
    assert reopened.pending() == []
    counts = reopened.durable_counts(
        harness.campaign_id,
        archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
            dict(intent.payload)
        ),
    )
    assert counts["total"] == 1
    completion_id = counts["completion_ids"][0]
    assert (
        harness.campaign
        / "archive"
        / f".research-rejection-{completion_id}.receipt.json"
    ).is_file()
    assert not Path(applied.workspace).exists()


def test_prepare_rejects_proposal_anchor_drift_from_durable_branch(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    with sqlite3.connect(harness.registry.db_path) as conn:
        rows = conn.execute(
            "SELECT event_id, audit_payload_json FROM experiment_events "
            "WHERE event_kind = 'proposal_attempt_transition'"
        ).fetchall()
        for event_id, raw_payload in rows:
            payload = json.loads(raw_payload)
            payload["anchors"]["branch_base_champion_hash"] = "wrong-anchor"
            conn.execute(
                "UPDATE experiment_events SET audit_payload_json = ? "
                "WHERE event_id = ?",
                (json.dumps(payload, sort_keys=True), event_id),
            )

    with pytest.raises(RuntimeError, match="branch anchor conflicts"):
        harness.finalizer.finalize(
            branch=harness.branch,
            hypothesis_record=harness.hypothesis,
            proposal_attempt_ref=ref,
            rejection_phase="hypothesis_contract",
            outcome=_outcome("hypothesis_contract"),
            checks=_check("H1_schema"),
        )


def test_committed_verifier_audits_typed_event_columns(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="hypothesis_contract",
        outcome=_outcome("hypothesis_contract"),
        checks=_check("H1_schema"),
    )
    with sqlite3.connect(harness.registry.db_path) as conn:
        conn.execute(
            "UPDATE experiment_events SET contract_result = 'passed' "
            "WHERE event_id = ?",
            (f"research-rejection-completion:{result.marker.completion_id}",),
        )

    with pytest.raises(RuntimeError, match="event identity conflict"):
        harness.store.verify_committed(
            result.marker,
            ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
                dict(intent.payload), require_cleanup_receipt=require
            ),
        )


def test_durable_verifier_rejects_hypothesis_proposal_digest_drift(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="hypothesis_contract",
        outcome=_outcome("hypothesis_contract"),
        checks=_check("H1_schema"),
    )
    with sqlite3.connect(harness.registry.db_path) as conn:
        conn.execute(
            "UPDATE hypotheses SET proposal_digest = ? WHERE hypothesis_id = ?",
            ("b" * 64, harness.hypothesis.hypothesis_id),
        )

    with pytest.raises(RuntimeError, match="hypothesis proposal identity conflict"):
        harness.store.verify_committed(
            result.marker,
            ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
                dict(intent.payload), require_cleanup_receipt=require
            ),
        )
    with pytest.raises(RuntimeError, match="hypothesis proposal identity conflict"):
        harness.store.durable_counts(
            harness.campaign_id,
            archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
                dict(intent.payload)
            ),
        )


def test_historical_counts_ignore_mutable_branch_evolution_but_marker_does_not(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    ref = _record_attempt(harness, phase="hypothesis", attempt_id="attempt-h")
    result = harness.finalizer.finalize(
        branch=harness.branch,
        hypothesis_record=harness.hypothesis,
        proposal_attempt_ref=ref,
        rejection_phase="hypothesis_contract",
        outcome=_outcome("hypothesis_contract"),
        checks=_check("H1_schema"),
    )
    harness.branch.screening_expand_count = 1
    harness.branch_store.save(harness.branch)

    counts = harness.store.durable_counts(
        harness.campaign_id,
        archive_validator=lambda intent: harness.materializer.validate_research_rejection_archive_receipt(
            dict(intent.payload)
        ),
    )

    assert counts["total"] == 1
    with pytest.raises(RuntimeError, match="branch identity conflict"):
        harness.store.verify_committed(
            result.marker,
            ownership_validator=lambda intent, require: harness.materializer.validate_research_rejection_ownership(
                dict(intent.payload), require_cleanup_receipt=require
            ),
        )
