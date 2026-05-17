"""Base implementation for read-only proposal tools."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from pydantic import BaseModel

from scion.proposal.tools.models import (
    EmptyInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)
from scion.proposal.tools.utils import _error_observation, _strip_forbidden_payload_refs

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

__all__ = ["_BaseReadOnlyTool"]
