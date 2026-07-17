from __future__ import annotations

import contextvars
import copy
import gc
import hashlib
import json
import pickle
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest

from scion.proposal import hypothesis_generation_authority as subject


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


_D1 = _digest(b"one")
_D2 = _digest(b"two")
_D3 = _digest(b"three")
_D4 = _digest(b"four")
_D5 = _digest(b"five")
_OWNER_CONTEXT = json.dumps(
    {
        "branch_id": "branch-a",
        "schema_version": "hypothesis-owner-context.v1",
    },
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")


@dataclass(frozen=True)
class _Owners:
    registry: object
    code_source_owner: object
    context_manager: object
    prompt_owner: object
    proposal_owner: object
    provider: object


@dataclass(frozen=True)
class _PromptPath:
    owners: _Owners
    authorities: subject._CheckpointAAuthorities
    view: subject.HypothesisGenerationView
    request: subject.HypothesisCodeSourceRequest
    source: subject.HypothesisCodeSource
    evidence: subject.HypothesisProblemEvidenceProjection
    prompt_source: subject.HypothesisPromptSource
    prompt: subject.BoundHypothesisPrompt


@dataclass(frozen=True)
class _StartedPath:
    prompt_path: _PromptPath
    started: subject.StartedHypothesisAttempt


@dataclass(frozen=True)
class _PermitPath:
    started_path: _StartedPath
    permit: subject.ProviderGenerationPermit


_OWNER_KEEPALIVE: list[_Owners] = []


def _install() -> tuple[_Owners, subject._CheckpointAAuthorities]:
    owners = _Owners(*(object() for _ in range(6)))
    _OWNER_KEEPALIVE.append(owners)
    authorities = subject._install_checkpoint_a_authorities(
        registry=owners.registry,
        code_source_owner=owners.code_source_owner,
        context_manager=owners.context_manager,
        prompt_owner=owners.prompt_owner,
        proposal_owner=owners.proposal_owner,
        provider=owners.provider,
    )
    return owners, authorities


def _request(
    authorities: subject._CheckpointAAuthorities,
    *,
    view: subject.HypothesisGenerationView,
) -> subject.HypothesisCodeSourceRequest:
    return subject._issue_code_source_request(authorities.registry, view)


def _view(
    authorities: subject._CheckpointAAuthorities,
) -> subject.HypothesisGenerationView:
    return subject._issue_generation_view(
        authorities.registry,
        root_identity=object(),
        root_generation=7,
        branch_owner=object(),
        hypothesis_bundle=(object(),),
        prior_head=object(),
        reservation_id="reservation-a",
        h_bundle_digest=_D1,
        owner_context_json=_OWNER_CONTEXT,
    )


def _issue_source(
    authorities: subject._CheckpointAAuthorities,
    request: subject.HypothesisCodeSourceRequest,
) -> subject.HypothesisCodeSource:
    content = b"def solve():\n    return 1\n"
    subject._claim_code_source_request(authorities.code_source_owner, request)
    return subject._issue_code_source(
        authorities.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_D2,
        code_hash=_D3,
        snapshot_hash=_D4,
        entries=(("solver.py", content, _digest(content), True, True),),
    )


def _prompt_path_for(
    owners: _Owners,
    authorities: subject._CheckpointAAuthorities,
) -> _PromptPath:
    view = _view(authorities)
    request = _request(authorities, view=view)
    source = _issue_source(authorities, request)
    inspected_source = subject._inspect_code_source(
        authorities.registry,
        source,
        view=view,
    )
    assert inspected_source.view_identity is view
    source_projection = subject._claim_code_source_for_evidence(
        authorities.context_manager,
        source,
    )
    assert source_projection.view_identity is view
    evidence = subject._issue_problem_evidence(
        authorities.context_manager,
        source,
        provider_context_json=b'{"problem":"cvrp"}',
        governance_json=b'{"protocol":"direct-v3"}',
    )
    prompt_source = subject._issue_prompt_source(
        authorities.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )
    prompt_projection, code_projection, evidence_projection = subject._claim_prompt_source(
        authorities.prompt_owner,
        prompt_source,
    )
    assert prompt_projection.view_identity is view
    assert code_projection.view_identity is view
    assert evidence_projection.code_source is source
    prompt = subject._issue_bound_prompt(
        authorities.prompt_owner,
        prompt_source,
        context_snapshot=object(),
        provider_context_json=b'{"problem":"cvrp"}',
        provider_snapshot_bytes=b'{"prompt":"bound"}',
        context_digest=_D1,
        prompt_hash=_D2,
        provider_tool_digest=_D3,
        governance_digest=_D4,
    )
    inspected_prompt = subject._inspect_bound_prompt(
        authorities.registry,
        prompt,
        view=view,
    )
    assert inspected_prompt.view_identity is view
    return _PromptPath(
        owners=owners,
        authorities=authorities,
        view=view,
        request=request,
        source=source,
        evidence=evidence,
        prompt_source=prompt_source,
        prompt=prompt,
    )


def _prompt_path() -> _PromptPath:
    owners, authorities = _install()
    return _prompt_path_for(owners, authorities)


def _started_path_for(path: _PromptPath) -> _StartedPath:
    subject._begin_started_attempt(
        path.authorities.registry,
        path.view,
        path.prompt,
    )
    prompt_projection = subject._claim_bound_prompt_for_start(
        path.authorities.proposal_owner,
        path.prompt,
    )
    started = subject._issue_started_attempt(
        path.authorities.proposal_owner,
        stored_event=object(),
        attempt_id="attempt-a",
        started_event_id="event-start-a",
        campaign_id="campaign-a",
        branch_id="branch-a",
        context_digest=prompt_projection.context_digest,
        prompt_hash=prompt_projection.prompt_hash,
        event_storage_sha256=_D5,
        bound_prompt=path.prompt,
    )
    inspected = subject._inspect_started_attempt(
        path.authorities.registry,
        started,
        view=path.view,
    )
    assert inspected.bound_prompt is path.prompt
    return _StartedPath(prompt_path=path, started=started)


def _started_path() -> _StartedPath:
    return _started_path_for(_prompt_path())


def _permit_path_for(
    path: _StartedPath,
    *,
    claim: bool = False,
) -> _PermitPath:
    authorities = path.prompt_path.authorities
    permit = subject._issue_provider_permit(
        authorities.registry,
        authorities.provider,
        view=path.prompt_path.view,
        started_attempt=path.started,
        bound_prompt=path.prompt_path.prompt,
    )
    if claim:
        permit_projection, prompt_projection, started_projection = (
            subject._claim_provider_permit(
                authorities.provider,
                permit,
                path.prompt_path.prompt,
            )
        )
        assert permit_projection.started_attempt is path.started
        assert prompt_projection.view_identity is path.prompt_path.view
        assert started_projection.bound_prompt is path.prompt_path.prompt
    return _PermitPath(started_path=path, permit=permit)


def _permit_path(*, claim: bool = False) -> _PermitPath:
    return _permit_path_for(_started_path(), claim=claim)


def _terminalize(
    path: _StartedPath,
    outcome: subject.FailedHypothesisGeneration
    | subject.AbortedHypothesisGeneration,
) -> subject.TerminalAttemptReceipt:
    authorities = path.prompt_path.authorities
    subject._begin_terminal_persistence(
        authorities.registry,
        path.prompt_path.view,
        outcome,
    )
    projection = subject._claim_terminal_outcome(
        authorities.proposal_owner,
        outcome,
        started_attempt=path.started,
        bound_prompt=path.prompt_path.prompt,
    )
    assert projection.started_attempt is path.started
    receipt = subject._issue_terminal_receipt(
        authorities.proposal_owner,
        terminal_event=object(),
        terminal_event_storage_sha256=_D5,
        outcome=outcome,
        started_attempt=path.started,
    )
    resolved = subject._resolve_terminal_receipt(
        authorities.registry,
        receipt,
        started_attempt=path.started,
        view=path.prompt_path.view,
    )
    assert resolved.outcome is outcome
    return receipt


def test_checkpoint_a_success_path_binds_every_capability_once() -> None:
    path = _permit_path(claim=True)
    authorities = path.started_path.prompt_path.authorities
    proposal = b'{"action":"create_new","hypothesis_text":"bounded move"}'
    result = subject._issue_generated_result(
        authorities.provider,
        path.permit,
        receipt=object(),
        trace_ref="artifact://trace-a",
        prompt_manifest_ref="artifact://trace-a#/prompt_manifest",
        raw_response_ref="artifact://trace-a#/response",
        proposal_canonical_bytes=proposal,
        proposal_sha256=_digest(proposal),
        provider_ok=True,
        ok=True,
        error_category=None,
        error_type=None,
        trace_persistence_error=None,
    )

    projection = subject._inspect_generation_outcome(
        authorities.registry,
        permit=path.permit,
        outcome=result,
        view=path.started_path.prompt_path.view,
    )

    assert projection.proposal_canonical_bytes == proposal
    assert projection.proposal_sha256 == _digest(proposal)
    assert projection.started_attempt is path.started_path.started
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._issue_generated_result(
            authorities.provider,
            path.permit,
            receipt=object(),
            trace_ref="artifact://trace-b",
            prompt_manifest_ref="artifact://trace-b#/prompt_manifest",
            raw_response_ref="artifact://trace-b#/response",
            proposal_canonical_bytes=proposal,
            proposal_sha256=_digest(proposal),
            provider_ok=True,
            ok=True,
            error_category=None,
            error_type=None,
            trace_persistence_error=None,
        )


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        ("provider_failure", "provider_call_failed"),
        ("provider_interruption", "provider_call_interrupted"),
        ("invalid_response", "response_parse_failed"),
    ],
)
def test_provider_failure_path_issues_one_terminal_receipt(
    kind: str,
    category: str,
) -> None:
    permit_path = _permit_path(claim=True)
    authorities = permit_path.started_path.prompt_path.authorities
    failure = subject._issue_failed_generation(
        authorities.provider,
        permit_path.permit,
        kind=kind,
        receipt=object(),
        trace_ref="artifact://trace-failure",
        prompt_manifest_ref="artifact://trace-failure#/prompt_manifest",
        raw_response_ref=(
            "artifact://trace-failure#/response"
            if kind == "invalid_response"
            else None
        ),
        provider_ok=(True if kind == "invalid_response" else False),
        ok=False,
        failure_category=category,
        failure_type="RuntimeError",
        trace_persistence_error=None,
    )
    projection = subject._inspect_generation_outcome(
        authorities.registry,
        permit=permit_path.permit,
        outcome=failure,
        view=permit_path.started_path.prompt_path.view,
    )
    assert projection.kind == kind
    assert projection.failure_category == category

    receipt = _terminalize(permit_path.started_path, failure)
    with pytest.raises(subject.HypothesisGenerationAuthorityError):
        subject._resolve_terminal_receipt(
            authorities.registry,
            receipt,
            started_attempt=permit_path.started_path.started,
            view=permit_path.started_path.prompt_path.view,
        )


@pytest.mark.parametrize("with_permit", [False, True])
def test_abort_before_transport_is_terminal_and_cannot_race_claim(
    with_permit: bool,
) -> None:
    path = _started_path()
    authorities = path.prompt_path.authorities
    permit = None
    if with_permit:
        permit = subject._issue_provider_permit(
            authorities.registry,
            authorities.provider,
            view=path.prompt_path.view,
            started_attempt=path.started,
            bound_prompt=path.prompt_path.prompt,
        )
    aborted = subject._issue_aborted_generation(
        authorities.registry,
        started_attempt=path.started,
        bound_prompt=path.prompt_path.prompt,
        view=path.prompt_path.view,
        permit=permit,
    )
    _terminalize(path, aborted)

    if permit is not None:
        with pytest.raises(subject.HypothesisGenerationLifecycleError):
            subject._claim_provider_permit(
                authorities.provider,
                permit,
                path.prompt_path.prompt,
            )


def test_owner_bound_handles_and_cross_installation_swaps_fail() -> None:
    owners_a, authorities_a = _install()
    owners_b, authorities_b = _install()
    view = _view(authorities_a)
    request = _request(authorities_a, view=view)

    assert (
        subject._require_authority(
            authorities_a.registry,
            role=subject._AuthorityRole.REGISTRY,
            owner=owners_a.registry,
        ).owner
        is owners_a.registry
    )
    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._require_authority(
            authorities_a.registry,
            role=subject._AuthorityRole.REGISTRY,
            owner=owners_b.registry,
        )
    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._claim_code_source_request(
            authorities_b.code_source_owner,
            request,
        )


def test_claim_before_work_and_preclaim_failures_are_irreversible() -> None:
    _, authorities = _install()
    view = _view(authorities)
    request = _request(authorities, view=view)
    content = b"print('x')\n"
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._issue_code_source(
            authorities.code_source_owner,
            request,
            source_kind="base_champion",
            selected_manifest_digest=_D1,
            code_hash=_D2,
            snapshot_hash=_D3,
            entries=(("x.py", content, _digest(content), True, True),),
        )
    subject._claim_code_source_request(authorities.code_source_owner, request)
    subject._finish_code_source_request_failure(
        authorities.code_source_owner,
        request,
        rejected=True,
    )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._claim_code_source_request(authorities.code_source_owner, request)

    path = _prompt_path()
    source = path.source
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._claim_code_source_for_evidence(
            path.authorities.context_manager,
            source,
        )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._claim_prompt_source(
            path.authorities.prompt_owner,
            path.prompt_source,
        )

    permit_path = _permit_path(claim=True)
    subject._mark_provider_claim_unknown(
        permit_path.started_path.prompt_path.authorities.provider,
        permit_path.permit,
    )
    proposal = b'{"hypothesis_text":"must not bind"}'
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._issue_generated_result(
            permit_path.started_path.prompt_path.authorities.provider,
            permit_path.permit,
            receipt=object(),
            trace_ref="artifact://trace",
            prompt_manifest_ref="artifact://trace#/prompt_manifest",
            raw_response_ref="artifact://trace#/response",
            proposal_canonical_bytes=proposal,
            proposal_sha256=_digest(proposal),
            provider_ok=True,
            ok=True,
            error_category=None,
            error_type=None,
            trace_persistence_error=None,
        )


def test_source_evidence_and_prompt_rejected_or_unknown_states_are_spent() -> None:
    for rejected in (False, True):
        _, authorities = _install()
        request = _request(authorities, view=_view(authorities))
        subject._claim_code_source_request(authorities.code_source_owner, request)
        subject._finish_code_source_request_failure(
            authorities.code_source_owner,
            request,
            rejected=rejected,
        )
        with pytest.raises(subject.HypothesisGenerationLifecycleError):
            subject._claim_code_source_request(authorities.code_source_owner, request)

        owners, evidence_authorities = _install()
        del owners
        view = _view(evidence_authorities)
        evidence_request = _request(evidence_authorities, view=view)
        source = _issue_source(evidence_authorities, evidence_request)
        subject._inspect_code_source(
            evidence_authorities.registry,
            source,
            view=view,
        )
        subject._claim_code_source_for_evidence(
            evidence_authorities.context_manager,
            source,
        )
        subject._finish_problem_evidence_failure(
            evidence_authorities.context_manager,
            source,
            rejected=rejected,
        )
        with pytest.raises(subject.HypothesisGenerationLifecycleError):
            subject._claim_code_source_for_evidence(
                evidence_authorities.context_manager,
                source,
            )

        prompt_path = _prompt_path()
        # Build a fresh prompt source because _prompt_path already consumed its own.
        fresh_view = _view(prompt_path.authorities)
        fresh_request = _request(prompt_path.authorities, view=fresh_view)
        fresh_source = _issue_source(prompt_path.authorities, fresh_request)
        subject._inspect_code_source(
            prompt_path.authorities.registry,
            fresh_source,
            view=fresh_view,
        )
        subject._claim_code_source_for_evidence(
            prompt_path.authorities.context_manager,
            fresh_source,
        )
        fresh_evidence = subject._issue_problem_evidence(
            prompt_path.authorities.context_manager,
            fresh_source,
            provider_context_json=b'{"problem":"cvrp"}',
            governance_json=b'{"protocol":"direct-v3"}',
        )
        fresh_prompt_source = subject._issue_prompt_source(
            prompt_path.authorities.registry,
            view=fresh_view,
            code_source=fresh_source,
            evidence=fresh_evidence,
        )
        subject._claim_prompt_source(
            prompt_path.authorities.prompt_owner,
            fresh_prompt_source,
        )
        subject._finish_prompt_failure(
            prompt_path.authorities.prompt_owner,
            fresh_prompt_source,
            rejected=rejected,
        )
        with pytest.raises(subject.HypothesisGenerationLifecycleError):
            subject._claim_prompt_source(
                prompt_path.authorities.prompt_owner,
                fresh_prompt_source,
            )


def test_capability_types_are_sealed_noncopyable_nonpickleable_and_unforgeable() -> (
    None
):
    success_path = _permit_path(claim=True)
    authorities = success_path.started_path.prompt_path.authorities
    proposal = b'{"hypothesis_text":"sealed"}'
    success = subject._issue_generated_result(
        authorities.provider,
        success_path.permit,
        receipt=object(),
        trace_ref="artifact://trace-success",
        prompt_manifest_ref="artifact://trace-success#/prompt_manifest",
        raw_response_ref="artifact://trace-success#/response",
        proposal_canonical_bytes=proposal,
        proposal_sha256=_digest(proposal),
        provider_ok=True,
        ok=True,
        error_category=None,
        error_type=None,
        trace_persistence_error=None,
    )
    failure_path = _permit_path(claim=True)
    failure = subject._issue_failed_generation(
        failure_path.started_path.prompt_path.authorities.provider,
        failure_path.permit,
        kind="provider_failure",
        receipt=object(),
        trace_ref="artifact://trace-failure",
        prompt_manifest_ref="artifact://trace-failure#/prompt_manifest",
        raw_response_ref=None,
        provider_ok=False,
        ok=False,
        failure_category="provider_call_failed",
        failure_type="RuntimeError",
        trace_persistence_error=None,
    )
    subject._inspect_generation_outcome(
        failure_path.started_path.prompt_path.authorities.registry,
        permit=failure_path.permit,
        outcome=failure,
        view=failure_path.started_path.prompt_path.view,
    )
    receipt = _terminalize(failure_path.started_path, failure)
    abort_path = _started_path()
    aborted = subject._issue_aborted_generation(
        abort_path.prompt_path.authorities.registry,
        started_attempt=abort_path.started,
        bound_prompt=abort_path.prompt_path.prompt,
        view=abort_path.prompt_path.view,
    )
    values = (
        success_path.started_path.prompt_path.view,
        success_path.started_path.prompt_path.request,
        success_path.started_path.prompt_path.source,
        success_path.started_path.prompt_path.evidence,
        success_path.started_path.prompt_path.prompt_source,
        success_path.started_path.prompt_path.prompt,
        success_path.started_path.started,
        success_path.permit,
        success,
        failure,
        aborted,
        receipt,
    )
    state_maps = (
        subject._GENERATION_VIEW_STATES,
        subject._CODE_REQUEST_STATES,
        subject._CODE_SOURCE_STATES,
        subject._EVIDENCE_STATES,
        subject._PROMPT_SOURCE_STATES,
        subject._BOUND_PROMPT_STATES,
        subject._STARTED_STATES,
        subject._PERMIT_STATES,
        subject._RESULT_STATES,
        subject._FAILURE_STATES,
        subject._ABORT_STATES,
        subject._RECEIPT_STATES,
    )
    for value, states in zip(values, state_maps, strict=True):
        capability_type = type(value)
        assert not hasattr(value, "__dict__")
        with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
            capability_type()
        with pytest.raises(TypeError, match="sealed"):
            type(f"Forged{capability_type.__name__}", (capability_type,), {})
        with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
            copy.copy(value)
        with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
            copy.deepcopy(value)
        with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
            pickle.dumps(value)
        forged = object.__new__(capability_type)
        with pytest.raises(
            subject.InvalidHypothesisGenerationCapabilityError,
            match="was not issued",
        ):
            subject._lookup_exact(
                forged,
                capability_type,
                states,
                label=capability_type.__name__,
            )


def test_settled_attempt_graph_returns_to_baseline_with_bounded_context() -> None:
    gc.collect()
    state_maps = (
        subject._GENERATION_VIEW_STATES,
        subject._CODE_REQUEST_STATES,
        subject._CODE_SOURCE_STATES,
        subject._EVIDENCE_STATES,
        subject._PROMPT_SOURCE_STATES,
        subject._BOUND_PROMPT_STATES,
        subject._STARTED_STATES,
        subject._PERMIT_STATES,
        subject._FAILURE_STATES,
        subject._RECEIPT_STATES,
    )
    state_baseline = tuple(len(states) for states in state_maps)
    context_baseline = len(contextvars.copy_context())

    def settle_one() -> tuple[weakref.ReferenceType[object], ...]:
        path = _permit_path(claim=True)
        authorities = path.started_path.prompt_path.authorities
        failure = subject._issue_failed_generation(
            authorities.provider,
            path.permit,
            kind="provider_failure",
            receipt=object(),
            trace_ref="artifact://trace-gc",
            prompt_manifest_ref="artifact://trace-gc#/prompt_manifest",
            raw_response_ref=None,
            provider_ok=False,
            ok=False,
            failure_category="provider_call_failed",
            failure_type="RuntimeError",
            trace_persistence_error=None,
        )
        subject._inspect_generation_outcome(
            authorities.registry,
            permit=path.permit,
            outcome=failure,
            view=path.started_path.prompt_path.view,
        )
        receipt = _terminalize(path.started_path, failure)
        values = (
            path.started_path.prompt_path.view,
            path.started_path.prompt_path.request,
            path.started_path.prompt_path.source,
            path.started_path.prompt_path.evidence,
            path.started_path.prompt_path.prompt_source,
            path.started_path.prompt_path.prompt,
            path.started_path.started,
            path.permit,
            failure,
            receipt,
        )
        return tuple(weakref.ref(value) for value in values)

    references = settle_one()
    gc.collect()
    context_after_first = len(contextvars.copy_context())
    more_references = settle_one()
    gc.collect()

    assert all(
        reference() is None
        for reference in references + more_references
    )
    assert tuple(len(states) for states in state_maps) == state_baseline
    assert context_after_first <= context_baseline + 1
    assert len(contextvars.copy_context()) == context_after_first


def test_owner_role_registration_is_released_with_authority_graph() -> None:
    owners = _Owners(*(object() for _ in range(6)))

    def install_once() -> tuple[weakref.ReferenceType[object], ...]:
        authorities = subject._install_checkpoint_a_authorities(
            registry=owners.registry,
            code_source_owner=owners.code_source_owner,
            context_manager=owners.context_manager,
            prompt_owner=owners.prompt_owner,
            proposal_owner=owners.proposal_owner,
            provider=owners.provider,
        )
        with pytest.raises(subject.HypothesisGenerationLifecycleError):
            subject._install_checkpoint_a_authorities(
                registry=owners.registry,
                code_source_owner=owners.code_source_owner,
                context_manager=owners.context_manager,
                prompt_owner=owners.prompt_owner,
                proposal_owner=owners.proposal_owner,
                provider=owners.provider,
            )
        return tuple(
            weakref.ref(handle)
            for handle in (
                authorities.registry,
                authorities.code_source_owner,
                authorities.context_manager,
                authorities.prompt_owner,
                authorities.proposal_owner,
                authorities.provider,
            )
        )

    first_handles = install_once()
    gc.collect()
    assert all(reference() is None for reference in first_handles)

    second = subject._install_checkpoint_a_authorities(
        registry=owners.registry,
        code_source_owner=owners.code_source_owner,
        context_manager=owners.context_manager,
        prompt_owner=owners.prompt_owner,
        proposal_owner=owners.proposal_owner,
        provider=owners.provider,
    )
    assert subject._require_authority(
        second.registry,
        role=subject._AuthorityRole.REGISTRY,
        owner=owners.registry,
    ).owner is owners.registry


def test_abandoned_graphs_use_one_bounded_context_entry() -> None:
    gc.collect()
    context_baseline = len(contextvars.copy_context())
    view_state_baseline = len(subject._GENERATION_VIEW_STATES)

    def abandon_many() -> tuple[weakref.ReferenceType[object], ...]:
        references: list[weakref.ReferenceType[object]] = []
        for index in range(50):
            owners = _Owners(*(object() for _ in range(6)))
            authorities = subject._install_checkpoint_a_authorities(
                registry=owners.registry,
                code_source_owner=owners.code_source_owner,
                context_manager=owners.context_manager,
                prompt_owner=owners.prompt_owner,
                proposal_owner=owners.proposal_owner,
                provider=owners.provider,
            )
            view = subject._issue_generation_view(
                authorities.registry,
                root_identity=object(),
                root_generation=index,
                branch_owner=object(),
                hypothesis_bundle=(),
                prior_head=None,
                reservation_id=f"abandoned-{index}",
                h_bundle_digest=_D1,
                owner_context_json=_OWNER_CONTEXT,
            )
            references.extend(
                (weakref.ref(view), weakref.ref(authorities.registry))
            )
        return tuple(references)

    references = abandon_many()
    gc.collect()

    assert all(reference() is None for reference in references)
    assert len(subject._GENERATION_VIEW_STATES) == view_state_baseline
    assert len(contextvars.copy_context()) <= context_baseline + 1


def test_provider_claim_unknown_has_exact_registry_settlement() -> None:
    path = _permit_path(claim=True)
    authorities = path.started_path.prompt_path.authorities
    subject._mark_provider_claim_unknown(authorities.provider, path.permit)

    assert subject._settle_provider_claim_unknown(
        authorities.registry,
        path.started_path.prompt_path.view,
    )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._settle_provider_claim_unknown(
            authorities.registry,
            path.started_path.prompt_path.view,
        )


def test_prestart_abort_spends_stable_view_without_terminal_outcome() -> None:
    _, authorities = _install()
    captured = _view(authorities)
    subject._abort_prestart_generation_view(authorities.registry, captured)
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._issue_code_source_request(authorities.registry, captured)

    prompt_path = _prompt_path()
    subject._abort_prestart_generation_view(
        prompt_path.authorities.registry,
        prompt_path.view,
    )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._begin_started_attempt(
            prompt_path.authorities.registry,
            prompt_path.view,
            prompt_path.prompt,
        )


def test_abort_state_allocation_failure_does_not_cancel_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _permit_path()
    authorities = path.started_path.prompt_path.authorities

    class _FailingAbortStates(subject._CapabilityStateTable):
        def __setitem__(self, key: object, state: object) -> None:
            raise MemoryError("injected abort state allocation failure")

    monkeypatch.setattr(subject, "_ABORT_STATES", _FailingAbortStates())
    with pytest.raises(MemoryError, match="injected abort"):
        subject._issue_aborted_generation(
            authorities.registry,
            started_attempt=path.started_path.started,
            bound_prompt=path.started_path.prompt_path.prompt,
            view=path.started_path.prompt_path.view,
            permit=path.permit,
        )

    assert (
        subject._PERMIT_STATES[path.permit].phase
        is subject._PermitPhase.ISSUED
    )


def test_replay_is_lifecycle_but_cross_binding_is_invalid() -> None:
    prompt_path = _prompt_path()
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._inspect_code_source(
            prompt_path.authorities.registry,
            prompt_path.source,
            view=prompt_path.view,
        )
    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._inspect_code_source(
            prompt_path.authorities.registry,
            prompt_path.source,
            view=_view(prompt_path.authorities),
        )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._inspect_bound_prompt(
            prompt_path.authorities.registry,
            prompt_path.prompt,
            view=prompt_path.view,
        )


def test_provider_and_terminal_cross_binding_are_invalid_not_replay() -> None:
    owners, authorities = _install()
    first = _permit_path_for(
        _started_path_for(_prompt_path_for(owners, authorities))
    )
    second = _permit_path_for(
        _started_path_for(_prompt_path_for(owners, authorities))
    )

    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._claim_provider_permit(
            authorities.provider,
            first.permit,
            second.started_path.prompt_path.prompt,
        )
    subject._claim_provider_permit(
        authorities.provider,
        first.permit,
        first.started_path.prompt_path.prompt,
    )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._claim_provider_permit(
            authorities.provider,
            first.permit,
            first.started_path.prompt_path.prompt,
        )

    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._issue_aborted_generation(
            authorities.registry,
            started_attempt=second.started_path.started,
            bound_prompt=second.started_path.prompt_path.prompt,
            view=second.started_path.prompt_path.view,
            permit=first.permit,
        )

    failure = subject._issue_failed_generation(
        authorities.provider,
        first.permit,
        kind="provider_failure",
        receipt=object(),
        trace_ref="artifact://trace-cross-binding",
        prompt_manifest_ref="artifact://trace-cross-binding#/prompt_manifest",
        raw_response_ref=None,
        provider_ok=False,
        ok=False,
        failure_category="provider_call_failed",
        failure_type="RuntimeError",
        trace_persistence_error=None,
    )
    first_view = first.started_path.prompt_path.view
    subject._inspect_generation_outcome(
        authorities.registry,
        permit=first.permit,
        outcome=failure,
        view=first_view,
    )
    subject._begin_terminal_persistence(
        authorities.registry,
        first_view,
        failure,
    )
    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._claim_terminal_outcome(
            authorities.proposal_owner,
            failure,
            started_attempt=second.started_path.started,
            bound_prompt=second.started_path.prompt_path.prompt,
        )
    subject._claim_terminal_outcome(
        authorities.proposal_owner,
        failure,
        started_attempt=first.started_path.started,
        bound_prompt=first.started_path.prompt_path.prompt,
    )
    with pytest.raises(subject.InvalidHypothesisGenerationCapabilityError):
        subject._issue_terminal_receipt(
            authorities.proposal_owner,
            terminal_event=object(),
            terminal_event_storage_sha256=_D5,
            outcome=failure,
            started_attempt=second.started_path.started,
        )
    subject._issue_terminal_receipt(
        authorities.proposal_owner,
        terminal_event=object(),
        terminal_event_storage_sha256=_D5,
        outcome=failure,
        started_attempt=first.started_path.started,
    )
    with pytest.raises(subject.HypothesisGenerationLifecycleError):
        subject._issue_terminal_receipt(
            authorities.proposal_owner,
            terminal_event=object(),
            terminal_event_storage_sha256=_D5,
            outcome=failure,
            started_attempt=first.started_path.started,
        )


def test_capability_rejects_cross_thread_without_spending_original_context() -> None:
    _, authorities = _install()
    request = _request(authorities, view=_view(authorities))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            subject._claim_code_source_request,
            authorities.code_source_owner,
            request,
        )
        with pytest.raises(
            subject.HypothesisGenerationLifecycleError,
            match="cross threads",
        ):
            future.result()

    projection = subject._claim_code_source_request(
        authorities.code_source_owner,
        request,
    )
    assert projection.reservation_id == "reservation-a"


def test_capability_rejects_copied_context_without_spending_original_context() -> None:
    _, authorities = _install()
    request = _request(authorities, view=_view(authorities))
    copied = contextvars.copy_context()

    with pytest.raises(
        subject.HypothesisGenerationLifecycleError,
        match="cross Contexts",
    ):
        copied.run(
            subject._claim_code_source_request,
            authorities.code_source_owner,
            request,
        )

    projection = subject._claim_code_source_request(
        authorities.code_source_owner,
        request,
    )
    assert projection.reservation_id == "reservation-a"
