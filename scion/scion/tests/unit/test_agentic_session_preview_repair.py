from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_agentic_session_contract_preview_failure_fails_closed(
    tmp_path: Path,
) -> None:
    bad_patch = PatchProposal(
        file_path="operators/local_a.py",
        action="modify",
        code_content="class LocalA:\n    def execute(self, solution, rng):\n        return solution\n",
    )
    creative = FakeCreative(patch=bad_patch)
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

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert output.failure_detail is not None
    assert "contract preview did not pass" in output.failure_detail
    assert output.self_check.contract_preview_passed is False
    assert output.self_check.contract_preview_codes
    assert output.self_check.contract_preview_codes[0] in output.failure_detail


def test_agentic_session_writes_api_visible_prompt_manifest_artifacts(
    tmp_path: Path,
) -> None:
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
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
            hypothesis_context={"seed_context": "manifest-test"},
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

    manifest_refs = [
        ref
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in ref
    ]
    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8")) for ref in manifest_refs
    ]
    rendered = json.dumps(manifests, sort_keys=True, default=str)

    assert output.status == AgenticProposalStatus.COMPLETED
    assert {manifest["call_kind"] for manifest in manifests} >= {"hypothesis", "code"}
    assert all(
        manifest["artifact_kind"] == "api_visible_prompt_manifest"
        for manifest in manifests
    )
    assert all(manifest["prompt_hash"] for manifest in manifests)
    assert all(manifest["raw_prompt_saved"] is False for manifest in manifests)
    assert all("section_names" in manifest for manifest in manifests)
    assert all("char_budget" in manifest for manifest in manifests)
    assert all(isinstance(manifest["section_statuses"], dict) for manifest in manifests)
    assert all(manifest["section_statuses"] for manifest in manifests)
    assert all(
        set(manifest["section_statuses"]) == set(manifest["section_names"])
        for manifest in manifests
    )
    assert all(
        status["status"] in {"included", "omitted", "truncated"}
        for manifest in manifests
        for status in manifest["section_statuses"].values()
    )
    assert any(
        manifest["included_observation_ids"] for manifest in manifests
    )
    assert '"raw_prompt":' not in rendered
    assert "def baseline_time_fraction" not in rendered
    assert "code_content" not in rendered


def test_repeated_tool_call_returns_already_read_ref_without_hiding_required_reads(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    config = AgenticToolLoopConfig(max_repeated_tool_calls=2)
    state = AgenticProposalSessionState(
        session_id="session-dedup",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-1",
        tool_loop_config=config.__dict__,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    args = {
        "surface": "search_policy",
        "detail": "full",
        "max_code_chars": 12000,
    }

    first = session._call_tool(
        context,
        state,
        AgenticProposalPhase.INSPECT_INTERFACE,
        "context.read_surface",
        args,
        selection_source="code_phase_planner",
    )
    second = session._call_tool(
        context,
        state,
        AgenticProposalPhase.INSPECT_INTERFACE,
        "context.read_surface",
        args,
        selection_source="code_phase_planner",
    )
    third = session._call_tool(
        context,
        state,
        AgenticProposalPhase.INSPECT_INTERFACE,
        "context.read_surface",
        args,
        selection_source="code_phase_planner",
    )

    assert first.is_error is False
    assert second.is_error is False
    assert second.observation_type == "already_read_ref"
    assert second.structured_payload["already_read_ref"]["observation_id"] == (
        first.observation_id
    )
    assert "current_artifact" not in second.structured_payload
    assert agentic_session_module._has_code_phase_surface_read(
        [second],
        hypothesis,
    )
    assert third.is_error is True
    assert third.failure_code == ProposalToolFailureCode.UNSUPPORTED


def test_repeated_active_solver_tool_returns_already_read_ref(
    tmp_path: Path,
) -> None:
    context = _cvrp_context_with_champion(tmp_path)
    state = AgenticProposalSessionState(
        session_id="session-active-dedup",
        campaign_id=context.campaign_id,
        branch_id=context.branch_id or "branch-cvrp",
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    first = session._call_tool(
        context,
        state,
        AgenticProposalPhase.DIAGNOSE,
        "context.read_active_solver_design",
        {"surface": "solver_design"},
    )
    second = session._call_tool(
        context,
        state,
        AgenticProposalPhase.DIAGNOSE,
        "context.read_active_solver_design",
        {"surface": "solver_design"},
    )

    assert first.is_error is False
    assert second.is_error is False
    assert second.observation_type == "already_read_ref"
    assert second.structured_payload["already_read_ref"]["observation_id"] == (
        first.observation_id
    )
    assert agentic_session_module._has_successful_tool(
        [second],
        "context.read_active_solver_design",
    )


def test_preview_failure_category_uses_specific_taxonomy() -> None:
    def observation(
        tool_name: str,
        payload: dict,
        *,
        is_error: bool = False,
        observation_type: str | None = None,
        failure_code: str | None = None,
    ) -> ProposalObservation:
        return ProposalObservation(
            observation_id=f"{tool_name}-obs",
            session_id="session-taxonomy",
            tool_name=tool_name,
            tool_call_id="call-taxonomy",
            observation_type=observation_type or tool_name.rsplit(".", 1)[-1],
            summary="preview failed",
            structured_payload=payload,
            is_error=is_error,
            failure_code=failure_code,
        )

    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.schema_preview",
                    {"passed": False, "issues": ["schema mismatch"]},
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE
    )
    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.contract_preview",
                    {
                        "passed": False,
                        "contract": {
                            "failed_checks": ["C9e_solver_design_integration"]
                        },
                    },
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.PATCH_GRAPH_FAILURE
    )
    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.contract_preview",
                    {"passed": False, "issues": ["import graph disconnected"]},
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.PATCH_GRAPH_FAILURE
    )
    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.contract_preview",
                    {"passed": False, "contract": {"failed_checks": ["C2_target"]}},
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
    )
    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.algorithm_smoke",
                    {"passed": False, "runtime_smoke": {"issues": ["runtime"]}},
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE
    )
    assert (
        agentic_session_module._preview_failure_category(
            [
                observation(
                    "proposal.contract_preview",
                    {
                        "skip_reason": "session_timeout",
                        "agentic_budget_control": True,
                    },
                    is_error=True,
                    observation_type="tool_skipped",
                    failure_code="session_timeout",
                )
            ]
        )
        == agentic_session_module.AgenticFailureCategory.AGENTIC_BUDGET_CONTROL
    )
    detail = agentic_session_module._latest_preview_failure_detail(
        [
            observation(
                "proposal.contract_preview",
                {
                    "skip_reason": "session_timeout",
                    "agentic_budget_control": True,
                },
                is_error=True,
                observation_type="tool_skipped",
                failure_code="session_timeout",
            )
        ]
    )
    assert detail == "contract preview skipped by agentic session_timeout/budget control"
    assert "runtime_exception" not in detail
    assert "tool_error" not in detail


def test_contract_preview_session_timeout_is_budget_skip_not_runtime_exception(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_wall_time_sec=0.0)
    state = AgenticProposalSessionState(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch_id=context.branch.branch_id,
        tool_loop_config=config.__dict__,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    patch = PatchProposal(**_valid_policy_patch_payload())

    observation = session._run_contract_preview_tool(
        context,
        hypothesis,
        patch,
        state,
    )
    detail = agentic_session_module._latest_preview_failure_detail([observation])
    self_check = agentic_session_module._self_check_from_previews([observation])
    category = agentic_session_module._preview_failure_category([observation])
    agentic_session_module._record_failure_ledger_entry(
        state,
        phase=AgenticProposalPhase.SELF_CHECK,
        category=category,
        detail=detail,
        source="preview_failure",
        observation=observation,
    )

    assert observation.is_error is True
    assert observation.observation_type == "tool_skipped"
    assert observation.failure_code == "session_timeout"
    assert observation.structured_payload["agentic_budget_control"] is True
    assert observation.structured_payload["skip_reason"] == "session_timeout"
    assert detail == "contract preview skipped by agentic session_timeout/budget control"
    assert "runtime_exception" not in detail
    assert "tool_error" not in detail
    assert self_check.contract_preview_passed is False
    assert self_check.contract_preview_codes == ("session_timeout", "tool_skipped")
    assert category == agentic_session_module.AgenticFailureCategory.AGENTIC_BUDGET_CONTROL
    assert state.failure_ledger[-1]["category"] == "agentic_budget_control"
    assert state.failure_ledger[-1]["failure_code"] == "session_timeout"


def test_agentic_session_repairs_two_contract_preview_failures(
    tmp_path: Path,
) -> None:
    missing_function = PatchProposal(
        **_valid_policy_patch_payload(
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.35\n"
            )
        )
    )
    bad_import = PatchProposal(
        **_valid_policy_patch_payload(
            code_content=(
                "import os\n\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.35\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            )
        )
    )
    good_patch = PatchProposal(**_valid_policy_patch_payload())
    creative = SequentialPatchCreative(
        [
            missing_function,
            bad_import,
            good_patch,
        ]
    )
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == good_patch
    assert len(creative.code_contexts) == 3
    assert "agentic_preview_feedback" in creative.code_contexts[1]
    assert "agentic_preview_feedback" in creative.code_contexts[2]
    assert creative.code_contexts[1]["previous_patch"]["code_content"] == (
        missing_function.code_content.rstrip()
    )
    assert creative.code_contexts[2]["previous_patch"]["code_content"] == (
        bad_import.code_content.rstrip()
    )


def test_agentic_session_repairs_self_reported_unresolved_patch_issue(
    tmp_path: Path,
) -> None:
    bad_payload = _valid_policy_patch_payload(
        test_hint="This generated file has a syntax error that needs fixing."
    )
    good_payload = _valid_policy_patch_payload(test_hint=None)
    creative = SequentialPatchCreative(
        [
            PatchProposal(**bad_payload),
            PatchProposal(**good_payload),
        ]
    )
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == PatchProposal(**good_payload)
    assert len(creative.code_contexts) == 2
    repair_context = creative.code_contexts[1]
    assert "agentic_code_self_check_feedback" in repair_context
    assert "syntax_error" in repair_context["prior_code_failure"]
    assert repair_context["previous_patch"]["code_content"] == bad_payload[
        "code_content"
    ].rstrip()


def test_agentic_session_rejects_self_reported_unresolved_patch_after_repair(
    tmp_path: Path,
) -> None:
    first_bad = PatchProposal(
        **_valid_policy_patch_payload(
            test_hint="This generated file has a syntax error that needs fixing."
        )
    )
    second_bad = PatchProposal(
        **_valid_policy_patch_payload(
            test_hint="The replacement is still broken and needs fixing."
        )
    )
    creative = SequentialPatchCreative([first_bad, second_bad])
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

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.patch is None
    assert output.termination_reason == AgenticTerminationReason.CODE_GENERATION_FAILED
    assert output.failure_detail is not None
    assert "self-reported unresolved code issue" in output.failure_detail
    assert "needs_fixing" in output.failure_detail
    assert len(creative.code_contexts) == 2


def test_agentic_session_contract_preview_timeout_returns_tool_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if not agentic_session_module._can_use_signal_timeout():
        pytest.skip("SIGALRM timeout is unavailable in this environment.")
    monkeypatch.setattr(
        agentic_session_module,
        "_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC",
        0.01,
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    state = AgenticProposalSessionState(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch_id=context.branch.branch_id,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry([HangingContractPreviewTool()]),
    )

    observation = session._call_tool(
        context,
        state,
        AgenticProposalPhase.SELF_CHECK,
        "proposal.contract_preview",
        {},
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RUNTIME_EXCEPTION
    assert "timed out" in observation.summary
    assert observation.structured_payload["tool_name"] == "proposal.contract_preview"
    assert state.transcript[-1].metadata["status"] == "error"
