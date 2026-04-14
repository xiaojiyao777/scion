"""
端到端测试

加载 data/ 下的真实实例 → 求解 → 验证结果可行性和输出格式。
"""

from __future__ import annotations

import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from config import Config
from models import Solution
from oracle import check_feasibility, recompute_objective
from solver import load_instance, solve, solution_to_dict


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

    def test_small3_assignment_consistent_with_vehicles(self):
        """small_3：assignment 与 vehicles 内 order_ids 一致。"""
        inst = load_instance(get_instance_path("instance_small_3.json"), phase=1)
        cfg = Config(max_iterations=5, no_improve_limit=3, random_seed=1)
        sol = solve(inst, cfg)

        for oid, vid in sol.assignment.items():
            assert oid in sol.vehicles[vid].order_ids, \
                f"订单 {oid} 在 assignment 中归属 {vid}，但不在该车 order_ids 中"


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
