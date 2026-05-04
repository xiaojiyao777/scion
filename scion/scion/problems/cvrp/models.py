"""CVRP data models used by the Scion adapter and tiny fixtures."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any


@dataclass(frozen=True)
class CvrpNode:
    id: int
    x: float
    y: float
    demand: int


@dataclass(frozen=True)
class CvrpInstance:
    name: str
    capacity: int
    depot: int
    nodes: tuple[CvrpNode, ...]
    allowed_routes: int | None = None
    bks: float | None = None
    bks_routes: int | None = None
    use_integer_cost: bool = True

    @property
    def node_ids(self) -> tuple[int, ...]:
        return tuple(n.id for n in self.nodes)

    @property
    def customer_ids(self) -> tuple[int, ...]:
        return tuple(n.id for n in self.nodes if n.id != self.depot)

    def demand(self, node_id: int) -> int:
        return self._node(node_id).demand

    def distance(self, i: int, j: int) -> float:
        a = self._node(i)
        b = self._node(j)
        d = math.hypot(a.x - b.x, a.y - b.y)
        return float(math.floor(d + 0.5)) if self.use_integer_cost else d

    def route_load(self, route: tuple[int, ...]) -> int:
        return sum(self.demand(c) for c in route)

    def route_distance(self, route: tuple[int, ...]) -> float:
        total = 0.0
        prev = self.depot
        for customer in route:
            total += self.distance(prev, customer)
            prev = customer
        total += self.distance(prev, self.depot)
        return total

    def _node(self, node_id: int) -> CvrpNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"unknown node id: {node_id}")

    @classmethod
    def from_json(cls, path: str) -> CvrpInstance:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        nodes = tuple(
            CvrpNode(
                id=int(item["id"]),
                x=float(item["x"]),
                y=float(item["y"]),
                demand=int(item.get("demand", 0)),
            )
            for item in data["nodes"]
        )
        ids = [n.id for n in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node ids")
        depot = int(data.get("depot", 0))
        if depot not in ids:
            raise ValueError(f"depot id {depot} not in nodes")

        return cls(
            name=str(data.get("name", "cvrp_instance")),
            capacity=int(data["capacity"]),
            depot=depot,
            nodes=nodes,
            allowed_routes=(
                int(data["allowed_routes"])
                if data.get("allowed_routes") is not None
                else None
            ),
            bks=(float(data["bks"]) if data.get("bks") is not None else None),
            bks_routes=(
                int(data["bks_routes"])
                if data.get("bks_routes") is not None
                else None
            ),
            use_integer_cost=bool(data.get("use_integer_cost", True)),
        )


@dataclass(frozen=True)
class CvrpSolution:
    """Implicit-depot CVRP solution: each route lists customers only."""

    routes: tuple[tuple[int, ...], ...]

