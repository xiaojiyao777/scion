from __future__ import annotations

from dataclasses import fields

from scion.core.models import DecisionFeatures
from scion.proposal.engine.hypothesis_context_profiles import (
    derive_hypothesis_context_profile,
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.engine.hypothesis_prompts import _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest


def test_algorithm_profile_filters_full_governance_noise_and_keeps_compact_learning():
    context = {
        "problem_summary": "summary",
        "branch_dossier": "## full Branch Dossier",
        "branch_dossier_payload": {"schema_version": "branch_dossier.v1"},
        "research_log": "full research log",
        "cross_branch_research": "full cross_branch_research.v1 payload",
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "material_difference_audit_records": [{"audit_token": "hidden-audit"}],
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
            "branch_lesson_records": [
                {
                    "schema_version": "branch_lesson.v1",
                    "lesson_id": "lesson:abc123",
                    "source": "proposal_only",
                    "decision_input_policy": "excluded_from_decision_features",
                    "scope": "branch_local",
                    "lesson_role": "preserve",
                    "lesson_type": "weak_positive",
                    "maturity": "fresh",
                    "source_branch_ids": ["branch-a"],
                    "shared_signature": {
                        "mechanism_family": "bounded",
                        "target_file": "policies/base.py",
                        "action": "modify",
                        "change_locus": "activation_policy",
                    },
                    "evidence_basis": {
                        "outcome_patterns": {"weak_positive": 1},
                        "activation_statuses": {"observed": 1},
                    },
                    "required_response": {
                        "required_for": "same_branch_refinement",
                        "required_output_field": "branch_lesson_usage",
                        "minimum_requirement": (
                            "name_borrowed_or_avoided_lesson_and_contrast_dimension"
                        ),
                        "required_contrast_dimensions": [
                            "mechanism_family",
                            "target_file",
                            "runtime_budget_strategy",
                        ],
                        "same_branch_refinement_allowed": True,
                        "sibling_duplication_allowed": False,
                    },
                    "full_audit": {"hidden": True},
                    "raw_text": "hidden raw audit text",
                    "material_difference_audit": {"hidden": True},
                    "reason_codes": ["BRANCH_LESSON_REQUIRED"],
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
                "similarity_graph": {"edges": [{"edge_type": "same_family_surface"}]},
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
                "family_saturation_summary": {
                    "schema_version": ("cross_branch_family_saturation_summary.v1"),
                    "visibility_marker": (
                        "advisory proposal-only " "excluded_from_DecisionFeatures"
                    ),
                    "proposal_visibility_only": True,
                    "advisory_only": True,
                    "decision_features_excluded": True,
                    "decision_input_policy": ("excluded_from_decision_features"),
                    "grouping_keys": [
                        "mechanism_family",
                        "intervention_type",
                        "surface",
                        "outcome_tier",
                    ],
                    "saturated_family_count": 1,
                    "summaries": [
                        {
                            "mechanism_family": "flat",
                            "intervention_type": "modify",
                            "surface": "activation_policy",
                            "attempt_count": 3,
                            "branch_count": 3,
                            "outcome_tier_counts": {
                                "no_effect": 2,
                                "weak_positive": 1,
                            },
                            "case_level_counts": {
                                "wins": 1,
                                "losses": 0,
                                "no_effect": 11,
                            },
                            "lifecycle_counts": {"weak_positive": 1},
                            "advisory_label": "spent_family",
                            "proposal_advisory": (
                                "Spent family with weak/no-effect history; "
                                "consider diversifying mechanism family, "
                                "intervention type, or surface when planning "
                                "the next proposal."
                            ),
                            "reason_codes": ["CROSS_BRANCH_FAMILY_SATURATION_ADVISORY"],
                        }
                    ],
                },
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
        "proposal_context_ablation": "full",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "measurement_diagnostics_visibility": "absent",
        "measurement_diagnostics_prompt_key": "",
        "measurement_diagnostics_standalone_section": False,
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
    assert "lesson:abc123" in compact
    assert "preserve" in compact
    assert "fresh" in compact
    assert "branch_lesson_usage" in compact
    assert "runtime_budget_strategy" in compact
    assert "same_branch_refinement_allowed" in compact
    assert "sibling_duplication_allowed" in compact
    assert "compact_portfolio_steering.v1" in compact
    assert "cross_branch_family_saturation_summary.v1" in compact
    assert "advisory proposal-only excluded_from_DecisionFeatures" in compact
    assert "consider diversifying" in compact
    assert "spent_family" in compact
    assert "portfolio_steering.v1" in compact
    assert "no_effect_plateau" in compact
    assert "no_effect_contrast_gap" in compact
    assert "activation_policy" in compact
    assert "signature_digest" not in compact
    assert "hidden-full-signature" not in compact
    assert "same_family_surface" not in compact
    assert "hidden-audit" not in compact
    assert "hidden-session" not in compact
    assert "hidden raw audit text" not in compact
    assert "full_audit" not in compact
    assert "material_difference_audit" not in compact
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
    assert "proposal_context_ablation" not in decision_fields
    assert "compact_research_signals" not in decision_fields
    assert "research_signal_ratio" not in decision_fields
    assert "branch_lesson_records" not in decision_fields
    assert "branch_lesson_usage" not in decision_fields
    assert "branch_lesson_usage_requirement" not in decision_fields
    assert "family_saturation_summary" not in decision_fields
    assert "cross_branch_family_saturation_summary" not in decision_fields
    assert "problem_measurement_diagnostics" not in decision_fields
    assert "compact_problem_measurement_diagnostics" not in decision_fields
    assert "measurement_diagnostics_visibility" not in decision_fields
    assert "measurement_diagnostics_prompt_key" not in decision_fields
    assert "measurement_diagnostics_standalone_section" not in decision_fields
    assert "measurement_noise_floor" not in decision_fields
    assert "objective_opportunity_profile" not in decision_fields


def test_no_measurement_diagnostics_ablation_keeps_protocol_mode_and_research_context():
    context = {
        "problem_summary": "CVRP formal screening objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1 screening complete",
        "measurement_governance": "on",
        "proposal_context_ablation": "no-measurement-diagnostics",
        "experiment_history": (
            "branch b1\n"
            "    screening_feedback.tier=weak activation=observed "
            "effect=none runtime_confidence=low "
            "opportunity_status=opportunity_poor\n"
            "    opportunity_diagnostics: measurement-owned low SNR guidance"
        ),
        "objective_opportunity_profile": (
            "## Objective Opportunity Profile (screening only)\n"
            "- total_cost: positive_cases=1 negative_cases=0 tie_cases=1"
        ),
        "runtime_feedback": (
            "## Runtime Feedback\n"
            "candidate runtime ratio remains within the branch budget"
        ),
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "branch_lesson_records": [
                {
                    "schema_version": "branch_lesson.v1",
                    "lesson_id": "lesson:non-measurement-still-visible",
                    "scope": "cross_branch",
                    "summary": "A sibling branch preserved feasibility.",
                }
            ],
        },
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "record_id": "branch_lesson_usage_requirement:measurement-ablation",
            "required_output_field": "branch_lesson_usage",
        },
        "branch_lesson_records": [
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": "lesson:branch-memory-still-visible",
                "scope": "same_branch",
                "summary": "Current branch memory remains available.",
            }
        ],
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "signal_to_noise_tier": "low_power",
            },
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "low_snr",
                    "summary": "Candidate effects below measured screening MDE.",
                    "reason_codes": ["MEASUREMENT_POWER_LOW"],
                }
            ],
        },
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert filtered["measurement_governance"] == "on"
    assert filtered["proposal_context_ablation"] == "no-measurement-diagnostics"
    assert (
        filtered["context_profile_metadata"]["proposal_context_ablation"]
        == "no-measurement-diagnostics"
    )
    assert "problem_measurement_diagnostics" not in filtered
    assert "measurement-owned low SNR guidance" not in filtered["experiment_history"]
    assert "opportunity_status=opportunity_poor" not in filtered["experiment_history"]
    assert "objective_opportunity_profile" in filtered
    assert "runtime_feedback" in filtered
    assert "compact_cross_branch_learning.v1" in filtered["cross_branch_research"]
    assert filtered["branch_lesson_records"][0]["lesson_id"] == (
        "lesson:branch-memory-still-visible"
    )

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(block["text"] for block in system_blocks) + user_prompt
    assert "## Problem Measurement Diagnostics" not in rendered_prompt
    assert "MEASUREMENT_POWER_LOW" not in rendered_prompt
    assert "## Objective Opportunity Profile (screening only)" in rendered_prompt
    assert "## Runtime Feedback" in rendered_prompt
    assert "compact_cross_branch_learning.v1" in rendered_prompt


def test_compact_measurement_diagnostics_ablation_keeps_research_context_without_standalone_section():
    context = {
        "problem_summary": "Warehouse objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1 screening complete",
        "measurement_governance": "on",
        "proposal_context_ablation": "measurement_diagnostics_compact",
        "experiment_history": (
            "branch b1\n"
            "    screening_feedback.tier=weak activation=observed "
            "effect=none runtime_confidence=low "
            "opportunity_status=opportunity_poor\n"
            "    opportunity_diagnostics: measurement-owned low SNR guidance"
        ),
        "objective_opportunity_profile": (
            "## Objective Opportunity Profile (screening only)\n"
            "- total_cost: positive_cases=1 negative_cases=0 tie_cases=1"
        ),
        "runtime_feedback": (
            "## Runtime Feedback\n"
            "candidate runtime ratio remains within the branch budget"
        ),
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "branch_lesson_records": [
                {
                    "schema_version": "branch_lesson.v1",
                    "lesson_id": "lesson:compact-mode-still-visible",
                    "scope": "cross_branch",
                    "summary": "A sibling branch preserved feasibility.",
                }
            ],
        },
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "record_id": "branch_lesson_usage_requirement:compact",
            "required_output_field": "branch_lesson_usage",
        },
        "branch_lesson_records": [
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": "lesson:branch-compact-visible",
                "scope": "same_branch",
                "summary": "Current branch memory remains available.",
            }
        ],
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "signal_to_noise_tier": "low_power",
                "raw_pair_rows": [{"case": "secret-readiness-row"}],
            },
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "low_snr",
                    "summary": "Candidate effects below measured screening MDE.",
                    "recommended_action": "try a larger bounded mechanism",
                    "reason_codes": ["MEASUREMENT_POWER_LOW"],
                    "validation_case_details": "secret-validation-case-detail",
                    "frozen_case_details": "secret-frozen-case-detail",
                    "raw_pair_rows": [{"case": "secret-raw-row"}],
                }
            ],
            "raw_calibration_pair_rows": [{"case": "secret-aa-row"}],
            "bks_gap_details": "secret-bks-gap",
            "prompt_ratios": {"research_signal_ratio": 0.1},
            "llm_text": "secret llm prose",
        },
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert filtered["measurement_governance"] == "on"
    assert filtered["proposal_context_ablation"] == "compact-measurement-diagnostics"
    assert (
        filtered["context_profile_metadata"]["proposal_context_ablation"]
        == "compact-measurement-diagnostics"
    )
    assert (
        filtered["context_profile_metadata"]["measurement_diagnostics_visibility"]
        == "compact"
    )
    assert (
        filtered["context_profile_metadata"]["measurement_diagnostics_prompt_key"]
        == "compact_problem_measurement_diagnostics"
    )
    assert (
        filtered["context_profile_metadata"][
            "measurement_diagnostics_standalone_section"
        ]
        is False
    )
    assert "problem_measurement_diagnostics" not in filtered
    assert "compact_problem_measurement_diagnostics" in filtered
    compact_diagnostic = filtered["compact_problem_measurement_diagnostics"]
    assert "MEASUREMENT_POWER_LOW" in compact_diagnostic
    assert "secret-readiness-row" not in compact_diagnostic
    assert "secret-validation-case-detail" not in compact_diagnostic
    assert "secret-frozen-case-detail" not in compact_diagnostic
    assert "secret-raw-row" not in compact_diagnostic
    assert "secret-aa-row" not in compact_diagnostic
    assert "secret-bks-gap" not in compact_diagnostic
    assert "research_signal_ratio" not in compact_diagnostic
    assert "secret llm prose" not in compact_diagnostic
    assert "branch b1" in filtered["experiment_history"]
    assert "measurement-owned low SNR guidance" not in filtered["experiment_history"]
    assert "opportunity_status=opportunity_poor" not in filtered["experiment_history"]
    assert "objective_opportunity_profile" in filtered
    assert "runtime_feedback" in filtered
    assert "compact_cross_branch_learning.v1" in filtered["cross_branch_research"]
    assert filtered["branch_lesson_records"][0]["lesson_id"] == (
        "lesson:branch-compact-visible"
    )

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(block["text"] for block in system_blocks) + user_prompt
    assert "## Problem Measurement Diagnostics" not in rendered_prompt
    assert "## Compact Research Signals" in rendered_prompt
    assert "MEASUREMENT_POWER_LOW" in rendered_prompt
    assert "measurement-owned low SNR guidance" not in rendered_prompt
    assert "## Objective Opportunity Profile (screening only)" in rendered_prompt
    assert "## Runtime Feedback" in rendered_prompt
    assert "compact_cross_branch_learning.v1" in rendered_prompt
    assert "secret-validation-case-detail" not in rendered_prompt
    assert "secret-frozen-case-detail" not in rendered_prompt
    assert "secret-raw-row" not in rendered_prompt
    assert "secret-aa-row" not in rendered_prompt
    assert "secret-bks-gap" not in rendered_prompt
    assert "research_signal_ratio" not in rendered_prompt
    assert "secret llm prose" not in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-compact-measurement-diagnostics",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    assert (
        manifest["context_profile_metadata"]["measurement_diagnostics_visibility"]
        == "compact"
    )
    assert "problem_measurement_diagnostics" not in manifest["section_names"]
    assert "problem_measurement_diagnostics" not in manifest["section_statuses"]
    assert "compact_research_signals" in manifest["section_names"]
    assert manifest["section_statuses"]["compact_research_signals"][
        "block_family"
    ] == "research_signal"
    assert not any(
        entry.get("section_name") == "problem_measurement_diagnostics"
        for entry in manifest["visibility_ledger"]["entries"]
    )


def test_minimal_research_context_ablation_keeps_source_and_measurement_context():
    context = {
        "problem_summary": "Warehouse objective.",
        "research_surfaces": "Research surfaces: operators",
        "operator_categories": "operators",
        "available_actions": "modify",
        "targetable_files": "operators/relocate.py",
        "champion_operators_code": "class Relocate:\n    pass\n",
        "branch_code": "class Relocate:\n    def execute(self):\n        return None\n",
        "champion_stats": "champion_v2",
        "measurement_governance": "on",
        "proposal_context_ablation": "minimal-research-context",
        "active_hyp_summary": "hidden occupied hypothesis",
        "blacklist_summary": "hidden rejected mechanism",
        "sibling_summary": "hidden sibling branch",
        "experiment_history": (
            "branch b1\n"
            "    opportunity_status=opportunity_poor\n"
            "    opportunity_diagnostics: measurement-owned low SNR guidance"
        ),
        "exploration_coverage": "hidden coverage",
        "strategy_guidance": "hidden strategy guidance",
        "search_control_guidance": "hidden search control guidance",
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_stable",
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "MEASUREMENT_POWER_LOW",
                "signal_to_noise_tier": "measurable",
            },
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "effect_scale",
                    "summary": "Measurement diagnostics remain visible.",
                    "reason_codes": ["MEASUREMENT_POWER_LOW"],
                }
            ],
        },
        "objective_opportunity_profile": "## Objective Opportunity Profile",
        "runtime_feedback": "runtime feedback that should be hidden",
        "cross_branch_research": "full cross branch text",
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "lesson_cards": [{"summary": "hidden lesson"}],
        },
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "record_id": "branch_lesson_usage_requirement:hidden",
        },
        "branch_lesson_records": [{"lesson_id": "lesson:hidden"}],
        "branch_direction": "hidden branch direction",
        "branch_dossier": "hidden branch dossier",
        "branch_followup_policy": "hidden follow-up policy",
        "champion_baselines": "hidden champion baselines",
        "objective_guidance": "hidden objective guidance",
        "saturation_signal": "hidden saturation signal",
        "search_memory": "hidden search memory",
        "research_log": "hidden research log",
        "weight_opt_feedback": "hidden weight feedback",
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert filtered["measurement_governance"] == "on"
    assert filtered["proposal_context_ablation"] == "minimal-research-context"
    assert (
        filtered["context_profile_metadata"]["proposal_context_ablation"]
        == "minimal-research-context"
    )
    assert filtered["champion_operators_code"] == context["champion_operators_code"]
    assert filtered["branch_code"] == context["branch_code"]
    assert "problem_measurement_diagnostics" in filtered
    assert "MEASUREMENT_POWER_LOW" in filtered["problem_measurement_diagnostics"]
    assert "cross_branch_research" not in filtered
    assert "branch_lesson_records" not in filtered
    assert "branch_lesson_usage_requirement" not in filtered
    assert "objective_opportunity_profile" not in filtered
    assert "runtime_feedback" not in filtered
    assert "experiment_history" not in filtered
    assert "sibling_summary" not in filtered
    assert "blacklist_summary" not in filtered
    assert "active_hyp_summary" not in filtered
    assert "strategy_guidance" not in filtered
    assert "search_control_guidance" not in filtered
    assert "search_memory" not in filtered
    assert "research_log" not in filtered

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(block["text"] for block in system_blocks) + user_prompt
    assert "## Current Champion Research Code" in rendered_prompt
    assert "class Relocate" in rendered_prompt
    assert "## Current Branch Code" in rendered_prompt
    assert "## Problem Measurement Diagnostics" in rendered_prompt
    assert "MEASUREMENT_POWER_LOW" in rendered_prompt
    assert "## Cross-Branch Research Map" not in rendered_prompt
    assert "## Runtime Feedback" not in rendered_prompt
    assert "## Objective Opportunity Profile" not in rendered_prompt
    assert "## Experiment History" not in rendered_prompt
    assert "hidden sibling branch" not in rendered_prompt
    assert "hidden rejected mechanism" not in rendered_prompt
    assert "hidden strategy guidance" not in rendered_prompt


def test_hypothesis_prompt_surfaces_research_signal_and_manifest_ratio():
    context = {
        "problem_summary": "CVRP formal screening objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1 screening complete",
        "experiment_history": (
            "branch b1: route_merge_reinsertion lost on large cases; "
            "effect zero on compact routes."
        ),
        "sibling_summary": "sibling b2 explored scheduler compaction with no effect.",
        "blacklist_summary": "avoid duplicate route_merge_reinsertion shape.",
        "cross_branch_research": (
            "compact_cross_branch_learning.v1 lesson:route-slack diversify "
            "away from no_effect local_search family."
        ),
        "branch_lesson_records": [
            {
                "lesson_id": "lesson:route-slack",
                "scope": "cross_branch",
                "lesson_role": "avoid",
            }
        ],
        "objective_opportunity_profile": "large-case gap remains on E-n101.",
        "runtime_feedback": "runtime saturated; treat as auxiliary signal.",
    }

    system_blocks, user_prompt = _split_hypothesis_context(context)
    rendered_system = "\n".join(str(block["text"]) for block in system_blocks)
    rendered_prompt = rendered_system + "\n" + user_prompt

    assert "## Compact Research Signals" in rendered_system
    assert "lesson:route-slack" in rendered_system
    assert "branch b1: route_merge_reinsertion lost" in rendered_system
    assert "## Compact Safety and Output Invariants" in user_prompt
    assert "Telemetry contract:" in user_prompt
    assert "Objective field contract:" in user_prompt
    assert "Runtime constraint:" in user_prompt
    assert "excluded from DecisionFeatures" in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-context-signal-density",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    accounting = manifest["block_family_accounting"]

    assert accounting["decision_features_excluded"] is True
    assert accounting["research_signal_chars"] > 0
    assert accounting["governance_chars"] > 0
    assert accounting["research_signal_char_share"] > 0
    assert accounting["governance_char_share"] > 0
    assert accounting["research_signal_ratio"] is not None
    assert accounting["families"]["research_signal"]["section_count"] >= 4
    assert accounting["families"]["governance"]["section_count"] >= 2


def test_branch_lesson_context_is_compact_and_prioritized_before_cross_branch_map():
    records = []
    for idx in range(6):
        records.append(
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": f"lesson:warehouse-{idx}",
                "source": "proposal_only",
                "decision_input_policy": "excluded_from_decision_features",
                "scope": "cross_branch",
                "lesson_role": "contrast",
                "lesson_type": "no_effect_plateau",
                "maturity": "fresh",
                "source_branch_ids": [f"branch-{idx}"],
                "shared_signature": {
                    "change_locus": "order_level",
                    "target_file": "operators/swap_orders.py",
                    "action": "modify",
                    "mechanism_family": "order_swap",
                    "raw_extra": "hidden" * 200,
                },
                "evidence_basis": {
                    "outcome_patterns": {"no_effect": 2},
                    "activation_statuses": {"observed": 1},
                    "raw_rows": [{"case": "hidden"}],
                },
                "required_response": {
                    "required_for": "clean_fork_new_branch",
                    "required_output_field": "branch_lesson_usage",
                    "required_contrast_dimensions": [
                        "target_file",
                        "mechanism_family",
                        "runtime_budget_strategy",
                    ],
                    "same_branch_refinement_allowed": False,
                    "sibling_duplication_allowed": False,
                    "raw_instruction": "hidden" * 200,
                },
                "raw_text": "hidden raw branch lesson text " * 200,
                "full_audit": {"hidden": True},
            }
        )
    context = {
        "problem_summary": "Warehouse objective.",
        "research_surfaces": "Research surfaces: order_level",
        "operator_categories": "order_level",
        "available_actions": "modify, create_new",
        "targetable_files": "operators/*.py",
        "champion_operators_code": "class SwapOrders:\n    pass\n",
        "champion_stats": "champion_v1",
        "cross_branch_research": "compact_cross_branch_learning.v1 broad map",
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "required_for": "clean_fork_new_branch",
            "required_output_field": "branch_lesson_usage",
            "candidate_lesson_ids": [record["lesson_id"] for record in records],
            "required_contrast_dimensions": [
                "target_file",
                "mechanism_family",
                "runtime_budget_strategy",
            ],
            "decision_features_excluded": True,
        },
        "branch_lesson_records": records,
    }

    system_blocks, user_prompt = _split_hypothesis_context(context)
    rendered_system = "\n".join(str(block["text"]) for block in system_blocks)

    assert rendered_system.index("## Branch Lesson Usage Context") < (
        rendered_system.index("## Cross-Branch Research Map")
    )
    assert "lesson:warehouse-0" in rendered_system
    assert "runtime_budget_strategy" in rendered_system
    assert "hidden raw branch lesson text" not in rendered_system
    assert "raw_extra" not in rendered_system
    assert "raw_rows" not in rendered_system
    assert "full_audit" not in rendered_system
    assert "<truncated agentic context>" not in rendered_system
    assert "When leaving a no-effect or weak-positive branch" in user_prompt
    assert "old target/action/mechanism family" in user_prompt


def test_problem_measurement_diagnostics_are_tainted_and_holdout_details_hidden():
    context = {
        "problem_summary": "CVRP formal screening objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1 screening complete",
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "effect_scale": {
                "metric": "total_distance",
                "unit": "raw_delta",
                "practical_delta_screen": 2.0,
                "practical_delta_validate": 1.0,
                "mde_at_power_80": 9.9,
            },
            "calibration": {
                "calibration_ref": "formal/calibration/aa_noise_floor.json",
                "mde_at_power_80": 9.9,
                "recommended_min_seeds": 8,
                "false_pass_rate_at_current_gate": 0.0,
                "selected_cases": ["secret-screening-case"],
            },
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "calibration_age_days": 1,
                "calibration_max_age_days": 90,
                "n_pairs": 96,
                "mde_at_power_80": 9.9,
                "noise_band_p90_abs": 2.4,
                "effect_to_mde_ratio": 0.2,
                "signal_to_noise_tier": "low_power",
                "calibration_ref": "formal/calibration/aa_noise_floor.json",
                "raw_pair_rows": [{"case": "secret-readiness-row"}],
            },
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "low_snr",
                    "surface": "solver_design",
                    "summary": "Candidate effects below measured screening MDE.",
                    "recommended_action": "continue with measurable bounded changes",
                    "reason_codes": ["MEASUREMENT_POWER_LOW"],
                    "validation_case_details": "secret-validation-case-detail",
                    "frozen_case_details": "secret-frozen-case-detail",
                    "raw_pair_rows": [{"case": "secret-raw-row"}],
                }
            ],
            "raw_calibration_pair_rows": [{"case": "secret-aa-row"}],
            "bks_gap_details": "secret-bks-gap",
            "prompt_ratios": {"research_signal_ratio": 0.1},
            "llm_text": "secret llm prose",
        },
    }

    filtered = filter_hypothesis_context_for_prompt(context)
    diagnostic = filtered["problem_measurement_diagnostics"]

    assert "problem_measurement_proposal_diagnostic.v1" in diagnostic
    assert "problem_owned_proposal_diagnostic" in diagnostic
    assert "excluded_from_decision_features" in diagnostic
    assert "total_distance" in diagnostic
    assert "mde_at_power_80" in diagnostic
    assert "signal_to_noise_tier" in diagnostic
    assert "low_power" in diagnostic
    assert "MEASUREMENT_POWER_LOW" in diagnostic
    assert "secret-screening-case" not in diagnostic
    assert "secret-readiness-row" not in diagnostic
    assert "secret-validation-case-detail" not in diagnostic
    assert "secret-frozen-case-detail" not in diagnostic
    assert "secret-raw-row" not in diagnostic
    assert "secret-aa-row" not in diagnostic
    assert "secret-bks-gap" not in diagnostic
    assert "research_signal_ratio" not in diagnostic
    assert "secret llm prose" not in diagnostic

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(block["text"] for block in system_blocks) + user_prompt
    assert "## Problem Measurement Diagnostics" in rendered_prompt
    assert "## Compact Research Signals" in rendered_prompt
    assert "excluded from DecisionFeatures" in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-problem-measurement-diagnostics",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    accounting = manifest["block_family_accounting"]
    assert accounting["decision_features_excluded"] is True
    assert accounting["research_signal_chars"] > 0
    assert "problem_measurement_diagnostics" in manifest["section_names"]
    assert manifest["section_statuses"]["problem_measurement_diagnostics"][
        "block_family"
    ] == "research_signal"
    measurement_entries = [
        entry
        for entry in manifest["visibility_ledger"]["entries"]
        if entry.get("entry_kind") == "section"
        and entry.get("section_name") == "problem_measurement_diagnostics"
    ]
    assert len(measurement_entries) == 1
    assert measurement_entries[0]["visibility_status"] == "full"


def test_record_only_measurement_governance_suppresses_prompt_measurement_diagnostics():
    context = {
        "problem_summary": "CVRP formal screening objective.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "champion_v1 screening complete",
        "experiment_history": (
            "branch b1\n"
            "    screening_feedback.tier=weak activation=observed "
            "effect=none runtime_confidence=low "
            "opportunity_status=opportunity_poor "
            "repeat_unchanged_allowed=false\n"
            "    opportunity_diagnostics: measurement-owned low SNR guidance"
        ),
        "objective_opportunity_profile": (
            "## Objective Opportunity Profile (screening only)\n"
            "- total_cost: positive_cases=1 negative_cases=0 tie_cases=1"
        ),
        "runtime_feedback": (
            "## Runtime Feedback\n"
            "candidate runtime ratio remains within the branch budget"
        ),
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "branch_lesson_records": [
                {
                    "schema_version": "branch_lesson.v1",
                    "lesson_id": "lesson:non-measurement-still-visible",
                    "scope": "cross_branch",
                    "summary": "A sibling branch preserved feasibility.",
                    "usage_requirement": {
                        "required_output_field": "branch_lesson_usage",
                    },
                }
            ],
        },
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "record_id": "branch_lesson_usage_requirement:record-only",
            "required_output_field": "branch_lesson_usage",
        },
        "branch_lesson_records": [
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": "lesson:branch-memory-still-visible",
                "scope": "same_branch",
                "summary": "Current branch memory remains available.",
            }
        ],
        "measurement_governance": "record_only",
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "runtime_model": "budget_exhausting",
            "pairing_validity": "trajectory_divergent",
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "signal_to_noise_tier": "low_power",
            },
            "opportunity_diagnostics": [
                {
                    "diagnostic_type": "low_snr",
                    "summary": "Candidate effects below measured screening MDE.",
                    "reason_codes": ["MEASUREMENT_POWER_LOW"],
                }
            ],
        },
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert "problem_measurement_diagnostics" not in filtered

    system_blocks, user_prompt = _split_hypothesis_context(filtered)
    rendered_prompt = "\n".join(block["text"] for block in system_blocks) + user_prompt
    assert "## Problem Measurement Diagnostics" not in rendered_prompt
    assert "MEASUREMENT_POWER_LOW" not in rendered_prompt
    assert "measurement-owned low SNR guidance" not in rendered_prompt
    assert "opportunity_status=opportunity_poor" not in rendered_prompt
    assert "## Objective Opportunity Profile (screening only)" in rendered_prompt
    still_on_non_measurement_signals = {
        "objective_opportunity_profile": "Objective Opportunity Profile",
        "runtime_feedback": "Runtime Feedback",
        "cross_branch_research": "compact_cross_branch_learning.v1",
        "branch_lesson_records": "lesson:branch-memory-still-visible",
        "branch_lesson_usage_requirement": (
            "branch_lesson_usage_requirement:record-only"
        ),
    }
    for key, expected_text in still_on_non_measurement_signals.items():
        assert key in filtered
        assert expected_text in str(filtered[key])
        assert expected_text in rendered_prompt

    manifest = build_api_visible_prompt_manifest(
        session_id="session-record-only-measurement-suppressed",
        phase="hypothesis",
        call_kind="hypothesis",
        prompt_context=filtered,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    assert "problem_measurement_diagnostics" not in manifest["section_names"]
    assert "problem_measurement_diagnostics" not in manifest["section_statuses"]
    assert not any(
        entry.get("section_name") == "problem_measurement_diagnostics"
        for entry in manifest["visibility_ledger"]["entries"]
    )

    on_context = dict(context, measurement_governance="on")
    on_filtered = filter_hypothesis_context_for_prompt(on_context)
    assert "problem_measurement_diagnostics" in on_filtered
    assert "MEASUREMENT_POWER_LOW" in on_filtered["problem_measurement_diagnostics"]
    assert "measurement-owned low SNR guidance" in on_filtered["experiment_history"]
    assert "opportunity_status=opportunity_poor" in on_filtered["experiment_history"]


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
        filter_hypothesis_context_for_prompt(active)["material_difference_requirement"][
            "record_id"
        ]
        == "material_difference_requirement:branch-a"
    )
    assert "material_difference_requirement" not in (
        filter_hypothesis_context_for_prompt(inactive)
    )
    assert "material_difference_requirement" not in (
        filter_hypothesis_context_for_prompt(empty_required)
    )


def test_branch_lesson_requirement_and_records_remain_top_level_after_filter():
    context = {
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "branch_lesson_records": [
                {
                    "schema_version": "branch_lesson.v1",
                    "lesson_id": "lesson:full-hidden",
                    "raw_text": "hidden raw branch lesson text",
                    "required_response": {
                        "required_for": "clean_fork_new_branch",
                        "required_output_field": "branch_lesson_usage",
                    },
                }
            ],
        },
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "record_id": "branch_lesson_usage_requirement:visible",
            "required_for": "clean_fork_new_branch",
            "required_output_field": "branch_lesson_usage",
        },
        "branch_lesson_records": [
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": "lesson:visible",
                "scope": "cross_branch",
                "lesson_role": "contrast",
                "lesson_type": "near_duplicate",
                "required_response": {
                    "required_for": "clean_fork_new_branch",
                    "required_output_field": "branch_lesson_usage",
                    "required_contrast_dimensions": ["target_file"],
                },
            }
        ],
    }

    filtered = filter_hypothesis_context_for_prompt(context)

    assert "cross_branch_research_payload" not in filtered
    assert (
        filtered["branch_lesson_usage_requirement"]["record_id"]
        == "branch_lesson_usage_requirement:visible"
    )
    assert filtered["branch_lesson_records"][0]["lesson_id"] == "lesson:visible"
    assert "hidden raw branch lesson text" not in str(filtered)


def test_branch_lesson_requirement_only_kept_when_required_and_nonempty():
    active = {
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "required_for": "clean_fork_new_branch",
            "record_id": "branch_lesson_usage_requirement:branch-a",
        }
    }
    inactive = {
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": False,
            "record_id": "branch_lesson_usage_requirement:branch-a",
        }
    }
    empty_required = {
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
        }
    }

    assert (
        filter_hypothesis_context_for_prompt(active)["branch_lesson_usage_requirement"][
            "record_id"
        ]
        == "branch_lesson_usage_requirement:branch-a"
    )
    assert "branch_lesson_usage_requirement" not in (
        filter_hypothesis_context_for_prompt(inactive)
    )
    assert "branch_lesson_usage_requirement" not in (
        filter_hypothesis_context_for_prompt(empty_required)
    )
