"""AgenticSessionToolCall mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionToolCallMixin:
    def _call_tool(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            phase: AgenticProposalPhase,
            name: str,
            args: Mapping[str, Any],
            *,
            selection_source: str = "fallback_selected",
            preserve_observation_chars: int = 0,
        ) -> ProposalObservation:
            assert self.tool_registry is not None
            args = self._budgeted_tool_args(name, args, selection_source=selection_source)
            authoritative_preview = _is_authoritative_self_check_preview_call(
                name,
                phase,
                selection_source,
            )
            if self._session_timeout_reached(state):
                self._record_loop_stop(
                    state, "session_timeout", error_code="session_timeout"
                )
                if authoritative_preview:
                    return self._session_timeout_preview_observation(
                        context,
                        state,
                        phase,
                        name=name,
                        selection_source=selection_source,
                    )
                observation = ProposalObservation(
                    observation_id=str(uuid.uuid4()),
                    session_id=context.session_id,
                    tool_name=name,
                    tool_call_id="",
                    observation_type="tool_skipped",
                    summary=(
                        "Proposal tool call skipped because the agentic session "
                        "wall-time budget was exhausted."
                    ),
                    structured_payload={
                        "skip_reason": "session_timeout",
                        "budget_exhausted": True,
                        "agentic_budget_control": True,
                        "framework_control": True,
                        "skip_class": "agentic_budget_control",
                        "max_wall_time_sec": self._tool_loop_config.max_wall_time_sec,
                    },
                    is_error=True,
                    failure_code="session_timeout",
                    repair_hint="Start a new bounded proposal session.",
                )
                state.note(
                    phase,
                    f"Proposal tool observation: {name}",
                    metadata={
                        "tool_name": observation.tool_name,
                        "status": "error",
                        "evidence_ref": observation.observation_id,
                        "result_summary": observation.summary,
                        "error_code": "session_timeout",
                        "observation_id": observation.observation_id,
                        "observation_type": observation.observation_type,
                        "exposure_level": _enum_value(observation.exposure_level),
                        "is_error": True,
                        "failure_code": "session_timeout",
                        "selection_source": selection_source,
                        "skip_reason": "session_timeout",
                        "skip_class": "agentic_budget_control",
                        "agentic_budget_control": True,
                    },
                )
                return observation
            state.tool_event_count = max(
                int(state.tool_event_count),
                int(state.tool_step_count) + int(state.preview_tool_step_count),
            )
            state.tool_event_count += 1
            if authoritative_preview:
                state.preview_tool_step_count += 1
                state.preview_tool_call_count += 1
            else:
                state.tool_step_count += 1
                state.tool_call_count += 1
            step_id = f"tool-{state.tool_event_count:04d}"
            fingerprint = _tool_call_fingerprint(name, args)
            fuse_count = state.tool_call_fuse_counts.get(fingerprint, 0) + 1
            state.tool_call_fuse_counts[fingerprint] = fuse_count
            if fuse_count > self._tool_loop_config.max_repeated_tool_calls:
                self._record_loop_stop(
                    state,
                    "repeated_tool_call",
                    error_code="repeated_tool_call_fuse",
                    tool_name=name,
                )
                observation = ProposalObservation(
                    observation_id=str(uuid.uuid4()),
                    session_id=context.session_id,
                    tool_name=name,
                    tool_call_id=step_id,
                    observation_type="tool_error",
                    summary="Repeated identical proposal tool call exceeded the configured fuse.",
                    structured_payload={
                        "max_repeated_tool_calls": self._tool_loop_config.max_repeated_tool_calls,
                    },
                    is_error=True,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    repair_hint="Select a different tool or change the arguments.",
                )
                state.note(
                    phase,
                    f"Proposal tool observation: {name}",
                    metadata={
                        "step_id": step_id,
                        "tool_name": name,
                        "status": "error",
                        "evidence_ref": observation.observation_id,
                        "result_summary": observation.summary,
                        "error_code": "repeated_tool_call_fuse",
                        "observation_id": observation.observation_id,
                        "observation_type": observation.observation_type,
                        "exposure_level": _enum_value(observation.exposure_level),
                        "is_error": True,
                        "failure_code": _enum_value(observation.failure_code),
                        "selection_source": selection_source,
                    },
                )
                return observation
            if self._should_deny_optional_tool_for_budget(
                name,
                selection_source=selection_source,
                state=state,
            ):
                observation = self._budget_error_observation(
                    context,
                    state,
                    tool_name=name,
                    tool_call_id=step_id,
                    summary=(
                        "Optional proposal tool call denied because the remaining "
                        "session observation budget is reserved."
                    ),
                    estimated_chars=None,
                    budget_action="tool_denied",
                    repair_hint="Use existing compact observations or stop planning.",
                )
            else:
                try:
                    observation = self._registry_call_with_timeout(
                        name,
                        args,
                        context,
                        tool_call_id=step_id,
                    )
                except _ProposalToolTimeout as exc:
                    timeout_sec = _preview_tool_timeout_sec(name)
                    observation = ProposalObservation(
                        observation_id=str(uuid.uuid4()),
                        session_id=context.session_id,
                        tool_name=name,
                        tool_call_id=step_id,
                        observation_type="tool_error",
                        summary=str(exc),
                        structured_payload={
                            "timeout_sec": timeout_sec,
                            "tool_name": name,
                        },
                        is_error=True,
                        failure_code=ProposalToolFailureCode.RUNTIME_EXCEPTION,
                        repair_hint=(
                            "Simplify the candidate and use statically bounded loops "
                            "before requesting Contract preview or algorithm smoke again."
                        ),
                    )
            observation = _deduplicate_observation_if_already_read(
                state,
                observation,
                tool_name=name,
                args=args,
                phase=phase,
                args_hash=fingerprint,
            )
            if authoritative_preview:
                observation = self._enforce_self_check_preview_budget(observation)
            else:
                observation = self._enforce_observation_budget(
                    context,
                    state,
                    observation,
                    preserve_observation_chars=preserve_observation_chars,
                )
            prompt_payload_chars = _json_size(_observation_prompt_payload(observation))
            remaining = (
                self._self_check_preview_budget_chars()
                if authoritative_preview
                else max(
                    0,
                    self._remaining_observation_chars(state)
                    - max(0, int(preserve_observation_chars)),
                )
            )
            if prompt_payload_chars > remaining:
                observation = self._fit_observation_to_remaining(
                    observation,
                    remaining_chars=remaining,
                )
                prompt_payload_chars = _json_size(_observation_prompt_payload(observation))
            if not authoritative_preview:
                previous_observation_chars = int(state.observation_chars_used)
                projected_observation_chars = (
                    previous_observation_chars + prompt_payload_chars
                )
                charge_ceiling = max(
                    0,
                    self._tool_loop_config.max_observation_chars
                    - max(0, int(preserve_observation_chars)),
                )
                if preserve_observation_chars > 0:
                    projected_observation_chars = min(
                        projected_observation_chars,
                        max(previous_observation_chars, charge_ceiling),
                    )
                state.observation_chars_used = min(
                    projected_observation_chars,
                    self._tool_loop_config.max_observation_chars,
                )
            if not authoritative_preview and self._observation_budget_exhausted(state):
                self._record_loop_stop(
                    state,
                    "tool_loop_limit",
                    error_code="observation_budget_exhausted",
                    tool_name=name,
                )
            state.note(
                phase,
                f"Proposal tool observation: {name}",
                metadata={
                    "step_id": step_id,
                    "tool_name": observation.tool_name,
                    "status": "error" if observation.is_error else "ok",
                    "taint": _enum_value(observation.taint),
                    "evidence_ref": observation.observation_id,
                    "result_summary": observation.summary,
                    "error_code": _enum_value(observation.failure_code),
                    "observation_id": observation.observation_id,
                    "observation_type": observation.observation_type,
                    "exposure_level": _enum_value(observation.exposure_level),
                    "is_error": observation.is_error,
                    "failure_code": _enum_value(observation.failure_code),
                    "selection_source": selection_source,
                },
            )
            return observation

    def _session_timeout_preview_observation(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            phase: AgenticProposalPhase,
            *,
            name: str,
            selection_source: str,
        ) -> ProposalObservation:
            elapsed = time.monotonic() - state.wall_time_started_at
            observation = ProposalObservation(
                observation_id=str(uuid.uuid4()),
                session_id=context.session_id,
                tool_name=name,
                tool_call_id="",
                observation_type="tool_skipped",
                summary=(
                    "Proposal preview skipped because the agentic session wall-time "
                    "budget was exhausted before the mandatory preview could start."
                ),
                structured_payload={
                    "skip_reason": "session_timeout",
                    "budget_exhausted": True,
                    "agentic_budget_control": True,
                    "framework_control": True,
                    "skip_class": "agentic_budget_control",
                    "max_wall_time_sec": self._tool_loop_config.max_wall_time_sec,
                    "elapsed_wall_time_sec": elapsed,
                    "tool_steps": state.tool_step_count,
                    "tool_calls": state.tool_call_count,
                    "preview_tool_steps": state.preview_tool_step_count,
                    "preview_tool_calls": state.preview_tool_call_count,
                    "error_code": "session_timeout",
                },
                is_error=True,
                failure_code="session_timeout",
                repair_hint=(
                    "Start a new bounded proposal session or stop code repair before "
                    "mandatory previews lose wall-time reserve."
                ),
            )
            state.note(
                phase,
                f"Proposal tool observation: {name}",
                metadata={
                    "tool_name": observation.tool_name,
                    "status": "error",
                    "taint": _enum_value(observation.taint),
                    "evidence_ref": observation.observation_id,
                    "result_summary": observation.summary,
                    "error_code": "session_timeout",
                    "observation_id": observation.observation_id,
                    "observation_type": observation.observation_type,
                    "exposure_level": _enum_value(observation.exposure_level),
                    "is_error": True,
                    "failure_code": "session_timeout",
                    "selection_source": selection_source,
                    "skip_reason": "session_timeout",
                    "skip_class": "agentic_budget_control",
                    "agentic_budget_control": True,
                },
            )
            return observation

    def _registry_call_with_timeout(
            self,
            name: str,
            args: Mapping[str, Any],
            context: ProposalToolContext,
            *,
            tool_call_id: str,
        ) -> ProposalObservation:
            assert self.tool_registry is not None
            if (
                name not in {"proposal.contract_preview", "proposal.algorithm_smoke"}
                or not _can_use_signal_timeout()
            ):
                return self.tool_registry.call(
                    name,
                    args,
                    context,
                    tool_call_id=tool_call_id,
                )

            previous_handler = signal.getsignal(signal.SIGALRM)
            previous_timer = signal.getitimer(signal.ITIMER_REAL)

            def _raise_timeout(_signum: int, _frame: Any) -> None:
                raise _ProposalToolTimeout(
                    "Preview timed out before workspace materialization."
                )

            timeout_sec = _preview_tool_timeout_sec(name)
            signal.signal(signal.SIGALRM, _raise_timeout)
            signal.setitimer(signal.ITIMER_REAL, timeout_sec)
            try:
                return self.tool_registry.call(
                    name,
                    args,
                    context,
                    tool_call_id=tool_call_id,
                )
            finally:
                signal.setitimer(signal.ITIMER_REAL, *previous_timer)
                signal.signal(signal.SIGALRM, previous_handler)
