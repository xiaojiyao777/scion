"""Problem-generic active solver map context tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scion.proposal.active_solver_map import (
    read_active_solver_map_payload,
    read_algorithm_slice_payload,
    read_operator_registry_payload,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolPermission,
)


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadActiveSolverMapInput(_StrictInput):
    surface: str | None = Field(
        default=None,
        description="Declared research surface id/name for the active solver map.",
    )
    subject_id: str | None = Field(
        default=None,
        description="Optional provider-owned solver subject id.",
    )


class ReadOperatorRegistryInput(_StrictInput):
    registry_id: str = Field(
        min_length=1,
        description=(
            "One registry_id returned by context.read_active_solver_map "
            "operator_registries[].registry_id."
        ),
    )
    surface: str | None = None
    subject_id: str | None = None


class ReadAlgorithmSliceInput(_StrictInput):
    slice_id: str = Field(
        min_length=1,
        description=(
            "One slice_id returned by context.read_active_solver_map "
            "algorithm_slices[].slice_id."
        ),
    )
    surface: str | None = None
    subject_id: str | None = None
    max_chars: int = Field(default=12000, ge=0, le=24000)


class ContextReadActiveSolverMapTool(_BaseReadOnlyTool):
    name = "context.read_active_solver_map"
    input_schema = ReadActiveSolverMapInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    max_result_chars = 64000

    def call(
        self,
        args: ReadActiveSolverMapInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload = read_active_solver_map_payload(
            context,
            surface=args.surface,
            subject_id=args.subject_id,
        )
        return self._observation(
            context,
            observation_type=_observation_type("active_solver_map", payload),
            summary=_summary("active solver map", payload),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadOperatorRegistryTool(_BaseReadOnlyTool):
    name = "context.read_operator_registry"
    input_schema = ReadOperatorRegistryInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    max_result_chars = 48000

    def call(
        self,
        args: ReadOperatorRegistryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload = read_operator_registry_payload(
            context,
            registry_id=args.registry_id,
            surface=args.surface,
            subject_id=args.subject_id,
        )
        return self._observation(
            context,
            observation_type=_observation_type("operator_registry", payload),
            summary=_summary("operator registry", payload),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


class ContextReadAlgorithmSliceTool(_BaseReadOnlyTool):
    name = "context.read_algorithm_slice"
    input_schema = ReadAlgorithmSliceInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    max_result_chars = 48000

    def call(
        self,
        args: ReadAlgorithmSliceInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload = read_algorithm_slice_payload(
            context,
            slice_id=args.slice_id,
            surface=args.surface,
            subject_id=args.subject_id,
            max_chars=args.max_chars,
        )
        return self._observation(
            context,
            observation_type=_observation_type("algorithm_slice", payload),
            summary=_summary("algorithm slice", payload),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


def _observation_type(prefix: str, payload: dict[str, Any]) -> str:
    return prefix if payload.get("available") else f"{prefix}_unavailable"


def _summary(label: str, payload: dict[str, Any]) -> str:
    if payload.get("available"):
        return f"Returned provider-declared {label} with read receipt."
    unavailable = payload.get("unavailable")
    reason = ""
    if isinstance(unavailable, dict):
        reason = str(unavailable.get("reason") or "").strip()
    suffix = f": {reason}" if reason else "."
    return f"Returned structured unavailable {label}{suffix}"


__all__ = [
    "ContextReadActiveSolverMapTool",
    "ContextReadAlgorithmSliceTool",
    "ContextReadOperatorRegistryTool",
    "ReadActiveSolverMapInput",
    "ReadAlgorithmSliceInput",
    "ReadOperatorRegistryInput",
]
