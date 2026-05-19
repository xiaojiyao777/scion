from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *

def test_agentic_session_records_tool_observations_in_evidence_and_transcript(
    tmp_path: Path,
) -> None:
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
            hypothesis_context={"seed": "hypothesis"},
            build_code_context=lambda hypothesis: {"approved": hypothesis.change_locus},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    transcript = [event.metadata for event in output.transcript]
    tool_names = [event["tool_name"] for event in transcript if "tool_name" in event]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.evidence_used
    assert "context.list_surfaces" in tool_names
    assert "context.read_problem" in tool_names
    assert "memory.query" in tool_names
    assert "feedback.query_screening" in tool_names
    assert "proposal.schema_preview" in tool_names
    assert "proposal.target_permission_preview" in tool_names
    assert "proposal.contract_preview" in tool_names
    assert "proposal.algorithm_smoke" in tool_names
    assert output.self_check.schema_valid is True
    assert output.self_check.contract_preview_passed is True
    assert creative.hypothesis_contexts[0]["agentic_tool_observations"]
    assert (
        creative.hypothesis_contexts[0]["agentic_research_diagnosis"]["schema_version"]
        == "agentic-research-diagnosis.v1"
    )
    assert (
        creative.code_contexts[0]["agentic_research_diagnosis"]["schema_version"]
        == "agentic-research-diagnosis.v1"
    )
    for event in output.transcript:
        if "tool_name" not in event.metadata:
            continue
        assert {
            "step_id",
            "tool_name",
            "status",
            "taint",
            "evidence_ref",
            "result_summary",
            "error_code",
        }.issubset(event.metadata)
        assert "structured_payload" not in event.metadata


def test_agentic_session_invalid_expected_telemetry_fails_before_code(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            expected_telemetry={"attribution": ["policy_loaded"]},
        )
    )
    creative = FakeCreative(hypothesis=hypothesis)
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
    assert creative.code_contexts == []
    assert output.self_check.schema_valid is False
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "C11_expected_telemetry" in output.failure_detail
    assert "attribution" in output.failure_detail


def test_creative_layer_renders_agentic_observations_and_research_diagnosis() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)
    diagnosis = {
        "schema_version": "agentic-research-diagnosis.v1",
        "latest_runtime_diagnosis": {
            "failure_mode_tags": ["screening_win_rate_failure"],
            "next_hypothesis_requirements": [
                "State which declared surface evidence fields are expected to change."
            ],
        },
    }
    observations = [
        {
            "tool_name": "feedback.query_runtime",
            "summary": "Returned screening-derived runtime feedback.",
            "structured_payload": {
                "research_diagnosis": diagnosis,
                "metrics_file_refs_exposed": False,
            },
        }
    ]

    creative.generate_hypothesis(
        {
            "problem_summary": "Synthetic problem.",
            "research_surfaces": "surface: search_policy",
            "objective_policy_guidance": "Minimize distance.",
            "solver_mechanics": "",
            "champion_operators_code": "def baseline_time_fraction(...): ...",
            "champion_stats": "champion v1",
            "operator_categories": "search_policy",
            "available_actions": "modify",
            "targetable_files": "policies/search_policy.py",
            "agentic_research_diagnosis": diagnosis,
            "agentic_tool_observations": observations,
        }
    )

    rendered = json.dumps(client.system_blocks, sort_keys=True) + "\n".join(
        client.prompts
    )
    assert "## Agentic Research Diagnosis" in rendered
    assert "## Agentic Proposal Tool Observations" in rendered
    assert "feedback.query_runtime" in rendered
    assert "screening_win_rate_failure" in rendered


def test_creative_layer_renders_active_boundary_novelty_requirements() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_hypothesis(
        {
            "problem_summary": "CVRP.",
            "research_surfaces": "surface: solver_design",
            "objective_policy_guidance": "Minimize fleet_violation then distance.",
            "solver_mechanics": "",
            "champion_operators_code": "def solve(...): ...",
            "champion_stats": "champion v1",
            "operator_categories": "solver_design",
            "active_problem_boundary_surfaces": "solver_design",
            "available_actions": "modify",
            "targetable_files": (
                "policies/baseline_algorithm.py, policies/baseline_modules/*.py"
            ),
            "agentic_hypothesis_constraints": {
                "active_problem_boundary_surfaces": ("solver_design",),
                "novelty_signature_requirements": {
                    "solver_design": {
                        "strategy": "semantic_signature",
                        "required_fields": [
                            "predicted_direction",
                            "target_objectives",
                            "algorithm_family",
                            "runtime_budget_strategy",
                        ],
                    }
                },
            },
        }
    )

    rendered = json.dumps(client.system_blocks, sort_keys=True) + "\n".join(
        client.prompts
    )
    assert "active problem-object research boundary" in rendered
    assert "algorithm_family" in rendered
    assert "runtime_budget_strategy" in rendered
    assert "choose the target file by mechanism ownership" in rendered
    assert "policies/baseline_algorithm.py" in rendered


def test_agentic_session_retries_code_generation_timeout_with_compact_scope(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Implement a hybrid ALNS/VNS destroy-repair route-pool solver."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_algorithm.py",
        target_weakness="The current hook is inactive.",
        expected_effect="Produce movement under solver_algorithm telemetry.",
        novelty_signature={
            "algorithm_family": "compact_timeout_retry",
            "construction_strategy": "nearest_seed",
            "improvement_strategy": "bounded_relocate",
            "acceptance_strategy": "strict_improvement",
            "runtime_budget_strategy": "time_checked_passes",
        },
    )
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    context.record_iteration('search', 1)\n"
                    "    return context.nearest_neighbor()\n"
        ),
    )
    creative = TimeoutThenPatchCreative(hypothesis=hypothesis, patch=patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_loop_config=AgenticToolLoopConfig(
            max_code_generation_timeout_retries=1,
        ),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": "policies/baseline_algorithm.py",
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            approved_hypothesis=hypothesis,
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    assert creative.code_contexts[0]["code_generation_mode"] == "compact_solver_design"
    retry_context = creative.code_contexts[1]
    assert retry_context["code_generation_mode"] == "compact_timeout_retry"
    assert "code_generation_timeout" in retry_context["prior_code_failure"]
    assert (
        "one primary construction or seeding path"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert (
        "no more than two move families"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert any(
        event.message == "Retrying patch generation with compact timeout scope."
        for event in output.transcript
    )


def test_agentic_session_stops_on_duplicate_code_premise_check(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add missing cross-route Or-opt relocation to improve route distance."
        ),
        change_locus="route_local",
        action="modify",
        target_file="operators/local_a.py",
        target_weakness="No cross-route Or-opt move is available.",
        expected_effect="Improve distance by relocating chains across routes.",
    )
    patch = PatchProposal(
        file_path="",
        action="modify",
        code_content="",
        premise_check="duplicate",
        premise_check_reason=(
            "Already-read operators/local_a.py implements cross-route Or-opt "
            "relocation, so this hypothesis duplicates the target mechanism."
        ),
    )
    creative = FakeCreative(hypothesis=hypothesis, patch=patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(creative)

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "duplicate-or-opt"},
            build_code_context=lambda _hypothesis: {
                "target_file_code": "def cross_route_or_opt():\n    return True\n"
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.termination_reason == AgenticTerminationReason.DUPLICATE_MECHANISM
    assert output.patch is None
    assert output.failure_category == "duplicate_mechanism"
    assert output.structured_rejection is not None
    assert output.structured_rejection["premise_check"] == "duplicate"
    assert output.structured_rejection["screening_allowed"] is False
    assert output.failure_ledger["first_root_cause"] == "duplicate_mechanism"
    assert output.failure_ledger["latest_failure"] == "duplicate_mechanism"
    assert output.failure_ledger["entries"][0]["phase"] == "draft_patch"
    assert len(creative.code_contexts) == 1


def test_agentic_session_retry_error_ledger_records_schema_failure(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    session = AgenticProposalSession(_HypothesisSchemaFailureCreative())

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "schema-failure"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.failure_category == "schema_output_failure"
    assert output.failure_ledger["entry_count"] == 1
    assert output.failure_ledger["first_root_cause"] == "schema_output_failure"
    assert output.failure_ledger["latest_failure"] == "schema_output_failure"
    entry = output.failure_ledger["entries"][0]
    assert entry["phase"] == "draft_hypothesis"
    assert entry["category"] == "schema_output_failure"
    assert "malformed hypothesis" in entry["detail"]


def test_agentic_session_retry_error_ledger_preserves_first_patch_graph_failure(
    tmp_path: Path,
) -> None:
    bad_patch = PatchProposal(**_valid_policy_patch_payload())
    creative = _PatchThenRetryExhaustedCreative(bad_patch)
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["proposal.contract_preview"] = _PatchGraphContractPreviewTool()
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

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    inspected = inspect_agentic_session_artifact(artifact)

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.failure_category == "structured_output_retry_exhausted"
    assert output.failure_ledger["first_root_cause"] == "patch_graph_failure"
    assert (
        output.failure_ledger["latest_failure"]
        == "structured_output_retry_exhausted"
    )
    assert [
        entry["category"] for entry in output.failure_ledger["entries"]
    ] == ["patch_graph_failure", "structured_output_retry_exhausted"]
    assert artifact["failure_ledger"] == output.failure_ledger
    assert inspected["failure_ledger"]["first_root_cause"] == "patch_graph_failure"
    assert inspected["failure_ledger"]["latest_failure"] == (
        "structured_output_retry_exhausted"
    )
    assert validate_agentic_session_artifact(artifact).ok is True


def test_agentic_session_retry_error_ledger_records_algorithm_smoke_failure(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    registry = ProposalToolRegistry.default_read_only()
    registry._tools["proposal.algorithm_smoke"] = _FailingAlgorithmSmokeTool()
    session = AgenticProposalSession(
        creative,
        tool_registry=registry,
        tool_loop_config=AgenticToolLoopConfig(max_code_repair_attempts=0),
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
    assert output.failure_category == "algorithm_smoke_failure"
    assert output.failure_ledger["first_root_cause"] == "algorithm_smoke_failure"
    assert output.failure_ledger["latest_failure"] == "algorithm_smoke_failure"

