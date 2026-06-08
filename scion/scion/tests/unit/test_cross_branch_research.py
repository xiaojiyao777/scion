from __future__ import annotations

from dataclasses import fields
import inspect
import json

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
    cross_branch_research_coverage as cross_branch_coverage_module,
)
from scion.proposal.context import (
    cross_branch_research_summary as cross_branch_summary_module,
)
from scion.proposal.context import (
    cross_branch_research_support as cross_branch_support_module,
)
from scion.proposal.context import research_portfolio as research_portfolio_module
from scion.proposal.context.cross_branch_research import (
    build_cross_branch_research_map,
    render_cross_branch_research_map,
)
from scion.proposal.context.cross_branch_research_summary import (
    build_branch_summary,
    safe_prompt_steps,
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
    runtime_confidence: str = "high",
    runtime_evidence_status: str = "sufficient",
    mechanism_evidence: dict | None = None,
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
            mechanism_changes=(MechanismChange(id=mechanism_id, change_type="modify"),),
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
            runtime_confidence=runtime_confidence,
            runtime_evidence_status=runtime_evidence_status,
            mechanism_evidence=mechanism_evidence or {},
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
        item["branch_id"] for item in payload["branches"] if item.get("recent_attempts")
    }

    hint_types = {item["hint_type"] for item in payload["similarity_hints"]}
    assert hint_types & {"near_duplicate", "saturated_family"}
    first_hint = payload["similarity_hints"][0]
    assert set(first_hint["branch_ids"]) == {"branch-a", "branch-b"}
    assert first_hint["shared_signature"]["target_file"] == "policies/base.py"
    assert first_hint["shared_signature"]["change_locus"] == "algorithm_design"
    assert first_hint["shared_signature"]["action"] == "modify"
    sibling_summary = {item["branch_id"]: item for item in payload["branches"]}[
        "branch-b"
    ]
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
    assert payload["material_difference_audit_records"]
    assert payload["cross_branch_research_metadata"][
        "material_difference_requirement_count"
    ] == len(payload["material_difference_audit_records"])
    assert payload["portfolio_guidance"]
    assert payload["portfolio_steering"]["schema_version"] == "portfolio_steering.v1"
    assert payload["portfolio_steering"]["proposal_visibility_only"] is True
    assert payload["portfolio_steering"]["decision_features_excluded"] is True

    assert "excluded_from_decision_features" in rendered
    assert "raw_metrics_ref" not in rendered
    assert "/internal/raw-metrics.json" not in rendered


def test_cross_branch_research_branch_summary_extraction_is_modularized() -> None:
    current = _branch("branch-a", mechanism_ids=("bounded_probe",))
    sibling = _branch("branch-b", mechanism_ids=("flat_probe",))
    steps = [
        _screening_step(
            "branch-a",
            round_num=1,
            mechanism_id="bounded_probe",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        ),
        _screening_step(
            "branch-a",
            round_num=2,
            mechanism_id="bounded_probe_validation",
            stage=ExperimentStage.VALIDATION,
            wins=4,
            gate_outcome="pass",
        ),
    ]

    safe_steps = safe_prompt_steps(steps)
    expected_summary = build_branch_summary(
        branch_id="branch-a",
        branch=current,
        steps=safe_steps,
        is_current_branch=True,
        max_steps_per_branch=4,
    )
    payload = build_cross_branch_research_map(current, [current, sibling], steps)

    assert cross_branch_module._build_branch_summary.__module__.endswith(
        "cross_branch_research_summary"
    )
    assert cross_branch_module._portfolio_coverage.__module__.endswith(
        "cross_branch_research_coverage"
    )
    assert cross_branch_module._opportunity_gaps.__module__.endswith(
        "cross_branch_research_coverage"
    )
    assert payload["branches"][0] == expected_summary
    assert payload["branches"][0]["recent_attempts"][0]["round_num"] == 1
    assert "bounded_probe_validation" not in json.dumps(payload, sort_keys=True)


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
    avoid = novelty["avoid_signature_set"][0]
    assert avoid["priority"] == "high"
    assert avoid["pressure_type"] == "repeated_zero_effect_signature"
    assert avoid["shared_signature"] == {
        "mechanism_family": "flat",
        "target_file": "policies/shared.py",
        "action": "modify",
        "change_locus": "activation_policy",
    }
    assert avoid["sibling_duplication_allowed"] is False
    assert avoid["same_branch_refinement_allowed"] is False
    requirements = avoid["material_difference_requirements"]
    assert requirements["requirement_id"].startswith("mdr:requirement:")
    assert len(requirements["requirement_digest"]) == 64
    assert requirements["proposal_visibility_only"] is True
    assert requirements["decision_features_excluded"] is True
    assert requirements["minimum_requirement"] == (
        "change_one_or_more_generic_dimensions"
    )
    assert requirements["required_change_dimensions"] == [
        "mechanism_family",
        "target_file",
        "action",
        "change_locus",
        "effect_path",
    ]
    assert requirements["evidence_status_dimensions"] == [
        "activation_status",
        "effect_status",
        "runtime_evidence_confidence",
        "runtime_evidence_status",
    ]
    blocked = novelty["blocked_signature_pressure"][0]
    assert blocked["deterministic_screening_block"] is False
    assert blocked["counted_screening_pressure"] == (
        "avoid_nearby_counted_screening_without_material_difference"
    )
    assert novelty["material_difference_requirements"][0] == requirements
    records = novelty["material_difference_audit_records"]
    assert len(records) == 1
    record = records[0]
    assert record["record_type"] == "material_difference_requirement"
    assert record["record_id"].startswith("mdr:")
    assert len(record["record_digest"]) == 64
    assert record["generic_signature"] == avoid["shared_signature"]
    assert record["requirement"] == requirements
    assert record["proposal_visibility_only"] is True
    assert record["decision_features_excluded"] is True
    assert record["raw_branch_text_excluded"] is True
    assert record["raw_hypothesis_excluded"] is True
    assert record["llm_trace_excluded"] is True
    assert "MATERIAL_DIFFERENCE_REQUIREMENT" in record["reason_codes"]
    assert set(record["family_pressure"]["pressure_sources"]) == {
        "avoid_signature_set",
        "saturated_signatures",
    }
    assert "flat_probe" not in json.dumps(record, sort_keys=True)
    assert "Tainted planning text" not in json.dumps(record, sort_keys=True)
    assert payload["material_difference_audit_records"] == records
    assert payload["cross_branch_research_metadata"][
        "material_difference_record_ids"
    ] == [record["record_id"]]
    lesson_records = payload["branch_lesson_records"]
    assert lesson_records
    assert payload["cross_branch_research_metadata"][
        "branch_lesson_record_count"
    ] == len(lesson_records)
    assert payload["cross_branch_research_metadata"]["branch_lesson_record_ids"] == [
        item["lesson_id"] for item in lesson_records
    ]

    roles = {item["lesson_role"] for item in lesson_records}
    assert {"preserve", "avoid", "contrast"} <= roles
    required_lesson_fields = {
        "schema_version",
        "lesson_id",
        "source",
        "decision_input_policy",
        "scope",
        "lesson_role",
        "lesson_type",
        "maturity",
        "source_branch_ids",
        "shared_signature",
        "evidence_basis",
        "required_response",
        "reason_codes",
    }
    for lesson in lesson_records:
        assert required_lesson_fields <= set(lesson)
        assert lesson["schema_version"] == "branch_lesson.v1"
        assert lesson["lesson_id"].startswith("lesson:")
        assert lesson["source"] == "proposal_only"
        assert lesson["decision_input_policy"] == ("excluded_from_decision_features")
        assert lesson["required_response"]["required_output_field"] == (
            "branch_lesson_usage"
        )
        assert lesson["required_response"]["sibling_duplication_allowed"] is False
        assert (
            "runtime_budget_strategy"
            in lesson["required_response"]["required_contrast_dimensions"]
        )
        assert "BRANCH_LESSON_REQUIRED" in lesson["reason_codes"]

    flat_lessons = [
        lesson
        for lesson in lesson_records
        if set(lesson["source_branch_ids"]) == {"branch-flat-a", "branch-flat-b"}
    ]
    assert any(lesson["lesson_role"] == "contrast" for lesson in flat_lessons)
    assert any(lesson["lesson_role"] == "avoid" for lesson in flat_lessons)
    contrast_requirements = [
        lesson for lesson in flat_lessons if lesson["lesson_role"] == "contrast"
    ]
    assert any(
        lesson["required_response"]["required_for"] == "sibling_nearby_attempt"
        for lesson in contrast_requirements
    )
    sibling_requirement = contrast_requirements[0]["required_response"]
    assert sibling_requirement["required_for"] in {
        "clean_fork_new_branch",
        "sibling_nearby_attempt",
    }
    assert all(
        lesson["required_response"]["minimum_requirement"]
        == "name_borrowed_or_avoided_lesson_and_contrast_dimension"
        for lesson in contrast_requirements
    )
    assert sibling_requirement["minimum_requirement"] == (
        "name_borrowed_or_avoided_lesson_and_contrast_dimension"
    )
    assert sibling_requirement["same_branch_refinement_allowed"] is False

    repeat_payload = build_cross_branch_research_map(
        current,
        [no_effect_b, abandoned, current, no_effect_a],
        list(reversed(steps)),
    )
    repeat_record = repeat_payload["material_difference_audit_records"][0]
    assert repeat_record["record_id"] == record["record_id"]
    assert repeat_record["record_digest"] == record["record_digest"]
    assert [item["lesson_id"] for item in repeat_payload["branch_lesson_records"]] == [
        item["lesson_id"] for item in lesson_records
    ]
    weak_allowance = {
        item["branch_id"]: item for item in novelty["same_branch_refinement_allowances"]
    }["branch-weak"]
    assert weak_allowance["same_branch_refinement_allowed"] is True
    assert weak_allowance["sibling_duplication_allowed"] is False
    assert weak_allowance["recommended_action"] == "refine"
    assert any(
        item["dimension"] == "action" and item["pressure"] == "overused_action"
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
        guidance_by_type["diversify_when_recent_signatures_saturated"][
            "recommended_action"
        ]
        == "diversify"
    )


def test_cross_branch_portfolio_steering_builds_signatures_and_no_effect_lessons() -> (
    None
):
    current = _branch(
        "branch-weak",
        mechanism_ids=("bounded_signal_refine",),
    )
    no_effect_a = _branch("branch-flat-a", mechanism_ids=("flat_probe",))
    no_effect_b = _branch(
        "branch-flat-b",
        mechanism_ids=("flat_probe_variant",),
    )
    steps = [
        _screening_step(
            "branch-weak",
            round_num=1,
            mechanism_id="bounded_signal_refine",
            target_file="policies/current.py",
            change_locus="selection_policy",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "weak"},
            },
        ),
        _screening_step(
            "branch-flat-a",
            round_num=2,
            mechanism_id="flat_probe",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
        _screening_step(
            "branch-flat-b",
            round_num=3,
            mechanism_id="flat_probe_variant",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, no_effect_a, no_effect_b],
        steps,
    )
    repeat_payload = build_cross_branch_research_map(
        current,
        [no_effect_b, current, no_effect_a],
        list(reversed(steps)),
    )
    portfolio = payload["portfolio_steering"]
    repeat_portfolio = repeat_payload["portfolio_steering"]

    assert portfolio["schema_version"] == "portfolio_steering.v1"
    assert portfolio["taint"] == "proposal_research_feedback"
    assert portfolio["proposal_visibility_only"] is True
    assert portfolio["decision_features_excluded"] is True
    assert portfolio["decision_input_policy"] == "excluded_from_decision_features"
    assert portfolio["signature_schema_version"] == "branch_research_signature.v1"

    required_signature_fields = {
        "branch_id",
        "surface",
        "change_locus",
        "target_file",
        "action",
        "intervention_type",
        "mechanism_family",
        "mechanism_ids",
        "outcome_pattern",
        "activation_status",
        "effect_status",
        "runtime_evidence_status",
        "failure_signature",
        "weak_signal_signature",
        "rollback_reason",
        "signature_digest",
    }
    for signature in portfolio["signatures"]:
        assert required_signature_fields <= set(signature)
        assert len(signature["signature_digest"]) == 64
        assert signature["schema_version"] == "branch_research_signature.v1"

    signatures_by_branch = {
        signature["branch_id"]: signature for signature in portfolio["signatures"]
    }
    assert signatures_by_branch["branch-flat-a"]["surface"] == "activation_policy"
    assert signatures_by_branch["branch-flat-a"]["outcome_pattern"] == "no_effect"
    assert (
        signatures_by_branch["branch-flat-a"]["failure_signature"]["status"]
        == "present"
    )
    assert (
        signatures_by_branch["branch-weak"]["weak_signal_signature"]["status"]
        == "present"
    )

    repeat_digests = {
        signature["branch_id"]: signature["signature_digest"]
        for signature in repeat_portfolio["signatures"]
    }
    assert {
        branch_id: signature["signature_digest"]
        for branch_id, signature in signatures_by_branch.items()
    } == repeat_digests

    graph = portfolio["similarity_graph"]
    assert graph["schema_version"] == "branch_similarity_graph.v1"
    assert graph["proposal_visibility_only"] is True
    assert graph["decision_features_excluded"] is True
    assert graph["node_count"] == len(portfolio["signatures"])
    assert graph["edge_count"] == len(graph["edges"])
    assert "same_family_surface" in graph["edge_types"]

    lesson = portfolio["no_effect_lessons"][0]
    assert lesson["lesson_type"] == "no_effect_plateau"
    assert set(lesson["branch_ids"]) == {"branch-flat-a", "branch-flat-b"}
    assert lesson["source_signature"] == {
        "mechanism_family": "flat",
        "surface": "activation_policy",
        "change_locus": "activation_policy",
        "target_file": "policies/shared.py",
        "action": "modify",
        "intervention_type": "modify",
    }
    assert lesson["required_contrast_dimensions"] == [
        "mechanism_family",
        "target_file",
        "surface",
        "intervention_type",
        "effect_path",
    ]
    assert lesson["recommended_action"] == "diversify"
    assert lesson["sibling_duplication_allowed"] is False
    assert "PORTFOLIO_NO_EFFECT_PLATEAU" in lesson["reason_codes"]

    assert any(
        cluster["cluster_signal"] == "no_effect_plateau"
        and set(cluster["branch_ids"]) == {"branch-flat-a", "branch-flat-b"}
        for cluster in portfolio["clusters"]
    )
    assert any(
        gap["gap_type"] == "no_effect_contrast_gap"
        for gap in portfolio["opportunity_gaps"]
    )
    assert "Tainted planning text" not in json.dumps(portfolio, sort_keys=True)


def test_cross_branch_research_map_builds_coverage_guidance_and_gaps() -> None:
    current = _branch(
        "branch-current",
        mechanism_ids=("bounded_signal_refine",),
    )
    low_a = _branch(
        "branch-low-a",
        mechanism_ids=("flat_probe",),
    )
    low_b = _branch(
        "branch-low-b",
        mechanism_ids=("flat_probe_variant",),
    )
    steps = [
        _screening_step(
            "branch-current",
            round_num=1,
            mechanism_id="bounded_signal_refine",
            target_file="policies/current.py",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "weak"},
            },
        ),
        _screening_step(
            "branch-low-a",
            round_num=2,
            mechanism_id="flat_probe",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=(
                "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
                "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
            ),
            runtime_confidence="low",
            runtime_evidence_status="fresh_champion_required",
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
        _screening_step(
            "branch-low-b",
            round_num=3,
            mechanism_id="flat_probe_variant",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=(
                "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
                "SCREENING_RUNTIME_EVIDENCE_INCOMPLETE",
            ),
            runtime_confidence="low",
            runtime_evidence_status="insufficient",
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, low_a, low_b],
        steps,
    )
    rendered = render_cross_branch_research_map(payload)

    coverage = payload["portfolio_coverage"]
    assert coverage["policy"] == "proposal_only"
    assert set(coverage["cluster_dimensions"]) >= {
        "mechanism_family",
        "target_file",
        "outcome_pattern",
        "effect_tier",
        "activation_status",
        "effect_status",
        "runtime_evidence_confidence",
        "runtime_evidence_status",
    }

    target_clusters = {
        item["value"]: item for item in coverage["dimension_coverage"]["target_file"]
    }
    shared_target = target_clusters["policies/shared.py"]
    assert shared_target["branch_count"] == 2
    assert shared_target["outcome_patterns"] == {"no_effect": 2}
    assert shared_target["runtime_evidence_quality"] == {"low_or_incomplete": 2}

    combined = [
        item
        for item in coverage["combined_clusters"]
        if item["signature"]
        == {
            "mechanism_family": "flat",
            "target_file": "policies/shared.py",
            "action": "modify",
        }
    ][0]
    assert combined["branch_count"] == 2
    assert combined["recommended_action"] == "bridge"
    assert combined["effect_statuses"] == {"zero": 2}

    guidance_types = {
        item["guidance_type"] for item in payload["avoid_bridge_guidance"]
    }
    assert "avoid_repeated_non_positive_cluster" in guidance_types
    assert "bridge_low_confidence_runtime_evidence" in guidance_types
    assert "bridge_repeated_zero_effect" in guidance_types
    runtime_guidance = {
        item["guidance_type"]: item for item in payload["avoid_bridge_guidance"]
    }["bridge_low_confidence_runtime_evidence"]
    assert runtime_guidance["runtime_signal_role"] == (
        "audit_or_proposal_guidance_only"
    )
    assert runtime_guidance["standalone_optimization_signal"] is False
    assert "standalone optimization signal" in runtime_guidance["proposal_guidance"]

    gap_types = {item["gap_type"] for item in payload["opportunity_gaps"]}
    assert "action_diversity_gap" in gap_types
    assert "family_diversity_gap" in gap_types
    assert "target_diversity_gap" in gap_types
    assert "observability_path_gap" in gap_types
    assert "runtime_evidence_confidence_gap" in gap_types
    runtime_gap = {item["gap_type"]: item for item in payload["opportunity_gaps"]}[
        "runtime_evidence_confidence_gap"
    ]
    assert runtime_gap["runtime_signal_role"] == "audit_or_proposal_guidance_only"
    assert runtime_gap["standalone_optimization_signal"] is False
    assert "standalone optimization signal" in runtime_gap["proposal_guidance"]

    current_summary = {item["branch_id"]: item for item in payload["branches"]}[
        "branch-current"
    ]
    assert current_summary["evidence_profile"]["effect_tier"] == "weak_positive"
    assert current_summary["evidence_profile"]["activation_status"] == "observed"
    assert current_summary["research_descriptors"][0]["mechanism_family"] == (
        "bounded_signal"
    )
    low_summary = {item["branch_id"]: item for item in payload["branches"]}[
        "branch-low-a"
    ]
    low_policy = low_summary["evidence_profile"]["runtime_evidence_policy"]
    assert low_policy["schema_version"] == "runtime_evidence_policy.v1"
    assert low_policy["fresh_champion_required"] is True
    assert low_policy["standalone_optimization_signal"] is False
    assert low_policy["runtime_signal_role"] == "audit_or_proposal_guidance_only"
    assert low_policy["proposal_guidance_only"] is True
    assert low_policy["decision_features_excluded"] is True
    assert any(
        lesson["lesson_role"] == "bridge"
        and lesson["required_response"]["required_output_field"]
        == "branch_lesson_usage"
        for lesson in payload["branch_lesson_records"]
    )

    assert "excluded_from_decision_features" in rendered
    assert "raw_metrics_ref" not in rendered
    assert "/internal/raw-metrics.json" not in rendered


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
    assert novelty["in_action_diversity_pressure"]["recommended_action"] == "diversify"
    guidance = {item["guidance_type"]: item for item in payload["portfolio_guidance"]}
    assert (
        guidance["diversify_within_executable_action"]["recommended_action"]
        == "diversify"
    )


def test_cross_branch_research_keeps_active_weak_positive_refinement_allowed() -> None:
    current = _branch(
        "branch-current",
        mechanism_ids=("bounded_signal_refine",),
    )
    sibling_a = _branch(
        "branch-sibling-a",
        mechanism_ids=("bounded_signal_probe",),
    )
    sibling_b = _branch(
        "branch-sibling-b",
        mechanism_ids=("bounded_signal_variant",),
    )
    steps = [
        _screening_step(
            "branch-current",
            round_num=1,
            mechanism_id="bounded_signal_refine",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "weak"},
            },
        ),
        _screening_step(
            "branch-sibling-a",
            round_num=2,
            mechanism_id="bounded_signal_probe",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
        _screening_step(
            "branch-sibling-b",
            round_num=3,
            mechanism_id="bounded_signal_variant",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            reason_codes=("SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "zero"},
            },
        ),
    ]

    payload = build_cross_branch_research_map(
        current,
        [current, sibling_a, sibling_b],
        steps,
    )

    novelty = payload["novelty_pressure"]
    avoid = novelty["avoid_signature_set"][0]
    assert avoid["shared_signature"] == {
        "mechanism_family": "bounded_signal",
        "target_file": "policies/shared.py",
        "action": "modify",
        "change_locus": "activation_policy",
    }
    assert avoid["same_branch_refinement_allowed"] is True
    assert avoid["same_branch_refinement_allowed_branch_ids"] == ["branch-current"]
    assert set(avoid["sibling_branch_ids"]) == {
        "branch-sibling-a",
        "branch-sibling-b",
    }
    assert avoid["material_difference_required_for"] == "sibling_nearby_attempt"
    assert (
        avoid["material_difference_requirements"]["same_branch_refinement_allowed"]
        is True
    )
    assert (
        avoid["material_difference_requirements"]["sibling_duplication_allowed"]
        is False
    )

    blocked = novelty["blocked_signature_pressure"][0]
    assert blocked["deterministic_screening_block"] is False
    assert blocked["same_branch_refinement_allowed_branch_ids"] == ["branch-current"]

    allowance = {
        item["branch_id"]: item for item in novelty["same_branch_refinement_allowances"]
    }["branch-current"]
    assert allowance["is_current_branch"] is True
    assert allowance["same_branch_refinement_allowed"] is True
    assert allowance["sibling_duplication_allowed"] is False
    assert allowance["signatures"][0]["mechanism_family"] == "bounded_signal"
    preserve_lesson = [
        lesson
        for lesson in payload["branch_lesson_records"]
        if lesson["lesson_role"] == "preserve"
        and lesson["source_branch_ids"] == ["branch-current"]
    ][0]
    assert preserve_lesson["lesson_type"] == "weak_positive"
    assert preserve_lesson["maturity"] == "fresh"
    assert preserve_lesson["required_response"]["required_for"] == (
        "same_branch_refinement"
    )
    assert (
        preserve_lesson["required_response"]["same_branch_refinement_allowed"] is True
    )
    assert preserve_lesson["required_response"]["sibling_duplication_allowed"] is False
    contrast_lesson = [
        lesson
        for lesson in payload["branch_lesson_records"]
        if lesson["lesson_role"] == "contrast"
        and set(lesson["source_branch_ids"])
        == {"branch-current", "branch-sibling-a", "branch-sibling-b"}
    ][0]
    assert set(contrast_lesson["source_branch_ids"]) == {
        "branch-current",
        "branch-sibling-a",
        "branch-sibling-b",
    }
    assert contrast_lesson["required_response"]["required_for"] == (
        "sibling_nearby_attempt"
    )


def test_cross_branch_research_exposes_sibling_weak_positive_borrow_lesson() -> None:
    current = _branch("branch-clean", mechanism_ids=("clean_probe",))
    weak = _branch(
        "branch-weak",
        mechanism_ids=("bounded_signal_probe",),
    )
    steps = [
        _screening_step(
            "branch-weak",
            round_num=1,
            mechanism_id="bounded_signal_probe",
            target_file="policies/shared.py",
            change_locus="activation_policy",
            wins=1,
            reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
            mechanism_evidence={
                "activation": {"status": "observed"},
                "effect": {"status": "weak"},
            },
        ),
    ]

    payload = build_cross_branch_research_map(current, [current, weak], steps)

    borrow = [
        lesson
        for lesson in payload["branch_lesson_records"]
        if lesson["lesson_role"] == "borrow"
        and lesson["lesson_type"] == "weak_positive"
        and lesson["source_branch_ids"] == ["branch-weak"]
    ][0]
    assert borrow["scope"] == "cross_branch"
    assert borrow["required_response"]["required_for"] == "clean_fork_new_branch"
    assert borrow["required_response"]["required_output_field"] == (
        "branch_lesson_usage"
    )
    assert borrow["required_response"]["minimum_requirement"] == (
        "borrow_or_preserve_or_machine_reject_with_activation_effect_linkage"
    )
    assert borrow["required_response"]["required_path_fields"] == [
        "activation_path",
        "effect_path",
    ]
    assert borrow["required_response"]["required_linkage_fields"] == [
        "target_file",
        "action",
        "mechanism_or_mechanism_change_id",
    ]
    assert "mechanism_or_change_locus" not in borrow["required_response"][
        "required_linkage_fields"
    ]
    assert borrow["required_response"]["one_of_required_fields"] == [
        "risk_to_avoid",
        "contrast_dimensions",
    ]
    assert borrow["required_response"]["reuse_or_reject_required"] is True
    assert borrow["required_response"]["machine_reject_fields"] == [
        "rejected_weak_positive_lessons.lesson_id",
        "rejected_weak_positive_lessons.reject_reason_code",
        "rejected_weak_positive_lessons.target_file",
        "rejected_weak_positive_lessons.action",
        "rejected_weak_positive_lessons.mechanism_or_mechanism_change_id",
    ]
    assert borrow["transfer_contract"]["trigger_mechanism"] == "bounded_signal"
    assert borrow["transfer_contract"]["activation_path"] == "activation_policy"
    assert borrow["transfer_contract"]["entry_file"] == "policies/shared.py"
    assert (
        borrow["transfer_contract"]["reuse_requirements"]["required_output_field"]
        == "branch_lesson_usage"
    )
    assert (
        borrow["transfer_contract"]["reject_requirements"]["required_usage"]
        == "rejected_weak_positive_lessons"
    )
    assert borrow["required_response"]["sibling_duplication_allowed"] is False
    assert borrow["decision_input_policy"] == "excluded_from_decision_features"


def test_cross_branch_research_map_does_not_extend_decision_features() -> None:
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert "cross_branch_research" not in decision_fields
    assert "cross_branch_research_payload" not in decision_fields
    assert "similarity_hints" not in decision_fields
    assert "lessons" not in decision_fields
    assert "lesson_cards" not in decision_fields
    assert "novelty_pressure" not in decision_fields
    assert "portfolio_guidance" not in decision_fields
    assert "runtime_evidence_policy" not in decision_fields
    assert "portfolio_coverage" not in decision_fields
    assert "avoid_bridge_guidance" not in decision_fields
    assert "opportunity_gaps" not in decision_fields
    assert "avoid_signature_set" not in decision_fields
    assert "blocked_signature_pressure" not in decision_fields
    assert "material_difference_requirements" not in decision_fields
    assert "material_difference_audit_records" not in decision_fields
    assert "cross_branch_research_session_metadata" not in decision_fields
    assert "same_branch_refinement_allowances" not in decision_fields
    assert "branch_lesson_records" not in decision_fields
    assert "branch_lesson_usage" not in decision_fields
    assert "branch_lesson_usage_requirement" not in decision_fields
    assert "portfolio_steering" not in decision_fields
    assert "branch_research_signatures" not in decision_fields
    assert "similarity_graph" not in decision_fields
    assert "no_effect_lessons" not in decision_fields
    assert "hypothesis_text" not in decision_fields


def test_cross_branch_research_module_has_no_problem_specific_control_terms() -> None:
    source = (
        inspect.getsource(cross_branch_module)
        + inspect.getsource(cross_branch_coverage_module)
        + inspect.getsource(cross_branch_summary_module)
        + inspect.getsource(cross_branch_support_module)
        + inspect.getsource(research_portfolio_module)
    ).lower()

    for term in ("cvrp", "route", "alns", "vns", "capacity", "demand", "fleet"):
        assert term not in source
