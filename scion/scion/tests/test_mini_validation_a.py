"""Mini-Validation A: smoke tests proving adapter + scoring + MILP anchor don't break the system."""
from __future__ import annotations

import os
import random
import yaml
import pytest

from scion.problem.spec import ProblemSpecV1
from scion.problem.loader import load_problem_adapter
from scion.problem.contracts import ProblemAdapter
from scion.problem.objectives import compare_lexicographic


WAREHOUSE_YAML = os.path.join(
    os.path.dirname(__file__), os.pardir, "problems", "warehouse_delivery", "problem-v1.yaml"
)
TOY_TSP_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "problems", "toy_tsp"
)
TOY_TSP_YAML = os.path.join(TOY_TSP_DIR, "problem.yaml")


# ---------------------------------------------------------------------------
# Warehouse synthetic smoke
# ---------------------------------------------------------------------------

class TestWarehouseSyntheticSmoke:
    """End-to-end: load warehouse adapter → load instance → solve → verify via adapter."""

    @pytest.fixture
    def spec(self) -> ProblemSpecV1:
        with open(WAREHOUSE_YAML) as f:
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

        # Run the actual solver to get a real output
        import subprocess, sys, json, tempfile
        solver_path = os.path.join(spec.root_dir, spec.solver_path)
        out_fd, out_path = tempfile.mkstemp(suffix=".json")
        os.close(out_fd)
        try:
            result = subprocess.run(
                [sys.executable, solver_path, canary,
                 "--seed", "42", "--time-limit", "30", "--output", out_path],
                cwd=spec.root_dir,
                capture_output=True, timeout=60,
                env={**os.environ, "PYTHONHASHSEED": "0"},
            )
            assert result.returncode == 0, f"solver failed: {result.stderr.decode()[:300]}"

            with open(out_path) as f:
                raw = json.load(f)
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

        # Deserialize through adapter
        artifact = adapter.deserialize_solver_output(raw, instance)
        assert artifact.feasible

        # Consistency check
        consistency = adapter.check_solution_consistency(artifact, instance)
        assert consistency.passed, f"consistency: {consistency.reasons}"

        # Feasibility check
        feasibility = adapter.check_feasibility(artifact, instance)
        assert feasibility.passed, f"feasibility: {feasibility.reasons}"

        # Objective recomputation
        recomputed = adapter.recompute_objective(artifact, instance)
        for key in artifact.objective:
            assert key in recomputed, f"missing key {key} in recomputed"
            assert recomputed[key] == artifact.objective[key], (
                f"{key}: solver={artifact.objective[key]}, recomputed={recomputed[key]}"
            )

        # Generic comparator with warehouse metrics
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
        # No milp_bounds dir → None (graceful)
        assert lb is None


# ---------------------------------------------------------------------------
# toy_tsp smoke
# ---------------------------------------------------------------------------

class TestToyTspSmoke:
    """End-to-end: load toy_tsp adapter → load instance → solve → verify."""

    @pytest.fixture
    def spec(self) -> ProblemSpecV1:
        with open(TOY_TSP_YAML) as f:
            data = yaml.safe_load(f)
        data["root_dir"] = os.path.abspath(TOY_TSP_DIR)
        return ProblemSpecV1(**data)

    @pytest.fixture
    def adapter(self, spec):
        return load_problem_adapter(spec)

    def test_full_pipeline_10(self, adapter, spec: ProblemSpecV1) -> None:
        path = os.path.join(spec.root_dir, "data", "tsp_10.json")
        instance = adapter.load_instance(path)

        from scion.problems.toy_tsp.solver import solve
        sol = solve(instance, random.Random(42))
        raw = {"tour": list(sol.tour)}

        artifact = adapter.deserialize_solver_output(raw, instance)
        assert artifact.feasible

        consistency = adapter.check_solution_consistency(artifact, instance)
        assert consistency.passed

        feasibility = adapter.check_feasibility(artifact, instance)
        assert feasibility.passed

        recomputed = adapter.recompute_objective(artifact, instance)
        assert abs(recomputed["tour_cost"] - artifact.objective["tour_cost"]) < 1e-6

        cmp = compare_lexicographic(
            spec.objectives,
            dict(artifact.objective),
            dict(artifact.objective),
        )
        assert cmp.outcome == "tie"

    def test_full_pipeline_20(self, adapter, spec: ProblemSpecV1) -> None:
        path = os.path.join(spec.root_dir, "data", "tsp_20.json")
        instance = adapter.load_instance(path)

        from scion.problems.toy_tsp.solver import solve
        sol = solve(instance, random.Random(99))
        raw = {"tour": list(sol.tour)}

        artifact = adapter.deserialize_solver_output(raw, instance)
        assert artifact.feasible

        recomputed = adapter.recompute_objective(artifact, instance)
        assert abs(recomputed["tour_cost"] - artifact.objective["tour_cost"]) < 1e-6

    def test_cross_problem_comparator(self, spec: ProblemSpecV1) -> None:
        """Prove generic comparator works identically for both problems."""
        r = compare_lexicographic(
            spec.objectives,
            {"tour_cost": 10.0},
            {"tour_cost": 15.0},
        )
        assert r.outcome == "win"
        assert r.decisive_metric == "tour_cost"
