"""Typed, problem-neutral research guidance contract schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

SUPPORTED_VISIBILITY_POLICIES = ("proposal_only",)
SUPPORTED_HYPOTHESIS_MECHANISM_BINDINGS = (
    "required",
    "context_only",
    "target_intent_required",
)


class ResearchGuidanceValidationError(ValueError):
    """Raised when a research guidance contract must fail closed."""


@dataclass(frozen=True)
class GuidanceContext:
    """Generic context passed into a problem-owned guidance provider."""

    problem_family: str
    campaign_id: str | None = None
    branch_id: str | None = None
    stage: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuidanceVisibility:
    """Visibility markers required for proposal-only guidance."""

    visibility_policy: str = "proposal_only"
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True


@dataclass(frozen=True)
class RequiredMechanism:
    """A problem-owned mechanism that generic code may carry but not interpret."""

    mechanism_id: str
    category: str
    description: str
    required_observations: tuple[str, ...] = ()
    protected_items: tuple[str, ...] = ()
    hypothesis_mechanism_binding: str = "required"
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class EvidenceRequirement:
    """Evidence that a problem package requires for proposal guidance."""

    requirement_id: str
    category: str
    description: str
    mechanism_ids: tuple[str, ...] = ()
    protected_items: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class AvoidRule:
    """Proposal guidance describing an avoided pattern."""

    rule_id: str
    category: str
    description: str
    applies_to: tuple[str, ...] = ()
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class ContinuityRequirement:
    """Proposal guidance that preserves research continuity."""

    requirement_id: str
    category: str
    description: str
    related_ids: tuple[str, ...] = ()
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class GuidanceBlock:
    """A stable, typed block rendered by generic prompt projection."""

    block_id: str
    category: str
    title: str
    lines: tuple[str, ...]
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class MeasurementGuidanceSummary:
    """Compact measurement guidance that remains outside DecisionFeatures."""

    summary_id: str
    summary: str
    metric_names: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    visibility: GuidanceVisibility = field(default_factory=GuidanceVisibility)


@dataclass(frozen=True)
class ResearchGuidanceContract:
    """Problem-neutral guidance contract exposed by problem packages."""

    schema_version: str
    problem_family: str
    current_question: str
    required_mechanisms: tuple[RequiredMechanism, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]
    avoid_rules: tuple[AvoidRule, ...]
    continuity_requirements: tuple[ContinuityRequirement, ...]
    guidance_blocks: tuple[GuidanceBlock, ...]
    measurement_summary: MeasurementGuidanceSummary | None
    decision_boundary: str
    visibility_policy: str = "proposal_only"
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True


class ProblemResearchGuidanceProvider(Protocol):
    """Problem-owned port for building generic research guidance."""

    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        """Return a schema-validated contract shape for generic rendering."""
        ...


def collect_research_guidance_errors(
    contract: ResearchGuidanceContract,
) -> tuple[str, ...]:
    """Return all generic schema errors without interpreting problem content."""

    errors: list[str] = []
    if not isinstance(contract, ResearchGuidanceContract):
        return (f"contract must be ResearchGuidanceContract, got {type(contract).__name__}",)

    _require_non_empty(contract.schema_version, "schema_version", errors)
    _require_non_empty(contract.problem_family, "problem_family", errors)
    _require_non_empty(contract.current_question, "current_question", errors)
    _require_non_empty(contract.decision_boundary, "decision_boundary", errors)
    _check_visibility_flags(
        "contract",
        contract.visibility_policy,
        contract.proposal_visibility_only,
        contract.decision_features_excluded,
        errors,
    )

    mechanism_ids: list[str] = []
    evidence_ids: list[str] = []
    avoid_ids: list[str] = []
    continuity_ids: list[str] = []
    guidance_block_ids: list[str] = []

    for index, mechanism in enumerate(
        _as_sequence(
            contract.required_mechanisms,
            "required_mechanisms",
            errors,
        )
    ):
        path = f"required_mechanisms[{index}]"
        if not isinstance(mechanism, RequiredMechanism):
            errors.append(f"{path} must be RequiredMechanism")
            continue
        _require_non_empty(mechanism.mechanism_id, f"{path}.mechanism_id", errors)
        _require_non_empty(mechanism.category, f"{path}.category", errors)
        _require_non_empty(mechanism.description, f"{path}.description", errors)
        _check_string_sequence(
            mechanism.required_observations,
            f"{path}.required_observations",
            errors,
        )
        _check_string_sequence(
            mechanism.protected_items,
            f"{path}.protected_items",
            errors,
        )
        _check_hypothesis_mechanism_binding(
            mechanism.hypothesis_mechanism_binding,
            f"{path}.hypothesis_mechanism_binding",
            errors,
        )
        _check_visibility_object(f"{path}.visibility", mechanism.visibility, errors)
        mechanism_ids.append(mechanism.mechanism_id)

    for index, requirement in enumerate(
        _as_sequence(
            contract.evidence_requirements,
            "evidence_requirements",
            errors,
        )
    ):
        path = f"evidence_requirements[{index}]"
        if not isinstance(requirement, EvidenceRequirement):
            errors.append(f"{path} must be EvidenceRequirement")
            continue
        _require_non_empty(requirement.requirement_id, f"{path}.requirement_id", errors)
        _require_non_empty(requirement.category, f"{path}.category", errors)
        _require_non_empty(requirement.description, f"{path}.description", errors)
        _check_string_sequence(requirement.mechanism_ids, f"{path}.mechanism_ids", errors)
        _check_string_sequence(
            requirement.protected_items,
            f"{path}.protected_items",
            errors,
        )
        _check_string_sequence(
            requirement.required_fields,
            f"{path}.required_fields",
            errors,
        )
        _check_visibility_object(f"{path}.visibility", requirement.visibility, errors)
        evidence_ids.append(requirement.requirement_id)

    for index, rule in enumerate(_as_sequence(contract.avoid_rules, "avoid_rules", errors)):
        path = f"avoid_rules[{index}]"
        if not isinstance(rule, AvoidRule):
            errors.append(f"{path} must be AvoidRule")
            continue
        _require_non_empty(rule.rule_id, f"{path}.rule_id", errors)
        _require_non_empty(rule.category, f"{path}.category", errors)
        _require_non_empty(rule.description, f"{path}.description", errors)
        _check_string_sequence(rule.applies_to, f"{path}.applies_to", errors)
        _check_visibility_object(f"{path}.visibility", rule.visibility, errors)
        avoid_ids.append(rule.rule_id)

    for index, requirement in enumerate(
        _as_sequence(
            contract.continuity_requirements,
            "continuity_requirements",
            errors,
        )
    ):
        path = f"continuity_requirements[{index}]"
        if not isinstance(requirement, ContinuityRequirement):
            errors.append(f"{path} must be ContinuityRequirement")
            continue
        _require_non_empty(requirement.requirement_id, f"{path}.requirement_id", errors)
        _require_non_empty(requirement.category, f"{path}.category", errors)
        _require_non_empty(requirement.description, f"{path}.description", errors)
        _check_string_sequence(requirement.related_ids, f"{path}.related_ids", errors)
        _check_visibility_object(f"{path}.visibility", requirement.visibility, errors)
        continuity_ids.append(requirement.requirement_id)

    for index, block in enumerate(
        _as_sequence(contract.guidance_blocks, "guidance_blocks", errors)
    ):
        path = f"guidance_blocks[{index}]"
        if not isinstance(block, GuidanceBlock):
            errors.append(f"{path} must be GuidanceBlock")
            continue
        _require_non_empty(block.block_id, f"{path}.block_id", errors)
        _require_non_empty(block.category, f"{path}.category", errors)
        _require_non_empty(block.title, f"{path}.title", errors)
        _check_string_sequence(block.lines, f"{path}.lines", errors, require_non_empty=True)
        _check_visibility_object(f"{path}.visibility", block.visibility, errors)
        guidance_block_ids.append(block.block_id)

    summary = contract.measurement_summary
    if summary is not None:
        if not isinstance(summary, MeasurementGuidanceSummary):
            errors.append("measurement_summary must be MeasurementGuidanceSummary or None")
        else:
            _require_non_empty(summary.summary_id, "measurement_summary.summary_id", errors)
            _require_non_empty(summary.summary, "measurement_summary.summary", errors)
            _check_string_sequence(
                summary.metric_names,
                "measurement_summary.metric_names",
                errors,
            )
            _check_string_sequence(
                summary.limitations,
                "measurement_summary.limitations",
                errors,
            )
            _check_visibility_object(
                "measurement_summary.visibility",
                summary.visibility,
                errors,
            )

    _check_duplicates("required mechanism id", mechanism_ids, errors)
    _check_duplicates("evidence requirement id", evidence_ids, errors)
    _check_duplicates("avoid rule id", avoid_ids, errors)
    _check_duplicates("continuity requirement id", continuity_ids, errors)
    _check_duplicates("guidance block id", guidance_block_ids, errors)
    return tuple(errors)


def validate_research_guidance_contract(contract: ResearchGuidanceContract) -> None:
    """Raise when a contract cannot be safely rendered."""

    errors = collect_research_guidance_errors(contract)
    if errors:
        raise ResearchGuidanceValidationError("; ".join(errors))


def expected_research_guidance_rendered_paths(
    contract: ResearchGuidanceContract,
) -> tuple[str, ...]:
    """Return the generic paths that must appear in rendered guidance."""

    validate_research_guidance_contract(contract)
    paths: list[str] = [
        "schema_version",
        "problem_family",
        "current_question",
        "visibility",
        "decision_boundary",
        "decision_features_exclusion",
    ]
    paths.extend(
        f"required_mechanisms.{mechanism.mechanism_id}"
        for mechanism in contract.required_mechanisms
    )
    paths.extend(
        f"evidence_requirements.{requirement.requirement_id}"
        for requirement in contract.evidence_requirements
    )
    paths.extend(f"avoid_rules.{rule.rule_id}" for rule in contract.avoid_rules)
    paths.extend(
        f"continuity_requirements.{requirement.requirement_id}"
        for requirement in contract.continuity_requirements
    )
    paths.extend(f"guidance_blocks.{block.block_id}" for block in contract.guidance_blocks)
    if contract.measurement_summary is not None:
        paths.append(f"measurement_summary.{contract.measurement_summary.summary_id}")
    return tuple(paths)


def validate_research_guidance_rendered_paths(
    contract: ResearchGuidanceContract,
    rendered_paths: Sequence[str],
) -> None:
    """Fail closed when a valid contract was not fully projected."""

    expected = set(expected_research_guidance_rendered_paths(contract))
    actual = set(rendered_paths)
    missing = sorted(expected - actual)
    if missing:
        raise ResearchGuidanceValidationError(
            "missing rendered paths: " + ", ".join(missing)
        )


def _check_visibility_object(
    path: str,
    visibility: GuidanceVisibility,
    errors: list[str],
) -> None:
    if not isinstance(visibility, GuidanceVisibility):
        errors.append(f"{path} is required")
        return
    _check_visibility_flags(
        path,
        visibility.visibility_policy,
        visibility.proposal_visibility_only,
        visibility.decision_features_excluded,
        errors,
    )


def _check_visibility_flags(
    path: str,
    visibility_policy: str,
    proposal_visibility_only: bool,
    decision_features_excluded: bool,
    errors: list[str],
) -> None:
    if visibility_policy not in SUPPORTED_VISIBILITY_POLICIES:
        errors.append(f"{path}.visibility_policy unsupported: {visibility_policy!r}")
    if proposal_visibility_only is not True:
        errors.append(f"{path}.proposal_visibility_only must be true")
    if decision_features_excluded is not True:
        errors.append(f"{path}.decision_features_excluded must be true")


def _check_hypothesis_mechanism_binding(
    value: Any,
    path: str,
    errors: list[str],
) -> None:
    if value not in SUPPORTED_HYPOTHESIS_MECHANISM_BINDINGS:
        errors.append(f"{path} unsupported: {value!r}")


def _as_sequence(value: Any, path: str, errors: list[str]) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        errors.append(f"{path} must be a sequence")
        return ()
    return tuple(value)


def _check_string_sequence(
    value: Any,
    path: str,
    errors: list[str],
    *,
    require_non_empty: bool = False,
) -> None:
    items = _as_sequence(value, path, errors)
    if require_non_empty and not items:
        errors.append(f"{path} must not be empty")
    for index, item in enumerate(items):
        _require_non_empty(item, f"{path}[{index}]", errors)


def _require_non_empty(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def _check_duplicates(label: str, values: Sequence[str], errors: list[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            errors.append(f"duplicate {label}: {value}")
            continue
        seen.add(value)
