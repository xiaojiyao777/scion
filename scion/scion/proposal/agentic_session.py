"""Bounded Agentic Proposal Session skeleton.

The session lives inside the tainted Creative Layer.  It may draft and persist
proposal-session artifacts, but it returns only the existing proposal shapes
that downstream Contract/Workspace/Verification services already understand.
"""

from __future__ import annotations

import json
import re
import signal
import threading
import time
import uuid
from dataclasses import replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.engine import ProposalValidationError
from scion.proposal.agentic_artifacts import (
    AgenticSessionStore,
    FileAgenticSessionArtifactStore,
    compute_agentic_idempotency_key,
    ensure_agentic_output_audit_metadata,
    inspect_agentic_session_artifact,
    resume_from_artifact,
    validate_agentic_session_artifact,
    _agentic_output_artifact,
    _agentic_transcript_artifact,
    _champion_version,
    _champion_weight_revision,
    _compact_transcript,
    _load_artifact_payload,
    _proposal_payload,
    _tool_call_fingerprint,
    _tool_budget_used_payload,
    _tool_loop_config_payload,
    _transcript_digest,
)
from scion.proposal.agentic_models import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticEvidenceRef,
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalPhase,
    AgenticProposalRequest,
    AgenticProposalSessionState,
    AgenticProposalStatus,
    AgenticSessionArtifactStore,
    AgenticTerminationReason,
    AgenticTranscriptEvent,
    AgenticToolLoopConfig,
    CreativeProposalLike,
)
from scion.proposal.agentic_code_context import (
    _code_context_tool_summary,
    _code_observation_prompt_payload,
    _code_prompt_observations,
    _code_timeout_retry_context,
    _is_code_generation_timeout,
    _observation_prompt_payload,
    _with_code_scope_control,
)
from scion.proposal.agentic_diagnostics import (
    _research_diagnosis_from_observations,
)
from scion.proposal.mechanism_novelty import MechanismNoveltyGate
from scion.proposal.agentic_preview import (
    AgenticSelfCheck,
    _algorithm_smoke_failure_detail,
    _compact_algorithm_smoke_observation,
    _compact_contract_preview_observation,
    _compact_self_check_preview_observation,
    _latest_preview_failure_detail,
    _minimal_self_check_preview_observation,
    _preview_observation_passed,
    _self_check_failure_detail,
    _self_check_from_previews,
    _self_check_required,
)
from scion.proposal.agentic_session_budget import (
    _code_phase_budget_reserved as _code_phase_budget_reserved_for_config,
    _diagnosis_budget_reserved as _diagnosis_budget_reserved_for_config,
    _diagnosis_feedback_budget_reserved as _diagnosis_feedback_budget_reserved_for_config,
    _minimum_budgeted_observation_chars,
    _observation_budget_exhausted as _observation_budget_exhausted_for_config,
    _optional_surface_read_budget_floor as _optional_surface_read_budget_floor_for_config,
    _remaining_observation_chars as _remaining_observation_chars_for_config,
    _remaining_tool_calls as _remaining_tool_calls_for_config,
    _remaining_tool_steps as _remaining_tool_steps_for_config,
    _self_check_observation_reserve_chars as _self_check_observation_reserve_chars_for_config,
    _self_check_step_reserve as _self_check_step_reserve_for_config,
    _self_check_tool_call_reserve as _self_check_tool_call_reserve_for_config,
    _should_deny_optional_tool_for_budget as _should_deny_optional_tool_for_budget_config,
)
from scion.proposal.agentic_session_feedback import (
    _compact_feedback_observation_for_budget,
    _feedback_query_args,
    _has_feedback_screening_history,
    _observation_satisfies_compact_requirement,
)
from scion.proposal.agentic_session_tools import (
    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
    _APS_CODE_SURFACE_READ_CODE_CHARS,
    _APS_SURFACE_READ_CODE_CHARS,
    _algorithm_file_path_guidance,
    _budgeted_tool_args,
    _filter_code_phase_tool_names,
    _filter_model_facing_tool_names,
    _has_code_phase_surface_read,
    _has_successful_code_phase_reusable_observation,
    _has_successful_reusable_observation,
    _has_successful_surface_read,
    _has_successful_tool,
    _is_solver_design_algorithm_target,
    _is_solver_design_support_module_target,
    _observation_selection_payload,
    _recommended_algorithm_file_path,
    _surface_names_from_observations,
)
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _enum_value,
    _json_size,
    _limit_string,
    _sanitize_agentic_value,
)
from scion.proposal.llm_client import (
    LLMFormatError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)
from scion.proposal.prompt_manifest import (
    build_api_visible_prompt_manifest,
    stable_digest,
)
from scion.proposal.tools import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalTaint,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    ProposalToolRegistry,
    _active_boundary_novelty_requirements,
)

_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC = 12.0
_ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC = 36.0
_SELF_REPORTED_CODE_FAILURE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:has|contains)\s+(?:a\s+)?syntax error\b"), "syntax_error"),
    (re.compile(r"\binvalid syntax\b"), "syntax_error"),
    (re.compile(r"\b(?:does not|will not|won't)\s+compile\b"), "does_not_compile"),
    (re.compile(r"\bneeds\s+(?:fixing|to be fixed)\b"), "needs_fixing"),
    (re.compile(r"\bmust\s+be\s+fixed\b"), "needs_fixing"),
    (re.compile(r"\bstill\s+(?:broken|failing|fails)\b"), "still_failing"),
    (re.compile(r"\b(?:not implemented|not yet implemented)\b"), "not_implemented"),
    (re.compile(r"\b(?:incomplete|unfinished)\b"), "incomplete"),
    (re.compile(r"\b(?:todo|fixme)\b"), "placeholder"),
)
_SELF_REPORTED_SYNTAX_NEGATIONS = (
    "no syntax error",
    "no syntax errors",
    "without syntax error",
    "without syntax errors",
    "valid syntax",
    "syntax-valid",
)
_CODE_PROMPT_STRING_CHARS = 1600
_CODE_PROMPT_LIST_ITEMS = 12
_CODE_PROMPT_MAP_ITEMS = 32
_CODE_PROMPT_FEEDBACK_TOOLS = frozenset(
    {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
        "context.read_branch_state",
    }
)
_AUTHORITATIVE_PREVIEW_TOOL_NAMES = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)
_AUTHORITATIVE_PREVIEW_SELECTION_SOURCES = frozenset({"fallback_selected"})
_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
_HYPOTHESIS_PROMPT_COMPACT_REQUIREMENT_TOOLS = frozenset(
    {
        "feedback.query_screening",
        "feedback.query_runtime",
    }
)
_SOLVER_DESIGN_GROUNDING_TOOLS = (
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
)
_SOLVER_DESIGN_FILE_DISCOVERY_TOOLS = ("context.list_algorithm_files",)
_SOLVER_DESIGN_BROAD_TERMS = (
    "hybrid",
    "alns",
    "vns",
    "lns",
    "destroy",
    "repair",
    "recombination",
    "route-pool",
    "route pool",
    "population",
    "portfolio",
    "ensemble",
    "multi-operator",
    "multi operator",
    "restart",
    "perturb",
)
_PATCH_METADATA_FIELDS = frozenset(
    {"premise_check", "premise_check_reason", "repair_attribution"}
)
_FAILURE_LEDGER_SCHEMA_VERSION = "agentic-retry-error-ledger.v1"
_MECHANISM_NOVELTY_GATE = MechanismNoveltyGate()
_SELF_CHECK_PREVIEW_OBSERVATION_BUDGET_CHARS = 24000
_PREVIEW_OBSERVATION_BUDGET_EXHAUSTED_CODE = "observation_budget_exhausted"
_PREVIEW_SESSION_TIMEOUT_CODE = "session_timeout"
_AGENT_GROUNDING_FAILURE = "agent_grounding_failure"
_LEGACY_PREMISE_CONTRADICTED = AgenticFailureCategory.PREMISE_CONTRADICTED.value
_PROPOSAL_PREMISE_CONTRADICTED_CODE = "proposal_premise_contradicted"
_AGENT_QUALITY_BLOCKED_REASON = "agent_quality_blocked"


class _ProposalToolTimeout(BaseException):
    pass


def _authoritative_preview_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    state: AgenticProposalSessionState,
) -> tuple[ProposalObservation, ...]:
    """Return deterministic self-check previews, excluding planner exploration."""
    ids = _authoritative_preview_observation_ids(state)
    return tuple(
        observation for observation in observations if observation.observation_id in ids
    )


def _authoritative_preview_observation_ids(
    state: AgenticProposalSessionState,
) -> set[str]:
    ids: set[str] = set()
    for event in state.transcript:
        if str(event.phase or "") != AgenticProposalPhase.SELF_CHECK.value:
            continue
        metadata = dict(event.metadata or {})
        if metadata.get("tool_name") not in _AUTHORITATIVE_PREVIEW_TOOL_NAMES:
            continue
        if (
            str(metadata.get("selection_source") or "")
            not in _AUTHORITATIVE_PREVIEW_SELECTION_SOURCES
        ):
            continue
        observation_id = str(
            metadata.get("observation_id") or metadata.get("evidence_ref") or ""
        ).strip()
        if observation_id:
            ids.add(observation_id)
    return ids


def _is_authoritative_self_check_preview_call(
    name: str,
    phase: AgenticProposalPhase,
    selection_source: str,
) -> bool:
    return (
        phase == AgenticProposalPhase.SELF_CHECK
        and name in _AUTHORITATIVE_PREVIEW_TOOL_NAMES
        and selection_source in _AUTHORITATIVE_PREVIEW_SELECTION_SOURCES
    )


def _preview_limit_error_code(tool_name: str, stop_reason: str) -> str:
    if stop_reason == "session_timeout":
        return _PREVIEW_SESSION_TIMEOUT_CODE
    if stop_reason == "observation_budget_exhausted":
        return _PREVIEW_OBSERVATION_BUDGET_EXHAUSTED_CODE
    suffix = str(tool_name or "preview").split(".")[-1]
    return f"tool_loop_limit_before_{suffix}"


def _can_use_signal_timeout() -> bool:
    return (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
    )


def _preview_tool_timeout_sec(name: str) -> float:
    if name == "proposal.algorithm_smoke":
        return _ALGORITHM_SMOKE_TOOL_TIMEOUT_SEC
    return _CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC


class AgenticProposalSession:
    """APS-1 deterministic session skeleton.

    The default implementation wraps the current two-step CreativeLayer path.
    Tests and future callers may inject a fixed output to exercise failure and
    partial-session handling without contacting a real LLM.
    """

    _SESSION_ERROR_TYPES = (
        LLMRetryExhaustedError,
        LLMFormatError,
        LLMTimeoutError,
        ProposalValidationError,
    )

    def __init__(
        self,
        creative: CreativeProposalLike | None = None,
        *,
        artifact_store: AgenticSessionArtifactStore | None = None,
        tool_registry: ProposalToolRegistry | None = None,
        tool_loop_config: AgenticToolLoopConfig | None = None,
        injected_output: (
            AgenticProposalOutput
            | Callable[[AgenticProposalRequest], AgenticProposalOutput]
            | None
        ) = None,
    ) -> None:
        self._creative = creative
        self._artifact_store = artifact_store
        self.tool_registry = tool_registry
        self._tool_loop_config = tool_loop_config or AgenticToolLoopConfig()
        self._injected_output = injected_output

    def idempotency_key_for_request(self, request: AgenticProposalRequest) -> str:
        return compute_agentic_idempotency_key(request, self._tool_loop_config)

    def _self_check_from_authoritative_previews(
        self,
        observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
        state: AgenticProposalSessionState,
    ) -> AgenticSelfCheck:
        return _self_check_from_previews(
            _authoritative_preview_observations(observations, state)
        )

    def _latest_authoritative_preview_failure_detail(
        self,
        observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
        state: AgenticProposalSessionState,
    ) -> str | None:
        return _latest_preview_failure_detail(
            _authoritative_preview_observations(observations, state)
        )

    def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
        session_id = str(uuid.uuid4())
        request_id = session_id
        idempotency_key = self.idempotency_key_for_request(request)
        state = AgenticProposalSessionState(
            session_id=session_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            tool_loop_config=_tool_loop_config_payload(self._tool_loop_config),
        )
        state.note(
            AgenticProposalPhase.ORIENT, "Loaded exposure-controlled proposal context."
        )
        state.note(
            AgenticProposalPhase.DIAGNOSE, "Prepared deterministic APS-1 proposal path."
        )
        evidence: list[AgenticEvidenceRef] = []
        observations: list[ProposalObservation] = []
        if self._session_timeout_reached(state):
            output = self._timeout_output(request, state, evidence_used=tuple(evidence))
            state.status = output.status
            return self._persist(output, state)

        if self.tool_registry is not None:
            if request.tool_context is None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.UNHANDLED_ERROR,
                    detail=(
                        "AgenticProposalSession requires ProposalToolContext "
                        "when a ProposalToolRegistry is configured"
                    ),
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session failed before proposal generation because tool context was missing.",
                )
                return self._persist(output, state)

            tool_context = replace(
                request.tool_context,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch=request.branch,
                champion=request.champion,
                problem_id=request.problem_id or request.tool_context.problem_id,
                problem_spec_hash=(
                    request.problem_spec_hash or request.tool_context.problem_spec_hash
                ),
            )
            observations = self._run_initial_tool_loop(tool_context, state)
            evidence.extend(_evidence_from_observations(observations))
            fatal_observation_error = self._fatal_observation_error(observations)
            if state.loop_stop_reason == "session_timeout":
                output = self._timeout_output(
                    request,
                    state,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                return self._persist(output, state)
            if fatal_observation_error is None:
                fatal_observation_error = self._missing_required_context_error(
                    observations,
                    context=tool_context,
                )
            if fatal_observation_error is not None:
                termination_reason = (
                    AgenticTerminationReason.TOOL_LOOP_LIMIT
                    if state.loop_stop_reason == "tool_loop_limit"
                    else AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED
                )
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=termination_reason,
                    detail=fatal_observation_error,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session failed closed after required proposal tool observation error.",
                    metadata={"detail": fatal_observation_error},
                )
                return self._persist(output, state)
        else:
            tool_context = None

        if self._injected_output is not None:
            output = self._resolve_injected_output(request, session_id)
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Finalized injected agentic proposal output.",
                metadata={"status": _enum_value(output.status)},
            )
            return self._persist(output, state)

        if self._creative is None:
            output = self._failed_output(
                request=request,
                session_id=session_id,
                status=AgenticProposalStatus.FAILED,
                termination_reason=AgenticTerminationReason.UNHANDLED_ERROR,
                detail="AgenticProposalSession requires a creative layer or injected output",
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Session failed before proposal generation.",
            )
            return self._persist(output, state)

        hypothesis = request.approved_hypothesis
        if hypothesis is None:
            if self._session_timeout_reached(state):
                output = self._timeout_output(
                    request,
                    state,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                return self._persist(output, state)
            state.note(
                AgenticProposalPhase.CHOOSE_SURFACE, "Delegating hypothesis generation."
            )
            state.note(
                AgenticProposalPhase.DRAFT_HYPOTHESIS, "Generating hypothesis proposal."
            )
            try:
                hypothesis_context = dict(
                    _sanitize_agentic_value(request.hypothesis_context or {})
                )
                if request.resume_context is not None:
                    hypothesis_context["agentic_resume_context"] = (
                        _sanitize_agentic_value(request.resume_context)
                    )
                constraints = self._hypothesis_constraints(tool_context)
                if constraints:
                    hypothesis_context["agentic_hypothesis_constraints"] = (
                        _sanitize_agentic_value(constraints)
                    )
                if observations:
                    prompt_observations = _hypothesis_prompt_observations(
                        observations,
                        tool_context,
                    )
                    research_diagnosis = _research_diagnosis_from_observations(
                        observations
                    )
                    if research_diagnosis:
                        hypothesis_context["agentic_research_diagnosis"] = (
                            research_diagnosis
                        )
                    hypothesis_context["agentic_tool_observations"] = [
                        _observation_prompt_payload(observation)
                        for observation in prompt_observations
                    ]
                else:
                    prompt_observations = []
                self._record_prompt_manifest(
                    state,
                    call_kind="hypothesis",
                    prompt_context=hypothesis_context,
                    observations=prompt_observations,
                )
                hypothesis = self._creative.generate_hypothesis(hypothesis_context)
            except self._SESSION_ERROR_TYPES as exc:
                failure_category = _structured_output_failure_category(exc)
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    category=failure_category,
                    detail=str(exc),
                    source="hypothesis_generation_exception",
                    attempt=1,
                )
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=str(exc),
                    evidence_used=tuple(evidence),
                    failure_category=failure_category,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Hypothesis generation failed.",
                    metadata={"error": type(exc).__name__},
                )
                return self._persist(output, state)
            if self._session_timeout_reached(state):
                output = self._timeout_output(
                    request,
                    state,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                return self._persist(output, state)

            forced_violation = self._forced_hypothesis_violation(
                tool_context,
                hypothesis,
                request=request,
            )
            if forced_violation is not None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=forced_violation,
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Hypothesis generation violated the forced research-surface constraint.",
                    metadata={"detail": forced_violation},
                )
                return self._persist(output, state)

            if tool_context is not None:
                if _is_solver_design_hypothesis(hypothesis):
                    grounding_observations = self._run_solver_design_grounding_tools(
                        tool_context,
                        state,
                        observations,
                        selection_source="solver_design_grounding_required",
                    )
                    observations.extend(grounding_observations)
                    evidence.extend(_evidence_from_observations(grounding_observations))
                    grounding_error = _missing_solver_design_grounding_error(
                        observations,
                        hypothesis=hypothesis,
                    )
                    if grounding_error is not None:
                        output = self._failed_output(
                            request=request,
                            session_id=session_id,
                            status=AgenticProposalStatus.FAILED,
                            termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                            detail=grounding_error,
                            evidence_used=tuple(evidence),
                            failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                        )
                        state.status = output.status
                        state.note(
                            AgenticProposalPhase.FINALIZE,
                            "Session failed closed before solver_design hypothesis approval because active solver grounding was missing.",
                            metadata={"detail": grounding_error},
                        )
                        return self._persist(output, state)
                    novelty_output = self._mechanism_novelty_failed_output(
                        request=request,
                        session_id=session_id,
                        state=state,
                        hypothesis=hypothesis,
                        observations=observations,
                        evidence_used=tuple(evidence),
                    )
                    if novelty_output is not None:
                        return novelty_output
                selected_surface_observations = (
                    self._run_selected_surface_observation_tool(
                        tool_context,
                        hypothesis,
                        state,
                        observations,
                    )
                )
                observations.extend(selected_surface_observations)
                evidence.extend(
                    _evidence_from_observations(selected_surface_observations)
                )
                preview_observations = self._run_hypothesis_preview_tools(
                    tool_context,
                    hypothesis,
                    state,
                )
                observations.extend(preview_observations)
                evidence.extend(_evidence_from_observations(preview_observations))
                self_check = self._self_check_from_authoritative_previews(
                    observations,
                    state,
                )
                self_check_detail = _self_check_failure_detail(
                    self_check,
                    require_schema_preview=_self_check_required(tool_context),
                    require_contract_preview=False,
                )
                if self_check_detail is not None:
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.SELF_CHECK,
                        category=_preview_failure_category(preview_observations),
                        detail=self_check_detail,
                        source="hypothesis_preview_failure",
                    )
                    output = self._self_check_failed_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        detail=self_check_detail,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        evidence_used=tuple(evidence),
                        self_check=self_check,
                        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Hypothesis self-check failed closed before approval.",
                        metadata={"detail": self_check_detail},
                    )
                    return self._persist(output, state)

            if request.approve_hypothesis is None:
                output = self._partial_hypothesis_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail="hypothesis awaits ContractGate approval",
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
                    evidence_used=tuple(evidence),
                    self_check=self._self_check_from_authoritative_previews(
                        observations,
                        state,
                    ),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session paused before code context until hypothesis approval.",
                    metadata={
                        "selected_surface": hypothesis.change_locus,
                        "action": hypothesis.action,
                    },
                )
                return self._persist(output, state)

            state.note(
                AgenticProposalPhase.SELF_CHECK,
                "Validating hypothesis before code context.",
                metadata={
                    "selected_surface": hypothesis.change_locus,
                    "action": hypothesis.action,
                },
            )
            try:
                approval = request.approve_hypothesis(hypothesis)
            except Exception as exc:
                output = self._partial_hypothesis_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail=str(exc),
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED,
                    evidence_used=tuple(evidence),
                    self_check=self._self_check_from_authoritative_previews(
                        observations,
                        state,
                    ),
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Hypothesis approval failed before code context.",
                    metadata={"error": type(exc).__name__},
                )
                return self._persist(output, state)

            if not getattr(approval, "passed", False):
                output = self._partial_hypothesis_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail=getattr(approval, "failure_reason", None)
                    or "hypothesis approval failed",
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED,
                    evidence_used=tuple(evidence),
                    self_check=self._self_check_from_authoritative_previews(
                        observations,
                        state,
                    ),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Hypothesis approval rejected before code context.",
                )
                return self._persist(output, state)
        elif tool_context is not None:
            forced_violation = self._forced_hypothesis_violation(
                tool_context,
                hypothesis,
                request=request,
            )
            if forced_violation is not None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=forced_violation,
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Approved hypothesis violated the forced research-surface constraint.",
                    metadata={"detail": forced_violation},
                )
                return self._persist(output, state)
            if _is_solver_design_hypothesis(hypothesis):
                grounding_observations = self._run_solver_design_grounding_tools(
                    tool_context,
                    state,
                    observations,
                    selection_source="solver_design_grounding_required",
                )
                observations.extend(grounding_observations)
                evidence.extend(_evidence_from_observations(grounding_observations))
                grounding_error = _missing_solver_design_grounding_error(
                    observations,
                    hypothesis=hypothesis,
                )
                if grounding_error is not None:
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=grounding_error,
                        evidence_used=tuple(evidence),
                        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Session failed closed before solver_design hypothesis approval because active solver grounding was missing.",
                        metadata={"detail": grounding_error},
                    )
                    return self._persist(output, state)
                novelty_output = self._mechanism_novelty_failed_output(
                    request=request,
                    session_id=session_id,
                    state=state,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence_used=tuple(evidence),
                )
                if novelty_output is not None:
                    return novelty_output
            selected_surface_observations = self._run_selected_surface_observation_tool(
                tool_context,
                hypothesis,
                state,
                observations,
            )
            observations.extend(selected_surface_observations)
            evidence.extend(_evidence_from_observations(selected_surface_observations))
            preview_observations = self._run_hypothesis_preview_tools(
                tool_context,
                hypothesis,
                state,
            )
            observations.extend(preview_observations)
            evidence.extend(_evidence_from_observations(preview_observations))
            self_check = self._self_check_from_authoritative_previews(
                observations,
                state,
            )
            self_check_detail = _self_check_failure_detail(
                self_check,
                require_schema_preview=_self_check_required(tool_context),
                require_contract_preview=False,
            )
            if self_check_detail is not None:
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.SELF_CHECK,
                    category=_preview_failure_category(preview_observations),
                    detail=self_check_detail,
                    source="hypothesis_preview_failure",
                )
                output = self._self_check_failed_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail=self_check_detail,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    evidence_used=tuple(evidence),
                    self_check=self_check,
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Approved hypothesis self-check failed closed before code context.",
                    metadata={"detail": self_check_detail},
                )
                return self._persist(output, state)

        state.note(
            AgenticProposalPhase.INSPECT_INTERFACE,
            "Building code context for approved hypothesis.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "action": hypothesis.action,
            },
        )
        try:
            if self._session_timeout_reached(state):
                output = self._timeout_output(
                    request,
                    state,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                return self._persist(output, state)
            code_context = dict(request.build_code_context(hypothesis))
            if request.resume_context is not None:
                code_context["agentic_resume_context"] = _sanitize_agentic_value(
                    request.resume_context
                )
            if tool_context is not None:
                code_phase_observations = self._run_code_context_tool_loop(
                    tool_context,
                    state,
                    hypothesis,
                    observations,
                    code_context,
                )
                observations.extend(code_phase_observations)
                evidence.extend(_evidence_from_observations(code_phase_observations))
            if observations:
                research_diagnosis = _research_diagnosis_from_observations(observations)
                if research_diagnosis:
                    code_context["agentic_research_diagnosis"] = research_diagnosis
                code_context["agentic_tool_observations"] = [
                    _code_observation_prompt_payload(observation)
                    for observation in _code_prompt_observations(observations)
                ]
                active_mechanisms = _active_solver_mechanism_evidence_for_code_context(
                    observations
                )
                if active_mechanisms:
                    code_context["agentic_active_solver_mechanisms"] = active_mechanisms
            code_context = _with_code_scope_control(
                code_context,
                hypothesis,
                timeout_retry=False,
            )
            state.note(AgenticProposalPhase.DRAFT_PATCH, "Generating patch proposal.")
            patch = self._generate_code_with_timeout_retry(
                state=state,
                hypothesis=hypothesis,
                code_context=code_context,
                observations=observations,
            )
            code_repair_attempts_used = 0
        except self._SESSION_ERROR_TYPES as exc:
            failure_category = _structured_output_failure_category(exc)
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=str(exc),
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
                failure_category=failure_category,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch generation failed after hypothesis draft.",
                metadata={"error": type(exc).__name__},
            )
            return self._persist(output, state)
        if self._session_timeout_reached(state):
            output = self._timeout_output(
                request,
                state,
                evidence_used=tuple(evidence),
            )
            state.status = output.status
            return self._persist(output, state)

        premise_rejection = _patch_premise_rejection(patch, hypothesis)
        if premise_rejection is not None:
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_PATCH,
                category=str(premise_rejection["failure_category"]),
                detail=str(premise_rejection.get("reason") or ""),
                source="premise_check",
                attempt=1,
            )
            output = self._structured_rejection_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                rejection=premise_rejection,
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Code phase rejected the approved hypothesis after premise check.",
                metadata={
                    "premise_check": premise_rejection["premise_check"],
                    "failure_category": premise_rejection["failure_category"],
                    "structured_rejection": premise_rejection,
                },
            )
            return self._persist(output, state)

        self_reported_issue = _patch_self_reported_unresolved_issue(patch)
        if (
            self_reported_issue is not None
            and code_repair_attempts_used
            < self._tool_loop_config.max_code_repair_attempts
            and not self._session_timeout_reached(state)
        ):
            patch = self._repair_patch_after_code_self_check(
                request=request,
                state=state,
                hypothesis=hypothesis,
                code_context=code_context,
                observations=observations,
                patch=patch,
                issue_detail=self_reported_issue,
                repair_attempt=code_repair_attempts_used + 1,
            )
            code_repair_attempts_used += 1
            premise_rejection = _patch_premise_rejection(patch, hypothesis)
            if premise_rejection is not None:
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_PATCH,
                    category=str(premise_rejection["failure_category"]),
                    detail=str(premise_rejection.get("reason") or ""),
                    source="premise_check",
                    repair_attempt=code_repair_attempts_used,
                )
                output = self._structured_rejection_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    rejection=premise_rejection,
                    evidence_used=tuple(evidence),
                    self_check=self._self_check_from_authoritative_previews(
                        observations,
                        state,
                    ),
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Patch repair rejected the approved hypothesis after premise check.",
                    metadata={
                        "premise_check": premise_rejection["premise_check"],
                        "failure_category": premise_rejection["failure_category"],
                    },
                )
                return self._persist(output, state)
            self_reported_issue = _patch_self_reported_unresolved_issue(patch)
        if self_reported_issue is not None:
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_PATCH,
                category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
                detail=self_reported_issue,
                source="patch_self_reported_issue",
            )
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_reported_issue,
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
                failure_category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch generation failed because generated patch self-reported an unresolved code issue.",
                metadata={"detail": self_reported_issue},
            )
            return self._persist(output, state)

        if tool_context is not None:
            while True:
                patch_preview = self._run_contract_preview_tool(
                    tool_context,
                    hypothesis,
                    patch,
                    state,
                )
                observations.append(patch_preview)
                evidence.extend(_evidence_from_observations((patch_preview,)))
                if not _preview_observation_passed(patch_preview):
                    preview_category = _preview_failure_category([patch_preview])
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.SELF_CHECK,
                        category=preview_category,
                        detail=(
                            _latest_preview_failure_detail([patch_preview])
                            or patch_preview.summary
                        ),
                        source="preview_failure",
                        tool_name=patch_preview.tool_name,
                        observation=patch_preview,
                        repair_attempt=code_repair_attempts_used,
                    )
                    if (
                        code_repair_attempts_used
                        >= self._tool_loop_config.max_code_repair_attempts
                        or self._session_timeout_reached(state)
                    ):
                        break
                    try:
                        patch = self._repair_patch_after_preview(
                            request=request,
                            state=state,
                            hypothesis=hypothesis,
                            code_context=code_context,
                            observations=observations,
                            failed_preview=patch_preview,
                            repair_attempt=code_repair_attempts_used + 1,
                        )
                        code_repair_attempts_used += 1
                    except self._SESSION_ERROR_TYPES as exc:
                        failure_category = _structured_output_failure_category(exc)
                        output = self._partial_hypothesis_output(
                            request=request,
                            session_id=session_id,
                            hypothesis=hypothesis,
                            detail=str(exc),
                            evidence_used=tuple(evidence),
                            self_check=self._self_check_from_authoritative_previews(
                                observations,
                                state,
                            ),
                            failure_category=failure_category,
                        )
                        state.status = output.status
                        state.note(
                            AgenticProposalPhase.FINALIZE,
                            "Patch repair generation failed after Contract preview feedback.",
                            metadata={"error": type(exc).__name__},
                        )
                        return self._persist(output, state)
                    premise_rejection = _patch_premise_rejection(patch, hypothesis)
                    if premise_rejection is not None:
                        _record_failure_ledger_entry(
                            state,
                            phase=AgenticProposalPhase.DRAFT_PATCH,
                            category=str(premise_rejection["failure_category"]),
                            detail=str(premise_rejection.get("reason") or ""),
                            source="premise_check",
                            repair_attempt=code_repair_attempts_used,
                        )
                        output = self._structured_rejection_output(
                            request=request,
                            session_id=session_id,
                            hypothesis=hypothesis,
                            rejection=premise_rejection,
                            evidence_used=tuple(evidence),
                            self_check=self._self_check_from_authoritative_previews(
                                observations,
                                state,
                            ),
                        )
                        state.status = output.status
                        state.note(
                            AgenticProposalPhase.FINALIZE,
                            "Patch repair rejected the approved hypothesis after premise check.",
                            metadata={
                                "premise_check": premise_rejection["premise_check"],
                                "failure_category": premise_rejection[
                                    "failure_category"
                                ],
                            },
                        )
                        return self._persist(output, state)
                    self_reported_issue = _patch_self_reported_unresolved_issue(patch)
                    if self_reported_issue is not None:
                        _record_failure_ledger_entry(
                            state,
                            phase=AgenticProposalPhase.DRAFT_PATCH,
                            category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
                            detail=self_reported_issue,
                            source="patch_self_reported_issue",
                            repair_attempt=code_repair_attempts_used,
                        )
                        output = self._partial_hypothesis_output(
                            request=request,
                            session_id=session_id,
                            hypothesis=hypothesis,
                            detail=self_reported_issue,
                            evidence_used=tuple(evidence),
                            self_check=self._self_check_from_authoritative_previews(
                                observations,
                                state,
                            ),
                            failure_category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
                        )
                        state.status = output.status
                        state.note(
                            AgenticProposalPhase.FINALIZE,
                            "Patch repair failed because generated patch self-reported an unresolved code issue.",
                            metadata={"detail": self_reported_issue},
                        )
                        return self._persist(output, state)
                    continue

                smoke_preview = self._run_algorithm_smoke_tool(
                    tool_context,
                    hypothesis,
                    patch,
                    state,
                )
                observations.append(smoke_preview)
                evidence.extend(_evidence_from_observations((smoke_preview,)))
                if _preview_observation_passed(smoke_preview):
                    break
                smoke_category = _preview_failure_category([smoke_preview])
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.SELF_CHECK,
                    category=smoke_category,
                    detail=(
                        _latest_preview_failure_detail([smoke_preview])
                        or smoke_preview.summary
                    ),
                    source="preview_failure",
                    tool_name=smoke_preview.tool_name,
                    observation=smoke_preview,
                    repair_attempt=code_repair_attempts_used,
                )
                if (
                    code_repair_attempts_used
                    >= self._tool_loop_config.max_code_repair_attempts
                    or self._session_timeout_reached(state)
                ):
                    break
                try:
                    patch = self._repair_patch_after_preview(
                        request=request,
                        state=state,
                        hypothesis=hypothesis,
                        code_context=code_context,
                        observations=observations,
                        failed_preview=smoke_preview,
                        repair_attempt=code_repair_attempts_used + 1,
                    )
                    code_repair_attempts_used += 1
                except self._SESSION_ERROR_TYPES as exc:
                    failure_category = _structured_output_failure_category(exc)
                    output = self._partial_hypothesis_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        detail=str(exc),
                        evidence_used=tuple(evidence),
                        self_check=self._self_check_from_authoritative_previews(
                            observations,
                            state,
                        ),
                        failure_category=failure_category,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Patch repair generation failed after algorithm-smoke feedback.",
                        metadata={"error": type(exc).__name__},
                    )
                    return self._persist(output, state)
                premise_rejection = _patch_premise_rejection(patch, hypothesis)
                if premise_rejection is not None:
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_PATCH,
                        category=str(premise_rejection["failure_category"]),
                        detail=str(premise_rejection.get("reason") or ""),
                        source="premise_check",
                        repair_attempt=code_repair_attempts_used,
                    )
                    output = self._structured_rejection_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        rejection=premise_rejection,
                        evidence_used=tuple(evidence),
                        self_check=self._self_check_from_authoritative_previews(
                            observations,
                            state,
                        ),
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Patch repair rejected the approved hypothesis after premise check.",
                        metadata={
                            "premise_check": premise_rejection["premise_check"],
                            "failure_category": premise_rejection[
                                "failure_category"
                            ],
                        },
                    )
                    return self._persist(output, state)
                self_reported_issue = _patch_self_reported_unresolved_issue(patch)
                if self_reported_issue is not None:
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_PATCH,
                        category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
                        detail=self_reported_issue,
                        source="patch_self_reported_issue",
                        repair_attempt=code_repair_attempts_used,
                    )
                    output = self._partial_hypothesis_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        detail=self_reported_issue,
                        evidence_used=tuple(evidence),
                        self_check=self._self_check_from_authoritative_previews(
                            observations,
                            state,
                        ),
                        failure_category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Patch repair failed because generated patch self-reported an unresolved code issue.",
                        metadata={"detail": self_reported_issue},
                    )
                    return self._persist(output, state)

        state.note(AgenticProposalPhase.SELF_CHECK, "Recorded APS-1 schema self-check.")
        self_check = (
            self._self_check_from_authoritative_previews(observations, state)
            if tool_context is not None
            else AgenticSelfCheck(schema_valid=True)
        )
        preview_failure_detail = self._latest_authoritative_preview_failure_detail(
            observations,
            state,
        )
        if preview_failure_detail is not None:
            authoritative_previews = _authoritative_preview_observations(
                observations,
                state,
            )
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=preview_failure_detail,
                termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=_preview_failure_category(authoritative_previews),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch self-check failed closed after latest preview failure.",
                metadata={"detail": preview_failure_detail},
            )
            return self._persist(output, state)
        self_check_detail = _self_check_failure_detail(
            self_check,
            require_schema_preview=_self_check_required(tool_context),
            require_contract_preview=_self_check_required(tool_context),
        )
        if self_check_detail is not None:
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_check_detail,
                termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch self-check failed closed before completed output.",
                metadata={"detail": self_check_detail},
            )
            return self._persist(output, state)
        output = self._completed_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            patch=patch,
            evidence_used=tuple(evidence),
            self_check=self_check,
        )
        state.status = output.status
        state.note(AgenticProposalPhase.FINALIZE, "Session completed.")
        return self._persist(output, state)

    def _resolve_injected_output(
        self,
        request: AgenticProposalRequest,
        session_id: str,
    ) -> AgenticProposalOutput:
        injected = self._injected_output
        assert injected is not None
        output = injected(request) if callable(injected) else injected
        return replace(
            output,
            session_id=output.session_id or session_id,
            campaign_id=output.campaign_id or request.campaign_id,
            branch_id=output.branch_id or request.branch.branch_id,
            champion_version=(
                output.champion_version
                if output.champion_version is not None
                else _champion_version(request.champion)
            ),
            champion_weight_revision=(
                output.champion_weight_revision
                if output.champion_weight_revision is not None
                else _champion_weight_revision(request.champion)
            ),
            problem_id=output.problem_id or request.problem_id,
            problem_spec_hash=output.problem_spec_hash or request.problem_spec_hash,
            idempotency_key=output.idempotency_key
            or self.idempotency_key_for_request(request),
            termination_reason=(
                output.termination_reason
                if output.termination_reason != AgenticTerminationReason.UNHANDLED_ERROR
                else AgenticTerminationReason.INJECTED_OUTPUT
            ),
        )

    def _completed_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        self_check: AgenticSelfCheck | None = None,
    ) -> AgenticProposalOutput:
        return AgenticProposalOutput(
            status=AgenticProposalStatus.COMPLETED,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            idempotency_key=self._idempotency_key_for_hypothesis(
                request,
                hypothesis,
            ),
            champion_version=_champion_version(request.champion),
            champion_weight_revision=_champion_weight_revision(request.champion),
            problem_id=request.problem_id,
            problem_spec_hash=request.problem_spec_hash,
            selected_surface=hypothesis.change_locus,
            action=hypothesis.action,
            hypothesis=hypothesis,
            patch=patch,
            evidence_used=evidence_used,
            self_check=self_check
            or AgenticSelfCheck(
                schema_valid=True,
                schema_preview_codes=(),
                contract_preview_passed=None,
                contract_preview_codes=(),
            ),
            termination_reason=AgenticTerminationReason.COMPLETED,
        )

    def _forced_hypothesis_violation(
        self,
        context: ProposalToolContext | None,
        hypothesis: HypothesisProposal,
        *,
        request: AgenticProposalRequest | None = None,
    ) -> str | None:
        forced_surface = str(
            getattr(context, "forced_surface", None)
            or (
                (request.hypothesis_context or {}).get("forced_surface")
                if request is not None and request.hypothesis_context is not None
                else ""
            )
            or ""
        ).strip()
        if not forced_surface:
            boundary = tuple(
                str(surface or "").strip()
                for surface in getattr(
                    context,
                    "active_problem_boundary_surfaces",
                    (),
                )
                if str(surface or "").strip()
            )
            if not boundary and request is not None and request.hypothesis_context:
                constraints = request.hypothesis_context.get(
                    "agentic_hypothesis_constraints"
                )
                if isinstance(constraints, Mapping):
                    raw = constraints.get("active_problem_boundary_surfaces")
                    if isinstance(raw, str):
                        boundary = tuple(
                            item.strip() for item in raw.split(",") if item.strip()
                        )
                    elif isinstance(raw, (list, tuple)):
                        boundary = tuple(
                            str(item).strip() for item in raw if str(item).strip()
                        )
            if boundary:
                actual_surface = str(hypothesis.change_locus or "").strip()
                if actual_surface not in set(boundary):
                    return (
                        "active_problem_boundary_constraint: change_locus must "
                        f"stay within {list(boundary)!r}; got "
                        f"{actual_surface!r}. Component policies are "
                        "implementation hooks or attribution evidence, not "
                        "replacement research goals."
                    )
            return None
        actual_surface = str(hypothesis.change_locus or "").strip()
        if actual_surface != forced_surface:
            return (
                "forced_surface_constraint: change_locus must be "
                f"{forced_surface!r}, got {actual_surface!r}"
            )
        forced_action = str(
            getattr(context, "forced_action", None)
            or (
                (request.hypothesis_context or {}).get("forced_action")
                if request is not None and request.hypothesis_context is not None
                else ""
            )
            or ""
        ).strip()
        if forced_action and str(hypothesis.action or "").strip() != forced_action:
            return (
                "forced_surface_constraint: action must be "
                f"{forced_action!r}, got {str(hypothesis.action or '').strip()!r}"
            )
        forced_target = str(
            getattr(context, "forced_target_file", None)
            or (
                (request.hypothesis_context or {}).get("forced_target_file")
                if request is not None and request.hypothesis_context is not None
                else ""
            )
            or ""
        ).strip()
        if forced_target and str(hypothesis.target_file or "").strip() != forced_target:
            return (
                "forced_surface_constraint: target_file must be "
                f"{forced_target!r}, got {str(hypothesis.target_file or '').strip()!r}"
            )
        return None

    def _partial_hypothesis_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        hypothesis: HypothesisProposal,
        detail: str,
        termination_reason: AgenticTerminationReason = (
            AgenticTerminationReason.CODE_GENERATION_FAILED
        ),
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        self_check: AgenticSelfCheck | None = None,
        failure_category: AgenticFailureCategory | str | None = None,
    ) -> AgenticProposalOutput:
        return AgenticProposalOutput(
            status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            idempotency_key=self._idempotency_key_for_hypothesis(
                request,
                hypothesis,
            ),
            champion_version=_champion_version(request.champion),
            champion_weight_revision=_champion_weight_revision(request.champion),
            problem_id=request.problem_id,
            problem_spec_hash=request.problem_spec_hash,
            selected_surface=hypothesis.change_locus,
            action=hypothesis.action,
            hypothesis=hypothesis,
            patch=None,
            evidence_used=evidence_used,
            self_check=self_check or AgenticSelfCheck(schema_valid=True),
            termination_reason=termination_reason,
            failure_detail=detail,
            failure_category=failure_category,
        )

    def _structured_rejection_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        hypothesis: HypothesisProposal,
        rejection: Mapping[str, Any],
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        self_check: AgenticSelfCheck | None = None,
    ) -> AgenticProposalOutput:
        rejection_payload = _normalized_structured_rejection(rejection)
        detail = (
            f"premise_check={rejection_payload.get('premise_check')}: "
            f"{rejection_payload.get('reason') or 'code phase rejected premise'}"
        )
        return AgenticProposalOutput(
            status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            idempotency_key=self._idempotency_key_for_hypothesis(
                request,
                hypothesis,
            ),
            champion_version=_champion_version(request.champion),
            champion_weight_revision=_champion_weight_revision(request.champion),
            problem_id=request.problem_id,
            problem_spec_hash=request.problem_spec_hash,
            selected_surface=hypothesis.change_locus,
            action=hypothesis.action,
            hypothesis=hypothesis,
            patch=None,
            evidence_used=evidence_used,
            self_check=self_check or AgenticSelfCheck(schema_valid=True),
            termination_reason=_rejection_termination_reason(rejection_payload),
            failure_detail=detail,
            failure_category=str(rejection_payload.get("failure_category") or ""),
            structured_rejection=rejection_payload,
        )

    def _self_check_failed_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        hypothesis: HypothesisProposal,
        detail: str,
        termination_reason: AgenticTerminationReason,
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        self_check: AgenticSelfCheck | None = None,
        failure_category: AgenticFailureCategory | str | None = None,
    ) -> AgenticProposalOutput:
        return AgenticProposalOutput(
            status=AgenticProposalStatus.FAILED,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            idempotency_key=self._idempotency_key_for_hypothesis(
                request,
                hypothesis,
            ),
            champion_version=_champion_version(request.champion),
            champion_weight_revision=_champion_weight_revision(request.champion),
            problem_id=request.problem_id,
            problem_spec_hash=request.problem_spec_hash,
            selected_surface=hypothesis.change_locus,
            action=hypothesis.action,
            hypothesis=hypothesis,
            patch=None,
            evidence_used=evidence_used,
            self_check=self_check or AgenticSelfCheck(schema_valid=False),
            termination_reason=termination_reason,
            failure_detail=detail,
            failure_category=failure_category,
        )

    def _idempotency_key_for_hypothesis(
        self,
        request: AgenticProposalRequest,
        hypothesis: HypothesisProposal,
    ) -> str:
        return compute_agentic_idempotency_key(
            replace(request, approved_hypothesis=hypothesis),
            self._tool_loop_config,
        )

    def _failed_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        status: AgenticProposalStatus,
        termination_reason: AgenticTerminationReason,
        detail: str,
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        failure_category: AgenticFailureCategory | str | None = None,
    ) -> AgenticProposalOutput:
        return AgenticProposalOutput(
            status=status,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            idempotency_key=self.idempotency_key_for_request(request),
            champion_version=_champion_version(request.champion),
            champion_weight_revision=_champion_weight_revision(request.champion),
            problem_id=request.problem_id,
            problem_spec_hash=request.problem_spec_hash,
            evidence_used=evidence_used,
            self_check=AgenticSelfCheck(schema_valid=False),
            termination_reason=termination_reason,
            failure_detail=detail,
            failure_category=failure_category,
        )

    def _timeout_output(
        self,
        request: AgenticProposalRequest,
        state: AgenticProposalSessionState,
        *,
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
    ) -> AgenticProposalOutput:
        self._record_loop_stop(state, "session_timeout", error_code="session_timeout")
        return self._failed_output(
            request=request,
            session_id=state.session_id,
            status=AgenticProposalStatus.FAILED,
            termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
            detail=(
                "agentic proposal session exceeded max_wall_time_sec="
                f"{self._tool_loop_config.max_wall_time_sec}"
            ),
            evidence_used=evidence_used,
        )

    def _mechanism_novelty_failed_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence_used: tuple[AgenticEvidenceRef, ...] = (),
    ) -> AgenticProposalOutput | None:
        result = _MECHANISM_NOVELTY_GATE.evaluate(
            hypothesis,
            observations=observations,
        )
        if result is None:
            return None
        rejection = result.to_rejection(hypothesis)
        _record_failure_ledger_entry(
            state,
            phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
            category=result.failure_category,
            detail=result.reason,
            source="mechanism_novelty_gate",
        )
        output = self._structured_rejection_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            rejection=rejection,
            evidence_used=evidence_used,
            self_check=AgenticSelfCheck(schema_valid=True),
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            "Mechanism novelty gate rejected the solver_design hypothesis before code context.",
            metadata={
                "premise_check": result.premise_check,
                "failure_category": result.failure_category,
                "mechanism": result.mechanism,
            },
        )
        return self._persist(output, state)

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
        if self._supports_tool_selection():
            observations = self._run_bounded_planner_tools(context, state)
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
        return self._run_hypothesis_observation_tools(context, state)

    def _supports_tool_selection(self) -> bool:
        if self._creative is None:
            return False
        return callable(getattr(self._creative, "select_tool", None)) or callable(
            getattr(self._creative, "plan_tool_call", None)
        )

    def _run_bounded_planner_tools(
        self,
        context: ProposalToolContext,
        state: AgenticProposalSessionState,
    ) -> list[ProposalObservation]:
        observations: list[ProposalObservation] = []
        selector = getattr(self._creative, "select_tool", None)
        if not callable(selector):
            selector = getattr(self._creative, "plan_tool_call", None)
        if not callable(selector):
            return self._run_hypothesis_observation_tools(context, state)

        while not self._tool_loop_limit_reached(state):
            if self._planner_context_satisfied(context, observations):
                self._record_loop_stop(state, "required_context_satisfied")
                break
            if (
                self._diagnosis_budget_reserved(state)
                and self._missing_required_context_error(
                    observations,
                    context=context,
                )
                is None
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
                "tool_arg_guidance": self._tool_arg_guidance(context, observations),
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
                        "Planner stopped before required compact context; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "error_code": "planner_stopped_before_required_context",
                            "fallback": "fixed_tool_plan",
                            "detail": missing,
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="planner_stopped_before_required_context",
                        tool_name=None,
                    )
                self._record_loop_stop(state, "planner_stop")
                break
            if isinstance(planned, Mapping) and planned.get("stop"):
                missing = self._missing_planner_context_error(context, observations)
                if missing is not None:
                    state.note(
                        AgenticProposalPhase.DIAGNOSE,
                        "Planner stopped before required compact context; using fixed APS-0 tool plan.",
                        metadata={
                            "status": "error",
                            "error_code": "planner_stopped_before_required_context",
                            "fallback": "fixed_tool_plan",
                            "detail": missing,
                        },
                    )
                    return self._fallback_after_planner_error(
                        context,
                        state,
                        observations,
                        error_code="planner_stopped_before_required_context",
                        tool_name=None,
                    )
                self._record_loop_stop(state, "planner_stop")
                break

            if not isinstance(planned, Mapping):
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
            fingerprint = _tool_call_fingerprint(name, args)
            fuse_count = state.tool_call_fuse_counts.get(fingerprint, 0)
            if fuse_count >= self._tool_loop_config.max_repeated_tool_calls:
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
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    (
                        "Planner selected a proposal tool already completed "
                        "successfully; using fallback for missing context only."
                    ),
                    metadata={
                        "status": "skipped",
                        "tool_name": name,
                        "error_code": "already_succeeded",
                        "fallback": "fixed_tool_plan",
                        "selection_source": "planner_selected",
                        "skip_reason": "already_succeeded",
                    },
                )
                return self._fallback_after_planner_error(
                    context,
                    state,
                    observations,
                    error_code="already_succeeded",
                    tool_name=name,
                )
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
            observation = self._call_tool(
                context,
                state,
                AgenticProposalPhase.DIAGNOSE,
                name,
                args,
                selection_source="planner_selected",
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
            if self._planner_context_satisfied(context, observations):
                self._record_loop_stop(state, "required_context_satisfied")
                break

        if self._tool_loop_limit_reached(state) and state.loop_stop_reason is None:
            self._record_loop_stop(state, self._current_loop_stop_reason(state))
        missing = self._missing_planner_context_error(context, observations)
        if missing is not None and state.loop_stop_reason == "tool_loop_limit":
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Planner exhausted bounded tool loop before useful compact feedback; using fixed APS-0 tool plan.",
                metadata={
                    "status": "error",
                    "error_code": "planner_tool_loop_limit_before_feedback",
                    "fallback": "fixed_tool_plan",
                    "detail": missing,
                },
            )
            return self._fallback_after_planner_error(
                context,
                state,
                observations,
                error_code="planner_tool_loop_limit_before_feedback",
                tool_name=None,
            )
        return observations

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
        if not _has_successful_tool(prior_observations, "context.read_branch_state"):
            calls.append(("context.read_branch_state", {}))
        if not _has_code_phase_surface_read(prior_observations, hypothesis):
            args: dict[str, Any] = {
                "surface": hypothesis.change_locus,
                "detail": "full",
                "max_code_chars": _APS_CODE_SURFACE_READ_CODE_CHARS,
            }
            if hypothesis.target_file:
                args["target_file"] = hypothesis.target_file
            calls.append(("context.read_surface", args))

        observations: list[ProposalObservation] = []
        for name, args in calls:
            mandatory_surface_read = (
                name == "context.read_surface"
                and selection_source == "code_phase_required"
            )
            call_args: Mapping[str, Any] = args
            call_selection_source = selection_source
            preserve_observation_chars = 0
            if self._code_phase_budget_reserved(state) and not mandatory_surface_read:
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
            if mandatory_surface_read:
                preserve_observation_chars = self._minimum_budgeted_observation_chars()
                remaining_chars = self._remaining_observation_chars(state)
                if remaining_chars <= preserve_observation_chars:
                    state.note(
                        AgenticProposalPhase.INSPECT_INTERFACE,
                        "Skipped mandatory code-phase surface read to preserve patch self-check observation budget.",
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
                if self._code_phase_budget_reserved(state):
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
                        },
                    )
            if self._tool_loop_limit_reached(state) and not (
                mandatory_surface_read
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
        return _code_phase_budget_reserved_for_config(
            self._tool_loop_config,
            state,
        )

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
                    "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS
                    if _is_solver_design_support_module_target(recommended_file_path)
                    else _APS_CODE_SURFACE_READ_CODE_CHARS,
                },
                "purpose": "Read one allowlisted active solver file when full source is needed.",
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

    def _repair_patch_after_preview(
        self,
        *,
        request: AgenticProposalRequest,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
        failed_preview: ProposalObservation,
        repair_attempt: int = 1,
    ) -> PatchProposal:
        repair_context = dict(code_context)
        if failed_preview.tool_name == "proposal.algorithm_smoke":
            detail = _algorithm_smoke_failure_detail([failed_preview])
            repair_context["prior_code_failure"] = (
                detail
                or "Algorithm smoke failed before official screening: "
                f"{failed_preview.summary}"
            )
            feedback_kind = "algorithm-smoke"
        else:
            repair_context["prior_code_failure"] = (
                "Contract preview failed before workspace materialization: "
                f"{failed_preview.summary}"
            )
            feedback_kind = "Contract-preview"
        repair_context["agentic_preview_feedback"] = _observation_prompt_payload(
            failed_preview
        )
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            repair_context["agentic_research_diagnosis"] = research_diagnosis
        prompt_observations = _code_prompt_observations(observations)
        if failed_preview not in prompt_observations:
            prompt_observations.append(failed_preview)
        repair_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in prompt_observations
        ]
        state.note(
            AgenticProposalPhase.DRAFT_PATCH,
            f"Regenerating patch proposal with {feedback_kind} feedback.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "target_file": hypothesis.target_file,
                "repair_attempt": repair_attempt,
                "feedback_tool": failed_preview.tool_name,
            },
        )
        repair_context = _with_code_scope_control(
            repair_context,
            hypothesis,
            timeout_retry=False,
        )
        return self._generate_code_with_timeout_retry(
            state=state,
            hypothesis=hypothesis,
            code_context=repair_context,
            observations=observations,
        )

    def _repair_patch_after_code_self_check(
        self,
        *,
        request: AgenticProposalRequest,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
        patch: PatchProposal,
        issue_detail: str,
        repair_attempt: int,
    ) -> PatchProposal:
        del request
        repair_context = dict(code_context)
        repair_context["prior_code_failure"] = issue_detail
        repair_context["agentic_code_self_check_feedback"] = {
            "passed": False,
            "issue": issue_detail,
            "file_path": patch.file_path,
            "action": patch.action,
            "test_hint": patch.test_hint,
        }
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            repair_context["agentic_research_diagnosis"] = research_diagnosis
        repair_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in _code_prompt_observations(observations)
        ]
        state.note(
            AgenticProposalPhase.DRAFT_PATCH,
            "Regenerating patch proposal after code self-check feedback.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "target_file": hypothesis.target_file,
                "repair_attempt": repair_attempt,
                "issue": issue_detail,
            },
        )
        repair_context = _with_code_scope_control(
            repair_context,
            hypothesis,
            timeout_retry=False,
        )
        return self._generate_code_with_timeout_retry(
            state=state,
            hypothesis=hypothesis,
            code_context=repair_context,
            observations=observations,
        )

    def _generate_code_with_timeout_retry(
        self,
        *,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
    ) -> PatchProposal:
        assert self._creative is not None
        max_retries = max(
            0,
            int(self._tool_loop_config.max_code_generation_timeout_retries),
        )
        attempt_context: Mapping[str, Any] = code_context
        for attempt in range(max_retries + 1):
            try:
                self._record_prompt_manifest(
                    state,
                    call_kind="code",
                    prompt_context=attempt_context,
                    observations=observations,
                )
                return self._creative.generate_code(attempt_context)
            except self._SESSION_ERROR_TYPES as exc:
                category = _structured_output_failure_category(exc)
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_PATCH,
                    category=category,
                    detail=str(exc),
                    source="code_generation_exception",
                    attempt=attempt + 1,
                )
                if (
                    attempt >= max_retries
                    or self._session_timeout_reached(state)
                    or not _is_code_generation_timeout(exc)
                ):
                    raise
                attempt_context = _code_timeout_retry_context(
                    attempt_context,
                    hypothesis,
                    exc,
                    observations,
                )
                state.note(
                    AgenticProposalPhase.DRAFT_PATCH,
                    "Retrying patch generation with compact timeout scope.",
                    metadata={
                        "selected_surface": hypothesis.change_locus,
                        "target_file": hypothesis.target_file,
                        "retry_attempt": attempt + 1,
                        "max_timeout_retries": max_retries,
                        "error": type(exc).__name__,
                    },
                )
        raise RuntimeError("unreachable code-generation timeout retry state")

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
        return self._missing_planner_context_error(context, observations) is None

    def _missing_planner_context_error(
        self,
        context: ProposalToolContext,
        observations: list[ProposalObservation],
    ) -> str | None:
        required_error = self._missing_required_context_error(
            observations,
            context=context,
        )
        if required_error is not None:
            return required_error
        available_feedback = self._available_compact_feedback_tools(context)
        if not available_feedback:
            return None
        observed_ok = {
            observation.tool_name
            for observation in observations
            if _observation_satisfies_compact_requirement(context, observation)
        }
        missing_feedback = [
            tool_name
            for tool_name in available_feedback
            if tool_name not in observed_ok
        ]
        if missing_feedback:
            return "missing compact proposal feedback tools: " + ", ".join(
                missing_feedback
            )
        return None

    def _available_compact_feedback_tools(
        self,
        context: ProposalToolContext,
    ) -> tuple[str, ...]:
        if self.tool_registry is None:
            return ()
        allowed = set(self.tool_registry.allowed_tools(context))
        available: list[str] = []
        if "memory.query" in allowed and (
            context.search_memory is not None or context.research_log is not None
        ):
            available.append("memory.query")
        has_screening_steps = _has_feedback_screening_history(context)
        if "feedback.query_screening" in allowed and has_screening_steps:
            available.append("feedback.query_screening")
        if "feedback.query_runtime" in allowed and has_screening_steps:
            available.append("feedback.query_runtime")
        return tuple(available)

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
            recommended_file_path = _recommended_algorithm_file_path(
                algorithm_file_guidance
            )
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
                    "max_chars": _APS_CODE_SURFACE_READ_CODE_CHARS,
                },
                "purpose": (
                    "Read one allowlisted active solver file only after "
                    "context.list_algorithm_files has provided the file_path."
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
                "purpose": (
                    "Read one symbol from an allowlisted active solver file only "
                    "after context.list_algorithm_files has provided the file_path."
                ),
            }
        return guidance

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

    def _planner_observation_requires_fallback(
        self,
        observation: ProposalObservation,
    ) -> bool:
        if not observation.is_error:
            return False
        if observation.tool_name in {"context.list_surfaces", "context.read_problem"}:
            return False
        return observation.failure_code in {
            ProposalToolFailureCode.SCHEMA_ERROR,
            ProposalToolFailureCode.PERMISSION_DENIED,
            ProposalToolFailureCode.NOT_FOUND,
            ProposalToolFailureCode.UNSUPPORTED,
        }

    def _run_hypothesis_preview_tools(
        self,
        context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        state: AgenticProposalSessionState,
    ) -> list[ProposalObservation]:
        hypothesis_payload = _proposal_payload(hypothesis)
        calls: tuple[tuple[str, Mapping[str, Any]], ...] = (
            ("proposal.schema_preview", {"hypothesis": hypothesis_payload}),
            (
                "proposal.target_permission_preview",
                {
                    "change_locus": hypothesis.change_locus,
                    "action": hypothesis.action,
                    "target_file": hypothesis.target_file,
                },
            ),
        )
        observations: list[ProposalObservation] = []
        for name, args in calls:
            if self._tool_loop_limit_reached(
                state,
                ignore_observation_budget=True,
            ):
                self._record_loop_stop(state, self._current_loop_stop_reason(state))
                break
            observations.append(
                self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.SELF_CHECK,
                    name,
                    args,
                    selection_source="fallback_selected",
                )
            )
        return observations

    def _run_solver_design_grounding_tools(
        self,
        context: ProposalToolContext,
        state: AgenticProposalSessionState,
        prior_observations: list[ProposalObservation],
        *,
        selection_source: str,
    ) -> list[ProposalObservation]:
        observations: list[ProposalObservation] = []
        for name in _SOLVER_DESIGN_GROUNDING_TOOLS:
            if _has_successful_tool([*prior_observations, *observations], name):
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    "Skipped solver_design grounding tool already completed successfully.",
                    metadata={
                        "tool_name": name,
                        "status": "skipped",
                        "selection_source": selection_source,
                        "skip_reason": "already_succeeded",
                    },
                )
                continue
            if (
                name == "context.read_solver_call_graph"
                and _has_active_solver_embedded_call_graph(
                    [*prior_observations, *observations]
                )
            ):
                state.note(
                    AgenticProposalPhase.DIAGNOSE,
                    "Skipped solver_design grounding tool already covered by active solver snapshot.",
                    metadata={
                        "tool_name": name,
                        "status": "skipped",
                        "selection_source": selection_source,
                        "skip_reason": "active_solver_snapshot_includes_call_graph",
                    },
                )
                continue
            if self._tool_loop_limit_reached(state):
                self._record_loop_stop(state, self._current_loop_stop_reason(state))
                break
            observations.append(
                self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.DIAGNOSE,
                    name,
                    {"surface": "solver_design"},
                    selection_source=selection_source,
                )
            )
        return observations

    def _run_selected_surface_observation_tool(
        self,
        context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        state: AgenticProposalSessionState,
        observations: list[ProposalObservation],
    ) -> list[ProposalObservation]:
        if _has_successful_surface_read(observations, hypothesis.change_locus):
            state.note(
                AgenticProposalPhase.INSPECT_INTERFACE,
                "Skipped selected-surface read already completed successfully.",
                metadata={
                    "tool_name": "context.read_surface",
                    "status": "skipped",
                    "selection_source": "selected_surface_required",
                    "skip_reason": "already_succeeded",
                },
            )
            return []
        if self._tool_loop_limit_reached(state):
            self._record_loop_stop(state, self._current_loop_stop_reason(state))
            return []
        args: dict[str, Any] = {
            "surface": hypothesis.change_locus,
            "detail": "compact",
            "max_code_chars": _APS_SURFACE_READ_CODE_CHARS,
        }
        if hypothesis.target_file:
            args["target_file"] = hypothesis.target_file
        observation = self._call_tool(
            context,
            state,
            AgenticProposalPhase.INSPECT_INTERFACE,
            "context.read_surface",
            args,
            selection_source="selected_surface_required",
        )
        return [observation]

    def _run_contract_preview_tool(
        self,
        context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        state: AgenticProposalSessionState,
    ) -> ProposalObservation:
        if self._tool_loop_limit_reached(
            state,
            ignore_observation_budget=True,
        ):
            stop_reason = self._current_loop_stop_reason(state)
            self._record_loop_stop(
                state,
                stop_reason,
                error_code=_preview_limit_error_code(
                    "proposal.contract_preview",
                    stop_reason,
                ),
                tool_name="proposal.contract_preview",
            )
            return self._skipped_self_check_preview_observation(
                context,
                state,
                tool_name="proposal.contract_preview",
                summary=(
                    "Contract preview skipped because the session wall-time limit was reached."
                    if stop_reason == "session_timeout"
                    else "Contract preview skipped because the tool loop limit was reached."
                ),
                stop_reason=stop_reason,
            )
        return self._call_tool(
            context,
            state,
            AgenticProposalPhase.SELF_CHECK,
            "proposal.contract_preview",
            {
                "hypothesis": _proposal_payload(hypothesis),
                "patch": _patch_payload_for_preview(patch),
            },
            selection_source="fallback_selected",
        )

    def _run_algorithm_smoke_tool(
        self,
        context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        state: AgenticProposalSessionState,
    ) -> ProposalObservation:
        if self._tool_loop_limit_reached(
            state,
            ignore_observation_budget=True,
        ):
            stop_reason = self._current_loop_stop_reason(state)
            self._record_loop_stop(
                state,
                stop_reason,
                error_code=_preview_limit_error_code(
                    "proposal.algorithm_smoke",
                    stop_reason,
                ),
                tool_name="proposal.algorithm_smoke",
            )
            return self._skipped_self_check_preview_observation(
                context,
                state,
                tool_name="proposal.algorithm_smoke",
                summary=(
                    "Algorithm smoke skipped because the session wall-time limit was reached."
                    if stop_reason == "session_timeout"
                    else "Algorithm smoke skipped because the tool loop limit was reached."
                ),
                stop_reason=stop_reason,
            )
        return self._call_tool(
            context,
            state,
            AgenticProposalPhase.SELF_CHECK,
            "proposal.algorithm_smoke",
            {
                "hypothesis": _proposal_payload(hypothesis),
                "patch": _patch_payload_for_preview(patch),
            },
            selection_source="fallback_selected",
        )

    def _skipped_self_check_preview_observation(
        self,
        context: ProposalToolContext,
        state: AgenticProposalSessionState,
        *,
        tool_name: str,
        summary: str,
        stop_reason: str,
    ) -> ProposalObservation:
        error_code = _preview_limit_error_code(tool_name, stop_reason)
        observation = ProposalObservation(
            observation_id=str(uuid.uuid4()),
            session_id=context.session_id,
            tool_name=tool_name,
            tool_call_id="",
            observation_type="tool_skipped",
            summary=summary,
            structured_payload={
                "skip_reason": stop_reason,
                "budget_exhausted": (
                    stop_reason
                    in {
                        "tool_loop_limit",
                        "observation_budget_exhausted",
                        "session_timeout",
                    }
                ),
                "max_steps": self._tool_loop_config.max_steps,
                "max_tool_calls": self._tool_loop_config.max_tool_calls,
                "tool_steps": state.tool_step_count,
                "tool_calls": state.tool_call_count,
                "error_code": error_code,
            },
            is_error=True,
            failure_code=error_code,
            repair_hint="Start a new bounded proposal session with enough self-check budget.",
        )
        state.note(
            AgenticProposalPhase.SELF_CHECK,
            f"Proposal tool observation: {tool_name}",
            metadata={
                "tool_name": observation.tool_name,
                "status": "error",
                "taint": _enum_value(observation.taint),
                "evidence_ref": observation.observation_id,
                "result_summary": observation.summary,
                "error_code": error_code,
                "observation_id": observation.observation_id,
                "observation_type": observation.observation_type,
                "exposure_level": _enum_value(observation.exposure_level),
                "is_error": True,
                "failure_code": error_code,
                "selection_source": "fallback_selected",
                "skip_reason": stop_reason,
            },
        )
        return observation

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
            return ProposalObservation(
                observation_id=str(uuid.uuid4()),
                session_id=context.session_id,
                tool_name=name,
                tool_call_id="",
                observation_type="tool_error",
                summary="Proposal tool call skipped because session wall-time limit was reached.",
                structured_payload={
                    "max_wall_time_sec": self._tool_loop_config.max_wall_time_sec,
                },
                is_error=True,
                failure_code=ProposalToolFailureCode.RUNTIME_EXCEPTION,
                repair_hint="Start a new bounded proposal session.",
            )
        state.tool_step_count += 1
        state.tool_call_count += 1
        step_id = f"tool-{state.tool_step_count:04d}"
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
        observed_ok = {
            observation.tool_name
            for observation in observations
            if not observation.is_error
        }
        missing = [
            name
            for name in _required_context_tool_names(context)
            if name not in observed_ok
        ]
        if missing:
            return f"missing required proposal context tools: {', '.join(missing)}"
        return None

    def _persist(
        self,
        output: AgenticProposalOutput,
        state: AgenticProposalSessionState,
    ) -> AgenticProposalOutput:
        terminal_category = _terminal_failure_category(output, state)
        if (
            output.status != AgenticProposalStatus.COMPLETED
            and terminal_category
            and not state.failure_ledger
        ):
            _record_failure_ledger_entry(
                state,
                phase=state.phase,
                category=terminal_category,
                detail=output.failure_detail,
                source="terminal_output",
            )
        ledger = _failure_ledger_payload(state.failure_ledger)
        compact_transcript = _compact_transcript(tuple(state.transcript))
        transcript_digest = _transcript_digest(compact_transcript)
        output = replace(
            output,
            schema_version=AGENTIC_SESSION_SCHEMA_VERSION,
            request_id=output.request_id or state.request_id or state.session_id,
            idempotency_key=output.idempotency_key or state.idempotency_key,
            transcript=tuple(state.transcript),
            tool_loop_config=_tool_loop_config_payload(self._tool_loop_config),
            tool_budget_used=_tool_budget_used_payload(state),
            transcript_digest=transcript_digest,
            failure_category=terminal_category,
            failure_ledger=ledger,
        )
        state.idempotency_key = output.idempotency_key or state.idempotency_key
        if self._artifact_store is None:
            return output
        output = replace(
            output,
            tainted_artifact_refs=tuple(
                dict.fromkeys((*output.tainted_artifact_refs, *state.scratch_artifact_refs))
            ),
        )
        transcript_ref = self._artifact_store.write_transcript(state)
        output_with_transcript = replace(
            output,
            tainted_artifact_refs=tuple(
                dict.fromkeys((*output.tainted_artifact_refs, transcript_ref))
            ),
        )
        output_ref = self._artifact_store.write_output(output_with_transcript)
        return replace(
            output_with_transcript,
            tainted_artifact_refs=tuple(
                dict.fromkeys(
                    (*output_with_transcript.tainted_artifact_refs, output_ref)
                )
            ),
        )


def _evidence_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[AgenticEvidenceRef]:
    return [
        AgenticEvidenceRef(
            observation_id=observation.observation_id,
            exposure_level=str(_enum_value(observation.exposure_level)),
            summary=observation.summary,
        )
        for observation in observations
    ]


def _record_failure_ledger_entry(
    state: AgenticProposalSessionState,
    *,
    phase: AgenticProposalPhase,
    category: AgenticFailureCategory | str,
    detail: str | None = None,
    source: str = "",
    attempt: int | None = None,
    repair_attempt: int | None = None,
    tool_name: str | None = None,
    observation: ProposalObservation | None = None,
    failure_code: str | None = None,
) -> None:
    category_value = _failure_category_value(category)
    if not category_value:
        return
    if category_value == _LEGACY_PREMISE_CONTRADICTED:
        category_value = _AGENT_GROUNDING_FAILURE
        failure_code = failure_code or _PROPOSAL_PREMISE_CONTRADICTED_CODE
    observation_payload: dict[str, Any] = {}
    if observation is not None:
        observation_payload = {
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "failure_code": _enum_value(observation.failure_code),
        }
    entry = _drop_empty_dict(
        {
            "entry_id": f"failure-{len(state.failure_ledger) + 1:04d}",
            "phase": phase.value,
            "category": category_value,
            "root_cause": category_value,
            "detail": _limit_string(str(detail or ""), 800),
            "source": source,
            "attempt": attempt,
            "repair_attempt": repair_attempt,
            "tool_name": tool_name or observation_payload.get("tool_name"),
            "observation_id": observation_payload.get("observation_id"),
            "failure_code": failure_code or observation_payload.get("failure_code"),
        }
    )
    if _failure_ledger_latest_matches(state.failure_ledger, entry):
        return
    state.failure_ledger.append(entry)


def _failure_ledger_latest_matches(
    entries: list[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> bool:
    if not entries:
        return False
    latest = entries[-1]
    return (
        str(latest.get("phase") or "") == str(candidate.get("phase") or "")
        and str(latest.get("category") or "") == str(candidate.get("category") or "")
        and str(latest.get("detail") or "") == str(candidate.get("detail") or "")
        and str(latest.get("source") or "") == str(candidate.get("source") or "")
        and str(latest.get("tool_name") or "") == str(candidate.get("tool_name") or "")
    )


def _failure_ledger_payload(
    entries: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> dict[str, Any]:
    sanitized_entries = [
        _sanitize_agentic_value(dict(entry)) for entry in entries if entry
    ]
    return {
        "schema_version": _FAILURE_LEDGER_SCHEMA_VERSION,
        "entries": sanitized_entries,
        "entry_count": len(sanitized_entries),
        "first_root_cause": (
            sanitized_entries[0].get("root_cause") if sanitized_entries else None
        ),
        "first_failure_phase": (
            sanitized_entries[0].get("phase") if sanitized_entries else None
        ),
        "latest_failure": (
            sanitized_entries[-1].get("category") if sanitized_entries else None
        ),
        "latest_failure_phase": (
            sanitized_entries[-1].get("phase") if sanitized_entries else None
        ),
    }


def _failure_category_value(category: AgenticFailureCategory | str | None) -> str:
    return str(_enum_value(category) or "")


def _structured_output_failure_category(
    exc: BaseException,
) -> AgenticFailureCategory:
    if isinstance(exc, LLMRetryExhaustedError):
        return AgenticFailureCategory.STRUCTURED_OUTPUT_RETRY_EXHAUSTED
    return AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE


def _normalized_structured_rejection(
    rejection: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(rejection)
    if _structured_rejection_is_premise_contradicted(payload):
        legacy_category = str(_enum_value(payload.get("failure_category")) or "")
        if legacy_category and legacy_category != _AGENT_GROUNDING_FAILURE:
            payload.setdefault("legacy_failure_category", legacy_category)
        payload["failure_category"] = _AGENT_GROUNDING_FAILURE
        payload.setdefault("failure_code", _PROPOSAL_PREMISE_CONTRADICTED_CODE)
        payload.setdefault("agent_block_reason", _AGENT_QUALITY_BLOCKED_REASON)
    return payload


def _structured_rejection_is_premise_contradicted(
    rejection: Mapping[str, Any],
) -> bool:
    failure_category = str(_enum_value(rejection.get("failure_category")) or "")
    failure_code = str(rejection.get("failure_code") or "")
    premise_check = str(rejection.get("premise_check") or "")
    return (
        failure_code == _PROPOSAL_PREMISE_CONTRADICTED_CODE
        or premise_check == "contradicted"
        or failure_category == _LEGACY_PREMISE_CONTRADICTED
    )


def _rejection_termination_reason(
    rejection: Mapping[str, Any],
) -> AgenticTerminationReason:
    failure_category = str(_enum_value(rejection.get("failure_category")) or "")
    if _structured_rejection_is_premise_contradicted(rejection) or (
        failure_category == _AGENT_GROUNDING_FAILURE
    ):
        return AgenticTerminationReason.PREMISE_CONTRADICTED
    if failure_category == AgenticFailureCategory.DUPLICATE_MECHANISM.value:
        return AgenticTerminationReason.DUPLICATE_MECHANISM
    if str(rejection.get("source") or "") == "mechanism_novelty_gate":
        return AgenticTerminationReason.MECHANISM_NOVELTY_REJECTED
    return AgenticTerminationReason.MECHANISM_NOVELTY_REJECTED


def _terminal_failure_category(
    output: AgenticProposalOutput,
    state: AgenticProposalSessionState,
) -> AgenticFailureCategory | str | None:
    if output.status == AgenticProposalStatus.COMPLETED:
        return None
    if output.failure_category is not None:
        return output.failure_category
    if output.termination_reason in {
        AgenticTerminationReason.TOOL_LOOP_LIMIT,
        AgenticTerminationReason.SESSION_TIMEOUT,
        AgenticTerminationReason.REPEATED_TOOL_CALL,
    } or state.loop_stop_reason in {
        "tool_loop_limit",
        "observation_budget_exhausted",
        "session_timeout",
        "repeated_tool_call",
    }:
        return AgenticFailureCategory.TOOL_BUDGET_EXHAUSTED
    return None


def _hypothesis_prompt_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    context: ProposalToolContext | None,
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    for observation in observations:
        if observation.tool_name in _HYPOTHESIS_PROMPT_COMPACT_REQUIREMENT_TOOLS:
            if _observation_satisfies_compact_requirement(context, observation):
                selected.append(observation)
            continue
        selected.append(observation)
    return selected


def _next_prompt_manifest_index(state: AgenticProposalSessionState) -> int:
    current = int(getattr(state, "_prompt_manifest_index", 0)) + 1
    setattr(state, "_prompt_manifest_index", current)
    return current


def _deduplicate_observation_if_already_read(
    state: AgenticProposalSessionState,
    observation: ProposalObservation,
    *,
    tool_name: str,
    args: Mapping[str, Any],
    phase: AgenticProposalPhase,
    args_hash: str,
) -> ProposalObservation:
    if observation.is_error or not str(tool_name).startswith("context."):
        return observation
    payload_digest = stable_digest(observation.structured_payload, length=16)
    source_hash = _observation_source_hash(observation, payload_digest=payload_digest)
    key = (
        str(tool_name),
        str(args_hash),
        phase.value,
        str(source_hash or payload_digest),
    )
    cache = _already_read_cache(state)
    cached = cache.get(key)
    if cached is not None:
        return replace(
            observation,
            observation_type="already_read_ref",
            summary=(
                "Repeated proposal tool call returned an already-read reference "
                "instead of duplicating the full payload."
            ),
            structured_payload=_already_read_payload(
                observation,
                cached,
                args_hash=args_hash,
                phase=phase.value,
                payload_digest=payload_digest,
                source_hash=source_hash,
            ),
            repair_hint=None,
        )
    cache[key] = {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "tool_call_id": observation.tool_call_id,
        "args_hash": args_hash,
        "args_digest": stable_digest(dict(args), length=16),
        "phase": phase.value,
        "payload_digest": payload_digest,
        "source_hash": source_hash,
    }
    return observation


def _already_read_cache(state: AgenticProposalSessionState) -> dict[tuple[str, ...], Any]:
    cache = getattr(state, "_already_read_observation_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(state, "_already_read_observation_cache", cache)
    return cache


def _already_read_payload(
    observation: ProposalObservation,
    cached: Mapping[str, Any],
    *,
    args_hash: str,
    phase: str,
    payload_digest: str,
    source_hash: str,
) -> dict[str, Any]:
    payload = observation.structured_payload
    return _drop_empty_dict(
        {
            "already_read_ref": {
                "observation_id": cached.get("observation_id"),
                "tool_name": cached.get("tool_name"),
                "tool_call_id": cached.get("tool_call_id"),
                "args_hash": args_hash,
                "phase": phase,
                "payload_digest": payload_digest,
                "source_hash": source_hash,
            },
            "deduplicated": True,
            "tool_name": observation.tool_name,
            "surface": _already_read_surface_payload(payload),
            "detail": payload.get("detail") if isinstance(payload, Mapping) else None,
            "section": payload.get("section") if isinstance(payload, Mapping) else None,
            "target_file": (
                payload.get("target_file") if isinstance(payload, Mapping) else None
            ),
            "file_path": payload.get("file_path") if isinstance(payload, Mapping) else None,
            "symbol": payload.get("symbol") if isinstance(payload, Mapping) else None,
            "readable": payload.get("readable") if isinstance(payload, Mapping) else None,
            "source": payload.get("source") if isinstance(payload, Mapping) else None,
        }
    )


def _already_read_surface_payload(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return None
    surface = value.get("surface")
    if isinstance(surface, Mapping):
        return {
            key: surface.get(key)
            for key in ("name", "id", "kind")
            if surface.get(key) is not None
        }
    return surface


def _observation_source_hash(
    observation: ProposalObservation,
    *,
    payload_digest: str,
) -> str:
    source_payload = _observation_source_payload(observation.structured_payload)
    if source_payload:
        return stable_digest(source_payload, length=16)
    return payload_digest


def _observation_source_payload(value: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                if key_text in {"source_digest", "provenance"} and isinstance(
                    child, Mapping
                ):
                    found.setdefault(key_text, _sanitize_agentic_value(dict(child)))
                elif key_text in {
                    "source",
                    "digest",
                    "sha256",
                    "snapshot_digest",
                    "branch_id",
                    "base_champion_hash",
                    "champion_code_snapshot_hash",
                }:
                    found.setdefault(key_text, _sanitize_agentic_value(child))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found


def _required_context_tool_names(
    context: ProposalToolContext | None,
) -> tuple[str, ...]:
    del context
    return ("context.list_surfaces", "context.read_problem")


def _fallback_required_context_tool_names(
    context: ProposalToolContext | None,
) -> tuple[str, ...]:
    names = ["context.list_surfaces", "context.read_problem"]
    if _context_requires_solver_design_grounding(context):
        names.extend(_SOLVER_DESIGN_FILE_DISCOVERY_TOOLS)
        names.extend(_SOLVER_DESIGN_GROUNDING_TOOLS)
    return tuple(names)


def _context_requires_solver_design_grounding(
    context: ProposalToolContext | None,
) -> bool:
    if context is None:
        return False
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface in _SOLVER_DESIGN_SURFACE_NAMES:
        return True
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    return bool(boundary) and boundary.issubset(_SOLVER_DESIGN_SURFACE_NAMES)


def _is_solver_design_hypothesis(hypothesis: HypothesisProposal) -> bool:
    return str(hypothesis.change_locus or "").strip() in _SOLVER_DESIGN_SURFACE_NAMES


def _missing_solver_design_grounding_error(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    hypothesis: HypothesisProposal,
) -> str | None:
    if not _is_solver_design_hypothesis(hypothesis):
        return None
    observed_ok = {
        observation.tool_name
        for observation in observations
        if not observation.is_error
    }
    if _has_active_solver_embedded_call_graph(observations):
        observed_ok.add("context.read_solver_call_graph")
    missing = [
        tool_name
        for tool_name in _SOLVER_DESIGN_GROUNDING_TOOLS
        if tool_name not in observed_ok
    ]
    if not missing:
        return None
    return (
        "missing required solver_design grounding tools before hypothesis approval: "
        + ", ".join(missing)
    )


def _has_successful_solver_call_graph_grounding(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    return _has_successful_tool(
        observations,
        "context.read_solver_call_graph",
    ) or _has_active_solver_embedded_call_graph(observations)


def _has_active_solver_embedded_call_graph(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        call_graph = payload.get("call_graph")
        if not isinstance(call_graph, Mapping):
            continue
        if any(
            key in call_graph
            for key in (
                "edges",
                "edge_count",
                "nodes",
                "node_count",
                "source_digest",
                "provenance",
            )
        ):
            return True
    return False


def _patch_payload_for_preview(patch: PatchProposal) -> dict[str, Any]:
    payload = _proposal_payload(patch)
    for field_name in _PATCH_METADATA_FIELDS:
        payload.pop(field_name, None)
    return payload


def _patch_premise_rejection(
    patch: PatchProposal,
    hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    premise_check = str(getattr(patch, "premise_check", "supported") or "supported")
    if premise_check == "supported":
        return None
    if premise_check not in {"contradicted", "duplicate", "wrong_owner"}:
        premise_check = "contradicted"
    reason = str(getattr(patch, "premise_check_reason", "") or "").strip()
    category = (
        AgenticFailureCategory.DUPLICATE_MECHANISM.value
        if premise_check == "duplicate"
        else AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value
        if premise_check == "wrong_owner"
        else _AGENT_GROUNDING_FAILURE
    )
    rejection = {
        "artifact_kind": "agentic_code_premise_rejection",
        "premise_check": premise_check,
        "failure_category": category,
        "reason": reason,
        "selected_surface": hypothesis.change_locus,
        "target_file": hypothesis.target_file,
        "patch_generated": False,
        "screening_allowed": False,
    }
    if premise_check == "contradicted":
        rejection["legacy_failure_category"] = _LEGACY_PREMISE_CONTRADICTED
        rejection["failure_code"] = _PROPOSAL_PREMISE_CONTRADICTED_CODE
        rejection["agent_block_reason"] = _AGENT_QUALITY_BLOCKED_REASON
    return rejection


def _preview_failure_category(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> AgenticFailureCategory:
    for observation in reversed(observations):
        if not observation.is_error and _preview_observation_passed(observation):
            continue
        if observation.tool_name == "proposal.schema_preview":
            return AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE
        if observation.tool_name == "proposal.algorithm_smoke":
            return AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE
        if observation.tool_name == "proposal.contract_preview":
            if _contract_preview_indicates_patch_graph_failure(observation):
                return AgenticFailureCategory.PATCH_GRAPH_FAILURE
            return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
        if observation.tool_name == "proposal.target_permission_preview":
            return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
    return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE


def _contract_preview_indicates_patch_graph_failure(
    observation: ProposalObservation,
) -> bool:
    text_values = [
        str(value).strip().lower()
        for value in _preview_text_values(observation.structured_payload)
        if str(value).strip()
    ]
    text_values.extend(
        value
        for value in (
            str(observation.summary or "").strip().lower(),
            str(_enum_value(observation.failure_code) or "").strip().lower(),
        )
        if value
    )
    joined = "\n".join(text_values)
    if "import_graph" in joined or "import graph" in joined:
        return True
    return any(
        value.startswith("c8")
        or value.startswith("c9e")
        or ": c8" in value
        or ": c9e" in value
        for value in text_values
    )


def _preview_text_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for item in value.values():
            values.extend(_preview_text_values(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_preview_text_values(item))
    elif value is not None:
        values.append(str(value))
    return values


def _compact_active_solver_observation_for_budget(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.is_error or observation.tool_name not in {
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    if observation.tool_name == "context.read_active_solver_design":
        compact_payload = _compact_active_solver_design_payload(payload)
    elif observation.tool_name == "context.read_solver_call_graph":
        compact_payload = _compact_solver_call_graph_payload(payload)
    elif observation.tool_name == "context.list_algorithm_files":
        compact_payload = _compact_algorithm_file_list_payload(payload)
    else:
        compact_payload = _compact_algorithm_read_payload(payload)
    return replace(
        observation,
        summary=_limit_string(observation.summary, 220)
        or "Returned compact active solver evidence.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_active_solver_design_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    call_graph = payload.get("call_graph")
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "active_surface": payload.get("active_surface"),
            "provenance": payload.get("provenance"),
            "source_digest": _compact_source_digest(payload.get("source_digest")),
            "entrypoint": payload.get("entrypoint"),
            "active_files": _compact_algorithm_files(payload.get("active_files")),
            "inactive_files": _compact_algorithm_files(payload.get("inactive_files")),
            "call_graph": (
                _compact_solver_call_graph_payload(call_graph)
                if isinstance(call_graph, Mapping)
                else None
            ),
            "mechanism_summary": _compact_mechanism_summary(
                payload.get("mechanism_summary")
            ),
            "mechanism_keys": sorted(
                str(key) for key in (payload.get("mechanism_summary") or {}).keys()
            )
            if isinstance(payload.get("mechanism_summary"), Mapping)
            else None,
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_solver_call_graph_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    edges = payload.get("edges")
    nodes = payload.get("nodes")
    compact_edges: list[dict[str, Any]] = []
    if isinstance(edges, list):
        for edge in edges[:12]:
            if not isinstance(edge, Mapping):
                continue
            compact_edges.append(
                _drop_empty_dict(
                    {
                        "from": edge.get("from"),
                        "to": edge.get("to"),
                        "mechanism": _limit_string(edge.get("mechanism"), 260),
                        "evidence": _compact_string_list(edge.get("evidence"), 8, 120),
                    }
                )
            )
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "provenance": payload.get("provenance"),
            "source_digest": _compact_source_digest(payload.get("source_digest")),
            "node_count": len(nodes) if isinstance(nodes, list) else None,
            "edge_count": len(edges) if isinstance(edges, list) else None,
            "edges": compact_edges,
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_file_list_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "allowlist_only": payload.get("allowlist_only"),
            "file_count": payload.get("file_count"),
            "files": _compact_algorithm_files(payload.get("files")),
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_read_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "file_path": payload.get("file_path"),
            "symbol": payload.get("symbol"),
            "readable": payload.get("readable"),
            "reason": payload.get("reason"),
            "source": payload.get("source"),
            "active": payload.get("active"),
            "role": payload.get("role"),
            "module": payload.get("module"),
            "line_start": payload.get("line_start"),
            "line_end": payload.get("line_end"),
            "sha256": payload.get("sha256"),
            "digest": payload.get("digest"),
            "truncated": payload.get("truncated"),
            "provenance": payload.get("provenance"),
            "content_preview": _limit_string(payload.get("content_preview"), 1600),
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    files: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, Mapping):
            continue
        files.append(
            _drop_empty_dict(
                {
                    "file_path": item.get("file_path"),
                    "module": item.get("module"),
                    "role": item.get("role"),
                    "active": item.get("active"),
                    "readable": item.get("readable"),
                    "reason": item.get("reason"),
                    "source": item.get("source"),
                    "digest": item.get("digest"),
                }
            )
        )
    return files


def _compact_source_digest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    files = value.get("files")
    compact_files = {}
    if isinstance(files, Mapping):
        compact_files = {
            str(path): str(digest)[:16]
            for path, digest in list(files.items())[:12]
        }
    return _drop_empty_dict(
        {
            "algorithm": value.get("algorithm"),
            "snapshot_digest": value.get("snapshot_digest"),
            "files": compact_files,
        }
    )


def _compact_mechanism_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    summary: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(item, Mapping):
            continue
        summary[str(key)] = _drop_empty_dict(
            {
                "active": item.get("active"),
                "summary": _limit_string(item.get("summary"), 600),
                "evidence_symbols": _compact_string_list(
                    item.get("evidence_symbols"),
                    12,
                    140,
                ),
            }
        )
    return _drop_empty_dict(summary)


def _compact_string_list(value: Any, limit: int, max_chars: int) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in list(value)[: max(0, limit)]:
        text = _limit_string(item, max_chars)
        if text:
            result.append(text)
    return result


def _active_solver_mechanism_evidence_for_code_context(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> dict[str, Any]:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        mechanisms = _compact_mechanism_summary(payload.get("mechanism_summary"))
        if not mechanisms:
            continue
        source_digest = payload.get("source_digest")
        snapshot_digest = (
            source_digest.get("snapshot_digest")
            if isinstance(source_digest, Mapping)
            else None
        )
        return _drop_empty_dict(
            {
                "source": "context.read_active_solver_design",
                "snapshot_digest": snapshot_digest,
                "mechanism_summary": mechanisms,
                "premise_check_rule": (
                    "Before returning premise_check='supported', compare the "
                    "hypothesis against these active mechanisms. For "
                    "related/proximity destroy proposals, account for existing "
                    "_shaw_removal: seed-based removal using distance, demand, "
                    "and original-route relatedness."
                ),
            }
        )
    return {}


def _patch_self_reported_unresolved_issue(patch: PatchProposal) -> str | None:
    hint = str(patch.test_hint or "").strip()
    if not hint:
        return None
    normalized = re.sub(r"\s+", " ", hint).strip()
    lowered = normalized.lower()
    for pattern, label in _SELF_REPORTED_CODE_FAILURE_PATTERNS:
        if not pattern.search(lowered):
            continue
        if label == "syntax_error" and any(
            phrase in lowered for phrase in _SELF_REPORTED_SYNTAX_NEGATIONS
        ):
            continue
        excerpt = normalized
        if len(excerpt) > 360:
            excerpt = excerpt[:357].rstrip() + "..."
        return (
            "generated patch self-reported unresolved code issue "
            f"({label}) in test_hint: {excerpt}"
        )
    return None
