"""AgenticSessionCodeGuidance mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionCodeGuidanceMixin:
    def _code_phase_allowed_tools(
            self,
            context: ProposalToolContext,
        ) -> tuple[str, ...]:
            if self.tool_registry is None:
                return ()
            return _filter_code_phase_tool_names(
                self.tool_registry.allowed_tools(context),
                context,
            )

    def _code_phase_allowed_tool_specs(
            self,
            context: ProposalToolContext,
        ) -> tuple[dict[str, Any], ...]:
            if self.tool_registry is None:
                return ()
            allowed = set(self._code_phase_allowed_tools(context))
            return tuple(
                spec
                for spec in self.tool_registry.allowed_tool_specs(context)
                if spec.get("name") in allowed
            )

    def _code_phase_budget_reserved(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            return self._code_phase_wall_time_reserved(
                state
            ) or _code_phase_budget_reserved_for_config(
                self._tool_loop_config,
                state,
            )

    def _code_phase_wall_time_reserved(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            max_wall_time = max(0.0, float(self._tool_loop_config.max_wall_time_sec))
            if max_wall_time <= 0:
                return self._session_timeout_reached(state)
            reserve = min(
                _FINAL_PREVIEW_WALL_TIME_RESERVE_SEC,
                max_wall_time / 4.0,
            )
            return self._remaining_wall_time_sec(state) <= reserve

    def _code_tool_arg_guidance(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
        ) -> dict[str, Any]:
            feedback_args = _feedback_query_args(context)
            if hypothesis.change_locus and "surface" not in feedback_args:
                feedback_args["surface"] = hypothesis.change_locus
            read_surface_args: dict[str, Any] = {
                "surface": hypothesis.change_locus,
                "detail": "full",
                "max_code_chars": _APS_CODE_SURFACE_READ_CODE_CHARS,
            }
            if hypothesis.target_file:
                read_surface_args["target_file"] = hypothesis.target_file
            if _is_solver_design_algorithm_target(hypothesis.target_file):
                read_surface_args["section"] = "target_preview"
            if _is_solver_design_support_module_target(hypothesis.target_file):
                read_surface_args["max_code_chars"] = (
                    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS
                )
            guidance = {
                "context.read_surface": {
                    "purpose": (
                        "Inspect the full approved research object before writing "
                        "the patch. This is the code phase, so a full target-surface "
                        "read is allowed within budget."
                    ),
                    "recommended_args": read_surface_args,
                    "already_has_code_phase_surface_read": _has_code_phase_surface_read(
                        observations,
                        hypothesis,
                    ),
                },
                "context.read_branch_state": {
                    "recommended_args": {},
                    "purpose": "Check retry/failure state before deciding implementation risk.",
                },
                "memory.query": {
                    "recommended_args": {
                        "surface": hypothesis.change_locus,
                        "query": (
                            "implementation lessons, failed mechanisms, and useful "
                            f"history for {hypothesis.change_locus}"
                        ),
                    },
                },
                "feedback.query_screening": {
                    "recommended_args": feedback_args,
                    "scope_rule": "Use screening feedback to avoid repeating failed mechanisms.",
                },
                "feedback.query_runtime": {
                    "recommended_args": feedback_args,
                    "scope_rule": "Use runtime feedback to tune algorithmic work and time budgets.",
                },
                "context.read_problem": {"recommended_args": {}},
                "context.read_objective_policy": {"recommended_args": {}},
                "context.read_champion_summary": {"recommended_args": {}},
            }
            if _is_solver_design_hypothesis(hypothesis):
                algorithm_file_guidance = _algorithm_file_path_guidance(
                    context,
                    observations,
                )
                recommended_file_path = _recommended_algorithm_file_path(
                    algorithm_file_guidance,
                    hypothesis.target_file,
                )
                guidance["context.read_active_solver_design"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "include_file_previews": False,
                    },
                    "purpose": (
                        "Ground solver_design implementation against the active "
                        "branch/champion solver entrypoint and mechanism summary."
                    ),
                    "already_has_grounding": _has_successful_tool(
                        observations,
                        "context.read_active_solver_design",
                    ),
                }
                guidance["context.read_solver_call_graph"] = {
                    "recommended_args": {"surface": "solver_design"},
                    "purpose": (
                        "Confirm the active solver_design call chain before choosing "
                        "where the implementation belongs."
                    ),
                    "already_has_grounding": _has_successful_solver_call_graph_grounding(
                        observations
                    ),
                }
                guidance["context.list_algorithm_files"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "include_inactive": True,
                    },
                    "purpose": "List allowlisted active solver files before targeted reads.",
                    "consumer_tools": [
                        "context.read_algorithm_file",
                        "context.read_algorithm_symbol",
                    ],
                    "already_has_file_list": _has_successful_tool(
                        observations,
                        "context.list_algorithm_files",
                    ),
                }
                guidance["context.read_algorithm_file"] = {
                    **algorithm_file_guidance,
                    "recommended_args": {
                        "surface": "solver_design",
                        "file_path": recommended_file_path,
                        "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
                    },
                    "purpose": (
                        "Read one allowlisted active solver file when full source "
                        "is needed. Code phase has a small full-file read budget; "
                        "use context.read_algorithm_symbol for extra symbols after "
                        "the approved target and owning integration files are clear."
                    ),
                }
                guidance["context.read_algorithm_symbol"] = {
                    **algorithm_file_guidance,
                    "recommended_args": {
                        "surface": "solver_design",
                        "file_path": recommended_file_path,
                        "symbol": "solve",
                        "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    },
                    "purpose": "Read one symbol from an allowlisted active solver file.",
                }
            return guidance
