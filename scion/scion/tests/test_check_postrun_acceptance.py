from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL_PATH = SCION_DIR / "tools" / "check_postrun_acceptance.py"
SPEC = importlib.util.spec_from_file_location("check_postrun_acceptance", TOOL_PATH)
assert SPEC is not None
check_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_tool)


@pytest.mark.parametrize("problem_family", ("cvrp", "warehouse_delivery"))
def test_problem_owned_summaries_are_report_only(problem_family: str) -> None:
    brief = {
        "prepared_run_contract": {"problem_family": problem_family},
        "cvrp_large_twoopt_summary": {
            "available": False,
            "interpretation": "historical_mechanism_summary",
        },
        "warehouse_followup_summary": {
            "available": False,
            "interpretation": "historical_checkpoint_summary",
        },
    }
    inventory = {
        "launcher": {
            "prepared_run_contract": {"problem_family": problem_family},
        }
    }

    status, detail = check_tool._problem_summary_actionability(brief, inventory)
    input_status, input_detail = (
        check_tool._review_input_summaries_actionability(Path("/tmp/run"), brief, inventory)
    )
    consistency_status, consistency_detail = (
        check_tool._problem_summary_input_consistency(brief, inventory)
    )

    assert status == "skipped"
    assert detail["reason"] == "problem_owned_summaries_are_report_only"
    assert input_status == "skipped"
    assert input_detail["reason"] == "problem_owned_review_inputs_are_report_only"
    assert consistency_status == "skipped"
    assert consistency_detail["reason"] == (
        "problem_owned_summary_consistency_is_report_only"
    )


@pytest.mark.parametrize("problem_family", ("cvrp", "warehouse_delivery"))
def test_typed_readiness_uses_only_generic_run_evidence(
    tmp_path: Path,
    problem_family: str,
) -> None:
    inventory = _ready_inventory(problem_family)

    payload = check_tool._typed_postrun_readiness_payload(
        tmp_path,
        inventory,
        analysis_brief={
            "raw_prompt_excluded": True,
            "raw_response_excluded": True,
            "patch_body_excluded": True,
        },
    )

    assert payload["current_run_analysis_ready"] is True
    assert payload["delegation_ready"] is True
    assert payload["failed_required_checks"] == []
    assert payload["lifecycle"]["current_run_evidence"] is True
    if problem_family == "cvrp":
        assert payload["problem_review"] is None
        return
    assert payload["problem_review"]["ready"] is True
    assert payload["problem_review"]["status"] == "not_reported"
    assert payload["problem_review"]["detail"]["readiness_input"] is False


def test_typed_readiness_still_rejects_missing_evaluated_outcome(
    tmp_path: Path,
) -> None:
    inventory = _ready_inventory("cvrp")
    inventory["execution_outcomes"] = {
        "evaluated_count": 0,
        "non_evaluated_count": 1,
        "execution_outcome_counts": {"rejected_response": 1},
        "research_conclusion_eligibility": {"eligible": False},
    }

    payload = check_tool._typed_postrun_readiness_payload(tmp_path, inventory)

    assert payload["current_run_analysis_ready"] is False
    assert "no_evaluated_execution_outcome" in payload["failed_required_checks"]


def test_typed_readiness_still_rejects_infra_only_run(tmp_path: Path) -> None:
    inventory = _ready_inventory("warehouse_delivery")
    inventory["execution_outcomes"] = {
        "evaluated_count": 0,
        "non_evaluated_count": 1,
        "execution_outcome_counts": {"blocked_infra": 1},
        "research_conclusion_eligibility": {"eligible": False},
    }

    payload = check_tool._typed_postrun_readiness_payload(tmp_path, inventory)

    assert payload["current_run_analysis_ready"] is False
    assert "invalid_infra_only" in payload["failed_required_checks"]
    assert "no_evaluated_execution_outcome" in payload["failed_required_checks"]


def test_failed_check_names_separates_required_from_report_only() -> None:
    checks = {
        "generic_failure": {"required": True, "status": "failed"},
        "problem_fact": {"required": False, "status": "failed"},
        "generic_ok": {"required": True, "status": "ok"},
    }

    assert check_tool._failed_check_names(checks, required=True) == [
        "generic_failure"
    ]
    assert check_tool._failed_check_names(checks, required=False) == [
        "problem_fact"
    ]


def _ready_inventory(problem_family: str) -> dict[str, object]:
    return {
        "problem_family": problem_family,
        "lifecycle": {
            "wrapper_exit_status": 0,
            "postrun_acceptance_status": "ok",
            "current_run_evidence": True,
        },
        "validity": {
            "invalid_infra_only": False,
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
        },
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
        },
        "proposal_runtime": {
            "status": "resolved",
            "resolved_mode": "direct_v3",
        },
        "execution_outcomes": {
            "evaluated_count": 1,
            "non_evaluated_count": 0,
            "execution_outcome_counts": {"evaluated": 1},
            "research_conclusion_eligibility": {"eligible": True},
        },
        "launcher": {
            "status_fields": {
                "wrapper_exit_status": 0,
                "postrun_acceptance_status": "ok",
            },
            "prepared_run_contract": {"problem_family": problem_family},
        },
        "prompt_context_visibility_summary": {
            "raw_prompt_excluded": True,
            "raw_response_excluded": True,
            "patch_body_excluded": True,
        },
    }
