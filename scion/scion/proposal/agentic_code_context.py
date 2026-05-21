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
_SOLVER_DESIGN_BROAD_TERMS = (
    "hybrid", "lns", "destroy", "repair",
    "recombination", "population",
    "portfolio", "ensemble", "multi-operator", "multi operator",
    "restart", "perturb",
)

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
                "approved telemetry contract."
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
        "mechanism while leaving a helper mechanism id without evidence."
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
    terms = (*_SOLVER_DESIGN_BROAD_TERMS, *provider_terms)
    return [term for term in dict.fromkeys(terms) if term in text]


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
            "surface": payload.get("surface"),
            "file_path": payload.get("file_path"),
            "readable": payload.get("readable"),
            "source": payload.get("source"),
            "truncated": payload.get("truncated"),
            "size_chars": payload.get("size_chars"),
            "max_chars": payload.get("max_chars"),
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
            "surface": payload.get("surface"),
            "file_path": payload.get("file_path"),
            "symbol": payload.get("symbol"),
            "readable": payload.get("readable"),
            "source": payload.get("source"),
            "truncated": payload.get("truncated"),
            "content_preview": _limit_string(
                payload.get("content_preview"),
                _CODE_PROMPT_ALGORITHM_SYMBOL_CHARS,
            ),
        }
    )


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
