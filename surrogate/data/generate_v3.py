#!/usr/bin/env python3
"""
generate_v3.py — High-quality benchmark instance generator for Scion v0.1 full experiment.

Upgrades over v2:
  - Screening starts at medium (50+ orders), not small
  - Validation uses large (120+) and xlarge (250+)
  - Frozen holdout uses xlarge (350+) and xxlarge (500-800)
  - More diversity axes exercised per instance
  - Total 24 instances for thorough operator evaluation

Usage:
  python generate_v3.py [--validate] [--master-seed 20260408]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Reuse constants from generate_v2
# ---------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent

DG_WAREHOUSES = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
    ("Dongguan", "Guangdong", "DG_NORTH_WH"),
    ("Dongguan", "Guangdong", "DG_SOUTH_WH"),
    ("Dongguan", "Guangdong", "DG_WEST_WH"),
]

SZ_WAREHOUSES = [
    ("Shenzhen", "Guangdong", "SZ_WH"),
    ("Shenzhen", "Guangdong", "SZ_FG_WH"),
    ("Shenzhen", "Guangdong", "SZ_NORTH_WH"),
]

LSPS = ["DB Schenker", "SF_INTL", "Maersk", "DHL", "COSCO", "Kuehne+Nagel"]
PACKING_TYPES = ["FULL_PLT", "FULL_CTN", "WOOD_CASE", "LOOSE_CTN", "TAILGATE"]

DESTINATION_ROUTES = [
    ("UK", "ROAD"), ("Germany", "ROAD"), ("France", "ROAD"),
    ("Mexico", "RAIL"), ("India", "SEA"), ("India", "AIR"),
    ("South Africa", "RAIL"), ("Brazil", "SEA"), ("Japan", "SEA"),
    ("USA", "AIR"), ("Australia", "SEA"), ("Canada", "ROAD"),
]

VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600, "is_hazard_special": True},
    "HQ40":    {"capacity": 40, "cost": 3300, "is_hazard_special": False},
    "T10":     {"capacity": 14, "cost": 1800, "is_hazard_special": False},
    "T5":      {"capacity":  6, "cost": 1200, "is_hazard_special": False},
    "T3":      {"capacity":  3, "cost":  800, "is_hazard_special": False},
}


def calc_pallets(spu_list: list[dict]) -> int:
    pallet_types = {"FULL_PLT", "TAILGATE", "WOOD_CASE"}
    pallets = sum(s["quantity"] for s in spu_list if s["packing_type"] in pallet_types)
    boxes = sum(s["quantity"] for s in spu_list if s["packing_type"] not in pallet_types)
    return pallets + math.ceil(boxes / 8) if boxes > 0 else pallets


@dataclass
class InstanceSpec:
    name: str
    role: str
    tier: str
    master_seed: int
    num_subcategories: int
    orders_per_subcat: list[int]
    num_dg_warehouses: int
    city_mix: str
    hazard_ratio: float
    locked_ratio: float
    spu_qty_range: tuple[int, int]
    num_spus_range: tuple[int, int]
    capacity_pressure: str
    description: str = ""


def build_pickup_configs(num_dg: int, city_mix: str) -> list[tuple[str, str, str]]:
    dg = DG_WAREHOUSES[:num_dg]
    if city_mix == "dg_only":
        return dg
    elif city_mix == "dg_heavy":
        return dg + SZ_WAREHOUSES[:1]
    elif city_mix == "mixed":
        return dg + SZ_WAREHOUSES[:max(1, num_dg // 2)]
    elif city_mix == "sz_heavy":
        return DG_WAREHOUSES[:2] + SZ_WAREHOUSES[:2]
    else:
        return dg


def generate_instance(spec: InstanceSpec) -> dict:
    rng = random.Random(spec.master_seed)
    pickups = build_pickup_configs(spec.num_dg_warehouses, spec.city_mix)
    num_cats = max(2, (spec.num_subcategories + 1) // 2)

    routes = [DESTINATION_ROUTES[i % len(DESTINATION_ROUTES)]
              for i in range(spec.num_subcategories)]
    rng.shuffle(routes)

    pressure_multiplier = {
        "loose": 0.6, "moderate": 1.0, "tight": 1.4, "overflow": 1.8,
    }.get(spec.capacity_pressure, 1.0)

    orders: list[dict] = []
    locked_ids: list[str] = []
    order_idx = 0

    for subcat_idx, n_orders in enumerate(spec.orders_per_subcat):
        cat = subcat_idx % num_cats
        dest_country, ship_method = routes[subcat_idx]

        for i in range(n_orders):
            oid = f"ORD_{order_idx:04d}"
            pickup_city, pickup_province, pickup_name = pickups[i % len(pickups)]
            lsp = rng.choice(LSPS)
            is_hazard = rng.random() < spec.hazard_ratio
            hazard_qty = rng.randint(1500, 3500) if is_hazard else 0

            num_spus = rng.randint(*spec.num_spus_range)
            spu_list = []
            for _ in range(num_spus):
                base_qty = rng.randint(*spec.spu_qty_range)
                adjusted_qty = max(1, round(base_qty * pressure_multiplier))
                spu_list.append({
                    "packing_type": rng.choice(PACKING_TYPES),
                    "quantity": adjusted_qty,
                })

            locked_vehicle_id = None
            if rng.random() < spec.locked_ratio:
                lid = f"V_LOCK_{spec.name}_{len(locked_ids)}"
                locked_ids.append(lid)
                locked_vehicle_id = lid

            orders.append({
                "order_id": oid,
                "vehicle_category": cat,
                "vehicle_subcategory": subcat_idx,
                "urgent": rng.random() < 0.08,
                "hazard_flag": is_hazard,
                "hazard_quantity": hazard_qty,
                "pickup_name": pickup_name,
                "pickup_province": pickup_province,
                "pickup_city": pickup_city,
                "declaration_amount": round(rng.uniform(50000, 500000), 2),
                "lsp": lsp,
                "ship_method": ship_method,
                "destination_country": dest_country,
                "spu_list": spu_list,
                "locked_vehicle_id": locked_vehicle_id,
            })
            order_idx += 1

    route_amounts: dict[str, float] = {}
    for o in orders:
        key = f"{o['destination_country']},{o['ship_method']}"
        route_amounts[key] = route_amounts.get(key, 0) + o["declaration_amount"]

    amount_limits = {
        key: round(total * 2.5, 2)
        for key, total in route_amounts.items()
    }

    total_pallets = sum(calc_pallets(o["spu_list"]) for o in orders)
    min_vehicles = math.ceil(total_pallets / 40)

    subcat_dg_wh: dict[int, set] = {}
    for o in orders:
        sc = o["vehicle_subcategory"]
        if o["pickup_city"] == "Dongguan":
            subcat_dg_wh.setdefault(sc, set()).add(o["pickup_name"])

    expected_splits = sum(
        max(0, math.ceil(len(whs) / 2) - 1)
        for whs in subcat_dg_wh.values()
    )

    meta = {
        "generator": "generate_v3.py",
        "spec_name": spec.name,
        "role": spec.role,
        "tier": spec.tier,
        "master_seed": spec.master_seed,
        "num_orders": len(orders),
        "num_subcategories": spec.num_subcategories,
        "num_dg_warehouses": spec.num_dg_warehouses,
        "city_mix": spec.city_mix,
        "hazard_ratio": spec.hazard_ratio,
        "locked_ratio": spec.locked_ratio,
        "capacity_pressure": spec.capacity_pressure,
        "total_pallets": total_pallets,
        "min_vehicles_hq40": min_vehicles,
        "expected_greedy_splits": expected_splits,
        "description": spec.description,
    }

    print(f"[{spec.name}] orders={len(orders)}, subcats={spec.num_subcategories}, "
          f"pallets={total_pallets}, min_HQ40={min_vehicles}, "
          f"est_splits={expected_splits}, dg_wh={spec.num_dg_warehouses}")

    return {"orders": orders, "amount_limits": amount_limits,
            "vehicle_types": VEHICLE_TYPES, "_meta": meta}


# ---------------------------------------------------------------------------
# V3 Instance Specifications — 24 instances
# ---------------------------------------------------------------------------

def build_all_specs(master_seed: int = 20260408) -> list[InstanceSpec]:
    rng = random.Random(master_seed)
    specs: list[InstanceSpec] = []

    def next_seed() -> int:
        return rng.randint(10000, 99999)

    # ================================================================
    # SCREENING (10): 6 medium (50-80) + 4 large (100-150)
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v3_scr_m01", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[12, 11, 11, 10, 10],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.05,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Medium baseline, 54 orders, 3 DG warehouses.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_m02", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[12, 11, 10, 10, 10, 9],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.15, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="6 subcats, 4 DG warehouses, 15% hazard.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_m03", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=4,
        orders_per_subcat=[18, 16, 14, 12],
        num_dg_warehouses=3, city_mix="mixed",
        hazard_ratio=0.05, locked_ratio=0.25,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="4 subcats, deep order counts, 25% locked.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_m04", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[14, 13, 12, 12, 11],
        num_dg_warehouses=5, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(3, 7), num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="5 DG warehouses, tight capacity, max split pressure.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_m05", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=7,
        orders_per_subcat=[10, 10, 9, 9, 8, 8, 7],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.20, locked_ratio=0.0,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="7 subcats, 20% hazard, high subcat diversity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_m06", role="screening", tier="medium",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[16, 14, 14, 12, 10],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.08, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Mixed city, 4 DG warehouses, balanced complexity.",
    ))

    # 4 large screening (100-150 orders)
    specs.append(InstanceSpec(
        name="instance_v3_scr_l01", role="screening", tier="large",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[22, 20, 18, 17, 16, 15],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Large screening, 108 orders, 6 subcats.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_l02", role="screening", tier="large",
        master_seed=next_seed(), num_subcategories=8,
        orders_per_subcat=[18, 17, 16, 15, 14, 13, 12, 11],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.12, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Large screening, 116 orders, 8 subcats, 4 DG.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_l03", role="screening", tier="large",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[30, 28, 26, 24, 22],
        num_dg_warehouses=5, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.05,
        spu_qty_range=(3, 6), num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Large screening, 130 orders, 5 DG, tight capacity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_scr_l04", role="screening", tier="large",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[26, 24, 24, 22, 20, 18],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.18, locked_ratio=0.30,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Large screening, 134 orders, 30% locked, 18% hazard.",
    ))

    # ================================================================
    # VALIDATION (6): 4 large (120-200) + 2 xlarge (250-350)
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v3_val_l01", role="validation", tier="large",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[24, 22, 22, 20, 18, 16],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation large, 122 orders, balanced baseline.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_val_l02", role="validation", tier="large",
        master_seed=next_seed(), num_subcategories=8,
        orders_per_subcat=[22, 20, 20, 18, 18, 16, 15, 14],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.15, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation large, 143 orders, 8 subcats, high diversity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_val_l03", role="validation", tier="large",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[40, 36, 34, 30, 28],
        num_dg_warehouses=5, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.05,
        spu_qty_range=(3, 6), num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Validation large, 168 orders, 5 DG, tight capacity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_val_l04", role="validation", tier="large",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[35, 32, 30, 28, 26, 24],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.20, locked_ratio=0.35,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Validation large, 175 orders, 35% locked, 20% hazard.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_val_x01", role="validation", tier="xlarge",
        master_seed=next_seed(), num_subcategories=7,
        orders_per_subcat=[45, 42, 40, 38, 35, 30, 28],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.12, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation xlarge, 258 orders, 7 subcats.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_val_x02", role="validation", tier="xlarge",
        master_seed=next_seed(), num_subcategories=8,
        orders_per_subcat=[50, 45, 40, 38, 35, 32, 28, 25],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.10, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation xlarge, 293 orders, max diversity.",
    ))

    # ================================================================
    # FROZEN HOLDOUT (4): 2 xlarge (350-500) + 2 xxlarge (500-800)
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v3_fro_x01", role="frozen", tier="xlarge",
        master_seed=next_seed(), num_subcategories=7,
        orders_per_subcat=[60, 55, 52, 50, 48, 44, 40],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.12, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xlarge, 349 orders, balanced holdout.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_x02", role="frozen", tier="xlarge",
        master_seed=next_seed(), num_subcategories=8,
        orders_per_subcat=[65, 60, 58, 55, 50, 45, 40, 35],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.15, locked_ratio=0.20,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xlarge, 408 orders, 5 DG, high difficulty.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_xx01", role="frozen", tier="xxlarge",
        master_seed=next_seed(), num_subcategories=8,
        orders_per_subcat=[85, 80, 75, 70, 65, 60, 55, 50],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xxlarge, 540 orders, stress test at scale.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_xx02", role="frozen", tier="xxlarge",
        master_seed=next_seed(), num_subcategories=10,
        orders_per_subcat=[90, 85, 80, 75, 70, 65, 60, 55, 50, 45],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.12, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xxlarge, 675 orders, 10 subcats, maximum complexity.",
    ))

    # ================================================================
    # CANARY (2): medium
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v3_can_m01", role="canary", tier="medium",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[10, 10, 9, 9, 8],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Canary medium, 46 orders, clean regression check.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_can_m02", role="canary", tier="medium",
        master_seed=next_seed(), num_subcategories=5,
        orders_per_subcat=[12, 11, 10, 10, 9],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.15, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Canary medium with hazard + locked.",
    ))

    # ================================================================
    # FROZEN HOLDOUT EXPANSION (4 additional): 2 large + 2 xlarge
    # Added in Sprint E2 T05 to improve statistical power and size diversity
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v3_fro_l01", role="frozen", tier="large",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[38, 35, 32, 30, 28, 25],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.12,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen large, 188 orders, 6 subcats, catches scale-limited operators.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_l02", role="frozen", tier="large",
        master_seed=next_seed(), num_subcategories=7,
        orders_per_subcat=[40, 36, 33, 30, 28, 26, 22],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.18, locked_ratio=0.08,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="tight",
        description="Frozen large, 215 orders, 7 subcats, tight capacity + high hazard.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_x03", role="frozen", tier="xlarge",
        master_seed=next_seed(), num_subcategories=6,
        orders_per_subcat=[70, 65, 60, 58, 55, 52],
        num_dg_warehouses=3, city_mix="sz_heavy",
        hazard_ratio=0.08, locked_ratio=0.25,
        spu_qty_range=(3, 7), num_spus_range=(2, 4),
        capacity_pressure="tight",
        description="Frozen xlarge, 360 orders, SZ-heavy, high locked ratio, tight capacity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v3_fro_x04", role="frozen", tier="xlarge",
        master_seed=next_seed(), num_subcategories=9,
        orders_per_subcat=[60, 55, 52, 50, 48, 45, 42, 40, 38],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.20, locked_ratio=0.05,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xlarge, 430 orders, 9 subcats, very high hazard, max subcat diversity.",
    ))

    return specs


# ---------------------------------------------------------------------------
# Validation (reuse from v2)
# ---------------------------------------------------------------------------

def validate_instance(
    filepath: Path,
    seeds: list[int] = [42, 137, 1042],
    max_iter: int = 150,
    time_limit_sec: int = 180,
) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import Config
    from solver import load_instance, solve
    from oracle import recompute_objective, check_feasibility
    from greedy_init import greedy_init

    instance = load_instance(str(filepath))
    greedy_sol = greedy_init(instance)
    feas = check_feasibility(greedy_sol, instance, instance.phase)
    greedy_obj = recompute_objective(greedy_sol, instance)

    report = {
        "file": filepath.name,
        "num_orders": len(instance.orders),
        "greedy_feasible": feas.is_feasible,
        "greedy_splits": greedy_obj.subcategory_splits,
        "greedy_cost": greedy_obj.total_cost,
        "greedy_violations": feas.violations if not feas.is_feasible else [],
        "seed_results": {},
        "is_discriminative": False,
    }

    if not feas.is_feasible:
        print(f"  FAIL: greedy init not feasible: {feas.violations[:2]}")
        return report

    results = []
    for seed in seeds:
        cfg = Config()
        cfg.random_seed = seed
        cfg.max_iterations = max_iter
        cfg.no_improve_limit = 30

        t0 = time.time()
        sol = solve(instance, cfg)
        elapsed = time.time() - t0
        obj = sol.objective
        report["seed_results"][f"seed_{seed}"] = {
            "splits": obj.subcategory_splits,
            "cost": obj.total_cost,
            "time_sec": round(elapsed, 2),
        }
        results.append((obj.subcategory_splits, obj.total_cost))
        print(f"  seed={seed}: splits={obj.subcategory_splits}, "
              f"cost={obj.total_cost}, time={elapsed:.1f}s")

    unique_results = set(results)
    report["unique_results"] = len(unique_results)
    report["is_discriminative"] = len(unique_results) >= 2

    if report["is_discriminative"]:
        print(f"  ✓ DISCRIMINATIVE ({len(unique_results)} unique results)")
    else:
        print(f"  ✗ NOT discriminative (all seeds produce same result)")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v3 benchmark instances for Scion")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--master-seed", type=int, default=20260408)
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--validate-seeds", type=str, default="42,137,1042")
    parser.add_argument("--max-iter", type=int, default=150)
    args = parser.parse_args()

    print("=" * 70)
    print("Scion v3 Instance Generator — High-Quality Benchmark Suite")
    print("=" * 70)

    specs = build_all_specs(args.master_seed)
    if args.only:
        specs = [s for s in specs if args.only in s.name]
        print(f"Filtered to {len(specs)} instances matching '{args.only}'")

    generated_files: list[Path] = []
    for spec in specs:
        print(f"\n--- Generating {spec.name} ({spec.role}/{spec.tier}) ---")
        instance_data = generate_instance(spec)
        filepath = OUT_DIR / f"{spec.name}.json"
        filepath.write_text(json.dumps(instance_data, ensure_ascii=False, indent=2))
        generated_files.append(filepath)

    print(f"\n{'=' * 70}")
    print(f"Generated {len(generated_files)} instances.")

    if args.validate:
        val_seeds = [int(s) for s in args.validate_seeds.split(",")]
        print(f"\n{'=' * 70}")
        print(f"Validating instances (seeds={val_seeds}, max_iter={args.max_iter})")
        print(f"{'=' * 70}")

        reports: list[dict] = []
        for filepath in generated_files:
            print(f"\n--- Validating {filepath.name} ---")
            report = validate_instance(filepath, seeds=val_seeds, max_iter=args.max_iter)
            reports.append(report)

        print(f"\n{'=' * 70}")
        print("VALIDATION SUMMARY")
        print(f"{'=' * 70}")
        discriminative = sum(1 for r in reports if r["is_discriminative"])
        feasible = sum(1 for r in reports if r["greedy_feasible"])
        print(f"Greedy-feasible: {feasible}/{len(reports)}")
        print(f"Discriminative:  {discriminative}/{len(reports)}")

        for r in reports:
            status = "✓" if r["is_discriminative"] else "✗"
            feas = "F" if r["greedy_feasible"] else "X"
            print(f"  {status} [{feas}] {r['file']:40s} orders={r['num_orders']:4d} "
                  f"greedy_splits={r['greedy_splits']}, unique_results={r.get('unique_results', 0)}")

        report_path = OUT_DIR / "validation_report_v3.json"
        report_path.write_text(json.dumps(reports, indent=2))
        print(f"\nValidation report saved to {report_path.name}")


if __name__ == "__main__":
    main()
