"""Exact ownership maps for the direct V3 proposal contexts."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.context_snapshot import (
    ProposalContextSnapshot,
    ProposalPhase,
    SafeProposalInputExtractor,
)
from scion.proposal.solver_design_guidance import RENDERER_INPUTS_KEY


def _owners(
    owner: str,
    keys: tuple[str, ...],
) -> dict[str, str]:
    return {key: owner for key in keys}


HYPOTHESIS_CONTEXT_OWNER_MAP = {
    **_owners(
        "static.problem",
        (
            "problem_summary",
            "problem_object",
            "solver_mechanics",
            "champion_version",
            "research_surfaces",
            "available_actions",
            "existing_target_files",
            "create_path_patterns",
            "champion_stats",
            "objective_policy_guidance",
            "problem_measurement_diagnostics",
        ),
    ),
    **_owners(
        "static.source_index",
        ("champion_operators_code", "branch_current_code"),
    ),
    **_owners(
        "static.task_constraints",
        (
            "branch_id",
            "research_question",
            "seed",
        ),
    ),
    **_owners(
        "evidence.screening",
        ("experiment_history",),
    ),
    **_owners(
        "evidence.safe_pre_protocol",
        ("last_research_rejection",),
    ),
    RENDERER_INPUTS_KEY: "renderer_inputs",
}


CODE_CONTEXT_OWNER_MAP = {
    **_owners(
        "static.problem",
        (
            "problem_summary",
            "problem_object",
            "solver_mechanics",
            "champion_version",
            "research_surface",
            "operator_interface_spec",
            "import_whitelist",
            "active_subject_code_constraints",
            "problem_id",
        ),
    ),
    **_owners(
        "static.approved_hypothesis",
        ("approved_hypothesis",),
    ),
    **_owners(
        "static.source_index",
        ("editable_source_context",),
    ),
    **_owners(
        "static.task_constraints",
        (
            "branch_id",
            "editable_patterns",
            "frozen_patterns",
            "seed",
        ),
    ),
    RENDERER_INPUTS_KEY: "renderer_inputs",
}


_EXTRACTORS = {
    "hypothesis": SafeProposalInputExtractor.with_owner_map(
        HYPOTHESIS_CONTEXT_OWNER_MAP,
        required_keys=frozenset(
            {
                "problem_summary",
                "branch_id",
                "research_surfaces",
                "champion_operators_code",
                "champion_stats",
            }
        ),
    ),
    "code": SafeProposalInputExtractor.with_owner_map(
        CODE_CONTEXT_OWNER_MAP,
        required_keys=frozenset(
            {
                "problem_summary",
                "branch_id",
                "approved_hypothesis",
                "editable_source_context",
                "operator_interface_spec",
                "editable_patterns",
                "frozen_patterns",
            }
        ),
    ),
}


def proposal_context_snapshot(
    phase: ProposalPhase,
    context: Mapping[str, Any],
) -> ProposalContextSnapshot:
    inputs = _EXTRACTORS[phase].extract(phase=phase, context=context)
    return ProposalContextSnapshot.from_safe_inputs(inputs)


__all__ = [
    "CODE_CONTEXT_OWNER_MAP",
    "HYPOTHESIS_CONTEXT_OWNER_MAP",
    "proposal_context_snapshot",
]
