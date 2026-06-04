from __future__ import annotations

from dataclasses import fields
import inspect

from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    DecisionFeatures,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context import cross_branch_research as cross_branch_module
from scion.proposal.context import (
    cross_branch_research_support as cross_branch_support_module,
)
from scion.proposal.context.cross_branch_research import (
    build_cross_branch_research_map,
    render_cross_branch_research_map,
)


def _branch(
    branch_id: str,
    *,
    state: BranchState = BranchState.EXPLORE,
    mechanism_ids: tuple[str, ...] = (),
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_mechanism_ids=mechanism_ids,
    )


def _screening_step(
    branch_id: str,
    *,
    round_num: int,
    mechanism_id: str,
    target_file: str = "policies/base.py",
    change_locus: str = "algorithm_design",
    action: str = "modify",
    wins: int = 0,
    losses: int = 0,
    reason_codes: tuple[str, ...] = (),
    gate_outcome: str = "continue",
    stage: ExperimentStage = ExperimentStage.SCREENING,
) -> StepRecord:
    stats = EvalStats(
        n_cases=4,
        wins=wins,
        losses=losses,
        ties=4 - wins - losses,
        win_rate=wins / 4,
        median_delta=0.02 if wins else (-0.02 if losses else 0.0),
        ci_low=-0.05,
        ci_high=0.08,
    )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="Tainted planning text should stay proposal-only.",
            change_locus=change_locus,
            action=action,
            target_file=target_file,
            mechanism_changes=(
                MechanismChange(id=mechanism_id, change_type="modify"),
            ),
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=gate_outcome,
            reason_codes=reason_codes,
            exposed_summary="filtered screening summary",
            raw_metrics_ref="/internal/raw-metrics.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=reason_codes,
    )


def test_cross_branch_research_map_is_tainted_and_finds_near_duplicates() -> None:
    current = _branch(
        "branch-a",
        mechanism_ids=("bounded_probe",),
    )
    sibling = _branch(
        "branch-b",
        mechanism_ids=("bounded_probe_variant",),
    )
    sibling.rollback_count = 1
    sibling.last_rollback_reason = "quality_block_checkpoint_rollback"
    sibling.best_quality_checkpoint_id = "checkpoint-1"
    sibling.branch_lifecycle_policy_blocks = 1
    validation_only = _branch("branch-hidden")
    steps = [
        _screening_step(
            "branch-a",
            round_num=1,
            mechanism_id="bounded_probe",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        ),
        _screening_step(
            "branch-b",
            round_num=1,
            mechanism_id="bounded_probe_variant",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        ),
        _screening_step(
            "branch-hidden",
            round_num=1,
            mechanism_id="bounded_probe_v2",
            stage=ExperimentStage.VALIDATION,
            wins=4,
            gate_outcome="pass",
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, sibling, validation_only],
        steps,
    )
    rendered = render_cross_branch_research_map(payload)

    assert payload["schema_version"] == "cross_branch_research.v1"
    assert payload["taint"] == "proposal_research_feedback"
    assert payload["decision_input_policy"] == "excluded_from_decision_features"
    assert payload["exposure_policy"] == "screening_and_safe_pre_protocol_only"
    assert {item["branch_id"] for item in payload["branches"]} >= {
        "branch-a",
        "branch-b",
    }
    assert "branch-hidden" not in {
        item["branch_id"]
        for item in payload["branches"]
        if item.get("recent_attempts")
    }

    hint_types = {item["hint_type"] for item in payload["similarity_hints"]}
    assert hint_types & {"near_duplicate", "saturated_family"}
    first_hint = payload["similarity_hints"][0]
    assert set(first_hint["branch_ids"]) == {"branch-a", "branch-b"}
    assert first_hint["shared_signature"]["target_file"] == "policies/base.py"
    assert first_hint["shared_signature"]["change_locus"] == "algorithm_design"
    assert first_hint["shared_signature"]["action"] == "modify"
    sibling_summary = {
        item["branch_id"]: item for item in payload["branches"]
    }["branch-b"]
    lifecycle = sibling_summary["lifecycle_summary"]
    assert lifecycle["rollback_count"] == 1
    assert lifecycle["best_quality_checkpoint_id"] == "checkpoint-1"
    assert "quality_block_checkpoint_rollback" in lifecycle["reason_codes"]

    lesson_scopes = {item["scope"] for item in payload["lessons"]}
    assert "branch_local" in lesson_scopes
    assert "cross_branch" in lesson_scopes
    lesson_types = {item["lesson_type"] for item in payload["lessons"]}
    assert "weak_positive" in lesson_types
    assert lesson_types & {"near_duplicate", "saturated_family"}
    assert payload["lesson_cards"]
    first_card = payload["lesson_cards"][0]
    assert {
        "failure_mode",
        "evidence_strength",
        "transferability",
        "recommended_action",
        "affected_stage",
        "confidence",
        "reason_codes",
    } <= set(first_card)
    assert payload["novelty_pressure"]["policy"] == "proposal_only"
    assert payload["portfolio_guidance"]

    assert "excluded_from_decision_features" in rendered
    assert "raw_metrics_ref" not in rendered
    assert "/internal/raw-metrics.json" not in rendered


def test_cross_branch_research_structured_guidance_is_generic() -> None:
    current = _branch(
        "branch-weak",
        mechanism_ids=("bounded_signal_refine",),
    )
    no_effect_a = _branch(
        "branch-flat-a",
        mechanism_ids=("flat_probe",),
    )
    no_effect_b = _branch(
        "branch-flat-b",
        mechanism_ids=("flat_probe_variant",),
    )
    abandoned = _branch(
        "branch-closed",
        state=BranchState.ABANDONED,
        mechanism_ids=("closed_probe",),
    )
    steps = [
        _screening_step(
            "branch-weak",
            round_num=1,
            mechanism_id="bounded_signal_refine",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        ),
        _screening_step(
            "branch-flat-a",
            round_num=1,
            mechanism_id="flat_probe",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        ),
        _screening_step(
            "branch-flat-b",
            round_num=1,
            mechanism_id="flat_probe_variant",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, no_effect_a, no_effect_b, abandoned],
        steps,
    )

    allowed_actions = {"avoid", "refine", "retry", "diversify", "observe", "park"}
    evidence_strengths = {"weak", "moderate", "strong"}
    transferability = {"same_branch", "shared_signature", "cross_branch_pattern"}
    required_card_fields = {
        "failure_mode",
        "evidence_strength",
        "transferability",
        "recommended_action",
        "affected_stage",
        "confidence",
        "reason_codes",
    }
    for card in payload["lesson_cards"]:
        assert required_card_fields <= set(card)
        assert card["recommended_action"] in allowed_actions
        assert card["evidence_strength"] in evidence_strengths
        assert card["transferability"] in transferability
        assert 0.0 <= card["confidence"] <= 1.0
        assert "mechanism_signature" in card or "shared_signature" in card
        if card.get("scope") == "branch_local":
            assert card["mechanism_ids"]
            if card["branch_id"] != "branch-closed":
                assert card["target_files"]

    cards_by_branch = {
        card["branch_id"]: card
        for card in payload["lesson_cards"]
        if card.get("scope") == "branch_local"
    }
    assert cards_by_branch["branch-weak"]["lesson_type"] == "weak_positive"
    assert cards_by_branch["branch-weak"]["recommended_action"] == "refine"
    assert cards_by_branch["branch-flat-a"]["lesson_type"] == "no_effect"
    assert cards_by_branch["branch-flat-a"]["recommended_action"] in {
        "avoid",
        "diversify",
        "observe",
    }
    assert cards_by_branch["branch-closed"]["lesson_type"] == "abandoned"
    assert cards_by_branch["branch-closed"]["recommended_action"] in {
        "avoid",
        "diversify",
        "observe",
    }

    novelty = payload["novelty_pressure"]
    assert novelty["saturated_signatures"]
    assert any(
        item["dimension"] == "action"
        and item["pressure"] == "overused_action"
        for item in novelty["overused_dimensions"]
    )
    assert "create_new" in novelty["unexplored_action_pressure"]["unexplored_actions"]
    assert "remove" in novelty["unexplored_action_pressure"]["unexplored_actions"]

    guidance_by_type = {
        item["guidance_type"]: item for item in payload["portfolio_guidance"]
    }
    assert (
        guidance_by_type["refine_active_weak_positive"]["recommended_action"]
        == "refine"
    )
    assert (
        guidance_by_type["avoid_no_effect_checkpoint"]["recommended_action"]
        == "observe"
    )
    assert guidance_by_type["avoid_closed_lineage"]["recommended_action"] == "avoid"
    assert (
        guidance_by_type[
            "diversify_when_recent_signatures_saturated"
        ]["recommended_action"]
        == "diversify"
    )


def test_cross_branch_research_filters_unavailable_actions() -> None:
    current = _branch(
        "branch-a",
        mechanism_ids=("flat_probe",),
    )
    sibling = _branch(
        "branch-b",
        mechanism_ids=("flat_probe_variant",),
    )
    steps = [
        _screening_step(
            "branch-a",
            round_num=1,
            mechanism_id="flat_probe",
            target_file="policies/shared.py",
            change_locus="algorithm_design",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        ),
        _screening_step(
            "branch-b",
            round_num=2,
            mechanism_id="flat_probe_variant",
            target_file="policies/shared.py",
            change_locus="algorithm_design",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, sibling],
        steps,
        available_actions={"modify"},
    )

    novelty = payload["novelty_pressure"]
    assert novelty["allowed_actions"] == ["modify"]
    assert "unexplored_action_pressure" not in novelty
    assert novelty["in_action_diversity_pressure"]["dominant_action"] == "modify"
    assert (
        novelty["in_action_diversity_pressure"]["recommended_action"]
        == "diversify"
    )
    guidance = {
        item["guidance_type"]: item for item in payload["portfolio_guidance"]
    }
    assert (
        guidance["diversify_within_executable_action"]["recommended_action"]
        == "diversify"
    )


def test_cross_branch_research_map_does_not_extend_decision_features() -> None:
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert "cross_branch_research" not in decision_fields
    assert "cross_branch_research_payload" not in decision_fields
    assert "similarity_hints" not in decision_fields
    assert "lessons" not in decision_fields
    assert "lesson_cards" not in decision_fields
    assert "novelty_pressure" not in decision_fields
    assert "portfolio_guidance" not in decision_fields
    assert "hypothesis_text" not in decision_fields


def test_cross_branch_research_module_has_no_problem_specific_control_terms() -> None:
    source = (
        inspect.getsource(cross_branch_module)
        + inspect.getsource(cross_branch_support_module)
    ).lower()

    for term in ("cvrp", "route", "alns", "vns", "capacity", "demand", "fleet"):
        assert term not in source
