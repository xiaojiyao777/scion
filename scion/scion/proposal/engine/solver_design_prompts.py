"""Solver-design prompt-provider glue for proposal-engine prompts."""

from __future__ import annotations

from typing import Any, Mapping

from scion.problem.providers import resolve_solver_design_prompt_provider

from .prompt_common import (
    _format_bulleted_section,
    _format_bullets,
    _limit_code_phase_text,
)


_SOLVER_DESIGN_CODE_PROBLEM_OBJECT_CHARS = 1800
_SOLVER_DESIGN_CODE_SOLVER_MECHANICS_CHARS = 1800
_SOLVER_DESIGN_CODE_INTERFACE_CHARS = 2400
_SOLVER_DESIGN_CODE_HYPOTHESIS_CHARS = 3000
_SOLVER_DESIGN_CODE_API_MANIFEST_CHARS = 4200
_SOLVER_DESIGN_CODE_INTEGRATION_FILES_CHARS = 22000
_SOLVER_DESIGN_COMPACT_RETRY_PROBLEM_OBJECT_CHARS = 1200
_SOLVER_DESIGN_COMPACT_RETRY_SOLVER_MECHANICS_CHARS = 1200
_SOLVER_DESIGN_COMPACT_RETRY_INTERFACE_CHARS = 1600
_SOLVER_DESIGN_COMPACT_RETRY_HYPOTHESIS_CHARS = 1600
_SOLVER_DESIGN_COMPACT_RETRY_API_MANIFEST_CHARS = 2600
_SOLVER_DESIGN_COMPACT_RETRY_INTEGRATION_FILES_CHARS = 12000
_SOLVER_DESIGN_BROAD_SCOPE_TERMS = (
    "hybrid",
    "population",
    "portfolio",
    "ensemble",
    "multi-operator",
    "multi operator",
    "restart",
    "perturb",
)


def _solver_design_hypothesis_guidance(context: Mapping[str, Any]) -> list[str]:
    provider = _solver_design_prompt_provider(context)
    lines = _provider_prompt_lines(
        provider,
        "solver_design_hypothesis_guidance",
        context,
    )
    if lines:
        return lines
    return [
        (
            "For `solver_design`, choose the target file by mechanism ownership, "
            "not by convenience."
        ),
        (
            "Ground `solver_design` hypotheses in active solver facts and prior "
            "screening/runtime feedback; name the bottleneck the algorithm-body "
            "change is expected to move."
        ),
        (
            "For `solver_design` expected_telemetry, use selected-surface "
            "evidence categories, not ad hoc top-level runtime field names."
        ),
    ]


def _solver_design_code_rules_section(
    context: Mapping[str, Any],
    *,
    is_solver_design_surface: bool,
) -> str:
    if not is_solver_design_surface:
        return ""
    provider = _solver_design_prompt_provider(context)
    lines = _provider_prompt_lines(provider, "solver_design_code_rules", context)
    if not lines:
        lines = [
            (
                "Implement a complete solver-design algorithm body for the "
                "approved target rather than a lifecycle/config dictionary."
            ),
            (
                "Keep the patch to one executable algorithm slice with explicit "
                "bounds and the minimal helper functions needed for that path."
            ),
            (
                "Do not change problem objective semantics, feasibility "
                "constraints, parsing, seeds, protocol splits, Decision rules, "
                "or adapter/runtime files."
            ),
        ]
    return "\n" + _format_bulleted_section("Full Solver-Algorithm Rules", lines)


def _solver_design_user_constraints(
    context: Mapping[str, Any],
    *,
    is_solver_design_surface: bool,
) -> str:
    if not is_solver_design_surface:
        return ""
    provider = _solver_design_prompt_provider(context)
    lines = _provider_prompt_lines(
        provider,
        "solver_design_user_constraints",
        context,
    )
    if not lines:
        lines = [
            (
                "For solver-design surfaces, return the complete contents of the "
                "approved target algorithm module."
            ),
            (
                "If the approved solver-design change requires more than one file "
                "to be executable, set the top-level `file_path` exactly to the "
                "approved `target_file` and put minimal integration edits in "
                "`additional_changes`."
            ),
            (
                "Use the supplied interface specification, API manifest, and "
                "branch-current integration files as the source of truth for "
                "imports and object-model details."
            ),
        ]
    return _format_bullets(lines)


def _code_hypothesis_detail(
    context: Mapping[str, Any],
    is_solver_design_surface: bool,
) -> str:
    detail = str(context.get("hypothesis_detail") or "")
    if not is_solver_design_surface:
        return detail
    if (
        str(context.get("code_generation_mode") or "").strip()
        == "compact_timeout_retry"
    ):
        return _limit_code_phase_text(
            detail,
            _SOLVER_DESIGN_COMPACT_RETRY_HYPOTHESIS_CHARS,
            label="hypothesis detail",
        )
    return _limit_code_phase_text(
        detail,
        _SOLVER_DESIGN_CODE_HYPOTHESIS_CHARS,
        label="hypothesis detail",
    )


def _solver_design_scope_control_section(
    context: Mapping[str, Any],
    *,
    is_solver_design_surface: bool,
) -> str:
    if not is_solver_design_surface:
        return ""
    scope = context.get("agentic_code_scope_control")
    if not isinstance(scope, Mapping):
        scope = {}
    mode = str(context.get("code_generation_mode") or scope.get("mode") or "").strip()
    broad_terms = _solver_design_broad_terms(context)
    if not broad_terms and isinstance(scope.get("detected_broad_terms"), list):
        broad_terms = [
            str(term)
            for term in scope.get("detected_broad_terms", ())
            if str(term).strip()
        ]
    provider = _solver_design_prompt_provider(context)
    lines = _provider_prompt_lines(
        provider,
        "solver_design_scope_guidance",
        context,
        mode=mode,
        broad_terms=broad_terms,
    )
    if not lines:
        lines = [
            "Scion controls the research boundary; the code agent should still write a real algorithm, but this patch must be small enough to generate, review, preview, and screen.",
            "Implement one primary mechanism now and keep the replacement file compact.",
            "If the approved solver-design change needs more than one file, keep the top-level `file_path` on the approved target and put minimal executable wiring in `additional_changes`.",
            "Every search loop must have explicit finite bounds and should use the provided context time-budget helpers where available.",
            "Record movement evidence through the selected surface telemetry helpers where the interface supports them.",
        ]
        if mode:
            lines.append(f"Current code-generation mode: `{mode}`.")
        if broad_terms:
            lines.append(
                "The approved hypothesis mentions broad mechanisms "
                f"({', '.join(dict.fromkeys(broad_terms))}). Reduce them to one "
                "executable path for this patch."
            )
        if scope.get("failure_detail"):
            lines.append(
                "Previous code generation timed out. Shrink implementation "
                "breadth before adding algorithmic detail."
            )
    telemetry_obligation = str(scope.get("telemetry_obligation_rule") or "").strip()
    if telemetry_obligation:
        lines.append(telemetry_obligation)
    return "\n" + _format_bulleted_section(
        "Compact Solver-Design Implementation Scope",
        lines,
    )


def _solver_design_broad_terms(context: Mapping[str, Any]) -> list[str]:
    provider_terms: tuple[str, ...] = ()
    provider = _solver_design_prompt_provider(context)
    terms_method = getattr(provider, "solver_design_broad_scope_terms", None)
    if callable(terms_method):
        provider_terms = tuple(
            str(term).lower()
            for term in terms_method()
            if str(term).strip()
        )
    text = "\n".join(
        str(context.get(key) or "")
        for key in (
            "hypothesis_detail",
            "prior_code_failure",
            "target_runtime_effect",
            "complexity_claim",
            "runtime_budget_strategy",
        )
    ).lower()
    terms = (*_SOLVER_DESIGN_BROAD_SCOPE_TERMS, *provider_terms)
    return [term for term in dict.fromkeys(terms) if term in text]


def _solver_design_prompt_provider(context: Mapping[str, Any]) -> Any | None:
    for key in (
        "solver_design_prompt_provider",
        "problem_prompt_provider",
        "prompt_provider",
    ):
        provider = context.get(key)
        if provider is not None:
            return provider
    return resolve_solver_design_prompt_provider(
        problem_spec=context.get("problem_spec"),
        adapter=context.get("adapter"),
    )


def _provider_prompt_lines(
    provider: Any | None,
    method_name: str,
    context: Mapping[str, Any],
    **kwargs: Any,
) -> list[str]:
    method = getattr(provider, method_name, None)
    if not callable(method):
        return []
    try:
        rendered = method(context, **kwargs)
    except TypeError:
        rendered = method(context)
    if isinstance(rendered, str):
        rendered = rendered.splitlines()
    return [str(line).strip() for line in rendered or () if str(line).strip()]
