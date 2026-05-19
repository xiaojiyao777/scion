"""AgenticSessionCodeTools mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionCodeToolsMixin:
    def _run_code_context_tool_loop(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            prior_observations: list[ProposalObservation],
            code_context: Mapping[str, Any],
        ) -> list[ProposalObservation]:
            if self.tool_registry is None:
                return []
            if not self._supports_tool_selection():
                return self._run_code_context_fixed_tools(
                    context,
                    state,
                    hypothesis,
                    prior_observations,
                    selection_source="code_phase_required",
                )

            selector = getattr(self._creative, "select_tool", None)
            if not callable(selector):
                selector = getattr(self._creative, "plan_tool_call", None)
            if not callable(selector):
                return self._run_code_context_fixed_tools(
                    context,
                    state,
                    hypothesis,
                    prior_observations,
                    selection_source="code_phase_required",
                )

            observations: list[ProposalObservation] = []
            allowed_tools = self._code_phase_allowed_tools(context)
            max_calls = max(0, int(self._tool_loop_config.max_code_tool_calls))
            state.note(
                AgenticProposalPhase.INSPECT_INTERFACE,
                "Starting code-phase proposal tool loop for approved hypothesis.",
                metadata={
                    "selected_surface": hypothesis.change_locus,
                    "target_file": hypothesis.target_file,
                    "max_code_tool_calls": max_calls,
                    "allowed_tools": allowed_tools,
                },
            )
            while len(observations) < max_calls and allowed_tools:
                deferred = _pop_deferred_code_phase_tool_call(state)
                if deferred is None:
                    break
                name, args = deferred
                if name not in set(allowed_tools):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped deferred code-phase proposal tool outside allowed list.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "code_invalid_tool_selection",
                            "selection_source": "code_phase_planner",
                            "skip_reason": "invalid_deferred_tool",
                        },
                    )
                    continue
                if self._tool_loop_limit_reached(state):
                    self._record_loop_stop(state, self._current_loop_stop_reason(state))
                    break
                if _has_successful_code_phase_reusable_observation(
                    [*prior_observations, *observations],
                    name,
                    args,
                    hypothesis=hypothesis,
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped deferred code-phase proposal tool already completed successfully.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "selection_source": "code_phase_planner",
                            "skip_reason": "already_succeeded",
                        },
                    )
                    continue
                if (
                    name == "context.read_algorithm_file"
                    and _solver_design_code_algorithm_file_read_budget_exhausted(
                        context,
                        [*prior_observations, *observations],
                        hypothesis=hypothesis,
                        next_args=args,
                    )
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped deferred code-phase full algorithm-file read after solver_design read budget.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "selection_source": "code_phase_planner",
                            "skip_reason": "solver_design_code_file_read_budget_reserved",
                            "recommended_next_tool": "context.read_algorithm_symbol",
                        },
                    )
                    continue
                observations.append(
                    self._call_tool(
                        context,
                        state,
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        name,
                        args,
                        selection_source="code_phase_planner",
                        preserve_observation_chars=(
                            self._minimum_budgeted_observation_chars()
                        ),
                    )
                )
                if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
                    break
            while (
                len(observations) < max_calls
                and allowed_tools
                and not self._tool_loop_limit_reached(state)
            ):
                if self._code_phase_budget_reserved(state):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Stopped code-phase proposal tool loop to reserve patch self-check budget.",
                        metadata={
                            "stop_reason": "code_self_check_budget_reserved",
                            "tool_steps": state.tool_step_count,
                            "tool_calls": state.tool_call_count,
                            "remaining_tool_calls": self._remaining_tool_calls(state),
                            "remaining_steps": self._remaining_tool_steps(state),
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                        },
                    )
                    break

                all_observations = [*prior_observations, *observations]
                planner_context = {
                    "session_id": state.session_id,
                    "phase": AgenticProposalPhase.DRAFT_PATCH.value,
                    "code_phase": True,
                    "allowed_tools": allowed_tools,
                    "allowed_tool_specs": self._code_phase_allowed_tool_specs(context),
                    "tool_arg_guidance": self._code_tool_arg_guidance(
                        context,
                        hypothesis,
                        all_observations,
                    ),
                    "approved_hypothesis": _proposal_payload(hypothesis),
                    "code_context_summary": _code_context_tool_summary(code_context),
                    "remaining_steps": self._remaining_tool_steps(state),
                    "remaining_tool_calls": self._remaining_tool_calls(state),
                    "remaining_code_tool_calls": max(0, max_calls - len(observations)),
                    "reserved_for_self_check": {
                        "tool_calls": 4,
                        "steps": 4,
                        "purpose": (
                            "final Contract preview and algorithm smoke after patch "
                            "generation"
                        ),
                    },
                    "observations": [
                        _observation_selection_payload(observation)
                        for observation in all_observations
                    ],
                }
                try:
                    planned = selector(_sanitize_agentic_value(planner_context))
                except Exception as exc:
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner tool selection failed; using deterministic code-context fallback.",
                        metadata={
                            "status": "error",
                            "error": type(exc).__name__,
                            "error_code": "code_planner_exception",
                            "fallback": "code_phase_fixed_tool_plan",
                        },
                    )
                    return observations + self._run_code_context_fixed_tools(
                        context,
                        state,
                        hypothesis,
                        [*prior_observations, *observations],
                        selection_source="code_phase_fallback",
                    )

                if not planned or getattr(planned, "stop", False):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner stopped.",
                        metadata={"stop_reason": "code_planner_stop"},
                    )
                    break
                if isinstance(planned, Mapping) and planned.get("stop"):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner stopped.",
                        metadata={"stop_reason": "code_planner_stop"},
                    )
                    break
                if not isinstance(planned, Mapping):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner returned malformed tool-selection payload; using deterministic fallback.",
                        metadata={
                            "status": "error",
                            "error_code": "code_malformed_tool_selection",
                            "fallback": "code_phase_fixed_tool_plan",
                        },
                    )
                    return observations + self._run_code_context_fixed_tools(
                        context,
                        state,
                        hypothesis,
                        [*prior_observations, *observations],
                        selection_source="code_phase_fallback",
                    )

                name = str(
                    planned.get("tool_name")
                    or planned.get("name")
                    or planned.get("tool")
                    or ""
                )
                args = planned.get("args") or planned.get("input") or {}
                if not isinstance(args, Mapping):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner returned malformed tool arguments; using deterministic fallback.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "code_malformed_tool_args",
                            "fallback": "code_phase_fixed_tool_plan",
                        },
                    )
                    return observations + self._run_code_context_fixed_tools(
                        context,
                        state,
                        hypothesis,
                        [*prior_observations, *observations],
                        selection_source="code_phase_fallback",
                    )
                if name not in set(allowed_tools):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner selected a tool outside the allowed list; using deterministic fallback.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "code_invalid_tool_selection",
                            "fallback": "code_phase_fixed_tool_plan",
                        },
                    )
                    return observations + self._run_code_context_fixed_tools(
                        context,
                        state,
                        hypothesis,
                        [*prior_observations, *observations],
                        selection_source="code_phase_fallback",
                    )
                fingerprint = _tool_call_fingerprint(name, args)
                fuse_count = state.tool_call_fuse_counts.get(fingerprint, 0)
                if fuse_count >= self._tool_loop_config.max_repeated_tool_calls:
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner repeated a proposal tool call; using deterministic fallback.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "code_repeated_tool_call_fuse",
                            "fallback": "code_phase_fixed_tool_plan",
                        },
                    )
                    return observations + self._run_code_context_fixed_tools(
                        context,
                        state,
                        hypothesis,
                        [*prior_observations, *observations],
                        selection_source="code_phase_fallback",
                    )
                if _has_successful_code_phase_reusable_observation(
                    [*prior_observations, *observations],
                    name,
                    args,
                    hypothesis=hypothesis,
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase planner selected a proposal tool already completed successfully.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "code_already_succeeded",
                            "selection_source": "code_phase_planner",
                            "skip_reason": "already_succeeded",
                        },
                    )
                    break
                if (
                    name == "context.read_algorithm_file"
                    and _solver_design_code_algorithm_file_read_budget_exhausted(
                        context,
                        [*prior_observations, *observations],
                        hypothesis=hypothesis,
                        next_args=args,
                    )
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Stopped code-phase planner full algorithm-file reads after solver_design read budget.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "solver_design_code_file_read_budget_reserved",
                            "selection_source": "code_phase_planner",
                            "skip_reason": "solver_design_code_file_read_budget_reserved",
                            "recommended_next_tool": "context.read_algorithm_symbol",
                        },
                    )
                    break
                observation = self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.INSPECT_INTERFACE,
                    name,
                    args,
                    selection_source="code_phase_planner",
                )
                observations.append(observation)
                if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
                    break
                if (
                    observation.tool_name == "context.read_surface"
                    and _has_code_phase_surface_read(
                        [*prior_observations, *observations],
                        hypothesis,
                    )
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Code-phase selected-surface context is complete.",
                        metadata={
                            "stop_reason": "code_surface_context_satisfied",
                            "tool_name": observation.tool_name,
                            "selection_source": "code_phase_planner",
                        },
                    )
                    break

            combined = [*prior_observations, *observations]
            if not _has_code_phase_surface_read(combined, hypothesis):
                if self._code_phase_budget_reserved(state):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped code-phase required fallback tools to preserve final preview reserve.",
                        metadata={
                            "status": "skipped",
                            "selection_source": "code_phase_required",
                            "skip_reason": "code_self_check_budget_reserved",
                            "remaining_tool_calls": self._remaining_tool_calls(state),
                            "remaining_steps": self._remaining_tool_steps(state),
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                            "remaining_wall_time_sec": self._remaining_wall_time_sec(
                                state
                            ),
                        },
                    )
                else:
                    observations.extend(
                        self._run_code_context_fixed_tools(
                            context,
                            state,
                            hypothesis,
                            combined,
                            selection_source="code_phase_required",
                        )
                    )
            state.note(
                AgenticProposalPhase.INSPECT_INTERFACE,
                "Collected code-phase proposal tool observations.",
                metadata={
                    "tool_names": [observation.tool_name for observation in observations],
                    "error_count": sum(
                        1 for observation in observations if observation.is_error
                    ),
                },
            )
            return observations

    def _run_code_context_fixed_tools(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            prior_observations: list[ProposalObservation],
            *,
            selection_source: str,
        ) -> list[ProposalObservation]:
            calls: list[tuple[str, Mapping[str, Any]]] = []
            target_read_args = _solver_design_target_file_read_args(
                hypothesis,
                context=context,
                observations=prior_observations,
            )
            if target_read_args is not None and not _has_successful_reusable_observation(
                prior_observations,
                "context.read_algorithm_file",
                target_read_args,
                forced_surface=hypothesis.change_locus,
            ):
                calls.append(("context.read_algorithm_file", target_read_args))
            if not _has_code_phase_surface_read(prior_observations, hypothesis):
                args: dict[str, Any] = {
                    "surface": hypothesis.change_locus,
                    "detail": "full",
                    "max_code_chars": _APS_CODE_SURFACE_READ_CODE_CHARS,
                }
                if hypothesis.target_file:
                    args["target_file"] = hypothesis.target_file
                calls.append(("context.read_surface", args))
            if not _has_successful_tool(prior_observations, "context.read_branch_state"):
                calls.append(("context.read_branch_state", {}))
            if _is_solver_design_hypothesis(hypothesis) and not _has_successful_tool(
                prior_observations,
                "context.list_algorithm_files",
            ):
                calls.append(
                    (
                        "context.list_algorithm_files",
                        {"surface": "solver_design", "include_inactive": True},
                    )
                )

            observations: list[ProposalObservation] = []
            for name, args in calls:
                mandatory_surface_read = (
                    name == "context.read_surface"
                    and selection_source == "code_phase_required"
                )
                mandatory_target_read = (
                    name == "context.read_algorithm_file"
                    and selection_source in {"code_phase_required", "code_phase_fallback"}
                )
                if (
                    self._remaining_tool_calls(state) <= 2
                    or self._remaining_tool_steps(state) <= 2
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped code-phase fallback tool to reserve final preview tool slots.",
                        metadata={
                            "tool_name": name,
                            "status": "skipped",
                            "selection_source": selection_source,
                            "skip_reason": "code_self_check_tool_slot_reserved",
                            "remaining_tool_calls": self._remaining_tool_calls(state),
                            "remaining_steps": self._remaining_tool_steps(state),
                        },
                    )
                    break
                call_args: Mapping[str, Any] = args
                call_selection_source = selection_source
                preserve_observation_chars = 0
                if self._code_phase_budget_reserved(state) and not (
                    mandatory_surface_read or mandatory_target_read
                ):
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped code-phase fallback tool to reserve patch self-check budget.",
                        metadata={
                            "tool_name": name,
                            "status": "skipped",
                            "selection_source": selection_source,
                            "skip_reason": "code_self_check_budget_reserved",
                        },
                    )
                    continue
                if mandatory_surface_read or mandatory_target_read:
                    preserve_observation_chars = self._minimum_budgeted_observation_chars()
                    remaining_chars = self._remaining_observation_chars(state)
                    if remaining_chars <= preserve_observation_chars:
                        state.note(
                            AgenticProposalPhase.INSPECT_INTERFACE,
                            "Skipped mandatory code-phase context read to preserve patch self-check observation budget.",
                            metadata={
                                "tool_name": name,
                                "status": "skipped",
                                "selection_source": selection_source,
                                "skip_reason": "code_self_check_observation_budget_reserved",
                                "remaining_observation_chars": remaining_chars,
                                "preserved_observation_chars": preserve_observation_chars,
                            },
                        )
                        continue
                    target_read_available = (
                        target_read_args is not None
                        and _has_successful_reusable_observation(
                            [*prior_observations, *observations],
                            "context.read_algorithm_file",
                            target_read_args,
                            forced_surface=hypothesis.change_locus,
                        )
                    )
                    surface_context_available = _has_successful_tool(
                        [*prior_observations, *observations],
                        "context.read_surface",
                    )
                    surface_context_budget_pressure = (
                        surface_context_available
                        and remaining_chars <= _SELF_CHECK_PREVIEW_OBSERVATION_BUDGET_CHARS
                    )
                    if mandatory_surface_read and (
                        self._code_phase_budget_reserved(state)
                        or target_read_available
                        or surface_context_budget_pressure
                    ):
                        compact_chars = max(
                            0,
                            min(
                                _APS_SURFACE_READ_CODE_CHARS,
                                remaining_chars - preserve_observation_chars,
                            ),
                        )
                        call_args = {
                            **dict(args),
                            "detail": "compact",
                            "max_code_chars": compact_chars,
                        }
                        call_selection_source = "code_phase_required_compact"
                        state.note(
                            AgenticProposalPhase.INSPECT_INTERFACE,
                            "Compressed mandatory code-phase surface read to preserve patch self-check budget.",
                            metadata={
                                "tool_name": name,
                                "status": "compressed",
                                "selection_source": call_selection_source,
                                "skip_reason": "code_self_check_budget_reserved",
                                "remaining_observation_chars": remaining_chars,
                                "preserved_observation_chars": preserve_observation_chars,
                                "max_code_chars": compact_chars,
                                "target_read_available": target_read_available,
                                "surface_context_available": surface_context_available,
                                "surface_context_budget_pressure": (
                                    surface_context_budget_pressure
                                ),
                            },
                        )
                if self._tool_loop_limit_reached(state) and not (
                    (mandatory_surface_read or mandatory_target_read)
                    and self._current_loop_stop_reason(state)
                    == "observation_budget_exhausted"
                    and self._remaining_tool_calls(state) > 0
                    and self._remaining_tool_steps(state) > 0
                    and not self._session_timeout_reached(state)
                ):
                    self._record_loop_stop(state, self._current_loop_stop_reason(state))
                    break
                observations.append(
                    self._call_tool(
                        context,
                        state,
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        name,
                        call_args,
                        selection_source=call_selection_source,
                        preserve_observation_chars=preserve_observation_chars,
                    )
                )
            return observations
