"""
端到端测试

加载 data/ 下的真实实例 → 求解 → 验证结果可行性和输出格式。
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from config import Config
from models import Solution
from operators.base import Operator
from oracle import check_feasibility, recompute_objective
from solver import load_instance, solve, solution_to_dict
from vns import run_vns


DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def get_instance_path(name: str) -> Path:
    p = DATA_DIR / name
    if not p.exists():
        pytest.skip(f"测试数据不存在: {p}")
    return p


# ---------------------------------------------------------------------------
# 测试：小规模实例（快速验证）
# ---------------------------------------------------------------------------

def _has_infeasible_locked_assignments(inst: "Instance") -> bool:
    """检查是否存在因锁定分配导致的不可逃避不可行（如超容量）。"""
    from collections import defaultdict
    from models import calc_pallets, VEHICLE_TYPES

    grouped: dict[str, list] = defaultdict(list)
    for order in inst.orders.values():
        if order.locked_vehicle_id is not None:
            grouped[order.locked_vehicle_id].append(order)

    for vid, orders in grouped.items():
        total = sum(calc_pallets(o.spu_list) for o in orders)
        max_capacity = max(v.capacity for v in VEHICLE_TYPES.values())
        if total > max_capacity:
            return True
    return False


class TestSmallInstance:
    def test_small1_feasible(self):
        """small_1 实例：求解结果必须可行（若锁定数据本身可行）。"""
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        if _has_infeasible_locked_assignments(inst):
            pytest.skip("测试数据含超容量锁定车辆，不可逃避不可行")
        cfg = Config(max_iterations=10, no_improve_limit=5, random_seed=42)
        sol = solve(inst, cfg)

        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible, f"不可行违反: {result.violations}"

    def test_small1_all_orders_assigned(self):
        """small_1：所有订单必须在 assignment 中。"""
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        cfg = Config(max_iterations=10, no_improve_limit=5, random_seed=42)
        sol = solve(inst, cfg)

        assert set(sol.assignment.keys()) == set(inst.orders.keys()), \
            "assignment 缺少部分订单"

    def test_small1_objective_computed(self):
        """small_1：解的目标值必须已计算且合法。"""
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        cfg = Config(max_iterations=10, no_improve_limit=5, random_seed=42)
        sol = solve(inst, cfg)

        assert sol.objective is not None
        assert sol.objective.subcategory_splits >= 0
        assert sol.objective.total_cost > 0

    def test_small2_solution_dict_format(self):
        """small_2：solution_to_dict 输出格式正确。"""
        inst = load_instance(get_instance_path("instance_small_2.json"), phase=1)
        cfg = Config(max_iterations=5, no_improve_limit=3, random_seed=0)
        sol = solve(inst, cfg)

        d = solution_to_dict(sol)
        assert "vehicles" in d
        assert "assignment" in d
        assert "objective" in d
        assert "subcategory_splits" in d["objective"]
        assert "total_cost" in d["objective"]

    def test_default_operator_registry_emits_state_transition_only(self):
        """默认 operator set 只证明 registry 激活，不声称尝试或效果。"""
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        cfg = Config(max_iterations=0, no_improve_limit=1, random_seed=42)

        sol = solve(inst, cfg)
        raw = solution_to_dict(sol, inst)

        runtime = raw["runtime"]
        assert runtime["operator_registry"] == [
            "swap_orders",
            "move_order",
            "destroy_rebuild",
            "merge_vehicles",
            "change_vehicle_type",
            "split_vehicle",
        ]
        assert "operator_diagnostics" not in runtime
        events = runtime["typed_telemetry_events"]
        assert len(events) == 1
        assert events[0]["lane"] == "state_transition"
        assert events[0]["mechanism_id"] == "warehouse_operator_registry"
        assert events[0]["occurrences"] == 1
        assert all(
            event["lane"] not in {"attempt", "direct_effect"}
            for event in events
        )

    def test_small3_assignment_consistent_with_vehicles(self):
        """small_3：assignment 与 vehicles 内 order_ids 一致。"""
        inst = load_instance(get_instance_path("instance_small_3.json"), phase=1)
        cfg = Config(max_iterations=5, no_improve_limit=3, random_seed=1)
        sol = solve(inst, cfg)

        for oid, vid in sol.assignment.items():
            assert oid in sol.vehicles[vid].order_ids, \
                f"订单 {oid} 在 assignment 中归属 {vid}，但不在该车 order_ids 中"

    def test_dynamic_operator_diagnostics_serialized(self, tmp_path, monkeypatch):
        """动态 registry 算子的实例 diagnostics 必须进入 solver runtime JSON。"""
        import operators as operators_pkg

        operator_dir = tmp_path / "operators"
        operator_dir.mkdir()
        operator_file = operator_dir / "diagnostic_operator.py"
        operator_file.write_text(
            """
from operators.base import Operator


class DiagnosticOperator(Operator):
    def __init__(self, instance, phase=1):
        self.instance = instance
        self.phase = phase
        self.validation_transfer_diagnostics = {
            "operator_invocations": 0,
            "eligible_vehicle_or_order_groups_seen": 0,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
        }

    def execute(self, solution, rng):
        diagnostics = self.validation_transfer_diagnostics
        diagnostics["operator_invocations"] += 1
        diagnostics["eligible_vehicle_or_order_groups_seen"] += 1
        diagnostics["accepted_moves"] += 1
        diagnostics["split_delta_sum"] += 1
        diagnostics["cost_delta_sum"] += 2
        diagnostics["improving_move_count"] += 1
        return solution.deep_copy()
""",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            operators_pkg,
            "__path__",
            [str(operator_dir), *list(operators_pkg.__path__)],
        )
        importlib.invalidate_caches()

        registry = tmp_path / "registry.yaml"
        registry.write_text(
            """
operators:
  - name: diagnostic_probe
    file_path: operators/diagnostic_operator.py
    class_name: DiagnosticOperator
    weight: 1.0
""",
            encoding="utf-8",
        )
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        cfg = Config(
            max_iterations=1,
            no_improve_limit=1,
            pool_size=1,
            random_seed=42,
        )

        sol = solve(inst, cfg, registry_path=registry)
        raw = solution_to_dict(sol, inst)

        diagnostics = raw["runtime"]["operator_diagnostics"]["diagnostic_probe"]
        assert diagnostics["operator_invocations"] > 0
        assert diagnostics["accepted_moves"] > 0
        assert diagnostics["split_delta_sum"] > 0
        assert (
            raw["runtime"]["validation_transfer_diagnostics"]
            == raw["runtime"]["operator_diagnostics"]
        )


# ---------------------------------------------------------------------------
# 测试：中等规模实例
# ---------------------------------------------------------------------------

class TestMediumInstance:
    def test_medium1_feasible(self):
        """medium_1 实例：求解结果必须可行（若锁定数据本身可行）。"""
        inst = load_instance(get_instance_path("instance_medium_1.json"), phase=1)
        if _has_infeasible_locked_assignments(inst):
            pytest.skip("测试数据含超容量锁定车辆")
        cfg = Config(max_iterations=20, no_improve_limit=10, random_seed=42)
        sol = solve(inst, cfg)

        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible, f"不可行违反: {result.violations}"

    def test_medium1_vehicle_types_valid(self):
        """medium_1：所有车辆的车型必须是合法类型。"""
        from models import VEHICLE_TYPES
        inst = load_instance(get_instance_path("instance_medium_1.json"), phase=1)
        cfg = Config(max_iterations=10, no_improve_limit=5, random_seed=42)
        sol = solve(inst, cfg)

        for vid, vehicle in sol.vehicles.items():
            assert vehicle.vehicle_type in VEHICLE_TYPES, \
                f"车辆 {vid} 的车型 {vehicle.vehicle_type} 非法"

    def test_medium2_objective_better_than_trivial(self):
        """medium_2：VNS 优化后目标不差于贪心初始解。"""
        from greedy_init import greedy_init
        inst = load_instance(get_instance_path("instance_medium_2.json"), phase=1)
        init_sol = greedy_init(inst, Random(42))
        init_obj = recompute_objective(init_sol, inst)

        cfg = Config(max_iterations=30, no_improve_limit=15, random_seed=42)
        sol = solve(inst, cfg)
        final_obj = sol.objective

        # VNS 结果应不差于初始解（字典序）
        assert final_obj is not None
        assert final_obj.as_tuple() <= init_obj.as_tuple(), \
            f"VNS 结果 {final_obj} 差于初始解 {init_obj}"


class SlowNoopOperator(Operator):
    """测试专用算子：制造可观测的 wall-clock 消耗。"""

    def execute(self, solution: Solution, rng: Random) -> Solution:
        time.sleep(0.01)
        return solution.deep_copy()


class TestTimeLimit:
    def test_vns_respects_wall_clock_time_limit(self):
        """极小时间预算应截断高迭代上限，并返回当前可行最优解。"""
        from greedy_init import greedy_init

        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        init_sol = greedy_init(inst, Random(42))
        init_sol.objective = recompute_objective(init_sol, inst)
        cfg = Config(
            pool_size=5,
            max_iterations=1000,
            no_improve_limit=1000,
            random_seed=42,
            time_limit_seconds=0.03,
        )
        iterations: list[int] = []

        t0 = time.monotonic()
        sol = run_vns(
            instance=inst,
            initial_solutions=[init_sol],
            operators=[SlowNoopOperator()],
            operator_weights=[1.0],
            cfg=cfg,
            on_iteration=lambda iteration, best: iterations.append(iteration),
        )
        elapsed = time.monotonic() - t0

        assert len(iterations) < cfg.max_iterations
        assert elapsed < 0.25
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible, f"超时返回解不可行: {result.violations}"


# ---------------------------------------------------------------------------
# 测试：greedy_init 单元
# ---------------------------------------------------------------------------

class TestGreedyInit:
    def test_all_orders_in_init_solution(self):
        """贪心初始解包含所有订单。"""
        from greedy_init import greedy_init
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        sol = greedy_init(inst, Random(42))
        assert set(sol.assignment.keys()) == set(inst.orders.keys())

    def test_init_solution_assignment_consistent(self):
        """贪心初始解 assignment 与 vehicles 一致。"""
        from greedy_init import greedy_init
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        sol = greedy_init(inst, Random(42))
        for oid, vid in sol.assignment.items():
            assert oid in sol.vehicles[vid].order_ids

    def test_init_solution_feasible(self):
        """贪心初始解可行（若锁定数据本身可行）。"""
        from greedy_init import greedy_init
        inst = load_instance(get_instance_path("instance_small_1.json"), phase=1)
        if _has_infeasible_locked_assignments(inst):
            pytest.skip("测试数据含超容量锁定车辆")
        sol = greedy_init(inst, Random(42))
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible, f"初始解不可行: {result.violations}"
