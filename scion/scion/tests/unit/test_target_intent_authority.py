from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scion.proposal.agentic_models import AgenticProposalRequest, AgenticProposalStatus
from scion.proposal.agentic_session import AgenticProposalSession
from scion.proposal.target_intent_authority import (
    resolve_target_intent_authority,
    tool_context_with_target_intent_authority_overrides,
)
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.registry import ProposalToolRegistry
from scion.tests.unit.agentic_session_test_support import (
    FakeCreative,
    FileAgenticSessionArtifactStore,
    HypothesisProposal,
    _cvrp_context_with_champion,
    _valid_hypothesis_payload,
)


def _context(
    *,
    required_ids: list[str] | None = None,
    branch_hygiene: dict | None = None,
) -> ProposalToolContext:
    launch_research_focus = {}
    if required_ids is not None:
        launch_research_focus = {
            "schema_version": "scion.launch_research_focus_prompt.v1",
            "taint": "prepared_launch_research_focus",
            "research_focus": {
                "required_mechanism_ids": list(required_ids),
                "next_required_direction": "Prepare the next generic direction.",
            },
        }
    return ProposalToolContext(
        session_id="session-target-intent-authority",
        campaign_id="campaign-target-intent-authority",
        branch_hygiene=branch_hygiene or {},
        launch_research_focus=launch_research_focus,
    )


def _intent(
    mechanism_id: str,
    *,
    target_file: str = "algorithms/existing_surface.py",
) -> dict:
    return {
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": target_file,
        "mechanism_id": mechanism_id,
        "mechanism_sketch": f"Sketch for {mechanism_id}.",
        "confidence": 0.7,
    }


class _TargetIntentCreative(FakeCreative):
    def __init__(self, *, intent: dict, hypothesis: HypothesisProposal) -> None:
        super().__init__(hypothesis=hypothesis)
        self.intent = dict(intent)
        self.target_intent_contexts: list[dict] = []

    def generate_hypothesis_target_intent(self, context):
        self.target_intent_contexts.append(dict(context))
        return dict(self.intent)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        return self.hypothesis


def test_open_exploration_prepared_required_mechanism_binds() -> None:
    required_id = "prepared_route_repair"
    resolution = resolve_target_intent_authority(
        _intent("candidate_branch_local"),
        _context(required_ids=[required_id]),
    )

    assert resolution.intent["mechanism_id"] == required_id
    assert resolution.intent["mechanism_id_status"] == (
        "launch_focus_required_mechanism"
    )
    assert resolution.diagnostics["authority_source"] == (
        "prepared_launch_research_focus"
    )
    assert resolution.diagnostics["selected_required_mechanism_id"] == required_id
    assert resolution.tool_context_overrides == {}


def test_branch_followup_disjoint_prepared_focus_defers_to_branch_id() -> None:
    prepared_id = "prepared_generic_seed"
    branch_id = "existing_branch_mechanism"
    context = _context(
        required_ids=[prepared_id],
        branch_hygiene={
            "hypothesis_generation_mode": "branch_local_followup",
            "branch_followup_policy": "branch_local_followup_or_explicit_bridge",
            "protected_mechanism_ids": [branch_id],
        },
    )
    resolution = resolve_target_intent_authority(_intent(prepared_id), context)

    assert resolution.intent["mechanism_id"] == branch_id
    assert resolution.intent["mechanism_id_status"] == (
        "prepared_focus_deferred_for_branch_followup"
    )
    assert resolution.diagnostics["authority_status"] == (
        "prepared_focus_deferred_for_branch_followup"
    )
    assert resolution.diagnostics["prepared_focus_deferred"] is True
    assert resolution.diagnostics["branch_protected_mechanism_ids"] == [branch_id]
    assert resolution.diagnostics["prepared_required_mechanism_ids"] == [
        prepared_id
    ]

    selected_context = {
        "intent": resolution.intent,
        "tool_context_overrides": resolution.tool_context_overrides,
    }
    effective_context = tool_context_with_target_intent_authority_overrides(
        context,
        selected_context,
    )
    assert effective_context is not None
    effective_focus = effective_context.launch_research_focus["research_focus"]
    assert effective_focus["required_mechanism_ids"] == []
    assert effective_focus["deferred_required_mechanism_ids"] == [prepared_id]


def test_branch_followup_allowed_only_authority_defers_prepared_focus() -> None:
    prepared_id = "prepared_generic_seed"
    branch_id = "existing_branch_allowed_mechanism"
    context = _context(
        required_ids=[prepared_id],
        branch_hygiene={
            "hypothesis_generation_mode": "branch_local_followup",
            "branch_followup_policy": "branch_local_followup_or_explicit_bridge",
            "allowed_mechanism_ids": [branch_id],
        },
    )
    resolution = resolve_target_intent_authority(_intent(prepared_id), context)

    assert resolution.intent["mechanism_id"] == branch_id
    assert resolution.intent["mechanism_id_status"] == (
        "prepared_focus_deferred_for_branch_followup"
    )
    assert resolution.diagnostics["branch_allowed_mechanism_ids"] == [branch_id]
    assert resolution.diagnostics["branch_authority_mechanism_ids"] == [branch_id]
    assert resolution.diagnostics["selected_branch_mechanism_id"] == branch_id

    effective_context = tool_context_with_target_intent_authority_overrides(
        context,
        {
            "intent": resolution.intent,
            "tool_context_overrides": resolution.tool_context_overrides,
        },
    )
    assert effective_context is not None
    effective_focus = effective_context.launch_research_focus["research_focus"]
    assert effective_focus["required_mechanism_ids"] == []
    assert effective_focus["deferred_required_mechanism_ids"] == [prepared_id]
    assert "tool_context_overrides" not in resolution.intent


def test_branch_followup_authority_unions_protected_and_allowed_ids() -> None:
    protected_id = "existing_branch_protected_mechanism"
    allowed_id = "existing_branch_allowed_extension"
    branch_hygiene = {
        "hypothesis_generation_mode": "branch_local_followup",
        "branch_followup_policy": "branch_local_followup_or_explicit_bridge",
        "protected_mechanism_ids": [protected_id],
        "allowed_mechanism_ids": [allowed_id],
    }

    protected_resolution = resolve_target_intent_authority(
        _intent(allowed_id),
        _context(required_ids=[protected_id], branch_hygiene=branch_hygiene),
    )
    assert protected_resolution.intent["mechanism_id"] == protected_id
    assert protected_resolution.diagnostics["branch_authority_mechanism_ids"] == [
        protected_id,
        allowed_id,
    ]
    assert (
        protected_resolution.diagnostics["selected_branch_mechanism_id"]
        == protected_id
    )

    allowed_resolution = resolve_target_intent_authority(
        _intent(protected_id),
        _context(required_ids=[allowed_id], branch_hygiene=branch_hygiene),
    )
    assert allowed_resolution.intent["mechanism_id"] == allowed_id
    assert allowed_resolution.diagnostics["branch_authority_mechanism_ids"] == [
        protected_id,
        allowed_id,
    ]
    assert allowed_resolution.diagnostics["selected_branch_mechanism_id"] == allowed_id


def test_branch_followup_create_new_intent_becomes_modify() -> None:
    prepared_id = "prepared_new_mechanism"
    branch_id = "existing_branch_mechanism"
    intent = _intent(prepared_id)
    intent["action"] = "create_new"

    resolution = resolve_target_intent_authority(
        intent,
        _context(
            required_ids=[prepared_id],
            branch_hygiene={
                "hypothesis_generation_mode": "branch_local_followup",
                "branch_followup_policy": "branch_local_followup_or_explicit_bridge",
                "protected_mechanism_ids": [branch_id],
            },
        ),
    )

    assert resolution.intent["mechanism_id"] == branch_id
    assert resolution.intent["action"] == "modify"
    assert resolution.diagnostics["original_target_intent_action"] == "create_new"
    assert resolution.diagnostics["selected_target_intent_action"] == "modify"
    assert resolution.diagnostics["target_intent_action_updated"] is True


def test_branch_followup_intersection_binds_intersecting_required_id() -> None:
    required_id = "existing_branch_mechanism"
    resolution = resolve_target_intent_authority(
        _intent("different_candidate"),
        _context(
            required_ids=[required_id],
            branch_hygiene={
                "hypothesis_generation_mode": "same_mechanism_only",
                "branch_followup_policy": "same_mechanism_followup_only",
                "protected_mechanism_ids": [
                    required_id,
                    "secondary_branch_mechanism",
                ],
            },
        ),
    )

    assert resolution.intent["mechanism_id"] == required_id
    assert resolution.intent["mechanism_id_status"] == (
        "branch_prepared_focus_intersection"
    )
    assert resolution.diagnostics["selected_required_mechanism_id"] == required_id
    assert resolution.diagnostics["selected_branch_mechanism_id"] == required_id
    assert resolution.tool_context_overrides == {}


def test_no_required_mechanism_ids_leaves_intent_unchanged() -> None:
    intent = _intent("existing_branch_mechanism")

    resolution = resolve_target_intent_authority(
        intent,
        _context(
            branch_hygiene={
                "hypothesis_generation_mode": "branch_local_followup",
                "protected_mechanism_ids": ["branch_other"],
            },
        ),
    )

    assert resolution.intent == intent
    assert resolution.diagnostics == {}
    assert resolution.tool_context_overrides == {}


def test_branch_authority_override_prevents_conflicting_required_guard(
    tmp_path,
) -> None:
    prepared_id = "prepared_generic_seed"
    branch_id = "existing_branch_mechanism"
    target_file = "policies/baseline_modules/local_search.py"
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            action="modify",
            target_file=target_file,
            hypothesis_text=(
                "Refine the existing branch-local mechanism instead of "
                "starting the prepared clean-focus mechanism."
            ),
            expected_effect="Improve the same branch-local evidence channel.",
            mechanism_changes=[
                {"id": branch_id, "change_type": "modify"},
            ],
            novelty_signature={
                "algorithm_family": "branch_local_authority_test",
                "target_file": target_file,
            },
            expected_telemetry={
                "activity": ["solver_algorithm_search_iterations"],
                "activation": [
                    f"solver_algorithm_context_records.{branch_id}_iterations"
                ],
                "budget": [f"solver_algorithm_phase_runtime_ms.{branch_id}"],
            },
        )
    )
    creative = _TargetIntentCreative(
        intent=_intent(prepared_id, target_file=target_file),
        hypothesis=hypothesis,
    )
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
        active_problem_boundary_surfaces=("solver_design",),
        branch_hygiene={
            "hypothesis_generation_mode": "branch_local_followup",
            "branch_followup_policy": "branch_local_followup_or_explicit_bridge",
            "protected_mechanism_ids": [branch_id],
        },
        launch_research_focus={
            "schema_version": "scion.launch_research_focus_prompt.v1",
            "taint": "prepared_launch_research_focus",
            "research_focus": {
                "required_mechanism_ids": [prepared_id],
                "next_required_direction": "Prepared clean-focus direction.",
            },
        },
    )
    session = AgenticProposalSession(
        creative,
        artifact_store=FileAgenticSessionArtifactStore(tmp_path / "artifacts"),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="campaign-target-intent-authority",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "branch-authority-conflict"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    selected = creative.hypothesis_contexts[0]["agentic_hypothesis_target_intent"]
    assert selected["intent"]["mechanism_id"] == branch_id
    assert "tool_context_overrides" not in selected["intent"]
    assert "tool_context_overrides" in selected
    authority = selected["host_adjustments"]["target_intent_authority"]
    assert authority["authority_status"] == (
        "prepared_focus_deferred_for_branch_followup"
    )
    effective_focus = creative.hypothesis_contexts[0]["launch_research_focus"][
        "research_focus"
    ]
    assert effective_focus["required_mechanism_ids"] == []
    assert effective_focus["deferred_required_mechanism_ids"] == [prepared_id]

    preview_refs = [
        Path(ref)
        for ref in output.tainted_artifact_refs
        if "self_check_preview_full" in ref
    ]
    assert preview_refs
    launch_guards = []
    for ref in preview_refs:
        payload = json.loads(ref.read_text(encoding="utf-8"))
        if payload.get("observation_type") != "schema_preview":
            continue
        hypothesis_payload = payload["structured_payload_full"]["hypothesis"]
        launch_guards.append(
            hypothesis_payload["launch_research_focus_required_mechanism_guard"]
        )
    assert launch_guards
    assert launch_guards[-1]["passed"] is True
    assert launch_guards[-1]["configured"] is False
