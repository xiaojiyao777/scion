from __future__ import annotations

from scion.core.models import MechanismChange
from scion.tests.unit.agentic_session_test_support import *


class _LedgerAlgorithmSmokeTool:
    name = "proposal.algorithm_smoke"
    input_schema = AlgorithmSmokeInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    read_only = True
    concurrency_safe = True
    max_result_chars = 60000

    def call(self, args, context: ProposalToolContext) -> ProposalObservation:
        del args
        return ProposalObservation(
            observation_id="algorithm-smoke-representative-ledger",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="algorithm_smoke",
            summary="Algorithm smoke passed with provider representative cases.",
            structured_payload={
                "passed": True,
                "status": "passed",
                "failure_code": "",
                "runtime_smoke": {
                    "passed": True,
                    "runtime_smoke_run": True,
                    "selected_surface": "solver_design",
                    "case_count": 2,
                    "selected_case_count": 2,
                    "attempted_case_count": 2,
                    "provider_hook_used": True,
                    "provider_hook_name": "solver_design_smoke_cases",
                    "provider_case_count": 2,
                    "provider_case_attempted_count": 2,
                    "case_execution_ledger": [
                        {
                            "label": "provider_small",
                            "case": "cases/small.vrp",
                            "case_path_ref": "provider:cases/small.vrp",
                            "seed": 11,
                            "case_source": "provider_representative",
                            "provider_hook_used": True,
                            "provider_hook_name": "solver_design_smoke_cases",
                            "attempted": True,
                            "success": True,
                            "failure": False,
                            "runtime_audit": {
                                "solver_algorithm_active": True,
                                "solver_algorithm_errors": 0,
                                "fallback_emitted": False,
                            },
                            "selected_surface": {
                                "active": True,
                                "errors": 0,
                                "fallback": False,
                            },
                            "duration_ms": 12,
                            "case_digest": "case-small-digest",
                            "run_digest": "run-small-digest",
                        },
                        {
                            "label": "provider_medium",
                            "case": "cases/medium.vrp",
                            "case_path_ref": "provider:cases/medium.vrp",
                            "seed": 13,
                            "case_source": "provider_representative",
                            "provider_hook_used": True,
                            "provider_hook_name": "solver_design_smoke_cases",
                            "attempted": True,
                            "success": True,
                            "failure": False,
                            "runtime_audit": {
                                "solver_algorithm_active": True,
                                "solver_algorithm_errors": 0,
                                "fallback_emitted": False,
                            },
                            "selected_surface": {
                                "active": True,
                                "errors": 0,
                                "fallback": False,
                            },
                            "duration_ms": 24,
                            "case_digest": "case-medium-digest",
                            "run_digest": "run-medium-digest",
                        },
                    ],
                },
            },
        )


class _RepairPathLedgerAlgorithmSmokeTool(_LedgerAlgorithmSmokeTool):
    def __init__(self) -> None:
        self.call_count = 0

    def call(self, args, context: ProposalToolContext) -> ProposalObservation:
        observation = super().call(args, context)
        self.call_count += 1
        payload = json.loads(json.dumps(observation.structured_payload))
        runtime_smoke = payload["runtime_smoke"]
        if self.call_count == 1:
            payload["passed"] = False
            payload["status"] = "failed"
            payload["failure_code"] = "algorithm_smoke_runtime_failure"
            payload["primary_issue"] = "synthetic repair-path smoke failure"
            runtime_smoke["passed"] = False
            runtime_smoke["runtime_audit_failure"] = {
                "category": "synthetic_repair_path_failure",
                "detail": "first smoke call failed to exercise repair retry",
            }
        return ProposalObservation(
            observation_id=f"algorithm-smoke-repair-ledger-{self.call_count}",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="algorithm_smoke",
            summary=(
                "Algorithm smoke failed before repair with provider cases."
                if self.call_count == 1
                else "Algorithm smoke passed after repair with provider cases."
            ),
            structured_payload=payload,
            is_error=False,
        )


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


def test_agentic_session_persists_algorithm_smoke_case_execution_evidence(
    tmp_path: Path,
) -> None:
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["proposal.algorithm_smoke"] = _LedgerAlgorithmSmokeTool()
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=registry,
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed_context": "smoke-ledger-test"},
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

    smoke_refs = [
        Path(ref)
        for ref in output.tainted_artifact_refs
        if "algorithm_smoke_execution_evidence" in ref
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert len(smoke_refs) == 1

    evidence = json.loads(smoke_refs[0].read_text(encoding="utf-8"))
    ledger = evidence["case_execution_ledger"]
    assert evidence["artifact_kind"] == "algorithm_smoke_execution_evidence"
    assert evidence["provider_hook_used"] is True
    assert evidence["provider_case_count"] == 2
    assert evidence["provider_case_attempted_count"] == 2
    assert [item["label"] for item in ledger] == [
        "provider_small",
        "provider_medium",
    ]
    assert all(item["attempted"] is True for item in ledger)
    assert all(item["success"] is True for item in ledger)
    assert all(item["case_path_ref"].startswith("provider:") for item in ledger)
    assert {item["case_digest"] for item in ledger} == {
        "case-small-digest",
        "case-medium-digest",
    }
    assert evidence["payload_hash"]
    assert evidence["raw_payload_omitted"] is True

    output_artifacts = [
        Path(ref) for ref in output.tainted_artifact_refs if Path(ref).name == "output.json"
    ]
    assert output_artifacts
    output_artifact = json.loads(output_artifacts[0].read_text(encoding="utf-8"))
    compact_metadata = [
        event.get("metadata", {})
        for event in output_artifact["compact_transcript"]
        if event.get("metadata", {}).get("tool_name") == "proposal.algorithm_smoke"
    ]
    assert compact_metadata
    smoke_metadata = compact_metadata[-1]
    assert smoke_metadata["algorithm_smoke_execution_evidence_ref"] == str(smoke_refs[0])
    assert smoke_metadata["runtime_smoke_provider_hook_used"] is True
    assert smoke_metadata["runtime_smoke_provider_case_count"] == 2
    assert smoke_metadata["runtime_smoke_provider_case_attempted_count"] == 2
    assert [item["label"] for item in smoke_metadata["runtime_smoke_case_execution_ledger"]] == [
        "provider_small",
        "provider_medium",
    ]


def test_agentic_session_repair_retry_preserves_algorithm_smoke_provider_evidence(
    tmp_path: Path,
) -> None:
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    registry = ProposalToolRegistry.default_read_only()
    smoke_tool = _RepairPathLedgerAlgorithmSmokeTool()
    registry._tools["proposal.algorithm_smoke"] = smoke_tool
    first_patch = PatchProposal(**_valid_policy_patch_payload())
    repaired_patch = PatchProposal(
        **_valid_policy_patch_payload(
            code_content=_valid_policy_patch_payload()["code_content"].replace(
                "return 0.35",
                "return 0.36",
            )
        )
    )
    creative = SequentialPatchCreative([first_patch, repaired_patch])
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=registry,
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed_context": "smoke-repair-ledger-test"},
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

    smoke_refs = [
        Path(ref)
        for ref in output.tainted_artifact_refs
        if "algorithm_smoke_execution_evidence" in ref
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == repaired_patch
    assert smoke_tool.call_count == 2
    assert len(smoke_refs) == 2

    evidences = [json.loads(ref.read_text(encoding="utf-8")) for ref in smoke_refs]
    assert [evidence["passed"] for evidence in evidences] == [False, True]
    for evidence in evidences:
        ledger = evidence["case_execution_ledger"]
        assert evidence["provider_hook_used"] is True
        assert evidence["provider_case_count"] == 2
        assert evidence["provider_case_attempted_count"] == 2
        assert [item["label"] for item in ledger] == [
            "provider_small",
            "provider_medium",
        ]
        assert all(item["provider_hook_used"] is True for item in ledger)
        assert all(item["attempted"] is True for item in ledger)
        assert all(item["case_digest"] for item in ledger)

    output_artifacts = [
        Path(ref) for ref in output.tainted_artifact_refs if Path(ref).name == "output.json"
    ]
    assert output_artifacts
    output_artifact = json.loads(output_artifacts[0].read_text(encoding="utf-8"))
    smoke_metadata = [
        event.get("metadata", {})
        for event in output_artifact["compact_transcript"]
        if event.get("metadata", {}).get("tool_name") == "proposal.algorithm_smoke"
    ]
    assert len(smoke_metadata) == 2
    assert [item["algorithm_smoke_execution_evidence_ref"] for item in smoke_metadata] == [
        str(smoke_refs[0]),
        str(smoke_refs[1]),
    ]
    for metadata in smoke_metadata:
        assert metadata["runtime_smoke_provider_hook_used"] is True
        assert metadata["runtime_smoke_provider_case_count"] == 2
        assert metadata["runtime_smoke_provider_case_attempted_count"] == 2
        assert [
            item["label"]
            for item in metadata["runtime_smoke_case_execution_ledger"]
        ] == ["provider_small", "provider_medium"]


def test_prompt_manifest_counts_rendered_provider_prompt_not_raw_context(
    tmp_path: Path,
) -> None:
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    trace_dir = tmp_path / "llm-traces"
    client = CapturingToolClient()
    creative = CreativeLayer(client, trace_dir=str(trace_dir))
    context = _context(tmp_path, policy=_tool_enabled_policy())
    raw_only_blob = "RAW_CONTEXT_ONLY_NOT_RENDERED" * 2000

    output = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
    ).run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "problem_summary": "Synthetic problem.",
                "research_surfaces": "surface: search_policy",
                "objective_policy_guidance": "Minimize cost.",
                "champion_operators_code": "def baseline_time_fraction(): pass",
                "champion_stats": "champion v1",
                "raw_prompt_context_only": raw_only_blob,
            },
            build_code_context=lambda _hypothesis: {
                "kind": "code",
                "problem_summary": "Synthetic problem.",
                "target_file_code": "def mutate(x):\n    return x\n",
                "raw_prompt_context_only": raw_only_blob,
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
        )
    )

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in ref
    ]
    traces = {
        payload["request_kind"]: payload
        for payload in (
            json.loads(path.read_text(encoding="utf-8"))
            for path in trace_dir.glob("*.json")
        )
    }

    assert output.status == AgenticProposalStatus.COMPLETED
    assert {"hypothesis", "code"}.issubset(traces)
    for manifest in manifests:
        trace = traces[manifest["call_kind"]]
        system_chars = sum(len(block["text"]) for block in trace["system_blocks"])
        user_chars = len(trace["user_prompt"])
        assert manifest["rendered_prompt_available"] is True
        assert manifest["char_budget"]["user_prompt_chars"] == user_chars
        assert manifest["char_budget"]["provider_visible_total_chars"] == (
            system_chars + user_chars
        )
        assert manifest["prompt_hash"] == trace["prompt_hash"]
        assert "raw_prompt_context_only" not in manifest["section_names"]
        assert "raw_prompt_context_only" in manifest["raw_context_audit"][
            "top_level_keys"
        ]
        assert manifest["raw_context_audit"]["api_visible_prompt"] is False
        assert manifest["raw_context_audit"]["json_char_count"] > manifest[
            "char_budget"
        ]["provider_visible_total_chars"]


def test_agentic_session_writes_session_to_trace_index(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    trace_dir = campaign_dir / "llm_traces"
    artifact_store = FileAgenticSessionArtifactStore(campaign_dir / "agentic_sessions")
    client = CapturingToolClient()
    creative = CreativeLayer(client, trace_dir=str(trace_dir))
    context = _context(tmp_path, policy=_tool_enabled_policy())

    output = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
    ).run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "problem_summary": "Synthetic problem.",
                "research_surfaces": "surface: search_policy",
                "objective_policy_guidance": "Minimize cost.",
                "champion_operators_code": "def baseline_time_fraction(): pass",
                "champion_stats": "champion v1",
            },
            build_code_context=lambda _hypothesis: {
                "kind": "code",
                "problem_summary": "Synthetic problem.",
                "target_file_code": "def mutate(x):\n    return x\n",
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
        )
    )

    index_path = campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    session_entry = next(
        item for item in index["sessions"] if item["session_id"] == output.session_id
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert index["artifact_kind"] == "agentic_session_trace_index"
    assert index["trace_count"] >= 2
    assert session_entry["final_status"] == "completed"
    assert session_entry["final_artifact_ref"].endswith("/output.json")
    assert session_entry["hypothesis_trace_ids"]
    assert session_entry["code_trace_ids"]
    assert not contains_absolute_path(index)
    for trace in session_entry["traces"]:
        assert trace["request_kind"] in {"hypothesis", "code"}
        assert trace["attempt_number"] == 1
        assert trace["phase"] in {"draft_hypothesis", "draft_patch"}
        assert trace["final_status"] == "ok"
        assert trace["trace_ref"].startswith("llm_traces/")
        assert trace["prompt_manifest_artifact_ref"]
        assert trace["prompt_visibility_ledger_digest"]
        trace_payload = json.loads(
            (campaign_dir / trace["trace_ref"]).read_text(encoding="utf-8")
        )
        assert trace_payload["prompt_visibility_ledger"]["entry_count"] > 0


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


def test_algorithm_smoke_non_activation_failure_keeps_algorithm_smoke_category() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-runtime",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-runtime",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found runtime issues.",
        structured_payload={
            "passed": False,
            "failure_class": "runtime_execution_failure",
            "primary_issue": "candidate runtime raised ValueError",
            "subprocess": {
                "error_category": "runtime_exception",
                "detail": "ValueError: bad candidate patch",
            },
        },
        is_error=False,
    )

    category = agentic_session_module._preview_failure_category([observation])
    detail = agentic_session_module._latest_preview_failure_detail([observation])

    assert (
        category
        == agentic_session_module.AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE
    )
    assert detail is not None
    assert "candidate runtime raised ValueError" in detail
    assert "proposal_activation_diagnostic" not in detail


def test_algorithm_smoke_activation_diagnostic_is_non_blocking() -> None:
    payload = {
        "passed": False,
        "failure_class": "activation_not_observed_diagnostic",
        "diagnostic_passed": True,
        "primary_issue": "telemetry guard failed",
        "activation_diagnostic": {
            "category": "proposal_activation_diagnostic",
            "code": "proposal_activation_diagnostic",
            "activation_diagnostic_kind": "instrumentation_missing",
            "source": "runtime_smoke.telemetry_guard",
            "telemetry_failure_code": (
                "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
            ),
            "telemetry_failure_mechanism": "late_probe",
            "telemetry_failure_category": "activation",
            "telemetry_failure_field": (
                "solver_algorithm_context_records.late_probe_iterations"
            ),
            "repair_guidance": [
                "Add context.record_iteration('late_probe', positive_count)."
            ],
        },
        "repair_hints": [
            "Add context.record_iteration('late_probe', positive_count)."
        ],
    }
    observation = ProposalObservation(
        observation_id="smoke-diagnostic",
        session_id="session-diagnostic",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-diagnostic",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload=payload,
        is_error=False,
    )
    state = AgenticProposalSessionState(
        session_id="session-diagnostic",
        campaign_id="camp-1",
        branch_id="branch-1",
    )

    category = agentic_session_module._preview_failure_category([observation])
    detail = agentic_session_module._latest_preview_failure_detail([observation])

    assert (
        category
        == agentic_session_module.AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
    )
    assert detail is None
    assert state.failure_ledger == []


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


def test_agentic_session_repairs_telemetry_identity_with_delta_feedback(
    tmp_path: Path,
) -> None:
    mechanism_changes = (
        MechanismChange(id="granular_intensify", change_type="add"),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Add a granular neighborhood intensification pass.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        novelty_signature={
            "budget_pattern": "lower_baseline_fraction",
            "round_limit_pattern": "fixed_small_cap",
        },
        mechanism_changes=mechanism_changes,
    )
    bad_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    context.record_move('alns', attempted=1, accepted=0)\n"
            "    return 0.35\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 10\n"
        ),
        mechanism_changes=mechanism_changes,
    )
    good_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=bad_patch.code_content.replace(
            "context.record_move('alns'",
            "context.record_move('granular_intensify'",
        ),
        mechanism_changes=mechanism_changes,
    )
    creative = SequentialPatchCreative(
        [bad_patch, good_patch],
        hypothesis=hypothesis,
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
    assert len(creative.code_contexts) == 2
    repair_context = creative.code_contexts[1]
    feedback = repair_context["agentic_code_self_check_feedback"]
    assert feedback["failure_code"] == "code_stage_telemetry_identity_mismatch"
    assert feedback["offending_telemetry_ids"] == ["alns"]
    assert feedback["protected_mechanism_ids"] == ["granular_intensify"]
    assert feedback["offending_telemetry_usages"] == [
        {
            "mechanism_id": "alns",
            "file_path": "policies/search_policy.py",
            "json_pointer": "/code_content",
            "line": 2,
            "column": 5,
            "helper": "record_move",
            "receiver": "context",
            "line_text": "context.record_move('alns', attempted=1, accepted=0)",
            "usage_kind": "new_or_increased_generated_telemetry",
            "repair_guidance": (
                "Replace this telemetry mechanism id with an approved "
                "protected mechanism id, or remove this newly added "
                "mechanism-evidence call."
            ),
        }
    ]


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
