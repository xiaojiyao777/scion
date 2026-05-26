"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403
from scion.core.models import MechanismChange

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
