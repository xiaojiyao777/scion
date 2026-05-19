"""AgenticSessionBudgetRuntime mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionBudgetRuntimeMixin:
    def _tool_loop_limit_reached(
            self,
            state: AgenticProposalSessionState,
            *,
            ignore_observation_budget: bool = False,
        ) -> bool:
            return (
                state.tool_step_count >= self._tool_loop_config.max_steps
                or state.tool_call_count >= self._tool_loop_config.max_tool_calls
                or (
                    not ignore_observation_budget
                    and self._observation_budget_exhausted(state)
                )
                or self._session_timeout_reached(state)
            )

    def _remaining_observation_chars(
            self,
            state: AgenticProposalSessionState,
        ) -> int:
            return _remaining_observation_chars_for_config(self._tool_loop_config, state)

    def _remaining_tool_calls(self, state: AgenticProposalSessionState) -> int:
            return _remaining_tool_calls_for_config(self._tool_loop_config, state)

    def _remaining_tool_steps(self, state: AgenticProposalSessionState) -> int:
            return _remaining_tool_steps_for_config(self._tool_loop_config, state)

    def _remaining_wall_time_sec(self, state: AgenticProposalSessionState) -> float:
            return max(
                0.0,
                float(self._tool_loop_config.max_wall_time_sec)
                - (time.monotonic() - state.wall_time_started_at),
            )

    def _self_check_tool_call_reserve(self) -> int:
            return _self_check_tool_call_reserve_for_config(self._tool_loop_config)

    def _self_check_step_reserve(self) -> int:
            return _self_check_step_reserve_for_config(self._tool_loop_config)

    def _self_check_observation_reserve_chars(self) -> int:
            return _self_check_observation_reserve_chars_for_config(
                self._tool_loop_config
            )

    def _diagnosis_budget_reserved(self, state: AgenticProposalSessionState) -> bool:
            return _diagnosis_budget_reserved_for_config(self._tool_loop_config, state)

    def _diagnosis_feedback_budget_reserved(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            return _diagnosis_feedback_budget_reserved_for_config(
                self._tool_loop_config,
                state,
            )

    def _observation_budget_exhausted(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            return _observation_budget_exhausted_for_config(self._tool_loop_config, state)

    def _minimum_budgeted_observation_chars(self) -> int:
            return _minimum_budgeted_observation_chars()

    def _optional_surface_read_budget_floor(self) -> int:
            return _optional_surface_read_budget_floor_for_config(self._tool_loop_config)

    def _self_check_preview_budget_chars(self) -> int:
            configured_reserve = self._self_check_observation_reserve_chars()
            if configured_reserve > 0:
                return configured_reserve
            return max(
                self._minimum_budgeted_observation_chars(),
                min(
                    _SELF_CHECK_PREVIEW_OBSERVATION_BUDGET_CHARS,
                    max(0, int(self._tool_loop_config.max_observation_chars)),
                ),
            )

    def _should_deny_optional_tool_for_budget(
            self,
            name: str,
            *,
            selection_source: str,
            state: AgenticProposalSessionState,
        ) -> bool:
            return _should_deny_optional_tool_for_budget_config(
                name,
                selection_source=selection_source,
                config=self._tool_loop_config,
                state=state,
            )

    def _budgeted_tool_args(
            self,
            name: str,
            args: Mapping[str, Any],
            *,
            selection_source: str,
        ) -> Mapping[str, Any]:
            return _budgeted_tool_args(name, args, selection_source=selection_source)

    def _session_timeout_reached(self, state: AgenticProposalSessionState) -> bool:
            return (
                time.monotonic() - state.wall_time_started_at
                >= self._tool_loop_config.max_wall_time_sec
            )

    def _current_loop_stop_reason(self, state: AgenticProposalSessionState) -> str:
            if self._session_timeout_reached(state):
                return "session_timeout"
            if (
                state.tool_step_count >= self._tool_loop_config.max_steps
                or state.tool_call_count >= self._tool_loop_config.max_tool_calls
            ):
                return "tool_loop_limit"
            if self._observation_budget_exhausted(state):
                return "observation_budget_exhausted"
            return "tool_loop_limit"

    def _record_loop_stop(
            self,
            state: AgenticProposalSessionState,
            reason: str,
            *,
            error_code: str | None = None,
            tool_name: str | None = None,
        ) -> None:
            if state.loop_stop_reason is None:
                state.loop_stop_reason = reason
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    "Stopped proposal tool loop.",
                    metadata={
                        "stop_reason": reason,
                        "tool_steps": state.tool_step_count,
                        "tool_calls": state.tool_call_count,
                        "observation_chars_used": state.observation_chars_used,
                        "error_code": error_code,
                        "tool_name": tool_name,
                    },
                )

    def _enforce_observation_budget(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            observation: ProposalObservation,
            *,
            preserve_observation_chars: int = 0,
        ) -> ProposalObservation:
            observation = _compact_feedback_observation_for_budget(observation)
            compact_preview = _compact_self_check_preview_observation(observation)
            if compact_preview is not None and (
                _json_size(_observation_prompt_payload(compact_preview))
                < _json_size(_observation_prompt_payload(observation))
            ):
                observation = compact_preview
            projected = _json_size(_observation_prompt_payload(observation))
            reserved = max(0, int(preserve_observation_chars))
            remaining = max(0, self._remaining_observation_chars(state) - reserved)
            if projected > remaining:
                compact_active_solver = _compact_active_solver_observation_for_budget(
                    observation
                )
                if compact_active_solver is not None and (
                    _json_size(_observation_prompt_payload(compact_active_solver))
                    < projected
                ):
                    observation = compact_active_solver
                    projected = _json_size(_observation_prompt_payload(observation))
            if projected <= remaining:
                return observation
            compact_preview = _compact_self_check_preview_observation(observation)
            if compact_preview is not None and (
                _json_size(_observation_prompt_payload(compact_preview)) <= remaining
            ):
                return compact_preview
            minimal_preview = _minimal_self_check_preview_observation(observation)
            if minimal_preview is not None:
                if _json_size(_observation_prompt_payload(minimal_preview)) <= remaining:
                    return minimal_preview
                return self._fit_observation_to_remaining(
                    minimal_preview,
                    remaining_chars=remaining,
                )
            return self._budget_error_observation(
                context,
                state,
                tool_name=observation.tool_name,
                tool_call_id=observation.tool_call_id,
                summary=(
                    "Tool observation exceeded the configured session observation budget."
                ),
                estimated_chars=projected,
                budget_action="observation_truncated",
                source_observation=observation,
                remaining_chars=remaining,
                preserved_observation_chars=reserved,
                repair_hint="Request fewer or smaller observations.",
            )

    def _enforce_self_check_preview_budget(
            self,
            observation: ProposalObservation,
        ) -> ProposalObservation:
            limit = self._self_check_preview_budget_chars()
            if _json_size(_observation_prompt_payload(observation)) <= limit:
                return observation
            compact_preview = _compact_self_check_preview_observation(observation)
            if compact_preview is not None and (
                _json_size(_observation_prompt_payload(compact_preview)) <= limit
            ):
                return compact_preview
            minimal_preview = _minimal_self_check_preview_observation(observation)
            if minimal_preview is not None:
                if _json_size(_observation_prompt_payload(minimal_preview)) <= limit:
                    return minimal_preview
                return self._fit_observation_to_remaining(
                    minimal_preview,
                    remaining_chars=limit,
                )
            return self._fit_observation_to_remaining(
                observation,
                remaining_chars=limit,
            )

    def _budget_error_observation(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            *,
            tool_name: str,
            tool_call_id: str,
            summary: str,
            estimated_chars: int | None,
            budget_action: str,
            source_observation: ProposalObservation | None = None,
            remaining_chars: int | None = None,
            preserved_observation_chars: int = 0,
            repair_hint: str | None = None,
        ) -> ProposalObservation:
            payload = {
                "budget_action": budget_action,
                "max_observation_chars": self._tool_loop_config.max_observation_chars,
                "observation_chars_used": state.observation_chars_used,
                "remaining_observation_chars": (
                    self._remaining_observation_chars(state)
                    if remaining_chars is None
                    else remaining_chars
                ),
            }
            if preserved_observation_chars:
                payload["preserved_observation_chars"] = preserved_observation_chars
            if estimated_chars is not None:
                payload["estimated_chars"] = estimated_chars
            if source_observation is not None:
                payload["source_observation_type"] = source_observation.observation_type
                payload["source_was_error"] = source_observation.is_error
                payload["source_failure_code"] = _enum_value(
                    source_observation.failure_code
                )
            observation = ProposalObservation(
                observation_id=str(uuid.uuid4()),
                session_id=context.session_id,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                observation_type="tool_error",
                summary=summary,
                structured_payload=payload,
                taint=(
                    source_observation.taint
                    if source_observation is not None
                    else ProposalTaint.PROPOSAL
                ),
                exposure_level=(
                    source_observation.exposure_level
                    if source_observation is not None
                    else ProposalExposureLevel.PUBLIC_SPEC
                ),
                is_error=True,
                failure_code=ProposalToolFailureCode.RESULT_TOO_LARGE,
                repair_hint=repair_hint,
            )
            return self._fit_observation_to_remaining(
                observation,
                remaining_chars=(
                    self._remaining_observation_chars(state)
                    if remaining_chars is None
                    else remaining_chars
                ),
            )

    def _fit_observation_to_remaining(
            self,
            observation: ProposalObservation,
            *,
            remaining_chars: int,
        ) -> ProposalObservation:
            if _json_size(_observation_prompt_payload(observation)) <= remaining_chars:
                return observation
            compact_payloads: tuple[Mapping[str, Any], ...] = (
                {
                    "budget_action": "observation_truncated",
                    "remaining_observation_chars": max(0, remaining_chars),
                },
                {},
            )
            summaries = (
                observation.summary,
                "Tool observation omitted because the remaining session observation budget is too small.",
                "Observation budget exhausted.",
                "",
            )
            for payload in compact_payloads:
                for summary in summaries:
                    candidate = replace(
                        observation,
                        summary=summary,
                        structured_payload=payload,
                        repair_hint=None,
                    )
                    if (
                        _json_size(_observation_prompt_payload(candidate))
                        <= remaining_chars
                    ):
                        return candidate
            return replace(
                observation,
                summary="",
                structured_payload={},
                repair_hint=None,
            )

    def _record_prompt_manifest(
            self,
            state: AgenticProposalSessionState,
            *,
            call_kind: str,
            prompt_context: Mapping[str, Any],
            observations: list[ProposalObservation],
        ) -> None:
            call_index = _next_prompt_manifest_index(state)
            manifest = build_api_visible_prompt_manifest(
                session_id=state.session_id,
                phase=state.phase.value,
                call_kind=call_kind,
                prompt_context=prompt_context,
                observations=tuple(observations),
                call_index=call_index,
            )
            artifact_ref: str | None = None
            if self._artifact_store is not None:
                artifact_ref = self._artifact_store.write_scratch(
                    state.session_id,
                    f"api_visible_prompt_manifest_{call_index:04d}_{call_kind}.json",
                    manifest,
                )
                state.scratch_artifact_refs.append(artifact_ref)
            state.note(
                state.phase,
                "Recorded API-visible prompt manifest.",
                metadata={
                    "artifact_kind": "api_visible_prompt_manifest",
                    "call_kind": call_kind,
                    "call_index": call_index,
                    "section_names": manifest["section_names"],
                    "prompt_hash": manifest["prompt_hash"],
                    "manifest_artifact_ref": artifact_ref,
                    "raw_prompt_saved": False,
                },
            )
