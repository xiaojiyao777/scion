"""Controlled active solver-design reading tools."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from scion.proposal.active_solver_snapshot import (
    build_active_solver_snapshot,
    list_algorithm_files_payload,
    read_algorithm_file_payload,
    read_algorithm_symbol_payload,
    solver_call_graph_payload,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)

_REJECTED_FILE_PATH = "<path_rejected>"
_ALGORITHM_FILE_LIST_TOOL = "context.list_algorithm_files"
_ALGORITHM_FILE_READ_TOOLS = frozenset(
    {"context.read_algorithm_file", "context.read_algorithm_symbol"}
)
_ALGORITHM_FILE_REPAIR_HINT = (
    "Call context.list_algorithm_files first, then pass exactly one returned "
    "files[].file_path value. Do not pass a surface id such as solver_design "
    "as file_path."
)
_INVALID_FILE_PATH_SENTINELS = frozenset(
    {
        "",
        "<unknown>",
        "unknown",
        "solver_design",
        "solver_algorithm",
    }
)


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadActiveSolverDesignInput(_StrictInput):
    surface: Literal["solver_design"] = "solver_design"
    include_file_previews: bool = False
    max_file_chars: int = Field(default=6000, ge=0, le=24000)


class ReadSolverCallGraphInput(_StrictInput):
    surface: Literal["solver_design"] = "solver_design"


class ListAlgorithmFilesInput(_StrictInput):
    surface: Literal["solver_design"] = "solver_design"
    include_inactive: bool = True


class ReadAlgorithmFileInput(_StrictInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "description": (
                "Read one allowlisted solver_design algorithm file. Before using "
                "this tool, call context.list_algorithm_files and use exactly one "
                "returned files[].file_path value; surface ids such as solver_design "
                "are not file paths."
            ),
            "x-required-first-tool": _ALGORITHM_FILE_LIST_TOOL,
        },
    )
    surface: Literal["solver_design"] = "solver_design"
    file_path: str = Field(
        description=(
            "One exact files[].file_path value returned by "
            "context.list_algorithm_files in this session. Call "
            "context.list_algorithm_files first; do not pass a surface id such "
            "as solver_design."
        )
    )
    max_chars: int = Field(default=12000, ge=0, le=24000)


class ReadAlgorithmSymbolInput(_StrictInput):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "description": (
                "Read one symbol from an allowlisted solver_design algorithm file. "
                "Before using this tool, call context.list_algorithm_files and use "
                "exactly one returned files[].file_path value; surface ids such as "
                "solver_design are not file paths."
            ),
            "x-required-first-tool": _ALGORITHM_FILE_LIST_TOOL,
        },
    )
    surface: Literal["solver_design"] = "solver_design"
    file_path: str = Field(
        description=(
            "One exact files[].file_path value returned by "
            "context.list_algorithm_files in this session. Call "
            "context.list_algorithm_files first; do not pass a surface id such "
            "as solver_design."
        )
    )
    symbol: str = Field(
        description=(
            "Top-level symbol or Class.method name from an allowed algorithm file."
        )
    )
    max_chars: int = Field(default=12000, ge=0, le=24000)


class ContextReadActiveSolverDesignTool(_BaseReadOnlyTool):
    name = "context.read_active_solver_design"
    input_schema = ReadActiveSolverDesignInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    max_result_chars = 64000

    def call(
        self,
        args: ReadActiveSolverDesignInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload = build_active_solver_snapshot(
            context,
            include_file_previews=args.include_file_previews,
            max_file_chars=args.max_file_chars,
        )
        return self._observation(
            context,
            observation_type="active_solver_design",
            summary=(
                "Returned active solver_design snapshot with entrypoint, call "
                "graph, mechanisms, provenance, and legacy exclusions."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadSolverCallGraphTool(_BaseReadOnlyTool):
    name = "context.read_solver_call_graph"
    input_schema = ReadSolverCallGraphInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    max_result_chars = 48000

    def call(
        self,
        args: ReadSolverCallGraphInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload = solver_call_graph_payload(context)
        return self._observation(
            context,
            observation_type="solver_call_graph",
            summary="Returned active solver_design call graph with provenance.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextListAlgorithmFilesTool(_BaseReadOnlyTool):
    name = "context.list_algorithm_files"
    input_schema = ListAlgorithmFilesInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ListAlgorithmFilesInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        files = list_algorithm_files_payload(
            context,
            include_inactive=args.include_inactive,
        )
        payload = {
            "surface": args.surface,
            "allowlist_only": True,
            "file_count": len(files),
            "files": files,
        }
        return self._observation(
            context,
            observation_type="solver_algorithm_file_list",
            summary="Returned allowlisted solver_design algorithm files.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadAlgorithmFileTool(_BaseReadOnlyTool):
    name = "context.read_algorithm_file"
    input_schema = ReadAlgorithmFileInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ReadAlgorithmFileInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        allowed_files = _allowed_algorithm_file_paths(context)
        file_path = _validated_algorithm_file_path(args.file_path, allowed_files)
        if file_path is None:
            return _path_rejected_observation(
                self,
                context,
                allowed_files=allowed_files,
                observation_target="algorithm file",
            )
        payload = read_algorithm_file_payload(
            context,
            file_path,
            max_chars=args.max_chars,
        )
        file_path = str(payload.get("file_path") or _REJECTED_FILE_PATH)
        return self._observation(
            context,
            observation_type="solver_algorithm_file",
            summary=f"Returned allowlisted solver_design file {file_path}.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadAlgorithmSymbolTool(_BaseReadOnlyTool):
    name = "context.read_algorithm_symbol"
    input_schema = ReadAlgorithmSymbolInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ReadAlgorithmSymbolInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        allowed_files = _allowed_algorithm_file_paths(context)
        file_path = _validated_algorithm_file_path(args.file_path, allowed_files)
        if file_path is None:
            return _path_rejected_observation(
                self,
                context,
                allowed_files=allowed_files,
                observation_target="algorithm symbol",
            )
        payload = read_algorithm_symbol_payload(
            context,
            file_path,
            args.symbol,
            max_chars=args.max_chars,
        )
        file_path = str(payload.get("file_path") or _REJECTED_FILE_PATH)
        return self._observation(
            context,
            observation_type="solver_algorithm_symbol",
            summary=(
                "Returned allowlisted solver_design symbol "
                f"{file_path}::{args.symbol}."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


def _allowed_algorithm_file_paths(context: ProposalToolContext) -> tuple[str, ...]:
    files = list_algorithm_files_payload(context, include_inactive=True)
    return tuple(
        str(item.get("file_path") or "")
        for item in files
        if item.get("file_path")
    )


def _validated_algorithm_file_path(
    file_path: str,
    allowed_files: tuple[str, ...],
) -> str | None:
    raw_text = str(file_path or "").strip()
    raw = raw_text.replace("\\", "/")
    if raw.lower() in _INVALID_FILE_PATH_SENTINELS:
        return None
    if raw.startswith(("/", "~")) or (len(raw) >= 2 and raw[1] == ":"):
        return None
    pure = PurePosixPath(raw)
    if pure.is_absolute() or pure.as_posix() != raw:
        return None
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None
    if raw not in set(allowed_files):
        return None
    return raw


def algorithm_file_path_guidance(
    context: ProposalToolContext,
) -> dict[str, Any]:
    """Return model-facing file_path guidance derived from the current context."""

    return _algorithm_file_path_guidance_payload(
        _allowed_algorithm_file_paths(context)
    )


def algorithm_file_path_guidance_for_tool(
    context: ProposalToolContext,
    tool_name: str,
) -> dict[str, Any] | None:
    """Return dynamic file_path guidance for model-facing tool specs."""

    if tool_name not in _ALGORITHM_FILE_READ_TOOLS:
        return None
    return _algorithm_file_path_guidance_payload(
        _allowed_algorithm_file_paths(context),
        tool_name=tool_name,
    )


def _algorithm_file_path_guidance_payload(
    allowed_files: tuple[str, ...],
    *,
    tool_name: str | None = None,
) -> dict[str, Any]:
    allowed_file_paths = list(allowed_files)
    active_file_paths = list(allowed_file_paths)
    payload: dict[str, Any] = {
        "surface": "solver_design",
        "file_path_source_tool": _ALGORITHM_FILE_LIST_TOOL,
        "required_first_tool": _ALGORITHM_FILE_LIST_TOOL,
        "required_sequence": [
            _ALGORITHM_FILE_LIST_TOOL,
            tool_name or "context.read_algorithm_file/context.read_algorithm_symbol",
        ],
        "allowed_file_count": len(allowed_file_paths),
        "allowed_file_paths": allowed_file_paths,
        "preferred_active_file_paths": active_file_paths,
        "primary_entrypoint_file_path": (
            "policies/baseline_algorithm.py"
            if "policies/baseline_algorithm.py" in allowed_file_paths
            else ""
        ),
        "allowed_paths_summary": (
            f"{len(allowed_file_paths)} allowlisted solver_design file_path "
            "values are available from context.list_algorithm_files."
        ),
        "path_selection_rule": (
            "Use preferred_active_file_paths for solver_design research: "
            "policies/baseline_algorithm.py and "
            "policies/baseline_modules/*.py."
        ),
        "surface_id_rule": (
            "solver_design is a research surface id; it is not a valid file_path."
        ),
    }
    if active_file_paths:
        payload["example_file_path"] = active_file_paths[0]
    elif allowed_file_paths:
        payload["example_file_path"] = allowed_file_paths[0]
    return payload


def _path_rejected_observation(
    tool: _BaseReadOnlyTool,
    context: ProposalToolContext,
    *,
    allowed_files: tuple[str, ...],
    observation_target: str,
) -> ProposalObservation:
    guidance = _algorithm_file_path_guidance_payload(
        allowed_files,
        tool_name=tool.name,
    )
    return tool._error(
        context,
        failure_code=ProposalToolFailureCode.NOT_FOUND,
        summary=(
            f"Rejected {observation_target} path; use an allowlisted file_path."
        ),
        structured_payload={
            "file_path": _REJECTED_FILE_PATH,
            "path_rejected": True,
            "readable": False,
            "reason": "file_path_not_allowed",
            "allowed_files": list(allowed_files),
            "allowed_file_paths": list(allowed_files),
            "repair_hint": _ALGORITHM_FILE_REPAIR_HINT,
            **guidance,
        },
        repair_hint=_ALGORITHM_FILE_REPAIR_HINT,
    )


__all__ = [
    "ContextListAlgorithmFilesTool",
    "ContextReadActiveSolverDesignTool",
    "ContextReadAlgorithmFileTool",
    "ContextReadAlgorithmSymbolTool",
    "ContextReadSolverCallGraphTool",
    "ListAlgorithmFilesInput",
    "ReadActiveSolverDesignInput",
    "ReadAlgorithmFileInput",
    "ReadAlgorithmSymbolInput",
    "ReadSolverCallGraphInput",
    "algorithm_file_path_guidance",
    "algorithm_file_path_guidance_for_tool",
]
