from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import ExperimentStage, RunResult, SolverOutput
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager


def test_strict_protocol_rejects_unresolved_relative_case_path(tmp_path: Path) -> None:
    runner = MagicMock()
    proto = _protocol(
        runner,
        tmp_path,
        SplitManifest(version="test", screening=["missing.json"]),
        strict_case_paths=True,
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
        strict_case_paths=True,
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
        strict_case_paths=True,
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


def test_protocol_raw_metrics_record_case_path_resolution_status(
    tmp_path: Path,
) -> None:
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _run_result(2, 1000),
        _run_result(1, 900),
    ]
    proto = _protocol(
        runner,
        tmp_path,
        SplitManifest(version="test", screening=["missing.json"]),
        strict_case_paths=False,
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        str(tmp_path / "candidate"),
        str(tmp_path / "champion"),
        "modify",
    )

    raw = json.loads(Path(result.raw_metrics_ref).read_text(encoding="utf-8"))
    resolution = raw["case_path_resolution"]
    assert resolution["strict"] is False
    assert resolution["status_counts"] == {
        "candidate:unresolved_relative": 1,
        "champion:unresolved_relative": 1,
    }
    assert resolution["cases"]["missing.json"]["candidate"]["safe"] is False
    assert (
        resolution["cases"]["missing.json"]["champion"]["status"]
        == "unresolved_relative"
    )


def _protocol(
    runner: MagicMock,
    tmp_path: Path,
    manifest: SplitManifest,
    *,
    strict_case_paths: bool,
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
        strict_case_paths=strict_case_paths,
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
