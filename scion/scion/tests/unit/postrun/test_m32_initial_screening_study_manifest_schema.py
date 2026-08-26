from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.postrun.research_effectiveness.study_manifest_controls_schema import (
    _CONTROLS_LIMITATIONS,
    _freeze_json,
)
from scion.postrun.research_effectiveness.study_manifest_schema import (
    _ERROR,
    _JOIN_LIMITATIONS,
    _canonical_json_bytes,
    _config_subset_join_result,
    _derive_expectation,
    _normalize_root_controls,
    _normalize_study_manifest,
    _StudyManifestSchemaError,
    _validate_root_control_join,
)

_EXPECTED_CONTROLS_LIMITATIONS = (
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
_EXPECTED_JOIN_LIMITATIONS = (
    "SCIENTIFIC_ENDPOINTS_NOT_EVALUATED",
    "PROBLEM_SPEC_UNVERIFIED",
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "PROVIDER_REQUEST_POLICY_UNVERIFIED",
    "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "MANIFEST_GIT_AND_PREOUTCOME_TIMING_UNVERIFIED",
    "POPULATION_FRESHNESS_UNVERIFIED",
    "ACTUAL_ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
    "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
    "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)


def _controls(block: int, k: int) -> dict[str, Any]:
    case_ref = f"development/block-{block}.vrp"
    canary_ref = f"canary/control-{block}.vrp"
    return {
        "schema_version": ("scion.initial_screening_study_controls.config_subset.v1"),
        "scope": "CONFIG_SUBSET_ONLY",
        "limitations": list(_EXPECTED_CONTROLS_LIMITATIONS),
        "campaign": {
            "campaign_mode": "qualification_only",
            "development_boundary_mode": "initial_screening_only_v1",
            "requested_rounds": 3,
            "qualification_limits": {
                "max_proposal_attempts": 3,
                "max_verified_candidate_chains": 3,
                "max_formal_screening_stages": 3,
            },
            "scheduler": {"max_active_branches": 3},
        },
        "code_research_limits": CodeResearchLimits(
            max_hypothesis_candidates=k
        ).to_primitive(),
        "resource_envelope": {
            "provider_call_cap": 40,
            "outer_hardwall_sec": 300,
        },
        "protocol": {
            "version": "m32-schema-test-v1",
            "strict_case_paths": True,
            "safe_data_roots": ["/srv/cvrp-data"],
            "initial_screening": {
                "cases_by_action": {
                    "modify_or_remove": [case_ref],
                    "create_new": [case_ref],
                },
                "seeds": [block],
                "selection": {
                    "n_cases_modify": 1,
                    "n_cases_create": 1,
                    "n_seeds": 1,
                    "expand_n_seeds": 2,
                    "expose": "full",
                    "expand_to_modify": 2,
                    "expand_to_create": 2,
                    "priority_case_ids": [case_ref],
                    "require_expanded_for_pass": True,
                },
                "screening_gate": {
                    "configured": {
                        "min_net_case_score": 0.25,
                        "max_case_loss_rate": 0.2,
                        "win_rate_min": 0.6,
                        "median_delta_min": "practical_delta_screen",
                        "bootstrap_ci_low_min": 0.0,
                        "initial_quality_expansion": {
                            "min_net_case_score": 0.125,
                            "max_case_loss_rate": 0.25,
                            "require_ci_high_at_practical_delta": True,
                        },
                    },
                    "resolved_median_delta_min": 0.0,
                },
                "effect_policy": {
                    "case_aggregation": "paired_effect_median",
                    "case_equivalence_band": 0.0,
                    "effect_metric": "total_distance",
                    "protected_objectives": ["fleet_violation"],
                    "pairing_validity": "trajectory_stable",
                    "measurement_governance": "on",
                    "runtime_model": "comparative",
                    "max_runtime_ratio": 2.0,
                    "tie_speedup_ratio": 0.75,
                    "tie_min_runtime_pairs": 1,
                    "metric_specs": [
                        {
                            "name": "fleet_violation",
                            "direction": "minimize",
                            "priority": 1,
                            "tie_tolerance": 0.0,
                            "weight": None,
                        },
                        {
                            "name": "total_distance",
                            "direction": "minimize",
                            "priority": 2,
                            "tie_tolerance": 0.001,
                            "weight": None,
                        },
                    ],
                    "objective_policy": {
                        "mode": "lexicographic",
                        "expose_weights_to_llm": False,
                    },
                },
                "measurement_readiness": {
                    "status": "not_ready",
                    "reason_code": "missing_measurement",
                    "calibration_age_days": None,
                    "calibration_max_age_days": 0,
                    "n_pairs": 0,
                    "mde_at_power_80": None,
                    "noise_band_p90_abs": None,
                    "effect_to_mde_ratio": None,
                    "signal_to_noise_tier": "unknown",
                    "calibration_evidence_level": "none",
                },
                "runtime_time_limits": {
                    "stage_defaults": {"screening": 30, "canary": 10},
                    "rules": [],
                },
                "resolved_time_limits": [{"case_ref": case_ref, "time_limit_sec": 30}],
            },
            "canary": {
                "cases": [canary_ref],
                "seeds": [100 + block],
                "resolved_time_limits": [
                    {"case_ref": canary_ref, "time_limit_sec": 10}
                ],
            },
            "time_limit_fallback_sec": 30,
        },
    }


def _manifest() -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for block in range(1, 6):
        order = (1, 2) if block % 2 else (2, 1)
        blocks.append(
            {
                "block_ordinal": block,
                "loaded_history": (
                    {"availability": "available", "files": []}
                    if block % 2
                    else {
                        "availability": "unavailable",
                        "reason": "HISTORY_REPLAY_BASIS_UNAVAILABLE",
                    }
                ),
                "arms": [
                    {
                        "treatment": f"K{k}",
                        "campaign_id": f"m32-block-{block}-k{k}",
                        "root_path": f"outcomes/block-{block}/k{k}",
                        "declared_controls": _controls(block, k),
                    }
                    for k in order
                ],
            }
        )
    return {
        "schema_version": ("scion.initial_screening_study_manifest.config_subset.v1"),
        "scope": "CONFIG_SUBSET_ONLY",
        "problem_id": "cvrp",
        "blocks": blocks,
    }


def _fixed_error(error: BaseException) -> None:
    assert type(error) is _StudyManifestSchemaError
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_normalizes_exact_manifest_without_retaining_aliases() -> None:
    raw = _manifest()
    normalized = _normalize_study_manifest(raw)
    original_bytes = normalized.blocks[0].arms[0].declared_controls.canonical_bytes
    raw["problem_id"] = "drift"
    raw["blocks"][0]["arms"][0]["declared_controls"]["campaign"]["requested_rounds"] = (
        99
    )

    assert normalized.problem_id == "cvrp"
    assert len(normalized.blocks) == 5
    assert normalized.blocks[0].loaded_history.available is True
    assert normalized.blocks[1].loaded_history.available is False
    assert normalized.blocks[0].arms[0].treatment == "K1"
    assert normalized.blocks[1].arms[0].treatment == "K2"
    assert normalized.blocks[0].arms[0].declared_controls.canonical_bytes == (
        original_bytes
    )
    assert repr(normalized) == "_NormalizedStudyManifest(<redacted>)"
    assert "development/block" not in repr(normalized.blocks[0].arms[0])


def test_joins_root_and_independent_subsets_and_derives_expectation() -> None:
    raw = _manifest()
    normalized = _normalize_study_manifest(raw)
    arm = normalized.blocks[0].arms[0]
    root = _normalize_root_controls(
        copy.deepcopy(raw["blocks"][0]["arms"][0]["declared_controls"])
    )
    joined = _validate_root_control_join(
        arm,
        root,
        copy.deepcopy(
            raw["blocks"][0]["arms"][0]["declared_controls"]["code_research_limits"]
        ),
        copy.deepcopy(
            raw["blocks"][0]["arms"][0]["declared_controls"]["resource_envelope"]
        ),
    )
    expectation = _derive_expectation(normalized.problem_id, joined)

    assert joined is root
    assert expectation.problem_id == "cvrp"
    assert expectation.expected_initial_case_count == 1
    assert expectation.expected_initial_pair_count == 1
    assert expectation.a_cap == 3
    assert expectation.p_cap == 40
    assert expectation.max_hypothesis_candidates == 1
    assert expectation.case_refs == ("development/block-1.vrp",)
    assert expectation.seeds == (1,)
    assert repr(expectation) == "_StudyExpectationFacts(<redacted>)"


def test_returns_only_fixed_partial_validation_result() -> None:
    result = _config_subset_join_result()
    assert result == {
        "schema_version": (
            "scion.initial_screening_study_manifest_join.config_subset.v1"
        ),
        "status": "CONFIG_SUBSET_JOINED",
        "validated_scope": "CONFIG_SUBSET_ONLY",
        "blocks_checked": 5,
        "arms_checked": 10,
        "limitations": list(_EXPECTED_JOIN_LIMITATIONS),
    }
    assert len(result["limitations"]) == 20
    assert not {
        "endpoint",
        "sign",
        "efficiency",
        "fidelity",
        "utility",
        "history_count",
    }.intersection(result)


def test_frozen_limitation_oracles_are_exact() -> None:
    assert _CONTROLS_LIMITATIONS == _EXPECTED_CONTROLS_LIMITATIONS
    assert _JOIN_LIMITATIONS == _EXPECTED_JOIN_LIMITATIONS


@pytest.mark.parametrize(
    "mutation",
    [
        "top_extra",
        "block_ordinal",
        "duplicate_campaign",
        "duplicate_root",
        "nested_root",
        "absolute_root",
        "history_suffix",
        "history_union",
        "treatment_k",
        "unbalanced_order",
        "pair_non_k",
        "pair_signed_zero",
        "cross_common",
        "cross_signed_zero",
        "overlapping_cell",
        "problem_id",
    ],
)
def test_rejects_manifest_structure_and_match_mutations(mutation: str) -> None:
    raw = _manifest()
    if mutation in {
        "top_extra",
        "problem_id",
        "block_ordinal",
        "duplicate_campaign",
        "duplicate_root",
        "nested_root",
        "absolute_root",
    }:
        _mutate_manifest_identity_or_path(raw, mutation)
    else:
        _mutate_manifest_history_or_controls(raw, mutation)

    with pytest.raises(_StudyManifestSchemaError) as caught:
        _normalize_study_manifest(raw)

    _fixed_error(caught.value)


def _mutate_manifest_identity_or_path(raw: dict[str, Any], mutation: str) -> None:
    if mutation == "top_extra":
        raw["go"] = True
    elif mutation == "problem_id":
        raw["problem_id"] = "1cvrp"
    elif mutation == "block_ordinal":
        raw["blocks"][2]["block_ordinal"] = 4
    elif mutation == "duplicate_campaign":
        raw["blocks"][1]["arms"][0]["campaign_id"] = raw["blocks"][0]["arms"][0][
            "campaign_id"
        ]
    elif mutation == "duplicate_root":
        raw["blocks"][1]["arms"][0]["root_path"] = raw["blocks"][0]["arms"][0][
            "root_path"
        ]
    elif mutation == "nested_root":
        raw["blocks"][1]["arms"][0]["root_path"] = "outcomes/block-1/k1/child"
    elif mutation == "absolute_root":
        raw["blocks"][0]["arms"][0]["root_path"] = "/tmp/root"


def _mutate_manifest_history_or_controls(raw: dict[str, Any], mutation: str) -> None:
    if mutation in {
        "history_suffix",
        "history_union",
        "treatment_k",
        "unbalanced_order",
    }:
        _mutate_manifest_history_or_treatment(raw, mutation)
    else:
        _mutate_manifest_control_match(raw, mutation)


def _mutate_manifest_history_or_treatment(raw: dict[str, Any], mutation: str) -> None:
    if mutation == "history_suffix":
        raw["blocks"][0]["loaded_history"]["files"] = ["history/input.json"]
    elif mutation == "history_union":
        raw["blocks"][1]["loaded_history"]["files"] = []
    elif mutation == "treatment_k":
        raw["blocks"][0]["arms"][0]["declared_controls"]["code_research_limits"][
            "max_hypothesis_candidates"
        ] = 2
    elif mutation == "unbalanced_order":
        for block in raw["blocks"]:
            block["arms"].sort(key=lambda arm: arm["treatment"])


def _mutate_manifest_control_match(raw: dict[str, Any], mutation: str) -> None:
    if mutation == "pair_non_k":
        raw["blocks"][0]["arms"][1]["declared_controls"]["campaign"]["scheduler"][
            "max_active_branches"
        ] = 2
    elif mutation == "pair_signed_zero":
        raw["blocks"][0]["arms"][1]["declared_controls"]["protocol"][
            "initial_screening"
        ]["effect_policy"]["case_equivalence_band"] = -0.0
    elif mutation == "cross_common":
        raw["blocks"][1]["arms"][0]["declared_controls"]["protocol"][
            "safe_data_roots"
        ] = ["/other"]
        raw["blocks"][1]["arms"][1]["declared_controls"]["protocol"][
            "safe_data_roots"
        ] = ["/other"]
    elif mutation == "cross_signed_zero":
        for arm in raw["blocks"][1]["arms"]:
            arm["declared_controls"]["protocol"]["initial_screening"]["effect_policy"][
                "case_equivalence_band"
            ] = -0.0
    else:
        for arm in raw["blocks"][1]["arms"]:
            initial = arm["declared_controls"]["protocol"]["initial_screening"]
            initial["cases_by_action"] = {
                "modify_or_remove": ["development/block-1.vrp"],
                "create_new": ["development/block-1.vrp"],
            }
            initial["seeds"] = [1]
            initial["selection"]["priority_case_ids"] = ["development/block-1.vrp"]
            initial["resolved_time_limits"] = [
                {"case_ref": "development/block-1.vrp", "time_limit_sec": 30}
            ]


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "loose_number",
        "qualification_mismatch",
        "create_roster",
        "resolved_order",
        "effect_metric",
        "metric_direction",
        "seed_overlap",
        "limitations",
        "nonpublic_case",
        "median_delta_text",
        "median_delta_mismatch",
        "median_delta_signed_zero",
    ],
)
def test_rejects_incomplete_or_semantically_invalid_controls(mutation: str) -> None:
    raw = _controls(1, 1)
    initial = raw["protocol"]["initial_screening"]
    if mutation in {
        "extra",
        "loose_number",
        "qualification_mismatch",
        "create_roster",
        "resolved_order",
        "effect_metric",
    }:
        _mutate_control_shape_or_roster(raw, initial, mutation)
    else:
        _mutate_control_effect_or_identity(raw, initial, mutation)

    with pytest.raises(_StudyManifestSchemaError) as caught:
        _normalize_root_controls(raw)

    _fixed_error(caught.value)


def _mutate_control_shape_or_roster(
    raw: dict[str, Any], initial: dict[str, Any], mutation: str
) -> None:
    if mutation == "extra":
        raw["campaign"]["extra"] = 1
    elif mutation == "loose_number":
        raw["campaign"]["scheduler"]["max_active_branches"] = 3.0
    elif mutation == "qualification_mismatch":
        raw["campaign"]["qualification_limits"]["max_proposal_attempts"] = 2
    elif mutation == "create_roster":
        initial["cases_by_action"]["create_new"] = ["development/other.vrp"]
    elif mutation == "resolved_order":
        initial["resolved_time_limits"][0]["case_ref"] = "development/other.vrp"
    elif mutation == "effect_metric":
        initial["effect_policy"]["effect_metric"] = "fleet_violation"


def _mutate_control_effect_or_identity(
    raw: dict[str, Any], initial: dict[str, Any], mutation: str
) -> None:
    if mutation == "metric_direction":
        initial["effect_policy"]["metric_specs"][1]["direction"] = "maximize"
    elif mutation == "seed_overlap":
        raw["protocol"]["canary"]["seeds"] = [1]
    elif mutation == "nonpublic_case":
        initial["cases_by_action"] = {
            "modify_or_remove": ["C:/hidden.vrp"],
            "create_new": ["C:/hidden.vrp"],
        }
        initial["selection"]["priority_case_ids"] = ["C:/hidden.vrp"]
        initial["resolved_time_limits"][0]["case_ref"] = "C:/hidden.vrp"
    elif mutation == "median_delta_text":
        initial["screening_gate"]["configured"]["median_delta_min"] = "arbitrary"
    elif mutation == "median_delta_mismatch":
        initial["screening_gate"]["configured"]["median_delta_min"] = "0.5"
    elif mutation == "median_delta_signed_zero":
        initial["screening_gate"]["configured"]["median_delta_min"] = 0.0
        initial["screening_gate"]["resolved_median_delta_min"] = -0.0
    else:
        raw["limitations"] = raw["limitations"][::-1]


def test_preserves_objective_metric_schema_fidelity_outside_endpoint_row() -> None:
    raw = _controls(1, 1)
    metrics = raw["protocol"]["initial_screening"]["effect_policy"]["metric_specs"]
    metrics[0]["priority"] = -7
    metrics[0]["tie_tolerance"] = -0.5
    metrics.append(copy.deepcopy(metrics[0]))

    controls = _normalize_root_controls(raw)

    assert controls.k == 1


@pytest.mark.parametrize(
    "surface", ["declaration", "signed_zero", "code_limits", "resource"]
)
def test_root_join_is_exact_and_type_aware(surface: str) -> None:
    raw = _manifest()
    manifest = _normalize_study_manifest(raw)
    arm = manifest.blocks[0].arms[0]
    controls_raw = copy.deepcopy(raw["blocks"][0]["arms"][0]["declared_controls"])
    if surface == "declaration":
        controls_raw["campaign"]["scheduler"]["max_active_branches"] = 2
    elif surface == "signed_zero":
        controls_raw["protocol"]["initial_screening"]["effect_policy"][
            "case_equivalence_band"
        ] = -0.0
    root = _normalize_root_controls(controls_raw)
    code_limits = copy.deepcopy(controls_raw["code_research_limits"])
    resource = copy.deepcopy(controls_raw["resource_envelope"])
    if surface == "code_limits":
        code_limits["max_turns"] -= 1
    elif surface == "resource":
        resource["provider_call_cap"] += 1

    with pytest.raises(_StudyManifestSchemaError) as caught:
        _validate_root_control_join(arm, root, code_limits, resource)

    _fixed_error(caught.value)


def test_freeze_json_preserves_signed_zero_in_readiness_and_masks() -> None:
    positive = _controls(1, 1)
    negative = copy.deepcopy(positive)
    positive["protocol"]["initial_screening"]["measurement_readiness"][
        "mde_at_power_80"
    ] = 0.0
    negative["protocol"]["initial_screening"]["measurement_readiness"][
        "mde_at_power_80"
    ] = -0.0

    positive_controls = _normalize_root_controls(positive)
    negative_controls = _normalize_root_controls(negative)

    assert _freeze_json(0.0) != _freeze_json(-0.0)
    assert positive_controls.measurement_readiness != (
        negative_controls.measurement_readiness
    )
    assert positive_controls.pair_key != negative_controls.pair_key
    assert positive_controls.cross_block_key != negative_controls.cross_block_key


def test_canonical_json_is_strict_bounded_and_terminal_lf() -> None:
    value = {"z": [1, 1.0, False], "a": "\u03bb"}
    encoded = _canonical_json_bytes(value, max_bytes=128)
    assert (
        encoded
        == json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    with pytest.raises(ValueError):
        _canonical_json_bytes(value, max_bytes=2)
    with pytest.raises(TypeError):
        _canonical_json_bytes({"bad": object()})


def test_rejects_container_subclasses_without_running_hooks() -> None:
    calls: list[str] = []

    class HookedDict(dict[str, Any]):
        def __iter__(self) -> Any:
            calls.append("iter")
            return super().__iter__()

    with pytest.raises(_StudyManifestSchemaError) as caught:
        _normalize_study_manifest(HookedDict(_manifest()))

    _fixed_error(caught.value)
    assert calls == []
