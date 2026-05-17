"""Code-generation context helpers for agentic proposal sessions."""
from __future__ import annotations

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
_CODE_PROMPT_LIST_ITEMS = 12
_CODE_PROMPT_MAP_ITEMS = 32
_CODE_PROMPT_FEEDBACK_TOOLS = frozenset(
    {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
        "context.read_branch_state",
    }
)
_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
_SOLVER_DESIGN_BROAD_TERMS = (
    "hybrid", "alns", "vns", "lns", "destroy", "repair",
    "recombination", "route-pool", "route pool", "population",
    "portfolio", "ensemble", "multi-operator", "multi operator",
    "restart", "perturb",
)

def _observation_prompt_payload(observation: ProposalObservation) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
        "structured_payload": _sanitize_agentic_value(observation.structured_payload),
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
    target_file = str(
        code_context.get("target_file") or hypothesis.target_file or ""
    ).strip()
    return (
        surface in _SOLVER_DESIGN_SURFACE_NAMES
        or kind in _SOLVER_DESIGN_SURFACE_NAMES
        or target_file.endswith("policies/baseline_algorithm.py")
        or target_file.endswith("policies/solver_algorithm.py")
        or target_file.startswith("policies/baseline_modules/")
    )


def _solver_design_code_scope_control(
    hypothesis: HypothesisProposal,
    *,
    timeout_retry: bool,
    failure_detail: str | None,
) -> dict[str, Any]:
    broad_terms = _solver_design_broad_terms(hypothesis)
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
                "complete target module content with one primary construction "
                "or seeding path and one bounded improvement/search loop using "
                "no more than two move families"
            ),
            "scope_rule": (
                "Reduce broad hybrid hypotheses to one executable vertical "
                "algorithm slice for this patch. Prefer the focused "
                "solver-design modules under policies/baseline_modules; do not "
                "turn the entrypoint into a context.baseline post-processing "
                "wrapper. The final JSON top-level file_path must remain the "
                "approved target_file; choose target modules by mechanism "
                "ownership, put entrypoint/scheduler/module wiring in "
                "additional_changes, and ensure any new helper is called from "
                "an existing solver path. If scheduler.py or "
                "baseline_algorithm.py is only an integration edit, preserve "
                "the stable runtime contract: baseline_algorithm.py calls "
                "_ALNSVNSSolver(...).solve(instance, rng), and scheduler.py "
                "keeps the class-based _ALNSVNSSolver.__init__(self, *, "
                "time_limit, destroy_ratio, segment_length, reaction_factor, "
                "vns_max_no_improve, use_vns, cw_threshold, vns_threshold, "
                "alns_threshold, max_destroy_customers, max_routes, context) "
                "plus _ALNSVNSSolver.solve(self, instance, rng) path without "
                "top-level solve, run, or main entrypoints. Put new seed or "
                "initial-state hooks inside scheduler methods, not by changing "
                "the baseline_algorithm.py call protocol."
            ),
            "import_rule": (
                "Use package-relative imports inside policies, for example "
                "from .baseline_modules.local_search import _vns or "
                "from .state import _Solution. Do not import "
                "policies.baseline_modules.*."
            ),
            "entrypoint_rule": (
                "If additional_changes touches policies/baseline_algorithm.py, "
                "keep the stable scheduler class API: import _ALNSVNSSolver "
                "from .baseline_modules.scheduler, instantiate it with the "
                "current explicit keywords (time_limit, destroy_ratio, "
                "segment_length, reaction_factor, vns_max_no_improve, use_vns, "
                "cw_threshold, vns_threshold, alns_threshold, "
                "max_destroy_customers, max_routes, context), and call "
                "solver.solve(instance, rng) with no extra seed/context/"
                "initial_solution arguments. Do not import scheduler solve, "
                "run, or main."
            ),
            "context_api_rule": (
                "context.nearest_neighbor() takes no arguments and returns a "
                "public CvrpSolution; do not pass rng and do not call .copy() "
                "on that public solution. Internal _Solution.copy() applies "
                "only to baseline_modules/state.py objects. _Solution has no "
                "from_routes, from_public, from_cvrp_solution, or to_public "
                "bridge API. Do not add those methods to state.py. Existing "
                "construction.py helpers already return internal _Solution "
                "objects; if public route tuples must become internal state, "
                "construct _Solution(instance, [_Route(instance, route) for "
                "route in routes]) and return public output via "
                "context.make_solution(solution.routes_as_tuples())."
            ),
            "state_model_rule": (
                "Do not use policies/baseline_modules/state.py as an "
                "additional-change adapter bridge unless state.py is the "
                "approved target. For scheduler, construction, destroy/repair, "
                "and local_search repairs, re-read the support artifact API "
                "summary and align with the existing _Route/_Solution methods "
                "instead of inventing conversion methods."
            ),
            "target_module_rule": _solver_design_target_module_rule(
                hypothesis.target_file
            ),
            "runtime_rule": (
                "Use explicit loop caps and context time checks; runtime is an "
                "optimization objective and evidence field. Search-bearing "
                "solver-design patches must record real iterations or move "
                "attempts; zero effort on every smoke case fails preview."
            ),
            "local_search_rule": (
                "For local_search targets, integrate new move operators through "
                "the existing _default_vns_operators()/_vns(...) path; do not "
                "invent detached scheduler _run or run entrypoints."
            ),
        }
    )


def _solver_design_broad_terms(
    hypothesis: HypothesisProposal,
) -> list[str]:
    fields = (
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
        hypothesis.complexity_claim,
        hypothesis.runtime_budget_strategy,
    )
    text = "\n".join(str(field or "") for field in fields).lower()
    return [term for term in _SOLVER_DESIGN_BROAD_TERMS if term in text]


def _solver_design_target_module_rule(target_file: str | None) -> str:
    target = str(target_file or "").replace("\\", "/").lstrip("/")
    if target == "policies/baseline_modules/destroy_repair.py":
        return (
            "destroy_repair.py is the primary mechanism owner. Implement "
            "destroy/repair operators in that file; scheduler.py may only "
            "wire exact destroy_repair symbols into destroy_ops/repair_ops. "
            "Do not add scheduler imports from construction.py for a "
            "destroy_repair target unless the same patch also changes "
            "construction.py and defines that exact imported symbol."
        )
    if target == "policies/baseline_modules/local_search.py":
        return (
            "local_search.py is the primary move owner. Wire new move "
            "functions through _default_vns_operators() or existing _vns(...) "
            "calls; do not create detached scheduler entrypoints."
        )
    if target == "policies/baseline_modules/construction.py":
        return (
            "construction.py is the primary seed owner. New construction "
            "helpers must return internal _Solution objects and scheduler.py "
            "may only import exact construction symbols defined by the branch."
        )
    return ""


def _code_prompt_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    latest_full_surface: ProposalObservation | None = None
    for observation in observations:
        if observation.tool_name == "context.read_surface":
            payload = observation.structured_payload
            if (
                not observation.is_error
                and isinstance(payload, Mapping)
                and str(payload.get("detail") or "") == "full"
            ):
                latest_full_surface = observation
            continue
        if observation.tool_name in _CODE_PROMPT_FEEDBACK_TOOLS:
            selected.append(observation)
            continue
        if observation.tool_name == "proposal.algorithm_smoke":
            selected.append(observation)
            continue
        if observation.is_error:
            selected.append(observation)
    if latest_full_surface is not None:
        selected.append(latest_full_surface)
    return selected


def _code_prompt_observation_payload(
    tool_name: str,
    structured_payload: Mapping[str, Any],
) -> Any:
    safe_payload = _sanitize_agentic_value(structured_payload)
    if tool_name == "context.read_surface" and isinstance(safe_payload, Mapping):
        return _compact_code_surface_payload(safe_payload)
    return _compact_code_prompt_value(safe_payload)


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
    ):
        value = code_context.get(key)
        if value is not None:
            summary[f"{key}_chars"] = len(str(value))
    return summary
