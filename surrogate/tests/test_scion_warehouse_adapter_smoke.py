"""Surrogate warehouse solver smoke through Scion's warehouse adapter.

This test belongs to the surrogate test surface because it runs the real
warehouse surrogate solver subprocess. Scion's default tests should cover the
adapter contract without executing the surrogate solver.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from scion.problem.loader import load_problem_adapter
from scion.problem.objectives import compare_lexicographic
from scion.problem.spec import ProblemSpecV1


REPO_ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE_YAML = REPO_ROOT / "scion" / "problems" / "warehouse_delivery" / "problem-v1.yaml"


class TestWarehouseSyntheticSmoke:
    """End-to-end: load warehouse adapter -> solve -> verify via adapter."""

    @pytest.fixture
    def spec(self) -> ProblemSpecV1:
        with open(WAREHOUSE_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ProblemSpecV1(**data)

    @pytest.fixture
    def adapter(self, spec):
        return load_problem_adapter(spec)

    def test_canary_full_pipeline(self, adapter, spec: ProblemSpecV1) -> None:
        canary = spec.canary_case_path
        if not canary or not os.path.isfile(canary):
            pytest.skip("canary instance not available")

        instance = adapter.load_instance(canary)
        assert len(instance.orders) > 0

        solver_path = os.path.join(spec.root_dir, spec.solver_path)
        out_fd, out_path = tempfile.mkstemp(suffix=".json")
        os.close(out_fd)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    solver_path,
                    canary,
                    "--seed",
                    "42",
                    "--time-limit",
                    "30",
                    "--output",
                    out_path,
                ],
                cwd=spec.root_dir,
                capture_output=True,
                timeout=60,
                env={**os.environ, "PYTHONHASHSEED": "0"},
                check=False,
            )
            assert result.returncode == 0, f"solver failed: {result.stderr.decode()[:300]}"

            with open(out_path, encoding="utf-8") as f:
                raw = json.load(f)
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

        artifact = adapter.deserialize_solver_output(raw, instance)
        assert artifact.feasible

        consistency = adapter.check_solution_consistency(artifact, instance)
        assert consistency.passed, f"consistency: {consistency.reasons}"

        feasibility = adapter.check_feasibility(artifact, instance)
        assert feasibility.passed, f"feasibility: {feasibility.reasons}"

        recomputed = adapter.recompute_objective(artifact, instance)
        for key in artifact.objective:
            assert key in recomputed, f"missing key {key} in recomputed"
            assert recomputed[key] == artifact.objective[key], (
                f"{key}: solver={artifact.objective[key]}, recomputed={recomputed[key]}"
            )

        cmp = compare_lexicographic(
            spec.objectives,
            dict(artifact.objective),
            dict(artifact.objective),
        )
        assert cmp.outcome == "tie"

    def test_lower_bound_graceful_when_missing(self, adapter, spec: ProblemSpecV1) -> None:
        canary = spec.canary_case_path
        if not canary:
            pytest.skip("no canary")
        lb = adapter.estimate_lower_bound("total_cost", [canary])
        assert lb is None

