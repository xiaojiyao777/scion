#!/usr/bin/env python3
"""
generate_v4_supplement.py — 补充实例生成，填补 v3 的规模空档。

新增实例：
  - Small (20-40 orders): 快速调试 & regression，screening/canary 补充
  - Medium-Large gap (70-100): screening 补充
  - XXLarge (800-1200): 压力测试，frozen/validation 补充
  - Extra frozen (各规模): 支持"每次 frozen 用全新实例"

Total: ~30 new instances across all roles and scales.
"""

from __future__ import annotations
import argparse
import json
import random
from pathlib import Path

# Reuse v3 generator
from generate_v3 import InstanceSpec, generate_instance

OUT_DIR = Path(__file__).parent


def build_supplement_specs(master_seed: int = 20260412) -> list[InstanceSpec]:
    rng = random.Random(master_seed)
    specs: list[InstanceSpec] = []

    def ns() -> int:
        return rng.randint(10000, 99999)

    # ================================================================
    # SMALL (20-40 orders) — 快速调试 & canary 补充
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v4_scr_s01", role="screening", tier="small",
        master_seed=ns(), num_subcategories=3,
        orders_per_subcat=[8, 7, 7],
        num_dg_warehouses=2, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(2, 4), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Small baseline, 22 orders, minimal complexity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_scr_s02", role="screening", tier="small",
        master_seed=ns(), num_subcategories=4,
        orders_per_subcat=[9, 8, 8, 7],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.15, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Small with hazard + locked, 32 orders.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_scr_s03", role="screening", tier="small",
        master_seed=ns(), num_subcategories=3,
        orders_per_subcat=[14, 13, 12],
        num_dg_warehouses=3, city_mix="mixed",
        hazard_ratio=0.10, locked_ratio=0.05,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="tight",
        description="Small-medium bridge, 39 orders, tight capacity.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_can_s01", role="canary", tier="small",
        master_seed=ns(), num_subcategories=3,
        orders_per_subcat=[8, 7, 6],
        num_dg_warehouses=2, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(2, 4), num_spus_range=(1, 2),
        capacity_pressure="loose",
        description="Ultra-fast canary, 21 orders.",
    ))

    # ================================================================
    # MEDIUM-LARGE GAP (70-100 orders) — screening 补充
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v4_scr_ml01", role="screening", tier="medium-large",
        master_seed=ns(), num_subcategories=5,
        orders_per_subcat=[16, 15, 15, 14, 13],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Gap filler, 73 orders, 5 subcats.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_scr_ml02", role="screening", tier="medium-large",
        master_seed=ns(), num_subcategories=6,
        orders_per_subcat=[16, 15, 14, 14, 13, 12],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.18, locked_ratio=0.20,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Gap filler, 84 orders, high hazard + locked.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_scr_ml03", role="screening", tier="medium-large",
        master_seed=ns(), num_subcategories=5,
        orders_per_subcat=[20, 19, 18, 17, 16],
        num_dg_warehouses=5, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(3, 6), num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Gap filler, 90 orders, 5 DG, tight, max split pressure.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_scr_ml04", role="screening", tier="medium-large",
        master_seed=ns(), num_subcategories=7,
        orders_per_subcat=[15, 14, 14, 13, 13, 12, 12],
        num_dg_warehouses=3, city_mix="dg_heavy",
        hazard_ratio=0.12, locked_ratio=0.08,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Gap filler, 93 orders, 7 subcats, high diversity.",
    ))

    # ================================================================
    # XXLARGE (800-1200 orders) — 压力测试
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v4_val_xx01", role="validation", tier="xxlarge",
        master_seed=ns(), num_subcategories=10,
        orders_per_subcat=[95, 90, 85, 80, 75, 70, 65, 60, 55, 50],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation xxlarge, 725 orders, 10 subcats, scale stress test.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_val_xx02", role="validation", tier="xxlarge",
        master_seed=ns(), num_subcategories=8,
        orders_per_subcat=[130, 120, 110, 105, 100, 95, 85, 80],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.15, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation xxlarge, 825 orders, extreme scale.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_xxx01", role="frozen", tier="xxxlarge",
        master_seed=ns(), num_subcategories=10,
        orders_per_subcat=[120, 115, 110, 105, 100, 95, 90, 85, 80, 75],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.12, locked_ratio=0.12,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xxxlarge, 975 orders, ultimate holdout.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_xxx02", role="frozen", tier="xxxlarge",
        master_seed=ns(), num_subcategories=12,
        orders_per_subcat=[110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55],
        num_dg_warehouses=5, city_mix="dg_heavy",
        hazard_ratio=0.18, locked_ratio=0.20,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="tight",
        description="Frozen xxxlarge, 990 orders, 12 subcats, max complexity.",
    ))

    # ================================================================
    # EXTRA FROZEN — 各规模补充，支持"每次 frozen 用全新实例"
    # ================================================================

    # Extra frozen medium (快速 frozen, 用于早期 campaign)
    specs.append(InstanceSpec(
        name="instance_v4_fro_m01", role="frozen", tier="medium",
        master_seed=ns(), num_subcategories=5,
        orders_per_subcat=[14, 13, 12, 11, 10],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.05,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen medium, 60 orders, fast holdout.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_m02", role="frozen", tier="medium",
        master_seed=ns(), num_subcategories=6,
        orders_per_subcat=[13, 12, 11, 11, 10, 10],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.15, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 2),
        capacity_pressure="moderate",
        description="Frozen medium, 67 orders, higher diversity.",
    ))

    # Extra frozen large
    specs.append(InstanceSpec(
        name="instance_v4_fro_l03", role="frozen", tier="large",
        master_seed=ns(), num_subcategories=5,
        orders_per_subcat=[42, 38, 36, 34, 30],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.08, locked_ratio=0.15,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen large, 180 orders, 5 subcats.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_l04", role="frozen", tier="large",
        master_seed=ns(), num_subcategories=7,
        orders_per_subcat=[32, 30, 28, 26, 24, 22, 20],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(3, 6), num_spus_range=(2, 3),
        capacity_pressure="tight",
        description="Frozen large, 182 orders, clean + tight, max split signal.",
    ))

    # Extra frozen xlarge (不同参数组合)
    specs.append(InstanceSpec(
        name="instance_v4_fro_x05", role="frozen", tier="xlarge",
        master_seed=ns(), num_subcategories=8,
        orders_per_subcat=[55, 52, 48, 46, 44, 42, 40, 38],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xlarge, 365 orders, 8 subcats, balanced.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_x06", role="frozen", tier="xlarge",
        master_seed=ns(), num_subcategories=6,
        orders_per_subcat=[75, 70, 65, 60, 55, 50],
        num_dg_warehouses=5, city_mix="dg_only",
        hazard_ratio=0.0, locked_ratio=0.0,
        spu_qty_range=(3, 7), num_spus_range=(2, 4),
        capacity_pressure="overflow",
        description="Frozen xlarge, 375 orders, overflow capacity, extreme split pressure.",
    ))

    # Extra frozen xxlarge
    specs.append(InstanceSpec(
        name="instance_v4_fro_xx03", role="frozen", tier="xxlarge",
        master_seed=ns(), num_subcategories=9,
        orders_per_subcat=[75, 72, 68, 65, 62, 58, 55, 52, 48],
        num_dg_warehouses=5, city_mix="mixed",
        hazard_ratio=0.14, locked_ratio=0.08,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Frozen xxlarge, 555 orders, 9 subcats.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_fro_xx04", role="frozen", tier="xxlarge",
        master_seed=ns(), num_subcategories=8,
        orders_per_subcat=[95, 90, 85, 80, 75, 70, 65, 60],
        num_dg_warehouses=4, city_mix="dg_heavy",
        hazard_ratio=0.20, locked_ratio=0.25,
        spu_qty_range=(2, 6), num_spus_range=(1, 3),
        capacity_pressure="tight",
        description="Frozen xxlarge, 620 orders, high hazard + locked + tight.",
    ))

    # ================================================================
    # EXTRA VALIDATION — 补充覆盖度
    # ================================================================

    specs.append(InstanceSpec(
        name="instance_v4_val_m01", role="validation", tier="medium",
        master_seed=ns(), num_subcategories=5,
        orders_per_subcat=[16, 15, 14, 13, 12],
        num_dg_warehouses=3, city_mix="dg_only",
        hazard_ratio=0.10, locked_ratio=0.10,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation medium, 70 orders, fast validation.",
    ))

    specs.append(InstanceSpec(
        name="instance_v4_val_m02", role="validation", tier="medium",
        master_seed=ns(), num_subcategories=6,
        orders_per_subcat=[17, 16, 15, 14, 13, 12],
        num_dg_warehouses=4, city_mix="mixed",
        hazard_ratio=0.15, locked_ratio=0.15,
        spu_qty_range=(2, 5), num_spus_range=(1, 3),
        capacity_pressure="moderate",
        description="Validation medium, 87 orders, higher diversity.",
    ))

    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v4 supplement instances")
    parser.add_argument("--master-seed", type=int, default=20260412)
    parser.add_argument("--dry-run", action="store_true", help="Print specs without generating")
    args = parser.parse_args()

    print("=" * 70)
    print("Scion v4 Supplement Instance Generator")
    print("=" * 70)

    specs = build_supplement_specs(args.master_seed)

    if args.dry_run:
        for s in specs:
            total_orders = sum(s.orders_per_subcat)
            print(f"  {s.name:40s} {s.role:12s} {s.tier:12s} n={total_orders}")
        print(f"\nTotal: {len(specs)} instances")
        return

    generated = []
    for spec in specs:
        print(f"\n--- Generating {spec.name} ({spec.role}/{spec.tier}) ---")
        instance_data = generate_instance(spec)
        filepath = OUT_DIR / f"{spec.name}.json"
        filepath.write_text(json.dumps(instance_data, ensure_ascii=False, indent=2))
        generated.append(filepath)

    print(f"\n{'=' * 70}")
    print(f"Generated {len(generated)} supplement instances.")

    # Summary by role
    from collections import Counter
    role_count = Counter(s.role for s in specs)
    for role, count in sorted(role_count.items()):
        print(f"  {role:12s}: {count}")


if __name__ == "__main__":
    main()
