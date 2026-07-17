from __future__ import annotations

import contextvars
import copy
import hashlib
import json
import pickle
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scion.config.problem import ProblemSpec, SearchSpace, SolverConfig
from scion.contract.gate import ContractGate
from scion.core.models import (
    Branch,
    BranchState,
    HypothesisProposal,
    HypothesisRecord,
)
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)
from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal.hypothesis_target_factory import (
    ClockAuthority,
    HypothesisTargetFactory,
    UUIDAuthority,
)


def _canonical(value: object, *, sort_keys: bool = True) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _spec(*, as_mapping: bool = True) -> ProblemSpec:
    surface: object = {
        "name": "local_search",
        "kind": "operator",
        "targets": {
            "files": ["operators/*.py"],
            "create_new_allowed": True,
            "modify_allowed": True,
            "remove_allowed": False,
        },
    }
    if not as_mapping:
        from types import SimpleNamespace

        surface = SimpleNamespace(
            name="local_search",
            kind="operator",
            targets=SimpleNamespace(
                files=["operators/*.py"],
                create_new_allowed=True,
                modify_allowed=True,
                remove_allowed=False,
            ),
        )
    return ProblemSpec(
        name="checkpoint-b",
        root_dir="/tmp/checkpoint-b",
        operator_categories=["local_search"],
        research_surfaces=[surface],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=[],
            import_whitelist=[],
        ),
        solver=SolverConfig(),
    )


def _branch_owner() -> RevisionedBranchRecord:
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    return RevisionedBranchRecord.from_value(
        Branch(
            branch_id="branch-b",
            state=BranchState.EXPLORE,
            base_champion_id=17,
            base_champion_hash="champion-hash",
            created_at=now,
            updated_at=now,
        ),
        4,
    )


def _prior_owner(created_at: datetime) -> RevisionedHypothesisRecord:
    return RevisionedHypothesisRecord.from_generated_value(
        HypothesisRecord(
            hypothesis_id="prior-h",
            branch_id="branch-b",
            change_locus="local_search",
            action="create_new",
            status="active",
            hypothesis_text="prior",
            created_at=created_at,
            proposal_digest=_digest(b"prior"),
        ),
        2,
    )


@dataclass(frozen=True)
class _Harness:
    authorities: generation._CheckpointAAuthorities
    b_authorities: generation._CheckpointBAuthorities
    gate: ContractGate
    factory: HypothesisTargetFactory
    view: generation.HypothesisGenerationView
    prompt: generation.BoundHypothesisPrompt
    started: generation.StartedHypothesisAttempt
    result: generation.GeneratedHypothesisResult


_KEEPALIVE: list[tuple[object, ...]] = []


def _harness(
    *,
    spec: ProblemSpec | None = None,
    now: datetime | None = None,
    prior: RevisionedHypothesisRecord | None = None,
    proposal_overrides: dict[str, object] | None = None,
    c0_governance: dict[str, object] | None = None,
) -> _Harness:
    problem_spec = spec or _spec()
    gate = ContractGate(problem_spec)
    clock = ClockAuthority(
        lambda: now or datetime(2026, 7, 17, 10, 0, 0, 5, tzinfo=timezone.utc)
    )
    uuid_authority = UUIDAuthority(
        lambda: uuid.UUID("11111111-1111-4111-8111-111111111111")
    )
    factory = HypothesisTargetFactory(
        taxonomy={
            "version": "v7",
            "families": ["bounded_search", "NEW_FAMILY"],
            "aliases": {"bounded_search": ["bounded move"]},
        },
        clock_authority=clock,
        uuid_authority=uuid_authority,
    )
    owners = tuple(object() for _ in range(6))
    authorities = generation._install_checkpoint_a_authorities(
        registry=owners[0],
        code_source_owner=owners[1],
        context_manager=owners[2],
        prompt_owner=owners[3],
        proposal_owner=owners[4],
        provider=owners[5],
    )
    b_authorities = generation._extend_checkpoint_b_authorities(
        authorities,
        contract_gate=gate,
        target_factory=factory,
    )
    gate._install_hypothesis_generation_authority(b_authorities.contract_gate)
    factory._install_hypothesis_generation_authority(b_authorities.target_factory)
    _KEEPALIVE.append((*owners, gate, factory, authorities, b_authorities))
    view = generation._issue_generation_view(
        authorities.registry,
        root_identity=object(),
        root_generation=9,
        branch_owner=_branch_owner(),
        hypothesis_bundle=(() if prior is None else (prior,)),
        prior_head=prior,
        reservation_id="reservation-b",
        h_bundle_digest=_digest(b"H-bundle"),
        owner_context_json=_canonical({"branch_id": "branch-b"}),
        contract_gate_authority=b_authorities.contract_gate,
        target_factory_authority=b_authorities.target_factory,
        contract_config_digest=gate.hypothesis_contract_config_digest,
        contract_protocol_generation=gate.hypothesis_contract_protocol_generation,
        target_factory_config_digest=factory.target_factory_config_digest,
        target_factory_protocol_generation=(
            factory.target_factory_protocol_generation
        ),
        taxonomy_digest=factory.taxonomy_digest,
    )
    request = generation._issue_code_source_request(authorities.registry, view)
    generation._claim_code_source_request(authorities.code_source_owner, request)
    source = generation._issue_code_source(
        authorities.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_digest(b"manifest"),
        code_hash=_digest(b"code"),
        snapshot_hash=_digest(b"snapshot"),
        entries=(),
    )
    generation._inspect_code_source(authorities.registry, source, view=view)
    generation._claim_code_source_for_evidence(authorities.context_manager, source)
    evidence = generation._issue_problem_evidence(
        authorities.context_manager,
        source,
        provider_context_json=b"{}",
        governance_json=b"{}",
    )
    prompt_source = generation._issue_prompt_source(
        authorities.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )
    generation._claim_prompt_source(authorities.prompt_owner, prompt_source)
    governance = {} if c0_governance is None else c0_governance
    c0 = _canonical(governance, sort_keys=False)
    prompt = generation._issue_bound_prompt(
        authorities.prompt_owner,
        prompt_source,
        context_snapshot=object(),
        provider_context_json=b"{}",
        provider_snapshot_bytes=b"{}",
        context_digest=_digest(b"context"),
        prompt_hash=_digest(b"prompt"),
        provider_tool_digest=_digest(b"tool"),
        governance_digest=_digest(
            _canonical(
                {
                    "schema_version": "proposal-governance-envelope.v1",
                    "governance": governance,
                },
                sort_keys=False,
            )
        ),
        c0_governance_json=c0,
    )
    generation._inspect_bound_prompt(authorities.registry, prompt, view=view)
    generation._begin_started_attempt(authorities.registry, view, prompt)
    prompt_projection = generation._claim_bound_prompt_for_start(
        authorities.proposal_owner,
        prompt,
    )
    started = generation._issue_started_attempt(
        authorities.proposal_owner,
        stored_event=object(),
        attempt_id="attempt-b",
        started_event_id="event-b",
        campaign_id="campaign-b",
        branch_id="branch-b",
        context_digest=prompt_projection.context_digest,
        prompt_hash=prompt_projection.prompt_hash,
        event_storage_sha256=_digest(b"START"),
        bound_prompt=prompt,
    )
    generation._inspect_started_attempt(authorities.registry, started, view=view)
    permit = generation._issue_provider_permit(
        authorities.registry,
        authorities.provider,
        view=view,
        started_attempt=started,
        bound_prompt=prompt,
    )
    generation._claim_provider_permit(authorities.provider, permit, prompt)
    proposal: dict[str, object] = {
        "action": "create_new",
        "change_locus": "local_search",
        "expected_effect": "improve",
        "hypothesis_text": "add bounded move",
        "predicted_direction": "improve",
        "suggested_weight": None,
        "target_file": "operators/new_move.py",
        "target_weakness": "missing move",
    }
    proposal.update(proposal_overrides or {})
    proposal_bytes = _canonical(proposal)
    result = generation._issue_generated_result(
        authorities.provider,
        permit,
        receipt=object(),
        trace_ref="trace",
        prompt_manifest_ref="manifest",
        raw_response_ref="response",
        proposal_canonical_bytes=proposal_bytes,
        proposal_sha256=_digest(proposal_bytes),
        provider_ok=True,
        ok=True,
        error_category=None,
        error_type=None,
        trace_persistence_error=None,
    )
    generation._inspect_generation_outcome(
        authorities.registry,
        permit=permit,
        outcome=result,
        view=view,
    )
    return _Harness(
        authorities=authorities,
        b_authorities=b_authorities,
        gate=gate,
        factory=factory,
        view=view,
        prompt=prompt,
        started=started,
        result=result,
    )


def test_contract_freezes_mapping_and_object_specs_after_composition() -> None:
    for as_mapping in (True, False):
        spec = _spec(as_mapping=as_mapping)
        harness = _harness(spec=spec)
        spec.operator_categories[:] = ["mutated"]
        raw_surface = spec.research_surfaces[0]
        if isinstance(raw_surface, dict):
            raw_surface["name"] = "mutated"
        else:
            raw_surface.name = "mutated"
        approval = harness.gate.validate_generated_hypothesis(harness.result)
        assert type(approval) is generation.HypothesisContractApproval


@pytest.mark.parametrize(
    "surface",
    [
        {
            "name": "local_search",
            "kind": "operator",
            "targets": {
                "files": ["operators/*.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
            },
        },
        pytest.param(
            SimpleNamespace(
                name="local_search",
                kind="operator",
                targets=SimpleNamespace(
                    files=["operators/*.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                ),
            ),
            id="object-v2-targets",
        ),
        pytest.param(
            SimpleNamespace(
                name="local_search",
                kind="operator",
                target_files=["operators/*.py"],
            ),
            id="object-legacy-default-flags",
        ),
        pytest.param(
            SimpleNamespace(
                name="local_search",
                kind="operator",
                targets={"files": ["ignored-by-SurfaceAccess/*.py"]},
                target_files=["operators/*.py"],
                create_new_allowed=False,
                modify_allowed=True,
                remove_allowed=False,
            ),
            id="object-with-mapping-targets",
        ),
    ],
    ids=lambda value: "mapping-surface" if isinstance(value, dict) else None,
)
@pytest.mark.parametrize(
    ("action", "target_file"),
    [
        ("create_new", "operators/new.py"),
        ("modify", "operators/existing.py"),
        ("remove", "operators/existing.py"),
        ("modify", "outside.py"),
    ],
)
def test_frozen_c1_c3_exactly_match_existing_contract_behavior(
    surface: object,
    action: str,
    target_file: str,
) -> None:
    spec = _spec()
    spec.research_surfaces[:] = [surface]
    gate = ContractGate(spec)
    proposal = HypothesisProposal(
        hypothesis_text="change one move",
        change_locus="local_search",
        action=action,  # type: ignore[arg-type]
        target_file=target_file,
        predicted_direction="improve",
        target_weakness="weak move",
        expected_effect="improve",
        suggested_weight=None,
    )

    legacy = (
        gate._c1_schema(proposal),
        gate._c2_change_locus(proposal),
        gate._c3_action_target(proposal),
    )
    frozen = (
        gate._frozen_c1_schema(proposal),
        gate._frozen_c2_change_locus(proposal),
        gate._frozen_c3_action_target(proposal),
    )

    assert [
        (check.name, check.passed, check.severity, check.detail)
        for check in frozen
    ] == [
        (check.name, check.passed, check.severity, check.detail)
        for check in legacy
    ]


@pytest.mark.parametrize(
    ("active_surfaces", "expected_type"),
    [
        (["local_search"], generation.HypothesisContractApproval),
        (["outside"], generation.HypothesisContractRejection),
    ],
)
def test_frozen_c0_c3_exactly_match_public_contract_behavior(
    active_surfaces: list[str],
    expected_type: type[object],
) -> None:
    governance = {"active_problem_boundary_surfaces": active_surfaces}
    harness = _harness(c0_governance=governance)
    decision = harness.gate.validate_generated_hypothesis(harness.result)
    assert type(decision) is expected_type
    states = (
        generation._CONTRACT_APPROVAL_STATES
        if type(decision) is generation.HypothesisContractApproval
        else generation._CONTRACT_REJECTION_STATES
    )
    frozen_result = states[decision].projection.contract_result
    proposal = HypothesisProposal(
        hypothesis_text="add bounded move",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_move.py",
        predicted_direction="improve",
        target_weakness="missing move",
        expected_effect="improve",
        suggested_weight=None,
    )
    public_result = harness.gate.validate_hypothesis(
        proposal,
        governance_envelope=SimpleNamespace(to_primitive=lambda: governance),
    )

    assert public_result.passed is frozen_result.passed
    assert [
        (check.name, check.passed, check.severity, check.detail)
        for check in frozen_result.checks
    ] == [
        (check.name, check.passed, check.severity, check.detail)
        for check in public_result.checks
    ]


def test_frozen_target_patterns_bind_normalized_semantics_and_fail_closed() -> None:
    def _gate(pattern: str) -> ContractGate:
        spec = _spec()
        spec.research_surfaces[:] = [
            SimpleNamespace(
                name="local_search",
                kind="operator",
                targets=SimpleNamespace(
                    files=[pattern],
                    create_new_allowed=True,
                    modify_allowed=True,
                    remove_allowed=False,
                ),
            )
        ]
        return ContractGate(spec)

    assert (
        _gate("operators/*.py").hypothesis_contract_config_digest
        == _gate("/operators/*.py").hypothesis_contract_config_digest
    )
    files = ["operators/*.py"]
    spec = _spec()
    spec.research_surfaces[:] = [
        SimpleNamespace(
            name="local_search",
            kind="operator",
            targets=SimpleNamespace(
                files=files,
                create_new_allowed=True,
                modify_allowed=True,
                remove_allowed=False,
            ),
        )
    ]
    frozen_gate = ContractGate(spec)
    frozen_digest = frozen_gate.hypothesis_contract_config_digest
    files[:] = ["replacement/*.py"]
    assert frozen_gate.hypothesis_contract_config_digest == frozen_digest
    proposal = HypothesisProposal(
        hypothesis_text="modify one operator",
        change_locus="local_search",
        action="modify",
        target_file="operators/existing.py",
        predicted_direction="improve",
        target_weakness="weak move",
        expected_effect="improve",
        suggested_weight=None,
    )
    assert frozen_gate._frozen_c3_action_target(proposal).passed is True
    for invalid in (
        "operators\\*.py",
        "operators//*.py",
        "../operators/*.py",
        " operators/*.py",
    ):
        with pytest.raises(ValueError, match="invalid hypothesis contract target"):
            _gate(invalid)


def test_nonempty_c0_is_sorted_frozen_and_post_bind_mutation_safe() -> None:
    governance: dict[str, object] = {
        "z_audit": {"second": 2, "first": 1},
        "active_problem_boundary_surfaces": ["local_search"],
    }
    harness = _harness(c0_governance=governance)
    prompt_projection = generation._BOUND_PROMPT_STATES[harness.prompt].projection
    expected = _canonical(governance)
    assert prompt_projection.c0_governance_json == expected
    expected_envelope = _canonical(
        {
            "governance": governance,
            "schema_version": "hypothesis-c0-governance.v1",
        }
    )
    assert prompt_projection.c0_governance_digest == _digest(expected_envelope)

    governance["active_problem_boundary_surfaces"] = ["outside"]
    nested = governance["z_audit"]
    assert isinstance(nested, dict)
    nested["first"] = 99
    approval = harness.gate.validate_generated_hypothesis(harness.result)
    assert type(approval) is generation.HypothesisContractApproval


def test_nonempty_c0_rejects_contradiction_and_cross_envelope_replacement() -> None:
    harness = _harness(
        c0_governance={"active_problem_boundary_surfaces": ["outside"]}
    )
    rejection = harness.gate.validate_generated_hypothesis(harness.result)
    assert type(rejection) is generation.HypothesisContractRejection

    first = {"alpha": {"x": 1, "y": 2}, "beta": [1, 2]}
    reordered = {"beta": [1, 2], "alpha": {"y": 2, "x": 1}}

    def _owner_digest(value: dict[str, object]) -> tuple[bytes, str]:
        raw = _canonical(value, sort_keys=False)
        envelope = _canonical(
            {
                "schema_version": "proposal-governance-envelope.v1",
                "governance": value,
            },
            sort_keys=False,
        )
        return raw, _digest(envelope)

    first_raw, first_digest = _owner_digest(first)
    reordered_raw, reordered_digest = _owner_digest(reordered)
    first_canonical, first_c0_digest = generation._canonical_c0_governance_bytes(
        first_raw,
        governance_digest=first_digest,
    )
    reordered_canonical, reordered_c0_digest = (
        generation._canonical_c0_governance_bytes(
            reordered_raw,
            governance_digest=reordered_digest,
        )
    )
    assert reordered_canonical == first_canonical
    assert reordered_c0_digest == first_c0_digest

    replacement_raw, _replacement_digest = _owner_digest(
        {"active_problem_boundary_surfaces": ["replacement"]}
    )
    with pytest.raises(
        generation.InvalidHypothesisGenerationCapabilityError,
        match="do not match governance digest",
    ):
        generation._canonical_c0_governance_bytes(
            replacement_raw,
            governance_digest=first_digest,
        )


def test_target_clock_rollback_and_exact_second_use_strict_generated_codec() -> None:
    prior_time = datetime(2026, 7, 17, 10, 0, 1, 999999, tzinfo=timezone.utc)
    harness = _harness(
        now=datetime(2026, 7, 17, 10, 0, 0, tzinfo=timezone.utc),
        prior=_prior_owner(prior_time),
    )
    approval = harness.gate.validate_generated_hypothesis(harness.result)
    assert type(approval) is generation.HypothesisContractApproval
    target = harness.factory.create_approved_target(approval)
    projection = generation._claim_approved_target_for_creation(
        harness.authorities.registry,
        harness.view,
        target,
    )
    assert type(projection.revision_zero_target) is RevisionedHypothesisRecord
    value = projection.revision_zero_target.value()
    assert value.created_at == datetime(2026, 7, 17, 10, 0, 2, tzinfo=timezone.utc)
    assert b'"created_at":"2026-07-17T10:00:02.000000+00:00"' in (
        projection.revision_zero_target.canonical_storage_payload_json
    )
    assert value.parent_hypothesis_id == "prior-h"
    assert value.base_champion_version == 17
    assert value.proposal_digest == _digest(
        generation._RESULT_STATES[harness.result].projection.proposal_canonical_bytes
    )
    creation = generation._issue_hypothesis_creation_view(
        harness.authorities.registry,
        harness.view,
        result=harness.result,
        approval=approval,
        target=target,
    )
    creation_projection = generation._claim_hypothesis_creation_view(
        harness.authorities.registry,
        creation,
    )
    assert creation_projection.result_projection.proposal_sha256 == value.proposal_digest
    assert creation_projection.revision_zero_target is projection.revision_zero_target
    spent = generation._spend_hypothesis_creation_view(
        harness.authorities.registry,
        creation,
    )
    assert spent is creation_projection
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        generation._spend_hypothesis_creation_view(
            harness.authorities.registry,
            creation,
        )


def test_owner_swap_reuse_and_creation_unknown_are_one_shot() -> None:
    harness = _harness()
    approval = harness.gate.validate_generated_hypothesis(harness.result)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.gate.validate_generated_hypothesis(harness.result)
    target = harness.factory.create_approved_target(approval)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.factory.create_approved_target(approval)
    generation._claim_approved_target_for_creation(
        harness.authorities.registry,
        harness.view,
        target,
    )
    generation._finish_hypothesis_creation_unknown(
        harness.authorities.registry,
        harness.view,
        target,
    )
    assert generation._settle_checkpoint_b_unknown(
        harness.authorities.registry,
        harness.view,
    ) == "creation_unknown"


def test_capabilities_and_bound_authorities_reject_copy_pickle_thread_context() -> None:
    harness = _harness()
    approval = harness.gate.validate_generated_hypothesis(harness.result)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
            operation(approval)
    copied = contextvars.copy_context()
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        copied.run(harness.factory.create_approved_target, approval)
    with ThreadPoolExecutor(max_workers=1) as pool:
        error = pool.submit(harness.factory.create_approved_target, approval).exception()
    assert isinstance(error, generation.HypothesisGenerationLifecycleError)


def test_contract_and_target_owner_swaps_fail_before_claim() -> None:
    first = _harness()
    second = _harness()
    with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
        second.gate.validate_generated_hypothesis(first.result)
    approval = first.gate.validate_generated_hypothesis(first.result)
    with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
        second.factory.create_approved_target(approval)
    target = first.factory.create_approved_target(approval)
    assert type(target) is generation.ApprovedHypothesisTarget


def test_taxonomy_clock_and_uuid_authorities_are_frozen_and_unswappable() -> None:
    taxonomy = {
        "version": "v1",
        "families": ["bounded_search"],
        "aliases": {"bounded_search": ["bounded move"]},
    }
    clock = ClockAuthority(
        lambda: datetime(2026, 7, 17, tzinfo=timezone.utc)
    )
    uuid_authority = UUIDAuthority(
        lambda: uuid.UUID("22222222-2222-4222-8222-222222222222")
    )
    factory = HypothesisTargetFactory(
        taxonomy=taxonomy,
        clock_authority=clock,
        uuid_authority=uuid_authority,
    )
    digest = factory.taxonomy_digest
    taxonomy["families"].append("mutated")
    taxonomy["aliases"]["bounded_search"].append("mutated")
    assert factory.taxonomy_digest == digest
    for authority in (clock, uuid_authority, factory):
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(Exception):
                operation(authority)


def test_contract_rejection_uses_terminal_receipt_path() -> None:
    harness = _harness(proposal_overrides={"change_locus": "outside"})
    rejection = harness.gate.validate_generated_hypothesis(harness.result)
    assert type(rejection) is generation.HypothesisContractRejection
    decision = generation._verify_hypothesis_contract_rejection(
        harness.authorities.registry,
        harness.view,
        rejection,
    )
    assert decision.contract_result.passed is False
    generation._begin_terminal_persistence(
        harness.authorities.registry,
        harness.view,
        rejection,
    )
    terminal = generation._claim_terminal_outcome(
        harness.authorities.proposal_owner,
        rejection,
        started_attempt=harness.started,
        bound_prompt=harness.prompt,
    )
    assert terminal.failure_category == "hypothesis_contract_rejected"
    receipt = generation._issue_terminal_receipt(
        harness.authorities.proposal_owner,
        terminal_event=object(),
        terminal_event_storage_sha256=_digest(b"terminal"),
        outcome=rejection,
        started_attempt=harness.started,
    )
    resolved = generation._resolve_terminal_receipt(
        harness.authorities.registry,
        receipt,
        started_attempt=harness.started,
        view=harness.view,
    )
    assert resolved.outcome is rejection
