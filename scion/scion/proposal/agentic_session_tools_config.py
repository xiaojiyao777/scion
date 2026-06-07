"""Stable tool-family constants for Agentic Proposal Session tools."""

from __future__ import annotations

_HOLDOUT_SUMMARY_TOOL = "feedback.query_holdout_summary"
_PLANNER_HIDDEN_PREVIEW_TOOLS = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)
_ACTIVE_SOLVER_TOOL_ALLOWLIST = frozenset(
    {
        "context.read_active_solver_map",
        "context.read_operator_registry",
        "context.read_algorithm_slice",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }
)
_ACTIVE_SOLVER_FILE_READ_TOOLS = frozenset(
    {
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }
)
_CODE_PHASE_TOOL_ALLOWLIST = frozenset(
    {
        "context.list_surfaces",
        "context.read_problem",
        "context.read_surface",
        "context.read_objective_policy",
        "context.read_champion_summary",
        "context.read_branch_state",
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    }
) | _ACTIVE_SOLVER_TOOL_ALLOWLIST
_SINGLE_SUCCESS_OBSERVATION_TOOLS = (
    "context.list_surfaces",
    "context.read_problem",
    "context.read_branch_state",
    "memory.query",
    "context.read_active_solver_map",
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
    "context.list_algorithm_files",
)
_ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS = 12000
_APS_SURFACE_READ_CODE_CHARS = 800
_APS_CODE_SURFACE_READ_CODE_CHARS = 12000
_APS_CODE_MODULE_SURFACE_READ_CODE_CHARS = 6000
_CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT = 5
