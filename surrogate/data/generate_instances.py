"""
生成大规模 benchmark 实例

输出：
  - instance_large_1.json  — 50 订单，8-10 辆车容量，3-4 子类别，含危险品
  - instance_large_2.json  — 50 订单，不同分布（小 SPU，多子类拆分机会）
  - instance_xlarge_1.json — 100 订单，15-20 辆车容量，5-6 子类别，复杂约束

使用方式：
  python3 generate_instances.py
"""

import json
import math
import random
from pathlib import Path

# ── 输出目录 ──────────────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(exist_ok=True)

# ── 常量定义 ──────────────────────────────────────────────────────────────────
# 打包类型（与 models.py 保持一致）
PACKING_TYPES = ["FULL_PLT", "FULL_CTN", "WOOD_CASE", "LOOSE_CTN", "TAILGATE"]

# 提货点配置（城市, 省份, 仓库名）
PICKUP_CONFIGS = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
    ("Shenzhen", "Guangdong", "SZ_WH"),
    ("Shenzhen", "Guangdong", "SZ_FG_WH"),
]

# 承运商列表
LSPS = ["DB Schenker", "SF_INTL", "Maersk", "COSCO", "DHL", "Kuehne+Nagel"]

# 运输方式
SHIP_METHODS = ["ROAD", "RAIL", "SEA", "AIR"]

# 目的国 + 运输方式的合法组合
DESTINATION_ROUTES = [
    ("UK",           "ROAD"),
    ("Germany",      "ROAD"),
    ("France",       "ROAD"),
    ("Mexico",       "RAIL"),
    ("India",        "SEA"),
    ("India",        "AIR"),
    ("South Africa", "RAIL"),
    ("Brazil",       "SEA"),
    ("Japan",        "SEA"),
    ("USA",          "AIR"),
]

# 车型配置（与 models.py 一致）
VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600, "is_hazard_special": True},
    "HQ40":    {"capacity": 40, "cost": 3300, "is_hazard_special": False},
    "T10":     {"capacity": 14, "cost": 1800, "is_hazard_special": False},
    "T5":      {"capacity":  6, "cost": 1200, "is_hazard_special": False},
    "T3":      {"capacity":  3, "cost":  800, "is_hazard_special": False},
}


def make_spu_list(rng: random.Random, num_spus: int, large: bool = False) -> list[dict]:
    """
    生成随机 SPU 列表。
    large=True 时生成更大量（栈板更多），使每张订单占用更多车辆容量。
    """
    spus = []
    for _ in range(num_spus):
        ptype = rng.choice(PACKING_TYPES)
        if large:
            qty = rng.randint(3, 8)   # 大订单：每个 SPU 数量多
        else:
            qty = rng.randint(1, 5)   # 普通订单
        spus.append({"packing_type": ptype, "quantity": qty})
    return spus


def calc_pallets(spu_list: list[dict]) -> int:
    """估算订单栈板数（与 models.py 中 calc_pallets 逻辑一致）。"""
    PALLET_TYPES = {"FULL_PLT", "TAILGATE", "WOOD_CASE"}
    pallets = 0
    boxes = 0
    for spu in spu_list:
        if spu["packing_type"] in PALLET_TYPES:
            pallets += spu["quantity"]
        else:
            boxes += spu["quantity"]
    pallets += math.ceil(boxes / 8)
    return pallets


def generate_instance(
    rng: random.Random,
    num_orders: int,
    num_subcategories: int,         # 子类别数量（影响拆分机会）
    num_categories: int,            # 大类数量
    hazard_ratio: float,            # 危险品订单占比
    locked_ratio: float,            # 锁车订单占比
    spu_per_order_range: tuple[int, int],  # 每张订单 SPU 条数范围
    spu_large: bool,                # 是否生成大量 SPU
    routes: list[tuple[str, str]],  # 使用的目的国路线子集
    target_vehicles: int,           # 目标车辆数（控制实例规模）
    label: str,                     # 实例标签（用于 locked_vehicle_id）
) -> dict:
    """
    生成单个问题实例字典（可直接序列化为 JSON）。

    设计策略：
    1. 按 (大类, 子类, 提货城市) 分组生成订单
    2. hazard_ratio 控制危险品订单比例
    3. locked_ratio 控制锁车订单比例（每个锁车 ID 对应一辆逻辑车）
    4. 确保总容量 > 总需求（至少有 30% 冗余）
    """
    orders = []
    # 每个子类别下生成的目的国路线（随机分配，确保多样性）
    subcat_routes: dict[int, tuple[str, str]] = {}
    for subcat in range(num_subcategories):
        subcat_routes[subcat] = routes[subcat % len(routes)]

    # 计算需要多少个 locked_vehicle_id
    num_locked = max(1, round(num_orders * locked_ratio))
    # 每辆锁车最多承载 num_orders // num_locked 张订单
    locked_ids = [f"V_LOCKED_{label}_{i}" for i in range(num_locked)]

    # 按子类别均匀分配订单数
    orders_per_subcat = num_orders // num_subcategories
    remainder = num_orders - orders_per_subcat * num_subcategories

    order_idx = 0
    # 追踪哪些 locked_id 已被使用以及使用次数
    locked_usage: dict[str, int] = {lid: 0 for lid in locked_ids}
    max_orders_per_lock = max(2, num_orders // (num_locked * 2))

    for subcat in range(num_subcategories):
        # 该子类订单数（最后一个子类吸收余量）
        n = orders_per_subcat + (remainder if subcat == num_subcategories - 1 else 0)
        dest_country, ship_method = subcat_routes[subcat]
        # 每个子类选一个大类
        cat = subcat % num_categories

        for i in range(n):
            oid = f"ORD_{order_idx:04d}"
            # 是否危险品
            is_hazard = rng.random() < hazard_ratio
            hazard_qty = rng.randint(1500, 4000) if is_hazard else 0

            # 提货点（同一子类内适当混合）
            pickup_city, pickup_province, pickup_name = rng.choice(PICKUP_CONFIGS)
            lsp = rng.choice(LSPS)

            # 金额：危险品订单通常金额较高
            amount_base = rng.uniform(50000, 200000) if is_hazard else rng.uniform(50000, 500000)
            amount = round(amount_base, 2)

            # SPU 列表
            num_spus = rng.randint(*spu_per_order_range)
            spu_list = make_spu_list(rng, num_spus, large=spu_large)

            # 锁车分配：从可用的 locked_id 中随机选，不超过上限
            locked_vehicle_id = None
            if rng.random() < locked_ratio:
                # 找未达上限的 locked_id
                available = [lid for lid, cnt in locked_usage.items()
                             if cnt < max_orders_per_lock]
                if available:
                    chosen = rng.choice(available)
                    locked_usage[chosen] += 1
                    locked_vehicle_id = chosen

            orders.append({
                "order_id": oid,
                "vehicle_category": cat,
                "vehicle_subcategory": subcat,
                "urgent": rng.random() < 0.08,   # ~8% 紧急单
                "hazard_flag": is_hazard,
                "hazard_quantity": hazard_qty,
                "pickup_name": pickup_name,
                "pickup_province": pickup_province,
                "pickup_city": pickup_city,
                "declaration_amount": amount,
                "lsp": lsp,
                "ship_method": ship_method,
                "destination_country": dest_country,
                "spu_list": spu_list,
                "locked_vehicle_id": locked_vehicle_id,
            })
            order_idx += 1

    # ── 计算金额限制 ───────────────────────────────────────────────────────────
    # 每条路线的金额上限 = 该路线订单总金额 × 1.5（确保宽松可行性）
    route_amounts: dict[str, float] = {}
    for order in orders:
        key = f"{order['destination_country']},{order['ship_method']}"
        route_amounts[key] = route_amounts.get(key, 0) + order["declaration_amount"]

    amount_limits = {}
    for key, total in route_amounts.items():
        # 每辆车的金额上限约等于总金额 / (大约 3 辆车/路线)
        # 保证单辆车能装下平均量的 1.5 倍
        vehicles_per_route = max(2, target_vehicles // len(route_amounts))
        limit_per_vehicle = (total / vehicles_per_route) * 1.8
        amount_limits[key] = round(limit_per_vehicle, 2)

    # ── 可行性校验 ─────────────────────────────────────────────────────────────
    total_pallets = sum(calc_pallets(o["spu_list"]) for o in orders)
    # 每辆 HQ40 容量 40 栈板，计算所需最少车辆数
    min_vehicles_needed = math.ceil(total_pallets / 40)
    print(f"[{label}] 总订单: {len(orders)}, 总栈板: {total_pallets}, "
          f"最少需要 HQ40 车辆数: {min_vehicles_needed}, "
          f"目标车辆数: {target_vehicles}")
    if min_vehicles_needed > target_vehicles:
        print(f"  ⚠️  警告: 实例可能过载，建议增加车辆容量或减少订单量")

    return {
        "orders": orders,
        "amount_limits": amount_limits,
        "vehicle_types": VEHICLE_TYPES,
    }


def main() -> None:
    # ── large_1: 50 订单，3-4 子类别，有危险品 ────────────────────────────────
    rng1 = random.Random(42)
    large_1 = generate_instance(
        rng=rng1,
        num_orders=50,
        num_subcategories=4,          # 4 个子类别
        num_categories=2,             # 2 个大类
        hazard_ratio=0.15,            # 15% 危险品订单
        locked_ratio=0.12,            # 12% 锁车订单
        spu_per_order_range=(3, 8),   # 每张订单 3-8 个 SPU 条
        spu_large=True,               # 大量 SPU，提高每张单的栈板占用
        routes=[
            ("UK",    "ROAD"),
            ("Germany", "ROAD"),
            ("Mexico", "RAIL"),
            ("India",  "SEA"),
        ],
        target_vehicles=10,           # 目标约 10 辆车
        label="L1",
    )
    out1 = OUT_DIR / "instance_large_1.json"
    out1.write_text(json.dumps(large_1, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out1}")

    # ── large_2: 50 订单，更多小 SPU，更多拆分机会 ────────────────────────────
    rng2 = random.Random(137)
    large_2 = generate_instance(
        rng=rng2,
        num_orders=50,
        num_subcategories=5,          # 5 个子类别（更多拆分机会）
        num_categories=2,
        hazard_ratio=0.10,
        locked_ratio=0.10,
        spu_per_order_range=(1, 4),   # 每张订单 1-4 个 SPU（小订单）
        spu_large=False,              # 小 SPU 量，允许更多子类别内分裂
        routes=[
            ("France",       "ROAD"),
            ("Japan",        "SEA"),
            ("Brazil",       "SEA"),
            ("South Africa", "RAIL"),
            ("USA",          "AIR"),
        ],
        target_vehicles=12,           # 目标约 12 辆（小订单需要更多车）
        label="L2",
    )
    out2 = OUT_DIR / "instance_large_2.json"
    out2.write_text(json.dumps(large_2, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out2}")

    # ── xlarge_1: 100 订单，5-6 子类别，复杂约束 ─────────────────────────────
    rng3 = random.Random(999)
    xlarge_1 = generate_instance(
        rng=rng3,
        num_orders=100,
        num_subcategories=6,          # 6 个子类别（最复杂）
        num_categories=3,             # 3 个大类
        hazard_ratio=0.18,            # 18% 危险品订单（需要 HQ40_DG）
        locked_ratio=0.15,            # 15% 锁车（约 15 张单锁定）
        spu_per_order_range=(2, 7),
        spu_large=True,
        routes=[
            ("UK",           "ROAD"),
            ("Germany",      "ROAD"),
            ("Mexico",       "RAIL"),
            ("India",        "SEA"),
            ("South Africa", "RAIL"),
            ("Japan",        "SEA"),
        ],
        target_vehicles=18,           # 目标约 18 辆
        label="XL1",
    )
    out3 = OUT_DIR / "instance_xlarge_1.json"
    out3.write_text(json.dumps(xlarge_1, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out3}")

    print("\n所有实例生成完毕。")


if __name__ == "__main__":
    main()
