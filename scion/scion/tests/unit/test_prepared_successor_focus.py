from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from scion.proposal.engine import (
    _split_hypothesis_context,
    _split_hypothesis_target_intent_context,
)
from scion.proposal.target_intent_authority import (
    launch_focus_prepared_successor_conflict,
    resolve_target_intent_authority,
)
from scion.proposal.tools.models import ProposalToolContext
from scion.tests.unit.agentic_schema_test_support import (
    ProposalToolRegistry,
    _cvrp_context,
    _valid_hypothesis_payload,
)

REVIEWED_ID = "large_instance_intra_route_two_opt_seed"
REVIEWED_ID_2 = "bounded_2node_cross_exchange"
SUCCESSOR_ID = "bounded_local_search_variant_probe"
SUCCESSOR_FAMILY = "bounded_local_search_variant"
DEFAULT_AVOID = "route-pressure acceptance variants"


def _branch_hygiene(*, protected: bool = True, allowed: bool = False) -> dict:
    hygiene = {
        "hypothesis_generation_mode": "same_mechanism_only",
        "branch_followup_policy": "same_mechanism_followup_only",
        "same_mechanism_followup_required": True,
        "same_mechanism_allowed_actions": [
            "tune",
            "integrate",
            "repair",
            "parameterize",
            "telemetry_wiring",
        ],
    }
    if protected:
        hygiene["protected_mechanism_ids"] = [REVIEWED_ID]
    if allowed:
        hygiene["allowed_mechanism_ids"] = [REVIEWED_ID]
    return hygiene


def _branch_hygiene_guidance() -> str:
    return (
        "branch_code_status=active_current; "
        "branch_followup_policy=same_mechanism_followup_only; "
        f"protected_mechanism_ids={REVIEWED_ID}; "
        "same_mechanism_allowed_actions=tune,integrate,repair,parameterize,"
        "telemetry_wiring. The next hypothesis on this branch must keep those "
        "protected mechanism ids."
    )


def _successor_launch_focus(*, flat: bool = False) -> dict:
    focus = {
        "reviewed_mechanism_ids": [REVIEWED_ID, REVIEWED_ID_2],
        "successor_opportunity_families": [SUCCESSOR_FAMILY],
        "default_avoid_directions": [DEFAULT_AVOID],
        "next_required_direction": "Test a materially different successor.",
    }
    if flat:
        return dict(focus)
    return {
        "schema_version": "scion.launch_research_focus_prompt.v1",
        "taint": "prepared_launch_research_focus",
        "research_focus": focus,
    }


def _tool_context(
    *,
    branch_hygiene: dict | None = None,
    launch_research_focus: dict | None = None,
) -> ProposalToolContext:
    return ProposalToolContext(
        session_id="session-prepared-successor",
        campaign_id="campaign-prepared-successor",
        branch_hygiene=branch_hygiene or _branch_hygiene(),
        launch_research_focus=launch_research_focus or _successor_launch_focus(),
    )


def _prompt_context() -> dict:
    return {
        "problem_summary": "Generic routing problem.",
        "research_surfaces": "solver_design",
        "objective_policy_guidance": "Optimize declared objective only.",
        "solver_mechanics": "Use adapter-declared solver mechanics.",
        "champion_operators_code": "def solve(instance):\n    return instance\n",
        "champion_stats": "champion=v1",
        "active_problem_boundary_surfaces": "solver_design",
        "targetable_files": "policies/baseline_modules/local_search.py",
        "branch_hygiene": _branch_hygiene(),
        "branch_hygiene_guidance": _branch_hygiene_guidance(),
        "branch_followup_policy": "same_mechanism_followup_only",
        "launch_research_focus": _successor_launch_focus(),
    }


def _schema_context(tmp_path: Path) -> ProposalToolContext:
    return replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
        branch_hygiene=_branch_hygiene(),
        launch_research_focus=_successor_launch_focus(),
    )


def _hypothesis_payload(mechanism_ids: list[str]) -> dict:
    return _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/local_search.py",
        hypothesis_text=(
            "Test a bounded local-search successor with direct objective "
            "evidence and protected runtime behavior."
        ),
        expected_effect="Improve total distance through bounded local search.",
        mechanism_changes=[
            {"id": mechanism_id, "change_type": "modify"}
            for mechanism_id in mechanism_ids
        ],
        novelty_signature={
            "algorithm_family": "bounded_local_search",
            "construction_strategy": "unchanged_seed_pool",
            "improvement_strategy": "_".join(mechanism_ids),
            "acceptance_strategy": "strict_improvement_only",
            "runtime_budget_strategy": "bounded_candidate_pool",
        },
    )


def test_successor_focus_rejects_reviewed_protected_target_intent() -> None:
    context = _tool_context()

    conflict = launch_focus_prepared_successor_conflict(context)
    resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": REVIEWED_ID,
            "mechanism_sketch": "Repeat the reviewed mechanism.",
        },
        context,
    )

    assert conflict["active"] is True
    assert conflict["reviewed_branch_mechanism_ids"] == [REVIEWED_ID]
    assert resolution.intent["mechanism_id"] == REVIEWED_ID
    assert resolution.intent["mechanism_id_status"] == (
        "prepared_successor_focus_rejects_reviewed_mechanism"
    )
    assert resolution.diagnostics["target_intent_rejected"] is True
    assert resolution.diagnostics["rejected_mechanism_id"] == REVIEWED_ID
    assert resolution.tool_context_overrides == {}


def test_successor_focus_rejects_second_reviewed_target_intent() -> None:
    context = _tool_context()

    resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": REVIEWED_ID_2,
            "mechanism_family": SUCCESSOR_FAMILY,
        },
        context,
    )

    assert resolution.intent["mechanism_id_status"] == (
        "prepared_successor_focus_rejects_reviewed_mechanism"
    )
    assert resolution.diagnostics["target_intent_rejected"] is True
    assert resolution.diagnostics["rejected_mechanism_id"] == REVIEWED_ID_2


def test_successor_focus_allows_new_bounded_sibling_target_intent() -> None:
    context = _tool_context()

    resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": "bounded_3node_ejection_chain_probe",
            "mechanism_family": SUCCESSOR_FAMILY,
        },
        context,
    )

    assert "mechanism_id_status" not in resolution.intent
    assert resolution.diagnostics == {}


def test_successor_focus_detects_allowed_only_reviewed_branch_id() -> None:
    context = _tool_context(branch_hygiene=_branch_hygiene(protected=False, allowed=True))

    conflict = launch_focus_prepared_successor_conflict(context)

    assert conflict["active"] is True
    assert conflict["branch_allowed_mechanism_ids"] == [REVIEWED_ID]
    assert conflict["reviewed_branch_mechanism_ids"] == [REVIEWED_ID]


def test_successor_focus_accepts_flat_launch_focus_payload() -> None:
    context = _tool_context(launch_research_focus=_successor_launch_focus(flat=True))

    conflict = launch_focus_prepared_successor_conflict(context)

    assert conflict["active"] is True
    assert conflict["reviewed_mechanism_ids"] == [REVIEWED_ID, REVIEWED_ID_2]
    assert conflict["successor_opportunity_families"] == [SUCCESSOR_FAMILY]


def test_required_mechanism_ids_keep_existing_branch_authority() -> None:
    context = _tool_context(
        launch_research_focus={
            "research_focus": {
                "required_mechanism_ids": ["prepared_required_seed"],
                "reviewed_mechanism_ids": [REVIEWED_ID],
                "successor_opportunity_families": [SUCCESSOR_FAMILY],
            },
        }
    )

    conflict = launch_focus_prepared_successor_conflict(context)
    resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": REVIEWED_ID,
        },
        context,
    )

    assert conflict["active"] is False
    assert resolution.intent["mechanism_id"] == REVIEWED_ID
    assert resolution.intent["mechanism_id_status"] == (
        "prepared_focus_deferred_for_branch_followup"
    )


def test_successor_focus_prompts_do_not_force_reviewed_same_mechanism() -> None:
    context = _prompt_context()

    target_blocks, target_user = _split_hypothesis_target_intent_context(context)
    hypothesis_blocks, hypothesis_user = _split_hypothesis_context(context)
    target_text = "\n\n".join(
        str(block.get("text") or "") for block in target_blocks
    ) + target_user
    hypothesis_text = "\n\n".join(
        str(block.get("text") or "") for block in hypothesis_blocks
    ) + hypothesis_user

    for prompt_text in (target_text, hypothesis_text):
        assert "## Prepared Successor Focus" in prompt_text
        assert REVIEWED_ID in prompt_text
        assert SUCCESSOR_FAMILY in prompt_text
        assert "do not select or repeat a reviewed mechanism id" in prompt_text
        assert "## Same-Mechanism Follow-up Constraints" not in prompt_text
        assert "must keep those protected mechanism ids" not in prompt_text

    assert "Select a target intent for the protected mechanism" not in target_user


def test_successor_focus_prompts_render_on_clean_successor_branch() -> None:
    context = _prompt_context()
    context["branch_hygiene"] = {
        "hypothesis_generation_mode": "open_exploration",
        "branch_followup_policy": "open_exploration_allowed",
        "same_mechanism_followup_required": False,
        "protected_mechanism_ids": [],
        "allowed_mechanism_ids": [],
    }
    context["branch_hygiene_guidance"] = ""
    context["branch_followup_policy"] = "open_exploration_allowed"

    conflict = launch_focus_prepared_successor_conflict(context)
    target_blocks, target_user = _split_hypothesis_target_intent_context(context)
    target_text = "\n\n".join(
        str(block.get("text") or "") for block in target_blocks
    ) + target_user

    assert conflict["active"] is False
    assert conflict["configured"] is True
    assert "## Prepared Successor Focus" in target_text
    assert REVIEWED_ID in target_text
    assert SUCCESSOR_FAMILY in target_text
    assert DEFAULT_AVOID in target_text
    assert "Test a materially different successor." in target_text
    assert "do not select or repeat a reviewed mechanism id" in target_text
    assert "Do not spend this target intent on default_avoid_directions" in (
        target_text
    )
    assert "## Same-Mechanism Follow-up Constraints" not in target_text


def test_successor_focus_rejects_default_avoid_target_intent() -> None:
    context = _tool_context(
        branch_hygiene={
            "hypothesis_generation_mode": "open_exploration",
            "branch_followup_policy": "open_exploration_allowed",
            "same_mechanism_followup_required": False,
            "protected_mechanism_ids": [],
            "allowed_mechanism_ids": [],
        }
    )

    resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/acceptance.py",
            "mechanism_id": "route_pressure_acceptance",
            "mechanism_family": "destroy_repair_selection",
        },
        context,
    )

    diagnostics = resolution.diagnostics
    assert resolution.intent["mechanism_id_status"] == (
        "prepared_launch_focus_default_avoid_rejects_target_intent"
    )
    assert diagnostics["target_intent_rejected"] is True
    assert diagnostics["matched_default_avoid_direction"] == DEFAULT_AVOID
    assert diagnostics["matched_default_avoid_tokens"] == [
        "route",
        "pressure",
        "acceptance",
    ]

    variant_resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/acceptance.py",
            "mechanism_id": "variance_tempered_acceptance",
            "mechanism_family": "destroy_repair_selection",
        },
        context,
    )

    assert variant_resolution.intent["mechanism_id_status"] == (
        "prepared_launch_focus_default_avoid_rejects_target_intent"
    )
    assert variant_resolution.diagnostics["matched_default_avoid_tokens"] == [
        "acceptance",
    ]

    unrelated_file_resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/acceptance.py",
            "mechanism_id": "risk_aware_capacity_probe",
            "mechanism_family": "destroy_repair_selection",
        },
        context,
    )

    assert "mechanism_id_status" not in unrelated_file_resolution.intent
    assert unrelated_file_resolution.diagnostics == {}

    generic_route_resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/destroy_repair.py",
            "mechanism_id": "route_entropy_removal",
            "mechanism_family": "destroy_repair_selection",
        },
        context,
    )

    assert "mechanism_id_status" not in generic_route_resolution.intent
    assert generic_route_resolution.diagnostics == {}


def test_successor_default_avoid_explicit_identity_does_not_block_sibling() -> None:
    focus = _successor_launch_focus()
    focus["research_focus"]["default_avoid_directions"] = [
        "unchanged bounded_interroute_2opt_bridge local-search bridge"
    ]
    context = _tool_context(
        branch_hygiene={
            "hypothesis_generation_mode": "open_exploration",
            "branch_followup_policy": "open_exploration_allowed",
            "same_mechanism_followup_required": False,
            "protected_mechanism_ids": [],
            "allowed_mechanism_ids": [],
        },
        launch_research_focus=focus,
    )

    exact_resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": "bounded_interroute_2opt_bridge",
            "mechanism_family": "bounded_local_search_variant",
        },
        context,
    )

    assert exact_resolution.intent["mechanism_id_status"] == (
        "prepared_launch_focus_default_avoid_rejects_target_intent"
    )
    assert exact_resolution.diagnostics["matched_default_avoid_mode"] == (
        "explicit_mechanism_identity"
    )

    sibling_resolution = resolve_target_intent_authority(
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": "bounded_2route_reinsertion_polish",
            "mechanism_family": "bounded_local_search_variant",
        },
        context,
    )

    assert "mechanism_id_status" not in sibling_resolution.intent
    assert sibling_resolution.diagnostics == {}


def test_rejected_target_intent_does_not_bind_formal_hypothesis() -> None:
    context = _prompt_context()
    context["agentic_hypothesis_target_intent"] = {
        "intent": {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/local_search.py",
            "mechanism_id": REVIEWED_ID,
        },
        "host_adjustments": {
            "target_intent_authority": {
                "authority_status": (
                    "prepared_successor_focus_rejects_reviewed_mechanism"
                ),
                "reviewed_mechanism_ids": [REVIEWED_ID],
                "successor_opportunity_families": [SUCCESSOR_FAMILY],
            },
        },
    }

    _blocks, hypothesis_user = _split_hypothesis_context(context)

    assert "Selected target-intent binding was rejected" in hypothesis_user
    assert "Do not use reviewed mechanism ids" in hypothesis_user
    assert f"Write formal `mechanism_changes[].id` as `{REVIEWED_ID}`" not in (
        hypothesis_user
    )


def test_default_avoid_rejected_target_intent_does_not_bind_formal_hypothesis() -> None:
    context = _prompt_context()
    rejected_id = "route_pressure_acceptance"
    context["agentic_hypothesis_target_intent"] = {
        "intent": {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_modules/acceptance.py",
            "mechanism_id": rejected_id,
            "mechanism_family": "destroy_repair_selection",
        },
        "host_adjustments": {
            "target_intent_authority": {
                "authority_status": (
                    "prepared_launch_focus_default_avoid_rejects_target_intent"
                ),
                "target_intent_rejected": True,
                "rejected_mechanism_id": rejected_id,
                "matched_default_avoid_direction": DEFAULT_AVOID,
            },
        },
    }

    _blocks, hypothesis_user = _split_hypothesis_context(context)

    assert "Selected target-intent binding was rejected" in hypothesis_user
    assert "Rejection status" in hypothesis_user
    assert "default_avoid_directions" in hypothesis_user
    assert f"Write formal `mechanism_changes[].id` as `{rejected_id}`" not in (
        hypothesis_user
    )
    assert "Selected target-intent binding: this formal hypothesis must keep" not in (
        hypothesis_user
    )


def test_schema_preview_allows_successor_on_reviewed_same_mechanism_branch(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _hypothesis_payload([SUCCESSOR_ID])},
        _schema_context(tmp_path),
    )

    section = preview.structured_payload["hypothesis"]
    branch_guard = section["branch_continuation_guard"]
    reviewed_guard = section["launch_research_focus_reviewed_mechanism_guard"]
    assert section["passed"] is True
    assert branch_guard["passed"] is True
    assert branch_guard["branch_authority_status"] == (
        "superseded_by_prepared_successor_focus"
    )
    assert branch_guard["candidate_routing"] == "clean_successor_required"
    assert reviewed_guard["passed"] is True
    assert reviewed_guard["configured"] is True


def test_schema_preview_rejects_reviewed_mechanism_repeat(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _hypothesis_payload([REVIEWED_ID])},
        _schema_context(tmp_path),
    )

    section = preview.structured_payload["hypothesis"]
    reviewed_guard = section["launch_research_focus_reviewed_mechanism_guard"]
    assert section["passed"] is False
    assert reviewed_guard["passed"] is False
    assert reviewed_guard["failure_code"] == (
        "launch_research_focus_reviewed_mechanism_repeat"
    )
    assert reviewed_guard["matched_reviewed_mechanism_ids"] == [REVIEWED_ID]
    assert SUCCESSOR_FAMILY in reviewed_guard["retry_constraint"]

    second_preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _hypothesis_payload([REVIEWED_ID_2])},
        _schema_context(tmp_path),
    )

    second_section = second_preview.structured_payload["hypothesis"]
    second_guard = second_section["launch_research_focus_reviewed_mechanism_guard"]
    assert second_section["passed"] is False
    assert second_guard["passed"] is False
    assert second_guard["matched_reviewed_mechanism_ids"] == [REVIEWED_ID_2]


def test_schema_preview_rejects_mixed_reviewed_and_successor_mechanisms(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _hypothesis_payload([REVIEWED_ID, SUCCESSOR_ID])},
        _schema_context(tmp_path),
    )

    section = preview.structured_payload["hypothesis"]
    reviewed_guard = section["launch_research_focus_reviewed_mechanism_guard"]
    assert section["passed"] is False
    assert reviewed_guard["passed"] is False
    assert reviewed_guard["matched_reviewed_mechanism_ids"] == [REVIEWED_ID]
