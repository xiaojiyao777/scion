from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.config.split_manifest import SplitManifest
from scion.protocol.experiment.selection import (
    resolve_case_path_details,
    validate_case_path_resolution,
)


def _write_budget(protocol_dir: Path) -> Path:
    protocol_dir.mkdir(parents=True)
    budgets = protocol_dir / "budgets.json"
    budgets.write_text(
        json.dumps(
            {
                "data_root_env": "SCION_PROBLEM_DATA_ROOT",
                "data_root_expected_repo_relative": "vrp",
            }
        ),
        encoding="utf-8",
    )
    protocol = protocol_dir / "protocol.yaml"
    protocol.write_text("version: test\n", encoding="utf-8")
    return protocol


def test_activate_declared_data_root_from_protocol_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCION_PROBLEM_DATA_ROOT", raising=False)
    problem_yaml = tmp_path / "repo" / "scion" / "scion" / "problems" / "cvrp" / "problem.yaml"
    problem_yaml.parent.mkdir(parents=True)
    problem_yaml.write_text("name: cvrp\n", encoding="utf-8")
    case = tmp_path / "repo" / "vrp" / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")
    protocol = _write_budget(problem_yaml.parent / "formal")

    activation = activate_declared_problem_data_root(
        problem_yaml=problem_yaml,
        protocol_path=protocol,
    )

    assert activation is not None
    assert activation.activated is True
    assert activation.env_name == "SCION_PROBLEM_DATA_ROOT"
    assert activation.data_root == tmp_path / "repo" / "vrp"
    assert os.environ["SCION_PROBLEM_DATA_ROOT"] == str(tmp_path / "repo" / "vrp")
    validate_declared_problem_data_cases(
        activation=activation,
        problem_yaml=problem_yaml,
        split_manifest=SplitManifest(
            screening=["cvrplib/A/A-n32-k5.vrp"],
            validation=[],
            frozen=[],
        ),
    )


def test_declared_data_root_validation_fails_before_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCION_PROBLEM_DATA_ROOT", raising=False)
    problem_yaml = tmp_path / "repo" / "scion" / "scion" / "problems" / "cvrp" / "problem.yaml"
    problem_yaml.parent.mkdir(parents=True)
    problem_yaml.write_text("name: cvrp\n", encoding="utf-8")
    protocol = _write_budget(problem_yaml.parent / "formal")

    activation = activate_declared_problem_data_root(
        problem_yaml=problem_yaml,
        protocol_path=protocol,
    )

    assert activation is not None
    assert activation.activated is False
    with pytest.raises(ValueError, match="cvrplib/A/A-n32-k5.vrp"):
        validate_declared_problem_data_cases(
            activation=activation,
            problem_yaml=problem_yaml,
            split_manifest=SplitManifest(
                screening=["cvrplib/A/A-n32-k5.vrp"],
                validation=[],
                frozen=[],
            ),
        )


def test_declared_data_root_is_wired_into_protocol_safe_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = tmp_path / "repo" / "scion" / "scion" / "problems" / "cvrp" / "problem.yaml"
    problem_yaml.parent.mkdir(parents=True)
    problem_yaml.write_text("name: cvrp\n", encoding="utf-8")
    data_root = tmp_path / "repo" / "vrp"
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")
    protocol = _write_budget(problem_yaml.parent / "formal")
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(data_root))
    split_manifest = SplitManifest(
        screening=["cvrplib/A/A-n32-k5.vrp"],
        validation=[],
        frozen=[],
    )

    activation = activate_declared_problem_data_root(
        problem_yaml=problem_yaml,
        protocol_path=protocol,
    )
    validate_declared_problem_data_cases(
        activation=activation,
        problem_yaml=problem_yaml,
        split_manifest=split_manifest,
    )
    wired_manifest = with_declared_problem_data_roots(
        activation=activation,
        split_manifest=split_manifest,
    )

    assert wired_manifest.safe_data_roots == [str(data_root.resolve())]
    assert split_manifest.safe_data_roots == []
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    resolved = resolve_case_path_details(
        "cvrplib/A/A-n32-k5.vrp",
        workspace=str(workspace),
        safe_data_roots=wired_manifest.safe_data_roots,
    )
    validate_case_path_resolution(resolved, strict=True)
    assert resolved.status == "resolved_safe_data_root"
    assert resolved.resolved == str(case.resolve())

    unresolved = resolve_case_path_details(
        "cvrplib/A/missing.vrp",
        workspace=str(workspace),
        safe_data_roots=wired_manifest.safe_data_roots,
    )
    with pytest.raises(ValueError, match="unresolved_relative"):
        validate_case_path_resolution(unresolved, strict=True)

    outside = tmp_path / "outside.vrp"
    outside.write_text("NAME : outside\n", encoding="utf-8")
    outside_resolution = resolve_case_path_details(
        str(outside),
        workspace=str(workspace),
        safe_data_roots=wired_manifest.safe_data_roots,
    )
    with pytest.raises(ValueError, match="absolute_outside_roots"):
        validate_case_path_resolution(outside_resolution, strict=True)
