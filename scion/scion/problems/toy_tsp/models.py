"""Toy TSP models — minimal for adapter validation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math


@dataclass(frozen=True)
class TspInstance:
    n: int
    coords: tuple[tuple[float, float], ...]

    def distance(self, i: int, j: int) -> float:
        ax, ay = self.coords[i]
        bx, by = self.coords[j]
        return math.hypot(ax - bx, ay - by)

    @classmethod
    def from_json(cls, path: str) -> TspInstance:
        with open(path) as f:
            data = json.load(f)
        coords = tuple(tuple(c) for c in data["coords"])
        return cls(n=len(coords), coords=coords)


@dataclass(frozen=True)
class TspSolution:
    tour: tuple[int, ...]
    cost: float
