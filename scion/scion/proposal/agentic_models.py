"""Data models for bounded agentic proposal sessions."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from scion.core.models import Branch, ChampionState, HypothesisProposal, PatchProposal
from scion.proposal.agentic_preview import AgenticSelfCheck
from scion.proposal.tools import ProposalToolContext

AGENTIC_SESSION_SCHEMA_VERSION = "agentic-proposal-session.v1"

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
    PREMISE_CONTRADICTED = "premise_contradicted"
    DUPLICATE_MECHANISM = "duplicate_mechanism"
    MECHANISM_NOVELTY_REJECTED = "mechanism_novelty_rejected"
    INJECTED_OUTPUT = "injected_output"
    TOOL_LOOP_LIMIT = "tool_loop_limit"
    SESSION_TIMEOUT = "session_timeout"
    REPEATED_TOOL_CALL = "repeated_tool_call"
    UNHANDLED_ERROR = "unhandled_error"


class AgenticFailureCategory(str, Enum):
    """Coarse failure category for retry and audit attribution."""

    LLM_TRANSIENT_API_ERROR = "llm_transient_api_error"
    SCHEMA_OUTPUT_FAILURE = "schema_output_failure"
    STRUCTURED_OUTPUT_RETRY_EXHAUSTED = "structured_output_retry_exhausted"
    CONTRACT_BOUNDARY_FAILURE = "contract_boundary_failure"
    PATCH_GRAPH_FAILURE = "patch_graph_failure"
    MODEL_REPAIR_FAILED = "model_repair_failed"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    AGENTIC_BUDGET_CONTROL = "agentic_budget_control"
    PREMISE_CONTRADICTED = "premise_contradicted"
    DUPLICATE_MECHANISM = "duplicate_mechanism"
    ALGORITHM_SMOKE_FAILURE = "algorithm_smoke_failure"


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

    max_steps: int = 30
    max_tool_calls: int = 24
    max_observation_chars: int = 192000
    max_wall_time_sec: float = 240.0
    max_repeated_tool_calls: int = 2
    max_code_tool_calls: int = 6
    max_code_repair_attempts: int = 2
    max_code_generation_timeout_retries: int = 1


@dataclass(frozen=True)
class AgenticEvidenceRef:
    observation_id: str
    exposure_level: str
    summary: str


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
    failure_ledger: list[Mapping[str, Any]] = field(default_factory=list)
    tool_step_count: int = 0
    tool_call_count: int = 0
    tool_event_count: int = 0
    preview_tool_step_count: int = 0
    preview_tool_call_count: int = 0
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
    failure_category: AgenticFailureCategory | str | None = None
    structured_rejection: Mapping[str, Any] | None = None
    failure_ledger: Mapping[str, Any] = field(default_factory=dict)

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
    artifact_ref_scope: str = "artifact_dir_relative"
    artifact_path_internal_only: bool = True
    tool_loop_config: Mapping[str, Any] = field(default_factory=dict)
    tool_budget_used: Mapping[str, Any] = field(default_factory=dict)
    prompt_manifest_required: bool = False
    prompt_manifest_artifact_ref: str = ""
    prompt_manifest_artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    prompt_manifest_ref_scope: str = "artifact_dir_relative"
    raw_prompt_saved: bool = False
    prompt_manifest_not_required_reason: str = ""


@dataclass(frozen=True)
class AgenticStoredSession:
    entry: AgenticSessionIndexEntry
    artifact: Mapping[str, Any] | None
    validation: AgenticReplayValidationResult

@dataclass(frozen=True)
class AgenticReplayValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()
