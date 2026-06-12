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
    assert "compact_research_signals" not in decision_fields
    assert "research_signal_ratio" not in decision_fields
    assert "branch_lesson_records" not in decision_fields
    assert "branch_lesson_usage" not in decision_fields
    assert "branch_lesson_usage_requirement" not in decision_fields
    assert "family_saturation_summary" not in decision_fields
    assert "cross_branch_family_saturation_summary" not in decision_fields
    assert "problem_measurement_diagnostics" not in decision_fields
    assert "measurement_noise_floor" not in decision_fields
    assert "objective_opportunity_profile" not in decision_fields


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
