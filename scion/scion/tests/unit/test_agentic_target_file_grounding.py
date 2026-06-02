from __future__ import annotations

import json
from pathlib import Path

from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.proposal.context_manager.code_context import (
    _build_solver_design_branch_current_integration_files,
)
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


def _solver_design_file_hypothesis(
    *,
    target_file: str,
    mechanism_id: str,
    text: str,
) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            hypothesis_text=text,
            target_weakness="Runtime feedback points at a solver-design gap.",
            expected_effect="Improve total_distance while preserving feasibility.",
            mechanism_changes=[
                {"id": mechanism_id, "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "solver_design_target_grounding_test",
                "target_file": target_file,
            },
            expected_telemetry={
                "activity": ["solver_algorithm_search_iterations"],
                "activation": [
                    f"solver_algorithm_context_records.{mechanism_id}_iterations",
                    f"solver_algorithm_phase_runtime_ms.{mechanism_id}",
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


def test_target_file_grounding_retry_resets_when_semantic_retry_changes_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scion.proposal.agentic_session_hypothesis as hypothesis_module

    target_a = "policies/baseline_modules/destroy_repair.py"
    target_b = "policies/baseline_modules/acceptance.py"
    first_a = _solver_design_file_hypothesis(
        target_file=target_a,
        mechanism_id="capacity_cluster_repair",
        text="Add capacity_cluster_repair in destroy_repair.py.",
    )
    second_a = _solver_design_file_hypothesis(
        target_file=target_a,
        mechanism_id="capacity_cluster_repair",
        text="After reading destroy_repair.py, add capacity_cluster_repair.",
    )
    first_b = _solver_design_file_hypothesis(
        target_file=target_b,
        mechanism_id="contextual_pair_weights",
        text="Switch to acceptance.py for contextual pair weights.",
    )
    second_b = _solver_design_file_hypothesis(
        target_file=target_b,
        mechanism_id="contextual_pair_weights",
        text="After reading acceptance.py, add contextual pair weights.",
    )

    class RejectTargetAOnce:
        def __init__(self) -> None:
            self.rejected = False

        def evaluate(self, hypothesis, **_kwargs):
            if (
                not self.rejected
                and str(hypothesis.target_file) == target_a
            ):
                self.rejected = True
                return SimpleNamespace(
                    is_hard_block=True,
                    premise_check="contradicted",
                    failure_category="premise_contradicted",
                    mechanism="shaw_related_removal",
                    reason="semantic retry should repair the contradicted premise",
                    fact_packet_digest="",
                    to_rejection=lambda _hypothesis: {
                        "source": "mechanism_novelty_gate",
                        "gate_name": "MechanismNoveltyGate",
                        "premise_check": "contradicted",
                        "failure_category": "premise_contradicted",
                        "mechanism": "shaw_related_removal",
                        "reason": (
                            "semantic retry should choose a different "
                            "mechanism family"
                        ),
                        "target_file": target_a,
                    },
                )
            return None

    monkeypatch.setattr(
        hypothesis_module,
        "_MECHANISM_NOVELTY_GATE",
        RejectTargetAOnce(),
    )
    creative = SequentialHypothesisCreative([first_a, second_a, first_b, second_b])
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-target-switch"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-grounding-switch",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-grounding-switch"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == second_b
    assert len(creative.hypothesis_contexts) == 4

    destroy_retry_context = creative.hypothesis_contexts[1]
    destroy_grounding = destroy_retry_context[
        "agentic_hypothesis_grounding_rejections"
    ][0]
    assert destroy_grounding["target_file"] == target_a
    assert destroy_grounding["target_context_key"].startswith(f"{target_a}@")

    semantic_retry_context = creative.hypothesis_contexts[2]
    assert "agentic_hypothesis_semantic_rejections" in semantic_retry_context
    assert "agentic_hypothesis_grounding_rejections" not in semantic_retry_context

    acceptance_retry_context = creative.hypothesis_contexts[3]
    acceptance_grounding = acceptance_retry_context[
        "agentic_hypothesis_grounding_rejections"
    ][0]
    assert acceptance_grounding["target_file"] == target_b
    assert acceptance_grounding["target_context_key"].startswith(f"{target_b}@")
    assert acceptance_grounding["retry_count_for_target"] == 1
    assert acceptance_grounding["api_visible_in_latest_prompt"] is False
    assert target_a not in json.dumps(
        acceptance_retry_context["agentic_hypothesis_grounding_rejections"],
        sort_keys=True,
    )
    acceptance_reads = [
        observation
        for observation in acceptance_retry_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_b
    ]
    assert acceptance_reads
    assert acceptance_reads[0]["structured_payload"]["readable"] is True
    assert acceptance_reads[0]["structured_payload"]["truncated"] is False

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]
    assert [manifest["call_kind"] for manifest in manifests[:4]] == [
        "hypothesis",
        "hypothesis_grounding_retry",
        "hypothesis_semantic_retry",
        "hypothesis_grounding_retry",
    ]
    third_manifest = manifests[2]
    fourth_manifest = manifests[3]
    assert not any(
        item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == target_b
        and item.get("full_content_visible_in_rendered_prompt") is True
        for item in third_manifest["included_observations"]
    )
    acceptance_items = [
        item
        for item in fourth_manifest["included_observations"]
        if item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == target_b
    ]
    assert acceptance_items
    assert acceptance_items[0]["included_in_prompt_for_call"] is True
    assert acceptance_items[0]["full_content_visible_in_rendered_prompt"] is True
    assert acceptance_items[0]["full_content_visible_in_dedicated_source_section"] is True


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


def test_prompt_manifest_writes_compact_explicit_visibility_ledger() -> None:
    full_content = "def projected_full_source():\n    return 1\n"
    truncated_content = "def partial_source():\n    return 2\n"
    full_observation = replace(
        _algorithm_read_observation(
            "context.read_algorithm_file",
            {
                "file_path": "policies/full.py",
                "readable": True,
                "content_preview": full_content,
                "truncated": False,
                "size_chars": len(full_content),
                "max_chars": len(full_content),
            },
        ),
        observation_id="full-source-observation",
    )
    truncated_observation = replace(
        _algorithm_read_observation(
            "context.read_algorithm_file",
            {
                "file_path": "policies/truncated.py",
                "readable": True,
                "content_preview": truncated_content,
                "truncated": True,
                "size_chars": len(truncated_content) * 3,
                "max_chars": len(truncated_content),
            },
        ),
        observation_id="truncated-source-observation",
    )
    receipt_observation = ProposalObservation(
        observation_id="receipt-only-observation",
        session_id="session-ledger",
        tool_name="context.list_surfaces",
        tool_call_id="tool-receipt",
        observation_type="surface_list",
        summary="receipt only",
        structured_payload={"already_observed": True},
    )
    omitted_observation = ProposalObservation(
        observation_id="omitted-observation",
        session_id="session-ledger",
        tool_name="context.hidden",
        tool_call_id="tool-hidden",
        observation_type="hidden",
        summary="not rendered",
        structured_payload={"content_preview": "not in rendered prompt"},
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="session-ledger",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[
            full_observation,
            truncated_observation,
            receipt_observation,
            omitted_observation,
        ],
        call_index=1,
        system_blocks=[
            {
                "text": (
                    "## Solver-Design Full Algorithm File Reads\n"
                    f"{full_content}\n\n"
                    "## Compact Section\n"
                    "<truncated for compact>\n"
                )
            }
        ],
        user_prompt=(
            "## Agentic Proposal Tool Observations\n"
            f"{truncated_content}\n"
            "receipt-only-observation\n"
        ),
    )

    ledger = manifest["visibility_ledger"]
    entries = ledger["entries"]
    assert ledger["schema_version"] == "prompt-visibility-ledger.v1"
    assert ledger["entry_count"] == len(entries)
    assert set(ledger["status_values"]) == {
        "full",
        "dedicated_projection",
        "summary",
        "truncated",
        "omitted",
    }
    by_ref = {
        entry.get("source_ref") or entry.get("ref"): entry for entry in entries
    }
    assert by_ref[full_observation.observation_id]["visibility_status"] == (
        "dedicated_projection"
    )
    assert by_ref[full_observation.observation_id]["projected_to_section"] == (
        "solver_design_full_algorithm_file_reads"
    )
    assert by_ref[truncated_observation.observation_id]["visibility_status"] == (
        "truncated"
    )
    assert by_ref[receipt_observation.observation_id]["visibility_status"] == (
        "summary"
    )
    assert by_ref[omitted_observation.observation_id]["visibility_status"] == (
        "omitted"
    )
    assert all("token_estimate" in entry for entry in entries)
    assert all(
        "digest" in entry
        for entry in entries
        if entry["visibility_status"] != "omitted"
    )
    assert manifest["visibility_ledger_summary"]["ledger_digest"]


def test_prompt_manifest_records_per_tool_result_visibility_hashes() -> None:
    file_observation = _algorithm_read_observation(
        "context.read_algorithm_file",
        {
            "file_path": "policies/baseline_modules/local_search.py",
            "readable": True,
            "content_preview": "def read_algorithm_file_visible():\n    return 1\n",
            "truncated": False,
            "size_chars": 47,
            "max_chars": 47,
        },
    )
    slice_observation = _algorithm_read_observation(
        "context.read_algorithm_slice",
        {
            "available": True,
            "slice_id": "slice.local_search.visible",
            "file_path": "policies/baseline_modules/local_search.py",
            "content": "def read_algorithm_slice_visible():\n    return 2\n",
            "truncated": False,
            "max_chars": 48,
        },
    )
    surface_observation = _algorithm_read_observation(
        "context.read_surface",
        {
            "surface": {"name": "solver_design", "kind": "solver_design"},
            "target_file": "policies/baseline_modules/local_search.py",
            "current_artifact": {
                "file_path": "policies/baseline_modules/local_search.py",
                "content_preview": "def read_surface_visible():\n    return 3\n",
                "readable": True,
                "truncated": False,
                "size_chars": 39,
                "max_chars": 39,
            },
        },
    )
    observations = [file_observation, slice_observation, surface_observation]
    user_prompt = (
        "## Agentic Proposal Tool Observations\n"
        + json.dumps([_observation_prompt_payload(item) for item in observations])
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="tool-result-visibility-ledger",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=observations,
        call_index=1,
        system_blocks=[],
        user_prompt=user_prompt,
    )

    ledger = manifest["tool_result_visibility_ledger"]
    by_tool = {item["tool_name"]: item for item in ledger}
    assert set(by_tool) == {
        "context.read_algorithm_file",
        "context.read_algorithm_slice",
        "context.read_surface",
    }
    for observation in observations:
        record = by_tool[observation.tool_name]
        assert record["stable_observation_id"] == observation.observation_id
        assert record["stable_name"] == observation.tool_name
        assert record["status"] == "ok"
        assert record["payload_hash"]
        assert record["visible_text_chars"] > 0
        assert record["visible_text_hash"]
        assert record["rendered_visibility_flag"] is True
        assert record["omitted"] is False


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


def test_code_prompt_projects_branch_created_helper_for_cross_target_followup(
    tmp_path: Path,
) -> None:
    target_rel = "policies/active_policy.py"
    helper_rel = "policies/helpers/alpha_helper.py"
    branch_root = tmp_path / "branch"
    champion_root = tmp_path / "champion"
    target_path = branch_root / target_rel
    helper_path = branch_root / helper_rel
    target_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    champion_root.mkdir(parents=True, exist_ok=True)
    target_source = "def active_policy():\n    return alpha_helper()\n"
    helper_source = "def alpha_helper():\n    return 7\n"
    target_path.write_text(target_source, encoding="utf-8")
    helper_path.write_text(helper_source, encoding="utf-8")

    integration_files = _build_solver_design_branch_current_integration_files(
        source_root=str(branch_root),
        champion_root=str(champion_root),
        target_file=target_rel,
        branch_created_files=(helper_rel,),
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": target_rel,
        "target_file_code": (
            f"File: {target_rel}\n```python\n{target_source}```\n"
        ),
        "solver_design_branch_current_integration_files": integration_files,
        "hypothesis_text": "Integrate the prior helper into the active policy.",
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Integrate the prior helper into the active policy.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_rel,
            "mechanism_changes": [
                {"id": "alpha_refinement", "change_type": "modify"}
            ],
        },
        "problem_summary": "Generic combinatorial optimisation problem.",
        "problem_object": "Generic problem object.",
        "solver_mechanics": "Call active_policy from the declared entrypoint.",
        "operator_interface_spec": "solve(instance, rng, time_limit_sec, context)",
        "import_whitelist": "math, random",
        "editable_patterns": "policies/*.py, policies/helpers/*.py",
        "frozen_patterns": "adapter.py",
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-branch-created-helper",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "Branch-Created Helper Sources" in rendered_system
    assert (
        "same-branch created or touched helper files are included"
        in rendered_system
    )
    assert helper_rel in rendered_system
    assert "branch_created_helper=True" in rendered_system
    assert helper_source.strip() in rendered_system
    assert helper_source.strip() not in user_prompt
    helper_records = [
        item
        for item in manifest["code_file_visibility_ledger"]["integration_files"]
        if item["file_path"] == helper_rel
    ]
    assert helper_records
    assert helper_records[0]["full_content_visible_in_rendered_prompt"] is True
    assert helper_records[0]["source_provenance"] == "branch_workspace"
    assert helper_records[0]["source_status"] == "current_branch_source"
    assert helper_records[0]["readable"] is True


def test_code_prompt_uses_branch_history_source_when_workspace_file_is_missing(
    tmp_path: Path,
) -> None:
    target_rel = "policies/active_policy.py"
    helper_rel = "policies/helpers/alpha_helper.py"
    branch_root = tmp_path / "branch"
    champion_root = tmp_path / "champion"
    branch_root.mkdir(parents=True, exist_ok=True)
    champion_root.mkdir(parents=True, exist_ok=True)
    helper_source = "def alpha_helper():\n    return 'branch-current'\n"

    integration_files = _build_solver_design_branch_current_integration_files(
        source_root=str(branch_root),
        champion_root=str(champion_root),
        target_file=target_rel,
        branch_created_files=(helper_rel,),
        branch_current_file_sources={helper_rel: helper_source},
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": target_rel,
        "target_file_code": "def active_policy():\n    return None\n",
        "solver_design_branch_current_integration_files": integration_files,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-branch-history-helper",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert helper_source.strip() in rendered_system
    assert helper_source.strip() not in user_prompt
    helper_record = next(
        item
        for item in manifest["code_file_visibility_ledger"]["integration_files"]
        if item["file_path"] == helper_rel
    )
    assert helper_record["source_provenance"] == "branch_history_current"
    assert helper_record["source_status"] == "current_branch_source"
    assert helper_record["full_content_visible_in_rendered_prompt"] is True


def test_missing_branch_created_helper_is_not_marked_as_full_source(
    tmp_path: Path,
) -> None:
    target_rel = "policies/active_policy.py"
    helper_rel = "policies/helpers/missing_helper.py"
    branch_root = tmp_path / "branch"
    champion_root = tmp_path / "champion"
    branch_root.mkdir(parents=True, exist_ok=True)
    champion_root.mkdir(parents=True, exist_ok=True)

    integration_files = _build_solver_design_branch_current_integration_files(
        source_root=str(branch_root),
        champion_root=str(champion_root),
        target_file=target_rel,
        branch_created_files=(helper_rel,),
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": target_rel,
        "target_file_code": "def active_policy():\n    return None\n",
        "solver_design_branch_current_integration_files": integration_files,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-missing-branch-helper",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "missing_current_source" in rendered_system
    assert "visibility=not_visible" in rendered_system
    assert "# could not read" in rendered_system
    assert "# could not read" not in user_prompt
    helper_record = next(
        item
        for item in manifest["code_file_visibility_ledger"]["integration_files"]
        if item["file_path"] == helper_rel
    )
    assert helper_record["source_status"] == "missing_current_source"
    assert helper_record["readable"] is False
    assert helper_record["placeholder_visible_in_rendered_prompt"] is True
    assert helper_record["full_content_visible_in_rendered_prompt"] is False


def test_create_new_target_prompt_uses_new_file_placeholder_status() -> None:
    target_rel = "policies/helpers/new_module.py"
    target_placeholder = (
        f"File: {target_rel}\n"
        "Provenance: new_file_placeholder; readable=False; "
        "source_status=new_file; visibility=new_file_placeholder\n"
        "This target file does not currently exist and may be created by a "
        "create_new proposal.\n"
        f"```python\n# new file placeholder for {target_rel}\n```"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "action": "create_new",
        "target_file": target_rel,
        "target_file_code": target_placeholder,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-new-file-placeholder",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "source_status=new_file" in rendered_system
    assert "visibility=new_file_placeholder" in rendered_system
    assert "visibility=not_visible" not in rendered_system
    target_record = manifest["code_file_visibility_ledger"]["target_file"]
    assert target_record["source_status"] == "new_file"
    assert target_record["source_provenance"] == "new_file_placeholder"
    assert target_record["visibility_status"] == "create_new_target_no_current_source"
    assert target_record["prompt_visibility_status"] == (
        "create_new_target_no_current_source"
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
