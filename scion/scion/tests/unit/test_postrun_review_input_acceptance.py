from __future__ import annotations

from copy import deepcopy

from scion.postrun import PostrunReviewInputAcceptancePort


def test_review_input_acceptance_emits_legacy_ready_payload() -> None:
    analysis_brief, expected_summaries = _ready_inputs()

    check = PostrunReviewInputAcceptancePort().summarize(
        problem_family="cvrp",
        interpretation="protocol_evaluated_without_large_twoopt_signal",
        analysis_brief=analysis_brief,
        expected_summaries=expected_summaries,
        required_summary_keys=PostrunReviewInputAcceptancePort.summary_keys(),
    ).checks[0]

    assert check.name == "review_input_summaries_actionability"
    assert check.status == "ok"
    assert check.required is True
    assert check.detail["problem_family"] == "cvrp"
    assert len(check.detail["summaries"]) == 4
    assert all(not item["failures"] for item in check.detail["summaries"])


def test_review_input_acceptance_rejects_required_and_present_optional_drift() -> None:
    analysis_brief, expected_summaries = _ready_inputs()
    analysis_brief["protocol_accounting_summary"]["schema_version"] = "stale"
    analysis_brief["runtime_feedback_summary"]["schema_version"] = "stale"
    analysis_brief["runtime_feedback_summary"]["aggregate"] = {"rows": 99}

    check = PostrunReviewInputAcceptancePort().summarize(
        problem_family="warehouse_delivery",
        interpretation="quality_blocked_no_protocol_plateau_conclusion",
        analysis_brief=analysis_brief,
        expected_summaries=expected_summaries,
        required_summary_keys={"protocol_accounting_summary"},
    ).checks[0]

    by_key = {item["summary"]: item for item in check.detail["summaries"]}

    assert check.status == "failed"
    assert by_key["protocol_accounting_summary"]["required_for_interpretation"]
    assert by_key["protocol_accounting_summary"]["failures"] == [
        "protocol_accounting_summary_schema_stale"
    ]
    assert by_key["runtime_feedback_summary"]["required_for_interpretation"] is False
    assert by_key["runtime_feedback_summary"]["failures"] == [
        "runtime_feedback_summary_schema_stale",
        "runtime_feedback_summary_aggregate_mismatch",
    ]


def test_review_input_acceptance_can_emit_skipped_payload() -> None:
    check = PostrunReviewInputAcceptancePort().summarize(
        problem_family="unknown",
        interpretation="",
        analysis_brief={},
        expected_summaries={},
        required_summary_keys=set(),
        enabled=False,
    ).checks[0]

    assert check.name == "review_input_summaries_actionability"
    assert check.status == "skipped"
    assert check.required is False
    assert check.detail == {
        "reason": "not_problem_specific_agentic_summary",
        "problem_family": "unknown",
    }


def _ready_inputs() -> tuple[dict[str, object], dict[str, object]]:
    summaries = {
        "protocol_accounting_summary": _summary(
            "scion.postrun_protocol_accounting_summary.v1",
            "accounting_report_count",
        ),
        "measurement_effect_summary": _summary(
            "scion.postrun_measurement_effect_summary.v1",
            "effect_report_count",
        ),
        "runtime_feedback_summary": {
            **_summary(
                "scion.postrun_runtime_feedback_summary.v1",
                "runtime_report_count",
            ),
            "drain_status_complete": True,
            "review_ready": True,
            "budget_diagnostic_source_count": 1,
            "runtime_budget_diagnostics": {"diagnostic_count": 1},
        },
        "research_continuity_summary": _summary(
            "scion.postrun_research_continuity_summary.v1",
            "continuity_report_count",
        ),
    }
    return deepcopy(summaries), deepcopy(summaries)


def _summary(schema: str, count_field: str) -> dict[str, object]:
    return {
        "schema_version": schema,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        count_field: 1,
        "aggregate": {"rows": 1},
        "entries": [
            {
                "path": "/tmp/scion/run/postrun_acceptance/report.json",
                "status": "ok",
            }
        ],
    }
