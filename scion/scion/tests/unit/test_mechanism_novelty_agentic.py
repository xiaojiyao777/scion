from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.tests.unit.mechanism_novelty_helpers import (
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalStatus,
    AgenticTerminationReason,
    FALSE_PREMISES,
    FileAgenticSessionArtifactStore,
    FakeCreative,
    HypothesisProposal,
    MECHANISM_FACT_IDS,
    MechanismNoveltyGate,
    PatchProposal,
    ProposalToolRegistry,
    SequentialHypothesisCreative,
    SimpleNamespace,
    _cvrp_context_with_champion,
    _solver_design_hypothesis,
    _split_hypothesis_context,
    _valid_hypothesis_payload,
    build_active_solver_snapshot,
)

@pytest.mark.parametrize("case_name,text,mechanism", FALSE_PREMISES)
def test_agentic_session_rejects_mechanism_false_premise_before_code_context(
    tmp_path,
    case_name: str,
    text: str,
    mechanism: str,
) -> None:
    del case_name
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = _solver_design_hypothesis(text)
    creative = FakeCreative(hypothesis=hypothesis)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    def build_code_context(_hypothesis):
        raise AssertionError("mechanism novelty rejection must stop before code")

    def approve_hypothesis(_hypothesis):
        raise AssertionError("mechanism novelty rejection must stop before approval")

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "mechanism-novelty"},
            build_code_context=build_code_context,
            approve_hypothesis=approve_hypothesis,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    tool_names = [
        event.metadata["tool_name"]
        for event in output.transcript
        if "tool_name" in event.metadata
    ]

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == AgenticTerminationReason.PREMISE_CONTRADICTED
    assert output.patch is None
    assert output.failure_category == "agent_grounding_failure"
    assert output.structured_rejection is not None
    assert output.structured_rejection["premise_check"] == "contradicted"
    assert output.structured_rejection["failure_category"] == "agent_grounding_failure"
    assert (
        output.structured_rejection["legacy_failure_category"]
        == "premise_contradicted"
    )
    assert (
        output.structured_rejection["failure_code"]
        == "proposal_premise_contradicted"
    )
    assert output.structured_rejection["agent_block_reason"] == "agent_quality_blocked"
    assert output.structured_rejection["mechanism"] == mechanism
    assert output.structured_rejection["screening_allowed"] is False
    assert output.structured_rejection["fact_packet_digest"]
    assert output.structured_rejection["contradicted_fact_ids"] == list(
        MECHANISM_FACT_IDS[mechanism]
    )
    assert output.structured_rejection["fact_provenance"]
    if mechanism == "shaw_related_removal":
        rendered = " ".join(
            [
                output.structured_rejection["reason"],
                *output.structured_rejection["evidence"],
            ]
        )
        assert "_shaw_removal" in rendered
        assert "distance" in rendered
        assert "demand" in rendered
        assert "route" in rendered
    assert output.failure_ledger["first_root_cause"] == "agent_grounding_failure"
    assert output.failure_ledger["latest_failure"] == "agent_grounding_failure"
    assert (
        output.failure_ledger["entries"][0]["failure_code"]
        == "proposal_premise_contradicted"
    )
    assert output.failure_ledger["entries"][0]["source"] == "mechanism_novelty_gate"
    assert creative.code_contexts == []
    assert "proposal.schema_preview" not in tool_names
    assert "proposal.contract_preview" not in tool_names
    assert "proposal.algorithm_smoke" not in tool_names


def test_novelty_gate_rejection_triggers_hypothesis_semantic_retry(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    rejected = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    accepted = _solver_design_hypothesis(
        "Improve existing cross-route Or-opt candidate ordering and delta scoring."
    )
    creative = SequentialHypothesisCreative([rejected, rejected, accepted])
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "semantic-retry"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
            },
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    retry_context = creative.hypothesis_contexts[2]
    retry_feedback = retry_context["agentic_hypothesis_semantic_rejections"][0]

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == (
        AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.hypothesis == accepted
    assert len(creative.hypothesis_contexts) == 3
    assert retry_feedback["source"] == "mechanism_novelty_gate"
    assert retry_feedback["premise_check"] == "contradicted"
    assert retry_feedback["failure_code"] == "proposal_premise_contradicted"
    assert retry_feedback["mechanism"] == "cross_route_or_opt_2_3"
    assert retry_feedback["contradicted_fact_ids"] == [
        "cvrp.local_search.cross_route_or_opt_2_3"
    ]
    assert retry_feedback["fact_packet_digest"]
    assert retry_feedback["fact_provenance"]
    assert "agentic_negative_fact_block" in retry_context
    assert "fact_id=cvrp.local_search.cross_route_or_opt_2_3" in retry_context[
        "agentic_negative_fact_block"
    ]
    assert "mechanism=cross_route_or_opt_2_3" in retry_context[
        "agentic_negative_fact_block"
    ]
    assert "active solver" in retry_feedback["reason"].lower()
    assert "_or_opt_2" in json.dumps(retry_feedback, sort_keys=True)
    assert "different mechanism family" in retry_context[
        "agentic_hypothesis_retry_rule"
    ]
    assert not any(
        entry.get("source") == "mechanism_novelty_gate"
        for entry in output.failure_ledger["entries"]
    )


def test_hypothesis_semantic_retry_feedback_is_api_visible_prompt_context() -> None:
    semantic_feedback = [
        {
            "source": "mechanism_novelty_gate",
            "premise_check": "contradicted",
            "mechanism": "cross_route_or_opt_2_3",
            "reason": "Existing _or_opt_2/_or_opt_3 already relocate segments.",
            "contradicted_fact_ids": ["cvrp.local_search.cross_route_or_opt_2_3"],
            "fact_packet_digest": "fact-packet-test-digest",
        }
    ]

    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "problem",
            "research_surfaces": "solver_design",
            "champion_operators_code": "code",
            "champion_stats": "stats",
            "agentic_hypothesis_semantic_rejections": semantic_feedback,
            "agentic_hypothesis_retry_rule": "Choose a different mechanism family.",
            "agentic_hypothesis_retry_attempt": 2,
        }
    )
    rendered = json.dumps(
        {"system_blocks": system_blocks, "user_prompt": user_prompt},
        sort_keys=True,
    )

    assert "Hypothesis Semantic Retry Feedback" in rendered
    assert "mechanism_novelty_gate" in rendered
    assert "_or_opt_2" in rendered
    assert "contradicted_fact_ids" in rendered
    assert "fact_packet_digest" in rendered
    assert "different mechanism family" in rendered


def test_hypothesis_semantic_retry_manifest_records_feedback_section(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    rejected = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    accepted = _solver_design_hypothesis(
        "Improve existing cross-route Or-opt candidate ordering and delta scoring."
    )
    creative = SequentialHypothesisCreative([rejected, rejected, accepted])
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "semantic-retry-manifest"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
            },
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in ref
    ]
    retry_manifests = [
        manifest
        for manifest in manifests
        if manifest.get("call_kind") == "hypothesis_semantic_retry"
    ]

    assert retry_manifests
    retry_manifest = retry_manifests[0]
    assert "hypothesis_semantic_retry_feedback" in retry_manifest[
        "section_names"
    ]
    assert retry_manifest["section_statuses"][
        "hypothesis_semantic_retry_feedback"
    ]["status"] == "included"


def test_repeated_novelty_gate_rejection_fails_after_semantic_retry(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    repeated = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    creative = SequentialHypothesisCreative([repeated, repeated])
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "semantic-retry-fail"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
            },
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert len(creative.hypothesis_contexts) == 3
    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == AgenticTerminationReason.PREMISE_CONTRADICTED
    assert output.failure_category == "agent_grounding_failure"
    assert output.structured_rejection["source"] == "mechanism_novelty_gate"
    assert output.structured_rejection["mechanism"] == "cross_route_or_opt_2_3"
    assert output.failure_ledger["entry_count"] == 1
    assert output.failure_ledger["entries"][0]["source"] == "mechanism_novelty_gate"


def test_agentic_session_code_context_exposes_shaw_evidence_for_premise_check(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    hypothesis = _solver_design_hypothesis(
        "Improve Shaw relatedness weights without adding a new destroy operator."
    )
    patch = PatchProposal(
        file_path="",
        action="modify",
        code_content="",
        premise_check="duplicate",
        premise_check_reason=(
            "Existing _shaw_removal already removes seed-related customers "
            "using distance, demand, and route relatedness."
        ),
    )
    creative = FakeCreative(hypothesis=hypothesis, patch=patch)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "shaw-code-context"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/destroy_repair.py",
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.failure_category == "duplicate_mechanism"
    assert output.failure_ledger["entries"][0]["source"] == "premise_check"
    assert creative.code_contexts
    rendered_context = json.dumps(creative.code_contexts[0], sort_keys=True)
    assert "agentic_active_solver_mechanisms" in rendered_context
    assert "_shaw_removal" in rendered_context
    assert "distance" in rendered_context
    assert "demand" in rendered_context
    assert "original-route relatedness" in rendered_context
