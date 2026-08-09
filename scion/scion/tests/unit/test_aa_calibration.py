from __future__ import annotations

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import ExperimentStage
from scion.measurement.aa_calibration import (
    AAPairRecord,
    build_aa_noise_floor_payload,
    estimate_combined_case_rule_null,
    estimate_protocol_power,
    resolve_calibration_time_limit_sec,
    runtime_policy_summary,
    summarize_aa_records,
)
from tools.calibrate_aa_noise import (
    _combined_case_rule,
    _parse_args,
    _select_calibration_population,
)

_COMBINED_RULE = {
    "min_net_case_score": 0.25,
    "max_case_loss_rate": 0.2,
    "median_delta_min": 2.0,
    "bootstrap_ci_low_min": 0.0,
}


def test_aa_calibration_summarizes_per_case_noise() -> None:
    records = [
        AAPairRecord("case-a", 1, 0, "tie", 0.0, 0.0),
        AAPairRecord("case-a", 2, 0, "win", 0.2, 0.2),
        AAPairRecord("case-a", 3, 0, "loss", -0.1, -0.1),
    ]

    rows = summarize_aa_records(records)

    assert rows == [
        {
            "case": "case-a",
            "n_pairs": 3,
            "seed_var": 0.02333333,
            "pair_tie_rate": 0.3333,
            "false_win_rate": 0.3333,
            "false_loss_rate": 0.3333,
            "delta_p50_abs": 0.1,
            "delta_p90_abs": 0.18,
            "delta_max_abs": 0.2,
        }
    ]


def test_aa_calibration_estimates_mde_above_practical_delta_when_noise_large() -> None:
    records = [
        AAPairRecord("case-a", idx, 0, "win" if idx % 2 else "loss", value, value)
        for idx, value in enumerate((-0.6, 0.4, -0.2, 0.3, -0.5, 0.5), start=1)
    ]

    power = estimate_protocol_power(
        records,
        win_rate_min=0.667,
        practical_delta=0.1,
        n_boot=80,
        seed=7,
    )

    assert power["false_pass_rate_at_current_gate"] < 0.5
    assert power["mde_at_power_80"] is not None
    assert power["mde_at_power_80"] > 0.1


def test_aa_calibration_payload_is_problem_owned_diagnostic() -> None:
    records = [
        AAPairRecord(
            "case-a",
            1,
            0,
            "tie",
            0.0,
            0.0,
            candidate_value=10.0,
            champion_value=10.0,
            candidate_seed=1_000_004,
            resolved_case_path="/data/case-a.vrp",
            case_resolution={
                "original": "case-a.vrp",
                "resolved": "/data/case-a.vrp",
                "status": "resolved_safe_data_root",
                "source": "safe_data_root",
                "safe": True,
            },
            champion_elapsed_ms=1200,
            candidate_elapsed_ms=1250,
            time_limit_sec=45,
        )
    ]
    runtime_policy = {
        "selected_policy": "protocol_time_limits",
        "uniform_time_limit_sec": 30,
        "formal_time_limits": {
            "stage": "screening",
            "resolved_unique_sec": [45],
            "rules": [{"min_dimension": 150, "time_limit_sec": 45}],
        },
        "runner_timeout_grace_sec": 15,
        "runner_timeout_sec": 60,
    }

    payload = build_aa_noise_floor_payload(
        records=records,
        problem_id="toy",
        stage="screening",
        metric="cost",
        unit="relative_pct",
        win_rate_min=0.667,
        practical_delta=0.1,
        calibrated_at="2026-06-11T00:00:00+00:00",
        champion_version="v1",
        protocol_version="p1",
        n_boot=10,
        selected_cases=["case-a"],
        selected_seeds=[1],
        replicates=1,
        seed_offset=1_000_003,
        selected_surface="solver_design",
        runtime_policy=runtime_policy,
        safe_data_roots=["/data"],
    )

    assert payload["schema"] == "scion.aa_noise_floor.v1"
    assert payload["decision_features_excluded"] is True
    assert payload["selected_cases"] == ["case-a"]
    assert payload["selected_seeds"] == [1]
    assert payload["replicate_count"] == 1
    assert payload["seed_offset"] == 1_000_003
    assert payload["bootstrap_samples"] == 10
    assert payload["selected_surface"] == "solver_design"
    assert payload["runtime_policy"] == runtime_policy
    assert payload["safe_data_roots"] == ["/data"]
    assert payload["calibration_run"]["decision_features_excluded"] is True
    assert payload["calibration_run"]["selected_cases"] == ["case-a"]
    assert payload["calibration_run"]["selected_seeds"] == [1]
    assert payload["calibration_run"]["replicate_count"] == 1
    assert payload["calibration_run"]["seed_offset"] == 1_000_003
    assert payload["calibration_run"]["bootstrap_samples"] == 10
    assert payload["calibration_run"]["selected_surface"] == "solver_design"
    assert payload["calibration_run"]["runtime_policy"] == runtime_policy
    assert payload["calibration_run"]["safe_data_roots"] == ["/data"]
    assert payload["pair_evidence"] == [
        {
            "case": "case-a",
            "ledger_seed": 1,
            "candidate_seed": 1_000_004,
            "replicate": 0,
            "outcome": "tie",
            "delta": 0.0,
            "raw_delta": 0.0,
            "candidate_value": 10.0,
            "champion_value": 10.0,
            "champion_elapsed_ms": 1200,
            "candidate_elapsed_ms": 1250,
            "resolved_case_path": "/data/case-a.vrp",
            "case_resolution": {
                "original": "case-a.vrp",
                "resolved": "/data/case-a.vrp",
                "status": "resolved_safe_data_root",
                "source": "safe_data_root",
                "safe": True,
            },
            "time_limit_sec": 45,
            "champion_runtime_budget_ratio": 0.0267,
            "candidate_runtime_budget_ratio": 0.0278,
            "champion_runtime_budget_hit": False,
            "candidate_runtime_budget_hit": False,
        }
    ]
    assert payload["policy"] == "problem_owned_measurement_diagnostic"
    assert payload["protocol_power"]["recommended_min_effect"] is not None
    assert "combined_case_rule_null" not in payload


def test_combined_case_rule_all_tie_null_never_passes() -> None:
    pair_evidence = [
        {"case": f"case-{index}", "delta": 0.0}
        for index in range(12)
    ]

    result = estimate_combined_case_rule_null(
        pair_evidence,
        case_equivalence_band=0.0,
        rule=_COMBINED_RULE,
        n_permutations=40,
        ci_bootstrap_samples=40,
        seed=17,
    )

    assert result["schema"] == "scion.combined_case_rule_null.v1"
    assert result["null_method"] == "independent_paired_label_swap"
    assert result["observed"]["ties"] == 12
    assert result["observed"]["passes_rule"] is False
    assert result["null_pass_count"] == 0
    assert result["null_pass_rate"] == 0.0
    assert 0.0 < result["null_pass_rate_wilson_upper_95"] < 0.1
    assert result["decision_features_excluded"] is True


def test_combined_case_rule_polarized_observation_fails() -> None:
    records = [
        AAPairRecord(
            f"case-{index}",
            1,
            0,
            "win" if index < 6 else "loss",
            3.0 if index < 6 else -3.0,
            3.0 if index < 6 else -3.0,
        )
        for index in range(12)
    ]

    result = estimate_combined_case_rule_null(
        records,
        case_equivalence_band=0.0,
        rule=_COMBINED_RULE,
        n_permutations=30,
        ci_bootstrap_samples=30,
        seed=23,
    )

    assert result["observed"]["decisive_cases"] == 12
    assert result["observed"]["net_case_score"] == 0.0
    assert result["observed"]["case_loss_rate"] == 0.5
    assert result["observed"]["passes_rule"] is False


def test_combined_case_rule_fixed_seed_is_deterministic() -> None:
    records = [
        AAPairRecord(
            f"case-{case}",
            seed,
            0,
            "win" if delta > 0 else "loss",
            delta,
            delta,
        )
        for case, deltas in enumerate(((4.0, 2.0), (3.0, -1.0), (-2.0, -4.0)))
        for seed, delta in enumerate(deltas, start=1)
    ]
    kwargs = {
        "case_equivalence_band": 0.0,
        "rule": _COMBINED_RULE,
        "n_permutations": 60,
        "ci_bootstrap_samples": 40,
        "seed": 101,
    }

    first = estimate_combined_case_rule_null(records, **kwargs)
    second = estimate_combined_case_rule_null(records, **kwargs)

    assert first == second


def test_aa_tool_selects_expanded_population_and_seed_prefix() -> None:
    protocol = ProtocolConfig.model_validate(
        {
            "practical_delta_screen": 2.0,
            "case_equivalence_band": 0.0,
            "screening": {
                "n_cases_modify": 2,
                "expand_to_modify": 4,
                "n_seeds": 2,
                "expand_n_seeds": 4,
            },
            "gates": {
                "screening": {
                    "min_net_case_score": 0.25,
                    "max_case_loss_rate": 0.2,
                    "bootstrap_ci_low_min": 0.0,
                }
            },
        }
    )
    split = SplitManifest(
        version="test",
        screening=["a", "b", "c", "d"],
    )
    ledger = SeedLedgerConfig(
        version="test",
        screening=[11, 29, 43, 59],
    )

    cases, seeds = _select_calibration_population(
        protocol=protocol,
        split=split,
        seed_ledger=ledger,
        stage=ExperimentStage.SCREENING,
        hypothesis_action="modify",
        expand_round=1,
        max_seeds=3,
    )

    assert cases == ["a", "b", "c", "d"]
    assert seeds == [11, 29, 43]
    assert _combined_case_rule(protocol, ExperimentStage.SCREENING) == {
        "case_equivalence_band": 0.0,
        "min_net_case_score": 0.25,
        "max_case_loss_rate": 0.2,
        "median_delta_min": 2.0,
        "bootstrap_ci_low_min": 0.0,
    }


def test_aa_tool_parser_exposes_expansion_and_seed_cap() -> None:
    args = _parse_args(
        [
            "--problem-v1", "problem.yaml",
            "--protocol", "protocol.yaml",
            "--split", "split.yaml",
            "--seeds", "seeds.yaml",
            "--champion-workspace", "workspace",
            "--output", "aa.json",
            "--expand-round", "1",
            "--max-seeds", "3",
        ]
    )

    assert args.expand_round == 1
    assert args.max_seeds == 3


def test_aa_calibration_payload_marks_runtime_budget_hits() -> None:
    records = [
        AAPairRecord(
            "case-a",
            1,
            0,
            "tie",
            0.0,
            0.0,
            champion_elapsed_ms=44_100,
            candidate_elapsed_ms=45_250,
            time_limit_sec=45,
        ),
        AAPairRecord(
            "case-b",
            1,
            0,
            "tie",
            0.0,
            0.0,
            champion_elapsed_ms=None,
            candidate_elapsed_ms=None,
            time_limit_sec=45,
        ),
    ]

    payload = build_aa_noise_floor_payload(
        records=records,
        problem_id="toy",
        stage="screening",
        metric="cost",
        unit="raw_delta",
        win_rate_min=0.667,
        practical_delta=0.1,
        calibrated_at="2026-06-11T00:00:00+00:00",
        n_boot=10,
    )

    first, second = payload["pair_evidence"]
    assert first["champion_runtime_budget_ratio"] == 0.98
    assert first["candidate_runtime_budget_ratio"] == 1.0056
    assert first["champion_runtime_budget_hit"] is True
    assert first["candidate_runtime_budget_hit"] is True
    assert second["champion_runtime_budget_ratio"] is None
    assert second["candidate_runtime_budget_ratio"] is None
    assert second["champion_runtime_budget_hit"] is None
    assert second["candidate_runtime_budget_hit"] is None


def test_aa_calibration_runtime_policy_can_resolve_protocol_case_rules() -> None:
    protocol = ProtocolConfig.model_validate(
        {
            "version": "test",
            "runtime": {
                "time_limits": {
                    "stage_defaults": {"screening": 30},
                    "rules": [
                        {
                            "stages": ["screening"],
                            "min_dimension": 150,
                            "max_dimension": 250,
                            "time_limit_sec": 45,
                        },
                        {
                            "stages": ["screening"],
                            "min_dimension": 251,
                            "time_limit_sec": 60,
                        },
                    ],
                }
            },
        }
    )

    summary = runtime_policy_summary(
        protocol=protocol,
        stage=ExperimentStage.SCREENING,
        cases=["cvrplib/A/A-n64-k9.vrp", "cvrplib/M/M-n200-k17.vrp"],
        fallback_time_limit_sec=30,
        selected_policy="protocol_time_limits",
    )

    assert summary["selected_policy"] == "protocol_time_limits"
    assert summary["formal_time_limits"]["resolved_unique_sec"] == [30, 45]
    assert summary["runner_timeout_grace_sec"] == 15
    assert summary["runner_timeout_sec"] == 60
    assert resolve_calibration_time_limit_sec(
        protocol=protocol,
        stage=ExperimentStage.SCREENING,
        case_path="/data/cvrplib/A/A-n64-k9.vrp",
        fallback_time_limit_sec=30,
        runtime_policy="protocol_time_limits",
    ) == 30
    assert resolve_calibration_time_limit_sec(
        protocol=protocol,
        stage=ExperimentStage.SCREENING,
        case_path="/data/cvrplib/M/M-n200-k17.vrp",
        fallback_time_limit_sec=30,
        runtime_policy="protocol_time_limits",
    ) == 45
    assert resolve_calibration_time_limit_sec(
        protocol=protocol,
        stage=ExperimentStage.SCREENING,
        case_path="/data/cvrplib/M/M-n200-k17.vrp",
        fallback_time_limit_sec=30,
        runtime_policy="uniform_time_limit",
    ) == 30
