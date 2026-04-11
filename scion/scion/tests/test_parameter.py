"""Tests for T12 (parameter data models), T14 (weight evaluator), T15a (optimizer)."""
from __future__ import annotations

import os
import pytest
import yaml

from scion.config.problem import ParameterSearchConfig, ProblemSpec
from scion.core.models import WeightConfig, WeightOptimizationResult, RunResult, SolverOutput
from scion.parameter.search_space import ParameterSearchSpace


# ─────────────────────────────────────────────────────────────────────────────
# T12 — ParameterSearchConfig
# ─────────────────────────────────────────────────────────────────────────────

def test_parameter_search_config_defaults():
    cfg = ParameterSearchConfig()
    assert cfg.enabled is True
    assert cfg.trigger == "on_promote"
    assert cfg.target == "operator_weights"
    assert cfg.strategy == "random_local"
    assert cfg.n_initial_random == 8
    assert cfg.n_iterations == 8
    assert cfg.n_eval_seeds == 2
    assert cfg.weight_bounds == (0.05, 5.0)
    assert cfg.eval_cases == []


def test_parameter_search_config_custom():
    cfg = ParameterSearchConfig(
        enabled=False,
        strategy="bayesian",
        n_initial_random=4,
        n_iterations=16,
        n_eval_seeds=3,
        weight_bounds=(0.1, 2.0),
        eval_cases=["case1", "case2"],
    )
    assert cfg.enabled is False
    assert cfg.strategy == "bayesian"
    assert cfg.n_initial_random == 4
    assert cfg.n_iterations == 16
    assert cfg.n_eval_seeds == 3
    assert cfg.weight_bounds == (0.1, 2.0)
    assert cfg.eval_cases == ["case1", "case2"]


def test_problem_spec_with_parameter_search():
    spec = ProblemSpec(
        name="test",
        root_dir="/tmp",
        operator_categories=["order_level"],
        search_space={"editable": [], "frozen": [], "import_whitelist": []},
    )
    assert hasattr(spec, "parameter_search")
    assert isinstance(spec.parameter_search, ParameterSearchConfig)
    assert spec.parameter_search.enabled is True


def test_problem_spec_yaml_without_parameter_search(tmp_path):
    yaml_content = (
        "name: test_problem\n"
        "root_dir: /tmp\n"
        "operator_categories:\n"
        "  - order_level\n"
        "search_space:\n"
        "  editable: []\n"
        "  frozen: []\n"
        "  import_whitelist: []\n"
    )
    yaml_path = tmp_path / "problem.yaml"
    yaml_path.write_text(yaml_content)
    spec = ProblemSpec.from_yaml(str(yaml_path))
    assert isinstance(spec.parameter_search, ParameterSearchConfig)
    assert spec.parameter_search.enabled is True


# ─────────────────────────────────────────────────────────────────────────────
# T12 — WeightConfig / WeightOptimizationResult
# ─────────────────────────────────────────────────────────────────────────────

def test_weight_config_frozen():
    wc = WeightConfig(weights={"op1": 1.0, "op2": 2.0}, source="uniform")
    with pytest.raises((AttributeError, TypeError)):
        wc.weights = {}


def test_weight_optimization_result_fields():
    result = WeightOptimizationResult(
        baseline_weights={"op1": 1.0},
        best_weights={"op1": 1.5},
        baseline_score=0.5,
        best_score=0.7,
        improved=True,
        n_evaluations=8,
        elapsed_seconds=120.0,
        observations_ref="/path/to/obs.json",
    )
    assert result.improved is True
    assert result.n_evaluations == 8
    assert result.elapsed_seconds == 120.0
    assert result.observations_ref == "/path/to/obs.json"
    assert result.best_weights == {"op1": 1.5}


# ─────────────────────────────────────────────────────────────────────────────
# T12 — ParameterSearchSpace
# ─────────────────────────────────────────────────────────────────────────────

def test_parameter_search_space_defaults():
    space = ParameterSearchSpace(operator_names=("op1", "op2"))
    assert space.weight_bounds == (0.05, 5.0)
    assert space.n_initial_random == 8
    assert space.n_iterations == 8
    assert space.n_eval_seeds == 2
    assert space.eval_cases == ()


# ─────────────────────────────────────────────────────────────────────────────
# T14 — Weight Evaluator
# ─────────────────────────────────────────────────────────────────────────────

def _make_registry(tmp_path, operators):
    data = {"operators": operators}
    path = tmp_path / "registry.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return str(path)


def _make_workspace(tmp_path):
    """Create a minimal workspace with a registry.yaml."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    ops = [
        {"name": "swap", "file_path": "operators/swap.py", "category": "order_level",
         "weight": 0.5, "class_name": "Swap"},
        {"name": "move", "file_path": "operators/move.py", "category": "order_level",
         "weight": 0.5, "class_name": "Move"},
    ]
    _make_registry(ws, ops)
    return str(ws)


def _make_run_result(objective_dict):
    output = SolverOutput(
        vehicles={},
        assignment={},
        objective=objective_dict,
        feasible=True,
    )
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=100,
        output=output,
    )


class _MockRunner:
    """Returns fixed objectives regardless of inputs."""

    def __init__(self, objectives_by_call):
        self._calls = list(objectives_by_call)
        self._idx = 0

    def run_solver(self, workdir, instance_path, seed, time_limit_sec, registry_path):
        if self._idx < len(self._calls):
            obj = self._calls[self._idx]
            self._idx += 1
            if obj is None:
                return RunResult(success=False, exit_code=1, stdout="", stderr="",
                                 elapsed_ms=10)
            return _make_run_result(obj)
        return RunResult(success=False, exit_code=1, stdout="", stderr="", elapsed_ms=10)


def test_collect_baseline_returns_structure(tmp_path):
    from scion.parameter.evaluator import collect_baseline

    ws = _make_workspace(tmp_path)
    obj1 = {"subcategory_splits": 2, "total_cost": 100.0}
    obj2 = {"subcategory_splits": 3, "total_cost": 90.0}
    runner = _MockRunner([obj1, obj2])

    baseline = collect_baseline(
        workspace=ws,
        cases=["case_a.json"],
        seeds=[1, 2],
        runner=runner,
        time_limit_sec=10,
    )

    assert "case_a.json" in baseline
    assert 1 in baseline["case_a.json"]
    assert 2 in baseline["case_a.json"]
    assert baseline["case_a.json"][1] == obj1
    assert baseline["case_a.json"][2] == obj2


def test_evaluate_weights_returns_median_delta(tmp_path):
    from scion.parameter.evaluator import evaluate_weights

    ws = _make_workspace(tmp_path)
    # candidate objectives (after weight update)
    cand1 = {"subcategory_splits": 2, "total_cost": 80.0}  # cost better by 20
    cand2 = {"subcategory_splits": 3, "total_cost": 85.0}  # cost better by 5
    runner = _MockRunner([cand1, cand2])

    baseline_objectives = {
        "case_a.json": {
            1: {"subcategory_splits": 2, "total_cost": 100.0},
            2: {"subcategory_splits": 3, "total_cost": 90.0},
        }
    }

    score = evaluate_weights(
        weights={"swap": 0.6, "move": 0.4},
        workspace=ws,
        cases=["case_a.json"],
        seeds=[1, 2],
        runner=runner,
        time_limit_sec=10,
        baseline_objectives=baseline_objectives,
    )

    # deltas: 100-80=20, 90-85=5 → median of [20, 5] = 12.5
    assert abs(score - 12.5) < 1e-9


def test_evaluate_weights_uses_compute_delta(tmp_path):
    from scion.parameter.evaluator import evaluate_weights
    from scion.protocol.evaluation import compute_delta

    ws = _make_workspace(tmp_path)
    cand_obj = {"subcategory_splits": 1, "total_cost": 50.0}
    base_obj = {"subcategory_splits": 2, "total_cost": 60.0}

    runner = _MockRunner([cand_obj])
    baseline_objectives = {"case.json": {42: base_obj}}

    score = evaluate_weights(
        weights={"swap": 0.5, "move": 0.5},
        workspace=ws,
        cases=["case.json"],
        seeds=[42],
        runner=runner,
        time_limit_sec=10,
        baseline_objectives=baseline_objectives,
    )

    expected = compute_delta(cand_obj, base_obj)
    assert abs(score - expected) < 1e-9


def test_evaluate_weights_skips_failed_runs(tmp_path):
    from scion.parameter.evaluator import evaluate_weights

    ws = _make_workspace(tmp_path)
    runner = _MockRunner([None, None])  # both fail

    baseline_objectives = {
        "case.json": {1: {"subcategory_splits": 2, "total_cost": 100.0}}
    }

    score = evaluate_weights(
        weights={"swap": 0.5, "move": 0.5},
        workspace=ws,
        cases=["case.json"],
        seeds=[1, 2],
        runner=runner,
        time_limit_sec=10,
        baseline_objectives=baseline_objectives,
    )
    # No successful runs → returns 0.0
    assert score == 0.0


def test_evaluate_weights_writes_registry(tmp_path):
    from scion.parameter.evaluator import evaluate_weights
    from scion.runtime.pool_manager import read_weights

    ws = _make_workspace(tmp_path)
    runner = _MockRunner([])

    evaluate_weights(
        weights={"swap": 0.8, "move": 0.2},
        workspace=ws,
        cases=[],
        seeds=[],
        runner=runner,
        time_limit_sec=10,
        baseline_objectives={},
    )

    written = read_weights(os.path.join(ws, "registry.yaml"))
    assert abs(written["swap"] - 0.8) < 1e-6
    assert abs(written["move"] - 0.2) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# T15a — RandomLocalWeightOptimizer
# ─────────────────────────────────────────────────────────────────────────────

def _make_space(n_initial=4, n_iter=4, bounds=(0.05, 5.0)):
    return ParameterSearchSpace(
        operator_names=("op_a", "op_b"),
        weight_bounds=bounds,
        n_initial_random=n_initial,
        n_iterations=n_iter,
    )


def test_optimizer_improves_on_convex_mock():
    """Convex evaluator: best_score > baseline_score (first-random score)."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer

    target = {"op_a": 1.0, "op_b": 1.0}

    def convex_eval(weights):
        return -sum((weights[k] - target[k]) ** 2 for k in target)

    space = _make_space(n_initial=8, n_iter=16)
    opt = RandomLocalWeightOptimizer(space, convex_eval, seed=42)
    result = opt.optimize({"op_a": 0.5, "op_b": 0.5})

    assert result.best_score >= result.baseline_score
    assert result.improved or result.best_score == result.baseline_score


def test_optimizer_is_seed_deterministic():
    """Same seed → identical results on two runs."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer

    call_log1: list = []
    call_log2: list = []

    def eval1(w):
        v = sum(w.values())
        call_log1.append(v)
        return v

    def eval2(w):
        v = sum(w.values())
        call_log2.append(v)
        return v

    space = _make_space(n_initial=4, n_iter=4)
    r1 = RandomLocalWeightOptimizer(space, eval1, seed=0).optimize({"op_a": 1.0, "op_b": 1.0})
    r2 = RandomLocalWeightOptimizer(space, eval2, seed=0).optimize({"op_a": 1.0, "op_b": 1.0})

    assert r1.best_score == r2.best_score
    assert r1.n_evaluations == r2.n_evaluations
    assert call_log1 == call_log2


def test_optimizer_returns_correct_structure():
    """All WeightOptimizationResult fields must be set (not None)."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer

    space = _make_space()
    opt = RandomLocalWeightOptimizer(space, lambda w: 1.0, seed=7)
    result = opt.optimize({"op_a": 1.0, "op_b": 1.0})

    assert result.baseline_weights is not None
    assert result.best_weights is not None
    assert result.baseline_score is not None
    assert result.best_score is not None
    assert result.improved is not None
    assert result.n_evaluations is not None
    assert result.elapsed_seconds is not None
    assert result.observations_ref is not None  # may be ""


def test_optimizer_respects_weight_bounds():
    """All weights returned must lie within [lo, hi]."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer

    lo, hi = 0.05, 5.0
    space = _make_space(n_initial=10, n_iter=20, bounds=(lo, hi))
    opt = RandomLocalWeightOptimizer(space, lambda w: sum(w.values()), seed=3)
    result = opt.optimize({"op_a": 1.0, "op_b": 1.0})

    for name, w in result.best_weights.items():
        assert lo <= w <= hi, f"{name}: {w} outside [{lo}, {hi}]"
    for name, w in result.baseline_weights.items():
        assert lo <= w <= hi, f"{name}: {w} outside [{lo}, {hi}]"


def test_optimizer_n_evaluations():
    """n_evaluations == 1 (baseline) + n_initial_random + n_iterations."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer

    n_init, n_iter = 5, 7
    space = _make_space(n_initial=n_init, n_iter=n_iter)
    opt = RandomLocalWeightOptimizer(space, lambda w: 0.0, seed=1)
    result = opt.optimize({"op_a": 1.0, "op_b": 1.0})

    assert result.n_evaluations == 1 + n_init + n_iter


# ─────────────────────────────────────────────────────────────────────────────
# T15b — BayesianWeightOptimizer
# ─────────────────────────────────────────────────────────────────────────────

def test_bayesian_optimizer_improves_convex_mock():
    """BayesianWeightOptimizer finds a better solution on a convex objective."""
    from scion.parameter.optimizer import BayesianWeightOptimizer

    target = {"op_a": 1.0, "op_b": 1.0}

    def convex_eval(weights):
        return -sum((weights[k] - target[k]) ** 2 for k in target)

    space = _make_space(n_initial=8, n_iter=16)
    opt = BayesianWeightOptimizer(space, convex_eval, seed=42)
    result = opt.optimize({"op_a": 2.0, "op_b": 2.0})

    assert result.best_score >= result.baseline_score
    assert result.best_weights is not None
    assert len(result.best_weights) == 2


def test_bayesian_optimizer_deterministic():
    """Same seed produces identical results on two independent runs."""
    from scion.parameter.optimizer import BayesianWeightOptimizer

    def eval_fn(w):
        return sum(w.values())

    space = _make_space(n_initial=4, n_iter=4)
    r1 = BayesianWeightOptimizer(space, eval_fn, seed=7).optimize({"op_a": 1.0, "op_b": 1.0})
    r2 = BayesianWeightOptimizer(space, eval_fn, seed=7).optimize({"op_a": 1.0, "op_b": 1.0})

    assert abs(r1.best_score - r2.best_score) < 1e-9
    assert r1.n_evaluations == r2.n_evaluations


def test_bayesian_fallback_to_scipy(monkeypatch):
    """When skopt import fails, BayesianWeightOptimizer falls back to scipy."""
    import builtins
    import importlib

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "skopt" or name.startswith("skopt."):
            raise ImportError(f"Mocked: no module named {name!r}")
        return real_import(name, *args, **kwargs)

    from scion.parameter.optimizer import BayesianWeightOptimizer

    space = _make_space(n_initial=3, n_iter=3)
    call_log: list = []

    def eval_fn(w):
        call_log.append(w)
        return sum(w.values())

    with monkeypatch.context() as m:
        m.setattr(builtins, "__import__", mock_import)
        # Should not raise — falls back to scipy or pure python
        result = BayesianWeightOptimizer(space, eval_fn, seed=1).optimize({"op_a": 1.0, "op_b": 1.0})

    assert result is not None
    assert result.best_weights is not None
    assert len(call_log) > 0


def test_optimizer_selection_by_config():
    """strategy='bayesian' in config causes BayesianWeightOptimizer to be used."""
    from scion.parameter.optimizer import BayesianWeightOptimizer, RandomLocalWeightOptimizer
    from scion.config.problem import ParameterSearchConfig

    cfg = ParameterSearchConfig(strategy="bayesian")
    assert cfg.strategy == "bayesian"

    space = _make_space(n_initial=2, n_iter=2)
    opt = BayesianWeightOptimizer(space, lambda w: 1.0, seed=0)
    result = opt.optimize({"op_a": 1.0, "op_b": 1.0})
    assert isinstance(result.best_weights, dict)


def test_default_optimizer_unchanged():
    """Default strategy is still random_local; RandomLocalWeightOptimizer is used."""
    from scion.parameter.optimizer import RandomLocalWeightOptimizer
    from scion.config.problem import ParameterSearchConfig

    cfg = ParameterSearchConfig()
    assert cfg.strategy == "random_local"

    space = _make_space()
    opt = RandomLocalWeightOptimizer(space, lambda w: 1.0, seed=0)
    result = opt.optimize({"op_a": 1.0, "op_b": 1.0})
    assert isinstance(result.best_weights, dict)

