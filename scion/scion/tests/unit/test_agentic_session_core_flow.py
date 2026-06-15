from __future__ import annotations

from scion.proposal.edit_protocol import source_digest_for_content
from scion.proposal.agentic_code_context import _with_code_scope_control
from scion.proposal.engine import _parse_patch
from scion.tests.unit.agentic_session_test_support import *

class AdditionalChangesShapeRetryCreative(FakeCreative):
    def __init__(self, patch: PatchProposal) -> None:
        super().__init__(patch=patch)
        self.calls = 0

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        self.calls += 1
        if self.calls == 1:
            raise ProposalValidationError(
                "additional_changes must be a JSON array, not a "
                "JSON-encoded string. Shape-only retry: preserve mechanism_changes ids."
            )
        return self.patch


class ExactReplaceShapeRetryCreative(FakeCreative):
    def __init__(self, patch: PatchProposal) -> None:
        super().__init__(patch=patch)
        self.calls = 0

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        self.calls += 1
        if self.calls == 1:
            before = "def value():\n    return 1\n"
            _parse_patch(
                {
                    "file_path": "policies/example.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(before),
                    "old_string": "return 1",
                },
                context={
                    "target_file": "policies/example.py",
                    "target_file_code": before,
                },
            )
        return self.patch


class WrongOwnerFixClient:
    def __init__(self) -> None:
        self.tool_names: list[str] = []

    def call_with_tool(self, prompt, tool, model=None, system_blocks=None, **kwargs):
        del prompt, model, system_blocks, kwargs
        self.tool_names.append(tool["name"])
        assert tool["name"] == "fix_patch"
        return {
            "premise_check": "wrong_owner",
            "premise_check_reason": (
                "verification environment is missing pytest; no patch-owned "
                "code edit can repair this"
            ),
            "file_path": "",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": "",
            "old_string": "",
            "new_string": "",
            "replace_all": False,
            "additional_changes": [],
            "test_hint": None,
        }


class NearWholeExactReplaceRetryCreative(FakeCreative):
    def __init__(self, patch: PatchProposal, *, fail_times: int = 1) -> None:
        super().__init__(patch=patch)
        self.calls = 0
        self.fail_times = fail_times

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        self.calls += 1
        if self.calls <= self.fail_times:
            _raise_near_whole_exact_replace()
        return self.patch


def _raise_near_whole_exact_replace() -> None:
    head = "def target():\n"
    body = "".join(f"    value_{idx} = {idx}\n" for idx in range(180))
    tail = "def untouched():\n    return 1\n"
    before = head + body + tail
    _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(before),
            "old_string": head + body,
            "new_string": head + "    return 2\n",
        },
        context={
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
    )


class NotSerializableExactReplaceRetryCreative(FakeCreative):
    def __init__(self, patch: PatchProposal, *, fail_times: int = 1) -> None:
        super().__init__(patch=patch)
        self.calls = 0
        self.fail_times = fail_times

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        self.calls += 1
        if self.calls <= self.fail_times:
            _raise_not_serializable_exact_replace()
        return self.patch


def _raise_not_serializable_exact_replace() -> None:
    before = "def target():\n    value = 1\n\ndef other():\n    value = 1\n"
    digest = source_digest_for_content(before)
    _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": digest,
            "old_string": "def target():\n    value = 1\n",
            "new_string": "def target():\n    value = 2\n",
            "additional_changes": [
                {
                    "file_path": "policies/example.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": digest,
                    "old_string": before,
                    "new_string": before.replace("value = 1", "value = 3", 1),
                }
            ],
        },
        context={
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
    )


def test_solver_design_telemetry_repair_rule_forbids_fake_activation() -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/scheduler.py",
            mechanism_changes=[
                {"id": "rare_large_neighborhood", "change_type": "modify"}
            ],
        )
    )
    scoped = _with_code_scope_control(
        {
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "target_file": hypothesis.target_file,
        },
        hypothesis,
        timeout_retry=False,
    )

    rule = scoped["agentic_code_scope_control"]["telemetry_repair_rule"]
    assert "exact mechanism id" in rule
    assert "real branch point" in rule
    assert "Do not force rare branches to run" in rule
    assert "max(..., 1)" in rule
    assert "fabricate positive counters" in rule


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
        if "step_id" not in event.metadata:
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


def test_agentic_session_retries_code_output_shape_only_for_additional_changes(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = AdditionalChangesShapeRetryCreative(patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    retry_context = creative.code_contexts[1]
    assert "agentic_code_schema_shape_retry_feedback" in retry_context
    assert retry_context["agentic_code_schema_shape_retry_feedback"]["field"] == (
        "additional_changes"
    )
    assert "Repair only the JSON shape" in retry_context["prior_code_failure"]
    assert any(
        event.metadata.get("failure_code") == "code_output_shape_retry"
        for event in output.transcript
    )


def test_agentic_session_retries_exact_replace_schema_preflight_feedback(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = ExactReplaceShapeRetryCreative(patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    retry_context = creative.code_contexts[1]
    feedback = retry_context["agentic_code_edit_retry_feedback"]
    assert feedback["stage"] == "schema_preflight"
    assert feedback["reason"] == "exact_replace_missing_new_string"
    assert feedback["json_pointer"] == "/new_string"
    assert feedback["minimal_json_shape"]["new_string"].endswith("for deletion>")
    assert 'new_string: ""' in retry_context["prior_code_failure"]
    assert any(
        event.metadata.get("failure_code") == "code_edit_protocol_retry"
        for event in output.transcript
    )


def test_creative_layer_fix_code_accepts_wrong_owner_no_patch() -> None:
    client = WrongOwnerFixClient()
    creative = CreativeLayer(client)

    fixed = creative.fix_code(
        {
            "problem_summary": "Synthetic problem.",
            "original_code": "def candidate():\n    return 1\n",
            "failure_detail": "V3_unit_tests: No module named pytest",
            "operator_interface_spec": "def candidate(): ...",
            "import_whitelist": "math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py",
        }
    )

    assert fixed is None
    assert client.tool_names == ["fix_patch"]


def test_agentic_session_retries_near_whole_exact_replace_feedback(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = NearWholeExactReplaceRetryCreative(patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    retry_context = creative.code_contexts[1]
    feedback = retry_context["agentic_code_edit_retry_feedback"]
    assert feedback["reason"] == "existing_file_near_whole_file_exact_replace_rejected"
    assert feedback["coverage_ratio"] > 0.85
    assert feedback["old_string_chars"] > 2000
    assert feedback["file_chars"] > feedback["old_string_chars"]
    assert feedback["source_digest"]
    assert "Split the change into smaller exact_replace edits" in feedback["guidance"]
    assert "function/block-level exact_replace edits" in feedback["final_task"]
    assert "coverage_ratio" in retry_context["prior_code_failure"]
    assert "old_string_chars" in retry_context["prior_code_failure"]
    assert "file_chars" in retry_context["prior_code_failure"]
    assert any(
        event.metadata.get("failure_code") == "code_edit_protocol_retry"
        for event in output.transcript
    )


def test_agentic_session_retries_not_serializable_exact_replace_feedback(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = NotSerializableExactReplaceRetryCreative(patch)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == patch
    assert len(creative.code_contexts) == 2
    retry_context = creative.code_contexts[1]
    feedback = retry_context["agentic_code_edit_retry_feedback"]
    assert feedback["reason"] == "exact_replace_not_serializable"
    assert feedback["json_pointer"] == "/additional_changes/0"
    assert feedback["prior_json_pointers"] == ["/"]
    assert "Use one file change for this file" in feedback["guidance"]
    assert "no-op exact_replace" in feedback["guidance"]
    assert "must use one change per file" in retry_context["prior_code_failure"]
    assert "old_string == new_string" in retry_context["prior_code_failure"]
    assert "no-op EOF/trailing newline" in feedback["final_task"]
    assert any(
        event.metadata.get("failure_code") == "code_edit_protocol_retry"
        for event in output.transcript
    )


def test_agentic_session_blocks_after_repeated_near_whole_exact_replace(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = NearWholeExactReplaceRetryCreative(patch, fail_times=2)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.patch is None
    assert output.failure_category == "schema_output_failure"
    assert output.failure_detail is not None
    assert "existing_file_near_whole_file_exact_replace_rejected" in output.failure_detail
    assert len(creative.code_contexts) == 2
    assert sum(
        1
        for event in output.transcript
        if event.metadata.get("failure_code") == "code_edit_protocol_retry"
    ) == 1


def test_agentic_session_blocks_after_repeated_not_serializable_exact_replace(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(**_valid_policy_patch_payload())
    creative = NotSerializableExactReplaceRetryCreative(patch, fail_times=2)
    context = _context(tmp_path)
    session = AgenticProposalSession(
        creative,
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
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.patch is None
    assert output.failure_category == "schema_output_failure"
    assert output.failure_detail is not None
    assert "exact_replace_not_serializable" in output.failure_detail
    assert len(creative.code_contexts) == 2
    assert sum(
        1
        for event in output.transcript
        if event.metadata.get("failure_code") == "code_edit_protocol_retry"
    ) == 1


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
        "one primary mechanism"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert (
        "minimal integration needed to reach the active solver path"
        in retry_context["agentic_code_scope_control"]["required_shape"]
    )
    assert any(
        event.message == "Retrying patch generation with compact timeout scope."
        for event in output.transcript
    )


def test_agentic_session_records_duplicate_code_premise_check_as_diagnostic(
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

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is patch
    assert output.failure_category is None
    assert output.structured_rejection is None
    assert output.failure_ledger["entry_count"] == 0
    duplicate_events = [
        event
        for event in output.transcript
        if event.metadata.get("result_kind") == "duplicate_diagnostic"
    ]
    assert duplicate_events
    assert duplicate_events[-1].metadata["gate_action"] == "diagnostic"
    assert len(creative.code_contexts) == 1


def test_agentic_session_records_contradicted_code_premise_check_as_diagnostic(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a bounded material variant of an existing relocation mechanism."
        ),
        change_locus="route_local",
        action="modify",
        target_file="operators/local_a.py",
        target_weakness="Existing relocation may miss a bounded variant.",
        expected_effect="Improve distance by changing trigger and scoring.",
    )
    patch = PatchProposal(
        file_path="operators/local_a.py",
        action="modify",
        code_content="def apply(solution):\n    return solution\n",
        premise_check="contradicted",
        premise_check_reason=(
            "Visible code has a near-existing relocation capability, but this "
            "patch implements the approved material variant."
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
            hypothesis_context={"seed": "contradicted-diagnostic"},
            build_code_context=lambda _hypothesis: {
                "target_file_code": "def apply(solution):\n    return solution\n"
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is patch
    assert output.failure_category is None
    assert output.structured_rejection is None
    premise_events = [
        event
        for event in output.transcript
        if event.metadata.get("diagnostic_kind") == "mechanism_premise_warning"
    ]
    assert premise_events
    assert premise_events[-1].metadata["gate_action"] == "diagnostic"
    assert premise_events[-1].metadata["quality_block"] is False


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
    ] == [
        "patch_graph_failure",
        "patch_graph_failure",
        "structured_output_retry_exhausted",
    ]
    retry_entry = output.failure_ledger["entries"][1]
    assert retry_entry["source"] == "code_retry_preview_failure"
    assert retry_entry["repair_attempt"] == 1
    assert retry_entry["attempt_index"] == 1
    assert retry_entry["session_index"] == 1
    assert artifact["failure_ledger"] == output.failure_ledger
    assert inspected["failure_ledger"]["first_root_cause"] == "patch_graph_failure"
    assert inspected["failure_ledger"]["latest_failure"] == (
        "structured_output_retry_exhausted"
    )
    assert validate_agentic_session_artifact(artifact).ok is True


def test_agentic_session_smoke_repair_502_is_transient_api_failure(
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

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.failure_category == "llm_transient_api_error"
    assert len(creative.code_contexts) == 2
    assert "prior_code_failure" in creative.code_contexts[1]
    assert "algorithm smoke did not pass" in creative.code_contexts[1][
        "prior_code_failure"
    ]
    assert output.failure_ledger["first_root_cause"] == "algorithm_smoke_failure"
    assert output.failure_ledger["latest_failure"] == "llm_transient_api_error"
    assert [
        entry["category"] for entry in output.failure_ledger["entries"]
    ] == [
        "algorithm_smoke_failure",
        "algorithm_smoke_failure",
        "llm_transient_api_error",
    ]
    retry_entry = output.failure_ledger["entries"][1]
    assert retry_entry["source"] == "code_retry_preview_failure"
    assert retry_entry["repair_attempt"] == 1
    assert retry_entry["attempt_index"] == 1
    assert retry_entry["session_index"] == 1
    assert artifact["failure_category"] == "llm_transient_api_error"
    assert artifact["failure_ledger"] == output.failure_ledger
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
