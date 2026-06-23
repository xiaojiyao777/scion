"""Renderer for problem-neutral research guidance contracts."""

from __future__ import annotations

from dataclasses import dataclass

from scion.research_guidance.schema import (
    ResearchGuidanceContract,
    validate_research_guidance_contract,
    validate_research_guidance_rendered_paths,
)


@dataclass(frozen=True)
class RenderedResearchGuidance:
    """Rendered proposal guidance plus projection coverage evidence."""

    text: str
    rendered_paths: tuple[str, ...]


def render_research_guidance_contract(
    contract: ResearchGuidanceContract,
) -> RenderedResearchGuidance:
    """Render a valid contract without interpreting problem-owned ids."""

    validate_research_guidance_contract(contract)
    lines: list[str] = []
    rendered_paths: list[str] = []

    def emit(path: str, line: str = "") -> None:
        rendered_paths.append(path)
        lines.append(line)

    emit("schema_version", f"schema_version: {contract.schema_version}")
    emit("problem_family", f"problem_family: {contract.problem_family}")
    emit("current_question", f"current_question: {contract.current_question}")
    emit(
        "visibility",
        (
            "visibility_policy: proposal_only; "
            "proposal_visibility_only: true; "
            "decision_features_excluded: true"
        ),
    )
    emit("decision_boundary", f"decision_boundary: {contract.decision_boundary}")
    emit(
        "decision_features_exclusion",
        "decision_input_policy: proposal-only guidance; excluded from DecisionFeatures",
    )

    lines.append("")
    lines.append("## Required mechanisms")
    for mechanism in contract.required_mechanisms:
        emit(
            f"required_mechanisms.{mechanism.mechanism_id}",
            (
                f"- {mechanism.mechanism_id} [{mechanism.category}]: "
                f"{mechanism.description} "
                f"(hypothesis_mechanism_binding="
                f"{mechanism.hypothesis_mechanism_binding})"
            ),
        )
        _append_optional_list(
            lines,
            "  required_observations",
            mechanism.required_observations,
        )
        _append_optional_list(lines, "  protected_items", mechanism.protected_items)

    lines.append("")
    lines.append("## Evidence requirements")
    for requirement in contract.evidence_requirements:
        emit(
            f"evidence_requirements.{requirement.requirement_id}",
            (
                f"- {requirement.requirement_id} [{requirement.category}]: "
                f"{requirement.description}"
            ),
        )
        _append_optional_list(lines, "  mechanism_ids", requirement.mechanism_ids)
        _append_optional_list(lines, "  protected_items", requirement.protected_items)
        _append_optional_list(lines, "  required_fields", requirement.required_fields)

    lines.append("")
    lines.append("## Avoid rules")
    for rule in contract.avoid_rules:
        emit(
            f"avoid_rules.{rule.rule_id}",
            f"- {rule.rule_id} [{rule.category}]: {rule.description}",
        )
        _append_optional_list(lines, "  applies_to", rule.applies_to)

    lines.append("")
    lines.append("## Continuity requirements")
    for requirement in contract.continuity_requirements:
        emit(
            f"continuity_requirements.{requirement.requirement_id}",
            (
                f"- {requirement.requirement_id} [{requirement.category}]: "
                f"{requirement.description}"
            ),
        )
        _append_optional_list(lines, "  related_ids", requirement.related_ids)

    lines.append("")
    lines.append("## Guidance blocks")
    for block in contract.guidance_blocks:
        emit(
            f"guidance_blocks.{block.block_id}",
            f"- {block.block_id} [{block.category}] {block.title}",
        )
        for line in block.lines:
            lines.append(f"  - {line}")

    if contract.measurement_summary is not None:
        summary = contract.measurement_summary
        lines.append("")
        lines.append("## Measurement guidance")
        emit(
            f"measurement_summary.{summary.summary_id}",
            f"- {summary.summary_id}: {summary.summary}",
        )
        _append_optional_list(lines, "  metric_names", summary.metric_names)
        _append_optional_list(lines, "  limitations", summary.limitations)

    rendered = RenderedResearchGuidance(
        text="\n".join(lines).strip() + "\n",
        rendered_paths=tuple(rendered_paths),
    )
    validate_research_guidance_rendered_paths(contract, rendered.rendered_paths)
    return rendered


def _append_optional_list(
    lines: list[str],
    label: str,
    values: tuple[str, ...],
) -> None:
    if values:
        lines.append(f"{label}: {', '.join(values)}")
