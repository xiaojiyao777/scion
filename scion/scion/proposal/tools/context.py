"""Context-reading proposal tools."""

from __future__ import annotations

from pydantic import BaseModel

from scion.proposal.context_manager import (
    _build_objective_policy_guidance,
    _build_problem_summary,
    _get_adapter_problem_spec,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.feedback import _diagnostic_surface_priorities
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)
from scion.proposal.tools.preview import (
    _active_problem_boundary_constraint_payload,
    _forced_surface_constraint_payload,
)
from scion.proposal.tools.surface import (
    _surface_list_for_context,
    _surface_listing_payload,
    _surfaces,
)
from scion.proposal.tools.utils import (
    _attr,
    _limit_text,
    _model_payload,
)


class ContextListSurfacesTool(_BaseReadOnlyTool):
    name = "context.list_surfaces"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        declared_surfaces = _surfaces(context)
        surfaces = _surface_list_for_context(context, declared_surfaces)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "surface_count": len(surfaces),
            "total_declared_surface_count": len(declared_surfaces),
            "surfaces": [_surface_listing_payload(surface) for surface in surfaces],
            "diagnostic_surface_priorities": _diagnostic_surface_priorities(
                context,
                declared_surfaces,
            ),
            "detail": "compact",
            "forced_surface_constraint": _forced_surface_constraint_payload(context),
            "active_problem_boundary_constraint": (
                _active_problem_boundary_constraint_payload(context)
            ),
        }
        return self._observation(
            context,
            observation_type="surface_list",
            summary=f"Returned {len(surfaces)} declared research surface(s).",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadProblemTool(_BaseReadOnlyTool):
    name = "context.read_problem"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        summary = _problem_summary(context)
        problem_object = _problem_object(context)
        solver_mechanics = _solver_mechanics(context)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "problem_spec_hash": context.problem_spec_hash,
            "summary": _limit_text(summary, 12000),
            "summary_truncated": len(summary) > 12000,
            "problem_object": _limit_text(problem_object, 20000),
            "problem_object_truncated": len(problem_object) > 20000,
            "solver_mechanics": _limit_text(solver_mechanics, 20000),
            "solver_mechanics_truncated": len(solver_mechanics) > 20000,
        }
        return self._observation(
            context,
            observation_type="problem_summary",
            summary="Returned adapter/spec-rendered problem summary.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadObjectivePolicyTool(_BaseReadOnlyTool):
    name = "context.read_objective_policy"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        adapter_spec = (
            _get_adapter_problem_spec(context.adapter) or context.problem_spec
        )
        rendered = _build_objective_policy_guidance(adapter_spec)
        objectives = [
            _model_payload(obj)
            for obj in list(_attr(adapter_spec, "objectives", []) or [])
        ]
        policy = _model_payload(_attr(adapter_spec, "objective_policy", None))
        payload = {
            "policy": policy,
            "objectives": objectives,
            "rendered_summary": rendered,
        }
        return self._observation(
            context,
            observation_type="objective_policy",
            summary="Returned declared objective policy and metric specs.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadChampionSummaryTool(_BaseReadOnlyTool):
    name = "context.read_champion_summary"
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        champion = context.champion
        if champion is None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary="No champion snapshot is available.",
            )
        operator_pool = []
        for name, op in sorted((champion.operator_pool or {}).items()):
            operator_pool.append(
                {
                    "name": name,
                    "file_path": _attr(op, "file_path"),
                    "category": _attr(op, "category"),
                    "weight": _attr(op, "weight"),
                    "class_name": _attr(op, "class_name"),
                }
            )
        payload = {
            "operator_count": len(operator_pool),
            "operator_pool": operator_pool,
            "solver_config_hash": champion.solver_config_hash,
            "code_snapshot_hash": champion.code_snapshot_hash,
            "has_code_snapshot": bool(champion.code_snapshot_path),
        }
        return self._observation(
            context,
            observation_type="champion_summary",
            summary="Returned champion artifact inventory.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadBranchStateTool(_BaseReadOnlyTool):
    name = "context.read_branch_state"
    permission = ProposalToolPermission.READ_PUBLIC_CONTEXT

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        branch = context.branch
        if branch is None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary="No branch state is available.",
            )
        state = _attr(branch, "state")
        payload = {
            "branch_id": _attr(branch, "branch_id"),
            "state": _model_payload(state),
            "base_champion_id": _attr(branch, "base_champion_id"),
            "base_champion_hash": _attr(branch, "base_champion_hash"),
            "current_code_hash": _attr(branch, "current_code_hash"),
            "last_clean_code_hash": _attr(branch, "last_clean_code_hash"),
            "retry_count": _attr(branch, "retry_count"),
            "failure_codes": list(_attr(branch, "failure_codes", []) or []),
            "pending_retry": bool(_attr(branch, "pending_retry", False)),
            "blocked_rounds": _attr(branch, "blocked_rounds"),
            "consecutive_llm_retries": _attr(branch, "consecutive_llm_retries"),
            "infra_block_count": _attr(branch, "infra_block_count"),
            "direction": _attr(branch, "direction"),
            "weight_revision": _attr(branch, "weight_revision"),
        }
        return self._observation(
            context,
            observation_type="branch_state",
            summary="Returned current branch state and retry/failure counters.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


def _problem_summary(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_problem_summary"
    ):
        return str(context.adapter.render_problem_summary())
    spec = context.problem_spec
    if spec is None:
        return ""
    if hasattr(spec, "name") and hasattr(spec, "operator_categories"):
        return _build_problem_summary(spec, adapter=context.adapter)
    lines = []
    display = _attr(spec, "display_name") or _attr(spec, "name") or _attr(spec, "id")
    if display:
        lines.append(f"Name: {display}")
    description = _attr(spec, "description")
    if description:
        lines.append(f"Description: {description}")
    surfaces = _surfaces(context)
    if surfaces:
        lines.append(
            "Research loci: "
            + ", ".join(str(_attr(surface, "name")) for surface in surfaces)
        )
    search_space = _attr(spec, "search_space")
    editable = _attr(search_space, "editable", [])
    frozen = _attr(search_space, "frozen", [])
    if editable:
        lines.append("Editable files: " + ", ".join(str(v) for v in editable))
    if frozen:
        lines.append(
            "Frozen files (do not modify): " + ", ".join(str(v) for v in frozen)
        )
    return "\n".join(lines)


def _problem_object(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_problem_object"
    ):
        return str(context.adapter.render_problem_object())
    return ""


def _solver_mechanics(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_solver_mechanics"
    ):
        return str(context.adapter.render_solver_mechanics())
    return ""


__all__ = [
    "ContextListSurfacesTool",
    "ContextReadBranchStateTool",
    "ContextReadChampionSummaryTool",
    "ContextReadObjectivePolicyTool",
    "ContextReadProblemTool",
]
