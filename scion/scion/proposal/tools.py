"""Proposal tools with explicit exposure control.

These tools live inside the tainted proposal layer.  They return typed
observations for an agentic proposal session, but they do not write candidate
workspaces and they do not expose validation/frozen raw metrics.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scion.contract.gate import ContractGate
from scion.core.models import (
    Branch,
    ChampionState,
    ContractResult,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
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

    def call(self, args: BaseModel, context: ProposalToolContext) -> ProposalObservation:
        ...


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
            raise ValueError(f"APS-2 registry accepts read-only tools only: {tool.name}")
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

    def allowed_tool_specs(self, context: ProposalToolContext) -> tuple[dict[str, Any], ...]:
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

    def call(self, args: BaseModel, context: ProposalToolContext) -> ProposalObservation:
        surfaces = _surfaces(context)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "surface_count": len(surfaces),
            "surfaces": [_surface_listing_payload(surface) for surface in surfaces],
            "detail": "compact",
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

    def call(self, args: BaseModel, context: ProposalToolContext) -> ProposalObservation:
        summary = _problem_summary(context)
        payload = {
            "problem_id": context.problem_id or _attr(context.problem_spec, "id"),
            "problem_spec_hash": context.problem_spec_hash,
            "summary": _limit_text(summary, 12000),
            "summary_truncated": len(summary) > 12000,
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

    def call(self, args: BaseModel, context: ProposalToolContext) -> ProposalObservation:
        adapter_spec = _get_adapter_problem_spec(context.adapter) or context.problem_spec
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

    def call(self, args: BaseModel, context: ProposalToolContext) -> ProposalObservation:
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
                    )
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
                    )
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
        rows = []
        for step in safe_steps:
            protocol = step.protocol_result
            if protocol is None or protocol.stage != ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            rows.append(_screening_step_payload(step))
            if len(rows) >= args.max_items:
                break
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "screening_steps": rows,
        }
        return self._observation(
            context,
            observation_type="screening_feedback",
            summary=f"Returned {len(rows)} screening feedback row(s).",
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
            else ProposalExposureLevel.FROZEN_AGGREGATE
            if rows
            else ProposalExposureLevel.NONE
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
        rendered = _build_runtime_feedback(safe_steps, max_items=args.max_items)
        adapter_spec = _get_adapter_problem_spec(context.adapter)
        guidance = _build_runtime_failure_guidance(
            safe_steps,
            problem_spec=context.problem_spec,
            adapter_spec=adapter_spec,
            max_items=args.max_items,
        )
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "runtime_feedback": rendered,
            "runtime_failure_guidance": guidance,
            "screening_only": True,
            "metrics_file_refs_exposed": False,
        }
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

        return self._observation(
            context,
            observation_type="schema_preview",
            summary=(
                "Schema preview passed."
                if payload["passed"]
                else "Schema preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


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

        payload = {
            "passed": passed,
            "surface": _surface_permission_summary(
                surface,
                allowed_actions=allowed_actions,
                declared_targets=declared_targets,
            )
            if surface is not None
            else None,
            "requested": {
                "change_locus": args.change_locus,
                "action": args.action,
                "target_file": args.target_file,
            },
            "allowed_actions": allowed_actions,
            "declared_targets": declared_targets,
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
                hypothesis_preview["contract"] = _contract_result_payload(result)
                hypothesis_preview["passed"] = result.passed
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(
                hypothesis_preview["passed"]
            )
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
                contract_payload = _contract_result_payload(result)
                patch_preview["contract"] = contract_payload
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
        return self._observation(
            context,
            observation_type="contract_preview",
            summary=(
                "Static contract preview passed."
                if payload["passed"]
                else "Static contract preview needs an approved hypothesis."
                if payload.get("needs_hypothesis")
                else "Static contract preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


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
        "hypothesis": _model_payload(hypothesis),
        "hypothesis_object": hypothesis,
    }


def _schema_preview_patch_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validated = DraftPatchInput.model_validate(dict(raw))
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    patch = _patch_from_input(validated)
    path_error = _patch_path_error(patch.file_path)
    patch_summary = _patch_preview_summary(patch)
    if path_error is not None:
        return {
            "passed": False,
            "errors": [{"loc": ("file_path",), "msg": path_error}],
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
    if novelty_guidance.get("required") and novelty_guidance.get("missing_fields"):
        passed = False
    return {
        "passed": passed,
        "checks": _checks_payload(c1_checks),
        "failure_reason": None
        if passed
        else (
            novelty_guidance.get("detail")
            if novelty_guidance.get("missing_fields")
            else _first_failure(c1_checks)
        ),
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
        if not isinstance(values, dict) or name not in values or values[name] in (
            None,
            "",
            [],
            {},
        ):
            missing.append(name)

    detail = ""
    if missing:
        detail = (
            "missing structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(missing)}"
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
            "unsupported_fields": unsupported,
            "detail": detail,
        }
    )


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
    if _attr(spec, "spec_version") == "problem-v1" or hasattr(spec, "operator_interface"):
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


def _contract_result_payload(result: ContractResult) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failure_reason": result.failure_reason,
        "checks": _checks_payload(result.checks),
    }


def _checks_payload(checks: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": _attr(check, "name"),
            "passed": bool(_attr(check, "passed")),
            "severity": _attr(check, "severity"),
            "detail": _limit_text(str(_attr(check, "detail", "")), 2000),
            "elapsed_ms": _attr(check, "elapsed_ms"),
        }
        for check in checks
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
    return {
        "file_path": patch.file_path,
        "action": patch.action,
        "code_char_count": len(code_content),
        "code_digest": hashlib.sha256(code_content.encode("utf-8")).hexdigest(),
        "functions": _module_level_functions(code_content),
        "classes": _module_classes(code_content),
        "checks": [],
    }


def _compact_problem_preview(preview: Mapping[str, Any] | None) -> dict[str, Any] | None:
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
    return [_limit_text(issue, 1000) for issue in values[:12]]


def _compact_problem_preview_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    checks: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, Mapping):
            continue
        checks.append(
            {
                "name": item.get("name"),
                "passed": bool(item.get("passed")),
                "detail": _limit_text(str(item.get("detail", "")), 1000),
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


def _find_surface(context: ProposalToolContext, name: str) -> Any | None:
    for surface in _surfaces(context):
        if _attr(surface, "name") == name:
            return surface
    return None


def _problem_summary(context: ProposalToolContext) -> str:
    if context.adapter is not None and hasattr(context.adapter, "render_problem_summary"):
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
            "Research loci: " + ", ".join(str(_attr(surface, "name")) for surface in surfaces)
        )
    search_space = _attr(spec, "search_space")
    editable = _attr(search_space, "editable", [])
    frozen = _attr(search_space, "frozen", [])
    if editable:
        lines.append("Editable files: " + ", ".join(str(v) for v in editable))
    if frozen:
        lines.append("Frozen files (do not modify): " + ", ".join(str(v) for v in frozen))
    return "\n".join(lines)


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
                _attr(interface, "return_contract", "")
                if interface is not None
                else ""
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
        + ", ".join(
            [section] if section != "all" else list(_COMPACT_SURFACE_SECTIONS)
        )
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
        "pattern_summary": _model_payload(protocol.pattern_summary),
        "case_feedback": [
            _model_payload(feedback)
            for feedback in (protocol.case_feedback or ())[:6]
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
