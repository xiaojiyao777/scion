from __future__ import annotations

import ast
import contextvars
import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal.engine import provider_call as subject
from scion.proposal.engine.facade import build_prompt_turn_snapshot
from scion.proposal.prompt_manifest import stable_digest

_RESPONSE = {
    "hypothesis_text": "Add one bounded local improvement move.",
    "change_locus": "local_search",
    "action": "create_new",
    "target_file": "operators/bounded_generated_result.py",
    "predicted_direction": "improve",
    "target_weakness": "The current control lacks this bounded move.",
    "expected_effect": "Improve the primary objective when the move applies.",
    "suggested_weight": 1.25,
}


class _DeterministicTransport:
    def __init__(
        self,
        response: dict[str, object] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.response = dict(_RESPONSE if response is None else response)
        self.error = error
        self.calls = 0

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
        if self.error is not None:
            raise self.error
        return dict(self.response)


@dataclass(frozen=True, slots=True)
class _Harness:
    authorities: generation._CheckpointAAuthorities
    view: generation.HypothesisGenerationView
    bound_prompt: generation.BoundHypothesisPrompt
    permit: generation.ProviderGenerationPermit
    owner: subject.ProviderCallOwner
    transport: _DeterministicTransport
    expected_turn: subject.PromptTurnSnapshot
    trace_root: Path


_KEEPALIVE: list[tuple[object, ...]] = []


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _context() -> dict[str, object]:
    return {
        "problem_summary": "Synthetic routing control.",
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "target_files": ["operators/*.py"],
            }
        ],
        "objective_policy_guidance": "Minimize cost while preserving feasibility.",
        "solver_mechanics": "",
        "champion_operators_code": "class Control: pass",
        "champion_stats": {"version": 3, "operators": []},
        "available_actions": ["create_new"],
        "targetable_files": ["operators/*.py"],
        "experiment_history": [],
        "branch_id": "branch-generated-result",
        "champion_version": 3,
    }


def _harness(
    tmp_path: Path,
    *,
    response: dict[str, object] | None = None,
    error: BaseException | None = None,
    mutate_provider_snapshot: object | None = None,
    transform_provider_context_bytes: object | None = None,
    transform_provider_snapshot_bytes: object | None = None,
) -> _Harness:
    context = _context()
    turn = build_prompt_turn_snapshot("hypothesis", context)
    context_snapshot = turn.authoritative_context
    assert context_snapshot is not None
    provider_context = context_snapshot.inputs.provider_context(
        include_renderer_inputs=True
    )
    provider_snapshot: dict[str, object] = {
        "schema_version": "hypothesis-provider-snapshot.v1",
        "render_kind": "hypothesis",
        "system_blocks": [dict(block) for block in turn.system_blocks],
        "user_prompt": turn.user_prompt,
        "context_digest": turn.context_digest,
        "provider_tool": dict(turn.provider_tool),
        "allowed_change_loci": list(turn.allowed_change_loci),
        "authoritative_context_ref": context_snapshot.snapshot_id,
    }
    if mutate_provider_snapshot is not None:
        assert callable(mutate_provider_snapshot)
        mutate_provider_snapshot(provider_snapshot)

    transport = _DeterministicTransport(response, error=error)
    trace_root = tmp_path / "traces"
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(trace_root),
    )
    registry_owner = object()
    code_owner = object()
    context_owner = object()
    prompt_owner = object()
    proposal_owner = object()
    authorities = generation._install_checkpoint_a_authorities(
        registry=registry_owner,
        code_source_owner=code_owner,
        context_manager=context_owner,
        prompt_owner=prompt_owner,
        proposal_owner=proposal_owner,
        provider=owner,
    )
    _KEEPALIVE.append(
        (
            registry_owner,
            code_owner,
            context_owner,
            prompt_owner,
            proposal_owner,
            owner,
            authorities,
        )
    )
    owner._install_hypothesis_generation_authority(authorities.provider)

    owner_context = _canonical(
        {
            "branch_id": "branch-generated-result",
            "schema_version": "hypothesis-owner-context.test.v1",
        }
    )
    view = generation._issue_generation_view(
        authorities.registry,
        root_identity=object(),
        root_generation=7,
        branch_owner=object(),
        hypothesis_bundle=(),
        prior_head=None,
        reservation_id="reservation-generated-result",
        h_bundle_digest=_digest(b"empty-H-bundle"),
        owner_context_json=owner_context,
    )
    request = generation._issue_code_source_request(authorities.registry, view)
    generation._claim_code_source_request(authorities.code_source_owner, request)
    source_content = b"def solve():\n    return 1\n"
    source = generation._issue_code_source(
        authorities.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_digest(b"source-manifest"),
        code_hash=_digest(b"code"),
        snapshot_hash=_digest(b"snapshot"),
        entries=(
            (
                "solver.py",
                source_content,
                _digest(source_content),
                True,
                True,
            ),
        ),
    )
    generation._inspect_code_source(authorities.registry, source, view=view)
    generation._claim_code_source_for_evidence(
        authorities.context_manager,
        source,
    )
    provider_context_bytes = _canonical(provider_context)
    if transform_provider_context_bytes is not None:
        assert callable(transform_provider_context_bytes)
        provider_context_bytes = transform_provider_context_bytes(
            provider_context_bytes
        )
    evidence = generation._issue_problem_evidence(
        authorities.context_manager,
        source,
        provider_context_json=provider_context_bytes,
        governance_json=_canonical({"protocol": "direct-v3"}),
    )
    prompt_source = generation._issue_prompt_source(
        authorities.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )
    generation._claim_prompt_source(authorities.prompt_owner, prompt_source)
    prompt_hash = subject._provider_prompt_hash(
        turn.system_blocks,
        turn.user_prompt,
    )
    provider_snapshot_bytes = _canonical(provider_snapshot)
    if transform_provider_snapshot_bytes is not None:
        assert callable(transform_provider_snapshot_bytes)
        provider_snapshot_bytes = transform_provider_snapshot_bytes(
            provider_snapshot_bytes
        )
    bound_prompt = generation._issue_bound_prompt(
        authorities.prompt_owner,
        prompt_source,
        context_snapshot=context_snapshot,
        provider_context_json=provider_context_bytes,
        provider_snapshot_bytes=provider_snapshot_bytes,
        context_digest=turn.context_digest,
        prompt_hash=prompt_hash,
        provider_tool_digest=stable_digest(turn.provider_tool, length=64),
        governance_digest=context_snapshot.governance_envelope.digest,
    )
    generation._inspect_bound_prompt(
        authorities.registry,
        bound_prompt,
        view=view,
    )
    generation._begin_started_attempt(authorities.registry, view, bound_prompt)
    prompt_projection = generation._claim_bound_prompt_for_start(
        authorities.proposal_owner,
        bound_prompt,
    )
    started = generation._issue_started_attempt(
        authorities.proposal_owner,
        stored_event=object(),
        attempt_id="attempt-generated-result",
        started_event_id="event-started-generated-result",
        campaign_id="test-campaign",
        branch_id="branch-generated-result",
        context_digest=prompt_projection.context_digest,
        prompt_hash=prompt_projection.prompt_hash,
        event_storage_sha256=_digest(b"stored-START"),
        bound_prompt=bound_prompt,
    )
    generation._inspect_started_attempt(
        authorities.registry,
        started,
        view=view,
    )
    permit = generation._issue_provider_permit(
        authorities.registry,
        authorities.provider,
        view=view,
        started_attempt=started,
        bound_prompt=bound_prompt,
    )
    return _Harness(
        authorities=authorities,
        view=view,
        bound_prompt=bound_prompt,
        permit=permit,
        owner=owner,
        transport=transport,
        expected_turn=turn,
        trace_root=trace_root,
    )


def _projection(
    harness: _Harness,
    outcome: generation.GeneratedHypothesisResult
    | generation.FailedHypothesisGeneration,
) -> generation._GeneratedResultProjection | generation._TerminalOutcomeProjection:
    return generation._inspect_generation_outcome(
        harness.authorities.registry,
        permit=harness.permit,
        outcome=outcome,
        view=harness.view,
    )


def test_real_six_owner_path_issues_leaf_success_from_persisted_provider_bytes(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)

    result = harness.owner.call_hypothesis(
        harness.permit,
        harness.bound_prompt,
    )
    projection = _projection(harness, result)

    assert type(result) is generation.GeneratedHypothesisResult
    assert harness.transport.calls == 1
    assert projection.provider_ok is True
    assert projection.ok is True
    assert projection.receipt.attempt_id == "attempt-generated-result"
    assert projection.receipt.attempt_started_event_id == (
        "event-started-generated-result"
    )
    assert projection.proposal_sha256 == hashlib.sha256(
        projection.proposal_canonical_bytes
    ).hexdigest()
    assert json.loads(projection.proposal_canonical_bytes) == _RESPONSE
    assert projection.trace_ref == projection.receipt.trace_ref
    assert projection.prompt_manifest_ref == (
        f"{projection.trace_ref}#/prompt_manifest"
    )
    assert projection.raw_response_ref == f"{projection.trace_ref}#/response"
    persisted = json.loads(
        (tmp_path / projection.trace_ref).read_text(encoding="utf-8")
    )
    assert persisted["ok"] is True
    assert persisted["response"] == _RESPONSE
    assert persisted["provider_call_attempt"]["attempt_id"] == (
        "attempt-generated-result"
    )


@pytest.mark.parametrize(
    ("error", "expected_kind", "expected_category"),
    (
        (RuntimeError("provider failed"), "provider_failure", "provider_call_failed"),
        (
            KeyboardInterrupt(),
            "provider_interruption",
            "provider_call_interrupted",
        ),
    ),
)
def test_real_provider_failure_receipt_issues_leaf_failure(
    tmp_path: Path,
    error: BaseException,
    expected_kind: str,
    expected_category: str,
) -> None:
    harness = _harness(tmp_path, error=error)

    failure = harness.owner.call_hypothesis(
        harness.permit,
        harness.bound_prompt,
    )
    projection = _projection(harness, failure)

    assert type(failure) is generation.FailedHypothesisGeneration
    assert harness.transport.calls == 1
    assert projection.kind == expected_kind
    assert projection.failure_category == expected_category
    assert projection.receipt.error_category == expected_category
    assert projection.ok is False


def test_invalid_response_issues_leaf_invalid_response_failure(tmp_path: Path) -> None:
    harness = _harness(
        tmp_path,
        response={**_RESPONSE, "change_locus": "not-allowed"},
    )

    failure = harness.owner.call_hypothesis(
        harness.permit,
        harness.bound_prompt,
    )
    projection = _projection(harness, failure)

    assert type(failure) is generation.FailedHypothesisGeneration
    assert harness.transport.calls == 1
    assert projection.kind == "invalid_response"
    assert projection.provider_ok is True
    assert projection.failure_category == "response_parse_failed"
    assert projection.raw_response_ref == (
        f"{projection.trace_ref}#/response"
    )


def test_malformed_bound_provider_bytes_claim_unknown_before_transport(
    tmp_path: Path,
) -> None:
    harness = _harness(
        tmp_path,
        mutate_provider_snapshot=lambda value: value.__setitem__(
            "caller_mapping",
            {"substitute": True},
        ),
    )

    with pytest.raises(subject.ProviderCallUnknownError):
        harness.owner.call_hypothesis(
            harness.permit,
            harness.bound_prompt,
        )

    assert harness.transport.calls == 0
    assert (
        generation._PERMIT_STATES[harness.permit].phase
        is generation._PermitPhase.CLAIMED_UNKNOWN
    )


@pytest.mark.parametrize(
    ("projection", "transform"),
    (
        ("snapshot", lambda value: value + b"\n"),
        (
            "snapshot",
            lambda _value: (
                b'{"schema_version":"one","schema_version":"two"}'
            ),
        ),
        ("snapshot", lambda _value: b'{"context_digest":NaN}'),
        ("context", lambda value: b" " + value),
    ),
)
def test_provider_rejects_noncanonical_duplicate_and_nonfinite_json(
    tmp_path: Path,
    projection: str,
    transform: object,
) -> None:
    kwargs = (
        {"transform_provider_snapshot_bytes": transform}
        if projection == "snapshot"
        else {"transform_provider_context_bytes": transform}
    )
    harness = _harness(tmp_path, **kwargs)

    with pytest.raises(subject.ProviderCallUnknownError):
        harness.owner.call_hypothesis(
            harness.permit,
            harness.bound_prompt,
        )

    assert harness.transport.calls == 0
    assert (
        generation._PERMIT_STATES[harness.permit].phase
        is generation._PermitPhase.CLAIMED_UNKNOWN
    )


def test_leaf_success_issuance_fault_marks_claim_unknown_after_one_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)

    def fail_issue(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("leaf issuance fault")

    monkeypatch.setattr(generation, "_issue_generated_result", fail_issue)
    with pytest.raises(subject.ProviderCallUnknownError):
        harness.owner.call_hypothesis(
            harness.permit,
            harness.bound_prompt,
        )

    assert harness.transport.calls == 1
    assert (
        generation._PERMIT_STATES[harness.permit].phase
        is generation._PermitPhase.CLAIMED_UNKNOWN
    )


def test_incomplete_persisted_success_becomes_truthful_provider_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)

    def incomplete_finish(
        _writer: object,
        path: str | None,
        **_kwargs: object,
    ) -> None:
        assert path is not None
        Path(path).write_text('{"ok":true}\n', encoding="utf-8")

    monkeypatch.setattr(subject._TraceWriter, "write_finish", incomplete_finish)
    failure = harness.owner.call_hypothesis(
        harness.permit,
        harness.bound_prompt,
    )
    projection = _projection(harness, failure)

    assert harness.transport.calls == 1
    assert type(failure) is generation.FailedHypothesisGeneration
    assert projection.kind == "provider_failure"
    assert projection.failure_category == "generated_result_issuance_failed"


def test_permit_is_claimed_before_transport_and_cannot_call_twice(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    harness.owner.call_hypothesis(harness.permit, harness.bound_prompt)

    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.owner.call_hypothesis(harness.permit, harness.bound_prompt)

    assert harness.transport.calls == 1


def test_provider_owner_handle_is_installed_once_and_entry_has_no_mapping_surface(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    signature = inspect.signature(subject.ProviderCallOwner.call_hypothesis)

    assert tuple(signature.parameters) == ("self", "permit", "bound_prompt")
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.owner._install_hypothesis_generation_authority(
            harness.authorities.provider
        )


def test_provider_module_has_no_old_authority_or_lineage_sql_dependencies() -> None:
    source = inspect.getsource(subject)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert not any("proposal_attempt_owner" in name for name in imported)
    assert not any("sqlite_connection" in name for name in imported)
    assert not hasattr(subject, "_issue_provider_generation_permit")
    assert not hasattr(subject, "_generate_hypothesis_result_with_receipt")
    assert not hasattr(subject, "_consume_generated_hypothesis_result")
    assert subject.ProviderGenerationPermit is generation.ProviderGenerationPermit
    assert subject.GeneratedHypothesisResult is generation.GeneratedHypothesisResult


def test_copied_context_fails_leaf_claim_before_transport(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    copied = contextvars.copy_context()

    with pytest.raises(
        generation.HypothesisGenerationLifecycleError,
        match="cross Contexts",
    ):
        copied.run(
            harness.owner.call_hypothesis,
            harness.permit,
            harness.bound_prompt,
        )

    assert harness.transport.calls == 0
    assert type(
        harness.owner.call_hypothesis(harness.permit, harness.bound_prompt)
    ) is generation.GeneratedHypothesisResult
    assert harness.transport.calls == 1
