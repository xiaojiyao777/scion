"""Typed models and input schemas for proposal tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field

from scion.core.models import Branch, ChampionState, StepRecord
from scion.proposal.schemas import HypothesisProposalInput, PatchProposalInput

class ProposalToolPermission(str, Enum):
    READ_PUBLIC_CONTEXT = "read_public_context"
    READ_TAINTED_MEMORY = "read_tainted_memory"
    READ_CHAMPION_ARTIFACT = "read_champion_artifact"
    CONTRACT_PREVIEW = "contract_preview"
    DRAFT_PATCH = "draft_patch"
    WRITE_SCRATCH = "write_scratch"
    FORBIDDEN = "forbidden"

class HoldoutExposure(str, Enum):
    NONE = "none"
    PASS_FAIL = "pass_fail"
    AGGREGATE = "aggregate"

class ProposalExposureLevel(str, Enum):
    NONE = "none"
    PUBLIC_SPEC = "public_spec"
    CHAMPION_CODE = "champion_code"
    SCREENING_DETAIL = "screening_detail"
    VALIDATION_AGGREGATE = "validation_aggregate"
    FROZEN_AGGREGATE = "frozen_aggregate"
    TAINTED_MEMORY = "tainted_memory"
    SCRATCH = "scratch"

class ProposalTaint(str, Enum):
    PROPOSAL = "proposal"

class ProposalToolFailureCode(str, Enum):
    SCHEMA_ERROR = "schema_error"
    PERMISSION_DENIED = "permission_denied"
    EXPOSURE_DENIED = "exposure_denied"
    NOT_FOUND = "not_found"
    RUNTIME_EXCEPTION = "runtime_exception"
    RESULT_TOO_LARGE = "result_too_large"
    UNSUPPORTED = "unsupported"

@dataclass(frozen=True)
class ContextExposurePolicy:
    """Code-enforced visibility policy for proposal tools.

    The default is intentionally strict for holdout data: screening detail is
    allowed, validation/frozen summaries are hidden, and raw metrics refs are
    neither returned nor expanded.  Screening runtime helpers may read
    screening-only raw metrics because the existing hypothesis context already
    uses that bounded path.
    """

    allow_public_context_read: bool = True
    allow_tainted_memory_read: bool = True
    allow_screening_case_detail: bool = True
    allow_screening_runtime_raw_read: bool = True
    validation_exposure: HoldoutExposure = HoldoutExposure.NONE
    frozen_exposure: HoldoutExposure = HoldoutExposure.NONE
    allow_raw_metrics_refs: bool = False
    allow_raw_metrics_read: bool = False
    allow_champion_code_read: bool = True
    allow_contract_preview: bool = False
    allow_draft_artifact: bool = False
    allow_candidate_workspace_read: bool = False
    allow_final_evidence_read: bool = False
    context_policy_id: str = "proposal-agent-v0.4-strict-aps3"

    def allows_permission(self, permission: ProposalToolPermission) -> bool:
        if permission == ProposalToolPermission.READ_PUBLIC_CONTEXT:
            return self.allow_public_context_read
        if permission == ProposalToolPermission.READ_TAINTED_MEMORY:
            return self.allow_tainted_memory_read
        if permission == ProposalToolPermission.READ_CHAMPION_ARTIFACT:
            return self.allow_champion_code_read
        if permission == ProposalToolPermission.CONTRACT_PREVIEW:
            return self.allow_contract_preview
        if permission == ProposalToolPermission.DRAFT_PATCH:
            return self.allow_draft_artifact
        return False

@dataclass(frozen=True)
class ProposalToolContext:
    session_id: str
    campaign_id: str
    branch: Branch | None = None
    champion: ChampionState | None = None
    problem_spec: Any = None
    split_manifest: Any = None
    seed_ledger: Any = None
    adapter: Any = None
    step_history: tuple[StepRecord, ...] = ()
    search_memory: Any = None
    research_log: Any = None
    policy: ContextExposurePolicy = field(default_factory=ContextExposurePolicy)
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    forced_surface: str | None = None
    forced_action: str | None = None
    forced_target_file: str | None = None
    active_problem_boundary_surfaces: tuple[str, ...] = ()
    branch_workspace: str | None = None

    @property
    def branch_id(self) -> str | None:
        return self.branch.branch_id if self.branch is not None else None

@dataclass(frozen=True)
class ProposalObservation:
    observation_id: str
    session_id: str
    tool_name: str
    tool_call_id: str
    observation_type: str
    summary: str
    structured_payload: Mapping[str, Any]
    artifact_ref: str | None = None
    taint: ProposalTaint = ProposalTaint.PROPOSAL
    exposure_level: ProposalExposureLevel = ProposalExposureLevel.PUBLIC_SPEC
    is_error: bool = False
    failure_code: ProposalToolFailureCode | None = None
    repair_hint: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now().isoformat())

class ProposalTool(Protocol):
    name: str
    input_schema: type[BaseModel]
    permission: ProposalToolPermission
    read_only: bool
    concurrency_safe: bool
    max_result_chars: int

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation: ...

class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

class EmptyInput(_StrictInput):
    pass

class ReadSurfaceInput(_StrictInput):
    surface: str = Field(
        description=(
            "Declared research surface id/name. Choose only a surface returned "
            "by context.list_surfaces in the current session."
        )
    )
    target_file: str | None = None
    detail: Literal["compact", "full"] = "compact"
    section: Literal[
        "all",
        "summary",
        "interface",
        "bounds",
        "evidence",
        "novelty",
        "target_preview",
    ] = "all"
    include_code: bool = True
    max_code_chars: int | None = Field(default=None, ge=0, le=24000)

class MemoryQueryInput(_StrictInput):
    query: str | None = None
    surface: str | None = None
    max_chars: int = Field(default=4000, ge=200, le=12000)

class FeedbackQueryInput(_StrictInput):
    branch_id: str | None = None
    surface: str | None = None
    max_items: int = Field(default=8, ge=1, le=25)

class DraftHypothesisInput(HypothesisProposalInput):
    model_config = ConfigDict(extra="forbid")

class DraftPatchInput(PatchProposalInput):
    model_config = ConfigDict(extra="forbid")

class SchemaPreviewInput(_StrictInput):
    hypothesis: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None

class TargetPermissionPreviewInput(_StrictInput):
    change_locus: str
    action: str
    target_file: str | None = None

class InterfacePreviewInput(_StrictInput):
    file_path: str
    action: str = "modify"
    code_content: str
    selected_surface: str | None = None

class ContractPreviewInput(_StrictInput):
    hypothesis: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None

class AlgorithmSmokeInput(_StrictInput):
    hypothesis: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None

__all__ = [
    "AlgorithmSmokeInput",
    "ContextExposurePolicy",
    "ContractPreviewInput",
    "DraftHypothesisInput",
    "DraftPatchInput",
    "EmptyInput",
    "FeedbackQueryInput",
    "HoldoutExposure",
    "InterfacePreviewInput",
    "MemoryQueryInput",
    "ProposalExposureLevel",
    "ProposalObservation",
    "ProposalTaint",
    "ProposalTool",
    "ProposalToolContext",
    "ProposalToolFailureCode",
    "ProposalToolPermission",
    "ReadSurfaceInput",
    "SchemaPreviewInput",
    "TargetPermissionPreviewInput",
]
