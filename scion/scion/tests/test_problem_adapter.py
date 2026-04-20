"""Tests for scion.problem — ProblemAdapter, ProblemSpecV1, comparator, loader."""
from __future__ import annotations

import json
import os
import random
import tempfile

import pytest
import yaml

from scion.problem.contracts import (
    CheckReport,
    LowerBoundEstimate,
    ProblemAdapter,
    SolverArtifact,
)
from scion.problem.loader import ProblemAdapterLoadError, load_problem_adapter
from scion.problem.objectives import (
    MetricComparison,
    ObjectiveComparison,
    compare_lexicographic,
)
from scion.problem.spec import (
    ObjectiveMetricSpec,
    ProblemAdapterRef,
    ProblemSpecV1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOY_TSP_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "problems", "toy_tsp"
)


def _load_toy_tsp_spec() -> ProblemSpecV1:
    yaml_path = os.path.join(TOY_TSP_DIR, "problem.yaml")
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    data["root_dir"] = os.path.abspath(TOY_TSP_DIR)
    return ProblemSpecV1(**data)


@pytest.fixture
def toy_spec() -> ProblemSpecV1:
    return _load_toy_tsp_spec()


@pytest.fixture
def toy_adapter(toy_spec: ProblemSpecV1) -> ProblemAdapter:
    return load_problem_adapter(toy_spec)


# ---------------------------------------------------------------------------
# ProblemSpecV1 schema validation
# ---------------------------------------------------------------------------


class TestProblemSpecV1:
    def test_valid_spec_loads(self, toy_spec: ProblemSpecV1) -> None:
        assert toy_spec.id == "toy_tsp"
        assert toy_spec.spec_version == "problem-v1"
        assert len(toy_spec.objectives) == 1
        assert toy_spec.objectives[0].name == "tour_cost"

    def test_extra_field_rejected(self) -> None:
        data = _minimal_spec_data()
        data["unknown_field"] = "bad"
        with pytest.raises(Exception):
            ProblemSpecV1(**data)

    def test_duplicate_objective_names_rejected(self) -> None:
        data = _minimal_spec_data()
        data["objectives"] = [
            {"name": "cost", "direction": "minimize", "priority": 1},
            {"name": "cost", "direction": "minimize", "priority": 2},
        ]
        with pytest.raises(ValueError, match="unique"):
            ProblemSpecV1(**data)

    def test_non_contiguous_priorities_rejected(self) -> None:
        data = _minimal_spec_data()
        data["objectives"] = [
            {"name": "a", "direction": "minimize", "priority": 1},
            {"name": "b", "direction": "minimize", "priority": 3},
        ]
        with pytest.raises(ValueError, match="contiguous"):
            ProblemSpecV1(**data)

    def test_adapter_path_prefix_enforced(self) -> None:
        data = _minimal_spec_data()
        data["adapter"]["import_path"] = "some.other.module:Adapter"
        with pytest.raises(ValueError, match="must start with"):
            ProblemSpecV1(**data)

    def test_valid_multi_objective(self) -> None:
        data = _minimal_spec_data()
        data["objectives"] = [
            {"name": "splits", "direction": "minimize", "priority": 1},
            {"name": "cost", "direction": "minimize", "priority": 2},
        ]
        spec = ProblemSpecV1(**data)
        assert len(spec.objectives) == 2
        assert spec.objectives[0].priority == 1


# ---------------------------------------------------------------------------
# Adapter loader
# ---------------------------------------------------------------------------


class TestAdapterLoader:
    def test_loads_toy_tsp(self, toy_spec: ProblemSpecV1) -> None:
        adapter = load_problem_adapter(toy_spec)
        assert isinstance(adapter, ProblemAdapter)

    def test_bad_module_path(self, toy_spec: ProblemSpecV1) -> None:
        toy_spec = toy_spec.model_copy(
            update={"adapter": ProblemAdapterRef(import_path="scion.problems.toy_tsp.nonexistent:Cls")}
        )
        with pytest.raises(ProblemAdapterLoadError, match="cannot import"):
            load_problem_adapter(toy_spec)

    def test_bad_class_name(self, toy_spec: ProblemSpecV1) -> None:
        toy_spec = toy_spec.model_copy(
            update={"adapter": ProblemAdapterRef(import_path="scion.problems.toy_tsp.adapter:NonexistentClass")}
        )
        with pytest.raises(ProblemAdapterLoadError, match="no attribute"):
            load_problem_adapter(toy_spec)

    def test_missing_colon_format(self, toy_spec: ProblemSpecV1) -> None:
        toy_spec = toy_spec.model_copy(
            update={"adapter": ProblemAdapterRef(import_path="scion.problems.toy_tsp.adapter.ToyTspAdapter")}
        )
        with pytest.raises(ProblemAdapterLoadError, match="module:Class"):
            load_problem_adapter(toy_spec)

    def test_path_outside_problems_rejected(self, toy_spec: ProblemSpecV1) -> None:
        toy_spec = toy_spec.model_copy(
            update={"adapter": ProblemAdapterRef(import_path="scion.core.models:Branch")}
        )
        with pytest.raises(ProblemAdapterLoadError, match="must start with"):
            load_problem_adapter(toy_spec)


# ---------------------------------------------------------------------------
# Generic objective comparator
# ---------------------------------------------------------------------------


class TestObjectiveComparator:
    SINGLE_METRIC = [
        ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
    ]
    MULTI_METRIC = [
        ObjectiveMetricSpec(name="splits", direction="minimize", priority=1),
        ObjectiveMetricSpec(name="cost", direction="minimize", priority=2),
    ]

    def test_win_single(self) -> None:
        r = compare_lexicographic(self.SINGLE_METRIC, {"cost": 10}, {"cost": 20})
        assert r.outcome == "win"
        assert r.decisive_metric == "cost"

    def test_loss_single(self) -> None:
        r = compare_lexicographic(self.SINGLE_METRIC, {"cost": 30}, {"cost": 20})
        assert r.outcome == "loss"

    def test_tie_single(self) -> None:
        r = compare_lexicographic(self.SINGLE_METRIC, {"cost": 20}, {"cost": 20})
        assert r.outcome == "tie"
        assert r.decisive_metric is None

    def test_win_primary_metric(self) -> None:
        r = compare_lexicographic(
            self.MULTI_METRIC,
            {"splits": 1, "cost": 999},
            {"splits": 3, "cost": 10},
        )
        assert r.outcome == "win"
        assert r.decisive_metric == "splits"

    def test_loss_primary_metric(self) -> None:
        r = compare_lexicographic(
            self.MULTI_METRIC,
            {"splits": 5, "cost": 1},
            {"splits": 2, "cost": 999},
        )
        assert r.outcome == "loss"
        assert r.decisive_metric == "splits"

    def test_tie_primary_win_secondary(self) -> None:
        r = compare_lexicographic(
            self.MULTI_METRIC,
            {"splits": 2, "cost": 10},
            {"splits": 2, "cost": 20},
        )
        assert r.outcome == "win"
        assert r.decisive_metric == "cost"

    def test_tie_all(self) -> None:
        r = compare_lexicographic(
            self.MULTI_METRIC,
            {"splits": 2, "cost": 20},
            {"splits": 2, "cost": 20},
        )
        assert r.outcome == "tie"

    def test_maximize_direction(self) -> None:
        specs = [
            ObjectiveMetricSpec(name="quality", direction="maximize", priority=1),
        ]
        r = compare_lexicographic(specs, {"quality": 90}, {"quality": 80})
        assert r.outcome == "win"

    def test_tie_tolerance(self) -> None:
        specs = [
            ObjectiveMetricSpec(
                name="cost", direction="minimize", priority=1, tie_tolerance=1.0
            ),
        ]
        r = compare_lexicographic(specs, {"cost": 10.5}, {"cost": 10.0})
        assert r.outcome == "tie"

        r2 = compare_lexicographic(specs, {"cost": 12.0}, {"cost": 10.0})
        assert r2.outcome == "loss"

    def test_metric_breakdown_structure(self) -> None:
        r = compare_lexicographic(
            self.MULTI_METRIC,
            {"splits": 2, "cost": 15},
            {"splits": 3, "cost": 10},
        )
        assert len(r.metrics) == 2
        splits_mc = r.metrics[0]
        assert splits_mc.name == "splits"
        assert splits_mc.decisive is True
        assert splits_mc.relation == "candidate"

        cost_mc = r.metrics[1]
        assert cost_mc.name == "cost"
        assert cost_mc.decisive is False

    def test_consistency_with_warehouse_semantics(self) -> None:
        """Verify the generic comparator produces the same results as the
        hardcoded warehouse lexicographic_compare for the warehouse metric set."""
        warehouse_specs = [
            ObjectiveMetricSpec(
                name="subcategory_splits", direction="minimize", priority=1
            ),
            ObjectiveMetricSpec(
                name="total_cost", direction="minimize", priority=2
            ),
        ]
        from scion.protocol.evaluation import lexicographic_compare as legacy

        cases = [
            ({"subcategory_splits": 2, "total_cost": 100}, {"subcategory_splits": 3, "total_cost": 50}),
            ({"subcategory_splits": 3, "total_cost": 50}, {"subcategory_splits": 2, "total_cost": 100}),
            ({"subcategory_splits": 2, "total_cost": 80}, {"subcategory_splits": 2, "total_cost": 100}),
            ({"subcategory_splits": 2, "total_cost": 100}, {"subcategory_splits": 2, "total_cost": 80}),
            ({"subcategory_splits": 2, "total_cost": 100}, {"subcategory_splits": 2, "total_cost": 100}),
        ]
        for cand, champ in cases:
            legacy_result = legacy(cand, champ)
            generic_result = compare_lexicographic(warehouse_specs, cand, champ)
            assert generic_result.outcome == legacy_result, (
                f"Mismatch for cand={cand}, champ={champ}: "
                f"legacy={legacy_result}, generic={generic_result.outcome}"
            )


# ---------------------------------------------------------------------------
# toy_tsp adapter integration
# ---------------------------------------------------------------------------


class TestToyTspAdapter:
    def test_render_problem_summary(self, toy_adapter: ProblemAdapter) -> None:
        s = toy_adapter.render_problem_summary()
        assert isinstance(s, str)
        assert len(s) > 10

    def test_render_operator_interface(self, toy_adapter: ProblemAdapter) -> None:
        s = toy_adapter.render_operator_interface()
        assert "execute" in s

    def test_load_instance(self, toy_adapter: ProblemAdapter, toy_spec: ProblemSpecV1) -> None:
        path = os.path.join(toy_spec.root_dir, "data", "tsp_10.json")
        inst = toy_adapter.load_instance(path)
        assert inst.n == 10

    def test_full_pipeline(self, toy_adapter: ProblemAdapter, toy_spec: ProblemSpecV1) -> None:
        path = os.path.join(toy_spec.root_dir, "data", "tsp_10.json")
        inst = toy_adapter.load_instance(path)

        from scion.problems.toy_tsp.solver import solve

        rng = random.Random(42)
        sol = solve(inst, rng)
        raw = {"tour": list(sol.tour)}

        artifact = toy_adapter.deserialize_solver_output(raw, inst)
        assert artifact.feasible is True
        assert "tour_cost" in artifact.objective

        consistency = toy_adapter.check_solution_consistency(artifact, inst)
        assert consistency.passed is True

        feasibility = toy_adapter.check_feasibility(artifact, inst)
        assert feasibility.passed is True

        obj = toy_adapter.recompute_objective(artifact, inst)
        assert abs(obj["tour_cost"] - artifact.objective["tour_cost"]) < 1e-6

    def test_infeasible_tour(self, toy_adapter: ProblemAdapter, toy_spec: ProblemSpecV1) -> None:
        path = os.path.join(toy_spec.root_dir, "data", "tsp_10.json")
        inst = toy_adapter.load_instance(path)

        raw = {"tour": [0, 1, 2]}  # too short
        artifact = toy_adapter.deserialize_solver_output(raw, inst)
        assert artifact.feasible is False

        feas = toy_adapter.check_feasibility(artifact, inst)
        assert feas.passed is False
        assert len(feas.reasons) > 0

    def test_estimate_lower_bound_returns_none(
        self, toy_adapter: ProblemAdapter, toy_spec: ProblemSpecV1
    ) -> None:
        path = os.path.join(toy_spec.root_dir, "data", "tsp_10.json")
        lb = toy_adapter.estimate_lower_bound("tour_cost", [path])
        assert lb is None

    def test_20_point_instance(self, toy_adapter: ProblemAdapter, toy_spec: ProblemSpecV1) -> None:
        path = os.path.join(toy_spec.root_dir, "data", "tsp_20.json")
        inst = toy_adapter.load_instance(path)
        assert inst.n == 20

        from scion.problems.toy_tsp.solver import solve

        rng = random.Random(99)
        sol = solve(inst, rng)
        raw = {"tour": list(sol.tour)}
        artifact = toy_adapter.deserialize_solver_output(raw, inst)
        assert artifact.feasible is True


# ---------------------------------------------------------------------------
# Data type tests
# ---------------------------------------------------------------------------


class TestDataTypes:
    def test_check_report_immutable(self) -> None:
        cr = CheckReport(passed=True)
        with pytest.raises(AttributeError):
            cr.passed = False  # type: ignore[misc]

    def test_solver_artifact_immutable(self) -> None:
        sa = SolverArtifact(raw_output={}, objective={"x": 1}, feasible=True)
        with pytest.raises(AttributeError):
            sa.feasible = False  # type: ignore[misc]

    def test_lower_bound_estimate(self) -> None:
        lb = LowerBoundEstimate(
            metric_name="cost", value=42.0, kind="exact", note="MILP optimal"
        )
        assert lb.kind == "exact"

    def test_metric_comparison_immutable(self) -> None:
        mc = MetricComparison(
            name="cost",
            candidate_value=10,
            champion_value=20,
            signed_delta=10.0,
            relation="candidate",
        )
        with pytest.raises(AttributeError):
            mc.decisive = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_spec_data() -> dict:
    return {
        "id": "toy_tsp",
        "display_name": "Toy TSP",
        "root_dir": "/tmp/toy",
        "search_space": {
            "editable": ["operators/*.py"],
            "frozen": ["solver.py"],
            "import_whitelist": ["math"],
        },
        "operator_interface": {
            "base_class_import": "scion.problems.toy_tsp.operators.two_opt:TwoOptOperator",
            "categories": [{"name": "local_search"}],
        },
        "objectives": [
            {"name": "tour_cost", "direction": "minimize", "priority": 1},
        ],
        "adapter": {
            "import_path": "scion.problems.toy_tsp.adapter:ToyTspAdapter",
        },
    }
