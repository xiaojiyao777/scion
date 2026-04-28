"""
算子：MoveOrder（将一个订单从 A 车移到 B 车）

从 pool 解中随机选一辆非空车，取一个未锁定订单，
移动到另一辆随机车（或新建一辆车）。
"""

from __future__ import annotations

from random import Random

from models import Instance, Solution, Vehicle, select_minimum_vehicle_type, calc_pallets
from operators.base import Operator, generate_vehicle_id


class MoveOrder(Operator):
    """将一个未锁定订单从 A 车移到 B 车（或新建车）。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选一个未锁定订单，移到另一辆车。

        目标车：从现有车辆中随机选（排除源车），或以 10% 概率新建一辆车。
        """
        new_sol = solution.deep_copy()
        self._repair_assignment_from_vehicles(new_sol)

        # 收集所有未锁定订单
        unlocked_oids = [
            oid for oid, vid in new_sol.assignment.items()
            if self.instance.orders[oid].locked_vehicle_id is None
        ]

        if not unlocked_oids:
            return solution

        # 随机选一个未锁定订单
        oid = rng.choice(unlocked_oids)
        src_vid = new_sol.assignment.get(oid)
        order = self.instance.orders[oid]
        if src_vid not in new_sol.vehicles or oid not in new_sol.vehicles[src_vid].order_ids:
            # Defensive repair: upstream operators may leave assignment and
            # vehicle.order_ids temporarily inconsistent. Use the actual
            # vehicle containing the order; if none exists, this move is unsafe.
            actual_src = next(
                (vid for vid, vehicle in new_sol.vehicles.items() if oid in vehicle.order_ids),
                None,
            )
            if actual_src is None:
                return solution
            src_vid = actual_src
            new_sol.assignment[oid] = src_vid

        # 决定目标车
        other_vehicles = [
            vid for vid in new_sol.vehicles
            if vid != src_vid
        ]

        if not other_vehicles or rng.random() < 0.1:
            # 10% 概率新建一辆车
            new_vid = generate_vehicle_id(rng)
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
        if oid not in new_sol.vehicles[src_vid].order_ids:
            actual_src = next(
                (vid for vid, vehicle in new_sol.vehicles.items() if oid in vehicle.order_ids),
                None,
            )
            if actual_src is None or actual_src == dst_vid:
                return solution
            src_vid = actual_src
        new_sol.vehicles[src_vid].order_ids.remove(oid)
        new_sol.vehicles[dst_vid].order_ids.append(oid)
        new_sol.assignment[oid] = dst_vid

        # 移除空车
        new_sol.remove_empty_vehicles()

        return new_sol

    @staticmethod
    def _repair_assignment_from_vehicles(solution: Solution) -> None:
        """Rebuild assignment from vehicle.order_ids when local state drifted."""
        repaired = {}
        for vid, vehicle in solution.vehicles.items():
            for oid in vehicle.order_ids:
                repaired[oid] = vid
        # Preserve assignments for orders that are not present in any vehicle;
        # later guards will no-op if such an order is selected.
        for oid, vid in solution.assignment.items():
            repaired.setdefault(oid, vid)
        solution.assignment = repaired
