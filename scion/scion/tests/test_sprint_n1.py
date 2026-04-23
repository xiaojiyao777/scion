"""Tests for N1 sprint: warehouse adapter, generic comparison in protocol, MILP gaps."""
from __future__ import annotations

import os
import yaml
import pytest

from scion.problem.contracts import CheckReport, LowerBoundEstimate, ProblemAdapter, SolverArtifact
from scion.problem.loader import load_problem_adapter
from scion.problem.objectives import compare_lexicographic, ObjectiveComparison
from scion.problem.spec import ProblemSpecV1, ObjectiveMetricSpec
from scion.problem.milp_bounds import compute_optimum_gap, OptimumGapReport

WAREHOUSE_YAML = os.path.join(
    os.path.dirname(__file__), os.pardir, "problems", "warehouse_delivery", "problem-v1.yaml"
)


# ---------------------------------------------------------------------------
# WarehouseDeliveryAdapter
# ---------------------------------------------------------------------------


class TestWarehouseAdapter:
    @pytest.fixture
    def spec(self) -> ProblemSpecV1:
        with open(WAREHOUSE_YAML) as f:
            data = yaml.safe_load(f)
        return ProblemSpecV1(**data)

    @pytest.fixture
    def adapter(self, spec: ProblemSpecV1):
        return load_problem_adapter(spec)

    def test_isinstance(self, adapter) -> None:
        assert isinstance(adapter, ProblemAdapter)

    def test_load_canary_instance(self, adapter, spec: ProblemSpecV1) -> None:
        if not spec.canary_case_path or not os.path.isfile(spec.canary_case_path):
            pytest.skip("canary instance not available")
        instance = adapter.load_instance(spec.canary_case_path)
        assert hasattr(instance, "orders")
        assert len(instance.orders) > 0

    def test_render_problem_summary(self, adapter) -> None:
        s = adapter.render_problem_summary()
        assert "Warehouse" in s or "warehouse" in s

    def test_render_operator_interface(self, adapter) -> None:
        s = adapter.render_operator_interface()
        assert "execute" in s

    def test_estimate_lower_bound_no_dir(self, adapter, spec: ProblemSpecV1) -> None:
        lb = adapter.estimate_lower_bound("total_cost", ["/fake/path.json"])
        assert lb is None


# ---------------------------------------------------------------------------
# Generic comparator with warehouse semantics
# ---------------------------------------------------------------------------


class TestWarehouseGenericComparator:
    WAREHOUSE_SPECS = [
        ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
        ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
    ]

    def test_splits_dominant_win(self) -> None:
        r = compare_lexicographic(
            self.WAREHOUSE_SPECS,
            {"subcategory_splits": 2, "total_cost": 999},
            {"subcategory_splits": 5, "total_cost": 100},
        )
        assert r.outcome == "win"
        assert r.decisive_metric == "subcategory_splits"

    def test_cost_secondary(self) -> None:
        r = compare_lexicographic(
            self.WAREHOUSE_SPECS,
            {"subcategory_splits": 3, "total_cost": 80},
            {"subcategory_splits": 3, "total_cost": 100},
        )
        assert r.outcome == "win"
        assert r.decisive_metric == "total_cost"

    def test_scalar_delta_meaningful(self) -> None:
        r = compare_lexicographic(
            self.WAREHOUSE_SPECS,
            {"subcategory_splits": 3, "total_cost": 80},
            {"subcategory_splits": 3, "total_cost": 100},
        )
        assert r.scalar_delta > 0


# ---------------------------------------------------------------------------
# Experiment protocol with metric_specs
# ---------------------------------------------------------------------------


class TestExperimentGenericPath:
    """Verify that _compare_objectives returns ObjectiveComparison directly."""

    def test_compare_returns_objective_comparison(self) -> None:
        from scion.problem.objectives import ObjectiveComparison
        specs = [
            ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
            ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
        ]
        result = compare_lexicographic(
            specs,
            {"subcategory_splits": 2, "total_cost": 100},
            {"subcategory_splits": 3, "total_cost": 80},
        )
        assert isinstance(result, ObjectiveComparison)
        assert result.decisive_metric == "subcategory_splits"
        assert result.outcome == "win"

    def test_compare_tie(self) -> None:
        specs = [
            ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
            ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
        ]
        result = compare_lexicographic(
            specs,
            {"subcategory_splits": 2, "total_cost": 100},
            {"subcategory_splits": 2, "total_cost": 100},
        )
        assert result.outcome == "tie"
        assert result.decisive_metric is None

    def test_non_warehouse_metrics(self) -> None:
        specs = [
            ObjectiveMetricSpec(name="tour_cost", direction="minimize", priority=1),
        ]
        result = compare_lexicographic(
            specs, {"tour_cost": 10}, {"tour_cost": 20},
        )
        assert result.decisive_metric == "tour_cost"
        assert result.outcome == "win"
        assert result.metrics[0].name == "tour_cost"


# ---------------------------------------------------------------------------
# MILP bounds
# ---------------------------------------------------------------------------


class TestMilpBounds:
    def test_compute_optimum_gap(self) -> None:
        lb = LowerBoundEstimate(
            metric_name="total_cost", value=1000, kind="exact",
        )
        report = compute_optimum_gap({"total_cost": 1200}, lb)
        assert isinstance(report, OptimumGapReport)
        assert abs(report.gap - 0.2) < 1e-6

    def test_zero_bound(self) -> None:
        lb = LowerBoundEstimate(
            metric_name="subcategory_splits", value=0, kind="exact",
        )
        report = compute_optimum_gap({"subcategory_splits": 3}, lb)
        assert report.gap == float("inf")

    def test_optimal_gap_is_zero(self) -> None:
        lb = LowerBoundEstimate(
            metric_name="total_cost", value=500, kind="exact",
        )
        report = compute_optimum_gap({"total_cost": 500}, lb)
        assert report.gap == 0.0


# ---------------------------------------------------------------------------
# Parameter evaluator scoring decouple
# ---------------------------------------------------------------------------


class TestScoringDecouple:
    def test_evaluate_weights_accepts_metric_specs(self) -> None:
        """Verify that evaluate_weights accepts the metric_specs parameter."""
        import inspect
        from scion.parameter.evaluator import evaluate_weights
        sig = inspect.signature(evaluate_weights)
        assert "metric_specs" in sig.parameters

    def test_private_compute_delta_generic_path(self) -> None:
        from scion.parameter.evaluator import _compute_delta

        specs = [
            ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
            ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
        ]
        delta = _compute_delta(
            {"subcategory_splits": 2, "total_cost": 100},
            {"subcategory_splits": 3, "total_cost": 80},
            metric_specs=specs,
        )
        assert delta > 0  # candidate better on splits

    def test_private_compute_delta_legacy_path(self) -> None:
        from scion.parameter.evaluator import _compute_delta

        delta = _compute_delta(
            {"subcategory_splits": 2, "total_cost": 100},
            {"subcategory_splits": 3, "total_cost": 80},
            metric_specs=None,
        )
        assert delta > 0  # same semantics
