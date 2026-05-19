"""Agentic proposal output classification and bounded failure payloads."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalStatus,
)

from .constants import (
    AGENT_GROUNDING_FAILURE,
    AGENT_QUALITY_BLOCKED,
    AGENTIC_BUDGET_CONTROL,
    AGENTIC_FAILURE_DETAIL_CHARS,
    ALGORITHM_SMOKE_FAILURE,
    LEGACY_PREMISE_CONTRADICTED,
    LLM_TRANSIENT_API_ERROR,
    PROPOSAL_PREMISE_CONTRADICTED,
    SESSION_TIMEOUT,
    TOOL_BUDGET_EXHAUSTED,
)
from .utils import _agentic_value


def _agentic_self_check_failure_detail(
    output: AgenticProposalOutput,
) -> str | None:
    self_check = output.self_check
    has_self_check_transcript = any(
        str(getattr(event, "phase", "") or "") == "self_check"
        or str(getattr(event, "metadata", {}).get("tool_name", "") or "").startswith(
            "proposal."
        )
        for event in output.transcript
    )
    has_self_check_evidence = bool(
        has_self_check_transcript
        or self_check.contract_preview_passed is not None
        or self_check.contract_preview_codes
    )
    if not has_self_check_evidence:
        return None
    if not self_check.schema_valid:
        return "agentic_self_check_failed: schema or target preview did not pass"
    if output.status == AgenticProposalStatus.COMPLETED:
        if self_check.contract_preview_passed is not True:
            codes = ", ".join(self_check.contract_preview_codes)
            suffix = f" ({codes})" if codes else ""
            return (
                "agentic_self_check_failed: contract preview did not pass"
                f"{suffix}"
            )
    return None


def _agentic_quality_block_classification(
    output: AgenticProposalOutput,
) -> dict[str, str] | None:
    structured = (
        output.structured_rejection
        if isinstance(output.structured_rejection, Mapping)
        else {}
    )
    termination_reason = _agentic_value(output.termination_reason)
    failure_category = _agentic_value(output.failure_category)
    failure_code = str(structured.get("failure_code") or "")
    premise_check = str(structured.get("premise_check") or "")
    detail = str(output.failure_detail or "").lower()
    if (
        failure_category == ALGORITHM_SMOKE_FAILURE
        or failure_code == ALGORITHM_SMOKE_FAILURE
        or "algorithm smoke did not pass" in detail
        or "runtime_smoke.telemetry_guard" in detail
    ):
        return {
            "failure_class": ALGORITHM_SMOKE_FAILURE,
            "failure_code": ALGORITHM_SMOKE_FAILURE,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        failure_code == PROPOSAL_PREMISE_CONTRADICTED
        or failure_category in {
            AGENT_GROUNDING_FAILURE,
            LEGACY_PREMISE_CONTRADICTED,
        }
        or termination_reason == LEGACY_PREMISE_CONTRADICTED
        or premise_check == "contradicted"
    ):
        return {
            "failure_class": AGENT_GROUNDING_FAILURE,
            "failure_code": PROPOSAL_PREMISE_CONTRADICTED,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    return None


def _agentic_output_is_quality_blocked(output: AgenticProposalOutput) -> bool:
    return _agentic_quality_block_classification(output) is not None


def _agentic_detail_is_framework_boundary(detail: str | None) -> bool:
    text = str(detail or "").lower()
    return (
        "contractgate-approved hypothesis" in text
        or "forced_surface_constraint" in text
    )


def _agentic_output_is_control_timeout(
    output: AgenticProposalOutput | None,
    detail: str | None = None,
) -> bool:
    reason = _agentic_value(getattr(output, "termination_reason", None))
    category = _agentic_value(getattr(output, "failure_category", None))
    combined_detail = " ".join(
        part
        for part in (
            str(detail or ""),
            str(getattr(output, "failure_detail", "") or ""),
        )
        if part
    ).lower()
    if reason == SESSION_TIMEOUT:
        return True
    if category == AGENTIC_BUDGET_CONTROL:
        return True
    if category == TOOL_BUDGET_EXHAUSTED and reason == SESSION_TIMEOUT:
        return True
    return (
        "session_timeout" in combined_detail
        and ("agentic" in combined_detail or "max_wall_time_sec" in combined_detail)
    )


def _agentic_output_is_llm_transient_api_error(
    output: AgenticProposalOutput | None,
    detail: str | None = None,
) -> bool:
    category = _agentic_value(getattr(output, "failure_category", None))
    if category == LLM_TRANSIENT_API_ERROR:
        return True
    combined_detail = " ".join(
        part
        for part in (
            str(detail or ""),
            str(getattr(output, "failure_detail", "") or ""),
        )
        if part
    ).lower()
    return (
        "llm_transient_api_error" in combined_detail
        or "transient api" in combined_detail
        or "transient provider error" in combined_detail
        or "bad gateway" in combined_detail
        or "gateway timeout" in combined_detail
        or "service unavailable" in combined_detail
    )


def _bounded_agentic_failure_text(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) <= AGENTIC_FAILURE_DETAIL_CHARS:
        return text
    return text[: AGENTIC_FAILURE_DETAIL_CHARS - 3].rstrip() + "..."


def _agentic_primary_secondary_failures(
    output: AgenticProposalOutput,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    reason = _agentic_value(output.termination_reason)
    quality = _agentic_quality_block_classification(output)
    secondary: list[dict[str, str]] = []
    if (
        output.status == AgenticProposalStatus.COMPLETED
        and not output.failure_detail
        and output.self_check.schema_valid is not False
        and output.self_check.contract_preview_passed is not False
        and quality is None
    ):
        return {}, secondary
    if quality is not None:
        primary = {
            "stage": AGENT_QUALITY_BLOCKED,
            "reason": quality["failure_code"],
            "category": quality["failure_class"],
            "code": quality["failure_code"],
        }
        if output.failure_detail:
            primary["detail"] = _bounded_agentic_failure_text(output.failure_detail)
        return primary, secondary

    if output.self_check.schema_valid is False:
        primary = {
            "stage": "self_check",
            "reason": "schema_or_target_preview_failed",
            "category": "contract_boundary_failure",
        }
        if output.self_check.schema_preview_codes:
            primary["code"] = _bounded_agentic_failure_text(
                output.self_check.schema_preview_codes[0]
            )
        if output.failure_detail:
            primary["detail"] = _bounded_agentic_failure_text(output.failure_detail)
        return primary, secondary

    if output.self_check.contract_preview_passed is False:
        primary = {
            "stage": "self_check",
            "reason": "contract_preview_failed",
            "category": "contract_boundary_failure",
        }
        if output.self_check.contract_preview_codes:
            primary["code"] = _bounded_agentic_failure_text(
                output.self_check.contract_preview_codes[0]
            )
        if output.failure_detail:
            primary["detail"] = _bounded_agentic_failure_text(output.failure_detail)
        return primary, secondary

    primary = {
        "stage": reason or "agentic_proposal",
        "reason": _bounded_agentic_failure_text(output.failure_detail or reason),
    }
    category = _agentic_value(output.failure_category)
    if category:
        primary["category"] = category
    return primary, secondary


def _agentic_rejection_constraint(
    output: AgenticProposalOutput,
) -> dict[str, Any] | None:
    structured = (
        output.structured_rejection
        if isinstance(output.structured_rejection, Mapping)
        else {}
    )
    if not structured:
        return None
    quality = _agentic_quality_block_classification(output)
    if quality is None:
        return None
    return {
        key: value
        for key, value in {
            "source": structured.get("source") or "mechanism_novelty_gate",
            "gate_name": structured.get("gate_name"),
            "mechanism": structured.get("mechanism"),
            "premise_check": structured.get("premise_check"),
            "failure_category": _agentic_value(output.failure_category),
            "failure_code": quality["failure_code"],
            "agent_block_reason": quality["block_reason"],
            "reason": _bounded_agentic_failure_text(structured.get("reason")),
            "evidence": [
                _bounded_agentic_failure_text(item)
                for item in list(structured.get("evidence") or ())[:8]
            ],
            "snapshot_digest": structured.get("snapshot_digest"),
            "selected_surface": structured.get("selected_surface"),
            "target_file": structured.get("target_file"),
            "retry_constraint": (
                "Do not repeat this missing-premise or duplicate mechanism. "
                "Choose a different mechanism family supported by active-solver "
                "evidence; changing names or novelty text is not enough."
            ),
        }.items()
        if value
    }
