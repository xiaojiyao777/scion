"""
贪心初始解生成

Phase 1：按分车小类聚合订单，贪心装箱生成初始解。
Phase 2：每个一次逻辑车作为独立初始车辆（输入即为基础解）。
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from models import (
    Instance,
    Order,
    Solution,
    Vehicle,
    calc_pallets,
    get_region,
    select_minimum_vehicle_type,
    VEHICLE_TYPES,
)


def greedy_init(instance: Instance) -> Solution:
    """生成贪心初始解。

    Phase 1：
      1. 按分车小类分组
      2. 同小类内按贪心装箱：当前车装不下则新建
      3. 车型先用 HQ40，再由 ChangeVehicleType 算子优化降级

    Phase 2：
      所有订单已锁定到一次逻辑车，每个 locked_vehicle_id 对应一辆初始车辆。
    """
    if instance.phase == 2:
        return _phase2_init(instance)
    return _phase1_init(instance)


def _phase1_init(instance: Instance) -> Solution:
    """Phase 1 贪心：按小类 + 大类分组装箱。"""
    vehicles: dict[str, Vehicle] = {}
    assignment: dict[str, str] = {}

    # 按 (vehicle_category, vehicle_subcategory, pickup_city) 分组
    # 同一辆车内大类必须相同（H4），片区必须一致（H2）
    groups: dict[tuple[int, int, str], list[Order]] = defaultdict(list)
    for order in instance.orders.values():
        key = (order.vehicle_category, order.vehicle_subcategory, order.pickup_city)
        groups[key].append(order)

    for (cat, subcat, city), orders in groups.items():
        region = get_region(city)
        # 当前正在填充的车辆 (vehicle_id, 已用栈板数, 危险品总量)
        current_vid: str | None = None
        current_pallets = 0
        current_hazard = 0
        current_pickups: set[str] = set()
        max_pickups = 2 if region == "东莞" else 3

        for order in orders:
            # 锁定订单：必须放在指定车辆内，单独处理
            if order.locked_vehicle_id is not None:
                locked_vid = order.locked_vehicle_id
                if locked_vid not in vehicles:
                    order_pallets = calc_pallets(order.spu_list)
                    order_hazard = order.hazard_quantity if order.hazard_flag else 0
                    vtype = "HQ40_DG" if order_hazard > 1800 else "HQ40"
                    vehicles[locked_vid] = Vehicle(
                        vehicle_id=locked_vid,
                        vehicle_type=vtype,
                        region=region,
                        order_ids=[],
                    )
                vehicles[locked_vid].order_ids.append(order.order_id)
                assignment[order.order_id] = locked_vid
                # 重置当前游标，避免后续未锁定订单混入锁定车辆
                current_vid = None
                current_pallets = 0
                current_hazard = 0
                current_pickups = set()
                continue
            order_pallets = calc_pallets(order.spu_list)
            order_hazard = order.hazard_quantity if order.hazard_flag else 0

            # 新增提货点后是否超过上限
            new_pickups = current_pickups | {order.pickup_name}
            pickups_ok = len(new_pickups) <= max_pickups

            # 暂定车型（先用 HQ40，危险品超量用专车）
            tentative_hazard = current_hazard + order_hazard
            if tentative_hazard > 1800:
                tentative_type = "HQ40_DG"
            else:
                tentative_type = "HQ40"
            capacity = VEHICLE_TYPES[tentative_type].capacity

            # 当前车能否容纳
            can_fit = (
                current_vid is not None
                and current_pallets + order_pallets <= capacity
                and pickups_ok
            )

            if not can_fit:
                # 开新车
                current_vid = f"V_{uuid.uuid4().hex[:8]}"
                current_pallets = 0
                current_hazard = 0
                current_pickups = set()
                new_pickups = {order.pickup_name}

                # 若危险品超 1800 用专车
                if order_hazard > 1800:
                    vtype = "HQ40_DG"
                else:
                    vtype = "HQ40"

                vehicles[current_vid] = Vehicle(
                    vehicle_id=current_vid,
                    vehicle_type=vtype,
                    region=region,
                    order_ids=[],
                )

            # 装入当前车
            vehicles[current_vid].order_ids.append(order.order_id)
            assignment[order.order_id] = current_vid
            current_pallets += order_pallets
            current_hazard += order_hazard
            current_pickups = current_pickups | {order.pickup_name}

            # 更新车型（可能因累积危险品而需要升级）
            if current_hazard > 1800:
                vehicles[current_vid].vehicle_type = "HQ40_DG"

    # 对每辆车尝试选最小车型（初始降级优化）
    for vehicle in vehicles.values():
        orders = [instance.orders[oid] for oid in vehicle.order_ids]
        total_p = sum(calc_pallets(o.spu_list) for o in orders)
        total_h = sum(o.hazard_quantity for o in orders if o.hazard_flag)
        vehicle.vehicle_type = select_minimum_vehicle_type(total_p, total_h)

    return Solution(vehicles=vehicles, assignment=assignment)


def _phase2_init(instance: Instance) -> Solution:
    """Phase 2 初始化：每个 locked_vehicle_id 对应一辆独立车辆。

    所有订单已锁定在一次逻辑车内，按 locked_vehicle_id 分组。
    """
    vehicles: dict[str, Vehicle] = {}
    assignment: dict[str, str] = {}

    # 按 locked_vehicle_id 分组
    groups: dict[str, list[Order]] = defaultdict(list)
    for order in instance.orders.values():
        vid = order.locked_vehicle_id or f"V_{uuid.uuid4().hex[:8]}"
        groups[vid].append(order)

    for vid, orders in groups.items():
        total_pallets = sum(calc_pallets(o.spu_list) for o in orders)
        total_hazard = sum(o.hazard_quantity for o in orders if o.hazard_flag)
        vtype = select_minimum_vehicle_type(total_pallets, total_hazard)
        region = get_region(orders[0].pickup_city)

        vehicles[vid] = Vehicle(
            vehicle_id=vid,
            vehicle_type=vtype,
            region=region,
            order_ids=[o.order_id for o in orders],
        )
        for order in orders:
            assignment[order.order_id] = vid

    return Solution(vehicles=vehicles, assignment=assignment)
