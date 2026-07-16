"""Crash-injection E2E coverage for typed decision completion."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from .campaign_test_support import *  # noqa: F401,F403
from scion.core.decision_completion_transaction import (
    LEGACY_TERMINAL_IDENTITY_SCHEMA,
)


class _NoCallClient:
    def __init__(self) -> None:
        self.calls = 0

    def call(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("startup decision recovery must not call a provider")

    def call_with_tool(self, *args, **kwargs):
        return self.call(*args, **kwargs)


def _reopen(tmp_path: Path, *, protocol=None, client=None) -> CampaignManager:
    shutil.rmtree(tmp_path / "champion_code", ignore_errors=True)
    return CampaignManager(
        problem_spec=_make_problem_spec(str(tmp_path / "champion_code")),
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest(),
        seed_ledger=_make_seed_ledger(),
        llm_client=client or _NoCallClient(),
        champion=_make_champion(str(tmp_path / "champion_code")),
        campaign_dir=str(tmp_path / "campaign"),
        verification_gate=AlwaysPassVerificationGate(),
        experiment_protocol=protocol or MockExperimentProtocol([]),
    )


@pytest.mark.parametrize(
    "fault_phase",
    ["before_hypothesis_update", "after_hypothesis_update"],
)
def test_continue_replays_atomic_branch_and_h_after_h_boundary_crash(
    tmp_path: Path,
    fault_phase: str,
) -> None:
    protocol = MockExperimentProtocol(
        [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
    )
    cm = _campaign(tmp_path, experiment_protocol=protocol)

    def crash(phase, _intent):
        if phase == fault_phase:
            raise OSError(f"crash at {fault_phase}")

    cm._decision_completion_store.fault_hook = crash
    with pytest.raises(OSError, match=fault_phase):
        cm.run_one_step()

    branch = next(iter(cm._branch_ctrl._branches.values()))
    bid = branch.branch_id
    h_id = branch.branch_evidence_summary["verified_candidate_commit"][
        "hypothesis_id"
    ]
    persisted_before = cm._branch_store.load(bid)
    assert persisted_before.branch_evidence_summary["verified_candidate_commit"][
        "evaluation_status"
    ] == "pending"
    assert cm._hyp_store.get_one(h_id).status == "active"
    assert cm._decision_completion_store.pending()

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)

    persisted = reopened._branch_store.load(bid)
    assert persisted.state is BranchState.EXPLORE
    assert persisted.branch_evidence_summary["verified_candidate_commit"][
        "evaluation_status"
    ] == "completed"
    assert reopened._hyp_store.get_one(h_id).status == "rejected"
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0
    assert bid not in reopened._branch_current_hypothesis


def test_continue_state_commit_then_callback_crash_is_startup_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
        ),
    )

    def crash_after_atomic_state(_branch_id):
        raise OSError("crash after atomic decision state")

    monkeypatch.setattr(
        cm._decision_finalizer,
        "persist_branch_state",
        crash_after_atomic_state,
    )
    with pytest.raises(OSError, match="after atomic decision state"):
        cm.run_one_step()

    branch = next(iter(cm._branch_ctrl._branches.values()))
    bid = branch.branch_id
    h_id = branch.branch_evidence_summary["verified_candidate_commit"][
        "hypothesis_id"
    ]
    assert cm._branch_store.load(bid).branch_evidence_summary[
        "verified_candidate_commit"
    ]["evaluation_status"] == "completed"
    assert cm._hyp_store.get_one(h_id).status == "rejected"
    assert cm._decision_completion_store.pending()

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)
    assert reopened._decision_completion_store.pending() == []
    assert reopened._hyp_store.get_one(h_id).status == "rejected"
    assert no_call.calls == 0


@pytest.mark.parametrize(
    ("gate_outcome", "expected_decision", "expected_state", "workspace_survives"),
    (
        (
            "continue",
            Decision.CONTINUE_EXPLORE,
            BranchState.EXPLORE,
            True,
        ),
        (
            "fail",
            Decision.ABANDON,
            BranchState.ABANDONED,
            False,
        ),
    ),
)
def test_validation_terminal_decision_recovers_atomically_before_protocol(
    tmp_path: Path,
    gate_outcome: str,
    expected_decision: Decision,
    expected_state: BranchState,
    workspace_survives: bool,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="pass",
                ),
                _make_protocol_result(
                    ExperimentStage.VALIDATION,
                    gate_outcome=gate_outcome,
                ),
            ]
        ),
    )
    screening = cm.run_one_step()
    assert screening.decision is Decision.QUEUE_VALIDATE
    bid = screening.branch_id
    workspace = Path(cm._branch_workspaces[bid])
    h_id = cm._branch_ctrl.get_branch(bid).branch_evidence_summary[
        "verified_candidate_commit"
    ]["hypothesis_id"]

    def crash(phase, _intent):
        if phase == "before_state_commit":
            raise OSError("crash before validation terminal commit")

    cm._decision_completion_store.fault_hook = crash
    with pytest.raises(OSError, match="validation terminal commit"):
        cm.run_one_step()

    persisted_before = cm._branch_store.load(bid)
    assert persisted_before.state is BranchState.VALIDATING
    assert cm._hyp_store.get_one(h_id).status == "active"
    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    assert pending[0].decision is expected_decision
    assert workspace.is_dir()

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)

    assert reopened._branch_store.load(bid).state is expected_state
    assert reopened._hyp_store.get_one(h_id).status == "rejected"
    assert workspace.exists() is workspace_survives
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0


def test_legacy_validation_terminal_decision_binds_h_and_branch_identity(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="pass",
                ),
                _make_protocol_result(
                    ExperimentStage.VALIDATION,
                    gate_outcome="continue",
                ),
            ]
        ),
    )
    screening = cm.run_one_step()
    assert screening.decision is Decision.QUEUE_VALIDATE
    bid = screening.branch_id
    branch = cm._branch_ctrl.get_branch(bid)
    marker = branch.branch_evidence_summary.pop("verified_candidate_commit")
    h_id = marker["hypothesis_id"]
    legacy_artifact = branch.branch_evidence_summary[
        "formal_candidate_patch_artifact_ref"
    ]
    assert (tmp_path / "campaign" / legacy_artifact).is_file()
    cm._branch_store.save(branch)

    # Exercise the real legacy restore boundary: no typed commit exists, so
    # reopen must strictly validate the formal candidate artifact and rebuild
    # the active H/P ownership before the validation terminal decision.
    no_call = _NoCallClient()
    resumed = _reopen(
        tmp_path,
        client=no_call,
        protocol=MockExperimentProtocol(
            [
                _make_protocol_result(
                    ExperimentStage.VALIDATION,
                    gate_outcome="continue",
                )
            ]
        ),
    )
    assert bid in resumed._branch_patches
    assert resumed._branch_current_hypothesis[bid].hypothesis_id == h_id

    def crash(phase, _intent):
        if phase == "before_state_commit":
            raise OSError("crash before legacy terminal commit")

    resumed._decision_completion_store.fault_hook = crash
    with pytest.raises(OSError, match="legacy terminal commit"):
        resumed.run_one_step()

    pending = resumed._decision_completion_store.pending()
    assert len(pending) == 1
    identity = pending[0].payload["verified_candidate_identity"]
    assert identity["schema_version"] == LEGACY_TERMINAL_IDENTITY_SCHEMA
    assert identity["hypothesis_id"] == h_id
    assert identity["lineage_id"] == (branch.lineage_id or bid)
    assert identity["current_code_hash"] == branch.current_code_hash
    assert identity["last_clean_code_hash"] == branch.last_clean_code_hash
    assert identity["canonical_hypothesis_sha256"]
    assert resumed._branch_store.load(bid).state is BranchState.VALIDATING
    assert resumed._hyp_store.get_one(h_id).status == "active"

    recovery_client = _NoCallClient()
    reopened = _reopen(tmp_path, client=recovery_client)

    assert reopened._branch_store.load(bid).state is BranchState.EXPLORE
    assert reopened._hyp_store.get_one(h_id).status == "rejected"
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0
    assert recovery_client.calls == 0


def test_typed_lineage_fault_rolls_back_then_recovers_exactly_once(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
        ),
    )

    def crash(phase, _intent):
        if phase == "after_typed_lineage":
            raise OSError("crash after typed lineage")

    cm._decision_completion_store.fault_hook = crash
    with pytest.raises(OSError, match="after typed lineage"):
        cm.run_one_step()

    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    intent = pending[0]
    assert cm._branch_store.load(intent.branch_id).branch_evidence_summary[
        "verified_candidate_commit"
    ]["evaluation_status"] == "pending"
    assert cm._hyp_store.get_one(intent.hypothesis_id).status == "active"
    with sqlite3.connect(cm._registry.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiment_events WHERE event_id = ?",
            (f"decision-completion:{intent.transaction_id}",),
        ).fetchone()[0] == 0

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)

    target = intent.payload["target_branch"]
    persisted = reopened._branch_store.load(intent.branch_id)
    assert persisted.state.value == target["state"]
    assert persisted.branch_evidence_summary == target["branch_evidence_summary"]
    assert reopened._hyp_store.get_one(intent.hypothesis_id).status == "rejected"
    with sqlite3.connect(reopened._registry.db_path) as conn:
        rows = conn.execute(
            """
            SELECT event_kind, decision, audit_payload_json
            FROM experiment_events WHERE event_id = ?
            """,
            (f"decision-completion:{intent.transaction_id}",),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0:2] == ("decision_completion", intent.decision.value)
    assert json.loads(rows[0][2])["transaction_id"] == intent.transaction_id
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0


def test_prepare_then_rich_lineage_crash_recovers_typed_lineage_before_restore(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
        ),
    )

    def crash_before_rich_lineage(*_args, **_kwargs):
        raise OSError("rich lineage unavailable after prepare")

    monkeypatch.setattr(
        cm._decision_finalizer,
        "record_step_lineage",
        crash_before_rich_lineage,
    )
    with pytest.raises(OSError, match="rich lineage unavailable"):
        cm.run_one_step()

    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    intent = pending[0]
    persisted_before = cm._branch_store.load(intent.branch_id)
    assert persisted_before.branch_evidence_summary["verified_candidate_commit"][
        "evaluation_status"
    ] == "pending"
    assert cm._hyp_store.get_one(intent.hypothesis_id).status == "active"

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)

    assert reopened._decision_completion_store.pending() == []
    assert reopened._hyp_store.get_one(intent.hypothesis_id).status == "rejected"
    with sqlite3.connect(reopened._registry.db_path) as conn:
        rows = conn.execute(
            """
            SELECT branch_id, hypothesis_id, decision, stage, audit_payload_json
            FROM experiment_events
            WHERE event_id = ? AND event_kind = 'decision_completion'
            """,
            (f"decision-completion:{intent.transaction_id}",),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][:4] == (
        intent.branch_id,
        intent.hypothesis_id,
        Decision.CONTINUE_EXPLORE.value,
        ExperimentStage.SCREENING.value,
    )
    audit = json.loads(rows[0][4])
    assert audit["protocol_identity"] == intent.payload["protocol_identity"]
    assert audit["verified_candidate_identity"] == intent.payload[
        "verified_candidate_identity"
    ]
    assert audit["decision"] == Decision.CONTINUE_EXPLORE.value
    assert audit["reason_codes"] == intent.payload["reason_codes"]
    assert audit["intent_ref"]["transaction_id"] == intent.transaction_id
    canonical = reopened._branch_store.load(intent.branch_id).branch_evidence_summary[
        "canonical_screening_history"
    ]
    assert canonical
    assert canonical == audit["target_branch"]["canonical_screening_history"]
    assert canonical[-1]["experiment_evidence"]["protocol_outcome"][
        "gate_outcome"
    ] == "fail"
    assert no_call.calls == 0


def test_abandon_cleanup_failure_replays_before_branch_restore(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING)],
            canary_pass=False,
        ),
    )

    def fail_cleanup(_workspace):
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(cm._materializer, "cleanup", fail_cleanup)
    with pytest.raises(OSError, match="cleanup unavailable"):
        cm.run_one_step()

    branch = next(iter(cm._branch_ctrl._branches.values()))
    bid = branch.branch_id
    h_id = branch.branch_evidence_summary["verified_candidate_commit"][
        "hypothesis_id"
    ]
    workspace = Path(cm._branch_workspaces[bid])
    assert cm._branch_store.load(bid).state is BranchState.ABANDONED
    assert cm._hyp_store.get_one(h_id).status == "rejected"
    assert workspace.is_dir()
    assert cm._decision_completion_store.pending()
    archives = list((tmp_path / "campaign" / "archive").glob("*decision*"))
    assert len(archives) == 1

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)
    assert reopened._branch_store.load(bid).state is BranchState.ABANDONED
    assert reopened._hyp_store.get_one(h_id).status == "rejected"
    assert not workspace.exists()
    assert reopened._decision_completion_store.pending() == []
    assert list((tmp_path / "campaign" / "archive").glob("*decision*")) == archives
    assert no_call.calls == 0
    assert bid not in reopened._branch_ctrl._branches


def test_abandon_recovery_rejects_tampered_workspace_before_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING)],
            canary_pass=False,
        ),
    )

    def fail_archive(*_args, **_kwargs):
        raise OSError("archive interrupted")

    monkeypatch.setattr(
        cm._materializer,
        "archive_decision_workspace",
        fail_archive,
    )
    with pytest.raises(OSError, match="archive interrupted"):
        cm.run_one_step()

    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    intent = pending[0]
    workspace = tmp_path / "campaign" / "workspaces" / intent.branch_id
    editable = workspace / "operators" / "local_search.py"
    editable.write_text(editable.read_text() + "\n# tampered after decision\n")

    no_call = _NoCallClient()
    with pytest.raises(RuntimeError, match="decision workspace code identity conflict"):
        _reopen(tmp_path, client=no_call)

    assert workspace.is_dir()
    assert cm._decision_completion_store.pending()
    assert no_call.calls == 0


def test_abandon_receipt_recovers_after_partial_workspace_removal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(
            [_make_protocol_result(ExperimentStage.SCREENING)],
            canary_pass=False,
        ),
    )

    def partial_cleanup(workspace: str) -> None:
        editable = Path(workspace) / "operators" / "local_search.py"
        editable.unlink()
        raise OSError("crash during recursive cleanup")

    monkeypatch.setattr(cm._materializer, "cleanup", partial_cleanup)
    with pytest.raises(OSError, match="recursive cleanup"):
        cm.run_one_step()

    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    intent = pending[0]
    workspace = tmp_path / "campaign" / "workspaces" / intent.branch_id
    assert workspace.is_dir()
    assert not (workspace / "operators" / "local_search.py").exists()
    receipts = list((tmp_path / "campaign" / "archive").glob(".*.receipt.json"))
    archives = list((tmp_path / "campaign" / "archive").glob("*decision*"))
    assert len(receipts) == len(archives) == 1

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)

    assert not workspace.exists()
    assert reopened._decision_completion_store.pending() == []
    assert list((tmp_path / "campaign" / "archive").glob(".*.receipt.json")) == receipts
    assert list((tmp_path / "campaign" / "archive").glob("*decision*")) == archives
    assert no_call.calls == 0


def test_retained_transition_replays_before_protocol_or_provider(
    tmp_path: Path,
) -> None:
    protocol = MockExperimentProtocol(
        [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")]
    )
    cm = _campaign(tmp_path, experiment_protocol=protocol)

    def crash(phase, _intent):
        if phase == "before_state_commit":
            raise OSError("crash before retained state commit")

    cm._decision_completion_store.fault_hook = crash
    with pytest.raises(OSError, match="retained state commit"):
        cm.run_one_step()

    branch = next(iter(cm._branch_ctrl._branches.values()))
    bid = branch.branch_id
    assert cm._branch_store.load(bid).state is BranchState.EXPLORE
    pending = cm._decision_completion_store.pending()
    assert len(pending) == 1
    with sqlite3.connect(cm._registry.db_path) as conn:
        rich_audit = conn.execute(
            """
            SELECT audit_payload_json FROM experiment_events
            WHERE event_id = ? AND event_kind = 'experiment'
            """,
            (pending[0].transaction_id,),
        ).fetchone()
    assert rich_audit is not None
    assert json.loads(rich_audit[0])["lineage_metadata"]["branch_state"] == (
        BranchState.EXPLORE.value
    )

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)
    restored = reopened._branch_store.load(bid)
    assert restored.state is BranchState.READY_VALIDATE
    assert restored.branch_evidence_summary["verified_candidate_commit"][
        "evaluation_status"
    ] == "completed"
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0


def test_promote_persist_then_callback_crash_reopens_committed_champion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())
    screening = cm.run_one_step()
    assert screening.decision is Decision.QUEUE_VALIDATE
    with sqlite3.connect(cm._registry.db_path) as conn:
        intent_count_after_screening = conn.execute(
            "SELECT COUNT(*) FROM decision_completion_intents"
        ).fetchone()[0]
    assert intent_count_after_screening == 1
    validation = cm.run_one_step()
    assert validation.decision is Decision.QUEUE_FROZEN
    with sqlite3.connect(cm._registry.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM decision_completion_intents"
        ).fetchone()[0] == intent_count_after_screening

    def persist_then_crash(branch_id):
        cm._branch_store.save(cm._branch_ctrl.get_branch(branch_id))
        raise OSError("crash after promoted branch persistence")

    monkeypatch.setattr(
        cm._decision_finalizer,
        "persist_branch_state",
        persist_then_crash,
    )
    with pytest.raises(OSError, match="promoted branch persistence"):
        cm.run_one_step()

    bid = screening.branch_id
    assert cm._champion_store.get_current().version == 2
    assert cm._branch_store.load(bid).state is BranchState.PROMOTED
    with sqlite3.connect(cm._registry.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM decision_completion_intents"
        ).fetchone()[0] == intent_count_after_screening

    no_call = _NoCallClient()
    reopened = _reopen(tmp_path, client=no_call)
    assert reopened._champion.version == 2
    assert reopened._branch_store.load(bid).state is BranchState.PROMOTED
    assert reopened._decision_completion_store.pending() == []
    assert no_call.calls == 0
