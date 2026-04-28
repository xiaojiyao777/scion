from __future__ import annotations

import math
import random


class SimulatedAnnealing:
    """Geometric cooling simulated annealing acceptance rule."""

    def __init__(
        self,
        initial_cost: float,
        estimated_iterations: int,
        start_ratio: float = 0.05,
        end_ratio: float = 0.0001,
    ):
        base = max(float(initial_cost), 1.0)
        self.start_temp = max(base * start_ratio, 1e-9)
        self.end_temp = max(base * end_ratio, 1e-12)
        self.temperature = self.start_temp
        estimated_iterations = max(1, estimated_iterations)
        self.cooling_rate = (self.end_temp / self.start_temp) ** (1.0 / estimated_iterations)

    def accept(self, current_cost: float, candidate_cost: float, rng: random.Random) -> bool:
        delta = candidate_cost - current_cost
        if delta <= 0:
            return True
        if self.temperature <= 0:
            return False
        return rng.random() < math.exp(-delta / self.temperature)

    def cool(self) -> None:
        self.temperature = max(self.end_temp, self.temperature * self.cooling_rate)
