from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "cvrp_runtime_curve.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("cvrp_runtime_curve", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_case_budget_and_build_jobs(tmp_path: Path) -> None:
    tool = _load_tool()

    case_budget = tool.parse_case_budget("cvrplib/X/X-n573-k30.vrp=120")
    jobs = tool.build_jobs(
        case_budgets=[case_budget],
        seeds=[61, 67],
        multipliers=[1.0, 2.0, 4.0],
        output_dir=tmp_path,
    )

    assert [job.time_limit_sec for job in jobs] == [120, 240, 480] * 2
    assert jobs[0].case == "cvrplib/X/X-n573-k30.vrp"
    assert jobs[0].output_path.name == "X-n573-k30_seed61_m1_tl120.json"


def test_runtime_curve_dry_run_writes_summary_and_csv(tmp_path: Path) -> None:
    tool = _load_tool()
    data_root = tmp_path / "vrp"
    case_dir = data_root / "cvrplib" / "X"
    case_dir.mkdir(parents=True)
    (case_dir / "X-n573-k30.sol").write_text("Route #1: 1\nCost 50673\n")

    output_dir = tmp_path / "curve"
    status = tool.main(
        [
            "--workspace",
            str(tmp_path / "workspace"),
            "--data-root",
            str(data_root),
            "--output-dir",
            str(output_dir),
            "--case-budget",
            "cvrplib/X/X-n573-k30.vrp=120",
            "--seed",
            "61",
            "--multiplier",
            "1",
            "--multiplier",
            "2",
            "--dry-run",
        ]
    )

    assert status == 0
    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["schema_version"] == "cvrp_runtime_curve.v1"
    assert summary["dry_run"] is True
    assert len(summary["jobs"]) == 2
    assert summary["jobs"][0]["status"] == "planned"
    assert summary["jobs"][0]["bks"] == 50673.0
    assert (output_dir / "summary.csv").exists()
