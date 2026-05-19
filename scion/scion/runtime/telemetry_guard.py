"""Generic runtime telemetry sanity guards for declared research surfaces."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scion.runtime.audit import normalize_surface_name

EXPECTED_TELEMETRY_CATEGORIES = frozenset(
    {"activity", "activation", "effect", "budget"}
)
_EXPECTED_TELEMETRY_META_KEYS = frozenset(
    {
        "mechanism",
        "mechanisms",
        "declared_mechanism",
        "declared_mechanisms",
        "declared_mechanism_change",
        "declared_mechanism_changes",
        "mechanism_change",
        "mechanism_changes",
    }
)
_MECHANISM_NOVELTY_KEYS = frozenset(
    {
        "mechanism",
        "mechanism_id",
        "mechanism_name",
        "declared_mechanism",
        "declared_mechanisms",
        "declared_mechanism_change",
        "declared_mechanism_changes",
    }
)
_WILDCARD_MECHANISM_KEYS = frozenset(
    {"*", "{mechanism}", "default", "__default__", "all", "__all__"}
)
_GENERIC_FIELD_CONTAINER_KEYS = frozenset(
    {"field", "fields", "path", "paths", "runtime_field", "runtime_fields", "runtime_path", "runtime_paths", "probes"}
)
_CATEGORY_PROBE_FIELD_NAMES: dict[str, tuple[str, ...]] = {
    "activation": (
        "activation_runtime_fields",
        "activation_runtime_paths",
        "activation_probe_runtime_fields",
        "mechanism_activation_runtime_fields",
        "mechanism_activation_runtime_paths",
    ),
    "effect": (
        "effect_probe_runtime_fields",
        "effect_probe_runtime_paths",
        "effect_runtime_fields",
        "effect_runtime_paths",
        "mechanism_effect_probe_runtime_fields",
        "mechanism_effect_probe_runtime_paths",
        "mechanism_effect_runtime_fields",
        "mechanism_effect_runtime_paths",
    ),
    "budget": (
        "stage_budget_runtime_fields",
        "stage_budget_runtime_paths",
        "budget_runtime_fields",
        "budget_runtime_paths",
        "mechanism_budget_runtime_fields",
        "mechanism_budget_runtime_paths",
        "mechanism_stage_budget_runtime_fields",
        "mechanism_stage_budget_runtime_paths",
    ),
}
_GENERIC_PROBE_CONTAINER_NAMES = (
    "mechanism_runtime_fields",
    "mechanism_runtime_paths",
    "mechanism_telemetry",
    "mechanism_probes",
    "runtime_mechanism_probes",
    "telemetry_mechanism_probes",
    "runtime_telemetry_probes",
    "telemetry_probes",
    "telemetry_guard_probes",
)

_ACTIVITY_SUFFIXES = (
    "_search_iterations",
    "_iterations",
    "_move_attempts",
    "_attempts",
)
_EFFECT_SUFFIXES = (
    "_improving_moves",
    "_best_improving_moves",
    "_best_delta",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_improvement_counts",
)
_BUDGET_SUFFIXES = (
    "_stage_budget_ms",
    "_stage_budget_ratio",
    "_phase_budget_ms",
    "_phase_budget_ratio",
    "_phase_runtime_ms",
    "_runtime_ms",
    "_elapsed_ms",
)


@dataclass(frozen=True)
class _MechanismProbe:
    mechanism: str
    category: str
    field: str
    source: str


def validate_expected_telemetry_contract(
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any,
    declared_mechanisms: Any = None,
) -> tuple[str, ...]:
    """Validate proposal-declared telemetry keys against adapter declarations."""

    category_errors = list(_expected_telemetry_category_errors(expected_telemetry))
    claims = normalize_expected_telemetry(expected_telemetry)
    mechanisms = normalize_declared_mechanisms(
        declared_mechanisms,
        expected_telemetry=expected_telemetry,
    )
    if not any(claims.values()):
        return tuple(category_errors)

    surface_name = normalize_surface_name(selected_surface)
    if not surface_name:
        return tuple(
            [
                *category_errors,
                "expected_telemetry requires a selected research surface",
            ]
        )

    surface = find_research_surface(problem_spec, surface_name)
    if surface is None:
        return tuple(
            [
                *category_errors,
                f"selected research surface '{surface_name}' is not declared "
                "in problem_spec.research_surfaces",
            ]
        )

    allowed = set(declared_surface_telemetry_fields(surface))
    for probe in declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=mechanisms,
    ):
        allowed.add(probe.field)
    if not allowed:
        return tuple(
            [
                *category_errors,
                f"research surface '{surface_name}' does not declare telemetry "
                "fields in surface.evidence",
            ]
        )

    errors: list[str] = list(category_errors)
    for category, fields in claims.items():
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            continue
        unknown = [field for field in fields if field not in allowed]
        if unknown:
            errors.append(
                f"expected_telemetry.{category} references undeclared "
                f"runtime field(s): {', '.join(sorted(unknown))}"
            )
    return tuple(errors)


def _expected_telemetry_category_errors(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    errors: list[str] = []
    for raw_category in value:
        category = str(raw_category or "").strip().lower()
        if not category or category in _EXPECTED_TELEMETRY_META_KEYS:
            continue
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            errors.append(
                f"expected_telemetry category '{category}' is not supported; "
                f"expected one of {sorted(EXPECTED_TELEMETRY_CATEGORIES)}"
            )
    return tuple(dict.fromkeys(errors))


def normalize_expected_telemetry(value: Any) -> dict[str, tuple[str, ...]]:
    """Return a category -> fields mapping from a flexible proposal payload."""

    claims: dict[str, list[str]] = {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES}
    if value in (None, "", [], (), {}):
        return {category: () for category in sorted(EXPECTED_TELEMETRY_CATEGORIES)}

    if isinstance(value, str):
        _append_field(claims["effect"], value)
        return _freeze_claims(claims)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _append_field(claims["effect"], item)
        return _freeze_claims(claims)
    if not isinstance(value, Mapping):
        return _freeze_claims(claims)

    for raw_category, raw_fields in value.items():
        category = str(raw_category or "").strip().lower()
        if not category:
            continue
        if category in _EXPECTED_TELEMETRY_META_KEYS:
            continue
        target = claims.setdefault(category, [])
        _append_fields(target, raw_fields)
    return _freeze_claims(claims)


def normalize_declared_mechanisms(
    value: Any = None,
    *,
    expected_telemetry: Any = None,
    novelty_signature: Any = None,
) -> tuple[str, ...]:
    """Return stable mechanism ids declared by a proposal or telemetry payload."""

    mechanisms: list[str] = []
    _append_mechanisms(mechanisms, value)

    if isinstance(expected_telemetry, Mapping):
        for key, raw_value in expected_telemetry.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key in _EXPECTED_TELEMETRY_META_KEYS:
                _append_mechanisms(mechanisms, raw_value)
                continue
            if normalized_key not in EXPECTED_TELEMETRY_CATEGORIES:
                continue
            if not isinstance(raw_value, Mapping):
                continue
            for raw_mechanism in raw_value:
                mechanism = _clean_mechanism_name(raw_mechanism)
                if _is_explicit_mechanism_key(mechanism):
                    _append_mechanism(mechanisms, mechanism)

    if isinstance(novelty_signature, Mapping):
        for key, raw_value in novelty_signature.items():
            if str(key or "").strip().lower() in _MECHANISM_NOVELTY_KEYS:
                _append_mechanisms(mechanisms, raw_value)

    return tuple(dict.fromkeys(mechanisms))


def normalize_expected_telemetry_by_mechanism(
    value: Any,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Return mechanism -> category -> runtime fields for grouped claims."""

    if not isinstance(value, Mapping):
        return {}
    claims: dict[str, dict[str, list[str]]] = {}
    for raw_category, raw_fields in value.items():
        category = str(raw_category or "").strip().lower()
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            continue
        if not isinstance(raw_fields, Mapping):
            continue
        for raw_mechanism, mechanism_fields in raw_fields.items():
            mechanism = _clean_mechanism_name(raw_mechanism)
            if not _is_explicit_mechanism_key(mechanism):
                continue
            category_claims = claims.setdefault(
                mechanism,
                {name: [] for name in EXPECTED_TELEMETRY_CATEGORIES},
            )
            _append_fields(category_claims[category], mechanism_fields)
    return {
        mechanism: {
            category: tuple(fields)
            for category, fields in sorted(category_claims.items())
            if fields
        }
        for mechanism, category_claims in sorted(claims.items())
    }


def declared_surface_telemetry_fields(surface: Any | None) -> frozenset[str]:
    """Return all runtime telemetry fields a surface exposes for guard use."""

    evidence = _field(surface, "evidence")
    fields: set[str] = set()
    for name in (
        "required_runtime_fields",
        "optional_runtime_fields",
        "activity_runtime_fields",
        "effect_probe_runtime_fields",
        "stage_budget_runtime_fields",
    ):
        fields.update(_string_list(_field(evidence, name)))
    activation = _field(evidence, "activation_runtime_fields")
    if isinstance(activation, Mapping):
        for value in activation.values():
            fields.update(_string_list(value))
    else:
        fields.update(_string_list(activation))
    for telemetry in _mechanism_telemetry_values(evidence):
        fields.update(_string_list(_field(telemetry, "activation_runtime_fields")))
        fields.update(_string_list(_field(telemetry, "effect_probe_runtime_fields")))
    return frozenset(field for field in fields if field)


def declared_activity_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "activity_runtime_fields"))
    if explicit:
        return tuple(explicit)
    mechanism_fields: list[str] = []
    for telemetry in _mechanism_telemetry_values(evidence):
        mechanism_fields.extend(
            _string_list(_field(telemetry, "activation_runtime_fields"))
        )
    if mechanism_fields:
        return tuple(dict.fromkeys(mechanism_fields))
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _ACTIVITY_SUFFIXES))


def declared_effect_probe_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "effect_probe_runtime_fields"))
    if explicit:
        return tuple(explicit)
    mechanism_fields: list[str] = []
    for telemetry in _mechanism_telemetry_values(evidence):
        mechanism_fields.extend(
            _string_list(_field(telemetry, "effect_probe_runtime_fields"))
        )
    if mechanism_fields:
        return tuple(dict.fromkeys(mechanism_fields))
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _EFFECT_SUFFIXES))


def declared_stage_budget_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "stage_budget_runtime_fields"))
    if explicit:
        return tuple(explicit)
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _BUDGET_SUFFIXES))


def declared_mechanism_runtime_probes(
    *,
    problem_spec: Any | None,
    surface: Any | None,
    declared_mechanisms: Any = None,
) -> tuple[_MechanismProbe, ...]:
    """Expand adapter/surface declared mechanism probes into runtime paths."""

    mechanisms = normalize_declared_mechanisms(declared_mechanisms)
    if not mechanisms:
        return ()

    probes: list[_MechanismProbe] = []
    seen: set[tuple[str, str, str]] = set()
    for mechanism in mechanisms:
        for source_name, source in _mechanism_probe_sources(problem_spec, surface):
            for category in ("activation", "effect", "budget"):
                fields = _mechanism_probe_fields(source, mechanism, category)
                for field in fields:
                    key = (mechanism, category, field)
                    if key in seen:
                        continue
                    seen.add(key)
                    probes.append(
                        _MechanismProbe(
                            mechanism=mechanism,
                            category=category,
                            field=field,
                            source=source_name,
                        )
                    )
    return tuple(probes)


def build_telemetry_guard_summary(
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]] = (),
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any = None,
    declared_mechanisms: Any = None,
    protected_objectives: Sequence[str] = (),
    implicit_activity_claim: bool = False,
) -> dict[str, Any]:
    """Build an aggregate, deterministic sanity summary for runtime telemetry."""

    surface_name = normalize_surface_name(selected_surface)
    surface = find_research_surface(problem_spec, surface_name)
    claims = normalize_expected_telemetry(expected_telemetry)
    mechanism_claims = normalize_expected_telemetry_by_mechanism(expected_telemetry)
    mechanisms = normalize_declared_mechanisms(
        declared_mechanisms,
        expected_telemetry=expected_telemetry,
    )
    protected_tokens = _protected_objective_tokens(protected_objectives)
    if not mechanisms and mechanism_claims:
        mechanisms = tuple(mechanism_claims)
    expected_present = any(claims.values()) or bool(mechanisms)
    evidence = _field(surface, "evidence")

    categories: dict[str, tuple[str, ...]] = {
        category: tuple(fields) for category, fields in claims.items() if fields
    }

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    field_summaries: dict[str, dict[str, Any]] = {}
    mechanism_summaries: dict[str, dict[str, Any]] = {
        mechanism: {"categories": {}, "fields": {}, "passed": True}
        for mechanism in mechanisms
    }

    for category, fields in sorted(categories.items()):
        for field in fields:
            summary = _runtime_field_summary(
                field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
            )
            field_summaries[field] = summary
            if category == "budget" and summary["candidate_positive"] == 0:
                failures.append(
                    _guard_issue(
                        "TELEMETRY_BUDGET_STARVED",
                        category=category,
                        field=field,
                        severity="fail",
                        summary=summary,
                    )
                )
            elif category == "effect" and _matches_protected_objective_field(
                field,
                protected_tokens,
            ):
                if summary["candidate_present"] == 0:
                    failures.append(
                        _guard_issue(
                            "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED",
                            category=category,
                            field=field,
                            severity="fail",
                            summary=summary,
                        )
                    )
            elif summary["candidate_positive"] == 0:
                failures.append(
                    _guard_issue(
                        f"TELEMETRY_{category.upper()}_NOT_OBSERVED",
                        category=category,
                        field=field,
                        severity="fail",
                        summary=summary,
                    )
                )

    mechanism_probe_categories: dict[str, dict[str, list[str]]] = {
        mechanism: {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES}
        for mechanism in mechanisms
    }
    for mechanism, category_claims in mechanism_claims.items():
        categories_for_mechanism = mechanism_probe_categories.setdefault(
            mechanism,
            {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES},
        )
        mechanism_summaries.setdefault(
            mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        for category, fields in category_claims.items():
            categories_for_mechanism.setdefault(category, [])
            for field in fields:
                if field not in categories_for_mechanism[category]:
                    categories_for_mechanism[category].append(field)

    for probe in declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=mechanisms,
    ):
        categories_for_mechanism = mechanism_probe_categories.setdefault(
            probe.mechanism,
            {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES},
        )
        mechanism_summaries.setdefault(
            probe.mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        fields = categories_for_mechanism.setdefault(probe.category, [])
        if probe.field not in fields:
            fields.append(probe.field)

    for mechanism, category_fields in sorted(mechanism_probe_categories.items()):
        mechanism_summary = mechanism_summaries.setdefault(
            mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        for category, fields in sorted(category_fields.items()):
            fields = [field for field in fields if field]
            if not fields or category not in ("activation", "effect", "budget"):
                continue
            mechanism_summary["categories"][category] = list(fields)
            category_positive = 0
            category_present = 0
            category_missing = 0
            category_champion_positive = 0
            for field in fields:
                summary = _runtime_field_summary(
                    field,
                    candidate_runtimes=candidate_runtimes,
                    champion_runtimes=champion_runtimes,
                    mechanism=mechanism,
                )
                mechanism_summary["fields"][field] = summary
                field_summaries[_mechanism_field_summary_key(mechanism, field)] = summary
                category_positive += int(summary["candidate_positive"])
                category_present += int(summary["candidate_present"])
                category_missing += int(summary["candidate_missing"])
                category_champion_positive += int(summary["champion_positive"])
            if category_positive > 0:
                continue
            code = (
                "TELEMETRY_MECHANISM_BUDGET_STARVED"
                if category == "budget"
                else f"TELEMETRY_MECHANISM_{category.upper()}_NOT_OBSERVED"
            )
            issue = _guard_issue(
                code,
                category=category,
                field=",".join(fields),
                severity="fail",
                summary={
                    "candidate_positive": category_positive,
                    "candidate_present": category_present,
                    "candidate_missing": category_missing,
                    "champion_positive": category_champion_positive,
                },
                mechanism=mechanism,
            )
            failures.append(issue)
            mechanism_summary["passed"] = False

    if not expected_present:
        activity_fields = declared_activity_runtime_fields(surface)
        if activity_fields:
            activity_positive = 0
            for field in activity_fields:
                summary = field_summaries.get(field)
                if summary is None:
                    summary = _runtime_field_summary(
                        field,
                        candidate_runtimes=candidate_runtimes,
                        champion_runtimes=champion_runtimes,
                    )
                    field_summaries[field] = summary
                activity_positive += int(summary["candidate_positive"])
            if candidate_runtimes and activity_positive == 0:
                issue = _guard_issue(
                    "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                    category="activity",
                    field=",".join(activity_fields),
                    severity=(
                        "fail"
                        if implicit_activity_claim
                        or _as_bool(_field(evidence, "fail_closed_on_zero_activity"))
                        else "warn"
                    ),
                    summary={
                        "candidate_runs": len(candidate_runtimes),
                        "candidate_positive": 0,
                    },
                )
                (failures if issue["severity"] == "fail" else warnings).append(issue)

        budget_fields = declared_stage_budget_runtime_fields(surface)
        for field in budget_fields:
            if field in field_summaries:
                continue
            summary = _runtime_field_summary(
                field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
            )
            field_summaries[field] = summary
            if (
                candidate_runtimes
                and summary["candidate_positive"] == 0
                and summary["champion_positive"] > 0
            ):
                issue = _guard_issue(
                    "TELEMETRY_BUDGET_STARVED",
                    category="budget",
                    field=field,
                    severity=(
                        "fail"
                        if _as_bool(
                            _field(evidence, "fail_closed_on_stage_budget_starvation")
                        )
                        else "warn"
                    ),
                    summary=summary,
                )
                (failures if issue["severity"] == "fail" else warnings).append(issue)

    return {
        "schema": "scion.telemetry_guard.v1",
        "selected_surface": surface_name or None,
        "passed": not failures,
        "expected_telemetry_present": expected_present,
        "implicit_activity_claim": bool(implicit_activity_claim),
        "declared_mechanisms": list(mechanisms),
        "protected_objectives": list(protected_tokens),
        "candidate_runs": len(candidate_runtimes),
        "champion_runs": len(champion_runtimes),
        "categories": {
            category: list(fields) for category, fields in sorted(categories.items())
        },
        "mechanisms": {
            mechanism: mechanism_summary
            for mechanism, mechanism_summary in sorted(mechanism_summaries.items())
            if mechanism_summary.get("categories") or mechanism_summary.get("fields")
        },
        "fields": field_summaries,
        "warnings": warnings,
        "failures": failures,
    }


def _protected_objective_tokens(protected_objectives: Sequence[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    for objective in protected_objectives:
        token = str(objective or "").strip().lower()
        if token:
            tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def _matches_protected_objective_field(
    field: str,
    protected_tokens: Sequence[str],
) -> bool:
    if not protected_tokens:
        return False
    normalized_field = re.sub(r"[^a-z0-9]+", "_", str(field or "").lower()).strip("_")
    if not normalized_field:
        return False
    padded = f"_{normalized_field}_"
    for token in protected_tokens:
        normalized_token = re.sub(r"[^a-z0-9]+", "_", token).strip("_")
        if normalized_token and f"_{normalized_token}_" in padded:
            return True
    return False


def format_telemetry_guard_issue(summary: Mapping[str, Any]) -> str | None:
    failures = summary.get("failures")
    if not isinstance(failures, Sequence) or not failures:
        return None
    first = failures[0]
    if not isinstance(first, Mapping):
        return "telemetry guard failed"
    code = str(first.get("code") or "TELEMETRY_GUARD_FAILED")
    field = str(first.get("field") or "")
    mechanism = str(first.get("mechanism") or "")
    category = str(first.get("category") or "telemetry")
    if code == "TELEMETRY_ACTIVITY_NOT_OBSERVED":
        activity_fields = []
        for item in failures:
            if (
                isinstance(item, Mapping)
                and item.get("code") == "TELEMETRY_ACTIVITY_NOT_OBSERVED"
            ):
                activity_fields.extend(
                    part.strip()
                    for part in str(item.get("field") or "").split(",")
                    if part.strip()
                )
        if activity_fields:
            field = ",".join(dict.fromkeys(activity_fields))
        field_zero_text = ", ".join(
            f"{item.strip()}=0" for item in field.split(",") if item.strip()
        )
        return (
            "telemetry guard observed zero active search effort: "
            f"{field_zero_text or field} had no positive runtime evidence across "
            f"{summary.get('candidate_runs', 0)} candidate run(s)"
        )
    if code == "TELEMETRY_BUDGET_STARVED":
        return (
            "telemetry guard observed stage budget starvation: "
            f"{field} had no positive candidate runtime evidence"
        )
    if code == "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED":
        return (
            "telemetry guard observed no protected-objective no-regression "
            f"runtime field presence for {field}"
        )
    if code == "TELEMETRY_ACTIVATION_NOT_OBSERVED":
        return (
            "telemetry guard observed no activation evidence for declared "
            f"mechanism telemetry field {field}"
        )
    if code == "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED":
        return (
            "telemetry guard observed no activation evidence for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    if code == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED":
        return (
            "telemetry guard observed no effect evidence for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    if code == "TELEMETRY_MECHANISM_BUDGET_STARVED":
        return (
            "telemetry guard observed budget starvation for declared "
            f"mechanism {mechanism or 'unknown'} via runtime path(s) {field}"
        )
    return (
        f"telemetry guard failed for {category} field {field}: "
        f"{code}"
    )


def find_research_surface(problem_spec: Any | None, name: str | None) -> Any | None:
    surface_name = normalize_surface_name(name)
    if not surface_name:
        return None
    for surface in _field(problem_spec, "research_surfaces") or ():
        if str(_field(surface, "name") or "").strip() == surface_name:
            return surface
    return None


def _mechanism_telemetry_values(evidence: Any | None) -> tuple[Any, ...]:
    telemetry = _field(evidence, "mechanism_telemetry")
    if not isinstance(telemetry, Mapping):
        return ()
    return tuple(telemetry.values())


def _runtime_field_summary(
    field: str,
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
    mechanism: str | None = None,
) -> dict[str, Any]:
    candidate_present = 0
    candidate_positive = 0
    candidate_zero = 0
    candidate_missing = 0
    champion_positive = 0
    examples: list[Any] = []

    for runtime in candidate_runtimes:
        observation = _runtime_path_observation(runtime, field, mechanism=mechanism)
        if not observation["present"]:
            candidate_missing += 1
            continue
        candidate_present += 1
        value = observation["value"]
        if _positive_evidence(value):
            candidate_positive += 1
        elif not _empty_value(value):
            candidate_zero += 1
        if len(examples) < 3:
            examples.append(_bounded_value(value))

    for runtime in champion_runtimes:
        observation = _runtime_path_observation(runtime, field, mechanism=mechanism)
        if observation["present"] and _positive_evidence(observation["value"]):
            champion_positive += 1

    return {
        "candidate_present": candidate_present,
        "candidate_missing": candidate_missing,
        "candidate_positive": candidate_positive,
        "candidate_zero": candidate_zero,
        "champion_positive": champion_positive,
        "examples": examples,
    }


def _guard_issue(
    code: str,
    *,
    category: str,
    field: str,
    severity: str,
    summary: Mapping[str, Any],
    mechanism: str | None = None,
) -> dict[str, Any]:
    issue = {
        "code": code,
        "severity": severity,
        "category": category,
        "field": field,
        "candidate_positive": summary.get("candidate_positive", 0),
        "candidate_present": summary.get("candidate_present", 0),
        "candidate_missing": summary.get("candidate_missing", 0),
        "champion_positive": summary.get("champion_positive", 0),
    }
    if mechanism:
        issue["mechanism"] = mechanism
    return issue


def _mechanism_probe_sources(
    problem_spec: Any | None,
    surface: Any | None,
) -> tuple[tuple[str, Any], ...]:
    evidence = _field(surface, "evidence")
    spec_evidence = _field(problem_spec, "evidence")
    sources: list[tuple[str, Any]] = []
    for name, source in (
        ("adapter", problem_spec),
        ("adapter.evidence", spec_evidence),
        ("adapter.telemetry_guard", _field(problem_spec, "telemetry_guard")),
        ("adapter.runtime_telemetry_guard", _field(problem_spec, "runtime_telemetry_guard")),
        ("adapter.telemetry_probes", _field(problem_spec, "telemetry_probes")),
        ("adapter.runtime_telemetry_probes", _field(problem_spec, "runtime_telemetry_probes")),
        ("surface", surface),
        ("surface.evidence", evidence),
        ("surface.telemetry_guard", _field(surface, "telemetry_guard")),
        ("surface.runtime_telemetry_guard", _field(surface, "runtime_telemetry_guard")),
        ("surface.telemetry_probes", _field(surface, "telemetry_probes")),
        ("surface.runtime_telemetry_probes", _field(surface, "runtime_telemetry_probes")),
        ("surface.evidence.telemetry_guard", _field(evidence, "telemetry_guard")),
        (
            "surface.evidence.runtime_telemetry_guard",
            _field(evidence, "runtime_telemetry_guard"),
        ),
    ):
        if source is not None:
            sources.append((name, source))
    return tuple(sources)


def _mechanism_probe_fields(
    source: Any,
    mechanism: str,
    category: str,
) -> tuple[str, ...]:
    fields: list[str] = []
    for field_name in _CATEGORY_PROBE_FIELD_NAMES.get(category, ()):
        fields.extend(
            _fields_for_mechanism(
                _field(source, field_name),
                mechanism=mechanism,
                category=category,
            )
        )
    for container_name in _GENERIC_PROBE_CONTAINER_NAMES:
        fields.extend(
            _fields_for_mechanism(
                _field(source, container_name),
                mechanism=mechanism,
                category=category,
            )
        )
    return tuple(dict.fromkeys(field for field in fields if field))


def _fields_for_mechanism(
    value: Any,
    *,
    mechanism: str,
    category: str | None,
) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, Mapping):
        fields: list[str] = []

        if category:
            for key in _category_field_keys(category):
                if key in value:
                    fields.extend(
                        _fields_for_mechanism(
                            value.get(key),
                            mechanism=mechanism,
                            category=None,
                        )
                    )

        for raw_key, raw_value in value.items():
            key = str(raw_key or "").strip()
            normalized_key = key.lower()
            if normalized_key in EXPECTED_TELEMETRY_CATEGORIES:
                continue
            if normalized_key in _GENERIC_FIELD_CONTAINER_KEYS:
                fields.extend(
                    _fields_for_mechanism(
                        raw_value,
                        mechanism=mechanism,
                        category=None,
                    )
                )
                continue
            if not _mechanism_probe_key_matches(key, mechanism):
                continue
            selected = raw_value
            if category and _has_category_probe_shape(selected):
                category_values: list[str] = []
                for category_key in _category_field_keys(category):
                    selected_value = _field(selected, category_key)
                    if selected_value is not None:
                        category_values.extend(
                            _fields_for_mechanism(
                                selected_value,
                                mechanism=mechanism,
                                category=None,
                            )
                        )
                if category_values:
                    fields.extend(category_values)
                continue
            fields.extend(
                _fields_for_mechanism(
                    selected,
                    mechanism=mechanism,
                    category=None,
                )
            )
        return _expand_mechanism_templates(fields, mechanism)
    return _expand_mechanism_templates(_string_list(value), mechanism)


def _category_field_keys(category: str) -> tuple[str, ...]:
    return (category, *_CATEGORY_PROBE_FIELD_NAMES.get(category, ()))


def _has_category_probe_shape(value: Any) -> bool:
    for category in ("activation", "effect", "budget"):
        for key in _category_field_keys(category):
            if _field(value, key) is not None:
                return True
    return False


def _mechanism_probe_key_matches(key: str, mechanism: str) -> bool:
    normalized_key = key.strip()
    if normalized_key == mechanism or normalized_key.lower() in _WILDCARD_MECHANISM_KEYS:
        return True
    if "*" not in normalized_key:
        return False
    pattern = re.escape(normalized_key).replace(r"\*", "[A-Za-z0-9_]*")
    return re.fullmatch(pattern, mechanism) is not None


def _expand_mechanism_templates(fields: Sequence[str], mechanism: str) -> list[str]:
    return [
        str(field).replace("{mechanism}", mechanism)
        for field in fields
        if str(field or "").strip()
    ]


def _mechanism_field_summary_key(mechanism: str, field: str) -> str:
    return f"{mechanism}:{field}"


def _runtime_path_observation(
    runtime: Mapping[str, Any],
    field: str,
    *,
    mechanism: str | None,
) -> dict[str, Any]:
    path = str(field or "").strip()
    raw_path = path
    if mechanism:
        path = path.replace("{mechanism}", mechanism)
    if not path:
        return {"present": False, "value": None}

    if path in runtime:
        return _mechanism_scoped_observation(runtime[path], mechanism=mechanism)

    segments = _parse_runtime_path(path)
    scope_final_mapping = bool(
        mechanism
        and "{mechanism}" not in raw_path
        and mechanism not in segments
    )
    values = _resolve_runtime_path(
        runtime,
        segments,
        mechanism=mechanism if scope_final_mapping else None,
    )
    if not values:
        return {"present": False, "value": None}
    value: Any = values[0] if len(values) == 1 else values
    return {"present": True, "value": value}


def _mechanism_scoped_observation(
    value: Any,
    *,
    mechanism: str | None,
) -> dict[str, Any]:
    if mechanism and isinstance(value, Mapping):
        if mechanism not in value:
            return {"present": False, "value": None}
        return {"present": True, "value": value.get(mechanism)}
    return {"present": True, "value": value}


def _resolve_runtime_path(
    root: Any,
    segments: Sequence[str],
    *,
    mechanism: str | None,
) -> list[Any]:
    values = [root]
    for segment in segments:
        next_values: list[Any] = []
        key = mechanism if segment == "*" and mechanism else segment
        for value in values:
            if isinstance(value, Mapping):
                if key == "*" and not mechanism:
                    next_values.extend(value.values())
                elif key in value:
                    next_values.append(value.get(key))
            elif (
                isinstance(value, Sequence)
                and not isinstance(value, (str, bytes, bytearray))
                and str(key).isdigit()
            ):
                index = int(str(key))
                if 0 <= index < len(value):
                    next_values.append(value[index])
        values = next_values
        if not values:
            return []
    if mechanism:
        scoped: list[Any] = []
        for value in values:
            observation = _mechanism_scoped_observation(value, mechanism=mechanism)
            if observation["present"]:
                scoped.append(observation["value"])
        return scoped
    return values


def _parse_runtime_path(path: str) -> tuple[str, ...]:
    segments: list[str] = []
    current: list[str] = []
    bracket = False
    quote: str | None = None
    for char in path:
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
            continue
        if char in {"'", '"'} and bracket:
            quote = char
            continue
        if char == "[":
            if current:
                segments.append("".join(current).strip())
                current = []
            bracket = True
            continue
        if char == "]" and bracket:
            segments.append("".join(current).strip())
            current = []
            bracket = False
            continue
        if char == "." and not bracket:
            if current:
                segments.append("".join(current).strip())
                current = []
            continue
        current.append(char)
    if current:
        segments.append("".join(current).strip())
    return tuple(segment for segment in segments if segment)


def _append_mechanisms(target: list[str], value: Any) -> None:
    if value in (None, "", [], (), {}):
        return
    if isinstance(value, Mapping):
        for key in ("name", "mechanism", "id", "mechanism_id"):
            if key in value:
                _append_mechanisms(target, value.get(key))
                return
        for item in value.values():
            _append_mechanisms(target, item)
        return
    if isinstance(value, str):
        for part in value.split(","):
            _append_mechanism(target, part)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _append_mechanisms(target, item)
        return
    object_id = getattr(value, "id", None)
    if object_id is not None:
        _append_mechanisms(target, object_id)
        return
    _append_mechanism(target, value)


def _append_mechanism(target: list[str], value: Any) -> None:
    mechanism = _clean_mechanism_name(value)
    if not mechanism or mechanism in target:
        return
    target.append(mechanism)


def _clean_mechanism_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:120]


def _is_explicit_mechanism_key(value: str) -> bool:
    key = str(value or "").strip().lower()
    return bool(key) and key not in (
        _WILDCARD_MECHANISM_KEYS
        | _GENERIC_FIELD_CONTAINER_KEYS
        | EXPECTED_TELEMETRY_CATEGORIES
        | _EXPECTED_TELEMETRY_META_KEYS
    )


def _append_fields(target: list[str], value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _append_fields(target, item)
        return
    if isinstance(value, str):
        _append_field(target, value)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _append_fields(target, item)
        return
    _append_field(target, value)


def _append_field(target: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if not text or text in target:
        return
    target.append(text)


def _freeze_claims(claims: Mapping[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {str(category): tuple(fields) for category, fields in sorted(claims.items())}


def _fields_with_suffix(fields: Sequence[str], suffixes: Sequence[str]) -> list[str]:
    return [
        field
        for field in fields
        if any(str(field).endswith(suffix) for suffix in suffixes)
    ]


def _string_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        result: list[str] = []
        for item in value.values():
            result.extend(_string_list(item))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _positive_evidence(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0.0
    if isinstance(value, str):
        text = value.strip().lower()
        return bool(text) and text not in {
            "0",
            "false",
            "none",
            "null",
            "disabled",
            "off",
            "no",
            "unknown",
        }
    if isinstance(value, Mapping):
        return any(_positive_evidence(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return any(_positive_evidence(item) for item in value)
    return bool(value)


def _empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) == 0
    return False


def _bounded_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _bounded_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_bounded_value(item) for item in list(value)[:8]]
    return str(value)[:160]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)
