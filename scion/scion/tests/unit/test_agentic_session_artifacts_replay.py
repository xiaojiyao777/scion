from __future__ import annotations

from scion.proposal.engine import _split_hypothesis_context
from scion.tests.unit.agentic_session_test_support import *

def test_agentic_session_does_not_emit_raw_refs_in_artifacts(tmp_path: Path) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "raw_metrics_ref": "/SECRET/raw.json",
                "note": "safe line\nvalidation SECRET_HOLDOUT_SIGNAL",
            },
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    rendered_output = json.dumps(output, default=str, sort_keys=True)
    rendered_prompt = json.dumps(
        creative.hypothesis_contexts, default=str, sort_keys=True
    )

    assert "raw_metrics_ref" not in rendered_output
    assert "SECRET_VALIDATION" not in rendered_output
    assert "SECRET_FROZEN" not in rendered_output
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_output
    assert "raw_metrics_ref" not in rendered_prompt
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_prompt
    for event in output.transcript:
        rendered_event = json.dumps(event.metadata, default=str, sort_keys=True)
        assert "raw_metrics_ref" not in rendered_event
        assert "SECRET_VALIDATION" not in rendered_event
        assert "SECRET_FROZEN" not in rendered_event


def test_agentic_session_artifact_schema_version_and_digest_exist(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))

    assert artifact["schema_version"] == AGENTIC_SESSION_SCHEMA_VERSION
    assert artifact["session_id"] == output.session_id
    assert artifact["request_id"] == output.request_id
    assert artifact["idempotency_key"] == output.idempotency_key
    assert artifact["idempotency_key"].startswith("aps:")
    assert artifact["termination_reason"] == "completed"
    assert (
        artifact["tool_loop_config"]["max_tool_calls"]
        >= artifact["tool_budget_used"]["tool_calls"]
    )
    assert artifact["transcript_digest"] == output.transcript_digest
    assert artifact["tainted"] is True
    assert artifact["patch"]["patch_body_omitted"] is True
    assert "code_content" not in json.dumps(artifact, sort_keys=True)
    assert validate_agentic_session_artifact(artifact).ok is True


def test_agentic_session_store_indexes_output_and_loads_across_instances(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        creative,
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    store = AgenticSessionStore(artifact_dir)
    by_session = store.load_by_session_id(output.session_id)
    by_key = AgenticSessionStore(artifact_dir).find_by_idempotency_key(
        output.idempotency_key
    )
    index_payload = json.loads(store.index_path.read_text(encoding="utf-8"))
    index_entry = index_payload[0]

    assert store.index_path.exists()
    assert not contains_absolute_path(index_payload)
    assert index_entry["artifact_ref"].endswith("/output.json")
    assert index_entry["artifact_ref"] == index_entry["artifact_path"]
    assert index_entry["branch_id"] == output.branch_id
    assert index_entry["kind"] == "agentic_proposal_session"
    assert index_entry["phase"]
    assert index_entry["output_artifact_ref"] == index_entry["artifact_ref"]
    assert index_entry["transcript_artifact_ref"].endswith("/transcript.json")
    assert index_entry["transcript_artifact_ref"] in index_entry["session_artifact_refs"]
    assert index_entry["artifact_ref_scope"] == "artifact_dir_relative"
    assert index_entry["artifact_path_internal_only"] is True
    assert index_entry["prompt_manifest_required"] is True
    assert index_entry["raw_prompt_saved"] is False
    assert "api_visible_prompt_manifest" in index_entry["prompt_manifest_artifact_ref"]
    assert (
        index_entry["prompt_manifest_artifact_ref"]
        in index_entry["prompt_manifest_artifact_refs"]
    )
    assert all(
        "api_visible_prompt_manifest" in ref
        for ref in index_entry["prompt_manifest_artifact_refs"]
    )
    assert index_entry["prompt_manifest_not_required_reason"] == ""
    assert by_session is not None
    assert by_session.validation.ok is True
    assert by_session.entry.session_id == output.session_id
    assert by_session.entry.status == "completed"
    assert by_session.entry.transcript_digest == output.transcript_digest
    assert by_session.entry.artifact_ref == index_entry["artifact_ref"]
    assert by_session.entry.prompt_manifest_required is True
    assert by_session.entry.raw_prompt_saved is False
    assert by_key is not None
    assert by_key.entry.session_id == output.session_id
    assert by_session.entry.branch_id == output.branch_id
    assert by_session.entry.output_artifact_ref == index_entry["artifact_ref"]


def test_agentic_session_index_marks_prompt_manifest_not_required_when_no_llm_call(
    tmp_path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    artifact_store = FileAgenticSessionArtifactStore(artifact_dir)
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="session-no-llm",
        campaign_id="camp-1",
        branch_id="branch-1",
        request_id="request-no-llm",
        idempotency_key="idempotency-no-llm",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
    )

    output_ref = artifact_store.write_output(output)
    store = AgenticSessionStore(artifact_dir)
    entry = store.record_output(output, output_ref)
    index_payload = json.loads(store.index_path.read_text(encoding="utf-8"))
    index_entry = index_payload[0]

    assert index_entry["prompt_manifest_required"] is False
    assert index_entry["raw_prompt_saved"] is False
    assert index_entry["prompt_manifest_artifact_ref"] == ""
    assert index_entry["prompt_manifest_artifact_refs"] == []
    assert (
        index_entry["prompt_manifest_not_required_reason"]
        == "no_llm_call_recorded_for_session"
    )
    assert entry.prompt_manifest_required is False
    assert entry.raw_prompt_saved is False
    assert entry.prompt_manifest_not_required_reason == "no_llm_call_recorded_for_session"
    assert not contains_absolute_path(index_payload)


def test_agentic_session_index_explains_tool_only_prompt_manifest_not_required(
    tmp_path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    artifact_store = FileAgenticSessionArtifactStore(artifact_dir)
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="session-tool-only",
        campaign_id="camp-1",
        branch_id="branch-1",
        request_id="request-tool-only",
        idempotency_key="idempotency-tool-only",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        transcript=(
            AgenticTranscriptEvent(
                phase="diagnose",
                message="tool step",
                metadata={"tool_name": "context.list_surfaces", "status": "ok"},
            ),
        ),
        tool_budget_used={"tool_steps": 1, "tool_calls": 1},
    )

    output_ref = artifact_store.write_output(output)
    store = AgenticSessionStore(artifact_dir)
    entry = store.record_output(output, output_ref)
    index_entry = json.loads(store.index_path.read_text(encoding="utf-8"))[0]

    assert index_entry["prompt_manifest_required"] is False
    assert (
        index_entry["prompt_manifest_not_required_reason"]
        == "tool_context_recorded_but_no_model_prompt_call_recorded_for_session"
    )
    assert entry.prompt_manifest_not_required_reason == (
        "tool_context_recorded_but_no_model_prompt_call_recorded_for_session"
    )


class _InterruptingHypothesisCreative(FakeCreative):
    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        raise KeyboardInterrupt("synthetic campaign abort")


class _InterruptAfterFirstOutputStore(FileAgenticSessionArtifactStore):
    def __init__(self, artifact_dir: Path) -> None:
        super().__init__(artifact_dir)
        self.output_writes = 0

    def write_output(self, output):
        ref = super().write_output(output)
        self.output_writes += 1
        if self.output_writes == 1:
            raise SystemExit("synthetic external stop after partial checkpoint")
        return ref


def test_agentic_session_persists_code_phase_partial_before_tool_selection_interrupt(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = _InterruptAfterFirstOutputStore(artifact_dir)
    session = AgenticProposalSession(
        FakeCreative(),
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    with pytest.raises(SystemExit):
        session.run(
            AgenticProposalRequest(
                campaign_id="camp-code-partial",
                branch=context.branch,
                champion=context.champion,
                hypothesis_context={},
                build_code_context=lambda _hypothesis: {"kind": "code"},
                approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                    passed=True,
                    failure_reason=None,
                ),
                problem_id=context.problem_id,
                problem_spec_hash=context.problem_spec_hash,
                tool_context=context,
            )
        )

    assert artifact_store.output_writes == 1
    [session_dir] = [path for path in artifact_dir.iterdir() if path.is_dir()]
    output = json.loads((session_dir / "output.json").read_text(encoding="utf-8"))
    transcript = json.loads(
        (session_dir / "transcript.json").read_text(encoding="utf-8")
    )
    index = json.loads(
        (artifact_dir / "agentic_session_index.json").read_text(encoding="utf-8")
    )

    assert output["status"] == "partial_hypothesis_only"
    assert output["phase"] == "inspect_interface"
    assert output["hypothesis"]["target_file"]
    assert "code phase in progress" in output["failure_detail"]
    assert transcript["phase"] == "inspect_interface"
    assert index[0]["status"] == "partial_hypothesis_only"
    assert index[0]["target_file"] == output["hypothesis"]["target_file"]
    assert validate_agentic_session_artifact(output).ok is True


def test_agentic_session_persists_abort_stub_on_keyboard_interrupt(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        _InterruptingHypothesisCreative(),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    branch = Branch(
        branch_id="branch-abort",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="code-hash",
    )

    with pytest.raises(KeyboardInterrupt):
        session.run(
            AgenticProposalRequest(
                campaign_id="camp-abort",
                branch=branch,
                champion=None,
                hypothesis_context={"seed": "abort"},
                build_code_context=lambda _hypothesis: {"kind": "code"},
            )
        )

    [session_dir] = [path for path in artifact_dir.iterdir() if path.is_dir()]
    output_path = session_dir / "output.json"
    transcript_path = session_dir / "transcript.json"
    index_path = artifact_dir / "agentic_session_index.json"
    output = json.loads(output_path.read_text(encoding="utf-8"))
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    index_entry = json.loads(index_path.read_text(encoding="utf-8"))[0]

    assert output_path.exists()
    assert transcript_path.exists()
    assert index_path.exists()
    assert output["status"] == "failed"
    assert output["termination_reason"] == "campaign_abort"
    assert output["failure_category"] == "agentic_budget_control"
    assert "abort" in output["failure_detail"]
    assert "KeyboardInterrupt" in output["failure_detail"]
    assert output["session_id"] == session_dir.name
    assert output["campaign_id"] == "camp-abort"
    assert output["branch_id"] == "branch-abort"
    assert output["idempotency_key"].startswith("aps:")
    assert output["phase"] == "draft_hypothesis"
    assert output["tool_budget_used"]["tool_calls"] == 0
    assert output["compact_transcript"]
    assert transcript["status"] == "failed"
    assert transcript["termination_reason"] == "campaign_abort"
    assert any(
        "api_visible_prompt_manifest" in ref
        for ref in output["prompt_manifest_artifact_refs"]
    )
    assert any(
        "api_visible_prompt_manifest" in ref
        for ref in output["tainted_artifact_refs"]
    )
    assert index_entry["status"] == "failed"
    assert index_entry["termination_reason"] == "campaign_abort"
    assert index_entry["failure_category"] == "agentic_budget_control"
    assert index_entry["failure_reason"] == index_entry["failure_detail"]
    assert index_entry["prompt_manifest_required"] is True
    assert "api_visible_prompt_manifest" in index_entry["prompt_manifest_artifact_ref"]


def test_agentic_session_index_preserves_failure_and_hypothesis_summary_fields(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    artifact_store = FileAgenticSessionArtifactStore(artifact_dir)
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="generic_surface",
            action="modify",
            target_file="policies/generic_policy.py",
            mechanism_changes=(
                {"id": "generic_counter_probe", "change_type": "modify"},
            ),
            branch_lesson_usage={
                "borrowed_lessons": [
                    {
                        "lesson_id": "lesson:generic-counter",
                        "source_branch_ids": ["branch-source"],
                        "target_file": "policies/generic_policy.py",
                        "action": "modify",
                        "mechanism": "generic_counter_probe",
                        "borrow_rationale": (
                            "RAW BRANCH LESSON RATIONALE SHOULD NOT LEAK"
                        ),
                    }
                ]
            },
        )
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="session-failed-summary",
        campaign_id="camp-1",
        branch_id="branch-1",
        request_id="request-failed-summary",
        idempotency_key="idempotency-failed-summary",
        selected_surface="generic_surface",
        action="modify",
        hypothesis=hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_category="algorithm_smoke_failure",
        failure_detail="synthetic smoke rejected declared activity attribution",
    )

    output_ref = artifact_store.write_output(output)
    store = AgenticSessionStore(artifact_dir)
    index_entry = json.loads(store.index_path.read_text(encoding="utf-8"))[0]
    loaded = store.load_by_session_id(output.session_id)
    artifact_summary = inspect_agentic_session_artifact(output_ref)

    assert index_entry["failure_category"] == "algorithm_smoke_failure"
    assert index_entry["failure_detail"] == (
        "synthetic smoke rejected declared activity attribution"
    )
    assert index_entry["failure_reason"] == index_entry["failure_detail"]
    assert index_entry["selected_surface"] == "generic_surface"
    assert index_entry["action"] == "modify"
    assert index_entry["target_file"] == "policies/generic_policy.py"
    assert index_entry["mechanism_ids"] == ["generic_counter_probe"]
    assert index_entry["hypothesis_summary"]["mechanism_ids"] == [
        "generic_counter_probe"
    ]
    usage_summary = index_entry["hypothesis_summary"]["branch_lesson_usage"]
    assert usage_summary["report_only"] is True
    assert usage_summary["decision_features_excluded"] is True
    assert usage_summary["present"] is True
    assert usage_summary["field_counts"] == {"borrowed_lessons": 1}
    assert "RAW BRANCH LESSON RATIONALE SHOULD NOT LEAK" not in json.dumps(
        index_entry,
        sort_keys=True,
    )
    artifact_payload = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    assert artifact_payload["hypothesis_summary"]["branch_lesson_usage"][
        "field_counts"
    ] == {"borrowed_lessons": 1}
    assert loaded is not None
    assert loaded.entry.failure_reason == loaded.entry.failure_detail
    assert loaded.entry.target_file == "policies/generic_policy.py"
    assert loaded.entry.mechanism_ids == ("generic_counter_probe",)
    assert artifact_summary["failure_reason"] == output.failure_detail
    assert artifact_summary["target_file"] == "policies/generic_policy.py"
    assert artifact_summary["mechanism_ids"] == ["generic_counter_probe"]


def test_agentic_session_index_refs_smoke_and_code_retry_failure_artifacts(
    tmp_path: Path,
) -> None:
    initial_patch = PatchProposal(**_valid_policy_patch_payload())
    creative = _PatchThenTransientApiErrorCreative(initial_patch)
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["proposal.algorithm_smoke"] = _FailingAlgorithmSmokeTool()
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=registry,
        tool_loop_config=AgenticToolLoopConfig(max_code_repair_attempts=1),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    store = AgenticSessionStore(tmp_path / "aps-artifacts")
    index_entry = json.loads(store.index_path.read_text(encoding="utf-8"))[0]
    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    retry_ref = index_entry["code_retry_failure_artifact_refs"][0]
    retry_artifact = json.loads(
        (tmp_path / "aps-artifacts" / retry_ref).read_text(encoding="utf-8")
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert index_entry["branch_id"] == context.branch.branch_id
    assert index_entry["phase"]
    assert index_entry["smoke_evidence_artifact_refs"]
    assert index_entry["code_retry_failure_artifact_refs"]
    assert index_entry["code_retry_failure_count"] == 1
    assert retry_ref in index_entry["session_artifact_refs"]
    assert artifact["code_retry_failure_artifact_refs"] == (
        index_entry["code_retry_failure_artifact_refs"]
    )
    assert artifact["code_retry_failure_count"] == 1
    assert retry_artifact["artifact_kind"] == "code_retry_failure_detail"
    assert retry_artifact["failure_kind"] == "preview_failure"
    assert retry_artifact["repair_attempt"] == 1
    assert retry_artifact["attempt_index"] == 1
    assert retry_artifact["session_index"] == 1
    assert retry_artifact["source"] == "proposal.algorithm_smoke"
    assert retry_artifact["source_tool"] == "proposal.algorithm_smoke"
    assert retry_artifact["source_phase"] == "draft_patch"
    assert retry_artifact["request_kind"] == "code"
    assert retry_artifact["request_id"] == output.request_id
    assert retry_artifact["error_type"]
    assert "algorithm smoke did not pass" in retry_artifact["error_message"]
    assert retry_artifact["failure_detail"] == retry_artifact["reason"]
    assert retry_artifact["detail"] == retry_artifact["reason"]
    assert retry_artifact["message"] == retry_artifact["reason"]
    assert retry_artifact["trace_id"] == ""
    assert retry_artifact["trace_ref"] == ""
    assert retry_artifact["observation_id"]
    assert retry_artifact["observation_type"]
    assert retry_artifact["observation_summary"]
    assert "algorithm smoke did not pass" in retry_artifact["reason"]
    context_failure_detail = creative.code_contexts[1][
        "agentic_code_retry_failure_detail"
    ]
    assert context_failure_detail["artifact_ref"].endswith(
        "code_retry_failure_detail_0001.json"
    )
    assert context_failure_detail["attempt_index"] == 1
    assert context_failure_detail["session_index"] == 1
    assert context_failure_detail["error_type"] == retry_artifact["error_type"]
    assert context_failure_detail["error_message"] == retry_artifact["reason"]
    assert context_failure_detail["failure_detail"] == retry_artifact["reason"]
    assert context_failure_detail["request_kind"] == "code"
    assert context_failure_detail["source_phase"] == "draft_patch"
    ledger_entry = next(
        item
        for item in artifact["failure_ledger"]["entries"]
        if item["source"] == "code_retry_preview_failure"
    )
    assert ledger_entry["repair_attempt"] == 1
    assert ledger_entry["attempt_index"] == 1
    assert ledger_entry["session_index"] == 1


def test_partial_hypothesis_awaiting_approval_is_not_contract_failure(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="generic_surface",
            action="modify",
            target_file="policies/generic_policy.py",
            mechanism_changes=(
                {"id": "generic_counter_probe", "change_type": "modify"},
            ),
        )
    )
    session = AgenticProposalSession(
        FakeCreative(hypothesis=hypothesis),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    branch = Branch(
        branch_id="branch-partial",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="code-hash",
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-partial",
            branch=branch,
            champion=None,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
        )
    )
    index_entry = json.loads(
        (artifact_dir / "agentic_session_index.json").read_text(encoding="utf-8")
    )[0]

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == (
        AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.failure_category is None
    assert index_entry["termination_reason"] == "hypothesis_awaiting_approval"
    assert index_entry["failure_category"] == ""
    assert index_entry["failure_detail"] == "hypothesis awaits ContractGate approval"
    assert index_entry["target_file"] == "policies/generic_policy.py"
    assert index_entry["mechanism_ids"] == ["generic_counter_probe"]


def test_agentic_replay_validator_rejects_budget_duplicate_step_and_raw_marker(
    tmp_path: Path,
) -> None:
    artifact = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "session_id": "session-1",
        "request_id": "request-1",
        "termination_reason": "tool_loop_limit",
        "tool_loop_config": {
            "max_steps": 1,
            "max_tool_calls": 1,
            "max_observation_chars": 100,
        },
        "tool_budget_used": {
            "tool_steps": 2,
            "tool_calls": 1,
            "observation_chars": 10,
        },
        "transcript_digest": "wrong",
        "compact_transcript": [
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.list_surfaces",
                    "status": "ok",
                    "result_summary": "safe",
                },
            },
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.read_problem",
                    "status": "ok",
                    "result_summary": "raw_metrics_ref should reject",
                },
            },
        ],
    }

    result = validate_agentic_session_artifact(artifact)

    assert result.ok is False
    rendered_errors = " ".join(result.errors)
    assert "tool budget exceeded" in rendered_errors
    assert "duplicate step_id" in rendered_errors
    assert "raw ref marker" in rendered_errors


def test_agentic_replay_validator_treats_zero_budget_limits_as_disabled() -> None:
    artifact = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "session_id": "session-disabled",
        "request_id": "request-disabled",
        "idempotency_key": "aps:disabled",
        "termination_reason": "completed",
        "tool_loop_config": {
            "max_steps": 0,
            "max_tool_calls": 0,
            "max_observation_chars": 0,
        },
        "tool_budget_used": {
            "tool_steps": 12,
            "tool_calls": 10,
            "observation_chars": 250000,
        },
        "transcript_digest": "",
        "compact_transcript": [
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.read_algorithm_file",
                    "status": "ok",
                    "result_summary": "source context captured",
                },
            }
        ],
    }

    result = validate_agentic_session_artifact(artifact)

    assert result.ok is True
    assert not result.errors


def test_resume_from_artifact_returns_sanitized_length_bounded_context(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )

    full_resume_context = resume_from_artifact(output_ref, max_chars=8000)
    resume_context = resume_from_artifact(output_ref, max_chars=600)
    rendered = json.dumps(resume_context, sort_keys=True)

    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    assert artifact["observation_ledger"]["observations"]
    assert artifact["observation_ledger"]["read_receipts"]
    assert full_resume_context["observation_ledger"]["observations"]
    assert full_resume_context["read_receipts"]
    assert full_resume_context["model_facing_projection"]["schema_version"] == (
        "agentic-resume-model-projection.v1"
    )
    assert len(resume_context["summary"]) <= 600
    assert resume_context["session_id"] == output.session_id
    assert resume_context["transcript_digest"] == output.transcript_digest
    assert resume_context["tool_steps"]
    assert {
        "tool_name",
        "status",
        "error_code",
        "evidence_ref",
        "result_summary",
    }.issubset(resume_context["tool_steps"][0])
    assert "structured_payload" not in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "code_content" not in rendered

    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Synthetic problem.",
            "research_surfaces": "surface: search_policy",
            "objective_policy_guidance": "Minimize cost.",
            "champion_operators_code": "def champion(): pass",
            "champion_stats": "champion v1",
            "agentic_resume_context": {
                "source": "agentic_session_store",
                "resume": full_resume_context,
            },
        }
    )
    model_visible = json.dumps(system_blocks, sort_keys=True) + user_prompt
    assert "## Agentic Resume Context" in model_visible
    assert "bounded_model_facing_handoff_no_raw_observation_ledger" in model_visible
    assert "content_preview" not in model_visible
    assert "structured_payload" not in model_visible
    assert '"observation_ledger":' not in model_visible


def test_agentic_session_tool_errors_are_controlled_or_fail_closed(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    nonfatal_context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )
    creative = FakeCreative()
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    degraded = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=nonfatal_context,
        )
    )
    failed_closed = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry(),
    ).run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    memory_events = [
        event.metadata
        for event in degraded.transcript
        if event.metadata.get("tool_name") == "memory.query"
    ]
    assert degraded.status == AgenticProposalStatus.COMPLETED
    assert memory_events[0]["is_error"] is True
    assert failed_closed.status == AgenticProposalStatus.FAILED
    assert creative.hypothesis_contexts
