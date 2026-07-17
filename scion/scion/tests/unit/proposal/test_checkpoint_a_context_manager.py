from __future__ import annotations

import builtins
import hashlib
import json
from dataclasses import dataclass

import pytest

from scion.proposal import hypothesis_generation_authority as generation
from scion.proposal.context_manager import manager as subject


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(slots=True)
class _Harness:
    manager: subject.ContextManager
    graph: generation._CheckpointAAuthorities
    view: generation.HypothesisGenerationView
    source: generation.HypothesisCodeSource


_LIVE_HARNESSES: list[_Harness] = []
_LIVE_GRAPHS: list[generation._CheckpointAAuthorities] = []


def _config() -> dict[str, object]:
    return {
        "problem_summary": "CVRP research problem",
        "research_surfaces": [
            {
                "allowed_actions": ["modify"],
                "kind": "policy",
                "name": "solver_design",
                "target_files": ["solution_pool.py"],
            }
        ],
        "available_actions": ["modify"],
        "experiment_history": [
            {
                "attempt_id": "h-1",
                "candidate_composition": {
                    "current_step": {"hypothesis_id": "h-1"}
                },
                "source_branch_id": "branch-1",
            }
        ],
    }


def _harness(config: dict[str, object]) -> _Harness:
    manager = subject.ContextManager(hypothesis_problem_evidence=config)
    registry = object()
    code_owner = object()
    prompt_owner = object()
    graph = generation._install_checkpoint_a_authorities(
        registry=registry,
        code_source_owner=code_owner,
        context_manager=manager,
        prompt_owner=prompt_owner,
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(graph)
    manager._install_hypothesis_generation_authority(graph.context_manager)
    view = generation._issue_generation_view(
        graph.registry,
        root_identity=object(),
        root_generation=3,
        branch_owner=object(),
        hypothesis_bundle=(object(),),
        prior_head=object(),
        reservation_id="reservation-1",
        h_bundle_digest=_digest(b"bundle"),
        owner_context_json=b'{"schema_version":"test-owner-context.v1"}',
    )
    request = generation._issue_code_source_request(graph.registry, view)
    generation._claim_code_source_request(graph.code_source_owner, request)
    content = b"def solve():\n    return 1\n"
    source = generation._issue_code_source(
        graph.code_source_owner,
        request,
        source_kind="base_champion",
        selected_manifest_digest=_digest(b"manifest"),
        code_hash=_digest(b"code"),
        snapshot_hash=_digest(b"snapshot"),
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
    harness = _Harness(manager=manager, graph=graph, view=view, source=source)
    _LIVE_HARNESSES.append(harness)
    return harness


def _claim_evidence_projection(
    harness: _Harness,
    evidence: generation.HypothesisProblemEvidenceProjection,
) -> generation._ProblemEvidenceProjection:
    prompt_source = generation._issue_prompt_source(
        harness.graph.registry,
        view=harness.view,
        code_source=harness.source,
        evidence=evidence,
    )
    _, _, projection = generation._claim_prompt_source(
        harness.graph.prompt_owner,
        prompt_source,
    )
    return projection


def test_context_manager_claims_once_and_issues_detached_canonical_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _config()
    harness = _harness(configured)
    configured["problem_summary"] = "mutated"
    surfaces = configured["research_surfaces"]
    assert isinstance(surfaces, list)
    surfaces[0]["name"] = "mutated"  # type: ignore[index]

    def fail_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("checkpoint-A ContextManager read the filesystem")

    monkeypatch.setattr(builtins, "open", fail_open)
    evidence = harness.manager._project_hypothesis_problem_evidence(
        harness.source
    )
    projection = _claim_evidence_projection(harness, evidence)

    provider_context = json.loads(projection.provider_context_json)
    assert provider_context["problem_summary"] == "CVRP research problem"
    assert provider_context["research_surfaces"][0]["name"] == "solver_design"
    assert projection.provider_context_json == json.dumps(
        provider_context,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    governance = json.loads(projection.governance_json)
    assert governance == {
        "configured_keys": sorted(provider_context),
        "configured_problem_evidence_sha256": _digest(
            projection.provider_context_json
        ),
        "provider_context_sha256": _digest(projection.provider_context_json),
        "schema_version": "hypothesis-problem-evidence-governance.v1",
    }


@pytest.mark.parametrize(
    "configured",
    [
        {"branch_id": "caller-branch"},
        {"champion_operators_code": "caller source"},
        {"problem_summary": "CVRP", "unknown": True},
        {"problem_summary": "CVRP", "research_surfaces": [object()]},
        {"problem_summary": lambda: "CVRP"},
    ],
)
def test_context_manager_configuration_rejects_owner_source_and_opaque_values(
    configured: dict[str, object],
) -> None:
    with pytest.raises(subject.HypothesisProblemEvidenceRejectedError):
        subject.ContextManager(hypothesis_problem_evidence=configured)


def test_context_manager_configuration_rejects_cycles() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(subject.HypothesisProblemEvidenceRejectedError):
        subject.ContextManager(
            hypothesis_problem_evidence={
                "problem_summary": "CVRP",
                "research_surfaces": [
                    {"name": "solver_design", "metadata": cyclic}
                ],
            }
        )


def test_context_manager_installation_is_exact_one_shot_and_callback_free() -> None:
    manager = subject.ContextManager(hypothesis_problem_evidence=_config())
    other_manager = subject.ContextManager(hypothesis_problem_evidence=_config())
    graph = generation._install_checkpoint_a_authorities(
        registry=object(),
        code_source_owner=object(),
        context_manager=manager,
        prompt_owner=object(),
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(graph)
    with pytest.raises(generation.InvalidHypothesisGenerationCapabilityError):
        other_manager._install_hypothesis_generation_authority(
            graph.context_manager
        )
    manager._install_hypothesis_generation_authority(graph.context_manager)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        manager._install_hypothesis_generation_authority(graph.context_manager)

    callback_manager = subject.ContextManager(
        adapter=object(),
        hypothesis_problem_evidence=_config(),
    )
    callback_graph = generation._install_checkpoint_a_authorities(
        registry=object(),
        code_source_owner=object(),
        context_manager=callback_manager,
        prompt_owner=object(),
        proposal_owner=object(),
        provider=object(),
    )
    _LIVE_GRAPHS.append(callback_graph)
    with pytest.raises(subject.HypothesisProblemEvidenceRejectedError):
        callback_manager._install_hypothesis_generation_authority(
            callback_graph.context_manager
        )


def test_deterministic_evidence_rejection_spends_the_claim() -> None:
    configured = _config()
    configured["research_surfaces"] = []
    harness = _harness(configured)

    with pytest.raises(subject.HypothesisProblemEvidenceRejectedError):
        harness.manager._project_hypothesis_problem_evidence(harness.source)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        generation._claim_code_source_for_evidence(
            harness.graph.context_manager,
            harness.source,
        )


def test_nested_owner_source_override_rejects_after_claim_before_issuance() -> None:
    configured = _config()
    configured["problem_object"] = {"branch_id": "caller-branch"}
    harness = _harness(configured)

    with pytest.raises(subject.HypothesisProblemEvidenceRejectedError):
        harness.manager._project_hypothesis_problem_evidence(harness.source)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        generation._claim_code_source_for_evidence(
            harness.graph.context_manager,
            harness.source,
        )


def test_unexpected_evidence_failure_is_unknown_with_original_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(_config())

    def fail_after_claim(_configured_json: bytes) -> bytes:
        raise RuntimeError("projection exploded")

    monkeypatch.setattr(subject, "_checkpoint_a_provider_context", fail_after_claim)
    with pytest.raises(subject.HypothesisProblemEvidenceUnknownError) as raised:
        harness.manager._project_hypothesis_problem_evidence(harness.source)
    assert isinstance(raised.value.__cause__, RuntimeError)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        generation._claim_code_source_for_evidence(
            harness.graph.context_manager,
            harness.source,
        )


def test_non_exception_evidence_failure_is_marked_unknown_then_propagated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(_config())

    def interrupt_after_claim(_configured_json: bytes) -> bytes:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        subject,
        "_checkpoint_a_provider_context",
        interrupt_after_claim,
    )
    with pytest.raises(KeyboardInterrupt):
        harness.manager._project_hypothesis_problem_evidence(harness.source)
    with pytest.raises(generation.HypothesisGenerationLifecycleError):
        generation._claim_code_source_for_evidence(
            harness.graph.context_manager,
            harness.source,
        )
