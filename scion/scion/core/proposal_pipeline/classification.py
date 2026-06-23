"""Agentic proposal output classification and bounded failure payloads."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.branch_repair_policy import (
    repair_policy_check_violation_code_from_detail,
)
from scion.core.repeated_contract_failures import (
    REPEATED_CONTRACT_FAILURE_CODE,
    REPEATED_CONTRACT_REROUTE_REASON,
)
from scion.proposal.agentic_session import (
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalStatus,
)

from .constants import (
    ACTIVATION_NOT_OBSERVED_DIAGNOSTIC,
    AGENT_GROUNDING_FAILURE,
    AGENT_QUALITY_BLOCKED,
    AGENTIC_BUDGET_CONTROL,
    AGENTIC_FAILURE_DETAIL_CHARS,
    ALGORITHM_SMOKE_FAILURE,
    BOUNDARY_CONTRADICTED,
    BRANCH_FOLLOWUP_POLICY_VIOLATION,
    LEGACY_PREMISE_CONTRADICTED,
    LLM_TRANSIENT_API_ERROR,
    OBJECTIVE_POLICY_CONTRADICTED,
    PROPOSAL_ACTIVATION_DIAGNOSTIC,
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
    if _structured_mechanism_novelty_diagnostic(structured):
        return None
    detail = str(output.failure_detail or "").lower()
    if _detail_is_soft_novelty_diagnostic(detail):
        return None
    if (
        "schema_quality_block" in detail
        or "mechanism_changes_duplicate_id_conflict" in detail
    ):
        return {
            "failure_class": AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE.value,
            "failure_code": "mechanism_changes_duplicate_id_conflict",
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        failure_code == BRANCH_FOLLOWUP_POLICY_VIOLATION
        or failure_category == BRANCH_FOLLOWUP_POLICY_VIOLATION
        or BRANCH_FOLLOWUP_POLICY_VIOLATION in detail
    ):
        return {
            "failure_class": AGENT_GROUNDING_FAILURE,
            "failure_code": BRANCH_FOLLOWUP_POLICY_VIOLATION,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        failure_category == ACTIVATION_NOT_OBSERVED_DIAGNOSTIC
        or failure_code == ACTIVATION_NOT_OBSERVED_DIAGNOSTIC
        or ACTIVATION_NOT_OBSERVED_DIAGNOSTIC in detail
    ):
        return None
    if (
        failure_category == PROPOSAL_ACTIVATION_DIAGNOSTIC
        or failure_code == PROPOSAL_ACTIVATION_DIAGNOSTIC
        or PROPOSAL_ACTIVATION_DIAGNOSTIC in detail
    ):
        return {
            "failure_class": PROPOSAL_ACTIVATION_DIAGNOSTIC,
            "failure_code": PROPOSAL_ACTIVATION_DIAGNOSTIC,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
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
        failure_code
        in {REPEATED_CONTRACT_REROUTE_REASON, REPEATED_CONTRACT_FAILURE_CODE}
        or REPEATED_CONTRACT_REROUTE_REASON in detail
        or REPEATED_CONTRACT_FAILURE_CODE.lower() in detail
    ):
        return {
            "failure_class": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "failure_code": REPEATED_CONTRACT_REROUTE_REASON,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        failure_code in {BOUNDARY_CONTRADICTED, OBJECTIVE_POLICY_CONTRADICTED}
        or failure_category in {BOUNDARY_CONTRADICTED, OBJECTIVE_POLICY_CONTRADICTED}
    ):
        code = (
            failure_code
            if failure_code in {BOUNDARY_CONTRADICTED, OBJECTIVE_POLICY_CONTRADICTED}
            else failure_category
        )
        return {
            "failure_class": code,
            "failure_code": code,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        str(structured.get("agent_block_reason") or "") == AGENT_QUALITY_BLOCKED
        or f"{AGENT_QUALITY_BLOCKED}:" in detail
    ):
        code = failure_code or _agent_quality_detail_code(detail)
        if not code:
            code = failure_category or AGENT_QUALITY_BLOCKED
        return {
            "failure_class": failure_category or AGENT_GROUNDING_FAILURE,
            "failure_code": code,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    if (
        failure_code == PROPOSAL_PREMISE_CONTRADICTED
        or failure_category in {
            AGENT_GROUNDING_FAILURE,
            LEGACY_PREMISE_CONTRADICTED,
        }
        or termination_reason == LEGACY_PREMISE_CONTRADICTED
        or (
            premise_check == "contradicted"
            and not _structured_mechanism_novelty_diagnostic(structured)
        )
    ):
        return {
            "failure_class": AGENT_GROUNDING_FAILURE,
            "failure_code": PROPOSAL_PREMISE_CONTRADICTED,
            "block_reason": AGENT_QUALITY_BLOCKED,
        }
    return None


def _agentic_output_is_quality_blocked(output: AgenticProposalOutput) -> bool:
    return _agentic_quality_block_classification(output) is not None


def _agent_quality_detail_code(detail: str) -> str:
    marker = f"{AGENT_QUALITY_BLOCKED}:"
    if marker not in detail:
        return ""
    suffix = detail.split(marker, 1)[1].strip()
    if not suffix:
        return AGENT_QUALITY_BLOCKED
    code = suffix.split(":", 1)[0].strip()
    return f"{marker}{code}" if code else AGENT_QUALITY_BLOCKED


def _structured_mechanism_novelty_diagnostic(
    structured: Mapping[str, Any],
) -> bool:
    if str(structured.get("source") or "") != "mechanism_novelty_gate":
        return False
    diagnostic_kind = str(structured.get("diagnostic_kind") or "")
    return (
        structured.get("gate_action") == "diagnostic"
        or structured.get("screening_allowed") is True
        or str(structured.get("result_kind") or "").endswith("_diagnostic")
        or diagnostic_kind
        in {
            "novelty_warning",
            "duplicate_risk",
            "grounding_risk",
            "mechanism_premise_warning",
        }
    )


def _detail_is_soft_novelty_diagnostic(detail: str) -> bool:
    return any(
        marker in detail
        for marker in (
            "mechanism_premise_warning",
            "mechanism_novelty_warning",
            "mechanism_novelty_diagnostic",
            "novelty_warning",
            "duplicate_risk",
            "gate_action=diagnostic",
            '"gate_action": "diagnostic"',
            "screening_allowed=true",
            '"screening_allowed": true',
            "quality_block=false",
            '"quality_block": false',
        )
    )


def _agentic_explicit_runtime_failure(
    output: AgenticProposalOutput,
) -> dict[str, str] | None:
    category = _agentic_value(output.failure_category)
    if category not in {
        LLM_TRANSIENT_API_ERROR,
        AGENTIC_BUDGET_CONTROL,
        TOOL_BUDGET_EXHAUSTED,
    }:
        return None
    reason = _agentic_value(output.termination_reason) or "agentic_proposal"
    primary = {
        "stage": reason,
        "reason": _bounded_agentic_failure_text(output.failure_detail or reason),
        "category": category,
    }
    if category == TOOL_BUDGET_EXHAUSTED:
        primary["code"] = TOOL_BUDGET_EXHAUSTED
    return primary


def _agentic_detail_is_framework_boundary(detail: str | None) -> bool:
    text = str(detail or "").lower()
    return (
        "contractgate-approved hypothesis" in text
        or "forced_surface_constraint" in text
        or repair_policy_check_violation_code_from_detail(detail) is not None
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
        if (
            output.failure_detail
            and quality["failure_code"] != REPEATED_CONTRACT_REROUTE_REASON
        ):
            primary["detail"] = _bounded_agentic_failure_text(output.failure_detail)
        return primary, secondary

    explicit_runtime_failure = _agentic_explicit_runtime_failure(output)
    if explicit_runtime_failure is not None:
        return explicit_runtime_failure, secondary

    if output.self_check.schema_valid is False:
        category = (
            AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE.value
            if _schema_invalid_is_mechanism_change_type_output_failure(output)
            else "contract_boundary_failure"
        )
        primary = {
            "stage": "self_check",
            "reason": "schema_or_target_preview_failed",
            "category": category,
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


def _schema_invalid_is_mechanism_change_type_output_failure(
    output: AgenticProposalOutput,
) -> bool:
    category = _agentic_value(output.failure_category)
    if category == AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE.value:
        return True
    text = " ".join(
        str(value or "")
        for value in (
            output.failure_detail,
            *tuple(output.self_check.schema_preview_codes or ()),
        )
    ).lower()
    if "mechanism_changes" not in text or "change_type" not in text:
        return False
    return (
        "input should be" in text
        or "literal_error" in text
        or "enum" in text
        or "parameterize" in text
        or "telemetry_wiring" in text
        or "tune" in text
    )


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
    payload = {
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
            "fact_packet_digest": structured.get("fact_packet_digest"),
            "fact_provenance": structured.get("fact_provenance"),
            "variant_allowed": structured.get("variant_allowed"),
            "contradicted_span": structured.get("contradicted_span"),
            "matched_span": structured.get("matched_span"),
            "allowed_variant_guidance": structured.get("allowed_variant_guidance"),
            "selected_surface": structured.get("selected_surface"),
            "target_file": structured.get("target_file"),
            "reason_code": structured.get("reason_code"),
            "check_id": structured.get("check_id"),
            "category_id": structured.get("category_id"),
            "threshold": structured.get("threshold"),
            "count": structured.get("count"),
            "prior_count": structured.get("prior_count"),
            "missing_claims": structured.get("missing_claims"),
            "missing_code_elements": structured.get("missing_code_elements"),
            "counts_as_screened_round": structured.get("counts_as_screened_round"),
            "counts_as_proposal_quality_attempt": structured.get(
                "counts_as_proposal_quality_attempt"
            ),
            "retry_constraint": (
                structured.get("retry_constraint")
                or "Acknowledge the existing mechanism and state the material "
                "trigger, scoring, schedule, or behavior difference. Do not "
                "change research direction merely to satisfy novelty wording."
            ),
    }
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", (), [], {})
    }
