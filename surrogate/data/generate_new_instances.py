"""
生成 5 个新的多样化 benchmark 实例

输出：
  - instance_small_2.json   — 20 订单，更多危险品（~30%），不同区域/子类分布
  - instance_medium_2.json  — 30 订单，更多子类别多样性（8 个子类别）
  - instance_medium_3.json  — 35 订单，高锁车比例（~40%）
  - instance_large_4.json   — 50 订单，极端场景：大量小件订单
  - instance_large_5.json   — 50 订单，多区域（Dongguan + Shenzhen + Guangzhou）
"""

import json
import math
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent

PACKING_TYPES = ["FULL_PLT", "FULL_CTN", "WOOD_CASE", "LOOSE_CTN", "TAILGATE"]

PICKUP_CONFIGS_DG = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
]
PICKUP_CONFIGS_SZ = [
    ("Shenzhen", "Guangdong", "SZ_WH"),
    ("Shenzhen", "Guangdong", "SZ_FG_WH"),
]
PICKUP_CONFIGS_GZ = [
    ("Guangzhou", "Guangdong", "GZ_WH"),
    ("Guangzhou", "Guangdong", "GZ_CENTRAL_WH"),
]
PICKUP_CONFIGS_ALL = PICKUP_CONFIGS_DG + PICKUP_CONFIGS_SZ + PICKUP_CONFIGS_GZ

LSPS = ["DB Schenker", "SF_INTL", "Maersk", "COSCO", "DHL", "Kuehne+Nagel"]

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

VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600,  "is_hazard_special": True},
    "HQ40":    {"capacity": 40, "cost": 3300,  "is_hazard_special": False},
    "T10":     {"capacity": 14, "cost": 1800,  "is_hazard_special": False},
    "T5":      {"capacity":  6, "cost": 1200,  "is_hazard_special": False},
    "T3":      {"capacity":  3, "cost":  800,  "is_hazard_special": False},
}


def make_spu_list(rng, num_spus, large=False, small_only=False):
    spus = []
    for _ in range(num_spus):
        if small_only:
            # 小件模式：偏向 LOOSE_CTN / FULL_CTN，数量 1-2
            ptype = rng.choice(["LOOSE_CTN", "FULL_CTN", "LOOSE_CTN", "FULL_CTN", "WOOD_CASE"])
            qty = rng.randint(1, 2)
        elif large:
            ptype = rng.choice(PACKING_TYPES)
            qty = rng.randint(3, 8)
        else:
            ptype = rng.choice(PACKING_TYPES)
            qty = rng.randint(1, 5)
        spus.append({"packing_type": ptype, "quantity": qty})
    return spus


def calc_pallets(spu_list):
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
    rng,
    num_orders,
    num_subcategories,
    num_categories,
    hazard_ratio,
    locked_ratio,
    spu_per_order_range,
    spu_large=False,
    spu_small_only=False,
    routes=None,
    target_vehicles=8,
    label="X",
    pickup_configs=None,
):
    if routes is None:
        routes = DESTINATION_ROUTES[:num_subcategories]
    if pickup_configs is None:
        pickup_configs = PICKUP_CONFIGS_DG

    orders = []
    subcat_routes = {}
    for subcat in range(num_subcategories):
        subcat_routes[subcat] = routes[subcat % len(routes)]

    num_locked = max(1, round(num_orders * locked_ratio))
    locked_ids = [f"V_LOCKED_{label}_{i}" for i in range(num_locked)]

    orders_per_subcat = num_orders // num_subcategories
    remainder = num_orders - orders_per_subcat * num_subcategories

    order_idx = 0
    locked_usage = {lid: 0 for lid in locked_ids}
    max_orders_per_lock = max(2, num_orders // max(1, num_locked * 2))

    for subcat in range(num_subcategories):
        n = orders_per_subcat + (remainder if subcat == num_subcategories - 1 else 0)
        dest_country, ship_method = subcat_routes[subcat]
        cat = subcat % num_categories

        for i in range(n):
            oid = f"ORD_{order_idx:04d}"
            is_hazard = rng.random() < hazard_ratio
            hazard_qty = rng.randint(1500, 4000) if is_hazard else 0

            pickup_city, pickup_province, pickup_name = rng.choice(pickup_configs)
            lsp = rng.choice(LSPS)
            amount = round(rng.uniform(50000, 200000) if is_hazard else rng.uniform(50000, 500000), 2)

            num_spus = rng.randint(*spu_per_order_range)
            spu_list = make_spu_list(rng, num_spus, large=spu_large, small_only=spu_small_only)

            locked_vehicle_id = None
            if rng.random() < locked_ratio and locked_ids:
                available = [lid for lid, cnt in locked_usage.items() if cnt < max_orders_per_lock]
                if available:
                    chosen = rng.choice(available)
                    locked_usage[chosen] += 1
                    locked_vehicle_id = chosen

            orders.append({
                "order_id": oid,
                "vehicle_category": cat,
                "vehicle_subcategory": subcat,
                "urgent": rng.random() < 0.08,
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

    # amount_limits
    route_amounts = {}
    for order in orders:
        key = f"{order['destination_country']},{order['ship_method']}"
        route_amounts[key] = route_amounts.get(key, 0) + order["declaration_amount"]

    amount_limits = {}
    for key, total in route_amounts.items():
        vehicles_per_route = max(2, target_vehicles // len(route_amounts))
        limit_per_vehicle = (total / vehicles_per_route) * 1.8
        amount_limits[key] = round(limit_per_vehicle, 2)

    total_pallets = sum(calc_pallets(o["spu_list"]) for o in orders)
    min_vehicles = math.ceil(total_pallets / 40)
    print(f"[{label}] 订单: {num_orders}, 栈板: {total_pallets}, "
          f"最少HQ40车辆: {min_vehicles}, 目标车辆: {target_vehicles}")
    if min_vehicles > target_vehicles:
        print(f"  ⚠️  警告: 实例可能过载")

    return {
        "orders": orders,
        "amount_limits": amount_limits,
        "vehicle_types": VEHICLE_TYPES,
    }


def validate_instance(data, filename):
    """验证实例的基本一致性"""
    errors = []
    orders = data["orders"]
    order_ids = {o["order_id"] for o in orders}

    # 收集所有出现过的 locked_vehicle_id
    locked_vid_to_orders = {}
    for o in orders:
        lvid = o.get("locked_vehicle_id")
        if lvid is not None:
            locked_vid_to_orders.setdefault(lvid, []).append(o["order_id"])

    # 验证：locked_vehicle_id 只要出现在 orders 中就 OK（没有单独的 vehicles 列表）
    for o in orders:
        lvid = o.get("locked_vehicle_id")
        if lvid is not None and lvid not in locked_vid_to_orders:
            errors.append(f"Order {o['order_id']} references non-existent locked_vehicle_id {lvid}")

    # 验证 subcategory_splits 可计算（检查各字段存在）
    for o in orders:
        assert "vehicle_subcategory" in o
        assert "spu_list" in o
        for spu in o["spu_list"]:
            assert "packing_type" in spu
            assert "quantity" in spu
            assert spu["packing_type"] in PACKING_TYPES

    # 验证 amount_limits 覆盖所有路线
    routes_in_orders = set()
    for o in orders:
        key = f"{o['destination_country']},{o['ship_method']}"
        routes_in_orders.add(key)
    for key in routes_in_orders:
        if key not in data["amount_limits"]:
            errors.append(f"Missing amount_limit for route {key}")

    if errors:
        print(f"  ❌ {filename}: {errors}")
        return False
    else:
        print(f"  ✅ {filename}: 验证通过 ({len(orders)} 订单, {len(locked_vid_to_orders)} 锁车ID)")
        return True


def main():
    # ── small_2: 20 订单，高危险品比例(~30%)，5 个子类别 ──────────────────────
    rng1 = random.Random(201)
    small_2 = generate_instance(
        rng=rng1,
        num_orders=20,
        num_subcategories=5,
        num_categories=2,
        hazard_ratio=0.30,           # 30% 危险品（显著高于 small_1 的 ~15%）
        locked_ratio=0.10,
        spu_per_order_range=(1, 6),
        spu_large=False,
        routes=[
            ("Germany",      "ROAD"),  # subcat 0
            ("Mexico",       "RAIL"),  # subcat 1
            ("India",        "SEA"),   # subcat 2
            ("Japan",        "SEA"),   # subcat 3
            ("USA",          "AIR"),   # subcat 4 — 新路线，small_1 没有
        ],
        target_vehicles=5,
        label="S2",
        pickup_configs=PICKUP_CONFIGS_DG,
    )
    out = OUT_DIR / "instance_small_2.json"
    out.write_text(json.dumps(small_2, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out}")
    validate_instance(small_2, "instance_small_2.json")

    # ── medium_2: 30 订单，8 个子类别（更多多样性）──────────────────────────
    rng2 = random.Random(314)
    medium_2 = generate_instance(
        rng=rng2,
        num_orders=30,
        num_subcategories=8,         # 8 个子类别（多样性显著提升）
        num_categories=3,
        hazard_ratio=0.13,
        locked_ratio=0.10,
        spu_per_order_range=(2, 7),
        spu_large=False,
        routes=[
            ("UK",           "ROAD"),
            ("Germany",      "ROAD"),
            ("France",       "ROAD"),
            ("Mexico",       "RAIL"),
            ("India",        "SEA"),
            ("South Africa", "RAIL"),
            ("Brazil",       "SEA"),
            ("Japan",        "SEA"),
        ],
        target_vehicles=7,
        label="M2",
        pickup_configs=PICKUP_CONFIGS_DG + PICKUP_CONFIGS_SZ,
    )
    out = OUT_DIR / "instance_medium_2.json"
    out.write_text(json.dumps(medium_2, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out}")
    validate_instance(medium_2, "instance_medium_2.json")

    # ── medium_3: 35 订单，高锁车比例 ~40% ──────────────────────────────────
    rng3 = random.Random(777)
    medium_3 = generate_instance(
        rng=rng3,
        num_orders=35,
        num_subcategories=5,
        num_categories=2,
        hazard_ratio=0.10,
        locked_ratio=0.40,           # ~40% 锁车 — 显著约束优化空间
        spu_per_order_range=(2, 6),
        spu_large=False,
        routes=[
            ("UK",    "ROAD"),
            ("Mexico", "RAIL"),
            ("India",  "SEA"),
            ("USA",    "AIR"),
            ("Brazil", "SEA"),
        ],
        target_vehicles=8,
        label="M3",
        pickup_configs=PICKUP_CONFIGS_DG,
    )
    out = OUT_DIR / "instance_medium_3.json"
    out.write_text(json.dumps(medium_3, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out}")
    validate_instance(medium_3, "instance_medium_3.json")

    # ── large_4: 50 订单，极端小件（大量 LOOSE_CTN，spu 数量极小）────────────
    rng4 = random.Random(555)
    large_4 = generate_instance(
        rng=rng4,
        num_orders=50,
        num_subcategories=4,
        num_categories=2,
        hazard_ratio=0.06,           # 少量危险品
        locked_ratio=0.08,
        spu_per_order_range=(1, 2),  # 每张订单 1-2 个 SPU 条（极端小件）
        spu_large=False,
        spu_small_only=True,         # 强制小件包装类型
        routes=[
            ("Germany", "ROAD"),
            ("Mexico",  "RAIL"),
            ("Japan",   "SEA"),
            ("USA",     "AIR"),
        ],
        target_vehicles=12,          # 小件多，需要更多小车（T5/T3）
        label="L4",
        pickup_configs=PICKUP_CONFIGS_DG,
    )
    out = OUT_DIR / "instance_large_4.json"
    out.write_text(json.dumps(large_4, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out}")
    validate_instance(large_4, "instance_large_4.json")

    # ── large_5: 50 订单，多城市（DG + SZ + GZ）────────────────────────────
    rng5 = random.Random(888)
    large_5 = generate_instance(
        rng=rng5,
        num_orders=50,
        num_subcategories=5,
        num_categories=3,
        hazard_ratio=0.14,
        locked_ratio=0.12,
        spu_per_order_range=(2, 7),
        spu_large=True,
        routes=[
            ("UK",           "ROAD"),
            ("Germany",      "ROAD"),
            ("India",        "SEA"),
            ("South Africa", "RAIL"),
            ("Japan",        "SEA"),
        ],
        target_vehicles=10,
        label="L5",
        pickup_configs=PICKUP_CONFIGS_ALL,  # DG + SZ + GZ 三城市混合
    )
    out = OUT_DIR / "instance_large_5.json"
    out.write_text(json.dumps(large_5, ensure_ascii=False, indent=2))
    print(f"  ✅ 写入 {out}")
    validate_instance(large_5, "instance_large_5.json")

    print("\n所有新实例生成完毕。")


if __name__ == "__main__":
    main()
