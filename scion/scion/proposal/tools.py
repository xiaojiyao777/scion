"""Proposal tools with explicit exposure control.

These tools live inside the tainted proposal layer.  They return typed
observations for an agentic proposal session, but they do not write candidate
workspaces and they do not expose validation/frozen raw metrics.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Mapping, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scion.contract.gate import ContractGate
from scion.core.models import (
    Branch,
    ChampionState,
    ContractResult,
    ExperimentStage,
    HypothesisProposal,
    PatchFileChange,
    PatchProposal,
    StepRecord,
    patch_file_changes,
)
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.proposal.context_manager import (
    _build_objective_policy_guidance,
    _build_problem_summary,
    _build_research_surface_interface_spec,
    _build_runtime_feedback,
    _build_runtime_failure_guidance,
    _filter_hypothesis_prompt_steps,
    _get_adapter_problem_spec,
    _get_research_surfaces,
)
from scion.proposal.schemas import HypothesisProposalInput, PatchProposalInput

_COMPACT_SURFACE_CODE_CHARS = 1200
_FULL_SURFACE_CODE_CHARS = 12000
_COMPACT_SURFACE_TEXT_CHARS = 600
_COMPACT_SURFACE_HINT_CHARS = 240
_COMPACT_SURFACE_INTERFACE_CHARS = 2400
_COMPACT_SURFACE_LIST_ITEMS = 32
_COMPACT_SURFACE_MAP_ITEMS = 32
_COMPACT_FEEDBACK_PAYLOAD_CHARS = 24000
_COMPACT_FEEDBACK_TEXT_CHARS = 8000
_COMPACT_FEEDBACK_STRING_CHARS = 1200
_COMPACT_FEEDBACK_LIST_ITEMS = 8
_COMPACT_FEEDBACK_MAP_ITEMS = 32
_PREVIEW_CHECK_DETAIL_CHARS = 500
_PREVIEW_FAILURE_REASON_CHARS = 800
_PREVIEW_MAX_CHECKS = 12
_PREVIEW_PROBLEM_ISSUE_CHARS = 500
_PREVIEW_PROBLEM_MAX_CHECKS = 8
_ALGORITHM_SMOKE_TIME_LIMIT_SEC = 3
_ALGORITHM_SMOKE_TIMEOUT_SEC = 10
_ALGORITHM_SMOKE_DEFAULT_SEED = 77
_ALGORITHM_SMOKE_MAX_SCREENING_CASES = 2
_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS = 120
_NONEMPTY_SEQUENCE_NOVELTY_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)
_COMPACT_SURFACE_SECTIONS = (
    "summary",
    "interface",
    "bounds",
    "evidence",
    "novelty",
    "target_preview",
)


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


@dataclass(frozen=True)
class _RuntimeSmokeCase:
    label: str
    rel_path: str
    seed: int
    path: Path


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


class ProposalToolRegistry:
    """Registry and call boundary for proposal tools."""

    def __init__(self, tools: list[ProposalTool] | None = None) -> None:
        self._tools: dict[str, ProposalTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ProposalTool) -> None:
        if not tool.name:
            raise ValueError("proposal tool name must not be empty")
        if tool.name in self._tools:
            raise ValueError(f"duplicate proposal tool: {tool.name}")
        if not tool.read_only:
            raise ValueError(
                f"APS-2 registry accepts read-only tools only: {tool.name}"
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> ProposalTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown proposal tool: {name}") from exc

    def list_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def allowed_tools(self, context: ProposalToolContext) -> tuple[str, ...]:
        """Return tools both registered and permitted by the active policy."""
        return tuple(
            sorted(
                name
                for name, tool in self._tools.items()
                if context.policy.allows_permission(tool.permission)
            )
        )

    def allowed_tool_specs(
        self, context: ProposalToolContext
    ) -> tuple[dict[str, Any], ...]:
        """Return model-facing specs for tools allowed by the active policy."""
        specs: list[dict[str, Any]] = []
        for name in self.allowed_tools(context):
            tool = self._tools[name]
            schema = tool.input_schema.model_json_schema()
            specs.append(
                {
                    "name": name,
                    "input_schema": _strip_forbidden_payload_refs(schema),
                    "permission": tool.permission.value,
                    "read_only": tool.read_only,
                    "max_result_chars": tool.max_result_chars,
                }
            )
        return tuple(specs)

    def call(
        self,
        name: str,
        raw_input: Mapping[str, Any] | None,
        context: ProposalToolContext,
        *,
        tool_call_id: str | None = None,
    ) -> ProposalObservation:
        call_id = tool_call_id or str(uuid.uuid4())
        try:
            tool = self.get(name)
        except KeyError:
            return _error_observation(
                context,
                tool_name=name,
                tool_call_id=call_id,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary=f"Tool not found: {name}",
                repair_hint="Call context.list_surfaces or inspect registry.list_tools().",
            )

        if not context.policy.allows_permission(tool.permission):
            return _error_observation(
                context,
                tool_name=tool.name,
                tool_call_id=call_id,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary=f"Permission denied for {tool.permission.value}.",
                repair_hint="Use a tool allowed by the active ContextExposurePolicy.",
            )

        try:
            args = tool.input_schema.model_validate(dict(raw_input or {}))
        except ValidationError as exc:
            return _error_observation(
                context,
                tool_name=tool.name,
                tool_call_id=call_id,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Tool input failed schema validation.",
                structured_payload={"errors": exc.errors(include_url=False)},
                repair_hint="Repair the tool arguments to match the input schema.",
            )

        try:
            observation = tool.call(args, context)
        except Exception as exc:  # pragma: no cover - hard boundary guard.
            return _error_observation(
                context,
                tool_name=tool.name,
                tool_call_id=call_id,
                failure_code=ProposalToolFailureCode.RUNTIME_EXCEPTION,
                summary=f"Tool raised {type(exc).__name__}: {exc}",
            )

        object.__setattr__(observation, "tool_call_id", call_id)
        if _json_size(observation.structured_payload) > tool.max_result_chars:
            return _error_observation(
                context,
                tool_name=tool.name,
                tool_call_id=call_id,
                failure_code=ProposalToolFailureCode.RESULT_TOO_LARGE,
                summary="Tool result exceeded the configured result budget.",
                structured_payload={
                    "max_result_chars": tool.max_result_chars,
                    "estimated_chars": _json_size(observation.structured_payload),
                },
                repair_hint="Request a narrower surface, branch, or max_items limit.",
            )
        return observation

    @classmethod
    def default_read_only(cls) -> ProposalToolRegistry:
        return cls(
            [
                ContextListSurfacesTool(),
                ContextReadProblemTool(),
                ContextReadSurfaceTool(),
                ContextReadObjectivePolicyTool(),
                ContextReadChampionSummaryTool(),
                ContextReadBranchStateTool(),
                MemoryQueryTool(),
                FeedbackQueryScreeningTool(),
                FeedbackQueryHoldoutSummaryTool(),
                FeedbackQueryRuntimeTool(),
                DraftHypothesisTool(),
                DraftPatchTool(),
                SchemaPreviewTool(),
                TargetPermissionPreviewTool(),
                InterfacePreviewTool(),
                ContractPreviewTool(),
                AlgorithmSmokeTool(),
            ]
        )


class _BaseReadOnlyTool:
    input_schema: type[BaseModel] = EmptyInput
    permission: ProposalToolPermission = ProposalToolPermission.READ_PUBLIC_CONTEXT
    read_only: bool = True
    concurrency_safe: bool = True
    max_result_chars: int = 32000

    def _observation(
        self,
        context: ProposalToolContext,
        *,
        observation_type: str,
        summary: str,
        structured_payload: Mapping[str, Any],
        exposure_level: ProposalExposureLevel,
        artifact_ref: str | None = None,
    ) -> ProposalObservation:
        return ProposalObservation(
            observation_id=str(uuid.uuid4()),
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type=observation_type,
            summary=summary,
            structured_payload=_strip_forbidden_payload_refs(structured_payload),
            artifact_ref=artifact_ref,
            exposure_level=exposure_level,
        )

    def _error(
        self,
        context: ProposalToolContext,
        *,
        failure_code: ProposalToolFailureCode,
        summary: str,
        structured_payload: Mapping[str, Any] | None = None,
        repair_hint: str | None = None,
    ) -> ProposalObservation:
        return _error_observation(
            context,
            tool_name=self.name,
            tool_call_id="",
            failure_code=failure_code,
            summary=summary,
            structured_payload=structured_payload,
            repair_hint=repair_hint,
        )


class ContextListSurfacesTool(_BaseReadOnlyTool):
    name = "context.list_surfaces"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        declared_surfaces = _surfaces(context)
        surfaces = _surface_list_for_context(context, declared_surfaces)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "surface_count": len(surfaces),
            "total_declared_surface_count": len(declared_surfaces),
            "surfaces": [_surface_listing_payload(surface) for surface in surfaces],
            "diagnostic_surface_priorities": _diagnostic_surface_priorities(
                context,
                declared_surfaces,
            ),
            "detail": "compact",
            "forced_surface_constraint": _forced_surface_constraint_payload(context),
            "active_problem_boundary_constraint": (
                _active_problem_boundary_constraint_payload(context)
            ),
        }
        return self._observation(
            context,
            observation_type="surface_list",
            summary=f"Returned {len(surfaces)} declared research surface(s).",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadProblemTool(_BaseReadOnlyTool):
    name = "context.read_problem"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        summary = _problem_summary(context)
        problem_object = _problem_object(context)
        solver_mechanics = _solver_mechanics(context)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "problem_spec_hash": context.problem_spec_hash,
            "summary": _limit_text(summary, 12000),
            "summary_truncated": len(summary) > 12000,
            "problem_object": _limit_text(problem_object, 20000),
            "problem_object_truncated": len(problem_object) > 20000,
            "solver_mechanics": _limit_text(solver_mechanics, 20000),
            "solver_mechanics_truncated": len(solver_mechanics) > 20000,
        }
        return self._observation(
            context,
            observation_type="problem_summary",
            summary="Returned adapter/spec-rendered problem summary.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadObjectivePolicyTool(_BaseReadOnlyTool):
    name = "context.read_objective_policy"

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        adapter_spec = (
            _get_adapter_problem_spec(context.adapter) or context.problem_spec
        )
        rendered = _build_objective_policy_guidance(adapter_spec)
        objectives = [
            _model_payload(obj)
            for obj in list(_attr(adapter_spec, "objectives", []) or [])
        ]
        policy = _model_payload(_attr(adapter_spec, "objective_policy", None))
        payload = {
            "policy": policy,
            "objectives": objectives,
            "rendered_summary": rendered,
        }
        return self._observation(
            context,
            observation_type="objective_policy",
            summary="Returned declared objective policy and metric specs.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadChampionSummaryTool(_BaseReadOnlyTool):
    name = "context.read_champion_summary"
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        champion = context.champion
        if champion is None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary="No champion snapshot is available.",
            )
        operator_pool = []
        for name, op in sorted((champion.operator_pool or {}).items()):
            operator_pool.append(
                {
                    "name": name,
                    "file_path": _attr(op, "file_path"),
                    "category": _attr(op, "category"),
                    "weight": _attr(op, "weight"),
                    "class_name": _attr(op, "class_name"),
                }
            )
        payload = {
            "operator_count": len(operator_pool),
            "operator_pool": operator_pool,
            "solver_config_hash": champion.solver_config_hash,
            "code_snapshot_hash": champion.code_snapshot_hash,
            "has_code_snapshot": bool(champion.code_snapshot_path),
        }
        return self._observation(
            context,
            observation_type="champion_summary",
            summary="Returned champion artifact inventory.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadBranchStateTool(_BaseReadOnlyTool):
    name = "context.read_branch_state"
    permission = ProposalToolPermission.READ_PUBLIC_CONTEXT

    def call(
        self, args: BaseModel, context: ProposalToolContext
    ) -> ProposalObservation:
        branch = context.branch
        if branch is None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary="No branch state is available.",
            )
        state = _attr(branch, "state")
        payload = {
            "branch_id": _attr(branch, "branch_id"),
            "state": _model_payload(state),
            "base_champion_id": _attr(branch, "base_champion_id"),
            "base_champion_hash": _attr(branch, "base_champion_hash"),
            "current_code_hash": _attr(branch, "current_code_hash"),
            "last_clean_code_hash": _attr(branch, "last_clean_code_hash"),
            "retry_count": _attr(branch, "retry_count"),
            "failure_codes": list(_attr(branch, "failure_codes", []) or []),
            "pending_retry": bool(_attr(branch, "pending_retry", False)),
            "blocked_rounds": _attr(branch, "blocked_rounds"),
            "consecutive_llm_retries": _attr(branch, "consecutive_llm_retries"),
            "infra_block_count": _attr(branch, "infra_block_count"),
            "direction": _attr(branch, "direction"),
            "weight_revision": _attr(branch, "weight_revision"),
        }
        return self._observation(
            context,
            observation_type="branch_state",
            summary="Returned current branch state and retry/failure counters.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContextReadSurfaceTool(_BaseReadOnlyTool):
    name = "context.read_surface"
    input_schema = ReadSurfaceInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ReadSurfaceInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.surface)
        if surface is None:
            available_surfaces = [
                str(_attr(candidate, "name") or _attr(candidate, "id") or "")
                for candidate in _surfaces(context)
            ]
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary=f"Research surface not found: {args.surface}",
                structured_payload={
                    "requested_surface": args.surface,
                    "available_surfaces": [
                        surface_name
                        for surface_name in available_surfaces
                        if surface_name
                    ],
                },
                repair_hint="Use context.list_surfaces and select a declared surface.",
            )
        target_files = _surface_target_files(surface)
        target_file = args.target_file or _first_concrete_target(target_files)
        if target_file is not None and not _target_declared(target_file, target_files):
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary=(
                    f"Target file {target_file!r} is not declared for surface "
                    f"{args.surface!r}."
                ),
                structured_payload={
                    "surface": args.surface,
                    "declared_targets": target_files,
                    "requested_target": target_file,
                },
                repair_hint="Read only files declared by the selected research surface.",
            )

        detail = args.detail
        code_char_limit = _surface_code_char_limit(
            detail=detail,
            requested_max=args.max_code_chars,
        )
        code_payload: dict[str, Any] | None = None
        support_artifacts: list[dict[str, Any]] = []
        if args.include_code and target_file:
            if context.champion is None:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.NOT_FOUND,
                    summary="No champion snapshot is available for surface read.",
                )
            code_payload = _read_champion_file(
                context.champion,
                target_file,
                max_chars=code_char_limit,
            )
            if _surface_name(surface) == "solver_design" and args.section in {
                "all",
                "target_preview",
            }:
                support_artifacts = _read_solver_design_support_artifacts(
                    context.champion,
                    target_files,
                    primary_target=target_file,
                    detail=detail,
                    primary_code_char_limit=code_char_limit,
                )

        payload = {
            "surface": _surface_read_payload(
                surface,
                detail=detail,
                section=args.section,
            ),
            "surface_contract": _surface_contract_metadata(
                surface,
                detail=detail,
                section=args.section,
                current_artifact=code_payload,
            ),
            "interface_summary": _surface_interface_summary(
                surface,
                detail=detail,
                section=args.section,
            ),
            "detail": detail,
            "section": args.section,
            "declared_targets": target_files,
            "target_file": target_file,
            "current_artifact": code_payload,
            "support_artifacts": support_artifacts,
        }
        return self._observation(
            context,
            observation_type="surface_interface",
            summary=f"Returned declared interface for surface {args.surface}.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class MemoryQueryTool(_BaseReadOnlyTool):
    name = "memory.query"
    input_schema = MemoryQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY
    max_result_chars = 20000

    def call(
        self,
        args: MemoryQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        sections: list[str] = []
        if context.search_memory is not None:
            render = getattr(context.search_memory, "render", None)
            if not callable(render):
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Search memory does not provide a callable render method.",
                    repair_hint=(
                        "Provide a callable render(view='hypothesis') implementation "
                        "for proposal memory reads."
                    ),
                )
            try:
                text = render(view="hypothesis")
            except TypeError:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Search memory does not support the safe hypothesis view.",
                    repair_hint=(
                        "Provide a render(view='hypothesis') implementation for "
                        "proposal memory reads."
                    ),
                )
            if text:
                sections.append(str(text))
        if context.research_log is not None:
            render = getattr(context.research_log, "render", None)
            if not callable(render):
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Research log does not provide a callable render method.",
                    repair_hint=(
                        "Provide a callable render(view='hypothesis') implementation "
                        "for proposal memory reads."
                    ),
                )
            try:
                text = render(view="hypothesis")
            except TypeError:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Research log does not support the safe hypothesis view.",
                    repair_hint=(
                        "Provide a render(view='hypothesis') implementation for "
                        "proposal memory reads."
                    ),
                )
            if text:
                sections.append(str(text))

        combined = "\n\n".join(sections)
        combined = _sanitize_memory_text(combined)
        if args.surface:
            combined = "\n".join(
                line for line in combined.splitlines() if args.surface in line
            )
        if args.query:
            q = args.query.lower()
            combined = "\n".join(
                line for line in combined.splitlines() if q in line.lower()
            )
        limited = _limit_text(combined, args.max_chars)
        payload = {
            "query": args.query,
            "surface": args.surface,
            "text": limited,
            "truncated": len(combined) > args.max_chars,
            "policy_id": context.policy.context_policy_id,
            "excluded_signals": [
                "champion_evolution",
                "promotion_path",
                "validation",
                "frozen",
                "holdout",
            ],
        }
        return self._observation(
            context,
            observation_type="proposal_memory",
            summary="Returned tainted proposal/search memory safe view.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.TAINTED_MEMORY,
        )


class FeedbackQueryScreeningTool(_BaseReadOnlyTool):
    name = "feedback.query_screening"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        if not context.policy.allow_screening_case_detail:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.EXPOSURE_DENIED,
                summary="Screening detail is disabled by ContextExposurePolicy.",
            )
        safe_steps = _filter_hypothesis_prompt_steps(list(context.step_history))
        available_screening_steps = [
            step
            for step in safe_steps
            if (
                step.protocol_result is not None
                and step.protocol_result.stage == ExperimentStage.SCREENING
            )
        ]
        rows = []
        matched_count = 0
        for step in reversed(available_screening_steps):
            protocol = step.protocol_result
            if protocol is None or protocol.stage != ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            matched_count += 1
            if len(rows) < args.max_items:
                rows.append(_screening_step_payload(step))
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "query_scope": {
                "campaign_id": context.campaign_id,
                "branch_filter_applied": bool(args.branch_id),
                "surface_filter_applied": bool(args.surface),
                "recent_first": True,
            },
            "available_screening_step_count": len(available_screening_steps),
            "matched_screening_step_count": matched_count,
            "screening_steps": rows,
        }
        payload = _bound_compact_feedback_payload(payload)
        return self._observation(
            context,
            observation_type="screening_feedback",
            summary=(
                f"Returned {len(rows)} of {matched_count} screening feedback row(s)."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
        )


class FeedbackQueryHoldoutSummaryTool(_BaseReadOnlyTool):
    name = "feedback.query_holdout_summary"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        rows = []
        for step in context.step_history:
            protocol = step.protocol_result
            if protocol is None or protocol.stage == ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            stage = _stage_value(protocol.stage)
            if stage == "validation":
                exposure = context.policy.validation_exposure
                level = ProposalExposureLevel.VALIDATION_AGGREGATE
            elif stage == "frozen":
                exposure = context.policy.frozen_exposure
                level = ProposalExposureLevel.FROZEN_AGGREGATE
            else:
                continue
            if exposure == HoldoutExposure.NONE:
                continue
            rows.append(_holdout_step_payload(step, exposure, level))
            if len(rows) >= args.max_items:
                break

        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "holdout_steps": rows,
            "validation_exposure": context.policy.validation_exposure.value,
            "frozen_exposure": context.policy.frozen_exposure.value,
            "metrics_file_refs_exposed": False,
        }
        exposure_level = (
            ProposalExposureLevel.VALIDATION_AGGREGATE
            if any(row.get("stage") == "validation" for row in rows)
            else (
                ProposalExposureLevel.FROZEN_AGGREGATE
                if rows
                else ProposalExposureLevel.NONE
            )
        )
        return self._observation(
            context,
            observation_type="holdout_summary",
            summary=f"Returned {len(rows)} exposure-controlled holdout row(s).",
            structured_payload=payload,
            exposure_level=exposure_level,
        )


class FeedbackQueryRuntimeTool(_BaseReadOnlyTool):
    name = "feedback.query_runtime"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        if not context.policy.allow_screening_runtime_raw_read:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.UNSUPPORTED,
                summary="Screening runtime raw read helper is disabled by policy.",
                repair_hint="Enable allow_screening_runtime_raw_read or use screening aggregates.",
            )
        safe_steps = [
            step
            for step in _filter_hypothesis_prompt_steps(list(context.step_history))
            if (not args.branch_id or step.branch_id == args.branch_id)
            and (not args.surface or step.hypothesis.change_locus == args.surface)
        ]
        rendered = _limit_text(
            _build_runtime_feedback(safe_steps, max_items=args.max_items),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        adapter_spec = _get_adapter_problem_spec(context.adapter)
        guidance = _limit_text(
            _build_runtime_failure_guidance(
                safe_steps,
                problem_spec=context.problem_spec,
                adapter_spec=adapter_spec,
                max_items=args.max_items,
                forced_surface=str(context.forced_surface or "").strip() or None,
            ),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "query_scope": {
                "campaign_id": context.campaign_id,
                "branch_filter_applied": bool(args.branch_id),
                "surface_filter_applied": bool(args.surface),
                "recent_first": True,
            },
            "runtime_feedback": rendered,
            "runtime_failure_guidance": guidance,
            "screening_runtime_attribution": [
                attribution
                for attribution in (
                    _surface_runtime_attribution_payload(step)
                    for step in reversed(safe_steps)
                    if (
                        step.protocol_result is not None
                        and step.protocol_result.stage == ExperimentStage.SCREENING
                    )
                )
                if attribution
            ][: args.max_items],
            "research_diagnosis": _research_diagnosis_payload(
                safe_steps,
                max_items=args.max_items,
                problem_spec=context.problem_spec,
            ),
            "screening_only": True,
            "metrics_file_refs_exposed": False,
        }
        payload = _bound_compact_feedback_payload(payload)
        return self._observation(
            context,
            observation_type="runtime_feedback",
            summary=(
                "Returned screening-derived runtime feedback."
                if rendered
                else "No safe screening-derived runtime feedback is available."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
        )


class DraftHypothesisTool(_BaseReadOnlyTool):
    name = "proposal.draft_hypothesis"
    input_schema = DraftHypothesisInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 24000

    def call(
        self,
        args: DraftHypothesisInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        hypothesis = _hypothesis_from_input(args)
        forced_violation = _forced_hypothesis_violation(context, hypothesis)
        if forced_violation is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft violates forced research-surface constraint.",
                structured_payload={
                    "passed": False,
                    "failure_reason": forced_violation,
                    "forced_surface_constraint": _forced_surface_constraint_payload(
                        context
                    ),
                    "hypothesis": _model_payload(hypothesis),
                    "workspace_materialized": False,
                },
                repair_hint="Draft only the forced surface/action/target.",
            )
        schema_result = _hypothesis_schema_preview(context, hypothesis)
        if not schema_result["passed"]:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft failed schema preview.",
                structured_payload=schema_result,
                repair_hint="Repair structured hypothesis fields before drafting.",
            )

        artifact_id = _artifact_id("hypothesis", hypothesis)
        payload = {
            "artifact_kind": "hypothesis_draft",
            "artifact_id": artifact_id,
            "hypothesis": _model_payload(hypothesis),
            "schema_preview": schema_result,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="hypothesis_draft",
            summary="Returned tainted hypothesis draft artifact.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )


class DraftPatchTool(_BaseReadOnlyTool):
    name = "proposal.draft_patch"
    input_schema = DraftPatchInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 80000

    def call(
        self,
        args: DraftPatchInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch = _patch_from_input(args)
        path_error = _patch_path_error(patch.file_path)
        if path_error is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary="Patch draft target path is unsafe.",
                structured_payload={
                    "file_path": patch.file_path,
                    "path_error": path_error,
                    "workspace_materialized": False,
                },
                repair_hint="Use a normalized POSIX path relative to the candidate root.",
            )

        artifact_id = _artifact_id("patch", patch)
        payload = {
            "artifact_kind": "patch_draft",
            "artifact_id": artifact_id,
            "patch": _model_payload(patch),
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="patch_draft",
            summary="Returned tainted patch draft artifact without workspace writes.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )


class SchemaPreviewTool(_BaseReadOnlyTool):
    name = "proposal.schema_preview"
    input_schema = SchemaPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: SchemaPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "workspace_materialized": False,
        }
        if args.hypothesis is None and args.patch is None:
            payload["passed"] = False
            payload["errors"] = ["Provide hypothesis and/or patch payload."]
        if args.hypothesis is not None:
            payload["hypothesis"] = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            payload["passed"] = payload["passed"] and bool(
                payload["hypothesis"]["passed"]
            )
        if args.patch is not None:
            payload["patch"] = _schema_preview_patch_payload(args.patch)
            payload["passed"] = payload["passed"] and bool(payload["patch"]["passed"])
        payload = _drop_internal_preview_objects(payload)
        summary = _schema_preview_summary(payload)

        return self._observation(
            context,
            observation_type="schema_preview",
            summary=summary,
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


def _schema_preview_summary(payload: Mapping[str, Any]) -> str:
    if bool(payload.get("passed")):
        return "Schema preview passed."
    details: list[str] = []
    for section_name in ("hypothesis", "patch"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        reason = section.get("failure_reason")
        if reason:
            details.append(str(reason))
        errors = section.get("errors")
        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, Mapping):
                    loc = ".".join(str(part) for part in error.get("loc", ()) or ())
                    message = error.get("msg") or error.get("message") or error
                    details.append(f"{loc}: {message}" if loc else str(message))
                elif error:
                    details.append(str(error))
    if not details:
        return "Schema preview found issues."
    compact = "; ".join(dict.fromkeys(details))
    return "Schema preview found issues: " + _limit_text(compact, 420)


class TargetPermissionPreviewTool(_BaseReadOnlyTool):
    name = "proposal.target_permission_preview"
    input_schema = TargetPermissionPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: TargetPermissionPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.change_locus)
        declared_targets = _surface_target_files(surface) if surface is not None else []
        allowed_actions = _surface_allowed_actions(surface)
        target_error = None
        if args.target_file:
            target_error = _patch_path_error(args.target_file)

        passed = surface is not None
        issues: list[str] = []
        if surface is None:
            issues.append(f"unknown research surface: {args.change_locus}")
        if args.action not in {"modify", "create_new", "remove"}:
            passed = False
            issues.append(f"invalid hypothesis action: {args.action}")
        elif surface is not None and args.action not in allowed_actions:
            passed = False
            issues.append(
                f"action '{args.action}' is not allowed for surface "
                f"'{args.change_locus}'"
            )
        if args.action in {"modify", "remove"} and not args.target_file:
            passed = False
            issues.append(f"action '{args.action}' requires target_file")
        if target_error is not None:
            passed = False
            issues.append(target_error)
        elif args.target_file and surface is not None:
            if not _target_declared(args.target_file, declared_targets):
                passed = False
                issues.append(
                    f"target_file '{args.target_file}' is not declared for surface "
                    f"'{args.change_locus}'"
                )
        forced_violation = _forced_action_target_violation(
            context,
            change_locus=args.change_locus,
            action=args.action,
            target_file=args.target_file,
        )
        if forced_violation is not None:
            passed = False
            issues.append(forced_violation)
        boundary_violation = _active_problem_boundary_violation(
            context,
            change_locus=args.change_locus,
        )
        if boundary_violation is not None:
            passed = False
            issues.append(boundary_violation)

        payload = {
            "passed": passed,
            "surface": (
                _surface_permission_summary(
                    surface,
                    allowed_actions=allowed_actions,
                    declared_targets=declared_targets,
                )
                if surface is not None
                else None
            ),
            "requested": {
                "change_locus": args.change_locus,
                "action": args.action,
                "target_file": args.target_file,
            },
            "allowed_actions": allowed_actions,
            "declared_targets": declared_targets,
            "forced_surface_constraint": _forced_surface_constraint_payload(context),
            "active_problem_boundary_constraint": (
                _active_problem_boundary_constraint_payload(context)
            ),
            "permission": {
                "surface_known": surface is not None,
                "action_allowed": bool(
                    surface is not None and args.action in allowed_actions
                ),
                "target_required": args.action in {"modify", "remove"},
                "target_path_safe": target_error is None,
                "target_declared": bool(
                    args.target_file
                    and surface is not None
                    and _target_declared(args.target_file, declared_targets)
                ),
            },
            "issues": issues,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="target_permission_preview",
            summary=(
                "Target/action permission preview passed."
                if passed
                else "Target/action permission preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class InterfacePreviewTool(_BaseReadOnlyTool):
    name = "proposal.interface_preview"
    input_schema = InterfacePreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 36000

    def call(
        self,
        args: InterfacePreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch_payload = {
            "file_path": args.file_path,
            "action": args.action,
            "code_content": args.code_content,
        }
        patch_preview = _schema_preview_patch_payload(patch_payload)
        if not patch_preview["passed"]:
            payload = {
                "passed": False,
                "patch_schema": patch_preview,
                "workspace_materialized": False,
            }
            return self._observation(
                context,
                observation_type="interface_preview",
                summary="Interface preview found schema issues.",
                structured_payload=payload,
                exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
            )

        patch = patch_preview["patch_object"]
        gate = _contract_gate(context)
        result = gate.validate_patch(
            patch,
            selected_surface=args.selected_surface,
        )
        interface_checks = [
            check for check in result.checks if check.name == "C7_interface"
        ]
        surface = _surface_for_selected_or_patch_path(
            context,
            patch.file_path,
            args.selected_surface,
        )
        interface_passed = bool(
            interface_checks and all(check.passed for check in interface_checks)
        )
        passed = interface_passed and result.passed
        if not interface_checks:
            passed = False
        problem_preview = None
        if passed:
            problem_preview = _problem_surface_preview(context, patch, surface)
            if problem_preview is not None:
                passed = passed and bool(problem_preview.get("passed"))
        payload = {
            "passed": passed,
            "surface": _surface_payload(surface) if surface is not None else None,
            "required_functions": _surface_required_functions(surface),
            "declared_function_signatures": _surface_function_signatures(surface),
            "declared_return_values": _surface_return_values(surface),
            "present_functions": _module_level_functions(args.code_content),
            "present_classes": _module_classes(args.code_content),
            "checks": _checks_payload(result.checks),
            "problem_preview": problem_preview,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="interface_preview",
            summary=(
                "Interface preview passed."
                if passed
                else "Interface preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class ContractPreviewTool(_BaseReadOnlyTool):
    name = "proposal.contract_preview"
    input_schema = ContractPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 60000

    def call(
        self,
        args: ContractPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "static_only": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
        }
        gate = _contract_gate(context)
        if args.hypothesis is None and args.patch is None:
            payload["passed"] = False
            payload["errors"] = ["Provide hypothesis and/or patch payload."]
        if args.hypothesis is not None:
            hypothesis_preview = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            if hypothesis_preview["passed"]:
                result = gate.validate_hypothesis(
                    hypothesis_preview["hypothesis_object"],
                    [],
                    [],
                    current_champion_version=_champion_version(context.champion),
                )
                hypothesis_preview["contract"] = _contract_summary_payload(result)
                hypothesis_preview["checks"] = _checks_payload(
                    result.checks,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_PREVIEW_MAX_CHECKS,
                )
                hypothesis_preview["passed"] = result.passed
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(hypothesis_preview["passed"])
        if args.patch is not None:
            patch_preview = _schema_preview_patch_payload(args.patch)
            if patch_preview["passed"]:
                hypothesis_object = None
                if (
                    args.hypothesis is not None
                    and payload["hypothesis"] is not None
                    and payload["hypothesis"].get("passed")
                ):
                    hypothesis_object = payload["hypothesis"].get("hypothesis_object")
                result = gate.validate_patch(
                    patch_preview["patch_object"],
                    approved_hypothesis=hypothesis_object,
                )
                contract_payload = _contract_result_payload(
                    result,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_preview_max_checks_for_patch(
                        patch_preview["patch_object"]
                    ),
                )
                patch_preview["contract"] = _contract_summary_payload(result)
                patch_preview["checks"] = contract_payload["checks"]
                patch_preview["passed"] = result.passed
                if result.passed:
                    selected_surface = _hypothesis_selected_surface(hypothesis_object)
                    surface = _surface_for_selected_or_patch_path(
                        context,
                        patch_preview["patch_object"].file_path,
                        selected_surface,
                    )
                    problem_preview = _problem_surface_preview(
                        context,
                        patch_preview["patch_object"],
                        surface,
                    )
                    if problem_preview is not None:
                        patch_preview["problem_preview"] = _compact_problem_preview(
                            problem_preview
                        )
                        patch_preview["passed"] = bool(
                            patch_preview["passed"]
                        ) and bool(problem_preview.get("passed"))
                        payload["static_only"] = False
                if args.hypothesis is None:
                    patch_preview["needs_hypothesis"] = True
                    patch_preview["passed"] = False
                    payload["incomplete"] = True
                    payload["needs_hypothesis"] = True
                else:
                    patch_preview["needs_hypothesis"] = False
            payload["patch"] = patch_preview
            payload["passed"] = payload["passed"] and bool(patch_preview["passed"])
        payload = _drop_internal_preview_objects(payload)
        issue_summary = _contract_preview_issue_summary(payload)
        if issue_summary:
            payload["issue_summary"] = issue_summary
        return self._observation(
            context,
            observation_type="contract_preview",
            summary=(
                "Static contract preview passed."
                if payload["passed"]
                else (
                    "Static contract preview needs an approved hypothesis."
                    if payload.get("needs_hypothesis")
                    else (
                        "Static contract preview found issues: "
                        f"{issue_summary}"
                        if issue_summary
                        else "Static contract preview found issues."
                    )
                )
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


class AlgorithmSmokeTool(_BaseReadOnlyTool):
    name = "proposal.algorithm_smoke"
    input_schema = AlgorithmSmokeInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 60000

    def call(
        self,
        args: AlgorithmSmokeInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "static_contract": None,
            "problem_preview": None,
            "runtime_smoke": None,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
        }
        gate = _contract_gate(context)
        if args.hypothesis is None or args.patch is None:
            payload["passed"] = False
            payload["errors"] = [
                "Provide both approved hypothesis and patch payload for algorithm smoke."
            ]
        hypothesis_object = None
        if args.hypothesis is not None:
            hypothesis_preview = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            if hypothesis_preview["passed"]:
                result = gate.validate_hypothesis(
                    hypothesis_preview["hypothesis_object"],
                    [],
                    [],
                    current_champion_version=_champion_version(context.champion),
                )
                hypothesis_preview["contract"] = _contract_summary_payload(result)
                hypothesis_preview["checks"] = _checks_payload(
                    result.checks,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_PREVIEW_MAX_CHECKS,
                )
                hypothesis_preview["passed"] = result.passed
                if result.passed:
                    hypothesis_object = hypothesis_preview["hypothesis_object"]
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(hypothesis_preview["passed"])

        if args.patch is not None:
            patch_preview = _schema_preview_patch_payload(args.patch)
            if patch_preview["passed"]:
                result = gate.validate_patch(
                    patch_preview["patch_object"],
                    approved_hypothesis=hypothesis_object,
                )
                contract_payload = _contract_result_payload(
                    result,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_preview_max_checks_for_patch(
                        patch_preview["patch_object"]
                    ),
                )
                patch_preview["contract"] = _contract_summary_payload(result)
                patch_preview["checks"] = contract_payload["checks"]
                patch_preview["passed"] = result.passed
                payload["static_contract"] = _contract_summary_payload(result)
                if result.passed and hypothesis_object is not None:
                    selected_surface = _hypothesis_selected_surface(hypothesis_object)
                    surface = _surface_for_selected_or_patch_path(
                        context,
                        patch_preview["patch_object"].file_path,
                        selected_surface,
                    )
                    problem_preview = _problem_surface_preview(
                        context,
                        patch_preview["patch_object"],
                        surface,
                    )
                    if problem_preview is None:
                        problem_preview = {
                            "passed": True,
                            "checks": [],
                            "issues": [],
                            "skipped": True,
                            "workspace_materialized": False,
                            "verification_run": False,
                        }
                    compact_preview = _compact_problem_preview(problem_preview)
                    patch_preview["problem_preview"] = compact_preview
                    payload["problem_preview"] = compact_preview
                    patch_preview["passed"] = bool(patch_preview["passed"]) and bool(
                        problem_preview.get("passed")
                    )
                    if patch_preview["passed"]:
                        smoke_preview = _runtime_algorithm_smoke_preview(
                            context,
                            patch_preview["patch_object"],
                            selected_surface,
                        )
                        if smoke_preview is not None:
                            payload["runtime_smoke"] = smoke_preview
                            patch_preview["runtime_smoke"] = smoke_preview
                            payload["workspace_materialized"] = bool(
                                smoke_preview.get("workspace_materialized")
                            )
                            patch_preview["passed"] = bool(
                                patch_preview["passed"]
                            ) and bool(smoke_preview.get("passed"))
                elif result.passed:
                    patch_preview["passed"] = False
                    patch_preview["needs_hypothesis"] = True
                    payload["needs_hypothesis"] = True
            payload["patch"] = patch_preview
            payload["passed"] = payload["passed"] and bool(patch_preview["passed"])

        payload = _drop_internal_preview_objects(payload)
        issue_summary = _contract_preview_issue_summary(payload)
        if issue_summary:
            payload["issue_summary"] = issue_summary
        return self._observation(
            context,
            observation_type="algorithm_smoke",
            summary=(
                (
                    "Algorithm smoke passed on tainted runtime preview."
                    if payload.get("runtime_smoke")
                    else "Algorithm smoke passed on tainted synthetic preview."
                )
                if payload["passed"]
                else (
                    "Algorithm smoke found issues: "
                    f"{issue_summary}"
                    if issue_summary
                    else "Algorithm smoke found issues."
                )
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


def _runtime_algorithm_smoke_preview(
    context: ProposalToolContext,
    patch: PatchProposal,
    selected_surface: str | None,
) -> dict[str, Any] | None:
    surface_name = str(selected_surface or "").strip()
    if surface_name != "solver_design":
        return None
    patch_paths = [
        _normalize_rel_path(change.file_path) for change in patch_file_changes(patch)
    ]
    if not any(_is_solver_design_runtime_patch_path(path) for path in patch_paths):
        return None

    base_workspace = _runtime_smoke_base_workspace(context)
    canary_rel = str(_attr(context.problem_spec, "canary_case_path", "") or "").strip()
    if base_workspace is None:
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "issues": ["No runnable base workspace found for solver_design smoke."],
        }
    if not canary_rel:
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "issues": ["No canary_case_path configured for solver_design smoke."],
        }

    with tempfile.TemporaryDirectory(prefix="scion_algorithm_smoke_") as tmp:
        workspace = Path(tmp) / "workspace"
        try:
            shutil.copytree(
                base_workspace,
                workspace,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                ),
            )
            _apply_patch_to_runtime_smoke_workspace(workspace, patch)
            smoke_cases, missing_cases = _runtime_smoke_cases(
                workspace=workspace,
                base_workspace=base_workspace,
                canary_rel=canary_rel,
            )
            if not smoke_cases:
                return {
                    "passed": False,
                    "skipped": False,
                    "workspace_materialized": True,
                    "runtime_smoke_run": False,
                    "issues": missing_cases
                    or [f"No runnable smoke case found: {canary_rel}"],
                }
            registry_path = workspace / "registry.yaml"
            if not registry_path.exists():
                registry_path = workspace / "registry.json"
            runs: list[dict[str, Any]] = []
            representative: dict[str, Any] | None = None
            issue: str | None = None
            audit_failure: Mapping[str, Any] | None = None
            for smoke_case in smoke_cases:
                raw, run_payload = _run_solver_design_smoke(
                    workspace=workspace,
                    smoke_case=smoke_case,
                    registry_path=registry_path,
                    selected_surface=surface_name,
                )
                if raw is None:
                    issue = str(run_payload.get("detail") or "solver run failed")
                    representative = {
                        "case": smoke_case.rel_path,
                        "seed": smoke_case.seed,
                        "label": smoke_case.label,
                        "passed": False,
                        "objective": None,
                        "feasible": None,
                        "runtime": {},
                        "run": run_payload,
                    }
                    runs.append(representative)
                    break

                audit_failure = _runtime_smoke_audit_failure(
                    raw,
                    context=context,
                    selected_surface=surface_name,
                )
                runtime = raw.get("runtime") if isinstance(raw, Mapping) else None
                run_result = {
                    "case": smoke_case.rel_path,
                    "seed": smoke_case.seed,
                    "label": smoke_case.label,
                    "passed": audit_failure is None,
                    "objective": raw.get("objective")
                    if isinstance(raw, Mapping)
                    else None,
                    "feasible": raw.get("feasible") if isinstance(raw, Mapping) else None,
                    "runtime": _compact_runtime_smoke_payload(runtime),
                    "run": run_payload,
                }
                if audit_failure is not None:
                    issue = str(audit_failure.get("detail") or "runtime audit failed")
                    run_result["runtime_audit_failure"] = (
                        _compact_runtime_audit_failure(audit_failure)
                    )
                runs.append(run_result)
                if representative is None or audit_failure is not None:
                    representative = run_result
                if audit_failure is not None:
                    break
        except Exception as exc:
            return {
                "passed": False,
                "skipped": False,
                "workspace_materialized": True,
                "runtime_smoke_run": False,
                "issues": [f"runtime smoke setup failed: {type(exc).__name__}: {exc}"],
            }

    representative = representative or {}
    passed = issue is None
    issues = [] if passed else [str(issue)]
    payload = {
        "passed": passed,
        "skipped": False,
        "workspace_materialized": True,
        "runtime_smoke_run": True,
        "selected_surface": surface_name,
        "case": representative.get("case") or canary_rel,
        "seed": representative.get("seed") or _ALGORITHM_SMOKE_DEFAULT_SEED,
        "case_count": len(runs),
        "cases": [
            {
                "label": run.get("label"),
                "case": run.get("case"),
                "seed": run.get("seed"),
                "passed": run.get("passed"),
            }
            for run in runs
        ],
        "time_limit_sec": _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        "objective": representative.get("objective"),
        "feasible": representative.get("feasible"),
        "runtime": representative.get("runtime") or {},
        "issues": issues,
        "run": representative.get("run") or {},
        "runs": runs,
    }
    if audit_failure is not None:
        payload["runtime_audit_failure"] = _compact_runtime_audit_failure(
            audit_failure
        )
    return payload


def _runtime_smoke_base_workspace(context: ProposalToolContext) -> Path | None:
    champion_path = _attr(context.champion, "code_snapshot_path")
    if champion_path:
        path = Path(str(champion_path)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    root_dir = _attr(context.problem_spec, "root_dir")
    if root_dir:
        path = Path(str(root_dir)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    return None


def _is_solver_design_runtime_patch_path(path: str | None) -> bool:
    normalized = str(path or "").replace("\\", "/").lstrip("/")
    return normalized in {
        "policies/baseline_algorithm.py",
        "policies/solver_algorithm.py",
    } or (
        normalized.startswith("policies/baseline_modules/")
        and normalized.endswith(".py")
    )


def _apply_patch_to_runtime_smoke_workspace(
    workspace: Path,
    patch: PatchProposal,
) -> None:
    for change in patch_file_changes(patch):
        _apply_file_change_to_runtime_smoke_workspace(workspace, change)


def _apply_file_change_to_runtime_smoke_workspace(
    workspace: Path,
    change: PatchFileChange,
) -> None:
    rel = normalize_relative_patch_path(change.file_path)
    target = (workspace / rel).resolve(strict=False)
    target.relative_to(workspace.resolve(strict=False))
    action = str(change.action or "modify")
    if action in {"modify", "add", "create", "create_new"}:
        _ensure_runtime_smoke_path_writable(target.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ensure_runtime_smoke_path_writable(target)
        target.write_text(str(change.code_content or ""), encoding="utf-8")
    elif action in {"remove", "delete"}:
        if target.exists():
            _ensure_runtime_smoke_path_writable(target.parent)
            _ensure_runtime_smoke_path_writable(target)
            target.unlink()
    else:
        raise ValueError(f"unsupported patch action for smoke: {action}")


def _ensure_runtime_smoke_path_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    writable_mode = mode | stat.S_IWUSR
    if path.is_dir():
        writable_mode |= stat.S_IXUSR
    if writable_mode != mode:
        path.chmod(writable_mode)


def _runtime_smoke_cases(
    *,
    workspace: Path,
    base_workspace: Path,
    canary_rel: str,
) -> tuple[list[_RuntimeSmokeCase], list[str]]:
    cases: list[_RuntimeSmokeCase] = []
    missing: list[str] = []
    seen: set[tuple[str, int]] = set()

    def add_case(label: str, rel_path: Any, seed: Any) -> None:
        rel = str(rel_path or "").strip()
        if not rel:
            return
        try:
            seed_value = int(seed)
        except (TypeError, ValueError):
            seed_value = _ALGORITHM_SMOKE_DEFAULT_SEED
        key = (rel, seed_value)
        if key in seen:
            return
        seen.add(key)
        instance_path = _resolve_smoke_instance_path(
            workspace=workspace,
            base_workspace=base_workspace,
            case_rel=rel,
        )
        if instance_path is None:
            missing.append(f"{label} smoke case not found: {rel}")
            return
        cases.append(
            _RuntimeSmokeCase(
                label=label,
                rel_path=rel,
                seed=seed_value,
                path=instance_path,
            )
        )

    add_case("canary", canary_rel, _ALGORITHM_SMOKE_DEFAULT_SEED)
    split_payload = _load_runtime_smoke_yaml(
        workspace=workspace,
        base_workspace=base_workspace,
        filename="split_manifest.yaml",
    )
    seed_payload = _load_runtime_smoke_yaml(
        workspace=workspace,
        base_workspace=base_workspace,
        filename="seed_ledger.yaml",
    )
    screening_seed = _first_int(
        seed_payload.get("screening"),
        _ALGORITHM_SMOKE_DEFAULT_SEED,
    )
    for rel in _string_list(split_payload.get("screening"))[
        :_ALGORITHM_SMOKE_MAX_SCREENING_CASES
    ]:
        add_case("screening", rel, screening_seed)
    return cases, missing


def _load_runtime_smoke_yaml(
    *,
    workspace: Path,
    base_workspace: Path,
    filename: str,
) -> Mapping[str, Any]:
    for root in (workspace, base_workspace):
        path = root / filename
        if not path.is_file():
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if isinstance(payload, Mapping):
            return payload
        return {}
    return {}


def _first_int(value: Any, default: int) -> int:
    if isinstance(value, (str, bytes)):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        candidates = []
    for item in candidates:
        try:
            return int(item)
        except (TypeError, ValueError):
            continue
    return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _resolve_smoke_instance_path(
    *,
    workspace: Path,
    base_workspace: Path,
    case_rel: str,
) -> Path | None:
    rel = Path(case_rel)
    candidates = []
    if rel.is_absolute():
        candidates.append(rel)
    else:
        candidates.append(workspace / rel)
        candidates.append(base_workspace / rel)
    for path in candidates:
        if path.is_file():
            return path
    return None


def _run_solver_design_smoke(
    *,
    workspace: Path,
    smoke_case: _RuntimeSmokeCase,
    registry_path: Path,
    selected_surface: str,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner(
        ResourceLimits(timeout_sec=_ALGORITHM_SMOKE_TIMEOUT_SEC, memory_mb=2048)
    )
    result = runner.run_solver(
        workdir=str(workspace),
        instance_path=str(smoke_case.path),
        seed=smoke_case.seed,
        time_limit_sec=_ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        registry_path=str(registry_path),
        selected_surface=selected_surface,
    )
    run_payload = {
        "case": smoke_case.rel_path,
        "seed": smoke_case.seed,
        "label": smoke_case.label,
        "success": result.success,
        "exit_code": result.exit_code,
        "elapsed_ms": result.elapsed_ms,
        "error_category": result.error_category,
        "stdout": _limit_text(result.stdout or "", 800),
        "stderr": _limit_text(result.stderr or "", 800),
    }
    if not result.success or result.output_path is None:
        detail = result.stderr.strip() if result.stderr else "solver run failed"
        run_payload["detail"] = detail
        return None, run_payload
    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        run_payload["detail"] = f"could not read solver output: {exc}"
        return None, run_payload
    run_payload["detail"] = "solver smoke completed"
    return raw, run_payload


def _runtime_smoke_audit_failure(
    raw: Mapping[str, Any],
    *,
    context: ProposalToolContext,
    selected_surface: str,
) -> Mapping[str, Any] | None:
    from scion.runtime.audit import runtime_audit_failure_from_raw

    problem_spec = _problem_spec_for_runtime_audit(context.problem_spec)
    return runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )


def _problem_spec_for_runtime_audit(problem_spec: Any) -> Any:
    if (
        str(_attr(problem_spec, "spec_version", "") or "") == "problem-v1"
        and _attr(problem_spec, "id") is not None
    ):
        return legacy_problem_spec_from_v1(problem_spec)
    return problem_spec


def _compact_runtime_smoke_payload(runtime: Any) -> dict[str, Any]:
    if not isinstance(runtime, Mapping):
        return {}
    keys = (
        "solver_algorithm_path",
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_events",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_search_iterations",
        "solver_algorithm_move_attempts",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_improving_moves",
        "solver_algorithm_neutral_accepted_moves",
        "solver_algorithm_best_improving_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_phase_best_delta",
        "solver_algorithm_phase_improvement_counts",
        "solver_algorithm_stop_reason",
    )
    return {key: runtime.get(key) for key in keys if key in runtime}


def _compact_runtime_audit_failure(value: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "error_category",
        "detail",
        "failed_runtime_fields",
        "solver_algorithm_errors",
        "solver_algorithm_events",
    )
    return {key: value.get(key) for key in keys if key in value}


def _hypothesis_from_input(value: HypothesisProposalInput) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=value.hypothesis_text,
        change_locus=value.change_locus,
        action=value.action,  # type: ignore[arg-type]
        target_file=value.target_file or None,
        predicted_direction=value.predicted_direction,  # type: ignore[arg-type]
        target_weakness=value.target_weakness,
        expected_effect=value.expected_effect,
        suggested_weight=value.suggested_weight,
        target_objectives=tuple(value.target_objectives or ()),
        protected_objectives=tuple(value.protected_objectives or ()),
        objective_tradeoff_policy=value.objective_tradeoff_policy,
        no_op_condition=value.no_op_condition,
        risk_to_higher_priority=value.risk_to_higher_priority,
        target_runtime_effect=value.target_runtime_effect,
        complexity_claim=value.complexity_claim,
        runtime_budget_strategy=value.runtime_budget_strategy,
        novelty_signature=dict(value.novelty_signature or {}),
    )


def _patch_from_input(value: PatchProposalInput) -> PatchProposal:
    return PatchProposal(
        file_path=value.file_path,
        action=value.action,  # type: ignore[arg-type]
        code_content=value.code_content,
        test_hint=value.test_hint or None,
        additional_changes=tuple(
            PatchFileChange(
                file_path=change.file_path,
                action=change.action,  # type: ignore[arg-type]
                code_content=change.code_content,
                test_hint=change.test_hint or None,
            )
            for change in value.additional_changes
        ),
    )


def _schema_preview_hypothesis_payload(
    context: ProposalToolContext,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validated = DraftHypothesisInput.model_validate(dict(raw))
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    hypothesis = _hypothesis_from_input(validated)
    schema_result = _hypothesis_schema_preview(context, hypothesis)
    return {
        **schema_result,
        "hypothesis": _hypothesis_preview_summary(hypothesis),
        "hypothesis_object": hypothesis,
    }


def _hypothesis_preview_summary(
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    novelty_signature = (
        hypothesis.novelty_signature
        if isinstance(hypothesis.novelty_signature, Mapping)
        else {}
    )
    novelty_payload: dict[str, Any] = {}
    for idx, (key, value) in enumerate(
        sorted(novelty_signature.items(), key=lambda item: str(item[0]))
    ):
        if idx >= _PREVIEW_MAX_CHECKS:
            break
        novelty_payload[str(key)] = _compact_preview_value(value)
    return _drop_empty_items(
        {
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_objectives": list(hypothesis.target_objectives),
            "protected_objectives": list(hypothesis.protected_objectives),
            "target_runtime_effect": hypothesis.target_runtime_effect,
            "suggested_weight": hypothesis.suggested_weight,
            "novelty_signature_keys": [
                str(key)
                for key in sorted(novelty_signature.keys(), key=str)[
                    :_PREVIEW_MAX_CHECKS
                ]
            ],
            "novelty_signature": novelty_payload,
            "hypothesis_text_chars": len(hypothesis.hypothesis_text or ""),
            "expected_effect_chars": len(hypothesis.expected_effect or ""),
            "runtime_budget_strategy_chars": len(
                hypothesis.runtime_budget_strategy or ""
            ),
        }
    )


def _compact_preview_value(value: Any, *, max_chars: int = 160) -> Any:
    value = _strip_forbidden_value(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _limit_text(value, max_chars)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for idx, (key, item) in enumerate(
            sorted(value.items(), key=lambda pair: str(pair[0]))
        ):
            if idx >= _COMPACT_FEEDBACK_LIST_ITEMS:
                break
            compact[str(key)] = _compact_preview_value(item, max_chars=max_chars)
        return compact
    if isinstance(value, (list, tuple)):
        return [
            _compact_preview_value(item, max_chars=max_chars)
            for item in list(value)[:_COMPACT_FEEDBACK_LIST_ITEMS]
        ]
    return _limit_text(str(value), max_chars)


def _schema_preview_patch_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validated = DraftPatchInput.model_validate(dict(raw))
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    patch = _patch_from_input(validated)
    path_errors = []
    for index, change in enumerate(patch_file_changes(patch)):
        path_error = _patch_path_error(change.file_path)
        if path_error is not None:
            loc = ("file_path",) if index == 0 else (
                "additional_changes",
                index - 1,
                "file_path",
            )
            path_errors.append({"loc": loc, "msg": path_error})
    patch_summary = _patch_preview_summary(patch)
    if path_errors:
        return {
            "passed": False,
            "errors": path_errors,
            "patch": patch_summary,
        }
    return {
        "passed": True,
        "errors": [],
        "patch": patch_summary,
        "patch_object": patch,
    }


def _hypothesis_schema_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    result = _contract_gate(context).validate_hypothesis(
        hypothesis,
        [],
        [],
        current_champion_version=_champion_version(context.champion),
    )
    c1_checks = [check for check in result.checks if check.name == "C1_schema"]
    novelty_guidance = _semantic_signature_preview_guidance(context, hypothesis)
    passed = bool(c1_checks and all(check.passed for check in c1_checks))
    forced_violation = _forced_hypothesis_violation(context, hypothesis)
    if forced_violation is not None:
        passed = False
    if novelty_guidance.get("required") and (
        novelty_guidance.get("missing_fields")
        or novelty_guidance.get("invalid_fields")
    ):
        passed = False
    return {
        "passed": passed,
        "checks": _checks_payload(
            c1_checks,
            detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
            max_checks=4,
        ),
        "failure_reason": (
            None
            if passed
            else (
                forced_violation
                if forced_violation is not None
                else (
                    novelty_guidance.get("detail")
                    if (
                        novelty_guidance.get("missing_fields")
                        or novelty_guidance.get("invalid_fields")
                    )
                    else _limit_text(
                        _first_failure(c1_checks) or "", _PREVIEW_FAILURE_REASON_CHARS
                    )
                )
            )
        ),
        "forced_surface_constraint": _forced_surface_constraint_payload(context),
        "novelty_signature_guidance": novelty_guidance,
    }


def _semantic_signature_preview_guidance(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    surface = _surface_for_hypothesis(context, hypothesis)
    novelty = _attr(surface, "novelty") if surface is not None else None
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}

    missing: list[str] = []
    invalid: list[str] = []
    unsupported: list[str] = []
    for field in fields:
        name = str(field).strip()
        if not name:
            continue
        if not ContractGate.supports_semantic_signature_field(name):
            unsupported.append(name)
            continue
        if name in {"predicted_direction", "target_objectives", "protected_objectives"}:
            value = getattr(hypothesis, name, None)
            if value in (None, "", [], (), {}):
                missing.append(name)
            continue
        values = hypothesis.novelty_signature
        if (
            not isinstance(values, dict)
            or name not in values
            or _semantic_signature_value_missing(values[name])
        ):
            missing.append(name)
            continue
        if (
            name in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            and not _is_nonempty_text_sequence(values[name])
        ):
            invalid.append(name)
        if (
            isinstance(values.get(name), str)
            and len(values[name].strip()) > _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS
        ):
            invalid.append(f"{name} > {_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} chars")

    detail = ""
    if missing:
        detail = (
            "missing structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(missing)}"
        )
    elif invalid:
        detail = (
            "invalid structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(invalid)} must be "
            "non-empty arrays of component names"
        )
    elif unsupported:
        detail = (
            "unsupported novelty.signature_fields for semantic_signature surface "
            f"'{hypothesis.change_locus}': {', '.join(unsupported)}"
        )
    else:
        detail = (
            "semantic_signature identity is present; contract preview/C10 will "
            "still reject duplicate structured values."
        )
    return _drop_empty_items(
        {
            "required": True,
            "strategy": strategy,
            "signature_fields": fields,
            "missing_fields": missing,
            "invalid_fields": invalid,
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "unsupported_fields": unsupported,
            "detail": detail,
        }
    )


def _semantic_signature_value_missing(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False


def _is_nonempty_text_sequence(value: Any) -> bool:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        return False
    return all(isinstance(item, str) and bool(item.strip()) for item in value)


def _contract_gate(context: ProposalToolContext) -> ContractGate:
    spec = _contract_problem_spec(context)
    return ContractGate(
        spec,
        operator_execute_signature=_operator_execute_signature(context),
    )


def _contract_problem_spec(context: ProposalToolContext) -> Any:
    spec = _get_adapter_problem_spec(context.adapter) or context.problem_spec
    if spec is None:
        raise ValueError("proposal tool context has no problem_spec")
    if hasattr(spec, "operator_categories"):
        return spec
    if _attr(spec, "spec_version") == "problem-v1" or hasattr(
        spec, "operator_interface"
    ):
        return legacy_problem_spec_from_v1(spec)
    return spec


def _operator_execute_signature(context: ProposalToolContext) -> str | None:
    adapter_spec = _get_adapter_problem_spec(context.adapter)
    for spec in (adapter_spec, context.problem_spec):
        operator_interface = _attr(spec, "operator_interface")
        execute_signature = _attr(operator_interface, "execute_signature")
        if execute_signature:
            return str(execute_signature)
    return None


def _contract_result_payload(
    result: ContractResult,
    *,
    detail_chars: int = 2000,
    max_checks: int | None = None,
) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failure_reason": (
            _limit_text(
                str(result.failure_reason or ""),
                max(detail_chars, _PREVIEW_FAILURE_REASON_CHARS),
            )
            if result.failure_reason
            else None
        ),
        "checks": _checks_payload(
            result.checks,
            detail_chars=detail_chars,
            max_checks=max_checks,
        ),
    }


def _preview_max_checks_for_patch(patch: PatchProposal) -> int:
    return _PREVIEW_MAX_CHECKS * max(1, len(patch_file_changes(patch)))


def _contract_summary_payload(result: ContractResult) -> dict[str, Any]:
    failed_checks = [
        str(_attr(check, "name"))
        for check in result.checks
        if not bool(_attr(check, "passed"))
    ]
    return _drop_empty_items(
        {
            "passed": result.passed,
            "failure_reason": (
                _limit_text(
                    str(result.failure_reason or ""),
                    _PREVIEW_FAILURE_REASON_CHARS,
                )
                if result.failure_reason
                else None
            ),
            "check_count": len(result.checks),
            "failed_checks": failed_checks[:_PREVIEW_MAX_CHECKS],
        }
    )


def _contract_preview_issue_summary(payload: Mapping[str, Any]) -> str:
    issues = _contract_preview_issue_strings(payload)
    if not issues:
        return ""
    return "; ".join(issues[:5])


def _contract_preview_issue_strings(value: Any) -> list[str]:
    issues: list[str] = []

    def add(text: Any) -> None:
        item = _limit_text(str(text or "").strip(), 240)
        if item and item not in issues:
            issues.append(item)

    def visit(item: Any, *, context: str = "") -> None:
        if isinstance(item, Mapping):
            failure_reason = item.get("failure_reason")
            if failure_reason:
                add(f"{context}: {failure_reason}" if context else failure_reason)
            for key in ("errors", "issues"):
                raw_values = item.get(key)
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
            name = item.get("name")
            if name and item.get("passed") is False:
                detail = item.get("detail")
                add(f"{name}: {detail}" if detail else name)
            contract = item.get("contract")
            if isinstance(contract, Mapping):
                failed_checks = contract.get("failed_checks")
                if isinstance(failed_checks, list):
                    for check_name in failed_checks:
                        add(check_name)
            for key, child in item.items():
                key_text = str(key)
                next_context = key_text if key_text in {"hypothesis", "patch"} else context
                if key_text in {"hypothesis_object", "patch_object", "code_content"}:
                    continue
                visit(child, context=next_context)
        elif isinstance(item, list):
            for child in item:
                visit(child, context=context)

    visit(value)
    return issues


def _checks_payload(
    checks: Any,
    *,
    detail_chars: int = 2000,
    max_checks: int | None = None,
) -> list[dict[str, Any]]:
    check_list = list(checks)
    if max_checks is not None:
        check_list = check_list[:max_checks]
    return [
        {
            "name": _attr(check, "name"),
            "passed": bool(_attr(check, "passed")),
            "severity": _attr(check, "severity"),
            "detail": _limit_text(str(_attr(check, "detail", "")), detail_chars),
            "elapsed_ms": _attr(check, "elapsed_ms"),
        }
        for check in check_list
    ]


def _first_failure(checks: Any) -> str | None:
    for check in checks:
        if not _attr(check, "passed"):
            return f"{_attr(check, 'name')}: {_attr(check, 'detail')}"
    return None


def _drop_internal_preview_objects(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _drop_internal_preview_objects(item)
            for key, item in value.items()
            if str(key) not in {"hypothesis_object", "patch_object"}
        }
    if isinstance(value, list):
        return [_drop_internal_preview_objects(item) for item in value]
    return value


def _patch_path_error(file_path: str) -> str | None:
    try:
        normalize_relative_patch_path(file_path)
    except ValueError as exc:
        return str(exc)
    return None


def _surface_allowed_actions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    targets = _attr(surface, "targets")
    allowed = []
    action_attrs = (
        ("create_new", "create_new_allowed"),
        ("modify", "modify_allowed"),
        ("remove", "remove_allowed"),
    )
    for action, attr in action_attrs:
        value = _attr(targets, attr, _attr(surface, attr, True))
        if value:
            allowed.append(action)
    return allowed


def _surface_permission_summary(
    surface: Any,
    *,
    allowed_actions: list[str],
    declared_targets: list[str],
) -> dict[str, Any]:
    return {
        "name": _attr(surface, "name"),
        "kind": _attr(surface, "kind"),
        "allowed_actions": list(allowed_actions),
        "declared_targets": list(declared_targets),
    }


def _patch_preview_summary(patch: PatchProposal) -> dict[str, Any]:
    code_content = str(patch.code_content or "")
    additional = [
        _patch_file_change_preview_summary(change)
        for change in patch_file_changes(patch)[1:]
    ]
    return {
        "file_path": patch.file_path,
        "action": patch.action,
        "code_char_count": len(code_content),
        "code_digest": hashlib.sha256(code_content.encode("utf-8")).hexdigest(),
        "functions": _module_level_functions(code_content),
        "classes": _module_classes(code_content),
        "additional_change_count": len(additional),
        "additional_changes": additional,
        "checks": [],
    }


def _patch_file_change_preview_summary(change: PatchFileChange) -> dict[str, Any]:
    code_content = str(change.code_content or "")
    return {
        "file_path": change.file_path,
        "action": change.action,
        "code_char_count": len(code_content),
        "code_digest": hashlib.sha256(code_content.encode("utf-8")).hexdigest(),
        "functions": _module_level_functions(code_content),
        "classes": _module_classes(code_content),
    }


def _compact_problem_preview(
    preview: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if preview is None:
        return None
    return {
        "passed": bool(preview.get("passed")),
        "surface": preview.get("surface"),
        "issues": _problem_preview_issues(preview),
        "checks": _compact_problem_preview_checks(preview.get("checks")),
        "workspace_materialized": bool(preview.get("workspace_materialized", False)),
        "verification_run": bool(preview.get("verification_run", False)),
    }


def _problem_preview_issues(preview: Mapping[str, Any]) -> list[str]:
    issues = preview.get("issues", [])
    if isinstance(issues, str):
        values = [issues]
    else:
        try:
            values = [str(issue) for issue in issues if str(issue)]
        except TypeError:
            values = []
    return [
        _limit_text(issue, _PREVIEW_PROBLEM_ISSUE_CHARS)
        for issue in values[:_PREVIEW_PROBLEM_MAX_CHECKS]
    ]


def _compact_problem_preview_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    checks: list[dict[str, Any]] = []
    for item in value[:_PREVIEW_PROBLEM_MAX_CHECKS]:
        if not isinstance(item, Mapping):
            continue
        checks.append(
            {
                "name": item.get("name"),
                "passed": bool(item.get("passed")),
                "detail": _limit_text(
                    str(item.get("detail", "")),
                    _PREVIEW_PROBLEM_ISSUE_CHARS,
                ),
            }
        )
    return checks


def _surface_required_functions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    interface = _attr(surface, "interface")
    required = _attr(interface, "required_functions", None)
    if required is None:
        required = _attr(surface, "required_functions", [])
    return [str(name) for name in (required or [])]


def _surface_function_signatures(surface: Any | None) -> dict[str, list[str]]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    signatures = _attr(interface, "function_signatures", None)
    if not isinstance(signatures, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_args in signatures.items():
        name = str(raw_name).strip()
        if not name:
            continue
        if isinstance(raw_args, str):
            args = [arg.strip() for arg in raw_args.split(",") if arg.strip()]
        else:
            try:
                args = [str(arg).strip() for arg in raw_args if str(arg).strip()]
            except TypeError:
                args = []
        normalized[name] = args
    return normalized


def _surface_return_values(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    values = _attr(interface, "return_values", None) if interface is not None else None
    if not isinstance(values, Mapping):
        return {}
    return _compact_mapping_payload(values)


def _surface_for_patch_path(
    context: ProposalToolContext,
    file_path: str,
) -> Any | None:
    normalized = _normalize_rel_path(file_path)
    if normalized is None:
        return None
    for surface in _surfaces(context):
        if _target_declared(normalized, _surface_target_files(surface)):
            return surface
    return None


def _surface_for_hypothesis(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> Any | None:
    surface = _find_surface(context, hypothesis.change_locus)
    if surface is not None:
        return surface
    if hypothesis.target_file:
        return _surface_for_patch_path(context, hypothesis.target_file)
    return None


def _forced_surface_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surface = str(context.forced_surface or "").strip()
    if not surface:
        return None
    return _drop_empty_items(
        {
            "surface": surface,
            "action": str(context.forced_action or "").strip() or None,
            "target_file": str(context.forced_target_file or "").strip() or None,
            "rule": (
                "Hypothesis outputs and proposal previews must use exactly this "
                "research surface"
                + (", action" if context.forced_action else "")
                + (", and target_file" if context.forced_target_file else "")
                + ". Off-surface hypotheses fail closed before code generation."
            ),
        }
    )


def _active_problem_boundary_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surfaces = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not surfaces:
        return None
    novelty_requirements = _active_boundary_novelty_requirements(context, surfaces)
    return {
        "surfaces": surfaces,
        "rule": (
            "Hypothesis outputs must keep change_locus on the active "
            "problem-object boundary. Component policies may appear only as "
            "implementation hooks or attribution evidence, not replacement "
            "research goals."
        ),
        "novelty_signature_requirements": novelty_requirements,
    }


def _active_boundary_novelty_requirements(
    context: ProposalToolContext,
    surfaces: list[str],
) -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    for surface_name in surfaces:
        surface = _find_surface(context, surface_name)
        requirement = _surface_novelty_signature_requirement(surface)
        if requirement:
            requirements[surface_name] = requirement
    return requirements


def _surface_novelty_signature_requirement(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    novelty = _attr(surface, "novelty")
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}
    return _drop_empty_items(
        {
            "strategy": strategy,
            "required_fields": fields,
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "rule": (
                "Provide every required novelty_signature field. Fields listed "
                "under nonempty_sequence_fields must be non-empty arrays of "
                "component names, not null, false, empty strings, or empty arrays. "
                "Scalar string values must be at most "
                f"{_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} characters."
            ),
        }
    )


def _forced_hypothesis_violation(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> str | None:
    forced = _forced_action_target_violation(
        context,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        target_file=hypothesis.target_file,
    )
    if forced is not None:
        return forced
    return _active_problem_boundary_violation(
        context,
        change_locus=hypothesis.change_locus,
    )


def _active_problem_boundary_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
) -> str | None:
    if context.forced_surface:
        return None
    boundary = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not boundary:
        return None
    actual = str(change_locus or "").strip()
    if actual in set(boundary):
        return None
    return (
        "active_problem_boundary_constraint: change_locus must stay within "
        f"{boundary!r}; got {actual!r}. Component policies are implementation "
        "hooks or attribution evidence, not replacement research goals."
    )


def _forced_action_target_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
    action: str | None,
    target_file: str | None,
) -> str | None:
    forced_surface = str(context.forced_surface or "").strip()
    if not forced_surface:
        return None
    actual_surface = str(change_locus or "").strip()
    if actual_surface != forced_surface:
        return (
            "forced_surface_constraint: change_locus must be "
            f"{forced_surface!r}, got {actual_surface!r}"
        )
    forced_action = str(context.forced_action or "").strip()
    if forced_action and str(action or "").strip() != forced_action:
        return (
            "forced_surface_constraint: action must be "
            f"{forced_action!r}, got {str(action or '').strip()!r}"
        )
    forced_target = str(context.forced_target_file or "").strip()
    if forced_target:
        actual_target = str(target_file or "").strip()
        if _normalize_rel_path(actual_target) != _normalize_rel_path(forced_target):
            return (
                "forced_surface_constraint: target_file must be "
                f"{forced_target!r}, got {actual_target!r}"
            )
    return None


def _surface_for_selected_or_patch_path(
    context: ProposalToolContext,
    file_path: str,
    selected_surface: str | None,
) -> Any | None:
    selected = str(selected_surface or "").strip()
    if selected:
        surface = _find_surface(context, selected)
        if surface is not None:
            return surface
    return _surface_for_patch_path(context, file_path)


def _hypothesis_selected_surface(
    hypothesis: HypothesisProposal | None,
) -> str | None:
    if hypothesis is None:
        return None
    value = str(getattr(hypothesis, "change_locus", "") or "").strip()
    return value or None


def _problem_surface_preview(
    context: ProposalToolContext,
    patch: PatchProposal,
    surface: Any | None,
) -> dict[str, Any] | None:
    adapter = context.adapter
    preview = getattr(adapter, "preview_research_surface_patch", None)
    if not callable(preview):
        return None
    try:
        payload = preview(patch=patch, surface=surface)
    except Exception as exc:
        return {
            "passed": False,
            "issues": [f"problem preview hook failed: {exc}"],
            "workspace_materialized": False,
            "verification_run": False,
        }
    if not isinstance(payload, Mapping):
        return {
            "passed": False,
            "issues": ["problem preview hook returned non-mapping payload"],
            "workspace_materialized": False,
            "verification_run": False,
        }
    normalized = dict(payload)
    normalized.setdefault("passed", False)
    normalized.setdefault("workspace_materialized", False)
    normalized.setdefault("verification_run", False)
    return normalized


def _module_level_functions(code_content: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        return []
    return [
        node.name
        for node in getattr(tree, "body", [])
        if isinstance(node, ast.FunctionDef)
    ]


def _module_classes(code_content: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        return []
    return [
        node.name
        for node in getattr(tree, "body", [])
        if isinstance(node, ast.ClassDef)
    ]


def _artifact_id(kind: str, value: Any) -> str:
    payload = json.dumps(_model_payload(value), sort_keys=True, default=str)
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"{kind}:{payload}").hex[:16]
    return f"{kind}-{digest}"


def _champion_version(champion: ChampionState | None) -> int:
    return int(_attr(champion, "version", 0) or 0)


def _surfaces(context: ProposalToolContext) -> list[Any]:
    adapter_spec = _get_adapter_problem_spec(context.adapter)
    return _get_research_surfaces(context.problem_spec, adapter_spec)


def _surface_list_for_context(
    context: ProposalToolContext,
    surfaces: list[Any],
) -> list[Any]:
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface:
        constrained = [
            surface
            for surface in surfaces
            if str(_attr(surface, "name") or "").strip() == forced_surface
        ]
        return constrained or surfaces
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    if not boundary:
        return surfaces
    constrained = [
        surface
        for surface in surfaces
        if str(_attr(surface, "name") or "").strip() in boundary
    ]
    return constrained or surfaces


def _find_surface(context: ProposalToolContext, name: str) -> Any | None:
    for surface in _surfaces(context):
        if _attr(surface, "name") == name:
            return surface
    return None


def _surface_name(surface: Any) -> str:
    return str(_attr(surface, "name") or "").strip()


def _problem_summary(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_problem_summary"
    ):
        return str(context.adapter.render_problem_summary())
    spec = context.problem_spec
    if spec is None:
        return ""
    if hasattr(spec, "name") and hasattr(spec, "operator_categories"):
        return _build_problem_summary(spec, adapter=context.adapter)
    lines = []
    display = _attr(spec, "display_name") or _attr(spec, "name") or _attr(spec, "id")
    if display:
        lines.append(f"Name: {display}")
    description = _attr(spec, "description")
    if description:
        lines.append(f"Description: {description}")
    surfaces = _surfaces(context)
    if surfaces:
        lines.append(
            "Research loci: "
            + ", ".join(str(_attr(surface, "name")) for surface in surfaces)
        )
    search_space = _attr(spec, "search_space")
    editable = _attr(search_space, "editable", [])
    frozen = _attr(search_space, "frozen", [])
    if editable:
        lines.append("Editable files: " + ", ".join(str(v) for v in editable))
    if frozen:
        lines.append(
            "Frozen files (do not modify): " + ", ".join(str(v) for v in frozen)
        )
    return "\n".join(lines)


def _problem_object(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_problem_object"
    ):
        return str(context.adapter.render_problem_object())
    return ""


def _solver_mechanics(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(
        context.adapter, "render_solver_mechanics"
    ):
        return str(context.adapter.render_solver_mechanics())
    return ""


def _surface_payload(surface: Any) -> dict[str, Any]:
    payload = _model_payload(surface)
    payload.setdefault("name", _attr(surface, "name"))
    payload.setdefault("kind", _attr(surface, "kind"))
    payload.setdefault("description", _attr(surface, "description", ""))
    return payload


def _surface_listing_payload(surface: Any) -> dict[str, Any]:
    target_files = _surface_target_files(surface)
    algorithm = _attr(surface, "algorithm")
    bounds = _attr(surface, "bounds")
    targets = _attr(surface, "targets")
    return _drop_empty_items(
        {
            "name": _attr(surface, "name"),
            "kind": _attr(surface, "kind"),
            "description": _compact_text(_attr(surface, "description", ""), 240),
            "algorithm": _drop_empty_items(
                {
                    "role": _attr(algorithm, "role") if algorithm is not None else None,
                    "invocation_point": (
                        _attr(algorithm, "invocation_point")
                        if algorithm is not None
                        else None
                    ),
                }
            ),
            "targets": _drop_empty_items(
                {
                    "files": target_files,
                    "allowed_actions": _surface_allowed_actions(surface),
                    "singleton": _attr(targets, "singleton"),
                }
            ),
            "target_files": target_files,
            "interface": _drop_empty_items(
                {"required_functions": _surface_required_functions(surface)}
            ),
            "bounds": _drop_empty_items(
                {
                    "allowed_components": _coerce_compact_list(
                        _attr(bounds, "allowed_components", [])
                        if bounds is not None
                        else []
                    ),
                    "numeric_ranges": _model_payload(
                        _attr(bounds, "numeric_ranges", {})
                        if bounds is not None
                        else {}
                    ),
                }
            ),
        }
    )


def _surface_read_payload(
    surface: Any,
    *,
    detail: str,
    section: str = "all",
) -> dict[str, Any]:
    if detail == "full":
        return _surface_payload(surface)
    return _surface_compact_payload(surface, section=section)


def _surface_compact_payload(surface: Any, *, section: str = "all") -> dict[str, Any]:
    target_files = _surface_target_files(surface)
    payload: dict[str, Any] = {
        "name": _attr(surface, "name"),
        "kind": _attr(surface, "kind"),
        "section": section,
    }
    if section in {"all", "summary"}:
        payload.update(
            {
                "description": _compact_text(_attr(surface, "description", "")),
                "algorithm": _compact_algorithm_payload(surface),
                "targets": _compact_targets_payload(surface, target_files),
                "target_files": target_files,
            }
        )
        prompt_hint = _compact_text(
            _attr(surface, "prompt_hint", ""),
            _COMPACT_SURFACE_HINT_CHARS,
        )
        if prompt_hint:
            payload["prompt_hint"] = prompt_hint
    if section in {"all", "interface"}:
        payload["interface"] = _compact_interface_payload(surface)
    if section in {"all", "bounds"}:
        payload["bounds"] = _compact_bounds_payload(surface)
    if section in {"all", "evidence"}:
        payload["evidence"] = _compact_evidence_payload(surface)
    if section in {"all", "novelty"}:
        payload["novelty"] = _compact_novelty_payload(surface)
    if section == "target_preview":
        payload["targets"] = _compact_targets_payload(surface, target_files)
        payload["target_files"] = target_files
    return _drop_empty_items(payload)


def _compact_algorithm_payload(surface: Any) -> dict[str, Any]:
    algorithm = _attr(surface, "algorithm")
    if algorithm is None:
        return {}
    return _drop_empty_items(
        {
            "role": _attr(algorithm, "role"),
            "invocation_point": _attr(algorithm, "invocation_point"),
            "description": _compact_text(_attr(algorithm, "description", "")),
        }
    )


def _compact_targets_payload(
    surface: Any,
    target_files: list[str],
) -> dict[str, Any]:
    targets = _attr(surface, "targets")
    return _drop_empty_items(
        {
            "files": target_files,
            "create_new_allowed": _attr(
                targets,
                "create_new_allowed",
                _attr(surface, "create_new_allowed"),
            ),
            "modify_allowed": _attr(
                targets,
                "modify_allowed",
                _attr(surface, "modify_allowed"),
            ),
            "remove_allowed": _attr(
                targets,
                "remove_allowed",
                _attr(surface, "remove_allowed"),
            ),
            "singleton": _attr(targets, "singleton"),
            "allowed_actions": _surface_allowed_actions(surface),
        }
    )


def _compact_interface_payload(surface: Any) -> dict[str, Any]:
    interface = _attr(surface, "interface")
    return _drop_empty_items(
        {
            "required_functions": _surface_required_functions(surface),
            "function_signatures": _surface_function_signatures(surface),
            "return_contract": _compact_text(
                _attr(interface, "return_contract", "") if interface is not None else ""
            ),
            "return_values": _surface_return_values(surface),
        }
    )


def _compact_bounds_payload(surface: Any) -> dict[str, Any]:
    bounds = _attr(surface, "bounds")
    if bounds is None:
        return {}
    return _drop_empty_items(
        {
            "allowed_components": _coerce_compact_list(
                _attr(bounds, "allowed_components", [])
            ),
            "numeric_ranges": _compact_mapping_payload(
                _attr(bounds, "numeric_ranges", {})
            ),
            "complexity_scale_terms": _coerce_compact_list(
                _attr(bounds, "complexity_scale_terms", [])
            ),
        }
    )


def _compact_evidence_payload(surface: Any) -> dict[str, Any]:
    evidence = _attr(surface, "evidence")
    if evidence is None:
        return {}
    return _drop_empty_items(
        {
            "required_runtime_fields": _coerce_compact_list(
                _attr(evidence, "required_runtime_fields", [])
            )
        }
    )


def _compact_novelty_payload(surface: Any) -> dict[str, Any]:
    novelty = _attr(surface, "novelty")
    if novelty is None:
        return {}
    return _drop_empty_items(
        {
            "strategy": _attr(novelty, "strategy"),
            "signature_fields": _coerce_compact_list(
                _attr(novelty, "signature_fields", [])
            ),
        }
    )


def _surface_contract_metadata(
    surface: Any,
    *,
    detail: str,
    section: str,
    current_artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "schema_version": "surface-contract.v1",
        "detail": detail,
        "section": section,
        "available_sections": list(_COMPACT_SURFACE_SECTIONS),
        "cap": {
            "text_chars_per_field": _COMPACT_SURFACE_TEXT_CHARS,
            "hint_chars": _COMPACT_SURFACE_HINT_CHARS,
            "list_items_per_field": _COMPACT_SURFACE_LIST_ITEMS,
            "map_items_per_field": _COMPACT_SURFACE_MAP_ITEMS,
        },
        "omitted_from_compact": [
            "prompt.hypothesis_guidance",
            "prompt.implementation_guidance",
            "prompt.anti_patterns",
            "full_target_file_content",
        ],
    }
    if detail == "compact":
        contract["section_paths"] = _surface_section_paths(section)
        target_preview = _target_artifact_preview(current_artifact)
        if target_preview:
            contract["target_preview"] = target_preview
    return _drop_empty_items(contract)


def _surface_section_paths(section: str) -> dict[str, list[str]]:
    sections = {
        "summary": [
            "surface.description",
            "surface.algorithm",
            "surface.targets",
            "surface.prompt_hint",
        ],
        "interface": ["surface.interface"],
        "bounds": ["surface.bounds"],
        "evidence": ["surface.evidence"],
        "novelty": ["surface.novelty"],
        "target_preview": ["surface_contract.target_preview", "current_artifact"],
    }
    if section == "all":
        return sections
    selected = sections.get(section, [])
    return {section: selected}


def _target_artifact_preview(
    current_artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not current_artifact:
        return {}
    return _drop_empty_items(
        {
            "file_path": current_artifact.get("file_path"),
            "readable": current_artifact.get("readable"),
            "reason": current_artifact.get("reason"),
            "size_chars": current_artifact.get("size_chars"),
            "content_preview_chars": len(
                str(current_artifact.get("content_preview", ""))
            ),
            "truncated": current_artifact.get("truncated"),
            "max_chars": current_artifact.get("max_chars"),
        }
    )


def _surface_interface_summary(
    surface: Any,
    *,
    detail: str,
    section: str = "all",
) -> str:
    if detail == "full":
        return _build_research_surface_interface_spec(surface)
    return _compact_surface_interface_summary(surface, section=section)


def _compact_surface_interface_summary(surface: Any, *, section: str = "all") -> str:
    compact = _surface_compact_payload(surface, section=section)
    lines = [
        (
            f"### Declared Research Surface: {compact.get('name', '')} "
            f"[{compact.get('kind', '')}]"
        )
    ]
    lines.append(
        "compact_contract_sections: "
        + ", ".join([section] if section != "all" else list(_COMPACT_SURFACE_SECTIONS))
    )
    description = compact.get("description")
    if description:
        lines.append(str(description))
    algorithm = compact.get("algorithm")
    if isinstance(algorithm, Mapping):
        _append_compact_summary_line(lines, "algorithm.role", algorithm.get("role"))
        _append_compact_summary_line(
            lines,
            "algorithm.invocation_point",
            algorithm.get("invocation_point"),
        )
        _append_compact_summary_line(
            lines,
            "algorithm.description",
            algorithm.get("description"),
        )
    targets = compact.get("targets")
    if isinstance(targets, Mapping):
        _append_compact_summary_line(lines, "targets.files", targets.get("files"))
        _append_compact_summary_line(
            lines,
            "targets.allowed_actions",
            targets.get("allowed_actions"),
        )
        _append_compact_summary_line(
            lines,
            "targets.singleton",
            targets.get("singleton"),
        )
    interface = compact.get("interface")
    if isinstance(interface, Mapping):
        _append_compact_summary_line(
            lines,
            "interface.required_functions",
            interface.get("required_functions"),
        )
        _append_compact_summary_line(
            lines,
            "interface.function_signatures",
            interface.get("function_signatures"),
        )
        _append_compact_summary_line(
            lines,
            "interface.return_contract",
            interface.get("return_contract"),
        )
        _append_compact_summary_line(
            lines,
            "interface.return_values",
            interface.get("return_values"),
        )
    bounds = compact.get("bounds")
    if isinstance(bounds, Mapping):
        _append_compact_summary_line(
            lines,
            "bounds.allowed_components",
            bounds.get("allowed_components"),
        )
        _append_compact_summary_line(
            lines,
            "bounds.numeric_ranges",
            bounds.get("numeric_ranges"),
        )
        _append_compact_summary_line(
            lines,
            "bounds.complexity_scale_terms",
            bounds.get("complexity_scale_terms"),
        )
    evidence = compact.get("evidence")
    if isinstance(evidence, Mapping):
        _append_compact_summary_line(
            lines,
            "evidence.required_runtime_fields",
            evidence.get("required_runtime_fields"),
        )
    novelty = compact.get("novelty")
    if isinstance(novelty, Mapping):
        _append_compact_summary_line(
            lines,
            "novelty.strategy",
            novelty.get("strategy"),
        )
        _append_compact_summary_line(
            lines,
            "novelty.signature_fields",
            novelty.get("signature_fields"),
        )
    _append_compact_summary_line(lines, "prompt_hint", compact.get("prompt_hint"))
    return _limit_text("\n".join(lines), _COMPACT_SURFACE_INTERFACE_CHARS)


def _append_compact_summary_line(
    lines: list[str],
    label: str,
    value: Any,
) -> None:
    if value in (None, "", [], {}):
        return
    if isinstance(value, (Mapping, list, tuple)):
        rendered = json.dumps(_model_payload(value), sort_keys=True, default=str)
    else:
        rendered = str(value)
    lines.append(f"{label}: {_compact_text(rendered)}")


def _surface_code_char_limit(
    *,
    detail: str,
    requested_max: int | None,
) -> int:
    if requested_max is not None:
        return requested_max
    if detail == "full":
        return _FULL_SURFACE_CODE_CHARS
    return _COMPACT_SURFACE_CODE_CHARS


def _compact_text(value: Any, max_chars: int = _COMPACT_SURFACE_TEXT_CHARS) -> str:
    text = str(value).strip() if value is not None else ""
    return _limit_text(text, max_chars) if text else ""


def _coerce_compact_list(
    values: Any,
    *,
    max_items: int = _COMPACT_SURFACE_LIST_ITEMS,
) -> list[str]:
    if values is None:
        return []
    try:
        items = [str(value) for value in values if str(value)]
    except TypeError:
        return []
    return items[:max_items]


def _compact_mapping_payload(
    value: Any,
    *,
    max_items: int = _COMPACT_SURFACE_MAP_ITEMS,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for idx, (key, item) in enumerate(
        sorted(value.items(), key=lambda pair: str(pair[0]))
    ):
        if idx >= max_items:
            break
        compact[str(key)] = _model_payload(item)
    return compact


def _drop_empty_items(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def _surface_target_files(surface: Any) -> list[str]:
    targets = _attr(surface, "targets")
    files = _attr(targets, "files", None) if targets is not None else None
    if files is None:
        files = _attr(surface, "target_files", [])
    return [str(path) for path in (files or []) if str(path)]


def _first_concrete_target(target_files: list[str]) -> str | None:
    for target in target_files:
        if not any(ch in target for ch in "*?["):
            return target
    return None


def _target_declared(target_file: str, declared_targets: list[str]) -> bool:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return False
    for pattern in declared_targets:
        try:
            pattern = normalize_relative_glob_pattern(pattern)
        except ValueError:
            continue
        if pattern == normalized:
            return True
        if segment_glob_match(normalized, pattern):
            return True
    return False


def _read_solver_design_support_artifacts(
    champion: ChampionState,
    target_files: list[str],
    *,
    primary_target: str,
    detail: str,
    primary_code_char_limit: int,
) -> list[dict[str, Any]]:
    root = Path(champion.code_snapshot_path).expanduser().resolve()
    primary = _normalize_rel_path(primary_target) or ""
    if primary == "policies/solver_algorithm.py" or primary.startswith(
        "policies/baseline_modules/"
    ):
        return []
    per_file_limit = min(primary_code_char_limit, _COMPACT_SURFACE_CODE_CHARS)
    total_limit = 6000 if detail == "full" else 9000
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    remaining = total_limit
    for raw_pattern in target_files:
        try:
            pattern = normalize_relative_glob_pattern(raw_pattern)
        except ValueError:
            continue
        if not pattern.startswith("policies/baseline_modules/"):
            continue
        if not any(ch in pattern for ch in "*?["):
            candidates = [root / pattern]
        else:
            candidates = sorted(root.glob(pattern))
        for path in candidates:
            if len(artifacts) >= 12 or remaining <= 0:
                return artifacts
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if (
                rel == primary
                or rel.endswith("/__init__.py")
                or rel in seen
                or not path.is_file()
            ):
                continue
            seen.add(rel)
            read_limit = max(0, min(per_file_limit, remaining))
            artifact = _read_champion_file(champion, rel, max_chars=read_limit)
            artifacts.append(artifact)
            if artifact.get("readable"):
                remaining -= len(str(artifact.get("content_preview", "")))
    return artifacts


def _read_champion_file(
    champion: ChampionState,
    target_file: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return {
            "file_path": target_file,
            "readable": False,
            "reason": "unsafe_relative_path",
        }
    root = Path(champion.code_snapshot_path).expanduser().resolve()
    unresolved_path = root / normalized
    if _path_has_symlink_component(root, normalized):
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "symlink_not_allowed",
        }
    path = unresolved_path.resolve()
    if path != root and root not in path.parents:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "path_escapes_champion_snapshot",
        }
    if not path.is_file():
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "not_found",
        }
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": f"unreadable:{exc}",
        }
    return {
        "file_path": normalized,
        "readable": True,
        "content_preview": _limit_text(content, max_chars),
        "truncated": len(content) > max_chars,
        "size_chars": len(content),
        "max_chars": max_chars,
    }


def _path_has_symlink_component(root: Path, normalized_rel_path: str) -> bool:
    current = root
    for part in PurePosixPath(normalized_rel_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


_RUNTIME_ATTRIBUTION_SUFFIXES = (
    "_initial_distance",
    "_returned_distance",
    "_objective_delta",
    "_active",
    "_loaded",
    "_errors",
    "_attempts",
    "_accepted",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_runtime_ms",
    "_objective_trace",
    "_delta_by_phase",
    "_stop_reason",
    "_coverage_status",
    "_quality_guard_applied",
    "_param_clamps",
)


_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES = (
    "_objective_trace",
    "_objective_delta",
    "_delta_by_phase",
    "_phase_delta_sum",
    "_initial_distance",
    "_returned_distance",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_accepted",
    "_attempts",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_coverage_status",
    "_stop_reason",
    "_errors",
    "_active",
    "_loaded",
)


def _surface_runtime_attribution_payload(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    if protocol is None:
        return {}
    summary = protocol.candidate_surface_runtime_summary or {}
    if not isinstance(summary, Mapping):
        return {}
    fields = summary.get("fields")
    if not isinstance(fields, Mapping):
        return {}
    candidates: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for field_name, field_summary in fields.items():
        if not isinstance(field_name, str) or not isinstance(field_summary, Mapping):
            continue
        if not _runtime_attribution_field_is_interesting(field_name, field_summary):
            continue
        candidates.append(
            (
                _runtime_attribution_sort_key(field_name, field_summary),
                {
                    "field": field_name,
                    "present": field_summary.get("present"),
                    "missing": field_summary.get("missing"),
                    "empty": field_summary.get("empty"),
                    "failed": field_summary.get("failed"),
                    "numeric_summary": _strip_forbidden_value(
                        field_summary.get("numeric_summary") or {}
                    ),
                    "values": _compact_runtime_attribution_values(
                        field_summary.get("values")
                    ),
                },
            )
        )
    candidates.sort(key=lambda item: item[0])
    highlights = [payload for _sort_key, payload in candidates[:12]]
    if not highlights:
        return {}
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(protocol.stats),
        "runtime_field_highlights": highlights,
    }


def _research_diagnosis_payload(
    safe_steps: list[StepRecord],
    *,
    max_items: int,
    problem_spec: Any = None,
) -> dict[str, Any]:
    screening_steps = [
        step
        for step in safe_steps
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ]
    recent_steps = list(reversed(screening_steps))[:max_items]
    reason_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    all_screening_surface_counts: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    failure_tags: set[str] = set()
    recent_rows: list[dict[str, Any]] = []
    runtime_signal_rows: list[dict[str, Any]] = []
    declared_solver_design_surfaces = _declared_solver_design_surface_names(
        problem_spec
    )
    failed_solver_design_surfaces = _pre_protocol_failed_solver_design_surface_names(
        safe_steps,
        declared_solver_design_surfaces,
    )
    screening_failed_solver_design_surfaces = (
        _screening_failed_solver_design_surface_names(
            safe_steps,
            declared_solver_design_surfaces,
        )
    )
    declared_mechanism_surfaces = (
        []
        if declared_solver_design_surfaces
        else _declared_mechanism_surface_names(problem_spec)
    )

    for step in screening_steps:
        surface = step.hypothesis.change_locus
        all_screening_surface_counts[surface] = (
            all_screening_surface_counts.get(surface, 0) + 1
        )

    for step in recent_steps:
        protocol = step.protocol_result
        if protocol is None:
            continue
        surface = step.hypothesis.change_locus
        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        gate = str(protocol.gate_outcome or "")
        gate_counts[gate] = gate_counts.get(gate, 0) + 1
        for reason in protocol.reason_codes or ():
            reason_text = str(reason)
            reason_counts[reason_text] = reason_counts.get(reason_text, 0) + 1
            if "WIN_RATE" in reason_text.upper():
                failure_tags.add("screening_win_rate_failure")
            if "RUNTIME" in reason_text.upper():
                failure_tags.add("runtime_related_failure")
        stats = protocol.stats
        if stats.win_rate is not None and float(stats.win_rate) <= 0.0:
            failure_tags.add("zero_case_win_rate")
        if stats.median_delta is not None and abs(float(stats.median_delta)) <= 1e-12:
            failure_tags.add("zero_median_delta")

        attribution = _surface_runtime_attribution_payload(step)
        runtime_fields = []
        runtime_issue_fields = []
        runtime_nonzero_fields = []
        zero_phase_delta_fields = []
        accepted_signal_fields = []
        recovery_signal_fields = []
        for highlight in attribution.get("runtime_field_highlights", []) or []:
            if not isinstance(highlight, Mapping):
                continue
            field = str(highlight.get("field") or "")
            if not field:
                continue
            runtime_fields.append(field)
            if any(
                _safe_positive_int(highlight.get(key))
                for key in ("missing", "empty", "failed")
            ):
                runtime_issue_fields.append(field)
            if _runtime_highlight_has_nonzero_numeric(highlight):
                runtime_nonzero_fields.append(field)
                if "accepted" in field:
                    accepted_signal_fields.append(field)
                if "recovery" in field:
                    recovery_signal_fields.append(field)
            if (
                "phase_delta" in field or field.endswith("_delta_by_phase")
            ) and _runtime_highlight_is_all_zero_numeric(highlight):
                zero_phase_delta_fields.append(field)
        if runtime_issue_fields:
            failure_tags.add("runtime_evidence_contract_issue")
        if runtime_nonzero_fields and gate != "pass":
            failure_tags.add("runtime_signal_without_protocol_pass")
        if zero_phase_delta_fields:
            failure_tags.add("zero_phase_delta")
        if zero_phase_delta_fields and accepted_signal_fields:
            failure_tags.add("accepted_signal_without_phase_delta")
        if zero_phase_delta_fields and recovery_signal_fields:
            failure_tags.add("recovery_only_accepted_moves")
        if runtime_fields:
            runtime_signal_rows.append(
                _drop_empty_items(
                    {
                        "round_num": step.round_num,
                        "surface": surface,
                        "gate_outcome": gate,
                        "highlight_fields": runtime_fields[:8],
                        "nonzero_numeric_fields": runtime_nonzero_fields[:8],
                        "zero_phase_delta_fields": zero_phase_delta_fields[:8],
                        "accepted_signal_fields": accepted_signal_fields[:8],
                        "recovery_signal_fields": recovery_signal_fields[:8],
                        "issue_fields": runtime_issue_fields[:8],
                    }
                )
            )
        recent_rows.append(
            {
                "round_num": step.round_num,
                "surface": surface,
                "target_file": step.hypothesis.target_file,
                "gate_outcome": gate,
                "reason_codes": list(protocol.reason_codes),
                "stats": _eval_stats_payload(stats),
            }
        )

    unselected_solver_design_surfaces = [
        surface
        for surface in declared_solver_design_surfaces
        if surface not in all_screening_surface_counts
    ]
    unselected_mechanism_surfaces = [
        surface
        for surface in declared_mechanism_surfaces
        if surface not in all_screening_surface_counts
    ]
    if declared_solver_design_surfaces and unselected_solver_design_surfaces:
        failure_tags.add("solver_design_not_selected")
    if failed_solver_design_surfaces:
        failure_tags.add("solver_design_pre_protocol_failure")
    if screening_failed_solver_design_surfaces:
        failure_tags.add("solver_design_screening_failure")
    if declared_mechanism_surfaces and unselected_mechanism_surfaces:
        failure_tags.add("deep_surface_not_selected")

    next_requirements = [
        "Name the screening/runtime evidence pattern being addressed.",
        "State which declared surface evidence fields are expected to change.",
        "Change the mechanism or bounded lever, not only wording or novelty text.",
        "State how the implementation remains within declared interface and bounds.",
    ]
    if failed_solver_design_surfaces:
        next_requirements.append(
            "Retry the solver-design boundary with a different lifecycle "
            "implementation; a pre-screening candidate failure does not retire "
            "the problem-object surface: "
            + ", ".join(failed_solver_design_surfaces[:8])
        )
    elif screening_failed_solver_design_surfaces:
        next_requirements.append(
            "Keep change_locus on the solver-design boundary and change the "
            "whole-lifecycle implementation; screening failure means the "
            "candidate design failed, not that component policies should become "
            "replacement research goals: "
            + ", ".join(screening_failed_solver_design_surfaces[:8])
        )
    elif unselected_solver_design_surfaces:
        next_requirements.append(
            "Use a solver-design surface that reasons from the problem object "
            "before repeating component policies: "
            + ", ".join(unselected_solver_design_surfaces[:8])
        )
    elif unselected_mechanism_surfaces:
        next_requirements.append(
            "Exercise an unselected mechanism surface before repeating older "
            "orchestration surfaces: " + ", ".join(unselected_mechanism_surfaces[:8])
        )
    if "zero_phase_delta" in failure_tags:
        next_requirements.append(
            "Explain how the candidate should move phase-best/objective-delta "
            "runtime fields, not only attempts or accepted counts."
        )

    return {
        "schema_version": "research-diagnosis.v1",
        "screening_only": True,
        "screening_step_count": len(screening_steps),
        "recent_screening_steps": recent_rows,
        "reason_code_counts": reason_counts,
        "surface_counts": surface_counts,
        "declared_solver_design_surfaces": declared_solver_design_surfaces,
        "failed_solver_design_surfaces": failed_solver_design_surfaces,
        "screening_failed_solver_design_surfaces": (
            screening_failed_solver_design_surfaces
        ),
        "unselected_solver_design_surfaces": unselected_solver_design_surfaces,
        "declared_mechanism_surfaces": declared_mechanism_surfaces,
        "unselected_mechanism_surfaces": unselected_mechanism_surfaces,
        "gate_outcome_counts": gate_counts,
        "failure_mode_tags": sorted(failure_tags),
        "runtime_signal_rows": runtime_signal_rows,
        "next_hypothesis_requirements": next_requirements,
    }


def _diagnostic_surface_priorities(
    context: ProposalToolContext,
    declared_surfaces: tuple[Any, ...],
) -> dict[str, Any]:
    solver_design_surfaces = _declared_solver_design_surface_names(
        context.problem_spec
    )
    failed_solver_design = _pre_protocol_failed_solver_design_surface_names(
        list(context.step_history),
        solver_design_surfaces,
    )
    screening_failed_solver_design = _screening_failed_solver_design_surface_names(
        list(context.step_history),
        solver_design_surfaces,
    )
    mechanism_surfaces = _declared_mechanism_surface_names(context.problem_spec)
    if not mechanism_surfaces:
        mechanism_surfaces = _mechanism_surface_names_from_surfaces(declared_surfaces)
    screened_surfaces = {
        step.hypothesis.change_locus
        for step in _filter_hypothesis_prompt_steps(list(context.step_history))
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    }
    has_screening_history = bool(screened_surfaces)
    if solver_design_surfaces:
        unselected_solver_design = [
            surface
            for surface in solver_design_surfaces
            if surface not in screened_surfaces
        ]
        failure_mode_tags = []
        if has_screening_history and unselected_solver_design:
            failure_mode_tags.append("solver_design_not_selected")
        if failed_solver_design:
            failure_mode_tags.append("solver_design_pre_protocol_failure")
        if screening_failed_solver_design:
            failure_mode_tags.append("solver_design_screening_failure")
        next_requirements = []
        if failed_solver_design:
            next_requirements.append(
                "Retry the problem-object solver-design surface with a "
                "different lifecycle implementation; the prior failure was a "
                "candidate failure, not a surface retirement: "
                + ", ".join(failed_solver_design[:8])
            )
        elif screening_failed_solver_design:
            next_requirements.append(
                "Keep the next change_locus on the problem-object "
                "solver-design surface; prior screening failures are candidate "
                "design failures, not a reason to switch research goals to "
                "component policies: "
                + ", ".join(screening_failed_solver_design[:8])
            )
        elif has_screening_history and unselected_solver_design:
            next_requirements.append(
                "Prioritize a solver-design surface that reasons from the "
                "problem object before repeating component policies: "
                + ", ".join(unselected_solver_design[:8])
            )
        recommendation = None
        if failed_solver_design:
            recommendation = (
                "Retry the problem-object solver-design boundary; the prior "
                "pre-protocol result is a candidate failure, and component "
                "policies remain attribution hooks, not fallback research goals."
            )
        elif screening_failed_solver_design:
            recommendation = (
                "Keep change_locus on the problem-object solver-design "
                "boundary; use component policies only as implementation hooks "
                "or attribution evidence inside the solver design."
            )
        elif has_screening_history and unselected_solver_design:
            recommendation = (
                "Prioritize the problem-object solver-design surface; "
                "component policies are attribution hooks, not isolated "
                "research targets."
            )
        return _drop_empty_items(
            {
                "solver_design_surfaces": solver_design_surfaces,
                "failed_solver_design_surfaces": failed_solver_design,
                "screening_failed_solver_design_surfaces": (
                    screening_failed_solver_design
                ),
                "unselected_solver_design_surfaces": unselected_solver_design,
                "failure_mode_tags": failure_mode_tags,
                "next_requirements": next_requirements,
                "recommendation": recommendation,
            }
        )
    unselected = [
        surface for surface in mechanism_surfaces if surface not in screened_surfaces
    ]
    failure_mode_tags = (
        ["deep_surface_not_selected"] if has_screening_history and unselected else []
    )
    next_requirements = (
        [
            "Exercise one unselected mechanism surface before repeating "
            "orchestration or legacy policy surfaces: " + ", ".join(unselected[:8])
        ]
        if has_screening_history and unselected
        else []
    )
    return _drop_empty_items(
        {
            "mechanism_surfaces": mechanism_surfaces,
            "unselected_mechanism_surfaces": unselected,
            "failure_mode_tags": failure_mode_tags,
            "next_requirements": next_requirements,
            "recommendation": (
                "Prioritize one unselected mechanism surface for the next short "
                "diagnostic before repeating orchestration or legacy policy surfaces."
                if has_screening_history and unselected
                else None
            ),
        }
    )


def _declared_solver_design_surface_names(problem_spec: Any) -> list[str]:
    if problem_spec is None:
        return []
    names: list[str] = []
    for surface in _get_research_surfaces(problem_spec):
        name = str(_attr(surface, "name") or "").strip()
        if not name:
            continue
        role = _attr(_attr(surface, "algorithm"), "role", "")
        kind = str(_attr(surface, "kind", "") or "")
        haystack = f"{kind} {role}".lower()
        if (
            kind in {"solver_design", "solver_algorithm"}
            or "solver_design" in haystack
            or "solver_algorithm" in haystack
        ):
            names.append(name)
    return names


def _pre_protocol_failed_solver_design_surface_names(
    steps: list[StepRecord],
    solver_design_surfaces: list[str],
) -> list[str]:
    if not solver_design_surfaces:
        return []
    allowed = set(solver_design_surfaces)
    failed: list[str] = []
    for step in _filter_hypothesis_prompt_steps(steps):
        surface = str(step.hypothesis.change_locus or "").strip()
        if surface not in allowed:
            continue
        if step.protocol_result is not None:
            continue
        if step.failure_stage in {"verification", "patch_contract", "workspace"}:
            if surface not in failed:
                failed.append(surface)
    return failed


def _screening_failed_solver_design_surface_names(
    steps: list[StepRecord],
    solver_design_surfaces: list[str],
) -> list[str]:
    if not solver_design_surfaces:
        return []
    allowed = set(solver_design_surfaces)
    failed: list[str] = []
    for step in _filter_hypothesis_prompt_steps(steps):
        surface = str(step.hypothesis.change_locus or "").strip()
        if surface not in allowed:
            continue
        result = step.protocol_result
        if result is None:
            continue
        if step.decision is not None and getattr(step.decision, "value", "") == "promote":
            continue
        if getattr(result, "gate_outcome", None) == "pass":
            continue
        if surface not in failed:
            failed.append(surface)
    return failed


def _declared_mechanism_surface_names(problem_spec: Any) -> list[str]:
    if problem_spec is None:
        return []
    return _mechanism_surface_names_from_surfaces(_get_research_surfaces(problem_spec))


def _mechanism_surface_names_from_surfaces(surfaces: Any) -> list[str]:
    names: list[str] = []
    for surface in surfaces or ():
        name = str(_attr(surface, "name") or "").strip()
        if not name:
            continue
        role = _attr(_attr(surface, "algorithm"), "role", "")
        description = _attr(_attr(surface, "algorithm"), "description", "")
        kind = str(_attr(surface, "kind", "") or "")
        haystack = f"{role} {description} {kind} {name}".lower()
        if (
            "mechanism" in haystack
            or "candidate_generation" in haystack
            or kind == "acceptance_restart"
        ):
            names.append(name)
    return names


def _runtime_highlight_is_all_zero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    summaries = _runtime_numeric_leaf_summaries(numeric)
    if not summaries:
        return False
    observed = False
    for summary in summaries:
        try:
            count = int(summary.get("observed_count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        observed = True
        if _safe_positive_int(summary.get("nonzero_count")):
            return False
        try:
            if abs(float(summary.get("weighted_sum") or 0.0)) > 1e-12:
                return False
        except (TypeError, ValueError):
            return False
    return observed


def _runtime_numeric_leaf_summaries(
    numeric: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    summaries: list[Mapping[str, Any]] = []
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if not isinstance(value, Mapping):
            continue
        if "observed_count" in value and (
            "nonzero_count" in value or "weighted_sum" in value
        ):
            summaries.append(value)
            continue
        stack.extend(value.values())
    return summaries


def _runtime_highlight_has_nonzero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in {"nonzero_count", "positive_count"} and _safe_positive_int(
                    nested
                ):
                    return True
                if key == "weighted_sum":
                    try:
                        if abs(float(nested or 0.0)) > 1e-12:
                            return True
                    except (TypeError, ValueError):
                        pass
                stack.append(nested)
        elif isinstance(value, list):
            stack.extend(value)
    return False


def _runtime_attribution_sort_key(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> tuple[int, int, str]:
    has_issue = any(
        _safe_positive_int(field_summary.get(key))
        for key in ("missing", "empty", "failed")
    )
    priority = len(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES)
    for index, suffix in enumerate(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES):
        if field_name.endswith(suffix):
            priority = index
            break
    return (0 if has_issue else 1, priority, field_name)


def _runtime_attribution_field_is_interesting(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> bool:
    for key in ("missing", "empty", "failed"):
        if _safe_positive_int(field_summary.get(key)):
            return True
    return any(field_name.endswith(suffix) for suffix in _RUNTIME_ATTRIBUTION_SUFFIXES)


def _safe_positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _compact_runtime_attribution_values(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in values[:3]:
        if not isinstance(item, Mapping):
            continue
        compact.append(
            _drop_empty_items(
                {
                    "value": _limit_text(str(item.get("value", "")), 240),
                    "count": item.get("count"),
                }
            )
        )
    return compact


def _screening_step_payload(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    stats = protocol.stats
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "action": step.hypothesis.action,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(stats),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "candidate_surface_runtime_attribution": _surface_runtime_attribution_payload(
            step
        ),
        "pattern_summary": _model_payload(protocol.pattern_summary),
        "case_feedback": [
            _model_payload(feedback) for feedback in (protocol.case_feedback or ())[:6]
        ],
        "metrics_file_ref_exposed": False,
    }


def _holdout_step_payload(
    step: StepRecord,
    exposure: HoldoutExposure,
    level: ProposalExposureLevel,
) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    payload: dict[str, Any] = {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "stage": _stage_value(protocol.stage),
        "exposure_level": level.value,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "metrics_file_ref_exposed": False,
        "case_ids_exposed": False,
        "pair_feedback_exposed": False,
    }
    if exposure == HoldoutExposure.AGGREGATE:
        payload["stats"] = _eval_stats_payload(protocol.stats)
    return payload


def _eval_stats_payload(stats: Any) -> dict[str, Any]:
    allowed = {
        "n_cases",
        "wins",
        "losses",
        "ties",
        "win_rate",
        "median_delta",
        "ci_low",
        "ci_high",
        "statistical_status",
        "statistical_metric",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "runtime_pairs",
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
    }
    return {name: _attr(stats, name) for name in allowed if hasattr(stats, name)}


def _strip_forbidden_payload_refs(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _strip_forbidden_value(payload)


def _bound_compact_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    estimated = _json_size(payload)
    if estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS:
        bounded = dict(payload)
        bounded.setdefault("payload_truncated", False)
        return bounded
    compact = _compact_feedback_value(payload)
    compact_estimated = _json_size(compact)
    if (
        isinstance(compact, Mapping)
        and compact_estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS
    ):
        bounded = dict(compact)
        bounded["payload_truncated"] = True
        bounded["original_estimated_chars"] = estimated
        return bounded
    return {
        "payload_truncated": True,
        "original_estimated_chars": estimated,
        "compacted_estimated_chars": compact_estimated,
        "available_keys": sorted(str(key) for key in payload.keys()),
        "summary": "Compact feedback payload exceeded budget and was summarized.",
    }


def _compact_feedback_value(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _COMPACT_FEEDBACK_MAP_ITEMS:
                compact["omitted_mapping_items"] = len(value) - index
                break
            compact[str(key)] = _compact_feedback_value(item, depth=depth + 1)
        return compact
    if isinstance(value, tuple):
        return _compact_feedback_value(list(value), depth=depth)
    if isinstance(value, list):
        compact_list = [
            _compact_feedback_value(item, depth=depth + 1)
            for item in value[:_COMPACT_FEEDBACK_LIST_ITEMS]
        ]
        if len(value) > _COMPACT_FEEDBACK_LIST_ITEMS:
            compact_list.append(
                {"omitted_items": len(value) - _COMPACT_FEEDBACK_LIST_ITEMS}
            )
        return compact_list
    if isinstance(value, str):
        limit = max(
            200,
            _COMPACT_FEEDBACK_STRING_CHARS // max(1, min(depth, 4)),
        )
        return _limit_text(value, limit)
    return _strip_forbidden_value(value)


def _strip_forbidden_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"raw_metrics_ref", "case_ids", "seed_set", "pair_feedback"}:
                continue
            cleaned[key_text] = _strip_forbidden_value(item)
        return cleaned
    if isinstance(value, tuple):
        return [_strip_forbidden_value(item) for item in value]
    if isinstance(value, list):
        return [_strip_forbidden_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _sanitize_memory_text(text: str) -> str:
    if not text:
        return ""
    forbidden_terms = (
        "champion_evolution",
        "champion evolution",
        "promotion",
        "promoted",
        "promote",
        "validation",
        "frozen",
        "holdout",
        "raw_metrics",
        "raw metrics",
    )
    safe_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in forbidden_terms):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)


def _error_observation(
    context: ProposalToolContext,
    *,
    tool_name: str,
    tool_call_id: str,
    failure_code: ProposalToolFailureCode,
    summary: str,
    structured_payload: Mapping[str, Any] | None = None,
    repair_hint: str | None = None,
) -> ProposalObservation:
    return ProposalObservation(
        observation_id=str(uuid.uuid4()),
        session_id=context.session_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        observation_type="tool_error",
        summary=summary,
        structured_payload=_strip_forbidden_payload_refs(structured_payload or {}),
        exposure_level=ProposalExposureLevel.NONE,
        is_error=True,
        failure_code=failure_code,
        repair_hint=repair_hint,
    )


def _model_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _strip_forbidden_value(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _strip_forbidden_value(asdict(value))
    if isinstance(value, Mapping):
        return _strip_forbidden_value(dict(value))
    if isinstance(value, tuple):
        return [_model_payload(item) for item in value]
    if isinstance(value, list):
        return [_model_payload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")


def _normalize_rel_path(path: str) -> str | None:
    raw_path = str(path).replace(os.sep, "/")
    if raw_path.startswith("/"):
        return None
    raw = raw_path
    if not raw or raw in {".", ".."}:
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"..", ""} for part in parts):
        return None
    return "/".join(parts)


def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated by proposal tool result budget]"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _json_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


__all__ = [
    "ContextExposurePolicy",
    "ContractPreviewTool",
    "ContextReadBranchStateTool",
    "DraftHypothesisTool",
    "DraftPatchTool",
    "FeedbackQueryHoldoutSummaryTool",
    "FeedbackQueryRuntimeTool",
    "FeedbackQueryScreeningTool",
    "HoldoutExposure",
    "InterfacePreviewTool",
    "ProposalExposureLevel",
    "ProposalObservation",
    "ProposalTaint",
    "ProposalTool",
    "ProposalToolContext",
    "ProposalToolFailureCode",
    "ProposalToolPermission",
    "ProposalToolRegistry",
    "SchemaPreviewTool",
    "TargetPermissionPreviewTool",
]
