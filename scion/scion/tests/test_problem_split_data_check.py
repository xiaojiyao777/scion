from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL = SCION_DIR / "tools" / "check_problem_split_data.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("check_problem_split_data", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_specs(tmp_path: Path) -> tuple[Path, Path, Path]:
    problem_dir = tmp_path / "problem"
    problem_dir.mkdir()
    problem = problem_dir / "problem.yaml"
    problem.write_text("name: unit\n", encoding="utf-8")
    split = problem_dir / "split.yaml"
    split.write_text(
        "version: unit\n"
        "screening:\n"
        "  - cvrplib/A/unit.vrp\n"
        "validation: []\n"
        "frozen: []\n"
        "canary:\n"
        "  - controlled/data/canary.vrp\n",
        encoding="utf-8",
    )
    canary = problem_dir / "controlled" / "data" / "canary.vrp"
    canary.parent.mkdir(parents=True)
    canary.write_text("NAME : canary\n", encoding="utf-8")
    return problem, split, tmp_path / "data"


def test_report_requires_cases_from_the_explicit_data_root(tmp_path: Path) -> None:
    tool = _load_tool_module()
    problem, split, data_root = _write_specs(tmp_path)
    instance = data_root / "cvrplib" / "A" / "unit.vrp"
    instance.parent.mkdir(parents=True)
    instance.write_text("NAME : unit\n", encoding="utf-8")
    instance.with_suffix(".sol").write_text("Cost 1\n", encoding="utf-8")

    report = tool.build_report(
        problem=str(problem),
        split=str(split),
        data_root=data_root,
    )

    assert report["ok"] is True
    assert report["declared_case_count"] == 2
    assert report["missing_cases"] == []
    assert report["missing_companions"] == []
    assert report["identity_file_count"] == 3
    assert len(str(report["identity_sha256"])) == 64


def test_report_fails_when_the_explicit_data_root_is_missing(tmp_path: Path) -> None:
    tool = _load_tool_module()
    problem, split, data_root = _write_specs(tmp_path)

    report = tool.build_report(
        problem=str(problem),
        split=str(split),
        data_root=data_root,
    )

    assert report["ok"] is False
    assert report["missing_cases"] == ["cvrplib/A/unit.vrp"]


def test_report_requires_external_solution_companion(tmp_path: Path) -> None:
    tool = _load_tool_module()
    problem, split, data_root = _write_specs(tmp_path)
    instance = data_root / "cvrplib" / "A" / "unit.vrp"
    instance.parent.mkdir(parents=True)
    instance.write_text("NAME : unit\n", encoding="utf-8")

    report = tool.build_report(
        problem=str(problem),
        split=str(split),
        data_root=data_root,
    )

    assert report["ok"] is False
    assert report["missing_cases"] == []
    assert report["missing_companions"] == ["cvrplib/A/unit.sol"]


def test_main_fails_closed_when_expected_identity_changes(
    tmp_path: Path,
    capsys,
) -> None:
    tool = _load_tool_module()
    problem, split, data_root = _write_specs(tmp_path)
    instance = data_root / "cvrplib" / "A" / "unit.vrp"
    instance.parent.mkdir(parents=True)
    instance.write_text("NAME : unit\n", encoding="utf-8")
    instance.with_suffix(".sol").write_text("Cost 1\n", encoding="utf-8")

    status = tool.main(
        [
            "--problem",
            str(problem),
            "--split",
            str(split),
            "--data-root",
            str(data_root),
            "--expected-identity-sha256",
            "0" * 64,
        ]
    )

    assert status == tool.FAILURE_EXIT
    assert '"identity_matches_expected": false' in capsys.readouterr().out
