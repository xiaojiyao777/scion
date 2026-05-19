"""Shared constants for proposal-pipeline agentic failure handling."""
from __future__ import annotations

from scion.proposal.agentic_session import (
    AgenticFailureCategory,
    AgenticTerminationReason,
)

AGENT_GROUNDING_FAILURE = "agent_grounding_failure"
LEGACY_PREMISE_CONTRADICTED = "premise_contradicted"
PROPOSAL_PREMISE_CONTRADICTED = "proposal_premise_contradicted"
AGENT_QUALITY_BLOCKED = "agent_quality_blocked"
AGENTIC_FAILURE_DETAIL_CHARS = 700
FRAMEWORK_CONTROL_FAILURE = "framework_control"
AGENTIC_BUDGET_CONTROL = AgenticFailureCategory.AGENTIC_BUDGET_CONTROL.value
LLM_TRANSIENT_API_ERROR = AgenticFailureCategory.LLM_TRANSIENT_API_ERROR.value
TOOL_BUDGET_EXHAUSTED = AgenticFailureCategory.TOOL_BUDGET_EXHAUSTED.value
ALGORITHM_SMOKE_FAILURE = AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE.value
SESSION_TIMEOUT = AgenticTerminationReason.SESSION_TIMEOUT.value
