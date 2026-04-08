#!/usr/bin/env python3
"""
generate_v2.py — Comprehensive discriminative benchmark instance generator for Scion.

Design principles:
  1. Greedy groups by (category, subcategory, pickup_city). For Dongguan,
     max_pickups=2. If a subcategory has orders from ≥3 DG warehouses,
     greedy MUST create ≥2 vehicles → subcategory splits.
  2. VNS can improve by reassigning orders to reduce splits, but the
     improvement depends on random seed → seed-dependent trajectories.
  3. Diversity axes: subcategory count, hazard ratio, locked ratio,
     DG warehouse count, city mix, capacity pressure.

Instance naming convention:
  instance_scr_s01.json  — screening, small, #01
  instance_scr_m01.json  — screening, medium, #01
  instance_val_m01.json  — validation, medium, #01
  instance_val_l01.json  — validation, large, #01
  instance_fro_l01.json  — frozen holdout, large, #01
  instance_fro_x01.json  — frozen holdout, xlarge, #01
  instance_can_s01.json  — canary, small, #01

Usage:
  python generate_v2.py [--validate] [--master-seed 12345]
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
# Constants
# ---------------------------------------------------------------------------

OUT_DIR = Path(__file__).parent

# Dongguan warehouses — having ≥3 forces greedy splits (max_pickups=2 in DG)
DG_WAREHOUSES = [
    ("Dongguan", "Guangdong", "SKD_WH"),
    ("Dongguan", "Guangdong", "FG_CENTRAL_WH"),
    ("Dongguan", "Guangdong", "DG_NORTH_WH"),
    ("Dongguan", "Guangdong", "DG_SOUTH_WH"),
    ("Dongguan", "Guangdong", "DG_WEST_WH"),
]

# Shenzhen warehouses
SZ_WAREHOUSES = [
    ("Shenzhen", "Guangdong", "SZ_WH"),
    ("Shenzhen", "Guangdong", "SZ_FG_WH"),
    ("Shenzhen", "Guangdong", "SZ_NORTH_WH"),
]

LSPS = ["DB Schenker", "SF_INTL", "Maersk", "DHL", "COSCO", "Kuehne+Nagel"]
PACKING_TYPES = ["FULL_PLT", "FULL_CTN", "WOOD_CASE", "LOOSE_CTN", "TAILGATE"]

DESTINATION_ROUTES = [
    ("UK", "ROAD"),
    ("Germany", "ROAD"),
    ("France", "ROAD"),
    ("Mexico", "RAIL"),
    ("India", "SEA"),
    ("India", "AIR"),
    ("South Africa", "RAIL"),
    ("Brazil", "SEA"),
    ("Japan", "SEA"),
    ("USA", "AIR"),
    ("Australia", "SEA"),
    ("Canada", "ROAD"),
]

VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600, "is_hazard_special": True},
    "HQ40":    {"capacity": 40, "cost": 3300, "is_hazard_special": False},
    "T10":     {"capacity": 14, "cost": 1800, "is_hazard_special": False},
    "T5":      {"capacity":  6, "cost": 1200, "is_hazard_special": False},
    "T3":      {"capacity":  3, "cost":  800, "is_hazard_special": False},
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def calc_pallets(spu_list: list[dict]) -> int:
    """Calculate total pallets from SPU list (consistent with models.py)."""
    pallet_types = {"FULL_PLT", "TAILGATE", "WOOD_CASE"}
    pallets = sum(s["quantity"] for s in spu_list if s["packing_type"] in pallet_types)
    boxes = sum(s["quantity"] for s in spu_list if s["packing_type"] not in pallet_types)
    return pallets + math.ceil(boxes / 8) if boxes > 0 else pallets


def make_spu(rng: random.Random, qty_range: tuple[int, int] = (2, 6)) -> dict:
    """Generate a single random SPU entry."""
    return {
        "packing_type": rng.choice(PACKING_TYPES),
        "quantity": rng.randint(*qty_range),
    }


# ---------------------------------------------------------------------------
# Instance specification
# ---------------------------------------------------------------------------

@dataclass
class InstanceSpec:
    """Specification for a single benchmark instance."""
    name: str                   # Output filename (without .json)
    role: str                   # screening / validation / frozen / canary
    tier: str                   # small / medium / large / xlarge
    master_seed: int            # Deterministic seed for this instance
    num_subcategories: int      # Number of vehicle subcategories (2-8)
    orders_per_subcat: list[int]  # Orders per subcategory
    num_dg_warehouses: int      # Number of Dongguan warehouses to use (2-5)
    city_mix: str               # "dg_only" | "dg_heavy" | "mixed" | "sz_heavy"
    hazard_ratio: float         # Fraction of orders that are hazardous
    locked_ratio: float         # Fraction of orders locked to a vehicle
    spu_qty_range: tuple[int, int]  # Range for SPU quantity per item
    num_spus_range: tuple[int, int]  # Range for number of SPU items per order
    capacity_pressure: str      # "loose" | "moderate" | "tight" | "overflow"
    description: str = ""       # Human-readable description


def build_pickup_configs(
    num_dg: int,
    city_mix: str,
) -> list[tuple[str, str, str]]:
    """Build pickup configuration based on DG warehouse count and city mix."""
    dg = DG_WAREHOUSES[:num_dg]
    if city_mix == "dg_only":
        return dg
    elif city_mix == "dg_heavy":
        # 75% DG, 25% SZ
        return dg + SZ_WAREHOUSES[:1]
    elif city_mix == "mixed":
        # Roughly equal DG and SZ
        return dg + SZ_WAREHOUSES[:max(1, num_dg // 2)]
    elif city_mix == "sz_heavy":
        # More SZ than DG
        return DG_WAREHOUSES[:2] + SZ_WAREHOUSES[:2]
    else:
        return dg


def generate_instance(spec: InstanceSpec) -> dict:
    """Generate a single instance from its specification.

    Key design choice for discriminativeness:
      Orders within each subcategory are distributed across ALL pickup configs
      in round-robin fashion. When a DG subcategory has ≥3 warehouses,
      the greedy init (max_pickups=2 for DG) MUST split that subcategory
      across multiple vehicles. VNS can then try to improve by reassigning
      orders, creating seed-dependent trajectories.
    """
    rng = random.Random(spec.master_seed)
    pickups = build_pickup_configs(spec.num_dg_warehouses, spec.city_mix)
    num_cats = max(2, (spec.num_subcategories + 1) // 2)

    # Assign routes to subcategories
    routes = [DESTINATION_ROUTES[i % len(DESTINATION_ROUTES)]
              for i in range(spec.num_subcategories)]
    rng.shuffle(routes)

    # Adjust SPU quantities based on capacity pressure
    pressure_multiplier = {
        "loose": 0.6,
        "moderate": 1.0,
        "tight": 1.4,
        "overflow": 1.8,
    }.get(spec.capacity_pressure, 1.0)

    orders: list[dict] = []
    locked_ids: list[str] = []
    order_idx = 0

    for subcat_idx, n_orders in enumerate(spec.orders_per_subcat):
        cat = subcat_idx % num_cats
        dest_country, ship_method = routes[subcat_idx]

        # Separate DG and SZ pickups for this subcategory
        dg_pickups = [p for p in pickups if p[0] == "Dongguan"]
        sz_pickups = [p for p in pickups if p[0] == "Shenzhen"]

        for i in range(n_orders):
            oid = f"ORD_{order_idx:04d}"

            # Distribute across all pickups in round-robin to maximize
            # warehouse diversity within each subcategory
            pickup_city, pickup_province, pickup_name = pickups[i % len(pickups)]

            lsp = rng.choice(LSPS)

            # Hazard determination
            is_hazard = rng.random() < spec.hazard_ratio
            hazard_qty = rng.randint(1500, 3500) if is_hazard else 0

            # SPU generation with capacity pressure adjustment
            num_spus = rng.randint(*spec.num_spus_range)
            spu_list = []
            for _ in range(num_spus):
                base_qty = rng.randint(*spec.spu_qty_range)
                adjusted_qty = max(1, round(base_qty * pressure_multiplier))
                spu_list.append({
                    "packing_type": rng.choice(PACKING_TYPES),
                    "quantity": adjusted_qty,
                })

            # Locked vehicle assignment
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

    # Amount limits — intentionally loose so VNS merges are feasible
    route_amounts: dict[str, float] = {}
    for o in orders:
        key = f"{o['destination_country']},{o['ship_method']}"
        route_amounts[key] = route_amounts.get(key, 0) + o["declaration_amount"]

    amount_limits = {
        key: round(total * 2.5, 2)
        for key, total in route_amounts.items()
    }

    # Compute stats
    total_pallets = sum(calc_pallets(o["spu_list"]) for o in orders)
    min_vehicles = math.ceil(total_pallets / 40)

    # Count DG warehouses per subcategory to estimate expected splits
    subcat_dg_wh: dict[int, set] = {}
    for o in orders:
        sc = o["vehicle_subcategory"]
        if o["pickup_city"] == "Dongguan":
            subcat_dg_wh.setdefault(sc, set()).add(o["pickup_name"])

    expected_splits = sum(
        max(0, math.ceil(len(whs) / 2) - 1)
        for whs in subcat_dg_wh.values()
    )

    # Metadata for the instance
    meta = {
        "generator": "generate_v2.py",
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

    return {
        "orders": orders,
        "amount_limits": amount_limits,
        "vehicle_types": VEHICLE_TYPES,
        "_meta": meta,
    }


# ---------------------------------------------------------------------------
# Instance specifications — 20 total instances
# ---------------------------------------------------------------------------

def build_all_specs(master_seed: int = 20260408) -> list[InstanceSpec]:
    """Build all instance specifications with deterministic seeds."""
    rng = random.Random(master_seed)
    specs: list[InstanceSpec] = []

    def next_seed() -> int:
        return rng.randint(10000, 99999)

    # ========================================================================
    # SCREENING instances (8 total: 4 small, 4 medium)
    # Must have proven seed-dependent VNS results
    # ========================================================================

    # scr_s01: Classic 3-DG split scenario, 4 subcategories
    specs.append(InstanceSpec(
        name="instance_scr_s01",
        role="screening", tier="small",
        master_seed=next_seed(),
        num_subcategories=4,
        orders_per_subcat=[5, 5, 5, 5],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.0,
        locked_ratio=0.0,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Pure DG, 3 warehouses, 4 subcats, no hazard/locked. "
                    "Clean split scenario for baseline screening.",
    ))

    # scr_s02: 3-DG warehouses, 4 subcategories, deeper order counts
    specs.append(InstanceSpec(
        name="instance_scr_s02",
        role="screening", tier="small",
        master_seed=next_seed(),
        num_subcategories=4,
        orders_per_subcat=[6, 6, 6, 6],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.10,
        locked_ratio=0.0,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="3 DG warehouses, 4 subcats, 24 orders. "
                    "Deep order counts per subcat maximize VNS search space.",
    ))

    # scr_s03: Mixed cities, 5 subcategories, some locked
    specs.append(InstanceSpec(
        name="instance_scr_s03",
        role="screening", tier="small",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[4, 4, 4, 4, 4],
        num_dg_warehouses=3,
        city_mix="dg_heavy",
        hazard_ratio=0.05,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="DG-heavy mixed city, 5 subcats, 10% locked. "
                    "Region constraint adds complexity.",
    ))

    # scr_s04: Moderate capacity, 3 DG warehouses, 5 subcategories
    specs.append(InstanceSpec(
        name="instance_scr_s04",
        role="screening", tier="small",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[5, 5, 5, 5, 5],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.0,
        locked_ratio=0.0,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="5 subcategories, 25 orders, moderate capacity. "
                    "High subcat count amplifies split opportunities.",
    ))

    # scr_m01: Medium screening, 5 subcats, 3 DG warehouses
    specs.append(InstanceSpec(
        name="instance_scr_m01",
        role="screening", tier="medium",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[8, 8, 7, 7, 6],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.10,
        locked_ratio=0.05,
        spu_qty_range=(2, 6),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Medium screening baseline. 5 subcats, 36 orders. "
                    "Good balance of splits and VNS improvement opportunity.",
    ))

    # scr_m02: Medium, 6 subcats, 4 DG warehouses, mixed hazard
    specs.append(InstanceSpec(
        name="instance_scr_m02",
        role="screening", tier="medium",
        master_seed=next_seed(),
        num_subcategories=6,
        orders_per_subcat=[7, 7, 6, 6, 6, 5],
        num_dg_warehouses=4,
        city_mix="dg_heavy",
        hazard_ratio=0.15,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Medium with 6 subcats, 4 DG warehouses, 15% hazard. "
                    "High subcategory diversity with hazard complexity.",
    ))

    # scr_m03: Medium, fewer subcats but more orders each, locked vehicles
    specs.append(InstanceSpec(
        name="instance_scr_m03",
        role="screening", tier="medium",
        master_seed=next_seed(),
        num_subcategories=4,
        orders_per_subcat=[12, 10, 10, 8],
        num_dg_warehouses=3,
        city_mix="mixed",
        hazard_ratio=0.05,
        locked_ratio=0.25,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Medium, 4 subcats with deep order counts, 25% locked. "
                    "Locked vehicles constrain VNS search space.",
    ))

    # scr_m04: Medium, tight capacity, 5 DG warehouses
    specs.append(InstanceSpec(
        name="instance_scr_m04",
        role="screening", tier="medium",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[10, 9, 8, 8, 7],
        num_dg_warehouses=5,
        city_mix="dg_only",
        hazard_ratio=0.0,
        locked_ratio=0.0,
        spu_qty_range=(3, 7),
        num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Medium, 5 DG warehouses, tight capacity, no hazard/locked. "
                    "Maximum split pressure, capacity-constrained merging.",
    ))

    # ========================================================================
    # VALIDATION instances (6 total: 2 medium, 4 large)
    # ========================================================================

    # val_m01: Validation medium with high hazard
    specs.append(InstanceSpec(
        name="instance_val_m01",
        role="validation", tier="medium",
        master_seed=next_seed(),
        num_subcategories=6,
        orders_per_subcat=[8, 8, 7, 7, 7, 6],
        num_dg_warehouses=3,
        city_mix="dg_heavy",
        hazard_ratio=0.30,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation medium, 30% hazard. HQ40_DG vehicle type "
                    "selection interacts with subcategory split minimization.",
    ))

    # val_m02: Validation medium, mixed cities with 3 DG warehouses
    specs.append(InstanceSpec(
        name="instance_val_m02",
        role="validation", tier="medium",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[10, 9, 9, 8, 8],
        num_dg_warehouses=3,
        city_mix="mixed",
        hazard_ratio=0.05,
        locked_ratio=0.15,
        spu_qty_range=(2, 6),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation medium, mixed city with 3 DG warehouses. "
                    "DG splits forced while SZ max_pickups=3 adds flexibility.",
    ))

    # val_l01: Validation large, 6 subcats, moderate complexity
    specs.append(InstanceSpec(
        name="instance_val_l01",
        role="validation", tier="large",
        master_seed=next_seed(),
        num_subcategories=6,
        orders_per_subcat=[16, 16, 15, 14, 14, 13],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.10,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation large, 88 orders, 6 subcats. "
                    "Core validation instance with balanced complexity.",
    ))

    # val_l02: Validation large, 8 subcats, diverse
    specs.append(InstanceSpec(
        name="instance_val_l02",
        role="validation", tier="large",
        master_seed=next_seed(),
        num_subcategories=8,
        orders_per_subcat=[14, 14, 13, 12, 12, 12, 11, 10],
        num_dg_warehouses=4,
        city_mix="mixed",
        hazard_ratio=0.15,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation large, 98 orders, 8 subcats, 4 DG warehouses. "
                    "Maximum subcategory diversity for operator sensitivity testing.",
    ))

    # val_l03: Validation large, tight capacity, 5 DG warehouses
    specs.append(InstanceSpec(
        name="instance_val_l03",
        role="validation", tier="large",
        master_seed=next_seed(),
        num_subcategories=5,
        orders_per_subcat=[20, 20, 18, 16, 16],
        num_dg_warehouses=5,
        city_mix="dg_only",
        hazard_ratio=0.0,
        locked_ratio=0.05,
        spu_qty_range=(3, 6),
        num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Validation large, 90 orders, 5 DG warehouses, tight capacity. "
                    "Stresses both split reduction and capacity-aware vehicle selection.",
    ))

    # val_l04: Validation large, high locked ratio
    specs.append(InstanceSpec(
        name="instance_val_l04",
        role="validation", tier="large",
        master_seed=next_seed(),
        num_subcategories=6,
        orders_per_subcat=[18, 16, 16, 14, 14, 12],
        num_dg_warehouses=3,
        city_mix="dg_heavy",
        hazard_ratio=0.10,
        locked_ratio=0.40,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Validation large, 90 orders, 40% locked. "
                    "Heavily constrained search space tests operator robustness.",
    ))

    # ========================================================================
    # FROZEN HOLDOUT instances (4 total: 2 large, 2 xlarge)
    # ========================================================================

    # fro_l01: Frozen large, balanced
    specs.append(InstanceSpec(
        name="instance_fro_l01",
        role="frozen", tier="large",
        master_seed=next_seed(),
        num_subcategories=7,
        orders_per_subcat=[18, 17, 16, 15, 14, 13, 12],
        num_dg_warehouses=4,
        city_mix="dg_heavy",
        hazard_ratio=0.12,
        locked_ratio=0.15,
        spu_qty_range=(2, 6),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen holdout large, 105 orders, 7 subcats. "
                    "Balanced complexity for unbiased operator evaluation.",
    ))

    # fro_l02: Frozen large, challenging
    specs.append(InstanceSpec(
        name="instance_fro_l02",
        role="frozen", tier="large",
        master_seed=next_seed(),
        num_subcategories=6,
        orders_per_subcat=[22, 20, 20, 18, 16, 14],
        num_dg_warehouses=5,
        city_mix="mixed",
        hazard_ratio=0.20,
        locked_ratio=0.20,
        spu_qty_range=(2, 6),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen holdout large, 110 orders, 5 DG warehouses, "
                    "20% hazard + 20% locked. High-difficulty holdout.",
    ))

    # fro_x01: Frozen xlarge, stress test
    specs.append(InstanceSpec(
        name="instance_fro_x01",
        role="frozen", tier="xlarge",
        master_seed=next_seed(),
        num_subcategories=7,
        orders_per_subcat=[40, 38, 36, 34, 30, 28, 24],
        num_dg_warehouses=4,
        city_mix="dg_heavy",
        hazard_ratio=0.10,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen holdout xlarge, 230 orders. "
                    "Stress-tests solver scalability and operator effectiveness at scale.",
    ))

    # fro_x02: Frozen xlarge, maximum complexity
    specs.append(InstanceSpec(
        name="instance_fro_x02",
        role="frozen", tier="xlarge",
        master_seed=next_seed(),
        num_subcategories=8,
        orders_per_subcat=[50, 45, 42, 38, 35, 32, 28, 25],
        num_dg_warehouses=5,
        city_mix="mixed",
        hazard_ratio=0.15,
        locked_ratio=0.15,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen holdout xlarge, 295 orders, 8 subcats, 5 DG warehouses. "
                    "Maximum complexity stress test.",
    ))

    # ========================================================================
    # CANARY instances (2 total: both small)
    # ========================================================================

    # can_s01: Canary, compact but sufficient for discrimination
    specs.append(InstanceSpec(
        name="instance_can_s01",
        role="canary", tier="small",
        master_seed=next_seed(),
        num_subcategories=4,
        orders_per_subcat=[6, 6, 5, 5],
        num_dg_warehouses=3,
        city_mix="dg_only",
        hazard_ratio=0.0,
        locked_ratio=0.0,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Canary instance for regression detection. "
                    "4 subcats, 22 orders, known-good discriminative properties.",
    ))

    # can_s02: Canary, with hazard
    specs.append(InstanceSpec(
        name="instance_can_s02",
        role="canary", tier="small",
        master_seed=next_seed(),
        num_subcategories=4,
        orders_per_subcat=[5, 5, 4, 4],
        num_dg_warehouses=3,
        city_mix="dg_heavy",
        hazard_ratio=0.15,
        locked_ratio=0.10,
        spu_qty_range=(2, 5),
        num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Canary instance with hazard + locked orders. "
                    "Tests hazard-aware operator regression.",
    ))

    return specs


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_instance(
    filepath: Path,
    seeds: list[int] = [42, 137, 1042],
    max_iter: int = 100,
    time_limit_sec: int = 120,
) -> dict:
    """Validate that an instance is discriminative.

    Runs the solver with multiple seeds and checks:
      1. Greedy init produces a feasible solution
      2. At least 1 subcategory split exists in greedy solution
      3. Different seeds produce different VNS results

    Returns a validation report dict.
    """
    # Import solver components (must be on sys.path)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import Config
    from solver import load_instance, solve
    from oracle import recompute_objective, check_feasibility
    from greedy_init import greedy_init

    instance = load_instance(str(filepath))

    # Check greedy init feasibility and splits
    greedy_sol = greedy_init(instance)
    feas = check_feasibility(greedy_sol, instance, instance.phase)
    greedy_obj = recompute_objective(greedy_sol, instance)

    report = {
        "file": filepath.name,
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

    if greedy_obj.subcategory_splits == 0:
        print(f"  WARN: greedy has 0 splits — limited VNS improvement opportunity")

    # Run solver with different seeds
    results = []
    for seed in seeds:
        cfg = Config()
        cfg.random_seed = seed
        cfg.max_iterations = max_iter
        cfg.no_improve_limit = 20

        t0 = time.time()
        sol = solve(instance, cfg)
        elapsed = time.time() - t0

        obj = sol.objective
        result_key = f"seed_{seed}"
        report["seed_results"][result_key] = {
            "splits": obj.subcategory_splits,
            "cost": obj.total_cost,
            "time_sec": round(elapsed, 2),
        }
        results.append((obj.subcategory_splits, obj.total_cost))
        print(f"  seed={seed}: splits={obj.subcategory_splits}, "
              f"cost={obj.total_cost}, time={elapsed:.1f}s")

    # Check discriminativeness: at least 2 different results across seeds
    unique_results = set(results)
    report["unique_results"] = len(unique_results)
    report["is_discriminative"] = len(unique_results) >= 2

    if report["is_discriminative"]:
        print(f"  ✓ DISCRIMINATIVE ({len(unique_results)} unique results)")
    else:
        print(f"  ✗ NOT discriminative (all seeds produce same result)")

    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate discriminative benchmark instances for Scion v2"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="After generating, validate each instance by running the solver"
    )
    parser.add_argument(
        "--master-seed", type=int, default=20260408,
        help="Master seed for deterministic generation (default: 20260408)"
    )
    parser.add_argument(
        "--only", type=str, default=None,
        help="Generate only instances matching this prefix (e.g., 'scr_s')"
    )
    parser.add_argument(
        "--validate-seeds", type=str, default="42,137,1042",
        help="Comma-separated seeds for validation (default: 42,137,1042)"
    )
    parser.add_argument(
        "--max-iter", type=int, default=100,
        help="Max VNS iterations for validation (default: 100)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Scion v2 Instance Generator")
    print("=" * 70)

    specs = build_all_specs(args.master_seed)

    if args.only:
        specs = [s for s in specs if args.only in s.name]
        print(f"Filtered to {len(specs)} instances matching '{args.only}'")

    # Generate all instances
    generated_files: list[Path] = []
    for spec in specs:
        print(f"\n--- Generating {spec.name} ({spec.role}/{spec.tier}) ---")
        instance_data = generate_instance(spec)
        filepath = OUT_DIR / f"{spec.name}.json"
        filepath.write_text(json.dumps(instance_data, ensure_ascii=False, indent=2))
        generated_files.append(filepath)
        print(f"  -> {filepath.name}")

    print(f"\n{'=' * 70}")
    print(f"Generated {len(generated_files)} instances.")

    # Validate if requested
    if args.validate:
        val_seeds = [int(s) for s in args.validate_seeds.split(",")]
        print(f"\n{'=' * 70}")
        print(f"Validating instances (seeds={val_seeds}, max_iter={args.max_iter})")
        print(f"{'=' * 70}")

        reports: list[dict] = []
        for filepath in generated_files:
            print(f"\n--- Validating {filepath.name} ---")
            report = validate_instance(
                filepath, seeds=val_seeds, max_iter=args.max_iter
            )
            reports.append(report)

        # Summary
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
            print(f"  {status} [{feas}] {r['file']}: "
                  f"greedy_splits={r['greedy_splits']}, "
                  f"unique_results={r.get('unique_results', 0)}")

        # Save validation report
        report_path = OUT_DIR / "validation_report_v2.json"
        report_path.write_text(json.dumps(reports, indent=2))
        print(f"\nValidation report saved to {report_path.name}")


if __name__ == "__main__":
    main()
