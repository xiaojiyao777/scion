"""Focused tests split from test_evidence_recorder.py."""

from dataclasses import replace

import pytest

from .evidence_recorder_test_support import *  # noqa: F401,F403


class _FaultyLineageRegistry:
    def __init__(self, *, fail_event: bool = False) -> None:
        self.fail_event = fail_event
        self.events = []

    def record_event(self, event):
        if self.fail_event:
            raise RuntimeError("lineage event write unavailable")
        self.events.append(dict(event))
        return "event-1"


def test_public_summary_and_status_redact_nested_diagnostics_and_branches(
    tmp_path: Path,
) -> None:
    branch_workspace = tmp_path / "workspaces" / "branch-1"
    branch_trace = tmp_path / "traces" / "branch-1.json"
    diagnostic_log = tmp_path / "diagnostics" / "branch-1.log"
    branch_summary = f"retry workspace {branch_workspace} before promotion"
    trace_note = f"trace captured at {branch_trace}, retryable"
    diagnostic_message = (
        f"runtime log stored at {diagnostic_log}; workspace={branch_workspace}"
    )
    colon_note = f"log:{diagnostic_log}; workspace:{branch_workspace}"
    local_uri_note = (
        f"log uri file://{diagnostic_log.as_posix()}, "
        f"workspace file://localhost{branch_workspace.as_posix()}"
    )
    trace_uri_note = f"trace uri file://{branch_trace.as_posix()}"
    branch_colon_summary = f"retry workspace:{branch_workspace} before promotion"
    external_note = "external diagnostic copied from /var/tmp/scion-internal.log"
    assert contains_absolute_path(trace_note)
    assert contains_absolute_path(diagnostic_message)
    assert contains_absolute_path(colon_note)
    assert contains_absolute_path(local_uri_note)
    assert contains_absolute_path(trace_uri_note)
    assert contains_absolute_path(branch_colon_summary)
    assert contains_absolute_path(external_note)
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    state = {
        **_operator_state(n_steps=1),
        "n_active_branches": 1,
        "branches": [
            {
                "branch_id": "branch-1",
                "workspace_path": str(branch_workspace),
                "branch_summary": branch_summary,
                "branch_colon_summary": branch_colon_summary,
                "diagnostics": {
                    "trace_path": str(branch_trace),
                    "trace_note": trace_note,
                    "trace_uri_note": trace_uri_note,
                },
            }
        ],
    }

    summary = recorder.write_campaign_summary(
        state=state,
        run_result=_run_projection(),
        step_history=[_step()],
        diagnostics=[
            {
                "kind": "runtime",
                "payload": {
                    "log_path": str(diagnostic_log),
                    "message": diagnostic_message,
                    "colon_note": colon_note,
                    "local_uri_note": local_uri_note,
                    "external_note": external_note,
                    "raw_metrics_ref": f"metrics captured in {diagnostic_log}",
                    "branches": [
                        {
                            "workspace": str(branch_workspace),
                            "note": f"branch workspace:{branch_workspace}",
                        }
                    ],
                },
            }
        ],
    )
    status = recorder.write_status(state=state, run_result=_run_projection())

    assert not contains_absolute_path(summary)
    assert not contains_absolute_path(status)
    assert not contains_absolute_path(
        json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    )
    assert summary["diagnostics"][0]["payload"]["log_path"] == (
        "diagnostics/branch-1.log"
    )
    assert summary["diagnostics"][0]["payload"]["message"] == (
        "runtime log stored at diagnostics/branch-1.log; "
        "workspace=workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["colon_note"] == (
        "log:diagnostics/branch-1.log; workspace:workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["local_uri_note"] == (
        "log uri diagnostics/branch-1.log, workspace workspaces/branch-1"
    )
    assert summary["diagnostics"][0]["payload"]["external_note"].startswith(
        "external diagnostic copied from artifact:scion-internal.log"
    )
    assert summary["diagnostics"][0]["payload"]["raw_metrics_ref"] == (
        "metrics captured in diagnostics/branch-1.log"
    )
    assert summary["diagnostics"][0]["payload"]["branches"][0]["note"] == (
        "branch workspace:workspaces/branch-1"
    )
    assert summary["branches"][0]["workspace_path"] == "workspaces/branch-1"
    assert summary["branches"][0]["branch_summary"] == (
        "retry workspace workspaces/branch-1 before promotion"
    )
    assert summary["branches"][0]["branch_colon_summary"] == (
        "retry workspace:workspaces/branch-1 before promotion"
    )
    assert status["branches"][0]["diagnostics"]["trace_path"] == "traces/branch-1.json"
    assert status["branches"][0]["diagnostics"]["trace_note"] == (
        "trace captured at traces/branch-1.json, retryable"
    )
    assert status["branches"][0]["diagnostics"]["trace_uri_note"] == (
        "trace uri traces/branch-1.json"
    )
    assert summary["steps"][0]["base_champion_version"] == 6
    assert summary["steps"][0]["base_source_ref"] == (
        "branch:branch-1:accepted-head:1"
    )
    assert summary["steps"][0]["changed_files"] == [
        "operators/local_search.py"
    ]


def test_promotion_lineage_payload_is_one_plain_experiment_event(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    branch = _branch()
    branch.current_code_hash = "accepted-old-head"
    event = recorder.build_step_lineage_event(
        branch=branch,
        code_hash="candidate-hash",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(
            passed=True,
            checks=(CheckResult("contract", True, "light", "ok", 1),),
        ),
        verification_result=VerificationResult(
            passed=True,
            checks=(CheckResult("syntax", True, "light", "ok", 1),),
        ),
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result("/tmp/promotion-metrics.json"),
        decision=Decision.PROMOTE,
        champion=_champion(version=8),
        decision_reason_codes=("frozen_positive", "runtime_ok"),
        base_champion_version=6,
        base_source_ref="branch:branch-1:accepted-head:1",
        changed_files=("operators/local_search.py",),
    )

    assert event["branch_id"] == "branch-1"
    assert event["code_hash"] == "candidate-hash"
    assert event["decision"] == "promote"
    assert not event["raw_metrics_ref"].startswith("/")
    assert "promotion-metrics.json" in event["raw_metrics_ref"]
    assert json.loads(event["decision_reason"]) == [
        "frozen_positive",
        "runtime_ok",
        "screening_positive",
    ]
    assert "audit_payload_json" not in event


def test_lineage_event_keeps_research_facts_without_replay_identity_mirror(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        protocol_version="protocol-v3",
    )
    protocol_result = replace(
        _protocol_result(str(tmp_path / "metrics" / "formal.json")),
        selected_surface="local_search",
    )

    event = recorder.build_step_lineage_event(
        branch=_branch(),
        code_hash="candidate-hash",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=protocol_result,
        decision=Decision.PROMOTE,
        champion=_champion(),
        base_champion_version=6,
        base_source_ref="branch:branch-1:accepted-head:2",
        changed_files=(
            "operators/local_search.py",
            "operators/new_move.py",
        ),
    )
    assert event["campaign_id"] == "camp-1"
    assert event["branch_id"] == "branch-1"
    assert event["code_hash"] == "candidate-hash"
    assert event["stage"] == "screening"
    assert json.loads(event["case_ids"]) == ["case-1", "case-2"]
    assert json.loads(event["seed_set"]) == [11, 13]
    assert event["raw_metrics_ref"] == "metrics/formal.json"
    assert event["protocol_version"] == "protocol-v3"
    assert event["decision"] == "promote"
    assert event["base_champion_version"] == 6
    assert event["base_source_ref"] == "branch:branch-1:accepted-head:2"
    assert json.loads(event["changed_files_json"]) == [
        "operators/local_search.py",
        "operators/new_move.py",
    ]
    assert "audit_payload_json" not in event


def test_lineage_event_without_protocol_has_no_missing_identity_state(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    event = recorder.build_step_lineage_event(
        branch=_branch(),
        code_hash="candidate-hash",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=None,
        decision=Decision.ABANDON,
        champion=_champion(),
        base_champion_version=6,
        base_source_ref="champion:v6",
        changed_files=("operators/local_search.py",),
    )

    assert event["code_hash"] == "candidate-hash"
    assert event["stage"] == "canary"
    assert event["execution_outcome"] == "evaluated"
    assert event["execution_outcome_reason_code"] == "EVALUATION_COMPLETED"
    assert json.loads(event["execution_outcome_provenance_json"]) == {
        "stage": "canary"
    }
    assert json.loads(event["case_ids"]) == []
    assert json.loads(event["seed_set"]) == []
    assert event["raw_metrics_ref"] == ""
    assert "audit_payload_json" not in event


def test_db_experiment_event_uses_public_raw_metrics_ref_without_audit_envelope(
    tmp_path: Path,
) -> None:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=registry,
    )
    metrics_path = tmp_path / "metrics" / "screening-metrics.json"

    recorder.record_step_lineage(
        branch=_branch(),
        code_hash="candidate-hash",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(
            passed=True,
            checks=(CheckResult("contract", True, "light", "ok", 1),),
        ),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result(str(metrics_path)),
        decision=Decision.ABANDON,
        champion=_champion(),
        base_champion_version=6,
        base_source_ref="champion:v6",
        changed_files=("operators/local_search.py",),
    )

    rows = registry.query_by_branch("branch-1")
    event = next(row for row in rows if row["event_kind"] == "experiment")

    assert event["raw_metrics_ref"] == "metrics/screening-metrics.json"
    assert event["base_champion_version"] == 6
    assert event["base_source_ref"] == "champion:v6"
    assert json.loads(event["changed_files_json"]) == [
        "operators/local_search.py"
    ]
    assert not contains_absolute_path(event["raw_metrics_ref"])
    assert "audit_payload_json" not in event


def test_strict_lineage_event_write_failure_raises_directly(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=_FaultyLineageRegistry(fail_event=True),
    )

    with pytest.raises(RuntimeError, match="lineage event write unavailable"):
        recorder.record_step_lineage(
            branch=_branch(),
            code_hash="candidate-hash",
            hypothesis=_hypothesis(),
            patch=_patch(),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            canary_result=CanaryResult(passed=True),
            protocol_result=_protocol_result(str(tmp_path / "metrics.json")),
            decision=Decision.PROMOTE,
            champion=_champion(),
            base_champion_version=6,
            base_source_ref="champion:v6",
            changed_files=("operators/local_search.py",),
            strict=True,
        )


def test_future_final_evidence_refs_do_not_change_step_schema(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    before = recorder.write_campaign_summary(
        state=_operator_state(n_steps=1),
        run_result=_run_projection(),
        step_history=[_step()],
    )
    before_step_keys = set(before["steps"][0].keys())

    recorder.attach_final_evidence_refs(
        {"frozen_quality_report": "/tmp/final-quality.json"}
    )
    after = recorder.write_campaign_summary(
        state=_operator_state(n_steps=1),
        run_result=_run_projection(),
        step_history=[_step()],
    )

    assert set(after["steps"][0].keys()) == before_step_keys
    assert not contains_absolute_path(after["final_evidence_refs"])
    assert "final-quality.json" in after["final_evidence_refs"]["frozen_quality_report"]
