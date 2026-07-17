from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scion.core import campaign_owner_registry as subject
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import branch_owner_store, hypothesis_owner_store
from scion.lineage import sqlite_connection
from scion.lineage.champion_store import ConnectionScopedChampionStore
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.lineage.proposal_attempt_owner import (
    ProposalAttemptCommitClassification,
    ProposalAttemptOwner,
)
from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal.context_manager.manager import ContextManager
from scion.proposal.engine import provider_call as provider_module
from scion.proposal.engine.provider_call import ProviderCallOwner
from scion.proposal.hypothesis_code_source_owner import (
    CampaignWorkspaceAuthority,
    HypothesisCodeSourceOwner,
)
from scion.proposal.prompt_projection_authority import (
    HypothesisPromptRejectedError,
    ProposalPromptProjectionAuthority,
)
from scion.runtime.workspace import WorkspaceMaterializer


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class _Transport:
    def __init__(self, *, error: BaseException | None = None) -> None:
        self.error = error
        self.calls = 0
        self.registry: subject.CampaignOwnerRegistry | None = None
        self.observed_unlocked = False

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, object],
        _model: str,
        *,
        system_blocks: list[dict[str, object]],
        request_kind: str,
    ) -> dict[str, object]:
        assert system_blocks
        assert request_kind == "hypothesis"
        self.calls += 1
        registry = self.registry
        assert registry is not None
        acquired = registry._owner_lock.acquire(blocking=False)
        if acquired:
            registry._owner_lock.release()
        self.observed_unlocked = (
            acquired and registry._availability is subject._Availability.CLEAR
        )
        if self.error is not None:
            raise self.error
        return {
            "hypothesis_text": "Tighten bounded solution-pool replacement.",
            "change_locus": "solution_pool_search",
            "action": "modify",
            "target_file": "solution_pool.py",
            "predicted_direction": "improve",
            "target_weakness": "The current pool keeps weak replacements.",
            "expected_effect": "Improve bounded elite retention.",
            "suggested_weight": 1.0,
        }


@dataclass(frozen=True, slots=True)
class _Harness:
    path: Path
    authority: sqlite_connection.CampaignDatabaseAuthority
    registry: subject.CampaignOwnerRegistry
    prompt_owner: ProposalPromptProjectionAuthority
    proposal_owner: ProposalAttemptOwner
    provider_owner: ProviderCallOwner
    transport: _Transport
    registry_authority: generation._AuthorityHandle


_LIVE_HARNESSES: list[_Harness] = []


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE branches (
            branch_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            base_champion_id INTEGER NOT NULL,
            base_champion_hash TEXT NOT NULL,
            lineage_id TEXT NOT NULL,
            current_code_hash TEXT,
            last_clean_code_hash TEXT,
            screening_expand_count INTEGER NOT NULL,
            validation_expand_count INTEGER NOT NULL,
            failure_codes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            direction TEXT,
            weight_revision INTEGER NOT NULL,
            branch_code_status TEXT NOT NULL,
            branch_evidence_summary_json TEXT NOT NULL,
            infra_block_count INTEGER NOT NULL,
            owner_revision INTEGER NOT NULL,
            owner_protocol_generation TEXT NOT NULL
        );
        CREATE TABLE hypotheses (
            hypothesis_id TEXT PRIMARY KEY,
            branch_id TEXT NOT NULL,
            change_locus TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            target_file TEXT,
            parent_hypothesis_id TEXT,
            suggested_weight REAL,
            hypothesis_text TEXT,
            created_at TEXT NOT NULL,
            base_champion_version INTEGER NOT NULL,
            family_id TEXT,
            family_source TEXT,
            taxonomy_version TEXT,
            predicted_direction TEXT NOT NULL,
            proposal_digest TEXT,
            owner_revision INTEGER NOT NULL,
            owner_protocol_generation TEXT NOT NULL
        );
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
        );
        CREATE TABLE experiment_events (
            event_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            hypothesis_id TEXT,
            timestamp TEXT NOT NULL,
            event_kind TEXT NOT NULL,
            stage TEXT NOT NULL,
            audit_payload_json TEXT NOT NULL
        );
        """
    )


def _problem_evidence(*, history_id: str = "hypothesis-prior") -> dict[str, object]:
    return {
        "available_actions": ["modify"],
        "experiment_history": [
            {
                "attempt_id": history_id,
                "candidate_composition": {
                    "current_step": {"hypothesis_id": history_id}
                },
                "source_branch_id": "branch-1",
            }
        ],
        "problem_summary": "Capacitated vehicle-routing research.",
        "research_surfaces": [
            {
                "allowed_actions": ["modify"],
                "kind": "policy",
                "name": "solution_pool_search",
                "target_files": ["solution_pool.py"],
            }
        ],
    }


def _unresolved_start_payload() -> dict[str, object]:
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "attempt-restored-open",
        "campaign_id": "campaign-a",
        "branch_id": "branch-1",
        "runtime_mode": "direct_v3",
        "phase": "hypothesis",
        "status": "started",
        "transition_reason": "provider_call_started",
        "failure_lane": None,
        "hypothesis_id": None,
        "hypothesis_digest": None,
        "patch_digest": None,
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": _digest(b"restored-context"),
            "prompt_hash": _digest(b"restored-prompt"),
            "trace_ref": None,
            "prompt_manifest_ref": None,
            "raw_response_ref": None,
            "provider_ok": None,
            "ok": None,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "cvrp",
            "problem_spec_hash": _digest(b"problem-spec"),
            "split_manifest_hash": _digest(b"split-manifest"),
            "seed_ledger_hash": _digest(b"seed-ledger"),
            "champion_version": 7,
            "champion_weight_revision": 2,
            "champion_code_snapshot_hash": _digest(b"champion"),
            "branch_base_champion_id": 7,
            "branch_base_champion_hash": _digest(b"champion"),
        },
        "tainted_artifact_refs": [],
    }


def _harness(
    tmp_path: Path,
    *,
    transport_error: BaseException | None = None,
    history_id: str = "hypothesis-prior",
    unresolved_start: bool = False,
    malformed_start: bool = False,
) -> _Harness:
    if unresolved_start and malformed_start:
        raise ValueError("restore fixture accepts one proposal-attempt condition")
    campaign_root = (tmp_path / "campaign").resolve()
    materializer = WorkspaceMaterializer(
        str(campaign_root),
        editable_patterns=("*.py",),
    )
    snapshot = campaign_root / "champions" / "champion_v7"
    snapshot.mkdir(parents=True)
    (snapshot / "solution_pool.py").write_text(
        "def bounded_elite_solution_pool_search(pool):\n    return pool\n",
        encoding="utf-8",
    )
    capture = materializer.capture_editable_identity_bytes(str(snapshot))

    branch = RevisionedBranchRecord.from_value(
        Branch(
            branch_id="branch-1",
            state=BranchState.EXPLORE,
            base_champion_id=7,
            base_champion_hash=capture.snapshot_hash,
            lineage_id="lineage-1",
            current_code_hash=None,
            last_clean_code_hash=None,
            created_at=datetime(2026, 7, 17, 1, 2, 3, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 17, 1, 2, 4, tzinfo=timezone.utc),
            weight_revision=2,
            branch_code_status="clean",
        ),
        owner_revision=3,
    )
    other_branch_value = branch.value()
    other_branch_value.branch_id = "branch-2"
    other_branch_value.lineage_id = "lineage-2"
    other_branch = RevisionedBranchRecord.from_value(
        other_branch_value,
        owner_revision=1,
    )
    prior = RevisionedHypothesisRecord.from_value(
        HypothesisRecord(
            hypothesis_id="hypothesis-prior",
            branch_id="branch-1",
            change_locus="solution_pool_search",
            action="modify",
            status="validated",
            target_file="solution_pool.py",
            hypothesis_text="Earlier bounded elite replacement.",
            created_at=datetime(
                2026,
                7,
                17,
                1,
                2,
                5,
                1,
                tzinfo=timezone.utc,
            ),
            base_champion_version=7,
            family_id="solution-pool",
            family_source="manual",
            taxonomy_version="v1",
            predicted_direction="improve",
            proposal_digest=_digest(b"prior-proposal"),
        ),
        owner_revision=4,
    )
    path = tmp_path / "registry-generation.db"
    with sqlite3.connect(path) as connection:
        _create_schema(connection)
        connection.execute(
            branch_owner_store._BRANCH_INSERT_SQL,
            (
                *branch_owner_store._branch_storage_values(branch),
                branch.owner_revision,
                branch_owner_store._OWNER_PROTOCOL_GENERATION,
            ),
        )
        connection.execute(
            branch_owner_store._BRANCH_INSERT_SQL,
            (
                *branch_owner_store._branch_storage_values(other_branch),
                other_branch.owner_revision,
                branch_owner_store._OWNER_PROTOCOL_GENERATION,
            ),
        )
        connection.execute(
            hypothesis_owner_store._HYPOTHESIS_INSERT_SQL,
            hypothesis_owner_store._write_parameters(prior),
        )
        connection.execute(
            """
            INSERT INTO champions (
                version, weight_revision, operator_pool_json, solver_config_hash,
                code_snapshot_path, code_snapshot_hash, promotion_experiment_id,
                promotion_dossier_ref, promoted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                7,
                2,
                "{}",
                "solver-config-v1",
                str(snapshot),
                capture.snapshot_hash,
                "experiment-7",
                "dossier-7",
                "2026-07-17T01:02:03+00:00",
            ),
        )
        if unresolved_start:
            connection.execute(
                "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "event-restored-open",
                    "campaign-a",
                    "branch-1",
                    None,
                    "2026-07-17T01:03:00.000000+00:00",
                    "proposal_attempt_transition",
                    "proposal_hypothesis",
                    _canonical(_unresolved_start_payload()),
                ),
            )
        if malformed_start:
            connection.execute(
                "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "event-restored-malformed",
                    "campaign-a",
                    "branch-1",
                    None,
                    "2026-07-17T01:03:00.000000+00:00",
                    "proposal_attempt_transition",
                    "proposal_hypothesis",
                    "{}",
                ),
            )

    authority = sqlite_connection._issue_test_campaign_database_authority(
        path,
        campaign_id="campaign-a",
    )
    registry = subject.CampaignOwnerRegistry(authority)
    code_owner = HypothesisCodeSourceOwner(
        CampaignWorkspaceAuthority(materializer),
        ConnectionScopedChampionStore(authority),
    )
    context_manager = ContextManager(
        hypothesis_problem_evidence=_problem_evidence(history_id=history_id)
    )
    prompt_owner = ProposalPromptProjectionAuthority()
    proposal_owner = ProposalAttemptOwner(authority)
    transport = _Transport(error=transport_error)
    provider_owner = ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    authorities = generation._install_checkpoint_a_authorities(
        registry=registry,
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider=provider_owner,
    )
    code_owner._install_hypothesis_generation_authority(
        authorities.code_source_owner
    )
    context_manager._install_hypothesis_generation_authority(
        authorities.context_manager
    )
    prompt_owner._install_hypothesis_generation_authority(
        authorities.prompt_owner
    )
    proposal_owner._install_hypothesis_generation_authority(
        authorities.proposal_owner
    )
    provider_owner._install_hypothesis_generation_authority(authorities.provider)
    registry._install_hypothesis_generation_components(
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider_owner=provider_owner,
        registry_authority=authorities.registry,
        provider_authority=authorities.provider,
        runtime_mode="direct_v3",
        problem_id="cvrp",
        problem_spec_hash=_digest(b"problem-spec"),
        split_manifest_hash=_digest(b"split-manifest"),
        seed_ledger_hash=_digest(b"seed-ledger"),
    )
    restore = registry.begin_restore()
    registry.seal_live(restore)
    transport.registry = registry
    harness = _Harness(
        path=path,
        authority=authority,
        registry=registry,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider_owner=provider_owner,
        transport=transport,
        registry_authority=authorities.registry,
    )
    _LIVE_HARNESSES.append(harness)
    return harness


def _start(harness: _Harness) -> tuple[
    generation.HypothesisGenerationView,
    generation.BoundHypothesisPrompt,
    generation.ProviderGenerationPermit,
]:
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    projection = generation._inspect_generation_view(
        harness.registry_authority,
        view,
    )
    owner_context = json.loads(projection.owner_context_json)
    assert set(owner_context) == {
        "anchors",
        "branch",
        "campaign_id",
        "h_bundle",
        "prior_head",
        "root_generation",
        "runtime_mode",
        "schema_version",
    }
    assert set(owner_context["branch"]) == {
        "base_champion_hash",
        "base_champion_id",
        "base_champion_weight_revision",
        "branch_code_status",
        "branch_id",
        "current_code_hash",
        "last_clean_code_hash",
        "owner_revision",
        "state",
        "storage_sha256",
    }
    assert set(owner_context["h_bundle"]) == {"count", "digest", "items"}
    assert set(owner_context["h_bundle"]["items"][0]) == {
        "hypothesis_id",
        "owner_revision",
        "storage_sha256",
    }
    assert set(owner_context["anchors"]) == {
        "branch_base_champion_hash",
        "branch_base_champion_id",
        "champion_code_snapshot_hash",
        "champion_version",
        "champion_weight_revision",
        "problem_id",
        "problem_spec_hash",
        "seed_ledger_hash",
        "split_manifest_hash",
    }
    assert owner_context["h_bundle"]["count"] == 1
    assert owner_context["prior_head"]["hypothesis_id"] == "hypothesis-prior"
    assert owner_context["h_bundle"]["digest"] == _digest(
        _canonical(
            {
                "branch_id": "branch-1",
                "count": 1,
                "items": owner_context["h_bundle"]["items"],
                "schema_version": "hypothesis-generation-source-bundle.v1",
            }
        ).encode("utf-8")
    )
    harness.registry.bind_hypothesis_code_source(view)
    prompt_source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(prompt_source)
    permit = harness.registry.start_hypothesis_generation(
        view,
        prompt,
        {"caller_note": "non-authoritative"},
    )
    return view, prompt, permit


def _event_statuses(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT audit_payload_json FROM experiment_events ORDER BY timestamp"
        ).fetchall()
    return [json.loads(row[0])["status"] for row in rows]


def test_real_failure_path_releases_no_lock_and_resolves_terminal(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, transport_error=RuntimeError("provider down"))
    view, prompt, permit = _start(harness)
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="reservation"):
        harness.registry.acquire_branch_mutation("branch-1")
    assert harness.registry.acquire_branch_mutation("branch-2").owner.branch_id == (
        "branch-2"
    )

    failure = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(failure) is generation.FailedHypothesisGeneration
    assert harness.transport.observed_unlocked
    harness.registry.observe_hypothesis_generation_outcome(view, failure)
    receipt = harness.registry.terminalize_hypothesis_generation(view, failure)

    assert type(receipt) is generation.TerminalAttemptReceipt
    assert _event_statuses(harness.path) == ["started", "failed"]
    assert harness.registry.acquire_branch_mutation("branch-1").owner.branch_id == (
        "branch-1"
    )


def test_success_result_stops_at_result_bound_with_durable_reservation(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    view, prompt, permit = _start(harness)
    result = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(result) is generation.GeneratedHypothesisResult
    harness.registry.observe_hypothesis_generation_outcome(view, result)

    assert harness.transport.observed_unlocked
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.DURABLE_OPEN
    with pytest.raises(subject.CampaignOwnerLifecycleError, match="reservation"):
        harness.registry.acquire_hypothesis_generation("branch-1")


def test_prompt_rejection_is_settled_from_leaf_state_and_releases_local(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, history_id="another-hypothesis")
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)

    with pytest.raises(HypothesisPromptRejectedError):
        harness.prompt_owner.bind_hypothesis_prompt(source)
    assert harness.registry.settle_hypothesis_prompt_failure(view) is True
    assert type(
        harness.registry.acquire_hypothesis_generation("branch-1")
    ) is generation.HypothesisGenerationView
    assert harness.transport.calls == 0


def test_prestart_abort_releases_captured_view_without_durable_event(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")

    assert harness.registry.abort_hypothesis_generation(view) is None
    assert _event_statuses(harness.path) == []
    assert "branch-1" not in harness.registry._hypothesis_generation_reservations
    with pytest.raises(subject.InvalidCampaignOwnerCapabilityError):
        harness.registry.abort_hypothesis_generation(view)


def test_prestart_abort_releases_bound_prompt_without_durable_event(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    harness.prompt_owner.bind_hypothesis_prompt(source)

    assert harness.registry.abort_hypothesis_generation(view) is None
    assert _event_statuses(harness.path) == []
    assert type(
        harness.registry.acquire_hypothesis_generation("branch-1")
    ) is generation.HypothesisGenerationView


def test_prestart_abort_rejects_code_source_in_flight(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    generation._issue_code_source_request(harness.registry_authority, view)

    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.registry.abort_hypothesis_generation(view)
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.LOCAL
    assert _event_statuses(harness.path) == []


def test_start_rollback_is_expected_and_releases_local_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(source)

    def fail_before_commit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("commit did not begin")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        fail_before_commit,
    )
    with pytest.raises(RuntimeError, match="commit did not begin"):
        harness.registry.start_hypothesis_generation(view, prompt)

    assert _event_statuses(harness.path) == []
    assert type(
        harness.registry.acquire_hypothesis_generation("branch-1")
    ) is generation.HypothesisGenerationView


@pytest.mark.parametrize(
    ("statement", "owner_id", "expected_message"),
    (
        (
            "UPDATE branches SET owner_revision = owner_revision + 1 "
            "WHERE branch_id = ?",
            "branch-1",
            "START Branch differs",
        ),
        (
            "UPDATE hypotheses SET owner_revision = owner_revision + 1 "
            "WHERE hypothesis_id = ?",
            "hypothesis-prior",
            "START H bundle differs",
        ),
    ),
)
def test_start_transaction_rejects_durable_owner_drift(
    tmp_path: Path,
    statement: str,
    owner_id: str,
    expected_message: str,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(source)
    with sqlite3.connect(harness.path) as connection:
        cursor = connection.execute(statement, (owner_id,))
        assert cursor.rowcount == 1

    with pytest.raises(
        subject.DurableOwnerIntegrityError,
        match=expected_message,
    ):
        harness.registry.start_hypothesis_generation(view, prompt)

    assert _event_statuses(harness.path) == []
    assert "branch-1" not in harness.registry._hypothesis_generation_reservations


def test_start_mixed_classification_holds_only_its_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(source)

    def classify_mixed(
        _owner: ProposalAttemptOwner,
        _snapshot: object,
        *,
        expected: object,
    ) -> tuple[ProposalAttemptCommitClassification, None]:
        del expected
        return ProposalAttemptCommitClassification.MIXED, None

    monkeypatch.setattr(
        ProposalAttemptOwner,
        "_classify_started_attempt_from_snapshot",
        classify_mixed,
    )
    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="START classification",
    ):
        harness.registry.start_hypothesis_generation(view, prompt)

    assert _event_statuses(harness.path) == ["started"]
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.registry._availability is subject._Availability.CLEAR


def test_fault_after_start_claim_releases_local_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(source)
    original_begin = generation._begin_started_attempt

    def begin_then_raise(*args: object, **kwargs: object) -> None:
        original_begin(*args, **kwargs)
        raise RuntimeError("fault after START claim")

    monkeypatch.setattr(generation, "_begin_started_attempt", begin_then_raise)
    with pytest.raises(RuntimeError, match="fault after START claim"):
        harness.registry.start_hypothesis_generation(view, prompt)

    assert _event_statuses(harness.path) == []
    assert type(
        harness.registry.acquire_hypothesis_generation("branch-1")
    ) is generation.HypothesisGenerationView


def test_commit_then_raise_is_classified_for_start_and_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    view = harness.registry.acquire_hypothesis_generation("branch-1")
    harness.registry.bind_hypothesis_code_source(view)
    source = harness.registry.issue_hypothesis_prompt_source(view)
    prompt = harness.prompt_owner.bind_hypothesis_prompt(source)
    original_commit = subject._sqlite._commit_coordinated_transaction

    def commit_then_raise(*args: object, **kwargs: object) -> None:
        original_commit(*args, **kwargs)
        raise RuntimeError("commit return lost")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        commit_then_raise,
    )
    permit = harness.registry.start_hypothesis_generation(view, prompt)
    assert type(permit) is generation.ProviderGenerationPermit
    aborted = harness.registry.abort_hypothesis_generation(view)
    receipt = harness.registry.terminalize_hypothesis_generation(view, aborted)

    assert type(receipt) is generation.TerminalAttemptReceipt
    assert _event_statuses(harness.path) == ["started", "failed"]
    assert harness.registry.acquire_branch_mutation("branch-1").owner.branch_id == (
        "branch-1"
    )


def test_claimed_unknown_provider_is_settled_to_branch_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    _view, prompt, permit = _start(harness)

    def fail_after_claim(_projection: object) -> object:
        raise RuntimeError("provider rebuild lost")

    monkeypatch.setattr(
        provider_module,
        "_rebuild_bound_hypothesis_turn",
        fail_after_claim,
    )
    with pytest.raises(provider_module.ProviderCallUnknownError):
        harness.provider_owner.call_hypothesis(permit, prompt)
    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="unresolved",
    ):
        harness.registry.acquire_hypothesis_generation("branch-1")
    assert harness.registry.acquire_branch_mutation("branch-2").owner.branch_id == (
        "branch-2"
    )

    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.transport.calls == 0
    with pytest.raises(subject.HypothesisGenerationReservationHoldError):
        harness.registry.acquire_branch_mutation("branch-1")


def test_terminal_rollback_retains_branch_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, transport_error=RuntimeError("provider down"))
    view, prompt, permit = _start(harness)
    failure = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(failure) is generation.FailedHypothesisGeneration
    harness.registry.observe_hypothesis_generation_outcome(view, failure)

    def fail_before_commit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("terminal commit did not begin")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        fail_before_commit,
    )
    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="terminal classification",
    ):
        harness.registry.terminalize_hypothesis_generation(view, failure)

    assert _event_statuses(harness.path) == ["started"]
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    with pytest.raises(subject.HypothesisGenerationReservationHoldError):
        harness.registry.acquire_branch_mutation("branch-1")


def test_fault_after_terminal_claim_becomes_uncertain_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, transport_error=RuntimeError("provider down"))
    view, prompt, permit = _start(harness)
    failure = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(failure) is generation.FailedHypothesisGeneration
    harness.registry.observe_hypothesis_generation_outcome(view, failure)
    original_begin = generation._begin_terminal_persistence

    def begin_then_raise(*args: object, **kwargs: object) -> None:
        original_begin(*args, **kwargs)
        raise RuntimeError("fault after terminal claim")

    monkeypatch.setattr(
        generation,
        "_begin_terminal_persistence",
        begin_then_raise,
    )
    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="terminal claim failed",
    ):
        harness.registry.terminalize_hypothesis_generation(view, failure)

    assert _event_statuses(harness.path) == ["started"]
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


def test_restore_installs_branch_hold_for_unresolved_start(tmp_path: Path) -> None:
    harness = _harness(tmp_path, unresolved_start=True)

    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="unresolved",
    ):
        harness.registry.acquire_branch_mutation("branch-1")
    with pytest.raises(
        subject.HypothesisGenerationReservationHoldError,
        match="unresolved",
    ):
        harness.registry.acquire_hypothesis_generation("branch-1")
    assert harness.registry.acquire_branch_mutation("branch-2").owner.branch_id == (
        "branch-2"
    )


def test_restore_installs_branch_hold_for_attributed_malformed_start(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, malformed_start=True)

    with pytest.raises(subject.HypothesisGenerationReservationHoldError):
        harness.registry.acquire_hypothesis_generation("branch-1")
    assert harness.registry.acquire_branch_mutation("branch-2").owner.branch_id == (
        "branch-2"
    )
