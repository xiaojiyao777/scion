"""Failure classification helpers for Agentic Proposal Sessions."""

from __future__ import annotations

import re
from typing import Any, Mapping

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.agentic_models import (
    AgenticFailureCategory,
    AgenticProposalPhase,
    AgenticProposalOutput,
    AgenticProposalSessionState,
    AgenticProposalStatus,
    AgenticTerminationReason,
)
from scion.proposal.agentic_preview import (
    _preview_observation_passed,
    _preview_skip_is_agentic_budget_control,
)
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _enum_value,
    _limit_string,
    _sanitize_agentic_value,
)
from scion.proposal.llm_client import (
    LLMRetryExhaustedError,
    is_llm_transient_api_error,
)
from scion.proposal.tools import ProposalObservation

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
_FAILURE_LEDGER_SCHEMA_VERSION = "agentic-retry-error-ledger.v1"
_AGENT_GROUNDING_FAILURE = "agent_grounding_failure"
_LEGACY_PREMISE_CONTRADICTED = AgenticFailureCategory.PREMISE_CONTRADICTED.value
_PROPOSAL_PREMISE_CONTRADICTED_CODE = "proposal_premise_contradicted"
_AGENT_QUALITY_BLOCKED_REASON = "agent_quality_blocked"


def _record_failure_ledger_entry(
    state: AgenticProposalSessionState,
    *,
    phase: AgenticProposalPhase,
    category: AgenticFailureCategory | str,
    detail: str | None = None,
    source: str = "",
    attempt: int | None = None,
    repair_attempt: int | None = None,
    tool_name: str | None = None,
    observation: ProposalObservation | None = None,
    failure_code: str | None = None,
) -> None:
    category_value = _failure_category_value(category)
    if not category_value:
        return
    if category_value == _LEGACY_PREMISE_CONTRADICTED:
        category_value = _AGENT_GROUNDING_FAILURE
        failure_code = failure_code or _PROPOSAL_PREMISE_CONTRADICTED_CODE
    observation_payload: dict[str, Any] = {}
    if observation is not None:
        observation_payload = {
            "observation_id": observation.observation_id,
            "tool_name": observation.tool_name,
            "failure_code": _enum_value(observation.failure_code),
        }
    entry = _drop_empty_dict(
        {
            "entry_id": f"failure-{len(state.failure_ledger) + 1:04d}",
            "phase": phase.value,
            "category": category_value,
            "root_cause": category_value,
            "detail": _limit_string(str(detail or ""), 800),
            "source": source,
            "attempt": attempt,
            "repair_attempt": repair_attempt,
            "tool_name": tool_name or observation_payload.get("tool_name"),
            "observation_id": observation_payload.get("observation_id"),
            "failure_code": failure_code or observation_payload.get("failure_code"),
        }
    )
    if _failure_ledger_latest_matches(state.failure_ledger, entry):
        return
    state.failure_ledger.append(entry)


def _failure_ledger_latest_matches(
    entries: list[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> bool:
    if not entries:
        return False
    latest = entries[-1]
    return (
        str(latest.get("phase") or "") == str(candidate.get("phase") or "")
        and str(latest.get("category") or "") == str(candidate.get("category") or "")
        and str(latest.get("detail") or "") == str(candidate.get("detail") or "")
        and str(latest.get("source") or "") == str(candidate.get("source") or "")
        and str(latest.get("tool_name") or "") == str(candidate.get("tool_name") or "")
    )


def _failure_ledger_payload(
    entries: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> dict[str, Any]:
    sanitized_entries = [
        _sanitize_agentic_value(dict(entry)) for entry in entries if entry
    ]
    return {
        "schema_version": _FAILURE_LEDGER_SCHEMA_VERSION,
        "entries": sanitized_entries,
        "entry_count": len(sanitized_entries),
        "first_root_cause": (
            sanitized_entries[0].get("root_cause") if sanitized_entries else None
        ),
        "first_failure_phase": (
            sanitized_entries[0].get("phase") if sanitized_entries else None
        ),
        "latest_failure": (
            sanitized_entries[-1].get("category") if sanitized_entries else None
        ),
        "latest_failure_phase": (
            sanitized_entries[-1].get("phase") if sanitized_entries else None
        ),
    }


def _failure_category_value(category: AgenticFailureCategory | str | None) -> str:
    return str(_enum_value(category) or "")


def _structured_output_failure_category(
    exc: BaseException,
) -> AgenticFailureCategory:
    if is_llm_transient_api_error(exc):
        return AgenticFailureCategory.LLM_TRANSIENT_API_ERROR
    if isinstance(exc, LLMRetryExhaustedError):
        return AgenticFailureCategory.STRUCTURED_OUTPUT_RETRY_EXHAUSTED
    return AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE


def _normalized_structured_rejection(
    rejection: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(rejection)
    if _structured_rejection_is_premise_contradicted(payload):
        legacy_category = str(_enum_value(payload.get("failure_category")) or "")
        if legacy_category and legacy_category != _AGENT_GROUNDING_FAILURE:
            payload.setdefault("legacy_failure_category", legacy_category)
        payload["failure_category"] = _AGENT_GROUNDING_FAILURE
        payload.setdefault("failure_code", _PROPOSAL_PREMISE_CONTRADICTED_CODE)
        payload.setdefault("agent_block_reason", _AGENT_QUALITY_BLOCKED_REASON)
    return payload


def _hypothesis_semantic_retry_rejection_payload(
    rejection: Mapping[str, Any],
    attempt: int,
) -> dict[str, Any]:
    payload = _normalized_structured_rejection(rejection)
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": payload.get("source") or "mechanism_novelty_gate",
            "gate_name": payload.get("gate_name"),
            "mechanism": payload.get("mechanism"),
            "premise_check": payload.get("premise_check"),
            "failure_category": payload.get("failure_category"),
            "legacy_failure_category": payload.get("legacy_failure_category"),
            "failure_code": payload.get("failure_code"),
            "agent_block_reason": payload.get("agent_block_reason"),
            "reason": _limit_string(payload.get("reason"), 1200),
            "evidence": _compact_string_list(payload.get("evidence"), 8, 180),
            "snapshot_digest": payload.get("snapshot_digest"),
            "selected_surface": payload.get("selected_surface"),
            "target_file": payload.get("target_file"),
            "retry_constraint": (
                "Do not repeat this missing-premise or duplicate mechanism. "
                "Choose a different mechanism family with active-solver evidence."
            ),
        }
    )


def _structured_rejection_is_premise_contradicted(
    rejection: Mapping[str, Any],
) -> bool:
    failure_category = str(_enum_value(rejection.get("failure_category")) or "")
    failure_code = str(rejection.get("failure_code") or "")
    premise_check = str(rejection.get("premise_check") or "")
    return (
        failure_code == _PROPOSAL_PREMISE_CONTRADICTED_CODE
        or premise_check == "contradicted"
        or failure_category == _LEGACY_PREMISE_CONTRADICTED
    )


def _rejection_termination_reason(
    rejection: Mapping[str, Any],
) -> AgenticTerminationReason:
    failure_category = str(_enum_value(rejection.get("failure_category")) or "")
    if _structured_rejection_is_premise_contradicted(rejection) or (
        failure_category == _AGENT_GROUNDING_FAILURE
    ):
        return AgenticTerminationReason.PREMISE_CONTRADICTED
    if failure_category == AgenticFailureCategory.DUPLICATE_MECHANISM.value:
        return AgenticTerminationReason.DUPLICATE_MECHANISM
    if str(rejection.get("source") or "") == "mechanism_novelty_gate":
        return AgenticTerminationReason.MECHANISM_NOVELTY_REJECTED
    return AgenticTerminationReason.MECHANISM_NOVELTY_REJECTED


def _terminal_failure_category(
    output: AgenticProposalOutput,
    state: AgenticProposalSessionState,
) -> AgenticFailureCategory | str | None:
    if output.status == AgenticProposalStatus.COMPLETED:
        return None
    if output.failure_category is not None:
        return output.failure_category
    if output.termination_reason in {
        AgenticTerminationReason.TOOL_LOOP_LIMIT,
        AgenticTerminationReason.SESSION_TIMEOUT,
        AgenticTerminationReason.REPEATED_TOOL_CALL,
    } or state.loop_stop_reason in {
        "tool_loop_limit",
        "observation_budget_exhausted",
        "session_timeout",
        "repeated_tool_call",
    }:
        return AgenticFailureCategory.TOOL_BUDGET_EXHAUSTED
    return None


def _patch_premise_rejection(
    patch: PatchProposal,
    hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    premise_check = str(getattr(patch, "premise_check", "supported") or "supported")
    if premise_check == "supported":
        return None
    if premise_check not in {"contradicted", "duplicate", "wrong_owner"}:
        premise_check = "contradicted"
    reason = str(getattr(patch, "premise_check_reason", "") or "").strip()
    category = (
        AgenticFailureCategory.DUPLICATE_MECHANISM.value
        if premise_check == "duplicate"
        else AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value
        if premise_check == "wrong_owner"
        else _AGENT_GROUNDING_FAILURE
    )
    rejection = {
        "artifact_kind": "agentic_code_premise_rejection",
        "premise_check": premise_check,
        "failure_category": category,
        "reason": reason,
        "selected_surface": hypothesis.change_locus,
        "target_file": hypothesis.target_file,
        "patch_generated": False,
        "screening_allowed": False,
    }
    if premise_check == "contradicted":
        rejection["legacy_failure_category"] = _LEGACY_PREMISE_CONTRADICTED
        rejection["failure_code"] = _PROPOSAL_PREMISE_CONTRADICTED_CODE
        rejection["agent_block_reason"] = _AGENT_QUALITY_BLOCKED_REASON
    return rejection


def _preview_failure_category(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> AgenticFailureCategory:
    for observation in reversed(observations):
        if not observation.is_error and _preview_observation_passed(observation):
            continue
        if _preview_skip_is_agentic_budget_control(observation):
            return AgenticFailureCategory.AGENTIC_BUDGET_CONTROL
        if observation.tool_name == "proposal.schema_preview":
            return AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE
        if observation.tool_name == "proposal.algorithm_smoke":
            return AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE
        if observation.tool_name == "proposal.contract_preview":
            if _contract_preview_indicates_patch_graph_failure(observation):
                return AgenticFailureCategory.PATCH_GRAPH_FAILURE
            return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
        if observation.tool_name == "proposal.target_permission_preview":
            return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE
    return AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE


def _contract_preview_indicates_patch_graph_failure(
    observation: ProposalObservation,
) -> bool:
    text_values = [
        str(value).strip().lower()
        for value in _preview_text_values(observation.structured_payload)
        if str(value).strip()
    ]
    text_values.extend(
        value
        for value in (
            str(observation.summary or "").strip().lower(),
            str(_enum_value(observation.failure_code) or "").strip().lower(),
        )
        if value
    )
    joined = "\n".join(text_values)
    if "import_graph" in joined or "import graph" in joined:
        return True
    return any(
        value.startswith("c8")
        or value.startswith("c9e")
        or ": c8" in value
        or ": c9e" in value
        for value in text_values
    )


def _preview_text_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for item in value.values():
            values.extend(_preview_text_values(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_preview_text_values(item))
    elif value is not None:
        values.append(str(value))
    return values


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


def _compact_string_list(value: Any, limit: int, max_chars: int) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in list(value)[: max(0, limit)]:
        text = _limit_string(item, max_chars)
        if text:
            result.append(text)
    return result
