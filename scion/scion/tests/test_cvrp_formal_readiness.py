"""Formal CVRP matrix-readiness assets.

These tests intentionally treat real benchmark case paths as opaque strings.
They do not open or adapter-load raw CVRPLIB instances.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.models import ExperimentStage
from scion.problems.cvrp.evidence import load_cvrp_case_manifest
from scion.protocol.experiment import SplitManager
from scion.protocol.experiment.selection import (
    resolve_case_path_details,
    select_cases,
    validate_case_path_resolution,
)

CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
FORMAL_DIR = CVRP_DIR / "formal"
VRP_DIR = CVRP_DIR.parents[3] / "vrp"
STAGES = ("screening", "validation", "frozen", "final")
PROTOCOL_STAGES = ("screening", "validation", "frozen")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_final_ledger_rows_by_path() -> dict[str, dict[str, str]]:
    source = VRP_DIR / "results" / "full_experiment_seed0_final.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        return {
            row["path"]: row
            for row in csv.DictReader(handle)
            if row["mode"] == "clarke_wright_alns_vns"
        }


def _load_reference_bad_instances() -> set[str]:
    source = VRP_DIR / "results" / "reference_validation_bad.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        return {row["instance"] for row in csv.DictReader(handle)}


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
    assert protocol.version == "0.4-cvrp-v3-quality-screen-r3"
    assert split.version == "0.4-cvrp-v3-quality-screen-r3"
    assert seeds.version == "0.4-cvrp-v3-quality-screen-r3"
    assert budgets["schema"] == "scion.cvrp_formal_readiness_budgets.v1"
    assert budgets["data_root_env"] == "SCION_PROBLEM_DATA_ROOT"
    assert budgets["data_root_expected_repo_relative"] == "vrp"
    assert matrix["schema"] == "scion.cvrp_formal_matrix.v1"
    assert matrix["models"] == ["gpt-5.6-terra"]
    assert "campaign_seeds" not in matrix
    assert matrix["rounds_per_campaign"] == 16
    assert matrix["total_campaigns"] == 1
    assert budgets["models"] == matrix["models"]
    assert budgets["campaign_rounds"] == matrix["rounds_per_campaign"]
    assert "campaign_seeds" not in budgets
    assert protocol.case_aggregation == "paired_effect_median"
    assert protocol.case_equivalence_band == 0.0
    assert protocol.screening.n_cases_modify == 8
    assert protocol.screening.n_cases_create == 8
    assert protocol.screening.n_seeds == 4
    assert protocol.screening.effective_expand_n_seeds == 8
    assert protocol.screening.expand_to_modify == 12
    assert protocol.screening.expand_to_create == 12
    assert protocol.screening.require_expanded_for_pass is True
    assert protocol.validation.n_cases == 12
    assert protocol.validation.n_seeds == 8
    assert protocol.frozen.n_cases == 12
    assert protocol.frozen.n_seeds == 8
    assert protocol.runtime.time_limits.stage_defaults == {
        "canary": 10,
        "screening": 30,
        "validation": 30,
        "frozen": 30,
    }


def test_formal_manifests_are_fixed_disjoint_and_data_root_relative() -> None:
    manifests = {
        stage: load_cvrp_case_manifest(FORMAL_DIR / "manifests" / f"{stage}.json")
        for stage in STAGES
    }

    seen: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for stage, manifest in manifests.items():
        budget = _load_json(FORMAL_DIR / "budgets.json")["stages"][stage]
        assert manifest.schema == "scion.cvrp_case_manifest.v1"
        assert manifest.problem_id == "cvrp"
        assert len(manifest.cases) == budget["cases"]
        assert manifest.config["seeds"] == budget["seeds"]
        assert manifest.metadata["time_limit_policy"].endswith("dimension_only")
        assert budget["time_limit_policy"] == "dimension_only"
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
            assert case.source_path not in seen_paths, (
                f"{case.source_path} appears in both "
                f"{seen_paths.get(case.source_path)} and {stage}"
            )
            seen[case.case_id] = stage
            seen_paths[case.source_path] = stage

    assert len(seen) == len(seen_paths) == 48


def test_formal_split_manifest_matches_stage_manifests() -> None:
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")
    screening = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "screening.json")
    validation = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "validation.json")
    frozen = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "frozen.json")

    assert split.screening == [case.source_path for case in screening.cases]
    assert split.validation == [case.source_path for case in validation.cases]
    assert split.frozen == [case.source_path for case in frozen.cases]
    assert split.canary == ["controlled/data/synthetic_controlled_canary_5.vrp"]


def test_formal_stage_seeds_are_consistent_across_assets() -> None:
    protocol = ProtocolConfig.from_yaml(FORMAL_DIR / "protocol.yaml")
    seeds = SeedLedgerConfig.from_yaml(FORMAL_DIR / "seed_ledger.yaml")
    budgets = _load_json(FORMAL_DIR / "budgets.json")

    for stage in ("validation", "frozen"):
        ledger_seeds = getattr(seeds, stage)
        manifest = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / f"{stage}.json")
        stage_protocol = getattr(protocol, stage)

        assert len(ledger_seeds) == stage_protocol.n_seeds
        assert budgets["stages"][stage]["seeds"] == ledger_seeds
        assert manifest.config["seeds"] == ledger_seeds
        assert manifest.metadata["seed_list"] == ledger_seeds

    # The screening manifest records the initial seed prefix and separately
    # names the exact quality expansion from the same ordered R3 ledger.
    screening_manifest = load_cvrp_case_manifest(
        FORMAL_DIR / "manifests" / "screening.json"
    )
    initial_screening_seeds = seeds.screening[: protocol.screening.n_seeds]
    assert seeds.screening == [11, 29, 43, 59, 73, 79, 97, 103]
    assert len(seeds.screening) == protocol.screening.effective_expand_n_seeds
    assert budgets["stages"]["screening"]["seeds"] == initial_screening_seeds
    assert screening_manifest.config["seeds"] == initial_screening_seeds
    assert screening_manifest.metadata["seed_list"] == initial_screening_seeds
    assert screening_manifest.metadata["expanded_seed_list"] == seeds.screening
    assert budgets["stages"]["screening"]["expanded_seeds"] == seeds.screening
    assert budgets["stages"]["screening"][
        "initial_selected_by_protocol_cases"
    ] == protocol.screening.n_cases_modify
    assert budgets["stages"]["screening"][
        "expanded_selected_by_protocol_cases"
    ] == protocol.screening.expand_to_modify
    assert budgets["stages"]["validation"][
        "selected_by_protocol_cases"
    ] == protocol.validation.n_cases
    assert budgets["stages"]["frozen"][
        "selected_by_protocol_cases"
    ] == protocol.frozen.n_cases

    final = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "final.json")
    final_seeds = [157, 163, 167, 173, 179, 181, 191, 193]
    assert final.config["seeds"] == budgets["final_evidence"]["seeds"] == final_seeds
    assert final.metadata["seed_list"] == final_seeds
    assert budgets["final_evidence"]["visibility"] == "post_campaign_manual_only"

    seed_groups = [
        set(seeds.screening),
        set(seeds.validation),
        set(seeds.frozen),
        set(seeds.canary),
        set(final_seeds),
    ]
    assert sum(len(group) for group in seed_groups) == len(set().union(*seed_groups))


def test_formal_protocol_uses_one_dimension_only_budget_policy() -> None:
    protocol = ProtocolConfig.from_yaml(FORMAL_DIR / "protocol.yaml")
    time_limits = protocol.runtime.time_limits
    budgets = _load_json(FORMAL_DIR / "budgets.json")

    examples = (
        ("cvrplib/A/A-n80-k10.vrp", 30),
        ("cvrplib/E/E-n101-k14.vrp", 45),
        ("cvrplib/M/M-n200-k17.vrp", 45),
        ("cvrplib/X/X-n204-k19.vrp", 60),
        ("cvrplib/X/X-n350-k40.vrp", 60),
        ("cvrplib/X/X-n359-k29.vrp", 90),
        ("cvrplib/X/X-n700-k40.vrp", 90),
        ("cvrplib/X/X-n701-k44.vrp", 120),
        ("cvrplib/X/X-n1001-k43.vrp", 120),
    )
    for stage in PROTOCOL_STAGES:
        for case_path, expected in examples:
            assert time_limits.resolve(
                stage=stage,
                case_path=case_path,
                fallback_time_limit_sec=10,
            ) == expected

    # CMT filenames omit n<N>. These aliases recover the CSV ledger dimensions
    # and therefore apply the same 101..200 rule rather than a family override.
    assert time_limits.resolve(
        stage="screening",
        case_path="cvrplib/CMT/CMT3.vrp",
        fallback_time_limit_sec=10,
    ) == 45
    assert time_limits.resolve(
        stage="frozen",
        case_path="cvrplib/CMT/CMT4.vrp",
        fallback_time_limit_sec=10,
    ) == 45
    assert time_limits.resolve(
        stage="validation",
        case_path="cvrplib/CMT/CMT2.vrp",
        fallback_time_limit_sec=10,
    ) == 30

    expected_bands = [
        {"min_dimension": 1, "max_dimension": 100, "time_limit_sec": 30},
        {"min_dimension": 101, "max_dimension": 200, "time_limit_sec": 45},
        {"min_dimension": 201, "max_dimension": 350, "time_limit_sec": 60},
        {"min_dimension": 351, "max_dimension": 700, "time_limit_sec": 90},
        {"min_dimension": 701, "max_dimension": 1001, "time_limit_sec": 120},
    ]
    assert budgets["time_limit_policy"] == {
        "basis": "instance_dimension",
        "bands": expected_bands,
        "canary_time_limit_sec": 10,
        "filename_dimension_aliases": {"CMT3.vrp": 101, "CMT4.vrp": 151},
    }

    for stage in PROTOCOL_STAGES:
        manifest = load_cvrp_case_manifest(
            FORMAL_DIR / "manifests" / f"{stage}.json"
        )
        for case in manifest.cases:
            assert case.dimension is not None
            expected = next(
                band["time_limit_sec"]
                for band in expected_bands
                if band["min_dimension"] <= case.dimension <= band["max_dimension"]
            )
            assert time_limits.resolve(
                stage=stage,
                case_path=case.source_path,
                fallback_time_limit_sec=10,
            ) == expected


def test_formal_screening_selection_uses_declared_quality_prefix() -> None:
    protocol = ProtocolConfig.from_yaml(FORMAL_DIR / "protocol.yaml")
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")

    selected = select_cases(
        config=protocol,
        split_manager=SplitManager(split),
        stage=ExperimentStage.SCREENING,
        hypothesis_action="create_new",
        expand_round=0,
    )

    assert len(selected) == protocol.screening.n_cases_create
    assert protocol.screening.priority_case_ids == tuple(split.screening[:8])
    assert selected == split.screening[:8] == [
        "cvrplib/P/P-n65-k10.vrp",
        "cvrplib/A/A-n80-k10.vrp",
        "cvrplib/E/E-n101-k14.vrp",
        "cvrplib/M/M-n151-k12.vrp",
        "cvrplib/X/X-n120-k6.vrp",
        "cvrplib/X/X-n233-k16.vrp",
        "cvrplib/X/X-n439-k37.vrp",
        "cvrplib/X/X-n502-k39.vrp",
    ]


def test_formal_modify_expansion_strictly_contains_initial_population() -> None:
    protocol = ProtocolConfig.from_yaml(FORMAL_DIR / "protocol.yaml")
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")
    manager = SplitManager(split)

    initial = select_cases(
        config=protocol,
        split_manager=manager,
        stage=ExperimentStage.SCREENING,
        hypothesis_action="modify",
        expand_round=0,
    )
    expanded = select_cases(
        config=protocol,
        split_manager=manager,
        stage=ExperimentStage.SCREENING,
        hypothesis_action="modify",
        expand_round=1,
    )

    assert len(initial) == protocol.screening.n_cases_modify == 8
    assert len(expanded) == protocol.screening.expand_to_modify == 12
    assert set(initial) < set(expanded)
    assert expanded == split.screening


def test_formal_cases_are_reference_clean_and_screening_has_gap_headroom() -> None:
    rows_by_path = _load_final_ledger_rows_by_path()
    reference_bad = _load_reference_bad_instances()
    manifests = {
        stage: load_cvrp_case_manifest(FORMAL_DIR / "manifests" / f"{stage}.json")
        for stage in STAGES
    }

    screening_gaps: list[float] = []
    for stage, manifest in manifests.items():
        for case in manifest.cases:
            row = rows_by_path.get(case.source_path)
            assert row is not None, f"{stage} case missing from final seed-0 ledger"
            assert row["status"] == "ok"
            assert row["feasible"] == "True"
            assert row["benchmark_feasible"] == "True"
            assert row["route_gap"] == "0"
            assert row["instance"] not in reference_bad
            assert float(row["gap_pct"]) > 1.0
            assert case.case_id == row["instance"]
            assert case.dimension == int(row["dimension"])
            assert case.bks == float(row["bks"])
            assert case.bks_routes == int(row["bks_routes"])
            assert case.subset == row["subset"]
            if stage == "screening":
                screening_gaps.append(float(row["gap_pct"]))

    assert len(screening_gaps) == 12
    assert min(screening_gaps) >= 2.0
    assert max(screening_gaps) <= 10.0
    assert sum(gap >= 2.5 for gap in screening_gaps) >= 11


def test_formal_split_case_resolves_strict_via_declared_problem_data_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = "cvrplib/A/A-n32-k5.vrp"
    data_root = tmp_path / "data-root"
    case_path = data_root / case
    case_path.parent.mkdir(parents=True)
    case_path.write_text("NAME : fixture\n", encoding="utf-8")
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(data_root))
    split = SplitManifest(
        version="0.4-cvrp-v3-quality-screen-r3",
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
    assert resolution.resolved == str(case_path.resolve())
    assert resolution.matched_root == str(data_root.resolve())


def test_formal_final_evidence_contract_is_post_campaign_only() -> None:
    budgets = _load_json(FORMAL_DIR / "budgets.json")
    matrix = _load_json(FORMAL_DIR / "matrix.json")
    split = SplitManifest.from_yaml(FORMAL_DIR / "split_manifest.yaml")
    final = load_cvrp_case_manifest(FORMAL_DIR / "manifests" / "final.json")

    assert budgets["final_evidence"]["manifest"] == "manifests/final.json"
    assert budgets["final_evidence"]["requires_explicit_registry_paths"] is True
    assert budgets["final_evidence"]["visibility"] == "post_campaign_manual_only"
    assert matrix["policy"]["final_evaluation"] == "post_campaign_manual"
    assert matrix["policy"]["final_replay_visibility"] == (
        "hidden_from_proposal_and_search_context"
    )
    assert [case.source_path for case in final.cases] == [
        "cvrplib/A/A-n64-k9.vrp",
        "cvrplib/X/X-n139-k10.vrp",
        "cvrplib/X/X-n561-k42.vrp",
        "cvrplib/B/B-n63-k10.vrp",
        "cvrplib/X/X-n261-k13.vrp",
        "cvrplib/X/X-n701-k44.vrp",
        "cvrplib/P/P-n70-k10.vrp",
        "cvrplib/tai/tai150b.vrp",
        "cvrplib/X/X-n1001-k43.vrp",
        "cvrplib/tai/tai75c.vrp",
        "cvrplib/X/X-n308-k13.vrp",
        "cvrplib/X/X-n856-k95.vrp",
    ]
    protocol_cases = set(split.screening + split.validation + split.frozen + split.canary)
    assert protocol_cases.isdisjoint(case.source_path for case in final.cases)
    assert matrix["policy"] == {
        "promotion_objective": ["fleet_violation", "total_distance"],
        "bks_gap_usage": "final_report_only",
        "final_evaluation": "post_campaign_manual",
        "final_replay_visibility": "hidden_from_proposal_and_search_context",
    }
