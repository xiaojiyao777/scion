from __future__ import annotations

import inspect
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.models import Branch, BranchState
from scion.lineage import sqlite_connection
from scion.lineage.champion_store import ConnectionScopedChampionStore
from scion.lineage.durable_owner import RevisionedBranchRecord
from scion.proposal import hypothesis_code_source_owner as subject
from scion.proposal import hypothesis_generation_authority as generation
from scion.runtime.workspace import WorkspaceMaterializer

_CREATE_CHAMPIONS = """
CREATE TABLE champions (
    version INTEGER NOT NULL,
    weight_revision INTEGER NOT NULL,
    operator_pool_json TEXT NOT NULL,
    solver_config_hash TEXT NOT NULL,
    code_snapshot_path TEXT NOT NULL,
    code_snapshot_hash TEXT NOT NULL,
    promotion_experiment_id TEXT,
    promotion_dossier_ref TEXT,
    promoted_at TEXT,
    PRIMARY KEY (version, weight_revision)
)
"""


@dataclass(slots=True)
class _Harness:
    database_authority: sqlite_connection.CampaignDatabaseAuthority
    graph: generation._CheckpointAAuthorities
    materializer: WorkspaceMaterializer
    owner: subject.HypothesisCodeSourceOwner
    registry_owner: object
    view_identity: object
    champion_snapshot: Path
    champion_snapshot_hash: str


# The leaf's installed-owner registry intentionally rejects an owner identity
# for the process lifetime.  Retain each focused-test graph so CPython cannot
# recycle an object ID into a later test and create a false duplicate install.
_LIVE_HARNESSES: list[_Harness] = []


def _operator_pool_json() -> str:
    return json.dumps(
        {
            "relocate": {
                "name": "relocate",
                "file_path": "operators/relocate.py",
                "category": "local_search",
                "weight": 1.0,
                "class_name": "RelocateOperator",
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _write_source(root: Path, *, marker: str) -> None:
    (root / "operators").mkdir(parents=True)
    (root / "operators" / "relocate.py").write_text(
        f"MARKER = {marker!r}\n",
        encoding="utf-8",
    )
    (root / "registry.yaml").write_text(
        "operators:\n  - relocate\n",
        encoding="utf-8",
    )


def _insert_champion(
    path: Path,
    *,
    snapshot: Path,
    snapshot_hash: str,
    version: int = 7,
    weight_revision: int = 2,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO champions (
                version, weight_revision, operator_pool_json, solver_config_hash,
                code_snapshot_path, code_snapshot_hash,
                promotion_experiment_id, promotion_dossier_ref, promoted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                weight_revision,
                _operator_pool_json(),
                "solver-config-v1",
                str(snapshot),
                snapshot_hash,
                "experiment-7",
                "dossier-7",
                "2026-07-17T01:02:03+00:00",
            ),
        )


def _harness(
    tmp_path: Path,
    *,
    champion_snapshot: Path | None = None,
) -> _Harness:
    campaign = (tmp_path / "campaign").resolve()
    materializer = WorkspaceMaterializer(
        str(campaign),
        editable_patterns=("operators/*.py",),
    )
    snapshot = (
        (campaign / "champions" / "champion_v7")
        if champion_snapshot is None
        else champion_snapshot.resolve()
    )
    _write_source(snapshot, marker="champion")
    snapshot_capture = materializer.capture_editable_identity_bytes(str(snapshot))

    database = tmp_path / "checkpoint-a-code-source.db"
    with sqlite3.connect(database) as connection:
        connection.execute(_CREATE_CHAMPIONS)
    _insert_champion(
        database,
        snapshot=snapshot,
        snapshot_hash=snapshot_capture.snapshot_hash,
    )
    database_authority = sqlite_connection._issue_test_campaign_database_authority(
        database,
        campaign_id="test-campaign",
    )
    store = ConnectionScopedChampionStore(database_authority)
    workspace_authority = subject.CampaignWorkspaceAuthority(materializer)
    owner = subject.HypothesisCodeSourceOwner(workspace_authority, store)
    registry_owner = object()
    graph = generation._install_checkpoint_a_authorities(
        registry=registry_owner,
        code_source_owner=owner,
        context_manager=object(),
        prompt_owner=object(),
        proposal_owner=object(),
        provider=object(),
    )
    owner._install_hypothesis_generation_authority(graph.code_source_owner)
    harness = _Harness(
        database_authority=database_authority,
        graph=graph,
        materializer=materializer,
        owner=owner,
        registry_owner=registry_owner,
        view_identity=object(),
        champion_snapshot=snapshot,
        champion_snapshot_hash=snapshot_capture.snapshot_hash,
    )
    _LIVE_HARNESSES.append(harness)
    return harness


def _branch(
    harness: _Harness,
    *,
    state: BranchState = BranchState.EXPLORE,
    base_champion_id: int = 7,
    current_code_hash: str | None = None,
    last_clean_code_hash: str | None = None,
    branch_code_status: str = "clean",
) -> Branch:
    return Branch(
        branch_id="branch-1",
        state=state,
        base_champion_id=base_champion_id,
        base_champion_hash=harness.champion_snapshot_hash,
        lineage_id="lineage-1",
        current_code_hash=current_code_hash,
        last_clean_code_hash=last_clean_code_hash,
        screening_expand_count=0,
        validation_expand_count=0,
        failure_codes=[],
        created_at=datetime(2026, 7, 17, 1, 2, 3),
        updated_at=datetime(2026, 7, 17, 1, 2, 3),
        direction=None,
        weight_revision=2,
        branch_code_status=branch_code_status,
        branch_evidence_summary={},
        infra_block_count=0,
    )


def _request(
    harness: _Harness,
    branch: Branch,
) -> generation.HypothesisCodeSourceRequest:
    owner = RevisionedBranchRecord.from_value(branch, owner_revision=3)
    view = generation._issue_generation_view(
        harness.graph.registry,
        root_identity=object(),
        root_generation=11,
        branch_owner=owner,
        hypothesis_bundle=(),
        prior_head=None,
        reservation_id="reservation-1",
        h_bundle_digest="b" * 64,
        owner_context_json=b'{"schema_version":"owner-context.test.v1"}',
    )
    harness.view_identity = view
    return generation._issue_code_source_request(harness.graph.registry, view)


def _bind(
    harness: _Harness,
    request: generation.HypothesisCodeSourceRequest,
) -> generation.HypothesisCodeSource:
    with sqlite_connection._independent_authority_read_snapshot(
        harness.database_authority
    ) as snapshot:
        return harness.owner._bind_hypothesis_code_source_from_snapshot(
            snapshot,
            request,
        )


def _inspect(
    harness: _Harness,
    source: generation.HypothesisCodeSource,
) -> generation._CodeSourceProjection:
    return generation._inspect_code_source(
        harness.graph.registry,
        source,
        view=harness.view_identity,  # type: ignore[arg-type]
    )


def test_missing_branch_hash_selects_exact_base_champion_without_branch_read(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    assert not (harness.materializer._workspaces_dir / "branch-1").exists()
    expected = harness.materializer.capture_editable_identity_bytes(
        str(harness.champion_snapshot)
    )

    source = _bind(harness, _request(harness, _branch(harness)))
    projection = _inspect(harness, source)

    assert projection.source_kind == "base_champion"
    assert projection.selected_manifest_digest == expected.manifest_digest
    assert projection.snapshot_hash == harness.champion_snapshot_hash
    assert projection.entries == (
        (
            "operators/relocate.py",
            b"MARKER = 'champion'\n",
            projection.entries[0][2],
            True,
            True,
        ),
        (
            "registry.yaml",
            b"operators:\n  - relocate\n",
            projection.entries[1][2],
            False,
            True,
        ),
    )


def test_verified_clean_branch_selects_owned_workspace_without_champion_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    workspace = Path(
        harness.materializer.create_branch_workspace(
            "branch-1",
            str(harness.champion_snapshot),
        )
    )
    (workspace / "operators" / "relocate.py").write_text(
        "MARKER = 'verified-branch'\n",
        encoding="utf-8",
    )
    capture = harness.materializer.capture_editable_identity_bytes(str(workspace))
    branch = _branch(
        harness,
        current_code_hash=capture.code_hash,
        last_clean_code_hash=capture.code_hash,
    )
    champion_loads = 0
    original = ConnectionScopedChampionStore._load_exact_from_snapshot

    def counted_load(
        store: ConnectionScopedChampionStore,
        snapshot: sqlite_connection._IndependentReadSnapshot,
        version: int,
        weight_revision: int,
    ) -> object:
        nonlocal champion_loads
        champion_loads += 1
        return original(store, snapshot, version, weight_revision)

    monkeypatch.setattr(
        ConnectionScopedChampionStore,
        "_load_exact_from_snapshot",
        counted_load,
    )
    source = _bind(harness, _request(harness, branch))
    projection = _inspect(harness, source)

    assert champion_loads == 0
    assert projection.source_kind == "verified_branch_workspace"
    assert projection.selected_manifest_digest == capture.manifest_digest
    assert projection.code_hash == capture.code_hash
    assert projection.snapshot_hash == capture.snapshot_hash
    assert projection.entries[0][1] == b"MARKER = 'verified-branch'\n"


@pytest.mark.parametrize(
    ("state", "current", "clean", "status", "expected"),
    (
        (BranchState.STALE, "a", "b", "dirty", "base_champion"),
        (BranchState.STALE_WEIGHT_UPDATE, "a", "a", "clean", "base_champion"),
        (BranchState.EXPLORE, None, "a", "clean", "base_champion"),
        (BranchState.EXPLORE, "a", None, "clean", "base_champion"),
        (
            BranchState.EXPLORE,
            "a",
            "a",
            "clean",
            "verified_branch_workspace",
        ),
    ),
)
def test_frozen_selection_table(
    tmp_path: Path,
    state: BranchState,
    current: str | None,
    clean: str | None,
    status: str,
    expected: str,
) -> None:
    harness = _harness(tmp_path)
    branch = _branch(
        harness,
        state=state,
        current_code_hash=current,
        last_clean_code_hash=clean,
        branch_code_status=status,
    )
    assert subject._select_source_kind(branch) == expected


@pytest.mark.parametrize(
    ("current", "clean", "status"),
    (("a", "b", "clean"), ("a", "a", "dirty")),
)
def test_selection_inconsistency_is_deterministic_rejection(
    tmp_path: Path,
    current: str,
    clean: str,
    status: str,
) -> None:
    harness = _harness(tmp_path)
    request = _request(
        harness,
        _branch(
            harness,
            current_code_hash=current,
            last_clean_code_hash=clean,
            branch_code_status=status,
        ),
    )

    with pytest.raises(subject.HypothesisCodeSourceRejectedError):
        _bind(harness, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_REJECTED
    )


def test_changed_verified_workspace_is_rejected_without_champion_fallback(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    workspace = Path(
        harness.materializer.create_branch_workspace(
            "branch-1",
            str(harness.champion_snapshot),
        )
    )
    clean_capture = harness.materializer.capture_editable_identity_bytes(
        str(workspace)
    )
    request = _request(
        harness,
        _branch(
            harness,
            current_code_hash=clean_capture.code_hash,
            last_clean_code_hash=clean_capture.code_hash,
        ),
    )
    (workspace / "operators" / "relocate.py").write_text(
        "MARKER = 'changed-after-capture'\n",
        encoding="utf-8",
    )

    with pytest.raises(subject.HypothesisCodeSourceRejectedError):
        _bind(harness, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_REJECTED
    )


def test_missing_exact_base_champion_is_rejected(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    request = _request(harness, _branch(harness, base_champion_id=99))

    with pytest.raises(subject.HypothesisCodeSourceRejectedError):
        _bind(harness, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_REJECTED
    )


def test_champion_snapshot_outside_sealed_campaign_root_is_rejected(
    tmp_path: Path,
) -> None:
    outside = (tmp_path / "outside-champion").resolve()
    harness = _harness(tmp_path, champion_snapshot=outside)
    request = _request(harness, _branch(harness))

    with pytest.raises(subject.HypothesisCodeSourceRejectedError):
        _bind(harness, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_REJECTED
    )


def test_symlinked_champion_snapshot_is_rejected(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    alias = harness.champion_snapshot.parent / "champion_v7_alias"
    alias.symlink_to(harness.champion_snapshot, target_is_directory=True)
    database_path = sqlite_connection._lookup_authority_state(
        harness.database_authority
    ).database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE champions SET code_snapshot_path = ?",
            (str(alias),),
        )
    request = _request(harness, _branch(harness))

    with pytest.raises(subject.HypothesisCodeSourceRejectedError):
        _bind(harness, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_REJECTED
    )


def test_inactive_exact_snapshot_marks_request_source_unknown(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    request = _request(harness, _branch(harness))
    with sqlite_connection._independent_authority_read_snapshot(
        harness.database_authority
    ) as snapshot:
        pass

    with pytest.raises(subject.HypothesisCodeSourceUnknownError):
        harness.owner._bind_hypothesis_code_source_from_snapshot(snapshot, request)

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.SOURCE_UNKNOWN
    )


def test_forged_snapshot_does_not_claim_request_and_valid_snapshot_still_binds(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    request = _request(harness, _branch(harness))

    with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
        harness.owner._bind_hypothesis_code_source_from_snapshot(  # type: ignore[arg-type]
            object(),
            request,
        )

    assert (
        generation._CODE_REQUEST_STATES[request].phase
        is generation._CodeRequestPhase.ISSUED
    )
    assert type(_bind(harness, request)) is generation.HypothesisCodeSource


def test_dependencies_handle_and_entry_surface_are_fixed_once(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    entry = inspect.signature(
        subject.HypothesisCodeSourceOwner._bind_hypothesis_code_source_from_snapshot
    )
    constructor = inspect.signature(subject.HypothesisCodeSourceOwner)

    assert tuple(entry.parameters) == ("self", "snapshot", "request")
    assert tuple(constructor.parameters) == (
        "workspace_authority",
        "champion_store",
    )
    assert not {
        "path",
        "root",
        "files",
        "mapping",
        "code",
        "manifest",
        "source_kind",
    }.intersection(entry.parameters)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.owner._install_hypothesis_generation_authority(
            harness.graph.code_source_owner
        )
