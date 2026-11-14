"""Tests for ordinary experiment and champion storage."""

from __future__ import annotations

import uuid
from datetime import datetime

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.lineage.registry import LineageRegistry

# ---------------------------------------------------------------------------
# LineageRegistry
# ---------------------------------------------------------------------------


class TestLineageRegistry:
    def test_record_and_query_by_branch(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = str(uuid.uuid4())
        reg.record_event(
            {
                "event_id": str(uuid.uuid4()),
                "branch_id": bid,
                "timestamp": datetime.now().isoformat(),
                "contract_result": "passed",
                "verification_result": "passed",
            }
        )
        rows = reg.query_by_branch(bid)
        assert len(rows) == 1
        assert rows[0]["branch_id"] == bid

    def test_record_event_auto_event_id(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_auto"
        eid = reg.record_event({"branch_id": bid, "timestamp": "t1"})
        assert eid is not None
        rows = reg.query_by_branch(bid)
        assert len(rows) == 1

    def test_record_event_append_only(self, tmp_path):
        """Multiple record_event calls create multiple rows, not overwrite."""
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        bid = "br_append"
        reg.record_event({"branch_id": bid, "timestamp": "t1"})
        reg.record_event({"branch_id": bid, "timestamp": "t2"})
        rows = reg.query_by_branch(bid)
        assert len(rows) == 2

    def test_get_campaign_summary_empty(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 0
        assert summary["n_branches"] == 0

    def test_get_campaign_summary_counts(self, tmp_path):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        for i in range(3):
            reg.record_event(
                {
                    "branch_id": f"br_{i}",
                    "timestamp": f"t{i}",
                    "decision": "abandon" if i < 2 else "promote",
                    "contract_result": "failed" if i == 0 else "passed",
                }
            )
        reg.record_execution_outcome(
            campaign_id="campaign-1",
            branch_id="br_0",
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_CONTRACT_REJECTED",
                detail="contract rejected",
                provenance={"stage": "hypothesis_contract"},
            ),
            event_kind="contract_fail",
            stage="hypothesis_contract",
        )
        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 3
        assert summary["n_branches"] == 3
        assert summary["by_decision"]["abandon"] == 2
        assert summary["by_decision"]["promote"] == 1
        assert summary["contract_failures"] == 1

    def test_typed_verification_failure_is_in_failure_queries_and_summary(
        self,
        tmp_path,
    ):
        reg = LineageRegistry(str(tmp_path / "scion.db"))
        reg.record_execution_outcome(
            campaign_id="campaign-1",
            branch_id="branch-1",
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="VERIFICATION_LIGHT_REJECTED",
                detail="verification rejected",
                provenance={
                    "stage": "verification",
                    "verification_checks": [
                        {"name": "V1_syntax", "passed": True},
                        {"name": "V1b_undefined_names", "passed": False},
                    ],
                },
            ),
            event_kind="verification_fail",
            stage="verification",
        )

        failures = reg.query_failures()
        assert len(failures) == 1
        assert failures[0]["event_kind"] == "verification_fail"
        assert failures[0]["reason_code"] == "VERIFICATION_LIGHT_REJECTED"
        assert failures[0]["detail"] == "verification rejected"
        assert failures[0]["provenance"]["verification_checks"][1]["name"] == (
            "V1b_undefined_names"
        )
        assert reg.query_failures(category="verification_fail") == failures
        assert reg.query_failures(category="VERIFICATION_LIGHT_REJECTED") == failures

        summary = reg.get_campaign_summary()
        assert summary["total_events"] == 0
        assert summary["gate_outcome_events"] == 1
        assert summary["contract_gate_outcome_events"] == 1
        assert summary["verification_gate_outcome_events"] == 1
        assert summary["verification_failures"] == 1

    def test_persistence_across_instances(self, tmp_path):
        db_path = str(tmp_path / "scion.db")
        r1 = LineageRegistry(db_path)
        r1.record_event({"branch_id": "b1", "timestamp": "t0"})
        r2 = LineageRegistry(db_path)
        rows = r2.query_by_branch("b1")
        assert len(rows) == 1
