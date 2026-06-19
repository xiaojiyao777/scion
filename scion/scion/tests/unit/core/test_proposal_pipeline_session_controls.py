"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

def test_generate_code_failure_routes_proposal_failure() -> None:
    creative = FakeCreative(code_error=LLMRetryExhaustedError("code failed"))
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)

    patch = pipeline.generate_code(branch, creative.hypothesis, prior_failure="first")

    assert patch is None
    assert circuit.failures == ["code failed"]
    assert len(failures) == 1
    failed_branch, failure = failures[0]
    assert failed_branch is branch
    assert failure.category == "proposal"
    assert failure.detail == "code failed"


def test_default_agentic_session_has_registry_and_requests_get_tool_context() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
    )

    default_session = _pipeline(use_agentic_proposal=True)[0]._get_agentic_session()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert isinstance(default_session, AgenticProposalSession)
    assert isinstance(default_session.tool_registry, ProposalToolRegistry)
    assert "context.list_surfaces" in default_session.tool_registry.list_tools()
    assert hypothesis is not None
    assert record is not None
    assert len(captured) == 1
    assert captured[0].campaign_id == "camp-1"
    assert captured[0].context_profile == "algorithm"
    assert isinstance(captured[0].tool_context, ProposalToolContext)
    assert captured[0].tool_context.branch is branch
    assert captured[0].tool_context.problem_id == "toy"


def test_agentic_requests_include_all_problem_identity_anchors() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                split_manifest_hash=request.split_manifest_hash,
                seed_ledger_hash=request.seed_ledger_hash,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
        require_agentic_problem_anchors=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    assert len(captured) == 1
    request = captured[0]
    assert request.problem_id == "toy"
    assert request.problem_spec_hash == "spec-hash"
    assert request.split_manifest_hash == "split-hash"
    assert request.seed_ledger_hash == "seed-hash"
    assert request.tool_context is not None
    assert request.tool_context.problem_id == "toy"
    assert request.tool_context.problem_spec_hash == "spec-hash"
    assert request.tool_context.split_manifest_hash == "split-hash"
    assert request.tool_context.seed_ledger_hash == "seed-hash"


def test_agentic_hypothesis_request_uses_filtered_prompt_context() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, runtime, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
    )
    raw_context = {
        "kind": "hypothesis",
        "branch_dossier": "full Branch Dossier",
        "research_log": "full research log",
        "cross_branch_research": "full cross_branch_research.v1 payload",
        "cross_branch_research_payload": {
            "schema_version": "cross_branch_research.v1",
            "similarity_hints": [
                {
                    "hint_type": "near_duplicate",
                    "branch_ids": ["branch-1", "sibling"],
                    "summary": "Nearby branch already tried this shape.",
                }
            ],
            "lesson_cards": [
                {
                    "scope": "cross_branch",
                    "lesson_type": "near_duplicate",
                    "summary": "Compact agentic lesson.",
                }
            ],
            "material_difference_audit_records": [{"audit": "hidden"}],
        },
        "cross_branch_research_audit_records": [{"audit": "hidden"}],
        "branch_lesson_usage_requirement": {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "record_type": "branch_lesson_usage_requirement",
            "record_id": "branch_lesson_usage_requirement:test",
            "required": True,
            "required_for": "sibling_nearby_attempt",
            "required_output_field": "branch_lesson_usage",
        },
        "branch_lesson_records": [
            {
                "schema_version": "branch_lesson.v1",
                "lesson_id": "lesson:agentic-visible",
                "scope": "cross_branch",
                "lesson_role": "contrast",
                "lesson_type": "near_duplicate",
                "required_response": {
                    "required_for": "sibling_nearby_attempt",
                    "required_output_field": "branch_lesson_usage",
                    "required_contrast_dimensions": ["target_file"],
                },
                "raw_text": "hidden raw lesson text",
            }
        ],
    }

    def build_hypothesis_context(**kwargs):
        runtime.hypothesis_kwargs = kwargs
        return raw_context

    runtime.build_hypothesis_context = build_hypothesis_context

    pipeline.generate_hypothesis(branch)

    assert len(captured) == 1
    assert captured[0].campaign_id == "camp-1"
    assert captured[0].context_profile == "algorithm"
    prompt_context = captured[0].hypothesis_context
    assert prompt_context["context_profile"] == "algorithm"
    assert prompt_context["context_profile_metadata"]["profile"] == "algorithm"
    assert "branch_dossier" in raw_context
    assert "branch_dossier" not in prompt_context
    assert "research_log" not in prompt_context
    assert "cross_branch_research_payload" not in prompt_context
    assert "cross_branch_research_audit_records" not in prompt_context
    assert "compact_cross_branch_learning.v1" in (
        prompt_context["cross_branch_research"]
    )
    assert "cross_branch_research.v1" not in prompt_context["cross_branch_research"]
    assert "Compact agentic lesson." in prompt_context["cross_branch_research"]
    ref = pipeline.pop_agentic_session_ref(branch.branch_id)
    assert ref is not None
    assert ref["cross_branch_research_status"] == "available"
    assert ref["branch_lesson_usage_requirement"]["required"] is True
    assert ref["branch_lesson_records"][0]["lesson_id"] == "lesson:agentic-visible"
    assert "hidden raw lesson text" not in str(ref)


def test_agentic_hypothesis_request_records_repair_context_profile() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                context_profile=request.context_profile,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, runtime, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
    )
    raw_context = {
        "kind": "hypothesis",
        "agentic_prior_quality_blocks": [
            {"failure_code": "proposal_activation_diagnostic"}
        ],
        "agentic_prior_quality_block_rule": "repair cited issue",
        "agentic_negative_fact_block": "negative fact",
    }

    def build_hypothesis_context(**kwargs):
        runtime.hypothesis_kwargs = kwargs
        return raw_context

    runtime.build_hypothesis_context = build_hypothesis_context

    pipeline.generate_hypothesis(branch)

    assert len(captured) == 1
    request = captured[0]
    assert request.campaign_id == "camp-1"
    assert request.context_profile == "repair"
    assert request.hypothesis_context["context_profile"] == "repair"
    assert request.hypothesis_context["context_profile_metadata"]["profile"] == (
        "repair"
    )
    assert request.hypothesis_context["agentic_prior_quality_blocks"]


def test_agentic_artifacts_record_campaign_id_and_context_profile(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        FakeCreative(),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=session,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is not None
    assert record is not None
    output_paths = list(artifact_dir.glob("*/output.json"))
    manifest_paths = list(
        artifact_dir.glob("*/scratch/api_visible_prompt_manifest_*.json")
    )
    transcript_paths = list(artifact_dir.glob("*/transcript.json"))
    assert len(output_paths) == 1
    assert manifest_paths
    assert len(transcript_paths) == 1

    output_payload = json.loads(output_paths[0].read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
    transcript_payload = json.loads(transcript_paths[0].read_text(encoding="utf-8"))
    index_payload = json.loads(
        (artifact_dir / "agentic_session_index.json").read_text(encoding="utf-8")
    )

    assert output_payload["campaign_id"] == "camp-1"
    assert output_payload["context_profile"] == "algorithm"
    assert manifest_payload["context_profile"] == "algorithm"
    assert manifest_payload["context_profile_metadata"]["profile"] == "algorithm"
    assert transcript_payload["campaign_id"] == "camp-1"
    assert transcript_payload["context_profile"] == "algorithm"
    assert index_payload[0]["context_profile"] == "algorithm"


def test_agentic_code_session_records_not_applicable_profile_and_anchor_indexes(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        FakeCreative(),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=session,
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    assert hypothesis is not None
    assert record is not None
    pipeline.generate_code(branch, hypothesis)
    output_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in artifact_dir.glob("*/output.json")
    ]
    transcript_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in artifact_dir.glob("*/transcript.json")
    ]
    manifest_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in artifact_dir.glob("*/scratch/api_visible_prompt_manifest_*.json")
    ]
    session_index = json.loads(
        (artifact_dir / "agentic_session_index.json").read_text(encoding="utf-8")
    )
    trace_index = json.loads(
        (artifact_dir / "agentic_session_trace_index.json").read_text(
            encoding="utf-8"
        )
    )

    hypothesis_output = next(
        payload for payload in output_payloads if payload.get("patch") is None
    )
    code_output = next(
        payload for payload in output_payloads if payload.get("patch") is not None
    )
    code_transcript = next(
        payload
        for payload in transcript_payloads
        if payload["session_id"] == code_output["session_id"]
    )
    code_manifest = next(
        payload for payload in manifest_payloads if payload["call_kind"] == "code"
    )
    code_index_entry = next(
        item
        for item in session_index
        if item["session_id"] == code_output["session_id"]
    )
    code_trace_entry = next(
        item
        for item in trace_index["sessions"]
        if item["session_id"] == code_output["session_id"]
    )

    assert hypothesis_output["context_profile"] == "algorithm"
    assert code_output["context_profile"] == "not_applicable_code_phase"
    assert code_output["context_profile"] != "algorithm"
    assert code_transcript["context_profile"] == "not_applicable_code_phase"
    assert code_manifest["context_profile"] == "not_applicable_code_phase"
    assert code_index_entry["context_profile"] == "not_applicable_code_phase"
    assert code_trace_entry["context_profile"] == "not_applicable_code_phase"
    assert code_trace_entry["campaign_id"] == "camp-1"
    assert code_output["campaign_id"] == "camp-1"
    for payload in (code_output, code_index_entry, code_trace_entry):
        assert payload["problem_id"] == "toy"
        assert payload["problem_spec_hash"] == "spec-hash"
        assert payload["split_manifest_hash"] == "split-hash"
        assert payload["seed_ledger_hash"] == "seed-hash"


def test_default_agentic_session_uses_configured_timeout() -> None:
    pipeline, _, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session_timeout_sec=7.5,
        agentic_tool_max_steps=120,
        agentic_tool_max_calls=96,
        agentic_code_tool_max_calls=88,
        agentic_observation_max_chars=1500000,
    )

    session = pipeline._get_agentic_session()

    assert isinstance(session, AgenticProposalSession)
    assert session._tool_loop_config.max_wall_time_sec == 7.5
    assert session._tool_loop_config.max_steps == 120
    assert session._tool_loop_config.max_tool_calls == 96
    assert session._tool_loop_config.max_code_tool_calls == 88
    assert session._tool_loop_config.max_observation_chars == 1500000


def test_agentic_session_invalid_target_does_not_build_code_context_or_patch(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Try an invalid target.",
        change_locus="local_search",
        action="modify",
        target_file="secret/forbidden.py",
    )
    champion_root = tmp_path / "champion"
    target = champion_root / "secret" / "forbidden.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    build_calls = 0

    def build_code_context(_hypothesis):
        nonlocal build_calls
        build_calls += 1
        target.read_text(encoding="utf-8")
        raise AssertionError("code context must not be built before approval")

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=False,
                failure_reason="C3_action_target: invalid target_file",
            ),
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED
    )
    assert output.hypothesis == creative.hypothesis
    assert output.patch is None
    assert build_calls == 0
    assert creative.code_calls == 0
    assert "SECRET_TARGET_CONTENT" not in str(output)


def test_agentic_pipeline_hypothesis_request_denies_custom_code_context_read(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    target = tmp_path / "champion" / "operators" / "bounded.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    target_reads = 0

    class MaliciousSession:
        attempted = False

        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            self.attempted = True
            request.build_code_context(creative.hypothesis)
            raise AssertionError("unapproved code context was available")

    session = MaliciousSession()
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=session,
    )

    def forbidden_build_code_context(**kwargs):
        nonlocal target_reads
        target_reads += 1
        target.read_text(encoding="utf-8")
        return {"kind": "code", **kwargs}

    runtime.build_code_context = forbidden_build_code_context

    hypothesis, record = pipeline.generate_hypothesis(branch)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)

    assert hypothesis is None
    assert record is None
    assert session.attempted is True
    assert detail is not None
    assert "ContractGate-approved hypothesis" in detail
    assert runtime.code_kwargs is None
    assert target_reads == 0
    assert "SECRET_TARGET_CONTENT" not in str(pipeline.agentic_outputs)
    assert len(failures) == 1
    assert circuit.failures == []


def test_agentic_session_builds_code_context_only_after_hypothesis_contract_pass() -> None:
    creative = FakeCreative()
    events: list[str] = []

    def approve_hypothesis(_hypothesis):
        events.append("approve")
        return SimpleNamespace(passed=True, failure_reason=None)

    def build_code_context(hypothesis):
        events.append("build_code_context")
        assert hypothesis == creative.hypothesis
        return {"kind": "code"}

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=approve_hypothesis,
        )
    )

    assert events == ["approve", "build_code_context"]
    assert output.is_completed
    assert isinstance(output.hypothesis, HypothesisProposal)
    assert isinstance(output.patch, PatchProposal)


def test_agentic_completed_patch_before_approval_is_downgraded_and_cleared() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        termination_reason=AgenticTerminationReason.COMPLETED,
    )
    pipeline, branch, runtime, _, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    stored = pipeline.agentic_outputs[branch.branch_id]

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert stored.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        stored.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert stored.patch is None
    assert "before ContractGate-approved hypothesis" in (stored.failure_detail or "")
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0
    assert failures == []


def test_agentic_forced_surface_rejects_off_surface_hypothesis_before_code() -> None:
    creative = FakeCreative()
    off_surface = HypothesisProposal(
        hypothesis_text="Try route-local work despite a forced policy surface.",
        change_locus="route_local",
        action="create_new",
        target_file="operators/local_new.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=off_surface,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        persistent_forced_locus="solver_design",
        forced_surface_action="modify",
        forced_surface_target_file="policies/baseline_algorithm.py",
        forced_surface_diagnostic=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "forced_surface_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == []
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0


def test_agentic_active_problem_boundary_rejects_component_hypothesis() -> None:
    creative = FakeCreative()
    component = HypothesisProposal(
        hypothesis_text="Tune a component policy outside the active boundary.",
        change_locus="baseline_policy",
        action="modify",
        target_file="policies/baseline_policy.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=component,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    solver_design_spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                algorithm=SimpleNamespace(role="problem_object_solver_algorithm"),
            ),
            SimpleNamespace(
                name="baseline_policy",
                kind="policy",
                algorithm=SimpleNamespace(role="component_policy"),
            ),
        ]
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        problem_spec=solver_design_spec,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "active_problem_boundary_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == [detail]
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0
