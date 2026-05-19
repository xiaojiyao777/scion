"""Generic runtime telemetry sanity guards for declared research surfaces."""
from __future__ import annotations

from scion.runtime.telemetry_guard.contract import (
    validate_expected_telemetry_contract,
)
from scion.runtime.telemetry_guard.declarations import (
    _ACTIVITY_SUFFIXES,
    _BUDGET_SUFFIXES,
    _EFFECT_SUFFIXES,
    _mechanism_telemetry_values,
    declared_activity_runtime_fields,
    declared_effect_probe_runtime_fields,
    declared_stage_budget_runtime_fields,
    declared_surface_telemetry_fields,
    find_research_surface,
)
from scion.runtime.telemetry_guard.evidence import (
    _as_bool,
    _bounded_value,
    _empty_value,
    _positive_evidence,
)
from scion.runtime.telemetry_guard.expected_schema import (
    EXPECTED_TELEMETRY_CATEGORIES,
    _EXPECTED_TELEMETRY_META_KEYS,
    _GENERIC_FIELD_CONTAINER_KEYS,
    _MECHANISM_NOVELTY_KEYS,
    _WILDCARD_MECHANISM_KEYS,
    _append_mechanism,
    _append_mechanisms,
    _clean_mechanism_name,
    _expected_telemetry_category_errors,
    _is_explicit_mechanism_key,
    normalize_declared_mechanisms,
    normalize_expected_telemetry,
    normalize_expected_telemetry_by_mechanism,
)
from scion.runtime.telemetry_guard.issues import (
    _guard_issue,
    format_telemetry_guard_issue,
)
from scion.runtime.telemetry_guard.mechanism_probes import (
    _CATEGORY_PROBE_FIELD_NAMES,
    _GENERIC_PROBE_CONTAINER_NAMES,
    _MechanismProbe,
    _category_field_keys,
    _expand_mechanism_templates,
    _fields_for_mechanism,
    _has_category_probe_shape,
    _mechanism_probe_fields,
    _mechanism_probe_key_matches,
    _mechanism_probe_sources,
    declared_mechanism_runtime_probes,
)
from scion.runtime.telemetry_guard.observations import (
    _matches_protected_objective_field,
    _protected_objective_tokens,
    _runtime_field_summary,
)
from scion.runtime.telemetry_guard.runtime_paths import (
    _mechanism_field_summary_key,
    _mechanism_scoped_observation,
    _parse_runtime_path,
    _resolve_runtime_path,
    _runtime_path_observation,
)
from scion.runtime.telemetry_guard.summary import (
    build_telemetry_guard_summary,
)
from scion.runtime.telemetry_guard.utils import (
    _append_field,
    _append_fields,
    _field,
    _fields_with_suffix,
    _freeze_claims,
    _string_list,
)

__all__ = [
    "EXPECTED_TELEMETRY_CATEGORIES",
    "build_telemetry_guard_summary",
    "declared_activity_runtime_fields",
    "declared_effect_probe_runtime_fields",
    "declared_mechanism_runtime_probes",
    "declared_stage_budget_runtime_fields",
    "declared_surface_telemetry_fields",
    "find_research_surface",
    "format_telemetry_guard_issue",
    "normalize_declared_mechanisms",
    "normalize_expected_telemetry",
    "normalize_expected_telemetry_by_mechanism",
    "validate_expected_telemetry_contract",
]
