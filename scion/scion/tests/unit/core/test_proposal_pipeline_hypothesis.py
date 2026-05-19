"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

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
