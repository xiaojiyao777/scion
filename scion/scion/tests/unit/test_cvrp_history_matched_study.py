from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.problem.loader import load_problem_adapter, load_problem_spec_v1_from_yaml
from tools import cvrp_history_matched_study as study_runner
from tools.generate_cvrp_history_matched_cases import (
    CASE_SPECS,
    NAMESPACE,
    check_cases,
    constructive_routes,
    generate_case,
    render_case,
    specs_for_block,
)

SCION_ROOT = Path(__file__).resolve().parents[3]
CONFIG = SCION_ROOT / "experiments" / "cvrp_history_matched_study" / "study.json"
VRP_ROOT = SCION_ROOT.parent / "vrp"
CVRPLIB_ROOT = VRP_ROOT / "cvrplib"
GENERATED_ROOT = VRP_ROOT / NAMESPACE
FULL_RESULTS = VRP_ROOT / "results" / "full_experiment_seed0_final.csv"
REFERENCE_VALIDATION_BAD = VRP_ROOT / "results" / "reference_validation_bad.csv"


def _without_arm_variation(command: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(command):
        value = command[index]
        if value == "--research-history":
            index += 2
            continue
        if value == "--campaign-dir":
            normalized.extend((value, "<campaign-dir>"))
            index += 2
            continue
        normalized.append(value)
        index += 1
    return normalized


def _csv_case_paths(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            str(row["path"])
            for row in csv.DictReader(stream)
            if str(row.get("path") or "").startswith("cvrplib/")
        }


def _local_cvrplib_paths() -> set[str]:
    return {
        f"cvrplib/{path.relative_to(CVRPLIB_ROOT).as_posix()}"
        for path in CVRPLIB_ROOT.glob("*/*.vrp")
    }


def _best_fit_decreasing_bin_count(demands: list[int], capacity: int) -> int:
    remaining: list[int] = []
    for demand in sorted(demands, reverse=True):
        choices = [
            (slack - demand, index)
            for index, slack in enumerate(remaining)
            if slack >= demand
        ]
        if not choices:
            remaining.append(capacity - demand)
            continue
        _, index = min(choices)
        remaining[index] -= demand
    return len(remaining)


def test_provider_free_preflight_loads_exact_matched_design() -> None:
    study = study_runner.load_study_config(CONFIG)

    assert study.model == "gpt-5.6-sol"
    assert study.problem_path.name == "problem-v1.yaml"
    assert study.problem_dir == SCION_ROOT / "scion" / "problems" / "cvrp"
    assert study.total_arms == 10
    assert len(study.blocks) == 5
    assert [block.order for block in study.blocks] == [
        ("on", "off"),
        ("off", "on"),
        ("on", "off"),
        ("off", "on"),
        ("on", "off"),
    ]
    assert len(study.history_paths) == 16
    assert len(study.history_records) == 45
    assert study.provider_call_cap == 34
    assert study.provider_call_cap_total == 340
    assert study.rounds == 2
    assert study.formal_stage_cap_total == 20
    assert not study.protocol.runtime.time_limits.rules
    assert {
        study.protocol.runtime.time_limits.resolve(
            stage="screening",
            case_path=case,
            fallback_time_limit_sec=study.time_limit_sec,
        )
        for block in study.blocks
        for case in block.split.screening
    } == {30}
    assert study.protocol.screening.require_expanded_for_pass is True
    assert (
        study_runner.preflight_summary(study, "/tmp/not-created")[
            "heldout_stage_reachable"
        ]
        is False
    )


def test_matched_pair_differs_only_by_history_and_output_path(tmp_path: Path) -> None:
    study = study_runner.load_study_config(CONFIG)
    block = study.blocks[0]
    off = study_runner.build_campaign_command(
        study, block, "off", tmp_path, python="python"
    )
    on = study_runner.build_campaign_command(
        study, block, "on", tmp_path, python="python"
    )

    assert off.count("--research-history") == 0
    assert on.count("--research-history") == 16
    assert off[off.index("--problem") + 1] == str(study.problem_path)
    assert _without_arm_variation(off) == _without_arm_variation(on)
    assert off[off.index("--split") + 1] == on[on.index("--split") + 1]
    for forbidden in (
        "--qualification-only",
        "--max-proposal-attempts",
        "--max-verified-candidate-chains",
        "--max-formal-screening-stages",
    ):
        assert forbidden not in off
        assert forbidden not in on


def test_existing_cvrplib_has_no_literal_fresh_case() -> None:
    pool = _local_cvrplib_paths()
    full_results = _csv_case_paths(FULL_RESULTS)
    reference_bad = _csv_case_paths(REFERENCE_VALIDATION_BAD)
    uncovered = pool - full_results

    assert len(pool) == 10_344
    assert len(full_results) == 10_330
    assert len(uncovered) == 14
    assert uncovered <= reference_bad
    assert len(pool - (full_results | reference_bad)) == 0
    assert study_runner.SCREENING_EXCLUSION_AUDIT == {
        "local_cvrplib_cases": 10_344,
        "full_results_covered_cases": 10_330,
        "reference_validation_bad_cases": 14,
        "historically_contaminated_existing_cases": 10_344,
        "fresh_existing_cases": 0,
        "synthetic_namespace": NAMESPACE,
        "synthetic_fixed_input_cases": 30,
        "synthetic_generator_historical_inputs": 0,
        "synthetic_generator_outcome_inputs": 0,
        "synthetic_solution_sidecars": 0,
    }


def test_generated_payload_construction_reads_no_external_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "builtins.open",
        lambda *_args, **_kwargs: pytest.fail(
            "fixed synthetic generation must not read an external source"
        ),
    )

    assert len([generate_case(spec) for spec in CASE_SPECS]) == 30


def test_generated_cases_exactly_regenerate_and_are_constructively_feasible() -> None:
    study = study_runner.load_study_config(CONFIG)
    adapter = load_problem_adapter(load_problem_spec_v1_from_yaml(study.problem_path))
    assert check_cases(GENERATED_ROOT) == tuple(
        spec.relative_path for spec in CASE_SPECS
    )
    assert not list(GENERATED_ROOT.glob("*.sol"))
    assert len(CASE_SPECS) == len({spec.relative_path for spec in CASE_SPECS}) == 30

    for block_index, block in enumerate(study.blocks, 1):
        specs = specs_for_block(block_index)
        assert tuple(block.split.screening) == tuple(
            spec.relative_path for spec in specs
        )
        assert [spec.structure for spec in specs]
        dimensions = [spec.dimension for spec in specs]
        assert dimensions[0] <= 100
        assert 180 <= dimensions[2] <= 320
        assert 500 <= dimensions[5] <= 800
        for spec in specs:
            path = VRP_ROOT / spec.relative_path
            assert path.read_text(encoding="utf-8") == render_case(spec)
            assert generate_case(spec)["bks"] is None
            assert generate_case(spec)["bks_routes"] is None
            instance = adapter.load_instance(str(path))
            routes = constructive_routes(spec)
            covered = tuple(customer for route in routes for customer in route)
            assert covered == instance.customer_ids
            assert len(routes) == instance.allowed_routes == spec.allowed_routes
            assert all(
                instance.route_load(route) <= instance.capacity for route in routes
            )
            total_demand = sum(instance.demands[customer] for customer in covered)
            assert (
                math.ceil(total_demand / instance.capacity) == instance.allowed_routes
            )
            assert (
                _best_fit_decreasing_bin_count(
                    [instance.demands[customer] for customer in covered],
                    instance.capacity,
                )
                == instance.allowed_routes
            )


def test_preflight_and_command_printing_do_not_launch_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        study_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("provider/solver launch is forbidden"),
    )

    assert (
        study_runner.main(
            [
                "--config",
                str(CONFIG),
                "--output-root",
                str(tmp_path / "not-created"),
                "--preflight",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ready"
    assert summary["history_files_off"] == 0
    assert summary["history_records_on"] == 45
    assert summary["screening_cases"] == 30
    assert summary["screening_cases_unique"] == 30
    assert summary["screening_cases_adapter_loaded"] == 30
    assert summary["screening_time_limit_sec_unique"] == [30]
    assert summary["screening_initial_positions"] == [0, 2, 5]
    assert summary["screening_initial_strata"] == ["small", "medium", "large"]
    assert summary["screening_generation_structures"] == [
        "uniform",
        "clustered",
        "radial",
    ]
    assert summary["screening_exact_regeneration_checked"] == 30
    assert summary["screening_arm_input_bytes_identical"] is True
    assert summary["screening_selection_reads_outcomes"] is False
    assert summary["screening_exclusion_audit_at_freeze"] == (
        study_runner.SCREENING_EXCLUSION_AUDIT
    )
    assert not (tmp_path / "not-created").exists()


def test_execute_uses_normal_artifact_paths_without_wrapper_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    study = study_runner.load_study_config(CONFIG)
    output_root = tmp_path / "study"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        campaign_path = Path(command[command.index("--campaign-dir") + 1])
        campaign_path.mkdir(parents=True)
        (campaign_path / "status.json").write_text("{}\n", encoding="utf-8")
        (campaign_path / "campaign_summary.json").write_text("{}\n", encoding="utf-8")
        assert kwargs["cwd"] == study_runner.SCION_ROOT
        assert kwargs["env"]["SCION_MODEL"] == "gpt-5.6-sol"
        return SimpleNamespace(returncode=124 if len(calls) == 1 else 21)

    monkeypatch.setenv("SCION_API_KEY", "local-test-key")
    monkeypatch.setattr(study_runner.subprocess, "run", fake_run)

    assert study_runner.execute_study(study, output_root) == 0
    assert len(calls) == 10
    assert [
        Path(command[command.index("--campaign-dir") + 1]).relative_to(output_root)
        for command in calls
    ] == [
        Path(block.block_id) / arm for block, arm in study_runner.iter_campaigns(study)
    ]
    assert not (output_root / "manifest.json").exists()
    assert not (output_root / "receipt.json").exists()


def test_analyze_existing_uses_matched_observed_endpoint_pairs(tmp_path: Path) -> None:
    study = study_runner.load_study_config(CONFIG)
    output_root = tmp_path / "study"
    source_record = json.loads(
        study.history_paths[0].read_text(encoding="utf-8").splitlines()[0]
    )
    hypothesis = source_record["hypothesis"]

    for block in study.blocks:
        for arm in study_runner.ARMS:
            paths = study_runner.campaign_artifact_paths(output_root, block, arm)
            paths["status"].parent.mkdir(parents=True)
            paths["status"].write_text("{}\n", encoding="utf-8")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "steps": [
                            {
                                "round": 1,
                                "branch_id": "branch-a",
                                "hypothesis": hypothesis,
                                "contract_passed": True,
                                "verification_passed": True,
                                "protocol_result": {"stage": "screening"},
                                "decision": "continue_explore",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            paths["history"].write_text(
                json.dumps(source_record, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            if arm == "on":
                paths["traces"].mkdir()
                (paths["traces"] / "hypothesis-0001.json").write_text(
                    json.dumps({"action": "read_history", "ref": "history-0001"})
                    + "\n",
                    encoding="utf-8",
                )

    report = study_runner.analyze_existing(study, output_root)

    assert report["schema_version"] == "scion.cvrp_history_matched_analysis.v1"
    assert len(report["blocks"]) == 5
    history_reads = report["aggregate_descriptive_endpoints"]["endpoints"][
        "history_use.all_deliberation.read_actions"
    ]
    assert history_reads == {
        "history_on_by_block": [1, 1, 1, 1, 1],
        "history_off_by_block": [0, 0, 0, 0, 0],
        "difference_on_minus_off_by_block": [1, 1, 1, 1, 1],
        "matched_history_on_mean": 1.0,
        "matched_history_off_mean": 0.0,
        "matched_mean_delta_on_minus_off": 1.0,
        "observed_pairs": 5,
    }
    assert not (output_root / "analysis.json").exists()
    assert not (output_root / "manifest.json").exists()


def test_aggregate_comparison_excludes_unmatched_missing_endpoint_values() -> None:
    reports = [
        {
            "endpoints": {
                "metric": {
                    "history_on": 4,
                    "history_off": 1,
                    "difference_on_minus_off": 3,
                }
            }
        },
        {
            "endpoints": {
                "metric": {
                    "history_on": 99,
                    "history_off": None,
                    "difference_on_minus_off": None,
                }
            }
        },
        {
            "endpoints": {
                "metric": {
                    "history_on": 8,
                    "history_off": 2,
                    "difference_on_minus_off": 6,
                }
            }
        },
    ]

    aggregate = study_runner._aggregate_comparisons(reports)["endpoints"]["metric"]

    assert aggregate == {
        "history_on_by_block": [4, 99, 8],
        "history_off_by_block": [1, None, 2],
        "difference_on_minus_off_by_block": [3, None, 6],
        "matched_history_on_mean": 6.0,
        "matched_history_off_mean": 1.5,
        "matched_mean_delta_on_minus_off": 4.5,
        "observed_pairs": 2,
    }


def test_execute_rejects_nonfresh_output_without_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    study = study_runner.load_study_config(CONFIG)
    monkeypatch.setenv("SCION_API_KEY", "local-test-key")
    monkeypatch.setattr(
        study_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("launch is forbidden"),
    )

    with pytest.raises(study_runner.StudyConfigError, match="fresh output root"):
        study_runner.execute_study(study, tmp_path)
