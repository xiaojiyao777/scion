"""Strict S2c1 controls schema used by the private M32 manifest join."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.public_refs import public_case_ref

_CONTROLS_SCHEMA_VERSION = "scion.initial_screening_study_controls.config_subset.v1"
_SCOPE = "CONFIG_SUBSET_ONLY"
_CONTROLS_MAX_BYTES = 1 << 20
_MAX_DEPTH = 24
_CONTROLS_LIMITATIONS = (
    "PROBLEM_SPEC_UNVERIFIED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RESEARCH_HISTORY_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_REQUEST_POLICY_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_CODE_LIMIT_KEYS = frozenset(
    {
        "max_turns",
        "max_read_calls",
        "max_search_calls",
        "max_read_chars",
        "max_read_bytes",
        "max_search_matches",
        "max_search_chars",
        "max_search_bytes",
        "max_read_lines",
        "max_action_bytes",
        "max_patch_files",
        "max_patch_chars",
        "max_test_calls",
        "max_test_suite_timeout_sec",
        "max_test_total_timeout_sec",
        "max_test_files",
        "max_test_copy_bytes",
        "max_test_result_chars",
        "max_tool_result_chars",
        "max_transcript_chars",
        "max_hypothesis_candidates",
    }
)
_POPULATION_PATHS = (
    ("protocol", "initial_screening", "cases_by_action", "modify_or_remove"),
    ("protocol", "initial_screening", "cases_by_action", "create_new"),
    ("protocol", "initial_screening", "seeds"),
    ("protocol", "initial_screening", "selection", "priority_case_ids"),
    ("protocol", "initial_screening", "resolved_time_limits"),
    ("protocol", "canary", "cases"),
    ("protocol", "canary", "seeds"),
    ("protocol", "canary", "resolved_time_limits"),
)
_K_PATH = ("code_research_limits", "max_hypothesis_candidates")
_STAGES = frozenset({"screening", "validation", "frozen", "canary"})
_NONNEGATIVE_NUMERIC_RE = re.compile(
    r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"
)


@dataclass(frozen=True, repr=False)
class _NormalizedStudyControls:
    """Detached exact controls plus the facts needed by the safe loader."""

    canonical_bytes: bytes
    frozen: tuple[Any, ...]
    code_research_limits: tuple[Any, ...]
    resource_envelope: tuple[Any, ...]
    a_cap: int
    p_cap: int
    k: int
    case_refs: tuple[str, ...]
    seeds: tuple[int, ...]
    equivalence_band: float
    scheduler_max: int
    measurement_readiness: tuple[Any, ...]
    pair_key: tuple[Any, ...]
    cross_block_key: tuple[Any, ...]
    development_cells: tuple[tuple[str, int], ...]

    def __repr__(self) -> str:
        return "_NormalizedStudyControls(<redacted>)"

    __str__ = __repr__


def _canonical_json_bytes(
    value: Any,
    *,
    max_bytes: int = 16 << 20,
) -> bytes:
    """Encode already-decoded strict JSON as sorted/minified UTF-8 plus LF."""

    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError
    detached = _detach_json(value, depth=0)
    encoded = (
        json.dumps(
            detached,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > max_bytes:
        raise ValueError
    return encoded


def _normalize_controls_unsafe(value: Any) -> _NormalizedStudyControls:
    canonical = _canonical_json_bytes(value, max_bytes=_CONTROLS_MAX_BYTES)
    controls = _exact_dict(
        value,
        {
            "schema_version",
            "scope",
            "limitations",
            "campaign",
            "code_research_limits",
            "resource_envelope",
            "protocol",
        },
    )
    if (
        controls["schema_version"] != _CONTROLS_SCHEMA_VERSION
        or controls["scope"] != _SCOPE
        or tuple(_exact_list(controls["limitations"])) != _CONTROLS_LIMITATIONS
    ):
        raise ValueError
    campaign = _validate_campaign(controls["campaign"])
    code_limits = _validate_code_limits(controls["code_research_limits"])
    resource = _validate_resource(controls["resource_envelope"])
    protocol = _validate_protocol(controls["protocol"])
    case_refs, seeds, equivalence_band, readiness = protocol
    a_cap = campaign[0]
    p_cap = resource["provider_call_cap"]
    k = code_limits["max_hypothesis_candidates"]
    return _NormalizedStudyControls(
        canonical_bytes=canonical,
        frozen=_freeze_json(controls),
        code_research_limits=_freeze_json(code_limits),
        resource_envelope=_freeze_json(resource),
        a_cap=a_cap,
        p_cap=p_cap,
        k=k,
        case_refs=case_refs,
        seeds=seeds,
        equivalence_band=equivalence_band,
        scheduler_max=campaign[1],
        measurement_readiness=readiness,
        pair_key=_masked_frozen(controls, (_K_PATH,)),
        cross_block_key=_masked_frozen(
            controls,
            (_K_PATH, *_POPULATION_PATHS),
        ),
        development_cells=tuple(
            (case_ref, seed) for case_ref in case_refs for seed in seeds
        ),
    )


def _validate_campaign(value: Any) -> tuple[int, int]:
    campaign = _exact_dict(
        value,
        {
            "campaign_mode",
            "development_boundary_mode",
            "requested_rounds",
            "qualification_limits",
            "scheduler",
        },
    )
    if (
        campaign["campaign_mode"] != "qualification_only"
        or campaign["development_boundary_mode"] != "initial_screening_only_v1"
    ):
        raise ValueError
    requested = _positive_int(campaign["requested_rounds"])
    limits = _exact_dict(
        campaign["qualification_limits"],
        {
            "max_proposal_attempts",
            "max_verified_candidate_chains",
            "max_formal_screening_stages",
        },
    )
    if any(_positive_int(value) != requested for value in limits.values()):
        raise ValueError
    scheduler = _exact_dict(campaign["scheduler"], {"max_active_branches"})
    return requested, _positive_int(scheduler["max_active_branches"])


def _validate_code_limits(value: Any) -> dict[str, int]:
    limits = _exact_dict(value, _CODE_LIMIT_KEYS)
    if any(type(item) is not int for item in limits.values()):
        raise TypeError
    normalized = CodeResearchLimits(**limits).to_primitive()
    if normalized != limits:
        raise ValueError
    return dict(limits)


def _validate_resource(value: Any) -> dict[str, int]:
    resource = _exact_dict(value, {"provider_call_cap", "outer_hardwall_sec"})
    if any(_positive_int(item) <= 0 for item in resource.values()):
        raise ValueError
    return dict(resource)


def _validate_protocol(
    value: Any,
) -> tuple[tuple[str, ...], tuple[int, ...], float, tuple[Any, ...]]:
    protocol = _exact_dict(
        value,
        {
            "version",
            "strict_case_paths",
            "safe_data_roots",
            "initial_screening",
            "canary",
            "time_limit_fallback_sec",
        },
    )
    _text(protocol["version"], allow_empty=False)
    if protocol["strict_case_paths"] is not True:
        raise ValueError
    _safe_data_roots(protocol["safe_data_roots"])
    fallback = _positive_int(protocol["time_limit_fallback_sec"])
    initial = _exact_dict(
        protocol["initial_screening"],
        {
            "cases_by_action",
            "seeds",
            "selection",
            "screening_gate",
            "effect_policy",
            "measurement_readiness",
            "runtime_time_limits",
            "resolved_time_limits",
        },
    )
    actions = _exact_dict(
        initial["cases_by_action"],
        {"modify_or_remove", "create_new"},
    )
    modify = _case_refs(actions["modify_or_remove"])
    create = _case_refs(actions["create_new"])
    if modify != create:
        raise ValueError
    seeds = _seeds(initial["seeds"])
    _validate_selection(initial["selection"], len(modify), len(create), len(seeds))
    _validate_screening_gate(initial["screening_gate"])
    equivalence_band = _validate_effect_policy(initial["effect_policy"])
    readiness = _validate_measurement_readiness(initial["measurement_readiness"])
    _validate_runtime_time_limits(initial["runtime_time_limits"])
    _validate_resolved_limits(initial["resolved_time_limits"], modify)
    canary_cases, canary_seeds = _validate_canary(protocol["canary"])
    if set(seeds).intersection(canary_seeds):
        raise ValueError
    basenames = tuple(os.path.basename(ref) for ref in (*modify, *canary_cases))
    if len(basenames) != len(set(basenames)):
        raise ValueError
    if fallback <= 0:
        raise ValueError
    return modify, seeds, equivalence_band, readiness


def _validate_selection(
    value: Any,
    modify_count: int,
    create_count: int,
    seed_count: int,
) -> None:
    selection = _exact_dict(
        value,
        {
            "n_cases_modify",
            "n_cases_create",
            "n_seeds",
            "expand_n_seeds",
            "expose",
            "expand_to_modify",
            "expand_to_create",
            "priority_case_ids",
            "require_expanded_for_pass",
        },
    )
    for key in (
        "n_cases_modify",
        "n_cases_create",
        "n_seeds",
        "expand_to_modify",
        "expand_to_create",
    ):
        _positive_int(selection[key])
    expand_seeds = selection["expand_n_seeds"]
    if expand_seeds is not None:
        _positive_int(expand_seeds)
        if expand_seeds < selection["n_seeds"]:
            raise ValueError
    _text(selection["expose"], allow_empty=False)
    if type(selection["require_expanded_for_pass"]) is not bool:
        raise TypeError
    _case_refs(selection["priority_case_ids"], allow_empty=True)
    if (
        selection["n_cases_modify"] != modify_count
        or selection["n_cases_create"] != create_count
        or selection["n_seeds"] != seed_count
    ):
        raise ValueError


def _validate_screening_gate(value: Any) -> None:
    gate = _exact_dict(
        value,
        {"configured", "resolved_median_delta_min"},
    )
    configured = _exact_dict(
        gate["configured"],
        {
            "min_net_case_score",
            "max_case_loss_rate",
            "win_rate_min",
            "median_delta_min",
            "bootstrap_ci_low_min",
            "initial_quality_expansion",
        },
    )
    min_score = _optional_float(configured["min_net_case_score"])
    max_loss = _optional_float(configured["max_case_loss_rate"])
    if (min_score is None) != (max_loss is None):
        raise ValueError
    if min_score is not None and not -1.0 <= min_score <= 1.0:
        raise ValueError
    if max_loss is not None and not 0.0 <= max_loss <= 1.0:
        raise ValueError
    win_rate = _finite_float(configured["win_rate_min"])
    if not 0.0 <= win_rate <= 1.0:
        raise ValueError
    median = configured["median_delta_min"]
    if type(median) is str:
        configured_median = _validate_median_delta_text(median)
    else:
        configured_median = _finite_float(median)
        if configured_median < 0.0:
            raise ValueError
    _optional_float(configured["bootstrap_ci_low_min"])
    expansion = configured["initial_quality_expansion"]
    if expansion is not None:
        fields = _exact_dict(
            expansion,
            {
                "min_net_case_score",
                "max_case_loss_rate",
                "require_ci_high_at_practical_delta",
            },
        )
        expansion_min = _finite_float(fields["min_net_case_score"])
        expansion_loss = _finite_float(fields["max_case_loss_rate"])
        if (
            not -1.0 <= expansion_min <= 1.0
            or not 0.0 <= expansion_loss <= 1.0
            or type(fields["require_ci_high_at_practical_delta"]) is not bool
        ):
            raise ValueError
    resolved = _finite_float(gate["resolved_median_delta_min"])
    if resolved < 0.0 or (
        configured_median is not None
        and _freeze_json(configured_median) != _freeze_json(resolved)
    ):
        raise ValueError


def _validate_median_delta_text(value: str) -> float | None:
    if value in {"practical_delta_screen", "practical_delta_validate"}:
        return None
    if _NONNEGATIVE_NUMERIC_RE.fullmatch(value) is None:
        raise ValueError
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError
    return number


def _validate_effect_policy(value: Any) -> float:
    policy = _exact_dict(
        value,
        {
            "case_aggregation",
            "case_equivalence_band",
            "effect_metric",
            "protected_objectives",
            "pairing_validity",
            "measurement_governance",
            "runtime_model",
            "max_runtime_ratio",
            "tie_speedup_ratio",
            "tie_min_runtime_pairs",
            "metric_specs",
            "objective_policy",
        },
    )
    equivalence_band = _finite_float(policy["case_equivalence_band"])
    if (
        policy["case_aggregation"] != "paired_effect_median"
        or equivalence_band < 0.0
        or policy["effect_metric"] != "total_distance"
        or policy["pairing_validity"]
        not in {"trajectory_stable", "trajectory_divergent"}
        or policy["measurement_governance"] not in {"on", "record_only"}
        or policy["runtime_model"] not in {"comparative", "budget_exhausting"}
    ):
        raise ValueError
    protected = _text_list(policy["protected_objectives"], allow_empty=True)
    if len(protected) != len(set(protected)):
        raise ValueError
    max_ratio = _finite_float(policy["max_runtime_ratio"])
    speedup = _finite_float(policy["tie_speedup_ratio"])
    if max_ratio <= 0.0 or not 0.0 < speedup <= 1.0:
        raise ValueError
    _positive_int(policy["tie_min_runtime_pairs"])
    _validate_metric_specs(policy["metric_specs"])
    objective = _exact_dict(
        policy["objective_policy"],
        {"mode", "expose_weights_to_llm"},
    )
    if (
        objective["mode"] not in {"single", "lexicographic", "weighted_sum"}
        or type(objective["expose_weights_to_llm"]) is not bool
    ):
        raise ValueError
    return equivalence_band


def _validate_metric_specs(value: Any) -> None:
    specs = _exact_list(value)
    if not specs:
        raise ValueError
    total_distance_rows = 0
    for raw_spec in specs:
        spec = _exact_dict(
            raw_spec,
            {"name", "direction", "priority", "tie_tolerance", "weight"},
        )
        name = _text(spec["name"], allow_empty=False)
        if spec["direction"] not in {"minimize", "maximize"}:
            raise ValueError
        if type(spec["priority"]) is not int:
            raise TypeError
        _finite_float(spec["tie_tolerance"])
        _optional_float(spec["weight"])
        if name == "total_distance":
            if spec["direction"] != "minimize":
                raise ValueError
            total_distance_rows += 1
    if total_distance_rows != 1:
        raise ValueError


def _validate_measurement_readiness(value: Any) -> tuple[Any, ...]:
    readiness = _exact_dict(
        value,
        {
            "status",
            "reason_code",
            "calibration_age_days",
            "calibration_max_age_days",
            "n_pairs",
            "mde_at_power_80",
            "noise_band_p90_abs",
            "effect_to_mde_ratio",
            "signal_to_noise_tier",
            "calibration_evidence_level",
        },
    )
    if (
        readiness["status"] not in {"ready", "degraded", "not_ready"}
        or readiness["reason_code"]
        not in {
            "ok",
            "missing_measurement",
            "missing_calibration_ref",
            "calibration_not_found",
            "calibration_unreadable",
            "calibration_incompatible",
            "calibration_incomplete",
            "calibration_stale",
        }
        or readiness["signal_to_noise_tier"]
        not in {"ready", "marginal", "low_power", "unknown"}
        or readiness["calibration_evidence_level"]
        not in {"none", "summary_only", "pair_evidence", "full_replay"}
    ):
        raise ValueError
    age = readiness["calibration_age_days"]
    if age is not None:
        _nonnegative_int(age)
    _nonnegative_int(readiness["calibration_max_age_days"])
    _nonnegative_int(readiness["n_pairs"])
    for key in (
        "mde_at_power_80",
        "noise_band_p90_abs",
        "effect_to_mde_ratio",
    ):
        number = _optional_float(readiness[key])
        if number is not None and number < 0.0:
            raise ValueError
    return _freeze_json(readiness)


def _validate_runtime_time_limits(value: Any) -> None:
    config = _exact_dict(value, {"stage_defaults", "rules"})
    defaults = config["stage_defaults"]
    if type(defaults) is not dict or any(
        type(stage) is not str
        or stage not in _STAGES
        or type(limit) is not int
        or limit <= 0
        for stage, limit in defaults.items()
    ):
        raise TypeError
    rules = _exact_list(config["rules"])
    for raw_rule in rules:
        rule = _exact_dict(
            raw_rule,
            {
                "time_limit_sec",
                "stages",
                "case_globs",
                "min_dimension",
                "max_dimension",
            },
        )
        _positive_int(rule["time_limit_sec"])
        stages = _text_list(rule["stages"], allow_empty=True)
        if len(stages) != len(set(stages)) or any(
            stage not in _STAGES for stage in stages
        ):
            raise ValueError
        globs = _text_list(rule["case_globs"], allow_empty=True)
        if len(globs) != len(set(globs)):
            raise ValueError
        lower = rule["min_dimension"]
        upper = rule["max_dimension"]
        if lower is not None:
            _nonnegative_int(lower)
        if upper is not None:
            _nonnegative_int(upper)
        if lower is not None and upper is not None and lower > upper:
            raise ValueError


def _validate_resolved_limits(value: Any, cases: tuple[str, ...]) -> None:
    rows = _exact_list(value)
    if len(rows) != len(cases):
        raise ValueError
    observed: list[str] = []
    for row in rows:
        fields = _exact_dict(row, {"case_ref", "time_limit_sec"})
        observed.append(_case_ref(fields["case_ref"]))
        _positive_int(fields["time_limit_sec"])
    if tuple(observed) != cases:
        raise ValueError


def _validate_canary(value: Any) -> tuple[tuple[str, ...], tuple[int, ...]]:
    canary = _exact_dict(value, {"cases", "seeds", "resolved_time_limits"})
    cases = _case_refs(canary["cases"])
    seeds = _seeds(canary["seeds"])
    _validate_resolved_limits(canary["resolved_time_limits"], cases)
    return cases, seeds


def _exact_dict(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise TypeError
    return value


def _exact_list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise TypeError
    return value


def _positive_int(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise TypeError
    return value


def _nonnegative_int(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise TypeError
    return value


def _finite_float(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise TypeError
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return _finite_float(value)


def _text(value: Any, *, allow_empty: bool) -> str:
    if (
        type(value) is not str
        or "\x00" in value
        or len(value.encode("utf-8")) > 4096
        or (not allow_empty and not value)
    ):
        raise TypeError
    return value


def _text_list(value: Any, *, allow_empty: bool) -> tuple[str, ...]:
    items = _exact_list(value)
    if not allow_empty and not items:
        raise ValueError
    return tuple(_text(item, allow_empty=False) for item in items)


def _case_refs(value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = _exact_list(value)
    if not allow_empty and not items:
        raise ValueError
    refs = tuple(_case_ref(item) for item in items)
    if len(refs) != len(set(refs)):
        raise ValueError
    return refs


def _case_ref(value: Any) -> str:
    token = _relative_token(value)
    if public_case_ref(token) != token:
        raise ValueError
    return token


def _seeds(value: Any) -> tuple[int, ...]:
    items = _exact_list(value)
    if not items or any(type(item) is not int or item < 0 for item in items):
        raise ValueError
    seeds = tuple(items)
    if len(seeds) != len(set(seeds)):
        raise ValueError
    return seeds


def _safe_data_roots(value: Any) -> tuple[str, ...]:
    roots = _exact_list(value)
    result: list[str] = []
    for root in roots:
        if (
            type(root) is not str
            or not root
            or "\x00" in root
            or not os.path.isabs(root)
            or os.path.normpath(root) != root
        ):
            raise ValueError
        result.append(root)
    if len(result) != len(set(result)):
        raise ValueError
    return tuple(result)


def _relative_token(value: Any, *, suffix: str | None = None) -> str:
    if type(value) is not str or not value or "\x00" in value or "\\" in value:
        raise TypeError
    encoded = value.encode("utf-8")
    parts = value.split("/")
    if (
        value.startswith("/")
        or len(encoded) > 4096
        or len(parts) > 128
        or any(
            part in {"", ".", ".."} or len(part.encode("utf-8")) > 255 for part in parts
        )
        or (suffix is not None and not value.endswith(suffix))
    ):
        raise ValueError
    return value


def _freeze_json(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if type(value) is str:
        return ("str", value)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return ("float", value.hex())
    if type(value) is list:
        return ("list", tuple(_freeze_json(item) for item in value))
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError
        return (
            "dict",
            tuple((key, _freeze_json(value[key])) for key in sorted(value)),
        )
    raise TypeError


def _masked_frozen(
    value: dict[str, Any],
    paths: tuple[tuple[str, ...], ...],
) -> tuple[Any, ...]:
    detached = _detach_json(value, depth=0)
    for path in paths:
        cursor = detached
        for component in path[:-1]:
            if type(cursor) is not dict:
                raise TypeError
            cursor = cursor[component]
        if type(cursor) is not dict or path[-1] not in cursor:
            raise ValueError
        cursor[path[-1]] = None
    return _freeze_json(detached)


def _detach_json(value: Any, *, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        raise ValueError
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError
        return value
    if type(value) is list:
        return [_detach_json(item, depth=depth + 1) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError
        return {key: _detach_json(item, depth=depth + 1) for key, item in value.items()}
    raise TypeError


__all__: tuple[str, ...] = ()
