"""Focused tests split from test_proposal_pipeline.py."""

from types import SimpleNamespace
from typing import Any

from .proposal_pipeline_test_support import *  # noqa: F401,F403
from scion.core.branch_hygiene import branch_hygiene_context
from scion.core.campaign_loop import CampaignLoop
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import Branch, BranchState, MechanismChange
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult

def test_generate_hypothesis_builds_context_and_record() -> None:
    pipeline, branch, runtime, circuit, failures, _ = _pipeline()

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert record.branch_id == branch.branch_id
    assert record.family_id == "bounded-local"
    assert record.suggested_weight == 0.5
    assert circuit.successes == 1
    assert failures == []
    assert runtime.hypothesis_kwargs["branch_workspace"] == "/tmp/branch"
    assert runtime.hypothesis_kwargs["forced_locus"] == "local_search"
    assert runtime.hypothesis_kwargs["weight_opt_result"] == {"weights": "latest"}
    assert [b.branch_id for b in runtime.hypothesis_kwargs["sibling_branches"]] == [
        "sibling"
    ]
    assert pipeline.agentic_outputs == {}


def test_generate_hypothesis_marks_suspect_branch_as_repair_focused() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Repair activation telemetry wiring for bounded_probe.",
        change_locus="local_search",
        action="modify",
        target_file="operators/bounded.py",
        target_weakness="The declared mechanism telemetry did not activate.",
        expected_effect="Fix activation/runtime telemetry without adding a new mechanism.",
        mechanism_changes=(
            MechanismChange(id="bounded_probe", change_type="add"),
        ),
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(creative=creative)
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_code_status = "telemetry_wiring_suspect"
    branch.last_screening_feedback_tier = "inactive"
    branch.last_telemetry_outcome = "activation_missing_or_wiring_suspect"
    branch.telemetry_repair_mechanism_ids = ("bounded_probe",)

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert runtime.hypothesis_kwargs["branch_workspace"] is None
    hygiene = creative.hypothesis_context["branch_hygiene"]
    assert hygiene["branch_code_status"] == "telemetry_wiring_suspect"
    assert hygiene["repair_focus_required"] is True
    assert hygiene["repair_focus_reason"] == "wiring_suspect_requires_repair"
    assert "wiring_suspect_requires_repair" in (
        creative.hypothesis_context["branch_hygiene_guidance"]
    )


def test_generate_hypothesis_rejects_new_mechanism_on_suspect_branch() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add a different local-search mechanism.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/different.py",
        mechanism_changes=(
            MechanismChange(id="different_mechanism", change_type="add"),
        ),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)
    branch.branch_code_status = "telemetry_wiring_suspect"
    branch.last_telemetry_outcome = "activation_missing_or_wiring_suspect"
    branch.telemetry_repair_mechanism_ids = ("bounded_probe",)

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert "repair_first_policy_violation" in detail
    assert "new_mechanism_requires_clean_fork" in detail
    assert "bounded_probe" in detail
    assert "different_mechanism" in detail
    assert failures == []
    assert circuit.failures == []


def test_generate_hypothesis_allows_active_no_effect_same_mechanism_followup() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Tune bounded route-pair search after no-effect screening.",
        change_locus="local_search",
        action="modify",
        target_file="operators/bounded.py",
        target_weakness="The existing bounded probe had no objective effect.",
        expected_effect="Tune the same mechanism without adding a new one.",
        mechanism_changes=(
            MechanismChange(id="bounded_probe", change_type="modify"),
        ),
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(creative=creative)
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert runtime.hypothesis_kwargs["branch_workspace"] == "/tmp/branch"
    hygiene = creative.hypothesis_context["branch_hygiene"]
    assert hygiene["branch_code_status"] == "active_no_effect"
    assert hygiene["repair_focus_required"] is False
    assert hygiene["hypothesis_generation_mode"] == "same_mechanism_only"
    assert hygiene["branch_followup_policy"] == "same_mechanism_followup_only"
    assert hygiene["clean_fork_policy"] == "clean_fork_required_for_new_mechanism"
    assert hygiene["branch_mechanism_ids"] == ["bounded_probe"]
    assert hygiene["baseline_policy"] == (
        "branch_workspace_same_mechanism_followup_only"
    )
    assert "active_no_effect" in creative.hypothesis_context[
        "branch_hygiene_guidance"
    ]
    assert "clean_fork_required_for_new_mechanism" in creative.hypothesis_context[
        "branch_hygiene_guidance"
    ]


def test_generate_hypothesis_context_includes_runtime_clean_fork_guidance() -> None:
    creative = FakeCreative()
    pipeline, branch, _, _, _, _ = _pipeline(creative=creative)
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.branch_evidence_summary = {
        "tier": "weak_positive",
        "wins": 0,
        "losses": 0,
        "runtime_evidence_confidence": "low_cached_champion",
        "runtime_evidence_status": "incomplete",
        "runtime_evidence_pressure_count": 2,
    }

    pipeline.generate_hypothesis(branch)

    hygiene = creative.hypothesis_context["branch_hygiene"]
    guidance = creative.hypothesis_context["branch_hygiene_guidance"]
    decision_field_names = {field.name for field in fields(DecisionFeatures)}
    assert hygiene["runtime_evidence_clean_fork_guidance"]["reason"] == (
        "runtime_evidence_completeness_clean_fork"
    )
    assert hygiene["runtime_evidence_clean_fork_guidance"][
        "tainted_proposal_guidance"
    ] is True
    assert hygiene["runtime_evidence_clean_fork_guidance"][
        "decision_features_excluded"
    ] is True
    assert "runtime_evidence_clean_fork_guidance" in guidance
    assert "excluded from DecisionFeatures" in guidance
    assert "runtime_evidence_clean_fork_guidance" not in decision_field_names


def test_generate_hypothesis_rejects_new_mechanism_on_active_no_effect_branch() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add a distinct route perturbation after no-effect screening.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_probe.py",
        mechanism_changes=(
            MechanismChange(id="different_probe", change_type="add"),
        ),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert "branch_lifecycle_policy_violation" in detail
    assert "new_mechanism_requires_clean_fork" in detail
    assert "bounded_probe" in detail
    assert "different_probe" in detail
    assert failures == []
    assert circuit.failures == []


def test_lifecycle_policy_block_fixture_marks_branch_and_reroutes_without_round_cost() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add a distinct route perturbation after no-effect screening.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_probe.py",
        mechanism_changes=(
            MechanismChange(id="different_probe", change_type="add"),
        ),
    )
    proposal, branch, _, circuit, failures, _ = _pipeline(creative=creative)
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)
    clean_branch = Branch(
        branch_id="clean-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
    )
    recorded_steps: list[StepRecord] = []
    loop_statuses: list[dict[str, Any]] = []
    last_results: list[StepResult] = []
    stopped_reasons: list[str | None] = []
    calls = 0

    explore = ExploreStepPipeline(
        branch_controller=SimpleNamespace(next_stage=lambda _branch_id: None),
        contract_gate=None,
        verification_gate=None,
        hypothesis_store=SimpleNamespace(
            mark_status=lambda *_args, **_kwargs: None,
            save=lambda *_args, **_kwargs: None,
        ),
        registry=SimpleNamespace(
            record_event=lambda *_args, **_kwargs: None,
            record_contract_failure=lambda *_args, **_kwargs: None,
        ),
        campaign_id="camp-1",
        get_champion=lambda: _champion(),
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak=proposal.failure_streak,
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=proposal.generate_hypothesis,
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=recorded_steps.append,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        proposal_failure_detail_for=proposal.pop_hypothesis_failure_detail,
        proposal_session_ref_for=lambda _branch_id: None,
        update_status_progress=lambda _payload: None,
    )

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return explore.run(branch)
        selected = Scheduler(max_active_branches=2).select_next(
            [branch, clean_branch]
        )
        assert selected.action == "run_existing"
        assert selected.branch is clean_branch
        return StepResult(
            action="explore",
            branch_id=clean_branch.branch_id,
            reason="screening complete",
        )

    def write_status(**kwargs: Any) -> None:
        if "loop_status" in kwargs:
            loop_statuses.append(dict(kwargs["loop_status"]))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=bool(circuit.failures),
            last_failure_detail=(circuit.failures[-1] if circuit.failures else None),
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert recorded_steps[0].attempt_kind == "branch_lifecycle_policy"
    assert recorded_steps[0].counts_toward_max_rounds is False
    assert "new_mechanism_requires_clean_fork" in (
        recorded_steps[0].failure_detail or ""
    )
    assert last_results[0].attempt_kind == "branch_lifecycle_policy"
    assert last_results[0].counts_toward_max_rounds is False
    block_status = next(
        status
        for status in loop_statuses
        if status["branch_lifecycle_policy_blocks"] == 1
        and status["effective_rounds_completed"] == 0
    )
    assert block_status["proposal_attempts_consumed"] == 0
    assert block_status["quality_blocks"] == 0
    assert loop_statuses[-1]["branch_lifecycle_policy_blocks"] == 1
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 1
    assert loop_statuses[-1]["effective_rounds_completed"] == 1
    assert loop_statuses[-1]["quality_blocks"] == 0
    assert failures == []
    assert circuit.failures == []
    assert proposal.failure_streak == {"proposal": 1}
    assert branch.pending_retry is False
    assert branch.failure_codes == []
    hygiene = branch_hygiene_context(branch)
    assert hygiene["branch_lifecycle_new_mechanism_ineligible"] is True
    assert hygiene["branch_lifecycle_reroute_reason"] == (
        "clean_fork_after_branch_lifecycle_policy_block"
    )
    assert hygiene["branch_followup_policy"] == "same_mechanism_followup_only"
    assert hygiene["next_branch_selection_policy"] == (
        "clean_branch_or_clean_fork_for_new_mechanism"
    )
    assert "max_rounds_exhausted" in stopped_reasons


def test_repeated_lifecycle_policy_blocks_do_not_trip_circuit_breaker() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add a distinct route perturbation after no-effect screening.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_probe.py",
        mechanism_changes=(
            MechanismChange(id="different_probe", change_type="add"),
        ),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"
    branch.branch_mechanism_ids = ("bounded_probe",)

    for _ in range(4):
        hypothesis, record = pipeline.generate_hypothesis(branch)
        assert hypothesis is None
        assert record is None
        assert "branch_lifecycle_policy_violation" in (
            pipeline.pop_hypothesis_failure_detail(branch.branch_id) or ""
        )

    assert failures == []
    assert circuit.failures == []


def test_active_no_effect_policy_uses_step_history_mechanism_ids() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add a distinct route perturbation after no-effect screening.",
        change_locus="local_search",
        action="create_new",
        target_file="operators/new_probe.py",
        mechanism_changes=(
            MechanismChange(id="different_probe", change_type="add"),
        ),
    )
    previous = HypothesisProposal(
        hypothesis_text="Initial bounded probe.",
        change_locus="local_search",
        action="modify",
        target_file="operators/bounded.py",
        mechanism_changes=(
            MechanismChange(id="bounded_probe", change_type="add"),
        ),
    )
    pipeline, branch, _, _, _, _ = _pipeline(creative=creative)
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"
    pipeline.step_history = [
        StepRecord(
            round_num=1,
            branch_id=branch.branch_id,
            hypothesis=previous,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=object(),
            decision=None,
            failure_stage=None,
            failure_detail=None,
        )
    ]

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert "branch_lifecycle_policy_violation" in detail
    assert "bounded_probe" in detail
    assert "different_probe" in detail


def test_generate_hypothesis_threads_diagnostic_forced_surface_controls() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Modify the forced blueprint surface.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(
        creative=creative,
        forced_locus="algorithm_blueprint",
        forced_surface_action="modify",
        forced_surface_target_file="policies/algorithm_blueprint.py",
        forced_surface_diagnostic=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True
    assert pipeline.forced_surface_action is None
    assert pipeline.forced_surface_target_file is None
    assert pipeline.forced_surface_diagnostic is False


def test_generate_hypothesis_keeps_launch_forced_surface_across_rounds() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Modify the forced blueprint surface.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
    )
    pipeline, branch, runtime, _, _, _ = _pipeline(
        creative=creative,
        forced_locus=None,
        persistent_forced_locus="algorithm_blueprint",
        forced_surface_action="modify",
        forced_surface_target_file="policies/algorithm_blueprint.py",
        forced_surface_diagnostic=True,
    )

    first_hypothesis, first_record = pipeline.generate_hypothesis(branch)

    assert first_hypothesis is not None
    assert first_record is not None
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True

    next_branch = _branch("round-2")
    second_hypothesis, second_record = pipeline.generate_hypothesis(next_branch)

    assert second_hypothesis is not None
    assert second_record is not None
    assert second_record.branch_id == "round-2"
    assert runtime.hypothesis_kwargs["forced_locus"] == "algorithm_blueprint"
    assert runtime.hypothesis_kwargs["forced_action"] == "modify"
    assert (
        runtime.hypothesis_kwargs["forced_target_file"]
        == "policies/algorithm_blueprint.py"
    )
    assert runtime.hypothesis_kwargs["forced_surface_diagnostic"] is True
    assert pipeline.persistent_forced_locus == "algorithm_blueprint"
    assert pipeline.forced_surface_action == "modify"
    assert (
        pipeline.forced_surface_target_file
        == "policies/algorithm_blueprint.py"
    )
    assert pipeline.forced_surface_diagnostic is True
