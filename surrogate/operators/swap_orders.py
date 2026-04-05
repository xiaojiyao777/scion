"""
算子：SwapOrders（两车各取一个订单互换）

从 pool 解中随机选两辆非空车，各取一个未锁定订单进行互换。
互换后由 VNS 调用方检查可行性。
"""

from __future__ import annotations

from random import Random

from models import Instance, Solution
from operators.base import Operator


class SwapOrders(Operator):
    """两辆车各取一个未锁定订单互换位置。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选两辆车各取一个未锁定订单互换。

        若找不到合适的订单对，返回原解。
        """
        # 找出所有有未锁定订单的车辆
        eligible_vehicles = [
            vid for vid, v in solution.vehicles.items()
            if any(
                self.instance.orders[oid].locked_vehicle_id is None
                for oid in v.order_ids
            )
        ]

        if len(eligible_vehicles) < 2:
            return solution

        new_sol = solution.deep_copy()

        # 随机选两辆不同的车
        v1_id, v2_id = rng.sample(eligible_vehicles, 2)
        v1 = new_sol.vehicles[v1_id]
        v2 = new_sol.vehicles[v2_id]

        # 从每辆车中随机选一个未锁定订单
        unlocked1 = [
            oid for oid in v1.order_ids
            if self.instance.orders[oid].locked_vehicle_id is None
        ]
        unlocked2 = [
            oid for oid in v2.order_ids
            if self.instance.orders[oid].locked_vehicle_id is None
        ]

        if not unlocked1 or not unlocked2:
            return solution

        oid1 = rng.choice(unlocked1)
        oid2 = rng.choice(unlocked2)

        # 执行互换：oid1 从 v1 移到 v2，oid2 从 v2 移到 v1
        v1.order_ids.remove(oid1)
        v2.order_ids.remove(oid2)
        v1.order_ids.append(oid2)
        v2.order_ids.append(oid1)

        # 更新 assignment
        new_sol.assignment[oid1] = v2_id
        new_sol.assignment[oid2] = v1_id

        return new_sol
