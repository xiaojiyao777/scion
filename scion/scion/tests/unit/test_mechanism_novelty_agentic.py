from __future__ import annotations

import json
from dataclasses import replace

import pytest

from scion.proposal.tools import ContextExposurePolicy
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
def test_agentic_session_warns_on_mechanism_false_premise_and_enters_code(
    tmp_path,
    case_name: str,
    text: str,
    mechanism: str,
) -> None:
    del case_name
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
    hypothesis = _solver_design_hypothesis(text)
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="# material variant would be implemented here\n",
        premise_check="supported",
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
            hypothesis_context={"seed": "mechanism-novelty"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is patch
    assert output.failure_category is None
    assert output.structured_rejection is None
    assert creative.code_contexts
    code_context = creative.code_contexts[-1]
    warning = code_context["agentic_mechanism_novelty_warnings"][0]
    assert warning["warning_kind"] == "mechanism_premise_warning"
    assert warning["premise_check"] == "contradicted"
    assert warning["failure_category"] == "mechanism_premise_warning"
    assert warning["mechanism"] == mechanism
    assert warning["blocking"] is False
    assert warning["quality_block"] is False
    assert warning["fact_packet_digest"]
    assert warning["fact_ids"] == list(MECHANISM_FACT_IDS[mechanism])
    if mechanism == "shaw_related_removal":
        rendered = " ".join(
            [
                warning["reason"],
                warning["agent_guidance"],
            ]
        )
        assert "_shaw_removal" in rendered
        assert "missing" in rendered or "absent" in rendered
    assert not any(
        entry.get("source") == "mechanism_novelty_gate"
        for entry in output.failure_ledger["entries"]
    )
    assert any(
        observation["tool_name"] == "proposal.mechanism_novelty_diagnostic"
        for observation in code_context["agentic_tool_observations"]
    )


def test_novelty_gate_premise_warning_continues_without_semantic_retry(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
    rejected = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="# material variant would be implemented here\n",
        premise_check="supported",
    )
    creative = FakeCreative(hypothesis=rejected, patch=patch)
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
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert creative.hypothesis_contexts
    assert not any(
        "agentic_hypothesis_semantic_rejections" in context
        for context in creative.hypothesis_contexts
    )
    warning = creative.code_contexts[-1]["agentic_mechanism_novelty_warnings"][0]
    assert warning["source"] == "mechanism_novelty_gate"
    assert warning["premise_check"] == "contradicted"
    assert warning["warning_kind"] == "mechanism_premise_warning"
    assert warning["mechanism"] == "cross_route_or_opt_2_3"
    assert warning["fact_ids"] == ["cvrp.local_search.cross_route_or_opt_2_3"]
    assert warning["fact_packet_digest"]
    assert "active solver" in warning["reason"].lower()
    assert "material" in warning["agent_guidance"].lower()
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
            "agentic_hypothesis_retry_rule": "State the material difference.",
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
    assert "material difference" in rendered


def test_mechanism_premise_warning_records_diagnostic_observation(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
    hypothesis = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="# material variant would be implemented here\n",
        premise_check="supported",
    )
    creative = FakeCreative(hypothesis=hypothesis, patch=patch)
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
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    diagnostic_events = [
        event
        for event in output.transcript
        if event.metadata.get("diagnostic_kind") == "mechanism_premise_warning"
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert diagnostic_events
    assert diagnostic_events[-1].metadata["gate_action"] == "diagnostic"
    assert creative.code_contexts
    observations = creative.code_contexts[-1]["agentic_tool_observations"]
    diagnostic_observations = [
        item
        for item in observations
        if item["tool_name"] == "proposal.mechanism_novelty_diagnostic"
    ]
    assert diagnostic_observations
    assert "material" in json.dumps(diagnostic_observations[-1], sort_keys=True)


def test_repeated_novelty_gate_warning_does_not_fail_after_retry_budget(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
    repeated = _solver_design_hypothesis(
        "The active solver lacks inter-route Or-opt segment relocation; "
        "add an NN-filtered cross-route segment relocation neighborhood."
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="# material variant would be implemented here\n",
        premise_check="supported",
    )
    creative = SequentialHypothesisCreative([repeated, repeated])
    creative.patch = patch
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
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert creative.hypothesis_contexts
    assert not any(
        "agentic_hypothesis_semantic_rejections" in context
        for context in creative.hypothesis_contexts
    )
    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.failure_category is None
    assert output.structured_rejection is None
    assert not any(
        entry.get("source") == "mechanism_novelty_gate"
        for entry in output.failure_ledger["entries"]
    )
    warning = creative.code_contexts[-1]["agentic_mechanism_novelty_warnings"][0]
    assert warning["warning_kind"] == "mechanism_premise_warning"
    assert warning["quality_block"] is False


def test_duplicate_mechanism_gate_diagnostic_continues_to_code(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
    hypothesis = _solver_design_hypothesis(
        "Add cross-route Or-opt 2 and 3 as new neighborhoods to local search."
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="# material variant would be implemented here\n",
        premise_check="supported",
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
            hypothesis_context={"seed": "duplicate-diagnostic"},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_modules/local_search.py",
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

    duplicate_events = [
        event
        for event in output.transcript
        if event.metadata.get("result_kind") == "duplicate_diagnostic"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is patch
    assert creative.code_contexts
    code_context = creative.code_contexts[-1]
    assert "agentic_mechanism_novelty_warnings" in code_context
    warning = code_context["agentic_mechanism_novelty_warnings"][0]
    assert warning["warning_kind"] == "duplicate_risk"
    assert warning["mechanism"] == "cross_route_or_opt_2_3"
    assert warning["blocking"] is False
    assert warning["quality_block"] is False
    assert "material" in warning["agent_guidance"].lower()
    assert any(
        observation["tool_name"] == "proposal.mechanism_novelty_diagnostic"
        for observation in code_context["agentic_tool_observations"]
    )
    assert output.structured_rejection is None
    assert not any(
        entry.get("source") == "mechanism_novelty_gate"
        for entry in output.failure_ledger["entries"]
    )
    assert duplicate_events
    assert duplicate_events[-1].metadata["gate_action"] == "diagnostic"
    assert duplicate_events[-1].metadata["diagnostic_kind"] == "duplicate_risk"
    assert duplicate_events[-1].metadata["mechanism"] == "cross_route_or_opt_2_3"


def test_forced_surface_contradiction_still_hard_blocks_before_code(tmp_path) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(
        context,
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/baseline_modules/local_search.py",
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="acceptance_policy",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text="Tune acceptance policy while a solver_design surface is forced.",
            target_weakness="Wrong forced surface.",
            expected_effect="Should not pass hard boundary.",
        )
    )
    creative = FakeCreative(hypothesis=hypothesis)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-mechanism",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "forced-boundary"},
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

    assert output.status == AgenticProposalStatus.FAILED
    assert output.failure_category == "contract_boundary_failure"
    assert output.patch is None
    assert creative.code_contexts == []
    assert "forced_surface_constraint" in (output.failure_detail or "")


def test_agentic_session_code_context_exposes_shaw_evidence_for_premise_check(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(context, policy=ContextExposurePolicy())
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.failure_category is None
    assert output.patch is patch
    assert not any(
        entry.get("source") == "premise_check"
        for entry in output.failure_ledger["entries"]
    )
    duplicate_events = [
        event
        for event in output.transcript
        if event.metadata.get("result_kind") == "duplicate_diagnostic"
    ]
    assert duplicate_events
    assert duplicate_events[-1].metadata["source"] == "premise_check"
    assert creative.code_contexts
    rendered_context = json.dumps(creative.code_contexts[0], sort_keys=True)
    assert "agentic_active_solver_mechanisms" in rendered_context
    assert "_shaw_removal" in rendered_context
    assert "distance" in rendered_context
    assert "demand" in rendered_context
    assert "original-route relatedness" in rendered_context
