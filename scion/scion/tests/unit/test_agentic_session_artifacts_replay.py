from __future__ import annotations

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

    resume_context = resume_from_artifact(output_ref, max_chars=600)
    rendered = json.dumps(resume_context, sort_keys=True)

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
