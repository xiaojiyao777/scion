from __future__ import annotations

import builtins
import hashlib
import json
from dataclasses import dataclass

import pytest

from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal import prompt_projection_authority as subject
from scion.proposal.context_manager.manager import ContextManager
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash


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


_H_ID = "hypothesis-1"
_H_BUNDLE_DIGEST = _digest(b"h-bundle")
_BASE_SNAPSHOT_HASH = _digest(b"base-snapshot")
_WORKSPACE_CODE_HASH = _digest(b"workspace-code")


def _owner_context(*, source_kind: str = "base_champion") -> bytes:
    item = {
        "hypothesis_id": _H_ID,
        "owner_revision": 5,
        "storage_sha256": _digest(b"hypothesis-storage"),
    }
    workspace = source_kind == "verified_branch_workspace"
    return _canonical(
        {
            "anchors": {
                "branch_base_champion_hash": _BASE_SNAPSHOT_HASH,
                "branch_base_champion_id": 7,
                "champion_code_snapshot_hash": _BASE_SNAPSHOT_HASH,
                "champion_version": 7,
                "champion_weight_revision": 2,
                "problem_id": "cvrp",
                "problem_spec_hash": _digest(b"problem-spec"),
                "seed_ledger_hash": _digest(b"seed-ledger"),
                "split_manifest_hash": _digest(b"split-manifest"),
            },
            "branch": {
                "base_champion_hash": _BASE_SNAPSHOT_HASH,
                "base_champion_id": 7,
                "base_champion_weight_revision": 2,
                "branch_code_status": "clean",
                "branch_id": "branch-1",
                "current_code_hash": _WORKSPACE_CODE_HASH if workspace else None,
                "last_clean_code_hash": (
                    _WORKSPACE_CODE_HASH if workspace else None
                ),
                "owner_revision": 3,
                "state": "explore",
                "storage_sha256": _digest(b"branch-storage"),
            },
            "campaign_id": "campaign-1",
            "h_bundle": {
                "count": 1,
                "digest": _H_BUNDLE_DIGEST,
                "items": [item],
            },
            "prior_head": item,
            "root_generation": 11,
            "runtime_mode": "direct_v3",
            "schema_version": "hypothesis-owner-context-projection.v1",
        }
    )


def _problem_evidence(*, hypothesis_id: str = _H_ID) -> dict[str, object]:
    return {
        "available_actions": ["modify"],
        "experiment_history": [
            {
                "attempt_id": hypothesis_id,
                "candidate_composition": {
                    "current_step": {"hypothesis_id": hypothesis_id}
                },
                "source_branch_id": "branch-1",
            }
        ],
        "problem_summary": "Capacitated vehicle-routing research",
        "research_surfaces": [
            {
                "allowed_actions": ["modify"],
                "kind": "policy",
                "name": "solution_pool_search",
                "target_files": ["solution_pool.py"],
            }
        ],
    }


@dataclass(slots=True)
class _Harness:
    graph: generation._CheckpointAAuthorities
    manager: ContextManager
    prompt_owner: subject.ProposalPromptProjectionAuthority
    view: generation.HypothesisGenerationView
    source: generation.HypothesisCodeSource
    prompt_source: generation.HypothesisPromptSource


_LIVE_HARNESSES: list[_Harness] = []
_LIVE_GRAPHS: list[generation._CheckpointAAuthorities] = []


def _harness(
    *,
    source_kind: str = "base_champion",
    hypothesis_id: str = _H_ID,
) -> _Harness:
    manager = ContextManager(
        hypothesis_problem_evidence=_problem_evidence(
            hypothesis_id=hypothesis_id
        )
    )
    prompt_owner = subject.ProposalPromptProjectionAuthority()
    graph = generation._install_checkpoint_a_authorities(
        registry=object(),
        code_source_owner=object(),
        context_manager=manager,
        prompt_owner=prompt_owner,
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(graph)
    manager._install_hypothesis_generation_authority(graph.context_manager)
    prompt_owner._install_hypothesis_generation_authority(graph.prompt_owner)
    view = generation._issue_generation_view(
        graph.registry,
        root_identity=object(),
        root_generation=11,
        branch_owner=object(),
        hypothesis_bundle=(object(),),
        prior_head=object(),
        reservation_id="reservation-1",
        h_bundle_digest=_H_BUNDLE_DIGEST,
        owner_context_json=_owner_context(source_kind=source_kind),
    )
    request = generation._issue_code_source_request(graph.registry, view)
    generation._claim_code_source_request(graph.code_source_owner, request)
    content = b"def bounded_pool_search(pool):\n    return pool\n"
    source = generation._issue_code_source(
        graph.code_source_owner,
        request,
        source_kind=source_kind,
        selected_manifest_digest=_digest(b"selected-manifest"),
        code_hash=(
            _WORKSPACE_CODE_HASH
            if source_kind == "verified_branch_workspace"
            else _digest(b"base-code")
        ),
        snapshot_hash=(
            _digest(b"workspace-snapshot")
            if source_kind == "verified_branch_workspace"
            else _BASE_SNAPSHOT_HASH
        ),
        entries=(
            (
                "solution_pool.py",
                content,
                _digest(content),
                True,
                True,
            ),
        ),
    )
    generation._inspect_code_source(graph.registry, source, view=view)
    evidence = manager._project_hypothesis_problem_evidence(source)
    prompt_source = generation._issue_prompt_source(
        graph.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )
    harness = _Harness(
        graph=graph,
        manager=manager,
        prompt_owner=prompt_owner,
        view=view,
        source=source,
        prompt_source=prompt_source,
    )
    _LIVE_HARNESSES.append(harness)
    return harness


@pytest.mark.parametrize(
    ("source_kind", "source_key"),
    [
        ("base_champion", "champion_operators_code"),
        ("verified_branch_workspace", "branch_current_code"),
    ],
)
def test_prompt_owner_binds_real_snapshot_turn_and_frozen_codecs_without_fs(
    source_kind: str,
    source_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(source_kind=source_kind)

    def fail_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("checkpoint-A prompt owner read the filesystem")

    monkeypatch.setattr(builtins, "open", fail_open)
    bound = harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)
    projection = generation._inspect_bound_prompt(
        harness.graph.registry,
        bound,
        view=harness.view,
    )

    assert type(projection.context_snapshot) is ProposalContextSnapshot
    provider_context = json.loads(projection.provider_context_json)
    assert projection.provider_context_json == _canonical(provider_context)
    assert provider_context["branch_id"] == "branch-1"
    assert provider_context[source_key]["source_kind"] == source_kind
    assert provider_context[source_key]["files"] == [
        {
            "content": "def bounded_pool_search(pool):\n    return pool\n",
            "file_path": "solution_pool.py",
            "sha256": _digest(
                b"def bounded_pool_search(pool):\n    return pool\n"
            ),
        }
    ]
    other_source_key = (
        "branch_current_code"
        if source_key == "champion_operators_code"
        else "champion_operators_code"
    )
    assert other_source_key not in provider_context
    assert projection.context_snapshot.inputs.provider_context(
        include_renderer_inputs=True
    ) == provider_context
    assert projection.context_digest == _digest(projection.provider_context_json)
    assert projection.context_digest == stable_digest(provider_context, length=64)

    provider_snapshot = json.loads(projection.provider_snapshot_bytes)
    assert projection.provider_snapshot_bytes == _canonical(provider_snapshot)
    assert set(provider_snapshot) == {
        "allowed_change_loci",
        "authoritative_context_ref",
        "context_digest",
        "provider_tool",
        "render_kind",
        "schema_version",
        "system_blocks",
        "user_prompt",
    }
    assert provider_snapshot["schema_version"] == "hypothesis-provider-snapshot.v1"
    assert provider_snapshot["render_kind"] == "hypothesis"
    assert provider_snapshot["context_digest"] == projection.context_digest
    assert provider_snapshot["allowed_change_loci"] == ["solution_pool_search"]
    assert projection.prompt_hash == _provider_prompt_hash(
        tuple(provider_snapshot["system_blocks"]),
        provider_snapshot["user_prompt"],
    )
    assert projection.provider_tool_digest == stable_digest(
        provider_snapshot["provider_tool"],
        length=64,
    )
    governance = projection.context_snapshot.governance_envelope.to_primitive()
    assert governance["checkpoint_a_generation"]["owner_context"] == json.loads(
        _owner_context(source_kind=source_kind)
    )
    assert projection.governance_digest == (
        projection.context_snapshot.governance_envelope.digest
    )


def test_prompt_owner_rejects_uncaptured_history_after_irreversible_claim() -> None:
    harness = _harness(hypothesis_id="hypothesis-other")

    with pytest.raises(subject.HypothesisPromptRejectedError):
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)


def test_prompt_owner_rejects_caller_evidence_owner_override() -> None:
    manager = ContextManager(hypothesis_problem_evidence=_problem_evidence())
    prompt_owner = subject.ProposalPromptProjectionAuthority()
    graph = generation._install_checkpoint_a_authorities(
        registry=object(),
        code_source_owner=object(),
        context_manager=manager,
        prompt_owner=prompt_owner,
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(graph)
    manager._install_hypothesis_generation_authority(graph.context_manager)
    prompt_owner._install_hypothesis_generation_authority(graph.prompt_owner)
    view = generation._issue_generation_view(
        graph.registry,
        root_identity=object(),
        root_generation=11,
        branch_owner=object(),
        hypothesis_bundle=(object(),),
        prior_head=object(),
        reservation_id="reservation-override",
        h_bundle_digest=_H_BUNDLE_DIGEST,
        owner_context_json=_owner_context(),
    )
    request = generation._issue_code_source_request(graph.registry, view)
    generation._claim_code_source_request(graph.code_source_owner, request)
    content = b"SOURCE = 1\n"
    source = generation._issue_code_source(
        graph.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_digest(b"selected-manifest"),
        code_hash=_digest(b"base-code"),
        snapshot_hash=_BASE_SNAPSHOT_HASH,
        entries=(("solution_pool.py", content, _digest(content), True, True),),
    )
    generation._inspect_code_source(graph.registry, source, view=view)
    generation._claim_code_source_for_evidence(graph.context_manager, source)
    tainted = _problem_evidence()
    tainted["branch_id"] = "caller-branch"
    provider_context_json = _canonical(tainted)
    evidence_governance = _canonical(
        {
            "configured_keys": sorted(tainted),
            "configured_problem_evidence_sha256": _digest(provider_context_json),
            "provider_context_sha256": _digest(provider_context_json),
            "schema_version": "hypothesis-problem-evidence-governance.v1",
        }
    )
    evidence = generation._issue_problem_evidence(
        graph.context_manager,
        source,
        provider_context_json=provider_context_json,
        governance_json=evidence_governance,
    )
    prompt_source = generation._issue_prompt_source(
        graph.registry,
        view=view,
        code_source=source,
        evidence=evidence,
    )

    with pytest.raises(subject.HypothesisPromptRejectedError):
        prompt_owner.bind_hypothesis_prompt(prompt_source)


def test_prompt_owner_marks_unexpected_render_failure_unknown_with_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness()

    def fail_render(
        _render_kind: str,
        _snapshot: ProposalContextSnapshot,
    ) -> subject.AuthoritativePromptProjection:
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(
        subject.ProposalPromptProjectionAuthority,
        "project",
        staticmethod(fail_render),
    )
    with pytest.raises(subject.HypothesisPromptUnknownError) as raised:
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)
    assert isinstance(raised.value.__cause__, RuntimeError)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)


def test_prompt_owner_marks_non_exception_render_failure_then_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness()

    def interrupt_render(
        _render_kind: str,
        _snapshot: ProposalContextSnapshot,
    ) -> subject.AuthoritativePromptProjection:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        subject.ProposalPromptProjectionAuthority,
        "project",
        staticmethod(interrupt_render),
    )
    with pytest.raises(KeyboardInterrupt):
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        harness.prompt_owner.bind_hypothesis_prompt(harness.prompt_source)


def test_prompt_owner_installation_is_exact_and_one_shot() -> None:
    owner = subject.ProposalPromptProjectionAuthority()
    other = subject.ProposalPromptProjectionAuthority()
    graph = generation._install_checkpoint_a_authorities(
        registry=object(),
        code_source_owner=object(),
        context_manager=object(),
        prompt_owner=owner,
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(graph)
    with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
        other._install_hypothesis_generation_authority(graph.prompt_owner)
    owner._install_hypothesis_generation_authority(graph.prompt_owner)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        owner._install_hypothesis_generation_authority(graph.prompt_owner)
