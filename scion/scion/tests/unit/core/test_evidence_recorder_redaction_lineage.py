"""Focused tests split from test_evidence_recorder.py."""

from .evidence_recorder_test_support import *  # noqa: F401,F403

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
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
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
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
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
    status = recorder.write_status()

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
        "external diagnostic copied from artifact:scion-internal.log#"
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


def test_promotion_lineage_payload_includes_decision_reason_champion_and_metrics_ref(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    runtime_check = CheckResult(
        "V9_perf_guard",
        True,
        "heavy",
        "perf ok: case=case-1 candidate=120ms champion=100ms ratio=1.20x timeout=60s",
        7,
        metadata={
            "case_id": "case-1",
            "candidate_ms": 120,
            "champion_ms": 100,
            "ratio": 1.2,
            "candidate_timeout": False,
        },
    )
    v8_check = CheckResult(
        "V8_nondeterminism",
        True,
        "heavy",
        "adapter_canonical_signature identical across two runs",
        5,
        metadata={
            "comparison_mode": "adapter_canonical_signature",
            "selected_surface": "search_policy",
            "adapter_backed": True,
            "comparison_equal": True,
        },
    )
    event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(
            passed=True,
            checks=(CheckResult("contract", True, "light", "ok", 1),),
        ),
        verification_result=VerificationResult(
            passed=True,
            checks=(
                CheckResult("syntax", True, "light", "ok", 1),
                v8_check,
                runtime_check,
            ),
        ),
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result("/tmp/promotion-metrics.json"),
        decision=Decision.PROMOTE,
        champion=_champion(version=8),
        hypothesis_id="hyp-1",
        decision_reason_codes=("frozen_positive", "runtime_ok"),
    )
    decision_payload = recorder.build_decision_lineage_payload(
        branch=_branch(),
        protocol_result=_protocol_result("/tmp/promotion-metrics.json"),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=(runtime_check,)),
        canary_result=CanaryResult(passed=True),
        decision=Decision.PROMOTE,
        decision_reason_codes=("frozen_positive", "runtime_ok"),
    )

    metadata = json.loads(event["decision_features_json"])
    reason_codes = json.loads(decision_payload["reason"])

    assert event["branch_id"] == "branch-1"
    assert event["decision"] == "promote"
    assert not event["raw_metrics_ref"].startswith("/")
    assert "promotion-metrics.json" in event["raw_metrics_ref"]
    assert metadata["current_champion_version"] == 8
    assert metadata["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["raw_metrics_internal_only"] is True
    assert metadata["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["metrics_refs"]["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert metadata["metrics_refs"]["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert metadata["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert metadata["metrics_refs"]["raw_metrics_internal_only"] is True
    assert metadata["metrics_refs"]["audit_payload_stored_in"] == (
        "experiment_events.audit_payload_json"
    )
    audit_payload = json.loads(event["audit_payload_json"])
    assert audit_payload["internal_only"] is True
    assert audit_payload["raw_metrics_internal_only"] is True
    assert audit_payload["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["metrics_refs"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref"] == (
        event["raw_metrics_ref"]
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert not contains_absolute_path(audit_payload)
    assert metadata["decision_reason_codes"] == ["frozen_positive", "runtime_ok"]
    assert metadata["runtime_guard"]["metadata"]["ratio"] == 1.2
    assert metadata["runtime_stats"]["runtime_ratio_median"] == 1.18
    assert metadata["runtime_stats"]["runtime_pairs"] == 4
    assert metadata["verification_checks"][1]["name"] == "V8_nondeterminism"
    assert metadata["verification_checks"][1]["metadata"]["comparison_mode"] == (
        "adapter_canonical_signature"
    )
    assert metadata["verification_checks"][1]["metadata"]["adapter_backed"] is True
    assert metadata["verification_checks"][2]["name"] == "V9_perf_guard"
    payload_features = json.loads(decision_payload["features_json"])
    assert payload_features["runtime_guard"]["metadata"]["case_id"] == "case-1"
    assert payload_features["runtime_stats"]["runtime_regression_rate"] == 0.5
    assert reason_codes == ["frozen_positive", "runtime_ok"]


def test_db_audit_payload_uses_public_raw_metrics_refs(tmp_path: Path) -> None:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=registry,
    )
    metrics_path = tmp_path / "metrics" / "screening-metrics.json"

    recorder.record_step_lineage(
        branch=_branch(),
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
        hypothesis_id="hyp-1",
    )

    rows = registry.query_by_branch("branch-1")
    event = next(row for row in rows if row["event_kind"] == "experiment")
    audit_payload = json.loads(event["audit_payload_json"])

    assert event["raw_metrics_ref"] == "metrics/screening-metrics.json"
    assert not contains_absolute_path(event["raw_metrics_ref"])
    assert not contains_absolute_path(audit_payload)
    assert audit_payload["internal_only"] is True
    assert audit_payload["raw_metrics_internal_only"] is True
    assert audit_payload["raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["protocol_raw_metrics_ref_scope"] == "public_artifact_ref"
    assert audit_payload["metrics_refs"]["raw_metrics_ref"] == event["raw_metrics_ref"]
    assert audit_payload["metrics_refs"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref"] == (
        event["raw_metrics_ref"]
    )
    assert audit_payload["metrics_refs"]["protocol_raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )


def test_future_final_evidence_refs_do_not_change_step_schema(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    before = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )
    before_step_keys = set(before["steps"][0].keys())

    recorder.attach_final_evidence_refs(
        {"frozen_quality_report": "/tmp/final-quality.json"}
    )
    after = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )

    assert set(after["steps"][0].keys()) == before_step_keys
    assert not contains_absolute_path(after["final_evidence_refs"])
    assert "final-quality.json" in after["final_evidence_refs"]["frozen_quality_report"]
