from __future__ import annotations

from scion.core.branch_hygiene import record_branch_lifecycle_policy_block
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
    _, user_prompt = _split_hypothesis_context(
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
    assert "clean_fork_policy=clean_fork_required_for_new_mechanism" in no_effect_line
    assert "branch_mechanism_ids=bounded_probe" in no_effect_line
    assert "baseline_policy=branch_workspace_same_mechanism_followup_only" in no_effect_line
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
