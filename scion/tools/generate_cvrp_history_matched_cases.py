"""Generate the fixed synthetic CVRP inputs for the history matched study.

The generator is intentionally closed over the constants in this module.  It
does not enumerate CVRPLIB, read campaign artifacts, or inspect solver
outcomes.  Feasibility is constructive: customers are partitioned in id order
into groups of at most ``CUSTOMERS_PER_ROUTE`` and every generated demand is
bounded so each such route fits the declared capacity.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NAMESPACE = "scion_generated/cvrp_history_matched_v1"
CAPACITY = 80
CUSTOMERS_PER_ROUTE = 10
DEMAND_LOW = 4
DEMAND_HIGH = 12
DEMAND_BASE = 8
STRUCTURES = ("uniform", "clustered", "radial")


@dataclass(frozen=True)
class CaseSpec:
    block: int
    position: int
    structure: str
    dimension: int
    seed: int
    capacity: int
    allowed_routes: int
    demand_low: int = DEMAND_LOW
    demand_high: int = DEMAND_HIGH

    @property
    def customer_count(self) -> int:
        return self.dimension - 1

    @property
    def filename(self) -> str:
        return (
            f"block_{self.block:02d}_pos_{self.position}_"
            f"{self.structure}_n{self.dimension:04d}_s{self.seed}.json"
        )

    @property
    def relative_path(self) -> str:
        return f"{NAMESPACE}/{self.filename}"


CASE_SPECS: tuple[CaseSpec, ...] = (
    CaseSpec(1, 0, "uniform", 61, 41001, CAPACITY, 6),
    CaseSpec(1, 1, "clustered", 126, 41002, CAPACITY, 13),
    CaseSpec(1, 2, "radial", 241, 41003, CAPACITY, 24),
    CaseSpec(1, 3, "uniform", 361, 41004, CAPACITY, 36),
    CaseSpec(1, 4, "clustered", 481, 41005, CAPACITY, 48),
    CaseSpec(1, 5, "radial", 721, 41006, CAPACITY, 72),
    CaseSpec(2, 0, "clustered", 67, 42001, CAPACITY, 7),
    CaseSpec(2, 1, "radial", 137, 42002, CAPACITY, 14),
    CaseSpec(2, 2, "uniform", 257, 42003, CAPACITY, 26),
    CaseSpec(2, 3, "clustered", 377, 42004, CAPACITY, 38),
    CaseSpec(2, 4, "radial", 497, 42005, CAPACITY, 50),
    CaseSpec(2, 5, "uniform", 737, 42006, CAPACITY, 74),
    CaseSpec(3, 0, "radial", 73, 43001, CAPACITY, 8),
    CaseSpec(3, 1, "uniform", 149, 43002, CAPACITY, 15),
    CaseSpec(3, 2, "clustered", 273, 43003, CAPACITY, 28),
    CaseSpec(3, 3, "radial", 393, 43004, CAPACITY, 40),
    CaseSpec(3, 4, "uniform", 513, 43005, CAPACITY, 52),
    CaseSpec(3, 5, "clustered", 753, 43006, CAPACITY, 76),
    CaseSpec(4, 0, "uniform", 79, 44001, CAPACITY, 8),
    CaseSpec(4, 1, "clustered", 161, 44002, CAPACITY, 16),
    CaseSpec(4, 2, "radial", 289, 44003, CAPACITY, 29),
    CaseSpec(4, 3, "uniform", 409, 44004, CAPACITY, 41),
    CaseSpec(4, 4, "clustered", 529, 44005, CAPACITY, 53),
    CaseSpec(4, 5, "radial", 769, 44006, CAPACITY, 77),
    CaseSpec(5, 0, "clustered", 83, 45001, CAPACITY, 9),
    CaseSpec(5, 1, "radial", 173, 45002, CAPACITY, 18),
    CaseSpec(5, 2, "uniform", 307, 45003, CAPACITY, 31),
    CaseSpec(5, 3, "clustered", 421, 45004, CAPACITY, 42),
    CaseSpec(5, 4, "radial", 547, 45005, CAPACITY, 55),
    CaseSpec(5, 5, "uniform", 787, 45006, CAPACITY, 79),
)


def specs_for_block(block: int) -> tuple[CaseSpec, ...]:
    return tuple(spec for spec in CASE_SPECS if spec.block == block)


def spec_by_relative_path(relative_path: str) -> CaseSpec | None:
    return next(
        (spec for spec in CASE_SPECS if spec.relative_path == relative_path),
        None,
    )


def constructive_routes(spec: CaseSpec) -> tuple[tuple[int, ...], ...]:
    customers = tuple(range(1, spec.dimension))
    return tuple(
        customers[index : index + CUSTOMERS_PER_ROUTE]
        for index in range(0, len(customers), CUSTOMERS_PER_ROUTE)
    )


def generate_case(spec: CaseSpec) -> dict[str, Any]:
    _validate_spec(spec)
    rng = random.Random(spec.seed)
    demands = _generate_demands(spec)
    occupied = {(500, 500)}
    nodes: list[dict[str, int]] = [{"id": 0, "x": 500, "y": 500, "demand": 0}]
    for customer in range(1, spec.dimension):
        x, y = _customer_point(
            structure=spec.structure,
            customer=customer,
            customer_count=spec.customer_count,
            rng=rng,
        )
        x, y = _deduplicate_point(x, y, occupied)
        occupied.add((x, y))
        nodes.append(
            {
                "id": customer,
                "x": x,
                "y": y,
                "demand": demands[customer - 1],
            }
        )
    payload: dict[str, Any] = {
        "name": spec.filename.removesuffix(".json"),
        "capacity": spec.capacity,
        "depot": 0,
        "allowed_routes": spec.allowed_routes,
        "bks": None,
        "bks_routes": None,
        "use_integer_cost": True,
        "nodes": nodes,
    }
    _validate_constructive_feasibility(spec, payload)
    return payload


def render_case(spec: CaseSpec) -> str:
    return json.dumps(generate_case(spec), indent=2, ensure_ascii=False) + "\n"


def write_cases(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    expected = {spec.filename for spec in CASE_SPECS}
    unexpected = sorted(
        path.name for path in output_root.iterdir() if path.name not in expected
    )
    if unexpected:
        raise ValueError(
            f"generated namespace contains unexpected file: {unexpected[0]}"
        )
    for spec in CASE_SPECS:
        (output_root / spec.filename).write_text(
            render_case(spec),
            encoding="utf-8",
        )


def check_cases(output_root: Path) -> tuple[str, ...]:
    expected = {spec.filename for spec in CASE_SPECS}
    actual = (
        {path.name for path in output_root.iterdir()} if output_root.is_dir() else set()
    )
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"generated namespace mismatch: missing={missing} extra={extra}"
        )
    checked: list[str] = []
    for spec in CASE_SPECS:
        path = output_root / spec.filename
        if path.read_text(encoding="utf-8") != render_case(spec):
            raise ValueError(f"generated case differs from fixed regeneration: {path}")
        checked.append(spec.relative_path)
    return tuple(checked)


def _validate_spec(spec: CaseSpec) -> None:
    if spec.structure not in STRUCTURES:
        raise ValueError(f"unsupported structure: {spec.structure}")
    if spec.dimension <= 1:
        raise ValueError("dimension must include a depot and at least one customer")
    if not 0 < spec.demand_low <= spec.demand_high:
        raise ValueError("demand bounds must be positive and ordered")
    if not spec.demand_low <= DEMAND_BASE <= spec.demand_high:
        raise ValueError("base demand must be inside the declared demand bounds")
    expected_routes = math.ceil(spec.customer_count / CUSTOMERS_PER_ROUTE)
    if spec.allowed_routes != expected_routes:
        raise ValueError("allowed_routes must equal the constructive route count")


def _validate_constructive_feasibility(
    spec: CaseSpec,
    payload: dict[str, Any],
) -> None:
    demands = {int(node["id"]): int(node["demand"]) for node in payload["nodes"]}
    routes = constructive_routes(spec)
    if len(routes) > spec.allowed_routes:
        raise ValueError("constructive witness exceeds allowed_routes")
    if any(
        sum(demands[customer] for customer in route) > spec.capacity for route in routes
    ):
        raise ValueError("constructive witness exceeds capacity")
    for route in routes:
        route_load = sum(demands[customer] for customer in route)
        expected_load = DEMAND_BASE * len(route)
        if route_load != expected_load:
            raise ValueError("constructive route load differs from its fixed target")
    covered = tuple(customer for route in routes for customer in route)
    if covered != tuple(range(1, spec.dimension)):
        raise ValueError("constructive witness does not cover each customer once")


def _generate_demands(spec: CaseSpec) -> tuple[int, ...]:
    """Return the fixed BFD-packable 12/4 pairs, with an odd 8 tail."""

    demands: list[int] = []
    for route in constructive_routes(spec):
        pairs, odd = divmod(len(route), 2)
        values = [value for _ in range(pairs) for value in (12, 4)]
        if odd:
            values.append(DEMAND_BASE)
        demands.extend(values)
    return tuple(demands)


def _customer_point(
    *,
    structure: str,
    customer: int,
    customer_count: int,
    rng: random.Random,
) -> tuple[int, int]:
    if structure == "uniform":
        return rng.randint(20, 980), rng.randint(20, 980)
    if structure == "clustered":
        centers = (
            (230, 230),
            (770, 230),
            (230, 770),
            (770, 770),
            (500, 180),
            (500, 820),
        )
        center_x, center_y = centers[(customer - 1) % len(centers)]
        return (
            _clamp(center_x + rng.randint(-95, 95)),
            _clamp(center_y + rng.randint(-95, 95)),
        )
    if structure == "radial":
        band = (170, 290, 410)[(customer - 1) % 3]
        angle = 2.0 * math.pi * (customer - 1) / max(1, customer_count) + rng.uniform(
            -0.025, 0.025
        )
        return (
            _clamp(round(500 + band * math.cos(angle))),
            _clamp(round(500 + band * math.sin(angle))),
        )
    raise ValueError(f"unsupported structure: {structure}")


def _deduplicate_point(
    x: int,
    y: int,
    occupied: set[tuple[int, int]],
) -> tuple[int, int]:
    for offset in range(1001):
        candidate = (_clamp(x + offset), _clamp(y + (offset * 37) % 101))
        if candidate not in occupied:
            return candidate
    raise ValueError("could not allocate a unique coordinate")


def _clamp(value: int) -> int:
    return max(0, min(1000, int(value)))


def _default_output_root() -> Path:
    return Path(__file__).resolve().parents[2] / "vrp" / NAMESPACE


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=_default_output_root())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.write:
            write_cases(args.output_root)
        checked = check_cases(args.output_root)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"INVALID: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": "exact_regeneration_match",
                "namespace": NAMESPACE,
                "cases": len(checked),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
