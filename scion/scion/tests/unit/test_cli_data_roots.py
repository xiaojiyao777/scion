from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
)
from scion.config.split_manifest import SplitManifest


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
