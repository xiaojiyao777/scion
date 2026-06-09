from __future__ import annotations

from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.mechanism_novelty import MechanismNoveltyGate
from scion.proposal.tools import ProposalToolContext


def _hypothesis(
    mechanism_id: str,
    *,
    text: str = "Add targeted multi relocate to improve total_distance.",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness="Prior local search missed this relocation pattern.",
        expected_effect="Improve total_distance.",
        mechanism_changes=(MechanismChange(id=mechanism_id, change_type="add"),),
        novelty_signature={
            "algorithm_family": "targeted_multi_relocate",
            "improvement_strategy": mechanism_id,
            "acceptance_strategy": "preserve_existing_acceptance",
            "runtime_budget_strategy": "bounded_pairs",
        },
    )


def _screening_result(*, win_rate: float = 0.0) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=16,
            wins=0,
            losses=0,
            ties=16,
            win_rate=win_rate,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/metrics.json",
    )


def _step(hypothesis: HypothesisProposal) -> StepRecord:
    return StepRecord(
        round_num=2,
        branch_id="branch-1",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=_screening_result(),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )


def _context(*steps: StepRecord, adapter=None) -> ProposalToolContext:
    return ProposalToolContext(
        session_id="session",
        campaign_id="campaign",
        branch=Branch("branch-1", BranchState.EXPLORE, 1, "champ"),
        step_history=steps,
        adapter=adapter,
    )


def test_repeated_mechanism_id_is_duplicate_diagnostic_not_hard_block() -> None:
    previous = _hypothesis("targeted_multi_relocate")
    candidate = _hypothesis("targeted_multi_relocate")

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "repeated_mechanism"
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "targeted_multi_relocate"
    assert "SCREENING_FAIL_WIN_RATE" in result.reason


def test_materially_different_repeated_mechanism_is_allowed() -> None:
    previous = _hypothesis("acceptance_reheat")
    candidate = _hypothesis(
        "acceptance_reheat",
        text=(
            "Add acceptance reheat with a materially different trigger based on "
            "runtime budget under-spend rather than plateau length."
        ),
    )

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is None


def test_shared_acceptance_strategy_does_not_define_repeated_mechanism() -> None:
    previous = _hypothesis(
        "adaptive_sa_reheat",
        text="Add adaptive SA reheat to improve plateau escape.",
    )
    candidate = _hypothesis(
        "route_removal",
        text="Add route removal destroy to diversify the destroy portfolio.",
    )
    previous.novelty_signature = {
        "algorithm_family": "acceptance_control",
        "improvement_strategy": "adaptive_sa_reheat",
        "acceptance_strategy": "simulated_annealing+adaptive_operator_weights",
        "runtime_budget_strategy": "bounded",
    }
    candidate.novelty_signature = {
        "algorithm_family": "destroy_repair",
        "improvement_strategy": "route_removal",
        "acceptance_strategy": "simulated_annealing+adaptive_operator_weights",
        "runtime_budget_strategy": "bounded",
    }

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is None


def test_shared_broad_algorithm_family_does_not_block_distinct_mechanism_ids() -> None:
    previous = _hypothesis(
        "intra_two_opt",
        text="Add intra-route 2-opt reversal.",
    )
    candidate = _hypothesis(
        "intra_swap",
        text="Add intra-route swap neighborhood.",
    )
    previous.novelty_signature = {
        "algorithm_family": "ALNS+VNS",
        "improvement_strategy": "intra_two_opt",
        "runtime_budget_strategy": "bounded",
    }
    candidate.novelty_signature = {
        "algorithm_family": "ALNS+VNS",
        "improvement_strategy": "intra_swap",
        "runtime_budget_strategy": "bounded",
    }

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is None


def test_generic_near_duplicate_signature_is_advisory_not_hard_block() -> None:
    previous = _hypothesis(
        "inter_route_exchange",
        text="Try an inter-route exchange local-search variant.",
    )
    candidate = _hypothesis(
        "intra_route_swap",
        text="Try an intra-route swap local-search variant.",
    )

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "near_duplicate_mechanism_signature"
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    diagnostic = result.to_diagnostic(candidate)
    assert diagnostic["blocking"] is False
    assert diagnostic["screening_allowed"] is True
    assert "generic_signature" in diagnostic["evidence"][1]


def test_registry_wiring_id_does_not_block_distinct_primary_mechanism() -> None:
    previous = _hypothesis(
        "vns_operator_registry",
        text="Modify VNS operator registry wiring for a failed local-search attempt.",
    )
    candidate = HypothesisProposal(
        hypothesis_text=(
            "Add knn_candidate_list local-search filtering and wire it through "
            "the existing VNS operator registry."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness="Local search scans too many route positions.",
        expected_effect="Improve total_distance with bounded candidate lists.",
        mechanism_changes=(
            MechanismChange(id="knn_candidate_list", change_type="add"),
            MechanismChange(id="vns_operator_registry", change_type="modify"),
        ),
        novelty_signature={
            "algorithm_family": "ALNS+VNS",
            "improvement_strategy": "knn_candidate_list_filtering",
            "acceptance_strategy": "preserve_existing_acceptance",
            "runtime_budget_strategy": "bounded_knn_candidates",
        },
    )

    result = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )

    assert result is None


def test_broad_algorithm_family_is_provider_declared_not_generic_default() -> None:
    class Provider:
        def active_subject_taxonomy(self, context=None, *, surface=None, subject_id=None):
            return {"mechanism_broad_family_ids": ("local_search",)}

    class Adapter:
        def active_subject_policy_provider(self):
            return Provider()

    previous = _hypothesis("first")
    candidate = _hypothesis("second")
    previous.mechanism_changes = ()
    candidate.mechanism_changes = ()
    previous.novelty_signature = {"algorithm_family": "local_search"}
    candidate.novelty_signature = {"algorithm_family": "local_search"}

    without_provider = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous)),
    )
    with_provider = MechanismNoveltyGate().evaluate(
        candidate,
        context=_context(_step(previous), adapter=Adapter()),
    )

    assert without_provider is not None
    assert without_provider.failure_category == "repeated_mechanism"
    assert without_provider.result_kind == "duplicate_diagnostic"
    assert without_provider.gate_action == "diagnostic"
    assert without_provider.is_hard_block is False
    assert with_provider is None
