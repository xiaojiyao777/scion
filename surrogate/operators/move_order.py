"""
算子：MoveOrder（将一个订单从 A 车移到 B 车）

从 pool 解中随机选一辆非空车，取一个未锁定订单，
移动到另一辆随机车（或新建一辆车）。
"""

from __future__ import annotations

import uuid
from random import Random

from models import Instance, Solution, Vehicle, select_minimum_vehicle_type, calc_pallets
from operators.base import Operator


class MoveOrder(Operator):
    """将一个未锁定订单从 A 车移到 B 车（或新建车）。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选一个未锁定订单，移到另一辆车。

        目标车：从现有车辆中随机选（排除源车），或以 10% 概率新建一辆车。
        """
        # 收集所有未锁定订单
        unlocked_oids = [
            oid for oid, vid in solution.assignment.items()
            if self.instance.orders[oid].locked_vehicle_id is None
        ]

        if not unlocked_oids:
            return solution

        new_sol = solution.deep_copy()

        # 随机选一个未锁定订单
        oid = rng.choice(unlocked_oids)
        src_vid = new_sol.assignment[oid]
        order = self.instance.orders[oid]

        # 决定目标车
        other_vehicles = [
            vid for vid in new_sol.vehicles
            if vid != src_vid
        ]

        if not other_vehicles or rng.random() < 0.1:
            # 10% 概率新建一辆车
            new_vid = f"V_{uuid.uuid4().hex[:8]}"
            pallets = calc_pallets(order.spu_list)
            vtype = select_minimum_vehicle_type(pallets, order.hazard_quantity if order.hazard_flag else 0)
            new_sol.vehicles[new_vid] = Vehicle(
                vehicle_id=new_vid,
                vehicle_type=vtype,
                region=order.pickup_city,  # 片区 = 城市（surrogate 简化）
                order_ids=[],
            )
            dst_vid = new_vid
        else:
            dst_vid = rng.choice(other_vehicles)

        # 执行移动
        new_sol.vehicles[src_vid].order_ids.remove(oid)
        new_sol.vehicles[dst_vid].order_ids.append(oid)
        new_sol.assignment[oid] = dst_vid

        # 移除空车
        new_sol.remove_empty_vehicles()

        return new_sol
