from __future__ import annotations

import base64
import dataclasses
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from scion.core.candidate_snapshot import (
    CandidateCodeParent,
    CandidateCodeParentKind,
    CandidateOriginKind,
    CandidateSnapshotError,
    CandidateSnapshotRequest,
    CandidateSnapshotTamperError,
    candidate_snapshot_closure_bytes,
    materialize_candidate_snapshot_closure,
)
from scion.core.candidate_snapshot_store import (
    CandidateOwnershipMode,
    CandidateSnapshotConflictError,
    CandidateSnapshotModeError,
    CandidateSnapshotStore,
)
from scion.tests.unit.core.test_candidate_snapshot import Harness, _harness
from scion.core.models import PatchProposal


class SimulatedCrash(RuntimeError):
    pass


def _store(
    harness: Harness,
    *,
    fault_phase: str | None = None,
) -> CandidateSnapshotStore:
    def fault(phase, _record) -> None:
        if phase == fault_phase:
            raise SimulatedCrash(phase)

    return CandidateSnapshotStore(
        harness.campaign / "campaign.sqlite3",
        campaign_root=harness.campaign,
        identity_manifest_for=harness.materializer.editable_identity_manifest,
        fault_hook=fault if fault_phase is not None else None,
    )


def _request(harness: Harness, **overrides: object) -> CandidateSnapshotRequest:
    values: dict[str, object] = {
        "campaign_id": "campaign-1",
        "origin_kind": CandidateOriginKind.DIRECT_CODE_ATTEMPT,
        "origin_id": "attempt-1",
        "branch_id": "branch-1",
        "lineage_id": "lineage-1",
        "parent_workspace": str(harness.parent),
        "candidate_workspace": str(harness.candidate),
        "code_parent": harness.code_parent,
        "base_champion_id": "1",
        "base_champion_hash": harness.code_parent.executable_snapshot_hash,
        "evidence_parent_hypothesis_id": None,
        "hypothesis_id": "hypothesis-1",
        "mechanism_owner_id": "unclassified",
        "patch": harness.patch,
        "verification_result": harness.verification,
    }
    values.update(overrides)
    return CandidateSnapshotRequest(**values)  # type: ignore[arg-type]


def _claimed_store(
    harness: Harness,
    *,
    fault_phase: str | None = None,
) -> CandidateSnapshotStore:
    store = _store(harness, fault_phase=fault_phase)
    store.claim_ownership_mode(
        "campaign-1",
        CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
    )
    return store


def test_mode_is_explicit_durable_and_exclusive_not_artifact_inferred(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    artifact_directory = harness.campaign / "candidate_snapshots"
    artifact_directory.mkdir()
    (artifact_directory / "legacy-looking.json").write_text("{}\n")
    store = _store(harness)

    with pytest.raises(CandidateSnapshotModeError, match="claimed"):
        store.record(_request(harness))
    assert (
        store.claim_ownership_mode(
            "campaign-1",
            CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
        )
        is CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1
    )
    assert (
        store.claim_ownership_mode(
            "campaign-1",
            CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
        )
        is CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1
    )

    with pytest.raises(CandidateSnapshotModeError, match="incompatible"):
        store.claim_ownership_mode(
            "campaign-1",
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
        )
    with pytest.raises(CandidateSnapshotModeError, match="requested owner"):
        store.record(_request(harness))
    with pytest.raises(CandidateSnapshotModeError, match="incompatible"):
        store.claim_ownership_mode(
            "another-campaign",
            CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1,
        )


def test_same_origin_same_payload_is_idempotent_and_drift_conflicts(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    closure = harness.build()

    first = store.record(_request(harness))
    second = store.record(_request(harness))

    assert first == second
    assert first.status == "committed"
    assert len(first.candidate_id) == 64
    assert first.candidate_id == first.identity_sha256
    assert (
        store.load_for_origin(
            "campaign-1",
            closure.snapshot.origin_kind,
            "attempt-1",
        )
        == first
    )
    assert store.verify(first.candidate_id) == closure

    noisy_check = dataclasses.replace(
        harness.verification.checks[0],
        elapsed_ms=999,
        detail="same result from another runtime",
        metadata={"workspace": "/tmp/other-run"},
    )
    noisy_verification = dataclasses.replace(
        harness.verification,
        checks=(noisy_check,),
    )
    artifact_drift = harness.build(verification_result=noisy_verification)
    assert artifact_drift.snapshot.candidate_id == first.candidate_id
    with pytest.raises(CandidateSnapshotConflictError, match="different payload"):
        store.record(_request(harness, verification_result=noisy_verification))

    drift = harness.build(lineage_id="lineage-drift")
    with pytest.raises(CandidateSnapshotConflictError, match="different payload"):
        store.record(_request(harness, lineage_id="lineage-drift"))
    assert (
        store.load_for_origin(
            "campaign-1",
            closure.snapshot.origin_kind,
            "attempt-1",
        )
        == first
    )


def test_record_rejects_closure_and_authoritative_reread_drift(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    calls: dict[str, int] = {}

    def provider(workspace: str):
        calls[workspace] = calls.get(workspace, 0) + 1
        if workspace == str(harness.candidate) and calls[workspace] == 2:
            (harness.candidate / "operators" / "op.py").write_text(
                "VALUE = 999\n", encoding="utf-8"
            )
        return harness.materializer.editable_identity_manifest(workspace)

    store = CandidateSnapshotStore(
        harness.campaign / "campaign.sqlite3",
        campaign_root=harness.campaign,
        identity_manifest_for=provider,
    )
    store.claim_ownership_mode(
        "campaign-1", CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
    )
    with pytest.raises(TypeError, match="typed request"):
        store.record(harness.build())  # type: ignore[arg-type]
    with pytest.raises(CandidateSnapshotTamperError, match="drifted"):
        store.record(_request(harness))
    assert store.pending() == ()
    assert not (harness.campaign / "candidate_snapshots").exists()
    assert calls == {str(harness.parent): 2, str(harness.candidate): 2}

    (harness.candidate / "operators" / "op.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    assert store.record(_request(harness)).status == "committed"
    assert calls == {str(harness.parent): 5, str(harness.candidate): 5}


def test_descendant_verification_pins_ancestor_registry_digest(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    parent_closure = harness.build()
    parent_record = store.record(_request(harness))
    parent_workspace = harness.campaign / "workspaces" / "candidate-parent"
    materialize_candidate_snapshot_closure(
        parent_closure,
        campaign_root=harness.campaign,
        destination=parent_workspace,
        ancestor_resolver=store.resolve_ancestor_artifact,
    )
    child_workspace = (
        harness.campaign / "candidate_workspaces" / "branch-1" / "attempt-2"
    )
    shutil.copytree(parent_workspace, child_workspace)
    (child_workspace / "operators" / "op.py").write_text(
        "VALUE = 3\n", encoding="utf-8"
    )
    candidate_parent = CandidateCodeParent(
        CandidateCodeParentKind.CANDIDATE,
        parent_record.candidate_id,
        parent_closure.snapshot.candidate_code_hash,
        parent_closure.snapshot.executable_snapshot_hash,
        parent_record.artifact_ref,
    )
    child = store.record(
        _request(
            harness,
            origin_id="attempt-2",
            hypothesis_id="hypothesis-2",
            parent_workspace=str(parent_workspace),
            candidate_workspace=str(child_workspace),
            code_parent=candidate_parent,
            patch=PatchProposal("operators/op.py", "modify", "VALUE = 3\n"),
        )
    )
    noisy = harness.build(
        verification_result=dataclasses.replace(
            harness.verification,
            checks=(
                dataclasses.replace(
                    harness.verification.checks[0],
                    detail="diagnostic-only drift",
                    elapsed_ms=99,
                ),
            ),
        )
    )
    assert noisy.snapshot.candidate_id == parent_record.candidate_id
    (harness.campaign / parent_record.artifact_ref).write_bytes(
        candidate_snapshot_closure_bytes(noisy)
    )
    with pytest.raises(CandidateSnapshotTamperError, match="hash"):
        store.verify(child.candidate_id)


def test_registry_is_append_only_and_contains_no_closure_payload(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    store = _claimed_store(harness)
    record = store.record(_request(harness))
    assert store.record(_request(harness)) == record

    artifacts = tuple((harness.campaign / "candidate_snapshots").glob("*.json"))
    assert artifacts == (harness.campaign / record.artifact_ref,)
    changed_content = next(item.content for item in closure.delta if item.content)
    encoded_content = base64.b64encode(changed_content).decode()
    assert artifacts[0].read_text().count(encoded_content) == 1

    with sqlite3.connect(store.db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(candidate_snapshots)")
        }
        assert not any(
            token in column
            for column in columns
            for token in ("payload", "bytes", "json", "closure")
        )
        assert conn.execute("SELECT COUNT(*) FROM candidate_snapshots").fetchone() == (
            1,
        )
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {"candidate_ownership_mode", "candidate_snapshots"}
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "DELETE FROM candidate_snapshots WHERE candidate_id = ?",
                (record.candidate_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "UPDATE candidate_snapshots SET artifact_sha256 = ? "
                "WHERE candidate_id = ?",
                ("0" * 64, record.candidate_id),
            )


def test_load_verify_fails_closed_on_artifact_tamper(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    record = store.record(_request(harness))
    artifact = harness.campaign / record.artifact_ref
    artifact.write_bytes(artifact.read_bytes() + b"tamper")

    assert store.load(record.candidate_id) == record
    with pytest.raises(CandidateSnapshotTamperError, match="hash"):
        store.verify(record.candidate_id)


def test_store_rejects_root_and_artifact_symlink_traversal(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    linked_root = tmp_path / "linked-campaign"
    linked_root.symlink_to(harness.campaign, target_is_directory=True)
    with pytest.raises(CandidateSnapshotError, match="symlink"):
        CandidateSnapshotStore(
            tmp_path / "linked.sqlite3",
            campaign_root=linked_root,
            identity_manifest_for=harness.materializer.editable_identity_manifest,
        )

    store = _claimed_store(harness)
    outside = tmp_path / "outside"
    outside.mkdir()
    snapshot_directory = harness.campaign / "candidate_snapshots"
    snapshot_directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(CandidateSnapshotTamperError, match="symlink"):
        store.record(_request(harness))


def test_verify_rejects_committed_artifact_symlink(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    record = store.record(_request(harness))
    artifact = harness.campaign / record.artifact_ref
    outside = tmp_path / "outside.json"
    outside.write_bytes(artifact.read_bytes())
    artifact.unlink()
    artifact.symlink_to(outside)

    with pytest.raises(CandidateSnapshotTamperError, match="symlink"):
        store.verify(record.candidate_id)


def test_verify_reads_from_pinned_directory_fd_during_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    record = store.record(_request(harness))
    public = harness.campaign / "candidate_snapshots"
    pinned = harness.campaign / "pinned-candidate-snapshots"
    outside = tmp_path / "outside-snapshots"
    outside.mkdir()
    final_name = f"{record.candidate_id}.json"
    (outside / final_name).write_bytes((public / final_name).read_bytes())
    real_open = os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == final_name and dir_fd is not None and not swapped:
            swapped = True
            public.rename(pinned)
            public.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", racing_open)
    with pytest.raises(CandidateSnapshotTamperError, match="canonical"):
        store.verify(record.candidate_id)
    assert swapped


def test_publish_renames_within_pinned_directory_fd_during_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    store = _claimed_store(harness)
    public = harness.campaign / "candidate_snapshots"
    pinned = harness.campaign / "pinned-candidate-snapshots"
    outside = tmp_path / "outside-snapshots"
    outside.mkdir()
    real_rename = os.rename
    swapped = False

    def racing_rename(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
        nonlocal swapped
        if src_dir_fd is not None and dst_dir_fd is not None and not swapped:
            swapped = True
            real_rename(public, pinned)
            public.symlink_to(outside, target_is_directory=True)
        return real_rename(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "rename", racing_rename)
    with pytest.raises(CandidateSnapshotTamperError, match="canonical"):
        store.record(_request(harness))
    pending = store.pending()
    assert len(pending) == 1 and pending[0].status == "prepared"
    record = pending[0]
    final_name = f"{record.candidate_id}.json"
    assert swapped
    assert (pinned / final_name).is_file()
    assert not (outside / final_name).exists()
    assert public.is_symlink()
    recovery = store.recover_pending()
    assert recovery.recovered_candidate_ids == ()
    assert recovery.held_candidate_ids == (record.candidate_id,)


def test_publish_does_not_commit_after_campaign_root_path_swap(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    public_root = harness.campaign
    pinned_root = tmp_path / "pinned-campaign-root"
    outside_root = tmp_path / "outside-campaign-root"
    outside_root.mkdir()
    swapped = False

    def fault(phase, _record) -> None:
        nonlocal swapped
        if phase == "before_registry_commit" and not swapped:
            swapped = True
            public_root.rename(pinned_root)
            public_root.symlink_to(outside_root, target_is_directory=True)

    store = CandidateSnapshotStore(
        tmp_path / "external-state.sqlite3",
        campaign_root=public_root,
        identity_manifest_for=harness.materializer.editable_identity_manifest,
        fault_hook=fault,
    )
    store.claim_ownership_mode(
        "campaign-1", CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
    )
    with pytest.raises(CandidateSnapshotTamperError, match="canonical"):
        store.record(_request(harness))

    pending = store.pending()
    assert swapped
    assert len(pending) == 1 and pending[0].status == "prepared"
    final_name = f"{pending[0].candidate_id}.json"
    assert (pinned_root / "candidate_snapshots" / final_name).is_file()
    assert not (outside_root / "candidate_snapshots" / final_name).exists()
    recovery = store.recover_pending()
    assert recovery.recovered_candidate_ids == ()
    assert recovery.held_candidate_ids == (pending[0].candidate_id,)


def test_explicit_retry_may_relocate_same_payload_workspace_after_prepare_crash(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    crashing = _claimed_store(harness, fault_phase="after_prepare")
    with pytest.raises(SimulatedCrash, match="after_prepare"):
        crashing.record(_request(harness))

    relocated = harness.candidate.with_name("attempt-1-relocated")
    shutil.copytree(harness.candidate, relocated)
    shutil.rmtree(harness.candidate)
    resumed = _store(harness)
    record = resumed.record(_request(harness, candidate_workspace=str(relocated)))

    assert record.candidate_id == closure.snapshot.candidate_id
    assert record.status == "committed"
    assert resumed.verify(record.candidate_id) == closure
    assert record.candidate_workspace_ref.endswith("attempt-1")


@pytest.mark.parametrize(
    "phase",
    (
        "after_temp_fsync",
        "after_artifact_rename",
        "before_registry_commit",
    ),
)
def test_recovery_converges_each_precommit_crash_phase(
    tmp_path: Path,
    phase: str,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    crashing = _claimed_store(harness, fault_phase=phase)
    with pytest.raises(SimulatedCrash, match=phase):
        crashing.record(_request(harness))

    prepared = crashing.load(closure.snapshot.candidate_id)
    assert prepared is not None and prepared.status == "prepared"
    recovered_store = _store(harness)
    report = recovered_store.recover_pending()

    assert report.recovered_candidate_ids == (closure.snapshot.candidate_id,)
    assert report.held_candidate_ids == ()
    assert recovered_store.verify(closure.snapshot.candidate_id) == closure
    assert not tuple((harness.campaign / "candidate_snapshots").glob(".*.tmp"))


def test_crash_after_registry_commit_is_already_durable(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    crashing = _claimed_store(harness, fault_phase="after_registry_commit")
    with pytest.raises(SimulatedCrash, match="after_registry_commit"):
        crashing.record(_request(harness))

    committed = crashing.load(closure.snapshot.candidate_id)
    assert committed is not None and committed.status == "committed"
    recovered_store = _store(harness)
    assert recovered_store.recover_pending().recovered_candidate_ids == ()
    assert recovered_store.verify(closure.snapshot.candidate_id) == closure


def test_missing_prepared_artifact_is_held_until_same_payload_is_retried(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    crashing = _claimed_store(harness, fault_phase="after_prepare")
    with pytest.raises(SimulatedCrash, match="after_prepare"):
        crashing.record(_request(harness))

    recovered_store = _store(harness)
    report = recovered_store.recover_pending()
    assert report.recovered_candidate_ids == ()
    assert report.held_candidate_ids == (closure.snapshot.candidate_id,)
    prepared = recovered_store.load(closure.snapshot.candidate_id)
    assert prepared is not None and prepared.status == "prepared"

    assert recovered_store.record(_request(harness)).status == "committed"


@pytest.mark.parametrize("phase", ("after_temp_fsync", "after_artifact_rename"))
def test_tampered_pending_temp_or_final_is_held(
    tmp_path: Path,
    phase: str,
) -> None:
    harness = _harness(tmp_path)
    closure = harness.build()
    crashing = _claimed_store(harness, fault_phase=phase)
    with pytest.raises(SimulatedCrash, match=phase):
        crashing.record(_request(harness))

    directory = harness.campaign / "candidate_snapshots"
    if phase == "after_temp_fsync":
        target = next(directory.glob(".*.tmp"))
    else:
        target = harness.campaign / closure.snapshot.candidate_snapshot_ref
    target.write_bytes(b"tampered")

    recovered_store = _store(harness)
    report = recovered_store.recover_pending()
    assert report.recovered_candidate_ids == ()
    assert report.held_candidate_ids == (closure.snapshot.candidate_id,)
    prepared = recovered_store.load(closure.snapshot.candidate_id)
    assert prepared is not None and prepared.status == "prepared"


def test_formal_tables_and_counts_do_not_define_snapshot_namespace(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    store = _store(harness)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("CREATE TABLE formal_candidate_index (candidate_id INTEGER)")
        conn.execute("CREATE TABLE events (event_id INTEGER)")
        conn.executemany(
            "INSERT INTO formal_candidate_index VALUES (?)",
            ((1,), (2,), (2**63 - 1,)),
        )
        conn.executemany("INSERT INTO events VALUES (?)", ((1,), (999999,)))
    store.claim_ownership_mode(
        "campaign-1",
        CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
    )

    closure = harness.build()
    record = store.record(_request(harness))
    assert record.candidate_id == closure.snapshot.candidate_id
    assert len(record.candidate_id) == 64
    assert record.candidate_id != "1"
