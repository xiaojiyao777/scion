from __future__ import annotations

import json
from pathlib import Path

import scion.proposal.agentic_session_hypothesis as hypothesis_facade
import scion.proposal.agentic_session_hypothesis_target as target_module
from scion.proposal.engine import (
    _parse_hypothesis_target_intent,
    _split_code_context,
    _split_hypothesis_context,
)
from scion.proposal.context_manager.code_context import (
    _build_solver_design_branch_current_integration_files,
)
from scion.proposal.agentic_session_hypothesis import (
    _observations_include_sufficient_target_context,
)
from scion.proposal.engine.exceptions import ProposalValidationError
from scion.proposal.agentic_observation_ledger.payloads import read_receipt_from_entry
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.proposal.prompt_manifest_visibility import VISIBILITY_LEDGER_SCHEMA_VERSION
from scion.proposal.target_intent_binding import (
    canonical_formal_mechanism_id,
    target_intent_binding_retry_feedback,
)
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


class TargetIntentCreative(SequentialHypothesisCreative):
    def __init__(
        self,
        *,
        intent: dict,
        hypotheses: list[HypothesisProposal],
    ) -> None:
        super().__init__(hypotheses)
        self.intent = dict(intent)
        self.target_intent_contexts: list[dict] = []

    def generate_hypothesis_target_intent(self, context):
        self.target_intent_contexts.append(dict(context))
        return dict(self.intent)


class SchemaErrorThenTargetIntentCreative(TargetIntentCreative):
    def __init__(
        self,
        *,
        intent: dict,
        hypothesis: HypothesisProposal,
    ) -> None:
        super().__init__(intent=intent, hypotheses=[hypothesis])
        self.failed_once = False

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.failed_once:
            self.failed_once = True
            raise ProposalValidationError(
                "1 validation error for HypothesisProposalInput\n"
                "mechanism_changes.0.id\n"
                "  Value error, mechanism id must match "
                "^[a-z][a-z0-9_]{0,63}$"
            )
        return self.hypotheses.pop(0)


class TargetIntentToolClient:
    def __init__(self, *, intent: dict, hypothesis_payload: dict) -> None:
        self.intent = dict(intent)
        self.hypothesis_payload = dict(hypothesis_payload)
        self.tool_names: list[str] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        del prompt, model, system_blocks, request_kind
        self.tool_names.append(tool["name"])
        if tool["name"] == "select_hypothesis_target_intent":
            return dict(self.intent)
        if tool["name"] == "generate_hypothesis":
            return dict(self.hypothesis_payload)
        if tool["name"] == "plan_proposal_tool_call":
            return {"intent": "stop"}
        raise AssertionError(f"unexpected tool request: {tool['name']}")


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


def _prompt_manifests(output: AgenticProposalOutput) -> list[dict]:
    return [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]


def _target_intent_artifacts(output: AgenticProposalOutput) -> list[dict]:
    payloads = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "hypothesis_target_intent" in str(ref)
    ]
    return [
        payload
        for payload in payloads
        if payload.get("artifact_kind") == "hypothesis_target_intent"
    ]


def _target_binding_artifacts(output: AgenticProposalOutput) -> list[dict]:
    return [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "hypothesis_target_intent_binding" in str(ref)
    ]


def test_target_grounding_helpers_remain_importable_from_hypothesis_facade() -> None:
    helper_names = (
        "_observations_include_sufficient_target_context",
        "_target_context_summary_from_observations",
        "_target_grounding_context_key",
        "_normalize_hypothesis_target_intent",
        "_mechanism_id_schema_output_retry_feedback",
    )

    for helper_name in helper_names:
        assert getattr(hypothesis_facade, helper_name) is getattr(
            target_module,
            helper_name,
        )


def test_target_intent_mismatch_retries_then_blocks_before_code(
    tmp_path: Path,
) -> None:
    selected_target = "policies/baseline_modules/local_search.py"
    formal_target = "policies/baseline_modules/destroy_repair.py"
    bad = _solver_design_file_hypothesis(
        target_file=formal_target,
        mechanism_id="cvrp_route_count_aware_repair",
        text="Modify destroy_repair.py despite the selected local_search intent.",
    )
    creative = TargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": selected_target,
            "mechanism_id": "cvrp.local_search.route_merge_savings",
            "mechanism_sketch": "Refine route merge savings in local_search.py.",
            "confidence": 0.72,
        },
        hypotheses=[bad, bad],
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-target-intent-mismatch"
    )
    code_context_calls: list[HypothesisProposal] = []

    def build_code_context(hypothesis: HypothesisProposal) -> dict:
        code_context_calls.append(hypothesis)
        return {"kind": "code"}

    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-intent-mismatch",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-intent-mismatch"},
            build_code_context=build_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(passed=True),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED
    )
    assert code_context_calls == []
    assert len(creative.hypothesis_contexts) == 2
    retry_context = creative.hypothesis_contexts[1]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert retry_feedback["failure_code"] == "target_intent_binding_mismatch"
    assert retry_feedback["binding_status"] == "mismatch"
    assert retry_feedback["selected_target_intent"]["target_file"] == selected_target
    assert retry_feedback["formal_hypothesis_target"]["target_file"] == formal_target
    assert "TARGET-INTENT BINDING RETRY" in retry_context[
        "agentic_hypothesis_preview_retry_rule"
    ]

    binding_artifacts = _target_binding_artifacts(output)
    assert [artifact["status"] for artifact in binding_artifacts] == [
        "retry",
        "blocked",
    ]
    blocked = binding_artifacts[-1]
    assert blocked["binding_status"] == "mismatch"
    assert blocked["selected_target_intent"]["target_file"] == selected_target
    assert blocked["formal_hypothesis_target"]["target_file"] == formal_target
    formal_ledger = blocked["formal_target_source_visibility_ledger"]
    assert formal_ledger["formal_target"]["target_file"] == formal_target
    assert formal_ledger["owner_source"]["file_path"] == formal_target
    assert formal_ledger["source_of_truth"] == (
        "formal_hypothesis_target_file; not preflight target intent"
    )
    assert "target_intent_binding_mismatch" in output.failure_detail


def test_target_intent_binding_allows_same_mechanism_refinement_suffix() -> None:
    hypothesis = _solver_design_file_hypothesis(
        target_file="policies/baseline_modules/destroy_repair.py",
        mechanism_id="cvrp_route_count_aware_repair_quality_guard",
        text="Refine the selected route-count-aware repair with a quality guard.",
    )
    feedback = target_intent_binding_retry_feedback(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/destroy_repair.py",
            "mechanism_id": "cvrp_route_count_aware_repair",
            "mechanism_family": "route_count_aware_repair",
        },
        hypothesis,
        attempt=1,
        manifest=None,
    )

    assert feedback is None


def test_target_intent_binding_allows_raw_dotted_id_with_refinement_formal_id() -> None:
    hypothesis = _solver_design_file_hypothesis(
        target_file="policies/baseline_modules/local_search.py",
        mechanism_id="intra_route_reinsertion_refine",
        text="Refine the selected local-search reinsertion mechanism.",
    )
    feedback = target_intent_binding_retry_feedback(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": "cvrp.local_search.intra_route_reinsertion",
            "mechanism_family": "local_search_reinsertion",
        },
        hypothesis,
        attempt=1,
        manifest=None,
    )

    assert feedback is None


def test_solver_design_existing_target_file_is_visible_before_first_hypothesis(
    tmp_path: Path,
) -> None:
    first = _scheduler_hypothesis(
        "Add stagnation_repair_scheduler to the active solver scheduler."
    )
    creative = SequentialHypothesisCreative([first])
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
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
    assert output.hypothesis == first
    assert len(creative.hypothesis_contexts) == 1
    assert "agentic_hypothesis_grounding_rejections" not in creative.hypothesis_contexts[0]

    first_context = creative.hypothesis_contexts[0]
    target_observations = [
        observation
        for observation in first_context["agentic_tool_observations"]
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
    assert manifests[0]["call_kind"] == "hypothesis"
    assert not any(
        manifest["call_kind"] == "hypothesis_grounding_retry"
        for manifest in manifests
    )
    retry_items = [
        item
        for item in manifests[0]["included_observations"]
        if item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == "policies/baseline_modules/scheduler.py"
    ]
    assert retry_items
    assert retry_items[0]["included_in_prompt_for_call"] is True
    assert retry_items[0]["full_content_included_in_prompt"] is True
    assert retry_items[0]["full_content_visible_in_rendered_prompt"] is True
    assert retry_items[0]["full_content_visible_in_dedicated_source_section"] is True
    assert retry_items[0]["full_content_visible_anywhere_in_rendered_prompt"] is True
    full_read_status = manifests[0]["section_statuses"][
        "solver_design_full_algorithm_file_reads"
    ]
    assert full_read_status["status"] == "included"
    assert "solver_design_full_algorithm_file_reads" not in manifests[0][
        "truncated_sections"
    ]

    scheduler_receipts = [
        receipt
        for receipt in output.observation_ledger["read_receipts"]
        if receipt.get("tool_name") == "context.read_algorithm_file"
        and receipt.get("file_path") == "policies/baseline_modules/scheduler.py"
    ]
    assert scheduler_receipts
    assert any(
        receipt["selection_source"] == "required_context_preface"
        for receipt in scheduler_receipts
    )


@pytest.mark.parametrize(
    ("target_file", "mechanism_id"),
    (
        ("policies/baseline_modules/local_search.py", "target_owner_probe_local"),
        ("policies/baseline_modules/destroy_repair.py", "target_owner_probe_repair"),
    ),
)
def test_solver_design_common_existing_targets_are_pregrounded_before_first_hypothesis(
    tmp_path: Path,
    target_file: str,
    mechanism_id: str,
) -> None:
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id=mechanism_id,
        text=f"Modify {target_file} after reading its owner source.",
    )
    creative = SequentialHypothesisCreative([hypothesis])
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / f"artifacts-{mechanism_id}"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id=f"camp-{mechanism_id}",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": mechanism_id},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert len(creative.hypothesis_contexts) == 1
    assert "agentic_hypothesis_grounding_rejections" not in creative.hypothesis_contexts[0]

    first_context = creative.hypothesis_contexts[0]
    target_observations = [
        observation
        for observation in first_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_file
    ]
    assert target_observations
    assert target_observations[0]["structured_payload"]["readable"] is True
    assert target_observations[0]["structured_payload"]["truncated"] is False

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]
    assert manifests[0]["call_kind"] == "hypothesis"
    assert not any(
        manifest["call_kind"] == "hypothesis_grounding_retry"
        for manifest in manifests
    )
    target_items = [
        item
        for item in manifests[0]["included_observations"]
        if item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == target_file
    ]
    assert target_items
    assert target_items[0]["included_in_prompt_for_call"] is True
    assert target_items[0]["full_content_visible_in_rendered_prompt"] is True
    assert target_items[0]["full_content_visible_in_dedicated_source_section"] is True


@pytest.mark.parametrize(
    ("target_file", "mechanism_id"),
    (
        (
            "policies/baseline_modules/construction.py",
            "target_intent_probe_construction",
        ),
        (
            "policies/baseline_modules/acceptance.py",
            "target_intent_probe_acceptance",
        ),
    ),
)
def test_target_intent_preflight_grounds_non_top_existing_target_before_first_hypothesis(
    tmp_path: Path,
    target_file: str,
    mechanism_id: str,
) -> None:
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id=mechanism_id,
        text=f"Modify {target_file} after target-intent grounding.",
    )
    creative = TargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": mechanism_id,
            "mechanism_sketch": "Modify the selected owner with a bounded mechanism.",
            "confidence": 0.91,
            "notes": "preflight target owner selection",
        },
        hypotheses=[hypothesis],
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / f"artifacts-target-intent-{mechanism_id}"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id=f"camp-{mechanism_id}",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": mechanism_id},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert len(creative.target_intent_contexts) == 1
    assert len(creative.hypothesis_contexts) == 1
    final_context = creative.hypothesis_contexts[0]
    assert "agentic_hypothesis_grounding_rejections" not in final_context
    assert final_context["agentic_hypothesis_target_intent"]["intent"][
        "target_file"
    ] == target_file
    target_reads = [
        observation
        for observation in final_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_file
    ]
    assert target_reads
    assert target_reads[0]["structured_payload"]["readable"] is True
    assert target_reads[0]["structured_payload"]["truncated"] is False

    manifests = _prompt_manifests(output)
    assert [manifest["call_kind"] for manifest in manifests[:2]] == [
        "hypothesis_target_intent",
        "hypothesis",
    ]
    assert not any(
        manifest["call_kind"] == "hypothesis_grounding_retry"
        for manifest in manifests
    )
    hypothesis_manifest = [
        manifest for manifest in manifests if manifest["call_kind"] == "hypothesis"
    ][0]
    target_ledger = hypothesis_manifest["hypothesis_target_source_visibility_ledger"]
    assert target_ledger["target_intent"]["target_file"] == target_file
    assert target_ledger["target_source_required"] is True
    assert target_ledger["visibility_status"] == "full_dedicated_source_visible"
    assert target_ledger["owner_source"][
        "full_content_visible_in_dedicated_source_section"
    ] is True
    assert any(
        receipt.get("tool_name") == "context.read_algorithm_file"
        and receipt.get("file_path") == target_file
        and receipt.get("selection_source") == "hypothesis_target_intent_grounding"
        for receipt in output.observation_ledger["read_receipts"]
    )
    intent_artifacts = _target_intent_artifacts(output)
    assert intent_artifacts
    assert intent_artifacts[0]["call_kind"] == "hypothesis_target_intent"
    assert intent_artifacts[0]["formal_proposal"] is False
    assert intent_artifacts[0]["intent"]["intent"]["target_file"] == target_file
    assert intent_artifacts[0]["intent"]["intent"]["mechanism_family_status"] == (
        "fallback_from_mechanism_id"
    )
    assert intent_artifacts[0]["intent"]["intent"]["mechanism_family"]
    binding_artifacts = _target_binding_artifacts(output)
    assert len(binding_artifacts) == 1
    binding = binding_artifacts[0]
    assert binding["status"] == "succeeded"
    assert binding["binding_status"] == "bound"
    assert binding["selected_target_intent"]["target_file"] == target_file
    assert binding["formal_hypothesis_target"]["target_file"] == target_file
    formal_ledger = binding["formal_target_source_visibility_ledger"]
    assert formal_ledger["formal_target"]["target_file"] == target_file
    assert formal_ledger["owner_source"]["file_path"] == target_file
    assert formal_ledger["visibility_status"] == "full_dedicated_source_visible"


def test_target_intent_dotted_mechanism_id_is_canonicalized_for_formal_prompt(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/local_search.py"
    raw_mechanism_id = "cvrp.local_search.intra_route_reinsertion"
    canonical_id = "cvrp_local_search_intra_route_reinsertion"
    assert canonical_formal_mechanism_id(raw_mechanism_id) == canonical_id
    parsed_intent = _parse_hypothesis_target_intent(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": raw_mechanism_id,
            "mechanism_sketch": "Refine intra-route reinsertion.",
        }
    )
    assert parsed_intent["mechanism_id"] == canonical_id
    assert parsed_intent["raw_mechanism_id"] == raw_mechanism_id
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id=canonical_id,
        text="Modify local_search.py with the selected canonical mechanism id.",
    )
    creative = TargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": raw_mechanism_id,
            "mechanism_sketch": "Refine intra-route reinsertion inside local_search.py.",
            "confidence": 0.93,
        },
        hypotheses=[hypothesis],
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-target-intent-canonical-id"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-intent-canonical-id",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "canonical-id"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    final_context = creative.hypothesis_contexts[0]
    selected_intent = final_context["agentic_hypothesis_target_intent"]["intent"]
    assert selected_intent["mechanism_id"] == canonical_id
    assert selected_intent["raw_mechanism_id"] == raw_mechanism_id
    assert selected_intent["mechanism_id_status"] == (
        "canonicalized_from_raw_mechanism_id"
    )
    assert selected_intent["formal_schema_id_policy"].startswith(
        "mechanism_id is canonical"
    )

    _system_blocks, prompt = _split_hypothesis_context(final_context)
    assert f"formal schema mechanism_id `{canonical_id}`" in prompt
    assert f"formal `mechanism_changes[].id` as `{canonical_id}`" in prompt
    assert f"Raw mechanism id `{raw_mechanism_id}` is audit provenance only" in prompt
    assert "do not copy raw/provenance ids into formal mechanism_changes" in prompt
    assert f"formal schema mechanism_id `{raw_mechanism_id}`" not in prompt

    intent_artifacts = _target_intent_artifacts(output)
    assert intent_artifacts[0]["intent"]["intent"]["mechanism_id"] == canonical_id
    assert intent_artifacts[0]["intent"]["intent"]["raw_mechanism_id"] == (
        raw_mechanism_id
    )
    binding_artifacts = _target_binding_artifacts(output)
    assert binding_artifacts[0]["binding_status"] == "bound"
    assert binding_artifacts[0]["selected_target_intent"]["mechanism_id"] == (
        canonical_id
    )
    assert binding_artifacts[0]["selected_target_intent"]["raw_mechanism_id"] == (
        raw_mechanism_id
    )
    assert binding_artifacts[0]["formal_hypothesis_target"]["mechanism_ids"] == [
        canonical_id
    ]


def test_invalid_mechanism_id_schema_retry_uses_canonical_target_intent_id(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/local_search.py"
    raw_mechanism_id = "cvrp.local_search.intra_route_reinsertion"
    canonical_id = "cvrp_local_search_intra_route_reinsertion"
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id=canonical_id,
        text="Retry with the canonical formal mechanism id.",
    )
    creative = SchemaErrorThenTargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": raw_mechanism_id,
            "mechanism_sketch": "Refine intra-route reinsertion inside local_search.py.",
            "confidence": 0.89,
        },
        hypothesis=hypothesis,
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-target-intent-schema-retry"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-intent-schema-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "canonical-id-schema-retry"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert len(creative.hypothesis_contexts) == 2
    retry_context = creative.hypothesis_contexts[1]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert retry_feedback["failure_code"] == "invalid_mechanism_id"
    assert retry_feedback["canonical_formal_mechanism_id"] == canonical_id
    assert retry_feedback["raw_mechanism_id"] == raw_mechanism_id
    assert "MECHANISM-ID SCHEMA RETRY" in retry_context[
        "agentic_hypothesis_preview_retry_rule"
    ]
    assert "raw_mechanism_id/provenance fields are audit-only" in retry_context[
        "agentic_hypothesis_preview_retry_rule"
    ]
    binding_artifacts = _target_binding_artifacts(output)
    assert binding_artifacts[-1]["binding_status"] == "bound"


def test_solver_design_existing_target_inferred_from_branch_state_is_pregrounded(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/scheduler.py"
    branch_source = (
        "class BranchScopedScheduler:\n"
        "    def choose(self, state):\n"
        "        return state\n"
    )
    creative = FakeCreative(
        hypothesis=_scheduler_hypothesis(
            "Modify the existing scheduler.py owner file for bounded scheduling."
        )
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        branch_current_file_sources={target_file: branch_source},
    )
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "artifacts-inferred")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-pregrounding",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-pregrounding"},
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
    target_observations = [
        observation
        for observation in first_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_file
    ]
    assert target_observations
    assert target_observations[0]["structured_payload"]["readable"] is True
    assert target_observations[0]["structured_payload"]["truncated"] is False

    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in str(ref)
    ]
    assert manifests[0]["call_kind"] == "hypothesis"
    assert not any(manifest["call_kind"] == "hypothesis_grounding_retry" for manifest in manifests)
    prompt_items = [
        item
        for item in manifests[0]["included_observations"]
        if item.get("tool_name") == "context.read_algorithm_file"
        and item.get("file_path") == target_file
    ]
    assert prompt_items
    assert prompt_items[0]["included_in_prompt_for_call"] is True
    assert prompt_items[0]["full_content_visible_anywhere_in_rendered_prompt"] is True


def test_target_intent_preflight_grounds_branch_current_existing_target(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/branch_current_target.py"
    branch_source = (
        "def branch_current_target(context):\n"
        "    context.record_phase('branch_current_target')\n"
        "    return None\n"
    )
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id="branch_current_refinement",
        text="Modify the branch-current target after reading its source.",
    )
    creative = TargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": "branch_current_refinement",
            "mechanism_sketch": "Refine an already accepted branch-current target.",
            "confidence": 0.88,
        },
        hypotheses=[hypothesis],
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        branch_current_file_sources={target_file: branch_source},
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-branch-current-target-intent"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-branch-current-target-intent",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "branch-current-target-intent"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    final_context = creative.hypothesis_contexts[0]
    target_reads = [
        observation
        for observation in final_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_file
    ]
    assert target_reads
    assert target_reads[0]["structured_payload"]["source"] == (
        "branch_current_file_sources"
    )
    assert target_reads[0]["structured_payload"]["content_preview"].strip() == (
        branch_source.strip()
    )
    manifests = _prompt_manifests(output)
    assert not any(
        manifest["call_kind"] == "hypothesis_grounding_retry"
        for manifest in manifests
    )
    hypothesis_manifest = [
        manifest for manifest in manifests if manifest["call_kind"] == "hypothesis"
    ][0]
    target_ledger = hypothesis_manifest["hypothesis_target_source_visibility_ledger"]
    assert target_ledger["target_intent"]["target_file"] == target_file
    assert target_ledger["visibility_status"] == "full_dedicated_source_visible"
    assert target_ledger["owner_source"]["source_provenance"] == (
        "branch_current_file_sources"
    )


def test_target_intent_preflight_writes_distinct_llm_trace_and_artifact(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/construction.py"
    mechanism_id = "traceable_target_intent"
    hypothesis_payload = _valid_hypothesis_payload(
        change_locus="solver_design",
        action="modify",
        target_file=target_file,
        hypothesis_text="Modify the selected target after preflight grounding.",
        target_weakness="The selected owner has a bounded improvement gap.",
        expected_effect="Improve total_distance with a scoped mechanism.",
        mechanism_changes=[{"id": mechanism_id, "change_type": "add"}],
        novelty_signature={
            "algorithm_family": "target_intent_trace_test",
            "target_file": target_file,
        },
        expected_telemetry={
            "activity": ["solver_algorithm_search_iterations"],
            "activation": [
                f"solver_algorithm_context_records.{mechanism_id}_iterations"
            ],
            "budget": [f"solver_algorithm_phase_runtime_ms.{mechanism_id}"],
        },
    )
    client = TargetIntentToolClient(
        intent={
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_id": mechanism_id,
            "mechanism_sketch": "Trace the selected target intent.",
            "confidence": 0.83,
        },
        hypothesis_payload=hypothesis_payload,
    )
    creative = CreativeLayer(client, model="test-model", trace_dir=str(tmp_path / "traces"))
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-target-intent-trace"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-intent-trace",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-intent-trace"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    model_generation_tools = [
        name
        for name in client.tool_names
        if name
        in {
            "select_hypothesis_target_intent",
            "generate_hypothesis",
        }
    ]
    assert model_generation_tools[:2] == [
        "select_hypothesis_target_intent",
        "generate_hypothesis",
    ]
    traces = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "traces").glob("*.json")
    ]
    trace_call_kinds = [
        trace["agentic_session"]["call_kind"]
        for trace in traces
        if "agentic_session" in trace
    ]
    assert "hypothesis_target_intent" in trace_call_kinds
    assert "hypothesis" in trace_call_kinds
    manifests = _prompt_manifests(output)
    assert [manifest["call_kind"] for manifest in manifests[:2]] == [
        "hypothesis_target_intent",
        "hypothesis",
    ]
    intent_artifacts = _target_intent_artifacts(output)
    assert intent_artifacts
    assert intent_artifacts[0]["status"] == "succeeded"
    assert intent_artifacts[0]["formal_proposal"] is False


def test_target_intent_preflight_create_new_uses_visible_placeholder(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_modules/new_target_intent_module.py"
    mechanism_id = "new_target_intent_module"
    hypothesis = _solver_design_file_hypothesis(
        target_file=target_file,
        mechanism_id=mechanism_id,
        text="Create a new target file using the visible placeholder context.",
    )
    hypothesis.action = "create_new"
    creative = TargetIntentCreative(
        intent={
            "change_locus": "solver_design",
            "action": "create_new",
            "target_file": target_file,
            "mechanism_id": mechanism_id,
            "mechanism_sketch": "Create a new bounded support target.",
            "confidence": 0.74,
        },
        hypotheses=[hypothesis],
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    artifact_store = FileAgenticSessionArtifactStore(
        tmp_path / "artifacts-create-new-target-intent"
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-create-new-target-intent",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "create-new-target-intent"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    final_context = creative.hypothesis_contexts[0]
    placeholder = final_context["agentic_hypothesis_target_placeholder"]
    assert placeholder["target_file"] == target_file
    assert placeholder["owner_required"] is False
    target_reads = [
        observation
        for observation in final_context["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"]["file_path"] == target_file
    ]
    assert not target_reads
    manifests = _prompt_manifests(output)
    assert not any(
        manifest["call_kind"] == "hypothesis_grounding_retry"
        for manifest in manifests
    )
    hypothesis_manifest = [
        manifest for manifest in manifests if manifest["call_kind"] == "hypothesis"
    ][0]
    target_ledger = hypothesis_manifest["hypothesis_target_source_visibility_ledger"]
    assert target_ledger["target_source_required"] is False
    assert target_ledger["visibility_status"] == "create_new_placeholder_visible"
    assert target_ledger["placeholder"]["visible"] is True


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
        and observation["structured_payload"].get("file_path")
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
    assert target_registries
    if target_slices:
        assert tool_names.index("context.read_algorithm_slice") < tool_names.index(
            "context.read_algorithm_file"
        )
    assert target_reads[0]["structured_payload"]["truncated"] is False
    assert target_reads[0]["structured_payload"]["max_chars"] == 96000
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
        receipt.get("tool_name") == "context.read_algorithm_file"
        and receipt.get("file_path") == "policies/baseline_modules/scheduler.py"
        and receipt.get("coverage_status") == "full"
        and receipt.get("max_chars") == 96000
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


def test_prompt_manifest_distinguishes_bounded_tool_projection_from_section_truncation(
) -> None:
    slice_content = "def bounded_scheduler_slice():\n    return 11\n"
    observation = _algorithm_read_observation(
        "context.read_algorithm_slice",
        {
            "available": True,
            "slice_id": "cvrp.slice.scheduler.solve",
            "file_path": "policies/baseline_modules/scheduler.py",
            "symbols": ["solve"],
            "content": slice_content,
            "content_digest": "scheduler-slice-digest",
            "truncated": True,
            "max_chars": 6000,
            "size_chars": 12000,
        },
    )
    user_prompt = (
        "## Agentic Proposal Tool Observations\n"
        + json.dumps(
            [
                {
                    "observation_id": observation.observation_id,
                    "tool_name": observation.tool_name,
                    "slice_id": "cvrp.slice.scheduler.solve",
                    "content_preview": slice_content,
                }
            ]
        )
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="bounded-projection",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[observation],
        call_index=1,
        system_blocks=[],
        user_prompt=user_prompt,
    )

    assert manifest["truncated_sections"] == []
    assert manifest["prompt_section_truncation_count"] == 0
    assert manifest["bounded_tool_projection_count"] == 1
    diagnostics = manifest["projection_diagnostics"]
    assert diagnostics["prompt_section_truncation_count"] == 0
    assert diagnostics["bounded_tool_projection_count"] == 1
    bounded = diagnostics["bounded_tool_projections"][0]
    assert bounded["projection_kind"] == "bounded_tool_projection"
    assert bounded["truncation_scope"] == "tool_result_payload_projection"
    assert bounded["prompt_section_truncation"] is False
    ledger_item = manifest["tool_result_visibility_ledger"][0]
    assert ledger_item["projection_kind"] == "bounded_tool_projection"
    assert ledger_item["truncation_scope"] == "tool_result_payload_projection"
    assert ledger_item["prompt_section_truncation"] is False
    assert "not prompt section truncation" in ledger_item["projection_reason"]


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
    assert ledger["schema_version"] == VISIBILITY_LEDGER_SCHEMA_VERSION
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
    required_integration_source = (
        "def accept(candidate, incumbent, rng):\n"
        "    return candidate.is_feasible and candidate.cost <= incumbent.cost\n"
    )
    champion_entrypoint_source = (
        "def champion_solve(instance, rng, time_limit_sec, context):\n"
        "    return context.champion_baseline(instance)\n"
    )
    champion_read_observation = {
        "observation_id": "obs-champion-entrypoint",
        "tool_name": "context.read_algorithm_file",
        "is_error": False,
        "structured_payload": {
            "file_path": "policies/baseline_algorithm.py",
            "active": True,
            "role": "champion_entrypoint",
            "readable": True,
            "source": "champion_snapshot",
            "truncated": False,
            "size_chars": len(champion_entrypoint_source),
            "max_chars": len(champion_entrypoint_source),
            "content_preview": champion_entrypoint_source,
        },
    }
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
        "agentic_required_full_integration_files": (
            "### policies/baseline_modules/acceptance.py\n"
            "Provenance: branch_workspace; readable=True\n"
            "```python\n"
            f"{required_integration_source}"
            "```"
        ),
        "agentic_tool_observations": [champion_read_observation],
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
        "measurement_governance": "record_only",
        "problem_measurement_diagnostics": {
            "schema_version": "problem_measurement_proposal_diagnostic.v1",
            "measurement_readiness": {"status": "degraded"},
            "opportunity_diagnostics": [
                {"diagnostic_type": "low_snr", "reason_codes": ["LOW_POWER"]}
            ],
        },
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
        "policies/baseline_modules/acceptance.py",
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
    required_integration_status = manifest["section_statuses"][
        "required_full_integration_edit_sources"
    ]
    assert required_integration_status["status"] == "included"
    assert required_integration_status["prompt_part"] == "user"
    assert (
        integration_records["policies/baseline_modules/acceptance.py"]["role"]
        == "required_full_integration_edit_source"
    )
    algorithm_read_records = {
        item["file_path"]: item for item in ledger["algorithm_file_reads"]
    }
    assert set(algorithm_read_records) == {"policies/baseline_algorithm.py"}
    champion_source_record = algorithm_read_records["policies/baseline_algorithm.py"]
    assert champion_source_record["full_content_visible_in_rendered_prompt"] is True
    algorithm_read_status = manifest["section_statuses"][
        "solver_design_full_algorithm_file_reads"
    ]
    assert algorithm_read_status["status"] == "included"
    guarantees = manifest["code_phase_source_guarantees"]
    assert guarantees["schema_version"] == "code-phase-source-visibility-guarantees.v1"
    assert guarantees["target_source_visible"] is True
    assert guarantees["required_integration_source_visible"] is True
    assert guarantees["algorithm_file_read_source_visible"] is True
    assert guarantees["protected_source_visible"] is True
    assert prompt_context["measurement_governance"] == "record_only"
    assert target_record["source_status"] == "current_branch_source"
    assert integration_records["policies/baseline_algorithm.py"][
        "source_provenance"
    ] == "branch_workspace"
    assert champion_source_record["source_status"] == "current_branch_source"
    assert guarantees["required_integration_source_count"] == 1
    assert guarantees["algorithm_file_read_source_count"] == 1
    assert guarantees.get("missing_required_source_paths", []) == []
    assert (
        ledger["source_visibility_guarantees"]["protected_source_visible"] is True
    )
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


def test_code_visibility_does_not_mark_visible_modify_target_as_missing_required_source() -> None:
    target_rel = "policies/operators/merge_vehicles.py"
    target_source = "def merge_vehicles(solution):\n    return solution\n"
    missing_duplicate_target = (
        f"### {target_rel}\n"
        "Provenance: branch_workspace; readable=False; "
        "source_status=missing_current_source; visibility=not_visible\n"
        "```python\n"
        f"# could not read {target_rel}\n"
        "```"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": target_rel,
        "target_file_code": f"File: {target_rel}\n```python\n{target_source}```",
        "agentic_required_full_integration_files": missing_duplicate_target,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-visible-target-duplicate-required",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    guarantees = manifest["code_phase_source_guarantees"]
    target_identity = guarantees["target_source_identity"]
    assert guarantees["target_source_visible"] is True
    assert guarantees["required_integration_source_visible"] is True
    assert guarantees["protected_source_visible"] is True
    assert guarantees.get("missing_required_source_paths", []) == []
    assert guarantees.get("missing_required_sources", []) == []
    assert guarantees["duplicate_target_paths_satisfied_by_target_source"] == [
        target_rel
    ]
    assert target_identity["file_path"] == target_rel
    assert target_identity["required_source_satisfied"] is True
    assert target_identity["source_digest"]
    assert target_identity["source_digest_visibility_status"] in {
        "literal_visible",
        "derivable_from_visible_source",
    }
    duplicate_requirement = guarantees[
        "required_integration_source_requirements"
    ][0]
    assert duplicate_requirement["file_path"] == target_rel
    assert duplicate_requirement["required_source_satisfied"] is True
    assert duplicate_requirement["satisfied_by"] == "target_source"
    assert duplicate_requirement["duplicate_target_requirement"] is True


def test_code_visibility_infers_create_new_from_target_file_absence() -> None:
    target_rel = "policies/helpers/new_module.py"
    target_placeholder = (
        f"File: {target_rel}\n"
        "Provenance: new_file_placeholder; readable=False; "
        "source_status=new_file; visibility=new_file_placeholder\n"
        "This target file does not currently exist and may be created.\n"
        f"```python\n# new file placeholder for {target_rel}\n```"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": target_rel,
        "target_file_exists": False,
        "target_file_code": target_placeholder,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-new-file-inferred",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    target_record = manifest["code_file_visibility_ledger"]["target_file"]
    assert target_record["target_file_create_mode"] is True
    assert target_record["source_status"] == "new_file"
    assert target_record["placeholder_visible_in_rendered_prompt"] is True
    guarantees = manifest["code_phase_source_guarantees"]
    assert guarantees["target_file_create_mode"] is True
    assert guarantees["target_source_visible"] is True
    assert guarantees["protected_source_visible"] is True
    assert guarantees.get("missing_required_source_paths", []) == []
    target_identity = guarantees["target_source_identity"]
    assert target_identity["file_path"] == target_rel
    assert target_identity["required"] is False
    assert target_identity["required_source_satisfied"] is True
    assert target_identity["source_digest_visibility_status"] == "not_visible"


def test_code_visibility_reports_missing_required_integration_source_with_reason() -> None:
    target_rel = "policies/operators/merge_vehicles.py"
    integration_rel = "policies/operators/vehicle_registry.py"
    target_source = "def merge_vehicles(solution):\n    return solution\n"
    missing_integration = (
        f"### {integration_rel}\n"
        "Provenance: branch_workspace; readable=False; "
        "source_status=missing_current_source; visibility=not_visible\n"
        "```python\n"
        f"# could not read {integration_rel}\n"
        "```"
    )
    prompt_context = {
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": target_rel,
        "target_file_code": f"File: {target_rel}\n```python\n{target_source}```",
        "agentic_required_full_integration_files": missing_integration,
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-missing-required-integration",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    guarantees = manifest["code_phase_source_guarantees"]
    assert guarantees["target_source_visible"] is True
    assert guarantees["required_integration_source_visible"] is False
    assert guarantees["protected_source_visible"] is False
    assert guarantees["missing_required_source_paths"] == [integration_rel]
    missing = guarantees["missing_required_sources"][0]
    assert missing["file_path"] == integration_rel
    assert missing["requirement_category"] == "required_integration_source"
    assert missing["missing_reason"] == "missing_current_source"
    assert missing["required_source_satisfied"] is False


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
