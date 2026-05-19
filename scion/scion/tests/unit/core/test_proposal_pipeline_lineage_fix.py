"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

def test_decision_features_do_not_include_agentic_rationale_or_memory() -> None:
    feature_names = {field.name for field in fields(DecisionFeatures)}

    assert "rationale_summary" not in feature_names
    assert "rejected_alternatives" not in feature_names
    assert "tainted_artifact_refs" not in feature_names
    assert "session_memory" not in feature_names
    assert "forced_surface" not in feature_names
    assert "forced_action" not in feature_names
    assert "forced_target_file" not in feature_names


def test_agentic_lineage_records_tainted_session_without_decision_rationale() -> None:
    creative = FakeCreative()
    registry = MemoryLineageRegistry()

    class SessionWithAudit:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="aps-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                champion_weight_revision=getattr(request.champion, "weight_revision", None),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                rationale_summary="private rationale must stay tainted",
                evidence_used=(
                    AgenticEvidenceRef(
                        observation_id="obs-1",
                        exposure_level="public_spec",
                        summary="safe summary",
                    ),
                ),
                transcript=(
                    AgenticTranscriptEvent(
                        phase="diagnose",
                        message="tool",
                        metadata={
                            "step_id": "tool-0001",
                            "tool_name": "context.list_surfaces",
                            "status": "ok",
                            "taint": "proposal",
                            "evidence_ref": "obs-1",
                            "result_summary": "safe summary",
                            "error_code": None,
                        },
                    ),
                ),
                self_check=AgenticSelfCheck(
                    schema_valid=True,
                    contract_preview_passed=False,
                    contract_preview_codes=("C1",),
                ),
                tainted_artifact_refs=("artifacts/aps-1/output.json",),
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=SessionWithAudit(),
        lineage_registry=registry,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert len(registry.events) == 1
    event = registry.events[0]
    payload = json.loads(event["audit_payload_json"])
    assert event["event_kind"] == "agentic_proposal_session"
    assert event["decision_features_json"] == ""
    assert event["raw_metrics_ref"] == ""
    assert payload["session_id"] == "aps-1"
    assert payload["request_id"] == "aps-1"
    assert payload["schema_version"]
    assert payload["transcript_digest"]
    assert payload["contract_preview_passed"] is False
    assert "tool_steps" not in payload
    assert "transcript" not in payload
    rendered = json.dumps(event, sort_keys=True)
    assert "private rationale" not in rendered
    assert "context.list_surfaces" not in rendered
    assert "raw_metrics_ref" in event


def test_agentic_lineage_audit_payload_marks_absolute_tainted_refs_internal(
    tmp_path,
) -> None:
    registry = MemoryLineageRegistry()
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        lineage_registry=registry,
    )
    absolute_output_ref = tmp_path / "agentic" / "session-1" / "output.json"

    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id=branch.branch_id,
        request_id="request-1",
        idempotency_key="idempotency-1",
        transcript_digest="digest-1",
        self_check=AgenticSelfCheck(
            schema_valid=True,
            contract_preview_passed=True,
            contract_preview_codes=("C1",),
        ),
        tainted_artifact_refs=(
            str(absolute_output_ref),
            "artifacts/session-1/transcript.json",
        ),
        termination_reason=AgenticTerminationReason.COMPLETED,
    )

    pipeline._record_agentic_lineage_event(output)

    event = registry.events[-1]
    payload = json.loads(event["audit_payload_json"])
    assert event["event_kind"] == "agentic_proposal_session"
    assert payload["internal_only"] is True
    assert payload["tainted_artifact_refs_internal_only"] is True
    assert payload["tainted_artifact_ref_scope"] == "public_relative"
    assert not contains_absolute_path(payload)
    assert payload["tainted_artifact_refs"][0].startswith("artifact:output.json#")
    assert payload["tainted_artifact_refs"][1] == "artifacts/session-1/transcript.json"


def test_attempt_fix_builds_fix_context_and_returns_patch() -> None:
    pipeline, branch, runtime, _, _, _ = _pipeline()
    patch = PatchProposal(
        file_path="operators/bounded.py",
        action="modify",
        code_content="bad",
    )
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is not None
    assert fixed.file_path == "operators/bounded.py"
    assert runtime.fix_kwargs["failure_streak"] == {"proposal": 1}
    assert runtime.fix_kwargs["verification_result"] is verification


def test_attempt_fix_validation_error_returns_none_without_balance_stop() -> None:
    creative = FakeCreative(fix_error=ProposalValidationError("bad fix"))
    pipeline, branch, _, circuit, _, balance = _pipeline(creative=creative)
    patch = PatchProposal("operators/bounded.py", "modify", "bad")
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is None
    assert balance["value"] is False
    assert circuit.failures == []


def test_attempt_fix_balance_error_sets_stop_signal() -> None:
    creative = FakeCreative(fix_error=LLMBalanceError("no credits"))
    pipeline, branch, _, circuit, _, balance = _pipeline(creative=creative)
    patch = PatchProposal("operators/bounded.py", "modify", "bad")
    verification = VerificationResult(
        passed=False,
        checks=(CheckResult("SYNTAX", False, "light", "bad", 1),),
        failure_severity="light",
        first_failure="SYNTAX",
    )

    fixed = pipeline.attempt_fix(branch, patch, verification)

    assert fixed is None
    assert balance["value"] is True
    assert circuit.failures == ["no credits"]
