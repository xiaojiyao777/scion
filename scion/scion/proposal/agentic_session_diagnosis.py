"""AgenticSessionDiagnosis mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionDiagnosisMixin:
    def _run_hypothesis_observation_tools(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            *,
            selection_source: str = "fallback_selected",
            skip_successful_required_tools: set[str] | None = None,
        ) -> list[ProposalObservation]:
            calls: list[tuple[str, Mapping[str, Any]]] = [
                ("context.list_surfaces", {}),
                ("context.read_problem", {}),
            ]
            if _context_requires_solver_design_grounding(context):
                calls.extend(
                    (name, {"surface": "solver_design", "include_inactive": True})
                    for name in _SOLVER_DESIGN_FILE_DISCOVERY_TOOLS
                )
                calls.extend(
                    (name, {"surface": "solver_design"})
                    for name in _SOLVER_DESIGN_GROUNDING_TOOLS
                )
            calls.extend(
                [
                    ("memory.query", {}),
                    (
                        "feedback.query_screening",
                        _feedback_query_args(context),
                    ),
                    (
                        "feedback.query_runtime",
                        _feedback_query_args(context),
                    ),
                ]
            )
            skip_successful_required_tools = skip_successful_required_tools or set()
            required_tool_names = set(_fallback_required_context_tool_names(context))
            observations: list[ProposalObservation] = []
            for name, args in calls:
                if name in skip_successful_required_tools:
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Skipped fallback proposal tool already completed successfully.",
                        metadata={
                            "tool_name": name,
                            "status": "skipped",
                            "selection_source": selection_source,
                            "fallback": "fixed_tool_plan",
                            "skip_reason": "already_succeeded",
                        },
                    )
                    continue
                if self._diagnosis_budget_reserved(state) and (
                    self._missing_required_context_error(
                        observations,
                        context=context,
                    )
                    is None
                    or name not in required_tool_names
                ):
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Stopped fixed proposal tool plan to reserve self-check budget.",
                        metadata={
                            "tool_name": name,
                            "status": "skipped",
                            "selection_source": selection_source,
                            "fallback": "fixed_tool_plan",
                            "skip_reason": "self_check_budget_reserved",
                            "remaining_tool_calls": self._remaining_tool_calls(state),
                            "remaining_steps": self._remaining_tool_steps(state),
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                        },
                    )
                    break
                if (
                    name in {"feedback.query_screening", "feedback.query_runtime"}
                    and self._diagnosis_feedback_budget_reserved(state)
                    and self._missing_required_context_error(
                        observations,
                        context=context,
                    )
                    is None
                ):
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Stopped fixed proposal feedback plan to preserve self-check budget.",
                        metadata={
                            "tool_name": name,
                            "status": "skipped",
                            "selection_source": selection_source,
                            "fallback": "fixed_tool_plan",
                            "skip_reason": "feedback_budget_reserved",
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                        },
                    )
                    break
                if self._tool_loop_limit_reached(state):
                    self._record_loop_stop(state, self._current_loop_stop_reason(state))
                    break
                observation = self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.DIAGNOSE,
                    name,
                    args,
                    selection_source=selection_source,
                )
                observations.append(observation)
                if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
                    break
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Collected fixed proposal tool observations.",
                metadata={
                    "tool_names": [observation.tool_name for observation in observations],
                    "error_count": sum(
                        1 for observation in observations if observation.is_error
                    ),
                },
            )
            return observations

    def _run_required_context_preface(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
        ) -> list[ProposalObservation]:
            return _run_required_context_preface_tools(self, context, state)

    def _successful_tool_names(
            self,
            observations: list[ProposalObservation],
            *,
            context: ProposalToolContext | None = None,
        ) -> set[str]:
            return {
                observation.tool_name
                for observation in observations
                if _observation_satisfies_compact_requirement(context, observation)
            }

    def _run_initial_tool_loop(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
        ) -> list[ProposalObservation]:
            observations = (
                self._run_required_context_preface(context, state)
                if _context_requires_solver_design_grounding(context)
                else []
            )
            if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
                return observations
            if self._supports_tool_selection():
                observations = self._run_bounded_planner_tools(
                    context,
                    state,
                    observations,
                )
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    "Collected bounded planner proposal tool observations.",
                    metadata={
                        "tool_names": [o.tool_name for o in observations],
                        "stop_reason": state.loop_stop_reason or "planner_stop",
                        "error_count": sum(1 for o in observations if o.is_error),
                    },
                )
                return observations
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Creative layer has no tool-selection interface; using fixed APS-0 tool plan.",
                metadata={"fallback": "fixed_tool_plan"},
            )
            return observations + self._run_hypothesis_observation_tools(
                context,
                state,
                skip_successful_required_tools=self._successful_tool_names(
                    observations,
                    context=context,
                ),
            )

    def _supports_tool_selection(self) -> bool:
            if self._creative is None:
                return False
            return callable(getattr(self._creative, "select_tool", None)) or callable(
                getattr(self._creative, "plan_tool_call", None)
            )

    def _fallback_after_planner_error(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            observations: list[ProposalObservation],
            *,
            error_code: str,
            tool_name: str | None,
        ) -> list[ProposalObservation]:
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Selected deterministic fallback proposal tool plan.",
                metadata={
                    "status": "fallback_selected",
                    "error_code": error_code,
                    "tool_name": tool_name,
                    "fallback": "fixed_tool_plan",
                    "selection_source": "fallback_selected",
                },
            )
            return observations + self._run_hypothesis_observation_tools(
                context,
                state,
                selection_source="fallback_selected",
                skip_successful_required_tools=self._successful_tool_names(
                    observations,
                    context=context,
                ),
            )

    def _required_context_satisfied(
            self,
            observations: list[ProposalObservation],
        ) -> bool:
            return self._missing_required_context_error(observations) is None

    def _planner_context_satisfied(
            self,
            context: ProposalToolContext,
            observations: list[ProposalObservation],
        ) -> bool:
            return _planner_policy_context_satisfied(
                self.tool_registry,
                context,
                observations,
            )

    def _missing_planner_context_error(
            self,
            context: ProposalToolContext,
            observations: list[ProposalObservation],
        ) -> str | None:
            return _planner_missing_context_error(
                self.tool_registry,
                context,
                observations,
            )

    def _available_compact_feedback_tools(
            self,
            context: ProposalToolContext,
        ) -> tuple[str, ...]:
            return _planner_available_compact_feedback_tools(self.tool_registry, context)

    def _planner_observation_requires_fallback(
            self,
            observation: ProposalObservation,
        ) -> bool:
            return _policy_planner_observation_requires_fallback(observation)

    def _fatal_observation_error(
            self,
            observations: list[ProposalObservation],
        ) -> str | None:
            fatal_tools = {"context.list_surfaces", "context.read_problem"}
            for observation in observations:
                if not observation.is_error:
                    continue
                if observation.tool_name in fatal_tools:
                    return (
                        f"{observation.tool_name}: "
                        f"{_enum_value(observation.failure_code)}: "
                        f"{observation.summary}"
                    )
            return None

    def _missing_required_context_error(
            self,
            observations: list[ProposalObservation],
            *,
            context: ProposalToolContext | None = None,
        ) -> str | None:
            return _policy_missing_required_context_error(
                observations,
                context=context,
            )
