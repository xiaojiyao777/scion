"""Tests for generic problem runtime dependency preflight."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from scion.problem.preflight import (
    ResearchEnvironmentPreflightError,
    RuntimeDependencyPreflightError,
    run_research_environment_preflight,
    run_runtime_preflight,
)
from scion.problem.spec import RuntimeDependencySpec


class _Spec:
    def __init__(self, dependencies: RuntimeDependencySpec | None = None) -> None:
        if dependencies is not None:
            self.runtime_dependencies = dependencies


def test_missing_required_python_module_fails_with_interpreter() -> None:
    missing = "scion_missing_dependency_for_preflight_test_987654321"
    spec = _Spec(RuntimeDependencySpec(required_python_modules=[missing]))

    with pytest.raises(RuntimeDependencyPreflightError) as excinfo:
        run_runtime_preflight(spec)

    message = str(excinfo.value)
    assert missing in message
    assert sys.executable in message


def test_existing_required_python_module_passes() -> None:
    spec = _Spec(RuntimeDependencySpec(required_python_modules=["sys"]))

    report = run_runtime_preflight(spec)

    assert report.passed is True


def test_problem_without_dependencies_keeps_noop_behavior() -> None:
    report = run_runtime_preflight(_Spec())

    assert report.passed is True


def test_adapter_owned_preflight_hook_can_fail_closed() -> None:
    class Adapter:
        def run_preflight_checks(self) -> list[str]:
            return ["adapter-owned check failed"]

    with pytest.raises(RuntimeDependencyPreflightError, match="adapter-owned"):
        run_runtime_preflight(_Spec(), adapter=Adapter())


def test_research_environment_preflight_checks_surface_and_verification(
    tmp_path,
) -> None:
    operators = tmp_path / "operators"
    operators.mkdir()
    (operators / "move.py").write_text("VALUE = 1\n", encoding="utf-8")
    spec = SimpleNamespace(
        root_dir=str(tmp_path),
        research_surfaces=[
            SimpleNamespace(
                name="moves",
                kind="operator",
                targets=SimpleNamespace(
                    files=["operators/*.py"],
                    create_new_allowed=True,
                    modify_allowed=True,
                    remove_allowed=False,
                ),
            )
        ],
    )

    class VerificationGate:
        calls = 0

        def run_preflight(self) -> None:
            self.calls += 1

    verification = VerificationGate()
    report = run_research_environment_preflight(
        spec,
        verification_gate=verification,
    )

    assert report.passed is True
    assert report.checks == (
        "runtime_dependencies",
        "research_surfaces",
        "verification_environment",
    )
    assert verification.calls == 1


def test_research_environment_preflight_rejects_unmaterialized_surface(
    tmp_path,
) -> None:
    spec = SimpleNamespace(
        root_dir=str(tmp_path),
        research_surfaces=[
            SimpleNamespace(
                name="missing",
                kind="operator",
                targets=SimpleNamespace(
                    files=["operators/*.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                ),
            )
        ],
    )

    with pytest.raises(
        ResearchEnvironmentPreflightError,
        match="no materialized target source",
    ):
        run_research_environment_preflight(spec)
