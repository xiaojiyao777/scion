from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.config.problem import ProblemSpec, SearchSpace, SolverConfig
from scion.contract.gate import ContractGate, HypothesisContractUnknownError
from scion.core import campaign_owner_registry as subject
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import branch_owner_store, hypothesis_owner_store, owner_transaction
from scion.lineage import sqlite_connection
from scion.lineage.champion_store import ConnectionScopedChampionStore
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.lineage.proposal_attempt_owner import (
    InvalidStartedHypothesisAttemptError,
    ProposalAttemptCommitClassification,
    ProposalAttemptOwner,
)
from scion.tests.unit.lineage.checkpoint_b_schema_contract import (
    CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL,
    CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL,
)
from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal.context_manager.manager import ContextManager
from scion.proposal.engine import provider_call as provider_module
from scion.proposal.engine.provider_call import ProviderCallOwner
from scion.proposal.hypothesis_code_source_owner import (
    CampaignWorkspaceAuthority,
    HypothesisCodeSourceOwner,
)
from scion.proposal.hypothesis_target_factory import (
    ClockAuthority,
    HypothesisTargetFactory,
    HypothesisTargetUnknownError,
    UUIDAuthority,
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
    contract_gate: ContractGate | None = None
    target_factory: HypothesisTargetFactory | None = None


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
        CREATE TABLE campaign_identity (campaign_id TEXT PRIMARY KEY);
        CREATE TABLE candidate_evaluation_leases (
            lease_id TEXT PRIMARY KEY,
            branch_id TEXT NOT NULL,
            source_hypothesis_id TEXT,
            state TEXT NOT NULL
        );
        """
        + CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL
        + CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL
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
    checkpoint_b: bool = False,
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
        connection.execute("INSERT INTO campaign_identity VALUES ('campaign-a')")
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
                """
                INSERT INTO experiment_events (
                    event_id, campaign_id, branch_id, hypothesis_id,
                    timestamp, event_kind, stage, audit_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
                """
                INSERT INTO experiment_events (
                    event_id, campaign_id, branch_id, hypothesis_id,
                    timestamp, event_kind, stage, audit_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
    contract_gate: ContractGate | None = None
    target_factory: HypothesisTargetFactory | None = None
    checkpoint_b_authorities: generation._CheckpointBAuthorities | None = None
    if checkpoint_b:
        spec = ProblemSpec(
            name="registry-checkpoint-b",
            root_dir=str(campaign_root),
            operator_categories=["solution_pool_search"],
            research_surfaces=[
                SimpleNamespace(
                    name="solution_pool_search",
                    kind="operator",
                    targets=SimpleNamespace(
                        files=["solution_pool.py"],
                        create_new_allowed=False,
                        modify_allowed=True,
                        remove_allowed=False,
                    ),
                )
            ],
            search_space=SearchSpace(
                editable=["solution_pool.py"],
                frozen=[],
                import_whitelist=[],
            ),
            solver=SolverConfig(),
        )
        contract_gate = ContractGate(spec)
        target_factory = HypothesisTargetFactory(
            taxonomy={
                "version": "v1",
                "families": ["solution_pool_search"],
                "aliases": {
                    "solution_pool_search": ["solution pool", "bounded elite"]
                },
            },
            clock_authority=ClockAuthority(
                lambda: datetime(
                    2026,
                    7,
                    17,
                    1,
                    2,
                    6,
                    tzinfo=timezone.utc,
                )
            ),
            uuid_authority=UUIDAuthority(
                lambda: uuid.UUID("11111111-1111-4111-8111-111111111111")
            ),
        )
        checkpoint_b_authorities = generation._extend_checkpoint_b_authorities(
            authorities,
            contract_gate=contract_gate,
            target_factory=target_factory,
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
    if checkpoint_b_authorities is not None:
        assert contract_gate is not None and target_factory is not None
        contract_gate._install_hypothesis_generation_authority(
            checkpoint_b_authorities.contract_gate
        )
        target_factory._install_hypothesis_generation_authority(
            checkpoint_b_authorities.target_factory
        )
    registry._install_hypothesis_generation_components(
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider_owner=provider_owner,
        registry_authority=authorities.registry,
        provider_authority=authorities.provider,
        contract_gate=contract_gate,
        target_factory=target_factory,
        contract_gate_authority=(
            None
            if checkpoint_b_authorities is None
            else checkpoint_b_authorities.contract_gate
        ),
        target_factory_authority=(
            None
            if checkpoint_b_authorities is None
            else checkpoint_b_authorities.target_factory
        ),
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
        contract_gate=contract_gate,
        target_factory=target_factory,
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


def _restart_registry_from_storage(
    harness: _Harness,
) -> _Harness:
    """Recompose a fresh database authority, owner graph, and live Registry."""

    database_key = subject._database_registry_key(harness.authority)
    with subject._AUTHORITY_REGISTRIES_LOCK:
        subject._DATABASE_REGISTRIES.pop(database_key, None)
    authority = sqlite_connection._issue_test_campaign_database_authority(
        harness.path,
        campaign_id="campaign-a",
    )
    registry = subject.CampaignOwnerRegistry(authority)
    campaign_root = (harness.path.parent / "campaign").resolve()
    materializer = WorkspaceMaterializer(
        str(campaign_root),
        editable_patterns=("*.py",),
    )
    code_owner = HypothesisCodeSourceOwner(
        CampaignWorkspaceAuthority(materializer),
        ConnectionScopedChampionStore(authority),
    )
    context_manager = ContextManager(
        hypothesis_problem_evidence=_problem_evidence()
    )
    prompt_owner = ProposalPromptProjectionAuthority()
    proposal_owner = ProposalAttemptOwner(authority)
    transport = _Transport()
    provider_owner = ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(harness.path.parent / "restart-traces"),
    )
    authorities = generation._install_checkpoint_a_authorities(
        registry=registry,
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider=provider_owner,
    )
    contract_gate: ContractGate | None = None
    target_factory: HypothesisTargetFactory | None = None
    checkpoint_b_authorities: generation._CheckpointBAuthorities | None = None
    if harness.contract_gate is not None:
        spec = ProblemSpec(
            name="registry-checkpoint-b-restart",
            root_dir=str(campaign_root),
            operator_categories=["solution_pool_search"],
            research_surfaces=[
                SimpleNamespace(
                    name="solution_pool_search",
                    kind="operator",
                    targets=SimpleNamespace(
                        files=["solution_pool.py"],
                        create_new_allowed=False,
                        modify_allowed=True,
                        remove_allowed=False,
                    ),
                )
            ],
            search_space=SearchSpace(
                editable=["solution_pool.py"],
                frozen=[],
                import_whitelist=[],
            ),
            solver=SolverConfig(),
        )
        contract_gate = ContractGate(spec)
        target_factory = HypothesisTargetFactory(
            taxonomy={
                "version": "v1",
                "families": ["solution_pool_search"],
                "aliases": {
                    "solution_pool_search": ["solution pool", "bounded elite"]
                },
            },
            clock_authority=ClockAuthority(
                lambda: datetime(
                    2026,
                    7,
                    17,
                    1,
                    2,
                    7,
                    tzinfo=timezone.utc,
                )
            ),
            uuid_authority=UUIDAuthority(
                lambda: uuid.UUID("22222222-2222-4222-8222-222222222222")
            ),
        )
        checkpoint_b_authorities = generation._extend_checkpoint_b_authorities(
            authorities,
            contract_gate=contract_gate,
            target_factory=target_factory,
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
    if checkpoint_b_authorities is not None:
        assert contract_gate is not None and target_factory is not None
        contract_gate._install_hypothesis_generation_authority(
            checkpoint_b_authorities.contract_gate
        )
        target_factory._install_hypothesis_generation_authority(
            checkpoint_b_authorities.target_factory
        )
    registry._install_hypothesis_generation_components(
        code_source_owner=code_owner,
        context_manager=context_manager,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider_owner=provider_owner,
        registry_authority=authorities.registry,
        provider_authority=authorities.provider,
        contract_gate=contract_gate,
        target_factory=target_factory,
        contract_gate_authority=(
            None
            if checkpoint_b_authorities is None
            else checkpoint_b_authorities.contract_gate
        ),
        target_factory_authority=(
            None
            if checkpoint_b_authorities is None
            else checkpoint_b_authorities.target_factory
        ),
        runtime_mode="direct_v3",
        problem_id="cvrp",
        problem_spec_hash=_digest(b"problem-spec"),
        split_manifest_hash=_digest(b"split-manifest"),
        seed_ledger_hash=_digest(b"seed-ledger"),
    )
    restore = registry.begin_restore()
    registry.seal_live(restore)
    transport.registry = registry
    restarted = _Harness(
        path=harness.path,
        authority=authority,
        registry=registry,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider_owner=provider_owner,
        transport=transport,
        registry_authority=authorities.registry,
        contract_gate=contract_gate,
        target_factory=target_factory,
    )
    _LIVE_HARNESSES.append(restarted)
    return restarted


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


def _checkpoint_b_generated_result(
    harness: _Harness,
) -> tuple[
    generation.HypothesisGenerationView,
    generation.GeneratedHypothesisResult,
]:
    view, prompt, permit = _start(harness)
    result = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(result) is generation.GeneratedHypothesisResult
    harness.registry.observe_hypothesis_generation_outcome(view, result)
    return view, result


def _checkpoint_b_approved_target(
    harness: _Harness,
) -> tuple[
    generation.HypothesisGenerationView,
    generation.ApprovedHypothesisTarget,
]:
    assert harness.contract_gate is not None
    assert harness.target_factory is not None
    view, result = _checkpoint_b_generated_result(harness)
    approval = harness.contract_gate.validate_generated_hypothesis(result)
    assert type(approval) is generation.HypothesisContractApproval
    target = harness.target_factory.create_approved_target(approval)
    return view, target


def _prepare_checkpoint_b_creation(
    harness: _Harness,
) -> tuple[
    generation.HypothesisGenerationView,
    generation.HypothesisCreationView,
]:
    view, target = _checkpoint_b_approved_target(harness)
    creation_view = harness.registry.prepare_hypothesis_creation(view, target)
    return view, creation_view


@pytest.mark.parametrize("boundary", ("claim", "issue"))
def test_checkpoint_b_contract_call_boundary_fault_becomes_unknown_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    assert harness.contract_gate is not None
    view, result = _checkpoint_b_generated_result(harness)
    name = (
        "_claim_generated_result_for_contract"
        if boundary == "claim"
        else "_issue_hypothesis_contract_approval"
    )
    original = getattr(generation, name)

    def call_then_raise(*args: object, **kwargs: object) -> object:
        original(*args, **kwargs)
        raise RuntimeError(f"Contract {boundary} crossed call boundary")

    monkeypatch.setattr(generation, name, call_then_raise)
    with pytest.raises(HypothesisContractUnknownError):
        harness.contract_gate.validate_generated_hypothesis(result)

    assert harness.registry.settle_hypothesis_creation_unknown(view) == (
        "contract_unknown"
    )
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


def test_checkpoint_b_contract_rejection_issue_boundary_becomes_unknown_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    assert harness.contract_gate is not None
    original_transport = harness.transport.call_with_tool

    def invalid_target(*args: object, **kwargs: object) -> dict[str, object]:
        payload = original_transport(*args, **kwargs)
        payload["target_file"] = "outside.py"
        return payload

    monkeypatch.setattr(harness.transport, "call_with_tool", invalid_target)
    view, result = _checkpoint_b_generated_result(harness)
    original_issue = generation._issue_hypothesis_contract_rejection

    def issue_then_raise(*args: object, **kwargs: object) -> object:
        original_issue(*args, **kwargs)
        raise RuntimeError("Contract rejection crossed call boundary")

    monkeypatch.setattr(
        generation,
        "_issue_hypothesis_contract_rejection",
        issue_then_raise,
    )
    with pytest.raises(HypothesisContractUnknownError):
        harness.contract_gate.validate_generated_hypothesis(result)

    assert harness.registry.settle_hypothesis_creation_unknown(view) == (
        "contract_unknown"
    )
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


@pytest.mark.parametrize("boundary", ("claim", "issue"))
def test_checkpoint_b_target_call_boundary_fault_becomes_unknown_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    assert harness.contract_gate is not None
    assert harness.target_factory is not None
    view, result = _checkpoint_b_generated_result(harness)
    approval = harness.contract_gate.validate_generated_hypothesis(result)
    assert type(approval) is generation.HypothesisContractApproval
    name = (
        "_claim_contract_approval_for_target"
        if boundary == "claim"
        else "_issue_approved_hypothesis_target"
    )
    original = getattr(generation, name)

    def call_then_raise(*args: object, **kwargs: object) -> object:
        original(*args, **kwargs)
        raise RuntimeError(f"target {boundary} crossed call boundary")

    monkeypatch.setattr(generation, name, call_then_raise)
    with pytest.raises(HypothesisTargetUnknownError):
        harness.target_factory.create_approved_target(approval)

    assert harness.registry.settle_hypothesis_creation_unknown(view) == (
        "target_unknown"
    )
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


def test_checkpoint_b_creation_view_issue_then_raise_becomes_unknown_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    view, target = _checkpoint_b_approved_target(harness)
    original = generation._issue_hypothesis_creation_view

    def issue_then_raise(*args: object, **kwargs: object) -> object:
        original(*args, **kwargs)
        raise RuntimeError("creation-view issue crossed call boundary")

    monkeypatch.setattr(
        generation,
        "_issue_hypothesis_creation_view",
        issue_then_raise,
    )
    with pytest.raises(RuntimeError, match="creation-view issue crossed"):
        harness.registry.prepare_hypothesis_creation(view, target)

    assert harness.registry.settle_hypothesis_creation_unknown(view) == (
        "creation_unknown"
    )
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


def test_checkpoint_b_target_claim_then_raise_becomes_creation_unknown_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    view, target = _checkpoint_b_approved_target(harness)
    original = generation._claim_approved_target_for_creation

    def claim_then_raise(*args: object, **kwargs: object) -> object:
        original(*args, **kwargs)
        raise RuntimeError("target claim crossed call boundary")

    monkeypatch.setattr(
        generation,
        "_claim_approved_target_for_creation",
        claim_then_raise,
    )
    with pytest.raises(RuntimeError, match="target claim crossed"):
        harness.registry.prepare_hypothesis_creation(view, target)

    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.registry.settle_hypothesis_creation_unknown(view) == (
        "creation_unknown"
    )
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        original(harness.registry_authority, view, target)


def test_checkpoint_b_creation_view_claim_then_raise_is_spent_and_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original = generation._claim_hypothesis_creation_view

    def claim_then_raise(*args: object, **kwargs: object) -> object:
        original(*args, **kwargs)
        raise RuntimeError("creation-view claim crossed call boundary")

    monkeypatch.setattr(
        generation,
        "_claim_hypothesis_creation_view",
        claim_then_raise,
    )
    with pytest.raises(RuntimeError, match="creation-view claim crossed"):
        harness.registry.commit_hypothesis_creation(creation_view)

    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.registry._availability is subject._Availability.CLEAR
    assert _event_statuses(harness.path) == ["started"]
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        original(harness.registry_authority, creation_view)


def test_checkpoint_b_hidden_authorization_is_discarded_after_return_fault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original = subject.ProposalAttemptOwner.begin_generated_hypothesis_creation_in

    def register_then_raise(
        self: subject.ProposalAttemptOwner,
        *args: object,
        **kwargs: object,
    ) -> object:
        original(self, *args, **kwargs)
        raise RuntimeError("authorization crossed call boundary")

    monkeypatch.setattr(
        subject.ProposalAttemptOwner,
        "begin_generated_hypothesis_creation_in",
        register_then_raise,
    )
    with pytest.raises(RuntimeError, match="authorization crossed"):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert harness.proposal_owner._ProposalAttemptOwner__creation_states == {}
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.registry._availability is subject._Availability.CLEAR
    assert _event_statuses(harness.path) == ["started"]


def test_checkpoint_b_generic_registration_boundary_leaves_only_closed_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original = owner_transaction._register_hypothesis_creation_authorization
    captured: list[object] = []

    def register_then_raise(*args: object, **kwargs: object) -> object:
        authorization = original(*args, **kwargs)
        captured.extend((authorization, args[2]))
        raise RuntimeError("generic authorization crossed call boundary")

    monkeypatch.setattr(
        owner_transaction,
        "_register_hypothesis_creation_authorization",
        register_then_raise,
    )
    with pytest.raises(RuntimeError, match="generic authorization crossed"):
        harness.registry.commit_hypothesis_creation(creation_view)

    authorization, ledger = captured
    authorization_state = owner_transaction._CREATION_AUTHORIZATION_STATES[
        authorization
    ]
    ledger_state = owner_transaction._lookup_ledger(ledger)
    assert authorization_state.ledger_ref() is ledger
    assert ledger_state.phase is owner_transaction._LedgerPhase.CLOSED
    assert harness.proposal_owner._ProposalAttemptOwner__creation_states == {}
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert _event_statuses(harness.path) == ["started"]


def test_checkpoint_b_active_lease_preflight_precedes_result_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            "INSERT INTO candidate_evaluation_leases VALUES (?, ?, ?, ?)",
            ("active-lease", "branch-1", None, "active"),
        )
    original = generation._claim_generated_result_for_creation
    claim_calls = 0

    def counted_claim(*args: object, **kwargs: object) -> object:
        nonlocal claim_calls
        claim_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        generation,
        "_claim_generated_result_for_creation",
        counted_claim,
    )
    with pytest.raises(
        InvalidStartedHypothesisAttemptError,
        match="active evaluation lease",
    ):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert claim_calls == 0
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD


def test_checkpoint_b_commits_one_complete_group_and_publishes_once(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)

    target = harness.registry.commit_hypothesis_creation(creation_view)

    assert target.owner_revision == 0
    assert target.value().status == "active"
    assert target.value().parent_hypothesis_id == "hypothesis-prior"
    assert target.canonical_storage_payload_json.decode("utf-8").endswith("}")
    assert b"2026-07-17T01:02:06.000000+00:00" in (
        target.canonical_storage_payload_json
    )
    assert _event_statuses(harness.path) == ["started", "generated"]
    with sqlite3.connect(harness.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM proposal_hypothesis_attempt_bindings"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT owner_revision, status FROM hypotheses WHERE hypothesis_id = ?",
            (target.hypothesis_id,),
        ).fetchone() == (0, "active")
    published = harness.registry._owner_state
    assert published is not prior_root
    assert published.publication_generation == prior_root.publication_generation + 1
    assert published.hypothesis_slots.by_id[target.hypothesis_id].owner == target
    assert (
        published.hypothesis_slots.current_by_branch["branch-1"]
        == target.hypothesis_id
    )
    assert "branch-1" not in harness.registry._hypothesis_generation_reservations
    assert harness.transport.calls == 1
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        inventory = (
            harness.proposal_owner
            ._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
        )
    assert subject._restore_generation_holds(
        inventory,
        published,
        creation_aware=True,
    ) == {}
    assert set(
        subject._restore_generation_holds(
            inventory,
            prior_root,
            creation_aware=True,
        )
    ) == {"branch-1"}
    assert subject._restore_generation_holds(
        inventory,
        prior_root,
        creation_aware=False,
    ) == {}


def test_checkpoint_b_commit_then_raise_classifies_and_publishes_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original_commit = subject._sqlite._commit_coordinated_transaction

    def commit_then_raise(*args: object, **kwargs: object) -> None:
        original_commit(*args, **kwargs)
        raise RuntimeError("uncertain commit return")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        commit_then_raise,
    )
    target = harness.registry.commit_hypothesis_creation(creation_view)

    assert target.hypothesis_id in harness.registry._owner_state.hypothesis_slots.by_id
    assert _event_statuses(harness.path) == ["started", "generated"]
    assert harness.transport.calls == 1


def test_checkpoint_b_snapshot_fault_uses_one_read_and_never_publishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original_commit = subject._sqlite._commit_coordinated_transaction
    snapshot_calls = 0

    def commit_then_raise(*args: object, **kwargs: object) -> None:
        original_commit(*args, **kwargs)
        raise RuntimeError("uncertain commit return")

    def fail_snapshot(*_args: object, **_kwargs: object) -> object:
        nonlocal snapshot_calls
        snapshot_calls += 1
        raise RuntimeError("classification snapshot unavailable")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        commit_then_raise,
    )
    monkeypatch.setattr(
        subject._sqlite,
        "_independent_authority_read_snapshot",
        fail_snapshot,
    )
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert snapshot_calls == 1
    assert harness.registry._owner_state is prior_root
    assert harness.registry._availability is subject._Availability.PERMANENT_HOLD
    assert harness.transport.calls == 1


def test_checkpoint_b_global_mixed_classification_never_publishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original_commit = subject._sqlite._commit_coordinated_transaction
    original_snapshot = subject._sqlite._independent_authority_read_snapshot
    snapshot_calls = 0

    def commit_then_raise(*args: object, **kwargs: object) -> None:
        original_commit(*args, **kwargs)
        raise RuntimeError("uncertain commit return")

    def counted_snapshot(*args: object, **kwargs: object) -> object:
        nonlocal snapshot_calls
        snapshot_calls += 1
        return original_snapshot(*args, **kwargs)

    def classify_mixed(*_args: object, **_kwargs: object) -> object:
        return ProposalAttemptCommitClassification.MIXED

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        commit_then_raise,
    )
    monkeypatch.setattr(
        subject._sqlite,
        "_independent_authority_read_snapshot",
        counted_snapshot,
    )
    monkeypatch.setattr(ProposalAttemptOwner, "_classify", classify_mixed)
    with pytest.raises(subject.CampaignOwnerIntegrityHoldError):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert snapshot_calls == 1
    assert harness.registry._owner_state is prior_root
    assert harness.registry._availability is subject._Availability.PERMANENT_HOLD
    assert harness.transport.calls == 1


def test_checkpoint_b_post_publication_settlement_fault_holds_globally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original_settle = ProposalAttemptOwner._settle

    def settle_then_raise(
        self: ProposalAttemptOwner,
        *args: object,
        **kwargs: object,
    ) -> None:
        original_settle(self, *args, **kwargs)
        raise RuntimeError("settlement crossed call boundary")

    monkeypatch.setattr(ProposalAttemptOwner, "_settle", settle_then_raise)
    with pytest.raises(subject.CampaignOwnerCleanupError):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert harness.registry._owner_state is not prior_root
    assert harness.registry._availability is subject._Availability.PERMANENT_HOLD
    assert _event_statuses(harness.path) == ["started", "generated"]
    assert harness.transport.calls == 1


def test_checkpoint_b_completed_deactivation_fault_reports_cleanup_after_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original = subject._sqlite._deactivate_coordinated_transaction

    def deactivate_then_raise(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        raise RuntimeError("deactivation crossed call boundary")

    monkeypatch.setattr(
        subject._sqlite,
        "_deactivate_coordinated_transaction",
        deactivate_then_raise,
    )
    with pytest.raises(subject.CampaignOwnerCleanupError):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert harness.registry._owner_state is not prior_root
    assert harness.registry._availability is subject._Availability.CLEAR
    assert harness.registry._hypothesis_generation_reservations == {}
    assert _event_statuses(harness.path) == ["started", "generated"]


def test_checkpoint_b_close_before_effect_publishes_but_holds_globally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    prior_root = harness.registry._owner_state
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    original = subject._sqlite._close_coordinated_transaction

    def fail_before_close(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("close failed before effect")

    monkeypatch.setattr(
        subject._sqlite,
        "_close_coordinated_transaction",
        fail_before_close,
    )
    with pytest.raises(subject.CampaignOwnerCleanupError):
        harness.registry.commit_hypothesis_creation(creation_view)

    session = subject._sqlite._thread_session_owner()
    assert type(session) is subject._sqlite._CoordinatedTransactionSession
    session_state = subject._sqlite._lookup_session_state(session)
    assert not subject._sqlite._session_resources_closed(session, session_state)
    assert harness.registry._owner_state is not prior_root
    assert harness.registry._availability is subject._Availability.PERMANENT_HOLD
    assert _event_statuses(harness.path) == ["started", "generated"]

    monkeypatch.setattr(
        subject._sqlite,
        "_close_coordinated_transaction",
        original,
    )
    original(session, harness.authority)


def test_checkpoint_b_restore_does_not_downgrade_generated_group_without_binding_table(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    harness.registry.commit_hypothesis_creation(creation_view)
    with sqlite3.connect(harness.path) as connection:
        connection.execute("DROP TABLE proposal_hypothesis_attempt_bindings")
    with sqlite_connection._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        inventory = (
            harness.proposal_owner
            ._load_hypothesis_attempt_inventory_from_snapshot(snapshot)
        )

    assert inventory.groups[0].disposition is subject._AttemptGroupDisposition.RESOLVED
    assert inventory.groups[0].binding is None
    assert set(
        subject._restore_generation_holds(
            inventory,
            harness.registry._owner_state,
            creation_aware=True,
        )
    ) == {"branch-1"}


def test_checkpoint_b_successful_creation_survives_full_registry_restore(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    target = harness.registry.commit_hypothesis_creation(creation_view)

    restarted = _restart_registry_from_storage(harness)
    restored = restarted.registry

    slot = restored._owner_state.hypothesis_slots.by_id[target.hypothesis_id]
    assert slot.owner == target
    assert (
        restored._owner_state.hypothesis_slots.current_by_branch["branch-1"]
        == target.hypothesis_id
    )
    assert restored._hypothesis_generation_reservations == {}
    assert restored.acquire_branch_mutation("branch-1").owner.branch_id == "branch-1"
    generation._require_authority(
        restarted.registry_authority,
        role=generation._AuthorityRole.REGISTRY,
        owner=restored,
    )
    branch_two_view = restored.acquire_hypothesis_generation("branch-2")
    assert restored.abort_hypothesis_generation(branch_two_view) is None


@pytest.mark.parametrize("partial", ("missing_hypothesis", "missing_binding_table"))
def test_checkpoint_b_partial_creation_group_restores_branch_local_hold(
    tmp_path: Path,
    partial: str,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)
    target = harness.registry.commit_hypothesis_creation(creation_view)
    with sqlite3.connect(harness.path) as connection:
        if partial == "missing_hypothesis":
            connection.execute(
                "DELETE FROM hypotheses WHERE hypothesis_id = ?",
                (target.hypothesis_id,),
            )
        else:
            connection.execute("DROP TABLE proposal_hypothesis_attempt_bindings")

    restored = _restart_registry_from_storage(harness).registry

    reservation = restored._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    with pytest.raises(subject.HypothesisGenerationReservationHoldError):
        restored.acquire_branch_mutation("branch-1")
    assert restored.acquire_branch_mutation("branch-2").owner.branch_id == "branch-2"


def test_checkpoint_a_restore_remains_compatible_without_binding_table(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=False)
    with sqlite3.connect(harness.path) as connection:
        connection.execute("DROP TABLE proposal_hypothesis_attempt_bindings")

    restored = _restart_registry_from_storage(harness).registry

    assert restored._hypothesis_generation_reservations == {}
    assert restored.acquire_branch_mutation("branch-1").owner.branch_id == "branch-1"


def test_checkpoint_b_malformed_generated_event_keeps_failure_branch_local(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    payload = _unresolved_start_payload()
    payload.update(
        attempt_id="malformed-generated-only",
        status="generated",
        transition_reason="generated",
        hypothesis_id="hypothesis-prior",
        hypothesis_digest=_digest(b"malformed-generated-proposal"),
    )
    prompt = payload["prompt_call"]
    assert isinstance(prompt, dict)
    prompt.update(
        trace_ref="artifact://trace",
        prompt_manifest_ref="artifact://manifest",
        raw_response_ref="artifact://response",
        provider_ok=True,
        ok=True,
        error_category=None,
        error_type=None,
    )
    with sqlite3.connect(harness.path) as connection:
        connection.execute(
            """
            INSERT INTO experiment_events (
                event_id, campaign_id, branch_id, hypothesis_id,
                timestamp, event_kind, stage, audit_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-malformed-generated-only",
                "campaign-a",
                "branch-1",
                "hypothesis-prior",
                "2026-07-17T01:04:00.000000+00:00",
                "proposal_attempt_transition",
                "proposal_hypothesis",
                _canonical(payload),
            ),
        )

    restored = _restart_registry_from_storage(harness).registry

    reservation = restored._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert restored.acquire_branch_mutation("branch-2").owner.branch_id == "branch-2"


def test_checkpoint_b_rolled_back_creation_spends_view_and_holds_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    _view, creation_view = _prepare_checkpoint_b_creation(harness)

    def fail_commit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("creation commit failed")

    monkeypatch.setattr(
        subject._sqlite,
        "_commit_coordinated_transaction",
        fail_commit,
    )
    with pytest.raises(RuntimeError, match="creation commit failed"):
        harness.registry.commit_hypothesis_creation(creation_view)

    assert _event_statuses(harness.path) == ["started"]
    with sqlite3.connect(harness.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM proposal_hypothesis_attempt_bindings"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM hypotheses"
        ).fetchone() == (1,)
    reservation = harness.registry._hypothesis_generation_reservations["branch-1"]
    assert reservation.phase is subject._GenerationReservationPhase.UNCERTAIN_HOLD
    assert harness.registry._availability is subject._Availability.CLEAR
    assert harness.transport.calls == 1
    with pytest.raises(subject.CampaignOwnerLifecycleError):
        harness.registry.commit_hypothesis_creation(creation_view)


def test_checkpoint_b_contract_rejection_uses_terminal_receipt_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path, checkpoint_b=True)
    assert harness.contract_gate is not None
    original_transport = harness.transport.call_with_tool

    def invalid_target(*args: object, **kwargs: object) -> dict[str, object]:
        payload = original_transport(*args, **kwargs)
        payload["target_file"] = "outside.py"
        return payload

    monkeypatch.setattr(harness.transport, "call_with_tool", invalid_target)
    view, prompt, permit = _start(harness)
    result = harness.provider_owner.call_hypothesis(permit, prompt)
    assert type(result) is generation.GeneratedHypothesisResult
    harness.registry.observe_hypothesis_generation_outcome(view, result)
    rejection = harness.contract_gate.validate_generated_hypothesis(result)
    assert type(rejection) is generation.HypothesisContractRejection
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.contract_gate.validate_generated_hypothesis(result)

    receipt = harness.registry.terminalize_hypothesis_generation(view, rejection)

    assert type(receipt) is generation.TerminalAttemptReceipt
    assert _event_statuses(harness.path) == ["started", "failed"]
    with sqlite3.connect(harness.path) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT audit_payload_json FROM experiment_events "
                "ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()[0]
        )
    assert payload["transition_reason"] == "hypothesis_contract_rejected"
    assert payload["failure_lane"] == "invalid_response"
    assert "branch-1" not in harness.registry._hypothesis_generation_reservations
    assert harness.transport.calls == 1


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
