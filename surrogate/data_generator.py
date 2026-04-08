import json
import random
import math
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional

# --- Constants from Spec ---

VEHICLE_TYPES = {
    "HQ40_DG": {"capacity": 40, "cost": 6600, "is_hazard_special": True},
    "HQ40": {"capacity": 40, "cost": 3300, "is_hazard_special": False},
    "T10": {"capacity": 14, "cost": 1800, "is_hazard_special": False},
    "T5": {"capacity": 6, "cost": 1200, "is_hazard_special": False},
    "T3": {"capacity": 3, "cost": 800, "is_hazard_special": False},
}

REGIONS = {
    "Dongguan": {
        "warehouses": ["SKD_WH", "FG_CENTRAL_WH", "DG_NORTH_WH"],
        "max_pickups": 2
    },
    "Shenzhen": {
        "warehouses": ["SZ_WH", "SZ_FG_WH"],
        "max_pickups": 3
    }
}

DESTINATION_COUNTRIES = ["Germany", "UK", "France", "India", "Brazil", "Mexico", "Japan", "South Korea", "UAE", "South Africa"]
LSPS = ["DHL", "Maersk", "COSCO", "SF_INTL", "DB Schenker"]
SHIP_METHODS = ["SEA", "AIR", "RAIL", "ROAD"]
PACKING_TYPES = ["FULL_PLT", "TAILGATE", "WOOD_CASE", "FULL_CTN", "LOOSE_CTN"]

# --- Data Structures ---

@dataclass
class SPU:
    packing_type: str
    quantity: int

@dataclass
class Order:
    order_id: str
    vehicle_category: int
    vehicle_subcategory: int
    urgent: bool
    hazard_flag: bool
    hazard_quantity: int
    pickup_name: str
    pickup_province: str
    pickup_city: str
    declaration_amount: float
    lsp: str
    ship_method: str
    destination_country: str
    spu_list: List[SPU]
    locked_vehicle_id: Optional[str] = None

@dataclass
class Instance:
    orders: List[Order]
    amount_limits: Dict[str, float]  # Keyed by "country,ship_method"
    vehicle_types: Dict[str, Any] = field(default_factory=lambda: VEHICLE_TYPES)

# --- Generator Logic ---

class DataGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_instance(self, 
                          num_orders: int = 50, 
                          num_categories: int = 3, 
                          num_subcategories: int = 12,
                          hazard_ratio: float = 0.15,
                          locked_ratio: float = 0.2) -> Dict[str, Any]:
        
        # 1. Generate Subcategory Definitions
        # A subcategory is a combination of Region, LSP, Country, Ship Method
        subcategories = []
        for i in range(num_subcategories):
            region_name = self.rng.choice(list(REGIONS.keys()))
            subcategories.append({
                "id": i,
                "category": self.rng.randint(0, num_categories - 1),
                "region": region_name,
                "warehouse": self.rng.choice(REGIONS[region_name]["warehouses"]),
                "lsp": self.rng.choice(LSPS),
                "country": self.rng.choice(DESTINATION_COUNTRIES),
                "ship_method": self.rng.choice(SHIP_METHODS)
            })

        # 2. Generate Orders
        orders = []
        # 跟踪锁定车辆的已用栈板数，确保不超过最大容量(40)
        locked_vehicle_pallets: Dict[str, int] = {}  # vehicle_id -> used_pallets
        locked_vehicle_counter: Dict[int, int] = {}   # subcat_id -> next_vehicle_seq
        MAX_LOCKED_CAPACITY = 40

        for i in range(num_orders):
            subcat = self.rng.choice(subcategories)
            is_hazard = self.rng.random() < hazard_ratio
            hazard_qty = self.rng.randint(100, 3000) if is_hazard else 0
            
            # SPU list: 1~8 SPUs (reduced from 1~20 to keep pallets per order reasonable)
            num_spus = self.rng.randint(1, 8)
            spu_list = []
            for _ in range(num_spus):
                spu_list.append(SPU(
                    packing_type=self.rng.choice(PACKING_TYPES),
                    quantity=self.rng.randint(1, 5)
                ))
            
            # 计算该订单的栈板数
            order_pallets = 0
            boxes = 0
            for s in spu_list:
                if s.packing_type in ('FULL_PLT', 'TAILGATE', 'WOOD_CASE'):
                    order_pallets += s.quantity
                else:
                    boxes += s.quantity
            order_pallets += math.ceil(boxes / 8) if boxes > 0 else 0

            is_locked = self.rng.random() < locked_ratio
            locked_id = None
            if is_locked:
                # 找到或创建一个有足够剩余容量的锁定车辆
                subcat_id = subcat['id']
                if subcat_id not in locked_vehicle_counter:
                    locked_vehicle_counter[subcat_id] = 0
                
                # 尝试放入已有的锁定车辆
                placed = False
                seq = locked_vehicle_counter[subcat_id]
                for s in range(seq + 1):
                    candidate_id = f"V_LOCKED_{subcat_id}_{s}"
                    used = locked_vehicle_pallets.get(candidate_id, 0)
                    if used + order_pallets <= MAX_LOCKED_CAPACITY:
                        locked_id = candidate_id
                        locked_vehicle_pallets[candidate_id] = used + order_pallets
                        placed = True
                        break
                
                if not placed:
                    # 新建一辆锁定车辆
                    new_seq = seq + 1
                    locked_vehicle_counter[subcat_id] = new_seq
                    locked_id = f"V_LOCKED_{subcat_id}_{new_seq}"
                    locked_vehicle_pallets[locked_id] = order_pallets

            order = Order(
                order_id=f"ORD_{i:04d}",
                vehicle_category=subcat["category"],
                vehicle_subcategory=subcat["id"],
                urgent=self.rng.random() < 0.1,
                hazard_flag=is_hazard,
                hazard_quantity=hazard_qty,
                pickup_name=subcat["warehouse"],
                pickup_province="Guangdong", # Fixed for simplicity
                pickup_city=subcat["region"],
                declaration_amount=round(self.rng.uniform(10000, 500000), 2),
                lsp=subcat["lsp"],
                ship_method=subcat["ship_method"],
                destination_country=subcat["country"],
                spu_list=spu_list,
                locked_vehicle_id=locked_id
            )
            orders.append(order)

        # 3. Generate Amount Limits (Baseline)
        # Key: "Country,ShipMethod"
        # 计算每个(country, ship_method)维度的最大单订单金额，基线设为 3~6 倍最大单订单金额
        # 确保贪心初始解基本可行
        amount_limits = {}
        combo_max_amount: Dict[str, float] = {}
        for o in orders:
            key = f"{o.destination_country},{o.ship_method}"
            combo_max_amount[key] = max(combo_max_amount.get(key, 0), o.declaration_amount)
        for key, max_amt in combo_max_amount.items():
            # 基线 = 最大单订单 * 3~6 倍，保证同车内多个订单不轻易超标
            multiplier = self.rng.uniform(3.0, 6.0)
            amount_limits[key] = round(max_amt * multiplier, 2)

        # 4. Assemble Instance
        instance = {
            "orders": [asdict(o) for o in orders],
            "amount_limits": amount_limits,
            "vehicle_types": VEHICLE_TYPES
        }
        return instance

def save_instance(instance: Dict[str, Any], path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(instance, f, ensure_ascii=False, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data for Scion surrogate solver.")
    parser.add_argument("--output-dir", type=str, default="./data/", help="Directory to save generated JSON files.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = DataGenerator()

    configs = {
        "small": {"num_orders": 20, "num_categories": 2, "num_subcategories": 5},
        "medium": {"num_orders": 80, "num_categories": 3, "num_subcategories": 12},
        "large": {"num_orders": 200, "num_categories": 5, "num_subcategories": 20}
    }

    for size, config in configs.items():
        for i in range(1, 4):
            filename = f"instance_{size}_{i}.json"
            instance = generator.generate_instance(**config)
            save_instance(instance, output_dir / filename)
            print(f"Generated {output_dir / filename}")

if __name__ == "__main__":
    main()
