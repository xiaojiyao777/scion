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
    assert failures
    assert "repair_first_policy_violation" in failures[-1][1].detail
    assert circuit.failures


def test_generate_hypothesis_allows_active_no_effect_branch_with_marker() -> None:
    creative = FakeCreative()
    pipeline, branch, runtime, _, _, _ = _pipeline(creative=creative)
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.last_telemetry_outcome = "no_objective_effect"

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert runtime.hypothesis_kwargs["branch_workspace"] == "/tmp/branch"
    hygiene = creative.hypothesis_context["branch_hygiene"]
    assert hygiene["branch_code_status"] == "active_no_effect"
    assert hygiene["repair_focus_required"] is False
    assert hygiene["baseline_policy"] == "branch_workspace_allowed_with_marker"
    assert "active_no_effect" in creative.hypothesis_context[
        "branch_hygiene_guidance"
    ]


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
