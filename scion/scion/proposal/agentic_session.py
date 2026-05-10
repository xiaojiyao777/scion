"""Bounded Agentic Proposal Session skeleton.

The session lives inside the tainted Creative Layer.  It may draft and persist
proposal-session artifacts, but it returns only the existing proposal shapes
that downstream Contract/Workspace/Verification services already understand.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from scion.core.models import Branch, ChampionState, HypothesisProposal, PatchProposal
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLMFormatError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)
from scion.proposal.tools import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalTaint,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolRegistry,
)

AGENTIC_SESSION_SCHEMA_VERSION = "agentic-proposal-session.v1"
_RAW_REF_MARKERS = (
    "raw_metrics_ref",
    "raw metrics",
    "raw_ref",
    "raw ref",
    "SECRET_RAW",
    "SECRET_VALIDATION",
    "SECRET_FROZEN",
    "SECRET_HOLDOUT",
)
_COMPACT_FEEDBACK_TOOLS = (
    "memory.query",
    "feedback.query_screening",
    "feedback.query_runtime",
)
_SINGLE_SUCCESS_OBSERVATION_TOOLS = (
    "context.list_surfaces",
    "context.read_problem",
    "memory.query",
)
_MIN_BUDGETED_OBSERVATION_CHARS = 512
_OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS = 3000
_APS_SURFACE_READ_CODE_CHARS = 1200


class AgenticProposalStatus(str, Enum):
    """Terminal status for one bounded proposal session."""

    COMPLETED = "completed"
    PARTIAL_HYPOTHESIS_ONLY = "partial_hypothesis_only"
    PARTIAL_PATCH_UNCHECKED = "partial_patch_unchecked"
    FAILED = "failed"


class AgenticTerminationReason(str, Enum):
    """Typed reason for session termination."""

    COMPLETED = "completed"
    ANCHOR_VALIDATION_FAILED = "anchor_validation_failed"
    HYPOTHESIS_AWAITING_APPROVAL = "hypothesis_awaiting_approval"
    HYPOTHESIS_APPROVAL_FAILED = "hypothesis_approval_failed"
    HYPOTHESIS_GENERATION_FAILED = "hypothesis_generation_failed"
    CODE_GENERATION_FAILED = "code_generation_failed"
    INJECTED_OUTPUT = "injected_output"
    TOOL_LOOP_LIMIT = "tool_loop_limit"
    SESSION_TIMEOUT = "session_timeout"
    REPEATED_TOOL_CALL = "repeated_tool_call"
    UNHANDLED_ERROR = "unhandled_error"


class AgenticProposalPhase(str, Enum):
    """Minimal APS-1 phase labels."""

    ORIENT = "orient"
    DIAGNOSE = "diagnose"
    CHOOSE_SURFACE = "choose_surface"
    DRAFT_HYPOTHESIS = "draft_hypothesis"
    INSPECT_INTERFACE = "inspect_interface"
    DRAFT_PATCH = "draft_patch"
    SELF_CHECK = "self_check"
    FINALIZE = "finalize"


@dataclass(frozen=True)
class AgenticToolLoopConfig:
    """Deterministic limits for one proposal-session tool loop."""

    max_steps: int = 12
    max_tool_calls: int = 9
    max_observation_chars: int = 48000
    max_wall_time_sec: float = 120.0
    max_repeated_tool_calls: int = 2


@dataclass(frozen=True)
class AgenticEvidenceRef:
    observation_id: str
    exposure_level: str
    summary: str


@dataclass(frozen=True)
class AgenticSelfCheck:
    schema_valid: bool = False
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgenticTranscriptEvent:
    phase: str
    message: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class AgenticProposalSessionState:
    session_id: str
    campaign_id: str
    branch_id: str
    request_id: str = ""
    idempotency_key: str = ""
    phase: AgenticProposalPhase = AgenticProposalPhase.ORIENT
    status: AgenticProposalStatus | None = None
    transcript: list[AgenticTranscriptEvent] = field(default_factory=list)
    scratch_artifact_refs: list[str] = field(default_factory=list)
    tool_step_count: int = 0
    tool_call_count: int = 0
    observation_chars_used: int = 0
    loop_stop_reason: str | None = None
    tool_loop_config: Mapping[str, Any] = field(default_factory=dict)
    wall_time_started_at: float = field(default_factory=time.monotonic)
    tool_call_fuse_counts: dict[str, int] = field(default_factory=dict)

    def note(
        self,
        phase: AgenticProposalPhase,
        message: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.phase = phase
        self.transcript.append(
            AgenticTranscriptEvent(
                phase=phase.value,
                message=message,
                metadata=dict(metadata or {}),
            )
        )


@dataclass(frozen=True)
class AgenticProposalOutput:
    status: AgenticProposalStatus
    session_id: str
    campaign_id: str
    branch_id: str
    schema_version: str = AGENTIC_SESSION_SCHEMA_VERSION
    request_id: str = ""
    idempotency_key: str = ""
    champion_version: int | None = None
    champion_weight_revision: int | None = None
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    selected_surface: str | None = None
    action: str | None = None
    hypothesis: HypothesisProposal | None = None
    patch: PatchProposal | None = None
    rationale_summary: str = ""
    evidence_used: tuple[AgenticEvidenceRef, ...] = ()
    transcript: tuple[AgenticTranscriptEvent, ...] = ()
    rejected_alternatives: tuple[str, ...] = ()
    self_check: AgenticSelfCheck = field(default_factory=AgenticSelfCheck)
    tainted_artifact_refs: tuple[str, ...] = ()
    termination_reason: AgenticTerminationReason = (
        AgenticTerminationReason.UNHANDLED_ERROR
    )
    tool_loop_config: Mapping[str, int] = field(default_factory=dict)
    tool_budget_used: Mapping[str, int] = field(default_factory=dict)
    transcript_digest: str = ""
    failure_detail: str | None = None

    @property
    def is_completed(self) -> bool:
        return (
            self.status == AgenticProposalStatus.COMPLETED
            and self.hypothesis is not None
            and self.patch is not None
        )


@dataclass(frozen=True)
class AgenticProposalRequest:
    campaign_id: str
    branch: Branch
    champion: ChampionState | None
    hypothesis_context: Mapping[str, Any] | None
    build_code_context: Callable[[HypothesisProposal], Mapping[str, Any]]
    approve_hypothesis: Callable[[HypothesisProposal], Any] | None = None
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    prior_failure: str | None = None
    approved_hypothesis: HypothesisProposal | None = None
    tool_context: ProposalToolContext | None = None
    resume_context: Mapping[str, Any] | None = None


class CreativeProposalLike(Protocol):
    def generate_hypothesis(self, context: Mapping[str, Any]) -> HypothesisProposal:
        ...

    def generate_code(self, context: Mapping[str, Any]) -> PatchProposal:
        ...


class AgenticSessionArtifactStore(Protocol):
    def write_transcript(self, state: AgenticProposalSessionState) -> str:
        ...

    def write_output(self, output: AgenticProposalOutput) -> str:
        ...

    def write_scratch(
        self,
        session_id: str,
        name: str,
        payload: Mapping[str, Any],
    ) -> str:
        ...


@dataclass(frozen=True)
class AgenticSessionIndexEntry:
    schema_version: str
    session_id: str
    request_id: str
    idempotency_key: str
    artifact_ref: str
    artifact_path: str
    transcript_digest: str
    termination_reason: str
    status: str
    created_at: str
    updated_at: str
    tainted: bool
    tool_loop_config: Mapping[str, Any] = field(default_factory=dict)
    tool_budget_used: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgenticStoredSession:
    entry: AgenticSessionIndexEntry
    artifact: Mapping[str, Any] | None
    validation: AgenticReplayValidationResult


class AgenticSessionStore:
    """File-backed, ops-safe index for persisted APS output artifacts."""

    _INDEX_NAME = "agentic_session_index.json"

    def __init__(self, artifact_dir: str | Path) -> None:
        self._root = Path(artifact_dir).resolve()
        self._index_path = self._root / self._INDEX_NAME

    @property
    def index_path(self) -> Path:
        return self._index_path

    def record_output(
        self,
        output: AgenticProposalOutput,
        artifact_ref: str | Path,
    ) -> AgenticSessionIndexEntry:
        artifact_path = Path(artifact_ref).resolve()
        self._ensure_inside_root(artifact_path)
        now = datetime.now().isoformat()
        entries = self._read_entries()
        existing_created_at = None
        kept: list[AgenticSessionIndexEntry] = []
        for entry in entries:
            if entry.session_id == output.session_id:
                existing_created_at = entry.created_at
                continue
            kept.append(entry)
        entry = AgenticSessionIndexEntry(
            schema_version=output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
            session_id=output.session_id,
            request_id=output.request_id or output.session_id,
            idempotency_key=output.idempotency_key,
            artifact_ref=str(artifact_path),
            artifact_path=str(artifact_path),
            transcript_digest=output.transcript_digest,
            termination_reason=str(_enum_value(output.termination_reason)),
            status=str(_enum_value(output.status)),
            created_at=existing_created_at or now,
            updated_at=now,
            tainted=True,
            tool_loop_config=dict(output.tool_loop_config),
            tool_budget_used=dict(output.tool_budget_used),
        )
        kept.append(entry)
        self._write_entries(kept)
        return entry

    def load_by_session_id(self, session_id: str) -> AgenticStoredSession | None:
        matches = [entry for entry in self._read_entries() if entry.session_id == session_id]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def find_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AgenticStoredSession | None:
        matches = [
            entry
            for entry in self._read_entries()
            if entry.idempotency_key == idempotency_key
        ]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def latest_for_request(self, request_id: str) -> AgenticStoredSession | None:
        matches = [entry for entry in self._read_entries() if entry.request_id == request_id]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def list_sessions(self) -> list[AgenticStoredSession]:
        return [
            self._load_stored_session(entry)
            for entry in sorted(
                self._read_entries(),
                key=lambda entry: (entry.updated_at, entry.created_at, entry.session_id),
            )
        ]

    def _load_stored_session(
        self,
        entry: AgenticSessionIndexEntry,
    ) -> AgenticStoredSession:
        artifact: Mapping[str, Any] | None = None
        try:
            artifact_path = Path(entry.artifact_path).resolve()
            self._ensure_inside_root(artifact_path)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            validation = validate_agentic_session_artifact(artifact)
        except Exception as exc:
            validation = AgenticReplayValidationResult(
                ok=False,
                errors=(f"artifact load failed: {exc}",),
            )
        return AgenticStoredSession(entry=entry, artifact=artifact, validation=validation)

    def _read_entries(self) -> list[AgenticSessionIndexEntry]:
        if not self._index_path.exists():
            return []
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        entries: list[AgenticSessionIndexEntry] = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            try:
                entries.append(
                    AgenticSessionIndexEntry(
                        schema_version=str(item.get("schema_version") or ""),
                        session_id=str(item.get("session_id") or ""),
                        request_id=str(item.get("request_id") or ""),
                        idempotency_key=str(item.get("idempotency_key") or ""),
                        artifact_ref=str(item.get("artifact_ref") or item.get("artifact_path") or ""),
                        artifact_path=str(item.get("artifact_path") or item.get("artifact_ref") or ""),
                        transcript_digest=str(item.get("transcript_digest") or ""),
                        termination_reason=str(item.get("termination_reason") or ""),
                        status=str(item.get("status") or ""),
                        created_at=str(item.get("created_at") or ""),
                        updated_at=str(item.get("updated_at") or ""),
                        tainted=bool(item.get("tainted", True)),
                        tool_loop_config=dict(item.get("tool_loop_config") or {}),
                        tool_budget_used=dict(item.get("tool_budget_used") or {}),
                    )
                )
            except Exception:
                continue
        return [
            entry
            for entry in entries
            if entry.session_id and entry.artifact_path and entry.idempotency_key
        ]

    def _write_entries(self, entries: list[AgenticSessionIndexEntry]) -> None:
        payload = [_json_ready(entry) for entry in entries]
        self._root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self._index_path, payload)

    def _ensure_inside_root(self, path: Path) -> None:
        if path != self._root and self._root not in path.parents:
            raise ValueError("agentic session artifact path escapes index root")

    @staticmethod
    def _latest_entry(
        entries: list[AgenticSessionIndexEntry],
    ) -> AgenticSessionIndexEntry:
        return max(
            entries,
            key=lambda entry: (entry.updated_at, entry.created_at, entry.session_id),
        )


class FileAgenticSessionArtifactStore:
    """Persist tainted session artifacts below one allowed directory."""

    _SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")

    def __init__(self, artifact_dir: str | Path) -> None:
        self._root = Path(artifact_dir).resolve()
        self.session_store = AgenticSessionStore(self._root)

    def write_transcript(self, state: AgenticProposalSessionState) -> str:
        path = self._session_dir(state.session_id) / "transcript.json"
        return self._write_json(path, _agentic_transcript_artifact(state))

    def write_output(self, output: AgenticProposalOutput) -> str:
        path = self._session_dir(output.session_id) / "output.json"
        ref = self._write_json(path, _agentic_output_artifact(output))
        self.session_store.record_output(output, ref)
        return ref

    def write_scratch(
        self,
        session_id: str,
        name: str,
        payload: Mapping[str, Any],
    ) -> str:
        safe_name = self._safe_segment(name)
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"
        path = self._session_dir(session_id) / "scratch" / safe_name
        return self._write_json(path, _json_ready(dict(payload)))

    def _session_dir(self, session_id: str) -> Path:
        safe_id = self._safe_segment(session_id)
        path = (self._root / safe_id).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError("session artifact path escapes allowed artifact dir")
        return path

    def _write_json(self, path: Path, payload: Any) -> str:
        resolved = path.resolve()
        if resolved != self._root and self._root not in resolved.parents:
            raise ValueError("session artifact path escapes allowed artifact dir")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(resolved, payload)
        return str(resolved)

    def _safe_segment(self, value: str) -> str:
        if not value or "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError(f"unsafe session artifact path segment: {value!r}")
        if not self._SAFE_SEGMENT.match(value):
            raise ValueError(f"unsafe session artifact path segment: {value!r}")
        return value


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
        injected_output: AgenticProposalOutput
        | Callable[[AgenticProposalRequest], AgenticProposalOutput]
        | None = None,
    ) -> None:
        self._creative = creative
        self._artifact_store = artifact_store
        self.tool_registry = tool_registry
        self._tool_loop_config = tool_loop_config or AgenticToolLoopConfig()
        self._injected_output = injected_output

    def idempotency_key_for_request(self, request: AgenticProposalRequest) -> str:
        return compute_agentic_idempotency_key(request, self._tool_loop_config)

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
        state.note(AgenticProposalPhase.ORIENT, "Loaded exposure-controlled proposal context.")
        state.note(AgenticProposalPhase.DIAGNOSE, "Prepared deterministic APS-1 proposal path.")
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
                    observations
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
            state.note(AgenticProposalPhase.FINALIZE, "Session failed before proposal generation.")
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
            state.note(AgenticProposalPhase.CHOOSE_SURFACE, "Delegating hypothesis generation.")
            state.note(AgenticProposalPhase.DRAFT_HYPOTHESIS, "Generating hypothesis proposal.")
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
                    hypothesis_context["agentic_tool_observations"] = [
                        _observation_prompt_payload(observation)
                        for observation in observations
                    ]
                hypothesis = self._creative.generate_hypothesis(
                    hypothesis_context
                )
            except self._SESSION_ERROR_TYPES as exc:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=str(exc),
                    evidence_used=tuple(evidence),
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
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Hypothesis generation violated the forced research-surface constraint.",
                    metadata={"detail": forced_violation},
                )
                return self._persist(output, state)

            if tool_context is not None:
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

            if request.approve_hypothesis is None:
                output = self._partial_hypothesis_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail="hypothesis awaits ContractGate approval",
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
                    evidence_used=tuple(evidence),
                    self_check=_self_check_from_previews(observations),
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
                    self_check=_self_check_from_previews(observations),
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
                    self_check=_self_check_from_previews(observations),
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
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Approved hypothesis violated the forced research-surface constraint.",
                    metadata={"detail": forced_violation},
                )
                return self._persist(output, state)
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
            if observations:
                code_context["agentic_tool_observations"] = [
                    _observation_prompt_payload(observation)
                    for observation in observations
                ]
            state.note(AgenticProposalPhase.DRAFT_PATCH, "Generating patch proposal.")
            patch = self._creative.generate_code(code_context)
        except self._SESSION_ERROR_TYPES as exc:
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=str(exc),
                evidence_used=tuple(evidence),
                self_check=_self_check_from_previews(observations),
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

        if tool_context is not None:
            patch_preview = self._run_contract_preview_tool(
                tool_context,
                hypothesis,
                patch,
                state,
            )
            observations.append(patch_preview)
            evidence.extend(_evidence_from_observations((patch_preview,)))

        state.note(AgenticProposalPhase.SELF_CHECK, "Recorded APS-1 schema self-check.")
        output = self._completed_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            patch=patch,
            evidence_used=tuple(evidence),
            self_check=_self_check_from_previews(observations),
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

    def _run_hypothesis_observation_tools(
        self,
        context: ProposalToolContext,
        state: AgenticProposalSessionState,
        *,
        selection_source: str = "fallback_selected",
        skip_successful_required_tools: set[str] | None = None,
    ) -> list[ProposalObservation]:
        calls: tuple[tuple[str, Mapping[str, Any]], ...] = (
            ("context.list_surfaces", {}),
            ("context.read_problem", {}),
            ("memory.query", {}),
            (
                "feedback.query_screening",
                _feedback_query_args(context),
            ),
            (
                "feedback.query_runtime",
                _feedback_query_args(context),
            ),
        )
        skip_successful_required_tools = skip_successful_required_tools or set()
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
                "error_count": sum(1 for observation in observations if observation.is_error),
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
            planner_context = {
                "session_id": state.session_id,
                "phase": state.phase.value,
                "allowed_tools": self.tool_registry.allowed_tools(context)
                if self.tool_registry is not None
                else (),
                "allowed_tool_specs": self.tool_registry.allowed_tool_specs(context)
                if self.tool_registry is not None
                else (),
                "tool_arg_guidance": self._tool_arg_guidance(context, observations),
                "hypothesis_constraints": self._hypothesis_constraints(context),
                "remaining_steps": max(
                    0, self._tool_loop_config.max_steps - state.tool_step_count
                ),
                "remaining_tool_calls": max(
                    0, self._tool_loop_config.max_tool_calls - state.tool_call_count
                ),
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
        required_error = self._missing_required_context_error(observations)
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
            tool_name for tool_name in available_feedback if tool_name not in observed_ok
        ]
        if missing_feedback:
            return (
                "missing compact proposal feedback tools: "
                + ", ".join(missing_feedback)
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
        if (
            "memory.query" in allowed
            and (context.search_memory is not None or context.research_log is not None)
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
                    "max_code_chars": 1200,
                },
                "full_detail_rule": (
                    "request detail='full' only for explicit debugging after "
                    "compact reads are insufficient"
                ),
            }
        }
        if forced_constraint:
            forced_surface = forced_constraint.get("forced_surface")
            guidance["context.read_surface"]["forced_surface_rule"] = (
                "A forced research-surface diagnostic is active. Read and "
                "draft only the forced surface."
            )
            guidance["context.read_surface"]["allowed_surface_ids"] = [forced_surface]
            guidance["proposal.draft_hypothesis"] = forced_constraint
            guidance["proposal.schema_preview"] = forced_constraint
            guidance["proposal.target_permission_preview"] = forced_constraint
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
        return guidance

    def _hypothesis_constraints(
        self,
        context: ProposalToolContext | None,
    ) -> dict[str, Any]:
        if context is None or not context.forced_surface:
            return {}
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
            if self._tool_loop_limit_reached(state):
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
            "max_code_chars": 1200,
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
        if self._tool_loop_limit_reached(state):
            stop_reason = self._current_loop_stop_reason(state)
            self._record_loop_stop(state, stop_reason)
            return ProposalObservation(
                observation_id=str(uuid.uuid4()),
                session_id=context.session_id,
                tool_name="proposal.contract_preview",
                tool_call_id="",
                observation_type="tool_skipped",
                summary=(
                    "Contract preview skipped because the session wall-time limit was reached."
                    if stop_reason == "session_timeout"
                    else "Contract preview skipped because the tool loop limit was reached."
                ),
                structured_payload={},
                is_error=True,
                failure_code=ProposalToolFailureCode.UNSUPPORTED,
            )
        return self._call_tool(
            context,
            state,
            AgenticProposalPhase.SELF_CHECK,
            "proposal.contract_preview",
            {
                "hypothesis": _proposal_payload(hypothesis),
                "patch": _proposal_payload(patch),
            },
            selection_source="fallback_selected",
        )

    def _call_tool(
        self,
        context: ProposalToolContext,
        state: AgenticProposalSessionState,
        phase: AgenticProposalPhase,
        name: str,
        args: Mapping[str, Any],
        *,
        selection_source: str = "fallback_selected",
    ) -> ProposalObservation:
        assert self.tool_registry is not None
        args = self._budgeted_tool_args(name, args, selection_source=selection_source)
        if self._session_timeout_reached(state):
            self._record_loop_stop(state, "session_timeout", error_code="session_timeout")
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
            observation = self.tool_registry.call(
                name,
                args,
                context,
                tool_call_id=step_id,
            )
        observation = self._enforce_observation_budget(context, state, observation)
        prompt_payload_chars = _json_size(_observation_prompt_payload(observation))
        remaining = self._remaining_observation_chars(state)
        if prompt_payload_chars > remaining:
            observation = self._fit_observation_to_remaining(
                observation,
                remaining_chars=remaining,
            )
            prompt_payload_chars = _json_size(_observation_prompt_payload(observation))
        state.observation_chars_used += prompt_payload_chars
        if state.observation_chars_used > self._tool_loop_config.max_observation_chars:
            state.observation_chars_used = self._tool_loop_config.max_observation_chars
        if self._observation_budget_exhausted(state):
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

    def _tool_loop_limit_reached(self, state: AgenticProposalSessionState) -> bool:
        return (
            state.tool_step_count >= self._tool_loop_config.max_steps
            or state.tool_call_count >= self._tool_loop_config.max_tool_calls
            or self._observation_budget_exhausted(state)
            or self._session_timeout_reached(state)
        )

    def _remaining_observation_chars(
        self,
        state: AgenticProposalSessionState,
    ) -> int:
        return max(
            0,
            int(self._tool_loop_config.max_observation_chars)
            - int(state.observation_chars_used),
        )

    def _observation_budget_exhausted(
        self,
        state: AgenticProposalSessionState,
    ) -> bool:
        remaining = self._remaining_observation_chars(state)
        if remaining <= 0:
            return True
        return remaining < self._minimum_budgeted_observation_chars()

    def _minimum_budgeted_observation_chars(self) -> int:
        return _MIN_BUDGETED_OBSERVATION_CHARS

    def _optional_surface_read_budget_floor(self) -> int:
        return max(
            self._minimum_budgeted_observation_chars(),
            min(
                _OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS,
                max(0, int(self._tool_loop_config.max_observation_chars) // 8),
            ),
        )

    def _should_deny_optional_tool_for_budget(
        self,
        name: str,
        *,
        selection_source: str,
        state: AgenticProposalSessionState,
    ) -> bool:
        if name != "context.read_surface":
            return False
        if selection_source == "selected_surface_required":
            return False
        return (
            self._remaining_observation_chars(state)
            < self._optional_surface_read_budget_floor()
        )

    def _budgeted_tool_args(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        selection_source: str,
    ) -> Mapping[str, Any]:
        if name != "context.read_surface":
            return args
        budgeted = dict(args)
        if budgeted.get("detail") != "compact":
            budgeted["detail"] = "compact"
        max_code_chars = budgeted.get("max_code_chars")
        if max_code_chars is None:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
            return budgeted
        try:
            requested = int(max_code_chars)
        except Exception:
            return budgeted
        if requested > _APS_SURFACE_READ_CODE_CHARS:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
        elif selection_source == "selected_surface_required" and requested < 0:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
        return budgeted

    def _session_timeout_reached(self, state: AgenticProposalSessionState) -> bool:
        return (
            time.monotonic() - state.wall_time_started_at
            >= self._tool_loop_config.max_wall_time_sec
        )

    def _current_loop_stop_reason(self, state: AgenticProposalSessionState) -> str:
        if self._session_timeout_reached(state):
            return "session_timeout"
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
    ) -> ProposalObservation:
        projected = _json_size(_observation_prompt_payload(observation))
        remaining = self._remaining_observation_chars(state)
        if projected <= remaining:
            return observation
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
            repair_hint="Request fewer or smaller observations.",
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
        repair_hint: str | None = None,
    ) -> ProposalObservation:
        payload = {
            "budget_action": budget_action,
            "max_observation_chars": self._tool_loop_config.max_observation_chars,
            "observation_chars_used": state.observation_chars_used,
            "remaining_observation_chars": self._remaining_observation_chars(state),
        }
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
            taint=source_observation.taint
            if source_observation is not None
            else ProposalTaint.PROPOSAL,
            exposure_level=source_observation.exposure_level
            if source_observation is not None
            else ProposalExposureLevel.PUBLIC_SPEC,
            is_error=True,
            failure_code=ProposalToolFailureCode.RESULT_TOO_LARGE,
            repair_hint=repair_hint,
        )
        return self._fit_observation_to_remaining(
            observation,
            remaining_chars=self._remaining_observation_chars(state),
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
    ) -> str | None:
        observed_ok = {
            observation.tool_name
            for observation in observations
            if not observation.is_error
        }
        missing = [
            name
            for name in ("context.list_surfaces", "context.read_problem")
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
        )
        state.idempotency_key = output.idempotency_key or state.idempotency_key
        if self._artifact_store is None:
            return output
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


@dataclass(frozen=True)
class AgenticReplayValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()


def validate_agentic_session_artifact(
    artifact: str | Path | Mapping[str, Any],
) -> AgenticReplayValidationResult:
    """Lightweight replay/audit validation for a persisted APS artifact.

    This does not execute tools or LLM calls. It only checks that the persisted
    artifact is a supported compact APS envelope with bounded, monotonic tool
    transcript metadata and no raw-reference markers.
    """
    payload = _load_artifact_payload(artifact)
    errors: list[str] = []
    if payload.get("schema_version") != AGENTIC_SESSION_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    for field_name in (
        "schema_version",
        "session_id",
        "request_id",
        "idempotency_key",
        "termination_reason",
        "tool_loop_config",
        "tool_budget_used",
        "transcript_digest",
    ):
        if field_name not in payload:
            errors.append(f"missing required field: {field_name}")

    compact_transcript = payload.get("compact_transcript")
    if compact_transcript is None:
        compact_transcript = payload.get("transcript", [])
    if not isinstance(compact_transcript, list):
        errors.append("transcript must be a list")
        compact_transcript = []

    step_numbers: list[int] = []
    seen_steps: set[str] = set()
    for event in compact_transcript:
        if not isinstance(event, Mapping):
            errors.append("transcript event must be an object")
            continue
        metadata = event.get("metadata", {})
        if not isinstance(metadata, Mapping):
            errors.append("transcript event metadata must be an object")
            continue
        step_id = metadata.get("step_id")
        if step_id is None:
            continue
        step_text = str(step_id)
        if step_text in seen_steps:
            errors.append(f"duplicate step_id: {step_text}")
        seen_steps.add(step_text)
        match = re.fullmatch(r"tool-(\d+)", step_text)
        if match is None:
            errors.append(f"invalid step_id: {step_text}")
            continue
        step_numbers.append(int(match.group(1)))
    if step_numbers != sorted(step_numbers):
        errors.append("transcript step_id values are not monotonic")

    config = payload.get("tool_loop_config", {})
    used = payload.get("tool_budget_used", {})
    if isinstance(config, Mapping) and isinstance(used, Mapping):
        for used_key, config_key in (
            ("tool_steps", "max_steps"),
            ("tool_calls", "max_tool_calls"),
            ("observation_chars", "max_observation_chars"),
        ):
            try:
                used_value = int(used.get(used_key, 0))
                max_value = int(config.get(config_key, 0))
            except Exception:
                errors.append(f"invalid tool budget field: {used_key}")
                continue
            if max_value >= 0 and used_value > max_value:
                errors.append(f"tool budget exceeded: {used_key}")
    else:
        errors.append("tool_loop_config and tool_budget_used must be objects")

    rendered = json.dumps(_json_ready(payload), sort_keys=True, default=str)
    marker = _find_raw_ref_marker(rendered)
    if marker is not None:
        errors.append(f"raw ref marker found: {marker}")

    expected_digest = payload.get("transcript_digest")
    if expected_digest and isinstance(compact_transcript, list):
        actual_digest = _transcript_digest(compact_transcript)
        if expected_digest != actual_digest:
            errors.append("transcript_digest mismatch")

    return AgenticReplayValidationResult(ok=not errors, errors=tuple(errors))


def inspect_agentic_session_artifact(
    artifact: str | Path | Mapping[str, Any],
) -> dict[str, Any]:
    """Return a compact ops-safe APS artifact summary."""
    payload = _load_artifact_payload(artifact)
    validation = validate_agentic_session_artifact(payload)
    return {
        "schema_version": payload.get("schema_version"),
        "session_id": payload.get("session_id"),
        "request_id": payload.get("request_id"),
        "termination_reason": payload.get("termination_reason"),
        "status": payload.get("status"),
        "tool_loop_config": payload.get("tool_loop_config", {}),
        "tool_budget_used": payload.get("tool_budget_used", {}),
        "transcript_digest": payload.get("transcript_digest"),
        "validation": {
            "ok": validation.ok,
            "errors": list(validation.errors),
        },
    }


def resume_from_artifact(
    artifact: str | Path | Mapping[str, Any],
    *,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """Build sanitized compact APS context for a follow-up session prompt."""
    payload = _load_artifact_payload(artifact)
    validation = validate_agentic_session_artifact(payload)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))
    compact_transcript = payload.get("compact_transcript")
    if compact_transcript is None:
        compact_transcript = payload.get("transcript", [])
    tool_steps = []
    for event in compact_transcript:
        metadata = event.get("metadata", {}) if isinstance(event, Mapping) else {}
        if not isinstance(metadata, Mapping) or not metadata.get("tool_name"):
            continue
        tool_steps.append(
            {
                "tool_name": metadata.get("tool_name"),
                "status": metadata.get("status"),
                "error_code": metadata.get("error_code"),
                "evidence_ref": metadata.get("evidence_ref"),
                "result_summary": _sanitize_agentic_value(
                    metadata.get("result_summary") or ""
                ),
            }
        )
    context = {
        "schema_version": payload.get("schema_version"),
        "session_id": payload.get("session_id"),
        "request_id": payload.get("request_id"),
        "termination_reason": payload.get("termination_reason"),
        "transcript_digest": payload.get("transcript_digest"),
        "tool_budget_used": payload.get("tool_budget_used", {}),
        "tool_steps": tool_steps,
    }
    summary = json.dumps(context, sort_keys=True, default=str)
    if len(summary) > max_chars:
        allowed_steps: list[dict[str, Any]] = []
        for step in tool_steps:
            candidate = dict(context, tool_steps=[*allowed_steps, step])
            if len(json.dumps(candidate, sort_keys=True, default=str)) > max_chars:
                break
            allowed_steps.append(step)
        context["tool_steps"] = allowed_steps
        summary = json.dumps(context, sort_keys=True, default=str)
        if len(summary) > max_chars:
            context["tool_steps"] = []
            summary = json.dumps(context, sort_keys=True, default=str)
            if len(summary) > max_chars:
                summary = summary[: max(0, max_chars - 3)] + "..."
    context["summary"] = summary
    return context


def ensure_agentic_output_audit_metadata(
    output: AgenticProposalOutput,
) -> AgenticProposalOutput:
    compact_transcript = _compact_transcript(tuple(output.transcript))
    return replace(
        output,
        schema_version=output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
        request_id=output.request_id or output.session_id,
        idempotency_key=output.idempotency_key,
        transcript_digest=output.transcript_digest
        or _transcript_digest(compact_transcript),
    )


def _champion_version(champion: ChampionState | None) -> int | None:
    return champion.version if champion is not None else None


def _champion_weight_revision(champion: ChampionState | None) -> int | None:
    return getattr(champion, "weight_revision", None) if champion is not None else None


def _tool_loop_config_payload(config: AgenticToolLoopConfig) -> dict[str, Any]:
    return {
        "max_steps": int(config.max_steps),
        "max_tool_calls": int(config.max_tool_calls),
        "max_observation_chars": int(config.max_observation_chars),
        "max_wall_time_sec": float(config.max_wall_time_sec),
        "max_repeated_tool_calls": int(config.max_repeated_tool_calls),
    }


def _tool_budget_used_payload(state: AgenticProposalSessionState) -> dict[str, int]:
    return {
        "tool_steps": int(state.tool_step_count),
        "tool_calls": int(state.tool_call_count),
        "observation_chars": int(state.observation_chars_used),
    }


def _compact_transcript(
    transcript: tuple[AgenticTranscriptEvent, ...] | list[AgenticTranscriptEvent],
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    allowed_metadata = {
        "step_id",
        "tool_name",
        "status",
        "error_code",
        "evidence_ref",
        "result_summary",
        "selection_source",
        "fallback",
        "skip_reason",
        "stop_reason",
        "tool_steps",
        "tool_calls",
        "observation_chars_used",
    }
    for event in transcript:
        metadata = {
            key: _sanitize_agentic_value(value)
            for key, value in dict(event.metadata).items()
            if key in allowed_metadata
        }
        compact.append(
            {
                "phase": event.phase,
                "created_at": event.created_at,
                "message": _sanitize_agentic_value(event.message),
                "metadata": metadata,
            }
        )
    return compact


def _transcript_digest(compact_transcript: Any) -> str:
    rendered = json.dumps(
        _json_ready(compact_transcript),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _agentic_transcript_artifact(
    state: AgenticProposalSessionState,
) -> dict[str, Any]:
    compact_transcript = _compact_transcript(tuple(state.transcript))
    return {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "artifact_kind": "agentic_proposal_transcript",
        "session_id": state.session_id,
        "request_id": state.request_id or state.session_id,
        "idempotency_key": state.idempotency_key,
        "campaign_id": state.campaign_id,
        "branch_id": state.branch_id,
        "phase": state.phase.value,
        "status": _enum_value(state.status),
        "termination_reason": state.loop_stop_reason,
        "tool_loop_config": dict(state.tool_loop_config),
        "tool_budget_used": _tool_budget_used_payload(state),
        "transcript_digest": _transcript_digest(compact_transcript),
        "compact_transcript": compact_transcript,
        "tainted": True,
    }


def _agentic_output_artifact(output: AgenticProposalOutput) -> dict[str, Any]:
    compact_transcript = _compact_transcript(tuple(output.transcript))
    transcript_digest = output.transcript_digest or _transcript_digest(
        compact_transcript
    )
    artifact = {
        "schema_version": output.schema_version or AGENTIC_SESSION_SCHEMA_VERSION,
        "artifact_kind": "agentic_proposal_output",
        "session_id": output.session_id,
        "request_id": output.request_id or output.session_id,
        "idempotency_key": output.idempotency_key,
        "campaign_id": output.campaign_id,
        "branch_id": output.branch_id,
        "status": _enum_value(output.status),
        "termination_reason": _enum_value(output.termination_reason),
        "tool_loop_config": dict(output.tool_loop_config),
        "tool_budget_used": dict(output.tool_budget_used),
        "transcript_digest": transcript_digest,
        "selected_surface": output.selected_surface,
        "action": output.action,
        "problem_id": output.problem_id,
        "problem_spec_hash": output.problem_spec_hash,
        "champion_version": output.champion_version,
        "champion_weight_revision": output.champion_weight_revision,
        "hypothesis": _proposal_payload(output.hypothesis)
        if output.hypothesis is not None
        else None,
        "patch": _patch_artifact_payload(output.patch)
        if output.patch is not None
        else None,
        "evidence_used": [
            {
                "observation_id": evidence.observation_id,
                "exposure_level": evidence.exposure_level,
                "summary": _sanitize_agentic_value(evidence.summary),
            }
            for evidence in output.evidence_used
        ],
        "self_check": _json_ready(output.self_check),
        "compact_transcript": compact_transcript,
        "failure_detail": _sanitize_agentic_value(output.failure_detail),
        "tainted": True,
    }
    return _json_ready(_sanitize_agentic_value(artifact))


def _patch_artifact_payload(patch: PatchProposal) -> dict[str, Any]:
    payload = _proposal_payload(patch)
    code_content = payload.pop("code_content", None)
    if code_content is not None:
        payload["patch_body_omitted"] = True
        payload["patch_body_chars"] = len(str(code_content))
    return payload


def _load_artifact_payload(artifact: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(artifact, Mapping):
        return dict(artifact)
    path = Path(artifact)
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: Any) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(rendered, encoding="utf-8")
    os.replace(tmp_path, path)


def _find_raw_ref_marker(rendered: str) -> str | None:
    lowered = rendered.lower()
    for marker in _RAW_REF_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _json_size(value: Any) -> int:
    return len(json.dumps(_json_ready(value), sort_keys=True, default=str))


def compute_agentic_idempotency_key(
    request: AgenticProposalRequest,
    tool_loop_config: AgenticToolLoopConfig,
) -> str:
    """Stable replay/audit key for duplicate APS requests.

    The key is derived from durable campaign/request anchors and policy/config,
    never from the random session_id.
    """
    policy_payload: Any = None
    if request.tool_context is not None:
        policy_payload = _json_ready(request.tool_context.policy)
    champion = request.champion
    branch = request.branch
    anchor_payload = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "campaign_id": request.campaign_id,
        "branch": {
            "branch_id": branch.branch_id,
            "base_champion_id": branch.base_champion_id,
            "base_champion_hash": branch.base_champion_hash,
            "current_code_hash": branch.current_code_hash,
            "weight_revision": getattr(branch, "weight_revision", None),
        },
        "champion": {
            "version": _champion_version(champion),
            "code_snapshot_hash": getattr(champion, "code_snapshot_hash", None)
            if champion is not None
            else None,
            "solver_config_hash": getattr(champion, "solver_config_hash", None)
            if champion is not None
            else None,
            "weight_revision": _champion_weight_revision(champion),
        },
        "problem": {
            "problem_id": request.problem_id,
            "problem_spec_hash": request.problem_spec_hash,
        },
        "request": {
            "kind": "code" if request.approved_hypothesis is not None else "hypothesis",
            "approved_hypothesis": _proposal_payload(request.approved_hypothesis)
            if request.approved_hypothesis is not None
            else None,
            "prior_failure": _sanitize_agentic_value(request.prior_failure),
        },
        "policy": policy_payload,
        "tool_loop_config": _tool_loop_config_payload(tool_loop_config),
    }
    rendered = json.dumps(
        _json_ready(_sanitize_agentic_value(anchor_payload)),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "aps:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _tool_call_fingerprint(name: str, args: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        _json_ready(_sanitize_agentic_value({"tool_name": name, "args": dict(args)})),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _proposal_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return dict(_sanitize_agentic_value(asdict(value)))
    if isinstance(value, Mapping):
        return dict(_sanitize_agentic_value(value))
    return dict(_sanitize_agentic_value(getattr(value, "__dict__", {})))


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


def _observation_prompt_payload(observation: ProposalObservation) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
        "structured_payload": _sanitize_agentic_value(observation.structured_payload),
    }


def _observation_selection_payload(observation: ProposalObservation) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": _sanitize_agentic_value(observation.summary),
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
    }


def _surface_names_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    names: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.list_surfaces":
            continue
        surfaces = observation.structured_payload.get("surfaces", ())
        if not isinstance(surfaces, (list, tuple)):
            continue
        for surface in surfaces:
            if not isinstance(surface, Mapping):
                continue
            for key in ("id", "name"):
                value = surface.get(key)
                if value:
                    names.append(str(value))
    return list(dict.fromkeys(names))


def _feedback_query_args(context: ProposalToolContext) -> dict[str, Any]:
    args: dict[str, Any] = {}
    if context.forced_surface:
        args["surface"] = context.forced_surface
    return args


def _has_feedback_screening_history(context: ProposalToolContext) -> bool:
    forced_surface = str(context.forced_surface or "").strip()
    for step in context.step_history:
        if _step_stage_name(step) != "screening":
            continue
        if forced_surface and _step_surface_name(step) != forced_surface:
            continue
        return True
    return False


def _step_surface_name(step: Any) -> str:
    hypothesis = getattr(step, "hypothesis", None)
    return str(getattr(hypothesis, "change_locus", "") or "").strip()


def _step_stage_name(step: Any) -> str:
    protocol = getattr(step, "protocol_result", None)
    stage = getattr(protocol, "stage", None)
    value = getattr(stage, "value", stage)
    return str(value or "").strip().lower()


def _observation_satisfies_compact_requirement(
    context: ProposalToolContext | None,
    observation: ProposalObservation,
) -> bool:
    if observation.is_error:
        return False
    if observation.tool_name == "feedback.query_screening":
        return _screening_feedback_observation_has_rows(observation)
    if observation.tool_name == "feedback.query_runtime":
        return _runtime_feedback_observation_has_content(observation)
    return True


def _screening_feedback_observation_has_rows(
    observation: ProposalObservation,
) -> bool:
    payload = observation.structured_payload
    rows = payload.get("screening_steps") if isinstance(payload, Mapping) else None
    return isinstance(rows, list) and bool(rows)


def _runtime_feedback_observation_has_content(
    observation: ProposalObservation,
) -> bool:
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return False
    for key in ("runtime_feedback", "runtime_failure_guidance"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    attribution = payload.get("screening_runtime_attribution")
    return isinstance(attribution, list) and bool(attribution)


def _has_successful_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    surface_name: str,
) -> bool:
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        surface = payload.get("surface")
        if isinstance(surface, Mapping) and surface.get("name") == surface_name:
            return True
    return False


def _has_successful_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    forced_surface: str | None = None,
) -> bool:
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return False
    if tool_name in _SINGLE_SUCCESS_OBSERVATION_TOOLS:
        return any(
            observation.tool_name == tool_name and not observation.is_error
            for observation in observations
        )
    if tool_name != "context.read_surface":
        return False
    requested_surface = str(args.get("surface") or forced_surface or "").strip()
    if not requested_surface:
        return False
    return _has_successful_surface_read(observations, requested_surface)


def _self_check_from_previews(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> AgenticSelfCheck:
    schema_valid = True
    schema_preview_evaluated = False
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()
    for observation in observations:
        if observation.is_error:
            if observation.tool_name in {
                "proposal.schema_preview",
                "proposal.target_permission_preview",
            }:
                if observation.failure_code != ProposalToolFailureCode.RESULT_TOO_LARGE:
                    schema_valid = False
                    schema_preview_evaluated = True
            if observation.tool_name == "proposal.contract_preview":
                contract_preview_codes = tuple(
                    code
                    for code in (
                        _enum_value(observation.failure_code),
                        observation.observation_type,
                    )
                    if code
                )
                budget_error = (
                    observation.failure_code
                    == ProposalToolFailureCode.RESULT_TOO_LARGE
                )
                contract_preview_passed = None if budget_error else False
            continue
        payload = observation.structured_payload
        if observation.tool_name in {
            "proposal.schema_preview",
            "proposal.target_permission_preview",
        }:
            schema_preview_evaluated = True
            schema_valid = schema_valid and bool(payload.get("passed"))
        if observation.tool_name == "proposal.contract_preview":
            contract_preview_passed = bool(payload.get("passed"))
            contract_preview_codes = _preview_codes(payload)
    return AgenticSelfCheck(
        schema_valid=schema_valid if schema_preview_evaluated else False,
        contract_preview_passed=contract_preview_passed,
        contract_preview_codes=contract_preview_codes,
    )


def _preview_codes(payload: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            name = value.get("name")
            if name and "passed" in value and not value.get("passed"):
                codes.append(str(name))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return tuple(dict.fromkeys(codes))


def _sanitize_agentic_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"raw_metrics_ref", "case_ids", "seed_set", "pair_feedback"}:
                continue
            cleaned[key_text] = _sanitize_agentic_value(item)
        return cleaned
    if isinstance(value, tuple):
        return [_sanitize_agentic_value(item) for item in value]
    if isinstance(value, list):
        return [_sanitize_agentic_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _sanitize_agentic_value(asdict(value))
    if isinstance(value, str):
        return _sanitize_agentic_text(value)
    return value


def _sanitize_agentic_text(text: str) -> str:
    forbidden_terms = (
        "raw_metrics_ref",
        "raw metrics",
        "validation",
        "frozen",
        "holdout",
    )
    safe_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in forbidden_terms):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)
