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
import signal
import threading
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
    ProposalToolPermission,
    ProposalToolRegistry,
    _active_boundary_novelty_requirements,
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
_HOLDOUT_SUMMARY_TOOL = "feedback.query_holdout_summary"
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
)
_SINGLE_SUCCESS_OBSERVATION_TOOLS = (
    "context.list_surfaces",
    "context.read_problem",
    "context.read_branch_state",
    "memory.query",
)
_MIN_BUDGETED_OBSERVATION_CHARS = 512
_OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS = 3000
_APS_SURFACE_READ_CODE_CHARS = 800
_APS_CODE_SURFACE_READ_CODE_CHARS = 12000
_APS_CODE_MODULE_SURFACE_READ_CODE_CHARS = 6000
_APS_FEEDBACK_OBSERVATION_TARGET_CHARS = 6000
_APS_FEEDBACK_TEXT_CHARS = 1200
_APS_FEEDBACK_LIST_ITEMS = 4
_APS_FEEDBACK_MAP_ITEMS = 16
_APS_FEEDBACK_CALL_RESERVE_CHARS = 6000
_SELF_CHECK_TOOL_CALL_RESERVE = 4
_SELF_CHECK_OBSERVATION_RESERVE_CHARS = 24000
_CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC = 12.0
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
_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
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


class AgenticProposalStatus(str, Enum):
    """Terminal status for one bounded proposal session."""

    COMPLETED = "completed"
    PARTIAL_HYPOTHESIS_ONLY = "partial_hypothesis_only"
    PARTIAL_PATCH_UNCHECKED = "partial_patch_unchecked"
    FAILED = "failed"


class _ProposalToolTimeout(BaseException):
    pass


def _can_use_signal_timeout() -> bool:
    return (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
    )


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

    max_steps: int = 22
    max_tool_calls: int = 18
    max_observation_chars: int = 64000
    max_wall_time_sec: float = 120.0
    max_repeated_tool_calls: int = 2
    max_code_tool_calls: int = 4
    max_code_repair_attempts: int = 1
    max_code_generation_timeout_retries: int = 1


@dataclass(frozen=True)
class AgenticEvidenceRef:
    observation_id: str
    exposure_level: str
    summary: str


@dataclass(frozen=True)
class AgenticSelfCheck:
    schema_valid: bool = False
    schema_preview_codes: tuple[str, ...] = ()
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
    def generate_hypothesis(self, context: Mapping[str, Any]) -> HypothesisProposal: ...

    def generate_code(self, context: Mapping[str, Any]) -> PatchProposal: ...


class AgenticSessionArtifactStore(Protocol):
    def write_transcript(self, state: AgenticProposalSessionState) -> str: ...

    def write_output(self, output: AgenticProposalOutput) -> str: ...

    def write_scratch(
        self,
        session_id: str,
        name: str,
        payload: Mapping[str, Any],
    ) -> str: ...


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
        matches = [
            entry for entry in self._read_entries() if entry.session_id == session_id
        ]
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
        matches = [
            entry for entry in self._read_entries() if entry.request_id == request_id
        ]
        if not matches:
            return None
        return self._load_stored_session(self._latest_entry(matches))

    def list_sessions(self) -> list[AgenticStoredSession]:
        return [
            self._load_stored_session(entry)
            for entry in sorted(
                self._read_entries(),
                key=lambda entry: (
                    entry.updated_at,
                    entry.created_at,
                    entry.session_id,
                ),
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
        return AgenticStoredSession(
            entry=entry, artifact=artifact, validation=validation
        )

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
                        artifact_ref=str(
                            item.get("artifact_ref") or item.get("artifact_path") or ""
                        ),
                        artifact_path=str(
                            item.get("artifact_path") or item.get("artifact_ref") or ""
                        ),
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
                    research_diagnosis = _research_diagnosis_from_observations(
                        observations
                    )
                    if research_diagnosis:
                        hypothesis_context["agentic_research_diagnosis"] = (
                            research_diagnosis
                        )
                    hypothesis_context["agentic_tool_observations"] = [
                        _observation_prompt_payload(observation)
                        for observation in observations
                    ]
                hypothesis = self._creative.generate_hypothesis(hypothesis_context)
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
                self_check = _self_check_from_previews(observations)
                self_check_detail = _self_check_failure_detail(
                    self_check,
                    require_schema_preview=_self_check_required(tool_context),
                    require_contract_preview=False,
                )
                if self_check_detail is not None:
                    output = self._self_check_failed_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        detail=self_check_detail,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        evidence_used=tuple(evidence),
                        self_check=self_check,
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
            self_check = _self_check_from_previews(observations)
            self_check_detail = _self_check_failure_detail(
                self_check,
                require_schema_preview=_self_check_required(tool_context),
                require_contract_preview=False,
            )
            if self_check_detail is not None:
                output = self._self_check_failed_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail=self_check_detail,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    evidence_used=tuple(evidence),
                    self_check=self_check,
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
            self_reported_issue = _patch_self_reported_unresolved_issue(patch)
        if self_reported_issue is not None:
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_reported_issue,
                evidence_used=tuple(evidence),
                self_check=_self_check_from_previews(observations),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch generation failed because generated patch self-reported an unresolved code issue.",
                metadata={"detail": self_reported_issue},
            )
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
            latest_preview = patch_preview
            if (
                not patch_preview.is_error
                and not bool(patch_preview.structured_payload.get("passed"))
                and code_repair_attempts_used
                < self._tool_loop_config.max_code_repair_attempts
                and not self._session_timeout_reached(state)
            ):
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
                        "Patch repair generation failed after Contract preview feedback.",
                        metadata={"error": type(exc).__name__},
                    )
                    return self._persist(output, state)
                self_reported_issue = _patch_self_reported_unresolved_issue(patch)
                if self_reported_issue is not None:
                    output = self._partial_hypothesis_output(
                        request=request,
                        session_id=session_id,
                        hypothesis=hypothesis,
                        detail=self_reported_issue,
                        evidence_used=tuple(evidence),
                        self_check=_self_check_from_previews(observations),
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Patch repair failed because generated patch self-reported an unresolved code issue.",
                        metadata={"detail": self_reported_issue},
                    )
                    return self._persist(output, state)
                repair_preview = self._run_contract_preview_tool(
                    tool_context,
                    hypothesis,
                    patch,
                    state,
                )
                observations.append(repair_preview)
                evidence.extend(_evidence_from_observations((repair_preview,)))
                latest_preview = repair_preview

            if _preview_observation_passed(latest_preview):
                smoke_preview = self._run_algorithm_smoke_tool(
                    tool_context,
                    hypothesis,
                    patch,
                    state,
                )
                observations.append(smoke_preview)
                evidence.extend(_evidence_from_observations((smoke_preview,)))
                if (
                    not _preview_observation_passed(smoke_preview)
                    and code_repair_attempts_used
                    < self._tool_loop_config.max_code_repair_attempts
                    and not self._session_timeout_reached(state)
                ):
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
                            "Patch repair generation failed after algorithm-smoke feedback.",
                            metadata={"error": type(exc).__name__},
                        )
                        return self._persist(output, state)
                    self_reported_issue = _patch_self_reported_unresolved_issue(patch)
                    if self_reported_issue is not None:
                        output = self._partial_hypothesis_output(
                            request=request,
                            session_id=session_id,
                            hypothesis=hypothesis,
                            detail=self_reported_issue,
                            evidence_used=tuple(evidence),
                            self_check=_self_check_from_previews(observations),
                        )
                        state.status = output.status
                        state.note(
                            AgenticProposalPhase.FINALIZE,
                            "Patch repair failed because generated patch self-reported an unresolved code issue.",
                            metadata={"detail": self_reported_issue},
                        )
                        return self._persist(output, state)
                    repaired_contract_preview = self._run_contract_preview_tool(
                        tool_context,
                        hypothesis,
                        patch,
                        state,
                    )
                    observations.append(repaired_contract_preview)
                    evidence.extend(
                        _evidence_from_observations((repaired_contract_preview,))
                    )
                    if _preview_observation_passed(repaired_contract_preview):
                        repaired_smoke_preview = self._run_algorithm_smoke_tool(
                            tool_context,
                            hypothesis,
                            patch,
                            state,
                        )
                        observations.append(repaired_smoke_preview)
                        evidence.extend(
                            _evidence_from_observations((repaired_smoke_preview,))
                        )

        state.note(AgenticProposalPhase.SELF_CHECK, "Recorded APS-1 schema self-check.")
        self_check = (
            _self_check_from_previews(observations)
            if tool_context is not None
            else AgenticSelfCheck(schema_valid=True)
        )
        algorithm_smoke_detail = _algorithm_smoke_failure_detail(observations)
        if algorithm_smoke_detail is not None:
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=algorithm_smoke_detail,
                termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch self-check failed closed after algorithm smoke.",
                metadata={"detail": algorithm_smoke_detail},
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
            if self._diagnosis_budget_reserved(state) and (
                self._missing_required_context_error(observations) is None
                or name not in {"context.list_surfaces", "context.read_problem"}
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
                and self._missing_required_context_error(observations) is None
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
                and self._missing_required_context_error(observations) is None
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
                and self._missing_required_context_error(observations) is None
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
            if self._code_phase_budget_reserved(state):
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
                break
            if self._tool_loop_limit_reached(state):
                self._record_loop_stop(state, self._current_loop_stop_reason(state))
                break
            observations.append(
                self._call_tool(
                    context,
                    state,
                    AgenticProposalPhase.INSPECT_INTERFACE,
                    name,
                    args,
                    selection_source=selection_source,
                )
            )
        return observations

    def _code_phase_allowed_tools(
        self,
        context: ProposalToolContext,
    ) -> tuple[str, ...]:
        if self.tool_registry is None:
            return ()
        allowed = set(
            _filter_model_facing_tool_names(
                self.tool_registry.allowed_tools(context),
                context,
            )
        )
        return tuple(sorted(allowed.intersection(_CODE_PHASE_TOOL_ALLOWLIST)))

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
        if self._remaining_tool_calls(state) <= 4:
            return True
        if self._remaining_tool_steps(state) <= 4:
            return True
        reserve = max(
            self._minimum_budgeted_observation_chars(),
            self._self_check_observation_reserve_chars(),
            min(8000, max(0, int(self._tool_loop_config.max_observation_chars) // 8)),
        )
        return self._remaining_observation_chars(state) <= reserve

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
        if _is_solver_design_support_module_target(hypothesis.target_file):
            read_surface_args["section"] = "target_preview"
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
        repair_context["prior_code_failure"] = (
            "Contract preview failed before workspace materialization: "
            f"{failed_preview.summary}"
        )
        repair_context["agentic_preview_feedback"] = _observation_prompt_payload(
            failed_preview
        )
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            repair_context["agentic_research_diagnosis"] = research_diagnosis
        repair_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in _code_prompt_observations(observations)
        ]
        state.note(
            AgenticProposalPhase.DRAFT_PATCH,
            "Regenerating patch proposal with Contract-preview feedback.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "target_file": hypothesis.target_file,
                "repair_attempt": repair_attempt,
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
                return self._creative.generate_code(attempt_context)
            except self._SESSION_ERROR_TYPES as exc:
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

    def _run_algorithm_smoke_tool(
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
                tool_name="proposal.algorithm_smoke",
                tool_call_id="",
                observation_type="tool_skipped",
                summary=(
                    "Algorithm smoke skipped because the session wall-time limit was reached."
                    if stop_reason == "session_timeout"
                    else "Algorithm smoke skipped because the tool loop limit was reached."
                ),
                structured_payload={},
                is_error=True,
                failure_code=ProposalToolFailureCode.UNSUPPORTED,
            )
        return self._call_tool(
            context,
            state,
            AgenticProposalPhase.SELF_CHECK,
            "proposal.algorithm_smoke",
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
                observation = ProposalObservation(
                    observation_id=str(uuid.uuid4()),
                    session_id=context.session_id,
                    tool_name=name,
                    tool_call_id=step_id,
                    observation_type="tool_error",
                    summary=str(exc),
                    structured_payload={
                        "timeout_sec": _CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC,
                        "tool_name": name,
                    },
                    is_error=True,
                    failure_code=ProposalToolFailureCode.RUNTIME_EXCEPTION,
                    repair_hint=(
                        "Simplify the candidate and use statically bounded loops "
                        "before requesting Contract preview or algorithm smoke again."
                    ),
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

        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, _CONTRACT_PREVIEW_TOOL_TIMEOUT_SEC)
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

    def _remaining_tool_calls(self, state: AgenticProposalSessionState) -> int:
        return max(
            0,
            int(self._tool_loop_config.max_tool_calls) - int(state.tool_call_count),
        )

    def _remaining_tool_steps(self, state: AgenticProposalSessionState) -> int:
        return max(
            0, int(self._tool_loop_config.max_steps) - int(state.tool_step_count)
        )

    def _self_check_tool_call_reserve(self) -> int:
        max_calls = max(0, int(self._tool_loop_config.max_tool_calls))
        if max_calls < 8:
            return 0
        return min(_SELF_CHECK_TOOL_CALL_RESERVE, max_calls // 3)

    def _self_check_step_reserve(self) -> int:
        max_steps = max(0, int(self._tool_loop_config.max_steps))
        if max_steps < 8:
            return 0
        return min(_SELF_CHECK_TOOL_CALL_RESERVE, max_steps // 3)

    def _self_check_observation_reserve_chars(self) -> int:
        max_chars = max(0, int(self._tool_loop_config.max_observation_chars))
        if max_chars < _SELF_CHECK_OBSERVATION_RESERVE_CHARS * 2:
            return 0
        return min(_SELF_CHECK_OBSERVATION_RESERVE_CHARS, max_chars // 3)

    def _diagnosis_budget_reserved(self, state: AgenticProposalSessionState) -> bool:
        call_reserve = self._self_check_tool_call_reserve()
        if call_reserve and self._remaining_tool_calls(state) <= call_reserve:
            return True
        step_reserve = self._self_check_step_reserve()
        if step_reserve and self._remaining_tool_steps(state) <= step_reserve:
            return True
        observation_reserve = self._self_check_observation_reserve_chars()
        if (
            observation_reserve
            and self._remaining_observation_chars(state) <= observation_reserve
        ):
            return True
        return False

    def _diagnosis_feedback_budget_reserved(
        self,
        state: AgenticProposalSessionState,
    ) -> bool:
        observation_reserve = self._self_check_observation_reserve_chars()
        if not observation_reserve:
            return False
        return self._remaining_observation_chars(state) <= (
            observation_reserve + _APS_FEEDBACK_CALL_RESERVE_CHARS
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
        self_check_reserve = self._self_check_observation_reserve_chars()
        minimum = self._minimum_budgeted_observation_chars()
        optional_floor = min(
            _OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS,
            max(0, int(self._tool_loop_config.max_observation_chars) // 8),
        )
        if self_check_reserve:
            return max(minimum, optional_floor, self_check_reserve + minimum)
        return max(
            minimum,
            optional_floor,
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
        if selection_source.startswith("code_phase"):
            target_file = str(budgeted.get("target_file") or "").strip()
            if _is_solver_design_support_module_target(target_file):
                budgeted["section"] = "target_preview"
                budgeted["max_code_chars"] = min(
                    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    _coerce_positive_int(
                        budgeted.get("max_code_chars"),
                        _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    ),
                )
                if budgeted.get("detail") != "full":
                    budgeted["detail"] = "full"
                return budgeted
            if budgeted.get("detail") != "full":
                budgeted["detail"] = "full"
            max_code_chars = budgeted.get("max_code_chars")
            if max_code_chars is None:
                budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
                return budgeted
            try:
                requested = int(max_code_chars)
            except Exception:
                budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
                return budgeted
            if requested > _APS_CODE_SURFACE_READ_CODE_CHARS or requested < 0:
                budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
            return budgeted
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
        observation = _compact_feedback_observation_for_budget(observation)
        compact_preview = _compact_self_check_preview_observation(observation)
        if compact_preview is not None and (
            _json_size(_observation_prompt_payload(compact_preview))
            < _json_size(_observation_prompt_payload(observation))
        ):
            observation = compact_preview
        projected = _json_size(_observation_prompt_payload(observation))
        remaining = self._remaining_observation_chars(state)
        if projected <= remaining:
            return observation
        compact_preview = _compact_self_check_preview_observation(observation)
        if compact_preview is not None and (
            _json_size(_observation_prompt_payload(compact_preview)) <= remaining
        ):
            return compact_preview
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
        "max_code_tool_calls": int(config.max_code_tool_calls),
        "max_code_repair_attempts": int(config.max_code_repair_attempts),
        "max_code_generation_timeout_retries": int(
            config.max_code_generation_timeout_retries
        ),
    }


def _tool_budget_used_payload(state: AgenticProposalSessionState) -> dict[str, int]:
    return {
        "tool_steps": int(state.tool_step_count),
        "tool_calls": int(state.tool_call_count),
        "observation_chars": int(state.observation_chars_used),
    }


def _compact_contract_preview_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name != "proposal.contract_preview" or observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    compact_payload = _drop_empty_mapping(
        {
            "passed": bool(payload.get("passed")),
            "static_only": payload.get("static_only"),
            "workspace_materialized": payload.get("workspace_materialized"),
            "verification_run": payload.get("verification_run"),
            "protocol_run": payload.get("protocol_run"),
            "decision_run": payload.get("decision_run"),
            "issue_summary": _limit_string(payload.get("issue_summary"), 320),
            "hypothesis": _compact_contract_preview_section(payload.get("hypothesis")),
            "patch": _compact_contract_preview_section(payload.get("patch")),
            "compact_due_to_budget": True,
        }
    )
    return replace(
        observation,
        summary=f"{observation.summary} Compact budget preview retained.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_algorithm_smoke_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name != "proposal.algorithm_smoke" or observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    compact_payload = _drop_empty_mapping(
        {
            "passed": bool(payload.get("passed")),
            "non_promotional": payload.get("non_promotional"),
            "tainted_debug": payload.get("tainted_debug"),
            "workspace_materialized": payload.get("workspace_materialized"),
            "verification_run": payload.get("verification_run"),
            "protocol_run": payload.get("protocol_run"),
            "decision_run": payload.get("decision_run"),
            "issue_summary": _limit_string(payload.get("issue_summary"), 240),
            "static_contract": _compact_contract_mapping(
                payload.get("static_contract")
            ),
            "hypothesis": _compact_contract_preview_section(payload.get("hypothesis")),
            "patch": _compact_contract_preview_section(payload.get("patch")),
            "problem_preview": _compact_problem_preview_mapping(
                payload.get("problem_preview")
            ),
            "compact_due_to_budget": True,
        }
    )
    return replace(
        observation,
        summary=f"{observation.summary} Compact smoke preview retained.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_self_check_preview_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name == "proposal.contract_preview":
        return _compact_contract_preview_observation(observation)
    if observation.tool_name == "proposal.algorithm_smoke":
        return _compact_algorithm_smoke_observation(observation)
    return None


def _compact_contract_preview_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "issue_summary": _limit_string(value.get("issue_summary"), 240),
            "contract": _compact_contract_mapping(value.get("contract")),
            "needs_hypothesis": value.get("needs_hypothesis"),
            "errors": _bounded_string_list(value.get("errors"), limit=4),
            "issues": _bounded_string_list(value.get("issues"), limit=4),
            "failed_checks": _failed_preview_checks(value.get("checks")),
            "problem_preview": _compact_problem_preview_mapping(
                value.get("problem_preview")
            ),
        }
    )
    return compact or None


def _compact_problem_preview_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "surface": value.get("surface"),
            "issues": _bounded_string_list(value.get("issues"), limit=8),
            "failed_checks": _failed_preview_checks(value.get("checks")),
        }
    )
    return compact or None


def _compact_contract_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "check_count": value.get("check_count"),
            "failed_checks": _bounded_string_list(
                value.get("failed_checks"),
                limit=8,
            ),
            "failure_reason": _limit_string(value.get("failure_reason"), 240),
        }
    )
    return compact or None


def _failed_preview_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    failed: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping) or item.get("passed") is not False:
            continue
        failed.append(
            _drop_empty_mapping(
                {
                    "name": item.get("name"),
                    "passed": False,
                    "severity": item.get("severity"),
                    "detail": _limit_string(item.get("detail"), 240),
                }
            )
        )
        if len(failed) >= 8:
            break
    return failed


def _bounded_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = _limit_string(item, 160)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _limit_string(value: Any, limit: int) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _drop_empty_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
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
        "hypothesis": (
            _proposal_payload(output.hypothesis)
            if output.hypothesis is not None
            else None
        ),
        "patch": (
            _patch_artifact_payload(output.patch) if output.patch is not None else None
        ),
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
    additional = []
    for change in payload.get("additional_changes") or []:
        if not isinstance(change, Mapping):
            continue
        compact = dict(change)
        change_code = compact.pop("code_content", None)
        if change_code is not None:
            compact["patch_body_omitted"] = True
            compact["patch_body_chars"] = len(str(change_code))
        additional.append(compact)
    if additional:
        payload["additional_changes"] = additional
        payload["additional_change_count"] = len(additional)
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
            "code_snapshot_hash": (
                getattr(champion, "code_snapshot_hash", None)
                if champion is not None
                else None
            ),
            "solver_config_hash": (
                getattr(champion, "solver_config_hash", None)
                if champion is not None
                else None
            ),
            "weight_revision": _champion_weight_revision(champion),
        },
        "problem": {
            "problem_id": request.problem_id,
            "problem_spec_hash": request.problem_spec_hash,
        },
        "request": {
            "kind": "code" if request.approved_hypothesis is not None else "hypothesis",
            "approved_hypothesis": (
                _proposal_payload(request.approved_hypothesis)
                if request.approved_hypothesis is not None
                else None
            ),
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


def _research_diagnosis_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> dict[str, Any]:
    runtime_diagnoses: list[dict[str, Any]] = []
    screening_counts = {
        "screening_observations": 0,
        "runtime_observations": 0,
    }
    for observation in observations:
        if observation.is_error:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if observation.tool_name == "feedback.query_screening":
            screening_counts["screening_observations"] += 1
        if observation.tool_name != "feedback.query_runtime":
            continue
        screening_counts["runtime_observations"] += 1
        diagnosis = payload.get("research_diagnosis")
        if isinstance(diagnosis, Mapping):
            runtime_diagnoses.append(_sanitize_agentic_value(diagnosis))
    if not runtime_diagnoses and not any(screening_counts.values()):
        return {}
    meaningful = [
        diagnosis
        for diagnosis in runtime_diagnoses
        if _research_diagnosis_has_signal(diagnosis)
    ]
    diagnosis_source = meaningful or runtime_diagnoses
    latest = diagnosis_source[-1] if diagnosis_source else {}
    return _json_ready(
        {
            "schema_version": "agentic-research-diagnosis.v1",
            "source": "proposal_tool_observations",
            "screening_only": True,
            "observation_counts": screening_counts,
            "runtime_diagnosis_count": len(runtime_diagnoses),
            "runtime_diagnoses_with_signal": len(meaningful),
            "latest_runtime_diagnosis": latest,
            "aggregate_runtime_diagnosis": _aggregate_runtime_diagnoses(
                diagnosis_source
            ),
            "recent_runtime_diagnoses": diagnosis_source[-3:],
            "research_protocol": [
                "Use screening/runtime observations as tainted evidence for proposal reasoning only.",
                "Identify the prior failure pattern before proposing a mechanism change.",
                "Tie the hypothesis to declared surface evidence fields and expected protocol movement.",
                "Do not use validation/frozen holdout detail or raw metric refs.",
            ],
        }
    )


def _research_diagnosis_has_signal(diagnosis: Mapping[str, Any]) -> bool:
    if _safe_positive_int(diagnosis.get("screening_step_count")):
        return True
    for key in (
        "recent_screening_steps",
        "reason_code_counts",
        "failure_mode_tags",
        "runtime_signal_rows",
        "gate_outcome_counts",
    ):
        value = diagnosis.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, list) and value:
            return True
    return False


def _aggregate_runtime_diagnoses(
    diagnoses: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    failure_tags: set[str] = set()
    runtime_signal_rows: list[dict[str, Any]] = []
    recent_screening_steps: list[dict[str, Any]] = []
    for diagnosis in diagnoses:
        _merge_int_counts(reason_counts, diagnosis.get("reason_code_counts"))
        _merge_int_counts(surface_counts, diagnosis.get("surface_counts"))
        _merge_int_counts(gate_counts, diagnosis.get("gate_outcome_counts"))
        tags = diagnosis.get("failure_mode_tags")
        if isinstance(tags, list):
            failure_tags.update(str(tag) for tag in tags if tag)
        rows = diagnosis.get("runtime_signal_rows")
        if isinstance(rows, list):
            runtime_signal_rows.extend(row for row in rows if isinstance(row, Mapping))
        steps = diagnosis.get("recent_screening_steps")
        if isinstance(steps, list):
            recent_screening_steps.extend(
                step for step in steps if isinstance(step, Mapping)
            )
    return _drop_empty_dict(
        {
            "reason_code_counts": reason_counts,
            "surface_counts": surface_counts,
            "gate_outcome_counts": gate_counts,
            "failure_mode_tags": sorted(failure_tags),
            "runtime_signal_rows": runtime_signal_rows[-8:],
            "recent_screening_steps": recent_screening_steps[-8:],
        }
    )


def _merge_int_counts(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, Mapping):
        return
    for key, count in value.items():
        try:
            amount = int(count)
        except (TypeError, ValueError):
            continue
        target[str(key)] = target.get(str(key), 0) + amount


def _drop_empty_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None)}


def _filter_model_facing_tool_names(
    tool_names: tuple[str, ...] | list[str],
    context: ProposalToolContext,
) -> tuple[str, ...]:
    filtered: list[str] = []
    for raw_name in tool_names:
        name = str(raw_name or "").strip()
        if not name:
            continue
        if name == _HOLDOUT_SUMMARY_TOOL:
            # The direct tool remains available to deterministic callers, but
            # model-facing planner prompts cannot safely render a tool name
            # containing holdout terminology under strict sanitization.
            continue
        if name == "proposal.algorithm_smoke":
            # This tool needs a completed patch; the session invokes it
            # deterministically after code generation instead of exposing it to
            # pre-code planning.
            continue
        filtered.append(name)
    return tuple(dict.fromkeys(filtered))


def _safe_positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


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


def _code_observation_prompt_payload(
    observation: ProposalObservation,
) -> dict[str, Any]:
    payload = _observation_prompt_payload(observation)
    payload["structured_payload"] = _code_prompt_observation_payload(
        observation.tool_name,
        observation.structured_payload,
    )
    return _drop_empty_dict(payload)


def _with_code_scope_control(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    timeout_retry: bool,
    failure_detail: str | None = None,
) -> dict[str, Any]:
    prepared = dict(code_context)
    if not _is_solver_design_code_context(prepared, hypothesis):
        return prepared
    if timeout_retry:
        prepared["code_generation_mode"] = "compact_timeout_retry"
    else:
        prepared.setdefault("code_generation_mode", "compact_solver_design")
    prepared["agentic_code_scope_control"] = _solver_design_code_scope_control(
        hypothesis,
        timeout_retry=timeout_retry,
        failure_detail=failure_detail,
    )
    return prepared


def _code_timeout_retry_context(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    exc: BaseException,
    observations: list[ProposalObservation],
) -> dict[str, Any]:
    detail = _code_timeout_failure_detail(exc)
    retry_context = _with_code_scope_control(
        dict(code_context),
        hypothesis,
        timeout_retry=True,
        failure_detail=detail,
    )
    retry_context["prior_code_failure"] = detail
    if observations:
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            retry_context["agentic_research_diagnosis"] = research_diagnosis
        retry_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in _code_prompt_observations(observations)
        ]
    return retry_context


def _code_timeout_failure_detail(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return (
        "code_generation_timeout: final patch generation timed out before "
        "returning a patch. Retry with a compact bounded implementation. "
        f"Original error: {text}"
    )


def _is_code_generation_timeout(exc: BaseException) -> bool:
    if isinstance(exc, LLMTimeoutError):
        return True
    if isinstance(exc, LLMRetryExhaustedError):
        lowered = str(exc).lower()
        return "timed out" in lowered or "timeout" in lowered
    return False


def _is_solver_design_code_context(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
) -> bool:
    surface = str(
        code_context.get("research_surface_name")
        or code_context.get("change_locus")
        or hypothesis.change_locus
        or ""
    ).strip()
    kind = str(code_context.get("research_surface_kind") or "").strip()
    target_file = str(
        code_context.get("target_file") or hypothesis.target_file or ""
    ).strip()
    return (
        surface in _SOLVER_DESIGN_SURFACE_NAMES
        or kind in _SOLVER_DESIGN_SURFACE_NAMES
        or target_file.endswith("policies/baseline_algorithm.py")
        or target_file.endswith("policies/solver_algorithm.py")
    )


def _solver_design_code_scope_control(
    hypothesis: HypothesisProposal,
    *,
    timeout_retry: bool,
    failure_detail: str | None,
) -> dict[str, Any]:
    broad_terms = _solver_design_broad_terms(hypothesis)
    return _drop_empty_mapping(
        {
            "mode": (
                "compact_timeout_retry" if timeout_retry else "compact_solver_design"
            ),
            "surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "failure_detail": failure_detail,
            "detected_broad_terms": broad_terms,
            "required_shape": (
                "complete target module content with one primary construction "
                "or seeding path and one bounded improvement/search loop using "
                "no more than two move families"
            ),
            "scope_rule": (
                "Reduce broad hybrid hypotheses to one executable vertical "
                "algorithm slice for this patch. Prefer the focused "
                "solver-design modules under policies/baseline_modules; do not "
                "turn the entrypoint into a context.baseline post-processing "
                "wrapper."
            ),
            "runtime_rule": (
                "Use explicit loop caps and context time checks; runtime is an "
                "optimization objective and evidence field."
            ),
        }
    )


def _solver_design_broad_terms(
    hypothesis: HypothesisProposal,
) -> list[str]:
    fields = (
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
        hypothesis.complexity_claim,
        hypothesis.runtime_budget_strategy,
    )
    text = "\n".join(str(field or "") for field in fields).lower()
    return [term for term in _SOLVER_DESIGN_BROAD_TERMS if term in text]


def _code_prompt_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    latest_full_surface: ProposalObservation | None = None
    for observation in observations:
        if observation.tool_name == "context.read_surface":
            payload = observation.structured_payload
            if (
                not observation.is_error
                and isinstance(payload, Mapping)
                and str(payload.get("detail") or "") == "full"
            ):
                latest_full_surface = observation
            continue
        if observation.tool_name in _CODE_PROMPT_FEEDBACK_TOOLS:
            selected.append(observation)
            continue
        if observation.is_error:
            selected.append(observation)
    if latest_full_surface is not None:
        selected.append(latest_full_surface)
    return selected


def _code_prompt_observation_payload(
    tool_name: str,
    structured_payload: Mapping[str, Any],
) -> Any:
    safe_payload = _sanitize_agentic_value(structured_payload)
    if tool_name == "context.read_surface" and isinstance(safe_payload, Mapping):
        return _compact_code_surface_payload(safe_payload)
    return _compact_code_prompt_value(safe_payload)


def _compact_code_surface_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    artifact = payload.get("current_artifact")
    current_artifact = (
        _code_artifact_metadata(artifact) if isinstance(artifact, Mapping) else {}
    )
    return _drop_empty_mapping(
        {
            "surface": _compact_code_prompt_value(payload.get("surface")),
            "surface_contract": _compact_code_prompt_value(
                payload.get("surface_contract")
            ),
            "detail": payload.get("detail"),
            "section": payload.get("section"),
            "declared_targets": _compact_code_prompt_value(
                payload.get("declared_targets")
            ),
            "target_file": payload.get("target_file"),
            "current_artifact": current_artifact,
        }
    )


def _code_artifact_metadata(artifact: Mapping[str, Any]) -> dict[str, Any]:
    content_preview = artifact.get("content_preview")
    metadata = {
        "file_path": artifact.get("file_path"),
        "readable": artifact.get("readable"),
        "reason": artifact.get("reason"),
        "truncated": artifact.get("truncated"),
        "size_chars": artifact.get("size_chars"),
        "max_chars": artifact.get("max_chars"),
        "content_preview_chars": (
            len(str(content_preview)) if content_preview is not None else None
        ),
        "content_preview_omitted": content_preview is not None or None,
    }
    return _drop_empty_mapping(metadata)


def _compact_code_prompt_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return _limit_string(value, _CODE_PROMPT_STRING_CHARS)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _CODE_PROMPT_MAP_ITEMS:
                compact["_truncated_items"] = len(value) - _CODE_PROMPT_MAP_ITEMS
                break
            key_text = str(key)
            if key_text in {
                "content_preview",
                "interface_summary",
                "problem_object",
                "target_file_code",
                "champion_operators_code",
                "reference_operators",
            }:
                if key_text == "content_preview":
                    compact["content_preview_omitted"] = True
                    compact["content_preview_chars"] = len(str(item))
                elif item:
                    compact[f"{key_text}_chars"] = len(str(item))
                continue
            if key_text == "current_artifact" and isinstance(item, Mapping):
                compact[key_text] = _code_artifact_metadata(item)
                continue
            compact[key_text] = _compact_code_prompt_value(item, depth=depth + 1)
        return _drop_empty_mapping(compact)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        items = [
            _compact_code_prompt_value(item, depth=depth + 1)
            for item in value[:_CODE_PROMPT_LIST_ITEMS]
        ]
        if len(value) > _CODE_PROMPT_LIST_ITEMS:
            items.append({"_truncated_items": len(value) - _CODE_PROMPT_LIST_ITEMS})
        return items
    if isinstance(value, str):
        return _limit_string(value, _CODE_PROMPT_STRING_CHARS) or ""
    return value


def _compact_feedback_observation_for_budget(
    observation: ProposalObservation,
) -> ProposalObservation:
    if observation.is_error or observation.tool_name not in {
        "feedback.query_screening",
        "feedback.query_runtime",
    }:
        return observation
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return observation
    if observation.tool_name == "feedback.query_screening":
        compact_payload = _compact_screening_feedback_payload(payload)
    else:
        compact_payload = _compact_runtime_feedback_payload(payload)
    compact_observation = replace(
        observation,
        summary=_limit_string(observation.summary, 260) or "Returned compact feedback.",
        structured_payload=compact_payload,
        repair_hint=None,
    )
    if _json_size(_observation_prompt_payload(compact_observation)) <= _json_size(
        _observation_prompt_payload(observation)
    ):
        return compact_observation
    return observation


def _compact_screening_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = payload.get("screening_steps")
    compact_rows = []
    if isinstance(rows, list):
        compact_rows = [
            _compact_screening_step_for_budget(row)
            for row in rows[:_APS_FEEDBACK_LIST_ITEMS]
            if isinstance(row, Mapping)
        ]
    compact = _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "query_scope": _compact_feedback_value_for_budget(
                payload.get("query_scope")
            ),
            "available_screening_step_count": payload.get(
                "available_screening_step_count"
            ),
            "matched_screening_step_count": payload.get("matched_screening_step_count"),
            "screening_steps": compact_rows,
            "metrics_file_ref_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
        }
    )
    return _shrink_feedback_payload_to_target(compact)


def _compact_runtime_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    attribution = payload.get("screening_runtime_attribution")
    compact_attribution = []
    if isinstance(attribution, list):
        compact_attribution = [
            _compact_runtime_attribution_for_budget(row)
            for row in attribution[:_APS_FEEDBACK_LIST_ITEMS]
            if isinstance(row, Mapping)
        ]
    compact = _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "query_scope": _compact_feedback_value_for_budget(
                payload.get("query_scope")
            ),
            "runtime_feedback": _limit_string(
                payload.get("runtime_feedback"),
                _APS_FEEDBACK_TEXT_CHARS,
            ),
            "runtime_failure_guidance": _limit_string(
                payload.get("runtime_failure_guidance"),
                _APS_FEEDBACK_TEXT_CHARS,
            ),
            "screening_runtime_attribution": compact_attribution,
            "research_diagnosis": _compact_research_diagnosis_for_budget(
                payload.get("research_diagnosis")
            ),
            "screening_only": payload.get("screening_only"),
            "metrics_file_refs_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
        }
    )
    return _shrink_feedback_payload_to_target(compact)


def _compact_screening_step_for_budget(row: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "round_num": row.get("round_num"),
            "branch_id": row.get("branch_id"),
            "surface": row.get("surface"),
            "action": row.get("action"),
            "target_file": row.get("target_file"),
            "gate_outcome": row.get("gate_outcome"),
            "reason_codes": _bounded_string_list(row.get("reason_codes"), limit=6),
            "stats": _compact_eval_stats_for_budget(row.get("stats")),
            "candidate_runtime_failure_categories": _compact_counts_for_budget(
                row.get("candidate_runtime_failure_categories")
            ),
            "candidate_first_runtime_failure": _compact_feedback_value_for_budget(
                row.get("candidate_first_runtime_failure")
            ),
            "candidate_runtime_stop_reasons": _compact_counts_for_budget(
                row.get("candidate_runtime_stop_reasons")
            ),
            "candidate_surface_runtime_attribution": _compact_runtime_attribution_for_budget(
                row.get("candidate_surface_runtime_attribution")
            ),
        }
    )


def _compact_runtime_attribution_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    highlights = value.get("runtime_field_highlights")
    compact_highlights = []
    if isinstance(highlights, list):
        compact_highlights = [
            _compact_runtime_highlight_for_budget(highlight)
            for highlight in highlights[: _APS_FEEDBACK_LIST_ITEMS * 2]
            if isinstance(highlight, Mapping)
        ]
    return _drop_empty_mapping(
        {
            "round_num": value.get("round_num"),
            "surface": value.get("surface"),
            "target_file": value.get("target_file"),
            "gate_outcome": value.get("gate_outcome"),
            "reason_codes": _bounded_string_list(value.get("reason_codes"), limit=6),
            "stats": _compact_eval_stats_for_budget(value.get("stats")),
            "runtime_field_highlights": compact_highlights,
        }
    )


def _compact_runtime_highlight_for_budget(value: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "field": value.get("field"),
            "present": value.get("present"),
            "missing": value.get("missing"),
            "empty": value.get("empty"),
            "failed": value.get("failed"),
            "numeric_summary": _compact_feedback_value_for_budget(
                value.get("numeric_summary")
            ),
        }
    )


def _compact_research_diagnosis_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    recent_steps = value.get("recent_screening_steps")
    runtime_rows = value.get("runtime_signal_rows")
    return _drop_empty_mapping(
        {
            "schema_version": value.get("schema_version"),
            "screening_only": value.get("screening_only"),
            "screening_step_count": value.get("screening_step_count"),
            "reason_code_counts": _compact_counts_for_budget(
                value.get("reason_code_counts")
            ),
            "surface_counts": _compact_counts_for_budget(value.get("surface_counts")),
            "declared_solver_design_surfaces": _bounded_string_list(
                value.get("declared_solver_design_surfaces"),
                limit=6,
            ),
            "failed_solver_design_surfaces": _bounded_string_list(
                value.get("failed_solver_design_surfaces"),
                limit=6,
            ),
            "screening_failed_solver_design_surfaces": _bounded_string_list(
                value.get("screening_failed_solver_design_surfaces"),
                limit=6,
            ),
            "unselected_solver_design_surfaces": _bounded_string_list(
                value.get("unselected_solver_design_surfaces"),
                limit=6,
            ),
            "gate_outcome_counts": _compact_counts_for_budget(
                value.get("gate_outcome_counts")
            ),
            "failure_mode_tags": _bounded_string_list(
                value.get("failure_mode_tags"),
                limit=8,
            ),
            "runtime_signal_rows": [
                _compact_feedback_value_for_budget(row)
                for row in (
                    runtime_rows[:_APS_FEEDBACK_LIST_ITEMS]
                    if isinstance(runtime_rows, list)
                    else []
                )
            ],
            "recent_screening_steps": [
                _compact_screening_step_for_budget(row)
                for row in (
                    recent_steps[:_APS_FEEDBACK_LIST_ITEMS]
                    if isinstance(recent_steps, list)
                    else []
                )
                if isinstance(row, Mapping)
            ],
            "next_hypothesis_requirements": _bounded_string_list(
                value.get("next_hypothesis_requirements"),
                limit=6,
            ),
        }
    )


def _compact_eval_stats_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "n_cases",
        "wins",
        "losses",
        "ties",
        "win_rate",
        "median_delta",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
    )
    return _drop_empty_mapping({key: value.get(key) for key in keys})


def _compact_counts_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for index, (key, item) in enumerate(
        sorted(value.items(), key=lambda pair: str(pair[0]))
    ):
        if index >= _APS_FEEDBACK_MAP_ITEMS:
            compact["_truncated_items"] = len(value) - _APS_FEEDBACK_MAP_ITEMS
            break
        compact[str(key)] = item
    return _drop_empty_mapping(compact)


def _compact_feedback_value_for_budget(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return _limit_string(value, 200)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _APS_FEEDBACK_MAP_ITEMS:
                compact["_truncated_items"] = len(value) - _APS_FEEDBACK_MAP_ITEMS
                break
            compact[str(key)] = _compact_feedback_value_for_budget(
                item,
                depth=depth + 1,
            )
        return _drop_empty_mapping(compact)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        items = [
            _compact_feedback_value_for_budget(item, depth=depth + 1)
            for item in value[:_APS_FEEDBACK_LIST_ITEMS]
        ]
        if len(value) > _APS_FEEDBACK_LIST_ITEMS:
            items.append({"_truncated_items": len(value) - _APS_FEEDBACK_LIST_ITEMS})
        return items
    if isinstance(value, str):
        return _limit_string(value, max(200, _APS_FEEDBACK_TEXT_CHARS // (depth + 1)))
    return value


def _shrink_feedback_payload_to_target(payload: dict[str, Any]) -> dict[str, Any]:
    if _json_size(payload) <= _APS_FEEDBACK_OBSERVATION_TARGET_CHARS:
        return payload
    shrunk = dict(payload)
    if "runtime_feedback" in shrunk:
        shrunk["runtime_feedback"] = _limit_string(shrunk.get("runtime_feedback"), 600)
    if "runtime_failure_guidance" in shrunk:
        shrunk["runtime_failure_guidance"] = _limit_string(
            shrunk.get("runtime_failure_guidance"),
            600,
        )
    for key in (
        "screening_steps",
        "screening_runtime_attribution",
        "runtime_signal_rows",
        "recent_screening_steps",
    ):
        value = shrunk.get(key)
        if isinstance(value, list) and len(value) > 2:
            shrunk[key] = value[:2] + [{"_truncated_items": len(value) - 2}]
    if _json_size(shrunk) <= _APS_FEEDBACK_OBSERVATION_TARGET_CHARS:
        return _drop_empty_mapping(shrunk)
    return _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "query_scope": payload.get("query_scope"),
            "available_screening_step_count": payload.get(
                "available_screening_step_count"
            ),
            "matched_screening_step_count": payload.get("matched_screening_step_count"),
            "screening_steps": _minimal_screening_rows_for_budget(
                payload.get("screening_steps")
            ),
            "screening_only": payload.get("screening_only"),
            "research_diagnosis": payload.get("research_diagnosis"),
            "metrics_file_refs_exposed": False,
            "metrics_file_ref_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
            "summary": "APS feedback payload was summarized to preserve preview budget.",
        }
    )


def _minimal_screening_rows_for_budget(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value[:2]:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            _drop_empty_mapping(
                {
                    "round_num": row.get("round_num"),
                    "surface": row.get("surface"),
                    "target_file": row.get("target_file"),
                    "gate_outcome": row.get("gate_outcome"),
                    "reason_codes": _bounded_string_list(
                        row.get("reason_codes"),
                        limit=4,
                    ),
                    "stats": _compact_eval_stats_for_budget(row.get("stats")),
                }
            )
        )
    return rows


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


def _is_solver_design_support_module_target(target_file: Any) -> bool:
    normalized = str(target_file or "").replace("\\", "/").lstrip("/")
    return normalized.startswith("policies/baseline_modules/") and normalized.endswith(
        ".py"
    )


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


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
    if isinstance(attribution, list) and bool(attribution):
        return True
    diagnosis = payload.get("research_diagnosis")
    return isinstance(diagnosis, Mapping) and _research_diagnosis_has_signal(diagnosis)


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
        requested_surface = str(args.get("surface") or forced_surface or "").strip()
        requested_branch = str(args.get("branch_id") or "").strip()
        for observation in observations:
            if observation.tool_name != tool_name:
                continue
            if not _observation_satisfies_compact_requirement(None, observation):
                continue
            payload = observation.structured_payload
            if not isinstance(payload, Mapping):
                continue
            observed_surface = str(payload.get("surface") or "").strip()
            if (
                requested_surface
                and observed_surface
                and observed_surface != requested_surface
            ):
                continue
            observed_branch = str(payload.get("branch_id") or "").strip()
            if requested_branch and observed_branch != requested_branch:
                continue
            return True
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


def _has_successful_tool(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
) -> bool:
    return any(
        observation.tool_name == tool_name and not observation.is_error
        for observation in observations
    )


def _has_successful_code_phase_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    hypothesis: HypothesisProposal,
) -> bool:
    if tool_name in {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    }:
        return False
    if tool_name == "context.read_surface":
        requested_surface = str(
            args.get("surface") or hypothesis.change_locus or ""
        ).strip()
        requested_target = str(
            args.get("target_file") or hypothesis.target_file or ""
        ).strip()
        return _has_code_phase_surface_read(
            observations,
            hypothesis,
            surface=requested_surface,
            target_file=requested_target or None,
        )
    return _has_successful_tool(observations, tool_name)


def _has_code_phase_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    hypothesis: HypothesisProposal,
    *,
    surface: str | None = None,
    target_file: str | None = None,
) -> bool:
    expected_surface = str(surface or hypothesis.change_locus or "").strip()
    expected_target = str(target_file or hypothesis.target_file or "").strip()
    if not expected_surface:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_surface = payload.get("surface")
        if not (
            isinstance(observed_surface, Mapping)
            and observed_surface.get("name") == expected_surface
        ):
            continue
        if str(payload.get("detail") or "") != "full":
            continue
        observed_target = str(payload.get("target_file") or "").strip()
        if expected_target and observed_target and observed_target != expected_target:
            continue
        artifact = payload.get("current_artifact")
        if not isinstance(artifact, Mapping):
            return True
        if not bool(artifact.get("readable", True)):
            continue
        try:
            max_chars = int(artifact.get("max_chars") or 0)
        except (TypeError, ValueError):
            max_chars = 0
        required_chars = (
            _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS
            if _is_solver_design_support_module_target(expected_target)
            else _APS_CODE_SURFACE_READ_CODE_CHARS
        )
        if max_chars >= required_chars or not artifact.get(
            "truncated"
        ):
            return True
    return False


def _code_context_tool_summary(code_context: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    compact_keys = (
        "research_surface_name",
        "research_surface_kind",
        "change_locus",
        "target_file",
        "editable_patterns",
        "frozen_patterns",
        "import_whitelist",
        "prior_code_failure",
    )
    for key in compact_keys:
        if key in code_context:
            summary[key] = _sanitize_agentic_value(code_context.get(key))
    for key in (
        "target_file_code",
        "champion_operators_code",
        "reference_operators",
        "operator_interface_spec",
        "problem_summary",
        "problem_object",
        "solver_mechanics",
    ):
        value = code_context.get(key)
        if value is not None:
            summary[f"{key}_chars"] = len(str(value))
    return summary


def _self_check_from_previews(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> AgenticSelfCheck:
    schema_valid = True
    schema_preview_evaluated = False
    schema_preview_codes: list[str] = []
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()
    for observation in observations:
        if observation.is_error:
            if observation.tool_name in {
                "proposal.schema_preview",
                "proposal.target_permission_preview",
            }:
                schema_valid = False
                schema_preview_evaluated = True
                schema_preview_codes.extend(
                    code
                    for code in (
                        _enum_value(observation.failure_code),
                        observation.observation_type,
                    )
                    if code
                )
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
                    observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
                )
                contract_preview_passed = None if budget_error else False
            continue
        payload = observation.structured_payload
        if observation.tool_name in {
            "proposal.schema_preview",
            "proposal.target_permission_preview",
        }:
            schema_preview_evaluated = True
            preview_passed = bool(payload.get("passed"))
            schema_valid = schema_valid and preview_passed
            if not preview_passed:
                schema_preview_codes.extend(_preview_codes(payload))
        if observation.tool_name == "proposal.contract_preview":
            contract_preview_passed = bool(payload.get("passed"))
            contract_preview_codes = _preview_codes(payload)
    return AgenticSelfCheck(
        schema_valid=schema_valid if schema_preview_evaluated else False,
        schema_preview_codes=tuple(dict.fromkeys(schema_preview_codes)),
        contract_preview_passed=contract_preview_passed,
        contract_preview_codes=contract_preview_codes,
    )


def _self_check_failure_detail(
    self_check: AgenticSelfCheck,
    *,
    require_schema_preview: bool,
    require_contract_preview: bool,
) -> str | None:
    if require_schema_preview and not self_check.schema_valid:
        codes = ", ".join(self_check.schema_preview_codes)
        suffix = f" ({codes})" if codes else ""
        return f"schema or target preview did not pass{suffix}"
    if require_contract_preview and self_check.contract_preview_passed is not True:
        codes = ", ".join(self_check.contract_preview_codes)
        suffix = f" ({codes})" if codes else ""
        return f"contract preview did not pass{suffix}"
    return None


def _preview_observation_passed(observation: ProposalObservation) -> bool:
    return (
        not observation.is_error
        and bool(observation.structured_payload.get("passed"))
    )


def _algorithm_smoke_failure_detail(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> str | None:
    smoke_observations = [
        observation
        for observation in observations
        if observation.tool_name == "proposal.algorithm_smoke"
    ]
    if not smoke_observations:
        return None
    latest = smoke_observations[-1]
    if latest.is_error:
        if latest.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE:
            return "algorithm smoke result exceeded observation budget"
        codes = ", ".join(
            code
            for code in (
                _enum_value(latest.failure_code),
                latest.observation_type,
            )
            if code
        )
        suffix = f" ({codes})" if codes else ""
        return f"algorithm smoke did not run{suffix}"
    if bool(latest.structured_payload.get("passed")):
        return None
    codes = ", ".join(_preview_codes(latest.structured_payload))
    suffix = f" ({codes})" if codes else ""
    return f"algorithm smoke did not pass{suffix}"


def _self_check_required(context: ProposalToolContext | None) -> bool:
    return bool(
        context is not None
        and context.policy.allows_permission(ProposalToolPermission.CONTRACT_PREVIEW)
    )


def _preview_codes(payload: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []

    def add(value: Any) -> None:
        text = _limit_string(value, 160)
        if text:
            codes.append(text)

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("issue_summary"):
                add(value.get("issue_summary"))
            if value.get("failure_reason"):
                add(value.get("failure_reason"))
            for key in ("errors", "issues"):
                raw_values = value.get(key)
                if isinstance(raw_values, list):
                    for raw in raw_values:
                        if isinstance(raw, Mapping):
                            location = ".".join(
                                str(part) for part in raw.get("loc", ()) or ()
                            )
                            message = raw.get("msg") or raw.get("message") or raw
                            add(f"{location}: {message}" if location else message)
                        else:
                            add(raw)
                elif raw_values:
                    add(raw_values)
            name = value.get("name")
            if name and "passed" in value and not value.get("passed"):
                detail = value.get("detail")
                add(f"{name}: {detail}" if detail else name)
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
