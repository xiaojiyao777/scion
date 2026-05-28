"""AgenticSessionToolCall mixin."""
from __future__ import annotations

from typing import Sequence

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
            args = self._budgeted_tool_args(
                name,
                args,
                selection_source=selection_source,
                context=context,
            )
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
            observation = already_observed_from_inherited_ledger(
                state,
                context,
                tool_name=name,
                args=args,
                tool_call_id=step_id,
            )
            if observation is not None:
                pass
            elif self._should_deny_optional_tool_for_budget(
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
            artifact_observation = observation
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
            record_agentic_ledger_observation(
                state,
                context,
                observation,
                args=args,
                proposal_phase=phase.value,
                prompt_visible_chars=prompt_payload_chars,
                selection_source=selection_source,
            )
            metadata = {
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
            }
            metadata.update(_tool_observation_transcript_metadata(observation))
            smoke_artifact_ref = _write_algorithm_smoke_execution_evidence_artifact(
                self._artifact_store,
                state,
                artifact_observation,
            )
            if smoke_artifact_ref:
                state.scratch_artifact_refs.append(smoke_artifact_ref)
                metadata["algorithm_smoke_execution_evidence_ref"] = smoke_artifact_ref
            state.note(
                phase,
                f"Proposal tool observation: {name}",
                metadata=metadata,
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


def _write_algorithm_smoke_execution_evidence_artifact(
    artifact_store: AgenticSessionArtifactStore | None,
    state: AgenticProposalSessionState,
    observation: ProposalObservation,
) -> str:
    if artifact_store is None or observation.tool_name != "proposal.algorithm_smoke":
        return ""
    payload = _algorithm_smoke_execution_evidence_payload(state, observation)
    if not payload:
        return ""
    index = int(getattr(state, "_algorithm_smoke_evidence_artifact_index", 0)) + 1
    setattr(state, "_algorithm_smoke_evidence_artifact_index", index)
    return artifact_store.write_scratch(
        state.session_id,
        f"algorithm_smoke_execution_evidence_{index:04d}.json",
        payload,
    )


def _algorithm_smoke_execution_evidence_payload(
    state: AgenticProposalSessionState,
    observation: ProposalObservation,
) -> dict[str, Any]:
    payload = (
        observation.structured_payload
        if isinstance(observation.structured_payload, Mapping)
        else {}
    )
    runtime_smoke = (
        payload.get("runtime_smoke")
        if isinstance(payload.get("runtime_smoke"), Mapping)
        else {}
    )
    ledger = _runtime_smoke_evidence_ledger(runtime_smoke)
    if not ledger and runtime_smoke in ({}, None):
        return {}
    provider_case_count = _runtime_smoke_provider_count(
        runtime_smoke,
        ledger,
        key="provider_case_count",
    )
    provider_case_attempted_count = _runtime_smoke_provider_count(
        runtime_smoke,
        ledger,
        key="provider_case_attempted_count",
        attempted_only=True,
    )
    evidence_diagnostics = _runtime_smoke_evidence_diagnostics(
        runtime_smoke,
        ledger=ledger,
        provider_case_count=provider_case_count,
        provider_case_attempted_count=provider_case_attempted_count,
        payload_diagnostics=payload.get("evidence_diagnostics"),
    )
    compact_runtime_smoke = {
        key: runtime_smoke.get(key)
        for key in (
            "passed",
            "runtime_smoke_run",
            "selected_surface",
            "case_count",
            "selected_case_count",
            "attempted_case_count",
            "provider_hook_used",
            "provider_unavailable",
            "provider_case_count",
            "provider_case_attempted_count",
            "provenance",
            "runtime_budget_diagnostic",
            "runtime_audit_failure",
        )
        if runtime_smoke.get(key) not in (None, "", [], {})
    }
    compact_runtime_smoke["provider_case_count"] = provider_case_count
    compact_runtime_smoke["provider_case_attempted_count"] = (
        provider_case_attempted_count
    )
    if evidence_diagnostics:
        compact_runtime_smoke["evidence_diagnostics"] = evidence_diagnostics
    return _drop_empty_dict(
        {
            "schema_version": "algorithm-smoke-execution-evidence.v1",
            "artifact_kind": "algorithm_smoke_execution_evidence",
            "session_id": state.session_id,
            "campaign_id": state.campaign_id,
            "branch_id": state.branch_id,
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "status": payload.get("status"),
            "passed": payload.get("passed"),
            "failure_code": payload.get("failure_code"),
            "failure_class": payload.get("failure_class"),
            "primary_issue": payload.get("primary_issue"),
            "provider_hook_used": runtime_smoke.get("provider_hook_used"),
            "provider_unavailable": runtime_smoke.get("provider_unavailable"),
            "provider_case_count": provider_case_count,
            "provider_case_attempted_count": provider_case_attempted_count,
            "case_execution_ledger": [
                _sanitize_agentic_value(item)
                for item in ledger
                if isinstance(item, Mapping)
            ],
            "evidence_diagnostics": evidence_diagnostics,
            "runtime_smoke": _sanitize_agentic_value(compact_runtime_smoke),
            "payload_hash": stable_digest(payload, length=16),
            "raw_payload_omitted": True,
            "tainted": True,
        }
    )


def _tool_observation_transcript_metadata(
    observation: ProposalObservation,
) -> dict[str, Any]:
    if observation.tool_name != "proposal.algorithm_smoke":
        return {}
    payload = (
        observation.structured_payload
        if isinstance(observation.structured_payload, Mapping)
        else {}
    )
    runtime_smoke = (
        payload.get("runtime_smoke")
        if isinstance(payload.get("runtime_smoke"), Mapping)
        else {}
    )
    ledger = _runtime_smoke_evidence_ledger(runtime_smoke)
    provider_case_count = _runtime_smoke_provider_count(
        runtime_smoke,
        ledger,
        key="provider_case_count",
    )
    provider_case_attempted_count = _runtime_smoke_provider_count(
        runtime_smoke,
        ledger,
        key="provider_case_attempted_count",
        attempted_only=True,
    )
    evidence_diagnostics = _runtime_smoke_evidence_diagnostics(
        runtime_smoke,
        ledger=ledger,
        provider_case_count=provider_case_count,
        provider_case_attempted_count=provider_case_attempted_count,
        payload_diagnostics=payload.get("evidence_diagnostics"),
    )
    return _drop_empty_dict(
        {
            "algorithm_smoke_status": payload.get("status"),
            "algorithm_smoke_failure_code": payload.get("failure_code"),
            "runtime_smoke_case_execution_ledger": [
                _sanitize_agentic_value(item)
                for item in ledger
                if isinstance(item, Mapping)
            ][:8],
            "runtime_smoke_provider_hook_used": runtime_smoke.get(
                "provider_hook_used"
            ),
            "runtime_smoke_provider_unavailable": runtime_smoke.get(
                "provider_unavailable"
            ),
            "runtime_smoke_provider_case_count": provider_case_count,
            "runtime_smoke_provider_case_attempted_count": (
                provider_case_attempted_count
            ),
            "runtime_smoke_evidence_diagnostics": evidence_diagnostics,
            "runtime_budget_diagnostic": runtime_smoke.get(
                "runtime_budget_diagnostic"
            ),
        }
    )


def _runtime_smoke_evidence_ledger(
    runtime_smoke: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    ledger = runtime_smoke.get("case_execution_ledger")
    if not isinstance(ledger, (list, tuple)):
        ledger = runtime_smoke.get("cases")
    if isinstance(ledger, (list, tuple)):
        records = [item for item in ledger if isinstance(item, Mapping)]
        if records:
            return records
    case = runtime_smoke.get("case")
    case_count = _int_or_none(runtime_smoke.get("case_count"))
    if not case and not case_count:
        return []
    run = (
        runtime_smoke.get("run")
        if isinstance(runtime_smoke.get("run"), Mapping)
        else {}
    )
    return [
        _drop_empty_dict(
            {
                "label": "runtime_smoke_case",
                "case": case,
                "case_path_ref": runtime_smoke.get("case_path_ref"),
                "seed": runtime_smoke.get("seed"),
                "provider_hook_used": False,
                "attempted": bool(runtime_smoke.get("runtime_smoke_run")),
                "success": run.get("success"),
                "passed": runtime_smoke.get("passed"),
                "failure": "case_execution_ledger_missing",
                "case_digest": runtime_smoke.get("case_digest")
                or runtime_smoke.get("case_metadata_hash"),
                "run_digest": run.get("run_digest"),
            }
        )
    ]


def _runtime_smoke_provider_count(
    runtime_smoke: Mapping[str, Any],
    ledger: Sequence[Mapping[str, Any]],
    *,
    key: str,
    attempted_only: bool = False,
) -> int:
    value = _int_or_none(runtime_smoke.get(key))
    if value is not None:
        return value
    count = 0
    for item in ledger:
        if not item.get("provider_hook_used"):
            continue
        if attempted_only and not item.get("attempted"):
            continue
        count += 1
    return count


def _runtime_smoke_evidence_diagnostics(
    runtime_smoke: Mapping[str, Any],
    *,
    ledger: Sequence[Mapping[str, Any]],
    provider_case_count: int,
    provider_case_attempted_count: int,
    payload_diagnostics: Any = None,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for item in _diagnostic_list(payload_diagnostics):
        diagnostics.append(item)
    for item in _diagnostic_list(runtime_smoke.get("evidence_diagnostics")):
        diagnostics.append(item)
    provider_unavailable = bool(runtime_smoke.get("provider_unavailable"))
    if provider_unavailable and not any(
        item.get("code") == "solver_design_smoke_provider_unavailable"
        for item in diagnostics
    ):
        diagnostics.append(
            {
                "code": "solver_design_smoke_provider_unavailable",
                "severity": "warning",
                "detail": (
                    "No problem-owned solver-design smoke provider is registered; "
                    "provider representative smoke cases cannot be selected."
                ),
                "provider_case_count": provider_case_count,
                "provider_case_attempted_count": provider_case_attempted_count,
                "case_count": runtime_smoke.get("case_count"),
            }
        )
    missing_fields = [
        field
        for field in (
            "provider_case_count",
            "provider_case_attempted_count",
            "case_execution_ledger",
        )
        if field not in runtime_smoke
        and not (field == "case_execution_ledger" and "cases" in runtime_smoke)
    ]
    if missing_fields and not provider_unavailable:
        diagnostics.append(
            {
                "code": "algorithm_smoke_provider_ledger_fields_missing",
                "severity": "warning",
                "detail": (
                    "Algorithm smoke payload lacked provider representative "
                    "case ledger/count fields; scratch evidence synthesized a "
                    "minimal ledger from compact runtime_smoke."
                ),
                "missing_fields": missing_fields,
            }
        )
    selected_surface = str(runtime_smoke.get("selected_surface") or "").strip()
    if (
        runtime_smoke.get("runtime_smoke_run")
        and selected_surface == "solver_design"
        and provider_case_count <= 0
        and not provider_unavailable
    ):
        diagnostics.append(
            {
                "code": "provider_representative_smoke_evidence_missing",
                "severity": "warning",
                "detail": (
                    "Algorithm smoke evidence does not show provider "
                    "representative cases; it may only prove canary or compact "
                    "runtime smoke execution."
                ),
                "provider_case_count": provider_case_count,
                "provider_case_attempted_count": provider_case_attempted_count,
                "case_count": runtime_smoke.get("case_count"),
            }
        )
    if provider_case_count > 0 and provider_case_attempted_count < provider_case_count:
        diagnostics.append(
            {
                "code": "provider_representative_smoke_cases_not_fully_attempted",
                "severity": "warning",
                "detail": (
                    "Provider representative smoke cases were selected but not "
                    "all were attempted before smoke completion."
                ),
                "provider_case_count": provider_case_count,
                "provider_case_attempted_count": provider_case_attempted_count,
            }
        )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in diagnostics:
        code = str(item.get("code") or item.get("detail") or item)
        if code in seen:
            continue
        seen.add(code)
        deduped.append(item)
    return deduped[:8]


def _diagnostic_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
