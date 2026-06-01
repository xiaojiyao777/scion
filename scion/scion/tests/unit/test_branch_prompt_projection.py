from __future__ import annotations

from scion.core.branch_hygiene import (
    branch_hygiene_guidance,
    record_branch_lifecycle_policy_block,
)
from scion.core.models import Branch, BranchState
from scion.proposal.context_manager import _summarise_siblings
from scion.proposal.engine import _split_hypothesis_context


def _branch(branch_id: str, *, branch_code_status: str = "clean") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status=branch_code_status,
    )


def _hypothesis_prompt_user_text(sibling_summary: str) -> str:
    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Test problem",
            "research_surfaces": "Research surfaces: local_search",
            "operator_categories": "local_search",
            "available_actions": "modify",
            "targetable_files": "operators/local_search.py",
            "champion_operators_code": "# champion code",
            "champion_stats": "Champion baseline",
            "experiment_history": "(none)",
            "blacklist_summary": "(none)",
            "active_hyp_summary": "(none)",
            "sibling_summary": sibling_summary,
        }
    )
    return user_prompt


def test_sibling_prompt_projection_includes_suspect_repair_focus() -> None:
    sibling = _branch(
        "suspect123456",
        branch_code_status="telemetry_wiring_suspect",
    )
    sibling.last_telemetry_outcome = "activation_missing_or_wiring_suspect"

    summary = _summarise_siblings([sibling])
    prompt = _hypothesis_prompt_user_text(summary)

    assert "## Sibling Branches" in prompt
    assert "branch suspect" in prompt
    assert "state=explore" in prompt
    assert "branch_code_status=telemetry_wiring_suspect" in prompt
    assert (
        "last_telemetry_outcome=activation_missing_or_wiring_suspect"
        in prompt
    )
    assert "repair_focus_required=true" in prompt
    assert "repair_focus=wiring_suspect_requires_repair" in prompt
    assert "repair_policy=repair_first_same_mechanism_or_clean_fork" in prompt


def test_sibling_prompt_projection_marks_clean_and_no_effect_status() -> None:
    clean = _branch("clean123456", branch_code_status="clean")
    no_effect = _branch("noeffect123", branch_code_status="active_no_effect")
    no_effect.last_telemetry_outcome = "no_objective_effect"
    no_effect.branch_mechanism_ids = ("bounded_probe",)

    summary = _summarise_siblings([clean, no_effect])
    prompt = _hypothesis_prompt_user_text(summary)
    clean_line = next(line for line in prompt.splitlines() if "clean123" in line)
    no_effect_line = next(
        line for line in prompt.splitlines() if "noeffect" in line
    )

    assert "branch_code_status=clean" in clean_line
    assert "last_telemetry_outcome=none" in clean_line
    assert "repair_focus_required=false" in clean_line
    assert "baseline_policy=clean" in clean_line

    assert "branch_code_status=active_no_effect" in no_effect_line
    assert "last_telemetry_outcome=no_objective_effect" in no_effect_line
    assert "repair_focus_required=false" in no_effect_line
    assert "branch_followup_policy=same_mechanism_followup_only" in no_effect_line
    assert "hypothesis_generation_mode=same_mechanism_only" in no_effect_line
    assert "clean_fork_policy=clean_fork_required_for_new_mechanism" in no_effect_line
    assert "branch_mechanism_ids=bounded_probe" in no_effect_line
    assert "allowed_mechanism_ids=bounded_probe" in no_effect_line
    assert "protected_mechanism_ids=bounded_probe" in no_effect_line
    assert "forbidden_mechanism_policy=no_unrelated_mechanism_ids" in no_effect_line
    assert "baseline_policy=branch_workspace_same_mechanism_followup_only" in no_effect_line
    assert (
        "diversity_redirect_guidance=runtime_saturated_diversity_redirect"
        in no_effect_line
    )
    assert (
        "diversity_action=change_mechanism_family_or_trigger_or_observability"
        in no_effect_line
    )
    assert "branch_code_status=clean" not in no_effect_line
    assert "baseline_policy=clean" not in no_effect_line


def test_sibling_prompt_projection_includes_lifecycle_reroute_policy() -> None:
    branch = _branch("blocked123456", branch_code_status="active_no_effect")
    branch.branch_mechanism_ids = ("bounded_probe",)
    record_branch_lifecycle_policy_block(
        branch,
        (
            "branch_lifecycle_policy_violation: "
            "new_mechanism_requires_clean_fork"
        ),
    )

    summary = _summarise_siblings([branch])
    prompt = _hypothesis_prompt_user_text(summary)
    blocked_line = next(line for line in prompt.splitlines() if "blocked" in line)

    assert "branch_followup_policy=same_mechanism_followup_only" in blocked_line
    assert "branch_lifecycle_new_mechanism_ineligible=true" in blocked_line
    assert (
        "branch_lifecycle_recovery_reason="
        "clean_fork_after_branch_lifecycle_policy_block"
    ) in blocked_line
    assert (
        "next_branch_selection_policy="
        "clean_branch_or_clean_fork_for_new_mechanism"
    ) in blocked_line


def test_sibling_prompt_projection_includes_checkpoint_branch_card() -> None:
    branch = _branch("restore123456", branch_code_status="regressed_followup")
    branch.last_screening_feedback_tier = "weak_positive"
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.last_valid_checkpoint_id = "checkpoint-last"
    branch.rollback_count = 1
    branch.branch_mechanism_ids = ("generic_probe",)
    branch.last_branch_lifecycle_policy_block = {
        "screening_case_wins": 3,
        "screening_case_losses": 1,
        "screening_case_ties": 2,
        "median_delta": 0.04,
        "runtime_ratio_median": 1.03,
        "decision_reason_codes": ["BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT"],
    }

    summary = _summarise_siblings([branch])
    prompt = _hypothesis_prompt_user_text(summary)
    restore_line = next(line for line in prompt.splitlines() if "restore" in line)

    assert "branch_id=restore123456" in restore_line
    assert "status=explore" in restore_line
    assert "mechanism_ids=generic_probe" in restore_line
    assert "lineage_status=restored_weak_positive" in restore_line
    assert "current_head_status=regressed_followup" in restore_line
    assert "best_checkpoint_status=best_quality_retained" in restore_line
    assert "best_quality_checkpoint_id=checkpoint-best" in restore_line
    assert "last_valid_checkpoint_id=checkpoint-last" in restore_line
    assert "rollback_count=1" in restore_line
    assert "latest_head_failed=true" in restore_line
    assert "lineage_retained_checkpoint=true" in restore_line
    assert (
        "generic_evidence_summary=tier:weak_positive,wins:3,losses:1,ties:2"
        in restore_line
    )
    assert "effect:0.04" in restore_line
    assert "runtime:1.03" in restore_line
    assert "why_not_promoted_reason_codes=BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT" in (
        restore_line
    )
    assert "allowed_next_actions=refine_checkpoint,tune,integrate,parameterize" in (
        restore_line
    )
    assert (
        "forbidden_next_actions=treat_failed_head_as_lineage_failure"
        in restore_line
    )


def test_no_effect_branch_card_marks_unchanged_repeat_forbidden() -> None:
    branch = _branch("noeffect123", branch_code_status="active_no_effect")
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    rendered = branch_hygiene_guidance(branch)

    assert "lineage_status=active_no_effect" in rendered
    assert "current_head_status=active_no_effect" in rendered
    assert "best_checkpoint_status=none" in rendered
    assert "allowed_next_actions=clean_fork" in rendered
    assert "forbidden_next_actions=unrelated_mechanism,unchanged_repeat" in rendered
    for forbidden in ("CVRP", "route", "capacity", "customer", "vehicle"):
        assert forbidden not in rendered


def test_non_clean_branch_prompt_forces_same_mechanism_followup() -> None:
    branch = _branch("followup123", branch_code_status="active_no_effect")
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Test problem",
            "research_surfaces": "Research surfaces: local_search",
            "operator_categories": "local_search",
            "available_actions": "modify",
            "targetable_files": "operators/local_search.py",
            "champion_operators_code": "# champion code",
            "champion_stats": "Champion baseline",
            "experiment_history": "(none)",
            "blacklist_summary": "(none)",
            "active_hyp_summary": "(none)",
            "sibling_summary": "(none)",
            "branch_hygiene_guidance": branch_hygiene_guidance(branch),
        }
    )
    rendered = "\n".join(str(block["text"]) for block in system_blocks) + user_prompt

    assert "## Branch Code Status" in rendered
    assert "same_mechanism_followup_only" in rendered
    assert "hypothesis_generation_mode=same_mechanism_only" in rendered
    assert "allowed_mechanism_ids=bounded_probe" in rendered
    assert "protected_mechanism_ids=bounded_probe" in rendered
    assert "no_unrelated_mechanism_ids" in rendered
    assert "bounded_probe" in rendered
    assert "tune, integrate, repair, parameterize, or wire telemetry" in rendered
    assert "research action labels, not mechanism_changes change_type values" in rendered
    assert "map tune/parameterize to modify" in rendered
    assert "clean branch or clean fork before generation" in rendered


def test_same_mechanism_constraints_are_prominent_in_hypothesis_prompt() -> None:
    branch = _branch("followup123", branch_code_status="active_no_effect")
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Test problem",
            "research_surfaces": "Research surfaces: local_search",
            "operator_categories": "local_search",
            "available_actions": "modify",
            "targetable_files": "operators/local_search.py",
            "champion_operators_code": "# champion code",
            "champion_stats": "Champion baseline",
            "experiment_history": "(none)",
            "blacklist_summary": "(none)",
            "active_hyp_summary": "(none)",
            "sibling_summary": "(none)",
            "branch_hygiene_guidance": branch_hygiene_guidance(branch),
        }
    )
    rendered_system = "\n".join(str(block["text"]) for block in system_blocks)
    rendered = rendered_system + user_prompt

    constraints_pos = rendered.find("## Same-Mechanism Follow-up Constraints")
    branch_status_pos = rendered.find("## Branch Code Status")
    user_task_pos = rendered.find("## Analysis Steps")

    assert constraints_pos >= 0
    assert constraints_pos < branch_status_pos
    assert constraints_pos < user_task_pos
    assert "protected_mechanism_ids=bounded_probe" in rendered
    assert "allowed_actions=tune,integrate,repair,parameterize,telemetry_wiring" in rendered
    assert "allowed_actions are research action labels" in rendered
    assert "telemetry_wiring to modify or integrate" in rendered
    assert "clean_fork_policy=clean_fork_required_for_new_mechanism" in rendered
    assert "new or unrelated mechanism requires a clean branch or clean fork" in rendered
