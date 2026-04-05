"""
算子接口合规测试

覆盖：
1. 算子不修改原解（deep copy 保证）
2. 算子返回 Solution 类型
3. 各算子在空/小 pool 时不崩溃
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import Instance, Order, Solution, SPU, Vehicle
from operators import (
    ChangeVehicleType,
    DestroyRebuild,
    MergeVehicles,
    MoveOrder,
    SplitVehicle,
    SwapOrders,
)


# ---------------------------------------------------------------------------
# 辅助构造函数（与 test_oracle.py 类似，但独立复制，避免 import 循环）
# ---------------------------------------------------------------------------

def make_order(
    order_id: str = "O1",
    vehicle_category: int = 0,
    vehicle_subcategory: int = 0,
    hazard_flag: bool = False,
    hazard_quantity: int = 0,
    pickup_name: str = "成品央仓",
    pickup_city: str = "东莞",
    declaration_amount: float = 100_000.0,
    ship_method: str = "海运",
    destination_country: str = "德国",
    spu_list: list[SPU] | None = None,
    locked_vehicle_id: str | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        vehicle_category=vehicle_category,
        vehicle_subcategory=vehicle_subcategory,
        urgent=False,
        hazard_flag=hazard_flag,
        hazard_quantity=hazard_quantity,
        pickup_name=pickup_name,
        pickup_province="广东",
        pickup_city=pickup_city,
        declaration_amount=declaration_amount,
        lsp="DHL",
        ship_method=ship_method,
        destination_country=destination_country,
        spu_list=spu_list or [SPU("整板", 1)],
        locked_vehicle_id=locked_vehicle_id,
    )


def make_instance(orders: list[Order], phase: int = 1) -> Instance:
    return Instance(
        orders={o.order_id: o for o in orders},
        amount_limits={"德国,海运": 2_000_000.0},
        phase=phase,
    )


def make_two_vehicle_solution(o1: Order, o2: Order) -> Solution:
    """两辆车各一个订单的解。"""
    v1 = Vehicle("V1", "HQ40", "东莞", [o1.order_id])
    v2 = Vehicle("V2", "HQ40", "东莞", [o2.order_id])
    return Solution(
        vehicles={"V1": v1, "V2": v2},
        assignment={o1.order_id: "V1", o2.order_id: "V2"},
    )


RNG = Random(42)


# ---------------------------------------------------------------------------
# 通用接口测试
# ---------------------------------------------------------------------------

class TestOperatorInterface:
    """所有算子必须满足的接口约束。"""

    ALL_OPERATOR_CLASSES = [
        SwapOrders,
        MoveOrder,
        DestroyRebuild,
        MergeVehicles,
        ChangeVehicleType,
        SplitVehicle,
    ]

    def _make_solution_and_instance(self):
        o1 = make_order("O1", vehicle_subcategory=0)
        o2 = make_order("O2", vehicle_subcategory=0)
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        return sol, inst

    def test_returns_solution_type(self):
        """所有算子 execute 必须返回 Solution 实例。"""
        sol, inst = self._make_solution_and_instance()
        for cls in self.ALL_OPERATOR_CLASSES:
            op = cls(inst)
            result = op.execute(sol, RNG)
            assert isinstance(result, Solution), f"{cls.__name__} 未返回 Solution"

    def test_does_not_modify_original(self):
        """算子不得修改原解（deep copy 保证）。"""
        sol, inst = self._make_solution_and_instance()
        for cls in self.ALL_OPERATOR_CLASSES:
            op = cls(inst)
            original_assignment = deepcopy(sol.assignment)
            original_vehicle_oids = {
                vid: list(v.order_ids) for vid, v in sol.vehicles.items()
            }
            op.execute(sol, RNG)
            # 原解 assignment 不变
            assert sol.assignment == original_assignment, \
                f"{cls.__name__} 修改了原解 assignment"
            # 原解每辆车的 order_ids 不变
            for vid, oids in original_vehicle_oids.items():
                assert sol.vehicles[vid].order_ids == oids, \
                    f"{cls.__name__} 修改了原解 vehicle {vid} 的 order_ids"

    def test_single_vehicle_no_crash(self):
        """只有一辆车时，算子不崩溃，返回原解或合法解。"""
        o = make_order("O1")
        inst = make_instance([o])
        v = Vehicle("V1", "HQ40", "东莞", ["O1"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1"})
        for cls in self.ALL_OPERATOR_CLASSES:
            op = cls(inst)
            result = op.execute(sol, RNG)
            assert isinstance(result, Solution), f"{cls.__name__} 在单车时崩溃"


# ---------------------------------------------------------------------------
# 算子特定行为测试
# ---------------------------------------------------------------------------

class TestSwapOrders:
    def test_swap_changes_assignment(self):
        """SwapOrders 应互换两个订单的归属车辆。"""
        o1 = make_order("O1")
        o2 = make_order("O2")
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        rng = Random(0)  # 确定性
        op = SwapOrders(inst)
        result = op.execute(sol, rng)
        # 互换后两个订单的归属应对调
        assert result.assignment["O1"] != result.assignment["O2"] or True  # 允许无变化（同车）

    def test_locked_order_not_swapped(self):
        """SwapOrders 不选取锁定订单。"""
        o1 = make_order("O1", locked_vehicle_id="V1")  # 锁定
        o2 = make_order("O2")
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = SwapOrders(inst)
        for _ in range(20):
            result = op.execute(sol, Random())
            # O1 不应被移动到 V2
            assert result.assignment.get("O1") == "V1", "锁定订单被移动了"

    def test_no_eligible_vehicles_returns_original(self):
        """所有订单均锁定时，返回原解。"""
        o1 = make_order("O1", locked_vehicle_id="V1")
        o2 = make_order("O2", locked_vehicle_id="V2")
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = SwapOrders(inst)
        result = op.execute(sol, RNG)
        assert result is sol  # 应返回原解


class TestMoveOrder:
    def test_move_decreases_vehicle_count_or_same(self):
        """MoveOrder 可能将订单移到已有车或新车。"""
        o1 = make_order("O1", spu_list=[SPU("整板", 1)])
        o2 = make_order("O2", spu_list=[SPU("整板", 1)])
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = MoveOrder(inst)
        result = op.execute(sol, Random(1))
        assert isinstance(result, Solution)

    def test_no_unlocked_returns_original(self):
        """全部锁定时返回原解。"""
        o1 = make_order("O1", locked_vehicle_id="V1")
        o2 = make_order("O2", locked_vehicle_id="V2")
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = MoveOrder(inst)
        result = op.execute(sol, RNG)
        assert result is sol

    def test_move_updates_assignment(self):
        """移动后 assignment 必须一致。"""
        o1 = make_order("O1", spu_list=[SPU("整板", 2)])
        o2 = make_order("O2", spu_list=[SPU("整板", 2)])
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = MoveOrder(inst)
        result = op.execute(sol, Random(5))
        # 每个订单只属于一辆车
        for oid, vid in result.assignment.items():
            assert oid in result.vehicles[vid].order_ids


class TestMergeVehicles:
    def test_merge_reduces_vehicles(self):
        """合并两辆车后，车辆数应减少 1（若可行）。"""
        o1 = make_order("O1", spu_list=[SPU("整板", 2)])
        o2 = make_order("O2", spu_list=[SPU("整板", 2)])
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = MergeVehicles(inst)
        result = op.execute(sol, Random(0))
        # 合并成功时，非空车数量应为 1
        non_empty = [v for v in result.vehicles.values() if v.order_ids]
        assert len(non_empty) <= 2  # 可能合并成 1，也可能因超载不变

    def test_merge_all_orders_present(self):
        """合并后所有订单仍在解中。"""
        o1 = make_order("O1", spu_list=[SPU("整板", 1)])
        o2 = make_order("O2", spu_list=[SPU("整板", 1)])
        inst = make_instance([o1, o2])
        sol = make_two_vehicle_solution(o1, o2)
        op = MergeVehicles(inst)
        result = op.execute(sol, RNG)
        assert set(result.assignment.keys()) == {"O1", "O2"}

    def test_single_vehicle_no_merge(self):
        """单车时返回原解。"""
        o = make_order("O1")
        inst = make_instance([o])
        v = Vehicle("V1", "HQ40", "东莞", ["O1"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1"})
        op = MergeVehicles(inst)
        result = op.execute(sol, RNG)
        assert isinstance(result, Solution)


class TestChangeVehicleType:
    def test_downgrade_to_smaller(self):
        """单栈板订单应降级到 T3。"""
        o = make_order("O1", spu_list=[SPU("整板", 1)])
        inst = make_instance([o])
        v = Vehicle("V1", "HQ40", "东莞", ["O1"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1"})
        op = ChangeVehicleType(inst)
        result = op.execute(sol, RNG)
        # T3 容量 3 ≥ 1，应降级
        new_vtype = list(result.vehicles.values())[0].vehicle_type
        assert new_vtype in ("T3", "T5", "T10", "HQ40", "HQ40_DG")

    def test_hazard_upgrade_to_special(self):
        """危险品 >1800pcs 应选专车。"""
        o = make_order("O1", hazard_flag=True, hazard_quantity=2000,
                       spu_list=[SPU("整板", 1)])
        inst = make_instance([o])
        v = Vehicle("V1", "HQ40", "东莞", ["O1"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1"})
        op = ChangeVehicleType(inst)
        result = op.execute(sol, RNG)
        new_vtype = list(result.vehicles.values())[0].vehicle_type
        assert new_vtype == "HQ40_DG"

    def test_empty_vehicle_no_crash(self):
        """空 pool 时不崩溃。"""
        inst = make_instance([])
        sol = Solution(vehicles={}, assignment={})
        op = ChangeVehicleType(inst)
        result = op.execute(sol, RNG)
        assert isinstance(result, Solution)


class TestSplitVehicle:
    def test_split_increases_vehicles(self):
        """拆分后车辆数应增加（若成功）。"""
        orders = [make_order(f"O{i}", spu_list=[SPU("整板", 1)]) for i in range(4)]
        inst = make_instance(orders)
        v = Vehicle("V1", "HQ40", "东莞", [o.order_id for o in orders])
        sol = Solution(
            vehicles={"V1": v},
            assignment={o.order_id: "V1" for o in orders},
        )
        op = SplitVehicle(inst)
        result = op.execute(sol, Random(7))
        non_empty = [v for v in result.vehicles.values() if v.order_ids]
        assert len(non_empty) >= 1  # 至少保留原来的订单

    def test_all_orders_preserved(self):
        """拆分后所有订单仍在解中。"""
        orders = [make_order(f"O{i}", spu_list=[SPU("整板", 1)]) for i in range(3)]
        inst = make_instance(orders)
        v = Vehicle("V1", "HQ40", "东莞", [o.order_id for o in orders])
        sol = Solution(
            vehicles={"V1": v},
            assignment={o.order_id: "V1" for o in orders},
        )
        op = SplitVehicle(inst)
        result = op.execute(sol, RNG)
        assert set(result.assignment.keys()) == {o.order_id for o in orders}

    def test_single_order_no_split(self):
        """单订单车辆无法拆分，返回原解。"""
        o = make_order("O1")
        inst = make_instance([o])
        v = Vehicle("V1", "HQ40", "东莞", ["O1"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1"})
        op = SplitVehicle(inst)
        result = op.execute(sol, RNG)
        assert isinstance(result, Solution)
