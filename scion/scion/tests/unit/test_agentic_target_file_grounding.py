from __future__ import annotations

import json
from pathlib import Path

from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.proposal.agentic_session_hypothesis import (
    _observations_include_sufficient_target_context,
)
from scion.proposal.agentic_observation_ledger.payloads import read_receipt_from_entry
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.tests.unit.agentic_session_test_support import *


class SequentialHypothesisCreative(FakeCreative):
    def __init__(self, hypotheses: list[HypothesisProposal]) -> None:
        super().__init__(hypothesis=hypotheses[-1])
        self.hypotheses = list(hypotheses)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.hypotheses:
            return self.hypothesis
        return self.hypotheses.pop(0)


def _scheduler_hypothesis(text: str) -> HypothesisProposal:
    mechanism_id = "stagnation_repair_scheduler"
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/scheduler.py",
            hypothesis_text=text,
            target_weakness=(
                "The active scheduler keeps the same repair ordering during "
                "distance stagnation."
            ),
            expected_effect=(
                "Improve total_distance by escalating bounded repair choices "
                "only after stagnation."
            ),
            mechanism_changes=[
                {"id": mechanism_id, "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "alns_vns_scheduler",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "stagnation_triggered_repair_ordering",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_scheduler_checks",
            },
            expected_telemetry={
                "activity": ["solver_algorithm_search_iterations"],
                "activation": [
                    f"solver_algorithm_context_records.{mechanism_id}_iterations",
                    f"solver_algorithm_phase_runtime_ms.{mechanism_id}",
                ],
                "effect": [
                    f"solver_algorithm_phase_improvement_counts.{mechanism_id}"
                ],
                "budget": [
                    f"solver_algorithm_phase_runtime_ms.{mechanism_id}"
                ],
            },
        )
    )


def test_solver_design_existing_target_file_is_read_then_redrafted(
    tmp_path: Path,
) -> None:
    first = _scheduler_hypothesis(
        "Add stagnation_repair_scheduler to the active solver scheduler."
    )
    second = _scheduler_hypothesis(
        "After reading scheduler.py, add stagnation_repair_scheduler as a "
        "bounded repair-ordering change inside the existing scheduler."
    )
    creative = SequentialHypothesisCreative([first, second])
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-grounding",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-grounding"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == second
    assert len(creative.hypothesis_contexts) == 2
    assert "agentic_hypothesis_grounding_rejections" not in creative.hypothesis_contexts[0]

    retry_context = creative.hypothesis_contexts[1]
    grounding_feedback = retry_context["agentic_hypothesis_grounding_rejections"][0]
    assert grounding_feedback["failure_code"] == (
        "solver_design_target_not_in_hypothesis_prompt"
    )
    assert grounding_feedback["target_file"] == "policies/baseline_modules/scheduler.py"
    assert grounding_feedback["preserve_hypothesis"]["target_file"] == (
        "policies/baseline_modules/scheduler.py"
    )
    target_observations = [
        observation
        for observation in retry_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"]
        == "policies/baseline_modules/scheduler.py"
    ]
    assert target_observations
    target_payload = target_observations[0]["structured_payload"]
    assert target_payload["readable"] is True
    assert target_payload["truncated"] is False
    assert "class _ALNSVNSSolver" in target_payload["content_preview"]

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]
    assert [manifest["call_kind"] for manifest in manifests[:2]] == [
        "hypothesis",
        "hypothesis_grounding_retry",
    ]
    first_manifest, retry_manifest = manifests[:2]
    assert not any(
        item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == "policies/baseline_modules/scheduler.py"
        for item in first_manifest["included_observations"]
    )
    retry_items = [
        item
        for item in retry_manifest["included_observations"]
        if item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == "policies/baseline_modules/scheduler.py"
    ]
    assert retry_items
    assert retry_items[0]["included_in_prompt_for_call"] is True
    assert retry_items[0]["full_content_included_in_prompt"] is True
    assert retry_items[0]["full_content_visible_in_rendered_prompt"] is True
    assert retry_items[0]["full_content_visible_in_dedicated_source_section"] is True
    assert retry_items[0]["full_content_visible_anywhere_in_rendered_prompt"] is True
    full_read_status = retry_manifest["section_statuses"][
        "solver_design_full_algorithm_file_reads"
    ]
    assert full_read_status["status"] == "included"
    assert "solver_design_full_algorithm_file_reads" not in retry_manifest[
        "truncated_sections"
    ]

    scheduler_receipts = [
        receipt
        for receipt in output.observation_ledger["read_receipts"]
        if receipt.get("tool_name") == "context.read_algorithm_file"
        and receipt.get("file_path") == "policies/baseline_modules/scheduler.py"
    ]
    assert scheduler_receipts
    assert scheduler_receipts[0]["included_in_prompt_for_call"] is False
    assert scheduler_receipts[0]["prompt_inclusion_status"] == (
        "not_asserted_by_read_receipt"
    )


def test_algorithm_slice_receipt_is_not_sufficient_target_file_grounding() -> None:
    target_args = {
        "surface": "solver_design",
        "file_path": "policies/baseline_modules/local_search.py",
        "max_chars": 24000,
    }
    slice_observation = ProposalObservation(
        observation_id="slice-1",
        session_id="session",
        tool_name="context.read_algorithm_slice",
        tool_call_id="tool-1",
        observation_type="algorithm_slice",
        summary="slice",
        structured_payload={
            "file_path": "policies/baseline_modules/local_search.py",
            "slice_id": "local_search.two_opt_star",
            "content": "def _two_opt_star(...): ...",
            "content_digest": "digest",
            "line_start": 10,
            "line_end": 80,
        },
    )

    assert not _observations_include_sufficient_target_context(
        [slice_observation],
        target_args,
    )


def test_truncated_algorithm_file_grounding_carries_digest_and_line_coverage() -> None:
    target_args = {
        "surface": "solver_design",
        "file_path": "policies/baseline_modules/large.py",
        "max_chars": 24000,
    }
    file_observation = ProposalObservation(
        observation_id="file-1",
        session_id="session",
        tool_name="context.read_algorithm_file",
        tool_call_id="tool-1",
        observation_type="solver_algorithm_file",
        summary="large file",
        structured_payload={
            "file_path": "policies/baseline_modules/large.py",
            "readable": True,
            "content_preview": "A = 1\nB = 2\n",
            "truncated": True,
            "size_chars": 50000,
            "max_chars": 24000,
            "line_start": 1,
            "line_end": 2,
            "covered_line_count": 2,
            "total_line_count": 1000,
            "content_digest": "sha256:large",
        },
    )

    assert _observations_include_sufficient_target_context(
        [file_observation],
        target_args,
    )


def test_forced_solver_design_target_is_grounded_before_first_hypothesis(
    tmp_path: Path,
) -> None:
    hypothesis = _scheduler_hypothesis(
        "Modify the forced scheduler target after reading its source."
    )
    creative = SequentialHypothesisCreative([hypothesis])
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file="policies/baseline_modules/scheduler.py",
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "artifacts-forced")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-forced-target-grounding",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert len(creative.hypothesis_contexts) == 1
    first_context = creative.hypothesis_contexts[0]
    assert "agentic_hypothesis_grounding_rejections" not in first_context
    assert "agentic_expected_telemetry_guidance" in first_context
    target_reads = [
        observation
        for observation in first_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"]
        == "policies/baseline_modules/scheduler.py"
    ]
    target_slices = [
        observation
        for observation in first_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_slice"
        and observation["structured_payload"]["file_path"]
        == "policies/baseline_modules/scheduler.py"
    ]
    target_registries = [
        observation
        for observation in first_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_operator_registry"
    ]
    tool_names = [
        observation["tool_name"]
        for observation in first_context["agentic_tool_observations"]
    ]
    assert target_reads
    assert target_slices
    assert target_registries
    assert tool_names.index("context.read_algorithm_slice") < tool_names.index(
        "context.read_algorithm_file"
    )
    assert target_reads[0]["structured_payload"]["truncated"] is False
    assert "class _ALNSVNSSolver" in target_reads[0]["structured_payload"][
        "content_preview"
    ]
    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]
    assert manifests
    section_status = manifests[0]["section_statuses"]["active_solver_map_receipts"]
    assert section_status["status"] == "included"
    rendered_manifest = json.dumps(manifests[0], sort_keys=True)
    assert "SECRET_VALIDATION" not in rendered_manifest
    assert "SECRET_FROZEN" not in rendered_manifest
    assert any(
        receipt.get("tool_name") == "context.read_algorithm_slice"
        and receipt.get("slice_id")
        and receipt.get("selection_source") == "planner_map_followup_required"
        for receipt in output.observation_ledger["read_receipts"]
    )
    assert any(
        receipt.get("tool_name") == "context.read_operator_registry"
        and receipt.get("registry_id")
        and receipt.get("selection_source") == "planner_map_followup_required"
        for receipt in output.observation_ledger["read_receipts"]
    )
    assert "SECRET_VALIDATION" not in json.dumps(
        output.observation_ledger,
        sort_keys=True,
    )
    assert "SECRET_FROZEN" not in json.dumps(
        output.observation_ledger,
        sort_keys=True,
    )


def test_read_receipt_is_not_prompt_inclusion_but_manifest_is() -> None:
    observation = _algorithm_read_observation(
        "context.read_algorithm_file",
        _algorithm_file_payload(
            "policies/baseline_modules/scheduler.py",
            max_chars=24000,
            preview_chars=120,
            size_chars=120,
        ),
    )
    manifest = build_api_visible_prompt_manifest(
        session_id="session-target-grounding",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[observation],
        call_index=1,
        system_blocks=[],
        user_prompt=json.dumps([_observation_prompt_payload(observation)]),
    )
    receipt = read_receipt_from_entry(
        {
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "file_path": "policies/baseline_modules/scheduler.py",
            "coverage": {
                "max_chars": 24000,
                "truncated": False,
                "coverage_status": "full",
                "content_preview_chars": 120,
                "size_chars": 120,
            },
        }
    )

    included = manifest["included_observations"][0]
    assert included["included_in_prompt_for_call"] is True
    assert included["full_content_included_in_prompt"] is True
    assert included["full_content_visible_in_rendered_prompt"] is True
    assert receipt["included_in_prompt_for_call"] is False
    assert receipt["full_content_included_in_prompt"] is False


def test_full_algorithm_reads_project_outside_generic_observation_cap() -> None:
    marker_block = "\n".join(
        [
            "def _route_removal(): pass",
            "def _shaw_removal(): pass",
            "def _regret_insertion(): pass",
            "def _random_removal(): pass",
        ]
    )
    full_source = (
        marker_block
        + "\n"
        + "# filler\n" * 9000
        + "\nFULL_SOURCE_END_MARKER\n"
    )
    observation = _algorithm_read_observation(
        "context.read_algorithm_file",
        {
            "file_path": "policies/baseline_modules/destroy_repair.py",
            "readable": True,
            "active": True,
            "source": "champion_snapshot",
            "content_preview": full_source,
            "truncated": False,
            "size_chars": len(full_source),
            "max_chars": len(full_source),
            "digest": "destroy-repair-digest",
        },
    )
    prompt_context = {
        "problem_summary": "CVRP.",
        "research_surfaces": "solver_design",
        "champion_operators_code": "",
        "champion_stats": "",
        "agentic_tool_observations": [_observation_prompt_payload(observation)],
    }
    system_blocks, user_prompt = _split_hypothesis_context(prompt_context)
    rendered = "\n".join(block["text"] for block in system_blocks) + "\n" + user_prompt
    manifest = build_api_visible_prompt_manifest(
        session_id="session-full-read-projection",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[observation],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "## Solver-Design Full Algorithm File Reads" in rendered
    assert "def _route_removal" in rendered
    assert "def _shaw_removal" in rendered
    assert "def _regret_insertion" in rendered
    assert "def _random_removal" in rendered
    assert "FULL_SOURCE_END_MARKER" in rendered
    assert "def _route_removal" not in user_prompt
    assert "FULL_SOURCE_END_MARKER" not in user_prompt
    observation_section = user_prompt.split(
        "## Agentic Proposal Tool Observations",
        maxsplit=1,
    )[1]
    assert "content_preview_ref" in observation_section
    assert "content_preview_omitted_from_generic_observations" in observation_section
    assert '"provenance"' not in observation_section
    full_read_status = manifest["section_statuses"][
        "solver_design_full_algorithm_file_reads"
    ]
    assert full_read_status["status"] == "included"
    assert full_read_status["prompt_part"] == "system"
    assert full_read_status["cacheable"] is True
    assert full_read_status["char_count"] > 24000
    assert "solver_design_full_algorithm_file_reads" not in manifest[
        "truncated_sections"
    ]
    cacheability = manifest["provider_visible_prompt"]["cacheability"]
    assert cacheability["cache_control_block_count"] >= 1
    assert cacheability["estimated_cacheable_chars"] >= full_read_status["char_count"]
    included = manifest["included_observations"][0]
    assert included["content_preview_visible_in_rendered_prompt"] is True
    assert included["full_content_included_in_prompt"] is True
    assert included["full_content_visible_in_rendered_prompt"] is True
    assert included["full_content_visible_in_dedicated_source_section"] is True
    assert included["full_content_visible_anywhere_in_rendered_prompt"] is True
    assert included["prompt_visibility_status"] == (
        "full_content_visible_in_dedicated_source_section"
    )


def test_prompt_manifest_marks_read_surface_nested_preview_visible() -> None:
    target_preview = "def visible_surface_target():\n    return 7\n"
    support_preview = "class VisibleSurfaceSupport:\n    pass\n"
    observation = _algorithm_read_observation(
        "context.read_surface",
        {
            "surface": {"name": "solver_design", "kind": "solver_design"},
            "target_file": "policies/baseline_modules/local_search.py",
            "current_artifact": {
                "file_path": "policies/baseline_modules/local_search.py",
                "content_preview": target_preview,
                "readable": True,
                "size_chars": len(target_preview),
                "max_chars": len(target_preview),
                "truncated": False,
            },
            "support_artifacts": [
                {
                    "file_path": "policies/baseline_modules/support.py",
                    "content_preview": support_preview,
                    "readable": True,
                    "size_chars": len(support_preview),
                    "max_chars": len(support_preview),
                    "truncated": False,
                }
            ],
        },
    )
    system_blocks = [
        {
            "text": (
                "## Solver-Design Full Algorithm File Reads\n"
                f"```python\n{target_preview}```\n"
                f"```python\n{support_preview}```\n"
            )
        }
    ]

    manifest = build_api_visible_prompt_manifest(
        session_id="surface-visible",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[observation],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt="## Agentic Proposal Tool Observations\n[]",
    )

    included = manifest["included_observations"][0]
    assert included["read_receipt_only"] is False
    assert included["content_preview_visible_in_rendered_prompt"] is True
    assert included["content_preview_visible_anywhere_in_rendered_prompt"] is True
    assert included["content_projection_count"] == 2
    assert included["visible_content_projection_count"] == 2
    assert included["prompt_visibility_status"] == (
        "full_content_visible_in_dedicated_source_section"
    )


def test_prompt_manifest_marks_algorithm_slice_content_visible() -> None:
    slice_content = "def bounded_algorithm_slice():\n    return 11\n"
    observation = _algorithm_read_observation(
        "context.read_algorithm_slice",
        {
            "available": True,
            "slice_id": "slice.local_search.bounded",
            "file_path": "policies/baseline_modules/local_search.py",
            "symbols": ["bounded_algorithm_slice"],
            "content": slice_content,
            "content_digest": "slice-digest",
            "truncated": False,
            "max_chars": len(slice_content),
        },
    )
    user_prompt = (
        "## Agentic Proposal Tool Observations\n"
        + json.dumps(
            {
                "slice_reads": [
                    {
                        "slice_id": "slice.local_search.bounded",
                        "content_preview": slice_content,
                    }
                ]
            }
        )
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="slice-visible",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[observation],
        call_index=1,
        system_blocks=[],
        user_prompt=user_prompt,
    )

    included = manifest["included_observations"][0]
    assert included["read_receipt_only"] is False
    assert included["slice_id"] == "slice.local_search.bounded"
    assert included["content_preview_visible_in_rendered_prompt"] is True
    assert included["content_projections"][0]["label"] == "algorithm_slice_content"
    assert included["prompt_visibility_status"] == (
        "full_content_visible_in_rendered_prompt"
    )


def test_code_prompt_manifest_audits_target_and_integration_file_visibility() -> None:
    target_source = (
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    return context.nearest_neighbor()\n"
    )
    scheduler_source = (
        "class _ALNSVNSSolver:\n"
        "    def solve(self, instance, rng):\n"
        "        return None\n"
    )
    entrypoint_source = (
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    solver = _ALNSVNSSolver(context=context)\n"
        "    return solver.solve(instance, rng)\n"
    )
    integration_files = (
        "### policies/baseline_algorithm.py\n"
        "Provenance: branch_workspace; readable=True\n"
        "```python\n"
        f"{entrypoint_source}"
        "```\n"
        "### policies/baseline_modules/scheduler.py\n"
        "Provenance: branch_workspace; readable=True\n"
        "```python\n"
        f"{scheduler_source}"
        "```"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "policies/baseline_modules/construction.py",
        "target_file_code": target_source,
        "solver_design_branch_current_integration_files": integration_files,
        "hypothesis_text": "Add a bounded construction variant.",
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Add a bounded construction variant.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/construction.py",
            "mechanism_changes": [
                {"id": "bounded_construction_variant", "change_type": "add"}
            ],
            "expected_telemetry": {
                "activation": [
                    "solver_algorithm_context_records."
                    "bounded_construction_variant_iterations"
                ],
                "budget": [
                    "solver_algorithm_phase_runtime_ms."
                    "bounded_construction_variant"
                ],
            },
            "no_op_condition": "Keep existing construction when no bounded seed applies.",
            "risk_to_higher_priority": "Must preserve fleet_violation feasibility.",
        },
        "target_weakness": "Construction has no targeted variant.",
        "expected_effect": "Improve total_distance.",
        "problem_summary": "CVRP.",
        "problem_object": "CVRP object.",
        "solver_mechanics": "Loads baseline_algorithm.py::solve.",
        "operator_interface_spec": "solve(instance, rng, time_limit_sec, context)",
        "import_whitelist": "math, random",
        "editable_patterns": "policies/baseline_algorithm.py, policies/baseline_modules/*.py",
        "frozen_patterns": "adapter.py, solver.py",
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-code-visibility",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    ledger = manifest["code_file_visibility_ledger"]
    assert ledger["schema_version"] == "code-file-visibility-ledger.v1"
    target_record = ledger["target_file"]
    assert target_record["file_path"] == "policies/baseline_modules/construction.py"
    assert target_record["section"] == "approved_target_file_current_content"
    assert target_record["section_status"] == "included"
    assert target_record["full_content_visible_in_rendered_prompt"] is True
    target_status = manifest["section_statuses"]["approved_target_file_current_content"]
    assert target_status["prompt_part"] == "system"
    assert target_status["cacheable"] is True
    integration_records = {
        item["file_path"]: item for item in ledger["integration_files"]
    }
    assert set(integration_records) == {
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/scheduler.py",
    }
    assert all(
        item["full_content_visible_in_rendered_prompt"]
        for item in integration_records.values()
    )
    integration_status = manifest["section_statuses"]["branch_current_integration_files"]
    assert integration_status["prompt_part"] == "system"
    assert integration_status["cacheable"] is True
    hypothesis_status = manifest["section_statuses"]["hypothesis_to_implement"]
    assert hypothesis_status["status"] == "included"
    assert hypothesis_status["prompt_part"] == "user"
    assert "hypothesis_to_implement" not in manifest["truncated_sections"]
    hypothesis_section = next(
        section
        for section in manifest["sections"]
        if section["name"] == "hypothesis_to_implement"
    )
    assert hypothesis_section["char_count"] < 12000
    assert "bounded_construction_variant" in user_prompt
    assert "policies/baseline_modules/construction.py" in user_prompt
    assert target_source not in user_prompt
    assert scheduler_source not in user_prompt
    assert entrypoint_source not in user_prompt
    assert "branch_current_integration_files" not in manifest["truncated_sections"]
    cacheability = manifest["provider_visible_prompt"]["cacheability"]
    assert cacheability["estimated_cacheable_chars"] >= (
        target_status["char_count"] + integration_status["char_count"]
    )


def test_code_prompt_keeps_normal_solver_design_handoff_sections_untruncated() -> None:
    target_source = (
        "File: policies/baseline_modules/local_search.py\n"
        "```python\n"
        "def local_search():\n"
        "    return None\n"
        "```\n"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "policies/baseline_modules/local_search.py",
        "target_file_code": target_source,
        "solver_design_branch_current_integration_files": (
            "### policies/baseline_algorithm.py\n"
            "```python\n"
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return None\n"
            "```\n"
        ),
        "solver_design_api_manifest": "module api\n" + ("api_entry\n" * 600),
        "hypothesis_detail": "detail\n" + ("mechanism rationale\n" * 220),
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Add a bounded same-route reinsertion mechanism.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_changes": [
                {"id": "intra_reinsertion_vns", "change_type": "add"}
            ],
            "expected_telemetry": {
                "activation": [
                    "solver_algorithm_phase_runtime_ms.intra_reinsertion_vns"
                ]
            },
        },
        "problem_summary": "CVRP.",
        "problem_object": "problem object\n" + ("objective and boundary\n" * 180),
        "solver_mechanics": "solver mechanics\n" + ("call path and state flow\n" * 180),
        "operator_interface_spec": "interface\n" + ("function and invariant\n" * 220),
        "import_whitelist": "math, random",
        "editable_patterns": "policies/baseline_algorithm.py, policies/baseline_modules/*.py",
        "frozen_patterns": "adapter.py, solver.py",
        "agentic_resume_context": {
            "resume": {
                "model_facing_projection": {
                    "schema_version": "agentic-resume-model-projection.v1",
                    "previous_session": {
                        "termination_reason": "hypothesis_awaiting_approval"
                    },
                    "notes": "handoff\n" + ("read receipt and retry state\n" * 170),
                }
            }
        },
        "agentic_tool_observations": [
            {
                "observation_id": "obs-runtime",
                "tool_name": "feedback.query_runtime",
                "summary": "runtime feedback",
                "structured_payload": {
                    "rows": [
                        {
                            "case": f"case-{idx}",
                            "summary": "runtime and screening observation",
                        }
                        for idx in range(220)
                    ]
                },
            }
        ],
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-code-section-budgets",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    for section_name in (
        "problem_object",
        "solver_design_module_api_manifest",
        "agentic_resume_context",
        "agentic_proposal_tool_observations",
        "hypothesis_detail_audit",
    ):
        assert section_name not in manifest["truncated_sections"]
        assert manifest["section_statuses"][section_name]["status"] == "included"
