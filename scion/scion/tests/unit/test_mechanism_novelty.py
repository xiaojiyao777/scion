from __future__ import annotations

import pytest

from scion.proposal.mechanism_novelty import MechanismNoveltyResult
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


def test_mechanism_novelty_result_requires_auditable_evidence_for_hard_block() -> None:
    result = MechanismNoveltyResult(
        premise_check="contradicted",
        failure_category="premise_contradicted",
        mechanism="route_limit",
        reason="missing fact packet and contradicted span",
        evidence=("text match only",),
    )

    assert result.result_kind == "premise_contradiction"
    assert result.gate_action == "diagnostic"
    assert result.diagnostic_kind == "incomplete_premise_contradiction_evidence"
    assert result.is_hard_block is False

    with pytest.raises(ValueError):
        result.to_rejection(_solver_design_hypothesis("Route limit is absent."))


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
    assert result.fact_packet_digest == snapshot["active_algorithm_facts"][
        "fact_packet_digest"
    ]
    assert result.fact_provenance
    assert result.contradicted_fact_ids == MECHANISM_FACT_IDS[mechanism]
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


def test_mechanism_novelty_gate_allows_vns_local_adaptive_neighborhood_ordering(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "VNS local search applies a fixed sequence of neighborhoods. "
                "Add a segment-based success counter and adaptive probability "
                "inside the VNS loop, analogous to ALNS adaptive weights but "
                "scoped only to VNS neighborhood ordering."
            ),
            target_weakness=(
                "The local-search phase uses fixed VNS neighborhood scheduling "
                "rather than adapting VNS neighborhood order from recent success."
            ),
            expected_effect=(
                "Improve total_distance by spending VNS effort on productive "
                "neighborhoods."
            ),
            mechanism_changes=[
                {
                    "id": "adaptive_vns_operator_weights",
                    "change_type": "add",
                },
                {"id": "vns_local_search", "change_type": "modify"},
            ],
            novelty_signature={
                "algorithm_family": "adaptive_vns",
                "improvement_strategy": (
                    "adaptive_weighted_vns_operator_selection_with_decay"
                ),
            },
        )
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


def test_mechanism_novelty_gate_allows_zone_cluster_contrast_with_existing_shaw(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "Unlike the existing _shaw_removal, which grows from a seed using "
        "distance and demand relatedness, add centroid zone cluster_removal "
        "that removes customers from a fixed geographic cell before repair."
    )

    assert (
        MechanismNoveltyGate().evaluate(
            _solver_design_hypothesis(text),
            context=context,
            active_solver_snapshot=snapshot,
        )
        is None
    )


def test_mechanism_novelty_gate_allows_single_seed_trajectory_with_portfolio(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "The current construction portfolio (sweep, Clarke-Wright, "
        "capacity-balanced, nearest-neighbor) generates a single seed solution "
        "per solve call, then follows one ALNS+VNS trajectory. Add a "
        "perturbation_restart in scheduler.py after stagnation."
    )

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


def test_mechanism_novelty_gate_allows_contiguous_segment_destroy_not_route_removal(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "The current ALNS destroy phase has existing operators "
        "(shaw_removal, worst_removal, route_removal), but lacks a "
        "positional/sequential destroy mechanism that removes a contiguous "
        "block of customers within a route segment. Add segment_destroy as a "
        "subroute window removal variant, not a whole-route removal."
    )

    assert (
        MechanismNoveltyGate().evaluate(
            _solver_design_hypothesis(text),
            context=context,
            active_solver_snapshot=snapshot,
        )
        is None
    )


def test_mechanism_novelty_gate_allows_double_bridge_scheduler_perturbation(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    text = (
        "Add double_bridge_perturbation in scheduler.py after ALNS stagnation. "
        "The existing destroy operators (shaw, route_removal, worst_removal) "
        "remove and reinsert customers, but none performs topological "
        "route-segment reconnection. This is not Shaw related removal and not "
        "proximity removal."
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
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "cross_route_or_opt_2_3"
    assert result.fact_ids == ("cvrp.local_search.cross_route_or_opt_2_3",)
    assert result.fact_packet_digest == snapshot["active_algorithm_facts"][
        "fact_packet_digest"
    ]


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
    assert result.contradicted_fact_ids == (
        "cvrp.local_search.cross_route_or_opt_2_3",
    )


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
    assert result.fact_ids == ("cvrp.local_search.cross_route_or_opt_2_3",)


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
        (
            "The active solver's VNS local search applies operators in a fixed "
            "round-robin sequence (_two_opt_intra, _relocate, _or_opt_1, "
            "_or_opt_2, _or_opt_3, _swap, _two_opt_star) with no inter-route "
            "node-pair distance filter. Add a neighbor-list filter for existing "
            "cross-route operators without adding any new Or-opt neighborhood."
        ),
        (
            "The active VNS phase applies every local-search operator "
            "(_two_opt_intra, _relocate, _or_opt_1/_2/_3, _swap, "
            "_two_opt_star) on every pass with no adaptive ordering or success "
            "feedback. Add adaptive_vns_op_order to reorder the existing "
            "operators by recent improvement evidence."
        ),
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
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "shaw_related_removal"
    assert "_shaw_removal" in " ".join([result.reason, *result.evidence])
    assert result.fact_ids == ("cvrp.destroy_repair.shaw_related_removal",)
    assert result.fact_packet_digest == snapshot["active_algorithm_facts"][
        "fact_packet_digest"
    ]


@pytest.mark.parametrize(
    "text,mechanism,fact_id",
    (
        (
            "Introduce a new intra-route 2-opt segment reversal neighborhood.",
            "intra_two_opt_reversal",
            "cvrp.local_search.intra_two_opt_reversal",
        ),
        (
            "Add Or-opt-1 single customer relocation as a new local-search neighborhood.",
            "or_opt_1_relocation",
            "cvrp.local_search.or_opt_1_relocation",
        ),
        (
            "Introduce a new whole route removal destroy operator.",
            "route_removal",
            "cvrp.destroy_repair.route_removal",
        ),
        (
            "Add a new random customer removal destroy operator.",
            "random_removal_destroy",
            "cvrp.destroy_repair.random_removal_destroy",
        ),
        (
            "Register an additional regret-2/regret-3 repair insertion operator.",
            "regret_insertion_repair",
            "cvrp.destroy_repair.regret_insertion_repair",
        ),
    ),
)
def test_mechanism_novelty_gate_blocks_explicit_existing_operator_duplicates(
    tmp_path,
    text: str,
    mechanism: str,
    fact_id: str,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.failure_category == "duplicate_mechanism"
    assert result.premise_check == "duplicate"
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == mechanism
    assert result.fact_ids == (fact_id,)
    assert result.fact_packet_digest == snapshot["active_algorithm_facts"][
        "fact_packet_digest"
    ]


def test_mechanism_novelty_gate_uses_agent_visible_fact_packet(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    fact_packet = snapshot["active_algorithm_facts"]
    text = (
        "The active solver has no proximity-cluster destroy removal, so add "
        "a seed-based related removal operator using distance and demand."
    )

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(text),
        context=context,
        active_solver_snapshot=snapshot,
    )

    assert result is not None
    assert result.snapshot_digest == fact_packet["snapshot_digest"]
    assert result.fact_packet_digest == fact_packet["fact_packet_digest"]
    assert result.contradicted_fact_ids == (
        "cvrp.destroy_repair.shaw_related_removal",
    )
    assert "cvrp.destroy_repair.shaw_related_removal" in {
        fact["fact_id"] for fact in fact_packet["facts"]
    }
    assert "fact_id:cvrp.destroy_repair.shaw_related_removal" in result.evidence


def test_mechanism_novelty_gate_uses_agent_visible_random_removal_fact(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    fact_packet = snapshot["active_algorithm_facts"]

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(
            "The active destroy portfolio lacks random customer removal, so add "
            "a random removal destroy operator."
        ),
        context=context,
        active_solver_snapshot=snapshot,
    )

    random_facts = [
        fact
        for fact in fact_packet["facts"]
        if fact.get("fact_id") == "cvrp.destroy_repair.random_removal_destroy"
    ]
    assert result is not None
    assert result.snapshot_digest == fact_packet["snapshot_digest"]
    assert result.fact_packet_digest == fact_packet["fact_packet_digest"]
    assert result.contradicted_fact_ids == (
        "cvrp.destroy_repair.random_removal_destroy",
    )
    assert random_facts
    random_fact = random_facts[0]
    assert random_fact["fact_digest"]
    assert random_fact["provenance"]["source"] == "active_algorithm_facts_provider"
    assert "fact_id:cvrp.destroy_repair.random_removal_destroy" in result.evidence


def test_mechanism_novelty_gate_does_not_use_private_summary_without_fact_packet(
    tmp_path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    snapshot = build_active_solver_snapshot(context)
    snapshot_without_facts = dict(snapshot)
    snapshot_without_facts.pop("active_algorithm_facts")

    result = MechanismNoveltyGate().evaluate(
        _solver_design_hypothesis(
            "The active solver lacks inter-route Or-opt segment relocation; "
            "add an NN-filtered cross-route segment relocation neighborhood."
        ),
        context=context,
        active_solver_snapshot=snapshot_without_facts,
    )

    assert result is None
