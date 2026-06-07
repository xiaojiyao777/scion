"""AgenticSessionPlannerLoop mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *
from scion.proposal.session_trace_index import attach_agentic_trace_context


class AgenticSessionPlannerLoopMixin:
    def _run_bounded_planner_tools(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            initial_observations: list[ProposalObservation] | None = None,
        ) -> list[ProposalObservation]:
            observations: list[ProposalObservation] = list(initial_observations or [])
            selector = getattr(self._creative, "select_tool", None)
            if not callable(selector):
                selector = getattr(self._creative, "plan_tool_call", None)
            if not callable(selector):
                return observations + self._run_hypothesis_observation_tools(
                    context,
                    state,
                    skip_successful_required_tools=self._successful_tool_names(
                        observations,
                        context=context,
                    ),
                )

            observations.extend(
                _run_deterministic_compact_feedback_prefetch(
                    self,
                    context,
                    state,
                    observations,
                    phase=AgenticProposalPhase.DIAGNOSE,
                    source="deterministic_prefetch",
                )
            )
            if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
                return observations
            if self._planner_context_satisfied(
                context,
                observations,
            ) and not _creative_declares_hypothesis_planner_needed(
                self._creative,
                context,
                observations,
            ):
                self._record_loop_stop(state, "required_context_satisfied")
                return observations

            planner_decisions = 0
            max_planner_decisions = max(
                1,
                (
                    int(self._tool_loop_config.max_steps)
                    + int(self._tool_loop_config.max_tool_calls)
                )
                * 2,
            )
            while not self._tool_loop_limit_reached(state):
                planner_decisions += 1
                if planner_decisions > max_planner_decisions:
                    missing = self._missing_planner_context_error(context, observations)
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner proposal tool loop exceeded the selection decision budget.",
                        metadata={
                            "status": (
                                "framework_required_completion"
                                if missing
                                else "skipped"
                            ),
                            "error_code": "planner_selection_limit",
                            "detail": missing,
                        },
                    )
                    if missing is not None:
                        return self._complete_required_context_after_planner_gap(
                            context,
                            state,
                            observations,
                            error_code="planner_selection_limit",
                            tool_name=None,
                            detail=missing,
                        )
                    self._record_loop_stop(
                        state,
                        "planner_selection_limit",
                        error_code="planner_selection_limit",
                    )
                    break
                if self._planner_context_satisfied(
                    context,
                    observations,
                ) and not _creative_declares_hypothesis_planner_needed(
                    self._creative,
                    context,
                    observations,
                ):
                    self._record_loop_stop(state, "required_context_satisfied")
                    break
                if (
                    self._diagnosis_budget_reserved(state)
                    and self._planner_context_satisfied(
                        context,
                        observations,
                    )
                ):
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Stopped planner proposal tool loop to reserve self-check budget.",
                        metadata={
                            "stop_reason": "self_check_budget_reserved",
                            "tool_steps": state.tool_step_count,
                            "tool_calls": state.tool_call_count,
                            "observation_chars_used": state.observation_chars_used,
                            "remaining_tool_calls": self._remaining_tool_calls(state),
                            "remaining_steps": self._remaining_tool_steps(state),
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                        },
                    )
                    break
                planner_context = {
                    "session_id": state.session_id,
                    "phase": state.phase.value,
                    "allowed_tools": self._planner_allowed_tools(context),
                    "allowed_tool_specs": self._planner_allowed_tool_specs(context),
                    "required_context_status": _planner_required_context_status(
                        self.tool_registry,
                        context,
                        observations,
                    ),
                    "tool_arg_guidance": self._tool_arg_guidance(context, observations),
                    "active_algorithm_facts_anchor": (
                        self._planner_active_algorithm_facts_anchor(observations)
                    ),
                    "hypothesis_constraints": self._hypothesis_constraints(context),
                    "remaining_steps": self._remaining_tool_steps(state),
                    "remaining_tool_calls": self._remaining_tool_calls(state),
                    "reserved_for_self_check": {
                        "tool_calls": self._self_check_tool_call_reserve(),
                        "steps": self._self_check_step_reserve(),
                        "observation_chars": self._self_check_observation_reserve_chars(),
                        "purpose": (
                            "selected surface read plus schema, target/action, and "
                            "Contract preview"
                        ),
                    },
                    "observations": [
                        _observation_selection_payload(observation)
                        for observation in observations
                    ],
                }
                planner_context = attach_agentic_trace_context(
                    planner_context,
                    session_id=state.session_id,
                    request_id=state.request_id or state.session_id,
                    branch_id=state.branch_id,
                    campaign_id=state.campaign_id,
                    request_kind="tool_selection",
                    call_kind="tool_selection",
                    phase=AgenticProposalPhase.DIAGNOSE.value,
                    attempt_number=planner_decisions,
                )
                try:
                    planned = selector(_sanitize_agentic_value(planner_context))
                except Exception as exc:
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner tool selection failed; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "error": type(exc).__name__,
                            "error_code": "planner_exception",
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="planner_exception",
                        tool_name=None,
                    )

                if not planned or getattr(planned, "stop", False):
                    missing = self._missing_planner_context_error(context, observations)
                    if missing is not None:
                        state.note(
                            AgenticProposalPhase.DIAGNOSE,
                            "Planner stopped before required compact context; completing framework-required context.",
                            metadata={
                                "status": "framework_required_completion",
                                "error_code": "planner_stopped_before_required_context",
                                "detail": missing,
                            },
                        )
                        return self._complete_required_context_after_planner_gap(
                            context,
                            state,
                            observations,
                            error_code="planner_stopped_before_required_context",
                            tool_name=None,
                            detail=missing,
                        )
                    self._record_loop_stop(state, "required_context_satisfied")
                    break
                if isinstance(planned, Mapping) and planned.get("stop"):
                    missing = self._missing_planner_context_error(context, observations)
                    if missing is not None:
                        state.note(
                            AgenticProposalPhase.DIAGNOSE,
                            "Planner stopped before required compact context; completing framework-required context.",
                            metadata={
                                "status": "framework_required_completion",
                                "error_code": "planner_stopped_before_required_context",
                                "detail": missing,
                            },
                        )
                        return self._complete_required_context_after_planner_gap(
                            context,
                            state,
                            observations,
                            error_code="planner_stopped_before_required_context",
                            tool_name=None,
                            detail=missing,
                        )
                    self._record_loop_stop(state, "required_context_satisfied")
                    break

                if not isinstance(planned, Mapping):
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name="",
                        args={},
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="malformed_tool_selection",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner returned an unsupported tool-selection payload; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "error_code": "malformed_tool_selection",
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="malformed_tool_selection",
                        tool_name=None,
                    )

                name = str(
                    planned.get("tool_name")
                    or planned.get("name")
                    or planned.get("tool")
                    or ""
                )
                args = planned.get("args") or planned.get("input") or {}
                if not isinstance(args, Mapping):
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args={},
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="malformed_tool_args",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner returned malformed tool arguments; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "malformed_tool_args",
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="malformed_tool_args",
                        tool_name=name,
                    )
                allowed_tools = set(planner_context["allowed_tools"])
                if name not in allowed_tools:
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="invalid_tool_selection",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner selected a tool outside the allowed list; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "invalid_tool_selection",
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="invalid_tool_selection",
                        tool_name=name,
                    )
                if (
                    name in {"feedback.query_screening", "feedback.query_runtime"}
                    and _has_equivalent_feedback_observation(
                        observations,
                        name,
                        args,
                        default_surface=str(context.forced_surface or "").strip(),
                    )
                ):
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="equivalent_feedback_observation",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        (
                            "Planner selected feedback already covered "
                            "by an equivalent canonical observation."
                        ),
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "feedback_observation_satisfied",
                            "selection_source": "planner_selected",
                            "skip_reason": "equivalent_feedback_observation",
                        },
                    )
                    missing = self._missing_planner_context_error(context, observations)
                    if missing is None:
                        self._record_loop_stop(
                            state,
                            "feedback_observation_satisfied",
                            error_code="feedback_observation_satisfied",
                            tool_name=name,
                        )
                        break
                    return self._complete_required_context_after_planner_gap(
                        context,
                        state,
                        observations,
                        error_code="feedback_observation_satisfied",
                        tool_name=name,
                        detail=missing,
                    )
                fingerprint = _tool_call_fingerprint(name, args)
                fuse_count = state.tool_call_fuse_counts.get(fingerprint, 0)
                if fuse_count >= self._tool_loop_config.max_repeated_tool_calls:
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="repeated_tool_call_fuse",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner repeated a proposal tool call; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "tool_name": name,
                            "error_code": "repeated_tool_call_fuse",
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="repeated_tool_call_fuse",
                        tool_name=name,
                    )
                if _has_successful_reusable_observation(
                    observations,
                    name,
                    args,
                    forced_surface=context.forced_surface,
                ):
                    if (
                        _context_requires_solver_design_grounding(context)
                        and name in set(_fallback_required_context_tool_names(context))
                    ):
                        _record_tool_selection_ledger_entry(
                            state,
                            phase=AgenticProposalPhase.DIAGNOSE.value,
                            source="planner_selected",
                            status="skipped",
                            tool_name=name,
                            args=args,
                            planner_context=planner_context,
                            planned=planned,
                            skip_reason="already_succeeded",
                        )
                        state.note(
                            AgenticProposalPhase.DIAGNOSE,
                            (
                                "Planner selected a required proposal tool already "
                                "completed by the deterministic preface."
                            ),
                            metadata={
                                "status": "skipped",
                                "tool_name": name,
                                "error_code": "already_succeeded",
                                "selection_source": "planner_selected",
                                "skip_reason": "already_succeeded",
                            },
                        )
                        missing = self._missing_planner_context_error(
                            context, observations
                        )
                        if missing is None:
                            self._record_loop_stop(
                                state,
                                "required_context_satisfied",
                                error_code="already_succeeded",
                                tool_name=name,
                            )
                            break
                        return self._complete_required_context_after_planner_gap(
                            context,
                            state,
                            observations,
                            error_code="already_succeeded",
                            tool_name=name,
                            detail=missing,
                        )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        (
                            "Planner selected a proposal tool already completed "
                            "successfully; completing framework-required missing "
                            "context only."
                        ),
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "already_succeeded",
                            "selection_source": "planner_selected",
                            "skip_reason": "already_succeeded",
                        },
                    )
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="already_succeeded",
                    )
                    return self._complete_required_context_after_planner_gap(
                        context,
                        state,
                        observations,
                        error_code="already_succeeded",
                        tool_name=name,
                        detail=self._missing_planner_context_error(
                            context,
                            observations,
                        ),
                    )
                if _should_defer_diagnosis_tool_to_code_phase(context, name, args):
                    _push_deferred_code_phase_tool_call(state, name, args)
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="deferred",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="code_phase_target_read",
                        deferred_selection_source="code_phase_planner",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Deferred planner-selected target surface read to code phase.",
                        metadata={
                            "status": "deferred",
                            "tool_name": name,
                            "selection_source": "planner_selected",
                            "deferred_selection_source": "code_phase_planner",
                            "skip_reason": "code_phase_target_read",
                        },
                    )
                    continue
                if (
                    name in {"feedback.query_screening", "feedback.query_runtime"}
                    and self._diagnosis_feedback_budget_reserved(state)
                    and self._missing_required_context_error(
                        observations,
                        context=context,
                    )
                    is None
                ):
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="feedback_budget_reserved",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Skipped planner feedback tool to preserve self-check budget.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "feedback_budget_reserved",
                            "selection_source": "planner_selected",
                            "skip_reason": "feedback_budget_reserved",
                            "remaining_observation_chars": self._remaining_observation_chars(
                                state
                            ),
                        },
                    )
                    self._record_loop_stop(
                        state,
                        "feedback_budget_reserved",
                        error_code="feedback_budget_reserved",
                        tool_name=name,
                    )
                    break
                if (
                    name == "context.read_algorithm_file"
                    and _context_requires_solver_design_grounding(context)
                ):
                    followups = self._run_active_solver_map_followup_tools(
                        context,
                        state,
                        observations,
                        selection_source="planner_map_followup_required",
                        target_file=args.get("file_path") or context.forced_target_file,
                    )
                    observations.extend(followups)
                    if state.loop_stop_reason in {
                        "session_timeout",
                        "repeated_tool_call",
                        "tool_loop_limit",
                    }:
                        break
                if _solver_design_planner_algorithm_file_read_budget_exhausted(
                    context,
                    observations,
                    next_tool_name=name,
                    next_args=args,
                ):
                    _record_tool_selection_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DIAGNOSE.value,
                        source="planner_selected",
                        status="skipped",
                        tool_name=name,
                        args=args,
                        planner_context=planner_context,
                        planned=planned,
                        skip_reason="solver_design_algorithm_file_read_budget_reserved",
                    )
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Stopped planner-selected solver_design file reads before full active-object exhaustion.",
                        metadata={
                            "status": "skipped",
                            "tool_name": name,
                            "error_code": "solver_design_algorithm_file_read_budget_reserved",
                            "selection_source": "planner_selected",
                            "skip_reason": "solver_design_algorithm_file_read_budget_reserved",
                        },
                    )
                    return self._complete_required_context_after_planner_gap(
                        context,
                        state,
                        observations,
                        error_code="solver_design_algorithm_file_read_budget_reserved",
                        tool_name=name,
                        detail=self._missing_planner_context_error(
                            context,
                            observations,
                        ),
                    )
                selection_ledger_index = _record_tool_selection_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DIAGNOSE.value,
                    source="planner_selected",
                    status="executed",
                    tool_name=name,
                    args=args,
                    planner_context=planner_context,
                    planned=planned,
                )
                observation = self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.DIAGNOSE,
                    name,
                    args,
                    selection_source="planner_selected",
                )
                _update_tool_selection_ledger_result(
                    state,
                    selection_ledger_index,
                    observation,
                    status="executed",
                )
                observations.append(observation)
                if state.loop_stop_reason == "session_timeout":
                    break
                if self._planner_observation_requires_fallback(observation):
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner tool call returned a recoverable error; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "tool_name": observation.tool_name,
                            "error_code": _enum_value(observation.failure_code),
                            "fallback": "fixed_tool_plan",
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code=str(_enum_value(observation.failure_code)),
                        tool_name=observation.tool_name,
                    )
                if self._planner_context_satisfied(
                    context,
                    observations,
                ) and not _creative_declares_hypothesis_planner_needed(
                    self._creative,
                    context,
                    observations,
                ):
                    self._record_loop_stop(state, "required_context_satisfied")
                    break

            if self._tool_loop_limit_reached(state) and state.loop_stop_reason is None:
                self._record_loop_stop(state, self._current_loop_stop_reason(state))
            missing = self._missing_planner_context_error(context, observations)
            if missing is not None and state.loop_stop_reason == "tool_loop_limit":
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    "Planner exhausted bounded tool loop before useful compact feedback; completing framework-required context.",
                    metadata={
                        "status": "framework_required_completion",
                        "error_code": "planner_tool_loop_limit_before_feedback",
                        "detail": missing,
                    },
                )
                return self._complete_required_context_after_planner_gap(
                    context,
                    state,
                    observations,
                    error_code="planner_tool_loop_limit_before_feedback",
                    tool_name=None,
                    detail=missing,
                )
            return observations

    def _planner_allowed_tools(
            self,
            context: ProposalToolContext,
        ) -> tuple[str, ...]:
            if self.tool_registry is None:
                return ()
            return _filter_model_facing_tool_names(
                self.tool_registry.allowed_tools(context),
                context,
            )

    def _planner_allowed_tool_specs(
            self,
            context: ProposalToolContext,
        ) -> tuple[dict[str, Any], ...]:
            if self.tool_registry is None:
                return ()
            allowed = set(self._planner_allowed_tools(context))
            return tuple(
                spec
                for spec in self.tool_registry.allowed_tool_specs(context)
                if str(spec.get("name") or "") in allowed
            )

    def _tool_arg_guidance(
            self,
            context: ProposalToolContext,
            observations: list[ProposalObservation],
        ) -> dict[str, Any]:
            surface_names = _surface_names_from_observations(observations)
            forced_constraint = self._hypothesis_constraints(context)
            guidance: dict[str, Any] = {
                "context.read_surface": {
                    "surface_source": "context.list_surfaces observations",
                    "surface_rule": (
                        "surface must exactly match one declared surface id/name "
                        "from context.list_surfaces"
                    ),
                    "detail_default": "compact",
                    "recommended_args": {
                        "detail": "compact",
                        "max_code_chars": _APS_SURFACE_READ_CODE_CHARS,
                    },
                    "full_detail_rule": (
                        "request detail='full' only for explicit debugging after "
                        "compact reads are insufficient"
                    ),
                }
            }
            if forced_constraint:
                forced_surface = str(forced_constraint.get("forced_surface") or "").strip()
                active_boundary = [
                    str(surface or "").strip()
                    for surface in forced_constraint.get(
                        "active_problem_boundary_surfaces",
                        (),
                    )
                    if str(surface or "").strip()
                ]
                if forced_surface:
                    guidance["context.read_surface"]["forced_surface_rule"] = (
                        "A forced research-surface diagnostic is active. Read and "
                        "draft only the forced surface."
                    )
                    guidance["context.read_surface"]["allowed_surface_ids"] = [
                        forced_surface
                    ]
                elif active_boundary:
                    guidance["context.read_surface"]["active_problem_boundary_rule"] = (
                        "An active problem-object boundary is present. Read and "
                        "draft one of these boundary surfaces; component policies "
                        "are implementation hooks, not replacement research goals."
                    )
                    guidance["context.read_surface"][
                        "allowed_surface_ids"
                    ] = active_boundary
                guidance["proposal.draft_hypothesis"] = forced_constraint
            if surface_names:
                guidance["context.read_surface"].setdefault(
                    "allowed_surface_ids",
                    surface_names,
                )
            feedback_args = _feedback_query_args(context)
            feedback_scope_rule = (
                "Default to same-campaign screening/runtime history. Do not add "
                "branch_id unless intentionally narrowing to a branch known to "
                "contain prior protocol evidence."
            )
            guidance["feedback.query_screening"] = {
                "scope_rule": feedback_scope_rule,
                "recommended_args": feedback_args,
                "empty_result_rule": (
                    "If branch-scoped feedback returns zero rows while screening "
                    "history exists, retry without branch_id or use only the "
                    "forced surface filter."
                ),
            }
            guidance["feedback.query_runtime"] = {
                "scope_rule": feedback_scope_rule,
                "recommended_args": feedback_args,
                "empty_result_rule": (
                    "Runtime feedback must be useful, not just a successful empty "
                    "tool call; prefer same-campaign or forced-surface scope."
                ),
            }
            if _context_requires_solver_design_grounding(context):
                algorithm_file_guidance = _algorithm_file_path_guidance(
                    context,
                    observations,
                )
                target_read_args = _pre_hypothesis_solver_design_target_file_read_args(
                    context,
                    observations=observations,
                )
                existing_target_files = [
                    str(args.get("file_path") or "").strip()
                    for args in target_read_args
                    if str(args.get("file_path") or "").strip()
                ]
                existing_target_file = existing_target_files[0] if existing_target_files else ""
                forced_target_file = str(context.forced_target_file or "").strip()
                recommended_file_path = _recommended_algorithm_file_path(
                    algorithm_file_guidance,
                    preferred=existing_target_file or forced_target_file,
                )
                map_context = _active_solver_map_context(
                    observations,
                    target_file=existing_target_file or context.forced_target_file,
                )
                recommended_registry_id = str(
                    map_context.get("recommended_registry_id")
                    or "<registry_id from context.read_active_solver_map.operator_registries>"
                )
                recommended_slice_id = str(
                    map_context.get("recommended_slice_id")
                    or "<slice_id from context.read_active_solver_map.algorithm_slices>"
                )
                guidance["context.read_active_solver_map"] = {
                    "recommended_args": {"surface": "solver_design"},
                    "purpose": (
                        "Read the provider-declared active solver map for generic "
                        "entrypoint, registry, integration, slice, telemetry, and "
                        "mechanism-fact ids."
                    ),
                    "consumer_tools": [
                        "context.read_operator_registry",
                        "context.read_algorithm_slice",
                    ],
                    "map_to_source_sequence": (
                        "Default research path is map -> operator registry and/or "
                        "algorithm slice -> targeted full file/symbol only if the "
                        "bounded provider slice is insufficient."
                    ),
                    "already_has_grounding": _has_successful_tool(
                        observations,
                        "context.read_active_solver_map",
                    ),
                    "available_registry_ids": map_context.get("available_registry_ids"),
                    "available_slice_ids": map_context.get("available_slice_ids"),
                }
                if forced_target_file or existing_target_file:
                    guidance["context.read_active_solver_map"][
                        "target_grounding_rule"
                    ] = (
                        "When an existing target_file is forced or inferred from "
                        "branch state, use the map's recommended registry/slice "
                        "or target owner source before drafting the first "
                        "hypothesis."
                    )
                guidance["context.read_operator_registry"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "registry_id": recommended_registry_id,
                    },
                    "purpose": (
                        "Read the provider-declared owner registry after active "
                        "solver map discovery, before broad full-file reads."
                    ),
                    "available_registry_ids": map_context.get("available_registry_ids"),
                    "recommended_registry": map_context.get("recommended_registry"),
                    "required_after_map_rule": (
                        "If context.read_active_solver_map has succeeded and a "
                        "registry_id is available, call this before drafting the "
                        "final solver_design hypothesis and before broad "
                        "full-file reads unless a narrower algorithm slice "
                        "already proves the target owner."
                    ),
                }
                guidance["context.read_algorithm_slice"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "slice_id": recommended_slice_id,
                        "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    },
                    "purpose": (
                        "Read a bounded provider-declared algorithm slice after "
                        "active solver map discovery. Prefer this before broad "
                        "full-file reads and before final hypothesis when the "
                        "target or integration owner is known."
                    ),
                    "available_slice_ids": map_context.get("available_slice_ids"),
                    "algorithm_slices": map_context.get("algorithm_slices"),
                    "recommended_slice": map_context.get("recommended_slice"),
                    "required_after_map_rule": (
                        "If context.read_active_solver_map has succeeded and a "
                        "slice_id is available, call a relevant slice before "
                        "context.read_algorithm_file unless the exact target body "
                        "is already visible."
                    ),
                }
                guidance["context.list_algorithm_files"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "include_inactive": True,
                    },
                    "purpose": (
                        "List allowlisted solver_design algorithm file_path values "
                        "before any targeted algorithm file or symbol read."
                    ),
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
                        "Read one allowlisted active solver file after "
                        "context.list_algorithm_files and after using the active "
                        "solver map's registry/slice consumers when available."
                    ),
                    "pre_full_read_rule": (
                        "For solver_design research, do not jump from map to "
                        "multiple broad full-file reads. Use read_operator_registry "
                        "or read_algorithm_slice first, then read a target owner "
                        "file only when exact source is needed."
                    ),
                    "existing_target_grounding_rule": (
                        "If forced_action is modify, branch/feedback context, "
                        "target preview, or the active solver map identifies "
                        "provider-declared existing target candidates, read their "
                        "owner source before returning stop=true or drafting the "
                        "first hypothesis."
                    ),
                    "existing_target_candidate": existing_target_file or None,
                    "existing_target_candidates": existing_target_files,
                    "active_solver_map_context": map_context,
                }
                guidance["context.read_algorithm_symbol"] = {
                    **algorithm_file_guidance,
                    "recommended_args": {
                        "surface": "solver_design",
                        "file_path": recommended_file_path,
                        "symbol": "solve",
                        "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    },
                    "purpose": (
                        "Read one symbol from an allowlisted active solver file only "
                        "after context.list_algorithm_files has provided the file_path."
                    ),
                }
            return guidance

    def _planner_active_algorithm_facts_anchor(
            self,
            observations: list[ProposalObservation],
        ) -> dict[str, Any]:
            facts = _active_algorithm_facts_for_prompt_context(observations)
            if not facts:
                return {}
            active_facts = facts.get("active_algorithm_facts")
            compact = active_facts if isinstance(active_facts, Mapping) else {}
            return {
                "source": facts.get("source"),
                "source_observation_id": facts.get("source_observation_id"),
                "source_tool_call_id": facts.get("source_tool_call_id"),
                "provenance": facts.get("provenance"),
                "source_digest": facts.get("source_digest"),
                "fact_packet_digest": facts.get("fact_packet_digest"),
                "snapshot_digest": facts.get("snapshot_digest"),
                "fact_ids": list(compact.get("fact_ids") or ())[:20],
                "rule": (
                    "Use this same adapter-provided fact packet as the anchor "
                    "when choosing owner files or deciding more context is needed."
                ),
            }

    def _hypothesis_constraints(
            self,
            context: ProposalToolContext | None,
        ) -> dict[str, Any]:
            if context is None:
                return {}
            active_boundary = tuple(
                surface
                for surface in context.active_problem_boundary_surfaces
                if str(surface or "").strip()
            )
            if not context.forced_surface:
                if not active_boundary:
                    return {}
                return {
                    "active_problem_boundary_surfaces": active_boundary,
                    "novelty_signature_requirements": (
                        _active_boundary_novelty_requirements(
                            context,
                            list(active_boundary),
                        )
                    ),
                    "rule": (
                        "Hypothesis generation must keep change_locus on the "
                        "active problem-object boundary. Component policies are "
                        "implementation hooks or attribution evidence, not "
                        "replacement research goals."
                    ),
                }
            return {
                key: value
                for key, value in {
                    "forced_surface": context.forced_surface,
                    "forced_action": context.forced_action,
                    "forced_target_file": context.forced_target_file,
                    "rule": (
                        "Hypothesis generation must use exactly the forced "
                        "surface/action/target when present. Off-surface output "
                        "fails closed before code generation."
                    ),
                    "active_problem_boundary_surfaces": active_boundary or None,
                    "novelty_signature_requirements": (
                        _active_boundary_novelty_requirements(
                            context,
                            [str(context.forced_surface).strip()],
                        )
                        if context.forced_surface
                        else None
                    ),
                }.items()
                if value
            }


def _creative_declares_hypothesis_planner_needed(
    creative: Any,
    context: ProposalToolContext,
    observations: list[ProposalObservation],
) -> bool:
    checker = getattr(creative, "has_pending_hypothesis_tool_plan", None)
    if not callable(checker):
        return False
    try:
        return bool(checker(context=context, observations=observations))
    except TypeError:
        return bool(checker())
