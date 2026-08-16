from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import ExperimentStage, RunResult, SolverOutput
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.protocol.experiment.selection import resolve_case_path_details
from scion.problem.spec import ObjectiveMetricSpec


_METRIC_SPECS = (
    ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
    ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
)


WAREHOUSE_CONFIG_DIR = (
    Path(__file__).resolve().parents[4] / "problems" / "warehouse_delivery"
)


def test_strict_protocol_rejects_unresolved_relative_case_path(tmp_path: Path) -> None:
    runner = MagicMock()
    proto = _protocol(
        runner,
        tmp_path,
        SplitManifest(version="test", screening=["missing.json"]),
    )

    with pytest.raises(ValueError, match="unresolved_relative"):
        proto.run_experiment(
            ExperimentStage.SCREENING,
            str(tmp_path / "candidate"),
            str(tmp_path / "champion"),
            "modify",
        )

    runner.run_solver.assert_not_called()


def test_strict_protocol_rejects_absolute_case_path_outside_allowed_roots(
    tmp_path: Path,
) -> None:
    outside_case = tmp_path / "outside.json"
    outside_case.write_text("{}", encoding="utf-8")
    runner = MagicMock()
    proto = _protocol(
        runner,
        tmp_path,
        SplitManifest(version="test", screening=[str(outside_case)]),
    )

    with pytest.raises(ValueError, match="absolute_outside_roots"):
        proto.run_experiment(
            ExperimentStage.SCREENING,
            str(tmp_path / "candidate"),
            str(tmp_path / "champion"),
            "modify",
        )

    runner.run_solver.assert_not_called()


def test_strict_protocol_resolves_relative_case_path_under_safe_data_root(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _run_result(1, 900),
        _run_result(1, 900),
    ]
    proto = _protocol(
        runner,
        tmp_path,
        SplitManifest(
            version="test",
            screening=["cvrplib/A/A-n32-k5.vrp"],
            safe_data_roots=[str(data_root)],
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        str(tmp_path / "candidate"),
        str(tmp_path / "champion"),
        "modify",
    )

    assert result.case_ids == ("cvrplib/A/A-n32-k5.vrp",)
    assert runner.run_solver.call_count == 2
    assert {
        call.kwargs["instance_path"]
        for call in runner.run_solver.call_args_list
    } == {str(case.resolve())}
    raw = json.loads(Path(result.raw_metrics_ref).read_text(encoding="utf-8"))
    assert raw["case_path_resolution"]["strict"] is True
    assert raw["case_path_resolution"]["status_counts"] == {
        "champion:resolved_safe_data_root": 1,
        "candidate:resolved_safe_data_root": 1,
    }


def test_warehouse_prod_canary_paths_run_under_strict_protocol(
    tmp_path: Path,
) -> None:
    split_manifest = SplitManifest.from_yaml(
        WAREHOUSE_CONFIG_DIR / "split_manifest_prod.yaml"
    )
    data_root = (
        WAREHOUSE_CONFIG_DIR / "../../../../scion-data"
    ).resolve(strict=False)

    assert split_manifest.canary
    assert Path(split_manifest.safe_data_roots[0]) == data_root
    for case in split_manifest.canary:
        resolution = resolve_case_path_details(
            case,
            workspace=str(tmp_path / "candidate"),
            safe_data_roots=split_manifest.safe_data_roots,
        )
        assert resolution.safe is True
        assert resolution.status == "resolved_safe_data_root"

    runner = MagicMock()
    runner.run_solver.side_effect = [
        _run_result(1, 12000),
        _run_result(1, 12000),
    ] * len(split_manifest.canary)
    (tmp_path / "candidate").mkdir()
    (tmp_path / "champion").mkdir()
    proto = ExperimentProtocol(
        ProtocolConfig.from_yaml(WAREHOUSE_CONFIG_DIR / "protocol_prod.yaml"),
        SplitManager(split_manifest),
        SeedLedger(
            SeedLedgerConfig(
                version="test",
                screening=[1],
                validation=[2],
                frozen=[3],
                canary=[99],
            )
        ),
        runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=_METRIC_SPECS,
    )

    result = proto.run_canary(
        str(tmp_path / "candidate"),
        str(tmp_path / "champion"),
    )

    assert result.passed is True
    assert runner.run_solver.call_count == len(split_manifest.canary) * 2
    assert {
        call.kwargs["instance_path"]
        for call in runner.run_solver.call_args_list
    } == set(split_manifest.canary)


def _protocol(
    runner: MagicMock,
    tmp_path: Path,
    manifest: SplitManifest,
) -> ExperimentProtocol:
    (tmp_path / "candidate").mkdir(exist_ok=True)
    (tmp_path / "champion").mkdir(exist_ok=True)
    return ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(manifest),
        SeedLedger(
            SeedLedgerConfig(
                version="test",
                screening=[1],
                validation=[2],
                frozen=[3],
                canary=[99],
            )
        ),
        runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=_METRIC_SPECS,
    )


def _run_result(splits: int, cost: float) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=100,
        output=SolverOutput(
            objective={"subcategory_splits": splits, "total_cost": cost},
            feasible=True,
            runtime={},
        ),
    )
