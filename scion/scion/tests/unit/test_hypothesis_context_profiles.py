from __future__ import annotations

from dataclasses import fields

from scion.core.models import DecisionFeatures
from scion.proposal.engine.hypothesis_context_profiles import (
    derive_hypothesis_context_profile,
    filter_hypothesis_context_for_prompt,
)


def test_algorithm_profile_filters_full_governance_noise_and_keeps_compact_learning():
    context = {
        "problem_summary": "summary",
        "branch_dossier": "## full Branch Dossier",
        "branch_dossier_payload": {"schema_version": "branch_dossier.v1"},
        "research_log": "full research log",
        "cross_branch_research": "full cross_branch_research.v1 payload",
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "material_difference_audit_records": [
                {"audit_token": "hidden-audit"}
            ],
            "cross_branch_research_metadata": {"session_id": "hidden-session"},
            "similarity_hints": [
                {
                    "hint_type": "near_duplicate",
                    "branch_ids": ["branch-a", "branch-b"],
                    "shared_signature": {
                        "change_locus": "algorithm_design",
                        "target_file": "policies/base.py",
                        "material_difference_requirements": {"hidden": True},
                    },
                    "outcome_patterns": {"weak_positive": 1},
                    "reason_codes": ["CROSS_BRANCH_NEAR_DUPLICATE"],
                    "summary": "Nearby branch already tested this shape.",
                }
            ],
            "lesson_cards": [
                {
                    "scope": "cross_branch",
                    "lesson_type": "near_duplicate",
                    "failure_mode": "saturation",
                    "recommended_action": "avoid repeating the same shape",
                    "metadata": {"hidden": True},
                    "summary": "Use a materially different structure.",
                }
            ],
            "avoid_bridge_guidance": [
                {
                    "hint_type": "avoid",
                    "recommended_action": "avoid same mechanism family",
                    "reason_codes": ["AVOID_REPEAT"],
                    "summary": "Do not repeat nearby branch behavior.",
                }
            ],
            "opportunity_gaps": [
                {
                    "opportunity_type": "coverage_gap",
                    "recommended_action": "try an untested generic lever",
                    "summary": "Open opportunity remains.",
                }
            ],
            "novelty_pressure": {
                "policy": "proposal_only",
                "recommended_action": "state a compact structural difference",
                "material_difference_audit_records": [{"hidden": True}],
            },
            "portfolio_guidance": [
                {"summary": "Keep portfolio coverage broad.", "audit": "hidden"}
            ],
            "portfolio_steering": {
                "schema_version": "portfolio_steering.v1",
                "taint": "proposal_research_feedback",
                "proposal_visibility_only": True,
                "decision_features_excluded": True,
                "summary": {
                    "signature_count": 3,
                    "branch_count": 3,
                    "cluster_count": 1,
                    "no_effect_lesson_count": 1,
                    "outcome_patterns": {"no_effect": 2, "weak_positive": 1},
                },
                "signatures": [
                    {
                        "branch_id": "branch-a",
                        "signature_digest": "hidden-full-signature",
                    }
                ],
                "similarity_graph": {
                    "edges": [{"edge_type": "same_family_surface"}]
                },
                "clusters": [
                    {
                        "cluster_id": "cluster-flat",
                        "cluster_type": "family_surface_target_action",
                        "branch_ids": ["branch-a", "branch-b"],
                        "branch_count": 2,
                        "shared_signature": {
                            "mechanism_family": "flat",
                            "surface": "activation_policy",
                            "target_file": "policies/shared.py",
                            "action": "modify",
                        },
                        "outcome_patterns": {"no_effect": 2},
                        "activation_statuses": {"observed": 2},
                        "effect_statuses": {"zero": 2},
                        "runtime_evidence_statuses": {"sufficient": 2},
                        "cluster_signal": "no_effect_plateau",
                        "recommended_action": "diversify",
                    }
                ],
                "no_effect_lessons": [
                    {
                        "lesson_type": "no_effect_plateau",
                        "source_cluster_id": "cluster-flat",
                        "source_signature": {"hidden": "full"},
                        "branch_ids": ["branch-a", "branch-b"],
                        "evidence_basis": {"outcome_patterns": {"no_effect": 2}},
                        "required_contrast_dimensions": [
                            "mechanism_family",
                            "target_file",
                            "surface",
                        ],
                        "recommended_action": "diversify",
                        "same_branch_refinement_allowed": False,
                        "sibling_duplication_allowed": False,
                        "reason_codes": ["PORTFOLIO_NO_EFFECT_PLATEAU"],
                    }
                ],
                "opportunity_gaps": [
                    {
                        "gap_type": "no_effect_contrast_gap",
                        "recommended_action": "diversify",
                        "priority": "high",
                        "basis": {"lesson_count": 1},
                        "reason_codes": ["PORTFOLIO_NO_EFFECT_CONTRAST_GAP"],
                        "confidence": 0.7,
                    }
                ],
            },
        },
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert derive_hypothesis_context_profile(context) == "algorithm"
    assert filtered["context_profile"] == "algorithm"
    assert filtered["context_profile_metadata"] == {
        "schema_version": "hypothesis_context_profile.v1",
        "profile": "algorithm",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }
    assert "branch_dossier" not in filtered
    assert "branch_dossier_payload" not in filtered
    assert "research_log" not in filtered
    assert "cross_branch_research_payload" not in filtered
    assert "cross_branch_research_audit_records" not in filtered
    assert "cross_branch_research_session_metadata" not in filtered
    compact = filtered["cross_branch_research"]
    assert "compact_cross_branch_learning.v1" in compact
    assert "cross_branch_research.v1" not in compact
    assert "near_duplicate" in compact
    assert "avoid same mechanism family" in compact
    assert "coverage_gap" in compact
    assert "Use a materially different structure." in compact
    assert "compact_portfolio_steering.v1" in compact
    assert "portfolio_steering.v1" in compact
    assert "no_effect_plateau" in compact
    assert "no_effect_contrast_gap" in compact
    assert "activation_policy" in compact
    assert "signature_digest" not in compact
    assert "hidden-full-signature" not in compact
    assert "same_family_surface" not in compact
    assert "hidden-audit" not in compact
    assert "hidden-session" not in compact
    assert "material_difference_requirements" not in compact


def test_algorithm_profile_drops_repair_feedback_without_repair_trigger():
    context = {
        "agentic_prior_quality_blocks": [],
        "agentic_negative_fact_block": "",
        "agent_quality_feedback": "",
        "contract_preview_failure_signature": {},
        "failure_pattern_warning": "",
        "runtime_failure_guidance": "",
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert derive_hypothesis_context_profile(context) == "algorithm"
    assert "agentic_prior_quality_blocks" not in filtered
    assert "agentic_negative_fact_block" not in filtered
    assert "agent_quality_feedback" not in filtered
    assert "contract_preview_failure_signature" not in filtered
    assert "failure_pattern_warning" not in filtered
    assert "runtime_failure_guidance" not in filtered


def test_repair_profile_retains_concrete_repair_feedback():
    context = {
        "agentic_prior_quality_blocks": [
            {"failure_code": "proposal_activation_diagnostic"}
        ],
        "agentic_prior_quality_block_rule": "repair cited issue",
        "agentic_negative_fact_block": "negative fact",
        "agent_quality_feedback": "quality feedback",
        "contract_preview_failure_signature": {"check_id": "boundary"},
        "failure_pattern_warning": "verification_heavy streak=3",
        "runtime_failure_guidance": "repair runtime failure",
        "branch_hygiene": {
            "repair_focus_required": True,
            "repair_focus_reason": "wiring_suspect_requires_repair",
        },
        "branch_hygiene_guidance": "repair_focus_required=True",
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert derive_hypothesis_context_profile(context) == "repair"
    assert filtered["context_profile"] == "repair"
    assert filtered["context_profile_metadata"]["profile"] == "repair"
    assert filtered["agentic_prior_quality_blocks"]
    assert filtered["agentic_prior_quality_block_rule"] == "repair cited issue"
    assert filtered["agentic_negative_fact_block"] == "negative fact"
    assert filtered["agent_quality_feedback"] == "quality feedback"
    assert filtered["contract_preview_failure_signature"]["check_id"] == "boundary"
    assert filtered["failure_pattern_warning"] == "verification_heavy streak=3"
    assert filtered["runtime_failure_guidance"] == "repair runtime failure"
    assert filtered["branch_hygiene"]["repair_focus_required"] is True


def test_context_profile_metadata_does_not_enter_decision_features():
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert "context_profile" not in decision_fields
    assert "context_profile_metadata" not in decision_fields


def test_material_difference_requirement_only_kept_when_required_and_nonempty():
    active = {
        "material_difference_requirement": {
            "schema_version": "proposal_material_difference_requirement.v1",
            "required": True,
            "required_for": "branch-a",
            "record_id": "material_difference_requirement:branch-a",
        }
    }
    inactive = {
        "material_difference_requirement": {
            "schema_version": "proposal_material_difference_requirement.v1",
            "required": False,
            "record_id": "material_difference_requirement:branch-a",
        }
    }
    empty_required = {
        "material_difference_requirement": {
            "schema_version": "proposal_material_difference_requirement.v1",
            "required": True,
        }
    }

    assert (
        filter_hypothesis_context_for_prompt(active)[
            "material_difference_requirement"
        ]["record_id"]
        == "material_difference_requirement:branch-a"
    )
    assert "material_difference_requirement" not in (
        filter_hypothesis_context_for_prompt(inactive)
    )
    assert "material_difference_requirement" not in (
        filter_hypothesis_context_for_prompt(empty_required)
    )
