"""
数据模型：订单、SPU、车型、车辆、解、目标值、实例

所有 dataclass 均支持 copy.deepcopy，确保算子操作不修改原解。
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# 车型常量
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VehicleTypeInfo:
    code: str
    capacity: int   # 最大栈板数
    cost: int       # 单车成本（元）
    is_hazard_special: bool = False  # 是否危险品专车


VEHICLE_TYPES: dict[str, VehicleTypeInfo] = {
    "HQ40_DG": VehicleTypeInfo("HQ40_DG", 40, 6600, is_hazard_special=True),
    "HQ40":    VehicleTypeInfo("HQ40",    40, 3300),
    "T10":     VehicleTypeInfo("T10",     14, 1800),
    "T5":      VehicleTypeInfo("T5",       6, 1200),
    "T3":      VehicleTypeInfo("T3",       3,  800),
}

# 车型按容量从小到大排列（用于选最小合适车型）
VEHICLE_TYPES_BY_CAPACITY = [
    ("T3",      3,   800),
    ("T5",      6,  1200),
    ("T10",    14,  1800),
    ("HQ40",   40,  3300),
    ("HQ40_DG", 40, 6600),
]

# ---------------------------------------------------------------------------
# 片区常量
# ---------------------------------------------------------------------------

# 片区 → 最大提货点数
REGION_MAX_PICKUPS: dict[str, int] = {
    "东莞": 2,
    "深圳": 3,
}

# 城市名 → 片区（surrogate 简化：城市即片区）
CITY_TO_REGION: dict[str, str] = {
    "东莞": "东莞",
    "深圳": "深圳",
}


def get_region(pickup_city: str) -> str:
    """根据提货城市获取片区名称。"""
    return CITY_TO_REGION.get(pickup_city, pickup_city)


def get_max_pickups(region: str) -> int:
    """获取该片区允许的最大提货点数。"""
    return REGION_MAX_PICKUPS.get(region, 3)


# ---------------------------------------------------------------------------
# SPU 与栈板计算
# ---------------------------------------------------------------------------

# 整板/尾板/木箱：每个 = 1 栈板；整箱/散箱：每 8 个 = 1 栈板
PALLET_TYPE = {"整板", "尾板", "木箱"}
BOX_TYPE    = {"整箱", "散箱"}


@dataclass
class SPU:
    """最小货运单元（Stock Packing Unit）。"""
    packing_type: str   # 整板 | 尾板 | 木箱 | 整箱 | 散箱
    quantity: int


def calc_pallets(spu_list: list[SPU]) -> int:
    """计算 SPU 列表折算后的栈板数。"""
    pallets = 0
    boxes = 0
    for spu in spu_list:
        if spu.packing_type in PALLET_TYPE:
            pallets += spu.quantity
        else:
            # 整箱 / 散箱
            boxes += spu.quantity
    pallets += math.ceil(boxes / 8)
    return pallets


# ---------------------------------------------------------------------------
# 订单
# ---------------------------------------------------------------------------

@dataclass
class Order:
    """物流订单（对应 spec §1.2）。"""
    order_id: str
    vehicle_category: int        # 分车大类序号
    vehicle_subcategory: int     # 分车小类序号
    urgent: bool
    hazard_flag: bool            # 是否危险品
    hazard_quantity: int         # 危险品数量（pcs）
    pickup_name: str             # 提货点名称
    pickup_province: str
    pickup_city: str             # 提货点城市（东莞 / 深圳）
    declaration_amount: float    # 报关金额
    lsp: str                     # 承运商
    ship_method: str             # 运输方式
    destination_country: str     # 目的国
    spu_list: list[SPU]
    locked_vehicle_id: Optional[str] = None  # None = 可自由分配


# ---------------------------------------------------------------------------
# 车辆与解
# ---------------------------------------------------------------------------

@dataclass
class Vehicle:
    """逻辑车辆（spec §1.4）。"""
    vehicle_id: str
    vehicle_type: str   # HQ40_DG | HQ40 | T10 | T5 | T3
    region: str         # 东莞 | 深圳
    order_ids: list[str] = field(default_factory=list)


@dataclass
class ObjectiveValue:
    """目标函数值（字典序：splits → cost → time）。"""
    subcategory_splits: int   # 分车小类拆分总数（越小越好）
    total_cost: int           # 总运输成本（越小越好）
    solve_time_ms: int = 0    # 求解时间 ms（外部测量）

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.subcategory_splits, self.total_cost, self.solve_time_ms)

    def __lt__(self, other: ObjectiveValue) -> bool:
        return self.as_tuple() < other.as_tuple()

    def __le__(self, other: ObjectiveValue) -> bool:
        return self.as_tuple() <= other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ObjectiveValue):
            return False
        return self.as_tuple() == other.as_tuple()


def is_better(a: ObjectiveValue, b: ObjectiveValue) -> bool:
    """字典序比较：a 是否严格优于 b。"""
    if a.subcategory_splits != b.subcategory_splits:
        return a.subcategory_splits < b.subcategory_splits
    if a.total_cost != b.total_cost:
        return a.total_cost < b.total_cost
    return a.solve_time_ms < b.solve_time_ms


@dataclass
class Solution:
    """优化解（spec §1.4）。

    - vehicles: vehicle_id → Vehicle
    - assignment: order_id → vehicle_id
    - objective: 目标函数值（由 oracle 计算后填入）
    """
    vehicles: dict[str, Vehicle]
    assignment: dict[str, str]                  # order_id → vehicle_id
    objective: Optional[ObjectiveValue] = None  # None 表示尚未计算

    def deep_copy(self) -> Solution:
        """深拷贝，确保算子不修改原解。"""
        return deepcopy(self)

    def remove_empty_vehicles(self) -> None:
        """移除无订单的空车（原地修改）。"""
        empty = [vid for vid, v in self.vehicles.items() if len(v.order_ids) == 0]
        for vid in empty:
            del self.vehicles[vid]


# ---------------------------------------------------------------------------
# 实例（问题输入）
# ---------------------------------------------------------------------------

@dataclass
class Instance:
    """问题实例（spec §1.2）。

    - orders: order_id → Order
    - amount_limits: "目的国,运输方式" → 金额上限
    - phase: 1（一次逻辑车）或 2（二次合并）
    - algorithm_identifiers: locked_vehicle_id → 算法标识（Phase 2 合并规则）
    """
    orders: dict[str, Order]
    amount_limits: dict[str, float]                   # key 格式: "德国,海运"
    phase: int = 1
    algorithm_identifiers: dict[str, str] = field(default_factory=dict)


def select_minimum_vehicle_type(total_pallets: int, total_hazard: int) -> str:
    """选择能容纳给定栈板数的最小（最低成本）车型。"""
    if total_hazard > 1800:
        return "HQ40_DG"
    for code, capacity, _cost in VEHICLE_TYPES_BY_CAPACITY:
        if code != "HQ40_DG" and capacity >= total_pallets:
            return code
    return "HQ40"  # 兜底
