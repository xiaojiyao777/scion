from __future__ import annotations

from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import Branch, BranchState


def test_explore_status_progress_includes_suspect_branch_hygiene() -> None:
    branch = Branch(
        branch_id="suspect-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        current_code_hash="candidate-hash",
        last_clean_code_hash="candidate-hash",
        branch_code_status="telemetry_wiring_suspect",
        last_screening_feedback_tier="inactive",
        last_telemetry_outcome="activation_missing_or_wiring_suspect",
    )
    updates: list[dict] = []
    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=None,
        verification_gate=None,
        hypothesis_store=None,
        registry=None,
        campaign_id="camp-1",
        get_champion=lambda: None,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (None, None),
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=lambda _step: None,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        update_status_progress=lambda payload: updates.append(payload),
    )

    pipeline._emit_status_progress(
        branch,
        phase="proposal_hypothesis",
        round_num=4,
    )

    assert updates
    payload = updates[0]
    assert payload["branch_code_status"] == "telemetry_wiring_suspect"
    assert payload["last_telemetry_outcome"] == (
        "activation_missing_or_wiring_suspect"
    )
    assert payload["repair_focus_required"] is True
    assert payload["repair_focus_reason"] == "wiring_suspect_requires_repair"
