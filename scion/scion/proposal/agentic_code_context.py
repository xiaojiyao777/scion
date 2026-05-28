"""Code-generation context helpers for agentic proposal sessions."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_diagnostics import _research_diagnosis_from_observations
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _drop_empty_mapping,
    _enum_value,
    _limit_string,
    _sanitize_agentic_value,
)
from scion.proposal.llm_client import LLMRetryExhaustedError, LLMTimeoutError
from scion.proposal.tools import ProposalObservation

_CODE_PROMPT_STRING_CHARS = 1600
_CODE_PROMPT_ALGORITHM_FILE_CHARS = 24000
_CODE_PROMPT_ALGORITHM_SYMBOL_CHARS = 12000
_CODE_PROMPT_LIST_ITEMS = 12
_CODE_PROMPT_MAP_ITEMS = 32
_CODE_PROMPT_MAX_ALGORITHM_READS = 3
_CODE_PROMPT_FEEDBACK_TOOLS = frozenset(
    {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
        "context.read_branch_state",
    }
)
_CODE_PROMPT_ALGORITHM_TOOLS = frozenset(
    {
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }
)
_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
def _observation_prompt_payload(observation: ProposalObservation) -> dict[str, Any]:
    structured_payload = _sanitize_agentic_value(observation.structured_payload)
    digest_payload = {
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "structured_payload": structured_payload,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "digest": digest,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
        "structured_payload": structured_payload,
    }


def _code_observation_prompt_payload(
    observation: ProposalObservation,
) -> dict[str, Any]:
    payload = _observation_prompt_payload(observation)
    payload["structured_payload"] = _code_prompt_observation_payload(
        observation.tool_name,
        observation.structured_payload,
    )
    return _drop_empty_dict(payload)


def _preview_repair_feedback_prompt_payload(
    observation: ProposalObservation,
) -> dict[str, Any]:
    payload = _observation_prompt_payload(observation)
    if observation.tool_name == "proposal.algorithm_smoke" and isinstance(
        payload.get("structured_payload"),
        Mapping,
    ):
        payload["structured_payload"] = _compact_algorithm_smoke_repair_feedback(
            payload["structured_payload"]
        )
    return _drop_empty_dict(payload)


def _compact_algorithm_smoke_repair_feedback(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_failure = _compact_algorithm_smoke_runtime_failure_feedback(payload)
    actionable = _first_mapping_item(payload.get("actionable_telemetry_feedback"))
    static_preview = payload.get("telemetry_static_preview")
    static = static_preview if isinstance(static_preview, Mapping) else {}
    telemetry_guard = payload.get("telemetry_guard")
    guard = telemetry_guard if isinstance(telemetry_guard, Mapping) else {}
    failure = _first_mapping_item(guard.get("failures"))
    diagnostic = payload.get("activation_diagnostic")
    activation_diagnostic = diagnostic if isinstance(diagnostic, Mapping) else {}
    telemetry_diagnostics = _compact_telemetry_diagnostics(
        payload.get("telemetry_diagnostics")
    )
    mechanism = str(
        (actionable or {}).get("mechanism_id")
        or (actionable or {}).get("failure_mechanism_id")
        or activation_diagnostic.get("mechanism_id")
        or activation_diagnostic.get("telemetry_failure_mechanism")
        or (failure or {}).get("mechanism")
        or ""
    ).strip()
    offending_fields = _compact_string_list(
        (actionable or {}).get("delta_valued_fields")
        or activation_diagnostic.get("missing_fields")
        or activation_diagnostic.get("telemetry_failure_field")
        or (failure or {}).get("field")
        or static.get("checked_fields")
    )
    failure_code = str(
        runtime_failure.get("failure_code")
        or (actionable or {}).get("failure_code")
        or activation_diagnostic.get("failure_code")
        or activation_diagnostic.get("code")
        or (failure or {}).get("code")
        or _first_text(static.get("issue_codes"))
        or payload.get("failure_code")
        or payload.get("failure_class")
        or "algorithm_smoke_failure"
    ).strip()
    if failure_code == "algorithm_smoke_failure:algorithm_smoke_failure":
        failure_code = "algorithm_smoke_failure"
    required_calls = _compact_repair_required_calls(static.get("required_calls"))
    return _drop_empty_dict(
        {
            "passed": payload.get("passed"),
            "failure_code": failure_code,
            "mechanism_id": mechanism,
            "primary_issue": _compact_failure_text(payload.get("primary_issue"), 420),
            "agent_summary": _drop_empty_dict(
                {
                    "primary_issue": _compact_failure_text(
                        payload.get("primary_issue"), 420
                    ),
                    "failure_code": payload.get("failure_code"),
                    "failure_class": payload.get("failure_class"),
                }
            ),
            "runtime_failure": runtime_failure,
            "offending_fields": offending_fields,
            "required_calls": required_calls,
            "allowed_repair_shape": _allowed_repair_shape(actionable, required_calls),
            "forbidden_repair_shape": (
                "Do not rename the mechanism id, weaken expected_telemetry, "
                "fabricate positive deltas, force unconditional activation, use "
                "max(..., 1), or add guarantee-positive fallback behavior just "
                "to satisfy smoke."
            ),
            "conditional_activation_guidance": (
                "For rare-trigger mechanisms, instrument the natural condition, "
                "decision/context counters, budget counters, diagnostic skipped "
                "status, or a canary-targeted threshold. Do not change algorithm "
                "behavior only to manufacture telemetry."
            ),
            "actionable_telemetry_feedback": _compact_actionable_feedback(actionable),
            "activation_diagnostic": _compact_activation_diagnostic(
                activation_diagnostic
            ),
            "telemetry_diagnostics": telemetry_diagnostics,
        }
    )


def _compact_algorithm_smoke_runtime_failure_feedback(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_smoke = payload.get("runtime_smoke")
    if not isinstance(runtime_smoke, Mapping):
        return {}
    audit = runtime_smoke.get("runtime_audit_failure")
    audit_payload = audit if isinstance(audit, Mapping) else {}
    subprocess = payload.get("subprocess")
    if not isinstance(subprocess, Mapping):
        subprocess = runtime_smoke.get("subprocess")
    if not isinstance(subprocess, Mapping):
        subprocess = {}
    counters = runtime_smoke.get("runtime_counters")
    counters_payload = counters if isinstance(counters, Mapping) else {}
    if not audit_payload and not subprocess.get("error_category"):
        return {}
    return _drop_empty_dict(
        {
            "failure_code": "algorithm_smoke_runtime_failure",
            "error_category": audit_payload.get("error_category")
            or subprocess.get("error_category"),
            "detail": _compact_failure_text(
                audit_payload.get("detail")
                or subprocess.get("detail")
                or payload.get("primary_issue"),
                420,
            ),
            "runtime_error_field": audit_payload.get("runtime_error_field"),
            "runtime_error_count": audit_payload.get("runtime_error_count"),
            "failed_runtime_fields": _compact_string_list(
                audit_payload.get("failed_runtime_fields")
            ),
            "event_tail": _compact_failure_text(
                audit_payload.get("event_tail")
                or subprocess.get("stderr_tail")
                or subprocess.get("stdout_tail"),
                360,
            ),
            "runtime_counters": _compact_runtime_failure_counters(counters_payload),
        }
    )


def _compact_runtime_failure_counters(
    counters: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not counters:
        return None
    result: dict[str, Any] = {}
    for key, value in counters.items():
        normalized = str(key).replace(".", "_")
        if (
            normalized.endswith("_errors")
            or normalized.endswith("_active")
            or normalized.endswith("_loaded")
            or normalized.endswith("_stop_reason")
        ):
            result[str(key)] = _compact_code_prompt_value(value, depth=0)
        if len(result) >= 8:
            break
    return result or None


def _compact_activation_diagnostic(
    diagnostic: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not diagnostic:
        return None
    return _drop_empty_dict(
        {
            "failure_code": diagnostic.get("failure_code") or diagnostic.get("code"),
            "mechanism_id": diagnostic.get("mechanism_id")
            or diagnostic.get("telemetry_failure_mechanism"),
            "kind": diagnostic.get("activation_diagnostic_kind"),
            "diagnostic_type": diagnostic.get("diagnostic_type"),
            "layer": diagnostic.get("layer") or diagnostic.get("source"),
            "missing_fields": _compact_string_list(diagnostic.get("missing_fields")),
            "detected_records": _compact_code_prompt_value(
                diagnostic.get("detected_records"),
                depth=0,
            ),
            "allowed_repair": _limit_string(diagnostic.get("allowed_repair"), 280),
            "forbidden_repair": _limit_string(
                diagnostic.get("forbidden_repair"),
                280,
            ),
        }
    )


def _compact_telemetry_diagnostics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    diagnostics: list[dict[str, Any]] = []
    for item in value[:4]:
        if not isinstance(item, Mapping):
            continue
        diagnostics.append(
            _drop_empty_dict(
                {
                    "diagnostic_type": item.get("diagnostic_type"),
                    "mechanism_id": item.get("mechanism_id"),
                    "category": item.get("category"),
                    "field": item.get("field"),
                    "activation_status": item.get("activation_status"),
                    "effect_status": item.get("effect_status"),
                    "allowed_repair": _limit_string(item.get("allowed_repair"), 220),
                }
            )
        )
    return diagnostics


def _allowed_repair_shape(
    actionable: Mapping[str, Any] | None,
    required_calls: list[str],
) -> str:
    declaration_alternative = str(
        (actionable or {}).get("declaration_alternative") or ""
    ).strip()
    if declaration_alternative:
        return _limit_string(declaration_alternative, 360)
    if required_calls:
        return "Add the required mechanism-specific telemetry call(s) on the natural active path while preserving existing passed records."
    return "Repair only the specific runtime/API/telemetry issue reported here while preserving the same hypothesis and integration wiring."


def _compact_actionable_feedback(
    actionable: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not actionable:
        return None
    return _drop_empty_dict(
        {
            "failure_code": actionable.get("failure_code"),
            "mechanism_id": actionable.get("mechanism_id")
            or actionable.get("failure_mechanism_id"),
            "category": actionable.get("category"),
            "delta_valued_fields": _compact_string_list(
                actionable.get("delta_valued_fields")
            ),
            "expected_call_pattern": _limit_string(
                actionable.get("expected_call_pattern"),
                220,
            ),
            "declaration_alternative": _limit_string(
                actionable.get("declaration_alternative"),
                360,
            ),
        }
    )


def _compact_repair_required_calls(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    calls: list[str] = []
    for item in value.values():
        calls.extend(_compact_string_list(item, limit=3))
        if len(calls) >= 4:
            break
    return calls[:4]


def _first_mapping_item(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return None


def _compact_string_list(value: Any, *, limit: int = 4) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, Mapping):
        raw_values = [json.dumps(value, sort_keys=True, default=str)]
    else:
        try:
            raw_values = list(value)
        except TypeError:
            raw_values = [value]
    result: list[str] = []
    for item in raw_values:
        text = _limit_string(item, 240)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _first_text(value: Any) -> str:
    items = _compact_string_list(value, limit=1)
    return items[0] if items else ""


def _compact_failure_text(value: Any, max_chars: int) -> str:
    text = str(_limit_string(value, max_chars) or "")
    while "algorithm_smoke_failure:algorithm_smoke_failure" in text:
        text = text.replace(
            "algorithm_smoke_failure:algorithm_smoke_failure",
            "algorithm_smoke_failure",
        )
    return text


def _with_code_scope_control(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    timeout_retry: bool,
    failure_detail: str | None = None,
) -> dict[str, Any]:
    prepared = dict(code_context)
    if not _is_solver_design_code_context(prepared, hypothesis):
        return prepared
    if timeout_retry:
        prepared["code_generation_mode"] = "compact_timeout_retry"
    else:
        prepared.setdefault("code_generation_mode", "compact_solver_design")
    prepared["agentic_code_scope_control"] = _solver_design_code_scope_control(
        prepared,
        hypothesis,
        timeout_retry=timeout_retry,
        failure_detail=failure_detail,
    )
    return prepared


def _code_timeout_retry_context(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    exc: BaseException,
    observations: list[ProposalObservation],
) -> dict[str, Any]:
    detail = _code_timeout_failure_detail(exc)
    retry_context = _with_code_scope_control(
        dict(code_context),
        hypothesis,
        timeout_retry=True,
        failure_detail=detail,
    )
    retry_context["prior_code_failure"] = detail
    if observations:
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            retry_context["agentic_research_diagnosis"] = research_diagnosis
        from scion.proposal.agentic_grounding import (
            _active_algorithm_facts_for_prompt_context,
        )

        active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
            observations
        )
        if active_algorithm_facts:
            retry_context["agentic_active_algorithm_facts"] = active_algorithm_facts
        retry_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in _code_prompt_observations(observations)
        ]
    return retry_context


def _code_timeout_failure_detail(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return (
        "code_generation_timeout: final patch generation timed out before "
        "returning a patch. Retry with a compact bounded implementation. "
        f"Original error: {text}"
    )


def _is_code_generation_timeout(exc: BaseException) -> bool:
    if isinstance(exc, LLMTimeoutError):
        return True
    if isinstance(exc, LLMRetryExhaustedError):
        lowered = str(exc).lower()
        return "timed out" in lowered or "timeout" in lowered
    return False


def _is_solver_design_code_context(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
) -> bool:
    surface = str(
        code_context.get("research_surface_name")
        or code_context.get("change_locus")
        or hypothesis.change_locus
        or ""
    ).strip()
    kind = str(code_context.get("research_surface_kind") or "").strip()
    return (
        surface in _SOLVER_DESIGN_SURFACE_NAMES
        or kind in _SOLVER_DESIGN_SURFACE_NAMES
    )


def _solver_design_code_scope_control(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    timeout_retry: bool,
    failure_detail: str | None,
) -> dict[str, Any]:
    broad_terms = _solver_design_broad_terms(code_context, hypothesis)
    mechanism_ids = _solver_design_mechanism_ids(hypothesis)
    return _drop_empty_mapping(
        {
            "mode": (
                "compact_timeout_retry" if timeout_retry else "compact_solver_design"
            ),
            "surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "failure_detail": failure_detail,
            "detected_broad_terms": broad_terms,
            "required_shape": (
                "complete target module content with one primary mechanism, "
                "explicit bounds, and the minimal integration needed to reach "
                "the active solver path"
            ),
            "scope_rule": (
                "Reduce broad hybrid hypotheses to one executable vertical "
                "algorithm slice for this patch. The final JSON top-level "
                "file_path must remain the approved target_file; put only "
                "minimal executable integration in additional_changes, and "
                "ensure any new helper is called from the active solver path."
            ),
            "import_rule": (
                "Use only imports allowed by the selected surface and the "
                "problem-owned interface/manifest supplied in context."
            ),
            "entrypoint_rule": (
                "Preserve the selected surface entrypoint and return contract "
                "exactly. If integration edits are required, base them on the "
                "problem-owned manifest and branch-current files in context."
            ),
            "runtime_rule": (
                "Use explicit loop caps and context time checks; runtime is an "
                "optimization objective and evidence field. Search-bearing "
                "solver-design patches must record real iterations or move "
                "attempts; zero effort on every smoke case fails preview."
            ),
            "telemetry_repair_rule": (
                "When repairing telemetry preview or smoke failures, preserve "
                "mechanism-specific records that already satisfied an earlier "
                "category. Add the missing activation/effect/budget evidence "
                "through the telemetry helpers declared by the selected "
                "surface; do not rename the mechanism id or weaken the "
                "approved telemetry contract. Use the exact mechanism id from "
                "mechanism_changes. Activation should be recorded at the real "
                "branch point where the mechanism is attempted or selected; "
                "effect should be recorded from real objective/runtime deltas "
                "when they exist. Baseline or structural telemetry ids outside "
                "mechanism_changes are diagnostic context only; do not "
                "introduce or increase them as mechanism evidence. Do not "
                "force rare branches to run, fabricate positive counters, "
                "wrap counters with max(..., 1), or add "
                "fallback behavior whose only purpose is satisfying telemetry."
            ),
            "telemetry_obligation_rule": _solver_design_telemetry_obligation_rule(
                mechanism_ids
            ),
        }
    )


def _solver_design_mechanism_ids(hypothesis: HypothesisProposal) -> list[str]:
    ids: list[str] = []
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        mechanism_id = str(getattr(change, "id", "") or "").strip()
        if mechanism_id and mechanism_id not in ids:
            ids.append(mechanism_id)
    return ids


def _solver_design_telemetry_obligation_rule(mechanism_ids: list[str]) -> str:
    if not mechanism_ids:
        return ""
    ids = ", ".join(f"`{mechanism_id}`" for mechanism_id in mechanism_ids)
    return (
        "Declared mechanism telemetry obligations: every mechanism_changes id "
        f"({ids}) must have active-path evidence using that exact id. Include "
        "the selected surface's declared activity, activation, effect, or "
        "budget records for each declared id unless premise_check is "
        "duplicate/contradicted/wrong_owner. Do not only record a parent "
        "mechanism while leaving a helper mechanism id without evidence. "
        "Baseline, structural, or broad phase telemetry ids outside this set "
        "are diagnostic context only: preserve them only when unchanged, and "
        "do not introduce or increase them as evidence for this hypothesis."
    )


def _solver_design_broad_terms(
    code_context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
) -> list[str]:
    provider_terms: list[str] = []
    provider = (
        code_context.get("solver_design_prompt_provider")
        or code_context.get("problem_prompt_provider")
        or code_context.get("prompt_provider")
    )
    terms_method = getattr(provider, "solver_design_broad_scope_terms", None)
    if callable(terms_method):
        provider_terms = [
            str(term).lower()
            for term in terms_method()
            if str(term).strip()
        ]
    fields = (
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
        hypothesis.complexity_claim,
        hypothesis.runtime_budget_strategy,
    )
    text = "\n".join(str(field or "") for field in fields).lower()
    return [term for term in dict.fromkeys(provider_terms) if term in text]


def _code_prompt_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    latest_surface: ProposalObservation | None = None
    algorithm_reads: list[ProposalObservation] = []
    algorithm_read_keys: set[tuple[str, str, str]] = set()
    for observation in observations:
        if observation.tool_name == "context.read_surface":
            payload = observation.structured_payload
            if (
                not observation.is_error
                and isinstance(payload, Mapping)
            ):
                latest_surface = observation
            continue
        if observation.tool_name in _CODE_PROMPT_ALGORITHM_TOOLS:
            if not observation.is_error:
                key = _algorithm_read_prompt_key(observation)
                if key in algorithm_read_keys:
                    for index, current in enumerate(algorithm_reads):
                        if _algorithm_read_prompt_key(current) == key:
                            algorithm_reads[index] = observation
                            break
                else:
                    algorithm_read_keys.add(key)
                    algorithm_reads.append(observation)
                    if len(algorithm_reads) > _CODE_PROMPT_MAX_ALGORITHM_READS:
                        dropped = algorithm_reads.pop(0)
                        algorithm_read_keys.discard(
                            _algorithm_read_prompt_key(dropped)
                        )
            continue
        if observation.tool_name in _CODE_PROMPT_FEEDBACK_TOOLS:
            selected.append(observation)
            continue
        if observation.tool_name == "proposal.algorithm_smoke":
            selected.append(observation)
            continue
        if observation.is_error:
            selected.append(observation)
    selected.extend(algorithm_reads)
    if latest_surface is not None:
        selected.append(latest_surface)
    return selected


def _algorithm_read_prompt_key(
    observation: ProposalObservation,
) -> tuple[str, str, str]:
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return (observation.tool_name, "", "")
    return (
        observation.tool_name,
        str(payload.get("file_path") or ""),
        str(payload.get("symbol") or ""),
    )


def _code_prompt_observation_payload(
    tool_name: str,
    structured_payload: Mapping[str, Any],
) -> Any:
    safe_payload = _sanitize_agentic_value(structured_payload)
    if tool_name == "context.read_surface" and isinstance(safe_payload, Mapping):
        return _compact_code_surface_payload(safe_payload)
    if tool_name == "context.read_algorithm_file" and isinstance(
        safe_payload,
        Mapping,
    ):
        return _compact_code_algorithm_file_payload(safe_payload)
    if tool_name == "context.read_algorithm_symbol" and isinstance(
        safe_payload,
        Mapping,
    ):
        return _compact_code_algorithm_symbol_payload(safe_payload)
    return _compact_code_prompt_value(safe_payload)


def _compact_code_algorithm_file_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "already_observed": payload.get("already_observed"),
            "source_observation_id": payload.get("source_observation_id"),
            "read_receipt": _compact_code_prompt_value(payload.get("read_receipt")),
            "surface": payload.get("surface"),
            "file_path": payload.get("file_path"),
            "symbol": payload.get("symbol"),
            "readable": payload.get("readable"),
            "source": payload.get("source"),
            "digest": payload.get("digest"),
            "source_digest": _canonical_code_source_digest(payload),
            "source_digest_hash": _noncanonical_code_source_digest(payload),
            "truncated": payload.get("truncated"),
            "size_chars": payload.get("size_chars"),
            "max_chars": payload.get("max_chars"),
            "coverage": _compact_code_prompt_value(payload.get("coverage")),
            "content_preview": _limit_string(
                payload.get("content_preview"),
                _CODE_PROMPT_ALGORITHM_FILE_CHARS,
            ),
            "python_api_summary": _limit_string(
                payload.get("python_api_summary"),
                2400,
            ),
        }
    )


def _compact_code_algorithm_symbol_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "already_observed": payload.get("already_observed"),
            "source_observation_id": payload.get("source_observation_id"),
            "read_receipt": _compact_code_prompt_value(payload.get("read_receipt")),
            "surface": payload.get("surface"),
            "file_path": payload.get("file_path"),
            "symbol": payload.get("symbol"),
            "readable": payload.get("readable"),
            "source": payload.get("source"),
            "digest": payload.get("digest"),
            "source_digest": _canonical_code_source_digest(payload),
            "source_digest_hash": _noncanonical_code_source_digest(payload),
            "truncated": payload.get("truncated"),
            "coverage": _compact_code_prompt_value(payload.get("coverage")),
            "content_preview": _limit_string(
                payload.get("content_preview"),
                _CODE_PROMPT_ALGORITHM_SYMBOL_CHARS,
            ),
        }
    )


def _canonical_code_source_digest(payload: Mapping[str, Any]) -> str:
    for key in ("source_digest", "sha256"):
        value = payload.get(key)
        if _looks_like_sha256(value):
            return str(value)
    content = payload.get("content_preview")
    if isinstance(content, str) and content and _payload_content_is_complete(payload):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ""


def _noncanonical_code_source_digest(payload: Mapping[str, Any]) -> Any:
    value = payload.get("source_digest")
    if _looks_like_sha256(value):
        return ""
    return _compact_code_prompt_value(value)


def _payload_content_is_complete(payload: Mapping[str, Any]) -> bool:
    if payload.get("readable") is not True:
        return False
    if bool(payload.get("truncated")):
        return False
    preview_chars = len(str(payload.get("content_preview") or ""))
    for key in ("size_chars", "max_chars"):
        try:
            expected = int(payload.get(key))
        except Exception:
            continue
        if expected >= 0 and preview_chars >= expected:
            return True
    return False


def _looks_like_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def _compact_code_surface_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    artifact = payload.get("current_artifact")
    current_artifact = (
        _code_artifact_metadata(artifact) if isinstance(artifact, Mapping) else {}
    )
    return _drop_empty_mapping(
        {
            "surface": _compact_code_prompt_value(payload.get("surface")),
            "surface_contract": _compact_code_prompt_value(
                payload.get("surface_contract")
            ),
            "detail": payload.get("detail"),
            "section": payload.get("section"),
            "declared_targets": _compact_code_prompt_value(
                payload.get("declared_targets")
            ),
            "target_file": payload.get("target_file"),
            "current_artifact": current_artifact,
            "support_artifacts": _compact_code_support_artifacts(
                payload.get("support_artifacts")
            ),
        }
    )


def _compact_code_support_artifacts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    artifacts: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, Mapping):
            continue
        preview = item.get("content_preview")
        artifacts.append(
            _drop_empty_mapping(
                {
                    "file_path": item.get("file_path"),
                    "readable": item.get("readable"),
                    "reason": item.get("reason"),
                    "source": item.get("source"),
                    "truncated": item.get("truncated"),
                    "size_chars": item.get("size_chars"),
                    "content_preview": _limit_string(preview, 1000),
                    "python_api_summary": _limit_string(
                        item.get("python_api_summary"),
                        1200,
                    ),
                }
            )
        )
    if len(value) > 8:
        artifacts.append({"_truncated_items": len(value) - 8})
    return [artifact for artifact in artifacts if artifact]


def _code_artifact_metadata(artifact: Mapping[str, Any]) -> dict[str, Any]:
    content_preview = artifact.get("content_preview")
    metadata = {
        "file_path": artifact.get("file_path"),
        "readable": artifact.get("readable"),
        "reason": artifact.get("reason"),
        "source": artifact.get("source"),
        "truncated": artifact.get("truncated"),
        "size_chars": artifact.get("size_chars"),
        "max_chars": artifact.get("max_chars"),
        "content_preview_chars": (
            len(str(content_preview)) if content_preview is not None else None
        ),
        "content_preview_omitted": content_preview is not None or None,
    }
    return _drop_empty_mapping(metadata)


def _compact_code_prompt_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return _limit_string(value, _CODE_PROMPT_STRING_CHARS)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _CODE_PROMPT_MAP_ITEMS:
                compact["_truncated_items"] = len(value) - _CODE_PROMPT_MAP_ITEMS
                break
            key_text = str(key)
            if key_text in {
                "content_preview",
                "interface_summary",
                "problem_object",
                "target_file_code",
                "champion_operators_code",
                "reference_operators",
            }:
                if key_text == "content_preview":
                    compact["content_preview_omitted"] = True
                    compact["content_preview_chars"] = len(str(item))
                elif item:
                    compact[f"{key_text}_chars"] = len(str(item))
                continue
            if key_text == "current_artifact" and isinstance(item, Mapping):
                compact[key_text] = _code_artifact_metadata(item)
                continue
            compact[key_text] = _compact_code_prompt_value(item, depth=depth + 1)
        return _drop_empty_mapping(compact)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        items = [
            _compact_code_prompt_value(item, depth=depth + 1)
            for item in value[:_CODE_PROMPT_LIST_ITEMS]
        ]
        if len(value) > _CODE_PROMPT_LIST_ITEMS:
            items.append({"_truncated_items": len(value) - _CODE_PROMPT_LIST_ITEMS})
        return items
    if isinstance(value, str):
        return _limit_string(value, _CODE_PROMPT_STRING_CHARS) or ""
    return value

def _code_context_tool_summary(code_context: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    compact_keys = (
        "research_surface_name",
        "research_surface_kind",
        "change_locus",
        "target_file",
        "editable_patterns",
        "frozen_patterns",
        "import_whitelist",
        "prior_code_failure",
    )
    for key in compact_keys:
        if key in code_context:
            summary[key] = _sanitize_agentic_value(code_context.get(key))
    for key in (
        "target_file_code",
        "champion_operators_code",
        "reference_operators",
        "operator_interface_spec",
        "problem_summary",
        "problem_object",
        "solver_mechanics",
        "solver_design_api_manifest",
        "solver_design_branch_current_integration_files",
    ):
        value = code_context.get(key)
        if value is not None:
            summary[f"{key}_chars"] = len(str(value))
    return summary
