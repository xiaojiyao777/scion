"""Focused tests split from test_evidence_recorder.py."""

from dataclasses import replace

import pytest

from scion.core.evidence_recording.replay_identity import (
    FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS,
    FORMAL_REPLAY_IDENTITY_SCHEMA,
)

from .evidence_recorder_test_support import *  # noqa: F401,F403


class _FaultyLineageRegistry:
    def __init__(
        self, *, fail_event: bool = False, fail_decision: bool = False
    ) -> None:
        self.fail_event = fail_event
        self.fail_decision = fail_decision
        self.events = []
        self.decisions = []

    def record_event(self, event):
        if self.fail_event:
            raise RuntimeError("lineage event write unavailable")
        self.events.append(dict(event))

    def record_decision(self, **payload):
        if self.fail_decision:
            raise RuntimeError("lineage decision write unavailable")
        self.decisions.append(dict(payload))


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
    protocol_result = replace(
        _protocol_result("/tmp/promotion-metrics.json"),
        candidate_surface_runtime_summary={
            "telemetry_guard": {
                "passed": False,
                "candidate_runs": 4,
                "failures": [
                    {
                        "severity": "fail",
                        "code": "TELEMETRY_ACTIVITY_ZERO",
                        "category": "activity",
                        "field": "activation_probe",
                        "candidate_missing": 16,
                        "candidate_present": 4,
                        "candidate_positive": 0,
                        "repairable": True,
                    }
                ],
            }
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
        protocol_result=protocol_result,
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
    audit_only_keys = {
        "protocol_raw_metrics_ref",
        "raw_metrics_public_ref",
        "metrics_refs",
        "raw_metrics_ref_scope",
        "raw_metrics_internal_only",
        "internal_audit_payload",
        "verification_checks",
        "runtime_guard",
        "telemetry_failure_details",
        "telemetry_validation_feedback",
    }
    assert audit_only_keys.isdisjoint(metadata)
    assert "perf ok:" not in event["decision_features_json"]
    assert "activation_probe" not in event["decision_features_json"]
    assert "candidate_missing=16" not in event["decision_features_json"]
    assert metadata["runtime_guard_passed"] is True
    assert metadata["runtime_guard_elapsed_ms"] == 7
    assert metadata["runtime_stats"]["runtime_ratio_median"] == 1.18
    assert metadata["runtime_stats"]["runtime_pairs"] == 4
    assert audit_payload["runtime_guard"]["metadata"]["ratio"] == 1.2
    assert audit_payload["verification_checks"][1]["name"] == "V8_nondeterminism"
    assert audit_payload["verification_checks"][1]["detail"] == (
        "adapter_canonical_signature identical across two runs"
    )
    assert audit_payload["verification_checks"][1]["metadata"]["comparison_mode"] == (
        "adapter_canonical_signature"
    )
    assert audit_payload["verification_checks"][1]["metadata"]["adapter_backed"] is True
    assert audit_payload["verification_checks"][2]["name"] == "V9_perf_guard"
    assert audit_payload["verification_checks"][2]["detail"] == (
        "perf ok: case=case-1 candidate=120ms champion=100ms ratio=1.20x timeout=60s"
    )
    assert audit_payload["telemetry_failure_details"][0]["surface_field_id"] == (
        "activation_probe"
    )
    assert "candidate_missing=16" in audit_payload["telemetry_validation_feedback"]
    payload_features = json.loads(decision_payload["features_json"])
    assert audit_only_keys.isdisjoint(payload_features)
    assert payload_features["runtime_guard_passed"] is True
    assert payload_features["runtime_guard_elapsed_ms"] == 7
    assert payload_features["runtime_stats"]["runtime_regression_rate"] == 0.5
    assert reason_codes == ["frozen_positive", "runtime_ok"]


def test_formal_lineage_audit_payload_includes_replay_identity_key_set(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    protocol_result = replace(
        _protocol_result(str(tmp_path / "metrics" / "formal.json")),
        selected_surface="local_search",
    )

    event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=protocol_result,
        decision=Decision.PROMOTE,
        champion=_champion(),
        hypothesis_id="hyp-1",
    )
    same_patch_event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis("Different free-text rationale."),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=protocol_result,
        decision=Decision.PROMOTE,
        champion=_champion(),
        hypothesis_id="hyp-2",
    )
    changed_patch_event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=PatchProposal(
            file_path="operators/local_search.py",
            action="modify",
            code_content="class LocalSearch:\n    marker = 1\n",
        ),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=protocol_result,
        decision=Decision.PROMOTE,
        champion=_champion(),
        hypothesis_id="hyp-3",
    )

    audit_payload = json.loads(event["audit_payload_json"])
    same_patch_payload = json.loads(same_patch_event["audit_payload_json"])
    changed_patch_payload = json.loads(changed_patch_event["audit_payload_json"])
    replay_identity = audit_payload["replay_identity"]
    required_keys = set(FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS)

    assert required_keys.issubset(audit_payload)
    assert required_keys.issubset(replay_identity)
    assert replay_identity["schema"] == FORMAL_REPLAY_IDENTITY_SCHEMA
    for key in required_keys:
        assert audit_payload[key]
        assert replay_identity[key]
        assert replay_identity[key] != "unknown"
    assert replay_identity["identity_status"] == "complete"
    assert replay_identity["status"] == "complete"
    assert replay_identity["missing_identity_keys"] == []
    assert replay_identity["missing_keys"] == []
    assert replay_identity["degraded_markers"] == []
    assert audit_payload["problem_spec_hash"] == "problem-hash"
    assert audit_payload["split_manifest_hash"] == "split-hash"
    assert audit_payload["seed_ledger_hash"] == "seed-hash"
    assert audit_payload["selected_surface"] == "local_search"
    assert audit_payload["protocol_version"] == "protocol-v3"
    assert audit_payload["raw_metrics_ref"] == "metrics/formal.json"
    assert event["protocol_version"] == "protocol-v3"
    assert audit_payload["patch_digest"] == audit_payload["patch_hash"]
    assert len(audit_payload["patch_digest"]) == 64
    assert same_patch_payload["patch_digest"] == audit_payload["patch_digest"]
    assert changed_patch_payload["patch_digest"] != audit_payload["patch_digest"]
    assert not contains_absolute_path(audit_payload)


def test_formal_lineage_audit_payload_marks_missing_replay_identity_degraded(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        canary_result=CanaryResult(passed=True),
        protocol_result=None,
        decision=Decision.ABANDON,
        champion=_champion(),
        hypothesis_id="hyp-1",
    )

    audit_payload = json.loads(event["audit_payload_json"])
    replay_identity = audit_payload["replay_identity"]
    required_keys = set(FORMAL_REPLAY_IDENTITY_REQUIRED_KEYS)

    for key in required_keys:
        assert key in audit_payload
        assert key in replay_identity
        assert audit_payload[key]
        assert replay_identity[key]
    assert replay_identity["schema"] == FORMAL_REPLAY_IDENTITY_SCHEMA
    assert replay_identity["identity_status"] == "degraded"
    assert replay_identity["status"] == "degraded"
    assert replay_identity["identity_degraded"] is True
    assert replay_identity["degraded_markers"] == ["missing_replay_identity"]
    assert set(replay_identity["missing_identity_keys"]) == {
        "problem_spec_hash",
        "split_manifest_hash",
        "seed_ledger_hash",
        "protocol_version",
        "raw_metrics_ref",
    }
    assert replay_identity["missing_keys"] == replay_identity["missing_identity_keys"]
    assert audit_payload["patch_digest"] != "unknown"
    assert audit_payload["selected_surface"] == "local_search"
    assert audit_payload["raw_metrics_ref"] == "unknown"


def test_internal_audit_verification_check_detail_is_redacted(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    workspace = tmp_path / "workspaces" / "branch-1"
    outside_path = "/var/tmp/scion-secret.log"
    verification = VerificationResult(
        passed=False,
        checks=(
            CheckResult(
                "V6_feasibility",
                False,
                "heavy",
                f"capacity violation; workspace={workspace}; log={outside_path}",
                12,
                metadata={"adapter_backed": True, "selected_surface": "solver_design"},
            ),
        ),
        failure_severity="heavy",
        first_failure="V6_feasibility",
    )

    event = recorder.build_step_lineage_event(
        branch=_branch(),
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=verification,
        canary_result=CanaryResult(passed=True),
        protocol_result=_protocol_result(str(tmp_path / "metrics.json")),
        decision=Decision.ABANDON,
        champion=_champion(),
        hypothesis_id="hyp-1",
    )

    audit_payload = json.loads(event["audit_payload_json"])
    check = audit_payload["verification_checks"][0]

    assert check["name"] == "V6_feasibility"
    assert "capacity violation" in check["detail"]
    assert "workspaces/branch-1" in check["detail"]
    assert "artifact:scion-secret.log#" in check["detail"]
    assert check["metadata"]["adapter_backed"] is True
    assert check["metadata"]["selected_surface"] == "solver_design"
    assert not contains_absolute_path(audit_payload)


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


def test_lineage_write_failures_degrade_summary_status_without_failing_step(
    tmp_path: Path,
) -> None:
    cases = (
        ("record_event", {"fail_event": True}),
        ("record_decision", {"fail_decision": True}),
    )
    for operation, registry_kwargs in cases:
        campaign_dir = tmp_path / operation
        registry = _FaultyLineageRegistry(**registry_kwargs)
        recorder = EvidenceRecorder(
            campaign_id="camp-1",
            campaign_dir=campaign_dir,
            registry=registry,
            state_provider=lambda: {
                "campaign_id": "camp-1",
                "requested_rounds": 1,
                "screened_experiments": 1,
                "n_experiments": 1,
                "proposal_attempts": 1,
                "branches": [],
            },
        )

        outcome = recorder.record_step_lineage(
            branch=_branch(),
            hypothesis=_hypothesis(),
            patch=_patch(),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            canary_result=CanaryResult(passed=True),
            protocol_result=_protocol_result(str(campaign_dir / "metrics.json")),
            decision=Decision.ABANDON,
            champion=_champion(),
            hypothesis_id="hyp-1",
        )

        summary = recorder.write_campaign_summary(
            step_history=[_step(str(campaign_dir / "metrics.json"))],
            round_num=1,
            champion=_champion(),
            stopped_reason="max_rounds_exhausted",
        )
        status = recorder.write_status(
            stopped_reason="max_rounds_exhausted",
            loop_status={
                "requested_rounds": 1,
                "effective_rounds_completed": 1,
                "proposal_attempts_consumed": 1,
            },
        )

        assert outcome["status"] == "degraded"
        assert outcome["errors"][0]["operation"] == operation
        assert summary["lineage_integrity"]["status"] == "degraded"
        assert summary["evidence_integrity"]["status"] == "degraded"
        assert summary["formal_readiness"]["lineage_integrity_status"] == "degraded"
        assert summary["run_validity"]["integrity_status"] == "degraded"
        assert "lineage_registry_write_degraded" in summary["run_validity"]["warnings"]
        assert status["lineage_integrity"]["status"] == "degraded"
        assert status["evidence_integrity"]["lineage_status"] == "degraded"
        assert status["run_validity"]["integrity_status"] == "degraded"
        assert "lineage_registry_write_degraded" in status["run_validity"]["warnings"]


def test_strict_lineage_write_failure_still_raises_and_records_degraded_outcome(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=_FaultyLineageRegistry(fail_decision=True),
    )

    with pytest.raises(RuntimeError, match="lineage decision write unavailable"):
        recorder.record_step_lineage(
            branch=_branch(),
            hypothesis=_hypothesis(),
            patch=_patch(),
            contract_result=ContractResult(passed=True, checks=()),
            verification_result=VerificationResult(passed=True, checks=()),
            canary_result=CanaryResult(passed=True),
            protocol_result=_protocol_result(str(tmp_path / "metrics.json")),
            decision=Decision.PROMOTE,
            champion=_champion(),
            hypothesis_id="hyp-1",
            strict=True,
        )

    integrity = recorder.lineage_integrity_snapshot()
    assert integrity["status"] == "degraded"
    assert integrity["decision_recording_failures"] == 1


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
