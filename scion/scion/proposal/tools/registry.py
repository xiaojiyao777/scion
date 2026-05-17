"""Proposal tool registry and call boundary."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from pydantic import ValidationError

from scion.proposal.tools.context import (
    ContextListSurfacesTool,
    ContextReadBranchStateTool,
    ContextReadChampionSummaryTool,
    ContextReadObjectivePolicyTool,
    ContextReadProblemTool,
)
from scion.proposal.tools.feedback import (
    FeedbackQueryHoldoutSummaryTool,
    FeedbackQueryRuntimeTool,
    FeedbackQueryScreeningTool,
    MemoryQueryTool,
)
from scion.proposal.tools.models import (
    ProposalObservation,
    ProposalTool,
    ProposalToolContext,
    ProposalToolFailureCode,
)
from scion.proposal.tools.preview import (
    AlgorithmSmokeTool,
    ContractPreviewTool,
    DraftHypothesisTool,
    DraftPatchTool,
    InterfacePreviewTool,
    SchemaPreviewTool,
    TargetPermissionPreviewTool,
)
from scion.proposal.tools.surface import ContextReadSurfaceTool
from scion.proposal.tools.utils import (
    _error_observation,
    _json_size,
    _strip_forbidden_payload_refs,
)


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


__all__ = ["ProposalToolRegistry"]
