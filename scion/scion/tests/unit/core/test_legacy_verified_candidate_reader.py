from __future__ import annotations

import copy
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.campaign_open import (
    CampaignOpenKind,
    CampaignOpenRequest,
    CampaignOwnershipStore,
)
from scion.core.models import (
    Branch,
    BranchState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.core.verified_candidate_commit import (
    LegacyVerifiedCandidateReader,
    VerifiedCandidateCommitRecorder,
)
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry


class _IdentityMaterializer:
    @staticmethod
    def _content(workspace: str) -> bytes:
        return (Path(workspace) / "operators" / "op.py").read_bytes()

    def compute_code_hash(self, workspace: str) -> str:
        return hashlib.sha256(self._content(workspace)).hexdigest()

    def compute_snapshot_hash(self, workspace: str) -> str:
        return hashlib.sha256(b"snapshot\0" + self._content(workspace)).hexdigest()


def _owned_candidate(tmp_path: Path):
    campaign = tmp_path / "campaign"
    workspace = campaign / "workspaces" / "branch-1"
    source = workspace / "operators" / "op.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    materializer = _IdentityMaterializer()
    code_hash = materializer.compute_code_hash(str(workspace))
    branch = Branch(
        branch_id="branch-1",
        state=BranchState.READY_VALIDATE,
        base_champion_id=1,
        base_champion_hash="base-code-hash",
        lineage_id="lineage-1",
        current_code_hash=code_hash,
        last_clean_code_hash=code_hash,
        screening_expand_count=2,
        validation_expand_count=1,
        failure_codes=["prior_failure"],
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        updated_at=datetime(2026, 1, 2, 3, 4, 6),
        direction="local_search: exact owner",
        weight_revision=3,
        infra_block_count=4,
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the operator implementation.",
        change_locus="local_search",
        action="modify",
        target_file="operators/op.py",
        predicted_direction="improve",
        suggested_weight=0.25,
    )
    h_record = HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id=branch.branch_id,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        status="active",
        target_file=hypothesis.target_file,
        parent_hypothesis_id="hypothesis-parent",
        suggested_weight=hypothesis.suggested_weight,
        hypothesis_text=hypothesis.hypothesis_text,
        family_id="local-search",
        family_source="classifier",
        taxonomy_version="v1",
        created_at=datetime(2026, 1, 2, 3, 4, 7),
        base_champion_version=1,
        predicted_direction=hypothesis.predicted_direction,
        proposal_digest="a" * 64,
    )
    patch = PatchProposal(
        file_path="operators/op.py",
        action="modify",
        code_content="VALUE = 2\n",
        test_hint="unit",
    )
    recorder = VerifiedCandidateCommitRecorder(campaign)
    recorder.record(
        branch=branch,
        hypothesis=hypothesis,
        h_record=h_record,
        patch=patch,
        workspace=str(workspace),
        base_code_hash="base-code-hash",
        materializer=materializer,
    )
    recorder.mark_promotion_committed(branch)
    db_path = campaign / "scion.db"
    registry = LineageRegistry(str(db_path))
    BranchStore(registry).save(branch)
    HypothesisStore(registry).save(h_record)
    CampaignOwnershipStore(db_path).open(
        CampaignOpenRequest(CampaignOpenKind.REOPEN, "campaign-1")
    )
    return campaign, workspace, branch, h_record, materializer


def _tree_state(root: Path) -> dict[str, tuple[object, ...]]:
    state: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*")):
        if path.name in {"scion.db", "scion.db-wal", "scion.db-shm"}:
            continue
        stat = path.stat()
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            state[relative] = (
                "file",
                stat.st_mode,
                stat.st_size,
                stat.st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        else:
            state[relative] = ("directory", stat.st_mode, stat.st_mtime_ns)
    return state


def _database_state(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as conn:
        return tuple(conn.iterdump())


def test_legacy_reader_has_no_write_api_and_reuses_recorder_validation() -> None:
    reader = LegacyVerifiedCandidateReader(".", campaign_id="campaign-1")

    assert not hasattr(reader, "record")
    assert not hasattr(reader, "mark_promotion_committed")
    assert not hasattr(reader, "artifact_dir")
    assert (
        VerifiedCandidateCommitRecorder._load_and_validate_common
        is LegacyVerifiedCandidateReader._load_and_validate_common
    )


def test_legacy_reader_success_is_strictly_read_only(tmp_path: Path) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id="campaign-1")
    branch_before = copy.deepcopy(branch)
    hypothesis_before = copy.deepcopy(h_record)
    database_before = _database_state(campaign / "scion.db")
    files_before = _tree_state(campaign)

    commit = reader.load_and_validate(
        branch=branch,
        hypothesis_record=h_record,
        workspace=str(workspace),
        materializer=materializer,
    )

    assert commit is not None
    assert commit.branch_id == branch.branch_id
    assert commit.hypothesis_id == "hypothesis-1"
    assert branch == branch_before
    assert h_record == hypothesis_before
    assert _database_state(campaign / "scion.db") == database_before
    assert _tree_state(campaign) == files_before


def test_legacy_reader_failure_is_strictly_read_only(tmp_path: Path) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    marker = branch.branch_evidence_summary["verified_candidate_commit"]
    artifact = campaign / marker["artifact_ref"]
    artifact.write_bytes(artifact.read_bytes() + b"tamper")
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id="campaign-1")
    branch_before = copy.deepcopy(branch)
    hypothesis_before = copy.deepcopy(h_record)
    database_before = _database_state(campaign / "scion.db")
    files_before = _tree_state(campaign)

    with pytest.raises(RuntimeError, match="artifact digest"):
        reader.load_and_validate(
            branch=branch,
            hypothesis_record=h_record,
            workspace=str(workspace),
            materializer=materializer,
        )

    assert branch == branch_before
    assert h_record == hypothesis_before
    assert _database_state(campaign / "scion.db") == database_before
    assert _tree_state(campaign) == files_before


@pytest.mark.parametrize(
    ("campaign_id", "mode_campaign_id", "mode"),
    (
        ("another-campaign", "campaign-1", "legacy_verified_commit_v1"),
        ("campaign-1", "another-campaign", "legacy_verified_commit_v1"),
        ("campaign-1", "campaign-1", "candidate_snapshot_v1"),
    ),
)
def test_legacy_reader_requires_exact_campaign_and_durable_legacy_mode(
    tmp_path: Path,
    campaign_id: str,
    mode_campaign_id: str,
    mode: str,
) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    if mode_campaign_id != "campaign-1" or mode != "legacy_verified_commit_v1":
        with sqlite3.connect(campaign / "scion.db") as conn:
            conn.execute("DROP TRIGGER candidate_ownership_mode_no_update")
            conn.execute(
                "UPDATE candidate_ownership_mode SET campaign_id = ?, mode = ? "
                "WHERE singleton = 1",
                (mode_campaign_id, mode),
            )
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id=campaign_id)

    with pytest.raises(RuntimeError, match="campaign ownership mismatch"):
        reader.load_and_validate(
            branch=branch,
            hypothesis_record=h_record,
            workspace=str(workspace),
            materializer=materializer,
        )


@pytest.mark.parametrize(
    "branch_state",
    (
        BranchState.READY_VALIDATE,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.READY_FROZEN,
        BranchState.FROZEN_TESTING,
    ),
)
def test_legacy_reader_accepts_exact_pending_validation_and_frozen_states(
    tmp_path: Path,
    branch_state: BranchState,
) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    branch.state = branch_state
    with sqlite3.connect(campaign / "scion.db") as conn:
        conn.execute(
            "UPDATE branches SET state = ? WHERE branch_id = ?",
            (branch_state.value, branch.branch_id),
        )
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id="campaign-1")

    commit = reader.load_and_validate(
        branch=branch,
        hypothesis_record=h_record,
        workspace=str(workspace),
        materializer=materializer,
    )

    assert commit.hypothesis_id == "hypothesis-1"


@pytest.mark.parametrize(
    ("table", "assignment", "value", "message"),
    (
        (
            "branches",
            "current_code_hash",
            "durable-drift",
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "screening_expand_count",
            99,
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "validation_expand_count",
            99,
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "failure_codes",
            '["durable_drift"]',
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "created_at",
            "2026-01-02T03:04:04",
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "updated_at",
            "2026-01-02T03:04:07",
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "direction",
            "durable drift",
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "weight_revision",
            4,
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "branch_evidence_summary_json",
            "{}",
            "durable legacy Branch owner mismatch",
        ),
        (
            "branches",
            "infra_block_count",
            5,
            "durable legacy Branch owner mismatch",
        ),
        (
            "hypotheses",
            "parent_hypothesis_id",
            "durable-parent-drift",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "created_at",
            "2026-01-02T03:04:08",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "base_champion_version",
            2,
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "family_id",
            "durable-family-drift",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "family_source",
            "manual",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "taxonomy_version",
            "v2",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "proposal_digest",
            "b" * 64,
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "status",
            "rejected",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "hypothesis_text",
            "durable drift",
            "durable legacy hypothesis owner mismatch",
        ),
        (
            "hypotheses",
            "branch_id",
            "another-branch",
            "durable legacy hypothesis owner mismatch",
        ),
    ),
)
def test_legacy_reader_rejects_durable_branch_or_hypothesis_drift(
    tmp_path: Path,
    table: str,
    assignment: str,
    value: object,
    message: str,
) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    identity_column = "branch_id" if table == "branches" else "hypothesis_id"
    identity = branch.branch_id if table == "branches" else "hypothesis-1"
    with sqlite3.connect(campaign / "scion.db") as conn:
        conn.execute(
            f"UPDATE {table} SET {assignment} = ? WHERE {identity_column} = ?",
            (value, identity),
        )
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id="campaign-1")

    with pytest.raises(RuntimeError, match=message):
        reader.load_and_validate(
            branch=branch,
            hypothesis_record=h_record,
            workspace=str(workspace),
            materializer=materializer,
        )


@pytest.mark.parametrize(
    ("branch_state", "evaluation_status", "message"),
    (
        (BranchState.EXPLORE, "pending", "Branch state"),
        (BranchState.EXPLORE_EXPAND, "pending", "Branch state"),
        (BranchState.PROMOTED, "pending", "Branch state"),
        (BranchState.READY_VALIDATE, "completed", "is not pending"),
    ),
)
def test_legacy_reader_rejects_non_validation_or_completed_owner(
    tmp_path: Path,
    branch_state: BranchState,
    evaluation_status: str,
    message: str,
) -> None:
    campaign, workspace, branch, h_record, materializer = _owned_candidate(tmp_path)
    branch.state = branch_state
    branch.branch_evidence_summary["verified_candidate_commit"][
        "evaluation_status"
    ] = evaluation_status
    reader = LegacyVerifiedCandidateReader(campaign, campaign_id="campaign-1")

    with pytest.raises(RuntimeError, match=message):
        reader.load_and_validate(
            branch=branch,
            hypothesis_record=h_record,
            workspace=str(workspace),
            materializer=materializer,
        )
