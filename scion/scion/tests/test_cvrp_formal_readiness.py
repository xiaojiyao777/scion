"""Formal CVRP matrix-readiness assets.

These tests intentionally treat real benchmark case paths as opaque strings.
They do not open or adapter-load raw CVRPLIB instances.
"""
from __future__ import annotations

import json
from pathlib import Path

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.config.problem import ProblemSpec, ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.protocol.experiment.selection import (
    resolve_case_path_details,
    validate_case_path_resolution,
)
from scion.problems.cvrp.evidence import load_cvrp_case_manifest


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
FORMAL_DIR = CVRP_DIR / "formal"
VRP_DIR = CVRP_DIR.parents[3] / "vrp"
STAGES = ("screening", "validation", "frozen", "final")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_formal_protocol_split_seed_and_budget_assets_load() -> None:
    legacy_problem = ProblemSpec.from_yaml(CVRP_DIR / "problem.yaml")
    protocol = ProtocolConfig.from_yaml(FORMAL_DIR / "protocol.yaml")
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")
    seeds = SeedLedgerConfig.from_yaml(FORMAL_DIR / "seed_ledger.yaml")
    budgets = _load_json(FORMAL_DIR / "budgets.json")
    matrix = _load_json(FORMAL_DIR / "matrix.json")

    assert legacy_problem.name == "cvrp"
    assert legacy_problem.canary_case_path.endswith(
        "controlled/data/synthetic_controlled_canary_5.vrp"
    )
    assert legacy_problem.parameter_search.enabled is False
    assert protocol.version == "0.4-cvrp-formal-readiness"
    assert split.version == "0.4-cvrp-formal-readiness"
    assert seeds.version == "0.4-cvrp-formal-readiness"
    assert budgets["schema"] == "scion.cvrp_formal_readiness_budgets.v1"
    assert budgets["data_root_env"] == "SCION_PROBLEM_DATA_ROOT"
    assert budgets["data_root_expected_repo_relative"] == "vrp"
    assert matrix["schema"] == "scion.cvrp_formal_matrix.v1"
    assert matrix["models"] == ["sonnet", "gpt-mini"]
    assert matrix["campaign_seeds"] == [11, 29, 47]
    assert matrix["rounds_per_campaign"] == 100


def test_formal_manifests_are_fixed_disjoint_and_data_root_relative() -> None:
    manifests = {
        stage: load_cvrp_case_manifest(FORMAL_DIR / "manifests" / f"{stage}.json")
        for stage in STAGES
    }

    seen: dict[str, str] = {}
    for stage, manifest in manifests.items():
        budget = _load_json(FORMAL_DIR / "budgets.json")["stages"][stage]
        assert manifest.schema == "scion.cvrp_case_manifest.v1"
        assert manifest.problem_id == "cvrp"
        assert len(manifest.cases) == budget["cases"]
        assert manifest.config["seeds"] == budget["seeds"]
        assert manifest.metadata["time_limit_sec"] == budget["time_limit_sec"]
        assert manifest.metadata["source_path"] == "vrp/results/full_experiment_seed0_final.csv"
        assert manifest.cases
        for case in manifest.cases:
            assert case.case_id
            assert case.dimension is not None and case.dimension > 0
            assert case.bks is not None
            assert case.bks_routes is not None and case.bks_routes > 0
            assert case.source_path.startswith("cvrplib/")
            assert not case.source_path.startswith("vrp/cvrplib/")
            assert case.case_id not in seen, (
                f"{case.case_id} appears in both {seen.get(case.case_id)} and {stage}"
            )
            seen[case.case_id] = stage


def test_formal_split_manifest_matches_stage_manifests() -> None:
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")
    screening = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "screening.json")
    validation = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "validation.json")
    frozen = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "frozen.json")

    assert split.screening == [case.source_path for case in screening.cases]
    assert split.validation == [case.source_path for case in validation.cases]
    assert split.frozen == [case.source_path for case in frozen.cases]
    assert split.canary == ["controlled/data/synthetic_controlled_canary_5.vrp"]


def test_formal_split_case_resolves_strict_via_declared_problem_data_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = "cvrplib/A/A-n32-k5.vrp"
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(VRP_DIR))
    split = SplitManifest(
        version="0.4-cvrp-formal-readiness",
        screening=[case],
        validation=[],
        frozen=[],
    )

    activation = activate_declared_problem_data_root(
        problem_yaml=CVRP_DIR / "problem.yaml",
        protocol_path=FORMAL_DIR / "protocol.yaml",
    )
    validate_declared_problem_data_cases(
        activation=activation,
        problem_yaml=CVRP_DIR / "problem.yaml",
        split_manifest=split,
    )
    wired_split = with_declared_problem_data_roots(
        activation=activation,
        split_manifest=split,
    )

    resolution = resolve_case_path_details(
        case,
        workspace=str(tmp_path / "workspace"),
        safe_data_roots=wired_split.safe_data_roots,
    )
    validate_case_path_resolution(resolution, strict=True)
    assert resolution.status == "resolved_safe_data_root"
    assert resolution.resolved == str((VRP_DIR / case).resolve())
    assert resolution.matched_root == str(VRP_DIR.resolve())


def test_formal_final_evidence_contract_is_post_campaign_only() -> None:
    budgets = _load_json(FORMAL_DIR / "budgets.json")
    matrix = _load_json(FORMAL_DIR / "matrix.json")

    assert budgets["final_evidence"]["manifest"] == "manifests/final.json"
    assert budgets["final_evidence"]["requires_explicit_registry_paths"] is True
    assert matrix["policy"] == {
        "promotion_objective": ["fleet_violation", "total_distance"],
        "bks_gap_usage": "final_report_only",
        "final_evaluation": "post_campaign_manual",
    }
