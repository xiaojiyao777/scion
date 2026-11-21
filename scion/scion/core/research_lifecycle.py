"""Explicit invocation intent and a non-scientific research conclusion."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchConclusion:
    """A saved ordinary material reference, never an H or a scientific verdict."""

    ref: str


def validate_run_intent(run_intent, formal_stage_limit):
    if run_intent not in {"formal_target", "investigation"}:
        raise ValueError("run_intent must be formal_target or investigation")
    if run_intent == "formal_target":
        if formal_stage_limit is not None:
            raise ValueError("formal_stage_limit requires investigation")
    elif type(formal_stage_limit) is not int or formal_stage_limit < 0:
        raise ValueError("investigation requires a nonnegative formal_stage_limit")


def validate_investigation(*, run_intent, formal_stage_limit, public_research,
                           research_input, code_research_limits, resource_envelope):
    validate_run_intent(run_intent, formal_stage_limit)
    if run_intent != "investigation":
        return
    from scion.observation.config import normalize_public_research
    from scion.core.research_input import normalize_research_input
    cfg = normalize_public_research(public_research)
    normalize_research_input(research_input)
    if (not (cfg.public_observation_enabled or cfg.research_materials_enabled)
            or code_research_limits is None
            or resource_envelope.provider_call_cap is None
            or resource_envelope.outer_hardwall_sec is None):
        raise ValueError("investigation requires O/M, research limits and explicit provider/wall caps")
