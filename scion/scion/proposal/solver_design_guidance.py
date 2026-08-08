"""Materialize problem-owned guidance for the direct V3 provider context."""

from __future__ import annotations

from typing import Any, Mapping


RENDERER_INPUTS_KEY = "proposal_renderer_inputs"
SOLVER_DESIGN_GUIDANCE_KEY = "solver_design_prompt_guidance"


def materialize_solver_design_prompt_guidance(
    provider: Any,
    context: Mapping[str, Any],
    *,
    phase: str,
    hypothesis: Any | None = None,
) -> dict[str, Any]:
    """Return one problem-owned guidance packet without alternate modes."""

    if provider is None:
        return {}
    if phase == "hypothesis":
        return {
            "hypothesis_guidance": _provider_lines(
                provider,
                "solver_design_hypothesis_guidance",
                context,
            )
        }
    if phase != "code" or hypothesis is None:
        raise ValueError(f"unsupported solver-design guidance phase: {phase}")
    return {
        "code_rules": _provider_lines(
            provider,
            "solver_design_code_rules",
            context,
        ),
        "user_constraints": _provider_lines(
            provider,
            "solver_design_user_constraints",
            context,
        ),
    }


def _provider_lines(
    provider: Any,
    method_name: str,
    context: Mapping[str, Any],
) -> list[str]:
    method = getattr(provider, method_name, None)
    if not callable(method):
        return []
    rendered = method(context)
    if isinstance(rendered, str):
        rendered = rendered.splitlines()
    return [str(line).strip() for line in rendered or () if str(line).strip()]


__all__ = [
    "RENDERER_INPUTS_KEY",
    "SOLVER_DESIGN_GUIDANCE_KEY",
    "materialize_solver_design_prompt_guidance",
]
