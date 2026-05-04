from __future__ import annotations

import json
from pathlib import Path

from scion.evidence import (
    CvrpCaseEntry,
    CvrpCaseManifest,
    CvrpCaseSelectionConfig,
    CvrpManifestEvaluationConfig,
    build_cvrp_case_manifest_from_csv,
    build_cvrp_final_evaluation_config_from_manifest,
    load_cvrp_case_manifest,
)
from scion.evidence.cvrp_baseline_import import load_cvrp_result_rows
from scion.problems.cvrp.adapter import CvrpAdapter


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
CONTROLLED_DIR = CVRP_DIR / "controlled"
STAGES = ("screening", "validation", "frozen", "final")
EXPECTED_TOP_LEVEL = (
    "README.md",
    "budgets.json",
    "screening.csv",
    "validation.csv",
    "frozen.csv",
    "final.csv",
)


class _Spec:
    pass


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(stage: str) -> CvrpCaseManifest:
    return load_cvrp_case_manifest(CONTROLLED_DIR / "manifests" / f"{stage}.json")


def _source_path(case: CvrpCaseEntry) -> Path:
    path = Path(case.source_path)
    return path if path.is_absolute() else CVRP_DIR / path


def test_all_expected_controlled_files_exist() -> None:
    for relative_path in EXPECTED_TOP_LEVEL:
        assert (CONTROLLED_DIR / relative_path).is_file()

    for stage in STAGES:
        assert (CONTROLLED_DIR / "manifests" / f"{stage}.json").is_file()
        manifest = _load_manifest(stage)
        for case in manifest.cases:
            instance_path = _source_path(case)
            assert instance_path.is_file()
            assert instance_path.with_suffix(".sol").is_file()


def test_manifests_have_expected_payload_shape() -> None:
    for stage in STAGES:
        payload = _load_json(CONTROLLED_DIR / "manifests" / f"{stage}.json")
        assert set(payload) == {"schema", "problem_id", "config", "metadata", "cases"}
        assert payload["schema"] == "scion.cvrp_case_manifest.v1"
        assert payload["problem_id"] == "cvrp"
        assert payload["config"]["subsets"] == [stage]
        assert payload["metadata"]["stage"] == stage
        assert payload["metadata"]["source_path"] == f"{stage}.csv"
        assert payload["metadata"]["n_selected_cases"] == len(payload["cases"])
        assert payload["cases"]
        for case in payload["cases"]:
            assert set(case) == {
                "bks",
                "bks_routes",
                "case_id",
                "dimension",
                "source_path",
                "subset",
            }
            assert case["subset"] == stage


def test_selected_case_ids_are_disjoint_across_stages() -> None:
    seen: dict[str, str] = {}
    for stage in STAGES:
        manifest = _load_manifest(stage)
        for case in manifest.cases:
            assert case.case_id not in seen, (
                f"{case.case_id} appears in both {seen.get(case.case_id)} and {stage}"
            )
            seen[case.case_id] = stage

    assert len(seen) == 8


def test_every_source_path_exists_and_loads_through_cvrp_adapter() -> None:
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    for stage in STAGES:
        manifest = _load_manifest(stage)
        for case in manifest.cases:
            instance_path = _source_path(case)
            instance = adapter.load_instance(str(instance_path))
            assert instance.name == case.case_id
            assert len(instance.nodes) == case.dimension
            assert instance.bks == case.bks
            assert instance.bks_routes == case.bks_routes
            assert instance.customer_ids


def test_budgets_declare_stage_time_limits_and_seeds() -> None:
    payload = _load_json(CONTROLLED_DIR / "budgets.json")
    assert payload["schema"] == "scion.cvrp_controlled_budgets.v1"
    assert payload["problem_id"] == "cvrp"
    assert set(payload["stages"]) == set(STAGES)

    for stage in STAGES:
        stage_budget = payload["stages"][stage]
        manifest = _load_manifest(stage)
        assert stage_budget["manifest"] == f"manifests/{stage}.json"
        assert stage_budget["csv"] == f"{stage}.csv"
        assert stage_budget["seeds"] == manifest.config["seeds"]
        assert stage_budget["time_limit_sec"] == manifest.metadata["time_limit_sec"]
        assert isinstance(stage_budget["time_limit_sec"], int)
        assert stage_budget["time_limit_sec"] > 0
        assert stage_budget["seeds"]


def test_csv_rows_are_importable_and_match_checked_in_manifests() -> None:
    for stage in STAGES:
        rows = load_cvrp_result_rows(CONTROLLED_DIR / f"{stage}.csv")
        checked_in = _load_manifest(stage)
        built = build_cvrp_case_manifest_from_csv(
            CONTROLLED_DIR / f"{stage}.csv",
            config=CvrpCaseSelectionConfig(
                subsets=(stage,),
                seeds=tuple(checked_in.config["seeds"]),  # type: ignore[arg-type]
                max_cases_total=2,
                source_label="controlled_synthetic_csv",
            ),
        )

        assert [row.case_id for row in rows] == [case.case_id for case in checked_in.cases]
        assert [case.to_payload() for case in built.cases] == [
            case.to_payload() for case in checked_in.cases
        ]
        assert all(row.status == "ok" for row in rows)
        assert all(row.benchmark_feasible is True for row in rows)


def test_final_manifest_builds_final_evaluation_config_from_budget() -> None:
    budgets = _load_json(CONTROLLED_DIR / "budgets.json")
    final_budget = budgets["stages"]["final"]
    manifest = _load_manifest("final")
    config = CvrpManifestEvaluationConfig(
        campaign_id="controlled-final-smoke",
        baseline_workspace=CVRP_DIR,
        candidate_workspace=CVRP_DIR,
        time_limit_sec=final_budget["time_limit_sec"],
        seeds=final_budget["seeds"],
    )

    final_config = build_cvrp_final_evaluation_config_from_manifest(
        manifest,
        config=config,
    )

    assert final_config.problem_id == "cvrp"
    assert final_config.campaign_id == "controlled-final-smoke"
    assert final_config.time_limit_sec == 2
    assert final_config.seeds == (0, 1)
    assert final_config.case_paths == tuple(case.source_path for case in manifest.cases)


def test_controlled_fixture_paths_do_not_reference_raw_benchmark_tree() -> None:
    forbidden = "vrp/cvrplib"
    for stage in STAGES:
        manifest = _load_manifest(stage)
        rows = load_cvrp_result_rows(CONTROLLED_DIR / f"{stage}.csv")
        assert forbidden not in str(CONTROLLED_DIR / f"{stage}.csv")
        for case in manifest.cases:
            assert forbidden not in case.source_path.lower()
        for row in rows:
            assert row.source_path is not None
            assert forbidden not in row.source_path.lower()
