"""
Oracle 单元测试

覆盖:
1. 正常可行解
2. 各硬约束违反(H1~H8)
3. objective recompute 正确性
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 surrogate/ 在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import (
    Instance,
    Order,
    Solution,
    SPU,
    Vehicle,
)
from oracle import check_feasibility, recompute_objective


# ---------------------------------------------------------------------------
# 辅助构造函数
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
        spu_list=spu_list or [SPU("整板", 2)],
        locked_vehicle_id=locked_vehicle_id,
    )


def make_instance(
    orders: list[Order],
    amount_limits: dict[str, float] | None = None,
    phase: int = 1,
) -> Instance:
    return Instance(
        orders={o.order_id: o for o in orders},
        amount_limits=amount_limits or {"德国,海运": 1_000_000.0},
        phase=phase,
    )


def make_solution(
    vid: str,
    order_ids: list[str],
    vehicle_type: str = "HQ40",
    region: str = "东莞",
) -> Solution:
    v = Vehicle(vehicle_id=vid, vehicle_type=vehicle_type, region=region, order_ids=order_ids)
    assignment = {oid: vid for oid in order_ids}
    return Solution(vehicles={vid: v}, assignment=assignment)


# ---------------------------------------------------------------------------
# 测试:正常可行解
# ---------------------------------------------------------------------------

class TestFeasibleSolution:
    def test_single_order_feasible(self):
        """单订单单车,所有约束满足。"""
        order = make_order()
        inst = make_instance([order])
        sol = make_solution("V1", ["O1"])
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible
        assert result.violations == []

    def test_two_orders_same_subcat(self):
        """两个同小类订单在同一辆车,可行。"""
        o1 = make_order("O1", vehicle_subcategory=1, spu_list=[SPU("整板", 3)])
        o2 = make_order("O2", vehicle_subcategory=1, spu_list=[SPU("整板", 3)])
        inst = make_instance([o1, o2])
        sol = make_solution("V1", ["O1", "O2"])
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible

    def test_hazard_special_vehicle_allowed(self):
        """危险品专车超 1800pcs,可行。"""
        o = make_order("O1", hazard_flag=True, hazard_quantity=2000,
                       spu_list=[SPU("整板", 1)])
        inst = make_instance([o])
        sol = make_solution("V1", ["O1"], vehicle_type="HQ40_DG")
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible


# ---------------------------------------------------------------------------
# 测试:硬约束违反(H1~H8)
# ---------------------------------------------------------------------------

class TestHardConstraintViolations:
    def test_H1_capacity_exceeded(self):
        """H1:栈板超容量。"""
        # T3 容量 3,装 4 栈板
        o = make_order("O1", spu_list=[SPU("整板", 4)])
        inst = make_instance([o])
        sol = make_solution("V1", ["O1"], vehicle_type="T3")
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H1" in v for v in result.violations)

    def test_H2_region_mismatch(self):
        """H2:同车订单来自不同片区。"""
        o1 = make_order("O1", pickup_city="东莞", pickup_name="成品央仓")
        o2 = make_order("O2", pickup_city="深圳", pickup_name="工厂直发仓A")
        inst = make_instance([o1, o2])
        v = Vehicle("V1", "HQ40", "东莞", ["O1", "O2"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1", "O2": "V1"})
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H2" in v for v in result.violations)

    def test_H3_too_many_pickups_donguan(self):
        """H3:东莞片区超过 2 个提货点。"""
        o1 = make_order("O1", pickup_name="成品央仓", pickup_city="东莞")
        o2 = make_order("O2", pickup_name="备件央仓", pickup_city="东莞")
        o3 = make_order("O3", pickup_name="SKD仓", pickup_city="东莞")
        inst = make_instance([o1, o2, o3])
        v = Vehicle("V1", "HQ40", "东莞", ["O1", "O2", "O3"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1", "O2": "V1", "O3": "V1"})
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H3" in v for v in result.violations)

    def test_H4_category_mismatch_phase1(self):
        """H4:Phase 1 中同车订单大类不同。"""
        o1 = make_order("O1", vehicle_category=0)
        o2 = make_order("O2", vehicle_category=1)
        inst = make_instance([o1, o2])
        v = Vehicle("V1", "HQ40", "东莞", ["O1", "O2"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1", "O2": "V1"})
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H4" in v for v in result.violations)

    def test_H4_not_checked_in_phase2(self):
        """H4:Phase 2 中不检查大类隔离。"""
        o1 = make_order("O1", vehicle_category=0)
        o2 = make_order("O2", vehicle_category=1)
        inst = make_instance([o1, o2], phase=2)
        v = Vehicle("V1", "HQ40", "东莞", ["O1", "O2"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1", "O2": "V1"})
        result = check_feasibility(sol, inst, phase=2)
        # Phase 2 跳过 H4,但 H2 片区一致,所以可行
        assert result.is_feasible

    def test_H5_hazard_over_1800_needs_special(self):
        """H5:危险品超 1800pcs 必须用专车。"""
        o = make_order("O1", hazard_flag=True, hazard_quantity=2000,
                       spu_list=[SPU("整板", 1)])
        inst = make_instance([o])
        sol = make_solution("V1", ["O1"], vehicle_type="HQ40")
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H5" in v for v in result.violations)

    def test_H6_amount_exceeds_limit(self):
        """H6:同车同 (国家, 运输方式) 金额超基线。"""
        o1 = make_order("O1", declaration_amount=600_000.0)
        o2 = make_order("O2", declaration_amount=600_000.0)
        inst = make_instance([o1, o2], amount_limits={"德国,海运": 1_000_000.0})
        v = Vehicle("V1", "HQ40", "东莞", ["O1", "O2"])
        sol = Solution(vehicles={"V1": v}, assignment={"O1": "V1", "O2": "V1"})
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H6" in v for v in result.violations)

    def test_H7_locked_group_split(self):
        """H7：同一锁定组的订单被拆到两辆车 → 违规。"""
        o1 = make_order("O1", locked_vehicle_id="V_LOCK_grp_0")
        o2 = make_order("O2", locked_vehicle_id="V_LOCK_grp_0")
        inst = make_instance([o1, o2])
        # 两个 locked 订单分在不同车
        from models import Solution, Vehicle
        sol = Solution(
            vehicles={
                "VEH_A": Vehicle(vehicle_id="VEH_A", vehicle_type="HQ40",
                                  region="DG", order_ids=["O1"]),
                "VEH_B": Vehicle(vehicle_id="VEH_B", vehicle_type="HQ40",
                                  region="DG", order_ids=["O2"]),
            },
            assignment={"O1": "VEH_A", "O2": "VEH_B"},
            objective=None,
        )
        result = check_feasibility(sol, inst, phase=1)
        assert not result.is_feasible
        assert any("H7" in v for v in result.violations)

    def test_H7_locked_group_merged_ok(self):
        """H7：同一锁定组整体并入另一辆车（任意 vehicle_id） → 允许。"""
        o1 = make_order("O1", locked_vehicle_id="V_LOCK_grp_0")
        o2 = make_order("O2", locked_vehicle_id="V_LOCK_grp_0")
        o3 = make_order("O3")  # unlocked
        inst = make_instance([o1, o2, o3])
        # 两个 locked 订单和 unlocked 订单都在同一辆（非原始）车上
        sol = make_solution("VEH_MERGED", ["O1", "O2", "O3"])
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible

    def test_H7_locked_order_same_vehicle_ok(self):
        """H7：单个锁定订单在任意车上 → 允许（组未被拆散）。"""
        o = make_order("O1", locked_vehicle_id="V_LOCK_0")
        inst = make_instance([o])
        sol = make_solution("V_OTHER", ["O1"])  # 车 ID 不同也 OK，因为组只有 1 个订单
        result = check_feasibility(sol, inst, phase=1)
        assert result.is_feasible


# ---------------------------------------------------------------------------
# 测试:Objective Recompute
# ---------------------------------------------------------------------------

class TestObjectiveRecompute:
    def test_no_split(self):
        """同一小类订单在同一辆车,splits=0。"""
        o1 = make_order("O1", vehicle_subcategory=0)
        o2 = make_order("O2", vehicle_subcategory=0)
        inst = make_instance([o1, o2])
        sol = make_solution("V1", ["O1", "O2"])
        obj = recompute_objective(sol, inst)
        assert obj.subcategory_splits == 0

    def test_one_split(self):
        """同一小类订单分布在两辆车,splits=1。"""
        o1 = make_order("O1", vehicle_subcategory=0)
        o2 = make_order("O2", vehicle_subcategory=0)
        inst = make_instance([o1, o2])
        v1 = Vehicle("V1", "HQ40", "东莞", ["O1"])
        v2 = Vehicle("V2", "HQ40", "东莞", ["O2"])
        sol = Solution(
            vehicles={"V1": v1, "V2": v2},
            assignment={"O1": "V1", "O2": "V2"},
        )
        obj = recompute_objective(sol, inst)
        assert obj.subcategory_splits == 1

    def test_total_cost(self):
        """总成本等于非空车辆成本之和。"""
        o1 = make_order("O1")
        o2 = make_order("O2")
        inst = make_instance([o1, o2])
        v1 = Vehicle("V1", "HQ40", "东莞", ["O1"])   # cost=3300
        v2 = Vehicle("V2", "T5",   "东莞", ["O2"])   # cost=1200
        sol = Solution(
            vehicles={"V1": v1, "V2": v2},
            assignment={"O1": "V1", "O2": "V2"},
        )
        obj = recompute_objective(sol, inst)
        assert obj.total_cost == 3300 + 1200

    def test_empty_vehicle_not_counted(self):
        """空车不计入总成本。"""
        o1 = make_order("O1")
        inst = make_instance([o1])
        v1 = Vehicle("V1", "HQ40", "东莞", ["O1"])  # cost=3300
        v2 = Vehicle("V2", "HQ40", "东莞", [])      # 空车,不计费
        sol = Solution(
            vehicles={"V1": v1, "V2": v2},
            assignment={"O1": "V1"},
        )
        obj = recompute_objective(sol, inst)
        assert obj.total_cost == 3300
