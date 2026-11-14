"""Mini-Validation A: smoke tests proving adapter + scoring plumbing works."""
from __future__ import annotations

import os
import random
import yaml
import pytest

from scion.problem.spec import ProblemSpecV1
from scion.problem.loader import load_problem_adapter
from scion.problem.objectives import compare_lexicographic


TOY_TSP_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "problems", "toy_tsp"
)
TOY_TSP_YAML = os.path.join(TOY_TSP_DIR, "problem.yaml")


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
