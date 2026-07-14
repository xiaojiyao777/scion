from __future__ import annotations

import importlib.util
from pathlib import Path
import json
import sqlite3

import pytest

from scion.core.execution_outcome import (
    ExecutionOutcome,
    execution_outcome_evidence,
    execution_outcome_evidence_from_counts,
)
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_INTERRUPTED_ONLY,
    RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY,
    RUN_VALIDITY_UNKNOWN_HISTORICAL,
    build_run_validity,
)
from scion.postrun.acceptance_checks import _execution_outcome_integrity
from scion.postrun.inventory.loader import _execution_outcomes_inventory
from scion.postrun.inventory.database import _events
from scion.postrun.readiness import (
    MappingPostrunInventoryPort,
    PostrunReadinessOrchestrator,
)

TOOL_PATH = Path(__file__).parents[3] / "tools" / "postrun_analysis_brief.py"
SPEC = importlib.util.spec_from_file_location("outcome_postrun_analysis_brief", TOOL_PATH)
assert SPEC is not None
brief_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(brief_tool)


def _all_outcome_counts(**overrides: int) -> dict[str, int]:
    counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    counts.update(overrides)
    return counts


def _readiness_inventory(outcomes: dict[str, object]) -> dict[str, object]:
    return {
        "proposal_runtime": {"status": "resolved", "resolved_mode": "direct_v3"},
        "lifecycle": {"wrapper_exit_status": 0, "postrun_acceptance_status": "ready"},
        "validity": {"run_validity_status": "valid"},
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
        },
        "execution_outcomes": outcomes,
    }


def test_six_state_projection_is_lossless_and_safe() -> None:
    rows = [
        {
            "outcome": outcome.value,
            "reason_code": f"REASON_{index}",
            "provenance": {
                "stage": "evaluation",
                "artifact_ref": f"artifact-{index}",
                "raw_prompt": "must-not-leak",
            },
        }
        for index, outcome in enumerate(ExecutionOutcome)
    ]

    evidence = execution_outcome_evidence(rows)

    assert evidence["execution_outcome_counts"] == _all_outcome_counts(
        evaluated=1,
        research_rejected=1,
        not_evaluated=1,
        blocked_infra=1,
        resource_exhausted=1,
        interrupted=1,
    )
    assert evidence["evaluated_count"] == 1
    assert evidence["non_evaluated_count"] == 5
    assert evidence["research_conclusion_eligibility"]["status"] == "partial_evaluated"
    assert evidence["last_execution_outcome"] == {
        "outcome": "interrupted",
        "reason_code": "REASON_5",
        "provenance_refs": {
            "stage": "evaluation",
            "artifact_ref": "artifact-5",
        },
    }


def test_partial_evaluated_plus_blocked_remains_eligible_with_exclusion() -> None:
    counts = _all_outcome_counts(evaluated=2, blocked_infra=1)
    validity = build_run_validity(
        requested_rounds=3,
        effective_rounds_completed=2,
        n_experiments=2,
        execution_outcome_counts=counts,
        stopped_reason="provider error text must not reclassify typed outcomes",
    )

    assert validity["valid"] is True
    assert validity["research_conclusion_eligibility"] == {
        "status": "partial_evaluated",
        "eligible": True,
        "algorithm_conclusions_allowed": True,
        "partial": True,
        "excluded_outcome_counts": {"blocked_infra": 1},
        "unknown_excluded_count": 0,
    }


@pytest.mark.parametrize(
    ("outcome", "expected_reason"),
    [
        ("resource_exhausted", RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY),
        ("interrupted", RUN_VALIDITY_INVALID_INTERRUPTED_ONLY),
    ],
)
def test_zero_evaluated_preserves_non_evaluated_taxonomy(
    outcome: str,
    expected_reason: str,
) -> None:
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=0,
        n_experiments=0,
        proposal_attempts=1,
        failure_categories={"infra": 99},
        stopped_reason="HTTP 503 provider error",
        execution_outcome_counts=_all_outcome_counts(**{outcome: 1}),
    )

    assert validity["reason"] == expected_reason
    assert validity["research_conclusion_eligibility"][
        "algorithm_conclusions_allowed"
    ] is False


def test_historical_missing_outcome_stays_unknown_not_negative() -> None:
    evidence = execution_outcome_evidence([{"decision": "rollback"}])
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=0,
        n_experiments=0,
        execution_outcome_counts=evidence["execution_outcome_counts"],
        unknown_outcome_count=evidence["unknown_outcome_count"],
        stopped_reason="provider error",
    )

    assert evidence["research_conclusion_eligibility"]["eligible"] is None
    assert validity["reason"] == RUN_VALIDITY_UNKNOWN_HISTORICAL
    assert validity["valid"] is None


def test_inventory_detects_non_evaluated_decision_protocol_and_count_drift() -> None:
    summary = {
        "execution_outcome_counts": _all_outcome_counts(not_evaluated=2),
        "unknown_outcome_count": 0,
        "steps": [
            {
                "round": 1,
                "branch_id": "branch-1",
                "execution_outcome": "not_evaluated",
                "decision": "rollback",
                "decision_reason_codes": ["NEGATIVE"],
                "protocol_result": {"tier": "regression"},
                "screened_experiment": True,
            }
        ],
    }

    outcomes = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary=summary,
        events={},
    )

    assert outcomes["summary_step_counts_consistent"] is False
    assert outcomes["step_invariants"]["status"] == "invalid"
    assert {item["code"] for item in outcomes["step_invariants"]["violations"]} == {
        "non_evaluated_has_decision",
        "non_evaluated_has_decision_reason_codes",
        "non_evaluated_has_protocol_result",
        "non_evaluated_is_screened",
    }


def test_readiness_allows_partial_evaluated_but_blocks_zero_evaluated() -> None:
    partial = execution_outcome_evidence_from_counts(
        _all_outcome_counts(evaluated=1, blocked_infra=1)
    )
    zero = execution_outcome_evidence_from_counts(
        _all_outcome_counts(resource_exhausted=1)
    )

    partial_payload = PostrunReadinessOrchestrator(
        MappingPostrunInventoryPort(_readiness_inventory(partial))
    ).build(Path("/tmp/partial")).to_payload()
    zero_payload = PostrunReadinessOrchestrator(
        MappingPostrunInventoryPort(_readiness_inventory(zero))
    ).build(Path("/tmp/zero")).to_payload()

    assert partial_payload["current_run_analysis_ready"] is True
    assert zero_payload["current_run_analysis_ready"] is False
    assert "no_evaluated_execution_outcome" in zero_payload["failed_required_checks"]


def test_acceptance_fail_closes_non_evaluated_step_but_not_historical_unknown() -> None:
    bad = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={
            "execution_outcome_counts": _all_outcome_counts(not_evaluated=1),
            "steps": [
                {
                    "execution_outcome": "not_evaluated",
                    "decision": "abandon",
                }
            ],
        },
        events={},
    )
    historical = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={"steps": [{"decision": "abandon"}]},
        events={},
    )

    bad_status, bad_detail = _execution_outcome_integrity(
        {"execution_outcomes": bad}, {"execution_outcomes": bad}
    )
    historical_status, historical_detail = _execution_outcome_integrity(
        {"execution_outcomes": historical}, {"execution_outcomes": historical}
    )

    assert bad_status == "failed"
    assert "step_outcome_invariants_invalid" in bad_detail["failures"]
    assert historical_status == "ok"
    assert historical_detail["research_conclusion_eligibility"]["eligible"] is None


def test_lineage_decision_rows_require_correlated_evaluated_outcome() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.executemany(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("camp", "b1", "h1", "execution_outcome", "screening", None, "evaluated"),
            ("camp", "b1", "h1", "decision", "screening", "keep", None),
            (
                "camp",
                "b2",
                "h2",
                "execution_outcome",
                "screening",
                None,
                "resource_exhausted",
            ),
            ("camp", "b2", "h2", "decision", "screening", "rollback", None),
        ],
    )

    events = _events(conn)

    assert events["decision_rows_with_non_evaluated_outcome"] == 1
    assert events["decision_outcome_consistency_status"] == "invalid"


def test_historical_lineage_decisions_without_outcome_are_unknown() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.execute(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("camp", "b1", "h1", "decision", "screening", "rollback", None),
    )

    events = _events(conn)

    assert events["explicit_execution_outcome_count"] == 0
    assert events["decision_outcome_consistency_status"] == "unknown_historical"


def test_identityless_decision_projection_is_diagnostic_not_false_negative() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.executemany(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("camp", "b1", "h1", "execution_outcome", "screening", None, "evaluated"),
            ("camp", "b1", "h1", "experiment", "screening", "keep", None),
            (None, "b1", None, "decision", None, "keep", None),
        ],
    )

    events = _events(conn)

    assert events["decision_rows_with_non_evaluated_outcome"] == 0
    assert events["decision_rows_without_correlation_identity"] == 1
    assert events["decision_outcome_consistency_status"] == "consistent"


def test_identityless_explicit_non_evaluated_decision_fails_closed() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.execute(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        (None, "b1", None, "decision", None, "rollback", "resource_exhausted"),
    )

    events = _events(conn)

    assert events["decision_rows_with_non_evaluated_outcome"] == 1
    assert events["decision_rows_without_correlation_identity"] == 0
    assert events["decision_outcome_consistency_status"] == "invalid"


def test_resumed_lineage_comparison_uses_current_campaign_scope() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.executemany(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("old", "b1", "h1", "outcome", "screening", None, "evaluated"),
            ("old", "b1", "h2", "outcome", "screening", None, "evaluated"),
            (
                "current",
                "b1",
                "h2",
                "outcome",
                "screening",
                None,
                "evaluated",
            ),
            ("current", "b1", "h2", "decision", "screening", "keep", None),
        ],
    )

    cumulative_events = _events(conn)
    current_events = _events(
        conn,
        campaign_id="current",
        require_campaign_scope=True,
    )
    outcomes = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={
            "campaign_id": "current",
            "execution_outcome_counts": _all_outcome_counts(evaluated=1),
            "steps": [
                {
                    "branch_id": "b1",
                    "execution_outcome": "evaluated",
                    "decision": "keep",
                }
            ],
        },
        events=current_events,
    )
    status, detail = _execution_outcome_integrity(
        {"execution_outcomes": outcomes},
        {"execution_outcomes": outcomes},
    )

    assert cumulative_events["by_execution_outcome"] == {"evaluated": 3}
    assert current_events["scope_status"] == "campaign"
    assert current_events["campaign_id"] == "current"
    assert current_events["by_execution_outcome"] == {"evaluated": 1}
    assert outcomes["summary_lineage_counts_comparable"] is True
    assert outcomes["summary_lineage_counts_consistent"] is True
    assert status == "ok"
    assert detail["failures"] == []


def test_current_campaign_scope_with_missing_lineage_outcome_fails_closed() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.execute(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("old", "b1", "h1", "outcome", "screening", None, "evaluated"),
    )
    current_events = _events(
        conn,
        campaign_id="current",
        require_campaign_scope=True,
    )
    outcomes = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={
            "campaign_id": "current",
            "execution_outcome_counts": _all_outcome_counts(evaluated=1),
            "steps": [{"execution_outcome": "evaluated"}],
        },
        events=current_events,
    )
    status, detail = _execution_outcome_integrity(
        {"execution_outcomes": outcomes},
        {"execution_outcomes": outcomes},
    )

    assert current_events["scope_status"] == "campaign"
    assert current_events["explicit_execution_outcome_count"] == 0
    assert outcomes["summary_lineage_counts_comparable"] is True
    assert outcomes["summary_lineage_counts_consistent"] is False
    assert status == "failed"
    assert "summary_lineage_outcome_counts_mismatch" in detail["failures"]


def test_explicit_zero_summary_counts_do_not_hide_scoped_lineage_outcome() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.execute(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "current",
            "b1",
            "h1",
            "outcome",
            "screening",
            None,
            "resource_exhausted",
        ),
    )
    current_events = _events(
        conn,
        campaign_id="current",
        require_campaign_scope=True,
    )
    outcomes = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={
            "campaign_id": "current",
            "execution_outcome_counts": _all_outcome_counts(),
        },
        events=current_events,
    )
    status, detail = _execution_outcome_integrity(
        {"execution_outcomes": outcomes},
        {"execution_outcomes": outcomes},
    )

    assert outcomes["summary_outcome_projection_explicit"] is True
    assert outcomes["summary_lineage_counts_comparable"] is True
    assert outcomes["summary_lineage_counts_consistent"] is False
    assert status == "failed"
    assert "summary_lineage_outcome_counts_mismatch" in detail["failures"]


def test_scoped_decision_without_outcome_cannot_borrow_old_campaign_outcome() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiment_events ("
        "campaign_id TEXT, branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    conn.executemany(
        "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("old", "b1", "h1", "outcome", "screening", None, "evaluated"),
            ("current", "b1", "h1", "decision", "screening", "keep", None),
        ],
    )

    current_events = _events(
        conn,
        campaign_id="current",
        require_campaign_scope=True,
    )

    assert current_events["explicit_execution_outcome_count"] == 0
    assert current_events["decision_row_count"] == 1
    assert current_events["decision_rows_with_non_evaluated_outcome"] == 1
    assert current_events["decision_outcome_consistency_status"] == "invalid"


@pytest.mark.parametrize("include_campaign_column", [True, False])
def test_lineage_comparison_is_incomparable_without_campaign_identity(
    include_campaign_column: bool,
) -> None:
    conn = sqlite3.connect(":memory:")
    campaign_column = "campaign_id TEXT, " if include_campaign_column else ""
    conn.execute(
        "CREATE TABLE experiment_events ("
        f"{campaign_column}branch_id TEXT, hypothesis_id TEXT, "
        "event_kind TEXT, stage TEXT, decision TEXT, execution_outcome TEXT)"
    )
    current_events = _events(
        conn,
        campaign_id=None if include_campaign_column else "current",
        require_campaign_scope=True,
    )
    outcomes = _execution_outcomes_inventory(
        campaign_run_status={},
        campaign_status={},
        summary={
            "execution_outcome_counts": _all_outcome_counts(evaluated=1),
            "steps": [{"execution_outcome": "evaluated"}],
        },
        events=current_events,
    )

    assert current_events["scope_status"] == "identity_unavailable"
    assert current_events["explicit_execution_outcome_count"] == 0
    assert outcomes["summary_lineage_counts_comparable"] is False
    assert outcomes["summary_lineage_counts_consistent"] is None


def test_analysis_effect_and_protocol_summaries_require_evaluated_outcome(
    tmp_path: Path,
) -> None:
    report_dir = tmp_path / "postrun_acceptance" / "research_efficiency"
    report_dir.mkdir(parents=True)
    (report_dir / "run.research_efficiency.v1.json").write_text(
        json.dumps(
            {
                "protocol_rows": {
                    "protocol_metric_results": 1,
                    "protocol_evaluated_candidates": 1,
                },
                "protocol_effects_vs_mde": {
                    "protocol_row_count": 1,
                    "positive_rows": 1,
                    "nonpositive_rows": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    base_inventory = {
        "phase4_evidence_coverage": {"current_run_evidence": True},
        "postrun_reports": {},
    }
    zero_inventory = {
        **base_inventory,
        "execution_outcomes": execution_outcome_evidence_from_counts(
            _all_outcome_counts(resource_exhausted=1)
        ),
    }
    evaluated_inventory = {
        **base_inventory,
        "execution_outcomes": execution_outcome_evidence_from_counts(
            _all_outcome_counts(evaluated=1)
        ),
    }

    zero_effect = brief_tool._measurement_effect_summary(tmp_path, zero_inventory)
    zero_protocol = brief_tool._protocol_accounting_summary(tmp_path, zero_inventory)
    evaluated_effect = brief_tool._measurement_effect_summary(
        tmp_path, evaluated_inventory
    )
    evaluated_protocol = brief_tool._protocol_accounting_summary(
        tmp_path, evaluated_inventory
    )

    assert zero_effect["available"] is False
    assert zero_effect["excluded_reason"] == "no_evaluated_execution_outcome"
    assert zero_protocol["available"] is False
    assert evaluated_effect["aggregate"]["positive_rows"] == 1
    assert evaluated_protocol["aggregate"]["protocol_rows"][
        "protocol_evaluated_candidates"
    ] == 1
