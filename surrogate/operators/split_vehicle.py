"""
算子：SplitVehicle（拆分超载或违约车辆）

对随机选择的一辆车，将其未锁定订单随机拆分到当前车和一辆新车，
用于修复超载或其他约束违反。
"""

from __future__ import annotations

import uuid
from random import Random

from models import (
    Instance,
    Solution,
    Vehicle,
    calc_pallets,
    get_region,
    select_minimum_vehicle_type,
    VEHICLE_TYPES,
)
from operators.base import Operator


class SplitVehicle(Operator):
    """将一辆车的未锁定订单拆分到两辆车。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选一辆有 ≥2 个未锁定订单的车，将其拆分。"""
        # 找有至少 2 个未锁定订单的车
        eligible = [
            vid for vid, v in solution.vehicles.items()
            if sum(1 for oid in v.order_ids
                   if self.instance.orders[oid].locked_vehicle_id is None) >= 2
        ]
        if not eligible:
            return solution

        new_sol = solution.deep_copy()
        vid = rng.choice(eligible)
        vehicle = new_sol.vehicles[vid]

        # 区分锁定与未锁定订单
        locked_oids = [
            oid for oid in vehicle.order_ids
            if self.instance.orders[oid].locked_vehicle_id is not None
        ]
        unlocked_oids = [
            oid for oid in vehicle.order_ids
            if self.instance.orders[oid].locked_vehicle_id is None
        ]

        # 随机分配未锁定订单到两组
        rng.shuffle(unlocked_oids)
        split_point = rng.randint(1, len(unlocked_oids) - 1)
        group1 = unlocked_oids[:split_point]
        group2 = unlocked_oids[split_point:]

        if not group2:
            return solution

        # 原车保留锁定订单 + group1
        vehicle.order_ids = locked_oids + group1

        # 根据 group1 重新选车型
        if vehicle.order_ids:
            orders1 = [self.instance.orders[oid] for oid in vehicle.order_ids]
            p1 = sum(calc_pallets(o.spu_list) for o in orders1)
            h1 = sum(o.hazard_quantity for o in orders1 if o.hazard_flag)
            vehicle.vehicle_type = select_minimum_vehicle_type(p1, h1)

        # 新建第二辆车承接 group2
        new_vid = f"V_{uuid.uuid4().hex[:8]}"
        orders2 = [self.instance.orders[oid] for oid in group2]
        p2 = sum(calc_pallets(o.spu_list) for o in orders2)
        h2 = sum(o.hazard_quantity for o in orders2 if o.hazard_flag)
        region2 = get_region(orders2[0].pickup_city)
        vtype2 = select_minimum_vehicle_type(p2, h2)

        new_sol.vehicles[new_vid] = Vehicle(
            vehicle_id=new_vid,
            vehicle_type=vtype2,
            region=region2,
            order_ids=group2,
        )
        for oid in group2:
            new_sol.assignment[oid] = new_vid

        # 移除变空的车
        new_sol.remove_empty_vehicles()
        return new_sol
