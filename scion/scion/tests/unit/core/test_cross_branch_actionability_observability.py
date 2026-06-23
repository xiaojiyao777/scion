from scion.core.evidence_recording.cross_branch_observability import (
    build_cross_branch_research_observability,
)


def test_clean_fork_policy_choices_are_not_missed_same_branch_refinements() -> None:
    payload = build_cross_branch_research_observability(
        scheduler_records=[
            {
                "clean_fork_selected": True,
                "same_branch_refinement_not_selected_reason": (
                    "scheduler_selected_clean_exploration_branch"
                ),
                "post_finalizer_actual_branch_action": "explore_new_clean_fork",
            },
            {
                "clean_fork_selected": True,
                "same_branch_refinement_not_selected_reason": (
                    "new_exploration_slot_available"
                ),
                "pre_finalizer_scheduler_slot": "explore_new",
                "post_finalizer_actual_branch_action": "explore_new_clean_fork",
                "post_finalizer_next_proposal_policy": "clean_fork_selected",
            },
            {
                "scheduler_slot": "explore_new",
                "scheduler_reason": "runtime_evidence_completeness_clean_fork",
                "result_action": "skip",
                "scheduler_audit_metadata": {
                    "runtime_evidence_clean_fork_selected": True,
                    "runtime_evidence_clean_fork_reason": (
                        "runtime_evidence_completeness_clean_fork"
                    ),
                    "runtime_evidence_clean_fork_candidates": [
                        {
                            "lineage_status": "active_no_effect",
                            "screening_tier": "no_effect",
                            "runtime_evidence_pressure_count": 2,
                        }
                    ],
                    "same_mechanism_clean_fork_justification": {
                        "reason": "clean_fork_selected_instead_of_same_branch",
                        "clean_fork_reason": (
                            "runtime_evidence_completeness_clean_fork"
                        ),
                        "active_branch_cap_context": {
                            "scheduler_slot": "explore_new",
                            "scheduler_reason": (
                                "runtime_evidence_completeness_clean_fork"
                            ),
                        },
                    },
                },
            },
        ],
    )

    assert payload["same_branch_refinement_not_selected_count"] == 1
    assert payload["accepted_clean_fork_policy_choice_count"] == 2
