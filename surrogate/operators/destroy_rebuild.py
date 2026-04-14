"""
算子：DestroyRebuild（打散多辆车的部分订单，贪心重装）

随机选 2~4 辆车，将它们的未锁定订单全部释放，
然后用贪心算法重新分配到现有车辆或新建车辆。
"""

from __future__ import annotations

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
from operators.base import Operator, generate_vehicle_id


class DestroyRebuild(Operator):
    """打散部分车辆的未锁定订单，贪心重装。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选 2~4 辆车，释放未锁定订单，贪心重新装箱。"""
        vehicle_ids = list(solution.vehicles.keys())
        if len(vehicle_ids) < 2:
            return solution

        new_sol = solution.deep_copy()

        # 随机选要打散的车辆数（2~4，但不超过总车辆数）
        num_destroy = min(rng.randint(2, 4), len(vehicle_ids))
        destroy_vids = rng.sample(vehicle_ids, num_destroy)

        # 收集被释放的未锁定订单
        freed_oids: list[str] = []
        for vid in destroy_vids:
            vehicle = new_sol.vehicles[vid]
            still_locked = []
            for oid in vehicle.order_ids:
                order = self.instance.orders[oid]
                if order.locked_vehicle_id is None:
                    freed_oids.append(oid)
                    del new_sol.assignment[oid]
                else:
                    still_locked.append(oid)
            vehicle.order_ids = still_locked

        if not freed_oids:
            return solution

        # 打乱顺序，避免贪心偏差
        rng.shuffle(freed_oids)

        # 贪心重装：尝试塞入现有车辆，不行则新建
        for oid in freed_oids:
            order = self.instance.orders[oid]
            order_pallets = calc_pallets(order.spu_list)
            order_region = get_region(order.pickup_city)
            placed = False

            # 尝试现有车辆（随机打乱顺序，避免每次都选同一辆）
            candidate_vids = list(new_sol.vehicles.keys())
            rng.shuffle(candidate_vids)

            for vid in candidate_vids:
                vehicle = new_sol.vehicles[vid]
                if not self._can_fit(vehicle, order, order_pallets, order_region, new_sol):
                    continue
                vehicle.order_ids.append(oid)
                new_sol.assignment[oid] = vid
                placed = True
                break

            if not placed:
                # 新建车辆
                new_vid = generate_vehicle_id(rng)
                hazard = order.hazard_quantity if order.hazard_flag else 0
                vtype = select_minimum_vehicle_type(order_pallets, hazard)
                new_sol.vehicles[new_vid] = Vehicle(
                    vehicle_id=new_vid,
                    vehicle_type=vtype,
                    region=order_region,
                    order_ids=[oid],
                )
                new_sol.assignment[oid] = new_vid

        # 移除打散后变空的车辆
        new_sol.remove_empty_vehicles()
        return new_sol

    def _can_fit(
        self,
        vehicle: Vehicle,
        order,
        order_pallets: int,
        order_region: str,
        solution: Solution,
    ) -> bool:
        """快速检查订单能否放入给定车辆（不做完整 oracle 检查）。"""
        # 片区必须一致
        existing_orders = [self.instance.orders[oid] for oid in vehicle.order_ids]
        if existing_orders:
            existing_region = get_region(existing_orders[0].pickup_city)
            if existing_region != order_region:
                return False

        # 栈板容量
        used_pallets = sum(calc_pallets(self.instance.orders[oid].spu_list) for oid in vehicle.order_ids)
        capacity = VEHICLE_TYPES[vehicle.vehicle_type].capacity
        if used_pallets + order_pallets > capacity:
            return False

        # Phase 1：分车大类必须一致
        if self.phase == 1 and existing_orders:
            if existing_orders[0].vehicle_category != order.vehicle_category:
                return False

        return True
