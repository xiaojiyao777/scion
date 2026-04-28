from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Iterable

from src.models import Route, Solution
from src.parser import parse_sol, parse_vrp


def _discover_vrp_files(data_path: Path, subsets: list[str] | None) -> list[Path]:
    if data_path.is_file():
        return [data_path] if data_path.suffix == ".vrp" else []

    if subsets:
        files: list[Path] = []
        for subset in subsets:
            subset_dir = data_path / subset
            if subset_dir.is_dir():
                files.extend(sorted(subset_dir.glob("*.vrp")))
        return files

    files = sorted(data_path.glob("*.vrp"))
    for subset_dir in sorted(p for p in data_path.iterdir() if p.is_dir()):
        files.extend(sorted(subset_dir.glob("*.vrp")))
    return files


def _read_header_value(path: Path, key: str) -> str:
    key = key.upper()
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.endswith("SECTION"):
                break
            if ":" not in stripped:
                continue
            name, _, value = stripped.partition(":")
            if name.strip().upper() == key:
                return value.strip()
    return ""


def _format_list(values: Iterable[int], max_items: int) -> str:
    ordered = list(values)
    shown = ordered[:max_items]
    suffix = "" if len(ordered) <= max_items else f";...(+{len(ordered) - max_items})"
    return ";".join(str(v) for v in shown) + suffix


def _format_counter(counter: Counter[int], max_items: int) -> str:
    items = [f"{customer}x{count}" for customer, count in sorted(counter.items())]
    shown = items[:max_items]
    suffix = "" if len(items) <= max_items else f";...(+{len(items) - max_items})"
    return ";".join(shown) + suffix


def validate_file(path: Path, tolerance: float, max_list_items: int) -> dict[str, object]:
    row: dict[str, object] = {
        "instance": path.stem,
        "subset": path.parent.name,
        "path": str(path),
        "sol_path": str(path.with_suffix(".sol")),
        "edge_weight_type": _read_header_value(path, "EDGE_WEIGHT_TYPE"),
        "dimension": "",
        "capacity": "",
        "status": "",
        "sol_exists": path.with_suffix(".sol").exists(),
        "bks_cost": "",
        "calculated_cost": "",
        "cost_diff": "",
        "route_count": "",
        "feasible": "",
        "missing_count": "",
        "duplicate_count": "",
        "invalid_customer_count": "",
        "over_capacity_count": "",
        "missing_customers": "",
        "duplicate_customers": "",
        "invalid_customers": "",
        "over_capacity_routes": "",
        "error": "",
    }

    try:
        instance = parse_vrp(str(path))
    except ValueError as exc:
        row["status"] = "unsupported" if "Unsupported EDGE_WEIGHT_TYPE" in str(exc) else "parse_error"
        row["error"] = str(exc)
        return row
    except Exception as exc:
        row["status"] = "parse_error"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    row["dimension"] = instance.dimension
    row["capacity"] = instance.capacity

    sol_path = path.with_suffix(".sol")
    if not sol_path.exists():
        row["status"] = "missing_sol"
        return row

    try:
        routes, bks_cost = parse_sol(str(sol_path))
    except Exception as exc:
        row["status"] = "sol_parse_error"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    row["bks_cost"] = bks_cost
    row["route_count"] = len(routes)

    seen = [customer for route in routes for customer in route]
    expected = set(range(1, instance.dimension))
    invalid = sorted(c for c in set(seen) if c < 1 or c >= instance.dimension)
    valid_seen = [c for c in seen if 1 <= c < instance.dimension]
    counts = Counter(valid_seen)
    duplicates = Counter({customer: count for customer, count in counts.items() if count > 1})
    missing = sorted(expected - set(valid_seen))

    row["missing_count"] = len(missing)
    row["duplicate_count"] = sum(count - 1 for count in duplicates.values())
    row["invalid_customer_count"] = len(invalid)
    row["missing_customers"] = _format_list(missing, max_list_items)
    row["duplicate_customers"] = _format_counter(duplicates, max_list_items)
    row["invalid_customers"] = _format_list(invalid, max_list_items)

    if invalid:
        row["status"] = "invalid_customer"
        row["feasible"] = False
        return row

    solution = Solution(instance, [Route(instance, route) for route in routes])
    over_capacity = [
        idx
        for idx, route in enumerate(solution.routes, start=1)
        if route.load > instance.capacity
    ]
    cost_diff = float(solution.total_cost - bks_cost)
    feasible = solution.is_feasible()

    row["calculated_cost"] = solution.total_cost
    row["cost_diff"] = cost_diff
    row["feasible"] = feasible
    row["over_capacity_count"] = len(over_capacity)
    row["over_capacity_routes"] = _format_list(over_capacity, max_list_items)

    if missing or duplicates or over_capacity or not feasible:
        row["status"] = "infeasible"
    elif abs(cost_diff) > tolerance:
        row["status"] = "cost_mismatch"
    else:
        row["status"] = "ok"

    return row


def run_validation(
    data_dir: str,
    subsets: list[str] | None,
    output_csv: str,
    tolerance: float,
    bad_only: bool,
    max_list_items: int,
) -> list[dict[str, object]]:
    paths = _discover_vrp_files(Path(data_dir), subsets)
    rows: list[dict[str, object]] = []
    counts: Counter[str] = Counter()

    for path in paths:
        row = validate_file(path, tolerance, max_list_items)
        counts[str(row["status"])] += 1
        if not bad_only or row["status"] != "ok":
            rows.append(row)

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "instance",
        "subset",
        "path",
        "sol_path",
        "edge_weight_type",
        "dimension",
        "capacity",
        "status",
        "sol_exists",
        "bks_cost",
        "calculated_cost",
        "cost_diff",
        "route_count",
        "feasible",
        "missing_count",
        "duplicate_count",
        "invalid_customer_count",
        "over_capacity_count",
        "missing_customers",
        "duplicate_customers",
        "invalid_customers",
        "over_capacity_routes",
        "error",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"checked={len(paths)} written={len(rows)} output={output_path}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CVRPLIB .sol reference routes")
    parser.add_argument("data_dir", nargs="?", default="cvrplib")
    parser.add_argument("--subsets", nargs="*", default=None)
    parser.add_argument("--output", default="results/reference_validation.csv")
    parser.add_argument("--tolerance", type=float, default=1e-2)
    parser.add_argument("--bad-only", action="store_true")
    parser.add_argument("--max-list-items", type=int, default=50)
    args = parser.parse_args()

    run_validation(
        data_dir=args.data_dir,
        subsets=args.subsets,
        output_csv=args.output,
        tolerance=args.tolerance,
        bad_only=args.bad_only,
        max_list_items=args.max_list_items,
    )


if __name__ == "__main__":
    main()
