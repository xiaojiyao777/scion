from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.proposal.active_solver_snapshot import build_active_solver_snapshot
from scion.proposal.engine import _split_hypothesis_context
from scion.proposal.agentic_models import (
    AgenticProposalRequest,
    AgenticProposalStatus,
    AgenticTerminationReason,
)
from scion.proposal.agentic_session import AgenticProposalSession
from scion.proposal.mechanism_novelty import MechanismNoveltyGate
from scion.proposal.tools import ProposalToolRegistry
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    FakeCreative,
    FileAgenticSessionArtifactStore,
    HypothesisProposal,
    PatchProposal,
    _cvrp_context_with_champion,
    _valid_hypothesis_payload,
)


FALSE_PREMISES = (
    (
        "nearest_neighbor_only",
        (
            "The current baseline only builds a single nearest-neighbor seed "
            "before search; replace it with sweep and Clarke-Wright seeding."
        ),
        "construction_seed_strategy",
    ),
    (
        "uniform_adaptive_weights",
        (
            "Adaptive operator weights remain uniform and non-adaptive "
            "throughout the run; make them learn from accepted moves."
        ),
        "adaptive_operator_weights",
    ),
    (
        "missing_cross_route_or_opt",
        (
            "The active solver is missing cross-route Or-opt 2/3, so add "
            "those cross-route route relocation neighborhoods."
        ),
        "cross_route_or_opt_2_3",
    ),
    (
        "missing_inter_route_or_opt_segment_relocation",
        (
            "The active solver lacks inter-route Or-opt segment relocation; "
            "add an NN-filtered cross-route segment relocation neighborhood."
        ),
        "cross_route_or_opt_2_3",
    ),
    (
        "missing_shaw_related_removal",
        (
            "The active solver has no proximity-cluster destroy removal, so add "
            "a seed-based related removal operator using distance and demand."
        ),
        "shaw_related_removal",
    ),
    (
        "missing_cross_route_tail_exchange",
        (
            "The active solver lacks cross-route tail swap / suffix exchange, "
            "so add that neighborhood to local search."
        ),
        "cross_route_tail_exchange",
    ),
    (
        "unreachable_feasibility_crossing",
        (
            "Reset adaptive weights on the first infeasible-to-feasible "
            "feasibility crossing in the current search state."
        ),
        "feasibility_crossing",
    ),
    (
        "unproven_construction_route_merge",
        (
            "The current construction can produce more routes than route_limit, "
            "leaving ALNS with fleet_violation to repair. Add "
            "construction_route_merge while len(routes) > route_limit."
        ),
        "route_limit_fleet_repair",
    ),
)


def _solver_design_hypothesis(text: str) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=text,
            target_weakness=text,
            expected_effect="Improve the active solver design.",
        )
    )


class SequentialHypothesisCreative(FakeCreative):
    def __init__(self, hypotheses: list[HypothesisProposal]) -> None:
        super().__init__(hypothesis=hypotheses[-1])
        self.hypotheses = list(hypotheses)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.hypotheses:
            return self.hypothesis
        return self.hypotheses.pop(0)


@pytest.mark.parametrize("case_name,text,mechanism", FALSE_PREMISES)
def test_mechanism_novelty_gate_blocks_known_false_premises(
    tmp_path,
    case_name: str,
    text: str,
    mechanism: str,
) -> None:
    del case_name
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.failure_category == "premise_contradicted"
    assert result.premise_check == "contradicted"
    assert result.mechanism == mechanism
    assert result.evidence
    if mechanism == "shaw_related_removal":
        rendered = " ".join([result.reason, *result.evidence])
        assert "_shaw_removal" in rendered
        assert "distance" in rendered
        assert "demand" in rendered
        assert "route" in rendered


def test_mechanism_novelty_gate_allows_adaptive_update_formula_improvement(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    hypothesis = _solver_design_hypothesis(
        "Improve adaptive weight update rate and score formula so accepted "
        "moves react faster without changing the operator set."
    )

    assert (
        MechanismNoveltyGate().evaluate(
            hypothesis,
            context=context,
        active_solver_snapshot=snapshot,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    (
        "Improve Shaw relatedness weights so distance and demand are balanced better.",
        "Make existing related removal adaptive without adding a new operator.",
        "Add stochastic p sampling to the existing Shaw removal selection.",
        "Diversify existing related removal with a mild route-spread penalty.",
    ),
)
def test_mechanism_novelty_gate_allows_shaw_related_improvements(
    tmp_path,
    text: str,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)

    assert (
        MechanismNoveltyGate().evaluate(
            _solver_design_hypothesis(text),
            context=context,
        active_solver_snapshot=snapshot,
        )
        is None
    )


def test_mechanism_novelty_gate_allows_segment_chain_repair_not_shaw_duplicate(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "Existing Shaw-related destroy operators remove individual customers, "
        "but the active solver lacks contiguous segment-chain repair as a unit."
    )

    assert (
        MechanismNoveltyGate().evaluate(
            _solver_design_hypothesis(text),
            context=context,
            active_solver_snapshot=snapshot,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    (
        (
            "Add cross-route Or-opt 2 and 3 as new neighborhoods to the active "
            "local search."
        ),
        (
            "Introduce NN-filtered inter-route Or-opt segment relocation as a "
            "new neighborhood for the active local search."
        ),
        (
            "Implement cross-route segment relocation as a new Or-opt operator "
            "between different route pairs."
        ),
    ),
)
def test_mechanism_novelty_gate_blocks_explicit_duplicate_or_opt_addition(
    tmp_path,
    text: str,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    hypothesis = HypothesisProposal(
        hypothesis_text=text,
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=text,
        expected_effect="Add the claimed new neighborhood.",
    )

    result = MechanismNoveltyGate().evaluate(
        hypothesis,
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.failure_category == "duplicate_mechanism"
    assert result.premise_check == "duplicate"
    assert result.mechanism == "cross_route_or_opt_2_3"


def test_mechanism_novelty_gate_blocks_unsystematic_cross_route_segment_claim(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "The existing VNS has Or-opt moves, but it does not systematically "
        "evaluate moving ordered segments of 2 or 3 customers across routes."
    )

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "cross_route_or_opt_2_3"


def test_mechanism_novelty_gate_blocks_cross_route_oropt_duplicate_from_smoke_round(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "The VNS already has an existing Or-Opt-3 pass, but it lacks "
        "cross-route segment exchange / Or-Opt for chains of 2-3 customers "
        "between routes; add cross_route_oropt after the existing pass."
    )

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.mechanism == "cross_route_or_opt_2_3"


@pytest.mark.parametrize(
    "text",
    (
        "Improve existing cross-route Or-opt candidate ordering and delta scoring.",
        (
            "Add nearest-neighbor candidate pruning to the existing Or-opt "
            "neighborhoods without adding a new operator."
        ),
        (
            "Tune current inter-route Or-opt segment relocation budget so the "
            "existing length-2 and length-3 moves are evaluated more selectively."
        ),
        "Add nearest-neighbor candidate filtering to cross-route Or-opt evaluation.",
        "The existing cross-route Or-opt lacks NN candidate filtering; add that filter.",
    ),
)
def test_mechanism_novelty_gate_allows_existing_or_opt_improvements(
    tmp_path,
    text: str,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)

    assert (
        MechanismNoveltyGate().evaluate(
            _solver_design_hypothesis(text),
            context=context,
        active_solver_snapshot=snapshot,
        )
        is None
    )


def test_mechanism_novelty_gate_blocks_duplicate_shaw_related_removal(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "Add a new proximity-cluster removal operator as a new destroy "
        "capability for the active ALNS solver."
    )

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.failure_category == "duplicate_mechanism"
    assert result.premise_check == "duplicate"
    assert result.mechanism == "shaw_related_removal"
    assert "_shaw_removal" in " ".join([result.reason, *result.evidence])


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
    creative = SequentialHypothesisCreative([rejected, accepted])
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

    retry_context = creative.hypothesis_contexts[1]
    retry_feedback = retry_context["agentic_hypothesis_semantic_rejections"][0]

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == (
        AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.hypothesis == accepted
    assert len(creative.hypothesis_contexts) == 2
    assert retry_feedback["source"] == "mechanism_novelty_gate"
    assert retry_feedback["premise_check"] == "contradicted"
    assert retry_feedback["failure_code"] == "proposal_premise_contradicted"
    assert retry_feedback["mechanism"] == "cross_route_or_opt_2_3"
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
    creative = SequentialHypothesisCreative([rejected, accepted])
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
    assert "agentic_hypothesis_semantic_rejections" in retry_manifest[
        "section_names"
    ]
    assert retry_manifest["section_statuses"][
        "agentic_hypothesis_semantic_rejections"
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

    assert len(creative.hypothesis_contexts) == 2
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
