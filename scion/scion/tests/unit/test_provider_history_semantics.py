"""Focused provider-only semantics for canonical screening history."""

from __future__ import annotations

from typing import Any

from scion.proposal.context_manager.history_projection import (
    proposal_screening_history,
)


def _record(candidate_composition: dict[str, Any] | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "attempt_id": "attempt-1",
        "round_num": 1,
        "source_branch_id": "branch-1",
        "relation": "current",
        "hypothesis": {
            "hypothesis_text": "Try the proposed search change.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/proposal_only.py",
        },
        "experiment_evidence": {
            "stage": "screening",
            "objective_outcome": {"aggregate": {"median_delta": 0.0}},
        },
    }
    if candidate_composition is not None:
        record["candidate_composition"] = candidate_composition
    return record


def test_eval_only_screening_separates_proposal_intent_from_patch_execution() -> None:
    raw = _record(
        {
            "current_step_change_scope": "eval_only_reuse",
            "evaluation_candidate": "reused_verified_branch_state",
        }
    )

    projected = proposal_screening_history([raw])[0]

    assert projected["proposal_intent"] == raw["hypothesis"]
    assert "hypothesis" not in projected
    assert projected["patch_present"] is False
    assert "executed_patch_files" not in projected
    assert "proposal_intent" not in raw
    assert raw["hypothesis"]["target_file"] == "policies/proposal_only.py"


def test_patch_files_are_projected_from_recorded_current_step_only() -> None:
    raw = _record(
        {
            "current_step_change_scope": "incremental_patch",
            "evaluation_candidate": "branch_state_after_current_step_patch",
            "current_step": {
                "target_files": [
                    "policies/executed_a.py",
                    "policies/executed_b.py",
                ],
            },
        }
    )

    projected = proposal_screening_history([raw])[0]

    assert projected["patch_present"] is True
    assert projected["executed_patch_files"] == [
        "policies/executed_a.py",
        "policies/executed_b.py",
    ]
    assert (
        projected["proposal_intent"]["target_file"]
        == "policies/proposal_only.py"
    )


def test_legacy_record_without_composition_stays_unknown_not_inferred() -> None:
    projected = proposal_screening_history([_record(None)])[0]

    assert "proposal_intent" in projected
    assert "hypothesis" not in projected
    assert "patch_present" not in projected
    assert "executed_patch_files" not in projected
