"""
Generate discriminative benchmark instances for Scion screening/validation.

Key design principle for discriminativeness:
  - Greedy groups by (category, subcategory, pickup_city). For Dongguan,
    max_pickups=2. If a subcategory has orders from 3 different Dongguan
    warehouses, greedy MUST create ≥2 vehicles per subcategory (split).
    VNS can then find improvements by reassigning orders, but not always —
    creating seed-dependent variation.
  - Moderate order counts (16-22) to stay in the "sweet spot": complex enough
    for greedy to be suboptimal, small enough for VNS to improve within budget.
  - Amount limits are intentionally loose so merging across vehicles is feasible.

Outputs:
  - instance_small_4.json  (18 orders, 3 DG warehouses, 4 subcats)
  - instance_small_5.json  (16 orders, 3 DG warehouses, tight capacity)
  - instance_small_6.json  (20 orders, 2 cities, 5 subcats)
  - instance_medium_4.json (25 orders, 4 subcats, mixed hazard)
"""
import json
import math
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent

# Three Dongguan warehouses — key to forcing greedy subcategory splits
PICKUPS_3DG = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
    ("Dongguan", "Guangdong", "DG_NORTH_WH"),
]
PICKUPS_2CITY = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
    ("Shenzhen", "Guangdong", "SZ_WH"),
]

LSPS = ["DB Schenker", "SF_INTL", "Maersk", "DHL"]
PACKING_TYPES = ["FULL_PLT", "FULL_CTN", "WOOD_CASE", "LOOSE_CTN", "TAILGATE"]

VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600, "is_hazard_special": True},
    "HQ40":    {"capacity": 40, "cost": 3300, "is_hazard_special": False},
    "T10":     {"capacity": 14, "cost": 1800, "is_hazard_special": False},
    "T5":      {"capacity":  6, "cost": 1200, "is_hazard_special": False},
    "T3":      {"capacity":  3, "cost":  800, "is_hazard_special": False},
}


def calc_pallets(spu_list):
    PALLET_TYPES = {"FULL_PLT", "TAILGATE", "WOOD_CASE"}
    p = sum(s["quantity"] for s in spu_list if s["packing_type"] in PALLET_TYPES)
    b = sum(s["quantity"] for s in spu_list if s["packing_type"] not in PALLET_TYPES)
    return p + math.ceil(b / 8)


def make_spu(rng, qty_range=(2, 8)):
    ptype = rng.choice(PACKING_TYPES)
    qty = rng.randint(*qty_range)
    return {"packing_type": ptype, "quantity": qty}


def generate(
    rng,
    orders_per_subcat,  # list of ints — one entry per subcategory
    pickup_configs,     # list of (city, province, warehouse)
    routes,             # list of (country, ship_method) — one per subcat
    hazard_subcats,     # set of subcat indices that can have hazard orders
    locked_ratio,
    spu_qty_range,
    label,
):
    """Generate an instance designed to be discriminative."""
    num_subcats = len(orders_per_subcat)
    num_cats = max(2, num_subcats // 2)

    orders = []
    order_idx = 0
    locked_ids = []

    for subcat, n_orders in enumerate(orders_per_subcat):
        cat = subcat % num_cats
        dest_country, ship_method = routes[subcat]

        # Distribute pickups ACROSS all configs within subcategory to force greedy splits
        for i in range(n_orders):
            oid = f"ORD_{order_idx:04d}"
            # Rotate through pickup configs to maximise warehouse diversity
            pickup_city, pickup_province, pickup_name = pickup_configs[i % len(pickup_configs)]
            lsp = rng.choice(LSPS)

            is_hazard = (subcat in hazard_subcats) and rng.random() < 0.4
            hazard_qty = rng.randint(1800, 3500) if is_hazard else 0

            num_spus = rng.randint(1, 2)
            spu_list = [make_spu(rng, spu_qty_range) for _ in range(num_spus)]

            # locked order?
            locked_vehicle_id = None
            if rng.random() < locked_ratio:
                lid = f"V_LOCK_{label}_{len(locked_ids)}"
                locked_ids.append(lid)
                locked_vehicle_id = lid

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
                "declaration_amount": round(rng.uniform(80000, 400000), 2),
                "lsp": lsp,
                "ship_method": ship_method,
                "destination_country": dest_country,
                "spu_list": spu_list,
                "locked_vehicle_id": locked_vehicle_id,
            })
            order_idx += 1

    # Loose amount_limits so VNS can merge without violating them
    route_amounts: dict[str, float] = {}
    for o in orders:
        key = f"{o['destination_country']},{o['ship_method']}"
        route_amounts[key] = route_amounts.get(key, 0) + o["declaration_amount"]

    amount_limits = {
        key: round(total * 2.5, 2)  # very loose — merging is always amount-feasible
        for key, total in route_amounts.items()
    }

    total_p = sum(calc_pallets(o["spu_list"]) for o in orders)
    min_v = math.ceil(total_p / 40)
    print(f"[{label}] orders={len(orders)}, pallets={total_p}, min_HQ40={min_v}")

    return {"orders": orders, "amount_limits": amount_limits, "vehicle_types": VEHICLE_TYPES}


def main():
    # ── small_4: 18 orders, 3 DG warehouses, 4 subcats ─────────────────────
    # With 3 warehouses and max_pickups=2, greedy must split subcategories
    rng = random.Random(1001)
    inst = generate(
        rng=rng,
        orders_per_subcat=[5, 5, 4, 4],       # 4 subcats, 18 orders
        pickup_configs=PICKUPS_3DG,             # 3 DG warehouses → forces splits
        routes=[
            ("UK",      "ROAD"),
            ("Germany", "ROAD"),
            ("Mexico",  "RAIL"),
            ("India",   "SEA"),
        ],
        hazard_subcats={0, 2},
        locked_ratio=0.10,
        spu_qty_range=(3, 7),
        label="S4",
    )
    (OUT_DIR / "instance_small_4.json").write_text(
        json.dumps(inst, ensure_ascii=False, indent=2)
    )
    print("  -> instance_small_4.json")

    # ── small_5: 16 orders, 3 DG warehouses, tighter capacity ───────────────
    rng = random.Random(2002)
    inst = generate(
        rng=rng,
        orders_per_subcat=[4, 4, 4, 4],        # 4 subcats, 16 orders
        pickup_configs=PICKUPS_3DG,
        routes=[
            ("France",       "ROAD"),
            ("Japan",        "SEA"),
            ("South Africa", "RAIL"),
            ("USA",          "AIR"),
        ],
        hazard_subcats={1, 3},
        locked_ratio=0.12,
        spu_qty_range=(4, 9),                  # larger SPU → tighter capacity
        label="S5",
    )
    (OUT_DIR / "instance_small_5.json").write_text(
        json.dumps(inst, ensure_ascii=False, indent=2)
    )
    print("  -> instance_small_5.json")

    # ── small_6: 20 orders, 2 cities, 5 subcats ─────────────────────────────
    # Mix of Dongguan + Shenzhen within subcategories
    rng = random.Random(3003)
    inst = generate(
        rng=rng,
        orders_per_subcat=[4, 4, 4, 4, 4],     # 5 subcats, 20 orders
        pickup_configs=PICKUPS_2CITY,            # 2 cities → region constraint also binds
        routes=[
            ("UK",      "ROAD"),
            ("Mexico",  "RAIL"),
            ("India",   "SEA"),
            ("Brazil",  "SEA"),
            ("USA",     "AIR"),
        ],
        hazard_subcats={0, 2, 4},
        locked_ratio=0.10,
        spu_qty_range=(2, 6),
        label="S6",
    )
    (OUT_DIR / "instance_small_6.json").write_text(
        json.dumps(inst, ensure_ascii=False, indent=2)
    )
    print("  -> instance_small_6.json")

    # ── medium_4: 25 orders, 4 subcats, mixed hazard, 3 DG warehouses ───────
    rng = random.Random(4004)
    inst = generate(
        rng=rng,
        orders_per_subcat=[7, 6, 6, 6],        # 4 subcats, 25 orders
        pickup_configs=PICKUPS_3DG,
        routes=[
            ("UK",           "ROAD"),
            ("Germany",      "ROAD"),
            ("India",        "SEA"),
            ("South Africa", "RAIL"),
        ],
        hazard_subcats={0, 1, 3},
        locked_ratio=0.10,
        spu_qty_range=(2, 6),
        label="M4",
    )
    (OUT_DIR / "instance_medium_4.json").write_text(
        json.dumps(inst, ensure_ascii=False, indent=2)
    )
    print("  -> instance_medium_4.json")

    print("\nDone.")


if __name__ == "__main__":
    main()
