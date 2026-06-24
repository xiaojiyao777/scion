from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scion.postrun import (
    MappingPostrunInventoryPort,
    PostrunReadinessOrchestrator,
    ProblemReviewRegistry,
    ProblemReviewSummary,
)


def test_postrun_readiness_ports_compose_generic_ready_summary() -> None:
    inventory = {
        "lifecycle": {
            "wrapper_exit_status": 0,
            "postrun_acceptance_status": "ready",
        },
        "validity": {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
        },
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
        },
        "prompt_context_visibility_summary": {
            "raw_prompt_excluded": True,
            "raw_response_excluded": True,
            "patch_body_excluded": True,
            "source_body_excluded": True,
        },
    }

    summary = PostrunReadinessOrchestrator(
        MappingPostrunInventoryPort(inventory),
    ).build(Path("/tmp/run-root"))
    payload = summary.to_payload()

    assert payload["schema_version"] == "scion.postrun_readiness_summary.v1"
    assert payload["current_run_analysis_ready"] is True
    assert payload["delegation_ready"] is True
    assert payload["decision_features_excluded"] is True
    assert payload["failed_required_checks"] == []
    assert payload["lifecycle"]["ready"] is True
    assert payload["exposure"]["ready"] is True
    assert payload["problem_review"] is None


def test_postrun_readiness_ports_keep_problem_review_problem_owned() -> None:
    inventory = {
        "problem_family": "fixture_problem",
        "lifecycle": {
            "wrapper_exit_status": 0,
            "postrun_acceptance_status": "ready",
        },
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
        },
    }
    registry = ProblemReviewRegistry(
        {
            "fixture_problem": _FixtureProblemReviewPort(
                ready=False,
                failed_required_checks=("fixture_problem_review_not_ready",),
            )
        }
    )

    summary = PostrunReadinessOrchestrator(
        MappingPostrunInventoryPort(inventory),
        problem_reviews=registry,
    ).build("/tmp/run-root")
    payload = summary.to_payload()

    assert payload["current_run_analysis_ready"] is False
    assert payload["delegation_ready"] is False
    assert payload["failed_required_checks"] == [
        "fixture_problem_review_not_ready"
    ]
    assert payload["problem_review"]["problem_family"] == "fixture_problem"
    assert payload["problem_review"]["proposal_visibility_only"] is True
    assert payload["problem_review"]["decision_features_excluded"] is True


def test_postrun_readiness_ports_fail_closed_on_generic_lifecycle() -> None:
    inventory = {
        "lifecycle": {
            "wrapper_exit_status": 64,
            "postrun_acceptance_status": "ready",
        },
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
        },
    }

    payload = PostrunReadinessOrchestrator(
        MappingPostrunInventoryPort(inventory),
    ).build("/tmp/run-root").to_payload()

    assert payload["current_run_analysis_ready"] is False
    assert payload["lifecycle"]["failed_required_checks"] == [
        "wrapper_exit_status_nonzero"
    ]
    assert payload["failed_required_checks"] == ["wrapper_exit_status_nonzero"]


@dataclass(frozen=True)
class _FixtureProblemReviewPort:
    ready: bool
    failed_required_checks: tuple[str, ...] = ()
    problem_family: str = "fixture_problem"

    def review(self, inventory: dict[str, object]) -> ProblemReviewSummary:
        return ProblemReviewSummary(
            problem_family=self.problem_family,
            review_key="fixture_review",
            status="ready" if self.ready else "not_ready",
            interpretation="fixture_interpretation",
            ready=self.ready,
            failed_required_checks=self.failed_required_checks,
        )
